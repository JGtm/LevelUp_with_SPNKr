"""Section Participation au match - Basée sur PersonalScores.

Sprint 8.2 - Affiche la décomposition du score personnel :
- Radar de participation (5 axes)
- Pie chart de contribution
- Indicateurs KPI
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    pass


def render_participation_section(
    db_path: str,
    match_id: str,
    xuid: str,
    db_key: tuple[int, int] | None = None,
) -> None:
    """Affiche la section Participation au match.

    Utilise les PersonalScoreAwards pour décomposer le score.

    Args:
        db_path: Chemin vers la base de données.
        match_id: ID du match.
        xuid: XUID du joueur.
        db_key: Clé de cache pour la DB.
    """
    from src.data.repositories import DuckDBRepository

    # Charger les données
    try:
        repo = DuckDBRepository(db_path, xuid)
        if not repo.has_personal_score_awards():
            # Table vide ou non existante - ne pas afficher la section
            return

        df = repo.load_personal_score_awards_as_polars(match_id=match_id)

        if df.is_empty():
            # Pas de données pour ce match - ne pas afficher
            return

    except Exception:
        # En cas d'erreur, ne pas bloquer le reste de la page
        return

    # Afficher la section
    st.subheader("🎯 Participation au match")

    # Import des visualisations
    from src.ui.components.radar_chart import create_participation_radar
    from src.visualization import (
        aggregate_participation_for_radar,
        create_participation_indicator,
        plot_participation_pie,
    )

    # Colonnes : Radar | Pie
    col_radar, col_pie = st.columns(2)

    with col_radar:
        # Préparer les données pour le radar
        radar_data = aggregate_participation_for_radar(df, name="Ce match", color="#636EFA")
        fig_radar = create_participation_radar(
            [radar_data],
            title="Profil de participation",
            height=350,
        )
        st.plotly_chart(fig_radar, width="stretch")

    with col_pie:
        fig_pie = plot_participation_pie(
            df,
            title="Répartition du score",
            show_values=True,
        )
        st.plotly_chart(fig_pie, width="stretch")

    # Indicateurs KPI en dessous
    fig_indicator = create_participation_indicator(df, title="")
    st.plotly_chart(fig_indicator, width="stretch")


def render_participation_comparison(
    db_path: str,
    match_ids: list[str],
    xuid: str,
    labels: list[str] | None = None,
    colors: list[str] | None = None,
) -> None:
    """Affiche une comparaison de participation entre plusieurs matchs.

    Args:
        db_path: Chemin vers la base de données.
        match_ids: Liste des IDs de matchs à comparer.
        xuid: XUID du joueur.
        labels: Labels pour chaque match (optionnel).
        colors: Couleurs pour chaque match (optionnel).
    """
    from src.data.repositories import DuckDBRepository
    from src.ui.components.radar_chart import create_participation_radar
    from src.visualization import aggregate_participation_for_radar

    if not match_ids:
        return

    default_colors = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A"]
    if labels is None:
        labels = [f"Match {i + 1}" for i in range(len(match_ids))]
    if colors is None:
        colors = default_colors[: len(match_ids)]

    try:
        repo = DuckDBRepository(db_path, xuid)
        if not repo.has_personal_score_awards():
            return

        radar_data = []
        for i, mid in enumerate(match_ids):
            df = repo.load_personal_score_awards_as_polars(match_id=mid)
            if not df.is_empty():
                data = aggregate_participation_for_radar(
                    df,
                    name=labels[i] if i < len(labels) else f"Match {i + 1}",
                    color=colors[i] if i < len(colors) else None,
                )
                radar_data.append(data)

        if not radar_data:
            return

        st.subheader("📊 Comparaison de participation")
        fig = create_participation_radar(radar_data, title="", height=400)
        st.plotly_chart(fig, width="stretch")

    except Exception:
        pass


__all__ = [
    "render_participation_section",
    "render_participation_comparison",
]
