"""Graphiques pour la comparaison trio (3 joueurs)."""

import plotly.graph_objects as go
import polars as pl

from src.config import HALO_COLORS, PLOT_CONFIG
from src.visualization._compat import DataFrameLike, ensure_polars
from src.visualization.theme import apply_halo_plot_style, get_legend_horizontal_bottom


def plot_trio_metric(
    d_self: DataFrameLike,
    d_f1: DataFrameLike,
    d_f2: DataFrameLike,
    *,
    metric: str,
    names: tuple[str, str, str],
    title: str,
    y_title: str,
    y_suffix: str = "",
    y_format: str = "",
    smooth_window: int = 7,
) -> go.Figure:
    """Graphique comparant une métrique entre 3 joueurs.

    Les 3 DataFrames doivent être alignés sur les mêmes matchs.

    Args:
        d_self: DataFrame du joueur principal.
        d_f1: DataFrame du premier ami.
        d_f2: DataFrame du deuxième ami.
        metric: Nom de la colonne à comparer.
        names: Tuple des 3 noms (self, ami1, ami2).
        title: Titre du graphique.
        y_title: Titre de l'axe Y.
        y_suffix: Suffixe pour les valeurs Y (ex: "%").
        y_format: Format pour le hover (ex: ".2f").

    Returns:
        Figure Plotly.
    """
    colors = HALO_COLORS.as_dict()
    color_list = [colors["cyan"], colors["red"], colors["green"]]

    # Normaliser les entrées en Polars
    d_self_pl = ensure_polars(d_self)
    d_f1_pl = ensure_polars(d_f1)
    d_f2_pl = ensure_polars(d_f2)

    def _prep(df: pl.DataFrame, alias: str) -> pl.DataFrame:
        """Prépare un DataFrame : sélection, cast datetime, tri."""
        if df is None or df.is_empty():
            return pl.DataFrame(schema={"start_time": pl.Datetime, alias: pl.Float64})
        out = df.select(["start_time", metric])
        # Cast start_time en Datetime si nécessaire
        if not out.schema["start_time"].is_temporal():
            out = out.with_columns(pl.col("start_time").str.to_datetime(strict=False))
        out = out.drop_nulls(subset=["start_time"]).sort("start_time").rename({metric: alias})
        return out

    a0 = _prep(d_self_pl, "v0")
    a1 = _prep(d_f1_pl, "v1")
    a2 = _prep(d_f2_pl, "v2")

    # Aligne sur l'intersection des timestamps (les DFs sont censés être alignés, mais on reste robuste).
    aligned = a0.join(a1, on="start_time", how="inner").join(a2, on="start_time", how="inner")

    fig = go.Figure()
    if aligned.is_empty():
        fig.update_layout(title=title)
        return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)

    def _roll(s: pl.Series) -> list:
        """Moyenne glissante, retourne une liste pour Plotly."""
        w = int(smooth_window) if smooth_window else 0
        if w <= 1:
            return s.to_list()
        return s.rolling_mean(window_size=w, min_samples=1).to_list()

    # Formatage des dates pour ticktext
    ticktext = aligned["start_time"].dt.strftime("%d/%m").fill_null("").to_list()
    xs = list(range(len(aligned)))

    col_names = ["v0", "v1", "v2"]
    series_lists = [aligned[col].to_list() for col in col_names]
    series_cols = [aligned[col] for col in col_names]

    # Moyenne horizontale des 3 séries
    avg_all = aligned.select(pl.mean_horizontal("v0", "v1", "v2")).to_series()

    for _idx, (s_list, s_col, name, color) in enumerate(
        zip(series_lists, series_cols, names, color_list, strict=False)
    ):
        hover_format = f"%{{customdata}}<br>%{{y{':' + y_format if y_format else ''}}}{y_suffix}<extra></extra>"
        fig.add_trace(
            go.Bar(
                x=xs,
                y=s_list,
                name=f"{name} (match)",
                marker_color=color,
                opacity=0.32,
                customdata=ticktext,
                hovertemplate=hover_format,
            )
        )

        fig.add_trace(
            go.Scatter(
                x=xs,
                y=_roll(s_col),
                mode="lines",
                name=f"{name} (moy. lissée)",
                line={"width": 3, "color": color},
                customdata=ticktext,
                hovertemplate=hover_format,
            )
        )

    # Moyenne lissée des 3 (pointillés)
    avg_color = colors.get("amber", "rgba(255, 255, 255, 0.85)")
    hover_format_avg = (
        f"%{{customdata}}<br>%{{y{':' + y_format if y_format else ''}}}{y_suffix}<extra></extra>"
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=_roll(avg_all),
            mode="lines",
            name="Moyenne (3) lissée",
            line={"width": 3, "color": avg_color, "dash": "dot"},
            customdata=ticktext,
            hovertemplate=hover_format_avg,
        )
    )

    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        hovermode="x unified",
        legend=get_legend_horizontal_bottom(),
        barmode="group",
    )
    fig.update_xaxes(tickmode="array", tickvals=xs, ticktext=ticktext, title_text="")
    fig.update_yaxes(title_text=y_title)

    if y_suffix:
        fig.update_yaxes(ticksuffix=y_suffix)

    return apply_halo_plot_style(fig, title=title, height=PLOT_CONFIG.default_height)
