"""Graphiques par carte (map)."""

import plotly.graph_objects as go
import polars as pl

from src.config import HALO_COLORS, PLOT_CONFIG
from src.visualization._compat import DataFrameLike, ensure_polars, to_pandas_for_plotly
from src.visualization.theme import apply_halo_plot_style, get_legend_horizontal_bottom


def plot_map_comparison(df_breakdown: DataFrameLike, metric: str, title: str) -> go.Figure:
    """Graphique de comparaison d'une métrique par carte.

    Args:
        df_breakdown: DataFrame issu de compute_map_breakdown.
        metric: Nom de la colonne à afficher (ratio_global, win_rate, accuracy_avg).
        title: Titre du graphique.

    Returns:
        Figure Plotly (barres horizontales).
    """
    colors = HALO_COLORS.as_dict()
    df_pl = ensure_polars(df_breakdown).drop_nulls(subset=[metric])

    if df_pl.is_empty():
        fig = go.Figure()
        fig.update_layout(
            height=PLOT_CONFIG.default_height, margin={"l": 40, "r": 20, "t": 30, "b": 40}
        )
        return apply_halo_plot_style(fig, height=PLOT_CONFIG.default_height)

    d = to_pandas_for_plotly(df_pl)

    fig = go.Figure(
        data=[
            go.Bar(
                x=d[metric],
                y=d["map_name"],
                orientation="h",
                marker_color=colors["cyan"],
                customdata=list(zip(d["matches"], d.get("accuracy_avg"), strict=False)),
                hovertemplate=(
                    "%{y}<br>value=%{x}<br>matches=%{customdata[0]}"
                    "<br>accuracy=%{customdata[1]:.2f}%<extra></extra>"
                ),
            )
        ]
    )
    fig.update_layout(
        height=PLOT_CONFIG.tall_height,
        title=title,
        margin={"l": 40, "r": 20, "t": 60, "b": 90},
        legend=get_legend_horizontal_bottom(),
    )

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.tall_height)


def plot_map_ratio_with_winloss(df_breakdown: DataFrameLike, title: str) -> go.Figure:
    """Graphique de ratio par carte avec taux de victoire/défaite.

    Args:
        df_breakdown: DataFrame issu de compute_map_breakdown.
        title: Titre du graphique.

    Returns:
        Figure Plotly avec barres empilées Win/Loss (+ autres statuts).
    """
    colors = HALO_COLORS.as_dict()
    df_pl = ensure_polars(df_breakdown).drop_nulls(subset=["win_rate", "loss_rate"])

    if df_pl.is_empty():
        fig = go.Figure()
        fig.update_layout(
            height=PLOT_CONFIG.default_height, margin={"l": 40, "r": 20, "t": 30, "b": 40}
        )
        return apply_halo_plot_style(fig, height=PLOT_CONFIG.default_height)

    # Complément: égalités / non terminés / inconnus -> affiché en "Autres".
    df_pl = df_pl.with_columns(
        (pl.lit(1.0) - pl.col("win_rate").cast(pl.Float64) - pl.col("loss_rate").cast(pl.Float64))
        .clip(0.0, 1.0)
        .alias("other_rate")
    )
    d = to_pandas_for_plotly(df_pl)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=d["win_rate"],
            y=d["map_name"],
            orientation="h",
            name="Taux de victoire",
            marker_color=colors["green"],
            opacity=0.70,
            customdata=d[["matches"]].values,
            hovertemplate="%{y}<br>win=%{x:.1%}<br>matchs=%{customdata[0]}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=d["loss_rate"],
            y=d["map_name"],
            orientation="h",
            name="Taux de défaite",
            marker_color=colors["red"],
            opacity=0.55,
            customdata=d[["matches"]].values,
            hovertemplate="%{y}<br>loss=%{x:.1%}<br>matchs=%{customdata[0]}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Bar(
            x=d["other_rate"],
            y=d["map_name"],
            orientation="h",
            name="Autres (égalité / non terminé)",
            marker_color=colors["violet"],
            opacity=0.35,
            customdata=d[["matches"]].values,
            hovertemplate="%{y}<br>autres=%{x:.1%}<br>matchs=%{customdata[0]}<extra></extra>",
        )
    )

    fig.update_layout(
        height=PLOT_CONFIG.tall_height,
        title=title,
        margin={"l": 40, "r": 20, "t": 60, "b": 90},
        barmode="stack",
        bargap=0.18,
        legend=get_legend_horizontal_bottom(),
    )
    fig.update_xaxes(title_text="Win / Loss", tickformat=".0%", range=[0, 1])

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.tall_height)
