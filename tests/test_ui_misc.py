"""Tests pour src/ui/perf.py et src/ui/sections/source.py — Sprint 7ter (7t.7).

Couvre perf.py (mesure de performance) et fonctions pures de source.py.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import polars as pl

# ============================================================================
# perf.py
# ============================================================================


class TestPerfEnabled:
    def test_disabled_by_default(self, monkeypatch):
        from src.ui import perf as mod

        monkeypatch.setattr(mod.st, "session_state", {})
        assert mod.perf_enabled() is False

    def test_enabled(self, monkeypatch):
        from src.ui import perf as mod

        monkeypatch.setattr(mod.st, "session_state", {"perf_enabled": True})
        assert mod.perf_enabled() is True


class TestPerfResetRun:
    def test_reset_when_enabled(self, monkeypatch):
        from src.ui import perf as mod

        state = {"perf_enabled": True, "_perf_timings_ms": [{"section": "test", "ms": 10}]}
        monkeypatch.setattr(mod.st, "session_state", state)
        mod.perf_reset_run()
        assert state["_perf_timings_ms"] == []

    def test_noop_when_disabled(self, monkeypatch):
        from src.ui import perf as mod

        state = {"_perf_timings_ms": [{"section": "test", "ms": 10}]}
        monkeypatch.setattr(mod.st, "session_state", state)
        mod.perf_reset_run()
        # Should NOT reset since perf_enabled is False
        assert len(state["_perf_timings_ms"]) == 1


class TestPerfSection:
    def test_records_timing(self, monkeypatch):
        from src.ui import perf as mod

        state = {"perf_enabled": True, "_perf_timings_ms": []}
        monkeypatch.setattr(mod.st, "session_state", state)

        with mod.perf_section("test_section"):
            time.sleep(0.01)

        assert len(state["_perf_timings_ms"]) == 1
        assert state["_perf_timings_ms"][0]["section"] == "test_section"
        assert state["_perf_timings_ms"][0]["ms"] > 0

    def test_noop_when_disabled(self, monkeypatch):
        from src.ui import perf as mod

        state = {}
        monkeypatch.setattr(mod.st, "session_state", state)

        with mod.perf_section("test_section"):
            pass

        assert "_perf_timings_ms" not in state


class TestPerfDataframe:
    def test_empty_returns_schema(self, monkeypatch):
        from src.ui import perf as mod

        monkeypatch.setattr(mod.st, "session_state", {})
        df = mod.perf_dataframe()
        assert isinstance(df, pl.DataFrame)
        assert df.is_empty()
        assert "section" in df.columns
        assert "ms" in df.columns

    def test_with_data(self, monkeypatch):
        from src.ui import perf as mod

        state = {
            "_perf_timings_ms": [
                {"section": "load", "ms": 50.0},
                {"section": "render", "ms": 30.0},
            ]
        }
        monkeypatch.setattr(mod.st, "session_state", state)
        df = mod.perf_dataframe()
        assert len(df) == 2
        assert df["section"].to_list() == ["load", "render"]


class TestRenderPerfPanel:
    def test_renders_without_error(self, mock_st):
        from src.ui import perf as mod

        ms = mock_st(mod)
        ms.session_state["perf_enabled"] = False
        ms.set_columns_dynamic()

        # Should not raise
        mod.render_perf_panel(location="sidebar")

    def test_renders_with_data(self, mock_st):
        from src.ui import perf as mod

        ms = mock_st(mod)
        ms.session_state["perf_enabled"] = True
        ms.session_state["_perf_timings_ms"] = [
            {"section": "test", "ms": 42.0},
        ]
        ms.set_columns_dynamic()

        mod.render_perf_panel(location="main")


# ============================================================================
# sections/source.py — fonctions pures
# ============================================================================


class TestDefaultIdentityFromSecrets:
    def test_from_env(self, monkeypatch):
        from src.ui.sections import source as mod

        # Mock st.secrets to raise (no secrets)
        monkeypatch.setattr(mod.st, "secrets", MagicMock(get=MagicMock(side_effect=Exception)))
        monkeypatch.setenv("OPENSPARTAN_DEFAULT_GAMERTAG", "TestGT")
        monkeypatch.setenv("OPENSPARTAN_DEFAULT_XUID", "1234567890123")

        identity, wp = mod._default_identity_from_secrets()
        assert identity == "TestGT"

    def test_from_defaults(self, monkeypatch):
        from src.ui.sections import source as mod

        monkeypatch.setattr(mod.st, "secrets", MagicMock(get=MagicMock(side_effect=Exception)))
        monkeypatch.delenv("OPENSPARTAN_DEFAULT_GAMERTAG", raising=False)
        monkeypatch.delenv("OPENSPARTAN_DEFAULT_XUID", raising=False)
        monkeypatch.delenv("OPENSPARTAN_DEFAULT_WAYPOINT_PLAYER", raising=False)

        identity, wp = mod._default_identity_from_secrets()
        # Should fallback to DEFAULT_PLAYER_GAMERTAG from config
        assert isinstance(identity, str)
        assert isinstance(wp, str)

    def test_from_secrets(self, monkeypatch):
        from src.ui.sections import source as mod

        secrets_mock = MagicMock()
        secrets_mock.get.return_value = {
            "gamertag": "SecretGT",
            "xuid": "9876543210123",
            "waypoint_player": "SecretWP",
        }
        monkeypatch.setattr(mod.st, "secrets", secrets_mock)
        monkeypatch.delenv("OPENSPARTAN_DEFAULT_GAMERTAG", raising=False)

        identity, wp = mod._default_identity_from_secrets()
        assert identity == "SecretGT"
        assert wp == "SecretWP"
