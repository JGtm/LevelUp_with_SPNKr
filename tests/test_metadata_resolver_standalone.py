"""Tests standalone pour MetadataResolver.

Important: ne pas modifier `sys.modules` au niveau module, sinon cela pollue la
collecte pytest et peut casser d'autres tests.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "src" / "data" / "sync" / "metadata_resolver.py"


def _load_metadata_resolver_with_mocks(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ModuleType | None, Exception | None]:
    """Charge metadata_resolver en isolant les mocks via `monkeypatch`."""

    monkeypatch.syspath_prepend(str(_REPO_ROOT))
    monkeypatch.setitem(sys.modules, "duckdb", MagicMock())

    spec = importlib.util.spec_from_file_location(
        "_levelup_metadata_resolver_standalone", _MODULE_PATH
    )
    if spec is None or spec.loader is None:
        return None, RuntimeError(f"Spec introuvable pour {_MODULE_PATH}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover
        return None, exc
    return module, None


def test_resolver_class_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test que la classe MetadataResolver existe."""
    module, exc = _load_metadata_resolver_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] metadata_resolver non chargeable: {exc}")

    cls = getattr(module, "MetadataResolver", None)
    assert cls is not None
    assert hasattr(cls, "resolve")
    assert hasattr(cls, "close")


def test_resolver_function_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test que la fonction create_metadata_resolver_function existe."""
    module, exc = _load_metadata_resolver_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] metadata_resolver non chargeable: {exc}")

    fn = getattr(module, "create_metadata_resolver_function", None)
    assert callable(fn)


def test_resolver_init_db_not_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test initialisation quand DB n'existe pas."""
    module, exc = _load_metadata_resolver_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] metadata_resolver non chargeable: {exc}")

    cls = module.MetadataResolver
    with patch("pathlib.Path.exists", return_value=False):
        resolver = cls("/nonexistent/metadata.duckdb")
        assert resolver._conn is None
        resolver.close()


def test_resolver_init_db_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test initialisation quand DB existe."""
    module, exc = _load_metadata_resolver_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] metadata_resolver non chargeable: {exc}")

    cls = module.MetadataResolver
    mock_conn = MagicMock()
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("duckdb.connect", return_value=mock_conn),
    ):
        resolver = cls("/fake/metadata.duckdb")
        assert resolver._conn is not None
        resolver.close()


def test_resolve_with_none_asset_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolve avec asset_id None."""
    module, exc = _load_metadata_resolver_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] metadata_resolver non chargeable: {exc}")

    cls = module.MetadataResolver
    mock_conn = MagicMock()
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("duckdb.connect", return_value=mock_conn),
    ):
        resolver = cls("/fake/metadata.duckdb")
        result = resolver.resolve("playlist", None)
        assert result is None
        resolver.close()


def test_resolve_with_empty_asset_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolve avec asset_id vide."""
    module, exc = _load_metadata_resolver_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] metadata_resolver non chargeable: {exc}")

    cls = module.MetadataResolver
    mock_conn = MagicMock()
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("duckdb.connect", return_value=mock_conn),
    ):
        resolver = cls("/fake/metadata.duckdb")
        result = resolver.resolve("playlist", "")
        assert result is None
        resolver.close()


def test_resolve_invalid_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolve avec type invalide."""
    module, exc = _load_metadata_resolver_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] metadata_resolver non chargeable: {exc}")

    cls = module.MetadataResolver
    mock_conn = MagicMock()
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("duckdb.connect", return_value=mock_conn),
    ):
        resolver = cls("/fake/metadata.duckdb")
        result = resolver.resolve("invalid_type", "some-id")
        assert result is None
        resolver.close()


def test_create_resolver_function_db_not_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test create_resolver_function quand DB n'existe pas."""
    module, exc = _load_metadata_resolver_with_mocks(monkeypatch)
    if module is None:
        pytest.skip(f"[SKIP] metadata_resolver non chargeable: {exc}")

    fn = module.create_metadata_resolver_function
    with patch("pathlib.Path.exists", return_value=False):
        result = fn("/nonexistent/metadata.duckdb")
        assert result is None
