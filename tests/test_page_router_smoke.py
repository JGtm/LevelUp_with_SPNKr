"""Tests smoke du routeur de pages Streamlit.

Ces tests valident automatiquement que chaque page navigable est dispatchée
vers son renderer attendu sans lever d'exception.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.app.page_router import PAGES, dispatch_page
from src.ui.settings import AppSettings


def _sample_df() -> pd.DataFrame:
    """Construit un DataFrame minimal compatible avec le dispatch."""
    return pd.DataFrame(
        {
            "match_id": ["m1", "m2", "m3"],
            "start_time": pd.to_datetime(
                [
                    datetime(2026, 1, 1, 20, 0),
                    datetime(2026, 1, 2, 20, 0),
                    datetime(2026, 1, 3, 20, 0),
                ]
            ),
            "session_id": ["s1", "s2", "s2"],
            "session_label": ["Session 1", "Session 2", "Session 2"],
            "kills": [10, 12, 8],
            "deaths": [9, 11, 7],
            "pair_name": ["Slayer", "Slayer", "CTF"],
            "map_name": ["Aquarius", "Live Fire", "Recharge"],
        }
    )


@pytest.fixture
def dispatch_context() -> dict[str, object]:
    """Contexte standard pour appeler dispatch_page."""
    df = _sample_df()
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

    ctx: dict[str, object] = {
        "dff": df.copy(),
        "df": df.copy(),
        "base": df.copy(),
        "me_name": "TestPlayer",
        "xuid": "123456",
        "db_path": "data/players/TestPlayer/stats.duckdb",
        "db_key": (123, 456),
        "aliases_key": 1,
        "settings": settings,
        "picked_session_labels": ["Session 2"],
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
                "match_id": ["m1", "m2", "m3"],
                "session_id": ["s1", "s2", "s2"],
                "session_label": ["Session 1", "Session 2", "Session 2"],
                "start_time": pd.to_datetime(
                    [
                        datetime(2026, 1, 1, 20, 0),
                        datetime(2026, 1, 2, 20, 0),
                        datetime(2026, 1, 3, 20, 0),
                    ]
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
    return ctx


@pytest.mark.parametrize(
    ("page", "expected_renderer"),
    [
        ("Dernier match", "render_last_match_page_fn"),
        ("Match", "render_match_search_page_fn"),
        ("Citations", "render_citations_page_fn"),
        ("Comparaison de sessions", "render_session_comparison_page_fn"),
        ("Séries temporelles", "render_timeseries_page_fn"),
        ("Victoires/Défaites", "render_win_loss_page_fn"),
        ("Mes coéquipiers", "render_teammates_page_fn"),
        ("Historique des parties", "render_match_history_page_fn"),
        ("Médias", "render_media_tab_fn"),
        ("Carrière", "render_career_page_fn"),
        ("Paramètres", "render_settings_page_fn"),
    ],
)
def test_dispatch_page_routes_to_expected_renderer(
    page: str,
    expected_renderer: str,
    dispatch_context: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie qu'une page donnée appelle exactement le renderer attendu."""
    monkeypatch.setattr(
        "src.app.filters.get_friends_xuids_for_sessions",
        lambda *_args, **_kwargs: tuple(),
    )

    dispatch_page(
        page=page,
        dff=dispatch_context["dff"],
        df=dispatch_context["df"],
        base=dispatch_context["base"],
        me_name=str(dispatch_context["me_name"]),
        xuid=str(dispatch_context["xuid"]),
        db_path=str(dispatch_context["db_path"]),
        db_key=dispatch_context["db_key"],
        aliases_key=dispatch_context["aliases_key"],
        settings=dispatch_context["settings"],
        picked_session_labels=dispatch_context["picked_session_labels"],
        waypoint_player=str(dispatch_context["waypoint_player"]),
        gap_minutes=int(dispatch_context["gap_minutes"]),
        match_view_params=dict(dispatch_context["match_view_params"]),
        render_last_match_page_fn=dispatch_context["render_last_match_page_fn"],
        render_match_search_page_fn=dispatch_context["render_match_search_page_fn"],
        render_citations_page_fn=dispatch_context["render_citations_page_fn"],
        render_session_comparison_page_fn=dispatch_context["render_session_comparison_page_fn"],
        render_timeseries_page_fn=dispatch_context["render_timeseries_page_fn"],
        render_win_loss_page_fn=dispatch_context["render_win_loss_page_fn"],
        render_teammates_page_fn=dispatch_context["render_teammates_page_fn"],
        render_match_history_page_fn=dispatch_context["render_match_history_page_fn"],
        render_media_tab_fn=dispatch_context["render_media_tab_fn"],
        render_career_page_fn=dispatch_context["render_career_page_fn"],
        render_settings_page_fn=dispatch_context["render_settings_page_fn"],
        cached_compute_sessions_db_fn=dispatch_context["cached_compute_sessions_db_fn"],
        top_medals_fn=dispatch_context["top_medals_fn"],
        build_friends_opts_map_fn=dispatch_context["build_friends_opts_map_fn"],
        assign_player_colors_fn=dispatch_context["assign_player_colors_fn"],
        plot_multi_metric_bars_fn=dispatch_context["plot_multi_metric_bars_fn"],
        get_local_dbs_fn=dispatch_context["get_local_dbs_fn"],
        clear_caches_fn=dispatch_context["clear_caches_fn"],
    )

    renderer_keys = [
        key for key in dispatch_context if key.startswith("render_") and key.endswith("_fn")
    ]
    for renderer_key in renderer_keys:
        renderer = dispatch_context[renderer_key]
        if not isinstance(renderer, MagicMock):
            continue
        if renderer_key == expected_renderer:
            renderer.assert_called_once()
        else:
            renderer.assert_not_called()


def test_pages_constant_matches_expected_navigation() -> None:
    """Valide la liste canonique des pages navigables affichées dans l'app."""
    expected_pages = [
        "Séries temporelles",
        "Comparaison de sessions",
        "Dernier match",
        "Match",
        "Médias",
        "Citations",
        "Victoires/Défaites",
        "Mes coéquipiers",
        "Historique des parties",
        "Carrière",
        "Paramètres",
    ]
    assert expected_pages == PAGES
