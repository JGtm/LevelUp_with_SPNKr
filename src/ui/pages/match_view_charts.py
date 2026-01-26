"""Graphiques pour la page Match View - Expected vs Actual."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src.config import HALO_COLORS
from src.analysis.stats import format_mmss, extract_mode_category, compute_mode_category_averages
from src.visualization.theme import apply_halo_plot_style, get_legend_horizontal_bottom
from src.ui.pages.match_view_helpers import os_card


# =============================================================================
# Graphiques Expected vs Actual
# =============================================================================


def render_expected_vs_actual(
    row: pd.Series,
    pm: dict,
    colors: dict,
    df_full: pd.DataFrame | None = None,
) -> None:
    """Rend la section Réel vs Attendu avec moyenne historique par catégorie de mode."""
    team_mmr = pm.get("team_mmr")
    enemy_mmr = pm.get("enemy_mmr")
    delta_mmr = (team_mmr - enemy_mmr) if (team_mmr is not None and enemy_mmr is not None) else None

    mmr_cols = st.columns(3)
    with mmr_cols[0]:
        os_card("MMR d'équipe", f"{team_mmr:.1f}" if team_mmr is not None else "-")
    with mmr_cols[1]:
        os_card("MMR adverse", f"{enemy_mmr:.1f}" if enemy_mmr is not None else "-")
    with mmr_cols[2]:
        if delta_mmr is None:
            os_card("Écart MMR", "-")
        else:
            dm = float(delta_mmr)
            col = "var(--color-win)" if dm > 0 else ("var(--color-loss)" if dm < 0 else "var(--color-tie)")
            os_card("Écart MMR", f"{dm:+.1f}", "équipe - adverse", accent=col, kpi_color=col)

    def _ev_card(title: str, perf: dict, *, mode: str) -> None:
        count = perf.get("count")
        expected = perf.get("expected")
        if count is None or expected is None:
            os_card(title, "-", "")
            return

        delta = float(count) - float(expected)
        if delta == 0:
            delta_class = "text-neutral"
        else:
            good = delta > 0
            if mode == "inverse":
                good = not good
            delta_class = "text-positive" if good else "text-negative"

        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        sub = f"<span class='{delta_class} fw-bold'>{arrow} {delta:+.1f}</span>"
        os_card(title, f"{float(count):.0f} vs {float(expected):.1f}", sub)

    perf_k = pm.get("kills") or {}
    perf_d = pm.get("deaths") or {}
    perf_a = pm.get("assists") or {}

    st.subheader("Réel vs attendu")
    av_cols = st.columns(3)
    with av_cols[0]:
        _ev_card("Frags", perf_k, mode="normal")
    with av_cols[1]:
        _ev_card("Morts", perf_d, mode="inverse")
    with av_cols[2]:
        avg_life_last = row.get("average_life_seconds")
        os_card("Durée de vie moyenne", format_mmss(avg_life_last), "")

    # Calculer la moyenne historique par catégorie de mode
    mode_category = extract_mode_category(row.get("pair_name"))
    hist_avgs: dict[str, float | None] = {
        "avg_kills": None,
        "avg_deaths": None,
        "avg_assists": None,
        "avg_ratio": None,
        "match_count": 0,
    }
    if df_full is not None and len(df_full) >= 10:
        hist_avgs = compute_mode_category_averages(df_full, mode_category)

    # Graphique F / D / A
    labels = ["F", "D", "A"]
    actual_vals = [
        float(row.get("kills") or 0.0),
        float(row.get("deaths") or 0.0),
        float(row.get("assists") or 0.0),
    ]
    exp_vals = [
        perf_k.get("expected"),
        perf_d.get("expected"),
        perf_a.get("expected"),
    ]
    hist_vals = [
        hist_avgs.get("avg_kills"),
        hist_avgs.get("avg_deaths"),
        hist_avgs.get("avg_assists"),
    ]

    real_ratio = row.get("ratio")
    try:
        real_ratio_f = float(real_ratio) if real_ratio == real_ratio else None
    except Exception:
        real_ratio_f = None
    if real_ratio_f is None:
        denom = max(1.0, float(row.get("deaths") or 0.0))
        real_ratio_f = (float(row.get("kills") or 0.0) + float(row.get("assists") or 0.0)) / denom

    exp_fig = make_subplots(specs=[[{"secondary_y": True}]])

    bar_colors = [HALO_COLORS.green, HALO_COLORS.red, HALO_COLORS.cyan]
    exp_fig.add_trace(
        go.Bar(
            x=labels,
            y=exp_vals,
            name="Attendu (MMR)",
            marker=dict(
                color=bar_colors,
                pattern=dict(shape="/", fgcolor="rgba(255,255,255,0.75)", solidity=0.22),
            ),
            opacity=0.50,
            hovertemplate="%{x} (attendu): %{y:.1f}<extra></extra>",
        ),
        secondary_y=False,
    )
    exp_fig.add_trace(
        go.Bar(
            x=labels,
            y=actual_vals,
            name="Réel",
            marker_color=bar_colors,
            opacity=0.90,
            hovertemplate="%{x} (réel): %{y:.0f}<extra></extra>",
        ),
        secondary_y=False,
    )
    
    # Moyenne historique par catégorie (si disponible)
    if hist_avgs.get("match_count", 0) >= 10:
        exp_fig.add_trace(
            go.Scatter(
                x=labels,
                y=hist_vals,
                mode="markers+lines",
                name=f"Moyenne {mode_category} ({hist_avgs['match_count']} matchs)",
                line=dict(color=HALO_COLORS.violet, width=3, dash="dot"),
                marker=dict(size=10, symbol="diamond"),
                hovertemplate=f"%{{x}} (moy. {mode_category}): %{{y:.1f}}<extra></extra>",
            ),
            secondary_y=False,
        )
    
    exp_fig.add_trace(
        go.Scatter(
            x=labels,
            y=[real_ratio_f] * len(labels),
            mode="lines+markers",
            name="Ratio réel",
            line=dict(color=HALO_COLORS.amber, width=4),
            marker=dict(size=7),
            hovertemplate="ratio (réel): %{y:.2f}<extra></extra>",
        ),
        secondary_y=True,
    )
    
    # Ratio moyen historique (si disponible)
    hist_ratio = hist_avgs.get("avg_ratio")
    if hist_ratio is not None and hist_avgs.get("match_count", 0) >= 10:
        exp_fig.add_trace(
            go.Scatter(
                x=labels,
                y=[hist_ratio] * len(labels),
                mode="lines",
                name=f"Ratio moy. {mode_category}",
                line=dict(color=HALO_COLORS.violet, width=2, dash="dash"),
                hovertemplate=f"ratio moy. {mode_category}: %{{y:.2f}}<extra></extra>",
            ),
            secondary_y=True,
        )

    exp_fig.update_layout(
        barmode="group",
        height=360,
        margin=dict(l=40, r=20, t=30, b=90),
        legend=get_legend_horizontal_bottom(),
    )
    exp_fig.update_yaxes(title_text="F / D / A", rangemode="tozero", secondary_y=False)
    exp_fig.update_yaxes(title_text="Ratio", secondary_y=True)
    st.plotly_chart(exp_fig, width="stretch")

    # Folie meurtrière / Tirs à la tête
    _render_spree_headshots(row)


def _render_spree_headshots(row: pd.Series) -> None:
    """Rend le graphique folie meurtrière / tirs à la tête."""
    spree_v = pd.to_numeric(row.get("max_killing_spree"), errors="coerce")
    headshots_v = pd.to_numeric(row.get("headshot_kills"), errors="coerce")
    if (spree_v == spree_v) or (headshots_v == headshots_v):
        st.subheader("Folie meurtrière / Tirs à la tête")
        fig_sh = go.Figure()
        fig_sh.add_trace(
            go.Bar(
                x=["Folie meurtrière (max)", "Tirs à la tête"],
                y=[
                    float(spree_v) if (spree_v == spree_v) else 0.0,
                    float(headshots_v) if (headshots_v == headshots_v) else 0.0,
                ],
                marker_color=[HALO_COLORS.violet, HALO_COLORS.cyan],
                opacity=0.85,
                hovertemplate="%{x}: %{y:.0f}<extra></extra>",
            )
        )
        fig_sh.update_layout(
            height=260,
            margin=dict(l=40, r=20, t=30, b=60),
            showlegend=False,
        )
        fig_sh.update_yaxes(rangemode="tozero")
        st.plotly_chart(apply_halo_plot_style(fig_sh, height=260), width="stretch")


# =============================================================================
# Exports publics
# =============================================================================

__all__ = [
    "render_expected_vs_actual",
]
