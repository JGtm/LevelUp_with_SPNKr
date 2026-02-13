"""Graphiques de séries temporelles — Combat (Sprint 16).

Fonctions déplacées depuis ``timeseries.py`` pour alléger le module principal.
"""

import math

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots

from src.analysis.performance_config import SCORE_THRESHOLDS
from src.config import HALO_COLORS, PLOT_CONFIG
from src.ui.components.chart_annotations import add_extreme_annotations  # noqa: F401
from src.visualization._compat import DataFrameLike, ensure_polars  # noqa: F401
from src.visualization.theme import apply_halo_plot_style, get_legend_horizontal_bottom
from src.visualization.timeseries import _normalize_df, _rolling_mean


def plot_average_life(df: DataFrameLike, title: str = "Durée de vie moyenne") -> go.Figure:
    """Graphique de la durée de vie moyenne.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonne average_life_seconds.
        title: Titre du graphique.

    Returns:
        Figure Plotly.
    """
    # Normaliser en Polars
    d = _normalize_df(df)

    colors = HALO_COLORS.as_dict()
    d = d.filter(pl.col("average_life_seconds").is_not_null()).sort("start_time")
    x_idx = list(range(d.height))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").to_list()
    step = max(1, len(labels) // 10) if len(labels) > 1 else 1

    y = d["average_life_seconds"].cast(pl.Float64, strict=False)
    custom = list(
        zip(
            d["deaths"].fill_null(0).cast(pl.Int64).to_list(),
            d["time_played_seconds"].cast(pl.Float64, strict=False).to_list(),
            d["match_id"].cast(pl.Utf8).to_list(),
            strict=False,
        )
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=y.to_list(),
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
            y=_rolling_mean(y, window=10).to_list(),
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
    df: DataFrameLike,
    perfect_counts: dict[str, int] | None = None,
) -> go.Figure:
    """Graphique combiné: Spree, Tirs à la tête, Précision et Perfect kills.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonnes max_killing_spree, headshot_kills, accuracy.
        perfect_counts: Dict optionnel {match_id: count} pour les médailles Perfect.

    Returns:
        Figure Plotly avec axe Y secondaire pour la précision.
    """
    # Normaliser en Polars
    d = _normalize_df(df)

    colors = HALO_COLORS.as_dict()
    d = d.sort("start_time")
    x_idx = list(range(d.height))

    if "max_killing_spree" in d.columns:
        spree = d["max_killing_spree"].cast(pl.Float64, strict=False).to_list()
    else:
        spree = [float("nan")] * d.height

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
            y=d["headshot_kills"].to_list(),
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
    if "match_id" in d.columns and perfect_counts is not None:
        match_ids = d["match_id"].cast(pl.Utf8).to_list()
        perfect_series = [perfect_counts.get(mid, 0) for mid in match_ids]
    else:
        perfect_series = [0] * d.height
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

    labels = d["start_time"].dt.strftime("%m-%d %H:%M").to_list()
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
    df: DataFrameLike,
    df_history: DataFrameLike | None = None,
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

    # Normaliser en Polars
    d = _normalize_df(df)
    history_pl: pl.DataFrame | None = None
    if df_history is not None:
        history_pl = _normalize_df(df_history)

    colors = HALO_COLORS.as_dict()
    d = d.sort("start_time")
    x_idx = list(range(d.height))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").to_list()
    step = max(1, len(labels) // 10) if len(labels) > 1 else 1

    # Calculer le score de performance RELATIF
    history = history_pl if history_pl is not None else d
    if "performance" not in d.columns or d["performance"].is_null().all():
        perf_series = compute_performance_series(d, history)
        if isinstance(perf_series, pl.Series):
            d = d.with_columns(perf_series.alias("performance"))
        else:
            d = d.with_columns(pl.Series("performance", perf_series.to_list()))

    performance = d["performance"].cast(pl.Float64, strict=False)

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
        _get_perf_color(v)
        if not (v is None or (isinstance(v, float) and math.isnan(v)))
        else colors.get("gray", "#888888")
        for v in performance.to_list()
    ]

    hover = "performance=%{y:.1f}<br>" "date=%{customdata[0]}<extra></extra>"
    customdata = list(zip(d["start_time"].dt.strftime("%d/%m/%Y %H:%M").to_list(), strict=False))

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=performance.to_list(),
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
                y=smooth.to_list(),
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
    df: DataFrameLike,
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
    d = _normalize_df(df)
    colors = HALO_COLORS.as_dict()

    d = d.sort("start_time")

    # Filtrer : ne garder que V/D
    d = d.filter(pl.col("outcome").is_in([2, 3]))
    if d.height == 0:
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

    x_idx = list(range(d.height))

    # Calculer la série : cumul dans chaque streak
    outcome_col = d["outcome"]
    is_win = (outcome_col == 2).cast(pl.Int64)
    new_streak = (outcome_col != outcome_col.shift(1)).fill_null(True)
    streak_group = new_streak.cast(pl.Int64).cum_sum()

    streak_counter: list[int] = []
    prev_group = -1
    count = 0
    for g in streak_group.to_list():
        if g != prev_group:
            count = 1
            prev_group = g
        else:
            count += 1
        streak_counter.append(count)

    is_win_list = is_win.to_list()
    streak_values = [c if w == 1 else -c for c, w in zip(streak_counter, is_win_list, strict=False)]

    bar_colors = [colors["green"] if v > 0 else colors["red"] for v in streak_values]

    labels = d["start_time"].dt.strftime("%m-%d %H:%M").to_list()
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
    df: DataFrameLike,
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
    d = _normalize_df(df)
    colors = HALO_COLORS.as_dict()

    d = d.sort("start_time")
    x_idx = list(range(d.height))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").to_list()
    step = max(1, len(labels) // 10) if labels else 1

    fig = go.Figure()

    if "damage_dealt" in d.columns:
        dealt = d["damage_dealt"].cast(pl.Float64, strict=False).fill_null(0)
        fig.add_trace(
            go.Bar(
                x=x_idx,
                y=dealt.to_list(),
                name="Dégâts infligés",
                marker_color=colors["cyan"],
                opacity=0.80,
                hovertemplate="infligés=%{y:.0f}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_idx,
                y=_rolling_mean(dealt, window=10).to_list(),
                mode="lines",
                name="Moy. infligés",
                line={"width": PLOT_CONFIG.line_width, "color": colors["cyan"]},
                hovertemplate="moy=%{y:.0f}<extra></extra>",
            )
        )

    if "damage_taken" in d.columns:
        taken = d["damage_taken"].cast(pl.Float64, strict=False).fill_null(0)
        fig.add_trace(
            go.Bar(
                x=x_idx,
                y=taken.to_list(),
                name="Dégâts subis",
                marker_color=colors["red"],
                opacity=0.65,
                hovertemplate="subis=%{y:.0f}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_idx,
                y=_rolling_mean(taken, window=10).to_list(),
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
    df: DataFrameLike,
    title: str = "Tirs et précision",
) -> go.Figure:
    """Graphique des tirs (tirés/touchés) en barres groupées avec courbe de précision.

    Args:
        df: DataFrame avec colonnes shots_fired, shots_hit, accuracy, start_time.
        title: Titre du graphique.

    Returns:
        Figure Plotly avec axe Y secondaire pour la précision.
    """
    d = _normalize_df(df)
    colors = HALO_COLORS.as_dict()

    d = d.sort("start_time")
    x_idx = list(range(d.height))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").to_list()
    step = max(1, len(labels) // 10) if labels else 1

    fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])

    if "shots_fired" in d.columns:
        fired = d["shots_fired"].cast(pl.Float64, strict=False).fill_null(0)
        fig.add_trace(
            go.Bar(
                x=x_idx,
                y=fired.to_list(),
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
        hit = d["shots_hit"].cast(pl.Float64, strict=False).fill_null(0)
        fig.add_trace(
            go.Bar(
                x=x_idx,
                y=hit.to_list(),
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
        accuracy = d["accuracy"].cast(pl.Float64, strict=False)
        fig.add_trace(
            go.Scatter(
                x=x_idx,
                y=accuracy.to_list(),
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
    df: DataFrameLike,
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
    d = _normalize_df(df)
    colors = HALO_COLORS.as_dict()

    d = d.sort("start_time")
    x_idx = list(range(d.height))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").to_list()
    step = max(1, len(labels) // 10) if labels else 1

    fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])

    if "personal_score" in d.columns:
        score = d["personal_score"].cast(pl.Float64, strict=False).fill_null(0)
        fig.add_trace(
            go.Bar(
                x=x_idx,
                y=score.to_list(),
                name="Score personnel",
                marker_color=colors["amber"],
                opacity=0.75,
                hovertemplate="score=%{y:.0f}<extra></extra>",
            ),
            secondary_y=False,
        )

    if "rank" in d.columns:
        rank = d["rank"].cast(pl.Float64, strict=False)
        fig.add_trace(
            go.Scatter(
                x=x_idx,
                y=rank.to_list(),
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
