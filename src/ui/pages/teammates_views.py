"""Vues de rendu pour la page Coéquipiers (single, multi, trio).

Extraites de teammates.py (Sprint 16 — refactoring Phase A).
"""

from __future__ import annotations

import polars as pl
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
    cached_query_matches_with_friend,
    cached_same_team_match_ids_with_friend,
)
from src.ui.medals import render_medals_grid
from src.ui.pages.teammates_charts import (
    render_comparison_charts,
    render_metric_bar_charts,
    render_outcome_bar_chart,
    render_trio_charts,
)
from src.ui.pages.teammates_helpers import (
    _clear_min_matches_maps_friends_auto,
    render_friends_history_table,
)
from src.ui.pages.teammates_impact import render_impact_taquinerie
from src.ui.pages.teammates_synergy import render_synergy_radar, render_trio_synergy_radar
from src.visualization import plot_map_ratio_with_winloss
from src.visualization._compat import DataFrameLike, ensure_polars, to_pandas_for_st

# ---------------------------------------------------------------------------
# Helpers partagés (rebindés depuis teammates.py)
# ---------------------------------------------------------------------------
# Ces fonctions sont injectées par teammates.py via les arguments.
# On utilise des callbacks passés en paramètre pour éviter les imports circulaires.


def render_single_teammate_view(
    df: DataFrameLike,
    dff: DataFrameLike,
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
    load_teammate_stats_fn,
    enrich_series_fn,
) -> None:
    """Vue pour un seul coéquipier sélectionné."""
    df = ensure_polars(df)
    dff = ensure_polars(dff)
    friend_xuid = picked_xuids[0]
    with st.spinner("Chargement des matchs avec ce coéquipier…"):
        dfr = ensure_polars(
            cached_friend_matches_df(
                db_path,
                xuid.strip(),
                friend_xuid,
                same_team_only=bool(same_team_only),
                db_key=db_key,
            )
        )
        if dfr.is_empty():
            st.warning("Aucun match trouvé avec ce coéquipier (selon le filtre).")
            return

        render_outcome_bar_chart(dfr)

        _render_match_details_expander(dfr)

        base_for_friend = dff if apply_current_filters else df
        shared_ids = set(dfr["match_id"].cast(pl.Utf8).to_list())
        sub = base_for_friend.filter(pl.col("match_id").cast(pl.Utf8).is_in(shared_ids))

        if sub.is_empty():
            st.info(
                "Aucun match à afficher avec les filtres actuels (période/sessions + map/playlist)."
            )
            return

        name = display_name_from_xuid(friend_xuid)

        _render_shared_stats_metrics(sub)

        # Charger les stats du coéquipier depuis SA propre DB
        friend_sub = ensure_polars(load_teammate_stats_fn(name, shared_ids, db_path))

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
        if not friend_sub.is_empty():
            series.append((name, friend_sub))
        colors_by_name = assign_player_colors_fn([n for n, _ in series])
        series = enrich_series_fn(series, db_path)

        render_metric_bar_charts(
            series=series,
            colors_by_name=colors_by_name,
            show_smooth=show_smooth,
            key_suffix=friend_xuid,
            plot_fn=plot_multi_metric_bars_fn,
        )

        # Radar de complémentarité
        render_synergy_radar(
            sub=sub,
            friend_sub=friend_sub,
            me_name=me_name,
            friend_name=name,
            colors_by_name=colors_by_name,
        )

        # Médailles
        _render_shared_medals(
            db_path,
            xuid,
            friend_xuid,
            me_name,
            name,
            shared_ids,
            db_key,
            top_medals_fn,
        )


def render_multi_teammate_view(
    df: DataFrameLike,
    dff: DataFrameLike,
    base: DataFrameLike,
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
    load_teammate_stats_fn,
    enrich_series_fn,
) -> None:
    """Vue pour plusieurs coéquipiers sélectionnés."""
    df = ensure_polars(df)
    dff = ensure_polars(dff)
    base = ensure_polars(base)
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
        all_match_ids, per_friend_ids = _collect_friend_match_ids(
            db_path,
            xuid,
            picked_xuids,
            same_team_only,
            db_key,
        )

        sub_all = base_for_friends_all.filter(
            pl.col("match_id").cast(pl.Utf8).is_in(list(all_match_ids))
        )

        series: list[tuple[str, DataFrameLike]] = [(me_name, sub_all)]
        with st.spinner("Chargement des stats des coéquipiers…"):
            for fx in picked_xuids:
                ids = per_friend_ids.get(str(fx), set())
                if not ids:
                    continue
                fx_gamertag = display_name_from_xuid(str(fx))
                fr_sub = ensure_polars(
                    load_teammate_stats_fn(fx_gamertag, {str(x) for x in ids}, db_path)
                )
                if fr_sub.is_empty():
                    continue
                series.append((fx_gamertag, fr_sub))
        colors_by_name = assign_player_colors_fn([n for n, _ in series])

        breakdown_all = ensure_polars(compute_map_breakdown(sub_all))
        breakdown_all = breakdown_all.filter(pl.col("matches") >= int(min_matches_maps_friends))

        if breakdown_all.is_empty():
            st.info("Pas assez de matchs avec tes coéquipiers (selon le filtre actuel).")
        else:
            try:
                view_all = breakdown_all.head(20).reverse()
                title = f"Ratio global par carte — avec mes coéquipiers (min {min_matches_maps_friends} matchs)"
                fig_map = plot_map_ratio_with_winloss(view_all, title=title)
                if fig_map is not None:
                    st.plotly_chart(fig_map, width="stretch")
                else:
                    st.info("Données insuffisantes pour le ratio par carte.")
            except Exception as e:
                st.warning(f"Impossible d'afficher le ratio par carte : {e}")

            st.subheader("Historique — matchs avec mes coéquipiers")

        if sub_all.is_empty():
            st.info("Aucun match trouvé avec tes coéquipiers (selon le filtre actuel).")
        else:
            render_friends_history_table(sub_all, db_path, xuid, db_key, waypoint_player)

        rendered_bottom_charts = False

    # Vue trio (moi + 2 coéquipiers)
    if len(picked_xuids) >= 2:
        rendered_bottom_charts = render_trio_view(
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
            load_teammate_stats_fn=load_teammate_stats_fn,
            enrich_series_fn=enrich_series_fn,
        )

    # Impact & Taquinerie (si ≥2 amis)
    if len(picked_xuids) >= 2:
        impact_match_ids = list(all_match_ids) if all_match_ids else []
        render_impact_taquinerie(
            db_path=db_path,
            xuid=xuid,
            match_ids=impact_match_ids,
            friend_xuids=picked_xuids,
            db_key=db_key,
        )

    if not rendered_bottom_charts:
        series = enrich_series_fn(series, db_path)
        render_metric_bar_charts(
            series=series,
            colors_by_name=colors_by_name,
            show_smooth=show_smooth,
            key_suffix=f"{len(series)}",
            plot_fn=plot_multi_metric_bars_fn,
        )


def render_trio_view(
    df: DataFrameLike,
    dff: DataFrameLike,
    base: DataFrameLike,
    me_name: str,
    xuid: str,
    db_path: str,
    db_key: tuple[int, int] | None,
    aliases_key: int | None,
    picked_xuids: list[str],
    apply_current_filters: bool,
    include_firefight: bool,
    series: list[tuple[str, DataFrameLike]],
    colors_by_name: dict[str, str],
    show_smooth: bool,
    assign_player_colors_fn,
    plot_multi_metric_bars_fn,
    top_medals_fn,
    load_teammate_stats_fn,
    enrich_series_fn,
) -> bool:
    """Affiche la vue trio (moi + 2 coéquipiers). Retourne True si les graphes du bas sont rendus."""
    df = ensure_polars(df)
    dff = ensure_polars(dff)
    base = ensure_polars(base)
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
    trio_ids = trio_ids & set(base_for_trio["match_id"].cast(pl.Utf8).to_list())

    if not trio_ids:
        st.warning(
            "Aucun match trouvé où vous êtes tous les trois dans la même équipe "
            "(avec les filtres actuels)."
        )
        return False

    trio_ids_set = {str(x) for x in trio_ids}

    _detect_trio_session(db_path, xuid, db_key, include_firefight, aliases_key, trio_ids_set)

    me_df = base_for_trio.filter(pl.col("match_id").is_in(list(trio_ids)))

    # Charger les stats des coéquipiers depuis LEURS propres DBs
    f1_df = ensure_polars(load_teammate_stats_fn(f1_name, trio_ids_set, db_path))
    f2_df = ensure_polars(load_teammate_stats_fn(f2_name, trio_ids_set, db_path))

    me_df = me_df.sort("start_time")

    _render_per_minute_stats(me_df, f1_df, f2_df, me_name, f1_name, f2_name, colors_by_name)

    # Radar de complémentarité trio
    render_trio_synergy_radar(
        me_df=me_df,
        f1_df=f1_df,
        f2_df=f2_df,
        me_name=me_name,
        f1_name=f1_name,
        f2_name=f2_name,
        colors_by_name=colors_by_name,
        db_path=db_path,
    )

    # Merge et performance
    merged = _merge_trio_dataframes(me_df, f1_df, f2_df)
    if merged.is_empty():
        st.warning("Impossible d'aligner les stats des 3 joueurs sur ces matchs.")
        return False

    _render_trio_performance_charts(merged, me_name, f1_name, f2_name, f1_xuid, f2_xuid)

    # Graphes de barres
    series = enrich_series_fn(series, db_path)
    render_metric_bar_charts(
        series=series,
        colors_by_name=colors_by_name,
        show_smooth=show_smooth,
        key_suffix=f"{len(series)}",
        plot_fn=plot_multi_metric_bars_fn,
    )

    # Médailles trio
    _render_trio_medals(
        merged,
        db_path,
        xuid,
        f1_xuid,
        f2_xuid,
        me_name,
        f1_name,
        f2_name,
        db_key,
        top_medals_fn,
    )

    return True


# ---------------------------------------------------------------------------
# Sous-fonctions privées extraites des monolithes
# ---------------------------------------------------------------------------


def _render_match_details_expander(dfr: DataFrameLike) -> None:
    """Affiche l'expander avec détails des matchs joueur vs joueur."""
    dfr = ensure_polars(dfr)
    with st.expander("Détails des matchs (joueur vs joueur)", expanded=False):
        st.dataframe(
            to_pandas_for_st(
                dfr.select(
                    "start_time",
                    "playlist_name",
                    "pair_name",
                    "same_team",
                    "my_team_id",
                    "my_outcome",
                    "friend_team_id",
                    "friend_outcome",
                    "match_id",
                )
            ),
            width="stretch",
            hide_index=True,
        )


def _render_shared_stats_metrics(sub: DataFrameLike) -> None:
    """Affiche les métriques KPI pour les matchs partagés."""
    rates_sub = compute_outcome_rates(sub)
    total_out = max(1, rates_sub.total)
    win_rate_sub = rates_sub.wins / total_out
    loss_rate_sub = rates_sub.losses / total_out
    global_ratio_sub = compute_global_ratio(sub)

    k = st.columns(3)
    k[0].metric("Matchs", f"{len(sub)}")
    k[1].metric("Win/Loss", f"{win_rate_sub*100:.1f}% / {loss_rate_sub*100:.1f}%")
    k[2].metric("Ratio global", f"{global_ratio_sub:.2f}" if global_ratio_sub is not None else "-")

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


def _render_shared_medals(
    db_path: str,
    xuid: str,
    friend_xuid: str,
    me_name: str,
    friend_name: str,
    shared_ids: set[str],
    db_key: tuple[int, int] | None,
    top_medals_fn,
) -> None:
    """Affiche la section médailles partagées (single view)."""
    st.subheader("Médailles (matchs partagés)")
    shared_list = sorted({str(x) for x in shared_ids if str(x).strip()})
    if not shared_list:
        st.info("Aucun match partagé pour calculer les médailles.")
        return

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
        st.caption(f"{friend_name}")
        render_medals_grid(
            [{"name_id": int(n), "count": int(c)} for n, c in (fr_top or [])],
            cols_per_row=6,
        )


def _collect_friend_match_ids(
    db_path: str,
    xuid: str,
    picked_xuids: list[str],
    same_team_only: bool,
    db_key: tuple[int, int] | None,
) -> tuple[set[str], dict[str, set[str]]]:
    """Collecte les match_ids par coéquipier et l'union totale."""
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
    return all_match_ids, per_friend_ids


def _detect_trio_session(
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
    include_firefight: bool,
    aliases_key: int | None,
    trio_ids_set: set[str],
) -> None:
    """Détecte et affiche la dernière session trio."""
    from src.app.filters import get_friends_xuids_for_sessions

    friends_tuple = get_friends_xuids_for_sessions(db_path, xuid.strip(), db_key, aliases_key)
    base_s_trio = ensure_polars(
        cached_compute_sessions_db(
            db_path,
            xuid.strip(),
            db_key,
            include_firefight,
            120,  # gap figé
            friends_xuids=friends_tuple,
        )
    )
    trio_rows = base_s_trio.filter(pl.col("match_id").cast(pl.Utf8).is_in(list(trio_ids_set)))
    latest_label = None
    if not trio_rows.is_empty():
        latest_sid = int(trio_rows["session_id"].max())
        latest_labels = (
            trio_rows.filter(pl.col("session_id") == latest_sid)
            .select("session_label")
            .drop_nulls()
            .unique()
            .to_series()
            .to_list()
        )
        latest_label = latest_labels[0] if latest_labels else None

    st.session_state["_trio_latest_session_label"] = latest_label
    if latest_label:
        st.caption(f"Dernière session trio détectée : {latest_label}.")
    else:
        st.caption("Impossible de déterminer une session trio (données insuffisantes).")


def _render_per_minute_stats(
    me_df: DataFrameLike,
    f1_df: DataFrameLike,
    f2_df: DataFrameLike,
    me_name: str,
    f1_name: str,
    f2_name: str,
    colors_by_name: dict[str, str],
) -> None:
    """Affiche le graphe barres groupées stats/min pour le trio."""
    import plotly.graph_objects as go

    from src.visualization.theme import apply_halo_plot_style

    me_stats = compute_aggregated_stats(me_df)
    f1_stats = compute_aggregated_stats(f1_df)
    f2_stats = compute_aggregated_stats(f2_df)
    st.subheader("Stats par minute")

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
    try:
        if fig_pm is not None:
            st.plotly_chart(fig_pm, width="stretch")
        else:
            st.info("Données insuffisantes pour les stats/min.")
    except Exception as e:
        st.warning(f"Impossible d'afficher les stats/min : {e}")


def _merge_trio_dataframes(
    me_df: DataFrameLike,
    f1_df: DataFrameLike,
    f2_df: DataFrameLike,
) -> pl.DataFrame:
    """Merge les DataFrames des 3 joueurs sur match_id."""
    me_df = ensure_polars(me_df)
    f1_df = ensure_polars(f1_df)
    f2_df = ensure_polars(f2_df)
    friend_cols = [
        "match_id",
        "kills",
        "deaths",
        "assists",
        "accuracy",
        "ratio",
        "average_life_seconds",
    ]
    me_cols = [
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
    f1_sel = f1_df.select(friend_cols).rename({c: f"f1_{c}" for c in friend_cols})
    f2_sel = f2_df.select(friend_cols).rename({c: f"f2_{c}" for c in friend_cols})
    return (
        me_df.select(me_cols)
        .join(f1_sel, left_on="match_id", right_on="f1_match_id", how="inner")
        .join(f2_sel, left_on="match_id", right_on="f2_match_id", how="inner")
    )


def _render_trio_performance_charts(
    merged: DataFrameLike,
    me_name: str,
    f1_name: str,
    f2_name: str,
    f1_xuid: str,
    f2_xuid: str,
) -> None:
    """Calcule les scores de performance et affiche les graphes trio."""
    from src.analysis.performance_score import compute_performance_series

    merged = ensure_polars(merged).sort("start_time")
    d_self = merged.select(
        "start_time",
        "kills",
        "deaths",
        "assists",
        "ratio",
        "accuracy",
        "average_life_seconds",
        "time_played_seconds",
    )
    d_f1 = merged.select(
        "start_time",
        "f1_kills",
        "f1_deaths",
        "f1_assists",
        "f1_ratio",
        "f1_accuracy",
        "f1_average_life_seconds",
        "time_played_seconds",
    ).rename(
        {
            "f1_kills": "kills",
            "f1_deaths": "deaths",
            "f1_assists": "assists",
            "f1_ratio": "ratio",
            "f1_accuracy": "accuracy",
            "f1_average_life_seconds": "average_life_seconds",
        }
    )
    d_f2 = merged.select(
        "start_time",
        "f2_kills",
        "f2_deaths",
        "f2_assists",
        "f2_ratio",
        "f2_accuracy",
        "f2_average_life_seconds",
        "time_played_seconds",
    ).rename(
        {
            "f2_kills": "kills",
            "f2_deaths": "deaths",
            "f2_assists": "assists",
            "f2_ratio": "ratio",
            "f2_accuracy": "accuracy",
            "f2_average_life_seconds": "average_life_seconds",
        }
    )

    d_self = d_self.with_columns(
        pl.Series("performance", compute_performance_series(d_self, d_self))
    )
    d_f1 = d_f1.with_columns(pl.Series("performance", compute_performance_series(d_f1, d_f1)))
    d_f2 = d_f2.with_columns(pl.Series("performance", compute_performance_series(d_f2, d_f2)))

    render_trio_charts(d_self, d_f1, d_f2, me_name, f1_name, f2_name, f1_xuid, f2_xuid)


def _render_trio_medals(
    merged: DataFrameLike,
    db_path: str,
    xuid: str,
    f1_xuid: str,
    f2_xuid: str,
    me_name: str,
    f1_name: str,
    f2_name: str,
    db_key: tuple[int, int] | None,
    top_medals_fn,
) -> None:
    """Affiche la section médailles du trio."""
    st.subheader("Médailles")
    trio_match_ids = (
        ensure_polars(merged).select("match_id").drop_nulls().to_series().cast(pl.Utf8).to_list()
    )
    if not trio_match_ids:
        st.info("Impossible de déterminer la liste des matchs pour l'agrégation des médailles.")
        return

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
