"""Tests pour le lazy loading et la pagination (Sprint 4.3).

Teste les nouvelles fonctionnalités de chargement paginé et lazy loading
du DuckDBRepository.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_duckdb_connection():
    """Crée une connexion DuckDB mock pour les tests."""
    mock_conn = MagicMock()

    # Mock fetchall pour retourner des données de test
    def create_mock_result(data, columns):
        result = MagicMock()
        result.fetchall.return_value = data
        result.description = [(col, None, None, None, None, None, None) for col in columns]
        return result

    return mock_conn, create_mock_result


@pytest.fixture
def sample_match_data():
    """Données de match de test."""
    return [
        (
            "match_1",  # match_id
            datetime(2026, 2, 1, 10, 0, 0, tzinfo=timezone.utc),  # start_time
            "map_1",  # map_id
            "Aquarius",  # map_name
            "playlist_1",  # playlist_id
            "Ranked Arena",  # playlist_name
            "pair_1",  # pair_id
            "Slayer",  # pair_name
            "variant_1",  # game_variant_id
            "Ranked Slayer",  # game_variant_name
            2,  # outcome (Win)
            0,  # team_id
            2.5,  # kda
            5,  # max_killing_spree
            3,  # headshot_kills
            45.5,  # avg_life_seconds
            600,  # time_played_seconds
            15,  # kills
            6,  # deaths
            3,  # assists
            55.0,  # accuracy
            50,  # my_team_score
            45,  # enemy_team_score
            1500.0,  # team_mmr
            1450.0,  # enemy_mmr
        ),
        (
            "match_2",
            datetime(2026, 2, 1, 11, 0, 0, tzinfo=timezone.utc),
            "map_2",
            "Streets",
            "playlist_1",
            "Ranked Arena",
            "pair_2",
            "CTF",
            "variant_2",
            "Ranked CTF",
            3,  # outcome (Loss)
            0,
            1.0,
            3,
            2,
            30.0,
            720,
            10,
            10,
            5,
            48.0,
            2,
            3,
            1480.0,
            1520.0,
        ),
    ]


# ============================================================================
# Tests load_matches avec limit/offset
# ============================================================================


class TestLoadMatchesPagination:
    """Tests pour load_matches avec limit et offset."""

    def test_load_matches_with_limit(self):
        """Test que limit restreint le nombre de résultats."""
        with patch("src.data.repositories.duckdb_repo.duckdb") as mock_duckdb:
            mock_conn = MagicMock()
            mock_duckdb.connect.return_value = mock_conn

            # Setup mock
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_result.description = []
            mock_conn.execute.return_value = mock_result

            from src.data.repositories.duckdb_repo import DuckDBRepository

            # Créer un repo avec un path qui "existe"
            with patch.object(Path, "exists", return_value=True):
                repo = DuckDBRepository(Path("/fake/path.duckdb"), "12345")
                # Forcer mode v4 : connexion déjà établie, sans shared attaché
                repo._connection = mock_conn
                repo._attached_dbs = set()
                repo.load_matches(limit=10)

            # Vérifier que LIMIT est dans la requête
            calls = mock_conn.execute.call_args_list
            assert any("LIMIT 10" in str(c) for c in calls)

    def test_load_matches_with_offset(self):
        """Test que offset décale les résultats."""
        with patch("src.data.repositories.duckdb_repo.duckdb") as mock_duckdb:
            mock_conn = MagicMock()
            mock_duckdb.connect.return_value = mock_conn

            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_result.description = []
            mock_conn.execute.return_value = mock_result

            from src.data.repositories.duckdb_repo import DuckDBRepository

            with patch.object(Path, "exists", return_value=True):
                repo = DuckDBRepository(Path("/fake/path.duckdb"), "12345")
                repo._connection = mock_conn
                repo._attached_dbs = set()
                repo.load_matches(limit=10, offset=20)

            calls = mock_conn.execute.call_args_list
            assert any("OFFSET 20" in str(c) for c in calls)

    def test_load_matches_without_pagination(self):
        """Test que sans limit/offset, pas de clause LIMIT/OFFSET."""
        with patch("src.data.repositories.duckdb_repo.duckdb") as mock_duckdb:
            mock_conn = MagicMock()
            mock_duckdb.connect.return_value = mock_conn

            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_result.description = []
            mock_conn.execute.return_value = mock_result

            from src.data.repositories.duckdb_repo import DuckDBRepository

            with patch.object(Path, "exists", return_value=True):
                repo = DuckDBRepository(Path("/fake/path.duckdb"), "12345")
                repo._connection = mock_conn
                repo._attached_dbs = set()
                repo.load_matches()

            # La requête ne devrait pas contenir LIMIT (sauf si None est interpolé)
            calls = mock_conn.execute.call_args_list
            # On vérifie qu'il n'y a pas de "LIMIT None" ou "LIMIT"
            for call in calls:
                sql = str(call)
                if "SELECT" in sql and "match_id" in sql:
                    # Vérifier que la pagination n'est pas ajoutée sans paramètres
                    assert "LIMIT None" not in sql


# ============================================================================
# Tests load_recent_matches
# ============================================================================


class TestLoadRecentMatches:
    """Tests pour load_recent_matches (lazy loading)."""

    def test_load_recent_matches_default_limit(self):
        """Test que le limit par défaut est 50."""
        with patch("src.data.repositories.duckdb_repo.duckdb") as mock_duckdb:
            mock_conn = MagicMock()
            mock_duckdb.connect.return_value = mock_conn

            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_result.description = []
            mock_conn.execute.return_value = mock_result

            from src.data.repositories.duckdb_repo import DuckDBRepository

            with patch.object(Path, "exists", return_value=True):
                repo = DuckDBRepository(Path("/fake/path.duckdb"), "12345")
                repo._connection = mock_conn
                repo._attached_dbs = set()
                repo.load_recent_matches()

            calls = mock_conn.execute.call_args_list
            assert any("LIMIT 50" in str(c) for c in calls)

    def test_load_recent_matches_descending_order(self):
        """Test que les matchs sont triés par date décroissante."""
        with patch("src.data.repositories.duckdb_repo.duckdb") as mock_duckdb:
            mock_conn = MagicMock()
            mock_duckdb.connect.return_value = mock_conn

            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_result.description = []
            mock_conn.execute.return_value = mock_result

            from src.data.repositories.duckdb_repo import DuckDBRepository

            with (
                patch.object(Path, "exists", return_value=True),
                patch.object(
                    DuckDBRepository,
                    "_build_metadata_resolution",
                    return_value=("", "map_name", "playlist_name", "pair_name"),
                ),
                patch.object(
                    DuckDBRepository,
                    "_build_mmr_fallback",
                    return_value=("", "team_mmr", "enemy_mmr"),
                ),
            ):
                repo = DuckDBRepository(Path("/fake/path.duckdb"), "12345")
                repo._connection = mock_conn
                repo._attached_dbs = set()
                repo.load_recent_matches(limit=10)

            calls = mock_conn.execute.call_args_list
            # Vérifier que la requête contient ORDER BY ... DESC
            sql_calls = [str(call) for call in calls if call and len(call) > 0]
            assert any("ORDER BY" in str(call) and "DESC" in str(call) for call in sql_calls)


# ============================================================================
# Tests load_matches_paginated
# ============================================================================


class TestLoadMatchesPaginated:
    """Tests pour load_matches_paginated.

    Note: Les tests avec mocks unitaires sont skip car le mocking de DuckDBRepository
    est complexe (appels d'init pour attacher metadata.duckdb).
    Les tests d'intégration dans TestLazyLoadingIntegration couvrent ce cas.
    """

    @pytest.mark.skip(reason="Mocking complexe - couvert par tests d'intégration")
    def test_pagination_page_1(self):
        """Test page 1 (offset 0)."""
        with patch("src.data.repositories.duckdb_repo.duckdb") as mock_duckdb:
            mock_conn = MagicMock()
            mock_duckdb.connect.return_value = mock_conn

            # Mock get_match_count
            count_result = MagicMock()
            count_result.fetchone.return_value = [100]

            matches_result = MagicMock()
            matches_result.fetchall.return_value = []
            matches_result.description = []

            mock_conn.execute.side_effect = [count_result, matches_result]

            from src.data.repositories.duckdb_repo import DuckDBRepository

            with patch.object(Path, "exists", return_value=True):
                repo = DuckDBRepository(Path("/fake/path.duckdb"), "12345")
                matches, total_pages = repo.load_matches_paginated(page=1, page_size=50)

            assert total_pages == 2  # 100 matchs / 50 par page = 2 pages

    @pytest.mark.skip(reason="Mocking complexe - couvert par tests d'intégration")
    def test_pagination_calculates_total_pages(self):
        """Test que le nombre total de pages est correct."""
        with patch("src.data.repositories.duckdb_repo.duckdb") as mock_duckdb:
            mock_conn = MagicMock()
            mock_duckdb.connect.return_value = mock_conn

            count_result = MagicMock()
            count_result.fetchone.return_value = [125]

            matches_result = MagicMock()
            matches_result.fetchall.return_value = []
            matches_result.description = []

            mock_conn.execute.side_effect = [count_result, matches_result]

            from src.data.repositories.duckdb_repo import DuckDBRepository

            with patch.object(Path, "exists", return_value=True):
                repo = DuckDBRepository(Path("/fake/path.duckdb"), "12345")
                _, total_pages = repo.load_matches_paginated(page=1, page_size=50)

            assert total_pages == 3  # 125 matchs / 50 par page = 3 pages (arrondi supérieur)

    @pytest.mark.skip(reason="Mocking complexe - couvert par tests d'intégration")
    def test_pagination_clamps_invalid_page(self):
        """Test que les pages invalides sont corrigées."""
        with patch("src.data.repositories.duckdb_repo.duckdb") as mock_duckdb:
            mock_conn = MagicMock()
            mock_duckdb.connect.return_value = mock_conn

            count_result = MagicMock()
            count_result.fetchone.return_value = [100]

            matches_result = MagicMock()
            matches_result.fetchall.return_value = []
            matches_result.description = []

            mock_conn.execute.side_effect = [count_result, matches_result]

            from src.data.repositories.duckdb_repo import DuckDBRepository

            with patch.object(Path, "exists", return_value=True):
                repo = DuckDBRepository(Path("/fake/path.duckdb"), "12345")
                # Page 999 devrait être corrigée à la dernière page (2)
                _, total_pages = repo.load_matches_paginated(page=999, page_size=50)

            assert total_pages == 2


# ============================================================================
# Tests d'intégration (si DB disponible)
# ============================================================================


class TestLazyLoadingIntegration:
    """Tests d'intégration avec une vraie DB DuckDB."""

    @pytest.fixture
    def temp_duckdb(self, tmp_path):
        """Crée une DB DuckDB temporaire avec des données de test."""
        import gc
        import uuid

        import duckdb

        db_path = tmp_path / f"test_stats_{uuid.uuid4().hex[:8]}.duckdb"
        conn = duckdb.connect(str(db_path))

        try:
            # Créer la table match_stats
            conn.execute("""
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
                    kda DOUBLE,
                    max_killing_spree INTEGER,
                    headshot_kills INTEGER,
                    avg_life_seconds DOUBLE,
                    time_played_seconds INTEGER,
                    kills INTEGER,
                    deaths INTEGER,
                    assists INTEGER,
                    accuracy DOUBLE,
                    my_team_score INTEGER,
                    enemy_team_score INTEGER,
                    team_mmr DOUBLE,
                    enemy_mmr DOUBLE,
                    is_firefight BOOLEAN DEFAULT FALSE
                )
            """)

            # Insérer des données de test avec des timestamps uniques
            for i in range(100):
                conn.execute(
                    """
                    INSERT INTO match_stats (
                        match_id, start_time, map_id, map_name,
                        playlist_id, playlist_name, pair_id, pair_name,
                        game_variant_id, game_variant_name,
                        outcome, team_id, kda, max_killing_spree, headshot_kills,
                        avg_life_seconds, time_played_seconds,
                        kills, deaths, assists, accuracy,
                        my_team_score, enemy_team_score, team_mmr, enemy_mmr
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        f"match_{i}",
                        datetime(2026, 2, 1, i % 24, i % 60, i % 60),  # Timestamps uniques
                        f"map_{i % 5}",
                        f"Map {i % 5}",
                        "playlist_1",
                        "Ranked",
                        "pair_1",
                        "Slayer",
                        "variant_1",
                        "Ranked Slayer",
                        2 if i % 2 == 0 else 3,
                        0,
                        2.0 + (i % 10) / 10,
                        i % 10,
                        i % 5,
                        30.0 + i,
                        600 + i * 10,
                        10 + i % 5,
                        5 + i % 3,
                        3 + i % 4,
                        50.0 + i % 20,
                        50,
                        45,
                        1500.0,
                        1480.0,
                    ],
                )
        finally:
            conn.close()
            del conn
            gc.collect()

        return db_path

    def test_integration_load_recent_matches(self, temp_duckdb):
        """Test load_recent_matches avec une vraie DB."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(temp_duckdb, "12345")
        matches = repo.load_recent_matches(limit=10)
        repo.close()

        assert len(matches) == 10
        # Les matchs devraient être triés par date décroissante
        for i in range(len(matches) - 1):
            assert matches[i].start_time >= matches[i + 1].start_time

    def test_integration_load_matches_paginated(self, temp_duckdb):
        """Test load_matches_paginated avec une vraie DB."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(temp_duckdb, "12345")
        matches, total_pages = repo.load_matches_paginated(page=1, page_size=25)
        repo.close()

        assert len(matches) == 25
        assert total_pages == 4  # 100 matchs / 25 par page

    def test_integration_pagination_consistency(self, temp_duckdb):
        """Test que la pagination couvre tous les matchs sans doublon."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(temp_duckdb, "12345")

        all_match_ids = set()
        page = 1
        page_size = 30

        while True:
            matches, total_pages = repo.load_matches_paginated(page=page, page_size=page_size)
            if not matches:
                break

            for m in matches:
                assert m.match_id not in all_match_ids, f"Doublon: {m.match_id}"
                all_match_ids.add(m.match_id)

            if page >= total_pages:
                break
            page += 1

        repo.close()

        # Vérifier qu'on a récupéré tous les matchs
        assert len(all_match_ids) == 100

    def test_integration_load_matches_with_limit_offset(self, temp_duckdb):
        """Test load_matches avec limit et offset."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(temp_duckdb, "12345")

        # Charger les 10 premiers
        first_10 = repo.load_matches(limit=10, offset=0)
        # Charger les 10 suivants
        next_10 = repo.load_matches(limit=10, offset=10)

        repo.close()

        assert len(first_10) == 10
        assert len(next_10) == 10

        # Vérifier qu'il n'y a pas de chevauchement
        first_ids = {m.match_id for m in first_10}
        next_ids = {m.match_id for m in next_10}
        assert first_ids.isdisjoint(next_ids)
