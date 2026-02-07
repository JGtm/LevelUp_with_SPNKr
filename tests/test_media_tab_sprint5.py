"""Tests Sprint 5 – Page Médias (media_tab.py)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import polars as pl

from src.ui.pages.media_tab import _format_short_date, render_media_tab
from src.ui.settings import AppSettings


def test_format_short_date() -> None:
    assert _format_short_date(None) == ""
    # Objet avec strftime
    from datetime import datetime

    dt = datetime(2026, 2, 7, 12, 0)
    assert _format_short_date(dt) == "07/02/26"
    # Chaîne
    assert "26" in _format_short_date("2026-02-07 14:30:00") or "2026" in _format_short_date(
        "2026-02-07"
    )


def test_render_media_tab_no_settings_media_disabled() -> None:
    """Si media_enabled=False, un message d'info est affiché."""
    settings = AppSettings(media_enabled=False)
    with patch("src.ui.pages.media_tab.st") as m_st:
        render_media_tab(settings=settings)
        m_st.subheader.assert_called_once()
        m_st.info.assert_called_once()
        assert (
            "désactivés" in m_st.info.call_args[0][0]
            or "médias" in m_st.info.call_args[0][0].lower()
        )


def test_render_media_tab_no_db_path() -> None:
    """Sans db_path en session, message d'info."""
    settings = AppSettings(media_enabled=True)
    mock_identity = type(
        "Identity",
        (),
        {"xuid": "", "xuid_or_gamertag": "", "xuid_fallback": ""},
    )()
    with (
        patch("src.ui.pages.media_tab.st") as m_st,
        patch("src.app.state.get_default_identity", return_value=mock_identity),
        patch("src.app.profile.resolve_xuid", return_value=None),
    ):
        m_st.session_state = {"db_path": "", "xuid_input": ""}
        render_media_tab(settings=settings)
        m_st.info.assert_called()
        calls = [c[0][0] for c in m_st.info.call_args_list]
        assert any(
            c and ("profil" in c.lower() or "duckdb" in c.lower() or "sélectionne" in c.lower())
            for c in calls
        )


def test_render_media_tab_empty_media(tmp_path: Path) -> None:
    """Avec DB sans médias (load_media_for_ui retourne vide), message d'info."""
    db_path = tmp_path / "stats.duckdb"
    db_path.touch()

    mock_identity = type(
        "Identity",
        (),
        {"xuid": "x1", "xuid_or_gamertag": "Test", "xuid_fallback": "x1"},
    )()

    with (
        patch("src.ui.pages.media_tab.st") as m_st,
        patch(
            "src.ui.pages.media_tab.MediaIndexer.load_media_for_ui",
            return_value=pl.DataFrame(),
        ),
        patch("src.app.state.get_default_identity", return_value=mock_identity),
        patch("src.app.profile.resolve_xuid", return_value="x1"),
    ):
        m_st.session_state = {"db_path": str(db_path), "xuid_input": ""}
        render_media_tab(settings=AppSettings(media_enabled=True))
    m_st.info.assert_called()
    calls = [c[0][0] for c in m_st.info.call_args_list]
    assert any(c and "indexé" in c for c in calls)
