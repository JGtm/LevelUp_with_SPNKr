"""Tests pour les fonctions de parsing dans src/utils."""

from src.utils import (
    guess_xuid_from_db_path,
    parse_xuid_input,
    resolve_xuid_from_db,
)


class TestResolveXuidFromDb:
    def test_returns_xuid_if_already_xuid(self, tmp_path):
        db_path = str(tmp_path / "dummy.db")
        assert resolve_xuid_from_db(db_path, "2533274823110022") == "2533274823110022"
        assert resolve_xuid_from_db(db_path, "xuid(2533274823110022)") == "2533274823110022"

    def test_fallback_default_player(self, tmp_path, monkeypatch):
        # Même si la DB n'aide pas, on doit pouvoir résoudre via des defaults locaux.
        monkeypatch.setenv("OPENSPARTAN_DEFAULT_GAMERTAG", "JGtm")
        monkeypatch.setenv("OPENSPARTAN_DEFAULT_XUID", "2533274823110022")
        db_path = str(tmp_path / "empty.db")
        assert resolve_xuid_from_db(db_path, "JGtm") == "2533274823110022"


class TestGuessXuidFromDbPath:
    """Tests pour guess_xuid_from_db_path."""

    def test_valid_xuid(self):
        """Test avec un chemin valide."""
        assert guess_xuid_from_db_path("/path/to/2533274823110022.db") == "2533274823110022"
        assert guess_xuid_from_db_path("C:\\Users\\data\\2533274823110022.db") == "2533274823110022"

    def test_invalid_xuid(self):
        """Test avec un chemin invalide."""
        assert guess_xuid_from_db_path("/path/to/mydata.db") is None
        assert guess_xuid_from_db_path("/path/to/abc123.db") is None


class TestParseXuidInput:
    """Tests pour parse_xuid_input."""

    def test_numeric_string(self):
        """Test avec chaîne numérique."""
        assert parse_xuid_input("2533274823110022") == "2533274823110022"

    def test_xuid_format(self):
        """Test avec format xuid()."""
        assert parse_xuid_input("xuid(2533274823110022)") == "2533274823110022"

    def test_with_whitespace(self):
        """Test avec espaces."""
        assert parse_xuid_input("  2533274823110022  ") == "2533274823110022"

    def test_empty(self):
        """Test avec chaîne vide."""
        assert parse_xuid_input("") is None
        assert parse_xuid_input("   ") is None

    def test_invalid(self):
        """Test avec valeur invalide."""
        assert parse_xuid_input("abc123") is None
        assert parse_xuid_input("xuid(abc)") is None
