"""Tests de non-régression pour le routeur de pages."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.app.page_router import dispatch_page
from src.ui.settings import AppSettings


@pytest.fixture
def router_ctx() -> dict[str, object]:
    """Contexte minimal reproductible pour les tests du routeur."""
    df = pd.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "start_time": pd.to_datetime(
                [datetime(2026, 1, 1, 20, 0), datetime(2026, 1, 2, 20, 0)]
            ),
            "kills": [12, 8],
            "deaths": [9, 10],
            "pair_name": ["Slayer", "CTF"],
            "map_name": ["Aquarius", "Recharge"],
            "session_id": ["legacy", "legacy"],
            "session_label": ["Legacy", "Legacy"],
        }
    )
    settings = AppSettings()

    renderers = {
        "render_last_match_page_fn": MagicMock(name="render_last_match_page_fn"),
        "render_match_search_page_fn": MagicMock(name="render_match_search_page_fn"),
        "render_citations_page_fn": MagicMock(name="render_citations_page_fn"),
        "render_session_comparison_page_fn": MagicMock(name="render_session_comparison_page_fn"),
        "render_timeseries_page_fn": MagicMock(name="render_timeseries_page_fn"),
        "render_win_loss_page_fn": MagicMock(name="render_win_loss_page_fn"),
        "render_teammates_page_fn": MagicMock(name="render_teammates_page_fn"),
        "render_match_history_page_fn": MagicMock(name="render_match_history_page_fn"),
        "render_media_tab_fn": MagicMock(name="render_media_tab_fn"),
        "render_career_page_fn": MagicMock(name="render_career_page_fn"),
        "render_settings_page_fn": MagicMock(name="render_settings_page_fn"),
    }

    return {
        "dff": df.copy(),
        "df": df.copy(),
        "base": df.copy(),
        "me_name": "TestPlayer",
        "xuid": "123456",
        "db_path": "data/players/TestPlayer/stats.duckdb",
        "db_key": (123, 456),
        "aliases_key": 1,
        "settings": settings,
        "picked_session_labels": ["Session A"],
        "waypoint_player": "TestPlayer",
        "gap_minutes": 120,
        "match_view_params": {
            "db_path": "data/players/TestPlayer/stats.duckdb",
            "xuid": "123456",
            "waypoint_player": "TestPlayer",
            "db_key": (123, 456),
            "settings": settings,
            "df_full": df,
            "render_match_view_fn": MagicMock(name="render_match_view_fn"),
            "normalize_mode_label_fn": lambda s: str(s),
            "format_score_label_fn": lambda *_: "score",
            "score_css_color_fn": lambda *_: "#fff",
            "format_datetime_fn": lambda *_: "date",
            "load_player_match_result_fn": MagicMock(name="load_player_match_result_fn"),
            "load_match_medals_fn": MagicMock(name="load_match_medals_fn"),
            "load_highlight_events_fn": MagicMock(name="load_highlight_events_fn"),
            "load_match_gamertags_fn": MagicMock(name="load_match_gamertags_fn"),
            "load_match_rosters_fn": MagicMock(name="load_match_rosters_fn"),
            "paris_tz": None,
        },
        **renderers,
        "cached_compute_sessions_db_fn": lambda *_args, **_kwargs: pd.DataFrame(
            {
                "match_id": ["m1", "m2"],
                "session_id": ["s1", "s2"],
                "session_label": ["Session 1", "Session 2"],
                "start_time": pd.to_datetime(
                    [datetime(2026, 1, 1, 20, 0), datetime(2026, 1, 2, 20, 0)]
                ),
            }
        ),
        "top_medals_fn": MagicMock(name="top_medals_fn"),
        "build_friends_opts_map_fn": MagicMock(name="build_friends_opts_map_fn"),
        "assign_player_colors_fn": MagicMock(name="assign_player_colors_fn"),
        "plot_multi_metric_bars_fn": MagicMock(name="plot_multi_metric_bars_fn"),
        "get_local_dbs_fn": MagicMock(name="get_local_dbs_fn"),
        "clear_caches_fn": MagicMock(name="clear_caches_fn"),
    }


def _dispatch(page: str, ctx: dict[str, object]) -> None:
    dispatch_page(
        page=page,
        dff=ctx["dff"],
        df=ctx["df"],
        base=ctx["base"],
        me_name=str(ctx["me_name"]),
        xuid=str(ctx["xuid"]),
        db_path=str(ctx["db_path"]),
        db_key=ctx["db_key"],
        aliases_key=ctx["aliases_key"],
        settings=ctx["settings"],
        picked_session_labels=ctx["picked_session_labels"],
        waypoint_player=str(ctx["waypoint_player"]),
        gap_minutes=int(ctx["gap_minutes"]),
        match_view_params=dict(ctx["match_view_params"]),
        render_last_match_page_fn=ctx["render_last_match_page_fn"],
        render_match_search_page_fn=ctx["render_match_search_page_fn"],
        render_citations_page_fn=ctx["render_citations_page_fn"],
        render_session_comparison_page_fn=ctx["render_session_comparison_page_fn"],
        render_timeseries_page_fn=ctx["render_timeseries_page_fn"],
        render_win_loss_page_fn=ctx["render_win_loss_page_fn"],
        render_teammates_page_fn=ctx["render_teammates_page_fn"],
        render_match_history_page_fn=ctx["render_match_history_page_fn"],
        render_media_tab_fn=ctx["render_media_tab_fn"],
        render_career_page_fn=ctx["render_career_page_fn"],
        render_settings_page_fn=ctx["render_settings_page_fn"],
        cached_compute_sessions_db_fn=ctx["cached_compute_sessions_db_fn"],
        top_medals_fn=ctx["top_medals_fn"],
        build_friends_opts_map_fn=ctx["build_friends_opts_map_fn"],
        assign_player_colors_fn=ctx["assign_player_colors_fn"],
        plot_multi_metric_bars_fn=ctx["plot_multi_metric_bars_fn"],
        get_local_dbs_fn=ctx["get_local_dbs_fn"],
        clear_caches_fn=ctx["clear_caches_fn"],
    )


@pytest.mark.regression
def test_dispatch_session_comparison_merges_session_columns(
    router_ctx: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La page comparaison reçoit bien un DataFrame enrichi (stats + sessions)."""
    monkeypatch.setattr(
        "src.app.filters.get_friends_xuids_for_sessions",
        lambda *_args, **_kwargs: (),
    )

    _dispatch("Comparaison de sessions", router_ctx)

    renderer = router_ctx["render_session_comparison_page_fn"]
    assert isinstance(renderer, MagicMock)
    renderer.assert_called_once()

    sessions_df = renderer.call_args.args[0]
    assert "kills" in sessions_df.columns
    assert "session_id" in sessions_df.columns
    assert "session_label" in sessions_df.columns
    assert set(sessions_df["session_id"].to_list()) == {"s1", "s2"}


@pytest.mark.regression
def test_dispatch_media_alias_routes_to_media_tab(router_ctx: dict[str, object]) -> None:
    """Alias historique 'Bibliothèque médias' route vers l'onglet médias."""
    _dispatch("Bibliothèque médias", router_ctx)

    media_renderer = router_ctx["render_media_tab_fn"]
    assert isinstance(media_renderer, MagicMock)
    media_renderer.assert_called_once()


@pytest.mark.regression
def test_dispatch_unknown_page_does_not_call_renderers(router_ctx: dict[str, object]) -> None:
    """Une page inconnue ne doit appeler aucun renderer."""
    _dispatch("Page inconnue", router_ctx)

    renderer_keys = [k for k in router_ctx if k.startswith("render_") and k.endswith("_fn")]
    for key in renderer_keys:
        renderer = router_ctx[key]
        if isinstance(renderer, MagicMock):
            renderer.assert_not_called()
