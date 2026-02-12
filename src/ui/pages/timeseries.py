"""Page Séries temporelles.

Graphes d'évolution des statistiques dans le temps.
"""

from __future__ import annotations

import polars as pl

# Type alias pour compatibilité DataFrame
try:
    import pandas as pd

    DataFrameType = pd.DataFrame | pl.DataFrame
except ImportError:
    pd = None  # type: ignore[assignment]
    DataFrameType = pl.DataFrame  # type: ignore[misc]

import streamlit as st

from src.analysis.performance_score import compute_performance_series
from src.config import HALO_COLORS
from src.visualization.distributions import (
    plot_correlation_scatter,
    plot_first_event_distribution,
    plot_histogram,
    plot_kda_distribution,
)
from src.visualization.performance import (
    plot_cumulative_kd,
    plot_cumulative_net_score,
    plot_rolling_kd,
    plot_session_trend,
)
from src.visualization.timeseries import (
    plot_assists_timeseries,
    plot_average_life,
    plot_damage_dealt_taken,
    plot_per_minute_timeseries,
    plot_performance_timeseries,
    plot_rank_score,
    plot_shots_accuracy,
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

    # Calculer le score de performance AVANT d'afficher les distributions
    # (nécessaire pour la distribution du score de performance)
    history_df = df_full if df_full is not None else dff
    if "performance_score" not in dff.columns:
        dff = dff.copy()
        dff["performance_score"] = compute_performance_series(dff, history_df)

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

        # ═══ Performance cumulée & tendance (Sprint 6) ═══
        st.divider()
        st.subheader("Performance cumulée & tendance")
        st.caption(
            "Net score et K/D cumulés au fil des matchs, K/D glissant, et tendance (début vs fin de période)."
        )
        _required_cumul = ["start_time", "kills", "deaths"]
        if all(c in dff.columns for c in _required_cumul):
            try:
                # Inclure time_played_seconds si disponible (pour marqueurs durée Sprint 6.4)
                _cumul_cols = list(_required_cumul)
                _has_tps = "time_played_seconds" in dff.columns
                if _has_tps:
                    _cumul_cols.append("time_played_seconds")

                _sorted_dff = dff.sort_values("start_time")
                pl_df = pl.from_pandas(_sorted_dff[_cumul_cols].copy())
                from src.analysis.cumulative import (
                    compute_cumulative_kd_series_polars,
                    compute_cumulative_net_score_series_polars,
                    compute_rolling_kd_polars,
                )

                if not pl_df.is_empty():
                    # Extraire time_played_seconds pour les marqueurs de durée
                    _tps_list: list[int | float] | None = None
                    if _has_tps:
                        _tps_list = _sorted_dff["time_played_seconds"].fillna(0).tolist()

                    cumul_net = compute_cumulative_net_score_series_polars(pl_df)
                    st.plotly_chart(
                        plot_cumulative_net_score(cumul_net, time_played_seconds=_tps_list),
                        width="stretch",
                    )
                    cumul_kd = compute_cumulative_kd_series_polars(pl_df)
                    st.plotly_chart(
                        plot_cumulative_kd(cumul_kd, time_played_seconds=_tps_list),
                        width="stretch",
                    )
                    rolling_df = compute_rolling_kd_polars(pl_df, window_size=5)
                    st.plotly_chart(
                        plot_rolling_kd(rolling_df, window_size=5),
                        width="stretch",
                    )
                    if len(pl_df) >= 4:
                        st.plotly_chart(
                            plot_session_trend(pl_df),
                            width="stretch",
                        )
                    else:
                        st.info("Tendance de session : au moins 4 matchs requis.")
            except Exception as e:
                st.warning(f"Graphiques de performance cumulée indisponibles : {e}")
        else:
            st.info("Colonnes start_time, kills ou deaths manquantes pour la performance cumulée.")

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
                    st.info(
                        f"Pas assez de données de précision ({len(acc_data)} matchs). "
                        "Il en faut au moins 6 pour afficher la distribution."
                    )
            else:
                st.info("Colonne précision non disponible dans les données.")

        with col_dist2:
            # Distribution des kills
            if "kills" in dff.columns:
                kills_data = dff["kills"].dropna()
                if len(kills_data) > 5:
                    fig_kills = plot_histogram(
                        kills_data,
                        title="Distribution des Frags",
                        x_label="Frags",
                        y_label="Matchs",
                        show_kde=True,
                        color=colors["green"],
                    )
                    st.plotly_chart(fig_kills, width="stretch")
                else:
                    st.info(
                        f"Pas assez de données de kills ({len(kills_data)} matchs). "
                        "Il en faut au moins 6 pour afficher la distribution."
                    )
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
                    st.info(
                        f"Pas assez de données de durée de vie ({len(life_data)} matchs). "
                        "Il en faut au moins 6 pour afficher la distribution."
                    )
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
                    st.info(
                        f"Pas assez de données de performance ({len(perf_data)} matchs). "
                        "Il en faut au moins 6 pour afficher la distribution."
                    )
            else:
                st.info("Score de performance non disponible.")

        # === Nouvelles distributions Sprint 6 (6.2, 6.3) ===
        col_dist5, col_dist6 = st.columns(2)

        with col_dist5:
            # Distribution du score personnel par minute (6.2)
            if "personal_score" in dff.columns and "time_played_seconds" in dff.columns:
                _ps = dff[["personal_score", "time_played_seconds"]].dropna()
                _ps = _ps[_ps["time_played_seconds"] > 0]
                if len(_ps) > 5:
                    score_per_min = _ps["personal_score"] / (_ps["time_played_seconds"] / 60)
                    fig_spm = plot_histogram(
                        score_per_min,
                        title="Distribution Score Personnel / min",
                        x_label="Score / min",
                        y_label="Matchs",
                        show_kde=True,
                        color=colors["amber"],
                    )
                    st.plotly_chart(fig_spm, width="stretch")
                else:
                    st.info("Pas assez de données pour la distribution du score par minute.")
            else:
                st.info("Colonnes score personnel ou time_played non disponibles.")

        with col_dist6:
            # Distribution du taux de victoire glissant (6.3)
            if "outcome" in dff.columns and len(dff) >= 10:
                _wr_df = dff.sort_values("start_time") if "start_time" in dff.columns else dff
                _wins = (_wr_df["outcome"] == 1).astype(float)
                win_rate_rolling = _wins.rolling(window=10, min_periods=10).mean() * 100
                win_rate_clean = win_rate_rolling.dropna()
                if len(win_rate_clean) > 5:
                    fig_wr = plot_histogram(
                        win_rate_clean,
                        title="Distribution Win Rate Glissant (10 matchs)",
                        x_label="Taux de victoire (%)",
                        y_label="Fréquence",
                        show_kde=True,
                        color=colors["green"],
                    )
                    st.plotly_chart(fig_wr, width="stretch")
                else:
                    st.info(
                        "Pas assez de données pour la distribution du win rate glissant "
                        "(10 matchs minimum par fenêtre)."
                    )
            else:
                if "outcome" not in dff.columns:
                    st.info("Colonne outcome non disponible.")
                else:
                    st.info("Au moins 10 matchs requis pour le win rate glissant.")

        # === Corrélations Sprint 5.4.5 ===
        st.divider()
        st.subheader("Corrélations")
        st.caption("Analyse les relations entre tes métriques et le résultat du match.")

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
                    title="Durée de vie vs frags",
                    x_label="Durée de vie (s)",
                    y_label="Frags",
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
                    st.info(
                        f"Pas assez de données de précision/FDA ({len(valid_data)} matchs). "
                        "Il en faut au moins 6 pour la corrélation."
                    )
            else:
                st.info("Colonnes précision ou FDA non disponibles.")

        # === Nouvelles corrélations Sprint 6 (6.1) ===
        col_corr3, col_corr4 = st.columns(2)

        with col_corr3:
            # Durée de vie vs Morts (6.1 §2.1)
            life_col = (
                "avg_life_seconds" if "avg_life_seconds" in dff.columns else "average_life_seconds"
            )
            if life_col in dff.columns and "deaths" in dff.columns:
                valid_life_deaths = dff.dropna(subset=[life_col, "deaths"])
                if len(valid_life_deaths) > 5:
                    fig_corr3 = plot_correlation_scatter(
                        dff,
                        life_col,
                        "deaths",
                        color_col="outcome",
                        title="Durée de vie vs morts",
                        x_label="Durée de vie (s)",
                        y_label="Morts",
                        show_trendline=True,
                    )
                    st.plotly_chart(fig_corr3, width="stretch")
                else:
                    st.info("Pas assez de données pour la corrélation durée de vie/morts.")
            else:
                st.info("Données insuffisantes pour cette corrélation.")

        with col_corr4:
            # Kills vs Deaths (6.1 §2.2)
            if "kills" in dff.columns and "deaths" in dff.columns:
                valid_kd = dff.dropna(subset=["kills", "deaths"])
                if len(valid_kd) > 5:
                    fig_corr4 = plot_correlation_scatter(
                        dff,
                        "kills",
                        "deaths",
                        color_col="outcome",
                        title="Frags vs morts",
                        x_label="Frags",
                        y_label="Morts",
                        show_trendline=True,
                    )
                    st.plotly_chart(fig_corr4, width="stretch")
                else:
                    st.info("Pas assez de données pour la corrélation frags/morts.")
            else:
                st.info("Colonnes frags ou morts non disponibles.")

        # Team MMR vs Enemy MMR (6.1 §2.3)
        if "team_mmr" in dff.columns and "enemy_mmr" in dff.columns:
            valid_mmr = dff.dropna(subset=["team_mmr", "enemy_mmr"])
            if len(valid_mmr) > 5:
                fig_mmr = plot_correlation_scatter(
                    dff,
                    "team_mmr",
                    "enemy_mmr",
                    color_col="outcome",
                    title="MMR Équipe vs MMR Adversaire",
                    x_label="MMR Équipe",
                    y_label="MMR Adversaire",
                    show_trendline=True,
                )
                st.plotly_chart(fig_mmr, width="stretch")
            else:
                st.info("Pas assez de données MMR pour cette corrélation.")

        # === Distribution Premier Kill/Death (Sprint 5.4.4) ===
        st.divider()
        st.subheader("Temps du premier frag / première mort")
        st.caption(
            "Distribution des timestamps du premier frag et de la première mort. "
            "Visualise à quelle vitesse tu obtiens ton premier frag vs ta première mort."
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
                "Données d'événements non disponibles (premier frag / première mort). "
                "L’**Actualiser** récupère déjà ces données pour les **nouveaux** matchs. "
                "Pour les matchs déjà en base sans événements film, active dans **Paramètres** "
                "→ **Options du bouton Actualiser** l’option **Backfill events**, puis **Actualiser**."
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

        st.subheader("Folie meurtrière / Tirs à la tête / Frags parfaits")

        # Charger les Perfect kills depuis le repository (priorité aux paramètres passés par le routeur)
        perfect_counts: dict[str, int] | None = None
        _db_path = db_path or st.session_state.get("db_path")
        _xuid = xuid or st.session_state.get("player_xuid") or st.session_state.get("xuid")

        if _db_path and _xuid and "match_id" in dff.columns:
            try:
                # Importer le repository ici pour éviter les imports circulaires
                from src.data.repositories.duckdb_repo import DuckDBRepository

                if _db_path.endswith(".duckdb"):
                    repo = DuckDBRepository(_db_path, str(_xuid).strip())
                    match_ids = dff["match_id"].astype(str).tolist()
                    perfect_counts = repo.count_perfect_kills_by_match(match_ids)
            except Exception:
                perfect_counts = None

        st.plotly_chart(
            plot_spree_headshots_accuracy(dff, perfect_counts=perfect_counts),
            width="stretch",
        )

        # === Sprint 7 — Nouvelles sections ===

        # 7.5 — Tirs et précision
        _has_shots = any(c in dff.columns for c in ("shots_fired", "shots_hit"))
        if _has_shots:
            st.divider()
            st.subheader("Tirs et précision")
            st.caption(
                "Tirs tirés vs touchés (barres groupées) et courbe de précision. "
                "La précision a été retirée du graphe Folie meurtrière pour une lecture plus claire."
            )
            st.plotly_chart(plot_shots_accuracy(dff, title=None), width="stretch")

        # 7.4 — Dégâts infligés vs subis
        _has_damage = any(c in dff.columns for c in ("damage_dealt", "damage_taken"))
        if _has_damage:
            st.divider()
            st.subheader("Dégâts")
            st.caption(
                "Compare les dégâts infligés et subis par match. "
                "Un ratio élevé (infligés > subis) indique une bonne efficacité au combat."
            )
            st.plotly_chart(plot_damage_dealt_taken(dff, title=None), width="stretch")

        # 7.3 — Rang et score personnel
        _has_rank_score = "rank" in dff.columns or "personal_score" in dff.columns
        if _has_rank_score:
            st.divider()
            st.subheader("Rang et score personnel")
            st.caption(
                "Le score personnel en barres et le rang en ligne (axe Y inversé : "
                "rang 1 en haut). Un bon score associé à un rang élevé confirme l'impact."
            )
            st.plotly_chart(plot_rank_score(dff, title=None), width="stretch")
