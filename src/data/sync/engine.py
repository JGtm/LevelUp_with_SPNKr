"""Moteur de synchronisation DuckDB unifié.

Ce module contient le DuckDBSyncEngine qui orchestre tout le pipeline :
API SPNKr → Transformation → DuckDB (direct, sans intermédiaire)

Usage:
    engine = DuckDBSyncEngine(
        player_db_path="data/players/Chocoboflor/stats.duckdb",
        xuid="123456789",
        gamertag="Chocoboflor",
    )

    # Sync incrémentale (rapide)
    result = await engine.sync_delta()
    print(result.to_message())

    # Sync complète (backfill)
    result = await engine.sync_full(SyncOptions(max_matches=500))
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from src.data.sync.api_client import SPNKrAPIClient, Tokens, get_tokens_from_env
from src.data.sync.models import (
    CareerRankData,
    MatchStatsRow,
    PlayerMatchStatsRow,
    SyncOptions,
    SyncResult,
)
from src.data.sync.transformers import (
    extract_aliases,
    extract_xuids_from_match,
    transform_highlight_events,
    transform_match_stats,
    transform_skill_stats,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Schéma DuckDB pour les nouvelles tables
# =============================================================================

SYNC_SCHEMA_DDL = """
-- Table player_match_stats (MMR/skill par match)
CREATE TABLE IF NOT EXISTS player_match_stats (
    match_id VARCHAR PRIMARY KEY,
    xuid VARCHAR NOT NULL,
    team_id TINYINT,
    team_mmr FLOAT,
    enemy_mmr FLOAT,
    kills_expected FLOAT,
    kills_stddev FLOAT,
    deaths_expected FLOAT,
    deaths_stddev FLOAT,
    assists_expected FLOAT,
    assists_stddev FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table highlight_events (kills, deaths depuis les films)
CREATE TABLE IF NOT EXISTS highlight_events (
    id INTEGER PRIMARY KEY,
    match_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    time_ms INTEGER,
    xuid VARCHAR,
    gamertag VARCHAR,
    type_hint INTEGER,
    raw_json VARCHAR
);
CREATE INDEX IF NOT EXISTS idx_highlight_match ON highlight_events(match_id);

-- Table killer_victim_pairs (Sprint 8 - Paires killer→victim par match)
-- Permet de calculer némésis/souffre-douleur sans recalculer depuis highlight_events
CREATE TABLE IF NOT EXISTS killer_victim_pairs (
    id INTEGER PRIMARY KEY,
    match_id VARCHAR NOT NULL,
    killer_xuid VARCHAR NOT NULL,
    killer_gamertag VARCHAR,
    victim_xuid VARCHAR NOT NULL,
    victim_gamertag VARCHAR,
    kill_count INTEGER DEFAULT 1,
    time_ms INTEGER,
    is_validated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kv_match ON killer_victim_pairs(match_id);
CREATE INDEX IF NOT EXISTS idx_kv_killer ON killer_victim_pairs(killer_xuid);
CREATE INDEX IF NOT EXISTS idx_kv_victim ON killer_victim_pairs(victim_xuid);

-- Table personal_score_awards (Sprint 8 - Décomposition du score personnel)
-- Stocke les awards individuels pour analyse de la contribution aux objectifs
CREATE TABLE IF NOT EXISTS personal_score_awards (
    id INTEGER PRIMARY KEY,
    match_id VARCHAR NOT NULL,
    xuid VARCHAR NOT NULL,
    award_name VARCHAR NOT NULL,
    award_category VARCHAR,
    award_count INTEGER DEFAULT 1,
    award_score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_psa_match ON personal_score_awards(match_id);
CREATE INDEX IF NOT EXISTS idx_psa_xuid ON personal_score_awards(xuid);
CREATE INDEX IF NOT EXISTS idx_psa_category ON personal_score_awards(award_category);

-- Table xuid_aliases (correspondances XUID → Gamertag)
CREATE TABLE IF NOT EXISTS xuid_aliases (
    xuid VARCHAR PRIMARY KEY,
    gamertag VARCHAR NOT NULL,
    last_seen TIMESTAMP,
    source VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_aliases_gamertag ON xuid_aliases(gamertag);

-- Table sync_meta (métadonnées de synchronisation)
CREATE TABLE IF NOT EXISTS sync_meta (
    key VARCHAR PRIMARY KEY,
    value VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table career_progression (Phase 5 - Rang carrière)
CREATE TABLE IF NOT EXISTS career_progression (
    id INTEGER PRIMARY KEY,
    xuid VARCHAR NOT NULL,
    rank INTEGER NOT NULL,
    rank_name VARCHAR,
    rank_tier VARCHAR,
    current_xp INTEGER,
    xp_for_next_rank INTEGER,
    xp_total INTEGER,
    is_max_rank BOOLEAN DEFAULT FALSE,
    adornment_path VARCHAR,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_career_xuid ON career_progression(xuid);
CREATE INDEX IF NOT EXISTS idx_career_date ON career_progression(recorded_at);
"""


# =============================================================================
# DuckDBSyncEngine
# =============================================================================


class DuckDBSyncEngine:
    """Moteur de synchronisation API → DuckDB unifié.

    Gère tout le pipeline en une seule étape :
    1. Fetch depuis l'API SPNKr
    2. Transformation via transformers.py
    3. Upsert direct dans DuckDB
    4. Mise à jour des agrégats

    Thread-safe via lock asyncio pour les écritures DB.
    """

    def __init__(
        self,
        player_db_path: Path | str,
        *,
        xuid: str,
        gamertag: str,
        metadata_db_path: Path | str | None = None,
        tokens: Tokens | None = None,
    ) -> None:
        """
        Args:
            player_db_path: Chemin vers stats.duckdb du joueur.
            xuid: XUID du joueur.
            gamertag: Gamertag pour l'identification API.
            metadata_db_path: Chemin vers metadata.duckdb (auto-détecté si None).
            tokens: Tokens SPNKr pré-fournis (sinon récupérés depuis env).
        """
        self._player_db_path = Path(player_db_path)
        self._xuid = xuid
        self._gamertag = gamertag
        self._tokens = tokens

        # Auto-détection du chemin metadata.duckdb
        if metadata_db_path is None:
            data_dir = self._player_db_path.parent.parent.parent
            self._metadata_db_path = data_dir / "warehouse" / "metadata.duckdb"
        else:
            self._metadata_db_path = Path(metadata_db_path)

        self._connection: duckdb.DuckDBPyConnection | None = None
        self._db_lock = asyncio.Lock()
        self._existing_match_ids: set[str] | None = None

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Retourne une connexion DuckDB (lecture/écriture)."""
        if self._connection is None:
            # Créer le dossier parent si nécessaire
            self._player_db_path.parent.mkdir(parents=True, exist_ok=True)

            # Connexion en lecture/écriture
            self._connection = duckdb.connect(
                str(self._player_db_path),
                read_only=False,
            )

            # Configuration
            self._connection.execute("SET memory_limit = '512MB'")
            self._connection.execute("SET enable_object_cache = true")

            # S'assurer que le schéma existe
            self._ensure_schema()

        return self._connection

    def _ensure_schema(self) -> None:
        """S'assure que les tables nécessaires existent."""
        conn = self._connection
        if conn is None:
            return

        # Tables de sync (nouvelles)
        for stmt in SYNC_SCHEMA_DDL.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    conn.execute(stmt)
                except Exception as e:
                    # Index déjà existant ou autre erreur non fatale
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Schema DDL warning: {e}")

    def _load_existing_match_ids(self) -> set[str]:
        """Charge les IDs des matchs existants depuis la DB."""
        if self._existing_match_ids is not None:
            return self._existing_match_ids

        try:
            conn = self._get_connection()
            result = conn.execute(
                "SELECT match_id FROM match_stats WHERE match_id IS NOT NULL"
            ).fetchall()
            self._existing_match_ids = {str(r[0]) for r in result if r[0]}
        except Exception:
            self._existing_match_ids = set()

        return self._existing_match_ids

    def _update_sync_meta(self, key: str, value: str) -> None:
        """Met à jour une entrée dans sync_meta."""
        conn = self._get_connection()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT OR REPLACE INTO sync_meta (key, value, updated_at)
               VALUES (?, ?, ?)""",
            (key, value, now),
        )

    def _get_sync_meta(self, key: str) -> str | None:
        """Récupère une valeur depuis sync_meta."""
        try:
            conn = self._get_connection()
            result = conn.execute("SELECT value FROM sync_meta WHERE key = ?", (key,)).fetchone()
            return result[0] if result else None
        except Exception:
            return None

    async def sync_delta(
        self,
        options: SyncOptions | None = None,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> SyncResult:
        """Synchronisation incrémentale (nouveaux matchs uniquement).

        S'arrête dès qu'un match déjà connu est rencontré.
        Optimal pour les synchronisations régulières (< 10s).

        Args:
            options: Options de sync (défauts si None).
            progress_callback: Callback (current, total) pour progression.

        Returns:
            SyncResult avec les détails.
        """
        return await self._sync_internal(
            options or SyncOptions(),
            delta_mode=True,
            progress_callback=progress_callback,
        )

    async def sync_full(
        self,
        options: SyncOptions | None = None,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> SyncResult:
        """Synchronisation complète (tous les matchs).

        Continue même si des matchs existent déjà (mise à jour).
        Utile pour backfill de données manquantes.

        Args:
            options: Options de sync (défauts si None).
            progress_callback: Callback (current, total) pour progression.

        Returns:
            SyncResult avec les détails.
        """
        return await self._sync_internal(
            options or SyncOptions(),
            delta_mode=False,
            progress_callback=progress_callback,
        )

    async def _sync_internal(
        self,
        options: SyncOptions,
        *,
        delta_mode: bool,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> SyncResult:
        """Implémentation interne de la synchronisation."""
        result = SyncResult()
        result.started_at = datetime.now(timezone.utc)
        start_time = time.time()

        try:
            # Récupérer les tokens si nécessaire
            if self._tokens is None:
                self._tokens = await get_tokens_from_env()

            # Charger les matchs existants
            existing_ids = self._load_existing_match_ids()
            logger.info(f"Matchs existants en DB: {len(existing_ids)}")

            if delta_mode and not existing_ids:
                logger.warning("Mode delta mais aucun match existant!")

            # Créer le client API
            async with SPNKrAPIClient(
                tokens=self._tokens,
                requests_per_second=options.requests_per_second,
            ) as client:
                result = await self._process_matches(
                    client,
                    options,
                    existing_ids,
                    delta_mode=delta_mode,
                    progress_callback=progress_callback,
                )

            # Rafraîchir les agrégats après sync
            if result.matches_inserted > 0:
                await self._refresh_aggregates_async()

            # Mettre à jour les métadonnées
            self._update_sync_meta("last_sync_at", datetime.now(timezone.utc).isoformat())
            self._update_sync_meta("last_sync_mode", "delta" if delta_mode else "full")
            self._update_sync_meta("last_sync_matches", str(result.matches_inserted))

            # Commit final
            conn = self._get_connection()
            conn.commit()

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Erreur sync: {e}")

        result.finished_at = datetime.now(timezone.utc)
        result.duration_seconds = time.time() - start_time

        return result

    async def _process_matches(
        self,
        client: SPNKrAPIClient,
        options: SyncOptions,
        existing_ids: set[str],
        *,
        delta_mode: bool,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> SyncResult:
        """Traite les matchs depuis l'API."""
        result = SyncResult()
        result.started_at = datetime.now(timezone.utc)

        start = 0
        remaining = options.max_matches
        semaphore = asyncio.Semaphore(options.parallel_matches)

        while remaining > 0:
            # Récupérer un batch d'historique
            batch_size = min(25, remaining)

            history = await client.get_match_history(
                self._gamertag,
                match_type=options.match_type,
                start=start,
                count=batch_size,
            )

            if not history:
                break

            # Traiter les matchs
            for item in history:
                if remaining <= 0:
                    break

                match_id = item.match_id

                # Vérifier si le match existe déjà
                if match_id in existing_ids:
                    if delta_mode:
                        logger.info(f"[DELTA] Match {match_id} déjà connu — arrêt")
                        return result
                    else:
                        result.matches_skipped += 1
                        remaining -= 1
                        start += 1
                        continue

                # Récupérer et traiter le match
                async with semaphore:
                    match_result = await self._process_single_match(
                        client,
                        match_id,
                        options,
                    )

                if match_result.get("inserted"):
                    result.matches_inserted += 1
                    result.highlight_events_inserted += match_result.get("events", 0)
                    result.skill_records_inserted += match_result.get("skill", 0)
                    result.aliases_updated += match_result.get("aliases", 0)
                    existing_ids.add(match_id)

                if match_result.get("error"):
                    result.warnings.append(match_result["error"])

                remaining -= 1
                start += 1

                # Callback de progression
                if progress_callback:
                    progress_callback(
                        options.max_matches - remaining,
                        options.max_matches,
                    )

                # Log de progression
                if result.matches_inserted > 0 and result.matches_inserted % 10 == 0:
                    logger.info(f"Importé {result.matches_inserted} matchs...")

            # Fin du batch
            if len(history) < batch_size:
                break

        return result

    async def _process_single_match(
        self,
        client: SPNKrAPIClient,
        match_id: str,
        options: SyncOptions,
    ) -> dict[str, Any]:
        """Traite un match unique : fetch, transform, insert."""
        result: dict[str, Any] = {
            "inserted": False,
            "events": 0,
            "skill": 0,
            "aliases": 0,
            "error": None,
        }

        try:
            # Récupérer les stats (obligatoire)
            stats_json = await client.get_match_stats(match_id)
            if stats_json is None:
                result["error"] = f"Impossible de récupérer {match_id}"
                return result

            # Extraire les XUIDs pour l'appel skill
            xuids = extract_xuids_from_match(stats_json)

            # Récupérer skill et events en parallèle
            skill_json = None
            highlight_events: list = []

            if options.with_skill and xuids:
                skill_json = await client.get_skill_stats(match_id, xuids)

            if options.with_highlight_events:
                highlight_events = await client.get_highlight_events(match_id)

            # Transformer les données
            match_row = transform_match_stats(stats_json, self._xuid, skill_json=skill_json)
            if match_row is None:
                result["error"] = f"Transformation échouée pour {match_id}"
                return result

            skill_row = None
            if skill_json:
                skill_row = transform_skill_stats(skill_json, match_id, self._xuid)

            event_rows = []
            if highlight_events:
                event_rows = transform_highlight_events(highlight_events, match_id)

            alias_rows = []
            if options.with_aliases:
                alias_rows = extract_aliases(stats_json)

            # Insérer dans DuckDB (protégé par lock)
            async with self._db_lock:
                self._insert_match_row(match_row)

                if skill_row:
                    self._insert_skill_row(skill_row)
                    result["skill"] = 1

                if event_rows:
                    self._insert_event_rows(event_rows)
                    result["events"] = len(event_rows)

                if alias_rows:
                    self._insert_alias_rows(alias_rows)
                    result["aliases"] = len(alias_rows)

            result["inserted"] = True

        except Exception as e:
            result["error"] = f"Erreur traitement {match_id}: {e}"
            logger.warning(result["error"])

        return result

    def _insert_match_row(self, row: MatchStatsRow) -> None:
        """Insère une ligne match_stats."""
        conn = self._get_connection()

        # Construire la requête d'insertion
        conn.execute(
            """INSERT OR REPLACE INTO match_stats (
                match_id, start_time, playlist_id, playlist_name,
                map_id, map_name, pair_id, pair_name,
                game_variant_id, game_variant_name,
                outcome, team_id, kills, deaths, assists,
                kda, accuracy, headshot_kills, max_killing_spree,
                time_played_seconds, avg_life_seconds,
                my_team_score, enemy_team_score,
                team_mmr, enemy_mmr,
                is_firefight, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row.match_id,
                row.start_time,
                row.playlist_id,
                row.playlist_name,
                row.map_id,
                row.map_name,
                row.pair_id,
                row.pair_name,
                row.game_variant_id,
                row.game_variant_name,
                row.outcome,
                row.team_id,
                row.kills,
                row.deaths,
                row.assists,
                row.kda,
                row.accuracy,
                row.headshot_kills,
                row.max_killing_spree,
                row.time_played_seconds,
                row.avg_life_seconds,
                row.my_team_score,
                row.enemy_team_score,
                row.team_mmr,
                row.enemy_mmr,
                row.is_firefight,
                datetime.now(timezone.utc),
            ),
        )

    def _insert_skill_row(self, row: PlayerMatchStatsRow) -> None:
        """Insère une ligne player_match_stats."""
        conn = self._get_connection()

        conn.execute(
            """INSERT OR REPLACE INTO player_match_stats (
                match_id, xuid, team_id, team_mmr, enemy_mmr,
                kills_expected, kills_stddev,
                deaths_expected, deaths_stddev,
                assists_expected, assists_stddev,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row.match_id,
                row.xuid,
                row.team_id,
                row.team_mmr,
                row.enemy_mmr,
                row.kills_expected,
                row.kills_stddev,
                row.deaths_expected,
                row.deaths_stddev,
                row.assists_expected,
                row.assists_stddev,
                datetime.now(timezone.utc),
            ),
        )

    def _insert_event_rows(self, rows: list) -> None:
        """Insère des lignes highlight_events."""
        if not rows:
            return

        conn = self._get_connection()

        for row in rows:
            with contextlib.suppress(Exception):
                conn.execute(
                    """INSERT INTO highlight_events (
                        match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row.match_id,
                        row.event_type,
                        row.time_ms,
                        row.xuid,
                        row.gamertag,
                        row.type_hint,
                        row.raw_json,
                    ),
                )

    def _insert_alias_rows(self, rows: list) -> None:
        """Insère des lignes xuid_aliases."""
        if not rows:
            return

        conn = self._get_connection()

        for row in rows:
            with contextlib.suppress(Exception):
                conn.execute(
                    """INSERT INTO xuid_aliases (xuid, gamertag, last_seen, source, updated_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(xuid) DO UPDATE SET
                           gamertag = CASE
                               WHEN excluded.gamertag != '' AND excluded.gamertag != xuid_aliases.gamertag
                               THEN excluded.gamertag
                               ELSE xuid_aliases.gamertag
                           END,
                           last_seen = excluded.last_seen,
                           updated_at = CURRENT_TIMESTAMP""",
                    (
                        row.xuid,
                        row.gamertag,
                        row.last_seen,
                        row.source,
                        datetime.now(timezone.utc),
                    ),
                )

    async def _refresh_aggregates_async(self) -> None:
        """Rafraîchit les agrégats après sync (async wrapper)."""
        # Exécuter dans un thread pour ne pas bloquer l'event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.refresh_aggregates)

    def refresh_aggregates(self) -> dict[str, int]:
        """Recalcule les tables d'agrégats après sync.

        Met à jour :
        - Vues matérialisées (mv_*)
        - teammates_aggregate (à implémenter)

        Returns:
            Dict table_name → rows_affected.
        """
        result: dict[str, int] = {}

        try:
            # Appeler refresh_materialized_views si disponible
            # (implémenté dans DuckDBRepository)
            try:
                from src.data.repositories.duckdb_repo import DuckDBRepository

                repo = DuckDBRepository(
                    self._player_db_path,
                    self._xuid,
                    read_only=False,
                )
                repo.refresh_materialized_views()
                result["materialized_views"] = 1
            except Exception as e:
                logger.debug(f"refresh_materialized_views non disponible: {e}")

        except Exception as e:
            logger.warning(f"Erreur refresh_aggregates: {e}")

        return result

    def get_sync_status(self) -> dict[str, Any]:
        """Retourne l'état de la dernière synchronisation.

        Returns:
            Dict avec last_sync_at, total_matches, etc.
        """
        try:
            conn = self._get_connection()

            # Compter les matchs
            match_count = conn.execute("SELECT COUNT(*) FROM match_stats").fetchone()[0]

            # Récupérer les métadonnées
            last_sync = self._get_sync_meta("last_sync_at")
            last_mode = self._get_sync_meta("last_sync_mode")
            last_matches = self._get_sync_meta("last_sync_matches")

            return {
                "total_matches": match_count,
                "last_sync_at": last_sync,
                "last_sync_mode": last_mode,
                "last_sync_matches": int(last_matches) if last_matches else 0,
                "gamertag": self._gamertag,
                "xuid": self._xuid,
            }
        except Exception as e:
            return {"error": str(e)}

    # =========================================================================
    # Méthodes Phase 5 : Career Rank
    # =========================================================================

    async def sync_career_rank(self) -> CareerRankData | None:
        """Synchronise la progression du rang carrière.

        Récupère les données depuis l'API et les sauvegarde en BDD.
        Crée un snapshot historique pour suivre la progression.

        Returns:
            CareerRankData ou None si erreur.
        """
        try:
            # Récupérer les tokens si nécessaire
            if self._tokens is None:
                self._tokens = await get_tokens_from_env()

            async with SPNKrAPIClient(tokens=self._tokens) as client:
                career_data = await client.get_career_rank_progression(self._xuid)

                if career_data is None:
                    logger.warning(f"Career rank non disponible pour {self._gamertag}")
                    return None

                # Sauvegarder en BDD
                self._save_career_rank(career_data)

                logger.info(
                    f"Career rank sync: {self._gamertag} → "
                    f"Rang {career_data.current_rank} ({career_data.current_rank_name})"
                )

                return career_data

        except Exception as e:
            logger.error(f"Erreur sync_career_rank: {e}")
            return None

    def _save_career_rank(self, data: CareerRankData) -> None:
        """Sauvegarde un snapshot de la progression de rang."""
        conn = self._get_connection()
        now = datetime.now(timezone.utc)

        conn.execute(
            """INSERT INTO career_progression (
                xuid, rank, rank_name, rank_tier,
                current_xp, xp_for_next_rank, xp_total,
                is_max_rank, adornment_path, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.xuid,
                data.current_rank,
                data.current_rank_name,
                data.current_rank_tier,
                data.current_xp,
                data.xp_for_next_rank,
                data.xp_total,
                data.is_max_rank,
                data.adornment_path,
                now,
            ),
        )
        conn.commit()

        # Mettre à jour sync_meta
        self._update_sync_meta("last_career_sync_at", now.isoformat())
        self._update_sync_meta("current_rank", str(data.current_rank))

    def get_career_rank_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Récupère l'historique de progression de rang.

        Args:
            limit: Nombre maximum d'entrées.

        Returns:
            Liste des snapshots de progression.
        """
        try:
            conn = self._get_connection()
            result = conn.execute(
                """SELECT rank, rank_name, rank_tier, current_xp,
                          xp_for_next_rank, xp_total, is_max_rank,
                          adornment_path, recorded_at
                   FROM career_progression
                   WHERE xuid = ?
                   ORDER BY recorded_at DESC
                   LIMIT ?""",
                (self._xuid, limit),
            ).fetchall()

            return [
                {
                    "rank": r[0],
                    "rank_name": r[1],
                    "rank_tier": r[2],
                    "current_xp": r[3],
                    "xp_for_next_rank": r[4],
                    "xp_total": r[5],
                    "is_max_rank": r[6],
                    "adornment_path": r[7],
                    "recorded_at": r[8],
                }
                for r in result
            ]

        except Exception as e:
            logger.warning(f"Erreur get_career_rank_history: {e}")
            return []

    def get_latest_career_rank(self) -> dict[str, Any] | None:
        """Récupère le dernier rang carrière enregistré.

        Returns:
            Dict avec les infos du rang ou None.
        """
        history = self.get_career_rank_history(limit=1)
        return history[0] if history else None

    def close(self) -> None:
        """Ferme la connexion DuckDB."""
        if self._connection:
            with contextlib.suppress(Exception):
                self._connection.close()
            self._connection = None
