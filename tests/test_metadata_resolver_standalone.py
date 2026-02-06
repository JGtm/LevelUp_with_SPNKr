"""Tests standalone pour MetadataResolver - peut s'exécuter sans dépendances complètes."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock DuckDB avant tout import
sys.modules["duckdb"] = MagicMock()

# Ajouter le chemin src
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importer directement le module sans passer par src.data
import importlib.util

spec = importlib.util.spec_from_file_location(
    "metadata_resolver",
    Path(__file__).parent.parent / "src" / "data" / "sync" / "metadata_resolver.py",
)
metadata_resolver = importlib.util.module_from_spec(spec)

# Mock les dépendances avant l'exécution
import logging

sys.modules["logging"] = logging

spec.loader.exec_module(metadata_resolver)

MetadataResolver = metadata_resolver.MetadataResolver
create_metadata_resolver_function = metadata_resolver.create_metadata_resolver_function


def test_resolver_class_exists():
    """Test que la classe MetadataResolver existe."""
    assert MetadataResolver is not None
    assert hasattr(MetadataResolver, "resolve")
    assert hasattr(MetadataResolver, "close")


def test_resolver_function_exists():
    """Test que la fonction create_metadata_resolver_function existe."""
    assert create_metadata_resolver_function is not None
    assert callable(create_metadata_resolver_function)


@patch("pathlib.Path.exists")
def test_resolver_init_db_not_exists(mock_exists):
    """Test initialisation quand DB n'existe pas."""
    mock_exists.return_value = False

    resolver = MetadataResolver("/nonexistent/metadata.duckdb")
    assert resolver._conn is None
    resolver.close()


@patch("pathlib.Path.exists")
@patch("duckdb.connect")
def test_resolver_init_db_exists(mock_connect, mock_exists):
    """Test initialisation quand DB existe."""
    mock_exists.return_value = True
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn

    resolver = MetadataResolver("/fake/metadata.duckdb")
    assert resolver._conn is not None
    resolver.close()


@patch("pathlib.Path.exists")
@patch("duckdb.connect")
def test_resolve_with_none_asset_id(mock_connect, mock_exists):
    """Test resolve avec asset_id None."""
    mock_exists.return_value = True
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn

    resolver = MetadataResolver("/fake/metadata.duckdb")
    result = resolver.resolve("playlist", None)
    assert result is None
    resolver.close()


@patch("pathlib.Path.exists")
@patch("duckdb.connect")
def test_resolve_with_empty_asset_id(mock_connect, mock_exists):
    """Test resolve avec asset_id vide."""
    mock_exists.return_value = True
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn

    resolver = MetadataResolver("/fake/metadata.duckdb")
    result = resolver.resolve("playlist", "")
    assert result is None
    resolver.close()


@patch("pathlib.Path.exists")
@patch("duckdb.connect")
def test_resolve_invalid_type(mock_connect, mock_exists):
    """Test resolve avec type invalide."""
    mock_exists.return_value = True
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn

    resolver = MetadataResolver("/fake/metadata.duckdb")
    result = resolver.resolve("invalid_type", "some-id")
    assert result is None
    resolver.close()


def test_create_resolver_function_db_not_exists():
    """Test create_resolver_function quand DB n'existe pas."""
    with patch("pathlib.Path.exists", return_value=False):
        result = create_metadata_resolver_function("/nonexistent/metadata.duckdb")
        assert result is None


if __name__ == "__main__":
    # Exécution simple sans pytest
    print("=" * 70)
    print("TESTS STANDALONE METADATA_RESOLVER")
    print("=" * 70)

    tests = [
        test_resolver_class_exists,
        test_resolver_function_exists,
        test_resolver_init_db_not_exists,
        test_resolver_init_db_exists,
        test_resolve_with_none_asset_id,
        test_resolve_with_empty_asset_id,
        test_resolve_invalid_type,
        test_create_resolver_function_db_not_exists,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"[OK] {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print("=" * 70)
    print(f"RESULTAT: {passed} passes, {failed} echecs")
    print("=" * 70)

    sys.exit(0 if failed == 0 else 1)
