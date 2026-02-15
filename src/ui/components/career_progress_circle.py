"""Composant cercle de progression pour le rang carrière Halo Infinite.

Affiche un indicateur gauge Plotly montrant la progression XP
vers le prochain rang.
"""

from __future__ import annotations

import plotly.graph_objects as go

from src.config import THEME_COLORS


def create_career_progress_gauge(
    current_xp: int,
    xp_for_next_rank: int,
    progress_pct: float,
    rank_name_fr: str,
    *,
    is_max_rank: bool = False,
    height: int = 280,
) -> go.Figure:
    """Crée un indicateur gauge de progression XP vers le prochain rang.

    Args:
        current_xp: XP actuel dans le rang courant.
        xp_for_next_rank: XP requis pour le prochain rang.
        progress_pct: Pourcentage de progression (0-100).
        rank_name_fr: Nom du rang en français.
        is_max_rank: True si le joueur est au rang maximum.
        height: Hauteur de la figure en pixels.

    Returns:
        Figure Plotly avec l'indicateur gauge.
    """
    if is_max_rank:
        progress_pct = 100.0
        subtitle = "Rang maximum atteint"
    else:
        subtitle = f"{current_xp:,} / {xp_for_next_rank:,} XP"

    # Couleur de la barre selon la progression
    if progress_pct >= 75:
        bar_color = "#00ff88"  # Vert vif
    elif progress_pct >= 50:
        bar_color = THEME_COLORS.accent  # Cyan Halo
    elif progress_pct >= 25:
        bar_color = "#ffaa00"  # Ambre
    else:
        bar_color = "#ff6666"  # Rouge doux

    bg_rgb = THEME_COLORS.bg_plot
    bg_color = f"rgb({bg_rgb[0]}, {bg_rgb[1]}, {bg_rgb[2]})"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=progress_pct,
            number={"suffix": "%", "font": {"size": 36, "color": "white"}},
            title={
                "text": f"<b>{rank_name_fr}</b><br><span style='font-size:12px;color:#aaa'>{subtitle}</span>",
                "font": {"size": 16, "color": "white"},
            },
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 0,
                    "tickcolor": "rgba(0,0,0,0)",
                    "dtick": 25,
                    "tickfont": {"size": 10, "color": "#666"},
                },
                "bar": {"color": bar_color, "thickness": 0.7},
                "bgcolor": "rgba(50, 60, 70, 0.3)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 25], "color": "rgba(255, 102, 102, 0.08)"},
                    {"range": [25, 50], "color": "rgba(255, 170, 0, 0.08)"},
                    {"range": [50, 75], "color": "rgba(51, 214, 255, 0.08)"},
                    {"range": [75, 100], "color": "rgba(0, 255, 136, 0.08)"},
                ],
                "threshold": {
                    "line": {"color": "white", "width": 2},
                    "thickness": 0.8,
                    "value": progress_pct,
                },
            },
        )
    )

    fig.update_layout(
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font={"color": "white"},
        height=height,
        margin={"t": 80, "b": 20, "l": 30, "r": 30},
    )

    return fig
