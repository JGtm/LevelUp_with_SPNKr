"""Tests pour DuckDBRepository - Prévention des régressions.

Tests spécifiques pour les nouvelles méthodes ajoutées pour corriger les régressions.
"""

from datetime import datetime, timezone

import duckdb
import pytest

from src.data.repositories.duckdb_repo import DuckDBRepository


@pytest.fixture
def repo_with_data(tmp_path):
    """Crée un repository DuckDB avec des données de test."""
    db_path = tmp_path / "test_repo.duckdb"
    conn = duckdb.connect(str(db_path))

    # Créer les tables
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP,
            team_id INTEGER,
            accuracy DOUBLE,
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE highlight_events (
            id INTEGER PRIMARY KEY,
            match_id VARCHAR,
            event_type VARCHAR,
            time_ms INTEGER,
            xuid VARCHAR,
            gamertag VARCHAR,
            type_hint INTEGER,
            raw_json VARCHAR
        )
    """)

    xuid_self = "2533274823110022"
    xuid_friend = "2533274823110023"
    xuid_enemy = "2533274823110024"
    match_id_1 = "match_1"
    match_id_2 = "match_2"
    match_id_3 = "match_3"

    # Matchs avec différents team_id
    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, team_id, accuracy, kills, deaths, assists)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        [match_id_1, datetime.now(timezone.utc), 0, 45.5, 10, 5, 3],
    )

    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, team_id, accuracy, kills, deaths, assists)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        [match_id_2, datetime.now(timezone.utc), 0, 50.0, 15, 4, 5],
    )

    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, team_id, accuracy, kills, deaths, assists)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        [match_id_3, datetime.now(timezone.utc), 1, 55.0, 20, 3, 7],
    )

    # Highlight events pour match_id_1 (self + friend dans même équipe)
    for idx, (mid, evt, tm, uid, gt) in enumerate(
        [
            (match_id_1, "Kill", 1000, xuid_self, "PlayerSelf"),
            (match_id_1, "Kill", 2000, xuid_friend, "PlayerFriend"),
            (match_id_2, "Kill", 1000, xuid_self, "PlayerSelf"),
            (match_id_2, "Kill", 2000, xuid_friend, "PlayerFriend"),
            (match_id_3, "Kill", 1000, xuid_self, "PlayerSelf"),
        ],
        start=1,
    ):
        conn.execute(
            """
            INSERT INTO highlight_events (id, match_id, event_type, time_ms, xuid, gamertag)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            [idx, mid, evt, tm, uid, gt],
        )

    conn.commit()
    conn.close()

    repo = DuckDBRepository(str(db_path), xuid_self)

    yield repo, xuid_self, xuid_friend, xuid_enemy, match_id_1, match_id_2, match_id_3


def test_load_match_rosters_basic(repo_with_data):
    """Test basique de load_match_rosters."""
    repo, xuid_self, _, _, match_id_1, _, _ = repo_with_data

    result = repo.load_match_rosters(match_id_1)

    assert result is not None
    assert "my_team_id" in result
    assert "my_team" in result
    assert "enemy_team" in result
    assert result["my_team_id"] == 0


def test_load_match_rosters_includes_self(repo_with_data):
    """Test que load_match_rosters inclut le joueur principal dans my_team."""
    repo, xuid_self, _, _, match_id_1, _, _ = repo_with_data

    result = repo.load_match_rosters(match_id_1)

    assert result is not None
    my_team = result["my_team"]
    assert len(my_team) > 0
    assert any(p["xuid"] == xuid_self and p["is_me"] for p in my_team)


def test_load_match_rosters_nonexistent_match(repo_with_data):
    """Test que load_match_rosters retourne None pour un match inexistant."""
    repo, _, _, _, _, _, _ = repo_with_data

    result = repo.load_match_rosters("nonexistent")

    assert result is None


def test_load_match_rosters_no_highlight_events(tmp_path):
    """Test que load_match_rosters retourne None si pas de highlight_events."""
    db_path = tmp_path / "test_no_events.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            team_id INTEGER
        )
    """)
    conn.execute("""
        INSERT INTO match_stats (match_id, team_id) VALUES ('match_1', 0)
    """)
    conn.commit()
    conn.close()

    repo = DuckDBRepository(str(db_path), "2533274823110022")
    result = repo.load_match_rosters("match_1")

    assert result is None, "Doit retourner None si pas de highlight_events"


def test_load_matches_with_teammate_basic(repo_with_data):
    """Test basique de load_matches_with_teammate."""
    repo, _, xuid_friend, _, match_id_1, match_id_2, _ = repo_with_data

    result = repo.load_matches_with_teammate(xuid_friend)

    assert isinstance(result, list)
    assert match_id_1 in result
    assert match_id_2 in result
    assert len(result) >= 2


def test_load_matches_with_teammate_no_shared_matches(repo_with_data):
    """Test que load_matches_with_teammate retourne liste vide si aucun match partagé."""
    repo, _, _, xuid_enemy, _, _, _ = repo_with_data

    result = repo.load_matches_with_teammate(xuid_enemy)

    assert isinstance(result, list)
    assert len(result) == 0


def test_load_same_team_match_ids_basic(repo_with_data):
    """Test basique de load_same_team_match_ids."""
    repo, _, xuid_friend, _, match_id_1, match_id_2, match_id_3 = repo_with_data

    result = repo.load_same_team_match_ids(xuid_friend)

    assert isinstance(result, list)
    assert match_id_1 in result, "match_id_1 doit être dans les résultats (même équipe)"
    assert match_id_2 in result, "match_id_2 doit être dans les résultats (même équipe)"
    assert (
        match_id_3 not in result
    ), "match_id_3 ne doit PAS être dans les résultats (équipe différente)"


def test_load_same_team_match_ids_no_same_team(repo_with_data):
    """Test que load_same_team_match_ids retourne liste vide si pas même équipe."""
    repo, _, _, xuid_enemy, _, _, _ = repo_with_data

    result = repo.load_same_team_match_ids(xuid_enemy)

    assert isinstance(result, list)
    assert len(result) == 0


def test_load_first_event_times_uses_information_schema(tmp_path):
    """Test que load_first_event_times utilise information_schema et non sqlite_master."""
    db_path = tmp_path / "test_info_schema.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE highlight_events (
            id INTEGER PRIMARY KEY,
            match_id VARCHAR,
            event_type VARCHAR,
            time_ms INTEGER,
            xuid VARCHAR
        )
    """)
    conn.execute("""
        INSERT INTO highlight_events (id, match_id, event_type, time_ms, xuid)
        VALUES (1, 'match_1', 'Kill', 1000, '2533274823110022')
    """)
    conn.commit()
    conn.close()

    repo = DuckDBRepository(str(db_path), "2533274823110022")
    result = repo.load_first_event_times(["match_1"], "Kill")

    # Si la méthode utilise sqlite_master, elle échouera avec DuckDB
    # Si elle utilise information_schema, elle fonctionnera
    assert isinstance(result, dict)
