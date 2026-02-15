"""Tests pour scripts/backfill/core.py — fonctions d'insertion DuckDB.

Utilise DuckDB :memory: pour chaque test.
Couvre : insert_medal_rows, insert_event_rows, insert_skill_row,
         insert_personal_score_rows, insert_alias_rows, insert_participant_rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import duckdb
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def conn():
    """Connexion DuckDB in-memory avec les tables nécessaires."""
    c = duckdb.connect(":memory:")

    # medals_earned
    c.execute("""
        CREATE TABLE medals_earned (
            match_id VARCHAR NOT NULL,
            medal_name_id BIGINT NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY (match_id, medal_name_id)
        )
    """)

    # highlight_events
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

    # player_match_stats
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

    # personal_score_awards
    c.execute("""
        CREATE TABLE personal_score_awards (
            match_id VARCHAR NOT NULL,
            xuid VARCHAR NOT NULL,
            award_name VARCHAR,
            award_category VARCHAR,
            award_count INTEGER,
            award_score INTEGER,
            created_at TIMESTAMP
        )
    """)

    # xuid_aliases
    c.execute("""
        CREATE TABLE xuid_aliases (
            xuid VARCHAR NOT NULL PRIMARY KEY,
            gamertag VARCHAR,
            last_seen VARCHAR,
            source VARCHAR,
            updated_at VARCHAR
        )
    """)

    yield c
    c.close()


# ─────────────────────────────────────────────────────────────────────────────
# Dataclass stubs (mimics src.data.sync.models)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class MedalRow:
    match_id: str
    medal_name_id: int
    count: int


@dataclass
class EventRow:
    match_id: str
    event_type: str
    time_ms: int = 0
    xuid: str | None = None
    gamertag: str | None = None
    type_hint: int | None = None
    raw_json: str | None = None


@dataclass
class SkillRow:
    match_id: str
    team_id: int | None = None
    team_mmr: float | None = None
    enemy_mmr: float | None = None
    kills_expected: float | None = None
    kills_stddev: float | None = None
    deaths_expected: float | None = None
    deaths_stddev: float | None = None
    assists_expected: float | None = None
    assists_stddev: float | None = None


@dataclass
class PersonalScoreRow:
    match_id: str
    xuid: str
    award_name: str = "Kill"
    award_category: str = "kill"
    award_count: int = 1
    award_score: int = 100


@dataclass
class AliasRow:
    xuid: str
    gamertag: str
    last_seen: datetime | None = None
    source: str = "test"


@dataclass
class ParticipantRow:
    match_id: str
    xuid: str
    team_id: int | None = None
    outcome: int | None = None
    gamertag: str | None = None
    rank: int | None = None
    score: int | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    shots_fired: int | None = None
    shots_hit: int | None = None
    damage_dealt: float | None = None
    damage_taken: float | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Tests insert_medal_rows
# ─────────────────────────────────────────────────────────────────────────────


class TestInsertMedalRows:
    def test_empty_input(self, conn):
        from scripts.backfill.core import insert_medal_rows

        assert insert_medal_rows(conn, []) == 0

    def test_insert_medals(self, conn):
        from scripts.backfill.core import insert_medal_rows

        rows = [
            MedalRow(match_id="m1", medal_name_id=100, count=3),
            MedalRow(match_id="m1", medal_name_id=200, count=1),
        ]
        n = insert_medal_rows(conn, rows)
        assert n == 2
        result = conn.execute("SELECT COUNT(*) FROM medals_earned").fetchone()[0]
        assert result == 2

    def test_upsert_duplicates(self, conn):
        from scripts.backfill.core import insert_medal_rows

        rows = [MedalRow(match_id="m1", medal_name_id=100, count=3)]
        insert_medal_rows(conn, rows)
        # Insert again → upsert
        rows2 = [MedalRow(match_id="m1", medal_name_id=100, count=5)]
        insert_medal_rows(conn, rows2)
        result = conn.execute(
            "SELECT count FROM medals_earned WHERE match_id='m1' AND medal_name_id=100"
        ).fetchone()[0]
        # Upsert should have updated or kept the value
        assert result in (3, 5)


# ─────────────────────────────────────────────────────────────────────────────
# Tests insert_event_rows
# ─────────────────────────────────────────────────────────────────────────────


class TestInsertEventRows:
    def test_empty_input(self, conn):
        from scripts.backfill.core import insert_event_rows

        assert insert_event_rows(conn, []) == 0

    def test_insert_events(self, conn):
        from scripts.backfill.core import insert_event_rows

        rows = [
            EventRow(match_id="m1", event_type="Kill", time_ms=5000, xuid="x1"),
            EventRow(match_id="m1", event_type="Death", time_ms=6000, xuid="x2"),
        ]
        n = insert_event_rows(conn, rows)
        assert n == 2
        result = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
        assert result == 2

    def test_dedup_on_reinsert(self, conn):
        """Reinserting for same match_id deletes old events first."""
        from scripts.backfill.core import insert_event_rows

        rows = [EventRow(match_id="m1", event_type="Kill", time_ms=5000)]
        insert_event_rows(conn, rows)
        # Insert again
        rows2 = [
            EventRow(match_id="m1", event_type="Death", time_ms=6000),
        ]
        insert_event_rows(conn, rows2)
        result = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
        assert result == 1  # old deleted, only new one

    def test_multiple_matches(self, conn):
        """Events for different matches don't interfere."""
        from scripts.backfill.core import insert_event_rows

        rows1 = [EventRow(match_id="m1", event_type="Kill")]
        rows2 = [EventRow(match_id="m2", event_type="Death")]
        insert_event_rows(conn, rows1)
        insert_event_rows(conn, rows2)
        result = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
        assert result == 2


# ─────────────────────────────────────────────────────────────────────────────
# Tests insert_skill_row
# ─────────────────────────────────────────────────────────────────────────────


class TestInsertSkillRow:
    def test_none_input(self, conn):
        from scripts.backfill.core import insert_skill_row

        assert insert_skill_row(conn, None, "xuid1") == 0

    def test_insert_skill(self, conn):
        from scripts.backfill.core import insert_skill_row

        row = SkillRow(
            match_id="m1",
            team_id=0,
            team_mmr=1200.0,
            enemy_mmr=1150.0,
            kills_expected=10.0,
            kills_stddev=2.0,
        )
        n = insert_skill_row(conn, row, "xuid1")
        assert n == 1
        result = conn.execute(
            "SELECT team_mmr FROM player_match_stats WHERE match_id='m1'"
        ).fetchone()
        assert result[0] == pytest.approx(1200.0)

    def test_upsert_skill(self, conn):
        from scripts.backfill.core import insert_skill_row

        row1 = SkillRow(match_id="m1", team_mmr=1200.0)
        insert_skill_row(conn, row1, "xuid1")
        row2 = SkillRow(match_id="m1", team_mmr=1300.0)
        insert_skill_row(conn, row2, "xuid1")
        count = conn.execute("SELECT COUNT(*) FROM player_match_stats").fetchone()[0]
        assert count == 1  # upsert, not duplicate


# ─────────────────────────────────────────────────────────────────────────────
# Tests insert_personal_score_rows
# ─────────────────────────────────────────────────────────────────────────────


class TestInsertPersonalScoreRows:
    def test_empty_input(self, conn):
        from scripts.backfill.core import insert_personal_score_rows

        assert insert_personal_score_rows(conn, []) == 0

    def test_insert_scores(self, conn):
        from scripts.backfill.core import insert_personal_score_rows

        rows = [
            PersonalScoreRow(
                match_id="m1", xuid="x1", award_name="Kill", award_count=5, award_score=500
            ),
            PersonalScoreRow(
                match_id="m1", xuid="x1", award_name="Assist", award_count=3, award_score=150
            ),
        ]
        n = insert_personal_score_rows(conn, rows)
        assert n == 2
        result = conn.execute("SELECT COUNT(*) FROM personal_score_awards").fetchone()[0]
        assert result == 2

    def test_dedup_on_reinsert(self, conn):
        """Reinserting for same match_id/xuid deletes old scores first."""
        from scripts.backfill.core import insert_personal_score_rows

        rows = [PersonalScoreRow(match_id="m1", xuid="x1", award_name="Kill")]
        insert_personal_score_rows(conn, rows)
        rows2 = [PersonalScoreRow(match_id="m1", xuid="x1", award_name="Assist")]
        insert_personal_score_rows(conn, rows2)
        result = conn.execute("SELECT COUNT(*) FROM personal_score_awards").fetchone()[0]
        assert result == 1  # old deleted


# ─────────────────────────────────────────────────────────────────────────────
# Tests insert_alias_rows
# ─────────────────────────────────────────────────────────────────────────────


class TestInsertAliasRows:
    def test_empty_input(self, conn):
        from scripts.backfill.core import insert_alias_rows

        assert insert_alias_rows(conn, []) == 0

    def test_insert_aliases(self, conn):
        from scripts.backfill.core import insert_alias_rows

        now = datetime.now(timezone.utc)
        rows = [
            AliasRow(xuid="x1", gamertag="Player1", last_seen=now),
            AliasRow(xuid="x2", gamertag="Player2", last_seen=now),
        ]
        n = insert_alias_rows(conn, rows)
        assert n == 2
        result = conn.execute("SELECT COUNT(*) FROM xuid_aliases").fetchone()[0]
        assert result == 2

    def test_upsert_alias(self, conn):
        from scripts.backfill.core import insert_alias_rows

        now = datetime.now(timezone.utc)
        rows = [AliasRow(xuid="x1", gamertag="OldName", last_seen=now)]
        insert_alias_rows(conn, rows)
        rows2 = [AliasRow(xuid="x1", gamertag="NewName", last_seen=now)]
        insert_alias_rows(conn, rows2)
        count = conn.execute("SELECT COUNT(*) FROM xuid_aliases").fetchone()[0]
        assert count == 1  # upsert, not duplicate


# ─────────────────────────────────────────────────────────────────────────────
# Tests insert_participant_rows
# ─────────────────────────────────────────────────────────────────────────────


class TestInsertParticipantRows:
    def test_empty_input(self, conn):
        from scripts.backfill.core import insert_participant_rows

        assert insert_participant_rows(conn, []) == 0

    def test_insert_participants(self, conn):
        from scripts.backfill.core import insert_participant_rows

        rows = [
            ParticipantRow(match_id="m1", xuid="x1", team_id=0, gamertag="P1", kills=10),
            ParticipantRow(match_id="m1", xuid="x2", team_id=1, gamertag="P2", kills=8),
        ]
        n = insert_participant_rows(conn, rows)
        assert n == 2
        result = conn.execute("SELECT COUNT(*) FROM match_participants").fetchone()[0]
        assert result == 2

    def test_upsert_participants(self, conn):
        from scripts.backfill.core import insert_participant_rows

        rows = [ParticipantRow(match_id="m1", xuid="x1", gamertag="P1")]
        insert_participant_rows(conn, rows)
        rows2 = [ParticipantRow(match_id="m1", xuid="x1", gamertag="P1_updated")]
        insert_participant_rows(conn, rows2)
        count = conn.execute("SELECT COUNT(*) FROM match_participants").fetchone()[0]
        assert count == 1

    def test_creates_table_if_absent(self):
        """Table match_participants is created if it doesn't exist."""
        from scripts.backfill.core import insert_participant_rows

        c = duckdb.connect(":memory:")
        rows = [ParticipantRow(match_id="m1", xuid="x1")]
        n = insert_participant_rows(c, rows)
        assert n == 1
        result = c.execute("SELECT COUNT(*) FROM match_participants").fetchone()[0]
        assert result == 1
        c.close()
