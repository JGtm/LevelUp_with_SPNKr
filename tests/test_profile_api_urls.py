"""Tests pour src/ui/profile_api_urls.py — Sprint 7ter (7t.2).

Couvre les fonctions de construction d'URLs Halo Waypoint.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ui.profile_api_urls import (
    _inventory_backdrop_to_waypoint_png,
    _inventory_emblem_to_waypoint_png,
    _inventory_json_to_cms_url,
    _to_image_url,
    _waypoint_nameplate_png_from_emblem,
    resolve_inventory_png_via_api,
)

HOST = "https://gamecms-hacs.svc.halowaypoint.com"


class TestToImageUrl:
    def test_none(self):
        assert _to_image_url(None) is None

    def test_empty(self):
        assert _to_image_url("") is None
        assert _to_image_url("   ") is None

    def test_already_http(self):
        url = "https://example.com/image.png"
        assert _to_image_url(url) == url

    def test_already_http_lowercase(self):
        url = "http://example.com/image.png"
        assert _to_image_url(url) == url

    def test_relative_path(self):
        result = _to_image_url("progression/Backdrops/bg.png")
        assert result == f"{HOST}/hi/Images/file/progression/Backdrops/bg.png"

    def test_path_with_leading_slash(self):
        result = _to_image_url("/progression/Backdrops/bg.png")
        assert result == f"{HOST}/hi/Images/file/progression/Backdrops/bg.png"

    def test_path_with_hi_images_file(self):
        result = _to_image_url("/hi/images/file/progression/Backdrops/bg.png")
        assert "/hi/Images/file/progression/Backdrops/bg.png" in result

    def test_path_with_hi_images_file_mixed_case(self):
        result = _to_image_url("/HI/IMAGES/FILE/progression/Backdrops/bg.png")
        assert result is not None
        assert result.startswith(HOST)


class TestInventoryEmblemToWaypointPng:
    def test_valid(self):
        result = _inventory_emblem_to_waypoint_png(
            "Inventory/Spartan/Emblems/104-001-olympus-stuck.json", 42
        )
        assert result == f"{HOST}/hi/Waypoint/file/images/emblems/104-001-olympus-stuck_42.png"

    def test_none_path(self):
        assert _inventory_emblem_to_waypoint_png(None, 42) is None

    def test_none_config_id(self):
        assert _inventory_emblem_to_waypoint_png("Inventory/Spartan/Emblems/x.json", None) is None

    def test_config_id_zero(self):
        assert _inventory_emblem_to_waypoint_png("Inventory/Spartan/Emblems/x.json", 0) is None

    def test_config_id_negative(self):
        assert _inventory_emblem_to_waypoint_png("Inventory/Spartan/Emblems/x.json", -5) is None

    def test_no_spartan_emblems_in_path(self):
        assert _inventory_emblem_to_waypoint_png("Inventory/Other/x.json", 42) is None

    def test_empty_path(self):
        assert _inventory_emblem_to_waypoint_png("", 42) is None


class TestInventoryJsonToCmsUrl:
    def test_valid(self):
        result = _inventory_json_to_cms_url("Inventory/Spartan/Emblems/x.json")
        assert result == f"{HOST}/hi/progression/file/Inventory/Spartan/Emblems/x.json"

    def test_none(self):
        assert _inventory_json_to_cms_url(None) is None

    def test_empty(self):
        assert _inventory_json_to_cms_url("") is None

    def test_not_inventory(self):
        assert _inventory_json_to_cms_url("Other/Path/file.json") is None

    def test_leading_slash(self):
        result = _inventory_json_to_cms_url("/Inventory/Spartan/item.json")
        assert result is not None
        assert "Inventory/Spartan/item.json" in result

    def test_nested_inventory(self):
        result = _inventory_json_to_cms_url("path/Inventory/item.json")
        assert result is not None


class TestWaypointNameplatePngFromEmblem:
    def test_valid_positive_cfg(self):
        result = _waypoint_nameplate_png_from_emblem(
            "Inventory/Spartan/Emblems/emblem-name.json", 42
        )
        assert result == f"{HOST}/hi/Waypoint/file/images/nameplates/emblem-name_42.png"

    def test_valid_negative_cfg(self):
        """Configuration_id can be negative (signed int32 in API)."""
        result = _waypoint_nameplate_png_from_emblem(
            "Inventory/Spartan/Emblems/emblem.json", -12345
        )
        assert result == f"{HOST}/hi/Waypoint/file/images/nameplates/emblem_-12345.png"

    def test_none_path(self):
        assert _waypoint_nameplate_png_from_emblem(None, 42) is None

    def test_none_cfg(self):
        assert _waypoint_nameplate_png_from_emblem("Inventory/Spartan/Emblems/x.json", None) is None

    def test_zero_cfg(self):
        assert _waypoint_nameplate_png_from_emblem("Inventory/Spartan/Emblems/x.json", 0) is None

    def test_no_spartan_emblems(self):
        assert _waypoint_nameplate_png_from_emblem("Inventory/Other/x.json", 42) is None


class TestInventoryBackdropToWaypointPng:
    def test_png_direct(self):
        result = _inventory_backdrop_to_waypoint_png("progression/Backdrops/bg.png")
        assert result is not None
        assert result.endswith(".png")

    def test_jpg_direct(self):
        result = _inventory_backdrop_to_waypoint_png("image.jpg")
        assert result is not None

    def test_json_returns_none(self):
        """JSON backdrops cannot be resolved statically."""
        result = _inventory_backdrop_to_waypoint_png("Inventory/Spartan/BackdropImages/x.json")
        assert result is None

    def test_none(self):
        assert _inventory_backdrop_to_waypoint_png(None) is None

    def test_empty(self):
        assert _inventory_backdrop_to_waypoint_png("") is None


class TestResolveInventoryPngViaApi:
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        return session

    def test_none_path(self):
        result = asyncio.get_event_loop().run_until_complete(
            resolve_inventory_png_via_api(
                MagicMock(), None, spartan_token="st", clearance_token="ct"
            )
        )
        assert result is None

    def test_not_inventory_path(self):
        result = asyncio.get_event_loop().run_until_complete(
            resolve_inventory_png_via_api(
                MagicMock(), "Other/path.json", spartan_token="st", clearance_token="ct"
            )
        )
        assert result is None

    def test_valid_response_common_data(self):
        response_data = {
            "CommonData": {
                "DisplayPath": {
                    "Media": {
                        "MediaUrl": {"Path": "progression/Backdrops/103-000-ui-background.png"}
                    }
                }
            }
        }

        resp_mock = AsyncMock()
        resp_mock.status = 200
        resp_mock.json = AsyncMock(return_value=response_data)
        resp_mock.__aenter__ = AsyncMock(return_value=resp_mock)
        resp_mock.__aexit__ = AsyncMock(return_value=False)

        session = MagicMock()
        session.get = MagicMock(return_value=resp_mock)

        result = asyncio.get_event_loop().run_until_complete(
            resolve_inventory_png_via_api(
                session,
                "Inventory/Spartan/BackdropImages/x.json",
                spartan_token="st",
                clearance_token="ct",
            )
        )
        assert result is not None
        assert "progression/Backdrops/103-000-ui-background.png" in result

    def test_404_response(self):
        resp_mock = AsyncMock()
        resp_mock.status = 404
        resp_mock.__aenter__ = AsyncMock(return_value=resp_mock)
        resp_mock.__aexit__ = AsyncMock(return_value=False)

        session = MagicMock()
        session.get = MagicMock(return_value=resp_mock)

        result = asyncio.get_event_loop().run_until_complete(
            resolve_inventory_png_via_api(
                session,
                "Inventory/Spartan/BackdropImages/x.json",
                spartan_token="st",
                clearance_token="ct",
            )
        )
        assert result is None

    def test_fallback_folder_filename(self):
        """Test fallback to FolderPath + FileName."""
        response_data = {
            "CommonData": {
                "DisplayPath": {
                    "FolderPath": "progression/Backdrops",
                    "FileName": "bg.png",
                }
            }
        }

        resp_mock = AsyncMock()
        resp_mock.status = 200
        resp_mock.json = AsyncMock(return_value=response_data)
        resp_mock.__aenter__ = AsyncMock(return_value=resp_mock)
        resp_mock.__aexit__ = AsyncMock(return_value=False)

        session = MagicMock()
        session.get = MagicMock(return_value=resp_mock)

        result = asyncio.get_event_loop().run_until_complete(
            resolve_inventory_png_via_api(
                session, "Inventory/Spartan/x.json", spartan_token="st", clearance_token="ct"
            )
        )
        assert result is not None
        assert "progression/Backdrops/bg.png" in result

    def test_fallback_image_path(self):
        """Test fallback to ImagePath."""
        response_data = {
            "CommonData": {"DisplayPath": {}},
            "ImagePath": {"Media": {"MediaUrl": {"Path": "images/backdrops/fallback.png"}}},
        }

        resp_mock = AsyncMock()
        resp_mock.status = 200
        resp_mock.json = AsyncMock(return_value=response_data)
        resp_mock.__aenter__ = AsyncMock(return_value=resp_mock)
        resp_mock.__aexit__ = AsyncMock(return_value=False)

        session = MagicMock()
        session.get = MagicMock(return_value=resp_mock)

        result = asyncio.get_event_loop().run_until_complete(
            resolve_inventory_png_via_api(
                session, "Inventory/item.json", spartan_token="st", clearance_token="ct"
            )
        )
        assert result is not None
        assert "images/backdrops/fallback.png" in result

    def test_empty_response(self):
        response_data = {"CommonData": {"DisplayPath": {}}}

        resp_mock = AsyncMock()
        resp_mock.status = 200
        resp_mock.json = AsyncMock(return_value=response_data)
        resp_mock.__aenter__ = AsyncMock(return_value=resp_mock)
        resp_mock.__aexit__ = AsyncMock(return_value=False)

        session = MagicMock()
        session.get = MagicMock(return_value=resp_mock)

        result = asyncio.get_event_loop().run_until_complete(
            resolve_inventory_png_via_api(
                session, "Inventory/item.json", spartan_token="st", clearance_token="ct"
            )
        )
        assert result is None
