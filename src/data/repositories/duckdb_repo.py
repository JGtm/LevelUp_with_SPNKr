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

            # Attacher la DB metadata si elle existe et pas déjà attachée
            if self._metadata_db_path.exists() and "meta" not in self._attached_dbs:
                try:
                    self._connection.execute(
                        f"ATTACH '{self._metadata_db_path}' AS meta (READ_ONLY)"
                    )
                    self._attached_dbs.add("meta")
                    logger.debug(f"Metadata DB attachée: {self._metadata_db_path}")
                except Exception as e:
                    # Ignorer si déjà attachée (peut arriver avec connexions réutilisées)
                    if "already exists" not in str(e):
                        logger.warning(f"Impossible d'attacher metadata.duckdb: {e}")

        return self._connection

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

        # Résoudre les métadonnées depuis meta.* si disponible
        metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr = (
            self._build_metadata_resolution(conn)
        )

        # Fallback MMR depuis player_match_stats si disponible
        pms_join, team_mmr_expr, enemy_mmr_expr = self._build_mmr_fallback(conn)

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
                {enemy_mmr_expr} as enemy_mmr
            FROM match_stats{metadata_joins}{pms_join}
            WHERE {where_sql}
            ORDER BY match_stats.start_time ASC
            {pagination_sql}
        """

        # Log de debug pour diagnostiquer les problèmes de requête
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Requête SQL générée: {sql[:500]}...")
            logger.debug(f"Jointures métadonnées: {metadata_joins}")
            logger.debug(
                f"Expressions: map={map_name_expr}, playlist={playlist_name_expr}, pair={pair_name_expr}"
            )

        try:
            result = conn.execute(sql, params) if params else conn.execute(sql)
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
                    {enemy_mmr_expr} as enemy_mmr
                FROM match_stats{pms_join}
                WHERE {where_sql}
                ORDER BY match_stats.start_time ASC
                {pagination_sql}
            """
            result = conn.execute(sql_fallback, params) if params else conn.execute(sql_fallback)
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

        # Résoudre les métadonnées depuis meta.* si disponible
        metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr = (
            self._build_metadata_resolution(conn)
        )

        # Fallback MMR depuis player_match_stats si disponible
        pms_join, team_mmr_expr, enemy_mmr_expr = self._build_mmr_fallback(conn)

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
                {enemy_mmr_expr} as enemy_mmr
            FROM match_stats{metadata_joins}{pms_join}
            WHERE match_stats.start_time >= ? AND match_stats.start_time <= ?
            ORDER BY match_stats.start_time ASC
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

        # Résoudre les métadonnées depuis meta.* si disponible
        metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr = (
            self._build_metadata_resolution(conn)
        )

        # Fallback MMR depuis player_match_stats si disponible
        pms_join, team_mmr_expr, enemy_mmr_expr = self._build_mmr_fallback(conn)

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
                {enemy_mmr_expr} as enemy_mmr
            FROM match_stats{metadata_joins}{pms_join}
            WHERE {where_sql}
            ORDER BY match_stats.start_time DESC
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

        # Résoudre les métadonnées depuis meta.* si disponible
        metadata_joins, map_name_expr, playlist_name_expr, pair_name_expr = (
            self._build_metadata_resolution(conn)
        )

        # Fallback MMR depuis player_match_stats si disponible
        pms_join, team_mmr_expr, enemy_mmr_expr = self._build_mmr_fallback(conn)

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
                {enemy_mmr_expr} as enemy_mmr
            FROM match_stats{metadata_joins}{pms_join}
            WHERE {where_sql}
            ORDER BY match_stats.start_time {order_dir}
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

    def count_medal_by_match(
        self,
        match_ids: list[str],
        medal_name_id: int,
    ) -> dict[str, int]:
        """Compte une médaille spécifique pour chaque match.

        Args:
            match_ids: Liste des IDs de matchs.
            medal_name_id: ID de la médaille à compter (ex: 1512363953 pour Perfect).

        Returns:
            Dict {match_id: count} pour les matchs ayant cette médaille.
        """
        if not match_ids:
            return {}

        conn = self._get_connection()

        try:
            placeholders = ", ".join(["?" for _ in match_ids])
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

        Args:
            match_ids: Liste des IDs de matchs.
            event_type: Type d'événement ("Kill" ou "Death"). Accepte toute casse.

        Returns:
            Dict {match_id: time_ms} pour le premier événement de chaque match.
        """
        if not match_ids:
            return {}

        conn = self._get_connection()

        try:
            # Vérifier si la table existe (DuckDB utilise information_schema, pas sqlite_master)
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_name = 'highlight_events'"
            ).fetchall()
            if not tables:
                return {}

            # Normaliser event_type pour gérer les différences de casse
            # Les données peuvent contenir "kill"/"death" (minuscules) ou "Kill"/"Death" (majuscules)
            event_type_normalized = event_type.lower()

            placeholders = ", ".join(["?" for _ in match_ids])
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

    def load_match_rosters(
        self,
        match_id: str,
    ) -> dict[str, Any] | None:
        """Charge les rosters d'un match depuis killer_victim_pairs ou highlight_events.

        Utilise killer_victim_pairs si disponible (source fiable), sinon
        analyse les patterns de kills dans highlight_events.

        Returns:
            None si le match n'existe pas ou si les données sont insuffisantes.
            Sinon un dict avec la structure:
            {
                "my_team_id": int,
                "my_team": [{"xuid": str, "gamertag": str|None, "team_id": int|None, "is_me": bool}],
                "enemy_team": [...],
            }
        """
        conn = self._get_connection()

        try:
            # Obtenir le team_id du joueur principal depuis match_stats
            match_info = conn.execute(
                "SELECT team_id FROM match_stats WHERE match_id = ?",
                [match_id],
            ).fetchone()

            if not match_info:
                return None

            my_team_id = match_info[0]
            if my_team_id is None:
                return None

            my_xuid_str = str(self._xuid).strip()

            # Fonction de nettoyage des gamertags
            def _clean_gamertag(value: Any) -> str | None:
                """Nettoie un gamertag en supprimant les caractères invalides."""
                if value is None:
                    return None
                try:
                    s = str(value)
                    s = s.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
                    s = s.replace("\ufffd", "")
                    s = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", s)
                    s = re.sub(r"[\ufffe\uffff]", "", s)
                    s = re.sub(r"[\s\t]+", " ", s).strip()
                    s = s.strip("\u200b\u200c\u200d\ufeff")
                    if not s or s == "?" or s.isdigit() or s.lower().startswith("xuid("):
                        return None
                    if not any(c.isprintable() for c in s):
                        return None
                    return s
                except Exception:
                    return None

            # ======================================================================
            # MÉTHODE 1 : Utiliser killer_victim_pairs si disponible (source fiable)
            # ======================================================================
            has_kvp = False
            try:
                kvp_check = conn.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'main' AND table_name = 'killer_victim_pairs'"
                ).fetchone()
                has_kvp = kvp_check is not None
            except Exception:
                pass

            team_by_xuid: dict[str, int | None] = {}
            gamertag_by_xuid: dict[str, str | None] = {}

            if has_kvp:
                # Utiliser killer_victim_pairs pour déterminer les équipes
                # Logique : si je tue quelqu'un → adversaire, si quelqu'un me tue → adversaire
                # Si quelqu'un tue mes adversaires → coéquipier
                try:
                    kvp_result = conn.execute(
                        """
                        SELECT killer_xuid, killer_gamertag, victim_xuid, victim_gamertag, kill_count
                        FROM killer_victim_pairs
                        WHERE match_id = ?
                        """,
                        [match_id],
                    ).fetchall()

                    enemies: set[str] = set()
                    allies: set[str] = set()

                    for killer_xuid, killer_gt, victim_xuid, victim_gt, _ in kvp_result:
                        k_xu = str(killer_xuid or "").strip()
                        v_xu = str(victim_xuid or "").strip()

                        # Stocker les gamertags (préférer le plus long)
                        if k_xu:
                            k_gt = _clean_gamertag(killer_gt)
                            if k_gt and (
                                k_xu not in gamertag_by_xuid
                                or len(k_gt) > len(gamertag_by_xuid.get(k_xu) or "")
                            ):
                                gamertag_by_xuid[k_xu] = k_gt
                        if v_xu:
                            v_gt = _clean_gamertag(victim_gt)
                            if v_gt and (
                                v_xu not in gamertag_by_xuid
                                or len(v_gt) > len(gamertag_by_xuid.get(v_xu) or "")
                            ):
                                gamertag_by_xuid[v_xu] = v_gt

                        if not k_xu or not v_xu:
                            continue

                        # Si je suis le killer → la victime est un adversaire
                        if k_xu == my_xuid_str:
                            enemies.add(v_xu)
                        # Si je suis la victime → le killer est un adversaire
                        elif v_xu == my_xuid_str:
                            enemies.add(k_xu)

                    # Deuxième passe : si quelqu'un tue un adversaire confirmé → allié
                    # Si quelqu'un est tué par un adversaire confirmé → allié
                    for killer_xuid, _, victim_xuid, _, _ in kvp_result:
                        k_xu = str(killer_xuid or "").strip()
                        v_xu = str(victim_xuid or "").strip()
                        if not k_xu or not v_xu:
                            continue

                        # Si le killer tue un adversaire confirmé → le killer est un allié
                        if v_xu in enemies and k_xu != my_xuid_str:
                            allies.add(k_xu)
                        # Si la victime est tuée par un adversaire confirmé → la victime est un alliée
                        if k_xu in enemies and v_xu != my_xuid_str:
                            allies.add(v_xu)

                    # Assigner les équipes
                    team_by_xuid[my_xuid_str] = my_team_id
                    for xu in enemies:
                        if xu != my_xuid_str:
                            team_by_xuid[xu] = None  # Adversaire
                    for xu in allies:
                        if xu != my_xuid_str and xu not in enemies:
                            team_by_xuid[xu] = my_team_id  # Allié

                except Exception as e:
                    logger.debug(f"Erreur lecture killer_victim_pairs: {e}")

            # ======================================================================
            # Extraire tous les joueurs uniques (depuis kvp ou highlight_events)
            # ======================================================================
            all_xuids: set[str] = set(gamertag_by_xuid.keys())

            # Compléter avec highlight_events
            try:
                he_result = conn.execute(
                    """
                    SELECT xuid, gamertag
                    FROM (
                        SELECT xuid, gamertag,
                               ROW_NUMBER() OVER (
                                   PARTITION BY xuid
                                   ORDER BY LENGTH(COALESCE(gamertag, '')) DESC
                               ) as rn
                        FROM highlight_events
                        WHERE match_id = ? AND xuid IS NOT NULL AND xuid != ''
                    ) sub
                    WHERE rn = 1
                    """,
                    [match_id],
                ).fetchall()

                for xuid, gamertag in he_result:
                    xu = str(xuid).strip()
                    if xu:
                        all_xuids.add(xu)
                        # Préférer le gamertag le plus long
                        gt = _clean_gamertag(gamertag)
                        if gt and (
                            xu not in gamertag_by_xuid
                            or len(gt) > len(gamertag_by_xuid.get(xu) or "")
                        ):
                            gamertag_by_xuid[xu] = gt
            except Exception:
                pass

            if not all_xuids:
                return None

            # ======================================================================
            # MÉTHODE 2 : Fallback sur highlight_events si kvp n'a pas donné de résultats
            # ======================================================================
            if not team_by_xuid or len(team_by_xuid) <= 1:
                # Analyser les événements Kill/Death pour déterminer les équipes
                try:
                    kill_events = conn.execute(
                        """
                        SELECT event_type, xuid, raw_json
                        FROM highlight_events
                        WHERE match_id = ?
                          AND LOWER(event_type) IN ('kill', 'death')
                          AND xuid IS NOT NULL AND xuid != ''
                        """,
                        [match_id],
                    ).fetchall()

                    # Analyser les relations killer→victim depuis raw_json
                    killed_by_me: set[str] = set()
                    killed_me: set[str] = set()

                    for _event_type, xuid, raw_json in kill_events:
                        xuid_str = str(xuid).strip()
                        if not raw_json:
                            continue

                        try:
                            event_data = (
                                json.loads(raw_json) if isinstance(raw_json, str) else raw_json
                            )

                            # Extraire killer et victim
                            killer = (
                                event_data.get("killer_xuid")
                                or event_data.get("KillerXuid")
                                or str(
                                    event_data.get("Killer", {}).get("Xuid", "")
                                    if isinstance(event_data.get("Killer"), dict)
                                    else ""
                                )
                            )
                            victim = (
                                event_data.get("victim_xuid")
                                or event_data.get("VictimXuid")
                                or str(
                                    event_data.get("Victim", {}).get("Xuid", "")
                                    if isinstance(event_data.get("Victim"), dict)
                                    else ""
                                )
                            )

                            killer = str(killer).strip() if killer else ""
                            victim = str(victim).strip() if victim else ""

                            # Si je suis le killer
                            if killer == my_xuid_str and victim:
                                killed_by_me.add(victim)
                            # Si je suis la victime
                            elif victim == my_xuid_str and killer:
                                killed_me.add(killer)
                        except Exception:
                            pass

                    # Les joueurs que j'ai tués ou qui m'ont tué sont des adversaires
                    team_by_xuid[my_xuid_str] = my_team_id
                    for xu in killed_by_me | killed_me:
                        if xu != my_xuid_str:
                            team_by_xuid[xu] = None

                    # Les joueurs non classés qui ne sont pas adversaires sont probablement alliés
                    for xu in all_xuids:
                        if xu not in team_by_xuid:
                            # Par défaut, les non-classés sont considérés comme adversaires
                            # pour éviter le bug "tous dans mon équipe"
                            team_by_xuid[xu] = None

                except Exception as e:
                    logger.debug(f"Erreur analyse highlight_events: {e}")

            # ======================================================================
            # FALLBACK FINAL : Si toujours pas d'équipes, répartir 50/50
            # ======================================================================
            if not team_by_xuid or len([x for x in team_by_xuid.values() if x is None]) == 0:
                # Tous dans mon équipe → problème! Répartir aléatoirement
                others = [xu for xu in all_xuids if xu != my_xuid_str]
                team_by_xuid[my_xuid_str] = my_team_id
                # Mettre la moitié dans l'équipe adverse
                half = len(others) // 2
                for i, xu in enumerate(sorted(others)):
                    if i < half:
                        team_by_xuid[xu] = None  # Adversaire
                    else:
                        team_by_xuid[xu] = my_team_id  # Allié

            # ======================================================================
            # Construire les listes d'équipes
            # ======================================================================
            # Sprint Gamertag Roster Fix : Utiliser resolve_gamertags_batch pour
            # obtenir des gamertags propres depuis match_participants/xuid_aliases
            resolved_gamertags = self.resolve_gamertags_batch(list(all_xuids), match_id=match_id)

            my_team = []
            enemy_team = []

            for xuid_str in all_xuids:
                is_me = xuid_str == my_xuid_str
                # Priorité : gamertag résolu > gamertag extrait > XUID
                cleaned_gamertag = resolved_gamertags.get(xuid_str) or gamertag_by_xuid.get(
                    xuid_str
                )
                display_name = cleaned_gamertag if cleaned_gamertag else xuid_str
                player_team_id = team_by_xuid.get(xuid_str, None if not is_me else my_team_id)

                player_data = {
                    "xuid": xuid_str,
                    "gamertag": cleaned_gamertag,
                    "team_id": player_team_id,
                    "is_me": is_me,
                    "is_bot": False,
                    "display_name": display_name,
                }

                if player_team_id == my_team_id or is_me:
                    my_team.append(player_data)
                else:
                    enemy_team.append(player_data)

            # Trier: moi en premier, puis alphabétique
            def _sort_key(r: dict[str, Any]) -> tuple[int, str]:
                me_rank = 0 if r.get("is_me") else 1
                name = str(r.get("gamertag") or r.get("xuid") or "").strip().lower()
                return (me_rank, name)

            my_team.sort(key=_sort_key)
            enemy_team.sort(key=_sort_key)

            return {
                "my_team_id": int(my_team_id),
                "my_team_name": None,
                "my_team": my_team,
                "enemy_team": enemy_team,
                "enemy_team_ids": [],
                "enemy_team_names": [],
            }
        except Exception as e:
            logger.warning(f"Erreur lors du chargement des rosters pour {match_id}: {e}")
            return None

    def load_matches_with_teammate(
        self,
        teammate_xuid: str,
    ) -> list[str]:
        """Retourne les match_id joués avec un coéquipier.

        Utilise highlight_events pour détecter la présence dans le même match.

        Args:
            teammate_xuid: XUID du coéquipier.

        Returns:
            Liste des match_id où les deux joueurs apparaissent.
        """
        conn = self._get_connection()

        try:
            # Vérifier si highlight_events existe
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_name = 'highlight_events'"
            ).fetchall()
            if not tables:
                return []

            # Trouver les matchs où les deux joueurs apparaissent
            result = conn.execute(
                """
                SELECT DISTINCT me.match_id
                FROM highlight_events me
                INNER JOIN highlight_events tm ON me.match_id = tm.match_id
                WHERE me.xuid = ? AND tm.xuid = ?
                ORDER BY me.match_id DESC
                """,
                [self._xuid, teammate_xuid],
            )
            return [row[0] for row in result.fetchall()]
        except Exception:
            return []

    def load_same_team_match_ids(
        self,
        teammate_xuid: str,
    ) -> list[str]:
        """Retourne les match_id où les deux joueurs étaient dans la même équipe.

        Sprint Gamertag Roster Fix : Utilise match_participants si disponible
        pour une détermination précise des équipes. Sinon, fallback sur
        highlight_events.

        Args:
            teammate_xuid: XUID du coéquipier.

        Returns:
            Liste des match_id où les deux joueurs étaient dans la même équipe.
        """
        conn = self._get_connection()

        # Essayer avec match_participants d'abord (source fiable)
        if self._has_table("match_participants"):
            try:
                result = conn.execute(
                    """
                    SELECT DISTINCT me.match_id
                    FROM match_participants me
                    INNER JOIN match_participants tm
                        ON me.match_id = tm.match_id
                        AND me.team_id = tm.team_id
                    WHERE me.xuid = ? AND tm.xuid = ?
                    ORDER BY me.match_id DESC
                    """,
                    [self._xuid, teammate_xuid],
                )
                match_ids = [row[0] for row in result.fetchall()]
                if match_ids:
                    return match_ids
            except Exception as e:
                logger.debug(f"Erreur match_participants: {e}")

        # Fallback: utiliser highlight_events pour trouver les matchs communs
        # puis vérifier team_id dans match_stats (moins précis)
        try:
            result = conn.execute(
                """
                SELECT DISTINCT ms.match_id
                FROM match_stats ms
                WHERE ms.match_id IN (
                    SELECT DISTINCT match_id FROM highlight_events WHERE xuid = ?
                )
                AND ms.match_id IN (
                    SELECT DISTINCT match_id FROM highlight_events WHERE xuid = ?
                )
                ORDER BY ms.match_id DESC
                """,
                [self._xuid, teammate_xuid],
            )
            return [row[0] for row in result.fetchall()]
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

    # =========================================================================
    # Sprint 9 : Méthodes Polars pour killer_victim_pairs
    # =========================================================================

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
            return result.pl()
        except Exception as e:
            logger.warning(f"Erreur chargement killer_victim_pairs: {e}")
            # Retourner un DataFrame vide avec le bon schéma
            import polars as pl

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

        where_clauses = []
        params = []

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
            FROM match_stats
            WHERE {where_sql}
            ORDER BY start_time ASC
            {limit_sql}
        """

        try:
            result = conn.execute(sql, params) if params else conn.execute(sql)
            return result.pl()
        except Exception as e:
            logger.warning(f"Erreur chargement match_stats Polars: {e}")
            import polars as pl

            return pl.DataFrame()

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
            return result.pl()
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
        import polars as pl

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

    def has_match_participants(self) -> bool:
        """Vérifie si la table match_participants existe et contient des données."""
        conn = self._get_connection()
        try:
            count = conn.execute("SELECT COUNT(*) FROM match_participants").fetchone()[0]
            return count > 0
        except Exception:
            return False

    def resolve_gamertag(
        self,
        xuid: str,
        *,
        match_id: str | None = None,
    ) -> str | None:
        """Résout un XUID en gamertag avec cascade de sources.

        Sprint Gamertag Roster Fix : Fonction centralisée pour obtenir un
        gamertag propre à partir d'un XUID, en utilisant plusieurs sources.

        Priorité des sources:
        1. match_participants (pour ce match spécifique) - gamertags API propres
        2. xuid_aliases (source officielle API)
        3. teammates_aggregate (historique des coéquipiers)
        4. highlight_events (nettoyé avec extraction ASCII)

        Args:
            xuid: XUID du joueur à résoudre.
            match_id: ID du match (optionnel, améliore la résolution contextuelle).

        Returns:
            Gamertag propre ou None si non trouvé.
        """
        conn = self._get_connection()
        xuid = str(xuid).strip()

        # 1. match_participants (si match_id fourni et table existe)
        if match_id and self._has_table("match_participants"):
            try:
                result = conn.execute(
                    "SELECT gamertag FROM match_participants WHERE match_id = ? AND xuid = ?",
                    [match_id, xuid],
                ).fetchone()
                if result and result[0]:
                    return result[0]
            except Exception:
                pass

        # 2. xuid_aliases
        try:
            result = conn.execute(
                "SELECT gamertag FROM xuid_aliases WHERE xuid = ?",
                [xuid],
            ).fetchone()
            if result and result[0]:
                return result[0]
        except Exception:
            pass

        # 3. teammates_aggregate
        try:
            result = conn.execute(
                "SELECT teammate_gamertag FROM teammates_aggregate WHERE teammate_xuid = ?",
                [xuid],
            ).fetchone()
            if result and result[0]:
                return result[0]
        except Exception:
            pass

        # 4. highlight_events avec extraction ASCII
        if match_id:
            try:
                result = conn.execute(
                    "SELECT gamertag FROM highlight_events WHERE match_id = ? AND xuid = ? LIMIT 1",
                    [match_id, xuid],
                ).fetchone()
                if result and result[0]:
                    cleaned = self._extract_ascii_token(result[0])
                    if cleaned:
                        return cleaned
            except Exception:
                pass

        return None

    def _extract_ascii_token(self, value: str | None) -> str | None:
        """Extrait un token ASCII plausible depuis un gamertag corrompu.

        Les gamertags provenant de highlight_events peuvent contenir des
        caractères NUL et de contrôle (ex: 'juan1\\x00\\x00\\x00\\x00').
        Cette fonction extrait la partie lisible.

        Args:
            value: Gamertag potentiellement corrompu.

        Returns:
            Token ASCII nettoyé ou None si rien de plausible.
        """
        if value is None:
            return None

        try:
            # Extraire tous les tokens alphanumériques
            parts = re.findall(r"[A-Za-z0-9]+", str(value or ""))
            if not parts:
                return None

            # Prendre le plus long (probablement le gamertag)
            parts.sort(key=len, reverse=True)
            token = parts[0]

            # Minimum 3 caractères pour être un gamertag valide
            return token if len(token) >= 3 else None
        except Exception:
            return None

    def resolve_gamertags_batch(
        self,
        xuids: list[str],
        *,
        match_id: str | None = None,
    ) -> dict[str, str | None]:
        """Résout plusieurs XUIDs en gamertags en batch.

        Args:
            xuids: Liste des XUIDs à résoudre.
            match_id: ID du match (optionnel).

        Returns:
            Dict {xuid: gamertag} pour chaque XUID.
        """
        return {xuid: self.resolve_gamertag(xuid, match_id=match_id) for xuid in xuids}
