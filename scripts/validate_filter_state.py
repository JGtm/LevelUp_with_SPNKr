#!/usr/bin/env python3
"""Script de validation manuelle pour le module filter_state.

Ce script teste les fonctionnalités de base du module filter_state
sans nécessiter pytest.
"""

from __future__ import annotations

# Ajouter le répertoire racine au path
import sys
import tempfile
from datetime import date
from pathlib import Path
from pathlib import Path as PathLib

project_root = PathLib(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ui.filter_state import (
    FilterPreferences,
    apply_filter_preferences,
    clear_filter_preferences,
    load_filter_preferences,
    save_filter_preferences,
)


def test_filter_preferences():
    """Test de la classe FilterPreferences."""
    print("Test 1: FilterPreferences.to_dict()")
    prefs = FilterPreferences(
        filter_mode="Période",
        start_date="2024-01-01",
        end_date="2024-01-31",
        playlists_selected=["Partie rapide", "Arène classée"],
    )
    result = prefs.to_dict()
    assert result["filter_mode"] == "Période"
    assert result["start_date"] == "2024-01-01"
    assert "gap_minutes" not in result  # None omis
    print("  ✓ OK")

    print("Test 2: FilterPreferences.from_dict()")
    data = {
        "filter_mode": "Sessions",
        "gap_minutes": 120,
        "playlists_selected": ["Partie rapide"],
    }
    prefs2 = FilterPreferences.from_dict(data)
    assert prefs2.filter_mode == "Sessions"
    assert prefs2.gap_minutes == 120
    assert prefs2.start_date is None
    print("  ✓ OK")


def test_persistence():
    """Test de persistance des filtres."""
    print("Test 3: Sauvegarde et chargement")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock _get_filters_dir pour utiliser le répertoire temporaire
        import src.ui.filter_state

        original_get_filters_dir = src.ui.filter_state._get_filters_dir
        filters_dir = Path(tmpdir) / "filter_preferences"
        filters_dir.mkdir(parents=True, exist_ok=True)

        def mock_get_filters_dir():
            return filters_dir

        src.ui.filter_state._get_filters_dir = mock_get_filters_dir

        try:
            prefs = FilterPreferences(
                filter_mode="Période",
                start_date="2024-01-15",
                end_date="2024-01-20",
                playlists_selected=["Partie rapide"],
            )

            # Sauvegarder
            save_filter_preferences("test_player", preferences=prefs)

            # Vérifier que le fichier existe
            file_path = filters_dir / "xuid_test_player.json"
            assert file_path.exists(), f"Fichier {file_path} non créé"

            # Charger
            loaded = load_filter_preferences("test_player")
            assert loaded is not None
            assert loaded.filter_mode == "Période"
            assert loaded.start_date == "2024-01-15"
            assert loaded.end_date == "2024-01-20"
            assert loaded.playlists_selected == ["Partie rapide"]
            print("  ✓ OK")

            # Test avec DuckDB v4 path
            print("Test 4: Sauvegarde avec chemin DuckDB v4")
            db_path = "data/players/MyGamertag/stats.duckdb"
            save_filter_preferences("dummy_xuid", db_path=db_path, preferences=prefs)
            file_path_v4 = filters_dir / "player_MyGamertag.json"
            assert file_path_v4.exists(), f"Fichier {file_path_v4} non créé"
            loaded_v4 = load_filter_preferences("dummy_xuid", db_path=db_path)
            assert loaded_v4 is not None
            assert loaded_v4.filter_mode == "Période"
            print("  ✓ OK")

            # Test suppression
            print("Test 5: Suppression des préférences")
            clear_filter_preferences("test_player")
            assert not file_path.exists(), "Fichier non supprimé"
            loaded_after_clear = load_filter_preferences("test_player")
            assert loaded_after_clear is None
            print("  ✓ OK")

        finally:
            src.ui.filter_state._get_filters_dir = original_get_filters_dir


def test_apply_preferences():
    """Test d'application des préférences."""
    print("Test 6: Application des préférences (mock session_state)")

    # Créer un mock session_state
    class MockSessionState(dict):
        pass

    original_st = None
    try:
        import streamlit as st

        original_st = st.session_state
    except ImportError:
        pass

    # Mock streamlit si disponible
    try:
        import streamlit as st

        st.session_state = MockSessionState()
    except ImportError:
        # Si streamlit n'est pas disponible, on skip ce test
        print("  ⚠ Skippé (streamlit non disponible)")
        return

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

        assert st.session_state["filter_mode"] == "Période"
        assert st.session_state["start_date_cal"] == date(2024, 1, 15)
        assert st.session_state["end_date_cal"] == date(2024, 1, 20)
        assert st.session_state["gap_minutes"] == 120
        assert st.session_state["picked_session_label"] == "Session 1"
        assert st.session_state["picked_sessions"] == ["Session 1"]
        assert st.session_state["filter_playlists"] == {"Partie rapide"}
        assert st.session_state["filter_modes"] == {"Assassin"}
        assert st.session_state["filter_maps"] == {"Carte 1"}
        print("  ✓ OK")
    finally:
        if original_st is not None:
            import streamlit as st

            st.session_state = original_st


def main():
    """Exécute tous les tests."""
    print("=" * 60)
    print("Validation du module filter_state")
    print("=" * 60)
    print()

    try:
        test_filter_preferences()
        test_persistence()
        test_apply_preferences()

        print()
        print("=" * 60)
        print("✓ Tous les tests sont passés !")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"✗ Échec du test: {e}")
        print("=" * 60)
        return 1
    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ Erreur inattendue: {e}")
        import traceback

        traceback.print_exc()
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
