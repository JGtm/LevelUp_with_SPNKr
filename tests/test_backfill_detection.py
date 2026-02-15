"""Tests pour scripts/backfill/detection.py — détection des matchs avec données manquantes.

Teste find_matches_missing_data avec différents flags sur une DB DuckDB :memory:.
"""

from __future__ import annotations

import duckdb
import pytest

from scripts.backfill.detection import (
    _done_guard,
    _has_backfill_completed_column,
    find_matches_missing_data,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
def conn():
    """Crée une connexion DuckDB :memory: avec les tables nécessaires."""
    c = duckdb.connect(":memory:")
    # Table match_stats avec backfill_completed
    c.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            accuracy DOUBLE,
            shots_fired INTEGER,
            shots_hit INTEGER,
            performance_score DOUBLE,
            playlist_name VARCHAR,
            playlist_id VARCHAR,
            map_name VARCHAR,
            map_id VARCHAR,
            pair_name VARCHAR,
            pair_id VARCHAR,
            game_variant_name VARCHAR,
            game_variant_id VARCHAR,
            backfill_completed INTEGER DEFAULT 0
        )
    """)
    # Tables annexes
    c.execute("""
        CREATE TABLE medals_earned (
            match_id VARCHAR,
            medal_name_id VARCHAR,
            count INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE highlight_events (
            match_id VARCHAR,
            event_type VARCHAR,
            time_ms INTEGER,
            xuid VARCHAR,
            gamertag VARCHAR
        )
    """)
    c.execute("""
        CREATE TABLE player_match_stats (
            match_id VARCHAR,
            xuid VARCHAR,
            enemy_mmr DOUBLE
        )
    """)
    c.execute("""
        CREATE TABLE personal_score_awards (
            match_id VARCHAR,
            xuid VARCHAR,
            award_name VARCHAR
        )
    """)
    c.execute("""
        CREATE TABLE match_participants (
            match_id VARCHAR,
            xuid VARCHAR,
            rank INTEGER,
            score INTEGER,
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER,
            shots_fired INTEGER,
            shots_hit INTEGER,
            damage_dealt DOUBLE,
            damage_taken DOUBLE
        )
    """)
    # Insert test matches
    c.execute("""
        INSERT INTO match_stats (match_id, accuracy, shots_fired, shots_hit, performance_score,
            playlist_name, playlist_id, map_name, map_id, pair_name, pair_id, game_variant_name, game_variant_id)
        VALUES
            ('m1', NULL, NULL, NULL, NULL, NULL, 'p1', NULL, 'map1', NULL, 'pair1', NULL, 'gv1'),
            ('m2', 0.5, 100, 50, 80.0, 'Ranked', 'p2', 'Recharge', 'map2', 'Slayer', 'pair2', 'Slayer', 'gv2'),
            ('m3', NULL, NULL, NULL, NULL, NULL, 'p3', NULL, 'map3', NULL, 'pair3', NULL, 'gv3')
    """)
    # m2 has medals, events, skill, scores
    c.execute("INSERT INTO medals_earned VALUES ('m2', 'double_kill', 1)")
    c.execute("INSERT INTO highlight_events VALUES ('m2', 'Kill', 0, '1234567890123456', 'GT')")
    c.execute("INSERT INTO player_match_stats VALUES ('m2', '1234567890123456', 1500.0)")
    c.execute("INSERT INTO personal_score_awards VALUES ('m2', '1234567890123456', 'award1')")
    c.execute(
        "INSERT INTO match_participants VALUES ('m2', '1234567890123456', 1, 100, 10, 5, 3, 50, 25, 1000.0, 800.0)"
    )
    yield c
    c.close()


@pytest.fixture
def conn_no_bf_col():
    """Connexion DuckDB :memory: SANS colonne backfill_completed."""
    c = duckdb.connect(":memory:")
    c.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            accuracy DOUBLE
        )
    """)
    c.execute("INSERT INTO match_stats (match_id) VALUES ('m1')")
    c.execute("CREATE TABLE medals_earned (match_id VARCHAR, medal_name_id VARCHAR, count INTEGER)")
    yield c
    c.close()


# ── Tests _has_backfill_completed_column ─────────────────────────────────────


class TestHasBackfillCompletedColumn:
    def test_with_column(self, conn):
        assert _has_backfill_completed_column(conn) is True

    def test_without_column(self, conn_no_bf_col):
        assert _has_backfill_completed_column(conn_no_bf_col) is False


# ── Tests _done_guard ────────────────────────────────────────────────────────


class TestDoneGuard:
    def test_returns_empty_when_no_column(self):
        result = _done_guard("medals", False)
        assert result == ""

    def test_returns_clause_when_column_exists(self):
        result = _done_guard("medals", True)
        assert "backfill_completed" in result
        assert "& " in result
        assert "= 0" in result

    def test_unknown_flag_returns_empty(self):
        result = _done_guard("unknown_flag_xyz", True)
        assert result == ""


# ── Tests find_matches_missing_data — medals ─────────────────────────────────


class TestFindMatchesMissingMedals:
    def test_finds_matches_without_medals(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", medals=True)
        # m1 and m3 have no medals
        assert "m1" in result
        assert "m3" in result
        assert "m2" not in result

    def test_force_medals_includes_all(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", medals=True, force_medals=True)
        # force includes m1, m3 which have no medals
        assert "m1" in result
        assert "m3" in result

    def test_no_flags_returns_empty(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456")
        assert result == []


# ── Tests find_matches_missing_data — events ─────────────────────────────────


class TestFindMatchesMissingEvents:
    def test_finds_matches_without_events(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", events=True)
        assert "m1" in result
        assert "m3" in result
        assert "m2" not in result


# ── Tests find_matches_missing_data — skill ──────────────────────────────────


class TestFindMatchesMissingSkill:
    def test_finds_matches_without_skill(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", skill=True)
        assert "m1" in result
        assert "m3" in result
        assert "m2" not in result


# ── Tests find_matches_missing_data — accuracy ──────────────────────────────


class TestFindMatchesMissingAccuracy:
    def test_finds_matches_with_null_accuracy(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", accuracy=True)
        assert "m1" in result
        assert "m3" in result
        assert "m2" not in result

    def test_force_accuracy_includes_all(self, conn):
        result = find_matches_missing_data(
            conn, "1234567890123456", accuracy=True, force_accuracy=True
        )
        # force = 1=1 → tous les matchs
        assert len(result) == 3


# ── Tests find_matches_missing_data — shots ──────────────────────────────────


class TestFindMatchesMissingShots:
    def test_finds_matches_with_null_shots(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", shots=True)
        assert "m1" in result
        assert "m3" in result
        assert "m2" not in result

    def test_force_shots_includes_all(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", shots=True, force_shots=True)
        assert len(result) == 3


# ── Tests find_matches_missing_data — personal_scores ────────────────────────


class TestFindMatchesMissingPersonalScores:
    def test_finds_matches_without_scores(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", personal_scores=True)
        assert "m1" in result
        assert "m3" in result
        assert "m2" not in result


# ── Tests find_matches_missing_data — performance_scores ─────────────────────


class TestFindMatchesMissingPerformance:
    def test_finds_matches_with_null_performance(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", performance_scores=True)
        assert "m1" in result
        assert "m3" in result
        assert "m2" not in result


# ── Tests find_matches_missing_data — enemy_mmr ─────────────────────────────


class TestFindMatchesMissingEnemyMmr:
    def test_finds_matches_with_null_enemy_mmr(self, conn):
        # m1, m3 have no player_match_stats at all, m2 has non-null enemy_mmr
        # enemy_mmr flag checks WHERE enemy_mmr IS NULL in player_match_stats
        # m1, m3 won't be IN that subquery since they have no rows at all
        result = find_matches_missing_data(conn, "1234567890123456", enemy_mmr=True)
        # The subquery finds match_ids IN player_match_stats WHERE enemy_mmr IS NULL
        # m1, m3 have no rows in player_match_stats, so they won't appear
        # m2 has enemy_mmr = 1500 (not null), so it won't appear
        assert "m2" not in result

    def test_force_enemy_mmr(self, conn):
        result = find_matches_missing_data(
            conn, "1234567890123456", enemy_mmr=True, force_enemy_mmr=True
        )
        # force_enemy_mmr uses the base condition, not 1=1
        # Still checks player_match_stats WHERE enemy_mmr IS NULL
        assert "m2" not in result


# ── Tests find_matches_missing_data — assets ─────────────────────────────────


class TestFindMatchesMissingAssets:
    def test_finds_matches_with_null_asset_names(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", assets=True)
        # m1 and m3 have NULL names with non-null IDs
        assert "m1" in result
        assert "m3" in result
        # m2 has all names filled
        assert "m2" not in result

    def test_force_assets(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", assets=True, force_assets=True)
        assert "m1" in result
        assert "m3" in result


# ── Tests find_matches_missing_data — participants ───────────────────────────


class TestFindMatchesMissingParticipants:
    def test_finds_matches_without_participants(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", participants=True)
        # m1, m3 have no participants
        assert "m1" in result
        assert "m3" in result
        assert "m2" not in result

    def test_force_participants(self, conn):
        result = find_matches_missing_data(
            conn, "1234567890123456", participants=True, force_participants=True
        )
        assert len(result) == 3


# ── Tests find_matches_missing_data — detection_mode ─────────────────────────


class TestDetectionMode:
    def test_or_mode_default(self, conn):
        result = find_matches_missing_data(
            conn, "1234567890123456", medals=True, accuracy=True, detection_mode="or"
        )
        # OR: matches missing medals OR accuracy
        assert "m1" in result
        assert "m3" in result

    def test_and_mode(self, conn):
        result = find_matches_missing_data(
            conn, "1234567890123456", medals=True, accuracy=True, detection_mode="and"
        )
        # AND: matches missing medals AND accuracy
        assert "m1" in result
        assert "m3" in result
        # m2 has both medals and accuracy → excluded in AND mode too
        assert "m2" not in result


# ── Tests find_matches_missing_data — max_matches ────────────────────────────


class TestMaxMatches:
    def test_limits_results(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", medals=True, max_matches=1)
        assert len(result) == 1


# ── Tests find_matches_missing_data — force_aliases ──────────────────────────


class TestForceAliases:
    def test_force_aliases_returns_all(self, conn):
        result = find_matches_missing_data(conn, "1234567890123456", force_aliases=True)
        assert len(result) == 3


# ── Tests backfill_completed bitmask filtering ───────────────────────────────


class TestBitmaskFiltering:
    def test_already_backfilled_excluded(self, conn):
        """Les matchs avec le bit medals activé ne sont pas re-détectés."""
        from src.data.sync.migrations import BACKFILL_FLAGS

        medal_bit = BACKFILL_FLAGS.get("medals", 0)
        if medal_bit:
            conn.execute(
                "UPDATE match_stats SET backfill_completed = ? WHERE match_id = 'm1'",
                [medal_bit],
            )
            result = find_matches_missing_data(conn, "1234567890123456", medals=True)
            # m1 should be excluded now
            assert "m1" not in result
            # m3 still missing
            assert "m3" in result


# ── Tests sans colonne backfill_completed ────────────────────────────────────


class TestWithoutBackfillColumn:
    def test_medals_works_without_bf_column(self, conn_no_bf_col):
        result = find_matches_missing_data(conn_no_bf_col, "1234567890123456", medals=True)
        # m1 has no medals
        assert "m1" in result


# ── Tests participants column conditions ─────────────────────────────────────


class TestParticipantsColumnConditions:
    def test_participants_kda(self, conn):
        # Add a participant with NULL kills for m3
        conn.execute(
            "INSERT INTO match_participants (match_id, xuid, kills) VALUES ('m3', 'x', NULL)"
        )
        result = find_matches_missing_data(conn, "1234567890123456", participants_kda=True)
        assert "m3" in result

    def test_participants_shots(self, conn):
        conn.execute(
            "INSERT INTO match_participants (match_id, xuid, shots_fired) VALUES ('m3', 'x', NULL)"
        )
        result = find_matches_missing_data(conn, "1234567890123456", participants_shots=True)
        assert "m3" in result

    def test_force_participants_shots(self, conn):
        result = find_matches_missing_data(
            conn, "1234567890123456", participants_shots=True, force_participants_shots=True
        )
        # force = 1=1 → all matches
        assert len(result) == 3

    def test_participants_damage(self, conn):
        conn.execute(
            "INSERT INTO match_participants (match_id, xuid, damage_dealt) VALUES ('m3', 'x', NULL)"
        )
        result = find_matches_missing_data(conn, "1234567890123456", participants_damage=True)
        assert "m3" in result

    def test_force_participants_damage(self, conn):
        result = find_matches_missing_data(
            conn, "1234567890123456", participants_damage=True, force_participants_damage=True
        )
        assert len(result) == 3

    def test_participants_scores(self, conn):
        conn.execute(
            "INSERT INTO match_participants (match_id, xuid, rank) VALUES ('m3', 'x', NULL)"
        )
        result = find_matches_missing_data(conn, "1234567890123456", participants_scores=True)
        assert "m3" in result
