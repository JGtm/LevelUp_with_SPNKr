"""Tests pour src/ui/player_assets.py — Sprint 7ter (7t.8).

Teste les fonctions de cache d'assets joueur sans accès réseau.
"""

from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock, patch

from src.ui.player_assets import (
    _hashed_name,
    _url_ext,
    download_image_to_cache,
    ensure_local_image_path,
    file_to_data_url,
    get_player_assets_cache_dir,
    is_http_url,
    resolve_local_image_path,
)

# ============================================================================
# is_http_url
# ============================================================================


class TestIsHttpUrl:
    def test_http(self):
        assert is_http_url("http://example.com/image.png") is True

    def test_https(self):
        assert is_http_url("https://example.com/image.png") is True

    def test_none(self):
        assert is_http_url(None) is False

    def test_empty(self):
        assert is_http_url("") is False

    def test_local_path(self):
        assert is_http_url("/path/to/image.png") is False

    def test_windows_path(self):
        assert is_http_url("C:\\Users\\test\\image.png") is False

    def test_case_insensitive(self):
        assert is_http_url("HTTP://example.com") is True
        assert is_http_url("HTTPS://example.com") is True


# ============================================================================
# _url_ext
# ============================================================================


class TestUrlExt:
    def test_png(self):
        assert _url_ext("https://example.com/image.png") == ".png"

    def test_jpg(self):
        assert _url_ext("https://example.com/image.jpg") == ".jpg"

    def test_jpeg(self):
        assert _url_ext("https://example.com/image.jpeg") == ".jpeg"

    def test_webp(self):
        assert _url_ext("https://example.com/image.webp") == ".webp"

    def test_unknown(self):
        assert _url_ext("https://example.com/data") == ".bin"

    def test_query_params(self):
        result = _url_ext("https://example.com/image.png?v=2")
        assert result == ".png"


# ============================================================================
# _hashed_name
# ============================================================================


class TestHashedName:
    def test_deterministic(self):
        name1 = _hashed_name("https://example.com/a.png", prefix="test")
        name2 = _hashed_name("https://example.com/a.png", prefix="test")
        assert name1 == name2

    def test_different_urls(self):
        name1 = _hashed_name("https://example.com/a.png", prefix="test")
        name2 = _hashed_name("https://example.com/b.png", prefix="test")
        assert name1 != name2

    def test_prefix_included(self):
        name = _hashed_name("https://example.com/a.png", prefix="emblem")
        assert name.startswith("emblem_")

    def test_extension_preserved(self):
        name = _hashed_name("https://example.com/a.png", prefix="test")
        assert name.endswith(".png")


# ============================================================================
# get_player_assets_cache_dir
# ============================================================================


class TestGetPlayerAssetsCacheDir:
    def test_returns_string(self):
        result = get_player_assets_cache_dir()
        assert isinstance(result, str)

    def test_contains_player_assets(self):
        result = get_player_assets_cache_dir()
        assert "player_assets" in result


# ============================================================================
# resolve_local_image_path
# ============================================================================


class TestResolveLocalImagePath:
    def test_none(self):
        assert resolve_local_image_path(None) is None

    def test_empty(self):
        assert resolve_local_image_path("") is None

    def test_existing_file(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG")
        assert resolve_local_image_path(str(f)) == str(f)

    def test_nonexistent_file(self):
        assert resolve_local_image_path("/nonexistent/image.png") is None

    def test_url_not_cached(self):
        result = resolve_local_image_path("https://example.com/unique_test_image_xyz.png")
        assert result is None

    def test_url_cached(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "src.ui.player_assets.get_player_assets_cache_dir", lambda: str(tmp_path)
        )
        url = "https://example.com/cached_image.png"
        fname = _hashed_name(url, prefix="asset")
        cached = tmp_path / fname
        cached.write_bytes(b"\x89PNG")

        result = resolve_local_image_path(url)
        assert result is not None
        assert result == str(cached)


# ============================================================================
# download_image_to_cache
# ============================================================================


class TestDownloadImageToCache:
    def test_invalid_url(self):
        ok, msg, path = download_image_to_cache("not_a_url", prefix="test")
        assert ok is False
        assert "invalide" in msg.lower() or "http" in msg.lower()
        assert path is None

    def test_empty_url(self):
        ok, msg, path = download_image_to_cache("", prefix="test")
        assert ok is False

    def test_successful_download(self, tmp_path, monkeypatch):
        """Test download with mocked urllib."""
        monkeypatch.setattr(
            "src.ui.player_assets.get_player_assets_cache_dir", lambda: str(tmp_path)
        )
        # Mock env tokens (no auth needed for test)
        monkeypatch.delenv("SPNKR_CLEARANCE_TOKEN", raising=False)
        monkeypatch.delenv("SPNKR_SPARTAN_TOKEN", raising=False)

        mock_response = MagicMock()
        mock_response.read.return_value = b"\x89PNG fake image data"
        mock_response.headers = {"content-type": "image/png"}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("src.ui.player_assets.urllib.request.urlopen", return_value=mock_response):
            ok, msg, path = download_image_to_cache(
                "https://example.com/test.png", prefix="test", timeout_seconds=5
            )

        assert ok is True
        assert path is not None
        assert os.path.exists(path)


# ============================================================================
# ensure_local_image_path
# ============================================================================


class TestEnsureLocalImagePath:
    def test_local_file(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG")
        result = ensure_local_image_path(str(f), prefix="test", download_enabled=False)
        assert result == str(f)

    def test_none(self):
        assert ensure_local_image_path(None, prefix="test", download_enabled=False) is None

    def test_download_disabled_url_not_cached(self):
        result = ensure_local_image_path(
            "https://example.com/unique_xyz_image.png",
            prefix="test",
            download_enabled=False,
        )
        assert result is None

    def test_cached_url(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "src.ui.player_assets.get_player_assets_cache_dir", lambda: str(tmp_path)
        )
        url = "https://example.com/cached.png"
        fname = _hashed_name(url, prefix="test")
        cached = tmp_path / fname
        cached.write_bytes(b"\x89PNG")

        result = ensure_local_image_path(url, prefix="test", download_enabled=False)
        assert result == str(cached)

    def test_auto_refresh_recent_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "src.ui.player_assets.get_player_assets_cache_dir", lambda: str(tmp_path)
        )
        url = "https://example.com/refresh.png"
        fname = _hashed_name(url, prefix="test")
        cached = tmp_path / fname
        cached.write_bytes(b"\x89PNG")

        result = ensure_local_image_path(
            url, prefix="test", download_enabled=True, auto_refresh_hours=24
        )
        # Cache is recent (just created) → should return cached
        assert result == str(cached)


# ============================================================================
# file_to_data_url
# ============================================================================


class TestFileToDataUrl:
    def test_png_file(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\x0d\x0a\x1a\x0a")
        result = file_to_data_url(str(f))
        assert result is not None
        assert result.startswith("data:image/png;base64,")

    def test_jpg_file(self, tmp_path):
        f = tmp_path / "image.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0")
        result = file_to_data_url(str(f))
        assert result is not None
        assert result.startswith("data:image/jpeg;base64,")

    def test_none(self):
        assert file_to_data_url(None) is None

    def test_empty(self):
        assert file_to_data_url("") is None

    def test_nonexistent(self):
        assert file_to_data_url("/nonexistent/image.png") is None

    def test_too_large(self, tmp_path):
        f = tmp_path / "large.png"
        f.write_bytes(b"\x00" * (4 * 1024 * 1024))  # 4MB
        result = file_to_data_url(str(f))
        assert result is None

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.png"
        f.write_bytes(b"")
        result = file_to_data_url(str(f))
        assert result is None

    def test_data_url_roundtrip(self, tmp_path):
        content = b"test image data"
        f = tmp_path / "test.png"
        f.write_bytes(content)
        result = file_to_data_url(str(f))
        assert result is not None
        # Decode and verify
        _, encoded = result.split(",", 1)
        decoded = base64.b64decode(encoded)
        assert decoded == content
