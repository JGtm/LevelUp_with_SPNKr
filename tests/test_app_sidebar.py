"""Tests pour sidebar.py et data_loader.py.

Sprint 7bis – Tâche 7b.8
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import polars as pl

# ═══════════════════════════════════════════════════════════════════
# data_loader – fonctions pures
# ═══════════════════════════════════════════════════════════════════


class TestDefaultIdentityFromSecrets:
    """Tests pour default_identity_from_secrets."""

    def test_returns_tuple_of_three(self, mock_st):
        from src.app import data_loader as mod

        ms = mock_st(mod)
        # Patcher st.secrets pour éviter l'accès réel
        secrets_mock = MagicMock()
        secrets_mock.get.return_value = {}
        ms._monkeypatch.setattr(mod.st, "secrets", secrets_mock)

        result = mod.default_identity_from_secrets()
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_reads_from_env(self, mock_st, monkeypatch):
        from src.app import data_loader as mod

        ms = mock_st(mod)
        secrets_mock = MagicMock()
        secrets_mock.get.return_value = {}
        ms._monkeypatch.setattr(mod.st, "secrets", secrets_mock)

        monkeypatch.setenv("OPENSPARTAN_DEFAULT_GAMERTAG", "TestPlayer")
        monkeypatch.setenv("OPENSPARTAN_DEFAULT_XUID", "1234567890")

        xuid_or_gt, xuid_fb, wp = mod.default_identity_from_secrets()
        assert xuid_or_gt == "TestPlayer"
        assert xuid_fb == "1234567890"


class TestPropagateIdentityEnv:
    """Tests pour propagate_identity_env."""

    def test_sets_env_vars(self, monkeypatch):
        from src.app.data_loader import propagate_identity_env

        monkeypatch.delenv("OPENSPARTAN_DEFAULT_GAMERTAG", raising=False)
        monkeypatch.delenv("OPENSPARTAN_DEFAULT_XUID", raising=False)
        monkeypatch.delenv("OPENSPARTAN_DEFAULT_WAYPOINT_PLAYER", raising=False)

        propagate_identity_env("MonGamertag", "999", "MonGamertag")
        assert os.environ.get("OPENSPARTAN_DEFAULT_GAMERTAG") == "MonGamertag"
        assert os.environ.get("OPENSPARTAN_DEFAULT_XUID") == "999"
        assert os.environ.get("OPENSPARTAN_DEFAULT_WAYPOINT_PLAYER") == "MonGamertag"

    def test_does_not_overwrite_existing(self, monkeypatch):
        from src.app.data_loader import propagate_identity_env

        monkeypatch.setenv("OPENSPARTAN_DEFAULT_GAMERTAG", "Existing")
        monkeypatch.setenv("OPENSPARTAN_DEFAULT_XUID", "111")

        propagate_identity_env("NewGT", "222", "NewGT")
        assert os.environ["OPENSPARTAN_DEFAULT_GAMERTAG"] == "Existing"
        assert os.environ["OPENSPARTAN_DEFAULT_XUID"] == "111"

    def test_noop_for_numeric_xuid(self, monkeypatch):
        from src.app.data_loader import propagate_identity_env

        monkeypatch.delenv("OPENSPARTAN_DEFAULT_GAMERTAG", raising=False)
        monkeypatch.delenv("OPENSPARTAN_DEFAULT_XUID", raising=False)

        # Si xuid_or_gt est numérique, on ne propage pas GT/XUID
        propagate_identity_env("123456", "123456", "")
        assert os.environ.get("OPENSPARTAN_DEFAULT_GAMERTAG") is None


class TestValidateDbPath:
    """Tests pour validate_db_path."""

    def test_nonexistent_returns_empty(self):
        from src.app.data_loader import validate_db_path

        result = validate_db_path("/nonexistent/path.duckdb", "")
        assert result == ""

    def test_valid_path_returned(self, tmp_path):
        from src.app.data_loader import validate_db_path

        db_file = tmp_path / "test.duckdb"
        db_file.write_bytes(b"dummy content")
        result = validate_db_path(str(db_file), "")
        assert result == str(db_file)

    def test_empty_file_returns_empty(self, tmp_path):
        from src.app.data_loader import validate_db_path

        db_file = tmp_path / "empty.duckdb"
        db_file.write_bytes(b"")
        result = validate_db_path(str(db_file), "")
        assert result == ""

    def test_empty_string_path(self):
        from src.app.data_loader import validate_db_path

        result = validate_db_path("", "")
        assert result == ""


class TestResolveXuidInput:
    """Tests pour resolve_xuid_input."""

    def test_numeric_input(self):
        from src.app.data_loader import resolve_xuid_input

        with patch("src.app.data_loader.parse_xuid_input", return_value="1234567890"):
            result = resolve_xuid_input("1234567890", "")
        assert result == "1234567890"

    def test_empty_input_returns_empty_without_db(self):
        from src.app.data_loader import resolve_xuid_input

        with (
            patch("src.app.data_loader.parse_xuid_input", return_value=""),
            patch("src.app.data_loader.default_identity_from_secrets", return_value=("", "", "")),
        ):
            result = resolve_xuid_input("", "")
        assert result == ""


class TestLoadMatchData:
    """Tests pour load_match_data."""

    def test_empty_db_path_returns_empty_df(self):
        from src.app.data_loader import load_match_data

        result = load_match_data("", "xuid123", None)
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()

    def test_nonexistent_path_returns_empty_df(self):
        from src.app.data_loader import load_match_data

        result = load_match_data("/nonexistent.duckdb", "xuid123", None)
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()

    def test_empty_xuid_returns_empty_df(self, tmp_path):
        from src.app.data_loader import load_match_data

        db_file = tmp_path / "test.duckdb"
        db_file.write_bytes(b"dummy")
        result = load_match_data(str(db_file), "", None)
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()


class TestGetDbCacheKey:
    """Tests pour get_db_cache_key."""

    def test_returns_tuple_for_existing_file(self, tmp_path):
        from src.app.data_loader import get_db_cache_key

        db_file = tmp_path / "test.duckdb"
        db_file.write_bytes(b"dummy content")
        result = get_db_cache_key(str(db_file))
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_none_for_nonexistent(self):
        from src.app.data_loader import get_db_cache_key

        result = get_db_cache_key("/nonexistent/test.duckdb")
        assert result is None


class TestGetAliasesCacheKey:
    """Tests pour get_aliases_cache_key."""

    def test_returns_int_or_none(self):
        from src.app.data_loader import get_aliases_cache_key

        result = get_aliases_cache_key()
        assert result is None or isinstance(result, int)


# ═══════════════════════════════════════════════════════════════════
# sidebar – render functions
# ═══════════════════════════════════════════════════════════════════


class TestRenderDbInfo:
    """Tests pour render_db_info."""

    def test_no_db_path(self, mock_st):
        from src.app import sidebar as mod

        ms = mock_st(mod)
        mod.render_db_info("")
        ms.calls["caption"].assert_called()

    def test_nonexistent_db(self, mock_st):
        from src.app import sidebar as mod

        ms = mock_st(mod)
        mod.render_db_info("/does/not/exist.duckdb")
        ms.calls["warning"].assert_called()

    def test_existing_db(self, mock_st, tmp_path):
        from src.app import sidebar as mod

        ms = mock_st(mod)
        db_file = tmp_path / "test.duckdb"
        db_file.write_bytes(b"x" * 1024 * 1024)
        mod.render_db_info(str(db_file))
        ms.calls["caption"].assert_called()


class TestRenderNavigationTabs:
    """Tests pour render_navigation_tabs."""

    def test_few_pages_uses_tabs(self, mock_st):
        from src.app import sidebar as mod

        ms = mock_st(mod)
        # st.tabs retourne une liste de MagicMock context managers
        tab_mocks = [MagicMock() for _ in range(3)]
        for t in tab_mocks:
            t.__enter__ = lambda s: s
            t.__exit__ = lambda _s, *_a: None
        ms.calls["tabs"] = MagicMock(return_value=tab_mocks)
        ms._monkeypatch.setattr(mod.st, "tabs", ms.calls["tabs"])

        result = mod.render_navigation_tabs(
            pages=["Page1", "Page2", "Page3"],
            current_page="Page1",
        )
        assert result == "Page1"
        ms.calls["tabs"].assert_called_once()

    def test_many_pages_uses_radio(self, mock_st):
        from src.app import sidebar as mod

        ms = mock_st(mod)
        pages = [f"Page{i}" for i in range(10)]
        ms.calls["radio"] = MagicMock(return_value="Page0")
        ms._monkeypatch.setattr(mod.st, "radio", ms.calls["radio"])

        result = mod.render_navigation_tabs(
            pages=pages,
            current_page="Page0",
        )
        assert result == "Page0"
        ms.calls["radio"].assert_called_once()


class TestRenderQuickFilters:
    """Tests pour render_quick_filters."""

    def test_empty_playlists(self, mock_st):
        from src.app import sidebar as mod

        mock_st(mod)
        result = mod.render_quick_filters(
            playlists=[],
            selected_playlists=["Ranked"],
        )
        assert result == ["Ranked"]

    def test_with_playlists(self, mock_st):
        from src.app import sidebar as mod

        ms = mock_st(mod)
        ms.calls["multiselect"] = MagicMock(return_value=["Ranked", "BTB"])
        ms._monkeypatch.setattr(mod.st, "multiselect", ms.calls["multiselect"])

        result = mod.render_quick_filters(
            playlists=["Ranked", "BTB", "Quick Play"],
            selected_playlists=["Ranked", "BTB"],
        )
        assert result == ["Ranked", "BTB"]


class TestRenderPlayerSelectorSidebar:
    """Tests pour render_player_selector_sidebar."""

    def test_no_db_path(self, mock_st):
        from src.app import sidebar as mod

        mock_st(mod)
        result = mod.render_player_selector_sidebar(
            db_path="",
            xuid="123",
        )
        assert result is None

    def test_nonexistent_db_path(self, mock_st):
        from src.app import sidebar as mod

        mock_st(mod)
        result = mod.render_player_selector_sidebar(
            db_path="/does/not/exist.duckdb",
            xuid="123",
        )
        assert result is None

    def test_same_xuid_returns_none(self, mock_st, tmp_path):
        from src.app import sidebar as mod

        mock_st(mod)
        db_file = tmp_path / "test.duckdb"
        db_file.write_bytes(b"dummy")

        with patch.object(mod, "render_player_selector", return_value="123"):
            result = mod.render_player_selector_sidebar(
                db_path=str(db_file),
                xuid="123",
            )
        assert result is None
