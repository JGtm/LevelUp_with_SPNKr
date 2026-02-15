"""INT-003: intégration participants partiels (graceful degradation)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

duckdb = pytest.importorskip("duckdb")


@pytest.fixture
def participants_partial_db(tmp_path):
    """Crée une DB temporaire avec match_participants partiellement renseignée."""
    db_path = tmp_path / "participants_partial.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE match_participants (
                match_id VARCHAR,
                xuid VARCHAR,
                gamertag VARCHAR,
                team_id INTEGER,
                score INTEGER,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER
            )
            """
        )

        conn.execute(
            """
            INSERT INTO match_participants (match_id, xuid, gamertag, team_id, score, kills, deaths, assists)
            VALUES
                ('m1', 'x_me', 'Me', 1, 1900, 12, 8, 6),
                ('m1', 'x_friend', 'Friend', 1, 1700, 10, 9, 7),
                ('m1', 'x_opp', 'Enemy', 2, NULL, NULL, NULL, NULL)
            """
        )

        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO match_stats (match_id, start_time) VALUES ('m1', ?)",
            [datetime.now(timezone.utc)],
        )
    finally:
        conn.close()

    return db_path


def test_partial_participants_are_handled_without_crash(participants_partial_db) -> None:
    """load_match_players_stats doit tolérer l'absence de colonnes rank/score et NULL KDA."""
    from src.data.repositories.duckdb_repo import DuckDBRepository

    repo = DuckDBRepository(str(participants_partial_db), xuid="x_me", read_only=True)
    try:
        rows = repo.load_match_players_stats("m1")

        assert len(rows) == 3
        assert all("xuid" in row and "gamertag" in row for row in rows)

        # Colonnes manquantes => fallback propre (rank indexé, score None)
        assert all("rank" in row for row in rows)
        assert all("score" in row for row in rows)

        # KDA partiel => valeurs nulles transformées sans crash
        enemy = next(row for row in rows if row["xuid"] == "x_opp")
        assert enemy["kills"] == 0
        assert enemy["deaths"] == 0
        assert enemy["assists"] == 0
    finally:
        repo.close()
