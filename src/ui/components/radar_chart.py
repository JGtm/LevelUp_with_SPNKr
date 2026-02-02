"""Composant graphe radar pour comparer des métriques entre joueurs.

Utilise Plotly pour générer des graphiques radar interactifs.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go


def create_radar_chart(
    data: list[dict[str, Any]],
    *,
    title: str | None = None,
    show_legend: bool = True,
    fill_opacity: float = 0.25,
    line_width: float = 2,
    height: int = 400,
) -> go.Figure:
    """Crée un graphe radar comparant des métriques entre plusieurs entités.

    Args:
        data: Liste de dicts avec format:
            [
                {
                    "name": "Joueur 1",
                    "values": [val1, val2, val3, ...],
                    "color": "#FF6B6B",  # optionnel
                },
                ...
            ]
        title: Titre du graphe (optionnel).
        show_legend: Afficher la légende.
        fill_opacity: Opacité du remplissage (0-1).
        line_width: Épaisseur des lignes.
        height: Hauteur du graphe en pixels.

    Returns:
        Figure Plotly.
    """
    fig = go.Figure()

    for item in data:
        name = item.get("name", "")
        values = item.get("values", [])
        color = item.get("color")

        # Fermer le polygone
        if values:
            values_closed = list(values) + [values[0]]
        else:
            values_closed = []

        trace_kwargs: dict[str, Any] = {
            "r": values_closed,
            "name": name,
            "fill": "toself",
            "fillcolor": color if color else None,
            "opacity": fill_opacity if color else 1.0,
            "line": {"width": line_width},
        }
        if color:
            trace_kwargs["line"]["color"] = color
            trace_kwargs["fillcolor"] = color

        fig.add_trace(go.Scatterpolar(**trace_kwargs))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                showticklabels=True,
                tickfont=dict(size=10),
            ),
        ),
        showlegend=show_legend,
        title=title,
        height=height,
        margin=dict(l=60, r=60, t=60 if title else 30, b=40),
    )

    return fig


def create_stats_per_minute_radar(
    players: list[dict[str, Any]],
    *,
    title: str = "Stats par minute",
    categories: list[str] | None = None,
    height: int = 350,
) -> go.Figure:
    """Crée un graphe radar pour les stats par minute (frags/morts/assists).

    Args:
        players: Liste de dicts avec format:
            [
                {
                    "name": "Joueur",
                    "kills_per_min": 0.8,
                    "deaths_per_min": 0.5,
                    "assists_per_min": 0.3,
                    "color": "#FF6B6B",  # optionnel
                },
                ...
            ]
        title: Titre du graphe.
        categories: Labels des axes (par défaut: Frags/min, Morts/min, Assists/min).
        height: Hauteur du graphe.

    Returns:
        Figure Plotly.
    """
    if categories is None:
        categories = ["Frags/min", "Morts/min", "Assists/min"]

    # Gestion du cas vide
    if not players:
        fig = go.Figure()
        fig.update_layout(title=dict(text=title, x=0.5, xanchor="center"), height=height)
        return fig

    # Normaliser les valeurs pour le radar (0-1)
    # Calculer les max pour chaque métrique
    max_kills = max((p.get("kills_per_min") or 0) for p in players) or 1
    max_deaths = max((p.get("deaths_per_min") or 0) for p in players) or 1
    max_assists = max((p.get("assists_per_min") or 0) for p in players) or 1

    fig = go.Figure()

    for player in players:
        name = player.get("name", "")
        kills = (player.get("kills_per_min") or 0) / max_kills
        deaths = (player.get("deaths_per_min") or 0) / max_deaths
        assists = (player.get("assists_per_min") or 0) / max_assists
        color = player.get("color")

        # Valeurs originales pour le hover
        orig_kills = player.get("kills_per_min") or 0
        orig_deaths = player.get("deaths_per_min") or 0
        orig_assists = player.get("assists_per_min") or 0

        values = [kills, deaths, assists, kills]  # Fermer le polygone
        theta = categories + [categories[0]]

        customdata = [
            [orig_kills],
            [orig_deaths],
            [orig_assists],
            [orig_kills],
        ]

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=theta,
                name=name,
                fill="toself",
                line=dict(width=2, color=color) if color else dict(width=2),
                fillcolor=color,
                opacity=0.3,
                customdata=customdata,
                hovertemplate="%{theta}: %{customdata[0]:.2f}<extra>%{fullData.name}</extra>",
            )
        )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1.1],
                showticklabels=False,
            ),
        ),
        showlegend=True,
        title=dict(text=title, x=0.5, xanchor="center"),
        height=height,
        margin=dict(l=60, r=60, t=50, b=40),
    )

    return fig


def create_performance_radar(
    players: list[dict[str, Any]],
    *,
    title: str = "Profil de performance",
    height: int = 400,
) -> go.Figure:
    """Crée un graphe radar pour le profil de performance (objectif/frags/morts/assists).

    Args:
        players: Liste de dicts avec format:
            [
                {
                    "name": "Joueur",
                    "objective_score": 50,  # Score objectif normalisé 0-100
                    "kills": 12,
                    "deaths": 8,
                    "assists": 5,
                    "color": "#FF6B6B",  # optionnel
                },
                ...
            ]
        title: Titre du graphe.
        height: Hauteur du graphe.

    Returns:
        Figure Plotly.
    """
    categories = ["Objectif", "Frags", "Survie", "Assists"]

    # Gestion du cas vide
    if not players:
        fig = go.Figure()
        fig.update_layout(title=dict(text=title, x=0.5, xanchor="center"), height=height)
        return fig

    # Calculer les max pour normalisation
    max_obj = max((p.get("objective_score") or 0) for p in players) or 1
    max_kills = max((p.get("kills") or 0) for p in players) or 1
    # Pour survie : moins de morts = mieux, donc on inverse
    max_deaths = max((p.get("deaths") or 1) for p in players) or 1
    max_assists = max((p.get("assists") or 0) for p in players) or 1

    fig = go.Figure()

    for player in players:
        name = player.get("name", "")
        color = player.get("color")

        obj = (player.get("objective_score") or 0) / max_obj
        kills_norm = (player.get("kills") or 0) / max_kills
        # Inverser pour survie : moins de morts = valeur plus élevée
        deaths_raw = player.get("deaths") or 0
        survival = 1 - (deaths_raw / max_deaths) if max_deaths > 0 else 0
        assists_norm = (player.get("assists") or 0) / max_assists

        values = [obj, kills_norm, survival, assists_norm, obj]
        theta = categories + [categories[0]]

        # Valeurs originales pour hover
        orig_obj = player.get("objective_score") or 0
        orig_kills = player.get("kills") or 0
        orig_deaths = deaths_raw
        orig_assists = player.get("assists") or 0

        customdata = [
            [f"{orig_obj:.1f}"],
            [f"{orig_kills}"],
            [f"{orig_deaths} morts"],
            [f"{orig_assists}"],
            [f"{orig_obj:.1f}"],
        ]

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=theta,
                name=name,
                fill="toself",
                line=dict(width=2, color=color) if color else dict(width=2),
                fillcolor=color,
                opacity=0.3,
                customdata=customdata,
                hovertemplate="%{theta}: %{customdata[0]}<extra>%{fullData.name}</extra>",
            )
        )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1.1],
                showticklabels=False,
            ),
        ),
        showlegend=True,
        title=dict(text=title, x=0.5, xanchor="center"),
        height=height,
        margin=dict(l=60, r=60, t=50, b=40),
    )

    return fig


__all__ = [
    "create_radar_chart",
    "create_stats_per_minute_radar",
    "create_performance_radar",
]
