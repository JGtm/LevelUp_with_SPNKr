"""
Tests pour le DuckDBRepository.

Ce module teste le nouveau repository DuckDB natif (architecture v4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Skip si DuckDB n'est pas disponible
pytest.importorskip("duckdb")


class TestDuckDBRepositoryImport:
    """Tests d'import et de structure."""

    def test_import_duckdb_repository(self):
        """Vérifie que DuckDBRepository peut être importé."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        assert DuckDBRepository is not None

    def test_import_from_factory(self):
        """Vérifie que le mode DUCKDB est disponible dans le factory."""
        from src.data.repositories.factory import RepositoryMode

        assert hasattr(RepositoryMode, "DUCKDB")
        assert RepositoryMode.DUCKDB.value == "duckdb"

    def test_import_get_repository_from_profile(self):
        """Vérifie que get_repository_from_profile est disponible."""
        from src.data.repositories.factory import get_repository_from_profile

        assert callable(get_repository_from_profile)

    def test_import_load_db_profiles(self):
        """Vérifie que load_db_profiles est disponible."""
        from src.data.repositories.factory import load_db_profiles

        assert callable(load_db_profiles)


class TestDuckDBRepositoryInit:
    """Tests d'initialisation du repository."""

    def test_init_with_nonexistent_db(self):
        """Vérifie que l'init ne fait pas d'erreur avec une DB inexistante."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path="nonexistent.duckdb",
            xuid="123456789",
        )

        assert repo.xuid == "123456789"
        assert repo.db_path == "nonexistent.duckdb"

    def test_init_with_gamertag(self):
        """Vérifie que le gamertag est stocké."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path="test.duckdb",
            xuid="123456789",
            gamertag="TestPlayer",
        )

        assert repo._gamertag == "TestPlayer"

    def test_connection_error_on_missing_db(self):
        """Vérifie l'erreur si la DB n'existe pas lors de la connexion."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path="nonexistent.duckdb",
            xuid="123456789",
        )

        with pytest.raises(FileNotFoundError):
            repo._get_connection()


class TestRepositoryModeSelection:
    """Tests de sélection du mode de repository."""

    def test_mode_duckdb_from_string(self):
        """Vérifie la conversion string -> RepositoryMode."""
        from src.data.repositories.factory import RepositoryMode

        mode = RepositoryMode("duckdb")
        assert mode == RepositoryMode.DUCKDB

    def test_get_repository_with_duckdb_mode(self):
        """Vérifie que get_repository crée un DuckDBRepository."""
        from src.data.repositories.duckdb_repo import DuckDBRepository
        from src.data.repositories.factory import RepositoryMode, get_repository

        repo = get_repository(
            "test.duckdb",
            "123456789",
            mode=RepositoryMode.DUCKDB,
        )

        assert isinstance(repo, DuckDBRepository)

    def test_get_repository_with_duckdb_string(self):
        """Vérifie que get_repository fonctionne avec 'duckdb' en string."""
        from src.data.repositories.duckdb_repo import DuckDBRepository
        from src.data.repositories.factory import get_repository

        repo = get_repository(
            "test.duckdb",
            "123456789",
            mode="duckdb",
        )

        assert isinstance(repo, DuckDBRepository)


class TestLoadDbProfiles:
    """Tests pour load_db_profiles."""

    def test_load_existing_profiles(self):
        """Vérifie le chargement de db_profiles.json."""
        from src.data.repositories.factory import load_db_profiles

        profiles = load_db_profiles()

        # Doit contenir version et profiles
        assert "version" in profiles
        assert "profiles" in profiles

    def test_profiles_version_2(self):
        """Vérifie que la version est >= 2.0 pour DuckDB."""
        from src.data.repositories.factory import load_db_profiles

        profiles = load_db_profiles()
        version = profiles.get("version", "1.0")

        assert version >= "2.0", "db_profiles.json devrait être en version 2.0+"

    def test_profiles_contain_duckdb_paths(self):
        """Vérifie que les profils pointent vers des fichiers .duckdb."""
        from src.data.repositories.factory import load_db_profiles

        profiles = load_db_profiles()

        for gamertag, profile in profiles.get("profiles", {}).items():
            db_path = profile.get("db_path", "")
            assert db_path.endswith(".duckdb"), f"{gamertag} devrait avoir un chemin .duckdb"


class TestStreamlitBridge:
    """Tests pour l'intégration Streamlit."""

    def test_import_get_repository_for_player(self):
        """Vérifie que get_repository_for_player est exporté."""
        from src.data.integration import get_repository_for_player

        assert callable(get_repository_for_player)

    def test_mode_detection_returns_duckdb(self):
        """Vérifie que l'auto-détection retourne DUCKDB pour v2.0."""
        from src.data.integration import get_repository_mode_from_settings
        from src.data.repositories.factory import RepositoryMode

        # Sans variable d'environnement et avec db_profiles v2.0
        # devrait retourner DUCKDB
        mode = get_repository_mode_from_settings()

        assert mode == RepositoryMode.DUCKDB


@pytest.mark.skipif(
    not Path("data/players/XxDaemonGamerxX/stats.duckdb").exists(),
    reason="Base de données de test non disponible",
)
class TestDuckDBRepositoryWithRealData:
    """Tests avec vraies données (si disponibles)."""

    @pytest.fixture
    def repo(self):
        """Crée un repository avec des vraies données."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path="data/players/XxDaemonGamerxX/stats.duckdb",
            xuid="2533274833178266",
            gamertag="XxDaemonGamerxX",
        )
        yield repo
        repo.close()

    def test_load_matches_returns_list(self, repo):
        """Vérifie que load_matches retourne une liste."""
        matches = repo.load_matches()
        assert isinstance(matches, list)

    def test_load_matches_returns_match_rows(self, repo):
        """Vérifie que les matchs sont des MatchRow."""
        from src.data.domain.models.stats import MatchRow

        matches = repo.load_matches()
        if matches:
            assert isinstance(matches[0], MatchRow)

    def test_get_match_count(self, repo):
        """Vérifie que get_match_count retourne un entier."""
        count = repo.get_match_count()
        assert isinstance(count, int)
        assert count >= 0

    def test_is_hybrid_available(self, repo):
        """Vérifie que is_hybrid_available fonctionne (architecture hybride supprimée en v4)."""
        # Note: L'architecture hybride a été supprimée en v4.
        # is_hybrid_available retourne maintenant False par défaut.
        result = repo.is_hybrid_available()
        assert isinstance(result, bool)

    def test_get_storage_info(self, repo):
        """Vérifie les infos de stockage."""
        info = repo.get_storage_info()

        assert info["type"] == "duckdb"
        assert "match_stats" in info["tables"]
        assert info["file_size_mb"] > 0

    def test_get_sync_metadata(self, repo):
        """Vérifie les métadonnées de sync."""
        meta = repo.get_sync_metadata()

        assert meta["storage_type"] == "duckdb"
        assert meta["player_xuid"] == "2533274833178266"
        assert "total_matches" in meta


@pytest.mark.skipif(
    not Path("data/players/XxDaemonGamerxX/stats.duckdb").exists(),
    reason="Base de données de test non disponible",
)
class TestDuckDBRepositoryQueries:
    """Tests des requêtes avancées."""

    @pytest.fixture
    def repo(self):
        """Crée un repository avec des vraies données."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path="data/players/XxDaemonGamerxX/stats.duckdb",
            xuid="2533274833178266",
        )
        yield repo
        repo.close()

    def test_query_raw_sql(self, repo):
        """Vérifie que query() fonctionne."""
        results = repo.query("SELECT COUNT(*) as cnt FROM match_stats")

        assert len(results) == 1
        assert "cnt" in results[0]

    def test_query_with_params(self, repo):
        """Vérifie query() avec paramètres."""
        results = repo.query(
            "SELECT COUNT(*) as cnt FROM match_stats WHERE outcome = ?",
            [2],  # Victoire
        )

        assert len(results) == 1

    def test_query_df_returns_polars(self, repo):
        """Vérifie que query_df retourne un DataFrame Polars."""
        import polars as pl

        df = repo.query_df("SELECT match_id, kda FROM match_stats LIMIT 5")

        assert isinstance(df, pl.DataFrame)
        assert "match_id" in df.columns
        assert "kda" in df.columns

    def test_load_top_teammates(self, repo):
        """Vérifie list_top_teammates."""
        teammates = repo.list_top_teammates(limit=5)

        assert isinstance(teammates, list)
        # Peut être vide si pas de données
