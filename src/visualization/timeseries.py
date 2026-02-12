"""Graphiques de séries temporelles."""

import pandas as pd
import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from src.analysis.performance_config import SCORE_THRESHOLDS
from src.config import HALO_COLORS, PLOT_CONFIG
from src.ui.components.chart_annotations import add_extreme_annotations
from src.visualization.theme import apply_halo_plot_style, get_legend_horizontal_bottom


def _normalize_df(df: pd.DataFrame | pl.DataFrame) -> pd.DataFrame:
    """Convertit un DataFrame Polars en Pandas si nécessaire.

    Les fonctions de visualisation utilisent encore certaines opérations Pandas
    spécifiques. Cette fonction normalise l'entrée pour compatibilité.
    """
    if isinstance(df, pl.DataFrame):
        return df.to_pandas()
    return df


def _rolling_mean(series: pd.Series | pl.Series, window: int = 10) -> pd.Series:
    """Calcule la moyenne mobile.

    Args:
        series: Série Pandas ou Polars.
        window: Taille de la fenêtre.

    Returns:
        Série Pandas avec moyenne mobile.
    """
    w = int(window) if window and window > 0 else 1
    if isinstance(series, pl.Series):
        series = series.to_pandas()
    return series.rolling(window=w, min_periods=1).mean()


def plot_timeseries(
    df: pd.DataFrame | pl.DataFrame, title: str = "Frags / Morts / Ratio"
) -> go.Figure:
    """Graphique principal: Kills/Deaths/Ratio dans le temps.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonnes kills, deaths, assists, accuracy, ratio, start_time.
        title: Titre du graphique.

    Returns:
        Figure Plotly.
    """
    # Normaliser en Pandas pour compatibilité avec le reste du code
    df = _normalize_df(df)

    if df is None or (hasattr(df, "empty") and df.empty) or len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="Aucune donnée disponible",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16},
        )
        return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.tall_height)

    fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])
    colors = HALO_COLORS.as_dict()

    d = df.sort_values("start_time").reset_index(drop=True)
    x_idx = list(range(len(d)))

    common_hover = (
        "frags=%{customdata[0]} morts=%{customdata[1]} assistances=%{customdata[2]}<br>"
        "précision=%{customdata[3]}% ratio=%{customdata[4]:.3f}<extra></extra>"
    )

    customdata = list(
        zip(
            d["kills"],
            d["deaths"],
            d["assists"],
            pd.to_numeric(d["accuracy"], errors="coerce").fillna(0).round(2),
            d["ratio"],
            strict=False,
        )
    )

    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=d["kills"],
            name="Frags",
            marker_color=colors["cyan"],
            opacity=PLOT_CONFIG.bar_opacity,
            alignmentgroup="kda_main",
            offsetgroup="kills",
            width=0.42,
            customdata=customdata,
            hovertemplate=common_hover,
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=d["deaths"],
            name="Morts",
            marker_color=colors["red"],
            opacity=PLOT_CONFIG.bar_opacity_secondary,
            alignmentgroup="kda_main",
            offsetgroup="deaths",
            width=0.42,
            customdata=customdata,
            hovertemplate=common_hover,
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=x_idx,
            y=d["ratio"],
            mode="lines",
            name="Ratio",
            line={"width": PLOT_CONFIG.line_width, "color": colors["green"]},
            customdata=customdata,
            hovertemplate=common_hover,
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title=title,
        legend=get_legend_horizontal_bottom(),
        margin={"l": 40, "r": 20, "t": 80, "b": 90},
        hovermode="x unified",
        barmode="group",
        bargap=0.15,
        bargroupgap=0.06,
    )

    fig.update_xaxes(type="category")
    fig.update_yaxes(title_text="Frags / Morts", rangemode="tozero", secondary_y=False)
    fig.update_yaxes(title_text="Ratio", secondary_y=True)

    # Labels de date/heure espacés
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").tolist()
    step = max(1, len(labels) // 10) if len(labels) > 1 else 1
    tickvals = x_idx[::step]
    ticktext = labels[::step]
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
    )

    # Annotations sur les valeurs extrêmes du ratio
    add_extreme_annotations(
        fig,
        x_idx,
        d["ratio"].tolist(),
        metric_name="ratio",
        show_max=True,
        show_min=False,
        max_color="#FFD700",  # Or
        secondary_y=True,
    )

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.tall_height)


def plot_assists_timeseries(
    df: pd.DataFrame | pl.DataFrame, title: str = "Assistances"
) -> go.Figure:
    """Graphique des assistances dans le temps.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonnes assists, start_time, etc.
        title: Titre du graphique.

    Returns:
        Figure Plotly.
    """
    # Normaliser en Pandas pour compatibilité
    df = _normalize_df(df)

    colors = HALO_COLORS.as_dict()
    d = df.sort_values("start_time").reset_index(drop=True)
    x_idx = list(range(len(d)))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").tolist()
    step = max(1, len(labels) // 10) if len(labels) > 1 else 1

    customdata = list(
        zip(
            d["kills"],
            d["deaths"],
            d["assists"],
            pd.to_numeric(d["accuracy"], errors="coerce").fillna(0).round(2),
            d["ratio"],
            d["map_name"].fillna(""),
            d["playlist_name"].fillna(""),
            d["match_id"],
            strict=False,
        )
    )
    hover = (
        "assistances=%{y}<br>"
        "frags=%{customdata[0]} morts=%{customdata[1]}<br>"
        "précision=%{customdata[3]}% ratio=%{customdata[4]:.3f}<extra></extra>"
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=d["assists"],
            name="Assistances",
            marker_color=colors["violet"],
            opacity=PLOT_CONFIG.bar_opacity,
            customdata=customdata,
            hovertemplate=hover,
        )
    )

    smooth = _rolling_mean(pd.to_numeric(d["assists"], errors="coerce"), window=10)
    fig.add_trace(
        go.Scatter(
            x=x_idx,
            y=smooth,
            mode="lines",
            name="Moyenne (lissée)",
            line={"width": PLOT_CONFIG.line_width, "color": colors["green"]},
            hovertemplate="moyenne=%{y:.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 60, "b": 90},
        hovermode="x unified",
        legend=get_legend_horizontal_bottom(),
    )
    fig.update_yaxes(title_text="Assistances", rangemode="tozero")
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
        type="category",
    )

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


def plot_per_minute_timeseries(
    df: pd.DataFrame | pl.DataFrame, title: str = "Frags / Morts / Assistances par minute"
) -> go.Figure:
    """Graphique des stats par minute.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonnes kills_per_min, deaths_per_min, assists_per_min.
        title: Titre du graphique.

    Returns:
        Figure Plotly.
    """
    # Normaliser en Pandas pour compatibilité
    df = _normalize_df(df)

    colors = HALO_COLORS.as_dict()
    d = df.sort_values("start_time").reset_index(drop=True)
    x_idx = list(range(len(d)))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").tolist()
    step = max(1, len(labels) // 10) if len(labels) > 1 else 1

    customdata = list(
        zip(
            d["time_played_seconds"].astype(float).fillna(float("nan")),
            d["kills"],
            d["deaths"],
            d["assists"],
            d["match_id"],
            strict=False,
        )
    )

    kpm = pd.to_numeric(d["kills_per_min"], errors="coerce")
    dpm = pd.to_numeric(d["deaths_per_min"], errors="coerce")
    apm = pd.to_numeric(d["assists_per_min"], errors="coerce")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=kpm,
            name="Frags/min",
            marker_color=colors["cyan"],
            opacity=PLOT_CONFIG.bar_opacity,
            customdata=customdata,
            hovertemplate=(
                "frags/min=%{y:.2f}<br>"
                "temps joué=%{customdata[0]:.0f}s (frags=%{customdata[1]:.0f})<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=dpm,
            name="Morts/min",
            marker_color=colors["red"],
            opacity=PLOT_CONFIG.bar_opacity_secondary,
            customdata=customdata,
            hovertemplate=(
                "morts/min=%{y:.2f}<br>"
                "temps joué=%{customdata[0]:.0f}s (morts=%{customdata[2]:.0f})<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=apm,
            name="Assist./min",
            marker_color=colors["violet"],
            opacity=PLOT_CONFIG.bar_opacity_secondary,
            customdata=customdata,
            hovertemplate=(
                "assist./min=%{y:.2f}<br>"
                "temps joué=%{customdata[0]:.0f}s (assistances=%{customdata[3]:.0f})<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x_idx,
            y=_rolling_mean(kpm, window=10),
            mode="lines",
            name="Moy. frags/min",
            line={"width": PLOT_CONFIG.line_width, "color": colors["cyan"]},
            hovertemplate="moy=%{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_idx,
            y=_rolling_mean(dpm, window=10),
            mode="lines",
            name="Moy. morts/min",
            line={"width": PLOT_CONFIG.line_width, "color": colors["red"], "dash": "dot"},
            hovertemplate="moy=%{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_idx,
            y=_rolling_mean(apm, window=10),
            mode="lines",
            name="Moy. assist./min",
            line={"width": PLOT_CONFIG.line_width, "color": colors["violet"], "dash": "dot"},
            hovertemplate="moy=%{y:.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 60, "b": 90},
        hovermode="x unified",
        legend=get_legend_horizontal_bottom(),
        barmode="group",
        bargap=0.15,
        bargroupgap=0.06,
    )
    fig.update_yaxes(title_text="Par minute", rangemode="tozero")
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
        type="category",
    )

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


def plot_accuracy_last_n(df: pd.DataFrame | pl.DataFrame, n: int) -> go.Figure:
    """Graphique de précision sur les N derniers matchs.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonne accuracy.
        n: Nombre de matchs à afficher.

    Returns:
        Figure Plotly.
    """
    # Normaliser en Pandas pour compatibilité
    df = _normalize_df(df)

    colors = HALO_COLORS.as_dict()
    d = df.dropna(subset=["accuracy"]).tail(n)

    fig = go.Figure(
        data=[
            go.Scatter(
                x=d["start_time"],
                y=d["accuracy"],
                mode="lines",
                name="Accuracy",
                line={"width": PLOT_CONFIG.line_width, "color": colors["violet"]},
                hovertemplate="précision=%{y:.2f}%<extra></extra>",
            )
        ]
    )
    fig.update_layout(height=PLOT_CONFIG.short_height, margin={"l": 40, "r": 20, "t": 30, "b": 40})
    fig.update_yaxes(title_text="%", rangemode="tozero")

    return apply_halo_plot_style(fig, height=PLOT_CONFIG.short_height)


def plot_average_life(
    df: pd.DataFrame | pl.DataFrame, title: str = "Durée de vie moyenne"
) -> go.Figure:
    """Graphique de la durée de vie moyenne.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonne average_life_seconds.
        title: Titre du graphique.

    Returns:
        Figure Plotly.
    """
    # Normaliser en Pandas pour compatibilité
    df = _normalize_df(df)

    colors = HALO_COLORS.as_dict()
    d = (
        df.dropna(subset=["average_life_seconds"])
        .sort_values("start_time")
        .reset_index(drop=True)
        .copy()
    )
    x_idx = list(range(len(d)))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").tolist()
    step = max(1, len(labels) // 10) if len(labels) > 1 else 1

    y = pd.to_numeric(d["average_life_seconds"], errors="coerce")
    custom = list(
        zip(
            d["deaths"].fillna(0).astype(int),
            d["time_played_seconds"].fillna(float("nan")).astype(float),
            d["match_id"].astype(str),
            strict=False,
        )
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=y,
            name="Durée de vie (s)",
            marker_color=colors["green"],
            opacity=PLOT_CONFIG.bar_opacity,
            customdata=custom,
            hovertemplate=(
                "durée de vie moy.=%{y:.1f}s<br>"
                "morts=%{customdata[0]}<br>"
                "temps joué=%{customdata[1]:.0f}s<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x_idx,
            y=_rolling_mean(y, window=10),
            mode="lines",
            name="Moyenne (lissée)",
            line={"width": PLOT_CONFIG.line_width, "color": colors["cyan"]},
            hovertemplate="moyenne=%{y:.2f}s<extra></extra>",
        )
    )

    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 50, "b": 90},
        hovermode="x unified",
        legend=get_legend_horizontal_bottom(),
    )
    fig.update_yaxes(title_text="Secondes", rangemode="tozero")
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
        type="category",
    )

    return apply_halo_plot_style(fig, height=PLOT_CONFIG.short_height)


def plot_spree_headshots_accuracy(
    df: pd.DataFrame | pl.DataFrame,
    perfect_counts: dict[str, int] | None = None,
) -> go.Figure:
    """Graphique combiné: Spree, Tirs à la tête, Précision et Perfect kills.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonnes max_killing_spree, headshot_kills, accuracy.
        perfect_counts: Dict optionnel {match_id: count} pour les médailles Perfect.

    Returns:
        Figure Plotly avec axe Y secondaire pour la précision.
    """
    # Normaliser en Pandas pour compatibilité
    df = _normalize_df(df)

    colors = HALO_COLORS.as_dict()
    d = df.sort_values("start_time").reset_index(drop=True).copy()
    x_idx = list(range(len(d)))

    spree = (
        pd.to_numeric(d.get("max_killing_spree"), errors="coerce")
        if "max_killing_spree" in d.columns
        else pd.Series([float("nan")] * len(d))
    )

    fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=spree,
            name="Folie meurtrière (max)",
            marker_color=colors["amber"],
            opacity=PLOT_CONFIG.bar_opacity,
            alignmentgroup="spree_hs",
            offsetgroup="spree",
            width=0.42,
            hovertemplate="folie meurtrière=%{y}<extra></extra>",
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=d["headshot_kills"],
            name="Tirs à la tête",
            marker_color=colors["red"],
            opacity=0.70,
            alignmentgroup="spree_hs",
            offsetgroup="headshots",
            width=0.42,
            hovertemplate="tirs à la tête=%{y}<extra></extra>",
        ),
        secondary_y=False,
    )

    # Frags parfaits (médaille Perfect = tuer sans prendre de dégâts) — toujours afficher la série
    if "match_id" in d.columns:
        perfect_series = (
            d["match_id"].astype(str).map(lambda mid: (perfect_counts or {}).get(mid, 0))
            if perfect_counts is not None
            else pd.Series([0] * len(d))
        )
    else:
        perfect_series = pd.Series([0] * len(d))
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=perfect_series,
            name="Frags parfaits",
            marker_color=colors["green"],
            opacity=0.65,
            alignmentgroup="spree_hs",
            offsetgroup="perfect",
            width=0.28,
            hovertemplate="frags parfaits=%{y}<extra></extra>",
        ),
        secondary_y=False,
    )

    labels = d["start_time"].dt.strftime("%m-%d %H:%M").tolist()
    step = max(1, len(labels) // 10) if labels else 1
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
    )

    fig.update_layout(
        height=420,
        margin={"l": 40, "r": 50, "t": 30, "b": 90},
        legend=get_legend_horizontal_bottom(),
        hovermode="x unified",
        barmode="group",
        bargap=0.15,
        bargroupgap=0.06,
    )

    fig.update_yaxes(title_text="Spree / Tirs à la tête", rangemode="tozero", secondary_y=False)

    return apply_halo_plot_style(fig, height=420)


def plot_performance_timeseries(
    df: pd.DataFrame | pl.DataFrame,
    df_history: pd.DataFrame | pl.DataFrame | None = None,
    title: str = "Score de performance",
    show_smooth: bool = True,
) -> go.Figure:
    """Graphique du score de performance dans le temps.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonnes performance ou kills/deaths/assists/accuracy/outcome.
        df_history: DataFrame complet (Pandas ou Polars) pour le calcul du score relatif.
        title: Titre du graphique.
        show_smooth: Afficher la courbe de moyenne lissée.

    Returns:
        Figure Plotly.
    """
    from src.analysis.performance_score import compute_performance_series

    # Normaliser en Pandas pour compatibilité
    df = _normalize_df(df)
    if df_history is not None:
        df_history = _normalize_df(df_history)

    colors = HALO_COLORS.as_dict()
    d = df.sort_values("start_time").reset_index(drop=True)
    x_idx = list(range(len(d)))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").tolist()
    step = max(1, len(labels) // 10) if len(labels) > 1 else 1

    # Calculer le score de performance RELATIF
    history = df_history if df_history is not None else df
    if "performance" not in d.columns or d["performance"].isna().all():
        d["performance"] = compute_performance_series(d, history)

    performance = pd.to_numeric(d["performance"], errors="coerce")

    # Déterminer la couleur en fonction du score
    def _get_perf_color(val: float) -> str:
        if val >= SCORE_THRESHOLDS["excellent"]:
            return colors.get("green", "#50C878")
        elif val >= SCORE_THRESHOLDS["good"]:
            return colors.get("cyan", "#00B7EB")
        elif val >= SCORE_THRESHOLDS["average"]:
            return colors.get("amber", "#FFBF00")
        elif val >= SCORE_THRESHOLDS["below_average"]:
            return colors.get("orange", "#FF8C00")
        else:
            return colors.get("red", "#FF4444")

    bar_colors = [
        _get_perf_color(v) if not pd.isna(v) else colors.get("gray", "#888888") for v in performance
    ]

    hover = "performance=%{y:.1f}<br>" "date=%{customdata[0]}<extra></extra>"
    customdata = list(zip(d["start_time"].dt.strftime("%d/%m/%Y %H:%M"), strict=False))

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=performance,
            name="Performance",
            marker_color=bar_colors,
            opacity=PLOT_CONFIG.bar_opacity,
            customdata=customdata,
            hovertemplate=hover,
        )
    )

    if show_smooth:
        smooth = _rolling_mean(performance, window=10)
        fig.add_trace(
            go.Scatter(
                x=x_idx,
                y=smooth,
                mode="lines",
                name="Moyenne (lissée)",
                line={"width": PLOT_CONFIG.line_width, "color": colors.get("violet", "#8B5CF6")},
                hovertemplate="moyenne=%{y:.1f}<extra></extra>",
            )
        )

    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 60, "b": 90},
        hovermode="x unified",
        legend=get_legend_horizontal_bottom(),
    )
    fig.update_yaxes(title_text="Score de performance", rangemode="tozero", range=[0, 100])
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
        type="category",
    )

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


# =============================================================================
# Sprint 7 — Nouvelles fonctions de visualisation
# =============================================================================


def plot_streak_chart(
    df: pd.DataFrame | pl.DataFrame,
    title: str = "Séries de victoires / défaites",
) -> go.Figure:
    """Graphique des séries de victoires et défaites dans le temps.

    Affiche des barres positives (victoires) et négatives (défaites)
    colorées par le type de résultat.

    Args:
        df: DataFrame avec colonnes outcome, start_time.
        title: Titre du graphique.

    Returns:
        Figure Plotly.
    """
    df = _normalize_df(df)
    colors = HALO_COLORS.as_dict()

    d = df.sort_values("start_time").reset_index(drop=True).copy()

    # Filtrer : ne garder que V/D
    d = d[d["outcome"].isin([2, 3])].reset_index(drop=True)
    if d.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Aucune donnée de victoires/défaites",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16},
        )
        return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.short_height)

    x_idx = list(range(len(d)))

    # Calculer la série : cumul dans chaque streak
    is_win = (d["outcome"] == 2).astype(int)
    new_streak = (d["outcome"] != d["outcome"].shift(1)).fillna(True)
    streak_group = new_streak.cumsum()

    streak_counter: list[int] = []
    prev_group = -1
    count = 0
    for g in streak_group:
        if g != prev_group:
            count = 1
            prev_group = g
        else:
            count += 1
        streak_counter.append(count)

    streak_values = [c if w == 1 else -c for c, w in zip(streak_counter, is_win, strict=False)]

    bar_colors = [colors["green"] if v > 0 else colors["red"] for v in streak_values]

    labels = d["start_time"].dt.strftime("%m-%d %H:%M").tolist()
    step = max(1, len(labels) // 10) if labels else 1

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=streak_values,
            marker_color=bar_colors,
            opacity=0.85,
            hovertemplate="série=%{y}<br>date=%{customdata}<extra></extra>",
            customdata=labels,
            showlegend=False,
        )
    )

    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 40, "b": 90},
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Série (+ victoires / − défaites)", zeroline=True)
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
        type="category",
    )

    return apply_halo_plot_style(fig, height=PLOT_CONFIG.short_height)


def plot_damage_dealt_taken(
    df: pd.DataFrame | pl.DataFrame,
    title: str = "Dégâts infligés vs subis",
) -> go.Figure:
    """Graphique des dégâts infligés et subis par match.

    Barres groupées pour damage_dealt et damage_taken.

    Args:
        df: DataFrame avec colonnes damage_dealt, damage_taken, start_time.
        title: Titre du graphique.

    Returns:
        Figure Plotly.
    """
    df = _normalize_df(df)
    colors = HALO_COLORS.as_dict()

    d = df.sort_values("start_time").reset_index(drop=True).copy()
    x_idx = list(range(len(d)))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").tolist()
    step = max(1, len(labels) // 10) if labels else 1

    fig = go.Figure()

    if "damage_dealt" in d.columns:
        dealt = pd.to_numeric(d["damage_dealt"], errors="coerce").fillna(0)
        fig.add_trace(
            go.Bar(
                x=x_idx,
                y=dealt,
                name="Dégâts infligés",
                marker_color=colors["cyan"],
                opacity=0.80,
                hovertemplate="infligés=%{y:.0f}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_idx,
                y=_rolling_mean(dealt, window=10),
                mode="lines",
                name="Moy. infligés",
                line={"width": PLOT_CONFIG.line_width, "color": colors["cyan"]},
                hovertemplate="moy=%{y:.0f}<extra></extra>",
            )
        )

    if "damage_taken" in d.columns:
        taken = pd.to_numeric(d["damage_taken"], errors="coerce").fillna(0)
        fig.add_trace(
            go.Bar(
                x=x_idx,
                y=taken,
                name="Dégâts subis",
                marker_color=colors["red"],
                opacity=0.65,
                hovertemplate="subis=%{y:.0f}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_idx,
                y=_rolling_mean(taken, window=10),
                mode="lines",
                name="Moy. subis",
                line={"width": PLOT_CONFIG.line_width, "color": colors["red"], "dash": "dot"},
                hovertemplate="moy=%{y:.0f}<extra></extra>",
            )
        )

    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 40, "b": 90},
        hovermode="x unified",
        legend=get_legend_horizontal_bottom(),
        barmode="group",
        bargap=0.15,
        bargroupgap=0.06,
    )
    fig.update_yaxes(title_text="Dégâts", rangemode="tozero")
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
        type="category",
    )

    return apply_halo_plot_style(fig, height=PLOT_CONFIG.default_height)


def plot_shots_accuracy(
    df: pd.DataFrame | pl.DataFrame,
    title: str = "Tirs et précision",
) -> go.Figure:
    """Graphique des tirs (tirés/touchés) en barres groupées avec courbe de précision.

    Args:
        df: DataFrame avec colonnes shots_fired, shots_hit, accuracy, start_time.
        title: Titre du graphique.

    Returns:
        Figure Plotly avec axe Y secondaire pour la précision.
    """
    df = _normalize_df(df)
    colors = HALO_COLORS.as_dict()

    d = df.sort_values("start_time").reset_index(drop=True).copy()
    x_idx = list(range(len(d)))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").tolist()
    step = max(1, len(labels) // 10) if labels else 1

    fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])

    if "shots_fired" in d.columns:
        fired = pd.to_numeric(d["shots_fired"], errors="coerce").fillna(0)
        fig.add_trace(
            go.Bar(
                x=x_idx,
                y=fired,
                name="Tirs tirés",
                marker_color=colors["amber"],
                opacity=0.70,
                alignmentgroup="shots",
                offsetgroup="fired",
                width=0.42,
                hovertemplate="tirés=%{y:.0f}<extra></extra>",
            ),
            secondary_y=False,
        )

    if "shots_hit" in d.columns:
        hit = pd.to_numeric(d["shots_hit"], errors="coerce").fillna(0)
        fig.add_trace(
            go.Bar(
                x=x_idx,
                y=hit,
                name="Tirs touchés",
                marker_color=colors["green"],
                opacity=0.70,
                alignmentgroup="shots",
                offsetgroup="hit",
                width=0.42,
                hovertemplate="touchés=%{y:.0f}<extra></extra>",
            ),
            secondary_y=False,
        )

    if "accuracy" in d.columns:
        accuracy = pd.to_numeric(d["accuracy"], errors="coerce")
        fig.add_trace(
            go.Scatter(
                x=x_idx,
                y=accuracy,
                mode="lines",
                name="Précision (%)",
                line={"width": PLOT_CONFIG.line_width, "color": colors["violet"]},
                hovertemplate="précision=%{y:.2f}%<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
    )

    fig.update_layout(
        title=title,
        height=420,
        margin={"l": 40, "r": 50, "t": 40, "b": 90},
        legend=get_legend_horizontal_bottom(),
        hovermode="x unified",
        barmode="group",
        bargap=0.15,
        bargroupgap=0.06,
    )

    fig.update_yaxes(title_text="Tirs", rangemode="tozero", secondary_y=False)
    fig.update_yaxes(
        title_text="Précision (%)", ticksuffix="%", rangemode="tozero", secondary_y=True
    )

    return apply_halo_plot_style(fig, height=420)


def plot_rank_score(
    df: pd.DataFrame | pl.DataFrame,
    title: str = "Rang et score personnel",
) -> go.Figure:
    """Graphique du rang et du score personnel par match.

    Barres pour le score personnel, ligne pour le rang.

    Args:
        df: DataFrame avec colonnes rank, personal_score, start_time.
        title: Titre du graphique.

    Returns:
        Figure Plotly avec axe Y secondaire pour le rang.
    """
    df = _normalize_df(df)
    colors = HALO_COLORS.as_dict()

    d = df.sort_values("start_time").reset_index(drop=True).copy()
    x_idx = list(range(len(d)))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").tolist()
    step = max(1, len(labels) // 10) if labels else 1

    fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])

    if "personal_score" in d.columns:
        score = pd.to_numeric(d["personal_score"], errors="coerce").fillna(0)
        fig.add_trace(
            go.Bar(
                x=x_idx,
                y=score,
                name="Score personnel",
                marker_color=colors["amber"],
                opacity=0.75,
                hovertemplate="score=%{y:.0f}<extra></extra>",
            ),
            secondary_y=False,
        )

    if "rank" in d.columns:
        rank = pd.to_numeric(d["rank"], errors="coerce")
        fig.add_trace(
            go.Scatter(
                x=x_idx,
                y=rank,
                mode="lines+markers",
                name="Rang",
                line={"width": PLOT_CONFIG.line_width, "color": colors["cyan"]},
                marker={"size": 4},
                hovertemplate="rang=%{y}<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
    )

    fig.update_layout(
        title=title,
        height=400,
        margin={"l": 40, "r": 50, "t": 40, "b": 90},
        legend=get_legend_horizontal_bottom(),
        hovermode="x unified",
    )

    fig.update_yaxes(title_text="Score personnel", rangemode="tozero", secondary_y=False)
    fig.update_yaxes(title_text="Rang", autorange="reversed", rangemode="tozero", secondary_y=True)

    return apply_halo_plot_style(fig, height=400)
