"""
Repository DuckDB natif pour les données joueur.
(Native DuckDB repository for player data)

HOW IT WORKS:
Ce repository utilise exclusivement DuckDB :
1. data/warehouse/metadata.duckdb : Référentiels (playlists, maps, médailles)
2. data/players/{gamertag}/stats.duckdb : Données joueur (matchs, médailles, etc.)
3. data/players/{gamertag}/archive/*.parquet : Archives (cold storage)

Les jointures entre les deux DBs sont faites via ATTACH.
Les archives Parquet peuvent être lues via `load_matches_from_archives()`.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from src.data.domain.models.stats import MatchRow
from src.data.repositories._antagonists_repo import AntagonistsMixin
from src.data.repositories._arrow_bridge import result_to_polars
from src.data.repositories._match_queries import MatchQueriesMixin
from src.data.repositories._materialized_views import MaterializedViewsMixin
from src.data.repositories._roster_loader import RosterLoaderMixin

logger = logging.getLogger(__name__)


class DuckDBRepository(
    MatchQueriesMixin,
    RosterLoaderMixin,
    MaterializedViewsMixin,
    AntagonistsMixin,
):
    """
    Repository utilisant DuckDB natif exclusivement.
    (Repository using native DuckDB exclusively)

    Lit depuis :
    - metadata.duckdb : Tables de référence
    - stats.duckdb : Données du joueur (matchs, médailles, etc.)
    """

    def __init__(
        self,
        player_db_path: str | Path,
        xuid: str,
        *,
        metadata_db_path: str | Path | None = None,
        shared_db_path: str | Path | None = None,
        gamertag: str | None = None,
        read_only: bool = True,
        memory_limit: str = "512MB",
    ) -> None:
        """
        Initialise le repository DuckDB.
        (Initialize DuckDB repository)

        Args:
            player_db_path: Chemin vers stats.duckdb du joueur
            xuid: XUID du joueur
            metadata_db_path: Chemin vers metadata.duckdb (auto-détecté si None)
            shared_db_path: Chemin vers shared_matches.duckdb (auto-détecté si None)
            gamertag: Gamertag du joueur (optionnel, pour logging)
            read_only: Si True, connexion en lecture seule
            memory_limit: Limite mémoire DuckDB
        """
        self._player_db_path = Path(player_db_path)
        self._xuid = xuid
        self._gamertag = gamertag
        self._read_only = read_only
        self._memory_limit = memory_limit

        # Auto-détection du chemin metadata.duckdb
        if metadata_db_path is None:
            # Cherche dans data/warehouse/metadata.duckdb
            data_dir = self._player_db_path.parent.parent.parent
            self._metadata_db_path = data_dir / "warehouse" / "metadata.duckdb"
        else:
            self._metadata_db_path = Path(metadata_db_path)

        # Auto-détection du chemin shared_matches.duckdb (v5)
        if shared_db_path is None:
            data_dir = self._player_db_path.parent.parent.parent
            self._shared_db_path = data_dir / "warehouse" / "shared_matches.duckdb"
        else:
            self._shared_db_path = Path(shared_db_path)

        # Connexion DuckDB (lazy loading)
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._attached_dbs: set[str] = set()

    @property
    def xuid(self) -> str:
        """XUID du joueur principal."""
        return self._xuid

    @property
    def db_path(self) -> str:
        """Chemin vers la base de données joueur."""
        return str(self._player_db_path)

    @property
    def has_shared(self) -> bool:
        """Indique si shared_matches.duckdb est attaché et disponible."""
        return "shared" in self._attached_dbs

    def _has_shared_table(self, table_name: str) -> bool:
        """Vérifie si une table existe dans shared_matches.duckdb.

        Args:
            table_name: Nom de la table à vérifier (sans préfixe 'shared.').

        Returns:
            True si la table existe dans le schema shared.
        """
        conn = self._get_connection()
        if not self.has_shared:
            return False
        try:
            result = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog = 'shared' AND table_name = ?",
                [table_name],
            ).fetchone()
            return result is not None
        except Exception:
            return False

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """
        Retourne une connexion DuckDB vers la DB joueur.
        (Returns DuckDB connection to player DB)
        """
        if self._connection is None:
            if not self._player_db_path.exists():
                raise FileNotFoundError(
                    f"Base de données joueur non trouvée: {self._player_db_path}"
                )

            # Connexion à la DB joueur
            self._connection = duckdb.connect(
                str(self._player_db_path),
                read_only=self._read_only,
            )

            # Configuration
            self._connection.execute(f"SET memory_limit = '{self._memory_limit}'")
            self._connection.execute("SET enable_object_cache = true")

            # Attacher la DB metadata si elle existe et pas déjà attachée
            if self._metadata_db_path.exists() and "meta" not in self._attached_dbs:
                try:
                    self._connection.execute(
                        f"ATTACH '{self._metadata_db_path}' AS meta (READ_ONLY)"
                    )
                    self._attached_dbs.add("meta")
                    logger.debug(f"Metadata DB attachée: {self._metadata_db_path}")
                except Exception as e:
                    err_str = str(e)
                    # DuckDB 1.4+ : le même fichier ne peut être attaché qu'à une seule connexion.
                    # Si déjà ouvert ailleurs (autre DuckDBRepository, MetadataResolver), ignorer silencieusement.
                    if (
                        "already exists" in err_str.lower()
                        or "unique file handle conflict" in err_str.lower()
                        or "already attached" in err_str.lower()
                    ):
                        logger.debug(
                            "metadata.duckdb déjà ouvert par une autre connexion, "
                            "résolution métadonnées désactivée pour cette instance"
                        )
                    else:
                        logger.warning(f"Impossible d'attacher metadata.duckdb: {e}")

            # Attacher shared_matches.duckdb en lecture seule (v5)
            if self._shared_db_path.exists() and "shared" not in self._attached_dbs:
                try:
                    self._connection.execute(
                        f"ATTACH '{self._shared_db_path}' AS shared (READ_ONLY)"
                    )
                    self._attached_dbs.add("shared")
                    logger.debug(f"Shared matches DB attachée: {self._shared_db_path}")
                except Exception as e:
                    err_str = str(e)
                    if (
                        "already exists" in err_str.lower()
                        or "unique file handle conflict" in err_str.lower()
                        or "already attached" in err_str.lower()
                    ):
                        logger.debug(
                            "shared_matches.duckdb déjà ouvert par une autre connexion, "
                            "lecture partagée désactivée pour cette instance"
                        )
                    else:
                        logger.warning(f"Impossible d'attacher shared_matches.duckdb: {e}")

        return self._connection

    def _has_column(
        self, conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str
    ) -> bool:
        """Retourne True si une colonne existe dans une table.

        Utile pour supporter des schémas historiques (colonnes ajoutées en v4).
        """

        try:
            return (
                conn.execute(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = ? AND column_name = ?",
                    (table_name, column_name),
                ).fetchone()[0]
                > 0
            )
        except Exception:
            return False

    def _select_optional_column(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        table_name: str,
        table_alias: str,
        column_name: str,
        output_name: str | None = None,
    ) -> str:
        """Construit une expression SELECT tolérante si la colonne manque."""

        out = output_name or column_name
        if self._has_column(conn, table_name, column_name):
            return f"{table_alias}.{column_name} AS {out}"
        return f"NULL AS {out}"

    def _build_metadata_resolution(
        self, conn: duckdb.DuckDBPyConnection
    ) -> tuple[str, str, str, str]:
        """
        Construit les expressions SQL et les jointures pour résoudre les métadonnées.

        Returns:
            Tuple (metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr)
        """
        metadata_joins = ""
        map_name_expr = "match_stats.map_name"
        playlist_name_expr = "match_stats.playlist_name"
        pair_name_expr = "match_stats.pair_name"

        if "meta" not in self._attached_dbs:
            logger.debug("Metadata DB non attachée, pas de résolution des métadonnées")
            return metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr

        try:
            # Vérifier si les tables de métadonnées existent
            # Utiliser une seule requête pour toutes les tables pour plus d'efficacité
            tables_check = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'meta' AND table_name IN ('maps', 'playlists', 'map_mode_pairs', 'playlist_map_mode_pairs')"
            ).fetchall()
            existing_tables = {row[0] for row in tables_check}

            has_maps = "maps" in existing_tables
            has_playlists = "playlists" in existing_tables
            has_pairs_map_mode = "map_mode_pairs" in existing_tables
            has_pairs_playlist = "playlist_map_mode_pairs" in existing_tables
            has_pairs = has_pairs_map_mode or has_pairs_playlist
            pair_table_name = (
                "map_mode_pairs"
                if has_pairs_map_mode
                else ("playlist_map_mode_pairs" if has_pairs_playlist else None)
            )

            logger.debug(
                f"Résolution métadonnées: maps={has_maps}, playlists={has_playlists}, "
                f"pairs={has_pairs} (table={pair_table_name})"
            )

            if has_maps:
                metadata_joins += (
                    " LEFT JOIN meta.maps m_meta ON match_stats.map_id = m_meta.asset_id"
                )
                # Préférer le nom résolu depuis les métadonnées, même si map_name contient déjà une valeur
                # (car map_name peut contenir un UUID si la résolution a échoué lors de la sync)
                map_name_expr = "COALESCE(m_meta.public_name, match_stats.map_name)"

            if has_playlists:
                metadata_joins += (
                    " LEFT JOIN meta.playlists p_meta ON match_stats.playlist_id = p_meta.asset_id"
                )
                # Préférer le nom résolu depuis les métadonnées
                playlist_name_expr = "COALESCE(p_meta.public_name, match_stats.playlist_name)"

            if has_pairs and pair_table_name:
                metadata_joins += f" LEFT JOIN meta.{pair_table_name} pair_meta ON match_stats.pair_id = pair_meta.asset_id"
                # Préférer le nom résolu depuis les métadonnées
                pair_name_expr = "COALESCE(pair_meta.public_name, match_stats.pair_name)"
        except Exception as e:
            # Si erreur, utiliser les valeurs directes (déjà définies par défaut)
            logger.warning(f"Erreur lors de la construction des jointures métadonnées: {e}")

        return metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr

    def _build_mmr_fallback(self, conn) -> tuple[str, str, str]:
        """Construit la jointure et les expressions pour le fallback MMR.

        Si player_match_stats existe, utilise COALESCE pour récupérer les MMR
        depuis cette table si match_stats a des valeurs NULL.

        Returns:
            Tuple (pms_join, team_mmr_expr, enemy_mmr_expr)
        """
        pms_join = ""
        team_mmr_expr = "match_stats.team_mmr"
        enemy_mmr_expr = "match_stats.enemy_mmr"

        try:
            pms_tables = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='main' AND table_name='player_match_stats'"
            ).fetchall()
            if pms_tables:
                pms_join = (
                    " LEFT JOIN player_match_stats pms ON match_stats.match_id = pms.match_id"
                )
                team_mmr_expr = "COALESCE(match_stats.team_mmr, pms.team_mmr)"
                enemy_mmr_expr = "COALESCE(match_stats.enemy_mmr, pms.enemy_mmr)"
        except Exception:
            pass

        return pms_join, team_mmr_expr, enemy_mmr_expr

    # =========================================================================
    # Médailles
    # =========================================================================

    def load_top_medals(
        self,
        match_ids: list[str],
        *,
        top_n: int | None = 25,
    ) -> list[tuple[int, int]]:
        """Charge les médailles les plus fréquentes.

        V5 : Utilise shared.medals_earned si disponible (filtré par xuid).
        """
        if not match_ids:
            return []

        conn = self._get_connection()
        placeholders = ", ".join(["?" for _ in match_ids])
        limit_sql = f"LIMIT {top_n}" if top_n else ""

        # V5 : shared.medals_earned
        if self._has_shared_table("medals_earned"):
            try:
                sql = f"""
                    SELECT medal_name_id, SUM(count) as total
                    FROM shared.medals_earned
                    WHERE match_id IN ({placeholders})
                      AND xuid = ?
                    GROUP BY medal_name_id
                    ORDER BY total DESC
                    {limit_sql}
                """
                result = conn.execute(sql, [*match_ids, self._xuid])
                rows = [(row[0], row[1]) for row in result.fetchall()]
                if rows:
                    return rows
            except Exception:
                pass

        # Fallback V4 : medals_earned locale (pas de colonne xuid)
        try:
            count = conn.execute("SELECT COUNT(*) FROM medals_earned").fetchone()[0]
            if count == 0:
                return []
        except Exception:
            return []

        sql = f"""
            SELECT medal_name_id, SUM(count) as total
            FROM medals_earned
            WHERE match_id IN ({placeholders})
            GROUP BY medal_name_id
            ORDER BY total DESC
            {limit_sql}
        """

        result = conn.execute(sql, match_ids)
        return [(row[0], row[1]) for row in result.fetchall()]

    def load_match_medals(self, match_id: str) -> list[dict[str, int]]:
        """Charge les médailles pour un match spécifique.

        V5 : Utilise shared.medals_earned (filtré par xuid du joueur principal).
        """
        conn = self._get_connection()

        # V5 : shared.medals_earned
        if self._has_shared_table("medals_earned"):
            try:
                result = conn.execute(
                    "SELECT medal_name_id, count FROM shared.medals_earned WHERE match_id = ? AND xuid = ?",
                    [match_id, self._xuid],
                )
                rows = [{"name_id": row[0], "count": row[1]} for row in result.fetchall()]
                if rows:
                    return rows
            except Exception:
                pass

        # Fallback V4 : medals_earned locale
        try:
            result = conn.execute(
                "SELECT medal_name_id, count FROM medals_earned WHERE match_id = ?",
                [match_id],
            )
            return [{"name_id": row[0], "count": row[1]} for row in result.fetchall()]
        except Exception:
            return []

    def count_medal_by_match(
        self,
        match_ids: list[str],
        medal_name_id: int,
    ) -> dict[str, int]:
        """Compte une médaille spécifique pour chaque match.

        V5 : Utilise shared.medals_earned si disponible.

        Args:
            match_ids: Liste des IDs de matchs.
            medal_name_id: ID de la médaille à compter (ex: 1512363953 pour Perfect).

        Returns:
            Dict {match_id: count} pour les matchs ayant cette médaille.
        """
        if not match_ids:
            return {}

        conn = self._get_connection()
        placeholders = ", ".join(["?" for _ in match_ids])

        # V5 : shared.medals_earned
        if self._has_shared_table("medals_earned"):
            try:
                result = conn.execute(
                    f"""
                    SELECT match_id, count
                    FROM shared.medals_earned
                    WHERE match_id IN ({placeholders})
                      AND medal_name_id = ?
                      AND xuid = ?
                    """,
                    [*match_ids, medal_name_id, self._xuid],
                )
                shared_result = {str(row[0]): row[1] for row in result.fetchall()}
                if shared_result:
                    return shared_result
            except Exception:
                pass

        # Fallback V4 : medals_earned locale
        try:
            result = conn.execute(
                f"""
                SELECT match_id, count
                FROM medals_earned
                WHERE match_id IN ({placeholders})
                  AND medal_name_id = ?
                """,
                [*match_ids, medal_name_id],
            )
            return {str(row[0]): row[1] for row in result.fetchall()}
        except Exception:
            return {}

    def count_perfect_kills_by_match(
        self,
        match_ids: list[str],
    ) -> dict[str, int]:
        """Compte les médailles 'Perfect' (kills parfaits) par match.

        La médaille 'Perfect' (ID 1512363953) est obtenue quand le joueur
        tue un adversaire sans prendre de dégâts.

        Args:
            match_ids: Liste des IDs de matchs.

        Returns:
            Dict {match_id: perfect_count} pour les matchs avec des Perfect.
        """
        return self.count_medal_by_match(match_ids, medal_name_id=1512363953)

    # =========================================================================
    # Highlight Events
    # =========================================================================

    def load_first_event_times(
        self,
        match_ids: list[str],
        event_type: str = "Kill",
    ) -> dict[str, int | None]:
        """Charge le timestamp du premier événement par match.

        V5 : Utilise shared.highlight_events si disponible.

        Args:
            match_ids: Liste des IDs de matchs.
            event_type: Type d'événement ("Kill" ou "Death"). Accepte toute casse.

        Returns:
            Dict {match_id: time_ms} pour le premier événement de chaque match.
        """
        if not match_ids:
            return {}

        conn = self._get_connection()
        event_type_normalized = event_type.lower()
        placeholders = ", ".join(["?" for _ in match_ids])

        # V5 : shared.highlight_events (killer_xuid/victim_xuid)
        if self._has_shared_table("highlight_events"):
            try:
                # Pour un Kill, le joueur est le killer ; pour un Death, le joueur est la victime
                xuid_column = "killer_xuid" if event_type_normalized == "kill" else "victim_xuid"
                result = conn.execute(
                    f"""
                    SELECT match_id, MIN(time_ms) as first_time
                    FROM shared.highlight_events
                    WHERE match_id IN ({placeholders})
                      AND LOWER(event_type) = ?
                      AND {xuid_column} = ?
                    GROUP BY match_id
                    """,
                    [*match_ids, event_type_normalized, self._xuid],
                )
                shared_result = {row[0]: row[1] for row in result.fetchall()}
                if shared_result:
                    return shared_result
            except Exception:
                pass

        # Fallback V4 : highlight_events locale (xuid unique)
        try:
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_name = 'highlight_events'"
            ).fetchall()
            if not tables:
                return {}

            result = conn.execute(
                f"""
                SELECT match_id, MIN(time_ms) as first_time
                FROM highlight_events
                WHERE match_id IN ({placeholders})
                  AND LOWER(event_type) = ?
                  AND xuid = ?
                GROUP BY match_id
                """,
                [*match_ids, event_type_normalized, self._xuid],
            )
            return {row[0]: row[1] for row in result.fetchall()}
        except Exception:
            return {}

    def get_first_kill_death_times(
        self,
        match_ids: list[str],
    ) -> tuple[dict[str, int | None], dict[str, int | None]]:
        """Charge les timestamps du premier kill et première mort par match.

        Args:
            match_ids: Liste des IDs de matchs.

        Returns:
            Tuple (first_kills, first_deaths) où chaque dict est {match_id: time_ms}.
        """
        first_kills = self.load_first_event_times(match_ids, event_type="Kill")
        first_deaths = self.load_first_event_times(match_ids, event_type="Death")
        return first_kills, first_deaths

    # =========================================================================
    # Coéquipiers
    # =========================================================================

    def list_top_teammates(
        self,
        limit: int = 20,
    ) -> list[tuple[str, int]]:
        """Liste les coéquipiers les plus fréquents."""
        conn = self._get_connection()

        try:
            result = conn.execute(
                """
                SELECT teammate_xuid, matches_together
                FROM teammates_aggregate
                ORDER BY matches_together DESC
                LIMIT ?
                """,
                [limit],
            )
            return [(row[0], row[1]) for row in result.fetchall()]
        except Exception:
            return []

    # =========================================================================
    # Métadonnées
    # =========================================================================

    def get_sync_metadata(self) -> dict[str, Any]:
        """Récupère les métadonnées de synchronisation."""
        conn = self._get_connection()

        # Essayer de lire depuis meta.sync_meta si attaché
        if "meta" in self._attached_dbs:
            try:
                result = conn.execute(
                    "SELECT last_sync_at FROM meta.sync_meta WHERE xuid = ?",
                    [self._xuid],
                ).fetchone()
                last_sync = result[0] if result else None
            except Exception:
                last_sync = None
        else:
            last_sync = None

        return {
            "last_sync_at": last_sync,
            "last_match_time": None,
            "total_matches": self.get_match_count(),
            "player_xuid": self._xuid,
            "storage_type": "duckdb",
        }

    # =========================================================================
    # Méthodes de diagnostic
    # =========================================================================

    def get_storage_info(self) -> dict[str, Any]:
        """Retourne des informations sur le stockage."""
        conn = self._get_connection()

        # Taille des tables
        tables_info = {}
        for table in ["match_stats", "teammates_aggregate", "medals_earned", "antagonists"]:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                tables_info[table] = count
            except Exception:
                tables_info[table] = 0

        # Taille du fichier
        file_size_mb = 0
        if self._player_db_path.exists():
            file_size_mb = self._player_db_path.stat().st_size / (1024 * 1024)

        return {
            "type": "duckdb",
            "player_db_path": str(self._player_db_path),
            "metadata_db_path": str(self._metadata_db_path),
            "shared_db_path": str(self._shared_db_path),
            "xuid": self._xuid,
            "gamertag": self._gamertag,
            "file_size_mb": round(file_size_mb, 2),
            "tables": tables_info,
            "has_metadata": "meta" in self._attached_dbs,
            "has_shared": "shared" in self._attached_dbs,
        }

    def is_hybrid_available(self) -> bool:
        """Vérifie si les données sont disponibles."""
        return self._player_db_path.exists() and self.get_match_count() > 0

    # =========================================================================
    # Requêtes avancées
    # =========================================================================

    def query(self, sql: str, params: list | None = None) -> list[dict[str, Any]]:
        """
        Exécute une requête SQL arbitraire.
        (Execute arbitrary SQL query)
        """
        conn = self._get_connection()
        result = conn.execute(sql, params) if params else conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]

    def query_df(self, sql: str, params: list | None = None):
        """
        Exécute une requête SQL et retourne un DataFrame Polars.
        (Execute SQL query and return Polars DataFrame)
        """
        conn = self._get_connection()
        result = conn.execute(sql, params) if params else conn.execute(sql)
        return result_to_polars(result)

    # =========================================================================
    # Gestion de la connexion
    # =========================================================================

    def close(self) -> None:
        """Ferme la connexion DuckDB."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self._attached_dbs.clear()

    def __enter__(self) -> DuckDBRepository:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # =========================================================================
    # Archives (Sprint 4.5 - Partitionnement Temporel)
    # =========================================================================

    def _get_archive_dir(self) -> Path:
        """Retourne le chemin vers le dossier archive du joueur.

        Dans le layout standard, les archives sont stockées dans un dossier
        `archive/` à côté de `stats.duckdb`.

        Pour certains scénarios (notamment des fixtures de tests), le dossier
        joueur peut être suffixé par un identifiant (ex: `TestPlayer_ab12cd34`).
        Dans ce cas, on tente aussi de résoudre `players/<base>/archive`.
        """

        archive_dir = self._player_db_path.parent / "archive"
        if archive_dir.exists():
            return archive_dir

        player_dir_name = self._player_db_path.parent.name
        m = re.match(r"^(?P<base>.+)_[0-9a-f]{8}$", player_dir_name)
        if m:
            base_dir = m.group("base")
            alternative = self._player_db_path.parent.parent / base_dir / "archive"
            if alternative.exists():
                return alternative

        return archive_dir

    def get_archive_info(self) -> dict[str, Any]:
        """Retourne les informations sur les archives existantes.

        Returns:
            Dict avec:
                - has_archives: bool
                - archive_count: int
                - total_size_mb: float
                - archives: list[dict] avec détails de chaque fichier
                - last_updated: str (datetime ISO) ou None
        """
        archive_dir = self._get_archive_dir()

        if not archive_dir.exists():
            return {
                "has_archives": False,
                "archive_count": 0,
                "total_size_mb": 0.0,
                "archives": [],
                "last_updated": None,
            }

        parquet_files = list(archive_dir.glob("*.parquet"))

        if not parquet_files:
            return {
                "has_archives": False,
                "archive_count": 0,
                "total_size_mb": 0.0,
                "archives": [],
                "last_updated": None,
            }

        archives = []
        total_size = 0

        for pf in sorted(parquet_files):
            size = pf.stat().st_size
            total_size += size

            # Essayer de lire le nombre de lignes via DuckDB
            try:
                conn = duckdb.connect(":memory:")
                count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{pf}')").fetchone()[0]
                conn.close()
            except Exception:
                count = None

            archives.append(
                {
                    "name": pf.name,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "row_count": count,
                    "modified_at": datetime.fromtimestamp(pf.stat().st_mtime).isoformat(),
                }
            )

        # Charger l'index si disponible
        index_file = archive_dir / "archive_index.json"
        last_updated = None
        if index_file.exists():
            try:
                with open(index_file, encoding="utf-8") as f:
                    index = json.load(f)
                    last_updated = index.get("last_updated")
            except Exception:
                pass

        return {
            "has_archives": True,
            "archive_count": len(archives),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "archives": archives,
            "last_updated": last_updated,
        }

    def load_matches_from_archives(
        self,
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[MatchRow]:
        """Charge les matchs depuis les fichiers Parquet archivés.

        Args:
            start_date: Date de début (incluse).
            end_date: Date de fin (exclue).

        Returns:
            Liste de MatchRow depuis les archives.
        """
        archive_dir = self._get_archive_dir()

        if not archive_dir.exists():
            return []

        parquet_files = list(archive_dir.glob("*.parquet"))

        if not parquet_files:
            return []

        # Construire la liste des fichiers à lire
        file_paths = [str(pf) for pf in sorted(parquet_files)]

        # Utiliser DuckDB pour lire les Parquet
        conn = duckdb.connect(":memory:")

        # Construire la clause WHERE
        where_clauses = []
        params = []

        if start_date:
            where_clauses.append("start_time >= ?")
            params.append(start_date)

        if end_date:
            where_clauses.append("start_time < ?")
            params.append(end_date)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Lire depuis tous les fichiers Parquet
        # DuckDB peut lire plusieurs fichiers avec read_parquet([...])
        file_list_sql = ", ".join([f"'{f}'" for f in file_paths])

        try:
            sql = f"""
                SELECT
                    match_id, start_time, map_id, map_name,
                    playlist_id, playlist_name, pair_id, pair_name,
                    game_variant_id, game_variant_name,
                    outcome, team_id, kda, max_killing_spree, headshot_kills,
                    avg_life_seconds, time_played_seconds,
                    kills, deaths, assists, accuracy,
                    my_team_score, enemy_team_score, team_mmr, enemy_mmr
                FROM read_parquet([{file_list_sql}])
                WHERE {where_sql}
                ORDER BY start_time ASC
            """

            result = conn.execute(sql, params) if params else conn.execute(sql)
            rows = result.fetchall()
            columns = [desc[0] for desc in result.description]

            conn.close()

            return [
                MatchRow(
                    match_id=row[columns.index("match_id")],
                    start_time=row[columns.index("start_time")],
                    map_id=row[columns.index("map_id")],
                    map_name=row[columns.index("map_name")],
                    playlist_id=row[columns.index("playlist_id")],
                    playlist_name=row[columns.index("playlist_name")],
                    map_mode_pair_id=row[columns.index("pair_id")],
                    map_mode_pair_name=row[columns.index("pair_name")],
                    game_variant_id=row[columns.index("game_variant_id")],
                    game_variant_name=row[columns.index("game_variant_name")],
                    outcome=row[columns.index("outcome")],
                    last_team_id=row[columns.index("team_id")],
                    kda=row[columns.index("kda")],
                    max_killing_spree=row[columns.index("max_killing_spree")],
                    headshot_kills=row[columns.index("headshot_kills")],
                    average_life_seconds=row[columns.index("avg_life_seconds")],
                    time_played_seconds=row[columns.index("time_played_seconds")],
                    kills=row[columns.index("kills")] or 0,
                    deaths=row[columns.index("deaths")] or 0,
                    assists=row[columns.index("assists")] or 0,
                    accuracy=row[columns.index("accuracy")],
                    my_team_score=row[columns.index("my_team_score")],
                    enemy_team_score=row[columns.index("enemy_team_score")],
                    team_mmr=row[columns.index("team_mmr")],
                    enemy_mmr=row[columns.index("enemy_mmr")],
                    personal_score=row[columns.index("personal_score")]
                    if "personal_score" in columns
                    else None,
                )
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Erreur lecture archives: {e}")
            conn.close()
            return []

    def load_all_matches_unified(
        self,
        *,
        include_archives: bool = True,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[MatchRow]:
        """Charge tous les matchs (DB principale + archives).

        Fournit une vue unifiée de l'historique complet du joueur,
        combinant la DB principale (données récentes) et les archives
        Parquet (données anciennes).

        Args:
            include_archives: Si True, inclut les matchs des archives.
            start_date: Date de début (incluse).
            end_date: Date de fin (exclue).

        Returns:
            Liste de MatchRow triée par start_time (chronologique).
        """
        matches: list[MatchRow] = []

        # 1. Charger depuis les archives (si demandé)
        if include_archives:
            archive_matches = self.load_matches_from_archives(
                start_date=start_date,
                end_date=end_date,
            )
            matches.extend(archive_matches)
            logger.debug(f"Archives: {len(archive_matches)} matchs chargés")

        # 2. Charger depuis la DB principale
        db_matches = self.load_matches()

        # Filtrer par dates si nécessaire
        if start_date or end_date:
            filtered = []
            for m in db_matches:
                if start_date and m.start_time < start_date:
                    continue
                if end_date and m.start_time >= end_date:
                    continue
                filtered.append(m)
            db_matches = filtered

        matches.extend(db_matches)
        logger.debug(f"DB principale: {len(db_matches)} matchs chargés")

        # 3. Dédupliquer (au cas où un match serait dans les deux)
        seen_ids: set[str] = set()
        unique_matches: list[MatchRow] = []

        for m in matches:
            if m.match_id not in seen_ids:
                seen_ids.add(m.match_id)
                unique_matches.append(m)

        # 4. Trier par date
        unique_matches.sort(key=lambda m: m.start_time)

        logger.debug(f"Total unifié: {len(unique_matches)} matchs")
        return unique_matches

    def get_total_match_count_with_archives(self) -> dict[str, int]:
        """Retourne le compte des matchs (DB + archives).

        Returns:
            Dict avec 'db_count', 'archive_count', 'total'.
        """
        db_count = self.get_match_count()

        archive_count = 0
        archive_info = self.get_archive_info()

        if archive_info["has_archives"]:
            for archive in archive_info["archives"]:
                if archive.get("row_count"):
                    archive_count += archive["row_count"]

        return {
            "db_count": db_count,
            "archive_count": archive_count,
            "total": db_count + archive_count,
        }

    def load_personal_score_awards_as_polars(
        self,
        *,
        match_id: str | None = None,
        match_ids: list[str] | None = None,
        category: str | None = None,
        limit: int | None = None,
    ):
        """Charge les PersonalScoreAwards en DataFrame Polars.

        Sprint 8.2 - Permet de visualiser la participation au match :
        kills, assists, objectifs, véhicules, pénalités.

        Args:
            match_id: Filtrer par un match spécifique.
            match_ids: Filtrer par une liste de matchs.
            category: Filtrer par catégorie (kill, assist, objective, etc.).
            limit: Limite du nombre de résultats.

        Returns:
            DataFrame Polars avec colonnes :
            match_id, xuid, award_name, award_category, award_count, award_score.
        """
        conn = self._get_connection()

        where_clauses = []
        params = []

        if match_id:
            where_clauses.append("match_id = ?")
            params.append(match_id)
        elif match_ids:
            placeholders = ", ".join(["?" for _ in match_ids])
            where_clauses.append(f"match_id IN ({placeholders})")
            params.extend(match_ids)

        if category:
            where_clauses.append("award_category = ?")
            params.append(category)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        limit_sql = f"LIMIT {int(limit)}" if limit else ""

        sql = f"""
            SELECT
                match_id,
                xuid,
                award_name,
                award_category,
                award_count,
                award_score,
                created_at
            FROM personal_score_awards
            WHERE {where_sql}
            ORDER BY award_score DESC
            {limit_sql}
        """

        try:
            result = conn.execute(sql, params) if params else conn.execute(sql)
            return result_to_polars(result)
        except Exception as e:
            logger.warning(f"Erreur chargement personal_score_awards Polars: {e}")
            import polars as pl

            return pl.DataFrame()

    def has_personal_score_awards(self) -> bool:
        """Vérifie si des PersonalScoreAwards existent dans la DB."""
        conn = self._get_connection()
        try:
            result = conn.execute("SELECT 1 FROM personal_score_awards LIMIT 1").fetchone()
            return result is not None
        except Exception:
            return False

    # =========================================================================
    # Sprint Gamertag Roster Fix : Helpers et résolution
    # =========================================================================

    def _has_table(self, table_name: str) -> bool:
        """Vérifie si une table existe dans la DB."""
        conn = self._get_connection()
        try:
            result = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_name = ?",
                [table_name],
            ).fetchone()
            return result is not None
        except Exception:
            return False

    # =========================================================================
    # Méthodes legacy-compat (ajoutées pour migration src/db/)
    # =========================================================================

    def load_highlight_events(self, match_id: str) -> list[dict[str, Any]]:
        """Charge les highlight events pour un match.

        V5 : Utilise shared.highlight_events si disponible (tous les events du match),
        puis complète avec les events locaux si nécessaire.

        Args:
            match_id: ID du match.

        Returns:
            Liste de dicts avec: event_type, time_ms, xuid, gamertag, type_hint.
        """
        if not match_id:
            return []

        conn = self._get_connection()

        # V5 : shared.highlight_events (structure killer_xuid/victim_xuid)
        if self._has_shared_table("highlight_events"):
            try:
                result = conn.execute(
                    """
                    SELECT event_type, time_ms,
                           CASE WHEN LOWER(event_type) = 'kill' THEN killer_xuid
                                WHEN LOWER(event_type) = 'death' THEN victim_xuid
                                ELSE COALESCE(killer_xuid, victim_xuid)
                           END AS xuid,
                           CASE WHEN LOWER(event_type) = 'kill' THEN killer_gamertag
                                WHEN LOWER(event_type) = 'death' THEN victim_gamertag
                                ELSE COALESCE(killer_gamertag, victim_gamertag)
                           END AS gamertag,
                           type_hint
                    FROM shared.highlight_events
                    WHERE match_id = ?
                    ORDER BY time_ms ASC NULLS LAST
                    """,
                    [match_id],
                )
                columns = ["event_type", "time_ms", "xuid", "gamertag", "type_hint"]
                rows = result.fetchall()
                if rows:
                    return [dict(zip(columns, row, strict=False)) for row in rows]
            except Exception as e:
                logger.debug(f"Erreur shared.highlight_events: {e}")

        # Fallback V4 : highlight_events locale
        try:
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_name = 'highlight_events'"
            ).fetchall()
            if not tables:
                return []

            result = conn.execute(
                """
                SELECT event_type, time_ms, xuid, gamertag, type_hint
                FROM highlight_events
                WHERE match_id = ?
                ORDER BY time_ms ASC NULLS LAST
                """,
                [match_id],
            )
            columns = ["event_type", "time_ms", "xuid", "gamertag", "type_hint"]
            return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]
        except Exception as e:
            logger.debug(f"Erreur load_highlight_events: {e}")
            return []

    def list_other_player_xuids(self, limit: int = 500) -> list[str]:
        """Liste les XUIDs des autres joueurs rencontrés.

        V5 : Utilise shared.match_participants si disponible (roster complet).
        Complète avec les sources locales.

        Args:
            limit: Nombre max de XUIDs à retourner.

        Returns:
            Liste de XUIDs uniques (hors le joueur principal).
        """
        conn = self._get_connection()
        xuids: set[str] = set()

        try:
            # V5 : shared.match_participants (tous les joueurs de tous les matchs)
            if self._has_shared_table("match_participants"):
                rows = conn.execute(
                    """
                    SELECT DISTINCT p2.xuid
                    FROM shared.match_participants p1
                    INNER JOIN shared.match_participants p2 ON p1.match_id = p2.match_id
                    WHERE p1.xuid = ? AND p2.xuid != ?
                    LIMIT ?
                    """,
                    [self._xuid, self._xuid, limit],
                ).fetchall()
                xuids.update(str(row[0]) for row in rows if row[0])

            # Depuis highlight_events locale
            if self._has_table("highlight_events"):
                rows = conn.execute(
                    """
                    SELECT DISTINCT xuid
                    FROM highlight_events
                    WHERE xuid IS NOT NULL AND xuid != ?
                    LIMIT ?
                    """,
                    [self._xuid, limit],
                ).fetchall()
                xuids.update(str(row[0]) for row in rows if row[0])

            # Depuis match_participants locale
            if self._has_table("match_participants"):
                rows = conn.execute(
                    """
                    SELECT DISTINCT xuid
                    FROM match_participants
                    WHERE xuid IS NOT NULL AND xuid != ?
                    LIMIT ?
                    """,
                    [self._xuid, limit],
                ).fetchall()
                xuids.update(str(row[0]) for row in rows if row[0])

            # Depuis antagonists
            if self._has_table("antagonists"):
                rows = conn.execute(
                    """
                    SELECT DISTINCT opponent_xuid
                    FROM antagonists
                    WHERE opponent_xuid IS NOT NULL
                    LIMIT ?
                    """,
                    [limit],
                ).fetchall()
                xuids.update(str(row[0]) for row in rows if row[0])

            return list(xuids)[:limit]
        except Exception as e:
            logger.debug(f"Erreur list_other_player_xuids: {e}")
            return []

    def get_match_session_info(self, match_id: str) -> dict[str, Any] | None:
        """Retourne les infos de session pour un match.

        Args:
            match_id: ID du match.

        Returns:
            Dict avec session_id, label, etc. ou None.
        """
        if not match_id:
            return None

        conn = self._get_connection()
        try:
            row = conn.execute(
                """
                SELECT session_id
                FROM match_stats
                WHERE match_id = ?
                """,
                [match_id],
            ).fetchone()

            if row and row[0]:
                return {"session_id": row[0]}
            return None
        except Exception:
            return None

    def has_table(self, table_name: str) -> bool:
        """Vérifie si une table existe (alias public de _has_table).

        Args:
            table_name: Nom de la table.

        Returns:
            True si la table existe.
        """
        return self._has_table(table_name)
