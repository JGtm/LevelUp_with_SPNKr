"""Tests de charge — Sprint 7 (v5 shared_matches).

Vérifie les performances du repository et du sync avec de gros volumes :
- Chargement de 1000+ matchs en < 2s
- Requêtes filtrées sur gros volume
- Pagination performante
- ATTACH shared ne dégrade pas les performances

Marqués @pytest.mark.slow pour exclusion en CI rapide.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import polars as pl
import pytest

from src.data.repositories.duckdb_repo import DuckDBRepository

# =============================================================================
# Helpers
# =============================================================================

PLAYER_XUID = "xuid_perf_player"
N_MATCHES_LARGE = 1000


def _create_large_player_db(db_path: Path, n_matches: int = N_MATCHES_LARGE) -> None:
    """Crée une DB joueur avec N matchs pour les tests de charge."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP NOT NULL,
            map_id VARCHAR, map_name VARCHAR,
            playlist_id VARCHAR, playlist_name VARCHAR,
            pair_id VARCHAR, pair_name VARCHAR,
            game_variant_id VARCHAR, game_variant_name VARCHAR,
            outcome INTEGER, team_id INTEGER,
            kda FLOAT, max_killing_spree INTEGER,
            headshot_kills INTEGER, avg_life_seconds FLOAT,
            time_played_seconds INTEGER,
            kills INTEGER, deaths INTEGER, assists INTEGER,
            accuracy FLOAT,
            my_team_score INTEGER, enemy_team_score INTEGER,
            team_mmr FLOAT, enemy_mmr FLOAT,
            personal_score INTEGER,
            is_firefight BOOLEAN DEFAULT FALSE
        )
    """)

    # Insérer N matchs en batch
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    maps = ["Aquarius", "Streets", "Recharge", "Live Fire", "Bazaar"]
    playlists = ["Ranked Arena", "Quick Play", "Big Team Battle"]

    rows = []
    for i in range(n_matches):
        m_id = f"perf_match_{i:05d}"
        start = base_time + timedelta(hours=i)
        map_name = maps[i % len(maps)]
        playlist = playlists[i % len(playlists)]
        outcome = 2 if i % 3 != 0 else 3  # 2/3 wins
        kills = 10 + (i % 20)
        deaths = 5 + (i % 15)
        assists = 3 + (i % 8)
        kda = (kills + assists / 3) / max(deaths, 1)
        accuracy = 40.0 + (i % 30)

        rows.append(
            (
                m_id,
                start,
                f"map_{i%5}",
                map_name,
                f"pl_{i%3}",
                playlist,
                None,
                None,
                None,
                None,
                outcome,
                0,
                round(kda, 2),
                i % 10,
                i % 8,
                30.0 + (i % 40),
                600 + (i % 300),
                kills,
                deaths,
                assists,
                accuracy,
                50 - (i % 10),
                45 + (i % 10),
                1500.0 + (i % 200),
                1480.0 + (i % 200),
                2000 + (i % 500),
                False,
            )
        )

    conn.executemany(
        """INSERT INTO match_stats VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )""",
        rows,
    )
    conn.close()


def _create_large_shared_db(db_path: Path, n_matches: int = N_MATCHES_LARGE) -> None:
    """Crée une shared_matches.duckdb avec N matchs."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

    conn.execute("""
        CREATE TABLE match_registry (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            playlist_id VARCHAR, playlist_name VARCHAR,
            map_id VARCHAR, map_name VARCHAR,
            pair_id VARCHAR, pair_name VARCHAR,
            game_variant_id VARCHAR, game_variant_name VARCHAR,
            mode_category VARCHAR,
            is_ranked BOOLEAN DEFAULT FALSE,
            is_firefight BOOLEAN DEFAULT FALSE,
            duration_seconds INTEGER,
            team_0_score SMALLINT, team_1_score SMALLINT,
            backfill_completed INTEGER DEFAULT 0,
            participants_loaded BOOLEAN DEFAULT FALSE,
            events_loaded BOOLEAN DEFAULT FALSE,
            medals_loaded BOOLEAN DEFAULT FALSE,
            first_sync_by VARCHAR, first_sync_at TIMESTAMP,
            last_updated_at TIMESTAMP,
            player_count SMALLINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE match_participants (
            match_id VARCHAR NOT NULL, xuid VARCHAR NOT NULL,
            gamertag VARCHAR, team_id INTEGER, outcome INTEGER,
            rank SMALLINT, score INTEGER, kills SMALLINT,
            deaths SMALLINT, assists SMALLINT,
            shots_fired INTEGER, shots_hit INTEGER,
            damage_dealt FLOAT, damage_taken FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, xuid)
        )
    """)
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS highlight_events_id_seq;
        CREATE TABLE highlight_events (
            id INTEGER PRIMARY KEY DEFAULT nextval('highlight_events_id_seq'),
            match_id VARCHAR NOT NULL, event_type VARCHAR NOT NULL,
            time_ms INTEGER, killer_xuid VARCHAR,
            killer_gamertag VARCHAR, victim_xuid VARCHAR,
            victim_gamertag VARCHAR, type_hint INTEGER,
            raw_json VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE medals_earned (
            match_id VARCHAR NOT NULL, xuid VARCHAR NOT NULL,
            medal_name_id BIGINT NOT NULL, count SMALLINT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, xuid, medal_name_id)
        )
    """)
    conn.execute("""
        CREATE TABLE xuid_aliases (
            xuid VARCHAR PRIMARY KEY, gamertag VARCHAR NOT NULL,
            last_seen TIMESTAMP, source VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY,
            description VARCHAR NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO schema_version VALUES (1, 'v5.0 perf test', CURRENT_TIMESTAMP)")

    # Insérer N matchs en batch
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    maps = ["Aquarius", "Streets", "Recharge", "Live Fire", "Bazaar"]

    reg_rows = []
    part_rows = []
    for i in range(n_matches):
        m_id = f"perf_match_{i:05d}"
        start = base_time + timedelta(hours=i)
        map_name = maps[i % len(maps)]
        reg_rows.append(
            (
                m_id,
                start,
                start + timedelta(minutes=10),
                f"pl_{i%3}",
                "Quick Play",
                f"map_{i%5}",
                map_name,
                None,
                None,
                None,
                None,
                "Arena",
                False,
                False,
                600,
                50,
                45,
            )
        )
        # 8 participants par match
        for p in range(8):
            pxuid = f"xuid_p{p}" if p > 0 else PLAYER_XUID
            gamertag = f"Player{p}" if p > 0 else "PerfPlayer"
            outcome = 2 if p < 4 else 3
            part_rows.append(
                (
                    m_id,
                    pxuid,
                    gamertag,
                    0 if p < 4 else 1,
                    outcome,
                    p + 1,
                    1500 + p * 100,
                    10 + p,
                    8 + p,
                    3 + p,
                    200 + p * 10,
                    100 + p * 5,
                    3000.0 + p * 100,
                    2500.0 + p * 100,
                )
            )

    conn.executemany(
        """INSERT INTO match_registry (
            match_id, start_time, end_time,
            playlist_id, playlist_name, map_id, map_name,
            pair_id, pair_name, game_variant_id, game_variant_name,
            mode_category, is_ranked, is_firefight,
            duration_seconds, team_0_score, team_1_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        reg_rows,
    )
    conn.executemany(
        """INSERT INTO match_participants (
            match_id, xuid, gamertag, team_id, outcome,
            rank, score, kills, deaths, assists,
            shots_fired, shots_hit, damage_dealt, damage_taken
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        part_rows,
    )
    conn.close()


# =============================================================================
# Tests de charge
# =============================================================================


@pytest.mark.slow
class TestLoadPerformance:
    """Tests de charge pour le repository v5."""

    @pytest.fixture(scope="class")
    def large_repo(self, tmp_path_factory) -> DuckDBRepository:
        """Crée un repo avec 1000 matchs (shared + player)."""
        tmp = tmp_path_factory.mktemp("perf")
        player_db = tmp / "player" / "stats.duckdb"
        shared_db = tmp / "shared_matches.duckdb"

        _create_large_player_db(player_db, N_MATCHES_LARGE)
        _create_large_shared_db(shared_db, N_MATCHES_LARGE)

        repo = DuckDBRepository(
            player_db,
            PLAYER_XUID,
            shared_db_path=shared_db,
            gamertag="PerfPlayer",
        )
        yield repo
        repo.close()

    def test_load_1000_matches_under_2s(self, large_repo: DuckDBRepository) -> None:
        """Charger 1000 matchs en < 2 secondes."""
        start = time.time()
        matches = large_repo.load_matches()
        elapsed = time.time() - start

        assert len(matches) >= N_MATCHES_LARGE
        assert elapsed < 2.0, f"load_matches trop lent : {elapsed:.2f}s"

    def test_get_match_count_fast(self, large_repo: DuckDBRepository) -> None:
        """Comptage rapide (< 0.5s)."""
        start = time.time()
        count = large_repo.get_match_count()
        elapsed = time.time() - start

        assert count >= N_MATCHES_LARGE
        assert elapsed < 0.5, f"get_match_count trop lent : {elapsed:.2f}s"

    def test_load_matches_paginated_fast(self, large_repo: DuckDBRepository) -> None:
        """Pagination page 1 en < 0.5s."""
        start = time.time()
        matches, total_pages = large_repo.load_matches_paginated(page=1, page_size=50)
        elapsed = time.time() - start

        assert len(matches) == 50
        assert total_pages >= 20  # 1000/50 = 20
        assert elapsed < 0.5, f"load_matches_paginated trop lent : {elapsed:.2f}s"

    def test_load_matches_paginated_last_page(self, large_repo: DuckDBRepository) -> None:
        """Pagination dernière page fonctionne."""
        _, total_pages = large_repo.load_matches_paginated(page=1, page_size=50)
        matches, _ = large_repo.load_matches_paginated(page=total_pages, page_size=50)
        assert len(matches) > 0
        assert len(matches) <= 50

    def test_load_matches_as_polars_fast(self, large_repo: DuckDBRepository) -> None:
        """Conversion Polars en < 1s."""
        start = time.time()
        df = large_repo.load_matches_as_polars()
        elapsed = time.time() - start

        assert isinstance(df, pl.DataFrame)
        assert len(df) >= N_MATCHES_LARGE
        assert elapsed < 1.0, f"load_matches_as_polars trop lent : {elapsed:.2f}s"

    def test_load_recent_matches_fast(self, large_repo: DuckDBRepository) -> None:
        """50 matchs récents en < 0.3s."""
        start = time.time()
        recent = large_repo.load_recent_matches(limit=50)
        elapsed = time.time() - start

        assert len(recent) == 50
        assert elapsed < 0.3, f"load_recent_matches trop lent : {elapsed:.2f}s"


@pytest.mark.slow
class TestLoadPerformanceV4Fallback:
    """Tests de charge en mode v4 (sans shared)."""

    @pytest.fixture(scope="class")
    def v4_repo(self, tmp_path_factory) -> DuckDBRepository:
        """Crée un repo v4 avec 1000 matchs (sans shared)."""
        tmp = tmp_path_factory.mktemp("perf_v4")
        player_db = tmp / "player" / "stats.duckdb"
        _create_large_player_db(player_db, N_MATCHES_LARGE)

        repo = DuckDBRepository(
            player_db,
            PLAYER_XUID,
            gamertag="PerfPlayerV4",
        )
        yield repo
        repo.close()

    def test_load_1000_matches_v4_under_2s(self, v4_repo: DuckDBRepository) -> None:
        """load_matches v4 en < 2s."""
        start = time.time()
        matches = v4_repo.load_matches()
        elapsed = time.time() - start

        assert len(matches) == N_MATCHES_LARGE
        assert elapsed < 2.0, f"load_matches v4 trop lent : {elapsed:.2f}s"

    def test_match_count_v4(self, v4_repo: DuckDBRepository) -> None:
        """V4 count."""
        count = v4_repo.get_match_count()
        assert count == N_MATCHES_LARGE
