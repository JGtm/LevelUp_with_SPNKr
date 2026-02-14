"""
Mixin pour les requêtes de matchs DuckDB.

Regroupe les méthodes de chargement et de requête des matchs
extraites de DuckDBRepository :
- load_matches
- load_matches_in_range
- get_match_count
- load_recent_matches
- load_matches_paginated
- load_match_mmr_batch
- load_match_stats_as_polars
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import polars as pl

from src.data.domain.models.stats import MatchRow
from src.data.repositories._arrow_bridge import result_to_polars

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MatchQueriesMixin:
    """Mixin fournissant les méthodes de requête de matchs pour DuckDBRepository."""

    # =========================================================================
    # Source de données matchs (v5 shared / v4 local)
    # =========================================================================

    def _get_match_source(self, conn) -> tuple[str, list[str]]:
        """Retourne l'expression FROM pour les matchs (v5 shared ou v4 local).

        En mode v5, construit une sous-requête combinant shared.match_registry,
        shared.match_participants et un LEFT JOIN vers match_stats local pour
        les colonnes non disponibles dans shared (kda, spree, headshot_kills, etc.).
        La sous-requête est aliasée ``match_stats`` pour que toutes les références
        externes (jointures metadata, MMR, filtres) restent inchangées.

        En mode v4, retourne simplement ``"match_stats"`` (table locale directe).

        Returns:
            Tuple (from_expression, params).
        """
        if not (
            self.has_shared
            and self._has_shared_table("match_registry")
            and self._has_shared_table("match_participants")
        ):
            return "match_stats", []

        # Vérifier si la table match_stats locale existe (période de transition)
        has_ms = (
            conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_name = 'match_stats'"
            ).fetchone()[0]
            > 0
        )

        if has_ms:
            ms_join = "LEFT JOIN match_stats ms ON r.match_id = ms.match_id"
            # Vérifier les colonnes optionnelles dans match_stats local
            has_is_ranked = self._has_column(conn, "match_stats", "is_ranked")
            has_is_firefight = self._has_column(conn, "match_stats", "is_firefight")

            kda_expr = (
                "COALESCE(ms.kda, "
                "CASE WHEN p.deaths > 0 "
                "THEN (CAST(p.kills AS FLOAT) + CAST(p.assists AS FLOAT) / 3.0) "
                "/ CAST(p.deaths AS FLOAT) "
                "ELSE CAST(p.kills AS FLOAT) + CAST(p.assists AS FLOAT) / 3.0 END)"
            )
            spree_expr = "COALESCE(ms.max_killing_spree, 0)"
            hs_expr = "COALESCE(ms.headshot_kills, 0)"
            avg_life_expr = "COALESCE(ms.avg_life_seconds, 0)"
            mmr_team = "ms.team_mmr"
            mmr_enemy = "ms.enemy_mmr"
            time_expr = "COALESCE(r.duration_seconds, ms.time_played_seconds)"
            acc_expr = (
                "COALESCE(ms.accuracy, "
                "CASE WHEN p.shots_fired > 0 "
                "THEN CAST(p.shots_hit AS FLOAT) * 100.0 / CAST(p.shots_fired AS FLOAT) "
                "ELSE NULL END)"
            )
            my_score = (
                "COALESCE(ms.my_team_score, "
                "CASE WHEN p.team_id = 0 THEN r.team_0_score ELSE r.team_1_score END)"
            )
            enemy_score = (
                "COALESCE(ms.enemy_team_score, "
                "CASE WHEN p.team_id = 0 THEN r.team_1_score ELSE r.team_0_score END)"
            )
            pscore = "COALESCE(ms.personal_score, p.score)"
            map_name = "COALESCE(r.map_name, ms.map_name)"
            playlist_name = "COALESCE(r.playlist_name, ms.playlist_name)"
            pair_name = "COALESCE(r.pair_name, ms.pair_name)"
            gv_name = "COALESCE(r.game_variant_name, ms.game_variant_name)"
            is_ff = (
                f"COALESCE(r.is_firefight, {'ms.is_firefight, ' if has_is_firefight else ''}FALSE)"
            )
            is_rk = f"COALESCE(r.is_ranked, {'ms.is_ranked, ' if has_is_ranked else ''}FALSE)"
        else:
            ms_join = ""
            kda_expr = (
                "CASE WHEN p.deaths > 0 "
                "THEN (CAST(p.kills AS FLOAT) + CAST(p.assists AS FLOAT) / 3.0) "
                "/ CAST(p.deaths AS FLOAT) "
                "ELSE CAST(p.kills AS FLOAT) + CAST(p.assists AS FLOAT) / 3.0 END"
            )
            spree_expr = "0"
            hs_expr = "0"
            avg_life_expr = "0"
            mmr_team = "NULL"
            mmr_enemy = "NULL"
            time_expr = "r.duration_seconds"
            acc_expr = (
                "CASE WHEN p.shots_fired > 0 "
                "THEN CAST(p.shots_hit AS FLOAT) * 100.0 / CAST(p.shots_fired AS FLOAT) "
                "ELSE NULL END"
            )
            my_score = "CASE WHEN p.team_id = 0 THEN r.team_0_score ELSE r.team_1_score END"
            enemy_score = "CASE WHEN p.team_id = 0 THEN r.team_1_score ELSE r.team_0_score END"
            pscore = "p.score"
            map_name = "r.map_name"
            playlist_name = "r.playlist_name"
            pair_name = "r.pair_name"
            gv_name = "r.game_variant_name"
            is_ff = "COALESCE(r.is_firefight, FALSE)"
            is_rk = "COALESCE(r.is_ranked, FALSE)"

        source = f"""(SELECT
            r.match_id,
            r.start_time,
            r.map_id,
            {map_name} AS map_name,
            r.playlist_id,
            {playlist_name} AS playlist_name,
            r.pair_id,
            {pair_name} AS pair_name,
            r.game_variant_id,
            {gv_name} AS game_variant_name,
            p.outcome,
            p.team_id,
            {kda_expr} AS kda,
            {spree_expr} AS max_killing_spree,
            {hs_expr} AS headshot_kills,
            {avg_life_expr} AS avg_life_seconds,
            {time_expr} AS time_played_seconds,
            COALESCE(p.kills, 0) AS kills,
            COALESCE(p.deaths, 0) AS deaths,
            COALESCE(p.assists, 0) AS assists,
            {acc_expr} AS accuracy,
            {my_score} AS my_team_score,
            {enemy_score} AS enemy_team_score,
            {mmr_team} AS team_mmr,
            {mmr_enemy} AS enemy_mmr,
            {pscore} AS personal_score,
            {is_ff} AS is_firefight,
            {is_rk} AS is_ranked
        FROM shared.match_registry r
        JOIN shared.match_participants p
            ON r.match_id = p.match_id AND p.xuid = ?
        {ms_join}
        ) AS match_stats"""

        logger.debug("Mode v5 : requête via shared.match_registry + match_participants")
        return source, [self._xuid]

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
        Charge tous les matchs (v5 : shared + local, v4 : local uniquement).
        """
        conn = self._get_connection()

        # Source v5 (shared) ou v4 (locale)
        source_sql, source_params = self._get_match_source(conn)
        is_shared = bool(source_params)

        where_clauses = []
        params: list = []

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

        # Résoudre les métadonnées depuis meta.* si disponible
        metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr = (
            self._build_metadata_resolution(conn)
        )

        # Fallback MMR depuis player_match_stats si disponible
        pms_join, team_mmr_expr, enemy_mmr_expr = self._build_mmr_fallback(conn)

        # En mode shared, personal_score est toujours dans la sous-requête
        if is_shared:
            personal_score_select = "match_stats.personal_score"
        else:
            personal_score_select = self._select_optional_column(
                conn,
                table_name="match_stats",
                table_alias="match_stats",
                column_name="personal_score",
            )

        sql = f"""
            SELECT
                match_stats.match_id,
                match_stats.start_time,
                match_stats.map_id,
                {map_name_expr} as map_name,
                match_stats.playlist_id,
                {playlist_name_expr} as playlist_name,
                match_stats.pair_id,
                {pair_name_expr} as pair_name,
                match_stats.game_variant_id,
                match_stats.game_variant_name,
                match_stats.outcome,
                match_stats.team_id,
                match_stats.kda,
                match_stats.max_killing_spree,
                match_stats.headshot_kills,
                match_stats.avg_life_seconds,
                match_stats.time_played_seconds,
                match_stats.kills,
                match_stats.deaths,
                match_stats.assists,
                match_stats.accuracy,
                match_stats.my_team_score,
                match_stats.enemy_team_score,
                {team_mmr_expr} as team_mmr,
                {enemy_mmr_expr} as enemy_mmr,
                {personal_score_select}
            FROM {source_sql}{metadata_joins}{pms_join}
            WHERE {where_sql}
            ORDER BY match_stats.start_time ASC
            {pagination_sql}
        """

        all_params = source_params + params

        # Log de debug pour diagnostiquer les problèmes de requête
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Requête SQL générée: {sql[:500]}...")
            logger.debug(f"Jointures métadonnées: {metadata_joins}")
            logger.debug(
                f"Expressions: map={map_name_expr}, playlist={playlist_name_expr}, pair={pair_name_expr}"
            )

        try:
            result = conn.execute(sql, all_params) if all_params else conn.execute(sql)
        except Exception as e:
            # Si la requête avec jointures échoue, essayer sans jointures
            logger.warning(
                f"Erreur requête avec jointures métadonnées: {e}. Fallback sans jointures."
            )
            logger.debug(f"Requête SQL qui a échoué: {sql}")
            # Fallback sans jointures métadonnées mais avec jointure MMR si possible
            sql_fallback = f"""
                SELECT
                    match_stats.match_id,
                    match_stats.start_time,
                    match_stats.map_id,
                    match_stats.map_name,
                    match_stats.playlist_id,
                    match_stats.playlist_name,
                    match_stats.pair_id,
                    match_stats.pair_name,
                    match_stats.game_variant_id,
                    match_stats.game_variant_name,
                    match_stats.outcome,
                    match_stats.team_id,
                    match_stats.kda,
                    match_stats.max_killing_spree,
                    match_stats.headshot_kills,
                    match_stats.avg_life_seconds,
                    match_stats.time_played_seconds,
                    match_stats.kills,
                    match_stats.deaths,
                    match_stats.assists,
                    match_stats.accuracy,
                    match_stats.my_team_score,
                    match_stats.enemy_team_score,
                    {team_mmr_expr} as team_mmr,
                    {enemy_mmr_expr} as enemy_mmr,
                    {personal_score_select}
                FROM {source_sql}{pms_join}
                WHERE {where_sql}
                ORDER BY match_stats.start_time ASC
                {pagination_sql}
            """
            result = (
                conn.execute(sql_fallback, all_params) if all_params else conn.execute(sql_fallback)
            )
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
                personal_score=row[columns.index("personal_score")]
                if "personal_score" in columns
                else None,
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

        # Source v5 (shared) ou v4 (locale)
        source_sql, source_params = self._get_match_source(conn)
        is_shared = bool(source_params)

        # Résoudre les métadonnées depuis meta.* si disponible
        metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr = (
            self._build_metadata_resolution(conn)
        )

        # Fallback MMR depuis player_match_stats si disponible
        pms_join, team_mmr_expr, enemy_mmr_expr = self._build_mmr_fallback(conn)

        if is_shared:
            personal_score_select = "match_stats.personal_score"
        else:
            personal_score_select = self._select_optional_column(
                conn,
                table_name="match_stats",
                table_alias="match_stats",
                column_name="personal_score",
            )

        sql = f"""
            SELECT
                match_stats.match_id,
                match_stats.start_time,
                match_stats.map_id,
                {map_name_expr} as map_name,
                match_stats.playlist_id,
                {playlist_name_expr} as playlist_name,
                match_stats.pair_id,
                {pair_name_expr} as pair_name,
                match_stats.game_variant_id,
                match_stats.game_variant_name,
                match_stats.outcome,
                match_stats.team_id,
                match_stats.kda,
                match_stats.max_killing_spree,
                match_stats.headshot_kills,
                match_stats.avg_life_seconds,
                match_stats.time_played_seconds,
                match_stats.kills,
                match_stats.deaths,
                match_stats.assists,
                match_stats.accuracy,
                match_stats.my_team_score,
                match_stats.enemy_team_score,
                {team_mmr_expr} as team_mmr,
                {enemy_mmr_expr} as enemy_mmr,
                {personal_score_select}
            FROM {source_sql}{metadata_joins}{pms_join}
            WHERE match_stats.start_time >= ? AND match_stats.start_time <= ?
            ORDER BY match_stats.start_time ASC
        """

        all_params = source_params + [start_date, end_date]
        result = conn.execute(sql, all_params)
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
                personal_score=row[columns.index("personal_score")]
                if "personal_score" in columns
                else None,
            )
            for row in rows
        ]

    def get_match_count(self) -> int:
        """Retourne le nombre total de matchs.

        En mode v5, compte depuis shared.match_participants pour le xuid.
        En mode v4, compte depuis match_stats locale.
        """
        conn = self._get_connection()
        if (
            self.has_shared
            and self._has_shared_table("match_registry")
            and self._has_shared_table("match_participants")
        ):
            result = conn.execute(
                "SELECT COUNT(*) FROM shared.match_participants WHERE xuid = ?",
                [self._xuid],
            ).fetchone()
        else:
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

        # Source v5 (shared) ou v4 (locale)
        source_sql, source_params = self._get_match_source(conn)
        is_shared = bool(source_params)

        # Résoudre les métadonnées depuis meta.* si disponible
        metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr = (
            self._build_metadata_resolution(conn)
        )

        # Fallback MMR depuis player_match_stats si disponible
        pms_join, team_mmr_expr, enemy_mmr_expr = self._build_mmr_fallback(conn)

        if is_shared:
            personal_score_select = "match_stats.personal_score"
        else:
            personal_score_select = self._select_optional_column(
                conn,
                table_name="match_stats",
                table_alias="match_stats",
                column_name="personal_score",
            )

        where_clauses = []
        if not include_firefight:
            where_clauses.append("match_stats.is_firefight = FALSE")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
            SELECT
                match_stats.match_id,
                match_stats.start_time,
                match_stats.map_id,
                {map_name_expr} as map_name,
                match_stats.playlist_id,
                {playlist_name_expr} as playlist_name,
                match_stats.pair_id,
                {pair_name_expr} as pair_name,
                match_stats.game_variant_id,
                match_stats.game_variant_name,
                match_stats.outcome,
                match_stats.team_id,
                match_stats.kda,
                match_stats.max_killing_spree,
                match_stats.headshot_kills,
                match_stats.avg_life_seconds,
                match_stats.time_played_seconds,
                match_stats.kills,
                match_stats.deaths,
                match_stats.assists,
                match_stats.accuracy,
                match_stats.my_team_score,
                match_stats.enemy_team_score,
                {team_mmr_expr} as team_mmr,
                {enemy_mmr_expr} as enemy_mmr,
                {personal_score_select}
            FROM {source_sql}{metadata_joins}{pms_join}
            WHERE {where_sql}
            ORDER BY match_stats.start_time DESC
            LIMIT {int(limit)}
        """

        result = conn.execute(sql, source_params) if source_params else conn.execute(sql)
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
                personal_score=row[columns.index("personal_score")]
                if "personal_score" in columns
                else None,
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

        # Source v5 (shared) ou v4 (locale)
        source_sql, source_params = self._get_match_source(conn)
        is_shared = bool(source_params)

        # Résoudre les métadonnées depuis meta.* si disponible
        metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr = (
            self._build_metadata_resolution(conn)
        )

        # Fallback MMR depuis player_match_stats si disponible
        pms_join, team_mmr_expr, enemy_mmr_expr = self._build_mmr_fallback(conn)

        if is_shared:
            personal_score_select = "match_stats.personal_score"
        else:
            personal_score_select = self._select_optional_column(
                conn,
                table_name="match_stats",
                table_alias="match_stats",
                column_name="personal_score",
            )

        where_clauses = []
        if not include_firefight:
            where_clauses.append("match_stats.is_firefight = FALSE")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        order_dir = "DESC" if order_desc else "ASC"

        sql = f"""
            SELECT
                match_stats.match_id,
                match_stats.start_time,
                match_stats.map_id,
                {map_name_expr} as map_name,
                match_stats.playlist_id,
                {playlist_name_expr} as playlist_name,
                match_stats.pair_id,
                {pair_name_expr} as pair_name,
                match_stats.game_variant_id,
                match_stats.game_variant_name,
                match_stats.outcome,
                match_stats.team_id,
                match_stats.kda,
                match_stats.max_killing_spree,
                match_stats.headshot_kills,
                match_stats.avg_life_seconds,
                match_stats.time_played_seconds,
                match_stats.kills,
                match_stats.deaths,
                match_stats.assists,
                match_stats.accuracy,
                match_stats.my_team_score,
                match_stats.enemy_team_score,
                {team_mmr_expr} as team_mmr,
                {enemy_mmr_expr} as enemy_mmr,
                {personal_score_select}
            FROM {source_sql}{metadata_joins}{pms_join}
            WHERE {where_sql}
            ORDER BY match_stats.start_time {order_dir}
            LIMIT {int(page_size)} OFFSET {int(offset)}
        """

        result = conn.execute(sql, source_params) if source_params else conn.execute(sql)
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
                personal_score=row[columns.index("personal_score")]
                if "personal_score" in columns
                else None,
            )
            for row in rows
        ]

        return matches, total_pages

    # =========================================================================
    # Chargement batch MMR (Sprint 4.2)
    # =========================================================================

    def load_match_mmr_batch(
        self, match_ids: list[str]
    ) -> dict[str, tuple[float | None, float | None]]:
        """Charge le MMR pour plusieurs matchs en une seule requête.

        Utilise match_stats avec fallback sur player_match_stats si les MMR
        sont NULL dans match_stats (cas des anciens matchs synchronisés
        avant l'extraction des MMR vers match_stats).

        Args:
            match_ids: Liste des match_id à charger.

        Returns:
            Dict match_id -> (team_mmr, enemy_mmr).
        """
        if not match_ids:
            return {}

        conn = self._get_connection()

        placeholders = ", ".join(["?" for _ in match_ids])

        # Vérifier si player_match_stats existe pour le fallback
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main' AND table_name='player_match_stats'"
        ).fetchall()
        has_pms = len(tables) > 0

        if has_pms:
            # Utiliser COALESCE pour fallback sur player_match_stats
            result = conn.execute(
                f"""
                SELECT
                    ms.match_id,
                    COALESCE(ms.team_mmr, pms.team_mmr) as team_mmr,
                    COALESCE(ms.enemy_mmr, pms.enemy_mmr) as enemy_mmr
                FROM match_stats ms
                LEFT JOIN player_match_stats pms ON ms.match_id = pms.match_id
                WHERE ms.match_id IN ({placeholders})
                """,
                match_ids,
            )
        else:
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
    # Chargement Polars zero-copy (Sprint 19 — hot path optimisé)
    # =========================================================================

    def load_matches_as_polars(
        self,
        *,
        include_firefight: bool = True,
        columns: list[str] | None = None,
    ) -> pl.DataFrame:
        """Charge les matchs en DataFrame Polars via Arrow zero-copy.

        Chemin optimisé S19 : DuckDB → Arrow → Polars sans intermédiaire
        MatchRow ni reconstruction Python. ~3× moins de copies mémoire
        que load_matches() + reconstruction DataFrame.

        Args:
            include_firefight: Inclure les matchs PvE.
            columns: Liste de colonnes à projeter (None = toutes).
                     Colonnes disponibles : match_id, start_time, map_id,
                     map_name, playlist_id, playlist_name, pair_id,
                     pair_name, game_variant_id, game_variant_name,
                     outcome, team_id, kda, max_killing_spree,
                     headshot_kills, avg_life_seconds, time_played_seconds,
                     kills, deaths, assists, accuracy, my_team_score,
                     enemy_team_score, team_mmr, enemy_mmr, personal_score.

        Returns:
            DataFrame Polars avec les colonnes demandées.
        """
        conn = self._get_connection()

        # Source v5 (shared) ou v4 (locale)
        source_sql, source_params = self._get_match_source(conn)
        is_shared = bool(source_params)

        where_clauses = []
        if not include_firefight:
            where_clauses.append("match_stats.is_firefight = FALSE")
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Résoudre les métadonnées
        metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr = (
            self._build_metadata_resolution(conn)
        )
        pms_join, team_mmr_expr, enemy_mmr_expr = self._build_mmr_fallback(conn)
        if is_shared:
            personal_score_select = "match_stats.personal_score"
        else:
            personal_score_select = self._select_optional_column(
                conn,
                table_name="match_stats",
                table_alias="match_stats",
                column_name="personal_score",
            )

        # Colonnes complètes avec alias standardisés
        all_select_exprs = f"""
                match_stats.match_id,
                match_stats.start_time,
                match_stats.map_id,
                {map_name_expr} as map_name,
                match_stats.playlist_id,
                {playlist_name_expr} as playlist_name,
                match_stats.pair_id,
                {pair_name_expr} as pair_name,
                match_stats.game_variant_id,
                match_stats.game_variant_name,
                match_stats.outcome,
                match_stats.team_id,
                match_stats.kda,
                match_stats.max_killing_spree,
                match_stats.headshot_kills,
                match_stats.avg_life_seconds,
                match_stats.time_played_seconds,
                COALESCE(match_stats.kills, 0) as kills,
                COALESCE(match_stats.deaths, 0) as deaths,
                COALESCE(match_stats.assists, 0) as assists,
                match_stats.accuracy,
                match_stats.my_team_score,
                match_stats.enemy_team_score,
                {team_mmr_expr} as team_mmr,
                {enemy_mmr_expr} as enemy_mmr,
                {personal_score_select}
        """

        sql = f"""
            SELECT {all_select_exprs}
            FROM {source_sql}{metadata_joins}{pms_join}
            WHERE {where_sql}
            ORDER BY match_stats.start_time ASC
        """

        try:
            result = conn.execute(sql, source_params) if source_params else conn.execute(sql)
            df = result_to_polars(result)
        except Exception as e:
            logger.warning(f"Requête avec jointures échouée: {e}. Fallback.")
            sql_fallback = f"""
                SELECT
                    match_stats.match_id,
                    match_stats.start_time,
                    match_stats.map_id,
                    match_stats.map_name,
                    match_stats.playlist_id,
                    match_stats.playlist_name,
                    match_stats.pair_id,
                    match_stats.pair_name,
                    match_stats.game_variant_id,
                    match_stats.game_variant_name,
                    match_stats.outcome,
                    match_stats.team_id,
                    match_stats.kda,
                    match_stats.max_killing_spree,
                    match_stats.headshot_kills,
                    match_stats.avg_life_seconds,
                    match_stats.time_played_seconds,
                    COALESCE(match_stats.kills, 0) as kills,
                    COALESCE(match_stats.deaths, 0) as deaths,
                    COALESCE(match_stats.assists, 0) as assists,
                    match_stats.accuracy,
                    match_stats.my_team_score,
                    match_stats.enemy_team_score,
                    {team_mmr_expr} as team_mmr,
                    {enemy_mmr_expr} as enemy_mmr,
                    {personal_score_select}
                FROM {source_sql}{pms_join}
                WHERE {where_sql}
                ORDER BY match_stats.start_time ASC
            """
            result = (
                conn.execute(sql_fallback, source_params)
                if source_params
                else conn.execute(sql_fallback)
            )
            df = result_to_polars(result)

        if df.is_empty():
            return df

        # Calculer le ratio en Polars (COALESCE kills/deaths déjà fait en SQL)
        df = df.with_columns(
            pl.when(pl.col("deaths") > 0)
            .then(
                (pl.col("kills").cast(pl.Float64) + pl.col("assists").cast(pl.Float64) / 2.0)
                / pl.col("deaths").cast(pl.Float64)
            )
            .otherwise(pl.lit(float("nan")))
            .alias("ratio")
        )

        # Renommer avg_life_seconds → average_life_seconds pour compat avec le code existant
        if "avg_life_seconds" in df.columns:
            df = df.rename({"avg_life_seconds": "average_life_seconds"})

        # Projection de colonnes si demandée (tâche 19.3)
        if columns is not None:
            available = [c for c in columns if c in df.columns]
            df = df.select(available)

        return df

    # =========================================================================
    # Export Polars (legacy — préférer load_matches_as_polars)
    # =========================================================================

    def load_match_stats_as_polars(
        self,
        *,
        match_ids: list[str] | None = None,
        limit: int | None = None,
        include_firefight: bool = True,
    ):
        """Charge les stats de matchs en DataFrame Polars.

        Optimisé pour les analyses avec Polars.

        Args:
            match_ids: Filtrer par une liste de matchs.
            limit: Limite du nombre de résultats.
            include_firefight: Inclure les matchs PvE.

        Returns:
            DataFrame Polars avec les colonnes de match_stats.
        """
        conn = self._get_connection()

        # Source v5 (shared) ou v4 (locale)
        source_sql, source_params = self._get_match_source(conn)

        where_clauses = []
        params: list = []

        if match_ids:
            placeholders = ", ".join(["?" for _ in match_ids])
            where_clauses.append(f"match_id IN ({placeholders})")
            params.extend(match_ids)

        if not include_firefight:
            where_clauses.append("is_firefight = FALSE")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        limit_sql = f"LIMIT {int(limit)}" if limit else ""

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
                kills,
                deaths,
                assists,
                kda,
                accuracy,
                headshot_kills,
                max_killing_spree,
                time_played_seconds,
                avg_life_seconds,
                my_team_score,
                enemy_team_score,
                team_mmr,
                enemy_mmr
            FROM {source_sql}
            WHERE {where_sql}
            ORDER BY start_time ASC
            {limit_sql}
        """

        all_params = source_params + params
        try:
            result = conn.execute(sql, all_params) if all_params else conn.execute(sql)
            return result_to_polars(result)
        except Exception as e:
            logger.warning(f"Erreur chargement match_stats Polars: {e}")
            import polars as pl

            return pl.DataFrame()
