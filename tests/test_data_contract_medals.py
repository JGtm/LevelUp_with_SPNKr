"""Contrats data pour les médailles (DuckDB).

Vérifie:
- présence des tables et colonnes critiques,
- cohérence des clés match_id,
- invariants de base sur les counts.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

duckdb = pytest.importorskip("duckdb")


@pytest.fixture
def medals_contract_db(tmp_path):
    """Crée une base DuckDB temporaire avec un jeu de données médailles valide."""
    db_path = tmp_path / "medals_contract.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                outcome INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE medals_earned (
                match_id VARCHAR NOT NULL,
                medal_name_id INTEGER NOT NULL,
                count INTEGER NOT NULL
            )
            """
        )

        now = datetime.now(timezone.utc)
        conn.execute(
            "INSERT INTO match_stats (match_id, start_time, outcome) VALUES (?, ?, ?), (?, ?, ?)",
            ["m1", now, 2, "m2", now, 3],
        )
        conn.execute(
            """
            INSERT INTO medals_earned (match_id, medal_name_id, count)
            VALUES
                ('m1', 1512363953, 2),
                ('m1', 1512363954, 1),
                ('m2', 1512363953, 1)
            """
        )
    finally:
        conn.close()
    return db_path


def test_medals_tables_and_columns_exist(medals_contract_db) -> None:
    """Les tables et colonnes critiques doivent exister."""
    conn = duckdb.connect(str(medals_contract_db), read_only=True)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        assert "match_stats" in tables
        assert "medals_earned" in tables

        medal_columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='medals_earned'"
            ).fetchall()
        }
        assert {"match_id", "medal_name_id", "count"}.issubset(medal_columns)
    finally:
        conn.close()


def test_medals_match_ids_reference_existing_matches(medals_contract_db) -> None:
    """Chaque ligne de medals_earned doit pointer vers un match existant."""
    conn = duckdb.connect(str(medals_contract_db), read_only=True)
    try:
        missing = conn.execute(
            """
            SELECT COUNT(*)
            FROM medals_earned m
            LEFT JOIN match_stats s ON s.match_id = m.match_id
            WHERE s.match_id IS NULL
            """
        ).fetchone()[0]
        assert missing == 0
    finally:
        conn.close()


def test_medals_counts_are_positive(medals_contract_db) -> None:
    """Les médailles doivent avoir un count strictement positif."""
    conn = duckdb.connect(str(medals_contract_db), read_only=True)
    try:
        invalid = conn.execute("SELECT COUNT(*) FROM medals_earned WHERE count <= 0").fetchone()[0]
        assert invalid == 0
    finally:
        conn.close()
