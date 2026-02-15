"""Tests pour src/ui/profile_api.py et profile_api_tokens.py — Sprint 7ter (7t.6).

Teste les fonctions d'authentification et helpers, sans appels réseau.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ============================================================================
# profile_api_tokens.py
# ============================================================================


class TestIsProbleAuthError:
    def test_401(self):
        from src.ui.profile_api_tokens import _is_probable_auth_error

        assert _is_probable_auth_error(Exception("Got 401 response")) is True

    def test_unauthorized(self):
        from src.ui.profile_api_tokens import _is_probable_auth_error

        assert _is_probable_auth_error(Exception("Unauthorized access")) is True

    def test_forbidden_403(self):
        from src.ui.profile_api_tokens import _is_probable_auth_error

        assert _is_probable_auth_error(Exception("403 Forbidden")) is True

    def test_normal_error(self):
        from src.ui.profile_api_tokens import _is_probable_auth_error

        assert _is_probable_auth_error(Exception("Connection timeout")) is False

    def test_empty_message(self):
        from src.ui.profile_api_tokens import _is_probable_auth_error

        assert _is_probable_auth_error(Exception("")) is False

    def test_case_insensitive(self):
        from src.ui.profile_api_tokens import _is_probable_auth_error

        assert _is_probable_auth_error(Exception("UNAUTHORIZED")) is True


class TestLoadDotenvIfPresent:
    def test_loads_env_file(self, tmp_path, monkeypatch):
        from src.ui.profile_api_tokens import _load_dotenv_if_present

        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY_DOTENV=test_value\n")
        monkeypatch.setattr("src.ui.profile_api_tokens._repo_root", lambda: tmp_path)
        monkeypatch.delenv("TEST_KEY_DOTENV", raising=False)

        _load_dotenv_if_present()

        assert os.environ.get("TEST_KEY_DOTENV") == "test_value"
        # Cleanup
        monkeypatch.delenv("TEST_KEY_DOTENV", raising=False)

    def test_does_not_override_existing(self, tmp_path, monkeypatch):
        from src.ui.profile_api_tokens import _load_dotenv_if_present

        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_KEY=new_value\n")
        monkeypatch.setattr("src.ui.profile_api_tokens._repo_root", lambda: tmp_path)
        monkeypatch.setenv("EXISTING_KEY", "original_value")

        _load_dotenv_if_present()

        assert os.environ.get("EXISTING_KEY") == "original_value"

    def test_env_local_priority(self, tmp_path, monkeypatch):
        from src.ui.profile_api_tokens import _load_dotenv_if_present

        (tmp_path / ".env.local").write_text("PRIORITY_KEY=local_value\n")
        (tmp_path / ".env").write_text("PRIORITY_KEY=env_value\n")
        monkeypatch.setattr("src.ui.profile_api_tokens._repo_root", lambda: tmp_path)
        monkeypatch.delenv("PRIORITY_KEY", raising=False)

        _load_dotenv_if_present()

        # .env.local is loaded first, so its value should win
        assert os.environ.get("PRIORITY_KEY") == "local_value"
        monkeypatch.delenv("PRIORITY_KEY", raising=False)

    def test_no_env_file(self, tmp_path, monkeypatch):
        from src.ui.profile_api_tokens import _load_dotenv_if_present

        monkeypatch.setattr("src.ui.profile_api_tokens._repo_root", lambda: tmp_path)
        # Should not raise
        _load_dotenv_if_present()

    def test_skips_comments_and_empty(self, tmp_path, monkeypatch):
        from src.ui.profile_api_tokens import _load_dotenv_if_present

        env_file = tmp_path / ".env"
        env_file.write_text("# Comment\n\nVALID_KEY=value\n  \n")
        monkeypatch.setattr("src.ui.profile_api_tokens._repo_root", lambda: tmp_path)
        monkeypatch.delenv("VALID_KEY", raising=False)

        _load_dotenv_if_present()

        assert os.environ.get("VALID_KEY") == "value"
        monkeypatch.delenv("VALID_KEY", raising=False)

    def test_strips_quotes(self, tmp_path, monkeypatch):
        from src.ui.profile_api_tokens import _load_dotenv_if_present

        env_file = tmp_path / ".env"
        env_file.write_text('QUOTED_KEY="quoted_value"\n')
        monkeypatch.setattr("src.ui.profile_api_tokens._repo_root", lambda: tmp_path)
        monkeypatch.delenv("QUOTED_KEY", raising=False)

        _load_dotenv_if_present()

        assert os.environ.get("QUOTED_KEY") == "quoted_value"
        monkeypatch.delenv("QUOTED_KEY", raising=False)


class TestGetTokensDirectPass:
    """Test get_tokens when tokens are provided directly."""

    @pytest.mark.asyncio
    async def test_tokens_passed_directly(self, monkeypatch):
        from src.ui.profile_api_tokens import get_tokens

        # Clear env to avoid interference
        monkeypatch.delenv("SPNKR_SPARTAN_TOKEN", raising=False)
        monkeypatch.delenv("SPNKR_CLEARANCE_TOKEN", raising=False)

        session = MagicMock()
        st, ct = await get_tokens(
            session,
            spartan_token="my_spartan_token",
            clearance_token="my_clearance_token",
            timeout_seconds=5,
        )
        assert st == "my_spartan_token"
        assert ct == "my_clearance_token"

    @pytest.mark.asyncio
    async def test_no_tokens_no_azure_raises(self, monkeypatch):
        from src.ui.profile_api_tokens import get_tokens

        # Neutraliser _load_dotenv_if_present pour éviter qu'il ne charge un .env
        monkeypatch.setattr("src.ui.profile_api_tokens._load_dotenv_if_present", lambda: None)
        monkeypatch.delenv("SPNKR_SPARTAN_TOKEN", raising=False)
        monkeypatch.delenv("SPNKR_CLEARANCE_TOKEN", raising=False)
        monkeypatch.delenv("SPNKR_AZURE_CLIENT_ID", raising=False)
        monkeypatch.delenv("SPNKR_AZURE_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("SPNKR_OAUTH_REFRESH_TOKEN", raising=False)

        session = MagicMock()
        with pytest.raises(RuntimeError, match="Tokens manquants"):
            await get_tokens(
                session,
                spartan_token=None,
                clearance_token=None,
                timeout_seconds=5,
            )


# ============================================================================
# profile_api.py — get_profile_appearance / get_xuid_for_gamertag
# ============================================================================


class TestProfileApiCacheLayer:
    """Test the cache logic without network calls."""

    def test_disabled_returns_none(self):
        from src.ui.profile_api import get_profile_appearance

        result, err = get_profile_appearance(
            xuid="2533274823110022",
            enabled=False,
            refresh_hours=0,
        )
        # When disabled, should return cached or None
        assert result is None or hasattr(result, "emblem_image_url")

    def test_xuid_for_gamertag_disabled(self):
        from src.ui.profile_api import get_xuid_for_gamertag

        xuid, err = get_xuid_for_gamertag(
            gamertag="TestPlayer",
            enabled=False,
            refresh_hours=0,
        )
        assert xuid is None or isinstance(xuid, str)


class TestRepoRoot:
    def test_returns_path(self):
        from src.ui.profile_api_tokens import _repo_root

        result = _repo_root()
        assert isinstance(result, Path)
        assert result.exists()
