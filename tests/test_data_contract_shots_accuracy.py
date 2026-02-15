"""Contrats data pour les statistiques tirs et précision (DuckDB)."""

from __future__ import annotations

import pytest

duckdb = pytest.importorskip("duckdb")


@pytest.fixture
def shots_contract_db(tmp_path):
    """Crée une base temporaire contenant shots_fired/shots_hit/accuracy."""
    db_path = tmp_path / "shots_contract.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                shots_fired INTEGER,
                shots_hit INTEGER,
                accuracy DOUBLE
            )
            """
        )

        conn.execute(
            """
            INSERT INTO match_stats (match_id, shots_fired, shots_hit, accuracy)
            VALUES
                ('m1', 120, 54, 45.0),
                ('m2', 250, 100, 40.0),
                ('m3', 80, 28, 35.0)
            """
        )
    finally:
        conn.close()
    return db_path


def test_shots_columns_exist(shots_contract_db) -> None:
    """Colonnes attendues présentes dans match_stats."""
    conn = duckdb.connect(str(shots_contract_db), read_only=True)
    try:
        cols = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='match_stats'"
            ).fetchall()
        }
        assert {"shots_fired", "shots_hit", "accuracy"}.issubset(cols)
    finally:
        conn.close()


def test_shots_hit_never_exceeds_shots_fired(shots_contract_db) -> None:
    """Invariant: shots_hit <= shots_fired."""
    conn = duckdb.connect(str(shots_contract_db), read_only=True)
    try:
        invalid = conn.execute(
            "SELECT COUNT(*) FROM match_stats WHERE shots_hit > shots_fired"
        ).fetchone()[0]
        assert invalid == 0
    finally:
        conn.close()


def test_accuracy_is_between_0_and_100(shots_contract_db) -> None:
    """Invariant: accuracy dans [0, 100]."""
    conn = duckdb.connect(str(shots_contract_db), read_only=True)
    try:
        invalid = conn.execute(
            "SELECT COUNT(*) FROM match_stats WHERE accuracy < 0 OR accuracy > 100"
        ).fetchone()[0]
        assert invalid == 0
    finally:
        conn.close()
