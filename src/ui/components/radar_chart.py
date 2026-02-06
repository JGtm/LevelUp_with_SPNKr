"""Composant graphe radar pour comparer des métriques entre joueurs.

Utilise Plotly pour générer des graphiques radar interactifs.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

from src.config import THEME_COLORS
from src.visualization.theme import apply_halo_plot_style


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
        values_closed = list(values) + [values[0]] if values else []

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
        polar={
            "radialaxis": {
                "visible": True,
                "showticklabels": True,
                "tickfont": {"size": 10},
            },
        },
        showlegend=show_legend,
        title=title,
        height=height,
        margin={"l": 60, "r": 60, "t": 60 if title else 30, "b": 40},
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
        fig.update_layout(title={"text": title, "x": 0.5, "xanchor": "center"}, height=height)
        return fig

    # Utiliser des seuils de référence FIXES pour une échelle absolue
    # Ces valeurs représentent des performances "excellentes" dans Halo Infinite
    # Ainsi, les joueurs sont comparés à une référence objective, pas entre eux
    REF_KILLS_PER_MIN = 1.2  # Un excellent joueur fait ~1.2 kills/min
    REF_DEATHS_PER_MIN = 1.0  # Un joueur moyen meurt ~1 fois/min
    REF_ASSISTS_PER_MIN = 0.6  # Un bon support fait ~0.6 assists/min

    fig = go.Figure()

    for player in players:
        name = player.get("name", "")
        color = player.get("color")

        # Valeurs originales
        orig_kills = player.get("kills_per_min") or 0
        orig_deaths = player.get("deaths_per_min") or 0
        orig_assists = player.get("assists_per_min") or 0

        # Normaliser par rapport aux seuils de référence (avec cap à 1.0)
        kills = min(orig_kills / REF_KILLS_PER_MIN, 1.0)
        deaths = min(orig_deaths / REF_DEATHS_PER_MIN, 1.0)
        assists = min(orig_assists / REF_ASSISTS_PER_MIN, 1.0)

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
                line={"width": 2, "color": color} if color else {"width": 2},
                fillcolor=color,
                opacity=0.3,
                customdata=customdata,
                hovertemplate="%{theta}: %{customdata[0]:.2f}<extra>%{fullData.name}</extra>",
            )
        )

    fig.update_layout(
        polar={
            "radialaxis": {
                "visible": True,
                "range": [0, 1.1],
                "showticklabels": False,
            },
        },
        showlegend=True,
        title={"text": title, "x": 0.5, "xanchor": "center"},
        height=height,
        margin={"l": 60, "r": 60, "t": 50, "b": 40},
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
        fig.update_layout(title={"text": title, "x": 0.5, "xanchor": "center"}, height=height)
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
                line={"width": 2, "color": color} if color else {"width": 2},
                fillcolor=color,
                opacity=0.3,
                customdata=customdata,
                hovertemplate="%{theta}: %{customdata[0]}<extra>%{fullData.name}</extra>",
            )
        )

    fig.update_layout(
        polar={
            "radialaxis": {
                "visible": True,
                "range": [0, 1.1],
                "showticklabels": False,
            },
        },
        showlegend=True,
        title={"text": title, "x": 0.5, "xanchor": "center"},
        height=height,
        margin={"l": 60, "r": 60, "t": 50, "b": 40},
    )

    return fig


# =============================================================================
# Sprint 8.2 : Radar de participation (PersonalScores)
# =============================================================================


def create_participation_radar(
    participation_data: list[dict[str, Any]],
    *,
    title: str = "Profil de participation",
    height: int = 400,
    show_values: bool = True,
) -> go.Figure:
    """Crée un radar de participation basé sur les PersonalScores.

    Axes : Frags, Assists, Objectifs, Véhicules, Survie (inverse pénalités).

    Args:
        participation_data: Liste de dicts avec format:
            [
                {
                    "name": "Match 1" ou "Joueur",
                    "kill_score": 700,      # Points kills
                    "assist_score": 150,    # Points assists
                    "objective_score": 300, # Points objectifs
                    "vehicle_score": 50,    # Points véhicules
                    "penalty_score": -100,  # Points pénalités (négatif)
                    "color": "#FF6B6B",     # optionnel
                },
                ...
            ]
        title: Titre du graphe.
        height: Hauteur du graphe.
        show_values: Afficher les valeurs dans le hover.

    Returns:
        Figure Plotly.
    """
    categories = ["Frags", "Assists", "Objectifs", "Survie"]

    if not participation_data:
        fig = go.Figure()
        fig.update_layout(
            title={"text": title, "x": 0.5, "xanchor": "center"},
            height=height,
        )
        return fig

    # Utiliser des seuils fixes pour la normalisation au lieu de normaliser par soi-même
    # Ces seuils sont basés sur les valeurs typiques dans Halo Infinite
    # Si on a plusieurs matchs, on peut utiliser le max historique, sinon on utilise les seuils fixes
    MAX_KILL_SCORE = 2000.0  # Score max théorique pour les kills
    MAX_ASSIST_SCORE = 500.0  # Score max théorique pour les assists
    MAX_OBJECTIVE_SCORE = 1000.0  # Score max théorique pour les objectifs
    MAX_PENALTY_SCORE = 500.0  # Score max théorique pour les pénalités (en valeur absolue)

    # Si on a plusieurs matchs, utiliser le max réel pour une meilleure comparaison
    # Sinon, utiliser les seuils fixes pour éviter que tout soit à 100%
    if len(participation_data) > 1:
        # Plusieurs matchs : utiliser le max réel pour comparaison relative
        max_kill = max(abs(p.get("kill_score") or 0) for p in participation_data) or MAX_KILL_SCORE
        max_assist = (
            max(abs(p.get("assist_score") or 0) for p in participation_data) or MAX_ASSIST_SCORE
        )
        max_obj = (
            max(abs(p.get("objective_score") or 0) for p in participation_data)
            or MAX_OBJECTIVE_SCORE
        )
        max_penalty = (
            max(abs(p.get("penalty_score") or 0) for p in participation_data) or MAX_PENALTY_SCORE
        )
    else:
        # Un seul match : utiliser les seuils fixes pour éviter que tout soit à 100%
        max_kill = MAX_KILL_SCORE
        max_assist = MAX_ASSIST_SCORE
        max_obj = MAX_OBJECTIVE_SCORE
        max_penalty = MAX_PENALTY_SCORE

    fig = go.Figure()

    for item in participation_data:
        name = item.get("name", "")
        color = item.get("color")

        # Valeurs brutes
        kill_raw = item.get("kill_score") or 0
        assist_raw = item.get("assist_score") or 0
        obj_raw = item.get("objective_score") or 0
        penalty_raw = item.get("penalty_score") or 0

        # Normaliser (0-1) avec capping à 1.0 pour éviter les dépassements
        kill_norm = min(kill_raw / max_kill if max_kill else 0, 1.0)
        assist_norm = min(assist_raw / max_assist if max_assist else 0, 1.0)
        obj_norm = min(obj_raw / max_obj if max_obj else 0, 1.0)
        # Survie : inverse des pénalités (moins de pénalités = mieux)
        # On utilise max(0, ...) pour éviter les valeurs négatives
        survival_norm = max(0.0, 1.0 - (abs(penalty_raw) / max_penalty) if max_penalty else 1.0)

        values = [kill_norm, assist_norm, obj_norm, survival_norm, kill_norm]
        theta = categories + [categories[0]]

        # Données pour hover
        customdata = [
            [f"{int(kill_raw):,} pts"],
            [f"{int(assist_raw):,} pts"],
            [f"{int(obj_raw):,} pts"],
            [f"{int(penalty_raw):,} pts" if penalty_raw else "Aucune"],
            [f"{int(kill_raw):,} pts"],
        ]

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=theta,
                name=name,
                fill="toself",
                line={"width": 2, "color": color} if color else {"width": 2},
                fillcolor=color,
                opacity=0.3,
                customdata=customdata,
                hovertemplate="%{theta}: %{customdata[0]}<extra>%{fullData.name}</extra>",
            )
        )

    fig.update_layout(
        polar={
            "radialaxis": {
                "visible": True,
                "range": [0, 1.1],
                "showticklabels": False,
            },
        },
        showlegend=len(participation_data) > 1,
        title={"text": title, "x": 0.5, "xanchor": "center"},
        height=height,
        margin={"l": 70, "r": 70, "t": 60 if title else 30, "b": 50},
    )

    return fig


# =============================================================================
# Radar de participation unifié (6 axes) - Réutilisable Dernier match / Coéquipiers
# =============================================================================


def create_participation_profile_radar(
    profiles: list[dict[str, Any]],
    *,
    title: str = "Profil de participation",
    height: int = 400,
) -> go.Figure:
    """Crée un radar à 6 axes : Objectifs, Combat, Support, Score, Impact, Survie.

    Conçu pour être réutilisable dans Dernier match et Mes coéquipiers.
    Les profils doivent être au format retourné par compute_participation_profile().

    Args:
        profiles: Liste de dicts avec format:
            [
                {
                    "name": "Moi" | "Coéquipier" | "Ce match",
                    "objectifs_raw": 300,
                    "combat_raw": 800,
                    "support_raw": 150,
                    "score_raw": 1200,
                    "impact_raw": 120.0,  # pts/min
                    "survie_raw": 0.8,     # 0-1
                    "objectifs_norm": 0.375,
                    "combat_norm": 0.53,
                    ...
                    "color": "#636EFA",
                },
                ...
            ]
        title: Titre du graphe.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly.
    """
    categories = ["Objectifs", "Combat", "Support", "Score", "Impact", "Survie"]

    if not profiles:
        fig = go.Figure()
        fig.update_layout(
            title={"text": title, "x": 0.5, "xanchor": "center"},
            height=height,
        )
        return fig

    fig = go.Figure()

    for item in profiles:
        name = item.get("name", "")
        color = item.get("color")

        # Valeurs normalisées (0-1) pour le tracé
        obj_n = item.get("objectifs_norm") or 0
        combat_n = item.get("combat_norm") or 0
        support_n = item.get("support_norm") or 0
        score_n = item.get("score_norm") or 0
        impact_n = item.get("impact_norm") or 0
        survie_n = item.get("survie_norm") or 0

        values = [obj_n, combat_n, support_n, score_n, impact_n, survie_n, obj_n]
        theta = categories + [categories[0]]

        # Valeurs brutes pour le hover
        obj_r = item.get("objectifs_raw") or 0
        combat_r = item.get("combat_raw") or 0
        support_r = item.get("support_raw") or 0
        score_r = item.get("score_raw") or 0
        impact_r = item.get("impact_raw") or 0
        survie_pct = (item.get("survie_raw") or 0) * 100

        customdata = [
            [f"{int(obj_r):,} pts"],
            [f"{int(combat_r):,} pts"],
            [f"{int(support_r):,} pts"],
            [f"{int(score_r):,} pts"],
            [f"{impact_r:.1f} pts/min"],
            [f"{survie_pct:.0f}% survie"],
            [f"{int(obj_r):,} pts"],
        ]

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=theta,
                name=name,
                fill="toself",
                line={"width": 2, "color": color} if color else {"width": 2},
                fillcolor=color,
                opacity=0.3,
                customdata=customdata,
                hovertemplate="%{theta}: %{customdata[0]}<extra>%{fullData.name}</extra>",
            )
        )

    fig.update_layout(
        polar={
            "radialaxis": {
                "visible": True,
                "range": [0, 1.1],
                "showticklabels": False,
                "gridcolor": "rgba(255,255,255,0.12)",
                "tickfont": {"color": THEME_COLORS.text_primary},
            },
            "angularaxis": {
                "gridcolor": "rgba(255,255,255,0.12)",
                "linecolor": THEME_COLORS.border,
                "tickfont": {"color": THEME_COLORS.text_primary},
            },
            "bgcolor": THEME_COLORS.bg_plot_rgba(1.0),
        },
        showlegend=len(profiles) > 1,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": -0.12,
            "x": 0.5,
            "xanchor": "center",
            "font": {"color": THEME_COLORS.text_primary},
        },
        title={
            "text": title,
            "x": 0.5,
            "xanchor": "center",
            "font": {"color": THEME_COLORS.text_primary},
        },
        height=height,
        margin={"l": 70, "r": 70, "t": 60 if title else 30, "b": 60},
    )

    return apply_halo_plot_style(fig, title=None, height=None)


def create_teammate_synergy_radar(
    me_data: dict[str, Any],
    teammate_data: dict[str, Any],
    *,
    title: str = "Complémentarité",
    height: int = 400,
) -> go.Figure:
    """Crée un radar comparant le profil de jeu entre moi et un coéquipier.

    Montre qui apporte quoi à l'équipe (complémentarité).

    Args:
        me_data: Dict avec format:
            {
                "name": "Moi",
                "kills_pct": 60,      # % de mes points en kills
                "assists_pct": 20,    # % en assists
                "objectives_pct": 15, # % en objectifs
                "kd_ratio": 1.5,      # K/D
                "accuracy": 45,       # Précision %
                "color": "#FF6B6B",
            }
        teammate_data: Même format pour le coéquipier.
        title: Titre du graphe.
        height: Hauteur du graphe.

    Returns:
        Figure Plotly.
    """
    categories = ["Frags %", "Assists %", "Objectifs %", "K/D", "Précision"]

    fig = go.Figure()

    for player in [me_data, teammate_data]:
        name = player.get("name", "")
        color = player.get("color")

        # Normaliser les valeurs
        kills_pct = (player.get("kills_pct") or 0) / 100
        assists_pct = (player.get("assists_pct") or 0) / 100
        obj_pct = (player.get("objectives_pct") or 0) / 100
        kd = min((player.get("kd_ratio") or 0) / 3, 1)  # Cap à 3.0 K/D
        acc = (player.get("accuracy") or 0) / 100

        values = [kills_pct, assists_pct, obj_pct, kd, acc, kills_pct]
        theta = categories + [categories[0]]

        # Valeurs originales
        orig_kills = player.get("kills_pct") or 0
        orig_assists = player.get("assists_pct") or 0
        orig_obj = player.get("objectives_pct") or 0
        orig_kd = player.get("kd_ratio") or 0
        orig_acc = player.get("accuracy") or 0

        customdata = [
            [f"{orig_kills:.1f}%"],
            [f"{orig_assists:.1f}%"],
            [f"{orig_obj:.1f}%"],
            [f"{orig_kd:.2f}"],
            [f"{orig_acc:.1f}%"],
            [f"{orig_kills:.1f}%"],
        ]

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=theta,
                name=name,
                fill="toself",
                line={"width": 2, "color": color} if color else {"width": 2},
                fillcolor=color,
                opacity=0.3,
                customdata=customdata,
                hovertemplate="%{theta}: %{customdata[0]}<extra>%{fullData.name}</extra>",
            )
        )

    fig.update_layout(
        polar={
            "radialaxis": {
                "visible": True,
                "range": [0, 1.1],
                "showticklabels": False,
            },
        },
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.15, "x": 0.5, "xanchor": "center"},
        title={"text": title, "x": 0.5, "xanchor": "center"},
        height=height,
        margin={"l": 70, "r": 70, "t": 60 if title else 30, "b": 70},
    )

    return fig


def create_session_trend_radar(
    sessions: list[dict[str, Any]],
    *,
    title: str = "Évolution du profil",
    height: int = 400,
) -> go.Figure:
    """Crée un radar montrant l'évolution du profil entre plusieurs sessions.

    Args:
        sessions: Liste de dicts avec format:
            [
                {
                    "name": "Session 1",
                    "kd_ratio": 1.2,
                    "win_rate": 55,      # %
                    "accuracy": 42,      # %
                    "obj_participation": 30,  # % du score en objectifs
                    "avg_score": 1500,   # Score moyen
                    "color": "#FF6B6B",
                },
                ...
            ]
        title: Titre du graphe.
        height: Hauteur du graphe.

    Returns:
        Figure Plotly.
    """
    categories = ["K/D", "Win Rate", "Précision", "Objectifs", "Score moy."]

    if not sessions:
        fig = go.Figure()
        fig.update_layout(
            title={"text": title, "x": 0.5, "xanchor": "center"},
            height=height,
        )
        return fig

    # Calculer les max pour normalisation
    max_kd = max((s.get("kd_ratio") or 0) for s in sessions) or 1
    max_score = max((s.get("avg_score") or 0) for s in sessions) or 1

    fig = go.Figure()

    for session in sessions:
        name = session.get("name", "")
        color = session.get("color")

        # Normaliser
        kd_norm = min((session.get("kd_ratio") or 0) / max(max_kd, 2), 1)
        wr_norm = (session.get("win_rate") or 0) / 100
        acc_norm = (session.get("accuracy") or 0) / 100
        obj_norm = (session.get("obj_participation") or 0) / 100
        score_norm = (session.get("avg_score") or 0) / max_score

        values = [kd_norm, wr_norm, acc_norm, obj_norm, score_norm, kd_norm]
        theta = categories + [categories[0]]

        # Valeurs originales
        orig_kd = session.get("kd_ratio") or 0
        orig_wr = session.get("win_rate") or 0
        orig_acc = session.get("accuracy") or 0
        orig_obj = session.get("obj_participation") or 0
        orig_score = session.get("avg_score") or 0

        customdata = [
            [f"{orig_kd:.2f}"],
            [f"{orig_wr:.1f}%"],
            [f"{orig_acc:.1f}%"],
            [f"{orig_obj:.1f}%"],
            [f"{int(orig_score):,}"],
            [f"{orig_kd:.2f}"],
        ]

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=theta,
                name=name,
                fill="toself",
                line={"width": 2, "color": color} if color else {"width": 2},
                fillcolor=color,
                opacity=0.3,
                customdata=customdata,
                hovertemplate="%{theta}: %{customdata[0]}<extra>%{fullData.name}</extra>",
            )
        )

    fig.update_layout(
        polar={
            "radialaxis": {
                "visible": True,
                "range": [0, 1.1],
                "showticklabels": False,
            },
        },
        showlegend=True,
        title={"text": title, "x": 0.5, "xanchor": "center"},
        height=height,
        margin={"l": 70, "r": 70, "t": 60 if title else 30, "b": 50},
    )

    return fig


__all__ = [
    "create_radar_chart",
    "create_stats_per_minute_radar",
    "create_performance_radar",
    # Sprint 8.2: Radars de participation
    "create_participation_radar",
    "create_teammate_synergy_radar",
    "create_session_trend_radar",
]
