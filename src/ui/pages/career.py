"""Page Carrière — Progression du rang Halo Infinite.

Affiche le rang actuel, une gauge de progression XP, et l'historique
de progression dans le temps.
"""

from __future__ import annotations

import logging

import plotly.graph_objects as go
import streamlit as st

from src.config import THEME_COLORS
from src.ui.career_ranks import (
    format_career_rank_label_fr,
    get_rank_icon_path,
)
from src.ui.components.career_progress_circle import create_career_progress_gauge
from src.visualization.theme import apply_halo_plot_style

logger = logging.getLogger(__name__)


def _load_career_data(db_path: str, xuid: str) -> dict | None:
    """Charge les dernières données de rang carrière depuis DuckDB.

    Returns:
        Dict avec rank, rank_name, rank_tier, current_xp, etc. ou None.
    """
    try:
        import duckdb

        conn = duckdb.connect(db_path, read_only=True)
        try:
            result = conn.execute(
                """SELECT rank, rank_name, rank_tier, current_xp,
                          xp_for_next_rank, xp_total, is_max_rank,
                          adornment_path, recorded_at
                   FROM career_progression
                   WHERE xuid = ?
                   ORDER BY recorded_at DESC
                   LIMIT 1""",
                (xuid,),
            ).fetchone()

            if result:
                return {
                    "rank": result[0],
                    "rank_name": result[1],
                    "rank_tier": result[2],
                    "current_xp": result[3],
                    "xp_for_next_rank": result[4],
                    "xp_total": result[5],
                    "is_max_rank": bool(result[6]),
                    "adornment_path": result[7],
                    "recorded_at": result[8],
                }
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"Impossible de charger career_progression: {e}")

    return None


def _load_career_history(db_path: str, xuid: str, limit: int = 50) -> list[dict]:
    """Charge l'historique de progression depuis DuckDB.

    Returns:
        Liste de dicts ordonnés par date croissante.
    """
    try:
        import duckdb

        conn = duckdb.connect(db_path, read_only=True)
        try:
            rows = conn.execute(
                """SELECT rank, rank_name, rank_tier, current_xp,
                          xp_for_next_rank, xp_total, is_max_rank,
                          recorded_at
                   FROM career_progression
                   WHERE xuid = ?
                   ORDER BY recorded_at ASC
                   LIMIT ?""",
                (xuid, limit),
            ).fetchall()

            return [
                {
                    "rank": r[0],
                    "rank_name": r[1],
                    "rank_tier": r[2],
                    "current_xp": r[3],
                    "xp_for_next_rank": r[4],
                    "xp_total": r[5],
                    "is_max_rank": bool(r[6]),
                    "recorded_at": r[7],
                }
                for r in rows
            ]
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"Impossible de charger career_history: {e}")
        return []


def _create_xp_history_chart(history: list[dict]) -> go.Figure | None:
    """Crée un graphique d'historique XP total dans le temps."""
    if len(history) < 2:
        return None

    dates = [h["recorded_at"] for h in history]
    xp_totals = [h["xp_total"] or 0 for h in history]

    # Texte au survol avec le rang
    hover_texts = []
    for h in history:
        name = h.get("rank_name", "")
        tier = h.get("rank_tier", "")
        label = format_career_rank_label_fr(tier=tier, title=name, grade=None)
        hover_texts.append(f"Rang {h['rank']}: {label}<br>XP total: {h['xp_total']:,}")

    bg_rgb = THEME_COLORS.bg_plot
    bg_color = f"rgb({bg_rgb[0]}, {bg_rgb[1]}, {bg_rgb[2]})"

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=xp_totals,
            mode="lines+markers",
            name="XP total",
            line={"color": THEME_COLORS.accent, "width": 2},
            marker={"size": 6, "color": THEME_COLORS.accent},
            hovertext=hover_texts,
            hoverinfo="text",
        )
    )

    fig.update_layout(
        title="Progression XP",
        xaxis_title="Date",
        yaxis_title="XP total",
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font={"color": "white"},
        height=350,
        margin={"t": 40, "b": 40, "l": 60, "r": 20},
        xaxis={"gridcolor": "rgba(255,255,255,0.05)"},
        yaxis={"gridcolor": "rgba(255,255,255,0.1)"},
    )

    apply_halo_plot_style(fig)

    return fig


def render_career_page(
    *,
    db_path: str,
    xuid: str,
    db_key: str | None = None,
) -> None:
    """Rend la page Carrière avec rang actuel, gauge et historique."""
    st.header("Carrière")

    # Charger les données
    career_data = _load_career_data(db_path, xuid)

    if career_data is None:
        st.info(
            "Aucune donnée de carrière disponible. "
            "Synchronisez vos données pour voir votre progression de rang."
        )
        return

    rank_number = career_data.get("rank", 0)
    rank_name = career_data.get("rank_name", "")
    rank_tier = career_data.get("rank_tier", "")
    current_xp = career_data.get("current_xp", 0) or 0
    xp_for_next = career_data.get("xp_for_next_rank", 1) or 1
    xp_total = career_data.get("xp_total", 0) or 0
    is_max = career_data.get("is_max_rank", False)

    # Calcul progression
    if is_max:
        progress_pct = 100.0
    elif xp_for_next > 0:
        progress_pct = min(100.0, (current_xp / xp_for_next) * 100)
    else:
        progress_pct = 0.0

    # Label FR du rang
    rank_label_fr = format_career_rank_label_fr(tier=rank_tier, title=rank_name, grade=None)
    if not rank_label_fr:
        rank_label_fr = rank_name or f"Rang {rank_number}"

    # --- Header avec icone + metriques ---
    col_icon, col_info, col_gauge = st.columns([1, 2, 2])

    with col_icon:
        # Icone du rang (si disponible)
        icon_path = get_rank_icon_path(rank_number) if rank_number else None
        if icon_path and icon_path.exists():
            st.image(str(icon_path), width=120)
        else:
            # Fallback : afficher le numéro de rang
            st.markdown(
                f"<div style='text-align:center;font-size:48px;color:{THEME_COLORS.accent}'>"
                f"{rank_number}</div>",
                unsafe_allow_html=True,
            )

    with col_info:
        st.subheader(rank_label_fr)

        # Métriques
        m1, m2 = st.columns(2)
        with m1:
            st.metric("Rang", f"{rank_number} / 272")
            st.metric("XP total", f"{xp_total:,}")
        with m2:
            if is_max:
                st.metric("Statut", "Rang maximum")
            else:
                st.metric("XP actuel", f"{current_xp:,}")
                st.metric("XP prochain rang", f"{xp_for_next:,}")

    with col_gauge:
        # Gauge de progression
        gauge_fig = create_career_progress_gauge(
            current_xp=current_xp,
            xp_for_next_rank=xp_for_next,
            progress_pct=progress_pct,
            rank_name_fr=rank_label_fr,
            is_max_rank=is_max,
        )
        st.plotly_chart(gauge_fig, key="career_gauge")

    # --- Historique de progression ---
    st.divider()

    history = _load_career_history(db_path, xuid)

    if history:
        history_fig = _create_xp_history_chart(history)
        if history_fig:
            st.plotly_chart(history_fig, key="career_xp_history")

        # Tableau récapitulatif des derniers snapshots
        with st.expander("Historique détaillé", expanded=False):
            # Afficher les 10 derniers snapshots (du plus récent au plus ancien)
            recent = list(reversed(history[-10:]))
            for snap in recent:
                snap_label = format_career_rank_label_fr(
                    tier=snap.get("rank_tier", ""),
                    title=snap.get("rank_name", ""),
                    grade=None,
                )
                date_str = str(snap.get("recorded_at", ""))[:19]
                xp_t = snap.get("xp_total", 0) or 0
                st.text(f"{date_str}  |  Rang {snap['rank']}: {snap_label}  |  XP: {xp_t:,}")
    else:
        st.info(
            "Pas encore d'historique de progression. Les données seront collectées à chaque synchronisation."
        )
