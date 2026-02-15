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

from src.data.sync.api_client import (
    SPNKrAPIClient,
    Tokens,
    enrich_match_info_with_assets,
    get_tokens_from_env,
)
from src.data.sync.batch_insert import (
    ALIAS_COLUMNS,
    HIGHLIGHT_EVENT_COLUMNS,
    MEDAL_COLUMNS,
    PARTICIPANT_COLUMNS,
    PERSONAL_SCORE_COLUMNS,
    SKILL_COLUMNS,
    batch_insert_rows,
    batch_upsert_rows,
)
from src.data.sync.migrations import (
    BACKFILL_FLAGS,
    ensure_backfill_completed_column,
    ensure_highlight_events_autoincrement,
)
from src.data.sync.models import (
    CareerRankData,
    MatchStatsRow,
    PlayerMatchStatsRow,
    SyncOptions,
    SyncResult,
)
from src.data.sync.transformers import (
    create_metadata_resolver,
    extract_aliases,
    extract_all_medals,
    extract_match_registry_data,
    extract_participants,
    extract_personal_score_awards,
    extract_xuids_from_match,
    transform_highlight_events,
    transform_match_stats,
    transform_personal_score_awards,
    transform_skill_stats,
)

logger = logging.getLogger(__name__)

# Import pour le calcul des scores de performance
try:
    import polars as pl

    from src.analysis.performance_config import MIN_MATCHES_FOR_RELATIVE
    from src.analysis.performance_score import compute_relative_performance_score

    _PERF_SCORE_AVAILABLE = True
except ImportError:
    pl = None
    compute_relative_performance_score = None
    MIN_MATCHES_FOR_RELATIVE = 10
    _PERF_SCORE_AVAILABLE = False


# =============================================================================
# Schéma DuckDB pour les nouvelles tables
# =============================================================================

SYNC_SCHEMA_DDL = """
-- Table medals_earned (médailles obtenues par match)
CREATE TABLE IF NOT EXISTS medals_earned (
    match_id VARCHAR,
    medal_name_id BIGINT,
    count SMALLINT,
    PRIMARY KEY (match_id, medal_name_id)
);

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
CREATE SEQUENCE IF NOT EXISTS highlight_events_id_seq;
CREATE TABLE IF NOT EXISTS highlight_events (
    id INTEGER PRIMARY KEY DEFAULT nextval('highlight_events_id_seq'),
    match_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    time_ms INTEGER,
    xuid VARCHAR,
    gamertag VARCHAR,
    type_hint INTEGER,
    raw_json VARCHAR
);
CREATE INDEX IF NOT EXISTS idx_highlight_match ON highlight_events(match_id);

-- Table personal_score_awards (Sprint 8 - Décomposition du score personnel)
-- Stocke les awards individuels pour analyse de la contribution aux objectifs
CREATE SEQUENCE IF NOT EXISTS personal_score_awards_id_seq;
CREATE TABLE IF NOT EXISTS personal_score_awards (
    id INTEGER PRIMARY KEY DEFAULT nextval('personal_score_awards_id_seq'),
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

-- Table match_participants (Sprint Gamertag Roster Fix)
-- Stocke TOUS les joueurs de chaque match avec team_id/outcome/gamertag/score/rank/kda
-- Source : MatchStats.Players[] (API propre, pas les films corrompus)
-- rank = classement (1 = meilleur), API prioritaire sinon calculé. Score et k/d/a = API
CREATE TABLE IF NOT EXISTS match_participants (
    match_id VARCHAR NOT NULL,
    xuid VARCHAR NOT NULL,
    team_id INTEGER,
    outcome INTEGER,
    gamertag VARCHAR,
    rank SMALLINT,
    score INTEGER,
    kills SMALLINT,
    deaths SMALLINT,
    assists SMALLINT,
    shots_fired INTEGER,
    shots_hit INTEGER,
    damage_dealt FLOAT,
    damage_taken FLOAT,
    PRIMARY KEY (match_id, xuid)
);
CREATE INDEX IF NOT EXISTS idx_participants_xuid ON match_participants(xuid);
CREATE INDEX IF NOT EXISTS idx_participants_team ON match_participants(match_id, team_id);

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

-- Tables media_files et media_match_associations : créées et migrées uniquement par
-- MediaIndexer.ensure_schema() (plan onglet Médias, refonte à partir de zéro).
-- Ne pas les créer ici pour éviter un schéma divergent.
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
        shared_db_path: Path | str | None = None,
        tokens: Tokens | None = None,
    ) -> None:
        """
        Args:
            player_db_path: Chemin vers stats.duckdb du joueur.
            xuid: XUID du joueur.
            gamertag: Gamertag pour l'identification API.
            metadata_db_path: Chemin vers metadata.duckdb (auto-détecté si None).
            shared_db_path: Chemin vers shared_matches.duckdb (auto-détecté si None).
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

        # Auto-détection du chemin shared_matches.duckdb (v5)
        if shared_db_path is None:
            data_dir = self._player_db_path.parent.parent.parent
            self._shared_db_path: Path | None = data_dir / "warehouse" / "shared_matches.duckdb"
        else:
            self._shared_db_path = Path(shared_db_path)

        self._connection: duckdb.DuckDBPyConnection | None = None
        self._shared_connection: duckdb.DuckDBPyConnection | None = None
        self._db_lock = asyncio.Lock()
        self._shared_db_lock = asyncio.Lock()
        self._existing_match_ids: set[str] | None = None

        # Créer le resolver pour les métadonnées
        self._metadata_resolver = create_metadata_resolver(self._metadata_db_path)

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

    def _get_shared_connection(self) -> duckdb.DuckDBPyConnection | None:
        """Retourne une connexion vers shared_matches.duckdb (R/W).

        Returns:
            Connexion DuckDB ou None si la base n'existe pas.
        """
        if self._shared_connection is not None:
            return self._shared_connection

        if self._shared_db_path is None or not self._shared_db_path.exists():
            logger.debug("shared_matches.duckdb absent, mode legacy v4")
            return None

        self._shared_connection = duckdb.connect(
            str(self._shared_db_path),
            read_only=False,
        )
        self._shared_connection.execute("SET enable_object_cache = true")
        return self._shared_connection

    @property
    def shared_enabled(self) -> bool:
        """Indique si le mode shared_matches est activé."""
        return self._shared_db_path is not None and self._shared_db_path.exists()

    def _ensure_schema(self) -> None:
        """S'assure que les tables nécessaires existent."""
        conn = self._connection
        if conn is None:
            return

        # S'assurer que match_stats existe avec toutes les colonnes nécessaires
        self._ensure_match_stats_table()

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

        # Colonnes rank/score sur match_participants (migration)
        self._ensure_match_participants_rank_score()

        # S'assurer que la séquence pour highlight_events existe (migration)
        self._ensure_highlight_events_sequence()

        # Colonne bitmask backfill_completed (migration)
        ensure_backfill_completed_column(conn)

    def _ensure_match_stats_table(self) -> None:
        """S'assure que la table match_stats existe avec toutes les colonnes nécessaires."""
        conn = self._connection
        if conn is None:
            return

        # Vérifier si la table existe
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'match_stats'"
        ).fetchall()

        if not tables:
            # Créer la table complète
            logger.info("Création de la table match_stats")
            conn.execute("""
                CREATE TABLE match_stats (
                    match_id VARCHAR PRIMARY KEY,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    playlist_id VARCHAR,
                    playlist_name VARCHAR,
                    map_id VARCHAR,
                    map_name VARCHAR,
                    pair_id VARCHAR,
                    pair_name VARCHAR,
                    game_variant_id VARCHAR,
                    game_variant_name VARCHAR,
                    outcome TINYINT,
                    team_id TINYINT,
                    rank SMALLINT,
                    kills SMALLINT,
                    deaths SMALLINT,
                    assists SMALLINT,
                    kda FLOAT,
                    accuracy FLOAT,
                    headshot_kills SMALLINT,
                    max_killing_spree SMALLINT,
                    time_played_seconds INTEGER,
                    avg_life_seconds FLOAT,
                    my_team_score SMALLINT,
                    enemy_team_score SMALLINT,
                    team_mmr FLOAT,
                    enemy_mmr FLOAT,
                    damage_dealt FLOAT,
                    damage_taken FLOAT,
                    shots_fired INTEGER,
                    shots_hit INTEGER,
                    grenade_kills SMALLINT,
                    melee_kills SMALLINT,
                    power_weapon_kills SMALLINT,
                    score INTEGER,
                    personal_score INTEGER,
                    mode_category VARCHAR,
                    is_ranked BOOLEAN DEFAULT FALSE,
                    is_firefight BOOLEAN DEFAULT FALSE,
                    left_early BOOLEAN DEFAULT FALSE,
                    session_id VARCHAR,
                    session_label VARCHAR,
                    performance_score FLOAT,
                    teammates_signature VARCHAR,
                    known_teammates_count SMALLINT,
                    is_with_friends BOOLEAN,
                    friends_xuids VARCHAR,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
        else:
            # Migrations centralisées
            from src.data.sync.migrations import ensure_match_stats_columns

            ensure_match_stats_columns(conn)

    def _ensure_match_participants_rank_score(self) -> None:
        """Ajoute les colonnes rank, score et k/d/a à match_participants si absentes (migration)."""
        conn = self._connection
        if conn is None:
            return
        from src.data.sync.migrations import ensure_match_participants_columns

        ensure_match_participants_columns(conn)

    def _ensure_highlight_events_sequence(self) -> None:
        """S'assure que highlight_events.id utilise une séquence auto-increment."""
        conn = self._connection
        if conn is None:
            return
        ensure_highlight_events_autoincrement(conn)

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

            # Sprint 6 : Calcul batch des performance scores post-sync
            if (
                result.matches_inserted > 0
                and options.defer_performance_score
                and _PERF_SCORE_AVAILABLE
            ):
                perf_count = self.batch_compute_performance_scores()
                logger.info(f"Performance scores calculés en batch : {perf_count}")

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

                    # Sprint 6 : Commit intermédiaire tous les N matchs
                    if (
                        options.batch_commit_size > 0
                        and result.matches_inserted % options.batch_commit_size == 0
                    ):
                        conn = self._get_connection()
                        conn.commit()
                        logger.debug(f"Commit intermédiaire après {result.matches_inserted} matchs")

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
        """Traite un match unique : fetch, transform, insert.

        Si shared_matches est activé, délègue à _process_known_match()
        ou _process_new_match() selon que le match existe déjà dans le
        registre partagé.
        """
        # ── Mode shared v5 ─────────────────────────────────────────
        shared_conn = self._get_shared_connection()
        if shared_conn is not None:
            try:
                registry = shared_conn.execute(
                    """SELECT
                        backfill_completed,
                        participants_loaded,
                        events_loaded,
                        medals_loaded,
                        player_count
                    FROM match_registry
                    WHERE match_id = ?""",
                    (match_id,),
                ).fetchone()
            except Exception:
                registry = None

            if registry is not None:
                logger.info(
                    f"Match {match_id} déjà connu dans shared " f"(player_count={registry[4]})"
                )
                return await self._process_known_match(
                    client,
                    match_id,
                    registry,
                    options,
                )
            else:
                logger.info(f"Nouveau match {match_id} → sync complète vers shared")
                return await self._process_new_match(
                    client,
                    match_id,
                    options,
                )

        # ── Mode legacy v4 (pas de shared_matches) ─────────────────
        return await self._process_single_match_legacy(
            client,
            match_id,
            options,
        )

    async def _process_single_match_legacy(
        self,
        client: SPNKrAPIClient,
        match_id: str,
        options: SyncOptions,
    ) -> dict[str, Any]:
        """Traite un match en mode legacy v4 (sans shared_matches)."""
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

            # Enrichir MatchInfo avec les PublicName depuis Discovery UGC (noms cartes/playlists)
            if options.with_assets:
                await enrich_match_info_with_assets(client, stats_json)

            # Extraire les XUIDs pour l'appel skill
            xuids = extract_xuids_from_match(stats_json)

            # Récupérer skill et events en parallèle (Sprint 6 — asyncio.gather)
            skill_json = None
            highlight_events: list = []

            api_tasks: list = []
            task_keys: list[str] = []

            if options.with_skill and xuids:
                api_tasks.append(client.get_skill_stats(match_id, xuids))
                task_keys.append("skill")
            if options.with_highlight_events:
                api_tasks.append(client.get_highlight_events(match_id))
                task_keys.append("events")

            if api_tasks:
                api_results = await asyncio.gather(*api_tasks, return_exceptions=True)
                for key, res in zip(task_keys, api_results, strict=False):
                    if isinstance(res, Exception):
                        logger.warning(f"Erreur API {key} pour {match_id}: {res}")
                        continue
                    if key == "skill":
                        skill_json = res
                    elif key == "events":
                        highlight_events = res if res else []

            # Transformer les données
            match_row = transform_match_stats(
                stats_json,
                self._xuid,
                skill_json=skill_json,
                metadata_resolver=self._metadata_resolver,
            )
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

            # Sprint Gamertag Roster Fix: Extraire les participants (roster complet)
            participant_rows = []
            if options.with_participants:
                participant_rows = extract_participants(stats_json)

            # Sprint 8.2: Extraire PersonalScores
            personal_scores = extract_personal_score_awards(stats_json, self._xuid)
            personal_score_rows = []
            if personal_scores:
                personal_score_rows = transform_personal_score_awards(
                    match_id, self._xuid, personal_scores
                )

            # Extraire les médailles
            from src.data.sync.transformers import extract_medals

            medal_rows = extract_medals(stats_json, self._xuid)

            # Insérer dans DuckDB (protégé par lock)
            async with self._db_lock:
                self._insert_match_row(match_row)

                if skill_row:
                    self._insert_skill_row(skill_row)
                    result["skill"] = 1

                if event_rows:
                    self._insert_event_rows(event_rows)
                    result["events"] = len(event_rows)

                if personal_score_rows:
                    self._insert_personal_score_rows(personal_score_rows)
                    result["personal_scores"] = len(personal_score_rows)

                if medal_rows:
                    self._insert_medal_rows(medal_rows)
                    result["medals"] = len(medal_rows)

                if participant_rows:
                    self._insert_participant_rows(participant_rows)
                    result["participants"] = len(participant_rows)

                if alias_rows:
                    self._insert_alias_rows(alias_rows)
                    result["aliases"] = len(alias_rows)

                # Calculer et mettre à jour le score de performance
                # Sprint 6 : si defer_performance_score, on skip le calcul inline
                # (sera fait en batch post-sync via batch_compute_performance_scores)
                if not options.defer_performance_score:
                    self._compute_and_update_performance_score(match_id, match_row)

                # ── Bitmask backfill_completed ──────────────────────────
                # Marquer les types de données effectivement traités lors
                # de cette sync pour que le backfill ne les re-détecte pas.
                bf_mask = 0
                # Toujours extraits depuis match_stats JSON :
                bf_mask |= BACKFILL_FLAGS["medals"]
                bf_mask |= BACKFILL_FLAGS["personal_scores"]
                bf_mask |= BACKFILL_FLAGS["performance_scores"]
                bf_mask |= BACKFILL_FLAGS["accuracy"]
                bf_mask |= BACKFILL_FLAGS["shots"]
                # Conditionnels selon SyncOptions :
                if options.with_skill:
                    bf_mask |= BACKFILL_FLAGS["skill"]
                    bf_mask |= BACKFILL_FLAGS["enemy_mmr"]
                if options.with_highlight_events:
                    bf_mask |= BACKFILL_FLAGS["events"]
                if options.with_participants:
                    bf_mask |= BACKFILL_FLAGS["participants"]
                    bf_mask |= BACKFILL_FLAGS["participants_scores"]
                    bf_mask |= BACKFILL_FLAGS["participants_kda"]
                    bf_mask |= BACKFILL_FLAGS["participants_shots"]
                    bf_mask |= BACKFILL_FLAGS["participants_damage"]
                if options.with_aliases:
                    bf_mask |= BACKFILL_FLAGS["aliases"]
                if options.with_assets:
                    bf_mask |= BACKFILL_FLAGS["assets"]
                # UPDATE atomique (OR pour ne pas écraser les bits existants)
                conn = self._get_connection()
                conn.execute(
                    "UPDATE match_stats "
                    "SET backfill_completed = COALESCE(backfill_completed, 0) | ? "
                    "WHERE match_id = ?",
                    [bf_mask, match_id],
                )

            result["inserted"] = True

        except Exception as e:
            result["error"] = f"Erreur traitement {match_id}: {e}"
            logger.warning(result["error"])

        return result

    # =====================================================================
    # v5 Shared Matches — Process known / new match
    # =====================================================================

    async def _process_known_match(
        self,
        client: SPNKrAPIClient,
        match_id: str,
        registry: tuple,
        options: SyncOptions,
    ) -> dict[str, Any]:
        """Traite un match déjà présent dans shared_matches (sync allégée).

        Seules les données personnelles (match_stats, enrichment) sont
        insérées dans la DB joueur. Les données communes manquantes sont
        backfillées dans shared si nécessaire.

        Args:
            client: Client API SPNKr.
            match_id: ID du match.
            registry: Tuple (backfill_completed, participants_loaded,
                      events_loaded, medals_loaded, player_count).
            options: Options de sync.

        Returns:
            Dict résultat avec mode='known_match'.
        """
        result: dict[str, Any] = {
            "inserted": False,
            "mode": "known_match",
            "events": 0,
            "skill": 0,
            "aliases": 0,
            "api_calls_saved": 0,
            "error": None,
        }

        _bf_completed, participants_loaded, events_loaded, medals_loaded, _player_count = registry

        try:
            # 1. Télécharger les stats (obligatoire pour extraire les données perso)
            stats_json = await client.get_match_stats(match_id)
            if stats_json is None:
                result["error"] = f"Impossible de récupérer {match_id}"
                return result

            if options.with_assets:
                await enrich_match_info_with_assets(client, stats_json)

            # 2. Transformer en match_row pour la player DB (mode legacy)
            xuids = extract_xuids_from_match(stats_json)
            skill_json = None
            highlight_events: list = []

            # Skill toujours utile pour le joueur (MMR dans match_stats)
            if options.with_skill and xuids:
                skill_json = await client.get_skill_stats(match_id, xuids)

            # Events : seulement si absent du shared
            if options.with_highlight_events and not events_loaded:
                highlight_events = await client.get_highlight_events(match_id)
            elif events_loaded:
                result["api_calls_saved"] += 1

            match_row = transform_match_stats(
                stats_json,
                self._xuid,
                skill_json=skill_json,
                metadata_resolver=self._metadata_resolver,
            )
            if match_row is None:
                result["error"] = f"Transformation échouée pour {match_id}"
                return result

            skill_row = None
            if skill_json:
                skill_row = transform_skill_stats(skill_json, match_id, self._xuid)

            # Extraire les médailles perso (player DB)
            from src.data.sync.transformers import extract_medals

            medal_rows = extract_medals(stats_json, self._xuid)

            # PersonalScores
            personal_scores = extract_personal_score_awards(stats_json, self._xuid)
            personal_score_rows = []
            if personal_scores:
                personal_score_rows = transform_personal_score_awards(
                    match_id,
                    self._xuid,
                    personal_scores,
                )

            alias_rows = []
            if options.with_aliases:
                alias_rows = extract_aliases(stats_json)

            participant_rows = []
            if options.with_participants:
                participant_rows = extract_participants(stats_json)

            # 3. Insérer dans la player DB (tout comme le legacy)
            async with self._db_lock:
                self._insert_match_row(match_row)

                if skill_row:
                    self._insert_skill_row(skill_row)
                    result["skill"] = 1

                if medal_rows:
                    self._insert_medal_rows(medal_rows)

                if personal_score_rows:
                    self._insert_personal_score_rows(personal_score_rows)

                if participant_rows:
                    self._insert_participant_rows(participant_rows)

                if alias_rows:
                    self._insert_alias_rows(alias_rows)
                    result["aliases"] = len(alias_rows)

                self._compute_and_update_performance_score(match_id, match_row)

                # Bitmask backfill_completed
                bf_mask = self._compute_backfill_mask(options)
                conn = self._get_connection()
                conn.execute(
                    "UPDATE match_stats "
                    "SET backfill_completed = COALESCE(backfill_completed, 0) | ? "
                    "WHERE match_id = ?",
                    [bf_mask, match_id],
                )

            # 4. Backfill sélectif dans shared si des données manquent
            backfill_needed: list[str] = []
            async with self._shared_db_lock:
                shared_conn = self._get_shared_connection()
                if shared_conn is None:
                    result["error"] = "shared_connection perdue"
                    return result

                if not participants_loaded:
                    participants = extract_participants(stats_json)
                    self._insert_shared_participants(shared_conn, participants)
                    shared_conn.execute(
                        "UPDATE match_registry SET participants_loaded = TRUE WHERE match_id = ?",
                        (match_id,),
                    )
                    backfill_needed.append("participants")

                if not events_loaded and highlight_events:
                    event_rows_shared = transform_highlight_events(highlight_events, match_id)
                    self._insert_shared_events(shared_conn, event_rows_shared)
                    shared_conn.execute(
                        "UPDATE match_registry SET events_loaded = TRUE WHERE match_id = ?",
                        (match_id,),
                    )
                    result["events"] = len(event_rows_shared)
                    backfill_needed.append("events")

                if not medals_loaded:
                    medals_all = extract_all_medals(stats_json)
                    self._insert_shared_medals(shared_conn, medals_all)
                    shared_conn.execute(
                        "UPDATE match_registry SET medals_loaded = TRUE WHERE match_id = ?",
                        (match_id,),
                    )
                    backfill_needed.append("medals")

                # Aliases vers shared
                if alias_rows:
                    self._insert_shared_aliases(shared_conn, alias_rows)

                # Incrémenter player_count
                shared_conn.execute(
                    "UPDATE match_registry "
                    "SET player_count = player_count + 1, "
                    "    last_updated_at = CURRENT_TIMESTAMP "
                    "WHERE match_id = ?",
                    (match_id,),
                )

            if backfill_needed:
                logger.info(f"Backfill shared pour {match_id}: {', '.join(backfill_needed)}")

            result["inserted"] = True

        except Exception as e:
            result["error"] = f"Erreur traitement known {match_id}: {e}"
            logger.warning(result["error"])

        return result

    async def _process_new_match(
        self,
        client: SPNKrAPIClient,
        match_id: str,
        options: SyncOptions,
    ) -> dict[str, Any]:
        """Traite un nouveau match (sync complète → shared + player DB).

        Toutes les données communes sont insérées dans shared_matches,
        les données personnelles dans la player DB.

        Args:
            client: Client API SPNKr.
            match_id: ID du match.
            options: Options de sync.

        Returns:
            Dict résultat avec mode='new_match'.
        """
        result: dict[str, Any] = {
            "inserted": False,
            "mode": "new_match",
            "events": 0,
            "skill": 0,
            "aliases": 0,
            "error": None,
        }

        try:
            # 1. Télécharger les stats
            stats_json = await client.get_match_stats(match_id)
            if stats_json is None:
                result["error"] = f"Impossible de récupérer {match_id}"
                return result

            if options.with_assets:
                await enrich_match_info_with_assets(client, stats_json)

            # 2. Télécharger events et skill
            xuids = extract_xuids_from_match(stats_json)
            skill_json = None
            highlight_events: list = []

            if options.with_skill and xuids:
                skill_json = await client.get_skill_stats(match_id, xuids)

            if options.with_highlight_events:
                highlight_events = await client.get_highlight_events(match_id)

            # 3. Extraire les données communes pour shared
            registry_data = extract_match_registry_data(
                stats_json,
                metadata_resolver=self._metadata_resolver,
            )
            if registry_data is None:
                result["error"] = f"Extraction registry échouée pour {match_id}"
                return result

            participants = extract_participants(stats_json)
            medals_all = extract_all_medals(stats_json)
            alias_rows = extract_aliases(stats_json) if options.with_aliases else []

            event_rows_shared = []
            if highlight_events:
                event_rows_shared = transform_highlight_events(highlight_events, match_id)

            # 4. Insérer dans shared_matches
            async with self._shared_db_lock:
                shared_conn = self._get_shared_connection()
                if shared_conn is None:
                    result["error"] = "shared_connection indisponible"
                    return result

                self._insert_shared_registry(shared_conn, registry_data)
                self._insert_shared_participants(shared_conn, participants)
                self._insert_shared_medals(shared_conn, medals_all)

                if event_rows_shared:
                    self._insert_shared_events(shared_conn, event_rows_shared)
                    result["events"] = len(event_rows_shared)

                if alias_rows:
                    self._insert_shared_aliases(shared_conn, alias_rows)
                    result["aliases"] = len(alias_rows)

                # Mettre à jour les flags du registre
                shared_conn.execute(
                    """UPDATE match_registry SET
                        participants_loaded = TRUE,
                        events_loaded = ?,
                        medals_loaded = TRUE,
                        first_sync_by = ?,
                        first_sync_at = CURRENT_TIMESTAMP,
                        player_count = 1
                    WHERE match_id = ?""",
                    (
                        len(event_rows_shared) > 0,
                        self._gamertag,
                        match_id,
                    ),
                )

            # 5. Insérer les données personnelles dans la player DB
            match_row = transform_match_stats(
                stats_json,
                self._xuid,
                skill_json=skill_json,
                metadata_resolver=self._metadata_resolver,
            )
            if match_row is None:
                result["error"] = f"Transformation match_stats échouée pour {match_id}"
                return result

            skill_row = None
            if skill_json:
                skill_row = transform_skill_stats(skill_json, match_id, self._xuid)

            from src.data.sync.transformers import extract_medals

            medal_rows_personal = extract_medals(stats_json, self._xuid)

            personal_scores = extract_personal_score_awards(stats_json, self._xuid)
            personal_score_rows = []
            if personal_scores:
                personal_score_rows = transform_personal_score_awards(
                    match_id,
                    self._xuid,
                    personal_scores,
                )

            participant_rows_player = []
            if options.with_participants:
                participant_rows_player = participants  # Réutiliser l'extraction

            async with self._db_lock:
                self._insert_match_row(match_row)

                if skill_row:
                    self._insert_skill_row(skill_row)
                    result["skill"] = 1

                if medal_rows_personal:
                    self._insert_medal_rows(medal_rows_personal)

                if personal_score_rows:
                    self._insert_personal_score_rows(personal_score_rows)

                if participant_rows_player:
                    self._insert_participant_rows(participant_rows_player)

                if alias_rows:
                    self._insert_alias_rows(alias_rows)

                self._compute_and_update_performance_score(match_id, match_row)

                # Bitmask backfill_completed
                bf_mask = self._compute_backfill_mask(options)
                conn = self._get_connection()
                conn.execute(
                    "UPDATE match_stats "
                    "SET backfill_completed = COALESCE(backfill_completed, 0) | ? "
                    "WHERE match_id = ?",
                    [bf_mask, match_id],
                )

            result["inserted"] = True

        except Exception as e:
            result["error"] = f"Erreur traitement new {match_id}: {e}"
            logger.warning(result["error"])

        return result

    def _compute_backfill_mask(self, options: SyncOptions) -> int:
        """Calcule le bitmask backfill_completed pour un match.

        Args:
            options: Options de sync courantes.

        Returns:
            Bitmask entier.
        """
        bf_mask = 0
        bf_mask |= BACKFILL_FLAGS["medals"]
        bf_mask |= BACKFILL_FLAGS["personal_scores"]
        bf_mask |= BACKFILL_FLAGS["performance_scores"]
        bf_mask |= BACKFILL_FLAGS["accuracy"]
        bf_mask |= BACKFILL_FLAGS["shots"]
        if options.with_skill:
            bf_mask |= BACKFILL_FLAGS["skill"]
            bf_mask |= BACKFILL_FLAGS["enemy_mmr"]
        if options.with_highlight_events:
            bf_mask |= BACKFILL_FLAGS["events"]
        if options.with_participants:
            bf_mask |= BACKFILL_FLAGS["participants"]
            bf_mask |= BACKFILL_FLAGS["participants_scores"]
            bf_mask |= BACKFILL_FLAGS["participants_kda"]
            bf_mask |= BACKFILL_FLAGS["participants_shots"]
            bf_mask |= BACKFILL_FLAGS["participants_damage"]
        if options.with_aliases:
            bf_mask |= BACKFILL_FLAGS["aliases"]
        if options.with_assets:
            bf_mask |= BACKFILL_FLAGS["assets"]
        return bf_mask

    # =====================================================================
    # v5 Shared Matches — Insertions dans shared_matches.duckdb
    # =====================================================================

    def _insert_shared_registry(
        self,
        shared_conn: duckdb.DuckDBPyConnection,
        data: dict[str, Any],
    ) -> None:
        """Insère un match dans match_registry (shared).

        Args:
            shared_conn: Connexion vers shared_matches.duckdb.
            data: Dict retourné par extract_match_registry_data().
        """
        shared_conn.execute(
            """INSERT OR IGNORE INTO match_registry (
                match_id, start_time, end_time,
                playlist_id, playlist_name,
                map_id, map_name,
                pair_id, pair_name,
                game_variant_id, game_variant_name,
                mode_category, is_ranked, is_firefight,
                duration_seconds,
                team_0_score, team_1_score,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (
                data["match_id"],
                data["start_time"],
                data["end_time"],
                data["playlist_id"],
                data["playlist_name"],
                data["map_id"],
                data["map_name"],
                data["pair_id"],
                data["pair_name"],
                data["game_variant_id"],
                data["game_variant_name"],
                data["mode_category"],
                data["is_ranked"],
                data["is_firefight"],
                data["duration_seconds"],
                data["team_0_score"],
                data["team_1_score"],
            ),
        )

    def _insert_shared_participants(
        self,
        shared_conn: duckdb.DuckDBPyConnection,
        participants: list,
    ) -> None:
        """Insère les participants dans shared.match_participants.

        Args:
            shared_conn: Connexion vers shared_matches.duckdb.
            participants: Liste de MatchParticipantRow.
        """
        if not participants:
            return
        from src.data.sync.batch_insert import PARTICIPANT_COLUMNS, batch_upsert_rows

        batch_upsert_rows(shared_conn, "match_participants", participants, PARTICIPANT_COLUMNS)

    def _insert_shared_events(
        self,
        shared_conn: duckdb.DuckDBPyConnection,
        event_rows: list,
    ) -> None:
        """Insère les highlight events dans shared.highlight_events.

        Args:
            shared_conn: Connexion vers shared_matches.duckdb.
            event_rows: Liste de HighlightEventRow.
        """
        if not event_rows:
            return
        from src.data.sync.batch_insert import HIGHLIGHT_EVENT_COLUMNS, batch_insert_rows

        batch_insert_rows(shared_conn, "highlight_events", event_rows, HIGHLIGHT_EVENT_COLUMNS)

    def _insert_shared_medals(
        self,
        shared_conn: duckdb.DuckDBPyConnection,
        medals: list,
    ) -> None:
        """Insère les médailles de TOUS les joueurs dans shared.medals_earned.

        Args:
            shared_conn: Connexion vers shared_matches.duckdb.
            medals: Liste de SharedMedalEarnedRow.
        """
        if not medals:
            return
        columns = ["match_id", "xuid", "medal_name_id", "count"]
        from src.data.sync.batch_insert import batch_upsert_rows

        batch_upsert_rows(shared_conn, "medals_earned", medals, columns)

    def _insert_shared_aliases(
        self,
        shared_conn: duckdb.DuckDBPyConnection,
        alias_rows: list,
    ) -> None:
        """Insère les aliases xuid→gamertag dans shared.xuid_aliases.

        Args:
            shared_conn: Connexion vers shared_matches.duckdb.
            alias_rows: Liste de XuidAliasRow.
        """
        if not alias_rows:
            return
        from src.data.sync.batch_insert import ALIAS_COLUMNS, batch_upsert_rows

        now = datetime.now(timezone.utc)
        alias_dicts = [
            {
                "xuid": row.xuid,
                "gamertag": row.gamertag,
                "last_seen": row.last_seen,
                "source": row.source,
                "updated_at": now,
            }
            for row in alias_rows
        ]
        batch_upsert_rows(shared_conn, "xuid_aliases", alias_dicts, ALIAS_COLUMNS)

    def _ensure_performance_score_column(self) -> None:
        """S'assure que la colonne performance_score existe dans match_stats."""
        from src.data.sync.migrations import ensure_performance_score_column

        conn = self._get_connection()
        ensure_performance_score_column(conn)

    def _compute_and_update_performance_score(
        self, match_id: str, match_row: MatchStatsRow
    ) -> None:
        """Calcule et met à jour le score de performance pour un match.

        Note: Chaque DB DuckDB est spécifique à un joueur, donc pas besoin de filtrer par xuid.

        Args:
            match_id: ID du match
            match_row: Données du match inséré
        """
        if not _PERF_SCORE_AVAILABLE:
            logger.debug("Modules de calcul de performance non disponibles, skip")
            return

        try:
            conn = self._get_connection()

            # S'assurer que la colonne existe
            self._ensure_performance_score_column()

            # Vérifier si le score existe déjà
            existing = conn.execute(
                "SELECT performance_score FROM match_stats WHERE match_id = ?",
                (match_id,),
            ).fetchone()

            if existing and existing[0] is not None:
                # Score déjà calculé, skip
                logger.debug(f"Score de performance déjà présent pour {match_id}")
                return

            # Charger l'historique (tous les matchs AVANT celui-ci, triés par date)
            current_start_time = match_row.start_time
            if current_start_time is None:
                logger.debug(f"Pas de start_time pour {match_id}, skip calcul score")
                return

            # Convertir datetime en format compatible avec DuckDB
            if isinstance(current_start_time, datetime):
                current_start_time_str = current_start_time.isoformat()
            else:
                current_start_time_str = str(current_start_time)

            # v4: inclure personal_score, damage_dealt, rank, team_mmr, enemy_mmr
            history_df = conn.execute(
                """
                SELECT
                    match_id, start_time, kills, deaths, assists, kda, accuracy,
                    time_played_seconds, avg_life_seconds,
                    personal_score, damage_dealt,
                    rank, team_mmr, enemy_mmr
                FROM match_stats
                WHERE match_id != ?
                  AND start_time IS NOT NULL
                  AND start_time < CAST(? AS TIMESTAMP)
                ORDER BY start_time ASC
                """,
                (match_id, current_start_time_str),
            ).pl()

            if history_df.is_empty() or len(history_df) < MIN_MATCHES_FOR_RELATIVE:
                logger.debug(
                    f"Pas assez d'historique pour calculer le score ({len(history_df)} matchs)"
                )
                return

            # Convertir match_row en dict pour le calcul v4
            match_dict = {
                "kills": match_row.kills or 0,
                "deaths": match_row.deaths or 0,
                "assists": match_row.assists or 0,
                "kda": match_row.kda,
                "accuracy": match_row.accuracy,
                "time_played_seconds": match_row.time_played_seconds or 600.0,
                "personal_score": getattr(match_row, "personal_score", None),
                "damage_dealt": getattr(match_row, "damage_dealt", None),
                "rank": getattr(match_row, "rank", None),
                "team_mmr": getattr(match_row, "team_mmr", None),
                "enemy_mmr": getattr(match_row, "enemy_mmr", None),
            }

            # Calculer le score
            score = compute_relative_performance_score(match_dict, history_df)

            if score is not None:
                conn.execute(
                    "UPDATE match_stats SET performance_score = ? WHERE match_id = ?",
                    (score, match_id),
                )
                # Sprint 6 : pas de commit individuel ici, le commit est géré
                # par le batching dans _process_matches ou le commit final
                logger.debug(f"Score de performance calculé pour {match_id}: {score:.1f}")
            else:
                logger.debug(f"Impossible de calculer le score pour {match_id}")

        except Exception as e:
            # Ne pas bloquer la synchronisation si le calcul échoue
            logger.warning(f"Erreur calcul score performance pour {match_id}: {e}")

    def batch_compute_performance_scores(self) -> int:
        """Calcule les performance_score pour tous les matchs où il est NULL.

        Exécuté post-sync pour ne pas bloquer l'insertion des matchs.
        Utilise le calcul vectorisé de compute_relative_performance_score()
        avec un chargement unique de l'historique complet.

        Returns:
            Nombre de matchs mis à jour.
        """
        if not _PERF_SCORE_AVAILABLE:
            logger.debug("Modules de calcul de performance non disponibles, skip batch")
            return 0

        try:
            conn = self._get_connection()
            self._ensure_performance_score_column()

            # 1. Charger TOUS les matchs triés par date
            all_matches_df = conn.execute(
                """
                SELECT
                    match_id, start_time, kills, deaths, assists, kda, accuracy,
                    time_played_seconds, avg_life_seconds,
                    personal_score, damage_dealt,
                    rank, team_mmr, enemy_mmr,
                    performance_score
                FROM match_stats
                WHERE start_time IS NOT NULL
                ORDER BY start_time ASC
                """
            ).pl()

            if all_matches_df.is_empty():
                return 0

            # 2. Identifier les matchs sans score
            null_mask = all_matches_df["performance_score"].is_null()
            if not null_mask.any():
                logger.info("Tous les matchs ont déjà un performance_score")
                return 0

            # 3. Calculer le score pour chaque match NULL
            #    en utilisant l'historique des matchs précédents
            updates: list[tuple[float, str]] = []
            match_ids = all_matches_df["match_id"].to_list()

            for i in range(len(all_matches_df)):
                if not null_mask[i]:
                    continue

                # Pas assez d'historique ?
                if i < MIN_MATCHES_FOR_RELATIVE:
                    continue

                # Historique = tous les matchs AVANT l'index i
                history_df = all_matches_df.slice(0, i).drop("performance_score")

                # Match courant en dict
                row = all_matches_df.row(i, named=True)
                match_dict = {
                    "kills": row.get("kills") or 0,
                    "deaths": row.get("deaths") or 0,
                    "assists": row.get("assists") or 0,
                    "kda": row.get("kda"),
                    "accuracy": row.get("accuracy"),
                    "time_played_seconds": row.get("time_played_seconds") or 600.0,
                    "personal_score": row.get("personal_score"),
                    "damage_dealt": row.get("damage_dealt"),
                    "rank": row.get("rank"),
                    "team_mmr": row.get("team_mmr"),
                    "enemy_mmr": row.get("enemy_mmr"),
                }

                score = compute_relative_performance_score(match_dict, history_df)
                if score is not None:
                    updates.append((score, match_ids[i]))

            # 4. Batch UPDATE
            if updates:
                conn.executemany(
                    "UPDATE match_stats SET performance_score = ? WHERE match_id = ?",
                    updates,
                )
                conn.commit()
                logger.info(f"Performance scores batch : {len(updates)} matchs mis à jour")

            return len(updates)

        except Exception as e:
            logger.warning(f"Erreur batch calcul performance scores : {e}")
            return 0

    def _insert_match_row(self, row: MatchStatsRow) -> None:
        """Insère une ligne match_stats."""
        conn = self._get_connection()

        # Construire la requête d'insertion
        conn.execute(
            """INSERT OR REPLACE INTO match_stats (
                match_id, start_time, end_time, playlist_id, playlist_name,
                map_id, map_name, pair_id, pair_name,
                game_variant_id, game_variant_name,
                outcome, team_id, kills, deaths, assists,
                kda, accuracy, headshot_kills, max_killing_spree,
                time_played_seconds, avg_life_seconds,
                my_team_score, enemy_team_score,
                team_mmr, enemy_mmr,
                shots_fired, shots_hit,
                is_firefight, teammates_signature, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row.match_id,
                row.start_time,
                row.end_time,
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
                row.shots_fired,
                row.shots_hit,
                row.is_firefight,
                row.teammates_signature,
                datetime.now(timezone.utc),
            ),
        )

    def _insert_skill_row(self, row: PlayerMatchStatsRow) -> None:
        """Insère une ligne player_match_stats en batch (Sprint 15)."""
        conn = self._get_connection()
        skill_dict = {
            "match_id": row.match_id,
            "xuid": row.xuid,
            "team_id": row.team_id,
            "team_mmr": row.team_mmr,
            "enemy_mmr": row.enemy_mmr,
            "kills_expected": row.kills_expected,
            "kills_stddev": row.kills_stddev,
            "deaths_expected": row.deaths_expected,
            "deaths_stddev": row.deaths_stddev,
            "assists_expected": row.assists_expected,
            "assists_stddev": row.assists_stddev,
            "created_at": datetime.now(timezone.utc),
        }
        batch_upsert_rows(conn, "player_match_stats", [skill_dict], SKILL_COLUMNS)

    def _insert_event_rows(self, rows: list) -> None:
        """Insère des lignes highlight_events en batch (Sprint 15)."""
        if not rows:
            return
        conn = self._get_connection()
        batch_insert_rows(conn, "highlight_events", rows, HIGHLIGHT_EVENT_COLUMNS)

    def _insert_alias_rows(self, rows: list) -> None:
        """Insère des lignes xuid_aliases en batch avec upsert (Sprint 15)."""
        if not rows:
            return
        conn = self._get_connection()
        now = datetime.now(timezone.utc)
        # Enrichir les rows avec updated_at avant l'upsert
        alias_dicts = []
        for row in rows:
            alias_dicts.append(
                {
                    "xuid": row.xuid,
                    "gamertag": row.gamertag,
                    "last_seen": row.last_seen,
                    "source": row.source,
                    "updated_at": now,
                }
            )
        batch_upsert_rows(conn, "xuid_aliases", alias_dicts, ALIAS_COLUMNS)

    def _insert_personal_score_rows(self, rows: list) -> None:
        """Insère des lignes personal_score_awards en batch (Sprint 15)."""
        if not rows:
            return
        conn = self._get_connection()
        now = datetime.now(timezone.utc)
        # Enrichir chaque row avec created_at
        score_dicts = []
        for row in rows:
            score_dicts.append(
                {
                    "match_id": row.match_id,
                    "xuid": row.xuid,
                    "award_name": row.award_name,
                    "award_category": row.award_category,
                    "award_count": row.award_count,
                    "award_score": row.award_score,
                    "created_at": now,
                }
            )
        batch_insert_rows(conn, "personal_score_awards", score_dicts, PERSONAL_SCORE_COLUMNS)

    def _insert_medal_rows(self, rows: list) -> None:
        """Insère les lignes medals_earned en batch (Sprint 15).

        medals_earned n'a pas de PK/UNIQUE → insert simple (pas upsert).
        """
        if not rows:
            return
        conn = self._get_connection()
        batch_insert_rows(conn, "medals_earned", rows, MEDAL_COLUMNS)

    def _insert_participant_rows(self, rows: list) -> None:
        """Insère les lignes match_participants en batch (Sprint 15).

        Sprint Gamertag Roster Fix : stocke tous les joueurs avec team_id, outcome,
        gamertag, score et rang dans le match (1 = meilleur).
        """
        if not rows:
            return
        conn = self._get_connection()
        batch_upsert_rows(conn, "match_participants", rows, PARTICIPANT_COLUMNS)

    async def _refresh_aggregates_async(self) -> None:
        """Rafraîchit les agrégats après sync (async wrapper)."""
        # Exécuter dans un thread pour ne pas bloquer l'event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.refresh_aggregates)

    def refresh_aggregates(self) -> dict[str, int]:
        """Recalcule les tables d'agrégats après sync.

        Met à jour :
        - Vues matérialisées (mv_*)

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
        """Ferme les connexions DuckDB (player + shared)."""
        if self._connection:
            with contextlib.suppress(Exception):
                self._connection.close()
            self._connection = None
        if self._shared_connection:
            with contextlib.suppress(Exception):
                self._shared_connection.close()
            self._shared_connection = None
