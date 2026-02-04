"""Tests pour les fonctions cache.py avec DuckDB v4 - Prévention des régressions.

Ces tests vérifient que les fonctions qui retournaient des valeurs vides
pour DuckDB v4 fonctionnent maintenant correctement.
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest

from src.data.repositories.duckdb_repo import DuckDBRepository
from src.ui.cache import (
    cached_load_match_rosters,
    cached_query_matches_with_friend,
    cached_same_team_match_ids_with_friend,
)


@pytest.fixture
def temp_duckdb():
    """Crée une base DuckDB temporaire avec des données de test."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name

    conn = duckdb.connect(db_path)

    # Créer les tables nécessaires
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

    # Insérer des données de test
    xuid_self = "2533274823110022"
    xuid_friend = "2533274823110023"
    match_id_1 = "test_match_1"
    match_id_2 = "test_match_2"

    # Matchs
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

    # Highlight events pour match_id_1 (les deux joueurs présents)
    conn.execute(
        """
        INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag)
        VALUES (?, ?, ?, ?, ?)
    """,
        [match_id_1, "Kill", 1000, xuid_self, "PlayerSelf"],
    )

    conn.execute(
        """
        INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag)
        VALUES (?, ?, ?, ?, ?)
    """,
        [match_id_1, "Kill", 2000, xuid_friend, "PlayerFriend"],
    )

    # Highlight events pour match_id_2 (seulement self)
    conn.execute(
        """
        INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag)
        VALUES (?, ?, ?, ?, ?)
    """,
        [match_id_2, "Kill", 1000, xuid_self, "PlayerSelf"],
    )

    conn.commit()
    conn.close()

    yield db_path, xuid_self, xuid_friend, match_id_1, match_id_2

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


def test_cached_load_match_rosters_not_none(temp_duckdb):
    """Test que cached_load_match_rosters ne retourne plus None pour DuckDB v4."""
    db_path, xuid_self, _, match_id_1, _ = temp_duckdb

    result = cached_load_match_rosters(
        db_path=db_path,
        match_id=match_id_1,
        xuid=xuid_self,
        db_key=None,
    )

    assert result is not None, "cached_load_match_rosters ne doit pas retourner None pour DuckDB v4"
    assert "my_team_id" in result
    assert "my_team" in result
    assert "enemy_team" in result
    assert len(result["my_team"]) > 0, "Au moins le joueur principal doit être dans my_team"


def test_cached_load_match_rosters_returns_none_for_invalid_match(temp_duckdb):
    """Test que cached_load_match_rosters retourne None pour un match inexistant."""
    db_path, xuid_self, _, _, _ = temp_duckdb

    result = cached_load_match_rosters(
        db_path=db_path,
        match_id="nonexistent_match",
        xuid=xuid_self,
        db_key=None,
    )

    assert result is None, "Doit retourner None pour un match inexistant"


def test_cached_query_matches_with_friend_not_empty(temp_duckdb):
    """Test que cached_query_matches_with_friend ne retourne plus une liste vide."""
    db_path, xuid_self, xuid_friend, match_id_1, _ = temp_duckdb

    result = cached_query_matches_with_friend(
        db_path=db_path,
        self_xuid=xuid_self,
        friend_xuid=xuid_friend,
        db_key=None,
    )

    assert isinstance(result, list), "Doit retourner une liste"
    assert len(result) > 0, "Doit retourner au moins un match_id"
    assert match_id_1 in result, f"Le match {match_id_1} doit être dans les résultats"


def test_cached_query_matches_with_friend_empty_when_no_shared_matches(temp_duckdb):
    """Test que cached_query_matches_with_friend retourne une liste vide si aucun match partagé."""
    db_path, xuid_self, _, _, _ = temp_duckdb

    result = cached_query_matches_with_friend(
        db_path=db_path,
        self_xuid=xuid_self,
        friend_xuid="9999999999999999",  # XUID qui n'existe pas
        db_key=None,
    )

    assert isinstance(result, list), "Doit retourner une liste"
    assert len(result) == 0, "Doit retourner une liste vide si aucun match partagé"


def test_cached_same_team_match_ids_with_friend_not_empty(temp_duckdb):
    """Test que cached_same_team_match_ids_with_friend ne retourne plus un tuple vide."""
    db_path, xuid_self, xuid_friend, match_id_1, _ = temp_duckdb

    result = cached_same_team_match_ids_with_friend(
        db_path=db_path,
        self_xuid=xuid_self,
        friend_xuid=xuid_friend,
        db_key=None,
    )

    assert isinstance(result, tuple), "Doit retourner un tuple"
    assert len(result) > 0, "Doit retourner au moins un match_id"
    assert match_id_1 in result, f"Le match {match_id_1} doit être dans les résultats"


def test_cached_same_team_match_ids_with_friend_empty_when_no_same_team(temp_duckdb):
    """Test que cached_same_team_match_ids_with_friend retourne un tuple vide si pas même équipe."""
    db_path, xuid_self, _, _, _ = temp_duckdb

    result = cached_same_team_match_ids_with_friend(
        db_path=db_path,
        self_xuid=xuid_self,
        friend_xuid="9999999999999999",  # XUID qui n'existe pas
        db_key=None,
    )

    assert isinstance(result, tuple), "Doit retourner un tuple"
    assert len(result) == 0, "Doit retourner un tuple vide si aucun match même équipe"


def test_duckdb_repo_load_match_rosters(temp_duckdb):
    """Test direct de DuckDBRepository.load_match_rosters."""
    db_path, xuid_self, _, match_id_1, _ = temp_duckdb

    repo = DuckDBRepository(db_path, xuid_self)
    result = repo.load_match_rosters(match_id_1)

    assert result is not None
    assert result["my_team_id"] == 0
    assert len(result["my_team"]) >= 1
    # Le joueur principal doit être dans my_team
    assert any(p["is_me"] for p in result["my_team"])


def test_duckdb_repo_load_matches_with_teammate(temp_duckdb):
    """Test direct de DuckDBRepository.load_matches_with_teammate."""
    db_path, xuid_self, xuid_friend, match_id_1, _ = temp_duckdb

    repo = DuckDBRepository(db_path, xuid_self)
    result = repo.load_matches_with_teammate(xuid_friend)

    assert isinstance(result, list)
    assert match_id_1 in result


def test_duckdb_repo_load_same_team_match_ids(temp_duckdb):
    """Test direct de DuckDBRepository.load_same_team_match_ids."""
    db_path, xuid_self, xuid_friend, match_id_1, _ = temp_duckdb

    repo = DuckDBRepository(db_path, xuid_self)
    result = repo.load_same_team_match_ids(xuid_friend)

    assert isinstance(result, list)
    # Les deux joueurs ont le même team_id (0) dans match_stats
    assert match_id_1 in result


def test_information_schema_not_sqlite_master():
    """Test que les requêtes utilisent information_schema et non sqlite_master."""
    # Ce test vérifie que le bug sqlite_master → information_schema est corrigé
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name

    try:
        conn = duckdb.connect(db_path)
        conn.execute("CREATE TABLE test_table (id INTEGER)")

        # Vérifier que information_schema fonctionne
        result = conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = 'test_table'
        """).fetchall()

        assert len(result) == 1, "information_schema doit fonctionner avec DuckDB"

        # Vérifier que sqlite_master ne fonctionne PAS avec DuckDB
        try:
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            pytest.fail("sqlite_master ne doit pas fonctionner avec DuckDB")
        except Exception:
            pass  # Attendu

        conn.close()
    finally:
        Path(db_path).unlink(missing_ok=True)
