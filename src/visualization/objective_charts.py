"""Graphiques d'analyse des objectifs avec Plotly.

Sprint 7: Visualisations pour la participation aux objectifs et la contribution des joueurs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import plotly.graph_objects as go

from src.config import THEME_COLORS
from src.visualization.theme import apply_halo_plot_style

# Import conditionnel de Polars
try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None  # type: ignore

if TYPE_CHECKING:
    import polars as pl


# =============================================================================
# Configuration des couleurs
# =============================================================================

OBJECTIVE_COLORS = {
    "objective": "#00ffcc",  # Cyan pour objectifs
    "kill": "#ff4444",  # Rouge pour kills
    "assist": "#ffaa00",  # Orange pour assists
    "mode": "#aa66ff",  # Violet pour mode
    "other": "#888888",  # Gris pour autres
    "highlight": "#00ff00",  # Vert néon pour highlights
    "bar_1": "#00aaff",  # Bleu
    "bar_2": "#ff6666",  # Rouge clair
    "bar_3": "#66ff66",  # Vert clair
}


# =============================================================================
# Graphique: Score objectifs vs Kills
# =============================================================================


def plot_objective_vs_kills_scatter(
    awards_df: pl.DataFrame,
    match_stats_df: pl.DataFrame,
    *,
    title: str = "Score Objectifs vs Kills",
    height: int = 450,
) -> go.Figure:
    """Crée un scatter plot comparant score objectifs et kills par match.

    Permet d'identifier les matchs où le joueur a contribué plus aux objectifs
    qu'aux kills (joueur support) ou l'inverse.

    Args:
        awards_df: DataFrame des personal_score_awards.
        match_stats_df: DataFrame des match_stats avec kills.
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec le scatter plot.
    """
    fig = go.Figure()

    if not POLARS_AVAILABLE or awards_df.is_empty() or match_stats_df.is_empty():
        fig.add_annotation(
            text="Aucune donnée disponible",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": THEME_COLORS.text_primary},
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    # Calculer score objectifs par match
    objective_categories = ["objective", "mode"]
    obj_by_match = (
        awards_df.filter(pl.col("score_category").is_in(objective_categories))
        .group_by("match_id")
        .agg(pl.col("points").sum().alias("objective_score"))
    )

    # Joindre avec match_stats pour avoir les kills
    combined = (
        match_stats_df.select(["match_id", "kills", "map_name", "start_time"])
        .join(obj_by_match, on="match_id", how="left")
        .with_columns([pl.col("objective_score").fill_null(0)])
    )

    if combined.is_empty():
        fig.add_annotation(
            text="Aucune donnée à afficher",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    data = combined.to_dicts()

    # Scatter plot
    fig.add_trace(
        go.Scatter(
            x=[d.get("kills", 0) for d in data],
            y=[d.get("objective_score", 0) for d in data],
            mode="markers",
            marker={
                "size": 12,
                "color": OBJECTIVE_COLORS["objective"],
                "opacity": 0.7,
                "line": {"width": 1, "color": "white"},
            },
            text=[d.get("map_name", "?") for d in data],
            customdata=[[d.get("start_time", ""), d.get("match_id", "")] for d in data],
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Kills: %{x}<br>"
                "Score Objectifs: %{y}<br>"
                "<extra>%{customdata[0]}</extra>"
            ),
            name="Matchs",
        )
    )

    # Ligne de tendance (régression linéaire simple)
    if len(data) > 2:
        kills_list = [d.get("kills", 0) for d in data]
        obj_list = [d.get("objective_score", 0) for d in data]

        # Calcul simple de la régression
        n = len(kills_list)
        sum_x = sum(kills_list)
        sum_y = sum(obj_list)
        sum_xy = sum(k * o for k, o in zip(kills_list, obj_list, strict=False))
        sum_x2 = sum(k**2 for k in kills_list)

        denom = n * sum_x2 - sum_x**2
        if denom != 0:
            slope = (n * sum_xy - sum_x * sum_y) / denom
            intercept = (sum_y - slope * sum_x) / n

            x_range = [min(kills_list), max(kills_list)]
            y_trend = [slope * x + intercept for x in x_range]

            fig.add_trace(
                go.Scatter(
                    x=x_range,
                    y=y_trend,
                    mode="lines",
                    line={"color": OBJECTIVE_COLORS["highlight"], "dash": "dash"},
                    name="Tendance",
                    showlegend=True,
                )
            )

    fig.update_layout(
        xaxis_title="Kills",
        yaxis_title="Score Objectifs",
        hovermode="closest",
    )

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_objective_breakdown_bars(
    awards_df: pl.DataFrame,
    *,
    xuid: str | None = None,
    title: str = "Répartition du Score par Catégorie",
    height: int = 400,
) -> go.Figure:
    """Crée un graphique en barres de la répartition du score par catégorie.

    Args:
        awards_df: DataFrame des personal_score_awards.
        xuid: XUID du joueur à filtrer (optionnel).
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec les barres.
    """
    fig = go.Figure()

    if not POLARS_AVAILABLE or awards_df.is_empty():
        fig.add_annotation(
            text="Aucune donnée disponible",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": THEME_COLORS.text_primary},
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    df = awards_df
    if xuid is not None and "xuid" in df.columns:
        df = df.filter(pl.col("xuid") == xuid)

    # Agréger par catégorie
    by_category = (
        df.group_by("score_category")
        .agg(
            [
                pl.col("points").sum().alias("total_points"),
                pl.count().alias("count"),
            ]
        )
        .sort("total_points", descending=True)
    )

    if by_category.is_empty():
        fig.add_annotation(
            text="Aucune donnée à afficher",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    data = by_category.to_dicts()

    # Mapping des couleurs par catégorie
    category_colors = {
        "objective": OBJECTIVE_COLORS["objective"],
        "mode": OBJECTIVE_COLORS["mode"],
        "kill": OBJECTIVE_COLORS["kill"],
        "assist": OBJECTIVE_COLORS["assist"],
    }

    categories = [d["score_category"] for d in data]
    points = [d["total_points"] for d in data]
    counts = [d["count"] for d in data]
    colors = [category_colors.get(c, OBJECTIVE_COLORS["other"]) for c in categories]

    fig.add_trace(
        go.Bar(
            x=categories,
            y=points,
            marker_color=colors,
            text=[f"{p:,.0f}" for p in points],
            textposition="outside",
            customdata=counts,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Points: %{y:,.0f}<br>"
                "Occurrences: %{customdata}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        xaxis_title="Catégorie",
        yaxis_title="Points Totaux",
        showlegend=False,
    )

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_top_players_objective_bars(
    rankings: list[Any],  # list[PlayerObjectiveRanking]
    *,
    top_n: int = 10,
    title: str = "Top Joueurs par Contribution aux Objectifs",
    height: int = 450,
) -> go.Figure:
    """Crée un graphique des top joueurs par contribution aux objectifs.

    Args:
        rankings: Liste de PlayerObjectiveRanking.
        top_n: Nombre de joueurs à afficher.
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec les barres horizontales.
    """
    fig = go.Figure()

    if not rankings:
        fig.add_annotation(
            text="Aucun joueur à afficher",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": THEME_COLORS.text_primary},
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    # Limiter au top N
    top_rankings = rankings[:top_n]

    # Extraire les données
    gamertags = [
        getattr(r, "gamertag", r.get("gamertag", "?"))
        if hasattr(r, "gamertag") or isinstance(r, dict)
        else str(r)
        for r in top_rankings
    ]
    scores = [
        getattr(r, "total_objective_score", r.get("total_objective_score", 0))
        if hasattr(r, "total_objective_score") or isinstance(r, dict)
        else 0
        for r in top_rankings
    ]
    matches = [
        getattr(r, "matches_count", r.get("matches_count", 0))
        if hasattr(r, "matches_count") or isinstance(r, dict)
        else 0
        for r in top_rankings
    ]

    # Inverser pour avoir le meilleur en haut
    gamertags = gamertags[::-1]
    scores = scores[::-1]
    matches = matches[::-1]

    fig.add_trace(
        go.Bar(
            y=gamertags,
            x=scores,
            orientation="h",
            marker_color=OBJECTIVE_COLORS["objective"],
            text=[f"{s:,.0f}" for s in scores],
            textposition="outside",
            customdata=matches,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Score Total: %{x:,.0f}<br>"
                "Matchs: %{customdata}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        xaxis_title="Score Objectifs Total",
        yaxis_title="",
        showlegend=False,
    )

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_objective_ratio_gauge(
    ratio: float,
    *,
    title: str = "Ratio Objectifs/Total",
    height: int = 250,
) -> go.Figure:
    """Crée un indicateur gauge pour le ratio objectifs/total.

    Args:
        ratio: Ratio entre 0 et 1 (objectifs / total).
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec l'indicateur.
    """
    # Convertir en pourcentage
    percentage = ratio * 100

    fig = go.Figure()

    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=percentage,
            number={"suffix": "%", "font": {"size": 32}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": OBJECTIVE_COLORS["objective"]},
                "bgcolor": "rgba(0,0,0,0.3)",
                "borderwidth": 2,
                "bordercolor": "gray",
                "steps": [
                    {"range": [0, 33], "color": "rgba(255,68,68,0.3)"},  # Faible
                    {"range": [33, 66], "color": "rgba(255,170,0,0.3)"},  # Moyen
                    {"range": [66, 100], "color": "rgba(0,255,136,0.3)"},  # Élevé
                ],
                "threshold": {
                    "line": {"color": OBJECTIVE_COLORS["highlight"], "width": 4},
                    "thickness": 0.75,
                    "value": percentage,
                },
            },
            title={"text": title, "font": {"size": 16}},
        )
    )

    return apply_halo_plot_style(fig, height=height)


def plot_assist_breakdown_pie(
    assist_breakdown: Any,  # AssistBreakdownResult
    *,
    title: str = "Répartition des Assistances",
    height: int = 350,
) -> go.Figure:
    """Crée un camembert de la répartition des assistances.

    Args:
        assist_breakdown: AssistBreakdownResult avec les compteurs.
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec le camembert.
    """
    fig = go.Figure()

    # Extraire les données selon le type
    if hasattr(assist_breakdown, "kill_assists"):
        kill_assists = assist_breakdown.kill_assists
        mark_assists = assist_breakdown.mark_assists
        emp_assists = assist_breakdown.emp_assists
        other_assists = getattr(assist_breakdown, "other_assists", 0)
    elif isinstance(assist_breakdown, dict):
        kill_assists = assist_breakdown.get("kill_assists", 0)
        mark_assists = assist_breakdown.get("mark_assists", 0)
        emp_assists = assist_breakdown.get("emp_assists", 0)
        other_assists = assist_breakdown.get("other_assists", 0)
    else:
        fig.add_annotation(
            text="Format de données non reconnu",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    labels = ["Kill Assists", "Mark Assists", "EMP Assists", "Autres"]
    values = [kill_assists, mark_assists, emp_assists, other_assists]
    colors = [
        OBJECTIVE_COLORS["kill"],
        OBJECTIVE_COLORS["highlight"],
        OBJECTIVE_COLORS["mode"],
        OBJECTIVE_COLORS["other"],
    ]

    # Filtrer les valeurs nulles
    filtered = [(lbl, v, c) for lbl, v, c in zip(labels, values, colors, strict=False) if v > 0]
    if not filtered:
        fig.add_annotation(
            text="Aucune assistance enregistrée",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    labels, values, colors = zip(*filtered, strict=False)

    fig.add_trace(
        go.Pie(
            labels=list(labels),
            values=list(values),
            marker_colors=list(colors),
            textinfo="label+percent",
            textposition="outside",
            hole=0.4,
            hovertemplate="<b>%{label}</b><br>%{value} (%{percent})<extra></extra>",
        )
    )

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_objective_trend_over_time(
    summary_df: pl.DataFrame,
    *,
    title: str = "Évolution du Score Objectifs",
    height: int = 400,
) -> go.Figure:
    """Crée un graphique de l'évolution du score objectifs dans le temps.

    Args:
        summary_df: DataFrame avec colonnes match_id, start_time, objective_score, etc.
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec la timeseries.
    """
    fig = go.Figure()

    if not POLARS_AVAILABLE or summary_df.is_empty():
        fig.add_annotation(
            text="Aucune donnée disponible",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": THEME_COLORS.text_primary},
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    # Trier par date
    df = summary_df.sort("start_time") if "start_time" in summary_df.columns else summary_df
    data = df.to_dicts()

    x_values = [d.get("start_time", d.get("match_id", str(i))) for i, d in enumerate(data)]

    # Score objectifs
    obj_scores = [d.get("objective_score", 0) for d in data]
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=obj_scores,
            mode="lines+markers",
            name="Score Objectifs",
            line={"color": OBJECTIVE_COLORS["objective"], "width": 2},
            marker={"size": 6},
            hovertemplate="<b>%{x}</b><br>Objectifs: %{y}<extra></extra>",
        )
    )

    # Score total si disponible
    if "total_score" in summary_df.columns:
        total_scores = [d.get("total_score", 0) for d in data]
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=total_scores,
                mode="lines",
                name="Score Total",
                line={"color": OBJECTIVE_COLORS["other"], "width": 1, "dash": "dot"},
                hovertemplate="<b>%{x}</b><br>Total: %{y}<extra></extra>",
            )
        )

    fig.update_layout(
        xaxis_title="Match",
        yaxis_title="Score",
        hovermode="x unified",
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    )

    return apply_halo_plot_style(fig, title=title, height=height)


# =============================================================================
# Fonctions utilitaires
# =============================================================================


def get_objective_chart_colors() -> dict[str, str]:
    """Retourne le dictionnaire des couleurs pour les graphiques d'objectifs.

    Returns:
        Dict avec les couleurs configurées.
    """
    return OBJECTIVE_COLORS.copy()
