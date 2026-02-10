#!/usr/bin/env python3
"""Script de test pour valider la persistance des filtres par joueur/DB.

Ce script teste que :
1. Chaque joueur/DB a ses propres filtres persistés
2. Les filtres sont correctement chargés lors du changement de joueur
3. Les filtres ne se mélangent pas entre les joueurs
"""

from __future__ import annotations

# Forcer UTF-8 pour l'encodage des sorties
import io
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Mock streamlit avant l'import de filter_state
class MockStreamlit:
    class session_state(dict):
        def get(self, key, default=None):
            return dict.get(self, key, default)

    @staticmethod
    def warning(msg):
        print(f"WARNING: {msg}")


import sys

sys.modules["streamlit"] = MockStreamlit()

# Import direct pour éviter les dépendances (pandas, etc.)
import importlib.util

filter_state_path = project_root / "src" / "ui" / "filter_state.py"
spec = importlib.util.spec_from_file_location("filter_state", filter_state_path)
filter_state = importlib.util.module_from_spec(spec)
sys.modules["filter_state"] = filter_state
spec.loader.exec_module(filter_state)

from filter_state import (
    FilterPreferences,
    _get_player_key,
    load_filter_preferences,
    save_filter_preferences,
)


def test_player_key_generation():
    """Test que la génération de clé de joueur fonctionne correctement."""
    print("Test 1: Génération de clé de joueur")

    # Test avec DuckDB v4 path
    db_path_v4 = "data/players/MyGamertag/stats.duckdb"
    key_v4 = _get_player_key("dummy_xuid", db_path_v4)
    assert key_v4 == "player_MyGamertag", f"Attendu 'player_MyGamertag', obtenu '{key_v4}'"
    print("  [OK] Cle DuckDB v4 correcte")

    # Test avec xuid seulement
    key_xuid = _get_player_key("123456789", None)
    assert key_xuid == "xuid_123456789", f"Attendu 'xuid_123456789', obtenu '{key_xuid}'"
    print("  [OK] Cle XUID correcte")

    # Test que deux joueurs différents ont des clés différentes
    key1 = _get_player_key("player1", "data/players/Player1/stats.duckdb")
    key2 = _get_player_key("player2", "data/players/Player2/stats.duckdb")
    assert key1 != key2, "Les cles doivent etre differentes pour des joueurs differents"
    print("  [OK] Cles differentes pour joueurs differents")


def test_filter_isolation_between_players():
    """Test que les filtres sont isolés entre différents joueurs."""
    print("\nTest 2: Isolation des filtres entre joueurs")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Utiliser le module filter_state déjà importé (mocké)
        original_get_filters_dir = filter_state._get_filters_dir
        filters_dir = Path(tmpdir) / "filter_preferences"
        filters_dir.mkdir(parents=True, exist_ok=True)

        def mock_get_filters_dir():
            return filters_dir

        filter_state._get_filters_dir = mock_get_filters_dir

        try:
            # Joueur A : Filtres spécifiques
            player_a_xuid = "player_a"
            player_a_db = "data/players/PlayerA/stats.duckdb"
            prefs_a = FilterPreferences(
                filter_mode="Période",
                start_date="2024-01-01",
                end_date="2024-01-31",
                playlists_selected=["Partie rapide", "Arène classée"],
                modes_selected=["Assassin"],
            )
            save_filter_preferences(player_a_xuid, player_a_db, prefs_a)

            # Joueur B : Filtres différents
            player_b_xuid = "player_b"
            player_b_db = "data/players/PlayerB/stats.duckdb"
            prefs_b = FilterPreferences(
                filter_mode="Sessions",
                gap_minutes=60,
                playlists_selected=["Firefight"],
                maps_selected=["Carte1", "Carte2"],
            )
            save_filter_preferences(player_b_xuid, player_b_db, prefs_b)

            # Vérifier que les fichiers sont différents
            key_a = _get_player_key(player_a_xuid, player_a_db)
            key_b = _get_player_key(player_b_xuid, player_b_db)
            file_a = filters_dir / f"{key_a}.json"
            file_b = filters_dir / f"{key_b}.json"

            assert file_a.exists(), f"Fichier pour joueur A non créé: {file_a}"
            assert file_b.exists(), f"Fichier pour joueur B non créé: {file_b}"
            assert file_a != file_b, "Les fichiers doivent être différents"
            print("  [OK] Fichiers de filtres separes crees")

            # Charger les filtres de chaque joueur
            loaded_a = load_filter_preferences(player_a_xuid, player_a_db)
            loaded_b = load_filter_preferences(player_b_xuid, player_b_db)

            assert loaded_a is not None, "Filtres du joueur A non chargés"
            assert loaded_b is not None, "Filtres du joueur B non chargés"

            # Vérifier que les filtres sont différents
            assert loaded_a.filter_mode == "Période", "Joueur A doit avoir mode Période"
            assert loaded_b.filter_mode == "Sessions", "Joueur B doit avoir mode Sessions"
            # Les playlists sont triées lors de la sauvegarde
            assert set(loaded_a.playlists_selected) == {
                "Arène classée",
                "Partie rapide",
            }, f"Playlists joueur A incorrectes: {loaded_a.playlists_selected}"
            assert loaded_b.playlists_selected == ["Firefight"], "Playlists joueur B incorrectes"
            assert loaded_a.modes_selected == ["Assassin"], "Modes joueur A incorrects"
            assert loaded_b.modes_selected is None, "Modes joueur B doivent etre None"
            assert loaded_a.maps_selected is None, "Cartes joueur A doivent etre None"
            # Les cartes sont triées lors de la sauvegarde
            assert set(loaded_b.maps_selected) == {
                "Carte1",
                "Carte2",
            }, f"Cartes joueur B incorrectes: {loaded_b.maps_selected}"

            print("  [OK] Filtres isoles correctement entre joueurs")

        finally:
            filter_state._get_filters_dir = original_get_filters_dir


def test_filter_loading_on_player_change():
    """Test que les filtres sont correctement chargés lors du changement de joueur."""
    print("\nTest 3: Chargement des filtres lors du changement de joueur")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Utiliser le module filter_state déjà importé (mocké)
        original_get_filters_dir = filter_state._get_filters_dir
        filters_dir = Path(tmpdir) / "filter_preferences"
        filters_dir.mkdir(parents=True, exist_ok=True)

        def mock_get_filters_dir():
            return filters_dir

        filter_state._get_filters_dir = mock_get_filters_dir

        try:
            # Créer des filtres pour deux joueurs
            player_a_xuid = "player_a"
            player_a_db = "data/players/PlayerA/stats.duckdb"
            prefs_a = FilterPreferences(
                filter_mode="Période",
                start_date="2024-01-15",
                end_date="2024-01-20",
                playlists_selected=["Partie rapide"],
            )
            save_filter_preferences(player_a_xuid, player_a_db, prefs_a)

            player_b_xuid = "player_b"
            player_b_db = "data/players/PlayerB/stats.duckdb"
            prefs_b = FilterPreferences(
                filter_mode="Sessions",
                gap_minutes=120,
                picked_session_label="Session 1",
            )
            save_filter_preferences(player_b_xuid, player_b_db, prefs_b)

            # Simuler un changement de joueur : charger A puis B puis A à nouveau
            loaded_a1 = load_filter_preferences(player_a_xuid, player_a_db)
            assert loaded_a1.filter_mode == "Période", "Premier chargement A incorrect"

            loaded_b = load_filter_preferences(player_b_xuid, player_b_db)
            assert loaded_b.filter_mode == "Sessions", "Chargement B incorrect"

            loaded_a2 = load_filter_preferences(player_a_xuid, player_a_db)
            assert loaded_a2.filter_mode == "Période", "Rechargement A incorrect"
            assert loaded_a2.start_date == "2024-01-15", "Dates A incorrectes après rechargement"
            assert loaded_a2.end_date == "2024-01-20", "Dates A incorrectes après rechargement"

            print("  [OK] Filtres correctement restaures lors du changement de joueur")

        finally:
            filter_state._get_filters_dir = original_get_filters_dir


def test_filter_save_and_load_consistency():
    """Test que sauvegarde puis chargement restaure les mêmes valeurs."""
    print("\nTest 4: Cohérence sauvegarde/chargement")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Utiliser le module filter_state déjà importé (mocké)
        original_get_filters_dir = filter_state._get_filters_dir
        filters_dir = Path(tmpdir) / "filter_preferences"
        filters_dir.mkdir(parents=True, exist_ok=True)

        def mock_get_filters_dir():
            return filters_dir

        filter_state._get_filters_dir = mock_get_filters_dir

        try:
            xuid = "test_player"
            db_path = "data/players/TestPlayer/stats.duckdb"

            # Créer des préférences complètes
            original_prefs = FilterPreferences(
                filter_mode="Période",
                start_date="2024-02-01",
                end_date="2024-02-28",
                gap_minutes=90,
                picked_session_label="Dernière session",
                playlists_selected=["Partie rapide", "Arène classée", "Assassin classé"],
                modes_selected=["Assassin", "Slayer"],
                maps_selected=["Carte1", "Carte2", "Carte3"],
            )

            # Sauvegarder
            save_filter_preferences(xuid, db_path, original_prefs)

            # Charger
            loaded_prefs = load_filter_preferences(xuid, db_path)

            assert loaded_prefs is not None, "Préférences non chargées"
            assert loaded_prefs.filter_mode == original_prefs.filter_mode
            assert loaded_prefs.start_date == original_prefs.start_date
            assert loaded_prefs.end_date == original_prefs.end_date
            assert loaded_prefs.gap_minutes == original_prefs.gap_minutes
            assert loaded_prefs.picked_session_label == original_prefs.picked_session_label
            assert loaded_prefs.playlists_selected == original_prefs.playlists_selected
            assert loaded_prefs.modes_selected == original_prefs.modes_selected
            assert loaded_prefs.maps_selected == original_prefs.maps_selected

            print("  [OK] Coherence sauvegarde/chargement validee")

        finally:
            filter_state._get_filters_dir = original_get_filters_dir


def test_multiple_players_same_session():
    """Test que plusieurs joueurs peuvent coexister sans interférence."""
    print("\nTest 5: Coexistence de plusieurs joueurs")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Utiliser le module filter_state déjà importé (mocké)
        original_get_filters_dir = filter_state._get_filters_dir
        filters_dir = Path(tmpdir) / "filter_preferences"
        filters_dir.mkdir(parents=True, exist_ok=True)

        def mock_get_filters_dir():
            return filters_dir

        filter_state._get_filters_dir = mock_get_filters_dir

        try:
            # Créer des filtres pour 3 joueurs différents
            players = [
                ("player1", "data/players/Player1/stats.duckdb", ["Partie rapide"]),
                ("player2", "data/players/Player2/stats.duckdb", ["Arène classée"]),
                ("player3", "data/players/Player3/stats.duckdb", ["Firefight"]),
            ]

            for xuid, db_path, playlists in players:
                prefs = FilterPreferences(
                    filter_mode="Période",
                    playlists_selected=playlists,
                )
                save_filter_preferences(xuid, db_path, prefs)

            # Vérifier que chaque joueur a ses propres filtres
            for xuid, db_path, expected_playlists in players:
                loaded = load_filter_preferences(xuid, db_path)
                assert loaded is not None, f"Filtres non chargés pour {xuid}"
                assert (
                    loaded.playlists_selected == expected_playlists
                ), f"Playlists incorrectes pour {xuid}: {loaded.playlists_selected} != {expected_playlists}"

            print("  [OK] Plusieurs joueurs coexistent sans interference")

        finally:
            filter_state._get_filters_dir = original_get_filters_dir


def main():
    """Exécute tous les tests."""
    print("=" * 70)
    print("Tests de persistance des filtres par joueur/DB")
    print("=" * 70)
    print()

    try:
        test_player_key_generation()
        test_filter_isolation_between_players()
        test_filter_loading_on_player_change()
        test_filter_save_and_load_consistency()
        test_multiple_players_same_session()

        print()
        print("=" * 70)
        print("[SUCCESS] Tous les tests sont passes !")
        print("=" * 70)
        return 0

    except AssertionError as e:
        print()
        print("=" * 70)
        print(f"[FAIL] Echec du test: {e}")
        print("=" * 70)
        import traceback

        traceback.print_exc()
        return 1

    except Exception as e:
        print()
        print("=" * 70)
        print(f"[ERROR] Erreur inattendue: {e}")
        print("=" * 70)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
