"""Page Séries temporelles.

Graphes d'évolution des statistiques dans le temps.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import HALO_COLORS
from src.visualization.distributions import (
    plot_correlation_scatter,
    plot_first_event_distribution,
    plot_histogram,
    plot_kda_distribution,
)
from src.visualization.timeseries import (
    plot_assists_timeseries,
    plot_average_life,
    plot_per_minute_timeseries,
    plot_performance_timeseries,
    plot_spree_headshots_accuracy,
    plot_timeseries,
)


def render_timeseries_page(
    dff: pd.DataFrame,
    df_full: pd.DataFrame | None = None,
    *,
    db_path: str | None = None,
    xuid: str | None = None,
) -> None:
    """Affiche la page Séries temporelles.

    Args:
        dff: DataFrame filtré des matchs.
        df_full: DataFrame complet pour le calcul du score relatif.
        db_path: Chemin vers la DB (optionnel, pour les features DuckDB).
        xuid: XUID du joueur (optionnel, pour les features DuckDB).
    """
    # Protection contre les DataFrames vides
    if dff.empty:
        st.warning("Aucun match à afficher. Vérifiez vos filtres ou synchronisez les données.")
        return

    with st.spinner("Génération des graphes…"):
        fig = plot_timeseries(dff)
        st.plotly_chart(fig, width="stretch")

        st.subheader("FDA")
        valid = dff.dropna(subset=["kda"]) if "kda" in dff.columns else pd.DataFrame()
        if valid.empty:
            st.info("FDA indisponible sur ce filtre.")
        else:
            m = st.columns(1)
            m[0].metric("KDA moyen", f"{valid['kda'].mean():.2f}", label_visibility="collapsed")
            st.plotly_chart(plot_kda_distribution(dff), width="stretch")

        # === Nouvelles distributions Sprint 5.4.3 ===
        st.divider()
        st.subheader("Distributions")
        st.caption("Visualise la répartition de tes statistiques.")

        colors = HALO_COLORS.as_dict()
        col_dist1, col_dist2 = st.columns(2)

        with col_dist1:
            # Distribution de la précision
            if "accuracy" in dff.columns:
                acc_data = dff["accuracy"].dropna()
                if len(acc_data) > 5:
                    fig_acc = plot_histogram(
                        acc_data,
                        title="Distribution de la Précision",
                        x_label="Précision (%)",
                        y_label="Matchs",
                        show_kde=True,
                        color=colors["cyan"],
                    )
                    st.plotly_chart(fig_acc, width="stretch")
                elif len(acc_data) == 0:
                    st.info("Aucune donnée de précision disponible pour ce filtre.")
                else:
                    st.info(f"Pas assez de données de précision ({len(acc_data)} matchs).")
            else:
                st.info("Colonne précision non disponible dans les données.")

        with col_dist2:
            # Distribution des kills
            if "kills" in dff.columns:
                kills_data = dff["kills"].dropna()
                if len(kills_data) > 5:
                    fig_kills = plot_histogram(
                        kills_data,
                        title="Distribution des Kills",
                        x_label="Kills",
                        y_label="Matchs",
                        show_kde=True,
                        color=colors["green"],
                    )
                    st.plotly_chart(fig_kills, width="stretch")
                else:
                    st.info("Pas assez de données de kills.")
            else:
                st.info("Colonne kills non disponible.")

        col_dist3, col_dist4 = st.columns(2)

        with col_dist3:
            # Distribution durée de vie
            if "avg_life_seconds" in dff.columns or "average_life_seconds" in dff.columns:
                life_col = (
                    "avg_life_seconds"
                    if "avg_life_seconds" in dff.columns
                    else "average_life_seconds"
                )
                life_data = dff[life_col].dropna()
                if len(life_data) > 5:
                    fig_life = plot_histogram(
                        life_data,
                        title="Distribution Durée de Vie",
                        x_label="Durée (secondes)",
                        y_label="Matchs",
                        show_kde=True,
                        color=colors["amber"],
                    )
                    st.plotly_chart(fig_life, width="stretch")
                else:
                    st.info("Pas assez de données de durée de vie.")
            else:
                st.info("Colonne durée de vie non disponible.")

        with col_dist4:
            # Distribution du score de performance
            if "performance_score" in dff.columns:
                perf_data = dff["performance_score"].dropna()
                if len(perf_data) > 5:
                    fig_perf = plot_histogram(
                        perf_data,
                        title="Distribution Score de Performance",
                        x_label="Score",
                        y_label="Matchs",
                        show_kde=True,
                        color=colors["violet"],
                    )
                    st.plotly_chart(fig_perf, width="stretch")
                else:
                    st.info("Pas assez de données de performance.")
            else:
                st.info("Score de performance non disponible.")

        # === Corrélations Sprint 5.4.5 ===
        st.divider()
        st.subheader("Corrélations")
        st.caption("Analyse les relations entre tes métriques.")

        col_corr1, col_corr2 = st.columns(2)

        with col_corr1:
            # Durée de vie vs Kills
            life_col = (
                "avg_life_seconds" if "avg_life_seconds" in dff.columns else "average_life_seconds"
            )
            if life_col in dff.columns and "kills" in dff.columns:
                fig_corr1 = plot_correlation_scatter(
                    dff,
                    life_col,
                    "kills",
                    color_col="outcome",
                    title="Durée de vie vs Kills",
                    x_label="Durée de vie (s)",
                    y_label="Kills",
                    show_trendline=True,
                )
                st.plotly_chart(fig_corr1, width="stretch")
            else:
                st.info("Données insuffisantes pour cette corrélation.")

        with col_corr2:
            # Précision vs KDA
            if "accuracy" in dff.columns and "kda" in dff.columns:
                # Vérifier qu'il y a des données non-NaN pour les deux colonnes
                valid_data = dff.dropna(subset=["accuracy", "kda"])
                if len(valid_data) > 5:
                    fig_corr2 = plot_correlation_scatter(
                        dff,
                        "accuracy",
                        "kda",
                        color_col="outcome",
                        title="Précision vs FDA",
                        x_label="Précision (%)",
                        y_label="FDA",
                        show_trendline=True,
                    )
                    st.plotly_chart(fig_corr2, width="stretch")
                else:
                    st.info("Pas assez de données de précision/FDA disponibles.")
            else:
                st.info("Colonnes précision ou FDA non disponibles.")

        # === Distribution Premier Kill/Death (Sprint 5.4.4) ===
        st.divider()
        st.subheader("Temps du premier kill / première mort")
        st.caption(
            "Distribution des timestamps du premier kill et de la première mort. "
            "Visualise à quelle vitesse tu obtiens ton premier kill vs ta première mort."
        )

        first_kills: dict[str, int | None] = {}
        first_deaths: dict[str, int | None] = {}

        if db_path and xuid and "match_id" in dff.columns:
            try:
                from src.data.repositories.duckdb_repo import DuckDBRepository

                if db_path.endswith(".duckdb"):
                    repo = DuckDBRepository(db_path, str(xuid).strip())
                    match_ids = dff["match_id"].astype(str).tolist()
                    first_kills, first_deaths = repo.get_first_kill_death_times(match_ids)
            except Exception:
                pass

        if first_kills or first_deaths:
            fig_events = plot_first_event_distribution(
                first_kills,
                first_deaths,
                title=None,
            )
            st.plotly_chart(fig_events, width="stretch")
        else:
            st.info(
                "Données d'événements non disponibles. "
                "Synchronise tes matchs avec l'option highlight_events activée."
            )

        st.subheader("Performance")
        history = df_full if df_full is not None else dff
        st.plotly_chart(plot_performance_timeseries(dff, df_history=history), width="stretch")

        st.subheader("Assistances")
        st.plotly_chart(plot_assists_timeseries(dff), width="stretch")

        st.subheader("Stats par minute")
        st.plotly_chart(
            plot_per_minute_timeseries(dff),
            width="stretch",
        )

        st.subheader("Durée de vie moyenne")
        if dff.dropna(subset=["average_life_seconds"]).empty:
            st.info("Average Life indisponible sur ce filtre.")
        else:
            st.plotly_chart(plot_average_life(dff), width="stretch")

        st.subheader("Folie meurtrière / Tirs à la tête / Précision / Frags parfaits")

        # Charger les Perfect kills depuis le repository si disponible
        perfect_counts: dict[str, int] | None = None
        db_path = st.session_state.get("db_path")
        xuid = st.session_state.get("player_xuid")

        if db_path and xuid and "match_id" in dff.columns:
            try:
                # Importer le repository ici pour éviter les imports circulaires
                from src.data.repositories.duckdb_repo import DuckDBRepository

                if db_path.endswith(".duckdb"):
                    repo = DuckDBRepository(db_path, str(xuid).strip())
                    match_ids = dff["match_id"].astype(str).tolist()
                    perfect_counts = repo.count_perfect_kills_by_match(match_ids)
            except Exception:
                perfect_counts = None

        st.plotly_chart(
            plot_spree_headshots_accuracy(dff, perfect_counts=perfect_counts),
            width="stretch",
        )
