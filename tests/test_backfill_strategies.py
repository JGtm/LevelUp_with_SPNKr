"""Tests pour scripts/backfill/strategies.py.

Couvre : backfill_end_time, backfill_killer_victim_pairs, compute_performance_score_for_match.
Utilise DuckDB :memory:.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import duckdb
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def conn_with_match_stats():
    """Connexion DuckDB in-memory avec table match_stats."""
    c = duckdb.connect(":memory:")
    c.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR NOT NULL PRIMARY KEY,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            time_played_seconds INTEGER,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            kda FLOAT,
            accuracy FLOAT,
            avg_life_seconds FLOAT,
            personal_score INTEGER,
            damage_dealt FLOAT,
            rank SMALLINT,
            team_mmr FLOAT,
            enemy_mmr FLOAT,
            performance_score FLOAT,
            backfill_completed INTEGER DEFAULT 0
        )
    """)
    yield c
    c.close()


@pytest.fixture()
def conn_with_events():
    """Connexion DuckDB in-memory avec highlight_events + killer_victim_pairs."""
    c = duckdb.connect(":memory:")
    c.execute("""
        CREATE TABLE highlight_events (
            id INTEGER DEFAULT 0,
            match_id VARCHAR NOT NULL,
            event_type VARCHAR,
            time_ms INTEGER,
            xuid VARCHAR,
            gamertag VARCHAR,
            type_hint INTEGER,
            raw_json VARCHAR
        )
    """)
    yield c
    c.close()


# ─────────────────────────────────────────────────────────────────────────────
# Tests backfill_end_time
# ─────────────────────────────────────────────────────────────────────────────


class TestBackfillEndTime:
    def test_updates_null_end_time(self, conn_with_match_stats):
        from scripts.backfill.strategies import backfill_end_time

        conn = conn_with_match_stats
        t = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        conn.execute(
            "INSERT INTO match_stats (match_id, start_time, time_played_seconds, end_time) "
            "VALUES (?, ?, ?, NULL)",
            ["m1", t, 600],
        )
        n = backfill_end_time(conn)
        assert n == 1
        result = conn.execute("SELECT end_time FROM match_stats WHERE match_id='m1'").fetchone()
        assert result[0] is not None

    def test_skips_already_set(self, conn_with_match_stats):
        from scripts.backfill.strategies import backfill_end_time

        conn = conn_with_match_stats
        t = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        end = t + timedelta(seconds=600)
        conn.execute(
            "INSERT INTO match_stats (match_id, start_time, time_played_seconds, end_time) "
            "VALUES (?, ?, ?, ?)",
            ["m1", t, 600, end],
        )
        n = backfill_end_time(conn)
        assert n == 0

    def test_force_recalculates(self, conn_with_match_stats):
        from scripts.backfill.strategies import backfill_end_time

        conn = conn_with_match_stats
        t = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        end_old = t + timedelta(seconds=300)  # wrong
        conn.execute(
            "INSERT INTO match_stats (match_id, start_time, time_played_seconds, end_time) "
            "VALUES (?, ?, ?, ?)",
            ["m1", t, 600, end_old],
        )
        n = backfill_end_time(conn, force=True)
        assert n == 1

    def test_no_matches(self, conn_with_match_stats):
        from scripts.backfill.strategies import backfill_end_time

        assert backfill_end_time(conn_with_match_stats) == 0

    def test_null_start_time_skipped(self, conn_with_match_stats):
        from scripts.backfill.strategies import backfill_end_time

        conn = conn_with_match_stats
        conn.execute(
            "INSERT INTO match_stats (match_id, start_time, time_played_seconds, end_time) "
            "VALUES (?, NULL, ?, NULL)",
            ["m1", 600],
        )
        n = backfill_end_time(conn)
        assert n == 0


# ─────────────────────────────────────────────────────────────────────────────
# Tests backfill_killer_victim_pairs
# ─────────────────────────────────────────────────────────────────────────────


class TestBackfillKillerVictimPairs:
    def test_no_events(self, conn_with_events):
        from scripts.backfill.strategies import backfill_killer_victim_pairs

        n = backfill_killer_victim_pairs(conn_with_events, "xuid1")
        assert n == 0

    def test_creates_table(self, conn_with_events):
        """La table killer_victim_pairs est créée si absente."""
        from scripts.backfill.strategies import backfill_killer_victim_pairs

        conn = conn_with_events
        backfill_killer_victim_pairs(conn, "xuid1")
        # Table should exist now
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'killer_victim_pairs'"
        ).fetchone()[0]
        assert result == 1

    def test_with_kill_death_events(self, conn_with_events):
        """Insert matching kill/death events → paires created."""
        from scripts.backfill.strategies import backfill_killer_victim_pairs

        conn = conn_with_events
        # Insert kill and death events at same time
        conn.execute(
            "INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag) "
            "VALUES (?, ?, ?, ?, ?)",
            ["m1", "Kill", 5000, "killer1", "KillerGT"],
        )
        conn.execute(
            "INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag) "
            "VALUES (?, ?, ?, ?, ?)",
            ["m1", "Death", 5000, "victim1", "VictimGT"],
        )
        n = backfill_killer_victim_pairs(conn, "xuid1")
        assert n >= 1

    def test_force_drops_table(self, conn_with_events):
        """Mode force recrée la table."""
        from scripts.backfill.strategies import backfill_killer_victim_pairs

        conn = conn_with_events
        # First call creates table
        backfill_killer_victim_pairs(conn, "xuid1")
        # Force drops and recreates
        backfill_killer_victim_pairs(conn, "xuid1", force=True)
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'killer_victim_pairs'"
        ).fetchone()[0]
        assert result == 1

    def test_incremental_skips_existing(self, conn_with_events):
        """Mode incrémental ne retraite pas les matchs déjà traités."""
        from scripts.backfill.strategies import backfill_killer_victim_pairs

        conn = conn_with_events
        conn.execute(
            "INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag) "
            "VALUES (?, ?, ?, ?, ?)",
            ["m1", "Kill", 5000, "k1", "K1"],
        )
        conn.execute(
            "INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag) "
            "VALUES (?, ?, ?, ?, ?)",
            ["m1", "Death", 5000, "v1", "V1"],
        )
        n1 = backfill_killer_victim_pairs(conn, "xuid1")
        assert n1 == 1
        # Second call should find no new matches
        n2 = backfill_killer_victim_pairs(conn, "xuid1")
        assert n2 == 0

    def test_only_kills_no_deaths(self, conn_with_events):
        """Match with only kills (no deaths) → skipped."""
        from scripts.backfill.strategies import backfill_killer_victim_pairs

        conn = conn_with_events
        conn.execute(
            "INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag) "
            "VALUES (?, ?, ?, ?, ?)",
            ["m1", "Kill", 5000, "k1", "K1"],
        )
        n = backfill_killer_victim_pairs(conn, "xuid1")
        assert n == 0


# ─────────────────────────────────────────────────────────────────────────────
# Tests compute_performance_score_for_match
# ─────────────────────────────────────────────────────────────────────────────


class TestComputePerformanceScoreForMatch:
    def test_score_already_exists(self, conn_with_match_stats):
        """Retourne False si le score existe déjà."""
        from scripts.backfill.strategies import compute_performance_score_for_match

        conn = conn_with_match_stats
        t = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        conn.execute(
            "INSERT INTO match_stats (match_id, start_time, performance_score, kills, deaths, assists, time_played_seconds) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ["m1", t, 75.0, 10, 5, 3, 600],
        )
        result = compute_performance_score_for_match(conn, "m1")
        assert result is False

    def test_not_enough_history(self, conn_with_match_stats):
        """Retourne False si pas assez de matchs historiques."""
        from scripts.backfill.strategies import compute_performance_score_for_match

        conn = conn_with_match_stats
        t = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        conn.execute(
            "INSERT INTO match_stats (match_id, start_time, performance_score, kills, deaths, assists, time_played_seconds) "
            "VALUES (?, ?, NULL, ?, ?, ?, ?)",
            ["m1", t, 10, 5, 3, 600],
        )
        result = compute_performance_score_for_match(conn, "m1")
        assert result is False

    def test_match_not_found(self, conn_with_match_stats):
        """Retourne False si le match n'existe pas."""
        from scripts.backfill.strategies import compute_performance_score_for_match

        result = compute_performance_score_for_match(conn_with_match_stats, "nonexistent")
        assert result is False

    def test_null_start_time(self, conn_with_match_stats):
        """Retourne False si start_time est NULL."""
        from scripts.backfill.strategies import compute_performance_score_for_match

        conn = conn_with_match_stats
        conn.execute(
            "INSERT INTO match_stats (match_id, start_time, performance_score, kills, deaths, assists, time_played_seconds) "
            "VALUES (?, NULL, NULL, ?, ?, ?, ?)",
            ["m1", 10, 5, 3, 600],
        )
        result = compute_performance_score_for_match(conn, "m1")
        assert result is False
