#!/usr/bin/env python3
"""Vérifie que l'extraction d'accuracy fonctionne correctement.

Ce script vérifie :
1. Si l'extraction d'accuracy dans transformers.py fonctionne
2. Si les données synchronisées ont bien accuracy
3. Propose des solutions si accuracy est NULL
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.data.sync.transformers import _extract_player_stats


def test_accuracy_extraction():
    """Test l'extraction d'accuracy avec des données de test."""
    print("=" * 80)
    print("TEST D'EXTRACTION D'ACCURACY")
    print("=" * 80)

    # Test 1: Structure normale avec Accuracy dans CoreStats
    test_player_1 = {
        "PlayerId": "xuid(2533274823110022)",
        "PlayerTeamStats": [
            {
                "Stats": {
                    "CoreStats": {
                        "Kills": 10,
                        "Deaths": 5,
                        "Assists": 3,
                        "Accuracy": 45.5,
                        "ShotsFired": 100,
                        "ShotsHit": 45,
                    }
                }
            }
        ],
    }

    kills, deaths, assists, accuracy = _extract_player_stats(test_player_1)
    print("\n✅ Test 1 - Structure normale:")
    print(f"   Kills: {kills}, Deaths: {deaths}, Assists: {assists}, Accuracy: {accuracy}")
    assert accuracy == 45.5, f"Accuracy devrait être 45.5, obtenu {accuracy}"

    # Test 2: Accuracy manquant (None)
    test_player_2 = {
        "PlayerId": "xuid(2533274823110022)",
        "PlayerTeamStats": [
            {
                "Stats": {
                    "CoreStats": {
                        "Kills": 10,
                        "Deaths": 5,
                        "Assists": 3,
                        # Pas d'Accuracy
                        "ShotsFired": 100,
                        "ShotsHit": 45,
                    }
                }
            }
        ],
    }

    kills, deaths, assists, accuracy = _extract_player_stats(test_player_2)
    print("\n⚠️  Test 2 - Accuracy manquant:")
    print(f"   Kills: {kills}, Deaths: {deaths}, Assists: {assists}, Accuracy: {accuracy}")
    assert accuracy is None, f"Accuracy devrait être None, obtenu {accuracy}"

    # Test 3: Structure alternative (Accuracy ailleurs)
    test_player_3 = {
        "PlayerId": "xuid(2533274823110022)",
        "PlayerTeamStats": [
            {
                "Stats": {
                    "CoreStats": {
                        "Kills": 10,
                        "Deaths": 5,
                        "Assists": 3,
                    },
                    "Accuracy": 50.0,  # Alternative location
                }
            }
        ],
    }

    kills, deaths, assists, accuracy = _extract_player_stats(test_player_3)
    print("\n⚠️  Test 3 - Accuracy dans Stats (pas CoreStats):")
    print(f"   Kills: {kills}, Deaths: {deaths}, Assists: {assists}, Accuracy: {accuracy}")
    # Ce test peut échouer si Accuracy n'est pas dans CoreStats

    # Test 4: Calcul depuis ShotsFired/ShotsHit si Accuracy manquant
    test_player_4 = {
        "PlayerId": "xuid(2533274823110022)",
        "PlayerTeamStats": [
            {
                "Stats": {
                    "CoreStats": {
                        "Kills": 10,
                        "Deaths": 5,
                        "Assists": 3,
                        "ShotsFired": 100,
                        "ShotsHit": 45,
                        # Pas d'Accuracy mais on peut calculer
                    }
                }
            }
        ],
    }

    kills, deaths, assists, accuracy = _extract_player_stats(test_player_4)
    print("\n⚠️  Test 4 - Calcul depuis ShotsFired/ShotsHit:")
    print(f"   Kills: {kills}, Deaths: {deaths}, Assists: {assists}, Accuracy: {accuracy}")
    print("   Note: Accuracy devrait être calculé depuis ShotsHit/ShotsFired si manquant")

    print("\n" + "=" * 80)
    print("CONCLUSION:")
    print("=" * 80)
    print("✅ L'extraction d'accuracy fonctionne si Accuracy est dans CoreStats")
    print("⚠️  Si accuracy est NULL dans la DB, vérifier:")
    print("   1. Les données JSON brutes contiennent-elles Accuracy?")
    print("   2. Les matchs ont-ils été synchronisés avec la bonne version du code?")
    print("   3. L'API retourne-t-elle toujours Accuracy?")
    print("\n💡 SOLUTION: Re-synchroniser les matchs si accuracy est NULL partout")


if __name__ == "__main__":
    try:
        test_accuracy_extraction()
        print("\n✅ Tous les tests passés!")
    except AssertionError as e:
        print(f"\n❌ Erreur: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
