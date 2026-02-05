"""Rendu des filtres sidebar extraits de main() pour simplification.

Ce module gère:
- Le rendu complet de la section filtres dans la sidebar
- La logique de sélection Période / Sessions
- Les filtres cascade Playlists -> Modes -> Cartes
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import pandas as pd
import streamlit as st

from src.ui import translate_pair_name, translate_playlist_name
from src.ui.cache import (
    cached_compute_sessions_db,
    cached_same_team_match_ids_with_friend,
)
from src.ui.components import (
    get_firefight_playlists,
    render_checkbox_filter,
    render_hierarchical_checkbox_filter,
)


@dataclass
class FilterState:
    """État des filtres après rendu."""

    filter_mode: str  # "Période" ou "Sessions"
    start_d: date
    end_d: date
    gap_minutes: int
    picked_session_labels: list[str] | None
    playlists_selected: list[str]
    modes_selected: list[str]
    maps_selected: list[str]
    base_s_ui: pd.DataFrame | None  # DataFrame sessions (mode Sessions)


def render_filters_sidebar(
    df: pd.DataFrame,
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
    aliases_key: int | None,
    date_range_fn: Callable[[pd.DataFrame], tuple[date, date]],
    clean_asset_label_fn: Callable[[str], str],
    normalize_mode_label_fn: Callable[[str], str],
    normalize_map_label_fn: Callable[[str], str],
    build_friends_opts_map_fn: Callable,
) -> FilterState:
    """Rend la section complète des filtres dans la sidebar.

    Returns:
        FilterState avec tous les paramètres de filtrage sélectionnés.
    """
    st.header("Filtres")

    base_for_filters = df.copy()
    dmin, dmax = date_range_fn(base_for_filters)

    # Consommation des états pending
    pending_mode = st.session_state.pop("_pending_filter_mode", None)
    if pending_mode in ("Période", "Sessions"):
        st.session_state["filter_mode"] = pending_mode

    pending_label = st.session_state.pop("_pending_picked_session_label", None)
    if isinstance(pending_label, str) and pending_label:
        st.session_state["picked_session_label"] = pending_label
    pending_sessions = st.session_state.pop("_pending_picked_sessions", None)
    if isinstance(pending_sessions, list):
        st.session_state["picked_sessions"] = pending_sessions

    # Sélecteur de mode
    if "filter_mode" not in st.session_state:
        st.session_state["filter_mode"] = "Période"
    filter_mode = st.radio(
        "Sélection",
        options=["Période", "Sessions"],
        horizontal=True,
        key="filter_mode",
    )

    # UX: reset min_matches_maps en mode Période
    if filter_mode == "Période" and bool(st.session_state.get("_min_matches_maps_auto")):
        st.session_state["min_matches_maps"] = 5
        st.session_state["_min_matches_maps_auto"] = False
    if filter_mode == "Période" and bool(st.session_state.get("_min_matches_maps_friends_auto")):
        st.session_state["min_matches_maps_friends"] = 5
        st.session_state["_min_matches_maps_friends_auto"] = False

    # Valeurs par défaut
    start_d, end_d = dmin, dmax
    gap_minutes = 35
    picked_session_labels: list[str] | None = None
    base_s_ui: pd.DataFrame | None = None

    if filter_mode == "Période":
        start_d, end_d = _render_period_filter(dmin, dmax)
    else:
        gap_minutes, picked_session_labels, base_s_ui = _render_session_filter(
            db_path,
            xuid,
            db_key,
            aliases_key,
            base_for_filters,
            build_friends_opts_map_fn,
        )

    # Filtres cascade
    playlists_selected, modes_selected, maps_selected = _render_cascade_filters(
        base_for_filters=base_for_filters,
        filter_mode=filter_mode,
        start_d=start_d,
        end_d=end_d,
        picked_session_labels=picked_session_labels,
        base_s_ui=base_s_ui,
        clean_asset_label_fn=clean_asset_label_fn,
        normalize_mode_label_fn=normalize_mode_label_fn,
        normalize_map_label_fn=normalize_map_label_fn,
    )

    return FilterState(
        filter_mode=filter_mode,
        start_d=start_d,
        end_d=end_d,
        gap_minutes=gap_minutes,
        picked_session_labels=picked_session_labels,
        playlists_selected=playlists_selected,
        modes_selected=modes_selected,
        maps_selected=maps_selected,
        base_s_ui=base_s_ui,
    )


def _render_period_filter(dmin: date, dmax: date) -> tuple[date, date]:
    """Rend les sélecteurs de dates en mode Période."""
    cols = st.columns(2)
    with cols[0]:
        start_default = pd.to_datetime(dmin, errors="coerce")
        if pd.isna(start_default):
            start_default = pd.Timestamp.today().normalize()
        start_default_date = start_default.date()
        end_limit = pd.to_datetime(dmax, errors="coerce")
        if pd.isna(end_limit):
            end_limit = start_default
        end_limit_date = end_limit.date()
        start_value = st.session_state.get("start_date_cal", start_default_date)
        if (
            not isinstance(start_value, date)
            or start_value < start_default_date
            or start_value > end_limit_date
        ):
            start_value = start_default_date
        start_date = st.date_input(
            "Début",
            value=start_value,
            min_value=start_default_date,
            max_value=end_limit_date,
            format="DD/MM/YYYY",
            key="start_date_cal",
        )
    with cols[1]:
        end_default = pd.to_datetime(dmax, errors="coerce")
        if pd.isna(end_default):
            end_default = pd.Timestamp.today().normalize()
        end_default_date = end_default.date()
        start_limit = pd.to_datetime(dmin, errors="coerce")
        if pd.isna(start_limit):
            start_limit = end_default
        start_limit_date = start_limit.date()
        end_value = st.session_state.get("end_date_cal", end_default_date)
        if (
            not isinstance(end_value, date)
            or end_value < start_limit_date
            or end_value > end_default_date
        ):
            end_value = end_default_date
        end_date = st.date_input(
            "Fin",
            value=end_value,
            min_value=start_limit_date,
            max_value=end_default_date,
            format="DD/MM/YYYY",
            key="end_date_cal",
        )
    if start_date > end_date:
        st.warning("La date de début est après la date de fin.")
    return start_date, end_date


def _render_session_filter(
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
    aliases_key: int | None,
    base_for_filters: pd.DataFrame,
    build_friends_opts_map_fn: Callable,
) -> tuple[int, list[str] | None, pd.DataFrame]:
    """Rend les contrôles en mode Sessions."""
    gap_minutes = st.slider(
        "Écart max entre parties (minutes)",
        min_value=15,
        max_value=240,
        value=int(st.session_state.get("gap_minutes", 120)),
        step=5,
        key="gap_minutes",
    )

    base_s_ui = cached_compute_sessions_db(
        db_path,
        xuid.strip(),
        db_key,
        True,
        gap_minutes,
    )
    session_labels_ui = (
        base_s_ui[["session_id", "session_label"]]
        .drop_duplicates()
        .sort_values("session_id", ascending=False)
    )
    options_ui = session_labels_ui["session_label"].tolist()
    st.session_state["_latest_session_label"] = options_ui[0] if options_ui else None

    def _set_session_selection(label: str) -> None:
        st.session_state.picked_session_label = label
        if label == "(toutes)":
            st.session_state.picked_sessions = []
        elif label in options_ui:
            st.session_state.picked_sessions = [label]

    if "picked_session_label" not in st.session_state:
        _set_session_selection(options_ui[0] if options_ui else "(toutes)")
    if "picked_sessions" not in st.session_state:
        st.session_state.picked_sessions = options_ui[:1] if options_ui else []

    # Boutons de navigation
    cols = st.columns(2)
    if cols[0].button("Dernière session", width="stretch"):
        _set_session_selection(options_ui[0] if options_ui else "(toutes)")
        st.session_state["min_matches_maps"] = 1
        st.session_state["_min_matches_maps_auto"] = True
        st.session_state["min_matches_maps_friends"] = 1
        st.session_state["_min_matches_maps_friends_auto"] = True
    if cols[1].button("Session précédente", width="stretch"):
        current = st.session_state.get("picked_session_label", "(toutes)")
        if not options_ui:
            _set_session_selection("(toutes)")
        elif current == "(toutes)" or current not in options_ui:
            _set_session_selection(options_ui[0])
        else:
            idx = options_ui.index(current)
            next_idx = min(idx + 1, len(options_ui) - 1)
            _set_session_selection(options_ui[next_idx])

    # Trio
    trio_label = _compute_trio_label(
        db_path,
        xuid,
        db_key,
        aliases_key,
        base_for_filters,
        base_s_ui,
        options_ui,
        build_friends_opts_map_fn,
    )
    _render_trio_button(trio_label)

    # Sélecteur de session
    picked_one = st.selectbox(
        "Session", options=["(toutes)"] + options_ui, key="picked_session_label"
    )
    picked_session_labels = None if picked_one == "(toutes)" else [picked_one]

    return gap_minutes, picked_session_labels, base_s_ui


@st.cache_data(show_spinner=False, ttl=120)
def _cached_get_trio_match_ids(
    db_path: str,
    xuid: str,
    f1_xuid: str,
    f2_xuid: str,
    db_key: tuple[int, int] | None,
) -> tuple[str, ...]:
    """Récupère les match IDs où les 3 joueurs sont dans la même équipe (cachée).

    Cette fonction est coûteuse car elle fait 2 requêtes SQL.
    Le cache TTL de 120s évite les recalculs fréquents.
    """
    try:
        ids_m = set(
            cached_same_team_match_ids_with_friend(db_path, xuid.strip(), f1_xuid, db_key=db_key)
        )
        ids_c = set(
            cached_same_team_match_ids_with_friend(db_path, xuid.strip(), f2_xuid, db_key=db_key)
        )
        trio_ids = ids_m & ids_c
        return tuple(sorted(trio_ids))
    except Exception:
        return ()


def _compute_trio_label(
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
    aliases_key: int | None,
    base_for_filters: pd.DataFrame,
    base_s_ui: pd.DataFrame,
    options_ui: list[str],
    build_friends_opts_map_fn: Callable,
) -> str | None:
    """Calcule le label de la dernière session en trio.

    Optimisé: utilise un cache TTL pour éviter les recalculs coûteux
    des requêtes SQL à chaque rendu.
    """
    try:
        # Récupérer les amis sélectionnés (déjà caché via @st.cache_data)
        friends_opts_map, friends_default_labels = build_friends_opts_map_fn(
            db_path, xuid.strip(), db_key, aliases_key
        )
        picked_friend_labels = st.session_state.get("friends_picked_labels")
        if not isinstance(picked_friend_labels, list) or not picked_friend_labels:
            picked_friend_labels = friends_default_labels
        picked_xuids = [
            friends_opts_map[lbl] for lbl in picked_friend_labels if lbl in friends_opts_map
        ]
        if len(picked_xuids) < 2:
            return None

        f1_xuid, f2_xuid = picked_xuids[0], picked_xuids[1]

        # Utiliser la fonction cachée avec TTL pour les requêtes coûteuses
        trio_ids_tuple = _cached_get_trio_match_ids(db_path, xuid.strip(), f1_xuid, f2_xuid, db_key)
        if not trio_ids_tuple:
            return None

        trio_ids = set(trio_ids_tuple)

        # Filtrer par les matchs disponibles dans base_for_filters
        base_match_ids = set(base_for_filters["match_id"].astype(str))
        trio_ids = trio_ids & base_match_ids

        if not trio_ids:
            return None

        # Trouver la dernière session trio
        trio_rows = base_s_ui.loc[base_s_ui["match_id"].astype(str).isin(trio_ids)].copy()
        if trio_rows.empty:
            return None

        latest_sid = int(trio_rows["session_id"].max())
        latest_labels = (
            trio_rows.loc[trio_rows["session_id"] == latest_sid, "session_label"]
            .dropna()
            .unique()
            .tolist()
        )
        return latest_labels[0] if latest_labels else None
    except Exception:
        return None


def _render_trio_button(trio_label: str | None) -> None:
    """Rend le bouton Dernière session en trio."""
    st.session_state["_trio_latest_session_label"] = trio_label
    disabled_trio = not isinstance(trio_label, str) or not trio_label
    if st.button("Dernière session en trio", width="stretch", disabled=disabled_trio):
        st.session_state["_pending_filter_mode"] = "Sessions"
        st.session_state["_pending_picked_session_label"] = trio_label
        st.session_state["_pending_picked_sessions"] = [trio_label]
        st.session_state["min_matches_maps"] = 1
        st.session_state["_min_matches_maps_auto"] = True
        st.session_state["min_matches_maps_friends"] = 1
        st.session_state["_min_matches_maps_friends_auto"] = True
        st.rerun()
    if disabled_trio:
        st.caption('Trio : sélectionne 2 amis dans "Avec mes amis" pour activer.')
    else:
        st.caption(f"Trio : {trio_label}")


def _render_cascade_filters(
    base_for_filters: pd.DataFrame,
    filter_mode: str,
    start_d: date,
    end_d: date,
    picked_session_labels: list[str] | None,
    base_s_ui: pd.DataFrame | None,
    clean_asset_label_fn: Callable[[str], str],
    normalize_mode_label_fn: Callable[[str], str],
    normalize_map_label_fn: Callable[[str], str],
) -> tuple[list[str], list[str], list[str]]:
    """Rend les filtres cascade Playlists -> Modes -> Cartes."""
    dropdown_base = base_for_filters.copy()

    if filter_mode == "Période":
        dropdown_base = dropdown_base.loc[
            (dropdown_base["date"] >= start_d) & (dropdown_base["date"] <= end_d)
        ].copy()
    else:
        if picked_session_labels and base_s_ui is not None:
            dropdown_base = base_s_ui.loc[
                base_s_ui["session_label"].isin(picked_session_labels)
            ].copy()
        elif base_s_ui is not None:
            dropdown_base = base_s_ui.copy()

    dropdown_base["playlist_ui"] = (
        dropdown_base["playlist_name"].apply(clean_asset_label_fn).apply(translate_playlist_name)
    )
    dropdown_base["mode_ui"] = dropdown_base["pair_name"].apply(normalize_mode_label_fn)
    dropdown_base["map_ui"] = dropdown_base["map_name"].apply(normalize_map_label_fn)

    # --- Playlists ---
    playlist_values = sorted(
        {str(x).strip() for x in dropdown_base["playlist_ui"].dropna().tolist() if str(x).strip()}
    )
    preferred_order = ["Partie rapide", "Arène classée", "Assassin classé"]
    playlist_values = [p for p in preferred_order if p in playlist_values] + [
        p for p in playlist_values if p not in preferred_order
    ]

    firefight_playlists = get_firefight_playlists(playlist_values)
    playlists_selected = render_checkbox_filter(
        label="Playlists",
        options=playlist_values,
        session_key="filter_playlists",
        default_unchecked=firefight_playlists,
        expanded=False,
    )

    # Scope après filtre playlist
    scope1 = dropdown_base
    if playlists_selected and len(playlists_selected) < len(playlist_values):
        scope1 = scope1.loc[scope1["playlist_ui"].fillna("").isin(playlists_selected)].copy()

    # --- Modes ---
    mode_values = sorted(
        {str(x).strip() for x in scope1["mode_ui"].dropna().tolist() if str(x).strip()}
    )
    modes_selected = render_hierarchical_checkbox_filter(
        label="Modes",
        options=mode_values,
        session_key="filter_modes",
        expanded=False,
    )

    # Scope après filtre mode
    scope2 = scope1
    if modes_selected and len(modes_selected) < len(mode_values):
        scope2 = scope2.loc[scope2["mode_ui"].fillna("").isin(modes_selected)].copy()

    # --- Cartes ---
    map_values = sorted(
        {str(x).strip() for x in scope2["map_ui"].dropna().tolist() if str(x).strip()}
    )
    maps_selected = render_checkbox_filter(
        label="Cartes",
        options=map_values,
        session_key="filter_maps",
        expanded=False,
    )

    return playlists_selected, modes_selected, maps_selected


def apply_filters(
    dff: pd.DataFrame,
    filter_state: FilterState,
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
    clean_asset_label_fn: Callable[[str], str],
    normalize_mode_label_fn: Callable[[str], str],
    normalize_map_label_fn: Callable[[str], str],
) -> pd.DataFrame:
    """Applique tous les filtres au DataFrame.

    Args:
        dff: DataFrame de base.
        filter_state: État des filtres depuis render_filters_sidebar.

    Returns:
        DataFrame filtré.
    """
    from src.ui.perf import perf_section

    with perf_section("filters/apply"):
        if filter_state.filter_mode == "Sessions":
            base_s = cached_compute_sessions_db(
                db_path, xuid.strip(), db_key, True, filter_state.gap_minutes
            )
            dff = (
                base_s.loc[base_s["session_label"].isin(filter_state.picked_session_labels)].copy()
                if filter_state.picked_session_labels
                else base_s.copy()
            )
        else:
            dff = dff.copy()

        if "playlist_fr" not in dff.columns:
            dff["playlist_fr"] = dff["playlist_name"].apply(translate_playlist_name)
        if "pair_fr" not in dff.columns:
            dff["pair_fr"] = dff["pair_name"].apply(translate_pair_name)

    if "playlist_ui" not in dff.columns:
        dff["playlist_ui"] = (
            dff["playlist_name"].apply(clean_asset_label_fn).apply(translate_playlist_name)
        )
    if "mode_ui" not in dff.columns:
        dff["mode_ui"] = dff["pair_name"].apply(normalize_mode_label_fn)
    if "map_ui" not in dff.columns:
        dff["map_ui"] = dff["map_name"].apply(normalize_map_label_fn)

    # Debug: Afficher l'état des filtres avant application
    # Désactivé par défaut - peut être activé via session_state["_show_debug_info"] = True
    show_debug = st.session_state.get("_show_debug_info", False)
    if show_debug:
        st.write(
            f"🔍 **Debug filtres** - Avant application des filtres checkboxes: {len(dff)} matchs"
        )
        st.write(
            f"- Playlists sélectionnées: {filter_state.playlists_selected if filter_state.playlists_selected else 'Toutes'}"
        )
        st.write(
            f"- Modes sélectionnés: {filter_state.modes_selected if filter_state.modes_selected else 'Tous'}"
        )
        st.write(
            f"- Cartes sélectionnées: {filter_state.maps_selected if filter_state.maps_selected else 'Toutes'}"
        )
        # Vérifier les matchs récents qui pourraient être exclus
        recent_matches = dff.sort_values("start_time", ascending=False).head(5)
        st.write("**5 matchs les plus récents avant filtres checkboxes:**")
        for _, row in recent_matches.iterrows():
            map_ui = (
                row.get("map_ui")
                if "map_ui" in row
                else normalize_map_label_fn(row.get("map_name"))
            )
            playlist_ui = (
                row.get("playlist_ui") if "playlist_ui" in row else (row.get("playlist_name") or "")
            )
            mode_ui = (
                row.get("mode_ui")
                if "mode_ui" in row
                else normalize_mode_label_fn(row.get("pair_name"))
            )
            st.write(
                f"- {row.get('start_time')} | Map: {map_ui} | Playlist: {playlist_ui} | Mode: {mode_ui}"
            )

    # Application des filtres checkboxes
    if filter_state.playlists_selected:
        before = len(dff)
        dff = dff.loc[dff["playlist_ui"].fillna("").isin(filter_state.playlists_selected)]
        if show_debug:
            st.write(f"🔍 Après filtre playlists: {before} → {len(dff)} matchs")
            null_playlists = dff["playlist_ui"].isna().sum()
            if null_playlists > 0:
                st.warning(f"⚠️ {null_playlists} matchs avec playlist_ui=NULL exclus par le filtre")
    if filter_state.modes_selected:
        before = len(dff)
        dff = dff.loc[dff["mode_ui"].fillna("").isin(filter_state.modes_selected)]
        if show_debug:
            st.write(f"🔍 Après filtre modes: {before} → {len(dff)} matchs")
            null_modes = dff["mode_ui"].isna().sum()
            if null_modes > 0:
                st.warning(f"⚠️ {null_modes} matchs avec mode_ui=NULL exclus par le filtre")
    if filter_state.maps_selected:
        before = len(dff)
        dff = dff.loc[dff["map_ui"].fillna("").isin(filter_state.maps_selected)]
        if show_debug:
            st.write(f"🔍 Après filtre cartes: {before} → {len(dff)} matchs")
            null_maps = dff["map_ui"].isna().sum()
            if null_maps > 0:
                st.warning(f"⚠️ {null_maps} matchs avec map_ui=NULL exclus par le filtre")

    if filter_state.filter_mode == "Période":
        before = len(dff)
        mask = (dff["date"] >= filter_state.start_d) & (dff["date"] <= filter_state.end_d)
        dff = dff.loc[mask].copy()
        if show_debug:
            st.write(
                f"🔍 Après filtre période ({filter_state.start_d} à {filter_state.end_d}): {before} → {len(dff)} matchs"
            )

    return dff
