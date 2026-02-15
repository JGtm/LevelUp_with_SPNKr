"""Tests pour scripts/backfill/orchestrator.py — fonctions helpers pures et DuckDB.

Couvre : _empty_result, _mark_backfill_completed, _apply_schema_migrations,
         _update_accuracy_shots, _update_enemy_mmr, _update_participants_details,
         _backfill_local_only, _resolve_xuid_fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch

import duckdb
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def conn():
    """Connexion DuckDB in-memory avec match_stats."""
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
            accuracy FLOAT,
            shots_fired INTEGER,
            shots_hit INTEGER,
            enemy_mmr FLOAT,
            performance_score FLOAT,
            backfill_completed INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE player_match_stats (
            match_id VARCHAR NOT NULL,
            xuid VARCHAR NOT NULL,
            team_id INTEGER,
            team_mmr FLOAT,
            enemy_mmr FLOAT,
            kills_expected FLOAT,
            kills_stddev FLOAT,
            deaths_expected FLOAT,
            deaths_stddev FLOAT,
            assists_expected FLOAT,
            assists_stddev FLOAT,
            PRIMARY KEY (match_id, xuid)
        )
    """)
    yield c
    c.close()


@dataclass
class FakeMatchRow:
    """Simule un MatchStatsRow pour _update_accuracy_shots."""

    accuracy: float | None = None
    shots_fired: int | None = None
    shots_hit: int | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _empty_result
# ─────────────────────────────────────────────────────────────────────────────


class TestEmptyResult:
    def test_has_expected_keys(self):
        from scripts.backfill.orchestrator import _empty_result

        result = _empty_result()
        assert isinstance(result, dict)
        expected_keys = [
            "matches_checked",
            "matches_missing_data",
            "medals_inserted",
            "events_inserted",
            "skill_inserted",
            "personal_scores_inserted",
            "performance_scores_inserted",
            "aliases_inserted",
            "accuracy_updated",
            "shots_updated",
            "enemy_mmr_updated",
            "assets_updated",
            "participants_inserted",
            "participants_scores_updated",
            "participants_kda_updated",
            "participants_shots_updated",
            "participants_damage_updated",
            "killer_victim_pairs_inserted",
            "end_time_updated",
            "sessions_updated",
            "citations_computed",
        ]
        for key in expected_keys:
            assert key in result
            assert result[key] == 0

    def test_returns_new_instance(self):
        from scripts.backfill.orchestrator import _empty_result

        r1 = _empty_result()
        r2 = _empty_result()
        r1["medals_inserted"] = 99
        assert r2["medals_inserted"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Tests _mark_backfill_completed
# ─────────────────────────────────────────────────────────────────────────────


class TestMarkBackfillCompleted:
    def test_sets_bitmask(self, conn):
        from scripts.backfill.orchestrator import _mark_backfill_completed

        conn.execute(
            "INSERT INTO match_stats (match_id, backfill_completed) VALUES (?, ?)",
            ["m1", 0],
        )
        _mark_backfill_completed(conn, "m1", mask=5)
        result = conn.execute(
            "SELECT backfill_completed FROM match_stats WHERE match_id='m1'"
        ).fetchone()[0]
        assert result == 5

    def test_or_with_existing(self, conn):
        from scripts.backfill.orchestrator import _mark_backfill_completed

        conn.execute(
            "INSERT INTO match_stats (match_id, backfill_completed) VALUES (?, ?)",
            ["m1", 3],
        )
        _mark_backfill_completed(conn, "m1", mask=4)
        result = conn.execute(
            "SELECT backfill_completed FROM match_stats WHERE match_id='m1'"
        ).fetchone()[0]
        assert result == 7  # 3 | 4

    def test_zero_mask_noop(self, conn):
        from scripts.backfill.orchestrator import _mark_backfill_completed

        conn.execute(
            "INSERT INTO match_stats (match_id, backfill_completed) VALUES (?, ?)",
            ["m1", 3],
        )
        _mark_backfill_completed(conn, "m1", mask=0)
        result = conn.execute(
            "SELECT backfill_completed FROM match_stats WHERE match_id='m1'"
        ).fetchone()[0]
        assert result == 3

    def test_null_backfill_completed(self, conn):
        from scripts.backfill.orchestrator import _mark_backfill_completed

        conn.execute(
            "INSERT INTO match_stats (match_id, backfill_completed) VALUES (?, NULL)",
            ["m1"],
        )
        _mark_backfill_completed(conn, "m1", mask=5)
        result = conn.execute(
            "SELECT backfill_completed FROM match_stats WHERE match_id='m1'"
        ).fetchone()[0]
        assert result == 5


# ─────────────────────────────────────────────────────────────────────────────
# Tests _update_accuracy_shots
# ─────────────────────────────────────────────────────────────────────────────


class TestUpdateAccuracyShots:
    def test_update_accuracy_when_null(self, conn):
        from scripts.backfill.orchestrator import _update_accuracy_shots

        conn.execute(
            "INSERT INTO match_stats (match_id, accuracy) VALUES (?, NULL)",
            ["m1"],
        )
        row = FakeMatchRow(accuracy=0.55)
        a, s = _update_accuracy_shots(
            conn,
            row,
            "m1",
            accuracy=True,
            shots=False,
            force_accuracy=False,
            force_shots=False,
        )
        assert a == 1
        assert s == 0
        result = conn.execute("SELECT accuracy FROM match_stats WHERE match_id='m1'").fetchone()[0]
        assert result == pytest.approx(0.55)

    def test_skip_accuracy_when_already_set(self, conn):
        from scripts.backfill.orchestrator import _update_accuracy_shots

        conn.execute(
            "INSERT INTO match_stats (match_id, accuracy) VALUES (?, ?)",
            ["m1", 0.40],
        )
        row = FakeMatchRow(accuracy=0.55)
        a, _ = _update_accuracy_shots(
            conn,
            row,
            "m1",
            accuracy=True,
            shots=False,
            force_accuracy=False,
            force_shots=False,
        )
        assert a == 0  # not updated

    def test_force_accuracy(self, conn):
        from scripts.backfill.orchestrator import _update_accuracy_shots

        conn.execute(
            "INSERT INTO match_stats (match_id, accuracy) VALUES (?, ?)",
            ["m1", 0.40],
        )
        row = FakeMatchRow(accuracy=0.55)
        a, _ = _update_accuracy_shots(
            conn,
            row,
            "m1",
            accuracy=True,
            shots=False,
            force_accuracy=True,
            force_shots=False,
        )
        assert a == 1

    def test_update_shots_when_null(self, conn):
        from scripts.backfill.orchestrator import _update_accuracy_shots

        conn.execute(
            "INSERT INTO match_stats (match_id, shots_fired, shots_hit) VALUES (?, NULL, NULL)",
            ["m1"],
        )
        row = FakeMatchRow(shots_fired=200, shots_hit=110)
        _, s = _update_accuracy_shots(
            conn,
            row,
            "m1",
            accuracy=False,
            shots=True,
            force_accuracy=False,
            force_shots=False,
        )
        assert s == 1

    def test_force_shots(self, conn):
        from scripts.backfill.orchestrator import _update_accuracy_shots

        conn.execute(
            "INSERT INTO match_stats (match_id, shots_fired, shots_hit) VALUES (?, ?, ?)",
            ["m1", 100, 50],
        )
        row = FakeMatchRow(shots_fired=200, shots_hit=110)
        _, s = _update_accuracy_shots(
            conn,
            row,
            "m1",
            accuracy=False,
            shots=True,
            force_accuracy=False,
            force_shots=True,
        )
        assert s == 1

    def test_no_accuracy_value(self, conn):
        from scripts.backfill.orchestrator import _update_accuracy_shots

        conn.execute("INSERT INTO match_stats (match_id) VALUES (?)", ["m1"])
        row = FakeMatchRow(accuracy=None)
        a, _ = _update_accuracy_shots(
            conn,
            row,
            "m1",
            accuracy=True,
            shots=False,
            force_accuracy=False,
            force_shots=False,
        )
        assert a == 0


# ─────────────────────────────────────────────────────────────────────────────
# Tests _backfill_local_only
# ─────────────────────────────────────────────────────────────────────────────


class TestBackfillLocalOnly:
    def test_no_options(self, conn):
        from pathlib import Path

        from scripts.backfill.orchestrator import _backfill_local_only

        result = _backfill_local_only(
            conn,
            Path("/fake"),
            "xuid1",
            killer_victim=False,
            end_time=False,
            sessions=False,
            citations=False,
        )
        assert isinstance(result, dict)
        assert result["killer_victim_pairs_inserted"] == 0

    def test_end_time_only(self, conn):
        from pathlib import Path

        from scripts.backfill.orchestrator import _backfill_local_only

        t = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        conn.execute(
            "INSERT INTO match_stats (match_id, start_time, time_played_seconds, end_time) "
            "VALUES (?, ?, ?, NULL)",
            ["m1", t, 600],
        )
        result = _backfill_local_only(
            conn,
            Path("/fake"),
            "xuid1",
            killer_victim=False,
            end_time=True,
            sessions=False,
            citations=False,
        )
        assert result["end_time_updated"] == 1

    def test_killer_victim(self, conn):
        from pathlib import Path

        from scripts.backfill.orchestrator import _backfill_local_only

        # No events → 0 pairs
        # Mock _get_shared_connection pour éviter d'accéder à la vraie shared DB
        with patch("scripts.backfill.orchestrator._get_shared_connection", return_value=None):
            result = _backfill_local_only(
                conn,
                Path("/fake"),
                "xuid1",
                killer_victim=True,
                end_time=False,
                sessions=False,
                citations=False,
            )
        assert result["killer_victim_pairs_inserted"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Tests _resolve_xuid_fallback
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveXuidFallback:
    def test_from_highlight_events(self, tmp_path):
        from scripts.backfill.orchestrator import _resolve_xuid_fallback

        db_path = tmp_path / "test.duckdb"
        c = duckdb.connect(str(db_path))
        c.execute("""
            CREATE TABLE highlight_events (
                match_id VARCHAR,
                event_type VARCHAR,
                time_ms INTEGER,
                xuid VARCHAR,
                gamertag VARCHAR
            )
        """)
        c.execute(
            "INSERT INTO highlight_events (match_id, event_type, xuid, gamertag) "
            "VALUES (?, ?, ?, ?)",
            ["m1", "Kill", "1234567890", "TestPlayer"],
        )
        c.close()

        with patch(
            "src.data.repositories.factory.load_db_profiles", side_effect=Exception("no profiles")
        ):
            result = _resolve_xuid_fallback(db_path, "TestPlayer")
        assert result == "1234567890"

    def test_not_found(self, tmp_path):
        from scripts.backfill.orchestrator import _resolve_xuid_fallback

        db_path = tmp_path / "test.duckdb"
        c = duckdb.connect(str(db_path))
        c.execute("""
            CREATE TABLE highlight_events (
                match_id VARCHAR,
                event_type VARCHAR,
                time_ms INTEGER,
                xuid VARCHAR,
                gamertag VARCHAR
            )
        """)
        c.close()

        with patch("src.data.repositories.factory.load_db_profiles", side_effect=Exception("no")):
            result = _resolve_xuid_fallback(db_path, "UnknownPlayer")
        assert result is None

    def test_db_without_events_table(self, tmp_path):
        from scripts.backfill.orchestrator import _resolve_xuid_fallback

        db_path = tmp_path / "test.duckdb"
        c = duckdb.connect(str(db_path))
        c.close()

        with patch("src.data.repositories.factory.load_db_profiles", side_effect=Exception("no")):
            result = _resolve_xuid_fallback(db_path, "TestPlayer")
        assert result is None

    def test_from_db_profiles(self, tmp_path):
        from scripts.backfill.orchestrator import _resolve_xuid_fallback

        db_path = tmp_path / "test.duckdb"
        c = duckdb.connect(str(db_path))
        c.close()

        profiles = {
            "profiles": {
                "TestPlayer": {
                    "xuid": "9876543210",
                    "waypoint_player": "TestPlayer",
                }
            }
        }
        with patch("src.data.repositories.factory.load_db_profiles", return_value=profiles):
            result = _resolve_xuid_fallback(db_path, "TestPlayer")
        assert result == "9876543210"
