"""Contrats data pour les métriques de performance (DuckDB)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

duckdb = pytest.importorskip("duckdb")


@pytest.fixture
def performance_contract_db(tmp_path):
    """Crée une base temporaire avec les métriques de perf attendues."""
    db_path = tmp_path / "performance_contract.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                outcome INTEGER,
                time_played_seconds INTEGER,
                personal_score INTEGER,
                performance_score DOUBLE,
                team_mmr DOUBLE,
                enemy_mmr DOUBLE
            )
            """
        )

        start = datetime.now(timezone.utc)
        rows = [
            ("m1", start, 2, 600, 1800, 72.5, 1450.0, 1490.0),
            ("m2", start + timedelta(minutes=15), 3, 700, 1600, 61.0, 1510.0, 1505.0),
            ("m3", start + timedelta(minutes=30), 2, 540, 1900, 78.2, 1530.0, 1520.0),
        ]
        conn.executemany(
            """
            INSERT INTO match_stats
            (match_id, start_time, outcome, time_played_seconds, personal_score, performance_score, team_mmr, enemy_mmr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    finally:
        conn.close()
    return db_path


def test_performance_required_columns_exist(performance_contract_db) -> None:
    """Les colonnes de performance critiques sont présentes."""
    conn = duckdb.connect(str(performance_contract_db), read_only=True)
    try:
        cols = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='match_stats'"
            ).fetchall()
        }
        assert {
            "match_id",
            "start_time",
            "personal_score",
            "performance_score",
            "time_played_seconds",
            "team_mmr",
            "enemy_mmr",
        }.issubset(cols)
    finally:
        conn.close()


def test_performance_mandatory_values_not_null(performance_contract_db) -> None:
    """Les métriques obligatoires ne doivent pas être NULL."""
    conn = duckdb.connect(str(performance_contract_db), read_only=True)
    try:
        nulls = conn.execute(
            """
            SELECT
                SUM(CASE WHEN personal_score IS NULL THEN 1 ELSE 0 END) AS null_personal,
                SUM(CASE WHEN performance_score IS NULL THEN 1 ELSE 0 END) AS null_perf,
                SUM(CASE WHEN time_played_seconds IS NULL THEN 1 ELSE 0 END) AS null_time
            FROM match_stats
            """
        ).fetchone()
        assert nulls == (0, 0, 0)
    finally:
        conn.close()


def test_performance_metric_invariants(performance_contract_db) -> None:
    """Invariants métier de base sur les métriques de performance."""
    conn = duckdb.connect(str(performance_contract_db), read_only=True)
    try:
        invalid = conn.execute(
            """
            SELECT COUNT(*)
            FROM match_stats
            WHERE time_played_seconds <= 0
               OR personal_score < 0
               OR performance_score < 0
            """
        ).fetchone()[0]
        assert invalid == 0

        score_per_min = conn.execute(
            """
            SELECT AVG(personal_score / (time_played_seconds / 60.0))
            FROM match_stats
            WHERE time_played_seconds > 0
            """
        ).fetchone()[0]
        assert score_per_min is not None
        assert score_per_min > 0
    finally:
        conn.close()
