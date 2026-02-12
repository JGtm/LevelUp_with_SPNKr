"""Contrats data pour les participants de match (DuckDB)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

duckdb = pytest.importorskip("duckdb")


@pytest.fixture
def participants_contract_db(tmp_path):
    """Crée une base temporaire avec match_stats + match_participants."""
    db_path = tmp_path / "participants_contract.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE match_participants (
                match_id VARCHAR NOT NULL,
                xuid VARCHAR NOT NULL,
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
            "INSERT INTO match_stats (match_id, start_time) VALUES ('m1', ?), ('m2', ?)",
            [now, now],
        )
        conn.execute(
            """
            INSERT INTO match_participants (
                match_id, xuid, gamertag, rank, personal_score, kills, deaths, assists,
                shots_fired, shots_hit, damage_dealt, damage_taken
            ) VALUES
                ('m1', 'x_me', 'Me', 1, 2100, 18, 9, 6, 230, 110, 3200, 2500),
                ('m1', 'x_friend', 'Friend', 2, 1700, 12, 11, 8, 210, 90, 2800, 2900),
                ('m2', 'x_me', 'Me', 3, 1500, 10, 12, 5, 180, 70, 2400, 3000)
            """
        )
    finally:
        conn.close()
    return db_path


def test_match_participants_columns_exist(participants_contract_db) -> None:
    """Colonnes clés présentes dans match_participants."""
    conn = duckdb.connect(str(participants_contract_db), read_only=True)
    try:
        cols = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='match_participants'"
            ).fetchall()
        }
        required = {
            "match_id",
            "xuid",
            "gamertag",
            "rank",
            "personal_score",
            "kills",
            "deaths",
            "assists",
            "shots_fired",
            "shots_hit",
            "damage_dealt",
            "damage_taken",
        }
        assert required.issubset(cols)
    finally:
        conn.close()


def test_match_participants_reference_existing_matches(participants_contract_db) -> None:
    """Chaque participant doit référencer un match existant."""
    conn = duckdb.connect(str(participants_contract_db), read_only=True)
    try:
        missing = conn.execute(
            """
            SELECT COUNT(*)
            FROM match_participants p
            LEFT JOIN match_stats s ON s.match_id = p.match_id
            WHERE s.match_id IS NULL
            """
        ).fetchone()[0]
        assert missing == 0
    finally:
        conn.close()


def test_match_participants_core_invariants(participants_contract_db) -> None:
    """Invariants métier de base: identifiants et bornes numériques."""
    conn = duckdb.connect(str(participants_contract_db), read_only=True)
    try:
        invalid_identity = conn.execute(
            """
            SELECT COUNT(*)
            FROM match_participants
            WHERE xuid IS NULL OR TRIM(xuid) = '' OR gamertag IS NULL OR TRIM(gamertag) = ''
            """
        ).fetchone()[0]
        assert invalid_identity == 0

        invalid_numbers = conn.execute(
            """
            SELECT COUNT(*)
            FROM match_participants
            WHERE shots_hit > shots_fired
               OR personal_score < 0
               OR damage_dealt < 0
               OR damage_taken < 0
            """
        ).fetchone()[0]
        assert invalid_numbers == 0
    finally:
        conn.close()
