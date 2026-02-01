"""
Repository DuckDB natif pour les données joueur.
(Native DuckDB repository for player data)

HOW IT WORKS:
Ce repository utilise exclusivement DuckDB :
1. data/warehouse/metadata.duckdb : Référentiels (playlists, maps, médailles)
2. data/players/{gamertag}/stats.duckdb : Données joueur (matchs, médailles, etc.)

Les jointures entre les deux DBs sont faites via ATTACH.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from src.models import MatchRow

logger = logging.getLogger(__name__)


class DuckDBRepository:
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

            # Attacher la DB metadata si elle existe
            if self._metadata_db_path.exists():
                try:
                    self._connection.execute(
                        f"ATTACH '{self._metadata_db_path}' AS meta (READ_ONLY)"
                    )
                    self._attached_dbs.add("meta")
                    logger.debug(f"Metadata DB attachée: {self._metadata_db_path}")
                except Exception as e:
                    logger.warning(f"Impossible d'attacher metadata.duckdb: {e}")

        return self._connection

    # =========================================================================
    # Chargement des matchs
    # =========================================================================

    def load_matches(
        self,
        *,
        playlist_filter: str | None = None,
        map_mode_pair_filter: str | None = None,
        map_filter: str | None = None,
        game_variant_filter: str | None = None,
        include_firefight: bool = True,
    ) -> list[MatchRow]:
        """
        Charge tous les matchs depuis match_stats.
        (Load all matches from match_stats)
        """
        conn = self._get_connection()

        where_clauses = []
        params = []

        if playlist_filter:
            where_clauses.append("playlist_id = ?")
            params.append(playlist_filter)

        if map_mode_pair_filter:
            where_clauses.append("pair_id = ?")
            params.append(map_mode_pair_filter)

        if map_filter:
            where_clauses.append("map_id = ?")
            params.append(map_filter)

        if game_variant_filter:
            where_clauses.append("game_variant_id = ?")
            params.append(game_variant_filter)

        if not include_firefight:
            where_clauses.append("is_firefight = FALSE")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
            SELECT
                match_id,
                start_time,
                map_id,
                map_name,
                playlist_id,
                playlist_name,
                pair_id,
                pair_name,
                game_variant_id,
                game_variant_name,
                outcome,
                team_id,
                kda,
                max_killing_spree,
                headshot_kills,
                avg_life_seconds,
                time_played_seconds,
                kills,
                deaths,
                assists,
                accuracy,
                my_team_score,
                enemy_team_score,
                team_mmr,
                enemy_mmr
            FROM match_stats
            WHERE {where_sql}
            ORDER BY start_time ASC
        """

        result = conn.execute(sql, params) if params else conn.execute(sql)
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description]

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
            )
            for row in rows
        ]

    def load_matches_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[MatchRow]:
        """Charge les matchs dans une plage de dates."""
        conn = self._get_connection()

        sql = """
            SELECT
                match_id, start_time, map_id, map_name,
                playlist_id, playlist_name, pair_id, pair_name,
                game_variant_id, game_variant_name,
                outcome, team_id, kda, max_killing_spree, headshot_kills,
                avg_life_seconds, time_played_seconds,
                kills, deaths, assists, accuracy,
                my_team_score, enemy_team_score, team_mmr, enemy_mmr
            FROM match_stats
            WHERE start_time >= ? AND start_time <= ?
            ORDER BY start_time ASC
        """

        result = conn.execute(sql, [start_date, end_date])
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description]

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
            )
            for row in rows
        ]

    def get_match_count(self) -> int:
        """Retourne le nombre total de matchs."""
        conn = self._get_connection()
        result = conn.execute("SELECT COUNT(*) FROM match_stats").fetchone()
        return result[0] if result else 0

    # =========================================================================
    # Médailles
    # =========================================================================

    def load_top_medals(
        self,
        match_ids: list[str],
        *,
        top_n: int | None = 25,
    ) -> list[tuple[int, int]]:
        """Charge les médailles les plus fréquentes."""
        if not match_ids:
            return []

        conn = self._get_connection()

        # Vérifier si la table medals_earned a des données
        try:
            count = conn.execute("SELECT COUNT(*) FROM medals_earned").fetchone()[0]
            if count == 0:
                return []
        except Exception:
            return []

        placeholders = ", ".join(["?" for _ in match_ids])
        limit_sql = f"LIMIT {top_n}" if top_n else ""

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
        """Charge les médailles pour un match spécifique."""
        conn = self._get_connection()

        try:
            result = conn.execute(
                "SELECT medal_name_id, count FROM medals_earned WHERE match_id = ?",
                [match_id],
            )
            return [{"name_id": row[0], "count": row[1]} for row in result.fetchall()]
        except Exception:
            return []

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
            "xuid": self._xuid,
            "gamertag": self._gamertag,
            "file_size_mb": round(file_size_mb, 2),
            "tables": tables_info,
            "has_metadata": "meta" in self._attached_dbs,
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
        return result.pl()

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
