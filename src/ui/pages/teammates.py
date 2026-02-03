"""Page Mes coéquipiers.

Analyse des statistiques avec les coéquipiers fréquents.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.analysis import (
    compute_aggregated_stats,
    compute_global_ratio,
    compute_map_breakdown,
    compute_outcome_rates,
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

# =============================================================================
# Helpers Sprint 8.2 - Radar de complémentarité
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
    """Affiche le radar de complémentarité entre moi et un coéquipier.

    Montre le profil de jeu (% kills, % assists, % objectifs, K/D, précision).
    Utilise les PersonalScores si disponibles pour les % objectifs.

    Args:
        sub: DataFrame de mes matchs.
        friend_sub: DataFrame des matchs du coéquipier.
        me_name: Mon nom.
        friend_name: Nom du coéquipier.
        colors_by_name: Mapping nom → couleur.
        db_path: Chemin vers la DB (pour PersonalScores).
        xuid: Mon XUID (pour PersonalScores).
        friend_xuid: XUID du coéquipier (pour PersonalScores).
    """
    if sub.empty or friend_sub.empty:
        return

    from src.ui.components.radar_chart import create_teammate_synergy_radar

    # Récupérer db_path et xuid depuis session_state si non fournis
    if db_path is None:
        db_path = st.session_state.get("db_path", "")
    if xuid is None:
        xuid = st.session_state.get("xuid", "")

    # Obtenir les match_ids partagés
    shared_match_ids = list(set(sub["match_id"].tolist()) & set(friend_sub["match_id"].tolist()))

    # Essayer de charger les PersonalScores pour les % objectifs
    my_obj_pct = 0.0
    friend_obj_pct = 0.0

    if db_path and xuid and shared_match_ids:
        try:
            from src.data.repositories import DuckDBRepository
            from src.visualization import compute_participation_percentages

            repo = DuckDBRepository(db_path, xuid)
            if repo.has_personal_score_awards():
                # Mes données
                my_ps = repo.load_personal_score_awards_as_polars(match_ids=shared_match_ids)
                if not my_ps.is_empty():
                    my_pcts = compute_participation_percentages(my_ps)
                    my_obj_pct = my_pcts.get("objectives_pct", 0)

                # Données du coéquipier (si on a son XUID et qu'il est dans la même DB)
                # Note: Les PersonalScores du coéquipier ne sont pas stockés dans notre DB
                # On garde 0 pour lui sauf si on a une autre source
        except Exception:
            pass

    # Calculer les stats agrégées pour chaque joueur
    def compute_profile(df: pd.DataFrame, obj_pct: float = 0.0) -> dict:
        total_kills = df["kills"].sum()
        total_deaths = df["deaths"].sum()
        total_assists = df["assists"].sum()
        total_actions = total_kills + total_assists

        return {
            "kills_pct": (total_kills / total_actions * 100) if total_actions > 0 else 0,
            "assists_pct": (total_assists / total_actions * 100) if total_actions > 0 else 0,
            "objectives_pct": obj_pct,
            "kd_ratio": total_kills / max(total_deaths, 1),
            "accuracy": df["accuracy"].mean() if "accuracy" in df.columns else 0,
        }

    my_profile = compute_profile(sub, my_obj_pct)
    my_profile["name"] = me_name
    my_profile["color"] = colors_by_name.get(me_name, "#636EFA")

    friend_profile = compute_profile(friend_sub, friend_obj_pct)
    friend_profile["name"] = friend_name
    friend_profile["color"] = colors_by_name.get(friend_name, "#EF553B")

    st.subheader("🤝 Complémentarité")

    # Afficher le radar
    fig = create_teammate_synergy_radar(
        me_data=my_profile,
        teammate_data=friend_profile,
        title="",
        height=350,
    )
    st.plotly_chart(fig, width="stretch")

    # Analyse textuelle de la complémentarité
    my_kills_pct = my_profile["kills_pct"]
    friend_kills_pct = friend_profile["kills_pct"]

    analysis_parts = []

    if abs(my_kills_pct - friend_kills_pct) > 20:
        if my_kills_pct > friend_kills_pct:
            analysis_parts.append(f"Tu es plus orienté frags, {friend_name} supporte davantage")
        else:
            analysis_parts.append(f"{friend_name} est plus orienté frags, tu supportes davantage")
    else:
        analysis_parts.append("Vous avez un style de jeu comparable")

    if my_obj_pct > 10:
        analysis_parts.append(f"Tu contribues {my_obj_pct:.0f}% aux objectifs")

    st.caption(f"💡 **Profil** : {'. '.join(analysis_parts)}.")


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

        friend_df = load_df_optimized(db_path, friend_xuid, db_key=db_key)
        friend_sub = friend_df.loc[friend_df["match_id"].astype(str).isin(shared_ids)].copy()

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
                try:
                    fr_df = load_df_optimized(db_path, str(fx), db_key=db_key)
                except Exception:
                    continue
                fr_sub = fr_df.loc[fr_df["match_id"].astype(str).isin(ids)].copy()
                if fr_sub.empty:
                    continue
                series.append((display_name_from_xuid(str(fx)), fr_sub))
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

    if not rendered_bottom_charts:
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
    try:
        gm = int(st.session_state.get("gap_minutes", 120))
    except Exception:
        gm = 120
    base_s_trio = cached_compute_sessions_db(
        db_path,
        xuid.strip(),
        db_key,
        include_firefight,
        gm,
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
        st.caption(f"Dernière session trio détectée : {latest_label} (gap {gm} min).")
    else:
        st.caption("Impossible de déterminer une session trio (données insuffisantes).")

    me_df = base_for_trio.loc[base_for_trio["match_id"].isin(trio_ids)].copy()
    f1_df = load_df_optimized(db_path, f1_xuid, db_key=db_key)
    f2_df = load_df_optimized(db_path, f2_xuid, db_key=db_key)
    f1_df = f1_df.loc[f1_df["match_id"].isin(trio_ids)].copy()
    f2_df = f2_df.loc[f2_df["match_id"].isin(trio_ids)].copy()

    me_df = me_df.sort_values("start_time")

    me_stats = compute_aggregated_stats(me_df)
    f1_stats = compute_aggregated_stats(f1_df)
    f2_stats = compute_aggregated_stats(f2_df)
    trio_per_min = pd.DataFrame(
        [
            {
                "Joueur": me_name,
                "Frags/min": round(float(me_stats.kills_per_minute), 2)
                if me_stats.kills_per_minute
                else None,
                "Morts/min": round(float(me_stats.deaths_per_minute), 2)
                if me_stats.deaths_per_minute
                else None,
                "Assists/min": round(float(me_stats.assists_per_minute), 2)
                if me_stats.assists_per_minute
                else None,
            },
            {
                "Joueur": f1_name,
                "Frags/min": round(float(f1_stats.kills_per_minute), 2)
                if f1_stats.kills_per_minute
                else None,
                "Morts/min": round(float(f1_stats.deaths_per_minute), 2)
                if f1_stats.deaths_per_minute
                else None,
                "Assists/min": round(float(f1_stats.assists_per_minute), 2)
                if f1_stats.assists_per_minute
                else None,
            },
            {
                "Joueur": f2_name,
                "Frags/min": round(float(f2_stats.kills_per_minute), 2)
                if f2_stats.kills_per_minute
                else None,
                "Morts/min": round(float(f2_stats.deaths_per_minute), 2)
                if f2_stats.deaths_per_minute
                else None,
                "Assists/min": round(float(f2_stats.assists_per_minute), 2)
                if f2_stats.assists_per_minute
                else None,
            },
        ]
    )
    st.subheader("Stats par minute")

    # Afficher tableau et graphe radar côte à côte
    col_table, col_radar = st.columns([1, 1])

    with col_table:
        st.dataframe(trio_per_min, width="stretch", hide_index=True)

    with col_radar:
        from src.ui.components.radar_chart import create_stats_per_minute_radar

        radar_players = [
            {
                "name": me_name,
                "kills_per_min": float(me_stats.kills_per_minute)
                if me_stats.kills_per_minute
                else 0,
                "deaths_per_min": float(me_stats.deaths_per_minute)
                if me_stats.deaths_per_minute
                else 0,
                "assists_per_min": float(me_stats.assists_per_minute)
                if me_stats.assists_per_minute
                else 0,
                "color": colors_by_name.get(me_name, "#636EFA"),
            },
            {
                "name": f1_name,
                "kills_per_min": float(f1_stats.kills_per_minute)
                if f1_stats.kills_per_minute
                else 0,
                "deaths_per_min": float(f1_stats.deaths_per_minute)
                if f1_stats.deaths_per_minute
                else 0,
                "assists_per_min": float(f1_stats.assists_per_minute)
                if f1_stats.assists_per_minute
                else 0,
                "color": colors_by_name.get(f1_name, "#EF553B"),
            },
            {
                "name": f2_name,
                "kills_per_min": float(f2_stats.kills_per_minute)
                if f2_stats.kills_per_minute
                else 0,
                "deaths_per_min": float(f2_stats.deaths_per_minute)
                if f2_stats.deaths_per_minute
                else 0,
                "assists_per_min": float(f2_stats.assists_per_minute)
                if f2_stats.assists_per_minute
                else 0,
                "color": colors_by_name.get(f2_name, "#00CC96"),
            },
        ]
        radar_fig = create_stats_per_minute_radar(radar_players, title="", height=300)
        st.plotly_chart(radar_fig, width="stretch")

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
