"""Tests pour src/data/sync/migrations.py — couverture S18.

Couvre :
  - Helpers utilitaires (get_table_columns, table_exists, column_exists)
  - Migrations match_stats, match_participants
  - Migration highlight_events (séquence auto-increment)
  - Migration medals_earned (INT32 → BIGINT)
  - Backfill bitmask
"""

from __future__ import annotations

import duckdb
import pytest

from src.data.sync.migrations import (
    BACKFILL_FLAGS,
    _add_column_if_missing,
    column_exists,
    compute_backfill_mask,
    ensure_backfill_completed_column,
    ensure_highlight_events_autoincrement,
    ensure_match_participants_columns,
    ensure_match_stats_columns,
    ensure_medals_earned_bigint,
    ensure_performance_score_column,
    get_table_columns,
    table_exists,
)


@pytest.fixture
def conn():
    """Connexion DuckDB in-memory pour les tests."""
    c = duckdb.connect(":memory:")
    yield c
    c.close()


# ─────────────────────────────────────────────────────────────────────────
# Helpers utilitaires
# ─────────────────────────────────────────────────────────────────────────


class TestHelpers:
    """Tests des fonctions utilitaires de base."""

    def test_get_table_columns_empty_when_no_table(self, conn):
        cols = get_table_columns(conn, "nonexistent_table")
        assert cols == set()

    def test_get_table_columns_returns_column_names(self, conn):
        conn.execute("CREATE TABLE t1 (a INTEGER, b VARCHAR, c FLOAT)")
        cols = get_table_columns(conn, "t1")
        assert cols == {"a", "b", "c"}

    def test_table_exists_false_when_absent(self, conn):
        assert table_exists(conn, "nonexistent") is False

    def test_table_exists_true_when_present(self, conn):
        conn.execute("CREATE TABLE t1 (id INTEGER)")
        assert table_exists(conn, "t1") is True

    def test_column_exists_false_when_absent(self, conn):
        conn.execute("CREATE TABLE t1 (id INTEGER)")
        assert column_exists(conn, "t1", "name") is False

    def test_column_exists_true_when_present(self, conn):
        conn.execute("CREATE TABLE t1 (id INTEGER, name VARCHAR)")
        assert column_exists(conn, "t1", "name") is True

    def test_column_exists_false_when_table_absent(self, conn):
        assert column_exists(conn, "nonexistent", "col") is False

    def test_add_column_if_missing_adds_column(self, conn):
        conn.execute("CREATE TABLE t1 (id INTEGER)")
        result = _add_column_if_missing(conn, "t1", "name", "VARCHAR")
        assert result is True
        assert column_exists(conn, "t1", "name") is True

    def test_add_column_if_missing_idempotent(self, conn):
        conn.execute("CREATE TABLE t1 (id INTEGER, name VARCHAR)")
        result = _add_column_if_missing(conn, "t1", "name", "VARCHAR")
        assert result is False

    def test_add_column_if_missing_uses_existing_cols(self, conn):
        conn.execute("CREATE TABLE t1 (id INTEGER)")
        existing = {"id"}
        result = _add_column_if_missing(conn, "t1", "name", "VARCHAR", existing)
        assert result is True
        assert column_exists(conn, "t1", "name") is True

    def test_add_column_if_missing_skips_with_existing_cols(self, conn):
        conn.execute("CREATE TABLE t1 (id INTEGER, name VARCHAR)")
        existing = {"id", "name"}
        result = _add_column_if_missing(conn, "t1", "name", "VARCHAR", existing)
        assert result is False


# ─────────────────────────────────────────────────────────────────────────
# Migrations match_stats
# ─────────────────────────────────────────────────────────────────────────


class TestMatchStatsMigrations:
    """Tests des migrations match_stats."""

    def test_ensure_match_stats_columns_on_empty_db(self, conn):
        """Ne crashe pas si match_stats n'existe pas."""
        ensure_match_stats_columns(conn)  # no-op, pas de table

    def test_ensure_match_stats_columns_adds_all(self, conn):
        conn.execute("CREATE TABLE match_stats (match_id VARCHAR PRIMARY KEY)")
        ensure_match_stats_columns(conn)
        cols = get_table_columns(conn, "match_stats")
        expected = {
            "accuracy",
            "end_time",
            "session_id",
            "session_label",
            "rank",
            "damage_dealt",
            "personal_score",
            "performance_score",
        }
        assert expected.issubset(cols)

    def test_ensure_match_stats_columns_idempotent(self, conn):
        conn.execute("CREATE TABLE match_stats (match_id VARCHAR PRIMARY KEY)")
        ensure_match_stats_columns(conn)
        ensure_match_stats_columns(conn)  # 2e appel idempotent
        cols = get_table_columns(conn, "match_stats")
        assert "performance_score" in cols

    def test_ensure_performance_score_column_alone(self, conn):
        conn.execute("CREATE TABLE match_stats (match_id VARCHAR PRIMARY KEY)")
        ensure_performance_score_column(conn)
        assert column_exists(conn, "match_stats", "performance_score") is True


# ─────────────────────────────────────────────────────────────────────────
# Migrations match_participants
# ─────────────────────────────────────────────────────────────────────────


class TestMatchParticipantsMigrations:
    def test_ensure_match_participants_on_empty_db(self, conn):
        """Ne crashe pas si match_participants n'existe pas."""
        ensure_match_participants_columns(conn)

    def test_ensure_match_participants_adds_all(self, conn):
        conn.execute("CREATE TABLE match_participants (match_id VARCHAR, xuid VARCHAR)")
        ensure_match_participants_columns(conn)
        cols = get_table_columns(conn, "match_participants")
        expected = {
            "rank",
            "score",
            "kills",
            "deaths",
            "assists",
            "shots_fired",
            "shots_hit",
            "damage_dealt",
            "damage_taken",
        }
        assert expected.issubset(cols)


# ─────────────────────────────────────────────────────────────────────────
# Migration highlight_events (séquence)
# ─────────────────────────────────────────────────────────────────────────


class TestHighlightEventsMigration:
    def _create_legacy_table(self, conn):
        """Crée une table highlight_events legacy (sans nextval)."""
        conn.execute("""
            CREATE TABLE highlight_events (
                id INTEGER PRIMARY KEY,
                match_id VARCHAR NOT NULL,
                event_type VARCHAR NOT NULL,
                time_ms INTEGER,
                xuid VARCHAR,
                gamertag VARCHAR,
                type_hint INTEGER,
                raw_json VARCHAR
            )
        """)

    def test_ensure_highlight_noop_if_no_table(self, conn):
        """Ne crashe pas si la table n'existe pas."""
        ensure_highlight_events_autoincrement(conn)

    def test_ensure_highlight_creates_sequence(self, conn):
        """Migre une table legacy vers nextval."""
        self._create_legacy_table(conn)
        conn.execute("""
            INSERT INTO highlight_events VALUES
            (1, 'match1', 'kill', 1000, 'xuid1', 'player1', 0, '{}'),
            (2, 'match1', 'medal', 2000, 'xuid1', 'player1', 1, '{}')
        """)
        ensure_highlight_events_autoincrement(conn)

        # Vérifier que les données existent toujours
        count = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
        assert count == 2

        # Vérifier que INSERT sans id fonctionne (nextval)
        conn.execute("""
            INSERT INTO highlight_events (match_id, event_type)
            VALUES ('match2', 'kill')
        """)
        new_id = conn.execute("SELECT MAX(id) FROM highlight_events").fetchone()[0]
        assert new_id == 3  # max_id était 2, séquence démarre à 3

    def test_ensure_highlight_idempotent(self, conn):
        """La migration est idempotente."""
        self._create_legacy_table(conn)
        conn.execute("""
            INSERT INTO highlight_events VALUES
            (1, 'match1', 'kill', 1000, 'xuid1', 'player1', 0, '{}')
        """)
        ensure_highlight_events_autoincrement(conn)
        ensure_highlight_events_autoincrement(conn)  # 2e appel
        count = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
        assert count == 1

    def test_ensure_highlight_empty_table(self, conn):
        """Fonctionne sur une table vide."""
        self._create_legacy_table(conn)
        ensure_highlight_events_autoincrement(conn)
        conn.execute("""
            INSERT INTO highlight_events (match_id, event_type)
            VALUES ('match1', 'kill')
        """)
        new_id = conn.execute("SELECT MAX(id) FROM highlight_events").fetchone()[0]
        assert new_id == 1  # start with 0+1=1


# ─────────────────────────────────────────────────────────────────────────
# Migration medals_earned (BIGINT)
# ─────────────────────────────────────────────────────────────────────────


class TestMedalsEarnedMigration:
    def test_ensure_medals_noop_if_no_table(self, conn):
        result = ensure_medals_earned_bigint(conn)
        assert result is False

    def test_ensure_medals_migrates_int_to_bigint(self, conn):
        conn.execute("""
            CREATE TABLE medals_earned (
                match_id VARCHAR,
                medal_name_id INTEGER,
                count SMALLINT,
                PRIMARY KEY (match_id, medal_name_id)
            )
        """)
        conn.execute("INSERT INTO medals_earned VALUES ('m1', 12345, 2)")
        result = ensure_medals_earned_bigint(conn)
        assert result is True

        # Vérifier le type
        col_type = conn.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'medals_earned' AND column_name = 'medal_name_id'"
        ).fetchone()
        assert col_type[0] == "BIGINT"

        # Données préservées
        count = conn.execute("SELECT COUNT(*) FROM medals_earned").fetchone()[0]
        assert count == 1

    def test_ensure_medals_already_bigint(self, conn):
        conn.execute("""
            CREATE TABLE medals_earned (
                match_id VARCHAR,
                medal_name_id BIGINT,
                count SMALLINT,
                PRIMARY KEY (match_id, medal_name_id)
            )
        """)
        result = ensure_medals_earned_bigint(conn)
        assert result is False


# ─────────────────────────────────────────────────────────────────────────
# Backfill bitmask
# ─────────────────────────────────────────────────────────────────────────


class TestBackfillBitmask:
    def test_compute_backfill_mask_single(self):
        assert compute_backfill_mask("medals") == 1
        assert compute_backfill_mask("events") == 2
        assert compute_backfill_mask("skill") == 4

    def test_compute_backfill_mask_combined(self):
        assert compute_backfill_mask("medals", "events") == 3
        assert compute_backfill_mask("medals", "events", "skill") == 7

    def test_compute_backfill_mask_unknown_type(self):
        assert compute_backfill_mask("unknown") == 0
        assert compute_backfill_mask("medals", "unknown") == 1

    def test_compute_backfill_mask_all_flags(self):
        mask = compute_backfill_mask(*BACKFILL_FLAGS.keys())
        expected = sum(BACKFILL_FLAGS.values())
        assert mask == expected

    def test_ensure_backfill_completed_column(self, conn):
        conn.execute("CREATE TABLE match_stats (match_id VARCHAR PRIMARY KEY)")
        ensure_backfill_completed_column(conn)
        assert column_exists(conn, "match_stats", "backfill_completed") is True

    def test_ensure_backfill_completed_idempotent(self, conn):
        conn.execute("CREATE TABLE match_stats (match_id VARCHAR PRIMARY KEY)")
        ensure_backfill_completed_column(conn)
        ensure_backfill_completed_column(conn)  # 2e appel
        assert column_exists(conn, "match_stats", "backfill_completed") is True
