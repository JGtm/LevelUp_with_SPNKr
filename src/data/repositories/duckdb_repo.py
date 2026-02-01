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
        limit: int | None = None,
        offset: int | None = None,
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

        # Construire les clauses LIMIT/OFFSET pour la pagination (Sprint 4.3)
        pagination_sql = ""
        if limit is not None:
            pagination_sql += f" LIMIT {int(limit)}"
        if offset is not None:
            pagination_sql += f" OFFSET {int(offset)}"

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
            {pagination_sql}
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
    # Lazy Loading et Pagination (Sprint 4.3)
    # =========================================================================

    def load_recent_matches(
        self,
        limit: int = 50,
        *,
        include_firefight: bool = True,
    ) -> list[MatchRow]:
        """Charge les N matchs les plus récents.

        Optimisé pour le chargement initial rapide de l'UI.
        Tri par start_time DESC (les plus récents en premier).

        Args:
            limit: Nombre maximum de matchs à retourner.
            include_firefight: Inclure les matchs PvE.

        Returns:
            Liste de MatchRow triée par date décroissante.
        """
        conn = self._get_connection()

        where_clauses = []
        if not include_firefight:
            where_clauses.append("is_firefight = FALSE")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
            SELECT
                match_id, start_time, map_id, map_name,
                playlist_id, playlist_name, pair_id, pair_name,
                game_variant_id, game_variant_name,
                outcome, team_id, kda, max_killing_spree, headshot_kills,
                avg_life_seconds, time_played_seconds,
                kills, deaths, assists, accuracy,
                my_team_score, enemy_team_score, team_mmr, enemy_mmr
            FROM match_stats
            WHERE {where_sql}
            ORDER BY start_time DESC
            LIMIT {int(limit)}
        """

        result = conn.execute(sql)
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

    def load_matches_paginated(
        self,
        page: int = 1,
        page_size: int = 50,
        *,
        order_desc: bool = True,
        include_firefight: bool = True,
    ) -> tuple[list[MatchRow], int]:
        """Charge les matchs avec pagination.

        Args:
            page: Numéro de page (1-indexed).
            page_size: Nombre de matchs par page.
            order_desc: Si True, tri décroissant (récents en premier).
            include_firefight: Inclure les matchs PvE.

        Returns:
            Tuple (matchs, total_pages).
        """
        # Calculer le total de pages
        total_count = self.get_match_count()
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

        # Valider la page
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size

        conn = self._get_connection()

        where_clauses = []
        if not include_firefight:
            where_clauses.append("is_firefight = FALSE")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        order_dir = "DESC" if order_desc else "ASC"

        sql = f"""
            SELECT
                match_id, start_time, map_id, map_name,
                playlist_id, playlist_name, pair_id, pair_name,
                game_variant_id, game_variant_name,
                outcome, team_id, kda, max_killing_spree, headshot_kills,
                avg_life_seconds, time_played_seconds,
                kills, deaths, assists, accuracy,
                my_team_score, enemy_team_score, team_mmr, enemy_mmr
            FROM match_stats
            WHERE {where_sql}
            ORDER BY start_time {order_dir}
            LIMIT {int(page_size)} OFFSET {int(offset)}
        """

        result = conn.execute(sql)
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description]

        matches = [
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

        return matches, total_pages

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

    # =========================================================================
    # Écriture des données
    # =========================================================================

    def save_antagonists(
        self,
        entries: list,
        *,
        replace: bool = False,
    ) -> int:
        """Sauvegarde les antagonistes dans la table DuckDB.

        Args:
            entries: Liste d'AntagonistEntry à sauvegarder.
            replace: Si True, remplace toutes les données existantes.

        Returns:
            Nombre d'entrées sauvegardées.
        """
        if not entries:
            return 0

        # Forcer une connexion en écriture
        if self._read_only:
            # Créer une nouvelle connexion en écriture
            if self._connection is not None:
                self._connection.close()
            self._connection = duckdb.connect(
                str(self._player_db_path),
                read_only=False,
            )
            self._connection.execute(f"SET memory_limit = '{self._memory_limit}'")
            self._read_only = False
            self._attached_dbs.clear()

        conn = self._get_connection()

        # Créer la table si elle n'existe pas
        conn.execute("""
            CREATE TABLE IF NOT EXISTS antagonists (
                opponent_xuid VARCHAR PRIMARY KEY,
                opponent_gamertag VARCHAR,
                times_killed INTEGER DEFAULT 0,
                times_killed_by INTEGER DEFAULT 0,
                matches_against INTEGER DEFAULT 0,
                last_encounter TIMESTAMP,
                net_kills INTEGER GENERATED ALWAYS AS (times_killed - times_killed_by)
            )
        """)

        # Si replace, vider la table
        if replace:
            conn.execute("DELETE FROM antagonists")

        # Préparer les données
        rows = []
        for entry in entries:
            # Gérer les différents types d'entrées (dict ou dataclass)
            if hasattr(entry, "opponent_xuid"):
                rows.append(
                    (
                        entry.opponent_xuid,
                        entry.opponent_gamertag,
                        entry.times_killed,
                        entry.times_killed_by,
                        entry.matches_against,
                        entry.last_encounter,
                    )
                )
            elif isinstance(entry, dict):
                rows.append(
                    (
                        entry.get("opponent_xuid", ""),
                        entry.get("opponent_gamertag", ""),
                        entry.get("times_killed", 0),
                        entry.get("times_killed_by", 0),
                        entry.get("matches_against", 0),
                        entry.get("last_encounter"),
                    )
                )

        if not rows:
            return 0

        # Insérer ou mettre à jour (upsert)
        # DuckDB supporte INSERT OR REPLACE avec ON CONFLICT
        conn.executemany(
            """
            INSERT INTO antagonists (
                opponent_xuid,
                opponent_gamertag,
                times_killed,
                times_killed_by,
                matches_against,
                last_encounter
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (opponent_xuid) DO UPDATE SET
                opponent_gamertag = EXCLUDED.opponent_gamertag,
                times_killed = EXCLUDED.times_killed,
                times_killed_by = EXCLUDED.times_killed_by,
                matches_against = EXCLUDED.matches_against,
                last_encounter = EXCLUDED.last_encounter
            """,
            rows,
        )

        return len(rows)

    def load_antagonists(
        self,
        *,
        limit: int = 50,
        order_by: str = "net_kills",
    ) -> list[dict]:
        """Charge les antagonistes depuis la table.

        Args:
            limit: Nombre maximum de résultats.
            order_by: Colonne de tri (net_kills, times_killed, times_killed_by).

        Returns:
            Liste de dicts représentant les antagonistes.
        """
        conn = self._get_connection()

        # Valider le order_by pour éviter l'injection SQL
        valid_orders = {
            "net_kills": "net_kills DESC",
            "times_killed": "times_killed DESC",
            "times_killed_by": "times_killed_by DESC",
            "matches_against": "matches_against DESC",
            "last_encounter": "last_encounter DESC",
        }
        order_clause = valid_orders.get(order_by, "net_kills DESC")

        try:
            result = conn.execute(
                f"""
                SELECT
                    opponent_xuid,
                    opponent_gamertag,
                    times_killed,
                    times_killed_by,
                    matches_against,
                    last_encounter,
                    net_kills
                FROM antagonists
                ORDER BY {order_clause}
                LIMIT ?
                """,
                [limit],
            )
            columns = [desc[0] for desc in result.description]
            return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]
        except Exception:
            return []

    def get_top_nemeses(self, limit: int = 20) -> list[dict]:
        """Retourne les adversaires qui nous ont le plus tué.

        Args:
            limit: Nombre maximum de résultats.

        Returns:
            Liste de dicts triée par times_killed_by décroissant.
        """
        return self.load_antagonists(limit=limit, order_by="times_killed_by")

    def get_top_victims(self, limit: int = 20) -> list[dict]:
        """Retourne les adversaires qu'on a le plus tué.

        Args:
            limit: Nombre maximum de résultats.

        Returns:
            Liste de dicts triée par times_killed décroissant.
        """
        return self.load_antagonists(limit=limit, order_by="times_killed")

    # =========================================================================
    # Vues Matérialisées (Sprint 4.1)
    # =========================================================================

    def _ensure_mv_tables(self) -> None:
        """Crée les tables de vues matérialisées si elles n'existent pas."""
        conn = self._get_connection()

        # mv_map_stats : Stats par carte
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mv_map_stats (
                map_id VARCHAR PRIMARY KEY,
                map_name VARCHAR,
                matches_played INTEGER,
                wins INTEGER,
                losses INTEGER,
                ties INTEGER,
                avg_kills DOUBLE,
                avg_deaths DOUBLE,
                avg_assists DOUBLE,
                avg_accuracy DOUBLE,
                avg_kda DOUBLE,
                win_rate DOUBLE,
                updated_at TIMESTAMP
            )
        """)

        # mv_mode_category_stats : Stats par catégorie de mode
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mv_mode_category_stats (
                mode_category VARCHAR PRIMARY KEY,
                matches_played INTEGER,
                avg_kills DOUBLE,
                avg_deaths DOUBLE,
                avg_assists DOUBLE,
                avg_kda DOUBLE,
                avg_accuracy DOUBLE,
                win_rate DOUBLE,
                updated_at TIMESTAMP
            )
        """)

        # mv_session_stats : Stats par session (pré-calculées)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mv_session_stats (
                session_id INTEGER PRIMARY KEY,
                match_count INTEGER,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                total_kills INTEGER,
                total_deaths INTEGER,
                total_assists INTEGER,
                kd_ratio DOUBLE,
                win_rate DOUBLE,
                avg_accuracy DOUBLE,
                avg_life_seconds DOUBLE,
                updated_at TIMESTAMP
            )
        """)

        # mv_global_stats : Stats globales du joueur
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mv_global_stats (
                stat_key VARCHAR PRIMARY KEY,
                stat_value DOUBLE,
                updated_at TIMESTAMP
            )
        """)

    def refresh_materialized_views(self) -> dict[str, int]:
        """Rafraîchit toutes les vues matérialisées après sync.

        Returns:
            Dict avec le nombre de lignes insérées par table.
        """
        # Forcer une connexion en écriture
        if self._read_only:
            if self._connection is not None:
                self._connection.close()
            self._connection = duckdb.connect(
                str(self._player_db_path),
                read_only=False,
            )
            self._connection.execute(f"SET memory_limit = '{self._memory_limit}'")
            self._read_only = False
            self._attached_dbs.clear()

        conn = self._get_connection()

        # Créer les tables si nécessaire
        self._ensure_mv_tables()

        results = {}

        # ─── mv_map_stats ───
        conn.execute("DELETE FROM mv_map_stats")
        conn.execute("""
            INSERT INTO mv_map_stats
            SELECT
                map_id,
                map_name,
                COUNT(*) as matches_played,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 3 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 1 THEN 1 ELSE 0 END) as ties,
                AVG(CAST(kills AS DOUBLE)) as avg_kills,
                AVG(CAST(deaths AS DOUBLE)) as avg_deaths,
                AVG(CAST(assists AS DOUBLE)) as avg_assists,
                AVG(accuracy) as avg_accuracy,
                AVG(kda) as avg_kda,
                CASE WHEN COUNT(*) > 0
                     THEN SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0.0 END) / COUNT(*)
                     ELSE 0 END as win_rate,
                CURRENT_TIMESTAMP as updated_at
            FROM match_stats
            WHERE map_id IS NOT NULL
            GROUP BY map_id, map_name
        """)
        results["mv_map_stats"] = conn.execute("SELECT COUNT(*) FROM mv_map_stats").fetchone()[0]

        # ─── mv_mode_category_stats ───
        # Catégorisation basée sur pair_name ou playlist_name
        conn.execute("DELETE FROM mv_mode_category_stats")
        conn.execute("""
            INSERT INTO mv_mode_category_stats
            SELECT
                COALESCE(
                    CASE
                        WHEN pair_name LIKE '%Slayer%' OR pair_name LIKE '%Tuerie%' THEN 'Slayer'
                        WHEN pair_name LIKE '%CTF%' OR pair_name LIKE '%Flag%' OR pair_name LIKE '%Drapeau%' THEN 'CTF'
                        WHEN pair_name LIKE '%Stronghold%' OR pair_name LIKE '%Forteresse%' THEN 'Strongholds'
                        WHEN pair_name LIKE '%Oddball%' OR pair_name LIKE '%Balle%' THEN 'Oddball'
                        WHEN pair_name LIKE '%Total%Control%' OR pair_name LIKE '%Contrôle%' THEN 'Total Control'
                        WHEN pair_name LIKE '%Attrition%' THEN 'Attrition'
                        WHEN pair_name LIKE '%KOTH%' OR pair_name LIKE '%King%' OR pair_name LIKE '%Roi%' THEN 'King of the Hill'
                        WHEN pair_name LIKE '%Extraction%' THEN 'Extraction'
                        WHEN pair_name LIKE '%Firefight%' OR pair_name LIKE '%Sentry%' THEN 'Firefight'
                        WHEN pair_name LIKE '%FFA%' OR pair_name LIKE '%Free%For%All%' THEN 'FFA'
                        ELSE 'Autre'
                    END,
                    'Autre'
                ) as mode_category,
                COUNT(*) as matches_played,
                AVG(CAST(kills AS DOUBLE)) as avg_kills,
                AVG(CAST(deaths AS DOUBLE)) as avg_deaths,
                AVG(CAST(assists AS DOUBLE)) as avg_assists,
                AVG(kda) as avg_kda,
                AVG(accuracy) as avg_accuracy,
                CASE WHEN COUNT(*) > 0
                     THEN SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0.0 END) / COUNT(*)
                     ELSE 0 END as win_rate,
                CURRENT_TIMESTAMP as updated_at
            FROM match_stats
            GROUP BY mode_category
        """)
        results["mv_mode_category_stats"] = conn.execute(
            "SELECT COUNT(*) FROM mv_mode_category_stats"
        ).fetchone()[0]

        # ─── mv_global_stats ───
        conn.execute("DELETE FROM mv_global_stats")
        global_stats = conn.execute("""
            SELECT
                COUNT(*) as total_matches,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(assists) as total_assists,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 3 THEN 1 ELSE 0 END) as losses,
                AVG(kda) as avg_kda,
                AVG(accuracy) as avg_accuracy,
                SUM(time_played_seconds) / 3600.0 as total_hours,
                AVG(avg_life_seconds) as avg_life_seconds
            FROM match_stats
        """).fetchone()

        if global_stats:
            stats_data = [
                ("total_matches", global_stats[0]),
                ("total_kills", global_stats[1]),
                ("total_deaths", global_stats[2]),
                ("total_assists", global_stats[3]),
                ("wins", global_stats[4]),
                ("losses", global_stats[5]),
                ("avg_kda", global_stats[6]),
                ("avg_accuracy", global_stats[7]),
                ("total_hours", global_stats[8]),
                ("avg_life_seconds", global_stats[9]),
            ]
            conn.executemany(
                """
                INSERT INTO mv_global_stats (stat_key, stat_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                stats_data,
            )
        results["mv_global_stats"] = conn.execute(
            "SELECT COUNT(*) FROM mv_global_stats"
        ).fetchone()[0]

        # mv_session_stats : Nécessite les sessions pré-calculées
        # On skip si session_id n'est pas dans match_stats
        try:
            has_sessions = (
                conn.execute(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_name = 'match_stats' AND column_name = 'session_id'"
                ).fetchone()[0]
                > 0
            )

            if has_sessions:
                conn.execute("DELETE FROM mv_session_stats")
                conn.execute("""
                    INSERT INTO mv_session_stats
                    SELECT
                        session_id,
                        COUNT(*) as match_count,
                        MIN(start_time) as start_time,
                        MAX(start_time) as end_time,
                        SUM(kills) as total_kills,
                        SUM(deaths) as total_deaths,
                        SUM(assists) as total_assists,
                        CASE WHEN SUM(deaths) > 0
                             THEN CAST(SUM(kills) AS DOUBLE) / SUM(deaths)
                             ELSE SUM(kills) END as kd_ratio,
                        CASE WHEN COUNT(*) > 0
                             THEN SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0.0 END) / COUNT(*)
                             ELSE 0 END as win_rate,
                        AVG(accuracy) as avg_accuracy,
                        AVG(avg_life_seconds) as avg_life_seconds,
                        CURRENT_TIMESTAMP as updated_at
                    FROM match_stats
                    WHERE session_id IS NOT NULL
                    GROUP BY session_id
                """)
                results["mv_session_stats"] = conn.execute(
                    "SELECT COUNT(*) FROM mv_session_stats"
                ).fetchone()[0]
            else:
                results["mv_session_stats"] = 0
        except Exception:
            results["mv_session_stats"] = 0

        logger.info(f"Vues matérialisées rafraîchies: {results}")
        return results

    def get_map_stats(self, min_matches: int = 1) -> list[dict]:
        """Récupère les stats par carte depuis la vue matérialisée.

        Args:
            min_matches: Nombre minimum de matchs pour inclure une carte.

        Returns:
            Liste de dicts avec les stats par carte.
        """
        conn = self._get_connection()

        try:
            result = conn.execute(
                """
                SELECT
                    map_id, map_name, matches_played, wins, losses, ties,
                    avg_kills, avg_deaths, avg_assists, avg_accuracy,
                    avg_kda, win_rate, updated_at
                FROM mv_map_stats
                WHERE matches_played >= ?
                ORDER BY matches_played DESC
                """,
                [min_matches],
            )
            columns = [desc[0] for desc in result.description]
            return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]
        except Exception:
            return []

    def get_mode_category_stats(self) -> list[dict]:
        """Récupère les stats par catégorie de mode depuis la vue matérialisée.

        Returns:
            Liste de dicts avec les stats par catégorie.
        """
        conn = self._get_connection()

        try:
            result = conn.execute(
                """
                SELECT
                    mode_category, matches_played, avg_kills, avg_deaths,
                    avg_assists, avg_kda, avg_accuracy, win_rate, updated_at
                FROM mv_mode_category_stats
                ORDER BY matches_played DESC
                """
            )
            columns = [desc[0] for desc in result.description]
            return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]
        except Exception:
            return []

    def get_global_stats(self) -> dict[str, float]:
        """Récupère les stats globales depuis la vue matérialisée.

        Returns:
            Dict avec stat_key -> stat_value.
        """
        conn = self._get_connection()

        try:
            result = conn.execute("SELECT stat_key, stat_value FROM mv_global_stats")
            return {row[0]: row[1] for row in result.fetchall()}
        except Exception:
            return {}

    def get_session_stats(self, limit: int = 50) -> list[dict]:
        """Récupère les stats par session depuis la vue matérialisée.

        Args:
            limit: Nombre maximum de sessions à retourner.

        Returns:
            Liste de dicts avec les stats par session.
        """
        conn = self._get_connection()

        try:
            result = conn.execute(
                """
                SELECT
                    session_id, match_count, start_time, end_time,
                    total_kills, total_deaths, total_assists,
                    kd_ratio, win_rate, avg_accuracy, avg_life_seconds, updated_at
                FROM mv_session_stats
                ORDER BY start_time DESC
                LIMIT ?
                """,
                [limit],
            )
            columns = [desc[0] for desc in result.description]
            return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]
        except Exception:
            return []

    def has_materialized_views(self) -> bool:
        """Vérifie si les vues matérialisées sont disponibles et remplies.

        Returns:
            True si au moins mv_global_stats contient des données.
        """
        conn = self._get_connection()

        try:
            count = conn.execute("SELECT COUNT(*) FROM mv_global_stats").fetchone()[0]
            return count > 0
        except Exception:
            return False

    # =========================================================================
    # Chargement batch (Sprint 4.2)
    # =========================================================================

    def load_match_mmr_batch(
        self, match_ids: list[str]
    ) -> dict[str, tuple[float | None, float | None]]:
        """Charge le MMR pour plusieurs matchs en une seule requête.

        Args:
            match_ids: Liste des match_id à charger.

        Returns:
            Dict match_id -> (team_mmr, enemy_mmr).
        """
        if not match_ids:
            return {}

        conn = self._get_connection()

        placeholders = ", ".join(["?" for _ in match_ids])
        result = conn.execute(
            f"""
            SELECT match_id, team_mmr, enemy_mmr
            FROM match_stats
            WHERE match_id IN ({placeholders})
            """,
            match_ids,
        )

        return {row[0]: (row[1], row[2]) for row in result.fetchall()}

    # =========================================================================
    # Archives (Sprint 4.5 - Partitionnement Temporel)
    # =========================================================================

    def _get_archive_dir(self) -> Path:
        """Retourne le chemin vers le dossier archive du joueur."""
        return self._player_db_path.parent / "archive"

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
