"""Graphiques de séries temporelles."""

from __future__ import annotations

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from src.config import HALO_COLORS, PLOT_CONFIG
from src.ui.components.chart_annotations import add_extreme_annotations
from src.visualization._compat import (
    DataFrameLike,
    ensure_polars,
    ensure_polars_series,
    smart_scatter,
)
from src.visualization.theme import apply_halo_plot_style, get_legend_horizontal_bottom


def _normalize_df(df: DataFrameLike) -> pl.DataFrame:
    """Normalise un DataFrame en Polars (compat arrière)."""
    return ensure_polars(df)


def _rolling_mean(series: pl.Series, window: int = 10) -> pl.Series:
    """Calcule la moyenne mobile.

    Args:
        series: Série Polars (accepte aussi Pandas pour compat arrière).
        window: Taille de la fenêtre.

    Returns:
        Série Polars avec moyenne mobile.
    """
    w = int(window) if window and window > 0 else 1
    if not isinstance(series, pl.Series):
        series = ensure_polars_series(series)
    return series.rolling_mean(window_size=w, min_samples=1)


def _build_kda_customdata(d: pl.DataFrame) -> tuple[list, str]:
    """Construit le customdata et le template hover commun pour graphiques KDA.

    Args:
        d: DataFrame trié avec colonnes kills, deaths, assists, accuracy, ratio.

    Returns:
        Tuple (customdata, common_hover).
    """
    common_hover = (
        "frags=%{customdata[0]} morts=%{customdata[1]} assistances=%{customdata[2]}<br>"
        "précision=%{customdata[3]}% ratio=%{customdata[4]:.3f}<extra></extra>"
    )
    accuracy = d["accuracy"].cast(pl.Float64, strict=False).fill_null(0).round(2)
    customdata = list(
        zip(
            d["kills"].to_list(),
            d["deaths"].to_list(),
            d["assists"].to_list(),
            accuracy.to_list(),
            d["ratio"].to_list(),
            strict=False,
        )
    )
    return customdata, common_hover


def _add_kda_traces(
    fig: go.Figure,
    x_idx: list[int],
    d: pl.DataFrame,
    customdata: list,
    common_hover: str,
    colors: dict,
) -> None:
    """Ajoute les traces Kills/Deaths/Ratio au subplot KDA."""
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=d["kills"].to_list(),
            name="Frags",
            marker_color=colors["cyan"],
            opacity=PLOT_CONFIG.bar_opacity,
            alignmentgroup="kda_main",
            offsetgroup="kills",
            width=0.42,
            customdata=customdata,
            hovertemplate=common_hover,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=d["deaths"].to_list(),
            name="Morts",
            marker_color=colors["red"],
            opacity=PLOT_CONFIG.bar_opacity_secondary,
            alignmentgroup="kda_main",
            offsetgroup="deaths",
            width=0.42,
            customdata=customdata,
            hovertemplate=common_hover,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        smart_scatter(
            x=x_idx,
            y=d["ratio"].to_list(),
            mode="lines",
            name="Ratio",
            line={"width": PLOT_CONFIG.line_width, "color": colors["green"]},
            customdata=customdata,
            hovertemplate=common_hover,
        ),
        secondary_y=True,
    )


def plot_timeseries(df: DataFrameLike, title: str = "Frags / Morts / Ratio") -> go.Figure:
    """Graphique principal: Kills/Deaths/Ratio dans le temps."""
    df_pl = pl.DataFrame() if df is None else ensure_polars(df)

    if df_pl.is_empty():
        fig = go.Figure()
        fig.add_annotation(
            text="Aucune donnée disponible",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16},
        )
        return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.tall_height)

    fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])
    colors = HALO_COLORS.as_dict()
    d = df_pl.sort("start_time")
    x_idx = list(range(len(d)))

    customdata, common_hover = _build_kda_customdata(d)
    _add_kda_traces(fig, x_idx, d, customdata, common_hover, colors)

    fig.update_layout(
        title=title,
        legend=get_legend_horizontal_bottom(),
        margin={"l": 40, "r": 20, "t": 80, "b": 90},
        hovermode="x unified",
        barmode="group",
        bargap=0.15,
        bargroupgap=0.06,
    )
    fig.update_xaxes(type="category")
    fig.update_yaxes(title_text="Frags / Morts", rangemode="tozero", secondary_y=False)
    fig.update_yaxes(title_text="Ratio", secondary_y=True)

    labels = d["start_time"].dt.strftime("%m-%d %H:%M").to_list()
    step = max(1, len(labels) // 10) if len(labels) > 1 else 1
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
    )

    add_extreme_annotations(
        fig,
        x_idx,
        d["ratio"].to_list(),
        metric_name="ratio",
        show_max=True,
        show_min=False,
        max_color="#FFD700",
        secondary_y=True,
    )

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.tall_height)


def plot_assists_timeseries(df: DataFrameLike, title: str = "Assistances") -> go.Figure:
    """Graphique des assistances dans le temps.

    Args:
        df: DataFrame avec colonnes assists, start_time, etc.
        title: Titre du graphique.

    Returns:
        Figure Plotly.
    """
    df_pl = ensure_polars(df)

    colors = HALO_COLORS.as_dict()
    d = df_pl.sort("start_time")
    x_idx = list(range(len(d)))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").to_list()
    step = max(1, len(labels) // 10) if len(labels) > 1 else 1

    accuracy = d["accuracy"].cast(pl.Float64, strict=False).fill_null(0).round(2)
    customdata = list(
        zip(
            d["kills"].to_list(),
            d["deaths"].to_list(),
            d["assists"].to_list(),
            accuracy.to_list(),
            d["ratio"].to_list(),
            d["map_name"].fill_null("").to_list(),
            d["playlist_name"].fill_null("").to_list(),
            d["match_id"].to_list(),
            strict=False,
        )
    )
    hover = (
        "assistances=%{y}<br>"
        "frags=%{customdata[0]} morts=%{customdata[1]}<br>"
        "précision=%{customdata[3]}% ratio=%{customdata[4]:.3f}<extra></extra>"
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=d["assists"].to_list(),
            name="Assistances",
            marker_color=colors["violet"],
            opacity=PLOT_CONFIG.bar_opacity,
            customdata=customdata,
            hovertemplate=hover,
        )
    )

    assists_series = d["assists"].cast(pl.Float64, strict=False)
    smooth = _rolling_mean(assists_series, window=10)
    fig.add_trace(
        smart_scatter(
            x=x_idx,
            y=smooth.to_list(),
            mode="lines",
            name="Moyenne (lissée)",
            line={"width": PLOT_CONFIG.line_width, "color": colors["green"]},
            hovertemplate="moyenne=%{y:.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 60, "b": 90},
        hovermode="x unified",
        legend=get_legend_horizontal_bottom(),
    )
    fig.update_yaxes(title_text="Assistances", rangemode="tozero")
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
        type="category",
    )

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


def _add_permin_rolling_lines(
    fig: go.Figure,
    x_idx: list[int],
    kpm: pl.Series,
    dpm: pl.Series,
    apm: pl.Series,
    colors: dict[str, str],
) -> None:
    """Ajoute les 3 courbes de moyenne mobile par minute (frags, morts, assistances).

    Args:
        fig: Figure Plotly à enrichir.
        x_idx: Index des matchs.
        kpm: Série kills per minute.
        dpm: Série deaths per minute.
        apm: Série assists per minute.
        colors: Dict de couleurs HALO.
    """
    fig.add_trace(
        smart_scatter(
            x=x_idx,
            y=_rolling_mean(kpm, window=10).to_list(),
            mode="lines",
            name="Moy. frags/min",
            line={"width": PLOT_CONFIG.line_width, "color": colors["cyan"]},
            hovertemplate="moy=%{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        smart_scatter(
            x=x_idx,
            y=_rolling_mean(dpm, window=10).to_list(),
            mode="lines",
            name="Moy. morts/min",
            line={"width": PLOT_CONFIG.line_width, "color": colors["red"], "dash": "dot"},
            hovertemplate="moy=%{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        smart_scatter(
            x=x_idx,
            y=_rolling_mean(apm, window=10).to_list(),
            mode="lines",
            name="Moy. assist./min",
            line={"width": PLOT_CONFIG.line_width, "color": colors["violet"], "dash": "dot"},
            hovertemplate="moy=%{y:.2f}<extra></extra>",
        )
    )


def plot_per_minute_timeseries(
    df: DataFrameLike, title: str = "Frags / Morts / Assistances par minute"
) -> go.Figure:
    """Graphique des stats par minute.

    Args:
        df: DataFrame avec colonnes kills_per_min, deaths_per_min, assists_per_min.
        title: Titre du graphique.

    Returns:
        Figure Plotly.
    """
    df_pl = ensure_polars(df)

    colors = HALO_COLORS.as_dict()
    d = df_pl.sort("start_time")
    x_idx = list(range(len(d)))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").to_list()
    step = max(1, len(labels) // 10) if len(labels) > 1 else 1

    time_played = d["time_played_seconds"].cast(pl.Float64, strict=False)
    customdata = list(
        zip(
            time_played.to_list(),
            d["kills"].to_list(),
            d["deaths"].to_list(),
            d["assists"].to_list(),
            d["match_id"].to_list(),
            strict=False,
        )
    )

    kpm = d["kills_per_min"].cast(pl.Float64, strict=False)
    dpm = d["deaths_per_min"].cast(pl.Float64, strict=False)
    apm = d["assists_per_min"].cast(pl.Float64, strict=False)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=kpm.to_list(),
            name="Frags/min",
            marker_color=colors["cyan"],
            opacity=PLOT_CONFIG.bar_opacity,
            customdata=customdata,
            hovertemplate=(
                "frags/min=%{y:.2f}<br>"
                "temps joué=%{customdata[0]:.0f}s (frags=%{customdata[1]:.0f})<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=dpm.to_list(),
            name="Morts/min",
            marker_color=colors["red"],
            opacity=PLOT_CONFIG.bar_opacity_secondary,
            customdata=customdata,
            hovertemplate=(
                "morts/min=%{y:.2f}<br>"
                "temps joué=%{customdata[0]:.0f}s (morts=%{customdata[2]:.0f})<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=apm.to_list(),
            name="Assist./min",
            marker_color=colors["violet"],
            opacity=PLOT_CONFIG.bar_opacity_secondary,
            customdata=customdata,
            hovertemplate=(
                "assist./min=%{y:.2f}<br>"
                "temps joué=%{customdata[0]:.0f}s (assistances=%{customdata[3]:.0f})<extra></extra>"
            ),
        )
    )

    _add_permin_rolling_lines(fig, x_idx, kpm, dpm, apm, colors)

    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 60, "b": 90},
        hovermode="x unified",
        legend=get_legend_horizontal_bottom(),
        barmode="group",
        bargap=0.15,
        bargroupgap=0.06,
    )
    fig.update_yaxes(title_text="Par minute", rangemode="tozero")
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
        type="category",
    )

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


def plot_accuracy_last_n(df: DataFrameLike, n: int) -> go.Figure:
    """Graphique de précision sur les N derniers matchs.

    Args:
        df: DataFrame avec colonne accuracy.
        n: Nombre de matchs à afficher.

    Returns:
        Figure Plotly.
    """
    df_pl = ensure_polars(df)

    colors = HALO_COLORS.as_dict()
    d = df_pl.drop_nulls(subset=["accuracy"]).tail(n)

    fig = go.Figure(
        data=[
            smart_scatter(
                x=d["start_time"].to_list(),
                y=d["accuracy"].to_list(),
                mode="lines",
                name="Accuracy",
                line={"width": PLOT_CONFIG.line_width, "color": colors["violet"]},
                hovertemplate="précision=%{y:.2f}%<extra></extra>",
            )
        ]
    )
    fig.update_layout(height=PLOT_CONFIG.short_height, margin={"l": 40, "r": 20, "t": 30, "b": 40})
    fig.update_yaxes(title_text="%", rangemode="tozero")

    return apply_halo_plot_style(fig, height=PLOT_CONFIG.short_height)


# Re-exports depuis timeseries_combat (compat backward — Sprint 16)
from src.visualization.timeseries_combat import (  # noqa: E402, F401
    plot_average_life,
    plot_damage_dealt_taken,
    plot_performance_timeseries,
    plot_rank_score,
    plot_shots_accuracy,
    plot_spree_headshots_accuracy,
    plot_streak_chart,
)
