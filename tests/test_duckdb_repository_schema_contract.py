"""Contrat de schéma DuckDB pour les méthodes clés du repository.

Objectif: détecter tôt un drift de schéma (table/colonne critique manquante)
avec des messages explicites.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

duckdb = pytest.importorskip("duckdb")


def _assert_has_columns(conn, table_name: str, required_columns: set[str]) -> None:
    """Assert utilitaire de présence de colonnes avec message explicite."""
    columns = {
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            [table_name],
        ).fetchall()
    }
    missing = sorted(required_columns - columns)
    assert not missing, f"Schema drift détecté sur {table_name}: colonnes manquantes={missing}"


@pytest.fixture
def temp_repo_contract_db(tmp_path):
    """DB temporaire avec schéma minimum attendu par le repository."""
    db_path = tmp_path / "repo_schema_contract.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                map_id VARCHAR,
                map_name VARCHAR,
                playlist_id VARCHAR,
                playlist_name VARCHAR,
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
                time_played_seconds INTEGER,
                avg_life_seconds DOUBLE,
                my_team_score INTEGER,
                enemy_team_score INTEGER,
                team_mmr DOUBLE,
                enemy_mmr DOUBLE,
                personal_score INTEGER,
                is_firefight BOOLEAN DEFAULT FALSE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE medals_earned (
                match_id VARCHAR,
                medal_name_id INTEGER,
                count INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE highlight_events (
                match_id VARCHAR,
                event_type VARCHAR,
                time_ms INTEGER,
                xuid VARCHAR,
                gamertag VARCHAR,
                type_hint INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE match_participants (
                match_id VARCHAR,
                xuid VARCHAR,
                gamertag VARCHAR,
                rank INTEGER,
                personal_score INTEGER,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                shots_fired INTEGER,
                shots_hit INTEGER,
                damage_dealt INTEGER,
                damage_taken INTEGER
            )
            """
        )

        now = datetime.now(timezone.utc)
        conn.execute(
            """
            INSERT INTO match_stats (
                match_id, start_time, map_id, map_name, playlist_id, playlist_name,
                pair_id, pair_name, game_variant_id, game_variant_name, outcome, team_id,
                kills, deaths, assists, kda, accuracy, headshot_kills, max_killing_spree,
                time_played_seconds, avg_life_seconds, my_team_score, enemy_team_score,
                team_mmr, enemy_mmr, personal_score, is_firefight
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "m1",
                now,
                "map1",
                "Recharge",
                "pl1",
                "Ranked",
                "pair1",
                "Slayer",
                "gv1",
                "Slayer",
                2,
                1,
                12,
                8,
                5,
                1.5,
                48.0,
                4,
                3,
                650,
                40.0,
                50,
                43,
                1500.0,
                1480.0,
                1700,
                False,
            ],
        )
        conn.execute(
            "INSERT INTO medals_earned (match_id, medal_name_id, count) VALUES ('m1', 1512363953, 1)"
        )
        conn.execute(
            """
            INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag, type_hint)
            VALUES ('m1', 'Kill', 1000, 'x_me', 'Me', 50)
            """
        )
    finally:
        conn.close()

    return db_path


def test_repository_critical_schema_contract(temp_repo_contract_db) -> None:
    """Le schéma critique attendu doit être présent (détection de drift)."""
    conn = duckdb.connect(str(temp_repo_contract_db), read_only=True)
    try:
        _assert_has_columns(
            conn,
            "match_stats",
            {
                "match_id",
                "start_time",
                "outcome",
                "kills",
                "deaths",
                "assists",
                "kda",
                "accuracy",
                "time_played_seconds",
                "team_mmr",
                "enemy_mmr",
            },
        )
        _assert_has_columns(conn, "medals_earned", {"match_id", "medal_name_id", "count"})
        _assert_has_columns(
            conn,
            "highlight_events",
            {"match_id", "event_type", "time_ms", "xuid", "gamertag"},
        )
        _assert_has_columns(
            conn,
            "match_participants",
            {
                "match_id",
                "xuid",
                "gamertag",
                "rank",
                "personal_score",
                "shots_fired",
                "shots_hit",
                "damage_dealt",
                "damage_taken",
            },
        )
    finally:
        conn.close()


def test_repository_methods_still_work_with_expected_schema(temp_repo_contract_db) -> None:
    """Les méthodes repository clés restent fonctionnelles sur le schéma contractuel."""
    from src.data.repositories.duckdb_repo import DuckDBRepository

    repo = DuckDBRepository(str(temp_repo_contract_db), xuid="x_me", read_only=True)
    try:
        matches = repo.load_matches()
        assert len(matches) == 1
        assert matches[0].match_id == "m1"

        medals = repo.load_top_medals(["m1"], top_n=5)
        assert medals

        events = repo.load_highlight_events("m1")
        assert events and events[0]["event_type"].lower() == "kill"

        stats_df = repo.load_match_stats_as_polars()
        assert not stats_df.is_empty()
    finally:
        repo.close()


# =============================================================================
# Sprint 15 : Tests CAST_PLAN vs schéma contractuel
# =============================================================================


def test_cast_plan_covers_all_contract_tables() -> None:
    """Le CAST_PLAN couvre les tables du contrat de schéma."""
    from src.data.sync.batch_insert import CAST_PLAN

    contract_tables = ["match_stats", "medals_earned", "highlight_events", "match_participants"]
    for table in contract_tables:
        assert table in CAST_PLAN, f"Table contractuelle {table} absente du CAST_PLAN"


def test_cast_plan_match_stats_columns_match_contract(temp_repo_contract_db) -> None:
    """Les colonnes du CAST_PLAN pour match_stats incluent celles du contrat."""
    from src.data.sync.batch_insert import CAST_PLAN

    plan_cols = set(CAST_PLAN["match_stats"].keys())
    # Colonnes minimales du contrat
    contract_cols = {
        "match_id",
        "start_time",
        "outcome",
        "kills",
        "deaths",
        "assists",
        "kda",
        "accuracy",
        "time_played_seconds",
        "team_mmr",
        "enemy_mmr",
    }
    missing = contract_cols - plan_cols
    assert not missing, f"Colonnes contractuelles manquantes dans CAST_PLAN: {missing}"


def test_audit_types_on_contract_db(temp_repo_contract_db) -> None:
    """L'audit de types ne détecte pas de TYPE_MISMATCH sur le schéma contractuel."""
    from src.data.sync.batch_insert import audit_column_types

    conn = duckdb.connect(str(temp_repo_contract_db), read_only=True)
    try:
        issues = audit_column_types(conn, "match_stats")
        type_mismatches = [i for i in issues if i["status"] == "TYPE_MISMATCH"]
        # Les types du schéma contractuel doivent être compatibles
        # (INTEGER est plus large que SMALLINT → acceptable)
        assert not type_mismatches, f"TYPE_MISMATCH inattendus: {type_mismatches}"
    finally:
        conn.close()


def test_batch_insert_compatible_with_contract_schema(temp_repo_contract_db) -> None:
    """Les insertions batch fonctionnent sur le schéma contractuel."""
    from src.data.sync.batch_insert import MEDAL_COLUMNS, batch_insert_rows
    from src.data.sync.models import MedalEarnedRow

    conn = duckdb.connect(str(temp_repo_contract_db))
    try:
        rows = [
            MedalEarnedRow(match_id="m2", medal_name_id=9999, count=3),
        ]
        inserted = batch_insert_rows(conn, "medals_earned", rows, MEDAL_COLUMNS)
        assert inserted == 1

        result = conn.execute("SELECT count FROM medals_earned WHERE match_id = 'm2'").fetchone()
        assert result[0] == 3
    finally:
        conn.close()
