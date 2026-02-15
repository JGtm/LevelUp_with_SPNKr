"""Contrats data pour sessions/navigation (DuckDB)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

duckdb = pytest.importorskip("duckdb")

from src.ui.cache import cached_compute_sessions_db


@pytest.fixture
def sessions_contract_db(tmp_path):
    """Crée une base temporaire avec colonnes de sessions dans match_stats."""
    db_path = tmp_path / "sessions_contract.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                teammates_signature VARCHAR,
                session_id VARCHAR,
                session_label VARCHAR,
                is_firefight BOOLEAN
            )
            """
        )

        t0 = datetime.now(timezone.utc) - timedelta(days=3)
        rows = [
            ("m1", t0, "a;b;c", "s1", "Session 1", False),
            ("m2", t0 + timedelta(minutes=18), "a;b;c", "s1", "Session 1", False),
            ("m3", t0 + timedelta(hours=6), "a;d;e", "s2", "Session 2", False),
        ]
        conn.executemany(
            """
            INSERT INTO match_stats (
                match_id, start_time, teammates_signature, session_id, session_label, is_firefight
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    finally:
        conn.close()

    return db_path


def test_session_columns_exist_in_match_stats(sessions_contract_db) -> None:
    """Les colonnes session_id/session_label doivent exister dans match_stats."""
    conn = duckdb.connect(str(sessions_contract_db), read_only=True)
    try:
        columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='match_stats'"
            ).fetchall()
        }
        assert {"session_id", "session_label", "start_time", "match_id"}.issubset(columns)
    finally:
        conn.close()


def test_sessions_columns_are_non_empty_for_loaded_rows(sessions_contract_db) -> None:
    """Les lignes de match_stats exploitables ne doivent pas avoir de session vide."""
    conn = duckdb.connect(str(sessions_contract_db), read_only=True)
    try:
        invalid = conn.execute(
            """
            SELECT COUNT(*)
            FROM match_stats
            WHERE start_time IS NOT NULL
              AND (session_id IS NULL OR TRIM(session_id) = ''
                   OR session_label IS NULL OR TRIM(session_label) = '')
            """
        ).fetchone()[0]
        assert invalid == 0
    finally:
        conn.close()


def test_cached_compute_sessions_db_returns_expected_contract(sessions_contract_db) -> None:
    """Le calcul de sessions doit fournir les colonnes attendues et des labels cohérents."""
    result = cached_compute_sessions_db(
        db_path=str(sessions_contract_db),
        xuid="x_me",
        db_key=None,
        include_firefight=True,
        gap_minutes=120,
        friends_xuids=None,
    )

    assert not result.is_empty()
    assert ["match_id", "start_time", "session_id", "session_label"] == result.columns
    assert set(result["session_id"].cast(str).to_list()) == {"s1", "s2"}
    assert set(result["session_label"].cast(str).to_list()) == {"Session 1", "Session 2"}
