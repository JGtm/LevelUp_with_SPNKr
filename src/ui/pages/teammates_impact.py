"""Onglet Impact & Taquinerie pour la page Coéquipiers.

Extrait de teammates.py (Sprint 16 — refactoring Phase A).
Heatmap des événements clés + tableau de ranking MVP/Boulet.
"""

from __future__ import annotations

import polars as pl
import streamlit as st

from src.analysis.friends_impact import (
    build_impact_matrix,
    get_all_impact_events,
)
from src.data.repositories import DuckDBRepository
from src.visualization.friends_impact_heatmap import (
    build_impact_ranking_df,
    count_events_by_player,
    plot_friends_impact_heatmap,
    render_impact_summary_stats,
)


def _load_highlight_events(
    conn,
    match_ids: list[str],
) -> pl.DataFrame | None:
    """Charge les événements highlight depuis la connexion DuckDB.

    Returns:
        DataFrame Polars des événements, ou None si indisponible.
    """
    has_events_table = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = 'highlight_events'"
    ).fetchone()

    if not has_events_table:
        return None

    events_query = """
        SELECT match_id, xuid::TEXT as xuid, gamertag, event_type, time_ms
        FROM highlight_events
        WHERE match_id IN ({})
    """.format(", ".join(["?" for _ in match_ids]))

    events_result = conn.execute(events_query, match_ids).fetchall()

    if not events_result:
        return pl.DataFrame()

    return pl.DataFrame(
        {
            "match_id": [str(r[0]) for r in events_result],
            "xuid": [str(r[1]) for r in events_result],
            "gamertag": [r[2] or "Unknown" for r in events_result],
            "event_type": [r[3] for r in events_result],
            "time_ms": [int(r[4] or 0) for r in events_result],
        }
    )


def _load_match_outcomes(
    conn,
    match_ids: list[str],
) -> pl.DataFrame:
    """Charge les outcomes des matchs depuis la connexion DuckDB."""
    matches_query = """
        SELECT match_id, outcome
        FROM match_stats
        WHERE match_id IN ({})
    """.format(", ".join(["?" for _ in match_ids]))

    matches_result = conn.execute(matches_query, match_ids).fetchall()

    return pl.DataFrame(
        {
            "match_id": [str(r[0]) for r in matches_result],
            "outcome": [int(r[1] or 0) for r in matches_result],
        }
    )


def _render_impact_stats(
    first_bloods: dict,
    clutch_finishers: dict,
    last_casualties: dict,
) -> None:
    """Affiche les métriques résumées d'impact."""
    stats = render_impact_summary_stats(first_bloods, clutch_finishers, last_casualties)
    cols = st.columns(4)
    cols[0].metric("🟢 Premier Sang", stats["total_fb"])
    cols[1].metric("🟡 Finisseur", stats["total_clutch"])
    cols[2].metric("🔴 Boulet", stats["total_casualty"])
    cols[3].metric("📊 Matchs analysés", stats["total_matches"])


def _render_ranking_table(
    scores: dict,
    first_bloods: dict,
    clutch_finishers: dict,
    last_casualties: dict,
) -> None:
    """Affiche le tableau de classement MVP/Boulet."""
    fb_counts = count_events_by_player(first_bloods)
    clutch_counts = count_events_by_player(clutch_finishers)
    casualty_counts = count_events_by_player(last_casualties)

    ranking_df = build_impact_ranking_df(
        scores,
        first_blood_counts=fb_counts,
        clutch_counts=clutch_counts,
        casualty_counts=casualty_counts,
    )

    if not ranking_df.is_empty():
        display_df = ranking_df.to_pandas()
        display_df.columns = [
            "Rang",
            "Joueur",
            "Score",
            "🟢 FB",
            "🟡 Clutch",
            "🔴 Boulet",
            "Badge",
        ]
        st.dataframe(display_df, width="stretch", hide_index=True)

        mvp = ranking_df[0, "gamertag"] if len(ranking_df) > 0 else None
        boulet = (
            ranking_df[-1, "gamertag"]
            if len(ranking_df) > 1 and ranking_df[-1, "score"] < 0
            else None
        )

        summary_cols = st.columns(2)
        if mvp:
            summary_cols[0].success(f"**🏆 MVP de la Soirée :** {mvp}")
        if boulet:
            summary_cols[1].error(f"**🍌 Maillon Faible :** {boulet}")


def render_impact_taquinerie(
    db_path: str,
    xuid: str,
    match_ids: list[str],
    friend_xuids: list[str],
    db_key: tuple[int, int] | None = None,
) -> None:
    """Affiche l'onglet Impact & Taquinerie (Sprint 12).

    Args:
        db_path: Chemin vers la DB principale.
        xuid: XUID du joueur principal.
        match_ids: Liste des match_id à analyser.
        friend_xuids: Liste des XUIDs des coéquipiers sélectionnés.
        db_key: Clé de cache (optionnel).
    """
    with st.expander("⚡ Impact & Taquinerie", expanded=False):
        if len(friend_xuids) < 2:
            st.info("Sélectionnez au moins 2 coéquipiers pour voir l'analyse d'impact.")
            return

        if not match_ids:
            st.warning("Aucun match à analyser.")
            return

        st.caption(
            "Qui fait le premier sang 🟢, finit les victoires (Finisseur) 🟡, "
            "ou meurt en dernier lors des défaites (Boulet) 🔴 ?"
        )

        try:
            repo = DuckDBRepository(db_path, xuid.strip())
            conn = repo._get_connection()

            # Charger les événements
            events_df = _load_highlight_events(conn, match_ids)
            if events_df is None:
                st.info(
                    "Les données d'événements (highlight_events) ne sont pas disponibles. "
                    "Cette fonctionnalité nécessite une synchronisation avec les détails de matchs."
                )
                return
            if events_df.is_empty():
                st.info("Aucun événement trouvé pour les matchs sélectionnés.")
                return

            # Charger les outcomes
            matches_df = _load_match_outcomes(conn, match_ids)

            # Inclure le joueur principal + tous les amis sélectionnés
            all_friend_xuids = {str(x) for x in friend_xuids}
            all_friend_xuids.add(str(xuid).strip())

            # Calculer les événements d'impact
            first_bloods, clutch_finishers, last_casualties, scores = get_all_impact_events(
                events_df, matches_df, friend_xuids=all_friend_xuids
            )

            if not scores:
                st.info("Aucun événement d'impact trouvé pour les joueurs sélectionnés.")
                return

            gamertags = list(scores.keys())
            sorted_match_ids = sorted(
                {
                    m
                    for m in match_ids
                    if m
                    in set(
                        list(first_bloods.keys())
                        + list(clutch_finishers.keys())
                        + list(last_casualties.keys())
                    )
                }
            )

            # Construire la matrice d'impact
            impact_matrix = build_impact_matrix(
                first_bloods,
                clutch_finishers,
                last_casualties,
                match_ids=sorted_match_ids[:50],
                gamertags=gamertags,
            )

            # Métriques résumées
            _render_impact_stats(first_bloods, clutch_finishers, last_casualties)

            # Heatmap
            st.subheader("Heatmap d'Impact")
            fig = plot_friends_impact_heatmap(
                impact_matrix,
                title=None,
                max_matches=50,
            )
            st.plotly_chart(fig, width="stretch")

            # Tableau de ranking
            st.subheader("🏆 Classement Taquinerie")
            _render_ranking_table(scores, first_bloods, clutch_finishers, last_casualties)

        except Exception as e:
            st.warning(f"Impossible de charger les données d'impact : {e}")
