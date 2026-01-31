#!/usr/bin/env python3
"""
Agent de nettoyage automatique du codebase.
(Automatic codebase cleanup agent)

HOW IT WORKS:
1. Supprime les fichiers temporaires (__pycache__, .pyc, .coverage, etc.)
2. Identifie les imports inutilisés (via ruff)
3. Détecte les fichiers Python orphelins (non importés)
4. Génère un rapport dans .ai/cleanup_report.md

Usage:
    python scripts/cleanup_codebase.py              # Mode dry-run (affiche seulement)
    python scripts/cleanup_codebase.py --fix       # Applique les corrections
    python scripts/cleanup_codebase.py --deep      # Analyse approfondie (dead code)
    python scripts/cleanup_codebase.py --fix --deep # Tout nettoyer

Automatisation (cron/task scheduler):
    # Linux/Mac - Ajouter à crontab (tous les jours à 3h)
    0 3 * * * cd /path/to/project && python scripts/cleanup_codebase.py --fix

    # Windows - Task Scheduler
    schtasks /create /tn "CleanupCodebase" /tr "python scripts/cleanup_codebase.py --fix" /sc daily /st 03:00
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TESTS_DIR = PROJECT_ROOT / "tests"
AI_DIR = PROJECT_ROOT / ".ai"

# Patterns de fichiers temporaires à supprimer
TEMP_PATTERNS = [
    "**/__pycache__",
    "**/*.pyc",
    "**/*.pyo",
    "**/*.pyd",
    "**/.pytest_cache",
    "**/.coverage",
    "**/.mypy_cache",
    "**/.ruff_cache",
    "**/*.egg-info",
    "**/dist",
    "**/build",
    "**/.eggs",
    "**/*.log",
    "**/tmp_*.sqlite",
    "**/tmp_*.db",
]

# Fichiers à ignorer pour l'analyse d'orphelins
IGNORE_FILES = {
    "__init__.py",
    "conftest.py",
    "streamlit_app.py",
}

# Dossiers à ignorer
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".ai",
    ".cursor",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


class CleanupStats(NamedTuple):
    """Statistiques de nettoyage."""

    temp_files_removed: int
    temp_dirs_removed: int
    bytes_freed: int
    unused_imports_fixed: int
    orphan_files: list[Path]
    dead_code_files: list[Path]


def format_size(size_bytes: int) -> str:
    """Formate une taille en bytes de manière lisible."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def remove_temp_files(dry_run: bool = True) -> tuple[int, int, int]:
    """
    Supprime les fichiers et dossiers temporaires.

    Returns:
        (fichiers supprimés, dossiers supprimés, bytes libérés)
    """
    files_removed = 0
    dirs_removed = 0
    bytes_freed = 0

    for pattern in TEMP_PATTERNS:
        for path in PROJECT_ROOT.glob(pattern):
            # Ignorer les dossiers exclus
            if any(ignore in path.parts for ignore in IGNORE_DIRS):
                continue

            try:
                if path.is_file():
                    size = path.stat().st_size
                    if not dry_run:
                        path.unlink()
                    files_removed += 1
                    bytes_freed += size
                    print(f"  {'[DRY]' if dry_run else '[DEL]'} {path.relative_to(PROJECT_ROOT)}")

                elif path.is_dir():
                    size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                    if not dry_run:
                        shutil.rmtree(path)
                    dirs_removed += 1
                    bytes_freed += size
                    print(f"  {'[DRY]' if dry_run else '[DEL]'} {path.relative_to(PROJECT_ROOT)}/")

            except Exception as e:
                print(f"  [ERR] {path}: {e}")

    return files_removed, dirs_removed, bytes_freed


def fix_unused_imports(dry_run: bool = True) -> int:
    """
    Corrige les imports inutilisés avec ruff.

    Returns:
        Nombre de fichiers corrigés
    """
    # Vérifier que ruff est installé
    try:
        subprocess.run(["ruff", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  [WARN] ruff n'est pas installé. Installez-le avec: pip install ruff")
        return 0

    # Lancer ruff pour détecter les imports inutilisés
    args = ["ruff", "check", str(SRC_DIR), str(SCRIPTS_DIR), "--select=F401"]

    if not dry_run:
        args.append("--fix")

    try:
        result = subprocess.run(args, capture_output=True, text=True)

        # Compter les lignes de sortie (approximation des corrections)
        lines = [line for line in result.stdout.splitlines() if "F401" in line]

        for line in lines[:20]:  # Limiter l'affichage
            print(f"  {'[DRY]' if dry_run else '[FIX]'} {line}")

        if len(lines) > 20:
            print(f"  ... et {len(lines) - 20} autres")

        return len(lines)

    except Exception as e:
        print(f"  [ERR] ruff: {e}")
        return 0


def find_orphan_files() -> list[Path]:
    """
    Identifie les fichiers Python qui ne sont jamais importés.

    Returns:
        Liste des fichiers potentiellement orphelins
    """
    orphans = []

    # Collecter tous les fichiers Python
    all_py_files = set()
    for directory in [SRC_DIR, SCRIPTS_DIR]:
        if directory.exists():
            all_py_files.update(directory.rglob("*.py"))

    # Collecter tous les imports dans le projet
    imported_modules = set()

    for py_file in all_py_files:
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")

            # Extraire les imports (simpliste mais efficace)
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("from ") or line.startswith("import "):
                    # Extraire le nom du module
                    parts = line.replace("from ", "").replace("import ", "").split()
                    if parts:
                        module_name = parts[0].split(".")[0]
                        imported_modules.add(module_name)

                        # Ajouter le chemin complet pour les imports relatifs
                        if "." in parts[0]:
                            full_path = parts[0].replace(".", "/")
                            imported_modules.add(full_path)

        except Exception:
            pass

    # Vérifier chaque fichier
    for py_file in all_py_files:
        if py_file.name in IGNORE_FILES:
            continue

        # Ignorer les fichiers dans les dossiers exclus
        if any(ignore in py_file.parts for ignore in IGNORE_DIRS):
            continue

        # Vérifier si le fichier est importé
        rel_path = py_file.relative_to(PROJECT_ROOT)
        module_path = str(rel_path.with_suffix("")).replace(os.sep, "/").replace("/", ".")

        # Simplifier le chemin
        simple_name = py_file.stem
        parent_name = py_file.parent.name

        is_imported = (
            simple_name in imported_modules
            or parent_name in imported_modules
            or module_path in imported_modules
            or any(module_path.endswith(f".{m}") for m in imported_modules)
        )

        if not is_imported:
            # Vérifier si c'est un script CLI (a un if __name__ == "__main__")
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                if 'if __name__ == "__main__"' in content or "if __name__ == '__main__'" in content:
                    continue  # C'est un script CLI, pas orphelin
            except Exception:
                pass

            orphans.append(py_file)

    return orphans


def find_dead_code() -> list[Path]:
    """
    Utilise vulture pour détecter le code mort.

    Returns:
        Liste des fichiers avec du code potentiellement mort
    """
    try:
        subprocess.run(["vulture", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  [INFO] vulture n'est pas installé. Installez-le avec: pip install vulture")
        return []

    try:
        result = subprocess.run(
            ["vulture", str(SRC_DIR), "--min-confidence=80"],
            capture_output=True,
            text=True,
        )

        dead_files = set()
        for line in result.stdout.splitlines():
            if ".py:" in line:
                file_path = line.split(":")[0]
                dead_files.add(Path(file_path))
                print(f"  [DEAD] {line}")

        return list(dead_files)

    except Exception as e:
        print(f"  [ERR] vulture: {e}")
        return []


def generate_report(stats: CleanupStats, dry_run: bool) -> None:
    """Génère le rapport de nettoyage dans .ai/cleanup_report.md."""

    AI_DIR.mkdir(parents=True, exist_ok=True)
    report_path = AI_DIR / "cleanup_report.md"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode = "DRY-RUN" if dry_run else "APPLIED"

    content = f"""# Rapport de Nettoyage - {now}

> Mode: **{mode}**

## Résumé

| Métrique | Valeur |
|----------|--------|
| Fichiers temp supprimés | {stats.temp_files_removed} |
| Dossiers temp supprimés | {stats.temp_dirs_removed} |
| Espace libéré | {format_size(stats.bytes_freed)} |
| Imports inutilisés corrigés | {stats.unused_imports_fixed} |
| Fichiers orphelins détectés | {len(stats.orphan_files)} |
| Fichiers avec code mort | {len(stats.dead_code_files)} |

## Fichiers Orphelins (non importés)

"""

    if stats.orphan_files:
        content += "Ces fichiers Python ne semblent jamais être importés. Vérifiez s'ils sont encore nécessaires :\n\n"
        for f in stats.orphan_files:
            content += f"- `{f.relative_to(PROJECT_ROOT)}`\n"
    else:
        content += "_Aucun fichier orphelin détecté._\n"

    content += "\n## Code Mort Potentiel\n\n"

    if stats.dead_code_files:
        content += (
            "Ces fichiers contiennent des fonctions/classes potentiellement non utilisées :\n\n"
        )
        for f in stats.dead_code_files:
            content += f"- `{f.relative_to(PROJECT_ROOT)}`\n"
    else:
        content += "_Aucun code mort détecté (ou vulture non installé)._\n"

    content += """
## Actions Recommandées

1. **Revoir les fichiers orphelins** : Supprimer ou archiver si non utilisés
2. **Analyser le code mort** : Supprimer les fonctions non appelées
3. **Lancer les tests** : `pytest tests/ -v` après nettoyage

---

*Rapport généré automatiquement par `scripts/cleanup_codebase.py`*
"""

    report_path.write_text(content, encoding="utf-8")
    print(f"\n[OK] Rapport généré: {report_path.relative_to(PROJECT_ROOT)}")


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Agent de nettoyage automatique du codebase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Applique les corrections (sinon dry-run)",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Analyse approfondie (détection code mort avec vulture)",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Ne pas générer le rapport .ai/cleanup_report.md",
    )

    args = parser.parse_args()
    dry_run = not args.fix

    print("=" * 60)
    print(f"[CLEANUP] Agent de Nettoyage - {'DRY-RUN' if dry_run else 'MODE FIX'}")
    print("=" * 60)

    # 1. Fichiers temporaires
    print("\n[1/4] Suppression des fichiers temporaires...")
    files_rm, dirs_rm, bytes_freed = remove_temp_files(dry_run)
    print(f"  -> {files_rm} fichiers, {dirs_rm} dossiers, {format_size(bytes_freed)} liberes")

    # 2. Imports inutilisés
    print("\n[2/4] Correction des imports inutilisés (ruff)...")
    imports_fixed = fix_unused_imports(dry_run)
    print(f"  -> {imports_fixed} imports a corriger")

    # 3. Fichiers orphelins
    print("\n[3/4] Détection des fichiers orphelins...")
    orphans = find_orphan_files()
    for f in orphans[:10]:
        print(f"  [ORPHAN] {f.relative_to(PROJECT_ROOT)}")
    if len(orphans) > 10:
        print(f"  ... et {len(orphans) - 10} autres")
    print(f"  -> {len(orphans)} fichiers potentiellement orphelins")

    # 4. Code mort (optionnel)
    dead_files: list[Path] = []
    if args.deep:
        print("\n[4/4] Détection du code mort (vulture)...")
        dead_files = find_dead_code()
        print(f"  -> {len(dead_files)} fichiers avec code potentiellement mort")
    else:
        print("\n[4/4] Détection du code mort... [SKIP] (utilisez --deep)")

    # Générer le rapport
    if not args.no_report:
        stats = CleanupStats(
            temp_files_removed=files_rm,
            temp_dirs_removed=dirs_rm,
            bytes_freed=bytes_freed,
            unused_imports_fixed=imports_fixed,
            orphan_files=orphans,
            dead_code_files=dead_files,
        )
        generate_report(stats, dry_run)

    # Résumé final
    print("\n" + "=" * 60)
    if dry_run:
        print("[OK] Dry-run termine. Utilisez --fix pour appliquer les corrections.")
    else:
        print("[OK] Nettoyage termine !")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
