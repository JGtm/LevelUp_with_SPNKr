"""Graphiques de distributions et répartitions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import polars as pl

from src.config import HALO_COLORS, OUTCOME_CODES, PLOT_CONFIG, SESSION_CONFIG
from src.visualization.theme import (
    apply_halo_plot_style,
    get_legend_horizontal_bottom,
)


def _normalize_df(df: pd.DataFrame | pl.DataFrame) -> pd.DataFrame:
    """Convertit un DataFrame Polars en Pandas si nécessaire.

    Les fonctions de visualisation utilisent encore certaines opérations Pandas
    spécifiques. Cette fonction normalise l'entrée pour compatibilité.
    """
    if isinstance(df, pl.DataFrame):
        return df.to_pandas()
    return df


def plot_kda_distribution(df: pd.DataFrame | pl.DataFrame) -> go.Figure:
    """Graphique de distribution du KDA (FDA) avec KDE.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonne kda.

    Returns:
        Figure Plotly avec densité KDE et rug plot.
    """
    # Normaliser en Pandas pour compatibilité
    df = _normalize_df(df)

    colors = HALO_COLORS.as_dict()
    d = df.dropna(subset=["kda"]).copy()
    x = pd.to_numeric(d["kda"], errors="coerce").dropna().astype(float).to_numpy()

    if x.size == 0:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height, margin=dict(l=40, r=20, t=30, b=40))
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
            line=dict(width=PLOT_CONFIG.line_width, color=colors["cyan"]),
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
            marker=dict(symbol="line-ns-open", size=10, color="rgba(255,255,255,0.45)"),
            hovertemplate="FDA=%{x:.2f}<extra></extra>",
        )
    )

    fig.add_vline(x=0, line_width=1, line_dash="dot", line_color="rgba(255,255,255,0.35)")
    fig.update_layout(height=PLOT_CONFIG.default_height, margin=dict(l=40, r=20, t=30, b=40))
    fig.update_xaxes(title_text="FDA", zeroline=True)
    fig.update_yaxes(title_text="Densité", rangemode="tozero")

    return apply_halo_plot_style(fig, height=PLOT_CONFIG.default_height)


def plot_outcomes_over_time(
    df: pd.DataFrame | pl.DataFrame, *, session_style: bool = False
) -> tuple[go.Figure, str]:
    """Graphique d'évolution des victoires/défaites dans le temps.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonnes outcome et start_time.
        session_style: Si True, force une logique de bucket orientée "session" :
            - <= 20 matchs : bucket par partie (1..n)
            - > 20 matchs : bucket par heure

    Returns:
        Tuple (figure, bucket_label) où bucket_label décrit la granularité.
    """
    # Normaliser en Pandas pour compatibilité
    df = _normalize_df(df)

    colors = HALO_COLORS.as_dict()
    d = df.dropna(subset=["outcome"]).copy()

    if d.empty:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height, margin=dict(l=40, r=20, t=30, b=40))
        fig.update_yaxes(title_text="Nombre")
        return apply_halo_plot_style(fig, height=PLOT_CONFIG.default_height), "période"

    if session_style:
        d = d.sort_values("start_time").reset_index(drop=True)
        if len(d.index) <= 20:
            bucket = d.index + 1
            bucket_label = "partie"
        else:
            t = pd.to_datetime(d["start_time"], errors="coerce")
            bucket = t.dt.floor("h")
            bucket_label = "heure"
    else:
        tmin = pd.to_datetime(d["start_time"], errors="coerce").min()
        tmax = pd.to_datetime(d["start_time"], errors="coerce").max()

        dt_range = (tmax - tmin) if (tmin == tmin and tmax == tmax) else pd.Timedelta(days=999)
        days = float(dt_range.total_seconds() / 86400.0) if dt_range is not None else 999.0

        cfg = SESSION_CONFIG

        # Détermine le bucket selon la plage de dates
        if days < cfg.bucket_threshold_hourly:
            d = d.sort_values("start_time").reset_index(drop=True)
            bucket = d.index + 1
            bucket_label = "partie"
        elif days <= cfg.bucket_threshold_daily:
            bucket = d["start_time"].dt.floor("h")
            bucket_label = "heure"
        elif days <= cfg.bucket_threshold_weekly:
            bucket = d["start_time"].dt.to_period("D").astype(str)
            bucket_label = "jour"
        elif days <= cfg.bucket_threshold_monthly:
            bucket = d["start_time"].dt.to_period("W-MON").astype(str)
            bucket_label = "semaine"
        else:
            bucket = d["start_time"].dt.to_period("M").astype(str)
            bucket_label = "mois"

    d["bucket"] = bucket
    pivot = (
        d.pivot_table(index="bucket", columns="outcome", values="match_id", aggfunc="count")
        .fillna(0)
        .astype(int)
        .sort_index()
    )

    def col(code: int) -> pd.Series:
        return (
            pivot[code] if code in pivot.columns else pd.Series([0] * len(pivot), index=pivot.index)
        )

    wins = col(2)
    losses = col(3)
    ties = col(1)
    nofin = col(4)

    # Objectif UI: victoires au-dessus (positif) et défaites en dessous (négatif).
    # Plotly empile séparément positifs/négatifs en mode "relative".
    losses_neg = -losses

    fig = go.Figure()
    fig.add_bar(
        x=pivot.index,
        y=wins,
        name="Victoires",
        marker_color=colors["green"],
        hovertemplate="%{x}<br>Victoires: %{y}<extra></extra>",
    )
    fig.add_bar(
        x=pivot.index,
        y=losses_neg,
        name="Défaites",
        marker_color=colors["red"],
        customdata=losses.to_numpy(),
        hovertemplate="%{x}<br>Défaites: %{customdata}<extra></extra>",
    )

    # Ces statuts ne sont pas des "défaites" : on les garde au-dessus.
    if ties.sum() > 0:
        fig.add_bar(
            x=pivot.index,
            y=ties,
            name="Égalités",
            marker_color=colors["violet"],
            hovertemplate="%{x}<br>Égalités: %{y}<extra></extra>",
        )
    if nofin.sum() > 0:
        fig.add_bar(
            x=pivot.index,
            y=nofin,
            name="Non terminés",
            marker_color=colors["violet"],
            hovertemplate="%{x}<br>Non terminés: %{y}<extra></extra>",
        )

    fig.update_layout(
        barmode="relative",
        height=PLOT_CONFIG.default_height,
        margin=dict(l=40, r=20, t=30, b=40),
    )
    fig.update_yaxes(title_text="Nombre", zeroline=True)

    if bucket_label == "partie" and len(pivot.index) > 30:
        fig.update_xaxes(showticklabels=False, title_text="")

    return apply_halo_plot_style(fig, height=PLOT_CONFIG.default_height), bucket_label


def plot_stacked_outcomes_by_category(
    df: pd.DataFrame | pl.DataFrame,
    category_col: str,
    *,
    title: str | None = None,
    min_matches: int = 1,
    sort_by: str = "total",
    max_categories: int = 20,
) -> go.Figure:
    """Graphique de colonnes empilées Win/Loss/Tie/Left par catégorie.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonnes `category_col` et `outcome`.
        category_col: Nom de la colonne de catégorie (ex: "map_name", "mode_category").
        title: Titre optionnel du graphique.
        min_matches: Nombre minimum de matchs pour afficher une catégorie.
        sort_by: Tri des catégories ("total", "win_rate", "name").
        max_categories: Nombre maximum de catégories à afficher.

    Returns:
        Figure Plotly avec barres empilées verticales.
    """
    # Normaliser en Pandas pour compatibilité
    df = _normalize_df(df)

    colors = HALO_COLORS.as_dict()
    d = df.dropna(subset=[category_col, "outcome"]).copy()

    if d.empty:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    # Agrégation par catégorie et outcome
    pivot = (
        d.pivot_table(
            index=category_col,
            columns="outcome",
            values="match_id",
            aggfunc="count",
        )
        .fillna(0)
        .astype(int)
    )

    def col(code: int) -> pd.Series:
        return pivot[code] if code in pivot.columns else pd.Series(0, index=pivot.index)

    pivot["wins"] = col(OUTCOME_CODES.WIN)
    pivot["losses"] = col(OUTCOME_CODES.LOSS)
    pivot["ties"] = col(OUTCOME_CODES.TIE)
    pivot["left"] = col(OUTCOME_CODES.NO_FINISH)
    pivot["total"] = pivot["wins"] + pivot["losses"] + pivot["ties"] + pivot["left"]
    pivot["win_rate"] = (pivot["wins"] / pivot["total"]).fillna(0)

    # Filtrer par minimum de matchs
    pivot = pivot[pivot["total"] >= min_matches]

    if pivot.empty:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    # Tri
    if sort_by == "win_rate":
        pivot = pivot.sort_values("win_rate", ascending=False)
    elif sort_by == "name":
        pivot = pivot.sort_index()
    else:
        pivot = pivot.sort_values("total", ascending=False)

    # Limiter le nombre de catégories
    pivot = pivot.head(max_categories)

    fig = go.Figure()

    # Victoires
    fig.add_trace(
        go.Bar(
            x=pivot.index,
            y=pivot["wins"],
            name="Victoires",
            marker_color=colors["green"],
            opacity=0.85,
            text=pivot["wins"],
            textposition="inside",
            hovertemplate="%{x}<br>Victoires: %{y}<br>Win Rate: %{customdata:.1%}<extra></extra>",
            customdata=pivot["win_rate"],
        )
    )

    # Défaites
    fig.add_trace(
        go.Bar(
            x=pivot.index,
            y=pivot["losses"],
            name="Défaites",
            marker_color=colors["red"],
            opacity=0.75,
            text=pivot["losses"],
            textposition="inside",
            hovertemplate="%{x}<br>Défaites: %{y}<extra></extra>",
        )
    )

    # Égalités (si présentes)
    if pivot["ties"].sum() > 0:
        fig.add_trace(
            go.Bar(
                x=pivot.index,
                y=pivot["ties"],
                name="Égalités",
                marker_color=colors["amber"],
                opacity=0.70,
                text=pivot["ties"].apply(lambda v: str(v) if v > 0 else ""),
                textposition="inside",
                hovertemplate="%{x}<br>Égalités: %{y}<extra></extra>",
            )
        )

    # Non terminés (si présents)
    if pivot["left"].sum() > 0:
        fig.add_trace(
            go.Bar(
                x=pivot.index,
                y=pivot["left"],
                name="Non terminés",
                marker_color=colors["violet"],
                opacity=0.60,
                text=pivot["left"].apply(lambda v: str(v) if v > 0 else ""),
                textposition="inside",
                hovertemplate="%{x}<br>Non terminés: %{y}<extra></extra>",
            )
        )

    height = PLOT_CONFIG.tall_height if len(pivot) > 10 else PLOT_CONFIG.default_height

    fig.update_layout(
        barmode="stack",
        bargap=0.15,
        height=height,
        margin=dict(l=40, r=20, t=60 if title else 30, b=100),
        legend=get_legend_horizontal_bottom(),
    )
    fig.update_xaxes(tickangle=45, title_text="")
    fig.update_yaxes(title_text="Matchs")

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_win_ratio_heatmap(
    df: pd.DataFrame,
    *,
    title: str | None = None,
    min_matches: int = 2,
) -> go.Figure:
    """Heatmap du Win Ratio par jour de la semaine et heure.

    Args:
        df: DataFrame avec colonnes `start_time` et `outcome`.
        title: Titre optionnel.
        min_matches: Minimum de matchs pour afficher une cellule.

    Returns:
        Figure Plotly avec heatmap (jours × heures).
    """
    colors = HALO_COLORS.as_dict()
    d = df.dropna(subset=["start_time", "outcome"]).copy()

    if d.empty:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    d["start_time"] = pd.to_datetime(d["start_time"], errors="coerce")
    d = d.dropna(subset=["start_time"])

    # Extraire jour de semaine et heure
    d["day_of_week"] = d["start_time"].dt.dayofweek  # 0=Lundi, 6=Dimanche
    d["hour"] = d["start_time"].dt.hour
    d["is_win"] = (d["outcome"] == OUTCOME_CODES.WIN).astype(int)

    # Agrégation
    agg = (
        d.groupby(["day_of_week", "hour"])
        .agg(
            wins=("is_win", "sum"),
            total=("match_id", "count"),
        )
        .reset_index()
    )
    agg["win_rate"] = (agg["wins"] / agg["total"]).fillna(0)

    # Filtrer par minimum de matchs
    agg.loc[agg["total"] < min_matches, "win_rate"] = np.nan

    # Pivoter pour créer la matrice
    matrix = agg.pivot(index="day_of_week", columns="hour", values="win_rate")
    counts = agg.pivot(index="day_of_week", columns="hour", values="total")

    # Remplir toutes les heures (0-23) et jours (0-6)
    all_hours = list(range(24))
    all_days = list(range(7))
    matrix = matrix.reindex(index=all_days, columns=all_hours)
    counts = counts.reindex(index=all_days, columns=all_hours).fillna(0).astype(int)

    day_labels = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    hour_labels = [f"{h:02d}h" for h in all_hours]

    # Créer le texte des cellules (nombre de matchs)
    text_matrix = counts.values.astype(str)
    text_matrix[counts.values == 0] = ""

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.values,
            x=hour_labels,
            y=day_labels,
            colorscale=[
                [0.0, colors["red"]],
                [0.5, colors["amber"]],
                [1.0, colors["green"]],
            ],
            zmin=0,
            zmax=1,
            text=text_matrix,
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate=(
                "%{y} %{x}<br>" "Win Rate: %{z:.1%}<br>" "Matchs: %{text}<extra></extra>"
            ),
            colorbar=dict(
                title="Win Rate",
                tickformat=".0%",
            ),
        )
    )

    fig.update_layout(
        height=PLOT_CONFIG.default_height,
        margin=dict(l=60, r=20, t=60 if title else 30, b=40),
    )
    fig.update_xaxes(title_text="Heure", side="bottom")
    fig.update_yaxes(title_text="Jour", autorange="reversed")

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


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

    if isinstance(values, pl.Series):
        x = values.drop_nulls().to_numpy()
    elif isinstance(values, pd.Series):
        x = values.dropna().to_numpy()
    else:
        x = np.array(values)
        x = x[~np.isnan(x)]

    if x.size == 0:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    # Calculer les bins
    if bins == "auto":
        n_bins = min(50, max(10, int(np.sqrt(x.size))))
    else:
        n_bins = int(bins)

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
                    line=dict(color=colors["amber"], width=2),
                    hoverinfo="skip",
                )
            )

    fig.update_layout(
        height=PLOT_CONFIG.default_height,
        margin=dict(l=40, r=20, t=60 if title else 30, b=40),
        bargap=0.05,
    )
    fig.update_xaxes(title_text=x_label)
    fig.update_yaxes(title_text=y_label)

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


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

    # Inverser pour afficher du plus grand au plus petit (haut → bas)
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
        margin=dict(l=40, r=60, t=60 if title else 30, b=40),
    )
    fig.update_xaxes(title_text="Nombre")
    fig.update_yaxes(title_text="")

    return apply_halo_plot_style(fig, title=title, height=height)


def plot_correlation_scatter(
    df: pd.DataFrame | pl.DataFrame,
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
    # Normaliser en Pandas pour compatibilité
    df = _normalize_df(df)

    colors = HALO_COLORS.as_dict()
    d = df.dropna(subset=[x_col, y_col]).copy()

    if d.empty:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    x = pd.to_numeric(d[x_col], errors="coerce")
    y = pd.to_numeric(d[y_col], errors="coerce")

    # Couleur des points
    if color_col and color_col in d.columns:
        d["_color"] = d[color_col]
        color_values = d["_color"].values

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

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="markers",
            marker=dict(
                color=marker_colors,
                size=8,
                opacity=0.6,
            ),
            hovertemplate=(
                f"{x_label or x_col}: %{{x:.2f}}<br>"
                f"{y_label or y_col}: %{{y:.2f}}<extra></extra>"
            ),
        )
    )

    # Ligne de tendance
    if show_trendline and x.size > 2:
        valid = ~(x.isna() | y.isna())
        if valid.sum() > 2:
            x_valid = x[valid].to_numpy()
            y_valid = y[valid].to_numpy()

            # Régression linéaire simple
            m, b = np.polyfit(x_valid, y_valid, 1)
            x_range = np.linspace(x_valid.min(), x_valid.max(), 50)
            y_trend = m * x_range + b

            # Calcul R²
            y_pred = m * x_valid + b
            ss_res = np.sum((y_valid - y_pred) ** 2)
            ss_tot = np.sum((y_valid - y_valid.mean()) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            fig.add_trace(
                go.Scatter(
                    x=x_range,
                    y=y_trend,
                    mode="lines",
                    name=f"Tendance (R²={r_squared:.2f})",
                    line=dict(color=colors["amber"], width=2, dash="dash"),
                    hoverinfo="skip",
                )
            )

    fig.update_layout(
        height=PLOT_CONFIG.default_height,
        margin=dict(l=40, r=20, t=60 if title else 30, b=40),
        showlegend=show_trendline,
    )
    fig.update_xaxes(title_text=x_label or x_col)
    fig.update_yaxes(title_text=y_label or y_col)

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


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


def plot_matches_at_top_by_week(
    df: pd.DataFrame,
    *,
    title: str | None = None,
    rank_col: str = "rank",
    top_n_ranks: int = 1,
) -> go.Figure:
    """Graphique comparant les matchs 'Top' vs Total par semaine.

    Args:
        df: DataFrame avec colonnes `start_time` et `rank` (ou équivalent).
        title: Titre optionnel.
        rank_col: Nom de la colonne de rang (défaut: "rank").
        top_n_ranks: Nombre de rangs considérés comme "Top" (défaut: 1 = 1ère place uniquement).

    Returns:
        Figure Plotly avec barres empilées (Top + Autres).
    """
    colors = HALO_COLORS.as_dict()
    d = df.dropna(subset=["start_time"]).copy()

    if d.empty:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    d["start_time"] = pd.to_datetime(d["start_time"], errors="coerce")
    d = d.dropna(subset=["start_time"])

    # Grouper par semaine
    d["week"] = d["start_time"].dt.to_period("W-MON").astype(str)

    # Déterminer si le joueur a fini "Top"
    if rank_col in d.columns:
        d["is_top"] = pd.to_numeric(d[rank_col], errors="coerce").fillna(99) <= top_n_ranks
    else:
        # Fallback: utiliser outcome (victoire = top)
        d["is_top"] = d["outcome"] == OUTCOME_CODES.WIN if "outcome" in d.columns else False

    # Agrégation
    agg = (
        d.groupby("week")
        .agg(
            total=("match_id", "count"),
            top_count=("is_top", "sum"),
        )
        .reset_index()
    )
    agg["other_count"] = agg["total"] - agg["top_count"]
    agg["top_rate"] = (agg["top_count"] / agg["total"] * 100).round(1)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=agg["week"],
            y=agg["top_count"],
            name=f"Top {top_n_ranks}",
            marker_color=colors["green"],
            opacity=0.85,
            text=agg["top_count"],
            textposition="inside",
            hovertemplate="%{x}<br>Top: %{y}<br>Taux: %{customdata:.1f}%<extra></extra>",
            customdata=agg["top_rate"],
        )
    )

    fig.add_trace(
        go.Bar(
            x=agg["week"],
            y=agg["other_count"],
            name="Autres",
            marker_color=colors["slate"],
            opacity=0.55,
            text=agg["other_count"].apply(lambda v: str(v) if v > 0 else ""),
            textposition="inside",
            hovertemplate="%{x}<br>Autres: %{y}<extra></extra>",
        )
    )

    # Ligne de tendance du taux
    fig.add_trace(
        go.Scatter(
            x=agg["week"],
            y=agg["top_rate"],
            mode="lines+markers",
            name="Taux Top (%)",
            yaxis="y2",
            line=dict(color=colors["amber"], width=2),
            marker=dict(size=6),
            hovertemplate="%{x}<br>Taux Top: %{y:.1f}%<extra></extra>",
        )
    )

    fig.update_layout(
        barmode="stack",
        bargap=0.15,
        height=PLOT_CONFIG.default_height,
        margin=dict(l=40, r=60, t=60 if title else 30, b=80),
        legend=get_legend_horizontal_bottom(),
        yaxis2=dict(
            title="Taux (%)",
            overlaying="y",
            side="right",
            range=[0, 100],
            showgrid=False,
        ),
    )
    fig.update_xaxes(tickangle=45, title_text="Semaine")
    fig.update_yaxes(title_text="Matchs")

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


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
                name="Premier kill",
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
            annotation_text=f"Moy. kill: {avg_kill:.0f}s",
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

    fig.update_layout(
        barmode="overlay",
        height=PLOT_CONFIG.default_height,
        margin={"l": 40, "r": 20, "t": 60 if title else 30, "b": 40},
        legend=get_legend_horizontal_bottom(),
    )
    fig.update_xaxes(title_text="Temps (secondes)")
    fig.update_yaxes(title_text="Nombre de matchs")

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


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
