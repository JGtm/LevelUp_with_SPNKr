"""Routage des pages extraits de main() pour simplification.

Ce module centralise:
- La liste des pages disponibles
- La construction des paramètres pour les pages de match
- Le dispatch vers les différentes pages
"""

from __future__ import annotations

from collections.abc import Callable

import polars as pl
import streamlit as st

from src.ui.settings import AppSettings


def _to_polars(df: pl.DataFrame) -> pl.DataFrame:
    """Convertit un DataFrame en Polars si nécessaire (bridge transitoire)."""
    if isinstance(df, pl.DataFrame):
        return df
    return pl.from_pandas(df)


# Liste des pages disponibles
PAGES: list[str] = [
    "Séries temporelles",
    "Comparaison de sessions",
    "Dernier match",
    "Match",
    "Médias",
    "Citations",
    "Victoires/Défaites",
    "Mes coéquipiers",
    "Historique des parties",
    "Carrière",
    "Paramètres",
]


def build_match_view_params(
    db_path: str,
    xuid: str,
    waypoint_player: str,
    db_key: str | None,
    settings: AppSettings,
    df_full: pl.DataFrame,
    render_match_view_fn: Callable,
    normalize_mode_label_fn: Callable,
    format_score_label_fn: Callable,
    score_css_color_fn: Callable,
    format_datetime_fn: Callable,
    load_player_match_result_fn: Callable,
    load_match_medals_fn: Callable,
    load_highlight_events_fn: Callable,
    load_match_gamertags_fn: Callable,
    load_match_rosters_fn: Callable,
    paris_tz,
) -> dict:
    """Construit les paramètres communs pour les pages de match."""
    return {
        "db_path": db_path,
        "xuid": xuid,
        "waypoint_player": waypoint_player,
        "db_key": db_key,
        "settings": settings,
        "df_full": df_full,
        "render_match_view_fn": render_match_view_fn,
        "normalize_mode_label_fn": normalize_mode_label_fn,
        "format_score_label_fn": format_score_label_fn,
        "score_css_color_fn": score_css_color_fn,
        "format_datetime_fn": format_datetime_fn,
        "load_player_match_result_fn": load_player_match_result_fn,
        "load_match_medals_fn": load_match_medals_fn,
        "load_highlight_events_fn": load_highlight_events_fn,
        "load_match_gamertags_fn": load_match_gamertags_fn,
        "load_match_rosters_fn": load_match_rosters_fn,
        "paris_tz": paris_tz,
    }


def consume_pending_page() -> None:
    """Consomme la page en attente si définie."""
    pending_page = st.session_state.pop("_pending_page", None)
    if isinstance(pending_page, str) and pending_page in PAGES:
        st.session_state["page"] = pending_page
    if "page" not in st.session_state:
        st.session_state["page"] = "Séries temporelles"


def consume_pending_match_id() -> None:
    """Consomme le match_id en attente si défini."""
    pending_mid = st.session_state.pop("_pending_match_id", None)
    if isinstance(pending_mid, str) and pending_mid.strip():
        st.session_state["match_id_input"] = pending_mid.strip()


def render_page_selector() -> str:
    """Rend le sélecteur de page et retourne la page choisie."""
    return st.segmented_control(
        "Onglets",
        options=PAGES,
        key="page",
        label_visibility="collapsed",
    )


def dispatch_page(
    page: str,
    dff: pl.DataFrame,
    df: pl.DataFrame,
    base: pl.DataFrame,
    me_name: str,
    xuid: str,
    db_path: str,
    db_key: str | None,
    aliases_key: str | None,
    settings: AppSettings,
    picked_session_labels: list[str] | None,
    waypoint_player: str,
    gap_minutes: int,
    match_view_params: dict,
    # Fonctions de rendu
    render_last_match_page_fn: Callable,
    render_match_search_page_fn: Callable,
    render_citations_page_fn: Callable,
    render_session_comparison_page_fn: Callable,
    render_timeseries_page_fn: Callable,
    render_win_loss_page_fn: Callable,
    render_teammates_page_fn: Callable,
    render_match_history_page_fn: Callable,
    render_media_tab_fn: Callable,
    render_career_page_fn: Callable,
    render_settings_page_fn: Callable,
    # Fonctions utilitaires
    cached_compute_sessions_db_fn: Callable,
    top_medals_fn: Callable,
    build_friends_opts_map_fn: Callable,
    assign_player_colors_fn: Callable,
    plot_multi_metric_bars_fn: Callable,
    get_local_dbs_fn: Callable,
    clear_caches_fn: Callable,
) -> None:
    """Dispatch vers la page appropriée."""
    # Les fonctions de rendu attendent encore pandas, donc on garde df en l'état
    # La conversion se fera progressivement au niveau de chaque page

    if page == "Dernier match":
        render_last_match_page_fn(dff=dff, **match_view_params)

    elif page == "Match":
        render_match_search_page_fn(df=df, dff=dff, **match_view_params)

    elif page == "Citations":
        render_citations_page_fn(
            dff=dff,
            df_full=df,
            xuid=xuid,
            db_path=db_path,
            db_key=db_key,
            top_medals_fn=top_medals_fn,
        )

    elif page == "Comparaison de sessions":
        from src.app.filters import get_friends_xuids_for_sessions

        friends_tuple = get_friends_xuids_for_sessions(db_path, xuid.strip(), db_key, aliases_key)
        all_sessions_df = cached_compute_sessions_db_fn(
            db_path, xuid.strip(), db_key, True, gap_minutes, friends_xuids=friends_tuple
        )
        # Normaliser en Polars
        all_sessions_pl = _to_polars(all_sessions_df)
        df_pl = _to_polars(df)

        # La page a besoin d'un DataFrame "sessions" enrichi : session_id/session_label
        # + toutes les stats match (kills, pair_name, etc.). En DuckDB v4, cached_compute_sessions_db
        # ne renvoie que match_id, start_time, session_id, session_label → on fusionne avec df.
        if (
            not all_sessions_pl.is_empty()
            and "match_id" in df_pl.columns
            and "match_id" in all_sessions_pl.columns
        ):
            sess_cols = ["match_id", "session_id", "session_label"]
            # Retirer session_id/session_label de df avant join pour éviter doublons
            drop_cols = [c for c in ("session_id", "session_label") if c in df_pl.columns]
            df_for_merge = df_pl.drop(drop_cols) if drop_cols else df_pl
            sessions_for_compare = df_for_merge.join(
                all_sessions_pl.select(sess_cols), on="match_id", how="inner"
            )
        else:
            sessions_for_compare = all_sessions_pl
        render_session_comparison_page_fn(sessions_for_compare, df_full=df)

    elif page == "Séries temporelles":
        render_timeseries_page_fn(dff, df_full=df, db_path=db_path, xuid=xuid)

    elif page == "Victoires/Défaites":
        render_win_loss_page_fn(
            dff=dff,
            base=base,
            picked_session_labels=picked_session_labels,
            db_path=db_path,
            xuid=xuid,
            db_key=db_key,
        )

    elif page == "Mes coéquipiers":
        render_teammates_page_fn(
            df=df,
            dff=dff,
            base=base,
            me_name=me_name,
            xuid=xuid,
            db_path=db_path,
            db_key=db_key,
            aliases_key=aliases_key,
            settings=settings,
            picked_session_labels=picked_session_labels,
            include_firefight=True,
            waypoint_player=waypoint_player,
            build_friends_opts_map_fn=build_friends_opts_map_fn,
            assign_player_colors_fn=assign_player_colors_fn,
            plot_multi_metric_bars_fn=plot_multi_metric_bars_fn,
            top_medals_fn=top_medals_fn,
        )

    elif page == "Historique des parties":
        render_match_history_page_fn(
            dff=dff,
            waypoint_player=waypoint_player,
            db_path=db_path,
            xuid=xuid,
            db_key=db_key,
            df_full=df,
        )

    elif page == "Médias" or page == "Bibliothèque médias":
        render_media_tab_fn(
            df_full=df,
            settings=settings,
        )

    elif page == "Carrière":
        render_career_page_fn(
            db_path=db_path,
            xuid=xuid,
            db_key=db_key,
        )

    elif page == "Paramètres":
        render_settings_page_fn(
            settings,
            get_local_dbs_fn=get_local_dbs_fn,
            on_clear_caches_fn=clear_caches_fn,
        )
