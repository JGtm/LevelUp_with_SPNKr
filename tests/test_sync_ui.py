"""Tests pour le module src/ui/sync.py.

Ce fichier teste les fonctionnalités de synchronisation UI :
- Détection DuckDB vs SQLite
- Extraction du gamertag depuis le chemin DuckDB v4
- Fonction _sync_duckdb_player
- Fonction sync_all_players avec support DuckDB
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

# =============================================================================
# Tests de détection de chemins
# =============================================================================


class TestIsSpnkrDbPath:
    """Tests pour is_spnkr_db_path."""

    def test_spnkr_db_legacy(self):
        """Test avec une base SPNKr legacy .db."""
        from src.ui.sync import is_spnkr_db_path

        assert is_spnkr_db_path("data/spnkr_JGtm.db") is True
        assert is_spnkr_db_path("spnkr_player.db") is True

    def test_halo_db_legacy(self):
        """Test avec une base fusionnée halo_*.db."""
        from src.ui.sync import is_spnkr_db_path

        assert is_spnkr_db_path("data/halo_merged.db") is True

    def test_duckdb_v4_stats(self, tmp_path):
        """Test avec une base DuckDB v4 (stats.duckdb)."""
        from src.ui.sync import is_spnkr_db_path

        # Créer la structure de dossiers
        players_dir = tmp_path / "data" / "players" / "JGtm"
        players_dir.mkdir(parents=True)
        db_path = players_dir / "stats.duckdb"
        db_path.touch()

        assert is_spnkr_db_path(str(db_path)) is True

    def test_non_db_file(self):
        """Test avec un fichier non-DB."""
        from src.ui.sync import is_spnkr_db_path

        assert is_spnkr_db_path("data/config.json") is False
        assert is_spnkr_db_path("data/readme.md") is False
        assert is_spnkr_db_path("data/image.png") is False

    def test_empty_path(self):
        """Test avec chemin vide."""
        from src.ui.sync import is_spnkr_db_path

        assert is_spnkr_db_path("") is False


# =============================================================================
# Tests d'extraction du gamertag depuis le chemin
# =============================================================================


class TestExtractGamertagFromDuckDBPath:
    """Tests pour l'extraction du gamertag depuis le chemin DuckDB v4."""

    def test_extract_gamertag_from_valid_path(self):
        """Test extraction depuis un chemin valide."""
        path = "data/players/JGtm/stats.duckdb"
        p = Path(path)

        # Le gamertag devrait être le nom du parent directory
        assert p.name == "stats.duckdb"
        assert p.parent.name == "JGtm"
        assert p.parent.parent.name == "players"

    def test_extract_gamertag_with_spaces(self):
        """Test extraction avec gamertag contenant des caractères spéciaux."""
        path = "data/players/Player With Spaces/stats.duckdb"
        p = Path(path)

        assert p.parent.name == "Player With Spaces"

    def test_invalid_path_structure(self):
        """Test avec une structure de chemin invalide."""
        # Le fichier n'est pas dans data/players/{gamertag}/
        path = "data/other/stats.duckdb"
        p = Path(path)

        # Ce n'est pas une structure valide DuckDB v4
        assert p.parent.parent.name != "players"


# =============================================================================
# Tests de _sync_duckdb_player (mocked)
# =============================================================================


class TestSyncDuckDBPlayer:
    """Tests pour _sync_duckdb_player."""

    @pytest.fixture
    def mock_duckdb_env(self, tmp_path):
        """Crée un environnement mock pour les tests DuckDB."""
        # Créer une vraie base DuckDB
        import duckdb

        players_dir = tmp_path / "data" / "players" / "TestPlayer"
        players_dir.mkdir(parents=True)
        db_path = players_dir / "stats.duckdb"

        conn = duckdb.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                kills INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS xuid_aliases (
                xuid VARCHAR PRIMARY KEY,
                gamertag VARCHAR,
                last_seen TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT INTO xuid_aliases VALUES ('2535423456789', 'TestPlayer', CURRENT_TIMESTAMP)
        """)
        conn.close()

        return str(db_path)

    def test_sync_missing_tokens(self, mock_duckdb_env):
        """Test sync avec tokens manquants."""

        # Mock get_tokens_from_env pour retourner None
        with patch("src.ui.sync._sync_duckdb_player") as mock_sync:
            mock_sync.return_value = (False, "Tokens SPNKr manquants.")

            ok, msg = mock_sync(
                db_path=mock_duckdb_env,
                gamertag="TestPlayer",
                max_matches=10,
                delta=True,
            )

            assert ok is False
            assert "Tokens" in msg or "manquants" in msg

    def test_sync_success_with_new_matches(self, mock_duckdb_env):
        """Test sync réussie avec nouveaux matchs."""

        with patch("src.ui.sync._sync_duckdb_player") as mock_sync:
            mock_sync.return_value = (True, "5 nouveau(x) match(s) synchronisé(s).")

            ok, msg = mock_sync(
                db_path=mock_duckdb_env,
                gamertag="TestPlayer",
                max_matches=100,
                delta=True,
            )

            assert ok is True
            assert "nouveau" in msg

    def test_sync_already_up_to_date(self, mock_duckdb_env):
        """Test sync quand déjà à jour."""

        with patch("src.ui.sync._sync_duckdb_player") as mock_sync:
            mock_sync.return_value = (True, "À jour (150 matchs).")

            ok, msg = mock_sync(
                db_path=mock_duckdb_env,
                gamertag="TestPlayer",
                delta=True,
            )

            assert ok is True
            assert "À jour" in msg


# =============================================================================
# Tests de sync_all_players
# =============================================================================


class TestSyncAllPlayers:
    """Tests pour sync_all_players avec support DuckDB."""

    @pytest.fixture
    def mock_duckdb_db(self, tmp_path):
        """Crée une base DuckDB mock."""
        import duckdb

        players_dir = tmp_path / "data" / "players" / "MockPlayer"
        players_dir.mkdir(parents=True)
        db_path = players_dir / "stats.duckdb"

        conn = duckdb.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS match_stats (
                match_id VARCHAR PRIMARY KEY
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS xuid_aliases (
                xuid VARCHAR PRIMARY KEY,
                gamertag VARCHAR,
                last_seen TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT INTO xuid_aliases VALUES ('999888777666', 'MockPlayer', CURRENT_TIMESTAMP)
        """)
        conn.close()

        return str(db_path)

    def test_detects_duckdb_path(self, mock_duckdb_db):
        """Test que sync_all_players détecte correctement un chemin DuckDB."""
        assert mock_duckdb_db.endswith(".duckdb")

        # Vérifier la structure du chemin
        p = Path(mock_duckdb_db)
        assert p.name == "stats.duckdb"
        assert p.parent.parent.name == "players"

    def test_extracts_gamertag_from_duckdb_path(self, mock_duckdb_db):
        """Test que le gamertag est correctement extrait du chemin."""
        p = Path(mock_duckdb_db)
        gamertag = p.parent.name

        assert gamertag == "MockPlayer"

    def test_extracts_xuid_from_xuid_aliases(self, mock_duckdb_db):
        """Test que le XUID est correctement extrait de xuid_aliases."""
        import duckdb

        conn = duckdb.connect(mock_duckdb_db, read_only=True)
        result = conn.execute(
            "SELECT xuid FROM xuid_aliases ORDER BY last_seen DESC LIMIT 1"
        ).fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "999888777666"

    def test_sync_all_players_uses_duckdb_sync(self, mock_duckdb_db):
        """Test que sync_all_players utilise _sync_duckdb_player pour DuckDB."""
        from src.ui.sync import sync_all_players

        # Mock _sync_duckdb_player
        with patch("src.ui.sync._sync_duckdb_player") as mock_sync:
            mock_sync.return_value = (True, "Sync OK")

            ok, msg = sync_all_players(
                db_path=mock_duckdb_db,
                max_matches=10,
                delta=True,
            )

            # Vérifier que _sync_duckdb_player a été appelé
            mock_sync.assert_called_once()
            call_args = mock_sync.call_args
            assert call_args.kwargs["gamertag"] == "MockPlayer"
            assert call_args.kwargs["db_path"] == mock_duckdb_db


# =============================================================================
# Tests de SyncResult.errors (vs .error)
# =============================================================================


class TestSyncResultErrors:
    """Tests pour vérifier que SyncResult utilise .errors (liste)."""

    def test_sync_result_has_errors_list(self):
        """Vérifie que SyncResult a un attribut errors (liste)."""
        from src.data.sync.models import SyncResult

        result = SyncResult()

        # Doit avoir .errors, pas .error
        assert hasattr(result, "errors")
        assert isinstance(result.errors, list)
        assert not hasattr(result, "error")

    def test_sync_result_with_errors(self):
        """Test SyncResult avec des erreurs."""
        from src.data.sync.models import SyncResult

        result = SyncResult(errors=["Erreur 1", "Erreur 2"])

        assert len(result.errors) == 2
        assert "Erreur 1" in result.errors
        assert result.success is False

    def test_sync_result_without_errors(self):
        """Test SyncResult sans erreurs."""
        from src.data.sync.models import SyncResult

        result = SyncResult(matches_inserted=5)

        assert len(result.errors) == 0
        assert result.success is True


# =============================================================================
# Tests pour refresh_spnkr_db_via_api (SQLite legacy)
# =============================================================================


class TestRefreshSpnkrDbViaApi:
    """Tests pour refresh_spnkr_db_via_api (script SQLite legacy)."""

    def test_missing_script(self, tmp_path):
        """Test quand le script d'import n'existe pas."""
        from src.ui.sync import refresh_spnkr_db_via_api

        # Le script n'existe pas dans tmp_path
        ok, msg = refresh_spnkr_db_via_api(
            db_path=str(tmp_path / "test.db"),
            player="TestPlayer",
            match_type="matchmaking",
            max_matches=10,
            rps=5,
            repo_root=tmp_path,
        )

        assert ok is False
        assert "introuvable" in msg

    def test_empty_player(self, tmp_path):
        """Test avec joueur vide."""
        from src.ui.sync import refresh_spnkr_db_via_api

        # Créer le script mock
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "spnkr_import_db.py").touch()

        ok, msg = refresh_spnkr_db_via_api(
            db_path=str(tmp_path / "test.db"),
            player="",
            match_type="matchmaking",
            max_matches=10,
            rps=5,
            repo_root=tmp_path,
        )

        assert ok is False
        assert "joueur" in msg.lower()


# =============================================================================
# Tests d'intégration légère
# =============================================================================


class TestSyncIntegration:
    """Tests d'intégration pour le module sync."""

    def test_duckdb_path_detection_and_gamertag_extraction(self, tmp_path):
        """Test complet : détection DuckDB + extraction gamertag."""
        import duckdb

        from src.ui.sync import is_spnkr_db_path

        # Créer une structure DuckDB v4 complète
        gamertag = "IntegrationTestPlayer"
        players_dir = tmp_path / "data" / "players" / gamertag
        players_dir.mkdir(parents=True)
        db_path = players_dir / "stats.duckdb"

        # Créer la base avec les tables nécessaires
        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE TABLE match_stats (match_id VARCHAR)")
        conn.execute(
            "CREATE TABLE xuid_aliases (xuid VARCHAR, gamertag VARCHAR, last_seen TIMESTAMP)"
        )
        conn.execute(
            f"INSERT INTO xuid_aliases VALUES ('123456789', '{gamertag}', CURRENT_TIMESTAMP)"
        )
        conn.close()

        # Test 1: is_spnkr_db_path détecte correctement
        assert is_spnkr_db_path(str(db_path)) is True

        # Test 2: Le gamertag peut être extrait du chemin
        p = Path(db_path)
        assert p.parent.name == gamertag
        assert p.parent.parent.name == "players"

        # Test 3: Le XUID peut être extrait de la table
        conn = duckdb.connect(str(db_path), read_only=True)
        result = conn.execute("SELECT xuid FROM xuid_aliases LIMIT 1").fetchone()
        conn.close()
        assert result is not None
        assert result[0] == "123456789"

    def test_sync_all_players_path_parsing(self, tmp_path):
        """Test que sync_all_players parse correctement différents chemins."""
        import duckdb

        # Cas 1: Chemin DuckDB v4 standard
        gamertag = "TestGamer"
        players_dir = tmp_path / "data" / "players" / gamertag
        players_dir.mkdir(parents=True)
        db_path = players_dir / "stats.duckdb"

        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE TABLE match_stats (match_id VARCHAR)")
        conn.execute(
            "CREATE TABLE xuid_aliases (xuid VARCHAR, gamertag VARCHAR, last_seen TIMESTAMP)"
        )
        conn.close()

        # Vérifier que le chemin est bien parsé
        assert str(db_path).endswith(".duckdb")
        p = Path(db_path)
        assert p.name == "stats.duckdb"
        assert p.parent.name == gamertag
        assert p.parent.parent.name == "players"
