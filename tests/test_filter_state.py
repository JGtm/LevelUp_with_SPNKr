"""Tests unitaires pour le module de persistance des filtres."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.ui.filter_state import (
    FilterPreferences,
    apply_filter_preferences,
    clear_filter_preferences,
    load_filter_preferences,
    save_filter_preferences,
)


class TestFilterPreferences:
    """Tests pour la classe FilterPreferences."""

    def test_to_dict(self):
        """Test de conversion en dictionnaire."""
        prefs = FilterPreferences(
            filter_mode="Période",
            start_date="2024-01-01",
            end_date="2024-01-31",
            playlists_selected=["Partie rapide", "Arène classée"],
        )
        result = prefs.to_dict()
        assert result["filter_mode"] == "Période"
        assert result["start_date"] == "2024-01-01"
        assert result["end_date"] == "2024-01-31"
        assert result["playlists_selected"] == ["Partie rapide", "Arène classée"]
        # Les valeurs None ne doivent pas être dans le dict
        assert "gap_minutes" not in result

    def test_to_dict_omits_none(self):
        """Test que les valeurs None sont omises."""
        prefs = FilterPreferences()
        result = prefs.to_dict()
        assert result == {}

    def test_from_dict(self):
        """Test de création depuis un dictionnaire."""
        data = {
            "filter_mode": "Sessions",
            "gap_minutes": 120,
            "playlists_selected": ["Partie rapide"],
        }
        prefs = FilterPreferences.from_dict(data)
        assert prefs.filter_mode == "Sessions"
        assert prefs.gap_minutes == 120
        assert prefs.playlists_selected == ["Partie rapide"]
        assert prefs.start_date is None

    def test_from_dict_ignores_unknown_keys(self):
        """Test que les clés inconnues sont ignorées."""
        data = {
            "filter_mode": "Période",
            "unknown_key": "value",
        }
        prefs = FilterPreferences.from_dict(data)
        assert prefs.filter_mode == "Période"
        # Vérifier que unknown_key n'a pas créé d'attribut
        assert not hasattr(prefs, "unknown_key")


class TestFilterPersistence:
    """Tests pour la persistance des filtres."""

    @pytest.fixture
    def temp_filters_dir(self, monkeypatch, tmp_path):
        """Crée un répertoire temporaire pour les filtres."""
        filters_dir = tmp_path / ".streamlit" / "filter_preferences"
        filters_dir.mkdir(parents=True, exist_ok=True)

        # Mock _get_filters_dir pour utiliser le répertoire temporaire
        def mock_get_filters_dir():
            return filters_dir

        monkeypatch.setattr("src.ui.filter_state._get_filters_dir", mock_get_filters_dir)
        return filters_dir

    def test_save_and_load_preferences(self, temp_filters_dir):
        """Test sauvegarde et chargement des préférences."""
        prefs = FilterPreferences(
            filter_mode="Période",
            start_date="2024-01-01",
            end_date="2024-01-31",
            playlists_selected=["Partie rapide", "Arène classée"],
            modes_selected=["Assassin"],
            maps_selected=["Carte 1"],
        )

        # Sauvegarder
        save_filter_preferences("test_player", preferences=prefs)

        # Charger
        loaded = load_filter_preferences("test_player")

        assert loaded is not None
        assert loaded.filter_mode == "Période"
        assert loaded.start_date == "2024-01-01"
        assert loaded.end_date == "2024-01-31"
        assert loaded.playlists_selected == ["Partie rapide", "Arène classée"]
        assert loaded.modes_selected == ["Assassin"]
        assert loaded.maps_selected == ["Carte 1"]

    def test_load_nonexistent_preferences(self, temp_filters_dir):
        """Test chargement de préférences inexistantes."""
        loaded = load_filter_preferences("nonexistent_player")
        assert loaded is None

    def test_save_with_duckdb_v4_path(self, temp_filters_dir):
        """Test sauvegarde avec chemin DuckDB v4."""
        prefs = FilterPreferences(filter_mode="Sessions", gap_minutes=120)
        db_path = "data/players/MyGamertag/stats.duckdb"

        save_filter_preferences("dummy_xuid", db_path=db_path, preferences=prefs)

        # Vérifier que le fichier a été créé avec la bonne clé
        file_path = temp_filters_dir / "player_MyGamertag.json"
        assert file_path.exists()

        loaded = load_filter_preferences("dummy_xuid", db_path=db_path)
        assert loaded is not None
        assert loaded.filter_mode == "Sessions"
        assert loaded.gap_minutes == 120

    def test_clear_preferences(self, temp_filters_dir):
        """Test suppression des préférences."""
        prefs = FilterPreferences(filter_mode="Période")
        save_filter_preferences("test_player", preferences=prefs)

        # Vérifier que le fichier existe
        file_path = temp_filters_dir / "xuid_test_player.json"
        assert file_path.exists()

        # Supprimer
        clear_filter_preferences("test_player")

        # Vérifier que le fichier n'existe plus
        assert not file_path.exists()

    def test_save_handles_invalid_data(self, temp_filters_dir):
        """Test que la sauvegarde gère les données invalides."""
        # Sauvegarder avec des données valides
        prefs = FilterPreferences(filter_mode="Période")
        save_filter_preferences("test_player", preferences=prefs)

        # Corrompre le fichier manuellement
        file_path = temp_filters_dir / "xuid_test_player.json"
        file_path.write_text("invalid json{")

        # Le chargement doit retourner None sans lever d'exception
        loaded = load_filter_preferences("test_player")
        assert loaded is None


class TestApplyFilterPreferences:
    """Tests pour l'application des préférences dans session_state."""

    def test_apply_preferences(self, monkeypatch):
        """Test application des préférences dans session_state."""
        # Mock streamlit.session_state
        session_state = {}

        def mock_getattr(obj, name):
            if name == "session_state":
                return session_state
            return getattr(obj, name)

        # Mock st.session_state
        import streamlit as st

        original_session_state = getattr(st, "session_state", None)
        monkeypatch.setattr(st, "session_state", session_state)

        try:
            prefs = FilterPreferences(
                filter_mode="Période",
                start_date="2024-01-15",
                end_date="2024-01-20",
                gap_minutes=120,
                picked_session_label="Session 1",
                playlists_selected=["Partie rapide"],
                modes_selected=["Assassin"],
                maps_selected=["Carte 1"],
            )

            apply_filter_preferences("test_player", preferences=prefs)

            assert session_state["filter_mode"] == "Période"
            assert session_state["start_date_cal"] == date(2024, 1, 15)
            assert session_state["end_date_cal"] == date(2024, 1, 20)
            assert session_state["gap_minutes"] == 120
            assert session_state["picked_session_label"] == "Session 1"
            assert session_state["picked_sessions"] == ["Session 1"]
            assert session_state["filter_playlists"] == {"Partie rapide"}
            assert session_state["filter_modes"] == {"Assassin"}
            assert session_state["filter_maps"] == {"Carte 1"}
        finally:
            if original_session_state is not None:
                monkeypatch.setattr(st, "session_state", original_session_state)

    def test_apply_preferences_with_toutes_session(self, monkeypatch):
        """Test application avec session '(toutes)'."""
        import streamlit as st

        session_state = {}
        original_session_state = getattr(st, "session_state", None)
        monkeypatch.setattr(st, "session_state", session_state)

        try:
            prefs = FilterPreferences(
                picked_session_label="(toutes)",
            )

            apply_filter_preferences("test_player", preferences=prefs)

            assert session_state["picked_session_label"] == "(toutes)"
            assert session_state["picked_sessions"] == []
        finally:
            if original_session_state is not None:
                monkeypatch.setattr(st, "session_state", original_session_state)

    def test_apply_preferences_handles_invalid_dates(self, monkeypatch):
        """Test que les dates invalides sont ignorées."""
        import streamlit as st

        session_state = {}
        original_session_state = getattr(st, "session_state", None)
        monkeypatch.setattr(st, "session_state", session_state)

        try:
            prefs = FilterPreferences(
                start_date="invalid-date",
                end_date="2024-01-20",
            )

            apply_filter_preferences("test_player", preferences=prefs)

            # start_date_cal ne doit pas être défini (date invalide)
            assert "start_date_cal" not in session_state
            # end_date_cal doit être défini (date valide)
            assert session_state["end_date_cal"] == date(2024, 1, 20)
        finally:
            if original_session_state is not None:
                monkeypatch.setattr(st, "session_state", original_session_state)

    def test_apply_none_preferences(self, monkeypatch):
        """Test application de None (ne fait rien)."""
        import streamlit as st

        session_state = {"existing_key": "existing_value"}
        original_session_state = getattr(st, "session_state", None)
        monkeypatch.setattr(st, "session_state", session_state)

        try:
            apply_filter_preferences("test_player", preferences=None)

            # Rien ne doit être modifié
            assert len(session_state) == 1
            assert session_state["existing_key"] == "existing_value"
        finally:
            if original_session_state is not None:
                monkeypatch.setattr(st, "session_state", original_session_state)


class TestPlayerKeyGeneration:
    """Tests pour la génération de clés de joueur."""

    def test_get_player_key_with_xuid(self):
        """Test génération de clé avec XUID."""
        from src.ui.filter_state import _get_player_key

        key = _get_player_key("123456789", None)
        assert key == "xuid_123456789"

    def test_get_player_key_with_duckdb_v4_path(self):
        """Test génération de clé avec chemin DuckDB v4."""
        from src.ui.filter_state import _get_player_key

        db_path = "data/players/MyGamertag/stats.duckdb"
        key = _get_player_key("dummy_xuid", db_path)
        assert key == "player_MyGamertag"

    def test_get_player_key_with_relative_path(self):
        """Test génération de clé avec chemin relatif."""
        from src.ui.filter_state import _get_player_key

        db_path = Path("data/players/TestPlayer/stats.duckdb")
        key = _get_player_key("dummy_xuid", str(db_path))
        assert key == "player_TestPlayer"

    def test_get_player_key_fallback_to_xuid(self):
        """Test fallback vers XUID si le chemin n'est pas DuckDB v4."""
        from src.ui.filter_state import _get_player_key

        db_path = "some/other/path.db"
        key = _get_player_key("123456789", db_path)
        assert key == "xuid_123456789"
