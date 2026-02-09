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
            line={"width": 3, "color": smooth_color},
            hovertemplate="moyenne=%{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 40, "b": 90},
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

    # Vérifier si match_id est disponible dans tous les DataFrames non-vides
    has_match_id = True
    for _, df_ in series:
        if df_ is not None and not df_.empty and "match_id" not in df_.columns:
            has_match_id = False
            break

    prepared: list[tuple[str, pd.DataFrame]] = []
    all_match_data: list[pd.DataFrame] = []  # Pour construire l'axe X commun

    for name, df_ in series:
        if df_ is None or df_.empty:
            continue
        if metric_col not in df_.columns or "start_time" not in df_.columns:
            continue

        cols_to_use = ["start_time", metric_col]
        if has_match_id:
            cols_to_use.append("match_id")

        d = df_[cols_to_use].copy()
        d["start_time"] = pd.to_datetime(d["start_time"], errors="coerce")
        d = d.dropna(subset=["start_time"]).sort_values("start_time").reset_index(drop=True)
        if d.empty:
            continue

        prepared.append((str(name), d))

        # Collecter les données pour l'axe X commun (vectorisé)
        if has_match_id:
            match_df = d[["match_id", "start_time"]].copy()
            match_df["match_id"] = match_df["match_id"].astype(str)
        else:
            match_df = d[["start_time"]].copy()
            match_df["match_id"] = match_df["start_time"].dt.strftime("%Y-%m-%dT%H:%M:%S")
        all_match_data.append(match_df)

    if not prepared or not all_match_data:
        return None

    # Construire l'axe X commun (vectorisé)
    combined = pd.concat(all_match_data, ignore_index=True)
    # Garder le premier start_time par match_id (le plus ancien)
    match_times = combined.groupby("match_id")["start_time"].min().reset_index()
    match_times = match_times.sort_values("start_time").reset_index(drop=True)

    match_ids_ordered = match_times["match_id"].tolist()
    idx_map = {mid: i for i, mid in enumerate(match_ids_ordered)}

    # Labels pour l'axe X (dates)
    labels = match_times["start_time"].dt.strftime("%d/%m %H:%M").tolist()
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

        # Mapper vers l'axe X commun via match_id (vectorisé)
        if has_match_id:
            d2["_match_key"] = d2["match_id"].astype(str)
        else:
            d2["_match_key"] = d2["start_time"].dt.strftime("%Y-%m-%dT%H:%M:%S")

        d2["_x"] = d2["_match_key"].map(idx_map)
        valid_mask = d2["_x"].notna()
        d2 = d2.loc[valid_mask].copy()
        y2 = y2.loc[valid_mask]

        # Calculer la moyenne lissée sur les valeurs dans l'ordre chronologique
        # (d2 est déjà trié par start_time, donc y2 est dans l'ordre chronologique)
        if bool(show_smooth_lines):
            smooth_chrono = (
                y2.rolling(window=max(1, w), min_periods=1).mean() if w and w > 1 else y2
            )
        else:
            smooth_chrono = None

        # Trier par indices X pour garantir l'ordre correct (évite les boucles visuelles)
        # Créer un DataFrame temporaire pour trier ensemble x, y2 et smooth
        temp_df = pd.DataFrame(
            {
                "_x": d2["_x"].astype(int),
                "y": y2.values,
            }
        )
        if smooth_chrono is not None:
            temp_df["smooth"] = smooth_chrono.values
        temp_df = temp_df.sort_values("_x").reset_index(drop=True)

        x = temp_df["_x"].tolist()
        y2_sorted = temp_df["y"].tolist()

        if not x:
            continue

        fig.add_trace(
            go.Bar(
                x=x,
                y=y2_sorted,
                name=name,
                marker_color=color,
                opacity=0.70,
                hovertemplate=f"{name}<br>{hover_label}=%{{y}}<extra></extra>",
                legendgroup=name,
            )
        )

        if bool(show_smooth_lines) and smooth_chrono is not None:
            smooth_sorted = temp_df["smooth"].tolist()

            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=smooth_sorted,
                    mode="lines",
                    name=f"{name} — moyenne lissée",
                    line={"width": 3, "color": color},
                    opacity=0.95,
                    hovertemplate=f"{name}<br>moyenne=%{{y:.2f}}<extra></extra>",
                    legendgroup=name,
                )
            )

    if not fig.data:
        return None

    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 20, "t": 40, "b": 90},
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
