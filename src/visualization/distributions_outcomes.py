"""Graphiques liés aux résultats (victoires/défaites/heatmap/top).

Extrait de distributions.py (Sprint 16 – refactoring).
"""

from __future__ import annotations

from datetime import timedelta

import plotly.graph_objects as go
import polars as pl

from src.config import HALO_COLORS, OUTCOME_CODES, PLOT_CONFIG, SESSION_CONFIG
from src.visualization._compat import DataFrameLike, ensure_polars
from src.visualization.theme import (
    apply_halo_plot_style,
    get_legend_horizontal_bottom,
)

# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------


def _ensure_datetime(df: pl.DataFrame, col: str) -> pl.DataFrame:
    """Convertit *col* en Datetime si nécessaire (tolérance String)."""
    dtype = df.schema[col]
    if dtype == pl.String:
        return df.with_columns(pl.col(col).str.to_datetime(strict=False))
    return df


def _safe_col(df: pl.DataFrame, col_name: str, default: int = 0) -> list:
    """Retourne la colonne *col_name* en liste, ou une liste de *default*."""
    if col_name in df.columns:
        return df[col_name].to_list()
    return [default] * df.height


# ---------------------------------------------------------------------------
# plot_outcomes_over_time  (ex-134L → orchestrateur + helper)
# ---------------------------------------------------------------------------


def _compute_outcome_buckets(d: pl.DataFrame, *, session_style: bool) -> tuple[pl.DataFrame, str]:
    """Détermine le bucket temporel et retourne (df_avec_bucket, bucket_label)."""
    if session_style:
        d = d.sort("start_time")
        if d.height <= 20:
            d = d.with_row_index("bucket").with_columns((pl.col("bucket") + 1).cast(pl.Int64))
            return d, "partie"
        d = _ensure_datetime(d, "start_time")
        d = d.with_columns(pl.col("start_time").dt.truncate("1h").alias("bucket"))
        return d, "heure"

    d = _ensure_datetime(d, "start_time")
    ts = d["start_time"].drop_nulls()
    tmin = ts.min() if ts.len() > 0 else None
    tmax = ts.max() if ts.len() > 0 else None

    dt_range = tmax - tmin if tmin is not None and tmax is not None else timedelta(days=999)
    days = dt_range.total_seconds() / 86400.0

    cfg = SESSION_CONFIG
    if days < cfg.bucket_threshold_hourly:
        d = d.sort("start_time")
        d = d.with_row_index("bucket").with_columns((pl.col("bucket") + 1).cast(pl.Int64))
        return d, "partie"
    if days <= cfg.bucket_threshold_daily:
        d = d.with_columns(pl.col("start_time").dt.truncate("1h").alias("bucket"))
        return d, "heure"
    if days <= cfg.bucket_threshold_weekly:
        d = d.with_columns(pl.col("start_time").dt.strftime("%Y-%m-%d").alias("bucket"))
        return d, "jour"
    if days <= cfg.bucket_threshold_monthly:
        d = d.with_columns(
            pl.col("start_time").dt.truncate("1w").dt.strftime("%Y-%m-%d").alias("bucket")
        )
        return d, "semaine"
    d = d.with_columns(pl.col("start_time").dt.strftime("%Y-%m").alias("bucket"))
    return d, "mois"


def plot_outcomes_over_time(
    df: DataFrameLike, *, session_style: bool = False
) -> tuple[go.Figure, str]:
    """Graphique d'évolution des victoires/défaites dans le temps.

    Returns:
        Tuple (figure, bucket_label).
    """
    d = ensure_polars(df)
    colors = HALO_COLORS.as_dict()
    d = d.drop_nulls(subset=["outcome"])

    if d.is_empty():
        fig = go.Figure()
        fig.update_layout(
            height=PLOT_CONFIG.default_height, margin={"l": 40, "r": 20, "t": 30, "b": 40}
        )
        fig.update_yaxes(title_text="Nombre")
        return apply_halo_plot_style(fig, height=PLOT_CONFIG.default_height), "période"

    d, bucket_label = _compute_outcome_buckets(d, session_style=session_style)

    # Pivot : bucket × outcome → count
    pivot = (
        d.group_by("bucket", "outcome")
        .agg(pl.col("match_id").count().alias("count"))
        .pivot(on="outcome", index="bucket", values="count")
        .fill_null(0)
        .sort("bucket")
    )

    # Extraire les séries par code outcome (colonnes nommées en str)
    buckets = pivot["bucket"].to_list()
    wins = _safe_col(pivot, str(OUTCOME_CODES.WIN))
    losses = _safe_col(pivot, str(OUTCOME_CODES.LOSS))
    ties = _safe_col(pivot, str(OUTCOME_CODES.TIE))
    nofin = _safe_col(pivot, str(OUTCOME_CODES.NO_FINISH))
    losses_neg = [-v for v in losses]

    fig = go.Figure()
    fig.add_bar(
        x=buckets,
        y=wins,
        name="Victoires",
        marker_color=colors["green"],
        hovertemplate="%{x}<br>Victoires: %{y}<extra></extra>",
    )
    fig.add_bar(
        x=buckets,
        y=losses_neg,
        name="Défaites",
        marker_color=colors["red"],
        customdata=losses,
        hovertemplate="%{x}<br>Défaites: %{customdata}<extra></extra>",
    )

    if sum(ties) > 0:
        fig.add_bar(
            x=buckets,
            y=ties,
            name="Égalités",
            marker_color=colors["violet"],
            hovertemplate="%{x}<br>Égalités: %{y}<extra></extra>",
        )
    if sum(nofin) > 0:
        fig.add_bar(
            x=buckets,
            y=nofin,
            name="Non terminés",
            marker_color=colors["violet"],
            hovertemplate="%{x}<br>Non terminés: %{y}<extra></extra>",
        )

    fig.update_layout(
        barmode="relative",
        height=PLOT_CONFIG.default_height,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
    )
    fig.update_yaxes(title_text="Nombre", zeroline=True)

    if bucket_label == "partie" and len(buckets) > 30:
        fig.update_xaxes(showticklabels=False, title_text="")

    return apply_halo_plot_style(fig, height=PLOT_CONFIG.default_height), bucket_label


# ---------------------------------------------------------------------------
# plot_stacked_outcomes_by_category  (ex-150L → orchestrateur + helper)
# ---------------------------------------------------------------------------


def _build_outcome_pivot(
    d: pl.DataFrame,
    category_col: str,
    min_matches: int,
    sort_by: str,
    max_categories: int,
) -> pl.DataFrame | None:
    """Construit le pivot agrégé par catégorie. Retourne None si vide."""
    pivot = (
        d.group_by(category_col, "outcome")
        .agg(pl.col("match_id").count().alias("count"))
        .pivot(on="outcome", index=category_col, values="count")
        .fill_null(0)
    )

    # Mapper les codes outcome → noms lisibles
    outcome_map = {
        str(OUTCOME_CODES.WIN): "wins",
        str(OUTCOME_CODES.LOSS): "losses",
        str(OUTCOME_CODES.TIE): "ties",
        str(OUTCOME_CODES.NO_FINISH): "left",
    }
    for code_str, name in outcome_map.items():
        if code_str in pivot.columns:
            pivot = pivot.rename({code_str: name})
        else:
            pivot = pivot.with_columns(pl.lit(0).alias(name))

    # Garder uniquement les colonnes nécessaires
    keep = {category_col, "wins", "losses", "ties", "left"}
    pivot = pivot.select([c for c in pivot.columns if c in keep])

    pivot = pivot.with_columns(
        (pl.col("wins") + pl.col("losses") + pl.col("ties") + pl.col("left")).alias("total"),
    ).with_columns(
        (pl.col("wins").cast(pl.Float64) / pl.col("total")).fill_null(0.0).alias("win_rate"),
    )

    pivot = pivot.filter(pl.col("total") >= min_matches)
    if pivot.is_empty():
        return None
    if sort_by == "win_rate":
        pivot = pivot.sort("win_rate", descending=True)
    elif sort_by == "name":
        pivot = pivot.sort(category_col)
    else:
        pivot = pivot.sort("total", descending=True)
    return pivot.head(max_categories)


def _add_outcome_traces(
    fig: go.Figure,
    pivot: pl.DataFrame,
    colors: dict,
    *,
    category_col: str,
) -> None:
    """Ajoute les traces Victoires / Défaites / Égalités / Non terminés."""
    cats = pivot[category_col].to_list()
    fig.add_trace(
        go.Bar(
            x=cats,
            y=pivot["wins"].to_list(),
            name="Victoires",
            marker_color=colors["green"],
            opacity=0.85,
            text=pivot["wins"].to_list(),
            textposition="inside",
            hovertemplate="%{x}<br>Victoires: %{y}<br>Win Rate: %{customdata:.1%}<extra></extra>",
            customdata=pivot["win_rate"].to_list(),
        )
    )
    fig.add_trace(
        go.Bar(
            x=cats,
            y=pivot["losses"].to_list(),
            name="Défaites",
            marker_color=colors["red"],
            opacity=0.75,
            text=pivot["losses"].to_list(),
            textposition="inside",
            hovertemplate="%{x}<br>Défaites: %{y}<extra></extra>",
        )
    )
    if pivot["ties"].sum() > 0:
        text_ties = (
            pivot.select(
                pl.when(pl.col("ties") > 0)
                .then(pl.col("ties").cast(pl.String))
                .otherwise(pl.lit(""))
            )
            .to_series()
            .to_list()
        )
        fig.add_trace(
            go.Bar(
                x=cats,
                y=pivot["ties"].to_list(),
                name="Égalités",
                marker_color=colors["amber"],
                opacity=0.70,
                text=text_ties,
                textposition="inside",
                hovertemplate="%{x}<br>Égalités: %{y}<extra></extra>",
            )
        )
    if pivot["left"].sum() > 0:
        text_left = (
            pivot.select(
                pl.when(pl.col("left") > 0)
                .then(pl.col("left").cast(pl.String))
                .otherwise(pl.lit(""))
            )
            .to_series()
            .to_list()
        )
        fig.add_trace(
            go.Bar(
                x=cats,
                y=pivot["left"].to_list(),
                name="Non terminés",
                marker_color=colors["violet"],
                opacity=0.60,
                text=text_left,
                textposition="inside",
                hovertemplate="%{x}<br>Non terminés: %{y}<extra></extra>",
            )
        )


def plot_stacked_outcomes_by_category(
    df: DataFrameLike,
    category_col: str,
    *,
    title: str | None = None,
    min_matches: int = 1,
    sort_by: str = "total",
    max_categories: int = 20,
) -> go.Figure:
    """Graphique de colonnes empilées Win/Loss/Tie/Left par catégorie."""
    d = ensure_polars(df)
    colors = HALO_COLORS.as_dict()
    d = d.drop_nulls(subset=[category_col, "outcome"])

    if d.is_empty():
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    pivot = _build_outcome_pivot(d, category_col, min_matches, sort_by, max_categories)
    if pivot is None:
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    fig = go.Figure()
    _add_outcome_traces(fig, pivot, colors, category_col=category_col)

    height = PLOT_CONFIG.tall_height if pivot.height > 10 else PLOT_CONFIG.default_height
    fig.update_layout(
        barmode="stack",
        bargap=0.15,
        height=height,
        margin={"l": 40, "r": 20, "t": 60 if title else 30, "b": 100},
        legend=get_legend_horizontal_bottom(),
    )
    fig.update_xaxes(tickangle=45, title_text="")
    fig.update_yaxes(title_text="Matchs")
    return apply_halo_plot_style(fig, title=title, height=height)


# ---------------------------------------------------------------------------
# plot_win_ratio_heatmap  (98L – OK, déplacé tel quel)
# ---------------------------------------------------------------------------


def plot_win_ratio_heatmap(
    df: DataFrameLike,
    *,
    title: str | None = None,
    min_matches: int = 2,
) -> go.Figure:
    """Heatmap du Win Ratio par jour de la semaine et heure."""
    d = ensure_polars(df)
    colors = HALO_COLORS.as_dict()
    d = d.drop_nulls(subset=["start_time", "outcome"])

    if d.is_empty():
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    d = _ensure_datetime(d, "start_time")
    d = d.drop_nulls(subset=["start_time"])
    d = d.with_columns(
        (pl.col("start_time").dt.weekday() - 1).cast(pl.Int32).alias("day_of_week"),
        pl.col("start_time").dt.hour().cast(pl.Int32).alias("hour"),
        (pl.col("outcome") == OUTCOME_CODES.WIN).cast(pl.Int32).alias("is_win"),
    )

    agg = d.group_by("day_of_week", "hour").agg(
        pl.col("is_win").sum().alias("wins"),
        pl.col("match_id").count().alias("total"),
    )
    agg = agg.with_columns(
        (pl.col("wins").cast(pl.Float64) / pl.col("total")).fill_null(0.0).alias("win_rate"),
    )
    agg = agg.with_columns(
        pl.when(pl.col("total") < min_matches)
        .then(None)
        .otherwise(pl.col("win_rate"))
        .alias("win_rate"),
    )

    # Grille complète 7 jours × 24 heures
    all_hours = list(range(24))
    all_days = list(range(7))
    full_grid = pl.DataFrame(
        {
            "day_of_week": [dow for dow in all_days for _ in all_hours],
            "hour": [h for _ in all_days for h in all_hours],
        }
    ).cast({"day_of_week": pl.Int32, "hour": pl.Int32})

    merged = full_grid.join(agg, on=["day_of_week", "hour"], how="left").sort("day_of_week", "hour")
    merged = merged.with_columns(
        pl.col("total").fill_null(0).cast(pl.Int64),
    )

    # Construire les matrices numpy 7×24
    win_rate_vals = merged["win_rate"].to_numpy().reshape(7, 24)
    count_vals = merged["total"].to_numpy().reshape(7, 24).astype(int)

    day_labels = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    hour_labels = [f"{h:02d}h" for h in all_hours]
    text_matrix = count_vals.astype(str)
    text_matrix[count_vals == 0] = ""

    fig = go.Figure(
        data=go.Heatmap(
            z=win_rate_vals,
            x=hour_labels,
            y=day_labels,
            colorscale=[[0.0, colors["red"]], [0.5, colors["amber"]], [1.0, colors["green"]]],
            zmin=0,
            zmax=1,
            text=text_matrix,
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate="%{y} %{x}<br>Win Rate: %{z:.1%}<br>Matchs: %{text}<extra></extra>",
            colorbar={"title": "Win Rate", "tickformat": ".0%"},
        )
    )
    fig.update_layout(
        height=PLOT_CONFIG.default_height,
        margin={"l": 60, "r": 20, "t": 60 if title else 30, "b": 40},
    )
    fig.update_xaxes(title_text="Heure", side="bottom")
    fig.update_yaxes(title_text="Jour", autorange="reversed")
    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)


# ---------------------------------------------------------------------------
# plot_matches_at_top_by_week  (ex-136L → orchestrateur + helper)
# ---------------------------------------------------------------------------


def _determine_top_period(d: pl.DataFrame) -> tuple[pl.DataFrame, str]:
    """Ajoute une colonne 'period' et retourne (df, period_label)."""
    d = _ensure_datetime(d, "start_time")
    d = d.drop_nulls(subset=["start_time"])
    ts = d["start_time"]
    tmin = ts.min() if ts.len() > 0 else None
    tmax = ts.max() if ts.len() > 0 else None

    dt_range = tmax - tmin if tmin is not None and tmax is not None else timedelta(days=999)
    days = dt_range.total_seconds() / 86400.0

    if days < 2:
        d = d.sort("start_time")
        d = d.with_row_index("period").with_columns(pl.col("period").cast(pl.String))
        return d, "Match"
    if days < 7:
        d = d.with_columns(pl.col("start_time").dt.strftime("%Y-%m-%d").alias("period"))
        return d, "Jour"
    d = d.with_columns(
        pl.col("start_time").dt.truncate("1w").dt.strftime("%Y-%m-%d").alias("period")
    )
    return d, "Semaine"


def plot_matches_at_top_by_week(
    df: DataFrameLike,
    *,
    title: str | None = None,
    rank_col: str = "rank",
    top_n_ranks: int = 1,
) -> go.Figure:
    """Graphique comparant les matchs 'Top' vs Total par période."""
    d = ensure_polars(df)
    colors = HALO_COLORS.as_dict()
    d = d.drop_nulls(subset=["start_time"])

    if d.is_empty():
        fig = go.Figure()
        fig.update_layout(height=PLOT_CONFIG.default_height)
        return apply_halo_plot_style(fig, title=title)

    d, period_label = _determine_top_period(d)

    if rank_col in d.columns:
        d = d.with_columns(
            (pl.col(rank_col).cast(pl.Float64, strict=False).fill_null(99.0) <= top_n_ranks).alias(
                "is_top"
            )
        )
    elif "outcome" in d.columns:
        d = d.with_columns((pl.col("outcome") == OUTCOME_CODES.WIN).alias("is_top"))
    else:
        d = d.with_columns(pl.lit(False).alias("is_top"))

    agg = (
        d.group_by("period")
        .agg(
            pl.col("match_id").count().alias("total"),
            pl.col("is_top").sum().alias("top_count"),
        )
        .sort("period")
    )
    agg = agg.with_columns(
        (pl.col("total") - pl.col("top_count")).alias("other_count"),
        (pl.col("top_count").cast(pl.Float64) / pl.col("total") * 100.0).round(1).alias("top_rate"),
    )

    periods = agg["period"].to_list()
    top_counts = agg["top_count"].to_list()
    other_counts = agg["other_count"].to_list()
    top_rates = agg["top_rate"].to_list()

    text_other = (
        agg.select(
            pl.when(pl.col("other_count") > 0)
            .then(pl.col("other_count").cast(pl.String))
            .otherwise(pl.lit(""))
        )
        .to_series()
        .to_list()
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=periods,
            y=top_counts,
            name=f"Top {top_n_ranks}",
            marker_color=colors["green"],
            opacity=0.85,
            text=top_counts,
            textposition="inside",
            hovertemplate="%{x}<br>Top: %{y}<br>Taux: %{customdata:.1f}%<extra></extra>",
            customdata=top_rates,
        )
    )
    fig.add_trace(
        go.Bar(
            x=periods,
            y=other_counts,
            name="Autres",
            marker_color=colors["slate"],
            opacity=0.55,
            text=text_other,
            textposition="inside",
            hovertemplate="%{x}<br>Autres: %{y}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=periods,
            y=top_rates,
            mode="lines+markers",
            name="Taux Top (%)",
            yaxis="y2",
            line={"color": colors["amber"], "width": 2},
            marker={"size": 6},
            hovertemplate="%{x}<br>Taux Top: %{y:.1f}%<extra></extra>",
        )
    )

    fig.update_layout(
        barmode="stack",
        bargap=0.15,
        height=PLOT_CONFIG.default_height,
        margin={"l": 40, "r": 60, "t": 60 if title else 30, "b": 80},
        legend=get_legend_horizontal_bottom(),
        yaxis2={
            "title": "Taux (%)",
            "overlaying": "y",
            "side": "right",
            "range": [0, 100],
            "showgrid": False,
        },
    )
    fig.update_xaxes(tickangle=45, title_text=period_label)
    fig.update_yaxes(title_text="Matchs")
    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)
