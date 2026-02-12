"""Contrats data pour assets et aliases (DuckDB)."""

from __future__ import annotations

import re

import pytest

duckdb = pytest.importorskip("duckdb")

from src.ui.aliases import load_aliases_from_db

UUID_LIKE_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


@pytest.fixture
def assets_aliases_contract_db(tmp_path):
    """Crée une base temporaire avec labels et aliases."""
    db_path = tmp_path / "assets_aliases_contract.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                map_name VARCHAR,
                playlist_name VARCHAR
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE xuid_aliases (
                xuid VARCHAR,
                gamertag VARCHAR
            )
            """
        )

        conn.execute(
            """
            INSERT INTO match_stats (match_id, map_name, playlist_name)
            VALUES
                ('m1', 'Recharge', 'Ranked Arena'),
                ('m2', 'Live Fire', 'Quick Play')
            """
        )
        conn.execute(
            """
            INSERT INTO xuid_aliases (xuid, gamertag)
            VALUES
                ('xuid_1', 'Alpha'),
                ('xuid_2', 'Bravo'),
                ('xuid_3', '')
            """
        )
    finally:
        conn.close()
    return db_path


def test_aliases_table_and_columns_exist(assets_aliases_contract_db) -> None:
    """La table xuid_aliases doit être exploitable."""
    conn = duckdb.connect(str(assets_aliases_contract_db), read_only=True)
    try:
        columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='xuid_aliases'"
            ).fetchall()
        }
        assert {"xuid", "gamertag"}.issubset(columns)
    finally:
        conn.close()


def test_load_aliases_from_db_reads_non_empty_aliases(assets_aliases_contract_db) -> None:
    """Le loader aliases doit retourner les XUID->gamertag valides."""
    aliases = load_aliases_from_db(str(assets_aliases_contract_db))
    assert aliases["xuid_1"] == "Alpha"
    assert aliases["xuid_2"] == "Bravo"
    assert "xuid_3" not in aliases


def test_match_labels_are_not_empty_or_uuid_like(assets_aliases_contract_db) -> None:
    """Les labels map/playlist doivent être lisibles (pas vides, pas UUID bruts)."""
    conn = duckdb.connect(str(assets_aliases_contract_db), read_only=True)
    try:
        rows = conn.execute("SELECT map_name, playlist_name FROM match_stats").fetchall()
    finally:
        conn.close()

    for map_name, playlist_name in rows:
        assert map_name and str(map_name).strip()
        assert playlist_name and str(playlist_name).strip()
        assert UUID_LIKE_RE.match(str(map_name)) is None
        assert UUID_LIKE_RE.match(str(playlist_name)) is None
