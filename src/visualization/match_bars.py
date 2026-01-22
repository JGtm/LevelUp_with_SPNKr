"""Graphiques en barres pour les métriques par match.

Ce module contient les fonctions pour afficher des graphiques
en barres chronologiques des statistiques de match.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import plotly.graph_objects as go

from src.visualization.theme import apply_halo_plot_style, get_legend_horizontal_bottom

if TYPE_CHECKING:
    pass


def plot_metric_bars_by_match(
    df_: pd.DataFrame,
    *,
    metric_col: str,
    title: str,
    y_axis_title: str,
    hover_label: str,
    bar_color: str,
    smooth_color: str,
    smooth_window: int = 10,
) -> go.Figure | None:
    """Graphique en barres d'une métrique par match avec courbe de moyenne lissée.
    
    Args:
        df_: DataFrame avec colonnes 'start_time' et la métrique.
        metric_col: Nom de la colonne de métrique.
        title: Titre du graphique.
        y_axis_title: Titre de l'axe Y.
        hover_label: Label pour le hover.
        bar_color: Couleur des barres.
        smooth_color: Couleur de la courbe lissée.
        smooth_window: Fenêtre de lissage (défaut: 10).
        
    Returns:
        Figure Plotly ou None si données insuffisantes.
    """
    if df_ is None or df_.empty:
        return None
    if metric_col not in df_.columns or "start_time" not in df_.columns:
        return None

    d = df_[["start_time", metric_col]].copy()
    d["start_time"] = pd.to_datetime(d["start_time"], errors="coerce")
    d = d.dropna(subset=["start_time"]).sort_values("start_time").reset_index(drop=True)
    if d.empty:
        return None

    y = pd.to_numeric(d[metric_col], errors="coerce")
    x_idx = list(range(len(d)))
    labels = d["start_time"].dt.strftime("%m-%d %H:%M").tolist()
    step = max(1, len(labels) // 10) if labels else 1

    w = int(smooth_window) if smooth_window else 0
    smooth = y.rolling(window=max(1, w), min_periods=1).mean() if w and w > 1 else y

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x_idx,
            y=y,
            name=y_axis_title,
            marker_color=bar_color,
            opacity=0.70,
            hovertemplate=f"{hover_label}=%{{y}}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x_idx,
            y=smooth,
            mode="lines",
            name="Moyenne (lissée)",
            line=dict(width=3, color=smooth_color),
            hovertemplate="moyenne=%{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        margin=dict(l=40, r=20, t=40, b=90),
        hovermode="x unified",
        legend=get_legend_horizontal_bottom(),
    )
    fig.update_yaxes(title_text=y_axis_title, rangemode="tozero")
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=x_idx[::step],
        ticktext=labels[::step],
        type="category",
    )

    return apply_halo_plot_style(fig, height=320)


def plot_multi_metric_bars_by_match(
    series: list[tuple[str, pd.DataFrame]],
    *,
    metric_col: str,
    title: str,
    y_axis_title: str,
    hover_label: str,
    colors: dict[str, str] | list[str] | None,
    smooth_window: int = 10,
    show_smooth_lines: bool = True,
) -> go.Figure | None:
    """Graphique en barres multi-joueurs d'une métrique par match.
    
    Args:
        series: Liste de tuples (nom, DataFrame).
        metric_col: Nom de la colonne de métrique.
        title: Titre du graphique.
        y_axis_title: Titre de l'axe Y.
        hover_label: Label pour le hover.
        colors: Dict ou liste de couleurs par joueur.
        smooth_window: Fenêtre de lissage (défaut: 10).
        show_smooth_lines: Afficher les courbes lissées.
        
    Returns:
        Figure Plotly ou None si données insuffisantes.
    """
    if not series:
        return None

    prepared: list[tuple[str, pd.DataFrame]] = []
    all_times: list[pd.Timestamp] = []
    for name, df_ in series:
        if df_ is None or df_.empty:
            continue
        if metric_col not in df_.columns or "start_time" not in df_.columns:
            continue
        d = df_[["start_time", metric_col]].copy()
        d["start_time"] = pd.to_datetime(d["start_time"], errors="coerce")
        d = d.dropna(subset=["start_time"]).sort_values("start_time").reset_index(drop=True)
        if d.empty:
            continue
        prepared.append((str(name), d))
        all_times.extend(d["start_time"].tolist())

    if not prepared or not all_times:
        return None

    # Axe X commun (timeline de tous les joueurs)
    uniq = pd.Series(all_times).dropna().drop_duplicates().sort_values()
    times = uniq.tolist()
    idx_map = {t: i for i, t in enumerate(times)}
    labels = [pd.to_datetime(t).strftime("%d/%m %H:%M") for t in times]
    step = max(1, len(labels) // 10) if labels else 1

    fig = go.Figure()
    w = int(smooth_window) if smooth_window else 0
    for i, (name, d) in enumerate(prepared):
        if isinstance(colors, dict):
            color = colors.get(name) or "#35D0FF"
        elif isinstance(colors, list) and colors:
            color = colors[i % len(colors)]
        else:
            color = "#35D0FF"
        y = pd.to_numeric(d[metric_col], errors="coerce")
        mask = y.notna()
        d2 = d.loc[mask].copy()
        if d2.empty:
            continue
        y2 = pd.to_numeric(d2[metric_col], errors="coerce")
        x = [idx_map.get(t) for t in d2["start_time"].tolist()]
        x = [xi for xi in x if xi is not None]
        if not x:
            continue

        fig.add_trace(
            go.Bar(
                x=x,
                y=y2,
                name=name,
                marker_color=color,
                opacity=0.70,
                hovertemplate=f"{name}<br>{hover_label}=%{{y}}<extra></extra>",
                legendgroup=name,
            )
        )

        if bool(show_smooth_lines):
            smooth = y2.rolling(window=max(1, w), min_periods=1).mean() if w and w > 1 else y2
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=smooth,
                    mode="lines",
                    name=f"{name} — moyenne lissée",
                    line=dict(width=3, color=color),
                    opacity=0.95,
                    hovertemplate=f"{name}<br>moyenne=%{{y:.2f}}<extra></extra>",
                    legendgroup=name,
                )
            )

    if not fig.data:
        return None

    fig.update_layout(
        title=title,
        margin=dict(l=40, r=20, t=40, b=90),
        hovermode="x unified",
        legend=get_legend_horizontal_bottom(),
        barmode="group",
    )
    fig.update_yaxes(title_text=y_axis_title, rangemode="tozero")
    fig.update_xaxes(
        title_text="Match (chronologique)",
        tickmode="array",
        tickvals=list(range(len(labels)))[::step],
        ticktext=labels[::step],
        type="category",
    )

    return apply_halo_plot_style(fig, height=320)
