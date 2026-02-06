"""Graphiques pour la page Match View - Expected vs Actual."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.analysis.stats import compute_mode_category_averages, extract_mode_category, format_mmss
from src.config import HALO_COLORS
from src.ui.pages.match_view_helpers import os_card
from src.visualization.theme import apply_halo_plot_style, get_legend_horizontal_bottom

# =============================================================================
# Graphiques Expected vs Actual
# =============================================================================


def render_expected_vs_actual(
    row: pd.Series,
    pm: dict,
    colors: dict,
    df_full: pd.DataFrame | None = None,
    *,
    db_path: str | None = None,
    xuid: str | None = None,
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
            col = (
                "var(--color-win)"
                if dm > 0
                else ("var(--color-loss)" if dm < 0 else "var(--color-tie)")
            )
            os_card("Écart MMR", f"{dm:+.1f}", "équipe - adverse", accent=col, kpi_color=col)

    def _ev_card(title: str, perf: dict, *, mode: str) -> None:
        count = perf.get("count")
        expected = perf.get("expected")

        # Si count est disponible mais expected est None (DuckDB v4), afficher quand même la valeur réelle
        if count is None:
            os_card(title, "-", "")
            return

        # Si expected est None, afficher seulement la valeur réelle sans comparaison
        if expected is None:
            os_card(title, f"{float(count):.0f}", "Valeur réelle (comparaison indisponible)")
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
            marker={
                "color": bar_colors,
                "pattern": {"shape": "/", "fgcolor": "rgba(255,255,255,0.75)", "solidity": 0.22},
            },
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

    # Moyenne historique par catégorie (si disponible) -> en barres
    if hist_avgs.get("match_count", 0) >= 10:
        exp_fig.add_trace(
            go.Bar(
                x=labels,
                y=hist_vals,
                name=f"Moyenne hist. {mode_category} ({hist_avgs['match_count']} matchs)",
                marker={
                    "color": bar_colors,
                    "pattern": {
                        "shape": ".",
                        "fgcolor": "rgba(255,255,255,0.75)",
                        "solidity": 0.10,
                    },
                },
                opacity=0.35,
                hovertemplate=f"%{{x}} (moy. hist. {mode_category}): %{{y:.1f}}<extra></extra>",
            ),
            secondary_y=False,
        )

    # Ratio moyen historique (si disponible) - affiché comme ligne de référence
    hist_ratio = hist_avgs.get("avg_ratio")
    if hist_ratio is not None and hist_avgs.get("match_count", 0) >= 10:
        exp_fig.add_trace(
            go.Scatter(
                x=labels,
                y=[hist_ratio] * len(labels),
                mode="lines",
                name=f"Ratio moy. {mode_category}",
                line={"color": HALO_COLORS.violet, "width": 2, "dash": "dash"},
                hovertemplate=f"ratio moy. {mode_category}: %{{y:.2f}}<extra></extra>",
            ),
            secondary_y=True,
        )

    exp_fig.update_layout(
        barmode="group",
        height=360,
        margin={"l": 40, "r": 20, "t": 50, "b": 90},  # Augmenter le top margin pour l'annotation
        legend=get_legend_horizontal_bottom(),
        annotations=[
            {
                "x": 1.0,  # Position à droite
                "y": 1.05,  # Au-dessus du graphique
                "xref": "paper",
                "yref": "paper",
                "text": f"Ratio K/D/A: <b>{real_ratio_f:.2f}</b>",
                "showarrow": False,
                "font": {"size": 14, "color": HALO_COLORS.amber},
                "bgcolor": "rgba(0,0,0,0.5)",
                "bordercolor": HALO_COLORS.amber,
                "borderwidth": 1,
                "borderpad": 4,
            }
        ],
    )
    exp_fig.update_yaxes(title_text="F / D / A", rangemode="tozero", secondary_y=False)
    # Masquer l'axe secondaire si pas de ratio historique (pour éviter confusion)
    if hist_ratio is None:
        exp_fig.update_yaxes(visible=False, secondary_y=True)
    else:
        exp_fig.update_yaxes(title_text="Ratio", secondary_y=True)
    st.plotly_chart(exp_fig, width="stretch")

    # Folie meurtrière / Tirs à la tête / Frags parfaits
    _render_spree_headshots(
        row,
        df_full=df_full,
        db_path=db_path,
        xuid=xuid,
    )


def _render_spree_headshots(
    row: pd.Series,
    df_full: pd.DataFrame | None = None,
    *,
    db_path: str | None = None,
    xuid: str | None = None,
) -> None:
    """Rend le graphique folie meurtrière / tirs à la tête / frags parfaits.

    Ajoute, si possible, une série de barres correspondant à la moyenne
    historique sur la même catégorie custom (alignée sidebar).
    Les frags parfaits sont comptés via les médailles Perfect (medals_earned).
    """
    spree_v = pd.to_numeric(row.get("max_killing_spree"), errors="coerce")
    headshots_v = pd.to_numeric(row.get("headshot_kills"), errors="coerce")
    mode_category = extract_mode_category(row.get("pair_name"))
    hist_avgs: dict[str, float | None] = {
        "avg_max_killing_spree": None,
        "avg_headshot_kills": None,
        "avg_perfect_kills": None,
        "match_count": 0,
    }
    if df_full is not None and len(df_full) >= 10:
        hist_avgs_full = compute_mode_category_averages(df_full, mode_category)
        hist_avgs["avg_max_killing_spree"] = hist_avgs_full.get("avg_max_killing_spree")
        hist_avgs["avg_headshot_kills"] = hist_avgs_full.get("avg_headshot_kills")
        hist_avgs["match_count"] = hist_avgs_full.get("match_count", 0)

    # Frags parfaits du match courant et moyenne historique (médailles Perfect)
    perfect_current = 0
    if db_path and xuid and str(db_path).endswith(".duckdb"):
        try:
            from src.data.repositories.duckdb_repo import DuckDBRepository

            repo = DuckDBRepository(db_path, str(xuid).strip())
            match_id = str(row.get("match_id", "")).strip()
            if match_id:
                counts = repo.count_perfect_kills_by_match([match_id])
                perfect_current = counts.get(match_id, 0)
            # Moyenne historique par catégorie (même filtre que spree/headshots)
            if df_full is not None and hist_avgs.get("match_count", 0) >= 10:
                mask = df_full["pair_name"].apply(extract_mode_category) == mode_category
                filtered = df_full.loc[mask]
                if len(filtered) >= 10:
                    match_ids = filtered["match_id"].astype(str).tolist()
                    perfect_counts = repo.count_perfect_kills_by_match(match_ids)
                    total = sum(perfect_counts.get(mid, 0) for mid in match_ids)
                    hist_avgs["avg_perfect_kills"] = total / len(match_ids)
        except Exception:
            pass

    has_spree_or_hs = (spree_v == spree_v) or (headshots_v == headshots_v)
    if has_spree_or_hs or (db_path and xuid):
        st.subheader("Folie meurtrière / Tirs à la tête / Frags parfaits")
        fig_sh = go.Figure()

        x_labels = ["Folie meurtrière (max)", "Tirs à la tête", "Frags parfaits"]
        bar_colors = [HALO_COLORS.violet, HALO_COLORS.cyan, HALO_COLORS.green]
        real_vals = [
            float(spree_v) if (spree_v == spree_v) else 0.0,
            float(headshots_v) if (headshots_v == headshots_v) else 0.0,
            float(perfect_current),
        ]
        fig_sh.add_trace(
            go.Bar(
                x=x_labels,
                y=real_vals,
                name="Réel",
                marker_color=bar_colors,
                opacity=0.85,
                hovertemplate="%{x} (réel): %{y:.0f}<extra></extra>",
            )
        )

        if hist_avgs.get("match_count", 0) >= 10:
            avg_perfect = hist_avgs.get("avg_perfect_kills")
            hist_vals = [
                float(hist_avgs.get("avg_max_killing_spree") or 0.0),
                float(hist_avgs.get("avg_headshot_kills") or 0.0),
                float(avg_perfect) if avg_perfect is not None else 0.0,
            ]
            fig_sh.add_trace(
                go.Bar(
                    x=x_labels,
                    y=hist_vals,
                    name=f"Moyenne hist. {mode_category} ({hist_avgs['match_count']} matchs)",
                    marker={
                        "color": bar_colors,
                        "pattern": {
                            "shape": ".",
                            "fgcolor": "rgba(255,255,255,0.75)",
                            "solidity": 0.10,
                        },
                    },
                    opacity=0.35,
                    hovertemplate=f"%{{x}} (moy. hist. {mode_category}): %{{y:.1f}}<extra></extra>",
                )
            )

        fig_sh.update_layout(
            barmode="group",
            height=260,
            margin={"l": 40, "r": 20, "t": 30, "b": 60},
            legend=get_legend_horizontal_bottom(),
        )
        fig_sh.update_yaxes(rangemode="tozero")
        st.plotly_chart(apply_halo_plot_style(fig_sh, height=260), width="stretch")


# =============================================================================
# Exports publics
# =============================================================================

__all__ = [
    "render_expected_vs_actual",
]
