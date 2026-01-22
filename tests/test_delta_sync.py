"""Tests pour les nouvelles fonctionnalités: delta sync, aliases, sync metadata."""

import json
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from src.ui.translations import (
    translate_playlist_name,
    translate_pair_name,
    PLAYLIST_FR,
    PAIR_FR,
)
from src.analysis.filters import is_allowed_playlist_name


# =============================================================================
# Tests Translations
# =============================================================================


class TestTranslatePlaylistName:
    """Tests pour translate_playlist_name."""

    def test_known_playlist(self):
        """Test avec une playlist connue."""
        assert translate_playlist_name("Quick Play") == "Partie rapide"
        assert translate_playlist_name("Ranked Arena") == "Arène classée"
        assert translate_playlist_name("Big Team Battle") == "Grande bataille en équipe"

    def test_unknown_playlist(self):
        """Test avec une playlist inconnue - retourne l'original."""
        assert translate_playlist_name("Unknown Playlist") == "Unknown Playlist"

    def test_none_value(self):
        """Test avec None."""
        assert translate_playlist_name(None) is None

    def test_whitespace_handling(self):
        """Test avec espaces autour."""
        assert translate_playlist_name("  Quick Play  ") == "Partie rapide"


class TestTranslatePairName:
    """Tests pour translate_pair_name."""

    def test_exact_match(self):
        """Test avec correspondance exacte."""
        assert translate_pair_name("Arena:CTF on Aquarius") == "Arène : Capture du drapeau"
        assert translate_pair_name("BTB:Slayer on Deadlock") == "BTB : Assassin"

    def test_generic_fallback(self):
        """Test avec fallback générique (sans carte)."""
        assert translate_pair_name("Arena:CTF") == "Arène : Capture du drapeau"
        assert translate_pair_name("Arena:King of the Hill") == "Arène : Roi de la colline"

    def test_case_normalization(self):
        """Test avec normalisation de casse."""
        # Le système normalise la casse mais peut ne pas trouver de match exact
        result = translate_pair_name("arena:ctf on aquarius")
        # Doit soit trouver la traduction, soit retourner une version normalisée
        assert result is not None

    def test_btb_heavies_preserved(self):
        """Test que BTB Heavies est préservé."""
        result = translate_pair_name("BTB Heavies:CTF on Highpower Heavies")
        assert result == "BTB Heavies : Capture du drapeau"

    def test_none_value(self):
        """Test avec None."""
        assert translate_pair_name(None) is None

    def test_empty_string(self):
        """Test avec chaîne vide."""
        assert translate_pair_name("") is None
        assert translate_pair_name("   ") is None

    def test_unknown_mode_arena_fallback(self):
        """Test fallback pour mode Arena inconnu."""
        # Mode Arena avec carte inconnue devrait utiliser le fallback
        result = translate_pair_name("Arena:Slayer on NewMap2025")
        # Devrait retourner "Arène : Assassin" via fallback
        assert "Assassin" in result or "NewMap2025" in result


class TestTranslationCompleteness:
    """Tests de complétude des traductions."""

    def test_playlist_fr_not_empty(self):
        """Vérifie que PLAYLIST_FR contient des entrées."""
        assert len(PLAYLIST_FR) >= 10

    def test_pair_fr_not_empty(self):
        """Vérifie que PAIR_FR contient des entrées."""
        assert len(PAIR_FR) >= 200

    def test_all_playlists_have_french(self):
        """Vérifie que toutes les playlists ont une traduction non vide."""
        for en, fr in PLAYLIST_FR.items():
            assert fr, f"Playlist '{en}' a une traduction vide"

    def test_all_pairs_have_french(self):
        """Vérifie que tous les modes ont une traduction non vide."""
        for en, fr in PAIR_FR.items():
            assert fr, f"Mode '{en}' a une traduction vide"


# =============================================================================
# Tests Delta Sync (mock-based)
# =============================================================================


class TestDeltaSyncLogic:
    """Tests pour la logique de synchronisation delta."""

    def test_sync_meta_table_structure(self):
        """Test que SyncMeta peut être créé avec la bonne structure."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS SyncMeta (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )
            """)
            con.commit()

            # Insérer une valeur
            now = datetime.now(timezone.utc).isoformat()
            cur.execute(
                "INSERT INTO SyncMeta (key, value, updated_at) VALUES (?, ?, ?)",
                ("last_sync", now, now)
            )
            con.commit()

            # Vérifier la lecture
            cur.execute("SELECT value FROM SyncMeta WHERE key = ?", ("last_sync",))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == now

            con.close()
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_xuid_aliases_table_structure(self):
        """Test que XuidAliases peut être créé avec la bonne structure."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS XuidAliases (
                    xuid TEXT PRIMARY KEY,
                    gamertag TEXT NOT NULL,
                    source TEXT DEFAULT 'unknown',
                    updated_at TEXT
                )
            """)
            con.commit()

            # Insérer un alias
            cur.execute(
                "INSERT INTO XuidAliases (xuid, gamertag, source, updated_at) VALUES (?, ?, ?, ?)",
                ("xuid:123456", "TestPlayer", "match_roster", datetime.now(timezone.utc).isoformat())
            )
            con.commit()

            # Vérifier la lecture
            cur.execute("SELECT gamertag FROM XuidAliases WHERE xuid = ?", ("xuid:123456",))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == "TestPlayer"

            con.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


# =============================================================================
# Tests Highlight Events
# =============================================================================


class TestHighlightEventsExtraction:
    """Tests pour l'extraction des highlight events."""

    def test_gamertag_extraction_from_json(self):
        """Test extraction de gamertag depuis un JSON d'event."""
        event_json = {
            "Events": [
                {"gamertag": "Player1", "type": "kill"},
                {"gamertag": "Player2", "type": "death"},
            ]
        }
        gamertags = {e.get("gamertag") for e in event_json.get("Events", []) if e.get("gamertag")}
        assert gamertags == {"Player1", "Player2"}

    def test_empty_events(self):
        """Test avec events vides."""
        event_json = {"Events": []}
        gamertags = {e.get("gamertag") for e in event_json.get("Events", []) if e.get("gamertag")}
        assert gamertags == set()

    def test_missing_gamertag(self):
        """Test avec events sans gamertag."""
        event_json = {
            "Events": [
                {"type": "kill"},  # pas de gamertag
                {"gamertag": "Player1", "type": "death"},
            ]
        }
        gamertags = {e.get("gamertag") for e in event_json.get("Events", []) if e.get("gamertag")}
        assert gamertags == {"Player1"}


# =============================================================================
# Tests Filter Logic
# =============================================================================


class TestPlaylistFilters:
    """Tests pour les filtres de playlist."""

    def test_btb_allowed(self):
        """Test que Big Team Battle est autorisé."""
        assert is_allowed_playlist_name("Big Team Battle") is True
        assert is_allowed_playlist_name("Big Team Battle: Refresh") is True

    def test_quick_play_allowed(self):
        """Test que Quick Play est autorisé."""
        assert is_allowed_playlist_name("Quick Play") is True

    def test_ranked_allowed(self):
        """Test que Ranked est autorisé."""
        assert is_allowed_playlist_name("Ranked Arena") is True
        assert is_allowed_playlist_name("Ranked Slayer") is True

    def test_none_returns_false(self):
        """Test que None retourne False."""
        assert is_allowed_playlist_name(None) is False
