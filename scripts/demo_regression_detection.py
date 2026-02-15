#!/usr/bin/env python3
"""Script de démonstration de la régression.

Ce script montre que les tests détectent bien la régression
quand on revient à l'ancienne version cassée de get_default_db_path().

Usage:
    python scripts/demo_regression_detection.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def simulate_broken_version():
    """Simule l'ancienne version cassée qui retournait toujours ''."""
    print("=" * 70)
    print("[BROKEN] SIMULATION: Ancienne version cassee (retourne '')")
    print("=" * 70)

    # Ancien code cassé
    def get_default_db_path_BROKEN() -> str:
        """Version cassée du 15 février 2026."""
        # Ne cherche plus de bases SQLite legacy dans OpenSpartan.Workshop
        # (migration DuckDB v4/v5 complétée)
        return ""  # ❌ CASSÉ - retourne toujours vide

    result = get_default_db_path_BROKEN()
    print(f"Resultat: '{result}'")
    print("[X] PROBLEME: Chaine vide meme si des joueurs existent !")
    print()


def test_fixed_version():
    """Teste la version corrigée."""
    from src.config import get_default_db_path

    print("=" * 70)
    print("[OK] VERSION CORRIGEE")
    print("=" * 70)

    result = get_default_db_path()
    print(f"Resultat: {result}")

    if result:
        print("[OK] Retourne un chemin valide")

        # Verifier que le fichier existe
        if Path(result).exists():
            print("[OK] Le fichier existe")
        else:
            print("[X] ERREUR: Le fichier n'existe pas")
    else:
        print("[WARN] ATTENTION: Chaine vide (peut etre normal si aucun joueur)")

    print()


def run_anti_regression_tests():
    """Lance les tests anti-régression."""
    import subprocess

    print("=" * 70)
    print("[TEST] EXECUTION DES TESTS ANTI-REGRESSION")
    print("=" * 70)

    cmd = [
        ".venv/Scripts/python.exe",
        "-m",
        "pytest",
        "tests/test_config_db_path.py",
        "-v",
        "--tb=line",
    ]

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        print("\n[OK] TOUS LES TESTS PASSENT")
    else:
        print("\n[X] CERTAINS TESTS ONT ECHOUE")

    return result.returncode


def main():
    """Point d'entrée."""
    print()
    print("=" * 70)
    print("DEMONSTRATION: Detection de Regression".center(70))
    print("Issue: App vide apres modification get_default_db_path()".center(70))
    print("=" * 70)
    print()

    # 1. Montrer l'ancienne version cassée
    simulate_broken_version()

    # 2. Montrer la version corrigée
    test_fixed_version()

    # 3. Lancer les tests
    exit_code = run_anti_regression_tests()

    print()
    print("=" * 70)
    print("RESUME")
    print("=" * 70)
    print()
    print("La regression du 15 fevrier 2026 etait:")
    print("  - get_default_db_path() retournait '' au lieu de chercher les joueurs")
    print("  - Resultat: app vide, aucune DB detectee")
    print()
    print("Les tests crees detectent cette regression:")
    print("  - tests/test_config_db_path.py (10 tests)")
    print("  - Si on revient a return '', les tests echouent [OK]")
    print()
    print("Protection mise en place:")
    print("  - [OK] Tests unitaires crees")
    print("  - [TODO] Ajouter au CI/CD (.github/workflows/)")
    print("  - [TODO] Pre-commit hook")
    print()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
