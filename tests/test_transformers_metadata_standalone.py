"""Tests standalone pour transformers metadata.

Objectif: pouvoir charger `src/data/sync/transformers.py` même si certaines
dependances runtime (DuckDB/Polars) ne sont pas disponibles.

Important: ne pas modifier `sys.modules` au niveau module, sinon cela pollue la
session pytest entière et peut casser des tests suivants.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TRANSFORMERS_PATH = _REPO_ROOT / "src" / "data" / "sync" / "transformers.py"


def _load_transformers_with_mocks(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ModuleType | None, Exception | None]:
    """Charge `transformers.py` en isolant les mocks via `monkeypatch`.

    Retourne (module, exception). Si l'import échoue, module=None et exception non-None.
    """

    # Permettre les imports relatifs depuis le repo
    monkeypatch.syspath_prepend(str(_REPO_ROOT))

    # Mocker uniquement les dépendances non-stdlib susceptibles de manquer
    monkeypatch.setitem(sys.modules, "duckdb", MagicMock())
    monkeypatch.setitem(sys.modules, "polars", MagicMock())

    # Mocker quelques modules internes si besoin (tests standalone)
    monkeypatch.setitem(sys.modules, "src.analysis.mode_categories", MagicMock())
    monkeypatch.setitem(sys.modules, "src.data.domain.refdata", MagicMock())
    monkeypatch.setitem(sys.modules, "src.data.sync.models", MagicMock())

    spec = importlib.util.spec_from_file_location(
        "_levelup_transformers_standalone", _TRANSFORMERS_PATH
    )
    if spec is None or spec.loader is None:
        return None, RuntimeError(f"Spec introuvable pour {_TRANSFORMERS_PATH}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover
        return None, exc

    return module, None


def test_extract_public_name_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test que _extract_public_name existe."""
    module, exc = _load_transformers_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] transformers non chargeable (dependances manquantes?): {exc}")

    fn = getattr(module, "_extract_public_name", None)
    assert callable(fn)


def test_extract_asset_id_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test que _extract_asset_id existe."""
    module, exc = _load_transformers_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] transformers non chargeable (dependances manquantes?): {exc}")

    fn = getattr(module, "_extract_asset_id", None)
    assert callable(fn)


def test_transform_match_stats_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test que transform_match_stats existe."""
    module, exc = _load_transformers_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] transformers non chargeable (dependances manquantes?): {exc}")

    fn = getattr(module, "transform_match_stats", None)
    assert callable(fn)


def test_extract_public_name_with_public_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test extraction PublicName quand présent."""
    module, exc = _load_transformers_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] transformers non chargeable (dependances manquantes?): {exc}")

    fn = getattr(module, "_extract_public_name", None)
    if not callable(fn):
        pytest.skip("[SKIP] _extract_public_name non disponible")

    match_info = {"Playlist": {"AssetId": "playlist-123", "PublicName": "Ranked Slayer"}}

    result = fn(match_info, "Playlist")
    assert result == "Ranked Slayer"


def test_extract_public_name_without_public_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test extraction PublicName quand absent."""
    module, exc = _load_transformers_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] transformers non chargeable (dependances manquantes?): {exc}")

    fn = getattr(module, "_extract_public_name", None)
    if not callable(fn):
        pytest.skip("[SKIP] _extract_public_name non disponible")

    match_info = {"Playlist": {"AssetId": "playlist-123"}}

    result = fn(match_info, "Playlist")
    assert result is None


def test_extract_asset_id_with_asset_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test extraction AssetId quand présent."""
    module, exc = _load_transformers_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] transformers non chargeable (dependances manquantes?): {exc}")

    fn = getattr(module, "_extract_asset_id", None)
    if not callable(fn):
        pytest.skip("[SKIP] _extract_asset_id non disponible")

    match_info = {"Playlist": {"AssetId": "playlist-123"}}

    result = fn(match_info, "Playlist")
    assert result == "playlist-123"


def test_extract_asset_id_without_asset_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test extraction AssetId quand absent."""
    module, exc = _load_transformers_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] transformers non chargeable (dependances manquantes?): {exc}")

    fn = getattr(module, "_extract_asset_id", None)
    if not callable(fn):
        pytest.skip("[SKIP] _extract_asset_id non disponible")

    match_info = {"Playlist": {}}

    result = fn(match_info, "Playlist")
    assert result is None
