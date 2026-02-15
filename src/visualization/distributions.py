"""Graphiques de distributions et répartitions.

Les fonctions liées aux outcome (outcomes_over_time, stacked_outcomes,
heatmap, matches_at_top) ont été extraites dans distributions_outcomes.py
(Sprint 16).  Elles sont ré-exportées ici pour compatibilité.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import plotly.graph_objects as go
import polars as pl

from src.config import HALO_COLORS, OUTCOME_CODES, PLOT_CONFIG
from src.visualization._compat import (
    DataFrameLike,
    ensure_polars,
    ensure_polars_series,
)
from src.visualization.theme import (
    apply_halo_plot_style,
    get_legend_horizontal_bottom,  # noqa: F401 – re-export implicite
)

if TYPE_CHECKING:
    import pandas as pd


def plot_kda_distribution(df: DataFrameLike) -> go.Figure:
    """Graphique de distribution du KDA (FDA) avec KDE.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonne kda.

    Returns:
        Figure Plotly avec densité KDE et rug plot.
    """
    df = ensure_polars(df)

    colors = HALO_COLORS.as_dict()
    d = df.drop_nulls(subset=["kda"])
    x = d.get_column("kda").cast(pl.Float64, strict=False).drop_nulls().to_numpy()

    if x.size == 0:
        fig = go.Figure()
        fig.update_layout(
            height=PLOT_CONFIG.default_height, margin={"l": 40, "r": 20, "t": 30, "b": 40}
        )
        fig.update_xaxes(title_text="FDA")
        fig.update_yaxes(title_text="Densité")
        return apply_halo_plot_style(fig, height=PLOT_CONFIG.default_height)

    # KDE gaussien (règle de Silverman)
    n = int(x.size)
    std = float(np.std(x, ddof=1)) if n > 1 else 0.0
    q25, q75 = np.percentile(x, [25, 75]).tolist() if n > 1 else [0.0, 0.0]
    iqr = float(q75 - q25)
    sigma = min(std, iqr / 1.34) if (std > 0 and iqr > 0) else max(std, iqr / 1.34)
    bw = (1.06 * sigma * (n ** (-1.0 / 5.0))) if sigma and sigma > 0 else 0.3
    bw = float(max(bw, 0.05))

    xmin = float(np.min(x))
    xmax = float(np.max(x))
    span = max(0.25, xmax - xmin)
    pad = 0.15 * span
    grid = np.linspace(xmin - pad, xmax + pad, 256)
    z = (grid[:, None] - x[None, :]) / bw
    dens = np.exp(-0.5 * (z**2)).sum(axis=1) / (n * bw * np.sqrt(2.0 * np.pi))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=grid,
            y=dens,
            mode="lines",
            name="Densité (KDE)",
            line={"width": PLOT_CONFIG.line_width, "color": colors["cyan"]},
            fill="tozeroy",
            fillcolor="rgba(53,208,255,0.18)",
            hovertemplate="FDA=%{x:.2f}<br>densité=%{y:.3f}<extra></extra>",
        )
    )

    # Rug plot
    fig.add_trace(
        go.Scatter(
            x=x,
            y=np.zeros_like(x),
            mode="markers",
            name="Matchs",
            marker={"symbol": "line-ns-open", "size": 10, "color": "rgba(255,255,255,0.45)"},
            hovertemplate="FDA=%{x:.2f}<extra></extra>",
        )
    )

    fig.add_vline(x=0, line_width=1, line_dash="dot", line_color="rgba(255,255,255,0.35)")

    # Ligne médiane
    if len(x) > 0:
        median_val = float(np.median(x))
        fig.add_vline(
            x=median_val,
            line_dash="dash",
            line_color="#ffaa00",
            annotation_text=f"Médiane: {median_val:.2f}",
            annotation_position="top right",
            annotation_font_color="#ffaa00",
        )

    fig.update_layout(
        height=PLOT_CONFIG.default_height, margin={"l": 40, "r": 20, "t": 30, "b": 40}
    )
    fig.update_xaxes(title_text="FDA", zeroline=True)
    fig.update_yaxes(title_text="Densité", rangemode="tozero")

    return apply_halo_plot_style(fig, height=PLOT_CONFIG.default_height)


def plot_top_weapons(
    weapons_data: list[dict],
    *,
    title: str | None = None,
    top_n: int = 10,
) -> go.Figure:
    """Graphique des armes les plus utilisées.

    Args:
        weapons_data: Liste de dicts avec weapon_name, total_kills, headshot_rate, accuracy.
        title: Titre optionnel.
        top_n: Nombre d'armes à afficher.

    Returns:
        Figure Plotly avec barres horizontales.
    """
    colors = HALO_COLORS.as_dict()

    if not weapons_data:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    # Limiter et trier
    data = sorted(weapons_data, key=lambda x: x.get("total_kills", 0), reverse=True)[:top_n]

    names = [w.get("weapon_name", "?") for w in data][::-1]
    kills = [w.get("total_kills", 0) for w in data][::-1]
    hs_rates = [w.get("headshot_rate", 0) for w in data][::-1]
    accuracies = [w.get("accuracy", 0) for w in data][::-1]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=kills,
            y=names,
            orientation="h",
            name="Kills",
            marker_color=colors["cyan"],
            opacity=0.85,
            text=[f"{k} kills" for k in kills],
            textposition="outside",
            customdata=list(zip(hs_rates, accuracies, strict=False)),
            hovertemplate=(
                "%{y}<br>"
                "Kills: %{x}<br>"
                "Headshot: %{customdata[0]:.1f}%<br>"
                "Précision: %{customdata[1]:.1f}%<extra></extra>"
            ),
        )
    )

    height = max(PLOT_CONFIG.default_height, 30 * len(names) + 80)

    fig.update_layout(
        height=height,
        margin={"l": 120, "r": 60, "t": 60 if title else 30, "b": 40},
    )
    fig.update_xaxes(title_text="Kills")
    fig.update_yaxes(title_text="")

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_histogram(
    values: pd.Series | pl.Series | np.ndarray,
    *,
    title: str | None = None,
    x_label: str = "Valeur",
    y_label: str = "Fréquence",
    bins: int | str = "auto",
    color: str | None = None,
    show_kde: bool = False,
) -> go.Figure:
    """Histogramme générique avec option KDE.

    Args:
        values: Série (Pandas ou Polars) ou array de valeurs numériques.
        title: Titre optionnel.
        x_label: Label de l'axe X.
        y_label: Label de l'axe Y.
        bins: Nombre de bins ou "auto".
        color: Couleur des barres (défaut: cyan).
        show_kde: Afficher la courbe KDE superposée.

    Returns:
        Figure Plotly avec histogramme.
    """
    colors = HALO_COLORS.as_dict()
    bar_color = color or colors["cyan"]

    if isinstance(values, np.ndarray):
        x = values[~np.isnan(values)].astype(float)
    else:
        s = ensure_polars_series(values)
        x = s.cast(pl.Float64, strict=False).drop_nulls().to_numpy()

    if x.size == 0:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    # Calculer les bins
    n_bins = min(50, max(10, int(np.sqrt(x.size)))) if bins == "auto" else int(bins)

    fig = go.Figure()

    fig.add_trace(
        go.Histogram(
            x=x,
            nbinsx=n_bins,
            name=x_label,
            marker_color=bar_color,
            opacity=0.75,
            hovertemplate=f"{x_label}: %{{x}}<br>{y_label}: %{{y}}<extra></extra>",
        )
    )

    if show_kde and x.size > 10:
        # KDE simple
        n = int(x.size)
        std = float(np.std(x, ddof=1)) if n > 1 else 0.0
        if std > 0:
            bw = 1.06 * std * (n ** (-1.0 / 5.0))
            bw = max(bw, 0.01)

            xmin, xmax = float(np.min(x)), float(np.max(x))
            pad = 0.1 * (xmax - xmin)
            grid = np.linspace(xmin - pad, xmax + pad, 128)
            z = (grid[:, None] - x[None, :]) / bw
            dens = np.exp(-0.5 * (z**2)).sum(axis=1) / (n * bw * np.sqrt(2 * np.pi))

            # Normaliser pour matcher l'histogramme
            hist_counts, hist_edges = np.histogram(x, bins=n_bins)
            bin_width = hist_edges[1] - hist_edges[0]
            dens_scaled = dens * n * bin_width

            fig.add_trace(
                go.Scatter(
                    x=grid,
                    y=dens_scaled,
                    mode="lines",
                    name="Densité",
                    line={"color": colors["amber"], "width": 2},
                    hoverinfo="skip",
                )
            )

    # Ligne médiane
    if len(x) > 0:
        median_val = float(np.median(x))
        fig.add_vline(
            x=median_val,
            line_dash="dash",
            line_color="#ffaa00",
            annotation_text=f"Médiane: {median_val:.1f}",
            annotation_position="top right",
            annotation_font_color="#ffaa00",
        )

    fig.update_layout(
        height=PLOT_CONFIG.default_height,
        margin={"l": 40, "r": 20, "t": 60 if title else 30, "b": 40},
        bargap=0.05,
    )
    fig.update_xaxes(title_text=x_label)
    fig.update_yaxes(title_text=y_label)

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


def plot_medals_distribution(
    medals_data: list[tuple[int, int]],
    medal_names: dict[int, str],
    *,
    title: str | None = None,
    top_n: int = 20,
) -> go.Figure:
    """Graphique de distribution des médailles (barres horizontales).

    Args:
        medals_data: Liste de tuples (medal_name_id, count).
        medal_names: Dictionnaire {medal_name_id: nom_traduit}.
        title: Titre optionnel.
        top_n: Nombre de médailles à afficher.

    Returns:
        Figure Plotly avec barres horizontales.
    """
    if not medals_data:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    # Trier et limiter
    sorted_medals = sorted(medals_data, key=lambda x: x[1], reverse=True)[:top_n]

    names = [medal_names.get(m[0], f"Médaille #{m[0]}") for m in sorted_medals]
    counts = [m[1] for m in sorted_medals]

    # Inverser pour afficher du plus grand au plus petit (haut -> bas)
    names = names[::-1]
    counts = counts[::-1]

    # Dégradé de couleurs basé sur le rang
    n = len(counts)
    gradient_colors = [f"rgba(53, 208, 255, {0.4 + 0.5 * (i / max(1, n - 1))})" for i in range(n)]

    fig = go.Figure(
        data=go.Bar(
            x=counts,
            y=names,
            orientation="h",
            marker_color=gradient_colors,
            text=counts,
            textposition="outside",
            hovertemplate="%{y}<br>Nombre: %{x}<extra></extra>",
        )
    )

    height = max(PLOT_CONFIG.default_height, 25 * len(names) + 80)

    fig.update_layout(
        height=height,
        margin={"l": 40, "r": 60, "t": 60 if title else 30, "b": 40},
    )
    fig.update_xaxes(title_text="Nombre")
    fig.update_yaxes(title_text="")

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_correlation_scatter(
    df: DataFrameLike,
    x_col: str,
    y_col: str,
    *,
    color_col: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    show_trendline: bool = True,
) -> go.Figure:
    """Scatter plot pour visualiser les corrélations.

    Args:
        df: DataFrame (Pandas ou Polars) avec les données.
        x_col: Colonne pour l'axe X.
        y_col: Colonne pour l'axe Y.
        color_col: Colonne pour colorer les points (optionnel).
        title: Titre optionnel.
        x_label: Label axe X (défaut: nom colonne).
        y_label: Label axe Y (défaut: nom colonne).
        show_trendline: Afficher la ligne de tendance.

    Returns:
        Figure Plotly avec scatter plot.
    """
    df = ensure_polars(df)

    colors = HALO_COLORS.as_dict()
    d = df.drop_nulls(subset=[x_col, y_col])

    if d.is_empty():
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    x_series = d.get_column(x_col).cast(pl.Float64, strict=False)
    y_series = d.get_column(y_col).cast(pl.Float64, strict=False)

    # Couleur des points
    if color_col and color_col in d.columns:
        color_values = d.get_column(color_col).to_list()

        # Si c'est outcome, mapper vers des couleurs
        if color_col == "outcome":
            color_map = {
                OUTCOME_CODES.WIN: colors["green"],
                OUTCOME_CODES.LOSS: colors["red"],
                OUTCOME_CODES.TIE: colors["amber"],
                OUTCOME_CODES.NO_FINISH: colors["violet"],
            }
            marker_colors = [color_map.get(v, colors["slate"]) for v in color_values]
        else:
            marker_colors = colors["cyan"]
    else:
        marker_colors = colors["cyan"]

    x_np = x_series.to_numpy()
    y_np = y_series.to_numpy()

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x_np,
            y=y_np,
            mode="markers",
            marker={
                "color": marker_colors,
                "size": 8,
                "opacity": 0.6,
            },
            hovertemplate=(
                f"{x_label or x_col}: %{{x:.2f}}<br>"
                f"{y_label or y_col}: %{{y:.2f}}<extra></extra>"
            ),
        )
    )

    # Ligne de tendance
    if show_trendline and len(x_np) > 2:
        valid = ~(np.isnan(x_np) | np.isnan(y_np))
        if valid.sum() > 2:
            x_valid = x_np[valid]
            y_valid = y_np[valid]

            # Vérifier que les données ont une variance suffisante
            x_std = np.std(x_valid)
            y_std = np.std(y_valid)

            # Skipper si variance nulle (tous les points alignés verticalement/horizontalement)
            if x_std > 1e-10 and y_std > 1e-10:
                try:
                    # Régression linéaire simple avec suppression des warnings NumPy
                    with np.errstate(divide="ignore", invalid="ignore"):
                        m, b = np.polyfit(x_valid, y_valid, 1)

                    x_range = np.linspace(x_valid.min(), x_valid.max(), 50)
                    y_trend = m * x_range + b

                    # Calcul R²
                    y_pred = m * x_valid + b
                    ss_res = np.sum((y_valid - y_pred) ** 2)
                    ss_tot = np.sum((y_valid - y_valid.mean()) ** 2)
                    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                    # Vérifier que le résultat est valide
                    if np.isfinite(m) and np.isfinite(b) and np.isfinite(r_squared):
                        fig.add_trace(
                            go.Scatter(
                                x=x_range,
                                y=y_trend,
                                mode="lines",
                                name=f"Tendance (R²={r_squared:.2f})",
                                line={"color": colors["amber"], "width": 2, "dash": "dash"},
                                hoverinfo="skip",
                            )
                        )
                except (np.linalg.LinAlgError, ValueError):
                    # Skipper silencieusement si la régression échoue
                    pass

    fig.update_layout(
        height=PLOT_CONFIG.default_height,
        margin={"l": 40, "r": 20, "t": 60 if title else 30, "b": 40},
        showlegend=show_trendline,
    )
    fig.update_xaxes(title_text=x_label or x_col)
    fig.update_yaxes(title_text=y_label or y_col)

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


def plot_first_event_distribution(
    first_kills: dict[str, int | None],
    first_deaths: dict[str, int | None],
    *,
    title: str | None = None,
) -> go.Figure:
    """Graphique de distribution des timestamps du premier kill/death.

    Args:
        first_kills: Dict {match_id: time_ms} pour le premier kill.
        first_deaths: Dict {match_id: time_ms} pour la première mort.
        title: Titre optionnel.

    Returns:
        Figure Plotly avec histogrammes superposés.
    """
    colors = HALO_COLORS.as_dict()

    # Convertir en secondes et filtrer les None
    kills_sec = [t / 1000 for t in first_kills.values() if t is not None and t > 0]
    deaths_sec = [t / 1000 for t in first_deaths.values() if t is not None and t > 0]

    if not kills_sec and not deaths_sec:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    fig = go.Figure()

    if kills_sec:
        fig.add_trace(
            go.Histogram(
                x=kills_sec,
                name="Premier frag",
                marker_color=colors["green"],
                opacity=0.7,
                nbinsx=20,
                hovertemplate="Temps: %{x:.0f}s<br>Matchs: %{y}<extra></extra>",
            )
        )

    if deaths_sec:
        fig.add_trace(
            go.Histogram(
                x=deaths_sec,
                name="Première mort",
                marker_color=colors["red"],
                opacity=0.6,
                nbinsx=20,
                hovertemplate="Temps: %{x:.0f}s<br>Matchs: %{y}<extra></extra>",
            )
        )

    # Ajouter des lignes verticales pour les moyennes
    if kills_sec:
        avg_kill = sum(kills_sec) / len(kills_sec)
        fig.add_vline(
            x=avg_kill,
            line_dash="dash",
            line_color=colors["green"],
            annotation_text=f"Moy. frag: {avg_kill:.0f}s",
            annotation_position="top",
        )

    if deaths_sec:
        avg_death = sum(deaths_sec) / len(deaths_sec)
        fig.add_vline(
            x=avg_death,
            line_dash="dash",
            line_color=colors["red"],
            annotation_text=f"Moy. mort: {avg_death:.0f}s",
            annotation_position="bottom",
        )

    # Ajouter des lignes verticales pour les médianes
    if kills_sec:
        median_kill = float(np.median(kills_sec))
        fig.add_vline(
            x=median_kill,
            line_dash="dot",
            line_color="#ffaa00",
            annotation_text=f"Méd. frag: {median_kill:.0f}s",
            annotation_position="top right",
            annotation_font_color="#ffaa00",
        )

    if deaths_sec:
        median_death = float(np.median(deaths_sec))
        fig.add_vline(
            x=median_death,
            line_dash="dot",
            line_color="#ffaa00",
            annotation_text=f"Méd. mort: {median_death:.0f}s",
            annotation_position="bottom right",
            annotation_font_color="#ffaa00",
        )

    fig.update_layout(
        barmode="overlay",
        height=PLOT_CONFIG.default_height,
        margin={"l": 40, "r": 20, "t": 60 if title else 30, "b": 40},
        legend=get_legend_horizontal_bottom(),
    )
    fig.update_xaxes(title_text="Temps (secondes)")
    fig.update_yaxes(title_text="Nombre de matchs")

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


# ---------------------------------------------------------------------------
# Re-exports depuis distributions_outcomes (compat backward — Sprint 16)
# ---------------------------------------------------------------------------
from src.visualization.distributions_outcomes import (  # noqa: E402, F401
    plot_matches_at_top_by_week,
    plot_outcomes_over_time,
    plot_stacked_outcomes_by_category,
    plot_win_ratio_heatmap,
)
