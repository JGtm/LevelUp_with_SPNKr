"""Graphiques de performance cumulée avec Plotly.

Sprint 6: Visualisations des séries cumulatives (net score, K/D, tendances).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.config import HALO_COLORS, THEME_COLORS
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

PERFORMANCE_COLORS = {
    "positive": HALO_COLORS.green,  # Vert néon pour positif
    "negative": HALO_COLORS.red,  # Rouge pour négatif
    "neutral": HALO_COLORS.cyan,  # Cyan pour neutre
    "kills": "#00ff00",  # Vert
    "deaths": "#ff4444",  # Rouge
    "kd_line": "#ffaa00",  # Orange pour K/D
    "cumulative": "#00ccff",  # Cyan pour cumulatif
    "rolling": "#ff66ff",  # Magenta pour rolling
    "trend_up": "#00ff88",  # Vert clair pour amélioration
    "trend_down": "#ff6666",  # Rouge clair pour dégradation
    "baseline": "#888888",  # Gris pour ligne de base
}


# =============================================================================
# Graphiques de performance cumulée
# =============================================================================


def plot_cumulative_net_score(
    cumulative_df: pl.DataFrame,
    *,
    title: str = "Net Score Cumulé",
    height: int = 400,
    show_zero_line: bool = True,
) -> go.Figure:
    """Crée un graphique du net score cumulé au fil des matchs.

    Le graphique montre la progression du net score (kills - deaths) avec
    une coloration positive/négative.

    Args:
        cumulative_df: DataFrame avec colonnes start_time, net_score, cumulative_net_score.
        title: Titre du graphique.
        height: Hauteur en pixels.
        show_zero_line: Afficher la ligne de référence à zéro.

    Returns:
        Figure Plotly avec le graphique.

    Example:
        >>> df = compute_cumulative_net_score_series_polars(match_stats)
        >>> fig = plot_cumulative_net_score(df)
        >>> st.plotly_chart(fig)
    """
    fig = go.Figure()

    if not POLARS_AVAILABLE or cumulative_df.is_empty():
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

    # Convertir en dicts pour Plotly
    data = cumulative_df.to_dicts()

    # Extraire les données
    x_values = [d.get("start_time", "") for d in data]
    y_cumulative = [d.get("cumulative_net_score", 0) for d in data]
    y_match = [d.get("net_score", 0) for d in data]

    # Couleur selon positif/négatif
    line_color = (
        PERFORMANCE_COLORS["positive"] if y_cumulative[-1] >= 0 else PERFORMANCE_COLORS["negative"]
    )

    # Ligne du cumul
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_cumulative,
            mode="lines+markers",
            name="Net Score Cumulé",
            line={"color": line_color, "width": 3},
            marker={"size": 8, "color": line_color},
            hovertemplate="<b>%{x}</b><br>Cumulé: %{y:+d}<extra></extra>",
        )
    )

    # Barres pour net score par match
    bar_colors = [
        PERFORMANCE_COLORS["positive"] if v >= 0 else PERFORMANCE_COLORS["negative"]
        for v in y_match
    ]
    fig.add_trace(
        go.Bar(
            x=x_values,
            y=y_match,
            name="Net Score du Match",
            marker_color=bar_colors,
            opacity=0.5,
            hovertemplate="<b>%{x}</b><br>Match: %{y:+d}<extra></extra>",
        )
    )

    # Ligne de référence à zéro
    if show_zero_line:
        fig.add_hline(
            y=0,
            line_dash="dash",
            line_color=PERFORMANCE_COLORS["baseline"],
            annotation_text="Équilibre",
            annotation_position="right",
        )

    # Layout
    fig.update_layout(
        yaxis_title="Net Score (Kills - Deaths)",
        xaxis_title="Match",
        hovermode="x unified",
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    )

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_cumulative_kd(
    cumulative_df: pl.DataFrame,
    *,
    title: str = "K/D Cumulé",
    height: int = 400,
    show_target: float | None = 1.0,
) -> go.Figure:
    """Crée un graphique du K/D cumulé au fil des matchs.

    Args:
        cumulative_df: DataFrame avec colonnes start_time, kd, cumulative_kd.
        title: Titre du graphique.
        height: Hauteur en pixels.
        show_target: Afficher une ligne cible (ex: 1.0 pour K/D équilibré).

    Returns:
        Figure Plotly avec le graphique.
    """
    fig = go.Figure()

    if not POLARS_AVAILABLE or cumulative_df.is_empty():
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

    data = cumulative_df.to_dicts()

    x_values = [d.get("start_time", "") for d in data]
    y_cumulative = [d.get("cumulative_kd", 0) for d in data]
    y_match = [d.get("kd", 0) for d in data]

    # K/D cumulé
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_cumulative,
            mode="lines+markers",
            name="K/D Cumulé",
            line={"color": PERFORMANCE_COLORS["kd_line"], "width": 3},
            marker={"size": 8, "color": PERFORMANCE_COLORS["kd_line"]},
            hovertemplate="<b>%{x}</b><br>K/D Cumulé: %{y:.2f}<extra></extra>",
        )
    )

    # K/D par match (points)
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_match,
            mode="markers",
            name="K/D du Match",
            marker={
                "size": 10,
                "color": PERFORMANCE_COLORS["neutral"],
                "opacity": 0.6,
                "symbol": "circle-open",
            },
            hovertemplate="<b>%{x}</b><br>K/D Match: %{y:.2f}<extra></extra>",
        )
    )

    # Ligne cible
    if show_target is not None:
        fig.add_hline(
            y=show_target,
            line_dash="dash",
            line_color=PERFORMANCE_COLORS["baseline"],
            annotation_text=f"Cible: {show_target}",
            annotation_position="right",
        )

    # Layout
    fig.update_layout(
        yaxis_title="K/D Ratio",
        xaxis_title="Match",
        hovermode="x unified",
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    )

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_rolling_kd(
    rolling_df: pl.DataFrame,
    *,
    window_size: int = 5,
    title: str | None = None,
    height: int = 400,
) -> go.Figure:
    """Crée un graphique du K/D glissant.

    Args:
        rolling_df: DataFrame avec colonnes start_time, kd, rolling_kd.
        window_size: Taille de la fenêtre (pour le titre).
        title: Titre personnalisé (par défaut: "K/D Glissant (5 matchs)").
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec le graphique.
    """
    if title is None:
        title = f"K/D Glissant ({window_size} matchs)"

    fig = go.Figure()

    if not POLARS_AVAILABLE or rolling_df.is_empty():
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

    data = rolling_df.to_dicts()

    x_values = [d.get("start_time", "") for d in data]
    y_rolling = [d.get("rolling_kd", 0) for d in data]
    y_match = [d.get("kd", 0) for d in data]

    # K/D par match (en fond)
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_match,
            mode="lines",
            name="K/D du Match",
            line={"color": PERFORMANCE_COLORS["neutral"], "width": 1},
            opacity=0.4,
            hovertemplate="<b>%{x}</b><br>K/D Match: %{y:.2f}<extra></extra>",
        )
    )

    # K/D glissant
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_rolling,
            mode="lines+markers",
            name=f"K/D Glissant ({window_size})",
            line={"color": PERFORMANCE_COLORS["rolling"], "width": 3},
            marker={"size": 6, "color": PERFORMANCE_COLORS["rolling"]},
            hovertemplate="<b>%{x}</b><br>K/D Glissant: %{y:.2f}<extra></extra>",
        )
    )

    # Ligne de référence à 1.0
    fig.add_hline(
        y=1.0,
        line_dash="dash",
        line_color=PERFORMANCE_COLORS["baseline"],
        annotation_text="K/D = 1.0",
        annotation_position="right",
    )

    fig.update_layout(
        yaxis_title="K/D Ratio",
        xaxis_title="Match",
        hovermode="x unified",
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    )

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_session_trend(
    match_stats_df: pl.DataFrame,
    *,
    title: str = "Tendance de la Session",
    height: int = 350,
) -> go.Figure:
    """Crée un graphique montrant la tendance de la session.

    Compare la première et la seconde moitié avec une indication visuelle
    de l'amélioration ou de la dégradation.

    Args:
        match_stats_df: DataFrame des matchs triés par start_time.
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec indicateurs de tendance.
    """
    fig = go.Figure()

    if not POLARS_AVAILABLE or match_stats_df.is_empty() or len(match_stats_df) < 4:
        fig.add_annotation(
            text="Pas assez de matchs pour analyser la tendance (min: 4)",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 14, "color": THEME_COLORS.text_primary},
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    # Import local pour éviter les imports circulaires
    from src.analysis.cumulative import compute_session_trend_polars

    trend_data = compute_session_trend_polars(match_stats_df)

    # Créer un graphique à indicateurs
    first_kd = trend_data.get("first_half_kd", 0) or 0
    second_kd = trend_data.get("second_half_kd", 0) or 0
    change_pct = trend_data.get("kd_change_pct", 0) or 0
    trend = trend_data.get("trend", "stable")

    # Couleurs selon la tendance
    if trend == "improving":
        delta_color = PERFORMANCE_COLORS["trend_up"]
        trend_symbol = "▲"
        trend_text = "En progression"
    elif trend == "declining":
        delta_color = PERFORMANCE_COLORS["trend_down"]
        trend_symbol = "▼"
        trend_text = "En déclin"
    else:
        delta_color = PERFORMANCE_COLORS["baseline"]
        trend_symbol = "◆"
        trend_text = "Stable"

    # Créer les indicateurs côte à côte
    fig = make_subplots(
        rows=1,
        cols=3,
        specs=[[{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}]],
        subplot_titles=["Début de session", "Fin de session", "Tendance"],
    )

    # Indicateur première moitié
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=first_kd,
            number={
                "font": {"size": 40, "color": PERFORMANCE_COLORS["neutral"]},
                "suffix": "",
                "valueformat": ".2f",
            },
            title={"text": "K/D", "font": {"size": 14}},
        ),
        row=1,
        col=1,
    )

    # Indicateur seconde moitié
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=second_kd,
            number={
                "font": {"size": 40, "color": PERFORMANCE_COLORS["kd_line"]},
                "suffix": "",
                "valueformat": ".2f",
            },
            title={"text": "K/D", "font": {"size": 14}},
        ),
        row=1,
        col=2,
    )

    # Indicateur de tendance avec delta
    fig.add_trace(
        go.Indicator(
            mode="number+delta",
            value=change_pct,
            number={
                "font": {"size": 32, "color": delta_color},
                "suffix": "%",
                "valueformat": "+.1f",
            },
            delta={
                "reference": 0,
                "relative": False,
                "valueformat": ".1f",
                "increasing": {"color": PERFORMANCE_COLORS["trend_up"]},
                "decreasing": {"color": PERFORMANCE_COLORS["trend_down"]},
            },
            title={"text": f"{trend_symbol} {trend_text}", "font": {"size": 14}},
        ),
        row=1,
        col=3,
    )

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_cumulative_comparison(
    session_a_df: pl.DataFrame,
    session_b_df: pl.DataFrame,
    *,
    label_a: str = "Session A",
    label_b: str = "Session B",
    title: str = "Comparaison des Sessions",
    height: int = 400,
) -> go.Figure:
    """Compare deux sessions avec leurs courbes de net score cumulé.

    Args:
        session_a_df: DataFrame de la première session.
        session_b_df: DataFrame de la seconde session.
        label_a: Label pour la session A.
        label_b: Label pour la session B.
        title: Titre du graphique.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec les deux courbes superposées.
    """
    fig = go.Figure()

    if not POLARS_AVAILABLE:
        fig.add_annotation(
            text="Polars non disponible",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return apply_halo_plot_style(fig, title=title, height=height)

    # Import local
    from src.analysis.cumulative import compute_cumulative_net_score_series_polars

    # Calculer les séries cumulées
    def add_session_trace(df: pl.DataFrame, label: str, color: str) -> None:
        if df.is_empty():
            return

        cumul = compute_cumulative_net_score_series_polars(df)
        if cumul.is_empty():
            return

        data = cumul.to_dicts()
        # Normaliser l'index des matchs (0, 1, 2, ...)
        x_values = list(range(len(data)))
        y_values = [d.get("cumulative_net_score", 0) for d in data]

        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines+markers",
                name=label,
                line={"color": color, "width": 2},
                marker={"size": 6, "color": color},
                hovertemplate=f"<b>{label}</b><br>Match #%{{x}}<br>Cumulé: %{{y:+d}}<extra></extra>",
            )
        )

    add_session_trace(session_a_df, label_a, PERFORMANCE_COLORS["neutral"])
    add_session_trace(session_b_df, label_b, PERFORMANCE_COLORS["kd_line"])

    # Ligne de référence
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color=PERFORMANCE_COLORS["baseline"],
        annotation_text="Équilibre",
        annotation_position="right",
    )

    fig.update_layout(
        xaxis_title="Match #",
        yaxis_title="Net Score Cumulé",
        hovermode="x unified",
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "center", "x": 0.5},
    )

    return apply_halo_plot_style(fig, title=title, height=height)


# =============================================================================
# Indicateurs de performance
# =============================================================================


def create_cumulative_metrics_indicator(
    metrics: Any,  # CumulativeMetricsResult
    *,
    show_trend: bool = True,
    height: int = 150,
) -> go.Figure:
    """Crée un indicateur compact des métriques cumulées.

    Args:
        metrics: CumulativeMetricsResult avec les métriques.
        show_trend: Afficher la tendance si disponible.
        height: Hauteur en pixels.

    Returns:
        Figure Plotly avec les indicateurs.
    """
    fig = make_subplots(
        rows=1,
        cols=4,
        specs=[[{"type": "indicator"}] * 4],
        subplot_titles=["Kills", "Deaths", "Net Score", "K/D"],
    )

    # Kills
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=metrics.total_kills if hasattr(metrics, "total_kills") else 0,
            number={
                "font": {"size": 28, "color": PERFORMANCE_COLORS["kills"]},
            },
        ),
        row=1,
        col=1,
    )

    # Deaths
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=metrics.total_deaths if hasattr(metrics, "total_deaths") else 0,
            number={
                "font": {"size": 28, "color": PERFORMANCE_COLORS["deaths"]},
            },
        ),
        row=1,
        col=2,
    )

    # Net Score
    net_score = metrics.cumulative_net_score if hasattr(metrics, "cumulative_net_score") else 0
    net_color = PERFORMANCE_COLORS["positive"] if net_score >= 0 else PERFORMANCE_COLORS["negative"]
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=net_score,
            number={
                "font": {"size": 28, "color": net_color},
                "valueformat": "+d",
            },
        ),
        row=1,
        col=3,
    )

    # K/D
    kd = metrics.cumulative_kd if hasattr(metrics, "cumulative_kd") else 0
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=kd,
            number={
                "font": {"size": 28, "color": PERFORMANCE_COLORS["kd_line"]},
                "valueformat": ".2f",
            },
        ),
        row=1,
        col=4,
    )

    return apply_halo_plot_style(fig, height=height)


# =============================================================================
# Fonctions utilitaires
# =============================================================================


def get_performance_colors() -> dict[str, str]:
    """Retourne le dictionnaire des couleurs de performance.

    Returns:
        Dict avec les couleurs configurées.
    """
    return PERFORMANCE_COLORS.copy()
