"""
Mixin pour la gestion des antagonistes (némésis et souffre-douleurs).

Regroupe les méthodes de sauvegarde, chargement et analyse des
relations killer/victim extraites de DuckDBRepository :
- save_antagonists
- load_antagonists
- get_top_nemeses
- get_top_victims
- load_killer_victim_pairs_as_polars
- get_antagonists_summary_polars
- has_killer_victim_pairs
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import duckdb
import polars as pl

from src.data.repositories._arrow_bridge import result_to_polars

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AntagonistsMixin:
    """Mixin fournissant la gestion des antagonistes pour DuckDBRepository."""

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

    def load_killer_victim_pairs_as_polars(
        self,
        *,
        match_id: str | None = None,
        match_ids: list[str] | None = None,
        limit: int | None = None,
    ):
        """Charge les paires killer→victim en DataFrame Polars.

        Args:
            match_id: Filtrer par un match spécifique.
            match_ids: Filtrer par une liste de matchs.
            limit: Limite du nombre de résultats.

        Returns:
            DataFrame Polars avec colonnes:
            - match_id, killer_xuid, killer_gamertag, victim_xuid,
              victim_gamertag, kill_count, time_ms
        """
        conn = self._get_connection()

        # Construire la requête
        where_clauses = []
        params = []

        if match_id:
            where_clauses.append("match_id = ?")
            params.append(match_id)
        elif match_ids:
            placeholders = ", ".join(["?" for _ in match_ids])
            where_clauses.append(f"match_id IN ({placeholders})")
            params.extend(match_ids)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        limit_sql = f"LIMIT {int(limit)}" if limit else ""

        sql = f"""
            SELECT
                match_id,
                killer_xuid,
                killer_gamertag,
                victim_xuid,
                victim_gamertag,
                kill_count,
                time_ms
            FROM killer_victim_pairs
            WHERE {where_sql}
            ORDER BY match_id, time_ms
            {limit_sql}
        """

        try:
            result = conn.execute(sql, params) if params else conn.execute(sql)
            return result_to_polars(result)
        except Exception as e:
            logger.warning(f"Erreur chargement killer_victim_pairs: {e}")
            # Retourner un DataFrame vide avec le bon schéma
            return pl.DataFrame(
                {
                    "match_id": [],
                    "killer_xuid": [],
                    "killer_gamertag": [],
                    "victim_xuid": [],
                    "victim_gamertag": [],
                    "kill_count": [],
                    "time_ms": [],
                }
            )

    def get_antagonists_summary_polars(
        self,
        top_n: int = 20,
    ):
        """Calcule un résumé des antagonistes avec Polars.

        Agrège les paires killer_victim pour obtenir le top némésis/victimes.

        Args:
            top_n: Nombre de résultats par catégorie.

        Returns:
            Dict avec 'nemeses' et 'victims' DataFrames Polars.
        """
        pairs_df = self.load_killer_victim_pairs_as_polars()

        if pairs_df.is_empty():
            return {
                "nemeses": pl.DataFrame(),
                "victims": pl.DataFrame(),
            }

        me_xuid = self._xuid

        # Top némésis (qui m'a le plus tué)
        nemeses = (
            pairs_df.filter(pl.col("victim_xuid") == me_xuid)
            .group_by("killer_xuid", "killer_gamertag")
            .agg(pl.col("kill_count").sum().alias("times_killed_by"))
            .sort("times_killed_by", descending=True)
            .head(top_n)
        )

        # Top victimes (qui j'ai le plus tué)
        victims = (
            pairs_df.filter(pl.col("killer_xuid") == me_xuid)
            .group_by("victim_xuid", "victim_gamertag")
            .agg(pl.col("kill_count").sum().alias("times_killed"))
            .sort("times_killed", descending=True)
            .head(top_n)
        )

        return {
            "nemeses": nemeses,
            "victims": victims,
        }

    def has_killer_victim_pairs(self) -> bool:
        """Vérifie si la table killer_victim_pairs existe et contient des données.

        Returns:
            True si des paires sont disponibles.
        """
        conn = self._get_connection()

        try:
            count = conn.execute("SELECT COUNT(*) FROM killer_victim_pairs").fetchone()[0]
            return count > 0
        except Exception:
            return False
