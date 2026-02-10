#!/usr/bin/env python3
"""
Agent de test intelligent.
(Smart test agent)

HOW IT WORKS:
1. Détecte les fichiers modifiés (git diff)
2. Mappe les fichiers sources vers leurs tests
3. Lance les tests ciblés en priorité
4. Lance la suite complète si tests ciblés OK
5. Génère un rapport de couverture

Usage:
    python scripts/smart_test.py              # Tests ciblés (fichiers modifiés)
    python scripts/smart_test.py --quick      # Tests rapides uniquement
    python scripts/smart_test.py --full       # Suite complète avec couverture
    python scripts/smart_test.py --file src/analysis/stats.py  # Tests pour un fichier
    python scripts/smart_test.py --watch      # Mode watch (relance sur changements)

Automatisation:
    - Pre-push hook: tests rapides avant push
    - CI/CD: suite complète sur PR
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
TESTS_DIR = PROJECT_ROOT / "tests"
AI_DIR = PROJECT_ROOT / ".ai"

# Mapping source → test
# Format: préfixe du fichier source → pattern de test
SOURCE_TO_TEST_MAP = {
    "src/analysis/": "tests/test_analysis.py",
    "src/data/query/": "tests/test_query_module.py",
    "src/data/domain/models/": "tests/test_models.py",
    "src/db/parsers": "tests/test_parsers.py",
    "src/app/": "tests/test_app_module.py",
    "src/ui/": "tests/test_app_module.py",
}


class TestResult(NamedTuple):
    """Résultat d'exécution de tests."""

    passed: int
    failed: int
    skipped: int
    duration_seconds: float
    coverage_percent: float | None
    failed_tests: list[str]


def get_modified_files() -> list[Path]:
    """
    Récupère les fichiers Python modifiés depuis le dernier commit.

    Returns:
        Liste des fichiers modifiés
    """
    try:
        # Fichiers modifiés (staged + unstaged)
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        files = []
        for line in result.stdout.splitlines():
            if line.endswith(".py"):
                path = PROJECT_ROOT / line
                if path.exists():
                    files.append(path)

        # Ajouter les fichiers non trackés
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        for line in result.stdout.splitlines():
            if line.endswith(".py"):
                path = PROJECT_ROOT / line
                if path.exists() and path not in files:
                    files.append(path)

        return files

    except Exception as e:
        print(f"[WARN] Impossible de récupérer les fichiers modifiés: {e}")
        return []


def map_source_to_tests(source_files: list[Path]) -> set[str]:
    """
    Mappe les fichiers sources vers les fichiers de test correspondants.

    Args:
        source_files: Liste des fichiers sources modifiés

    Returns:
        Ensemble des fichiers de test à exécuter
    """
    tests_to_run = set()

    for source in source_files:
        rel_path = str(source.relative_to(PROJECT_ROOT)).replace("\\", "/")

        # Vérifier le mapping explicite
        for prefix, test_file in SOURCE_TO_TEST_MAP.items():
            if rel_path.startswith(prefix):
                test_path = PROJECT_ROOT / test_file
                if test_path.exists():
                    tests_to_run.add(str(test_path))
                break
        else:
            # Fallback: chercher un test avec le même nom
            if rel_path.startswith("src/"):
                # src/analysis/stats.py → tests/test_stats.py
                test_name = f"test_{source.stem}.py"
                potential_test = TESTS_DIR / test_name
                if potential_test.exists():
                    tests_to_run.add(str(potential_test))

    return tests_to_run


def run_tests(
    test_paths: list[str] | None = None,
    quick: bool = False,
    with_coverage: bool = False,
    verbose: bool = True,
) -> TestResult:
    """
    Exécute les tests pytest.

    Args:
        test_paths: Chemins des tests à exécuter (None = tous)
        quick: Exclure les tests lents
        with_coverage: Générer un rapport de couverture
        verbose: Afficher la sortie pytest

    Returns:
        Résultat des tests
    """
    args = ["pytest"]

    # Chemins des tests
    if test_paths:
        args.extend(test_paths)
    else:
        args.append(str(TESTS_DIR))

    # Options
    args.extend(["-v", "--tb=short"])

    if quick:
        args.extend(["-m", "not slow and not integration", "-x"])

    if with_coverage:
        args.extend(
            [
                "--cov=src",
                "--cov-report=term-missing",
                "--cov-report=html:htmlcov",
                "--cov-fail-under=0",  # Ne pas échouer sur couverture
            ]
        )

    start_time = time.time()

    try:
        result = subprocess.run(
            args,
            capture_output=not verbose,
            text=True,
            cwd=PROJECT_ROOT,
        )

        duration = time.time() - start_time

        # Parser la sortie pour extraire les stats
        output = result.stdout if not verbose else ""

        # Valeurs par défaut
        passed, failed, skipped = 0, 0, 0
        coverage = None
        failed_tests = []

        # Essayer de parser la sortie pytest
        if not verbose:
            for line in output.splitlines():
                if "passed" in line or "failed" in line:
                    # Format: "5 passed, 2 failed, 1 skipped"
                    import re

                    match = re.search(r"(\d+) passed", line)
                    if match:
                        passed = int(match.group(1))
                    match = re.search(r"(\d+) failed", line)
                    if match:
                        failed = int(match.group(1))
                    match = re.search(r"(\d+) skipped", line)
                    if match:
                        skipped = int(match.group(1))

                if "TOTAL" in line and "%" in line:
                    # Format coverage: "TOTAL    1000    200    80%"
                    import re

                    match = re.search(r"(\d+)%", line)
                    if match:
                        coverage = float(match.group(1))

                if "FAILED" in line:
                    failed_tests.append(line.strip())

        return TestResult(
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_seconds=duration,
            coverage_percent=coverage,
            failed_tests=failed_tests,
        )

    except Exception as e:
        print(f"[ERR] Erreur lors de l'exécution des tests: {e}")
        return TestResult(0, 1, 0, 0.0, None, [str(e)])


def run_smart_tests(
    quick: bool = False,
    full: bool = False,
    file_path: str | None = None,
    watch: bool = False,
) -> int:
    """
    Exécute les tests de manière intelligente.

    Args:
        quick: Tests rapides uniquement
        full: Suite complète avec couverture
        file_path: Fichier spécifique à tester
        watch: Mode watch

    Returns:
        Code de sortie (0 = succès)
    """
    print("=" * 60)
    print("[TEST] Agent de Test Intelligent")
    print("=" * 60)

    if file_path:
        # Test d'un fichier spécifique
        print(f"\n[1/1] Tests pour: {file_path}")
        source = Path(file_path)
        if source.exists():
            tests = map_source_to_tests([source])
            if tests:
                print(f"  -> Tests trouves: {', '.join(tests)}")
                result = run_tests(list(tests), quick=quick, verbose=True)
            else:
                print("  -> Aucun test mappe, lancement de tous les tests...")
                result = run_tests(quick=quick, verbose=True)
        else:
            print(f"  [ERR] Fichier non trouvé: {file_path}")
            return 1

    elif full:
        # Suite complète
        print("\n[1/1] Suite complète avec couverture...")
        result = run_tests(with_coverage=True, verbose=True)

    elif quick:
        # Tests rapides
        print("\n[1/1] Tests rapides (marqueur: not slow)...")
        result = run_tests(quick=True, verbose=True)

    else:
        # Mode intelligent: tests ciblés puis complets
        modified = get_modified_files()

        if modified:
            print(f"\n[1/2] Fichiers modifiés détectés: {len(modified)}")
            for f in modified[:5]:
                print(f"  - {f.relative_to(PROJECT_ROOT)}")
            if len(modified) > 5:
                print(f"  ... et {len(modified) - 5} autres")

            targeted_tests = map_source_to_tests(modified)

            if targeted_tests:
                print(f"\n[2/2] Tests ciblés: {len(targeted_tests)} fichiers")
                result = run_tests(list(targeted_tests), verbose=True)

                if result.failed == 0:
                    print("\n[OK] Tests cibles OK, vous pouvez commit/push.")
                    print("  (Utilisez --full pour la suite complète)")
            else:
                print("\n[2/2] Aucun test mappé, tests rapides...")
                result = run_tests(quick=True, verbose=True)
        else:
            print("\n[1/1] Aucun fichier modifié, tests rapides...")
            result = run_tests(quick=True, verbose=True)

    # Résumé final
    print("\n" + "=" * 60)
    print("RÉSUMÉ")
    print("=" * 60)

    status = "[OK] SUCCES" if result.failed == 0 else "[FAIL] ECHEC"
    print(f"\n{status}")
    print(f"  Passés: {result.passed}")
    print(f"  Échoués: {result.failed}")
    print(f"  Ignorés: {result.skipped}")
    print(f"  Durée: {result.duration_seconds:.1f}s")

    if result.coverage_percent is not None:
        print(f"  Couverture: {result.coverage_percent:.1f}%")

    if result.failed_tests:
        print("\n[FAIL] Tests echoues:")
        for test in result.failed_tests[:10]:
            print(f"  - {test}")

    return 0 if result.failed == 0 else 1


def watch_mode():
    """Mode watch: relance les tests sur changements."""
    print("[WATCH] Mode watch active. Ctrl+C pour arreter.")
    print("   Les tests seront relancés à chaque modification.\n")

    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        print("[ERR] watchdog n'est pas installé.")
        print("      pip install watchdog")
        return 1

    class TestHandler(FileSystemEventHandler):
        def __init__(self):
            self.last_run = 0
            self.debounce_seconds = 2

        def on_modified(self, event):
            if not event.src_path.endswith(".py"):
                return

            now = time.time()
            if now - self.last_run < self.debounce_seconds:
                return

            self.last_run = now
            print(f"\n[CHANGE] Changement detecte: {event.src_path}")
            run_smart_tests()

    handler = TestHandler()
    observer = Observer()
    observer.schedule(handler, str(SRC_DIR), recursive=True)
    observer.schedule(handler, str(TESTS_DIR), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
    return 0


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Agent de test intelligent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--quick",
        "-q",
        action="store_true",
        help="Tests rapides uniquement (exclut slow, integration)",
    )
    parser.add_argument(
        "--full",
        "-f",
        action="store_true",
        help="Suite complète avec couverture",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Tester un fichier source spécifique",
    )
    parser.add_argument(
        "--watch",
        "-w",
        action="store_true",
        help="Mode watch (relance sur changements)",
    )

    args = parser.parse_args()

    if args.watch:
        return watch_mode()

    return run_smart_tests(
        quick=args.quick,
        full=args.full,
        file_path=args.file,
    )


if __name__ == "__main__":
    sys.exit(main())
