"""Graphiques de participation au match basés sur PersonalScores.

Sprint 8.2 - Visualise la contribution au score :
- Kills, Assists, Objectifs, Véhicules, Pénalités
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import plotly.express as px
import plotly.graph_objects as go

from src.visualization.theme import apply_halo_plot_style

if TYPE_CHECKING:
    import polars as pl


# =============================================================================
# Constantes de couleurs
# =============================================================================

CATEGORY_COLORS: dict[str, str] = {
    "kill": "#FF6B6B",  # Rouge - kills
    "assist": "#4ECDC4",  # Turquoise - assists
    "objective": "#45B7D1",  # Bleu - objectifs
    "vehicle": "#96CEB4",  # Vert - véhicules
    "penalty": "#2C3E50",  # Gris foncé - pénalités
    "other": "#95A5A6",  # Gris - autre
}

CATEGORY_LABELS: dict[str, str] = {
    "kill": "Frags",
    "assist": "Assists",
    "objective": "Objectifs",
    "vehicle": "Véhicules",
    "penalty": "Pénalités",
    "other": "Autre",
}


def get_participation_colors() -> dict[str, str]:
    """Retourne le mapping couleur par catégorie."""
    return CATEGORY_COLORS.copy()


# =============================================================================
# Graphique Pie : Répartition du score par catégorie
# =============================================================================


def plot_participation_pie(
    df: pl.DataFrame,
    *,
    title: str = "Répartition du score",
    show_values: bool = True,
) -> go.Figure:
    """Pie chart de la contribution au score par catégorie.

    Args:
        df: DataFrame avec colonnes award_category, award_score.
        title: Titre du graphique.
        show_values: Afficher les valeurs absolues.

    Returns:
        Figure Plotly.
    """
    import polars as pl

    # Agréger par catégorie
    agg = (
        df.group_by("award_category")
        .agg(pl.col("award_score").sum().alias("total_score"))
        .sort("total_score", descending=True)
    )

    # Convertir en pandas pour Plotly
    pdf = agg.to_pandas()

    # Mapper les labels et couleurs
    pdf["label"] = pdf["award_category"].map(
        lambda x: CATEGORY_LABELS.get(x, x.capitalize() if x else "Autre")
    )
    pdf["color"] = pdf["award_category"].map(
        lambda x: CATEGORY_COLORS.get(x, CATEGORY_COLORS["other"])
    )

    # Filtrer les valeurs négatives pour le pie (pénalités)
    # On les affiche séparément dans l'annotation
    penalties = pdf[pdf["total_score"] < 0]["total_score"].sum()
    pdf_positive = pdf[pdf["total_score"] > 0].copy()

    fig = go.Figure()

    if not pdf_positive.empty:
        text_info = "percent+value" if show_values else "percent"

        fig.add_trace(
            go.Pie(
                labels=pdf_positive["label"],
                values=pdf_positive["total_score"],
                marker={"colors": pdf_positive["color"].tolist()},
                textinfo=text_info,
                texttemplate="%{label}<br>%{value:,.0f} pts<br>(%{percent})"
                if show_values
                else "%{label}<br>%{percent}",
                hole=0.4,  # Donut chart
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} points<br>%{percent}<extra></extra>",
            )
        )

    # Annotation centrale avec le total
    total_positive = pdf_positive["total_score"].sum()
    total_net = total_positive + penalties

    fig.update_layout(
        title={"text": title, "x": 0.5},
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.1},
        annotations=[
            {
                "text": f"<b>{int(total_net):,}</b><br>points",
                "x": 0.5,
                "y": 0.5,
                "font_size": 18,
                "showarrow": False,
            }
        ],
    )

    # Annotation pénalités si présentes
    if penalties < 0:
        fig.add_annotation(
            text=f"Pénalités: {int(penalties):,} pts",
            xref="paper",
            yref="paper",
            x=0.5,
            y=-0.15,
            showarrow=False,
            font={"size": 12, "color": CATEGORY_COLORS["penalty"]},
        )

    return apply_halo_plot_style(fig)


# =============================================================================
# Graphique Bars : Détail des actions
# =============================================================================


def plot_participation_bars(
    df: pl.DataFrame,
    *,
    title: str = "Détail des actions",
    top_n: int = 10,
    orientation: str = "h",
) -> go.Figure:
    """Bar chart horizontal des actions par type.

    Args:
        df: DataFrame avec colonnes award_name, award_count, award_score, award_category.
        title: Titre du graphique.
        top_n: Nombre d'actions à afficher.
        orientation: "h" horizontal, "v" vertical.

    Returns:
        Figure Plotly.
    """
    import polars as pl

    # Agréger par action
    agg = (
        df.group_by(["award_name", "award_category"])
        .agg(
            pl.col("award_count").sum().alias("count"),
            pl.col("award_score").sum().alias("score"),
        )
        .sort("score", descending=True)
        .head(top_n)
    )

    # Convertir en pandas
    pdf = agg.to_pandas()

    if pdf.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Aucune donnée",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return apply_halo_plot_style(fig)

    # Mapper les couleurs
    pdf["color"] = pdf["award_category"].map(
        lambda x: CATEGORY_COLORS.get(x, CATEGORY_COLORS["other"])
    )

    # Inverser pour afficher du haut vers le bas
    if orientation == "h":
        pdf = pdf.iloc[::-1]

    fig = go.Figure()

    if orientation == "h":
        fig.add_trace(
            go.Bar(
                y=pdf["award_name"],
                x=pdf["score"],
                orientation="h",
                marker={"color": pdf["color"].tolist()},
                text=[
                    f"{int(s):,} pts ({int(c)}x)"
                    for s, c in zip(pdf["score"], pdf["count"], strict=False)
                ],
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Score: %{x:,.0f} pts<extra></extra>",
            )
        )
        fig.update_layout(
            xaxis_title="Points",
            yaxis_title="",
        )
    else:
        fig.add_trace(
            go.Bar(
                x=pdf["award_name"],
                y=pdf["score"],
                marker={"color": pdf["color"].tolist()},
                text=[f"{int(s):,}" for s in pdf["score"]],
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Score: %{y:,.0f} pts<extra></extra>",
            )
        )
        fig.update_layout(
            xaxis_title="",
            yaxis_title="Points",
            xaxis_tickangle=-45,
        )

    fig.update_layout(
        title={"text": title, "x": 0.5},
        showlegend=False,
        margin={"l": 150} if orientation == "h" else {"b": 100},
    )

    return apply_halo_plot_style(fig)


# =============================================================================
# Graphique Stacked Bars : Participation par match
# =============================================================================


def plot_participation_by_match(
    df: pl.DataFrame,
    *,
    title: str = "Participation par match",
    last_n: int = 20,
) -> go.Figure:
    """Stacked bar chart de la participation par match.

    Args:
        df: DataFrame avec colonnes match_id, award_category, award_score.
        title: Titre du graphique.
        last_n: Nombre de matchs à afficher.

    Returns:
        Figure Plotly.
    """
    import polars as pl

    # Agréger par match et catégorie
    agg = df.group_by(["match_id", "award_category"]).agg(
        pl.col("award_score").sum().alias("score")
    )

    # Pivoter pour avoir une colonne par catégorie
    pivoted = agg.pivot(
        index="match_id",
        on="award_category",
        values="score",
    ).fill_null(0)

    # Prendre les derniers matchs
    if pivoted.height > last_n:
        pivoted = pivoted.tail(last_n)

    # Convertir en pandas
    pdf = pivoted.to_pandas()

    fig = go.Figure()

    # Ordre des catégories pour le stacking
    categories_order = ["kill", "assist", "objective", "vehicle", "other", "penalty"]

    for cat in categories_order:
        if cat in pdf.columns:
            fig.add_trace(
                go.Bar(
                    name=CATEGORY_LABELS.get(cat, cat.capitalize()),
                    x=pdf["match_id"],
                    y=pdf[cat],
                    marker={"color": CATEGORY_COLORS.get(cat, CATEGORY_COLORS["other"])},
                    hovertemplate=f"<b>{CATEGORY_LABELS.get(cat, cat)}</b><br>"
                    + "%{y:,.0f} pts<extra></extra>",
                )
            )

    fig.update_layout(
        title={"text": title, "x": 0.5},
        barmode="relative",  # Permet les valeurs négatives
        xaxis_title="Match",
        yaxis_title="Points",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        xaxis={"tickangle": -45, "showticklabels": False},  # Masquer les IDs longs
    )

    return apply_halo_plot_style(fig)


# =============================================================================
# Indicateur : Résumé de participation
# =============================================================================


def create_participation_indicator(
    df: pl.DataFrame,
    *,
    title: str = "Participation",
) -> go.Figure:
    """Indicateur multi-valeurs de participation.

    Affiche kills, assists, objectifs, pénalités en un coup d'œil.

    Args:
        df: DataFrame avec colonnes award_category, award_count, award_score.
        title: Titre.

    Returns:
        Figure Plotly avec indicateurs.
    """
    import polars as pl

    # Agréger par catégorie
    agg = df.group_by("award_category").agg(
        pl.col("award_count").sum().alias("count"),
        pl.col("award_score").sum().alias("score"),
    )

    # Convertir en dict pour accès facile
    stats = {}
    for row in agg.iter_rows(named=True):
        cat = row["award_category"]
        stats[cat] = {"count": row["count"], "score": row["score"]}

    # Extraire les valeurs
    kills = stats.get("kill", {"count": 0, "score": 0})
    assists = stats.get("assist", {"count": 0, "score": 0})
    objectives = stats.get("objective", {"count": 0, "score": 0})
    penalties = stats.get("penalty", {"count": 0, "score": 0})

    fig = go.Figure()

    # 4 indicateurs sur une ligne
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=kills["count"],
            title={
                "text": f"Frags<br><span style='font-size:0.7em;color:gray'>{kills['score']:,} pts</span>"
            },
            domain={"x": [0, 0.25], "y": [0, 1]},
            number={"font": {"color": CATEGORY_COLORS["kill"], "size": 48}},
        )
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=assists["count"],
            title={
                "text": f"Assists<br><span style='font-size:0.7em;color:gray'>{assists['score']:,} pts</span>"
            },
            domain={"x": [0.25, 0.5], "y": [0, 1]},
            number={"font": {"color": CATEGORY_COLORS["assist"], "size": 48}},
        )
    )

    fig.add_trace(
        go.Indicator(
            mode="number",
            value=objectives["count"],
            title={
                "text": f"Objectifs<br><span style='font-size:0.7em;color:gray'>{objectives['score']:,} pts</span>"
            },
            domain={"x": [0.5, 0.75], "y": [0, 1]},
            number={"font": {"color": CATEGORY_COLORS["objective"], "size": 48}},
        )
    )

    # Pénalités (avec signe négatif)
    penalty_display = abs(penalties["count"]) if penalties["count"] else 0
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=penalty_display,
            title={
                "text": f"Pénalités<br><span style='font-size:0.7em;color:gray'>{penalties['score']:,} pts</span>"
            },
            domain={"x": [0.75, 1], "y": [0, 1]},
            number={"font": {"color": CATEGORY_COLORS["penalty"], "size": 48}},
        )
    )

    fig.update_layout(
        title={"text": title, "x": 0.5},
        height=150,
        margin={"t": 60, "b": 20, "l": 20, "r": 20},
    )

    return fig


# =============================================================================
# Graphique Sunburst : Hiérarchie catégorie → action
# =============================================================================


def plot_participation_sunburst(
    df: pl.DataFrame,
    *,
    title: str = "Détail de la participation",
) -> go.Figure:
    """Sunburst chart hiérarchique catégorie → action.

    Args:
        df: DataFrame avec colonnes award_category, award_name, award_score.
        title: Titre du graphique.

    Returns:
        Figure Plotly.
    """
    import polars as pl

    # Agréger par catégorie et action
    agg = (
        df.group_by(["award_category", "award_name"])
        .agg(pl.col("award_score").sum().alias("score"))
        .filter(pl.col("score") > 0)  # Exclure les pénalités du sunburst
        .sort("score", descending=True)
    )

    pdf = agg.to_pandas()

    if pdf.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Aucune donnée positive",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return apply_halo_plot_style(fig)

    # Mapper les labels de catégorie
    pdf["category_label"] = pdf["award_category"].map(
        lambda x: CATEGORY_LABELS.get(x, x.capitalize() if x else "Autre")
    )

    # Mapper les couleurs
    color_map = {}
    for cat, color in CATEGORY_COLORS.items():
        label = CATEGORY_LABELS.get(cat, cat.capitalize())
        color_map[label] = color

    fig = px.sunburst(
        pdf,
        path=["category_label", "award_name"],
        values="score",
        color="category_label",
        color_discrete_map=color_map,
    )

    fig.update_traces(
        textinfo="label+value",
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} pts<extra></extra>",
    )

    fig.update_layout(
        title={"text": title, "x": 0.5},
    )

    return apply_halo_plot_style(fig)


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "get_participation_colors",
    "plot_participation_pie",
    "plot_participation_bars",
    "plot_participation_by_match",
    "create_participation_indicator",
    "plot_participation_sunburst",
]
