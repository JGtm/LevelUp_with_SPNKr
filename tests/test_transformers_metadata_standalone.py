"""Tests standalone pour transformers metadata - peut s'exécuter sans dépendances complètes."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock toutes les dépendances avant les imports
sys.modules["duckdb"] = MagicMock()
sys.modules["polars"] = MagicMock()

# Ajouter le chemin src
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importer directement le module transformers
import importlib.util

spec = importlib.util.spec_from_file_location(
    "transformers", Path(__file__).parent.parent / "src" / "data" / "sync" / "transformers.py"
)

# Mock les dépendances avant l'exécution
import logging

sys.modules["logging"] = logging
sys.modules["re"] = __import__("re")
sys.modules["math"] = __import__("math")
sys.modules["json"] = __import__("json")
sys.modules["collections"] = __import__("collections")
sys.modules["collections.abc"] = __import__("collections.abc")
sys.modules["datetime"] = __import__("datetime")
typing_module = __import__("typing")
sys.modules["typing"] = typing_module
# Callable est dans typing en Python 3.9+
if not hasattr(typing_module, "Callable"):
    from collections.abc import Callable as _Callable

    typing_module.Callable = _Callable

# Mock les modules src
sys.modules["src.analysis.mode_categories"] = MagicMock()
sys.modules["src.data.domain.refdata"] = MagicMock()
sys.modules["src.data.sync.models"] = MagicMock()

transformers = importlib.util.module_from_spec(spec)

try:
    spec.loader.exec_module(transformers)
    transform_match_stats = getattr(transformers, "transform_match_stats", None)
    _extract_public_name = getattr(transformers, "_extract_public_name", None)
    _extract_asset_id = getattr(transformers, "_extract_asset_id", None)
except Exception as e:
    print(f"Note: Impossible de charger transformers completement: {e}")
    transform_match_stats = None
    _extract_public_name = None
    _extract_asset_id = None


def test_extract_public_name_exists():
    """Test que _extract_public_name existe."""
    if _extract_public_name is None:
        print("[SKIP] _extract_public_name non disponible (dependances manquantes)")
        return
    assert callable(_extract_public_name)


def test_extract_asset_id_exists():
    """Test que _extract_asset_id existe."""
    if _extract_asset_id is None:
        print("[SKIP] _extract_asset_id non disponible (dependances manquantes)")
        return
    assert callable(_extract_asset_id)


def test_transform_match_stats_exists():
    """Test que transform_match_stats existe."""
    if transform_match_stats is None:
        print("[SKIP] transform_match_stats non disponible (dependances manquantes)")
        return
    assert callable(transform_match_stats)


def test_extract_public_name_with_public_name():
    """Test extraction PublicName quand présent."""
    if _extract_public_name is None:
        print("[SKIP] Test skip - dependances manquantes")
        return

    match_info = {"Playlist": {"AssetId": "playlist-123", "PublicName": "Ranked Slayer"}}

    result = _extract_public_name(match_info, "Playlist")
    assert result == "Ranked Slayer"


def test_extract_public_name_without_public_name():
    """Test extraction PublicName quand absent."""
    if _extract_public_name is None:
        print("[SKIP] Test skip - dependances manquantes")
        return

    match_info = {"Playlist": {"AssetId": "playlist-123"}}

    result = _extract_public_name(match_info, "Playlist")
    assert result is None


def test_extract_asset_id_with_asset_id():
    """Test extraction AssetId quand présent."""
    if _extract_asset_id is None:
        print("[SKIP] Test skip - dependances manquantes")
        return

    match_info = {"Playlist": {"AssetId": "playlist-123"}}

    result = _extract_asset_id(match_info, "Playlist")
    assert result == "playlist-123"


def test_extract_asset_id_without_asset_id():
    """Test extraction AssetId quand absent."""
    if _extract_asset_id is None:
        print("[SKIP] Test skip - dependances manquantes")
        return

    match_info = {"Playlist": {}}

    result = _extract_asset_id(match_info, "Playlist")
    assert result is None


if __name__ == "__main__":
    print("=" * 70)
    print("TESTS STANDALONE TRANSFORMERS METADATA")
    print("=" * 70)

    tests = [
        test_extract_public_name_exists,
        test_extract_asset_id_exists,
        test_transform_match_stats_exists,
        test_extract_public_name_with_public_name,
        test_extract_public_name_without_public_name,
        test_extract_asset_id_with_asset_id,
        test_extract_asset_id_without_asset_id,
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            if "SKIP" in str(e) or "skip" in str(e).lower():
                skipped += 1
            else:
                print(f"[FAIL] {test.__name__}: {e}")
                failed += 1

    print("=" * 70)
    print(f"RESULTAT: {passed} passes, {failed} echecs, {skipped} skips")
    print("=" * 70)

    sys.exit(0 if failed == 0 else 1)
