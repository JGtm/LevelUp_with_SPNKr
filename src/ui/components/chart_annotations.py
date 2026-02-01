"""Annotations pour les graphiques Plotly.

Ajoute des étiquettes sur les valeurs extrêmes (min/max).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go


def add_extreme_annotations(
    fig: go.Figure,
    x_values: list[Any],
    y_values: list[float],
    *,
    metric_name: str = "",
    show_max: bool = True,
    show_min: bool = False,
    max_color: str = "#00FF00",
    min_color: str = "#FF4444",
    yshift_max: int = 15,
    yshift_min: int = -15,
    font_size: int = 10,
    secondary_y: bool = False,
) -> go.Figure:
    """Ajoute des annotations sur les valeurs extrêmes d'une série.

    Args:
        fig: Figure Plotly à modifier.
        x_values: Valeurs de l'axe X.
        y_values: Valeurs de l'axe Y.
        metric_name: Nom de la métrique (pour le label).
        show_max: Afficher l'annotation sur le max.
        show_min: Afficher l'annotation sur le min.
        max_color: Couleur de l'annotation max.
        min_color: Couleur de l'annotation min.
        yshift_max: Décalage vertical du label max.
        yshift_min: Décalage vertical du label min.
        font_size: Taille de police.
        secondary_y: Si True, utilise l'axe Y secondaire.

    Returns:
        Figure modifiée.
    """
    if not x_values or not y_values or len(x_values) != len(y_values):
        return fig

    # Convertir en listes si nécessaire
    if isinstance(y_values, pd.Series):
        y_values = y_values.tolist()
    if isinstance(x_values, pd.Series):
        x_values = x_values.tolist()

    # Filtrer les NaN
    valid_pairs = [
        (x, y)
        for x, y in zip(x_values, y_values, strict=False)
        if y is not None and y == y  # y == y exclut NaN
    ]

    if not valid_pairs:
        return fig

    x_valid, y_valid = zip(*valid_pairs, strict=False)

    if show_max:
        max_idx = y_valid.index(max(y_valid))
        max_x = x_valid[max_idx]
        max_y = y_valid[max_idx]

        label = f"{max_y:.1f}" if isinstance(max_y, float) else str(max_y)
        if metric_name:
            label = f"{label}"

        fig.add_annotation(
            x=max_x,
            y=max_y,
            text=f"▲ {label}",
            showarrow=False,
            yshift=yshift_max,
            font=dict(size=font_size, color=max_color),
            bgcolor="rgba(0,0,0,0.5)",
            borderpad=2,
            yref="y2" if secondary_y else "y",
        )

    if show_min:
        min_idx = y_valid.index(min(y_valid))
        min_x = x_valid[min_idx]
        min_y = y_valid[min_idx]

        label = f"{min_y:.1f}" if isinstance(min_y, float) else str(min_y)

        fig.add_annotation(
            x=min_x,
            y=min_y,
            text=f"▼ {label}",
            showarrow=False,
            yshift=yshift_min,
            font=dict(size=font_size, color=min_color),
            bgcolor="rgba(0,0,0,0.5)",
            borderpad=2,
            yref="y2" if secondary_y else "y",
        )

    return fig


def annotate_timeseries_extremes(
    fig: go.Figure,
    df: pd.DataFrame,
    *,
    x_col: str = "idx",
    metrics: list[dict[str, Any]] | None = None,
) -> go.Figure:
    """Ajoute des annotations d'extrêmes sur un graphique de séries temporelles.

    Args:
        fig: Figure Plotly.
        df: DataFrame avec les données.
        x_col: Colonne pour l'axe X (ou "idx" pour utiliser l'index).
        metrics: Liste de dicts définissant les métriques à annoter:
            [
                {"col": "ratio", "show_max": True, "show_min": True, "secondary_y": True},
                {"col": "kills", "show_max": True, "show_min": False},
            ]

    Returns:
        Figure modifiée.
    """
    if metrics is None:
        metrics = [
            {
                "col": "ratio",
                "show_max": True,
                "show_min": False,
                "secondary_y": True,
                "max_color": "#FFD700",
            },
        ]

    if df is None or df.empty:
        return fig

    if x_col == "idx":
        x_values = list(range(len(df)))
    else:
        x_values = df[x_col].tolist() if x_col in df.columns else list(range(len(df)))

    for metric in metrics:
        col = metric.get("col", "")
        if col not in df.columns:
            continue

        y_values = df[col].tolist()

        add_extreme_annotations(
            fig,
            x_values,
            y_values,
            metric_name=col,
            show_max=metric.get("show_max", True),
            show_min=metric.get("show_min", False),
            max_color=metric.get("max_color", "#00FF00"),
            min_color=metric.get("min_color", "#FF4444"),
            secondary_y=metric.get("secondary_y", False),
        )

    return fig


__all__ = [
    "add_extreme_annotations",
    "annotate_timeseries_extremes",
]
