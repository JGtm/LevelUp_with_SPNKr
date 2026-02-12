"""Page Mes coéquipiers.

Analyse des statistiques avec les coéquipiers fréquents.
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

from src.analysis import (
    compute_aggregated_stats,
    compute_global_ratio,
    compute_map_breakdown,
    compute_outcome_rates,
)

# Sprint 12 - Impact & Taquinerie
from src.analysis.friends_impact import (
    build_impact_matrix,
    get_all_impact_events,
)
from src.ui import display_name_from_xuid
from src.ui.cache import (
    cached_compute_sessions_db,
    cached_friend_matches_df,
    cached_has_cache_tables,
    cached_query_matches_with_friend,
    cached_same_team_match_ids_with_friend,
    load_df_optimized,
)
from src.ui.medals import render_medals_grid

# Import des sous-modules extraits
from src.ui.pages.teammates_charts import (
    render_comparison_charts,
    render_metric_bar_charts,
    render_outcome_bar_chart,
    render_trio_charts,
)
from src.ui.pages.teammates_helpers import (
    _clear_min_matches_maps_friends_auto,
    render_friends_history_table,
    render_teammate_cards,
)
from src.ui.perf import perf_section
from src.visualization import plot_map_ratio_with_winloss
from src.visualization.friends_impact_heatmap import (
    build_impact_ranking_df,
    count_events_by_player,
    plot_friends_impact_heatmap,
    render_impact_summary_stats,
)
from src.visualization.performance import plot_session_trend

# =============================================================================
# Helper - Chargement des stats coéquipiers depuis leurs propres DBs
# =============================================================================


def _load_teammate_stats_from_own_db(
    teammate_gamertag: str,
    match_ids: set[str],
    reference_db_path: str,
) -> pd.DataFrame:
    """Charge les stats d'un coéquipier depuis sa propre DB si disponible.

    Dans l'architecture DuckDB v4, chaque joueur a sa propre DB :
    data/players/{gamertag}/stats.duckdb

    Pour afficher les stats d'un coéquipier sur des matchs communs,
    on doit aller chercher dans SA DB, pas dans celle du joueur principal.

    Args:
        teammate_gamertag: Gamertag du coéquipier.
        match_ids: Set des match_id à filtrer.
        reference_db_path: Chemin vers la DB de référence (pour déduire le dossier parent).

    Returns:
        DataFrame des stats du coéquipier (filtré sur match_ids), ou vide si DB non trouvée.
    """
    from pathlib import Path

    # Construire le chemin vers la DB du coéquipier
    # reference_db_path = data/players/{mon_gamertag}/stats.duckdb
    # On veut : data/players/{teammate_gamertag}/stats.duckdb
    base_dir = Path(reference_db_path).parent.parent  # Remonter de {gamertag}/stats.duckdb
    teammate_db_path = base_dir / teammate_gamertag / "stats.duckdb"

    if not teammate_db_path.exists():
        return pd.DataFrame()

    try:
        import polars as pl

        # Charger depuis la DB du coéquipier (retourne Polars maintenant)
        df_pl = load_df_optimized(str(teammate_db_path), "", db_key=None)
        if df_pl.is_empty():
            return pd.DataFrame()

        # Filtrer avec Polars puis convertir en Pandas pour compatibilité
        df_filtered = df_pl.filter(
            pl.col("match_id").cast(pl.Utf8).is_in([str(mid) for mid in match_ids])
        )
        return df_filtered.to_pandas()
    except Exception:
        return pd.DataFrame()


# =============================================================================
# Enrichissement Perfect Kills (médailles) pour graphes de barres
# =============================================================================


def _enrich_series_with_perfect_kills(
    series: list[tuple[str, pd.DataFrame]],
    db_path: str,
) -> list[tuple[str, pd.DataFrame]]:
    """Ajoute la colonne perfect_kills à chaque DataFrame de la série.

    Le 1er élément (idx=0) = joueur principal (utilise db_path).
    Les suivants = coéquipiers (utilise base_dir / gamertag / stats.duckdb).
    """
    from pathlib import Path

    from src.data.repositories.duckdb_repo import DuckDBRepository

    if not db_path or not str(db_path).endswith(".duckdb"):
        return series

    base_dir = Path(db_path).parent.parent
    enriched = []
    for idx, (name, df) in enumerate(series):
        df = df.copy()
        if "match_id" in df.columns and not df.empty:
            match_ids = df["match_id"].astype(str).tolist()
            try:
                if idx == 0:
                    use_path = db_path
                else:
                    player_db = base_dir / name / "stats.duckdb"
                    use_path = str(player_db) if player_db.exists() else db_path
                repo = DuckDBRepository(use_path, "")
                counts = repo.count_perfect_kills_by_match(match_ids)
                df["perfect_kills"] = df["match_id"].astype(str).map(counts).fillna(0).astype(int)
            except Exception:
                df["perfect_kills"] = 0
        else:
            df["perfect_kills"] = 0
        enriched.append((name, df))
    return enriched


# =============================================================================
# Radar de complémentarité (profil participation 6 axes)
# =============================================================================


def _render_synergy_radar(
    sub: pd.DataFrame,
    friend_sub: pd.DataFrame,
    me_name: str,
    friend_name: str,
    colors_by_name: dict[str, str],
    *,
    db_path: str | None = None,
    xuid: str | None = None,
    friend_xuid: str | None = None,
) -> None:
    """Affiche le radar de complémentarité (6 axes) entre moi et un coéquipier.

    Objectifs, Combat, Support, Score, Impact, Survie.
    Utilise PersonalScores depuis ma DB et la DB du coéquipier.

    Args:
        sub: DataFrame de mes matchs.
        friend_sub: DataFrame des matchs du coéquipier.
        me_name: Mon nom.
        friend_name: Nom (gamertag) du coéquipier.
        colors_by_name: Mapping nom → couleur.
        db_path: Chemin vers ma DB.
        xuid: Mon XUID.
        friend_xuid: XUID du coéquipier (non utilisé pour le chargement).
    """
    if sub.empty or friend_sub.empty:
        return

    if db_path is None:
        db_path = st.session_state.get("db_path", "")
    if xuid is None:
        xuid = st.session_state.get("xuid", "")

    shared_match_ids = list(
        set(sub["match_id"].astype(str)) & set(friend_sub["match_id"].astype(str))
    )
    if not shared_match_ids:
        return

    from pathlib import Path

    from src.data.repositories import DuckDBRepository
    from src.ui.components.radar_chart import create_participation_profile_radar
    from src.visualization.participation_radar import (
        RADAR_AXIS_LINES,
        compute_participation_profile,
        get_radar_thresholds,
    )

    profiles = []

    thresholds = get_radar_thresholds(db_path) if db_path else None

    # Mon profil
    try:
        repo = DuckDBRepository(db_path, xuid or "")
        if repo.has_personal_score_awards():
            my_ps = repo.load_personal_score_awards_as_polars(match_ids=shared_match_ids)
            if not my_ps.is_empty():
                match_row_me = {
                    "deaths": int(sub["deaths"].sum()) if "deaths" in sub.columns else 0,
                    "time_played_seconds": float(sub["time_played_seconds"].sum())
                    if "time_played_seconds" in sub.columns
                    else 600.0 * len(sub),
                    "pair_name": sub["pair_name"].iloc[0]
                    if "pair_name" in sub.columns and len(sub) > 0
                    else None,
                }
                profile_me = compute_participation_profile(
                    my_ps,
                    match_row=match_row_me,
                    name=me_name,
                    color=colors_by_name.get(me_name, "#636EFA"),
                    pair_name=match_row_me.get("pair_name"),
                    thresholds=thresholds,
                )
                profiles.append(profile_me)
    except Exception:
        pass

    # Profil du coéquipier (depuis sa DB)
    base_dir = Path(db_path).parent.parent
    friend_db_path = base_dir / friend_name / "stats.duckdb"
    if friend_db_path.exists():
        try:
            friend_repo = DuckDBRepository(str(friend_db_path), "")
            if friend_repo.has_personal_score_awards():
                friend_ps = friend_repo.load_personal_score_awards_as_polars(
                    match_ids=shared_match_ids
                )
                if not friend_ps.is_empty():
                    match_row_fr = {
                        "deaths": int(friend_sub["deaths"].sum())
                        if "deaths" in friend_sub.columns
                        else 0,
                        "time_played_seconds": float(friend_sub["time_played_seconds"].sum())
                        if "time_played_seconds" in friend_sub.columns
                        else 600.0 * len(friend_sub),
                        "pair_name": friend_sub["pair_name"].iloc[0]
                        if "pair_name" in friend_sub.columns and len(friend_sub) > 0
                        else None,
                    }
                    profile_fr = compute_participation_profile(
                        friend_ps,
                        match_row=match_row_fr,
                        name=friend_name,
                        color=colors_by_name.get(friend_name, "#EF553B"),
                        pair_name=match_row_fr.get("pair_name"),
                        thresholds=thresholds,
                    )
                    profiles.append(profile_fr)
        except Exception:
            pass

    if not profiles:
        st.subheader("🤝 Complémentarité")
        st.info("Données de participation indisponibles (PersonalScores manquants).")
        return

    st.subheader("🤝 Complémentarité")
    col_radar, col_legend = st.columns([2, 1])
    with col_radar:
        fig = create_participation_profile_radar(
            profiles,
            title="Profil de participation",
            height=380,
        )
        st.plotly_chart(fig, width="stretch")
    with col_legend:
        st.markdown("**Axes**")
        for line in RADAR_AXIS_LINES:
            st.markdown(line)


# =============================================================================
# Radar de complémentarité trio (profil participation 6 axes, 3 joueurs)
# =============================================================================


def _render_trio_synergy_radar(
    me_df: pd.DataFrame,
    f1_df: pd.DataFrame,
    f2_df: pd.DataFrame,
    me_name: str,
    f1_name: str,
    f2_name: str,
    colors_by_name: dict[str, str],
    *,
    db_path: str | None = None,
) -> None:
    """Radar complémentarité trio (6 axes) : moi + 2 coéquipiers.

    Réutilise compute_participation_profile et create_participation_profile_radar.
    """
    if me_df.empty:
        return

    if db_path is None:
        db_path = st.session_state.get("db_path", "")

    shared_match_ids = list(
        set(me_df["match_id"].astype(str))
        & set(f1_df["match_id"].astype(str))
        & set(f2_df["match_id"].astype(str))
    )
    if not shared_match_ids:
        return

    from pathlib import Path

    from src.data.repositories import DuckDBRepository
    from src.ui.components.radar_chart import create_participation_profile_radar
    from src.visualization.participation_radar import (
        RADAR_AXIS_LINES,
        compute_participation_profile,
        get_radar_thresholds,
    )

    thresholds = get_radar_thresholds(db_path) if db_path else None
    base_dir = Path(db_path).parent.parent
    profiles: list[dict] = []

    players = [
        (me_name, me_df, db_path, colors_by_name.get(me_name, "#636EFA")),
        (
            f1_name,
            f1_df,
            str(base_dir / f1_name / "stats.duckdb"),
            colors_by_name.get(f1_name, "#EF553B"),
        ),
        (
            f2_name,
            f2_df,
            str(base_dir / f2_name / "stats.duckdb"),
            colors_by_name.get(f2_name, "#00CC96"),
        ),
    ]

    for name, df_player, player_db, color in players:
        if df_player.empty or not Path(player_db).exists():
            continue
        try:
            repo = DuckDBRepository(player_db, "")
            if repo.has_personal_score_awards():
                ps = repo.load_personal_score_awards_as_polars(match_ids=shared_match_ids)
                if not ps.is_empty():
                    match_row = {
                        "deaths": int(df_player["deaths"].sum())
                        if "deaths" in df_player.columns
                        else 0,
                        "time_played_seconds": float(df_player["time_played_seconds"].sum())
                        if "time_played_seconds" in df_player.columns
                        else 600.0 * len(df_player),
                        "pair_name": df_player["pair_name"].iloc[0]
                        if "pair_name" in df_player.columns and len(df_player) > 0
                        else None,
                    }
                    profile = compute_participation_profile(
                        ps,
                        match_row=match_row,
                        name=name,
                        color=color,
                        pair_name=match_row.get("pair_name"),
                        thresholds=thresholds,
                    )
                    profiles.append(profile)
        except Exception:
            pass

    if not profiles:
        st.subheader("Complémentarité trio")
        st.info("Données de participation indisponibles (PersonalScores manquants).")
        return

    st.subheader("Complémentarité trio")
    col_radar, col_legend = st.columns([2, 1])
    with col_radar:
        fig = create_participation_profile_radar(
            profiles,
            title="Profil de participation",
            height=380,
        )
        st.plotly_chart(fig, width="stretch")
    with col_legend:
        st.markdown("**Axes**")
        for line in RADAR_AXIS_LINES:
            st.markdown(line)


# =============================================================================
# Sprint 12 — Impact & Taquinerie
# =============================================================================


def _render_impact_taquinerie(
    db_path: str,
    xuid: str,
    match_ids: list[str],
    friend_xuids: list[str],
    db_key: tuple[int, int] | None = None,
) -> None:
    """Affiche l'onglet Impact & Taquinerie (Sprint 12).

    Heatmap des événements clés + tableau de ranking "MVP/Boulet".

    Args:
        db_path: Chemin vers la DB principale.
        xuid: XUID du joueur principal.
        match_ids: Liste des match_id à analyser.
        friend_xuids: Liste des XUIDs des coéquipiers sélectionnés.
        db_key: Clé de cache (optionnel).
    """

    from src.data.repositories import DuckDBRepository

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
            # Charger les événements highlight depuis la DB du joueur
            repo = DuckDBRepository(db_path, xuid.strip())

            # Vérifier si highlight_events existe
            conn = repo._get_connection()
            has_events_table = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_name = 'highlight_events'"
            ).fetchone()

            if not has_events_table:
                st.info(
                    "Les données d'événements (highlight_events) ne sont pas disponibles. "
                    "Cette fonctionnalité nécessite une synchronisation avec les détails de matchs."
                )
                return

            # Charger les événements
            events_query = """
                SELECT match_id, xuid::TEXT as xuid, gamertag, event_type, time_ms
                FROM highlight_events
                WHERE match_id IN ({})
            """.format(", ".join(["?" for _ in match_ids]))

            events_result = conn.execute(events_query, match_ids).fetchall()

            if not events_result:
                st.info("Aucun événement trouvé pour les matchs sélectionnés.")
                return

            events_df = pl.DataFrame(
                {
                    "match_id": [str(r[0]) for r in events_result],
                    "xuid": [str(r[1]) for r in events_result],
                    "gamertag": [r[2] or "Unknown" for r in events_result],
                    "event_type": [r[3] for r in events_result],
                    "time_ms": [int(r[4] or 0) for r in events_result],
                }
            )

            # Charger les outcomes des matchs
            matches_query = """
                SELECT match_id, outcome
                FROM match_stats
                WHERE match_id IN ({})
            """.format(", ".join(["?" for _ in match_ids]))

            matches_result = conn.execute(matches_query, match_ids).fetchall()

            matches_df = pl.DataFrame(
                {
                    "match_id": [str(r[0]) for r in matches_result],
                    "outcome": [int(r[1] or 0) for r in matches_result],
                }
            )

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

            # Obtenir les gamertags des joueurs avec des événements
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
                match_ids=sorted_match_ids[:50],  # Limiter à 50 matchs
                gamertags=gamertags,
            )

            # Afficher les stats résumées
            stats = render_impact_summary_stats(first_bloods, clutch_finishers, last_casualties)
            cols = st.columns(4)
            cols[0].metric("🟢 Premier Sang", stats["total_fb"])
            cols[1].metric("🟡 Finisseur", stats["total_clutch"])
            cols[2].metric("🔴 Boulet", stats["total_casualty"])
            cols[3].metric("📊 Matchs analysés", stats["total_matches"])

            # Afficher la heatmap
            st.subheader("Heatmap d'Impact")
            fig = plot_friends_impact_heatmap(
                impact_matrix,
                title=None,
                max_matches=50,
            )
            st.plotly_chart(fig, width="stretch")

            # Afficher le tableau de ranking
            st.subheader("🏆 Classement Taquinerie")
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
                # Convertir en Pandas pour Streamlit
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

                # MVP et Boulet du groupe
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

        except Exception as e:
            st.warning(f"Impossible de charger les données d'impact : {e}")


def render_teammates_page(
    df: pd.DataFrame,
    dff: pd.DataFrame,
    base: pd.DataFrame,
    me_name: str,
    xuid: str,
    db_path: str,
    db_key: tuple[int, int] | None,
    aliases_key: int | None,
    settings: object,
    picked_session_labels: list[str] | None,
    include_firefight: bool,
    waypoint_player: str,
    build_friends_opts_map_fn,
    assign_player_colors_fn,
    plot_multi_metric_bars_fn,
    top_medals_fn,
) -> None:
    """Affiche la page Mes coéquipiers.

    Args:
        df: DataFrame complet des matchs.
        dff: DataFrame filtré des matchs.
        base: DataFrame de base (après filtres Firefight).
        me_name: Nom affiché du joueur.
        xuid: XUID du joueur.
        db_path: Chemin vers la base de données.
        db_key: Clé de cache de la DB.
        aliases_key: Clé de cache des alias.
        settings: Paramètres de l'application.
        picked_session_labels: Labels des sessions sélectionnées.
        include_firefight: Inclure Firefight dans les stats.
        waypoint_player: Nom Waypoint du joueur.
        build_friends_opts_map_fn: Fonction pour construire la map des coéquipiers.
        assign_player_colors_fn: Fonction pour assigner les couleurs aux joueurs.
        plot_multi_metric_bars_fn: Fonction pour tracer les barres multi-métriques.
        top_medals_fn: Fonction pour récupérer les top médailles.
    """
    # Protection contre les DataFrames vides
    if dff.empty:
        st.warning("Aucun match à afficher. Vérifiez vos filtres ou synchronisez les données.")
        return

    # Vérification du cache pour performance
    if not st.session_state.get("_cache_warning_shown"):
        has_cache = cached_has_cache_tables(db_path, db_key)
        if not has_cache:
            st.warning(
                "⚠️ **Performance** : Les tables de cache ne sont pas initialisées. "
                "Le chargement sera plus lent. Exécutez `python scripts/migrate_to_cache.py` "
                "pour accélérer significativement cette page.",
                icon="⚠️",
            )
            st.session_state["_cache_warning_shown"] = True

    apply_current_filters_teammates = st.toggle(
        "Appliquer les filtres actuels (période/sessions + map/playlist)",
        value=True,
        key="apply_current_filters_teammates",
    )
    same_team_only_teammates = st.checkbox(
        "Même équipe", value=True, key="teammates_same_team_only"
    )

    show_smooth_teammates = st.toggle(
        "Afficher les courbes lissées",
        value=bool(st.session_state.get("teammates_show_smooth", True)),
        key="teammates_show_smooth",
        help="Active/désactive les courbes de moyenne lissée sur les graphes de cette section.",
    )

    with perf_section("teammates/build_friends_opts_map"):
        opts_map, default_labels = build_friends_opts_map_fn(
            db_path, xuid.strip(), db_key, aliases_key
        )
    picked_labels = st.multiselect(
        "Coéquipiers",
        options=list(opts_map.keys()),
        default=default_labels,
        key="teammates_picked_labels",
    )
    picked_xuids = [opts_map[lbl] for lbl in picked_labels if lbl in opts_map]

    # Afficher les Spartan ID cards des coéquipiers sélectionnés en grille 2 colonnes
    with perf_section("teammates/render_cards"):
        render_teammate_cards(picked_xuids, settings)

    # Tendance de session (matchs affichés) - Sprint 6
    _req_trend = ["start_time", "kills", "deaths"]
    if len(dff) >= 4 and all(c in dff.columns for c in _req_trend):
        try:
            pl_dff = pl.from_pandas(dff.sort_values("start_time")[_req_trend].copy())
            st.subheader("Tendance de session (matchs affichés)")
            st.caption("Compare ta performance en première vs seconde moitié des matchs affichés.")
            st.plotly_chart(plot_session_trend(pl_dff), width="stretch")
        except Exception:
            pass

    if len(picked_xuids) < 1:
        st.info("Sélectionne au moins un coéquipier.")
    elif len(picked_xuids) == 1:
        _render_single_teammate_view(
            df=df,
            dff=dff,
            me_name=me_name,
            xuid=xuid,
            db_path=db_path,
            db_key=db_key,
            picked_xuids=picked_xuids,
            apply_current_filters=apply_current_filters_teammates,
            same_team_only=same_team_only_teammates,
            show_smooth=show_smooth_teammates,
            assign_player_colors_fn=assign_player_colors_fn,
            plot_multi_metric_bars_fn=plot_multi_metric_bars_fn,
            top_medals_fn=top_medals_fn,
        )
    else:
        _render_multi_teammate_view(
            df=df,
            dff=dff,
            base=base,
            me_name=me_name,
            xuid=xuid,
            db_path=db_path,
            db_key=db_key,
            aliases_key=aliases_key,
            picked_xuids=picked_xuids,
            picked_session_labels=picked_session_labels,
            apply_current_filters=apply_current_filters_teammates,
            same_team_only=same_team_only_teammates,
            show_smooth=show_smooth_teammates,
            include_firefight=include_firefight,
            waypoint_player=waypoint_player,
            assign_player_colors_fn=assign_player_colors_fn,
            plot_multi_metric_bars_fn=plot_multi_metric_bars_fn,
            top_medals_fn=top_medals_fn,
        )


def _render_single_teammate_view(
    df: pd.DataFrame,
    dff: pd.DataFrame,
    me_name: str,
    xuid: str,
    db_path: str,
    db_key: tuple[int, int] | None,
    picked_xuids: list[str],
    apply_current_filters: bool,
    same_team_only: bool,
    show_smooth: bool,
    assign_player_colors_fn,
    plot_multi_metric_bars_fn,
    top_medals_fn,
) -> None:
    """Vue pour un seul coéquipier sélectionné."""
    friend_xuid = picked_xuids[0]
    with st.spinner("Chargement des matchs avec ce coéquipier…"):
        dfr = cached_friend_matches_df(
            db_path,
            xuid.strip(),
            friend_xuid,
            same_team_only=bool(same_team_only),
            db_key=db_key,
        )
        if dfr.empty:
            st.warning("Aucun match trouvé avec ce coéquipier (selon le filtre).")
            return

        render_outcome_bar_chart(dfr)

        with st.expander("Détails des matchs (joueur vs joueur)", expanded=False):
            st.dataframe(
                dfr[
                    [
                        "start_time",
                        "playlist_name",
                        "pair_name",
                        "same_team",
                        "my_team_id",
                        "my_outcome",
                        "friend_team_id",
                        "friend_outcome",
                        "match_id",
                    ]
                ].reset_index(drop=True),
                width="stretch",
                hide_index=True,
            )

        base_for_friend = dff if apply_current_filters else df
        shared_ids = set(dfr["match_id"].astype(str))
        sub = base_for_friend.loc[base_for_friend["match_id"].astype(str).isin(shared_ids)].copy()

        if sub.empty:
            st.info(
                "Aucun match à afficher avec les filtres actuels (période/sessions + map/playlist)."
            )
            return

        name = display_name_from_xuid(friend_xuid)

        rates_sub = compute_outcome_rates(sub)
        total_out = max(1, rates_sub.total)
        win_rate_sub = rates_sub.wins / total_out
        loss_rate_sub = rates_sub.losses / total_out
        global_ratio_sub = compute_global_ratio(sub)

        k = st.columns(3)
        k[0].metric("Matchs", f"{len(sub)}")
        k[1].metric("Win/Loss", f"{win_rate_sub*100:.1f}% / {loss_rate_sub*100:.1f}%")
        k[2].metric(
            "Ratio global", f"{global_ratio_sub:.2f}" if global_ratio_sub is not None else "-"
        )

        stats_sub = compute_aggregated_stats(sub)
        per_min = st.columns(3)
        per_min[0].metric(
            "Frags / min",
            f"{stats_sub.kills_per_minute:.2f}" if stats_sub.kills_per_minute else "-",
        )
        per_min[1].metric(
            "Morts / min",
            f"{stats_sub.deaths_per_minute:.2f}" if stats_sub.deaths_per_minute else "-",
        )
        per_min[2].metric(
            "Assistances / min",
            f"{stats_sub.assists_per_minute:.2f}" if stats_sub.assists_per_minute else "-",
        )

        # Charger les stats du coéquipier depuis SA propre DB
        friend_sub = _load_teammate_stats_from_own_db(name, shared_ids, db_path)

        # Graphes côte à côte
        render_comparison_charts(
            sub=sub,
            friend_sub=friend_sub,
            me_name=me_name,
            friend_name=name,
            friend_xuid=friend_xuid,
            show_smooth=show_smooth,
        )

        # Graphes de barres (folie meurtrière, headshots)
        series = [(me_name, sub)]
        if not friend_sub.empty:
            series.append((name, friend_sub))
        colors_by_name = assign_player_colors_fn([n for n, _ in series])
        series = _enrich_series_with_perfect_kills(series, db_path)

        render_metric_bar_charts(
            series=series,
            colors_by_name=colors_by_name,
            show_smooth=show_smooth,
            key_suffix=friend_xuid,
            plot_fn=plot_multi_metric_bars_fn,
        )

        # Radar de complémentarité (Sprint 8.2)
        _render_synergy_radar(
            sub=sub,
            friend_sub=friend_sub,
            me_name=me_name,
            friend_name=name,
            colors_by_name=colors_by_name,
        )

        # Médailles
        st.subheader("Médailles (matchs partagés)")
        shared_list = sorted({str(x) for x in shared_ids if str(x).strip()})
        if not shared_list:
            st.info("Aucun match partagé pour calculer les médailles.")
        else:
            with st.spinner("Agrégation des médailles (moi + coéquipier)…"):
                my_top = top_medals_fn(db_path, xuid.strip(), shared_list, top_n=12, db_key=db_key)
                fr_top = top_medals_fn(db_path, friend_xuid, shared_list, top_n=12, db_key=db_key)

            m1, m2 = st.columns(2)
            with m1:
                st.caption(f"{me_name}")
                render_medals_grid(
                    [{"name_id": int(n), "count": int(c)} for n, c in (my_top or [])],
                    cols_per_row=6,
                )
            with m2:
                st.caption(f"{name}")
                render_medals_grid(
                    [{"name_id": int(n), "count": int(c)} for n, c in (fr_top or [])],
                    cols_per_row=6,
                )


def _render_multi_teammate_view(
    df: pd.DataFrame,
    dff: pd.DataFrame,
    base: pd.DataFrame,
    me_name: str,
    xuid: str,
    db_path: str,
    db_key: tuple[int, int] | None,
    aliases_key: int | None,
    picked_xuids: list[str],
    picked_session_labels: list[str] | None,
    apply_current_filters: bool,
    same_team_only: bool,
    show_smooth: bool,
    include_firefight: bool,
    waypoint_player: str,
    assign_player_colors_fn,
    plot_multi_metric_bars_fn,
    top_medals_fn,
) -> None:
    """Vue pour plusieurs coéquipiers sélectionnés."""
    st.subheader("Par carte — avec mes coéquipiers")
    with st.spinner("Calcul du ratio par carte (coéquipiers)…"):
        current_mode = st.session_state.get("filter_mode")
        latest_session_label = st.session_state.get("_latest_session_label")
        trio_latest_label = st.session_state.get("_trio_latest_session_label")

        selected_session = None
        if (
            current_mode == "Sessions"
            and isinstance(picked_session_labels, list)
            and len(picked_session_labels) == 1
        ):
            selected_session = picked_session_labels[0]

        is_last_session = bool(selected_session and selected_session == latest_session_label)
        is_last_trio_session = bool(
            selected_session
            and isinstance(trio_latest_label, str)
            and selected_session == trio_latest_label
        )

        if is_last_session or is_last_trio_session:
            last_applied = st.session_state.get("_friends_min_matches_last_session_label")
            if last_applied != selected_session:
                st.session_state["min_matches_maps_friends"] = 1
                st.session_state["_min_matches_maps_friends_auto"] = True
                st.session_state["_friends_min_matches_last_session_label"] = selected_session

        min_matches_maps_friends = st.slider(
            "Minimum de matchs par carte",
            1,
            30,
            1,
            step=1,
            key="min_matches_maps_friends",
            on_change=_clear_min_matches_maps_friends_auto,
        )

        base_for_friends_all = dff if apply_current_filters else df
        all_match_ids: set[str] = set()
        per_friend_ids: dict[str, set[str]] = {}
        for fx in picked_xuids:
            ids: set[str] = set()
            if bool(same_team_only):
                ids = {
                    str(x)
                    for x in cached_same_team_match_ids_with_friend(
                        db_path, xuid.strip(), fx, db_key=db_key
                    )
                }
            else:
                rows = cached_query_matches_with_friend(db_path, xuid.strip(), fx, db_key=db_key)
                ids = {str(r.match_id) for r in rows}
            per_friend_ids[str(fx)] = ids
            all_match_ids.update(ids)

        sub_all = base_for_friends_all.loc[
            base_for_friends_all["match_id"].astype(str).isin(all_match_ids)
        ].copy()

        use_xuids = picked_xuids

        series: list[tuple[str, pd.DataFrame]] = [(me_name, sub_all)]
        with st.spinner("Chargement des stats des coéquipiers…"):
            for fx in use_xuids:
                ids = per_friend_ids.get(str(fx), set())
                if not ids:
                    continue
                # Obtenir le gamertag et charger depuis la DB du coéquipier
                fx_gamertag = display_name_from_xuid(str(fx))
                ids_str = {str(x) for x in ids}
                fr_sub = _load_teammate_stats_from_own_db(fx_gamertag, ids_str, db_path)
                if fr_sub.empty:
                    continue
                series.append((fx_gamertag, fr_sub))
        colors_by_name = assign_player_colors_fn([n for n, _ in series])

        breakdown_all = compute_map_breakdown(sub_all)
        breakdown_all = breakdown_all.loc[
            breakdown_all["matches"] >= int(min_matches_maps_friends)
        ].copy()

        if breakdown_all.empty:
            st.info("Pas assez de matchs avec tes coéquipiers (selon le filtre actuel).")
        else:
            view_all = breakdown_all.head(20).iloc[::-1]
            title = f"Ratio global par carte — avec mes coéquipiers (min {min_matches_maps_friends} matchs)"
            st.plotly_chart(plot_map_ratio_with_winloss(view_all, title=title), width="stretch")

            st.subheader("Historique — matchs avec mes coéquipiers")

        if sub_all.empty:
            st.info("Aucun match trouvé avec tes coéquipiers (selon le filtre actuel).")
        else:
            render_friends_history_table(sub_all, db_path, xuid, db_key, waypoint_player)

        rendered_bottom_charts = False

    # Vue trio (moi + 2 coéquipiers)
    if len(picked_xuids) >= 2:
        rendered_bottom_charts = _render_trio_view(
            df=df,
            dff=dff,
            base=base,
            me_name=me_name,
            xuid=xuid,
            db_path=db_path,
            db_key=db_key,
            aliases_key=aliases_key,
            picked_xuids=picked_xuids,
            apply_current_filters=apply_current_filters,
            include_firefight=include_firefight,
            series=series,
            colors_by_name=colors_by_name,
            show_smooth=show_smooth,
            assign_player_colors_fn=assign_player_colors_fn,
            plot_multi_metric_bars_fn=plot_multi_metric_bars_fn,
            top_medals_fn=top_medals_fn,
        )

    # Sprint 12 - Impact & Taquinerie (si ≥2 amis sélectionnés)
    if len(picked_xuids) >= 2:
        # Utiliser tous les match_ids communs
        impact_match_ids = list(all_match_ids) if all_match_ids else []
        _render_impact_taquinerie(
            db_path=db_path,
            xuid=xuid,
            match_ids=impact_match_ids,
            friend_xuids=picked_xuids,
            db_key=db_key,
        )

    if not rendered_bottom_charts:
        series = _enrich_series_with_perfect_kills(series, db_path)
        render_metric_bar_charts(
            series=series,
            colors_by_name=colors_by_name,
            show_smooth=show_smooth,
            key_suffix=f"{len(series)}",
            plot_fn=plot_multi_metric_bars_fn,
        )


def _render_trio_view(
    df: pd.DataFrame,
    dff: pd.DataFrame,
    base: pd.DataFrame,
    me_name: str,
    xuid: str,
    db_path: str,
    db_key: tuple[int, int] | None,
    aliases_key: int | None,
    picked_xuids: list[str],
    apply_current_filters: bool,
    include_firefight: bool,
    series: list[tuple[str, pd.DataFrame]],
    colors_by_name: dict[str, str],
    show_smooth: bool,
    assign_player_colors_fn,
    plot_multi_metric_bars_fn,
    top_medals_fn,
) -> bool:
    """Affiche la vue trio (moi + 2 coéquipiers). Retourne True si les graphes du bas ont été rendus."""
    f1_xuid, f2_xuid = picked_xuids[0], picked_xuids[1]
    f1_name = display_name_from_xuid(f1_xuid)
    f2_name = display_name_from_xuid(f2_xuid)
    st.subheader(f"Tous les trois — {f1_name} + {f2_name}")

    ids_m = set(
        cached_same_team_match_ids_with_friend(db_path, xuid.strip(), f1_xuid, db_key=db_key)
    )
    ids_c = set(
        cached_same_team_match_ids_with_friend(db_path, xuid.strip(), f2_xuid, db_key=db_key)
    )
    trio_ids = ids_m & ids_c

    base_for_trio = dff if apply_current_filters else df
    trio_ids = trio_ids & set(base_for_trio["match_id"].astype(str))

    if not trio_ids:
        st.warning(
            "Aucun match trouvé où vous êtes tous les trois dans la même équipe (avec les filtres actuels)."
        )
        return False

    trio_ids_set = {str(x) for x in trio_ids}
    from src.app.filters import get_friends_xuids_for_sessions

    friends_tuple = get_friends_xuids_for_sessions(db_path, xuid.strip(), db_key, aliases_key)
    base_s_trio = cached_compute_sessions_db(
        db_path,
        xuid.strip(),
        db_key,
        include_firefight,
        120,  # gap figé
        friends_xuids=friends_tuple,
    )
    trio_rows = base_s_trio.loc[base_s_trio["match_id"].astype(str).isin(trio_ids_set)].copy()
    latest_label = None
    if not trio_rows.empty:
        latest_sid = int(trio_rows["session_id"].max())
        latest_labels = (
            trio_rows.loc[trio_rows["session_id"] == latest_sid, "session_label"]
            .dropna()
            .unique()
            .tolist()
        )
        latest_label = latest_labels[0] if latest_labels else None

    st.session_state["_trio_latest_session_label"] = latest_label
    if latest_label:
        st.caption(f"Dernière session trio détectée : {latest_label}.")
    else:
        st.caption("Impossible de déterminer une session trio (données insuffisantes).")

    me_df = base_for_trio.loc[base_for_trio["match_id"].isin(trio_ids)].copy()

    # Charger les stats des coéquipiers depuis LEURS propres DBs
    trio_ids_str = {str(x) for x in trio_ids}
    f1_df = _load_teammate_stats_from_own_db(f1_name, trio_ids_str, db_path)
    f2_df = _load_teammate_stats_from_own_db(f2_name, trio_ids_str, db_path)

    me_df = me_df.sort_values("start_time")

    me_stats = compute_aggregated_stats(me_df)
    f1_stats = compute_aggregated_stats(f1_df)
    f2_stats = compute_aggregated_stats(f2_df)
    st.subheader("Stats par minute")

    import plotly.graph_objects as go

    from src.visualization.theme import apply_halo_plot_style

    _pm_metrics = ["Frags/min", "Morts/min", "Assists/min"]
    _pm_players = [
        (me_name, me_stats, colors_by_name.get(me_name, "#636EFA")),
        (f1_name, f1_stats, colors_by_name.get(f1_name, "#EF553B")),
        (f2_name, f2_stats, colors_by_name.get(f2_name, "#00CC96")),
    ]
    fig_pm = go.Figure()
    for _pm_name, _pm_st, _pm_color in _pm_players:
        _pm_vals = [
            round(float(_pm_st.kills_per_minute), 2) if _pm_st.kills_per_minute else 0,
            round(float(_pm_st.deaths_per_minute), 2) if _pm_st.deaths_per_minute else 0,
            round(float(_pm_st.assists_per_minute), 2) if _pm_st.assists_per_minute else 0,
        ]
        fig_pm.add_trace(
            go.Bar(
                name=_pm_name,
                x=_pm_metrics,
                y=_pm_vals,
                marker_color=_pm_color,
                text=[f"{v:.2f}" for v in _pm_vals],
                textposition="auto",
            )
        )
    fig_pm.update_layout(
        barmode="group",
        height=350,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0.5, "xanchor": "center"},
    )
    fig_pm = apply_halo_plot_style(fig_pm, title=None, height=None)
    st.plotly_chart(fig_pm, width="stretch")

    # Radar de complémentarité trio (6 axes)
    _render_trio_synergy_radar(
        me_df=me_df,
        f1_df=f1_df,
        f2_df=f2_df,
        me_name=me_name,
        f1_name=f1_name,
        f2_name=f2_name,
        colors_by_name=colors_by_name,
        db_path=db_path,
    )

    f1_df = f1_df[
        ["match_id", "kills", "deaths", "assists", "accuracy", "ratio", "average_life_seconds"]
    ].copy()
    f2_df = f2_df[
        ["match_id", "kills", "deaths", "assists", "accuracy", "ratio", "average_life_seconds"]
    ].copy()
    merged = (
        me_df[
            [
                "match_id",
                "start_time",
                "kills",
                "deaths",
                "assists",
                "accuracy",
                "ratio",
                "average_life_seconds",
                "time_played_seconds",
            ]
        ]
        .merge(f1_df.add_prefix("f1_"), left_on="match_id", right_on="f1_match_id", how="inner")
        .merge(f2_df.add_prefix("f2_"), left_on="match_id", right_on="f2_match_id", how="inner")
    )
    if merged.empty:
        st.warning("Impossible d'aligner les stats des 3 joueurs sur ces matchs.")
        return False

    from src.analysis.performance_score import compute_performance_series

    merged = merged.sort_values("start_time")
    d_self = merged[
        [
            "start_time",
            "kills",
            "deaths",
            "assists",
            "ratio",
            "accuracy",
            "average_life_seconds",
            "time_played_seconds",
        ]
    ].copy()
    d_f1 = merged[
        [
            "start_time",
            "f1_kills",
            "f1_deaths",
            "f1_assists",
            "f1_ratio",
            "f1_accuracy",
            "f1_average_life_seconds",
            "time_played_seconds",
        ]
    ].rename(
        columns={
            "f1_kills": "kills",
            "f1_deaths": "deaths",
            "f1_assists": "assists",
            "f1_ratio": "ratio",
            "f1_accuracy": "accuracy",
            "f1_average_life_seconds": "average_life_seconds",
        }
    )
    d_f2 = merged[
        [
            "start_time",
            "f2_kills",
            "f2_deaths",
            "f2_assists",
            "f2_ratio",
            "f2_accuracy",
            "f2_average_life_seconds",
            "time_played_seconds",
        ]
    ].rename(
        columns={
            "f2_kills": "kills",
            "f2_deaths": "deaths",
            "f2_assists": "assists",
            "f2_ratio": "ratio",
            "f2_accuracy": "accuracy",
            "f2_average_life_seconds": "average_life_seconds",
        }
    )

    # Calculer les scores de performance RELATIF pour les 3 joueurs
    d_self["performance"] = compute_performance_series(d_self, d_self)
    d_f1["performance"] = compute_performance_series(d_f1, d_f1)
    d_f2["performance"] = compute_performance_series(d_f2, d_f2)

    render_trio_charts(d_self, d_f1, d_f2, me_name, f1_name, f2_name, f1_xuid, f2_xuid)

    # Graphes de barres
    series = _enrich_series_with_perfect_kills(series, db_path)
    render_metric_bar_charts(
        series=series,
        colors_by_name=colors_by_name,
        show_smooth=show_smooth,
        key_suffix=f"{len(series)}",
        plot_fn=plot_multi_metric_bars_fn,
    )

    # Médailles
    st.subheader("Médailles")
    trio_match_ids = [str(x) for x in merged["match_id"].dropna().astype(str).tolist()]
    if not trio_match_ids:
        st.info("Impossible de déterminer la liste des matchs pour l'agrégation des médailles.")
    else:
        with st.spinner("Agrégation des médailles…"):
            top_self = top_medals_fn(db_path, xuid.strip(), trio_match_ids, top_n=12, db_key=db_key)
            top_f1 = top_medals_fn(db_path, f1_xuid, trio_match_ids, top_n=12, db_key=db_key)
            top_f2 = top_medals_fn(db_path, f2_xuid, trio_match_ids, top_n=12, db_key=db_key)

        c1, c2, c3 = st.columns(3)
        with c1, st.expander(f"{me_name}", expanded=True):
            render_medals_grid(
                [{"name_id": int(n), "count": int(c)} for n, c in (top_self or [])],
                cols_per_row=6,
            )
        with c2, st.expander(f"{f1_name}", expanded=True):
            render_medals_grid(
                [{"name_id": int(n), "count": int(c)} for n, c in (top_f1 or [])],
                cols_per_row=6,
            )
        with c3, st.expander(f"{f2_name}", expanded=True):
            render_medals_grid(
                [{"name_id": int(n), "count": int(c)} for n, c in (top_f2 or [])],
                cols_per_row=6,
            )

    return True
