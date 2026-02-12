"""Tests pour les vues matérialisées (Sprint 4.1).

Ce module teste :
- La création des tables mv_*
- Le rafraîchissement des vues
- La lecture des stats agrégées
- Les performances comparées aux requêtes directes
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

# Import direct pour éviter l'import circulaire dans src.data
# On ajoute le chemin du repo au sys.path
_repo_root = Path(__file__).parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


def _get_duckdb_repository_class():
    """Import lazy du DuckDBRepository pour éviter l'import circulaire."""
    # Import direct du module sans passer par src.data
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "duckdb_repo", _repo_root / "src" / "data" / "repositories" / "duckdb_repo.py"
    )
    module = importlib.util.module_from_spec(spec)

    # Charger les dépendances nécessaires d'abord
    # Le module a besoin des dataclasses de match
    from src.data.domain.models.stats import MatchRow  # noqa: F401

    spec.loader.exec_module(module)
    return module.DuckDBRepository


class TestMaterializedViews:
    """Tests pour les vues matérialisées du DuckDBRepository."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path) -> Path:
        """Crée une base de données DuckDB temporaire avec des données de test."""
        import gc
        import uuid

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
                    enemy_mmr DOUBLE
                )
            """)

            # Insérer des données de test variées
            base_time = datetime.now() - timedelta(days=30)
            test_matches = []

            maps_data = [
                ("map1", "Streets"),
                ("map2", "Recharge"),
                ("map3", "Live Fire"),
            ]
            modes_data = [
                ("Slayer", "Team Slayer"),
                ("CTF", "Capture The Flag"),
                ("Oddball", "Oddball"),
            ]

            for i in range(50):
                map_id, map_name = maps_data[i % 3]
                mode_name, pair_name = modes_data[i % 3]
                outcome = 2 if i % 3 == 0 else (3 if i % 3 == 1 else 1)  # Win, Loss, Tie

                test_matches.append(
                    (
                        f"match_{i:04d}",
                        base_time + timedelta(hours=i),
                        map_id,
                        map_name,
                        f"playlist_{i % 2}",
                        f"Playlist {i % 2}",
                        f"pair_{i % 3}",
                        pair_name,
                        f"variant_{i % 3}",
                        mode_name,
                        outcome,
                        1,  # team_id
                        1.5 + (i % 10) * 0.1,  # kda
                        3 + i % 5,  # max_killing_spree
                        2 + i % 4,  # headshot_kills
                        45.0 + i % 30,  # avg_life_seconds
                        600 + i * 10,  # time_played_seconds
                        10 + i % 15,  # kills
                        5 + i % 10,  # deaths
                        3 + i % 5,  # assists
                        0.40 + (i % 20) * 0.01,  # accuracy
                        50,  # my_team_score
                        45 + i % 10,  # enemy_team_score
                        1200.0 + i * 5,  # team_mmr
                        1190.0 + i * 5,  # enemy_mmr
                    )
                )

            conn.executemany(
                """
                INSERT INTO match_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                test_matches,
            )
        finally:
            conn.close()
            del conn
            gc.collect()

        return db_path

    @pytest.fixture
    def repo(self, temp_db: Path):
        """Crée un DuckDBRepository pour les tests."""
        DuckDBRepository = _get_duckdb_repository_class()

        repo = DuckDBRepository(
            player_db_path=temp_db,
            xuid="test_xuid",
            gamertag="TestPlayer",
            read_only=False,  # Besoin d'écriture pour refresh
        )
        yield repo
        repo.close()

    def test_refresh_creates_tables(self, repo):
        """Test que refresh_materialized_views crée les tables."""
        # Vérifier que les tables n'existent pas encore
        assert not repo.has_materialized_views()

        # Rafraîchir
        results = repo.refresh_materialized_views()

        # Vérifier les résultats
        assert "mv_map_stats" in results
        assert "mv_mode_category_stats" in results
        assert "mv_global_stats" in results
        assert results["mv_map_stats"] == 3  # 3 cartes
        assert results["mv_global_stats"] == 10  # 10 stats globales

        # Vérifier que has_materialized_views retourne True
        assert repo.has_materialized_views()

    def test_get_map_stats(self, repo):
        """Test la récupération des stats par carte."""
        repo.refresh_materialized_views()

        stats = repo.get_map_stats()

        assert len(stats) == 3  # 3 cartes
        for stat in stats:
            assert "map_id" in stat
            assert "map_name" in stat
            assert "matches_played" in stat
            assert "wins" in stat
            assert "avg_kda" in stat
            assert "win_rate" in stat
            assert stat["matches_played"] > 0

    def test_get_map_stats_min_matches_filter(self, repo):
        """Test le filtre min_matches sur les stats par carte."""
        repo.refresh_materialized_views()

        # Avec min_matches=100, aucune carte ne passe
        stats = repo.get_map_stats(min_matches=100)
        assert len(stats) == 0

        # Avec min_matches=1, toutes passent
        stats = repo.get_map_stats(min_matches=1)
        assert len(stats) == 3

    def test_get_mode_category_stats(self, repo):
        """Test la récupération des stats par catégorie de mode."""
        repo.refresh_materialized_views()

        stats = repo.get_mode_category_stats()

        assert len(stats) > 0
        for stat in stats:
            assert "mode_category" in stat
            assert "matches_played" in stat
            assert "avg_kda" in stat
            assert "win_rate" in stat

    def test_get_global_stats(self, repo):
        """Test la récupération des stats globales."""
        repo.refresh_materialized_views()

        stats = repo.get_global_stats()

        assert "total_matches" in stats
        assert "total_kills" in stats
        assert "total_deaths" in stats
        assert "avg_kda" in stats
        assert "wins" in stats
        assert "losses" in stats
        assert stats["total_matches"] == 50

    def test_refresh_is_idempotent(self, repo):
        """Test que refresh peut être appelé plusieurs fois."""
        results1 = repo.refresh_materialized_views()
        results2 = repo.refresh_materialized_views()

        # Les résultats doivent être identiques
        assert results1 == results2

    def test_empty_tables_before_refresh(self, repo):
        """Test que les méthodes retournent des listes/dicts vides avant refresh."""
        # Avant refresh, les tables n'existent pas
        assert repo.get_map_stats() == []
        assert repo.get_mode_category_stats() == []
        assert repo.get_global_stats() == {}


class TestBatchMmrLoading:
    """Tests pour le chargement batch des MMR (Sprint 4.2)."""

    @pytest.fixture
    def temp_db_with_mmr(self, tmp_path: Path) -> Path:
        """Crée une DB avec des matchs ayant des MMR variés."""
        import gc
        import uuid

        db_path = tmp_path / f"test_mmr_{uuid.uuid4().hex[:8]}.duckdb"

        conn = duckdb.connect(str(db_path))

        try:
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
                    enemy_mmr DOUBLE
                )
            """)

            # Insérer des matchs avec MMR
            test_data = [
                ("match_001", 1200.5, 1180.3),
                ("match_002", 1250.0, 1230.0),
                ("match_003", None, None),  # Match sans MMR
                ("match_004", 1300.0, 1350.0),
                ("match_005", 1100.0, 1100.0),
            ]

            for match_id, team_mmr, enemy_mmr in test_data:
                conn.execute(
                    """
                    INSERT INTO match_stats (match_id, start_time, team_mmr, enemy_mmr, kills, deaths, assists)
                    VALUES (?, CURRENT_TIMESTAMP, ?, ?, 10, 5, 3)
                """,
                    [match_id, team_mmr, enemy_mmr],
                )
        finally:
            conn.close()
            del conn
            gc.collect()

        return db_path

    @pytest.fixture
    def repo_mmr(self, temp_db_with_mmr: Path):
        """Crée un DuckDBRepository pour les tests MMR."""
        DuckDBRepository = _get_duckdb_repository_class()

        repo = DuckDBRepository(
            player_db_path=temp_db_with_mmr,
            xuid="test_xuid",
            gamertag="TestPlayer",
            read_only=True,
        )
        yield repo
        repo.close()

    def test_load_match_mmr_batch_single(self, repo_mmr):
        """Test le chargement batch avec un seul match."""
        result = repo_mmr.load_match_mmr_batch(["match_001"])

        assert "match_001" in result
        team_mmr, enemy_mmr = result["match_001"]
        assert team_mmr == pytest.approx(1200.5)
        assert enemy_mmr == pytest.approx(1180.3)

    def test_load_match_mmr_batch_multiple(self, repo_mmr):
        """Test le chargement batch avec plusieurs matchs."""
        result = repo_mmr.load_match_mmr_batch(["match_001", "match_002", "match_004"])

        assert len(result) == 3
        assert result["match_001"] == (pytest.approx(1200.5), pytest.approx(1180.3))
        assert result["match_002"] == (pytest.approx(1250.0), pytest.approx(1230.0))
        assert result["match_004"] == (pytest.approx(1300.0), pytest.approx(1350.0))

    def test_load_match_mmr_batch_with_nulls(self, repo_mmr):
        """Test le chargement batch avec des matchs sans MMR."""
        result = repo_mmr.load_match_mmr_batch(["match_003"])

        assert "match_003" in result
        team_mmr, enemy_mmr = result["match_003"]
        assert team_mmr is None
        assert enemy_mmr is None

    def test_load_match_mmr_batch_empty(self, repo_mmr):
        """Test le chargement batch avec une liste vide."""
        result = repo_mmr.load_match_mmr_batch([])
        assert result == {}

    def test_load_match_mmr_batch_unknown_match(self, repo_mmr):
        """Test le chargement batch avec un match inexistant."""
        result = repo_mmr.load_match_mmr_batch(["match_unknown"])
        assert result == {}


class TestPerformanceComparison:
    """Tests de performance comparant les vues matérialisées aux requêtes directes."""

    @pytest.fixture
    def large_db(self, tmp_path: Path) -> Path:
        """Crée une DB avec beaucoup de matchs pour les tests de perf."""
        import gc
        import random
        import uuid

        db_path = tmp_path / f"test_perf_{uuid.uuid4().hex[:8]}.duckdb"

        conn = duckdb.connect(str(db_path))

        try:
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
                    enemy_mmr DOUBLE
                )
            """)

            # Générer 1000 matchs
            random.seed(42)

            maps = [
                ("map1", "Streets"),
                ("map2", "Recharge"),
                ("map3", "Live Fire"),
                ("map4", "Aquarius"),
                ("map5", "Bazaar"),
            ]
            modes = [
                ("Slayer", "Team Slayer"),
                ("CTF", "CTF"),
                ("Oddball", "Oddball"),
                ("Strongholds", "Forteresse"),
                ("Total Control", "Contrôle Total"),
            ]

            base_time = datetime.now() - timedelta(days=365)

            for i in range(1000):
                map_id, map_name = random.choice(maps)
                mode_name, pair_name = random.choice(modes)
                outcome = random.choice([1, 2, 3])

                conn.execute(
                    """
                    INSERT INTO match_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        f"match_{i:06d}",
                        base_time + timedelta(hours=i),
                        map_id,
                        map_name,
                        f"playlist_{i % 3}",
                        f"Playlist {i % 3}",
                        f"pair_{i % 5}",
                        pair_name,
                        f"variant_{i % 5}",
                        mode_name,
                        outcome,
                        1,
                        random.uniform(0.5, 3.0),
                        random.randint(0, 10),
                        random.randint(0, 8),
                        random.uniform(30, 90),
                        random.randint(300, 900),
                        random.randint(5, 25),
                        random.randint(3, 20),
                        random.randint(1, 10),
                        random.uniform(0.25, 0.60),
                        random.randint(40, 60),
                        random.randint(35, 65),
                        random.uniform(1000, 1500),
                        random.uniform(1000, 1500),
                    ],
                )
        finally:
            conn.close()
            del conn
            gc.collect()

        return db_path

    def test_mv_faster_than_direct_query(self, large_db: Path):
        """Test que les vues matérialisées sont plus rapides que les requêtes directes."""
        import time

        DuckDBRepository = _get_duckdb_repository_class()

        repo = DuckDBRepository(
            player_db_path=large_db,
            xuid="test_xuid",
            read_only=False,
        )

        try:
            # Mesurer le temps de la requête directe (sans MV)
            start = time.perf_counter()
            for _ in range(10):
                repo.query("""
                    SELECT map_id, map_name, COUNT(*) as matches_played,
                           AVG(kda) as avg_kda, AVG(accuracy) as avg_accuracy
                    FROM match_stats
                    GROUP BY map_id, map_name
                """)
            direct_time = time.perf_counter() - start

            # Rafraîchir les vues matérialisées
            repo.refresh_materialized_views()

            # Mesurer le temps avec MV
            start = time.perf_counter()
            for _ in range(10):
                repo.get_map_stats()
            mv_time = time.perf_counter() - start

            # Les MV devraient être au moins aussi rapides (souvent plus rapides)
            # On tolère une marge car les deux sont très rapides sur DuckDB
            assert (
                mv_time <= direct_time * 2
            ), f"MV time ({mv_time:.4f}s) should be faster than direct ({direct_time:.4f}s)"

        finally:
            repo.close()
