"""Tests Sprint 6 — Optimisations API & Sync.

Teste :
- 6.1 Parallélisation appels API (asyncio.gather)
- 6.2 Désactivation perf score pendant sync (defer_performance_score)
- 6.3 Batch compute performance scores post-sync
- 6.4 Batching des insertions DB (batch_commit_size)
- 6.5 Rate limit et parallel_matches augmentés
"""

from __future__ import annotations

import gc
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest

from src.data.sync.engine import DuckDBSyncEngine
from src.data.sync.models import MatchStatsRow, SyncOptions

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_duckdb(tmp_path: Path) -> Path:
    """Crée une base DuckDB temporaire avec le schéma match_stats complet."""
    db_path = tmp_path / f"test_player_{uuid.uuid4().hex[:8]}" / "stats.duckdb"
    db_path.parent.mkdir(parents=True)

    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS match_stats (
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
            outcome INTEGER,
            team_id INTEGER,
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER,
            kda DOUBLE,
            accuracy DOUBLE,
            headshot_kills INTEGER,
            max_killing_spree INTEGER,
            time_played_seconds DOUBLE,
            avg_life_seconds DOUBLE,
            my_team_score INTEGER,
            enemy_team_score INTEGER,
            team_mmr DOUBLE,
            enemy_mmr DOUBLE,
            shots_fired INTEGER,
            shots_hit INTEGER,
            is_firefight BOOLEAN,
            teammates_signature VARCHAR,
            updated_at TIMESTAMP,
            performance_score DOUBLE,
            personal_score INTEGER,
            damage_dealt DOUBLE,
            damage_taken DOUBLE,
            rank INTEGER,
            backfill_completed INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_meta (
            key VARCHAR PRIMARY KEY,
            value VARCHAR,
            updated_at TIMESTAMP
        )
    """)
    conn.close()
    del conn
    gc.collect()

    return db_path


def _make_match_row(
    match_id: str,
    start_time: datetime,
    kills: int = 10,
    deaths: int = 8,
    assists: int = 5,
) -> MatchStatsRow:
    """Crée un MatchStatsRow de test."""
    return MatchStatsRow(
        match_id=match_id,
        start_time=start_time,
        kills=kills,
        deaths=deaths,
        assists=assists,
        kda=round((kills + assists / 3) / max(deaths, 1), 2),
        accuracy=0.45,
        time_played_seconds=600,
        avg_life_seconds=45.0,
        playlist_id="playlist-123",
        playlist_name="Ranked Arena",
        map_id="map-456",
        map_name="Recharge",
        outcome=2,
        team_id=0,
    )


def _insert_test_matches(db_path: Path, count: int = 30) -> list[str]:
    """Insère N matchs de test dans la DB. Retourne les match_ids."""
    conn = duckdb.connect(str(db_path))
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    match_ids = []

    for i in range(count):
        mid = f"match-{i:04d}"
        match_ids.append(mid)
        t = base_time + timedelta(hours=i)
        conn.execute(
            """INSERT INTO match_stats (
                match_id, start_time, kills, deaths, assists, kda, accuracy,
                time_played_seconds, avg_life_seconds, personal_score,
                damage_dealt, rank, team_mmr, enemy_mmr, performance_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mid,
                t,
                10 + i % 5,
                8 + i % 3,
                5 + i % 4,
                1.5 + (i % 5) * 0.1,
                0.4 + (i % 10) * 0.01,
                600,
                45.0,
                1500 + i * 10,
                3000.0 + i * 50,
                i % 8 + 1,
                1200.0 + i * 5,
                1200.0 + i * 3,
                None,  # performance_score = NULL
            ),
        )

    conn.commit()
    conn.close()
    del conn
    gc.collect()
    return match_ids


# =============================================================================
# 6.1 — Tests parallélisation API
# =============================================================================


class TestAPIParallelization:
    """Tests pour la parallélisation des appels skill + events."""

    def test_sync_options_defaults_sprint6(self):
        """Les valeurs par défaut Sprint 6 sont correctes."""
        opts = SyncOptions()
        assert opts.requests_per_second == 10, "Rate limit devrait être 10 req/s"
        assert opts.parallel_matches == 5, "parallel_matches devrait être 5"
        assert opts.defer_performance_score is True, "defer_perf_score devrait être True"
        assert opts.batch_commit_size == 10, "batch_commit_size devrait être 10"


# =============================================================================
# 6.2 — Tests defer_performance_score
# =============================================================================


class TestDeferPerformanceScore:
    """Tests pour la désactivation du calcul perf score pendant sync."""

    def test_defer_performance_score_default_true(self):
        """Par défaut, defer_performance_score est True."""
        opts = SyncOptions()
        assert opts.defer_performance_score is True

    def test_defer_can_be_disabled(self):
        """On peut explicitement désactiver le defer."""
        opts = SyncOptions(defer_performance_score=False)
        assert opts.defer_performance_score is False


# =============================================================================
# 6.3 — Tests batch_compute_performance_scores
# =============================================================================


class TestBatchComputePerformanceScores:
    """Tests pour le calcul batch des performance scores post-sync."""

    def test_batch_compute_no_matches(self, temp_duckdb: Path):
        """Avec une DB vide, batch_compute retourne 0."""
        engine = DuckDBSyncEngine(
            player_db_path=str(temp_duckdb),
            xuid="2535423456789",
            gamertag="TestPlayer",
        )
        result = engine.batch_compute_performance_scores()
        assert result == 0
        engine.close()

    def test_batch_compute_with_null_scores(self, temp_duckdb: Path):
        """Calcule les scores manquants pour les matchs avec assez d'historique."""
        _insert_test_matches(temp_duckdb, count=30)

        engine = DuckDBSyncEngine(
            player_db_path=str(temp_duckdb),
            xuid="2535423456789",
            gamertag="TestPlayer",
        )

        updated = engine.batch_compute_performance_scores()

        # Au moins quelques matchs devraient avoir été calculés
        # (les premiers n'ont pas assez d'historique, les suivants oui)
        assert updated > 0, "Au moins quelques scores devraient être calculés"

        # Vérifier dans la DB
        conn = duckdb.connect(str(temp_duckdb))
        non_null = conn.execute(
            "SELECT COUNT(*) FROM match_stats WHERE performance_score IS NOT NULL"
        ).fetchone()[0]
        conn.close()

        assert non_null == updated
        engine.close()

    def test_batch_compute_idempotent(self, temp_duckdb: Path):
        """Exécuter batch_compute 2 fois ne recalcule pas les scores existants."""
        _insert_test_matches(temp_duckdb, count=30)

        engine = DuckDBSyncEngine(
            player_db_path=str(temp_duckdb),
            xuid="2535423456789",
            gamertag="TestPlayer",
        )

        first_run = engine.batch_compute_performance_scores()
        second_run = engine.batch_compute_performance_scores()

        assert first_run > 0
        assert second_run == 0, "Le 2e appel ne devrait rien recalculer"
        engine.close()

    def test_batch_compute_all_scores_already_present(self, temp_duckdb: Path):
        """Si tous les matchs ont un score, retourne 0."""
        conn = duckdb.connect(str(temp_duckdb))
        base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for i in range(5):
            conn.execute(
                """INSERT INTO match_stats (
                    match_id, start_time, kills, deaths, assists, kda,
                    accuracy, time_played_seconds, avg_life_seconds,
                    performance_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"m-{i}",
                    base_time + timedelta(hours=i),
                    10,
                    8,
                    5,
                    1.5,
                    0.45,
                    600,
                    45.0,
                    65.0,
                ),
            )
        conn.commit()
        conn.close()
        del conn
        gc.collect()

        engine = DuckDBSyncEngine(
            player_db_path=str(temp_duckdb),
            xuid="2535423456789",
            gamertag="TestPlayer",
        )
        result = engine.batch_compute_performance_scores()
        assert result == 0
        engine.close()


# =============================================================================
# 6.4 — Tests batching DB commits
# =============================================================================


class TestBatchCommitSize:
    """Tests pour le batching des commits DB."""

    def test_batch_commit_size_in_options(self):
        """batch_commit_size est configurable."""
        opts = SyncOptions(batch_commit_size=20)
        assert opts.batch_commit_size == 20

    def test_batch_commit_size_zero_disables(self):
        """batch_commit_size=0 désactive le commit intermédiaire."""
        opts = SyncOptions(batch_commit_size=0)
        assert opts.batch_commit_size == 0


# =============================================================================
# 6.5 — Tests rate limit augmenté
# =============================================================================


class TestRateLimitIncreased:
    """Tests pour l'augmentation du rate limit."""

    def test_default_rate_limit_is_10(self):
        """Le rate limit par défaut est 10 req/s."""
        opts = SyncOptions()
        assert opts.requests_per_second == 10

    def test_default_parallel_matches_is_5(self):
        """Le nombre de matchs parallèles par défaut est 5."""
        opts = SyncOptions()
        assert opts.parallel_matches == 5

    def test_custom_rate_limit(self):
        """On peut personnaliser le rate limit."""
        opts = SyncOptions(requests_per_second=3, parallel_matches=2)
        assert opts.requests_per_second == 3
        assert opts.parallel_matches == 2


# =============================================================================
# Tests d'intégration : engine lifecycle
# =============================================================================


class TestEngineLifecycle:
    """Tests de cycle de vie du moteur avec les optimisations Sprint 6."""

    def test_engine_creates_with_new_options(self, temp_duckdb: Path):
        """Le moteur s'initialise correctement avec les nouvelles options."""
        engine = DuckDBSyncEngine(
            player_db_path=str(temp_duckdb),
            xuid="2535423456789",
            gamertag="TestPlayer",
        )
        # Vérifier que batch_compute_performance_scores est appelable
        assert hasattr(engine, "batch_compute_performance_scores")
        assert callable(engine.batch_compute_performance_scores)
        engine.close()

    def test_batch_compute_perf_scores_returns_int(self, temp_duckdb: Path):
        """batch_compute_performance_scores retourne toujours un int."""
        engine = DuckDBSyncEngine(
            player_db_path=str(temp_duckdb),
            xuid="2535423456789",
            gamertag="TestPlayer",
        )
        result = engine.batch_compute_performance_scores()
        assert isinstance(result, int)
        engine.close()
