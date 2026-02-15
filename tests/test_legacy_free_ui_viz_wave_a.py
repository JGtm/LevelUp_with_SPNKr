"""Tests anti-régression : aucun import pandas résiduel dans la vague A.

Vérifie que les fichiers UI/visualization de la vague A n'importent plus
pandas au runtime (sauf cas justifiés et documentés).
"""

from __future__ import annotations

import ast
import pathlib

import pytest

# ---------------------------------------------------------------------------
# Fichiers cibles de la vague A
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parent.parent

VIZ_FILES = [
    "src/visualization/distributions.py",
    "src/visualization/distributions_outcomes.py",
    "src/visualization/maps.py",
    "src/visualization/match_bars.py",
    "src/visualization/timeseries.py",
    "src/visualization/timeseries_combat.py",
    "src/visualization/trio.py",
    "src/visualization/participation_charts.py",
]

UI_PAGE_FILES = [
    "src/ui/pages/citations.py",
    "src/ui/pages/last_match.py",
    "src/ui/pages/match_history.py",
    "src/ui/pages/match_view.py",
    "src/ui/pages/match_view_charts.py",
    "src/ui/pages/match_view_helpers.py",
    "src/ui/pages/match_view_participation.py",
    "src/ui/pages/media_library.py",
    "src/ui/pages/session_compare.py",
    "src/ui/pages/session_compare_charts.py",
    "src/ui/pages/teammates.py",
    "src/ui/pages/teammates_charts.py",
    "src/ui/pages/teammates_helpers.py",
    "src/ui/pages/teammates_synergy.py",
    "src/ui/pages/teammates_views.py",
    "src/ui/pages/timeseries.py",
]

# Exceptions documentées : fichiers qui DOIVENT garder pandas au runtime
# avec justification.
ALLOWED_RUNTIME_PANDAS = {
    # win_loss.py utilise l'API .style de Streamlit/Pandas pour le styling conditionnel
    "src/ui/pages/win_loss.py": "API pd.DataFrame.style requise par Streamlit",
}

ALL_WAVE_A_FILES = VIZ_FILES + UI_PAGE_FILES


# ---------------------------------------------------------------------------
# Helpers AST
# ---------------------------------------------------------------------------


def _has_runtime_pandas_import(filepath: pathlib.Path) -> list[int]:
    """Retourne les numéros de ligne des imports pandas au runtime.

    Ignore les imports sous `if TYPE_CHECKING:`.
    """
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        pytest.skip(f"Erreur de syntaxe dans {filepath}")
        return []

    runtime_imports: list[int] = []

    for node in ast.walk(tree):
        # import pandas / import pandas as pd
        if isinstance(node, ast.Import):
            for alias in node.names:
                if (
                    alias.name == "pandas" or alias.name.startswith("pandas.")
                ) and not _is_inside_type_checking(tree, node):
                    runtime_imports.append(node.lineno)

        # from pandas import ...
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and (node.module == "pandas" or node.module.startswith("pandas."))
            and not _is_inside_type_checking(tree, node)
        ):
            runtime_imports.append(node.lineno)

    return runtime_imports


def _is_inside_type_checking(tree: ast.Module, target_node: ast.AST) -> bool:
    """Vérifie si un nœud AST est dans un bloc `if TYPE_CHECKING:`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            # Vérifie if TYPE_CHECKING:
            test = node.test
            is_type_checking = False
            if (
                isinstance(test, ast.Name)
                and test.id == "TYPE_CHECKING"
                or isinstance(test, ast.Attribute)
                and test.attr == "TYPE_CHECKING"
            ):
                is_type_checking = True

            if is_type_checking:
                for child in ast.walk(node):
                    if child is target_node:
                        return True
    return False


# ---------------------------------------------------------------------------
# Tests paramétrés
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relpath", ALL_WAVE_A_FILES)
def test_no_runtime_pandas_import(relpath: str) -> None:
    """Aucun import pandas au runtime dans les fichiers de la vague A."""
    filepath = ROOT / relpath
    if not filepath.exists():
        pytest.skip(f"Fichier non trouvé : {relpath}")

    if relpath in ALLOWED_RUNTIME_PANDAS:
        pytest.skip(f"Exception documentée : {ALLOWED_RUNTIME_PANDAS[relpath]}")

    lines = _has_runtime_pandas_import(filepath)
    assert lines == [], (
        f"{relpath} importe pandas au runtime (lignes {lines}). "
        f"Utiliser `from src.visualization._compat import ensure_polars` à la place."
    )


@pytest.mark.parametrize("relpath", ALL_WAVE_A_FILES)
def test_no_sqlite_import(relpath: str) -> None:
    """Aucun import sqlite3 résiduel dans les fichiers de la vague A."""
    filepath = ROOT / relpath
    if not filepath.exists():
        pytest.skip(f"Fichier non trouvé : {relpath}")

    source = filepath.read_text(encoding="utf-8")
    assert "import sqlite3" not in source, f"{relpath} importe encore sqlite3."
    assert "sqlite_master" not in source, f"{relpath} référence encore sqlite_master."


# ---------------------------------------------------------------------------
# Test global : décompte résiduel
# ---------------------------------------------------------------------------


def test_wave_a_pandas_budget() -> None:
    """Le nombre total de fichiers avec pandas runtime ne dépasse pas le budget."""
    exceptions = 0
    for relpath in ALL_WAVE_A_FILES + list(ALLOWED_RUNTIME_PANDAS.keys()):
        filepath = ROOT / relpath
        if filepath.exists() and _has_runtime_pandas_import(filepath):
            exceptions += 1

    # Budget : seul win_loss.py est autorisé
    assert exceptions <= 1, (
        f"{exceptions} fichiers ont encore un import pandas runtime. "
        f"Budget = 1 (win_loss.py uniquement)."
    )
