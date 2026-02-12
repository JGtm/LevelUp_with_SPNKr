"""Healthcheck d'environnement pour LevelUp (Windows).

Objectif: vérifier rapidement qu'on exécute bien le projet avec l'environnement
Python officiel du repo (`.venv`) et que les packages critiques sont installés
avec des versions attendues.

Usage:
    python scripts/check_env.py

Exit codes:
    0: OK
    1: Erreur (mauvais env / package manquant / version incompatible)
"""

from __future__ import annotations

import os
import platform
import sys
from importlib import metadata
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _is_venv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _norm_path(p: str) -> str:
    try:
        return str(Path(p).resolve())
    except Exception:
        return p


def _print_kv(key: str, value: str) -> None:
    print(f"- {key}: {value}")


def _dist_version(dist_name: str) -> str | None:
    try:
        return metadata.version(dist_name)
    except metadata.PackageNotFoundError:
        return None


def _check_versions(expected: dict[str, str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for dist_name, expected_version in expected.items():
        actual = _dist_version(dist_name)
        if actual is None:
            errors.append(f"Package manquant: {dist_name} (attendu {expected_version})")
            continue
        if actual != expected_version:
            errors.append(
                f"Version incompatible: {dist_name}={actual} (attendu {expected_version})"
            )

    return errors, warnings


def _check_python_version() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    v = sys.version_info
    if (v.major, v.minor) != (3, 12):
        errors.append(f"Python {v.major}.{v.minor}.{v.micro} détecté (attendu 3.12.x dans `.venv`)")
    elif v.micro != 10:
        warnings.append(f"Python 3.12.{v.micro} détecté (référence documentée: 3.12.10)")

    return errors, warnings


def _check_running_from_repo_venv(repo_root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    expected_venv = (repo_root / ".venv").resolve()
    exe = Path(sys.executable)
    exe_resolved = Path(_norm_path(str(exe)))

    if not expected_venv.exists():
        errors.append("Dossier `.venv` introuvable à la racine du repo")
        return errors, warnings

    # Heuristique robuste: l'exécutable doit se trouver dans `.venv/Scripts/python.exe`.
    expected_python = expected_venv / "Scripts" / "python.exe"
    if expected_python.exists():
        if exe_resolved != expected_python.resolve():
            errors.append(
                "Mauvais interpréteur: ce script n'est pas exécuté via `.venv`. "
                f"sys.executable={exe_resolved} (attendu {expected_python.resolve()})"
            )
    else:
        warnings.append(
            "`.venv` détecté mais `.venv/Scripts/python.exe` introuvable (format non Windows?)"
        )

    if not _is_venv():
        errors.append(
            "Environnement virtuel non actif (sys.prefix == sys.base_prefix). "
            "Activez `.venv` ou utilisez directement `.venv/Scripts/python.exe`."
        )

    return errors, warnings


def _check_path_contamination() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not sys.platform.startswith("win"):
        return errors, warnings

    path_value = os.environ.get("PATH", "")
    lower = path_value.lower()

    if "\\msys64\\" in lower or "\\mingw" in lower:
        warnings.append(
            "PATH contient des entrées MSYS2/MinGW (risque de conflits DLL pour DuckDB/Polars). "
            "Évitez d'exécuter le projet avec le Python MSYS2/MinGW."
        )

    return errors, warnings


def main() -> int:
    repo_root = _repo_root()

    print("LevelUp — Healthcheck Environnement")
    _print_kv("OS", f"{platform.system()} {platform.release()}")
    _print_kv("Platform", platform.platform())
    _print_kv("Repo", str(repo_root))
    _print_kv("Python", sys.version.split()[0])
    _print_kv("sys.executable", _norm_path(sys.executable))
    _print_kv("Venv actif", "oui" if _is_venv() else "non")

    errors: list[str] = []
    warnings: list[str] = []

    e, w = _check_running_from_repo_venv(repo_root)
    errors += e
    warnings += w

    e, w = _check_python_version()
    errors += e
    warnings += w

    e, w = _check_path_contamination()
    errors += e
    warnings += w

    expected_versions = {
        "pytest": "9.0.2",
        "pytest-xdist": "3.8.0",
        "pytest-asyncio": "1.3.0",
        "pytest-cov": "7.0.0",
        "duckdb": "1.4.4",
        "polars": "1.38.1",
        "pyarrow": "23.0.0",
        "pandas": "2.3.3",
        "numpy": "2.4.2",
    }

    e, w = _check_versions(expected_versions)
    errors += e
    warnings += w

    if warnings:
        print("\nAvertissements:")
        for msg in warnings:
            print(f"- {msg}")

    if errors:
        print("\nERREURS:")
        for msg in errors:
            print(f"- {msg}")

        print("\nActions suggérées:")
        print("- PowerShell: .\\.venv\\Scripts\\Activate.ps1")
        print("- Cmd: .venv\\Scripts\\activate.bat")
        print('- Puis: python -m pip install -e ".[dev,spnkr]"')
        print("- Puis: python -m pytest -q --ignore=tests/integration")
        return 1

    print("\nOK: environnement conforme.")
    print("Commandes utiles:")
    print("- python -m pytest -q --ignore=tests/integration")
    print("- python scripts/sync.py --delta --gamertag <TonGamertag>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
