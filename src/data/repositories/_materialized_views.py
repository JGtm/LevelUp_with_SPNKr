"""
Mixin pour les vues matérialisées DuckDB.

Regroupe les méthodes de création, rafraîchissement et lecture
des vues matérialisées extraites de DuckDBRepository :
- _ensure_mv_tables
- refresh_materialized_views
- get_map_stats
- get_mode_category_stats
- get_global_stats
- get_session_stats
- has_materialized_views
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MaterializedViewsMixin:
    """Mixin fournissant la gestion des vues matérialisées pour DuckDBRepository."""

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
