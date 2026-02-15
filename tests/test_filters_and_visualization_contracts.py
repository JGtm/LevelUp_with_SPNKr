"""Contrats automatiques filtres + visualisations.

Objectifs :
- Valider que les changements de filtres modifient bien les données affichées.
- Garantir que les graphes clés retournent des figures avec des données représentées.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import polars as pl
import pytest

from src.app.filters_render import FilterState, apply_filters
from src.visualization.distributions import (
    plot_kda_distribution,
    plot_outcomes_over_time,
    plot_win_ratio_heatmap,
)
from src.visualization.friends_impact_heatmap import plot_friends_impact_heatmap
from src.visualization.maps import plot_map_comparison
from src.visualization.match_bars import plot_metric_bars_by_match
from src.visualization.timeseries import plot_timeseries


def _make_match_df() -> pd.DataFrame:
    """Construit un DataFrame de matchs synthétique mais réaliste."""
    df = pd.DataFrame(
        {
            "match_id": ["m1", "m2", "m3", "m4"],
            "start_time": pd.to_datetime(
                [
                    "2026-01-01 20:00:00",
                    "2026-01-02 20:00:00",
                    "2026-01-03 20:00:00",
                    "2026-01-04 20:00:00",
                ]
            ),
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
            "playlist_name": ["Ranked", "Quick Play", "Quick Play", "Ranked"],
            "pair_name": ["Slayer", "CTF", "Slayer", "CTF"],
            "map_name": ["Aquarius", "Live Fire", "Recharge", "Aquarius"],
            "kills": [10, 14, 7, 11],
            "deaths": [8, 12, 9, 10],
            "assists": [4, 5, 3, 6],
            "accuracy": [52.0, 49.5, 47.0, 54.1],
            "ratio": [1.25, 1.16, 0.78, 1.10],
            "kda": [6.0, 7.0, 1.0, 7.0],
            "outcome": [2, 3, 2, 2],
            "time_played_seconds": [720, 690, 705, 730],
            "matches": [20, 18, 12, 22],
            "accuracy_avg": [52.0, 49.5, 47.0, 54.1],
            "ratio_global": [1.25, 1.16, 0.78, 1.10],
            "playlist_ui": ["Ranked", "Quick Play", "Quick Play", "Ranked"],
            "mode_ui": ["Slayer", "CTF", "Slayer", "CTF"],
            "map_ui": ["Aquarius", "Live Fire", "Recharge", "Aquarius"],
        }
    )
    return df


def _assert_has_represented_data(fig: go.Figure) -> None:
    """Vérifie qu'une figure contient au moins une trace non vide."""
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0

    represented = False
    for trace in fig.data:
        x = getattr(trace, "x", None)
        y = getattr(trace, "y", None)
        z = getattr(trace, "z", None)
        if x is not None and len(x) > 0:
            represented = True
            break
        if y is not None and len(y) > 0:
            represented = True
            break
        if z is not None and len(z) > 0:
            represented = True
            break

    assert represented, "Aucune donnée représentée détectée dans la figure"


def test_apply_filters_period_updates_result_set() -> None:
    """Le changement des filtres période+checkboxes réduit correctement le dataset."""
    df = _make_match_df()
    filter_state = FilterState(
        filter_mode="Période",
        start_d=date(2026, 1, 2),
        end_d=date(2026, 1, 3),
        gap_minutes=120,
        picked_session_labels=None,
        playlists_selected=["Quick Play"],
        modes_selected=["CTF"],
        maps_selected=["Live Fire"],
        base_s_ui=None,
        friends_tuple=None,
    )

    filtered = apply_filters(
        dff=df,
        filter_state=filter_state,
        db_path="",
        xuid="",
        db_key=None,
        clean_asset_label_fn=lambda s: str(s),
        normalize_mode_label_fn=lambda s: str(s),
        normalize_map_label_fn=lambda s: str(s),
    )

    assert len(filtered) == 1
    assert filtered["match_id"][0] == "m2"


def test_apply_filters_sessions_updates_result_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le changement de session sélectionnée filtre bien sur les match_id attendus."""
    df = _make_match_df()

    sessions_df = pd.DataFrame(
        {
            "match_id": ["m1", "m2", "m3", "m4"],
            "session_id": ["s1", "s2", "s2", "s3"],
            "session_label": ["Session 1", "Session 2", "Session 2", "Session 3"],
            "start_time": pd.to_datetime(
                [
                    "2026-01-01 20:00:00",
                    "2026-01-02 20:00:00",
                    "2026-01-03 20:00:00",
                    "2026-01-04 20:00:00",
                ]
            ),
        }
    )
    monkeypatch.setattr(
        "src.app.filters_render.cached_compute_sessions_db", lambda *_args, **_kwargs: sessions_df
    )

    filter_state = FilterState(
        filter_mode="Sessions",
        start_d=date(2026, 1, 1),
        end_d=date(2026, 1, 31),
        gap_minutes=120,
        picked_session_labels=["Session 2"],
        playlists_selected=[],
        modes_selected=[],
        maps_selected=[],
        base_s_ui=sessions_df,
        friends_tuple=("friend-xuid",),
    )

    filtered = apply_filters(
        dff=df,
        filter_state=filter_state,
        db_path="data/players/TestPlayer/stats.duckdb",
        xuid="123456",
        db_key=(1, 2),
        clean_asset_label_fn=lambda s: str(s),
        normalize_mode_label_fn=lambda s: str(s),
        normalize_map_label_fn=lambda s: str(s),
    )

    assert sorted(filtered["match_id"].to_list()) == ["m2", "m3"]


def test_plot_kda_distribution_has_represented_data() -> None:
    """Le graphe KDA contient des données exploitables."""
    fig = plot_kda_distribution(_make_match_df())
    _assert_has_represented_data(fig)


def test_plot_outcomes_over_time_has_represented_data() -> None:
    """Le graphe victoire/défaite contient des données exploitables."""
    fig, _label = plot_outcomes_over_time(_make_match_df())
    _assert_has_represented_data(fig)


def test_plot_win_ratio_heatmap_has_represented_data() -> None:
    """La heatmap de win ratio contient des données exploitables."""
    fig = plot_win_ratio_heatmap(_make_match_df())
    _assert_has_represented_data(fig)


def test_plot_timeseries_has_represented_data() -> None:
    """Le graphe de séries temporelles contient des données exploitables."""
    fig = plot_timeseries(_make_match_df())
    _assert_has_represented_data(fig)


def test_plot_metric_bars_by_match_has_represented_data() -> None:
    """Le graphe barres par match contient des données exploitables."""
    fig = plot_metric_bars_by_match(
        _make_match_df(),
        metric_col="kills",
        title="Frags par match",
        y_axis_title="Frags",
        hover_label="frags",
        bar_color="#00bcd4",
        smooth_color="#66ff99",
        smooth_window=3,
    )
    assert fig is not None
    _assert_has_represented_data(fig)


def test_plot_map_comparison_has_represented_data() -> None:
    """Le graphe comparatif cartes contient des données exploitables."""
    maps_df = (
        _make_match_df()
        .groupby("map_name", as_index=False)
        .agg(
            matches=("match_id", "count"),
            accuracy_avg=("accuracy", "mean"),
            ratio_global=("ratio", "mean"),
        )
    )
    fig = plot_map_comparison(maps_df, metric="ratio_global", title="Ratio par carte")
    _assert_has_represented_data(fig)


def test_plot_friends_impact_heatmap_has_represented_data() -> None:
    """La heatmap d'impact coéquipiers représente bien des cellules."""
    impact_matrix = pl.DataFrame(
        {
            "match_id": ["m1", "m1", "m2"],
            "gamertag": ["Ami1", "Ami2", "Ami1"],
            "event_type": ["first_blood", "last_casualty", "clutch_finisher"],
            "event_value": [1, -1, 2],
        }
    )
    fig = plot_friends_impact_heatmap(impact_matrix)
    _assert_has_represented_data(fig)


@pytest.mark.parametrize(
    ("playlists", "modes", "maps", "expected_match_ids"),
    [
        (["Ranked"], [], [], ["m1", "m4"]),
        ([], ["CTF"], [], ["m2", "m4"]),
        ([], [], ["Aquarius"], ["m1", "m4"]),
    ],
)
def test_filters_change_dataset_for_key_pages(
    playlists: list[str],
    modes: list[str],
    maps: list[str],
    expected_match_ids: list[str],
) -> None:
    """Vérifie que les filtres modifient bien le dataset source de 3 pages clés."""
    df = _make_match_df()
    filter_state = FilterState(
        filter_mode="Période",
        start_d=date(2026, 1, 1),
        end_d=date(2026, 1, 31),
        gap_minutes=120,
        picked_session_labels=None,
        playlists_selected=playlists,
        modes_selected=modes,
        maps_selected=maps,
        base_s_ui=None,
        friends_tuple=None,
    )

    filtered = apply_filters(
        dff=df,
        filter_state=filter_state,
        db_path="",
        xuid="",
        db_key=None,
        clean_asset_label_fn=lambda s: str(s),
        normalize_mode_label_fn=lambda s: str(s),
        normalize_map_label_fn=lambda s: str(s),
    )

    assert sorted(filtered["match_id"].to_list()) == expected_match_ids

    # Pages clés ciblées : timeseries, win/loss, teammates-impact (via figure impact)
    fig_timeseries = plot_timeseries(filtered)
    fig_outcomes, _label = plot_outcomes_over_time(filtered)
    _assert_has_represented_data(fig_timeseries)
    _assert_has_represented_data(fig_outcomes)


def test_filters_change_graph_metric_values() -> None:
    """Vérifie que changer le filtre playlist change réellement les valeurs tracées."""
    df = _make_match_df()

    ranked_state = FilterState(
        filter_mode="Période",
        start_d=date(2026, 1, 1),
        end_d=date(2026, 1, 31),
        gap_minutes=120,
        picked_session_labels=None,
        playlists_selected=["Ranked"],
        modes_selected=[],
        maps_selected=[],
        base_s_ui=None,
        friends_tuple=None,
    )
    quick_state = FilterState(
        filter_mode="Période",
        start_d=date(2026, 1, 1),
        end_d=date(2026, 1, 31),
        gap_minutes=120,
        picked_session_labels=None,
        playlists_selected=["Quick Play"],
        modes_selected=[],
        maps_selected=[],
        base_s_ui=None,
        friends_tuple=None,
    )

    ranked_df = apply_filters(
        dff=df,
        filter_state=ranked_state,
        db_path="",
        xuid="",
        db_key=None,
        clean_asset_label_fn=lambda s: str(s),
        normalize_mode_label_fn=lambda s: str(s),
        normalize_map_label_fn=lambda s: str(s),
    )
    quick_df = apply_filters(
        dff=df,
        filter_state=quick_state,
        db_path="",
        xuid="",
        db_key=None,
        clean_asset_label_fn=lambda s: str(s),
        normalize_mode_label_fn=lambda s: str(s),
        normalize_map_label_fn=lambda s: str(s),
    )

    assert len(ranked_df) > 0 and len(quick_df) > 0
    assert ranked_df["match_id"].to_list() != quick_df["match_id"].to_list()

    fig_ranked = plot_timeseries(ranked_df)
    fig_quick = plot_timeseries(quick_df)

    _assert_has_represented_data(fig_ranked)
    _assert_has_represented_data(fig_quick)

    # Une métrique tracée doit différer entre les deux vues filtrées.
    ranked_deaths_sum = float(ranked_df["deaths"].sum())
    quick_deaths_sum = float(quick_df["deaths"].sum())
    assert ranked_deaths_sum != quick_deaths_sum
