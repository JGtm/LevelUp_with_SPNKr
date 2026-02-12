"""Graphiques pour la page Coéquipiers.

Fonctions de visualisation pour comparer les performances avec les coéquipiers.
"""

from __future__ import annotations

import polars as pl

# Type alias pour compatibilité DataFrame
try:
    import pandas as pd

    DataFrameType = pd.DataFrame | pl.DataFrame
except ImportError:
    pd = None  # type: ignore[assignment]
    DataFrameType = pl.DataFrame  # type: ignore[misc]

import plotly.graph_objects as go
import streamlit as st

from src.config import HALO_COLORS
from src.visualization import (
    plot_average_life,
    plot_per_minute_timeseries,
    plot_performance_timeseries,
    plot_timeseries,
    plot_trio_metric,
)


def render_comparison_charts(
    sub: pd.DataFrame,
    friend_sub: pd.DataFrame,
    me_name: str,
    friend_name: str,
    friend_xuid: str,
    show_smooth: bool = True,
) -> None:
    """Affiche les graphes de comparaison côte à côte.

    Args:
        sub: DataFrame des matchs du joueur principal.
        friend_sub: DataFrame des matchs du coéquipier.
        me_name: Nom du joueur principal.
        friend_name: Nom du coéquipier.
        friend_xuid: XUID du coéquipier.
        show_smooth: Afficher les courbes lissées.
    """
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            plot_timeseries(sub, title=f"{me_name} — matchs avec {friend_name}"),
            width="stretch",
            key=f"friend_ts_me_{friend_xuid}",
        )
    with c2:
        if friend_sub.empty:
            st.warning("Impossible de charger les stats du coéquipier sur les matchs partagés.")
        else:
            st.plotly_chart(
                plot_timeseries(friend_sub, title=f"{friend_name} — matchs avec {me_name}"),
                width="stretch",
                key=f"friend_ts_fr_{friend_xuid}",
            )

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(
            plot_per_minute_timeseries(sub, title=f"{me_name} — stats/min (avec {friend_name})"),
            width="stretch",
            key=f"friend_pm_me_{friend_xuid}",
        )
    with c4:
        if not friend_sub.empty:
            st.plotly_chart(
                plot_per_minute_timeseries(
                    friend_sub,
                    title=f"{friend_name} — stats/min (avec {me_name})",
                ),
                width="stretch",
                key=f"friend_pm_fr_{friend_xuid}",
            )

    c5, c6 = st.columns(2)
    with c5:
        if not sub.dropna(subset=["average_life_seconds"]).empty:
            st.plotly_chart(
                plot_average_life(sub, title=f"{me_name} — Durée de vie (avec {friend_name})"),
                width="stretch",
                key=f"friend_life_me_{friend_xuid}",
            )
    with c6:
        if not friend_sub.empty and not friend_sub.dropna(subset=["average_life_seconds"]).empty:
            st.plotly_chart(
                plot_average_life(
                    friend_sub, title=f"{friend_name} — Durée de vie (avec {me_name})"
                ),
                width="stretch",
                key=f"friend_life_fr_{friend_xuid}",
            )

    # Graphes de performance
    c7, c8 = st.columns(2)
    with c7:
        st.plotly_chart(
            plot_performance_timeseries(
                sub, title=f"{me_name} — Performance (avec {friend_name})", show_smooth=show_smooth
            ),
            width="stretch",
            key=f"friend_perf_me_{friend_xuid}",
        )
    with c8:
        if not friend_sub.empty:
            st.plotly_chart(
                plot_performance_timeseries(
                    friend_sub,
                    title=f"{friend_name} — Performance (avec {me_name})",
                    show_smooth=show_smooth,
                ),
                width="stretch",
                key=f"friend_perf_fr_{friend_xuid}",
            )


def render_metric_bar_charts(
    series: list[tuple[str, pd.DataFrame]],
    colors_by_name: dict[str, str],
    show_smooth: bool,
    key_suffix: str,
    plot_fn,
) -> None:
    """Affiche les graphes de barres pour les métriques.

    Args:
        series: Liste de tuples (nom, DataFrame).
        colors_by_name: Mapping nom → couleur.
        show_smooth: Afficher les courbes lissées.
        key_suffix: Suffixe pour les clés Streamlit.
        plot_fn: Fonction de tracé.
    """
    fig_spree = plot_fn(
        series,
        metric_col="max_killing_spree",
        title="Folie meurtrière (max)",
        y_axis_title="Folie meurtrière (max)",
        hover_label="folie meurtrière",
        colors=colors_by_name,
        smooth_window=10,
        show_smooth_lines=show_smooth,
    )
    if fig_spree is None:
        st.info("Aucune donnée de folie meurtrière (max) sur ces matchs.")
    else:
        st.plotly_chart(fig_spree, width="stretch", key=f"friend_spree_multi_{key_suffix}")

    fig_hs = plot_fn(
        series,
        metric_col="headshot_kills",
        title="Tirs à la tête",
        y_axis_title="Tirs à la tête",
        hover_label="tirs à la tête",
        colors=colors_by_name,
        smooth_window=10,
        show_smooth_lines=show_smooth,
    )
    if fig_hs is None:
        st.info("Aucune donnée de tirs à la tête sur ces matchs.")
    else:
        st.plotly_chart(fig_hs, width="stretch", key=f"friend_hs_multi_{key_suffix}")

    fig_pk = plot_fn(
        series,
        metric_col="perfect_kills",
        title="Frags parfaits",
        y_axis_title="Frags parfaits",
        hover_label="frags parfaits",
        colors=colors_by_name,
        smooth_window=10,
        show_smooth_lines=show_smooth,
    )
    if fig_pk is None:
        st.info("Aucune donnée de frags parfaits sur ces matchs.")
    else:
        st.plotly_chart(fig_pk, width="stretch", key=f"friend_pk_multi_{key_suffix}")


def render_outcome_bar_chart(dfr: pd.DataFrame) -> None:
    """Affiche le graphe de distribution des résultats.

    Args:
        dfr: DataFrame avec colonne 'my_outcome'.
    """
    outcome_map = {2: "Victoire", 3: "Défaite", 1: "Égalité", 4: "Non terminé"}
    dfr = dfr.copy()
    dfr["my_outcome_label"] = dfr["my_outcome"].map(outcome_map).fillna("?")
    counts = (
        dfr["my_outcome_label"]
        .value_counts()
        .reindex(["Victoire", "Défaite", "Égalité", "Non terminé", "?"], fill_value=0)
    )
    colors = HALO_COLORS.as_dict()
    fig = go.Figure(data=[go.Bar(x=counts.index, y=counts.values, marker_color=colors["cyan"])])
    fig.update_layout(height=300, margin={"l": 40, "r": 20, "t": 30, "b": 40})
    st.plotly_chart(fig, width="stretch")


def render_trio_charts(
    d_self: pd.DataFrame,
    d_f1: pd.DataFrame,
    d_f2: pd.DataFrame,
    me_name: str,
    f1_name: str,
    f2_name: str,
    f1_xuid: str,
    f2_xuid: str,
) -> None:
    """Affiche les graphes trio (moi + 2 coéquipiers).

    Args:
        d_self: DataFrame du joueur principal.
        d_f1: DataFrame du premier coéquipier.
        d_f2: DataFrame du deuxième coéquipier.
        me_name: Nom du joueur principal.
        f1_name: Nom du premier coéquipier.
        f2_name: Nom du deuxième coéquipier.
        f1_xuid: XUID du premier coéquipier.
        f2_xuid: XUID du deuxième coéquipier.
    """
    names = (me_name, f1_name, f2_name)

    st.plotly_chart(
        plot_trio_metric(
            d_self, d_f1, d_f2, metric="kills", names=names, title="Frags", y_title="Frags"
        ),
        width="stretch",
        key=f"trio_kills_{f1_xuid}_{f2_xuid}",
    )
    st.plotly_chart(
        plot_trio_metric(
            d_self, d_f1, d_f2, metric="deaths", names=names, title="Morts", y_title="Morts"
        ),
        width="stretch",
        key=f"trio_deaths_{f1_xuid}_{f2_xuid}",
    )
    st.plotly_chart(
        plot_trio_metric(
            d_self,
            d_f1,
            d_f2,
            metric="assists",
            names=names,
            title="Assistances",
            y_title="Assists",
        ),
        width="stretch",
        key=f"trio_assists_{f1_xuid}_{f2_xuid}",
    )
    st.plotly_chart(
        plot_trio_metric(
            d_self,
            d_f1,
            d_f2,
            metric="ratio",
            names=names,
            title="FDA",
            y_title="FDA",
            y_format=".3f",
        ),
        width="stretch",
        key=f"trio_ratio_{f1_xuid}_{f2_xuid}",
    )
    st.plotly_chart(
        plot_trio_metric(
            d_self,
            d_f1,
            d_f2,
            metric="accuracy",
            names=names,
            title="Précision",
            y_title="%",
            y_suffix="%",
            y_format=".2f",
        ),
        width="stretch",
        key=f"trio_accuracy_{f1_xuid}_{f2_xuid}",
    )
    st.plotly_chart(
        plot_trio_metric(
            d_self,
            d_f1,
            d_f2,
            metric="average_life_seconds",
            names=names,
            title="Durée de vie moyenne",
            y_title="Secondes",
            y_format=".1f",
        ),
        width="stretch",
        key=f"trio_life_{f1_xuid}_{f2_xuid}",
    )
    st.plotly_chart(
        plot_trio_metric(
            d_self,
            d_f1,
            d_f2,
            metric="performance",
            names=names,
            title="Performance",
            y_title="Score",
            y_format=".1f",
        ),
        width="stretch",
        key=f"trio_performance_{f1_xuid}_{f2_xuid}",
    )
