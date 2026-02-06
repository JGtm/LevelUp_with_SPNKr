"""LevelUp - Dashboard Streamlit.

Application de visualisation des statistiques Halo Infinite
depuis la base de données SPNKr.
"""

import contextlib
import logging
import os
import threading
import urllib.parse

import streamlit as st

# Suppression des warnings connus et non bloquants
logging.getLogger("streamlit.runtime.caching.cache_data_api").setLevel(logging.ERROR)

from src.app.data_loader import (
    default_identity_from_secrets,
    ensure_h5g_commendations_repo,
    init_source_state,
)
from src.app.filters import (
    build_friends_opts_map,
)
from src.app.filters_render import (
    apply_filters,
    render_filters_sidebar,
)

# Phase 1 refactoring: Import des nouveaux modules app
# Phase 2 refactoring: Helpers et fonctions extraites
from src.app.helpers import (
    assign_player_colors,
    avg_match_duration_seconds,
    clean_asset_label,
    compute_session_span_seconds,
    compute_total_play_seconds,
    date_range,
    normalize_map_label,
    normalize_mode_label,
    styler_map,
)

# Phase 5 refactoring: KPIs et Filtres
from src.app.kpis_render import (
    render_kpis_section,
    render_performance_info,
)
from src.app.main_helpers import (
    apply_settings_path_overrides as apply_settings_overrides_main,
)

# Phase 4 refactoring: Main helpers
from src.app.main_helpers import (
    load_match_dataframe,
    load_profile_api,
    propagate_identity_to_env,
    render_profile_hero,
    resolve_xuid_from_input,
    validate_and_fix_db_path,
)

# Phase 4 refactoring: Page router
from src.app.page_router import (
    build_match_view_params,
    consume_pending_match_id,
    consume_pending_page,
    dispatch_page,
    render_page_selector,
)

# Imports depuis la nouvelle architecture
from src.config import (
    get_aliases_file_path,
    get_default_db_path,
)
from src.ui import (
    AppSettings,
    display_name_from_xuid,
    load_css,
    load_settings,
)
from src.ui.cache import (
    cached_compute_sessions_db,
    cached_list_local_dbs,
    cached_load_highlight_events_for_match,
    cached_load_match_medals_for_player,
    cached_load_match_player_gamertags,
    cached_load_match_rosters,
    cached_load_player_match_result,
    clear_app_caches,
    db_cache_key,
    top_medals_smart,
)
from src.ui.filter_state import _get_player_key, apply_filter_preferences, save_filter_preferences
from src.ui.formatting import (
    PARIS_TZ,
    format_datetime_fr_hm,
    format_score_label,
    score_css_color,
)
from src.ui.multiplayer import (
    get_gamertag_from_duckdb_v4_path,
    render_player_selector_unified,
)
from src.ui.pages import (
    render_citations_page,
    render_last_match_page,
    render_match_history_page,
    render_match_search_page,
    render_match_view,
    render_media_library_page,
    render_session_comparison_page,
    render_settings_page,
    render_teammates_page,
    render_timeseries_page,
    render_win_loss_page,
)
from src.ui.perf import perf_reset_run, perf_section
from src.ui.sync import (
    cleanup_orphan_tmp_dbs,
    is_spnkr_db_path,
    render_sync_indicator,
    sync_all_players,
)
from src.visualization import (
    plot_multi_metric_bars_by_match,
)

# =============================================================================
# Aliases vers les fonctions extraites (Phase 2)
# =============================================================================
_default_identity_from_secrets = default_identity_from_secrets
_init_source_state = init_source_state
_ensure_h5g_commendations_repo = ensure_h5g_commendations_repo
_clean_asset_label = clean_asset_label
_normalize_mode_label = normalize_mode_label
_normalize_map_label = normalize_map_label
_styler_map = styler_map
_assign_player_colors = assign_player_colors
_compute_session_span_seconds = compute_session_span_seconds
_compute_total_play_seconds = compute_total_play_seconds
_avg_match_duration_seconds = avg_match_duration_seconds
_date_range = date_range
_build_friends_opts_map = build_friends_opts_map


def _qp_first(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list | tuple):
        return str(value[0]) if value else None
    s = str(value)
    return s if s.strip() else None


def _set_query_params(**kwargs: str) -> None:
    clean: dict[str, str] = {
        k: str(v) for k, v in kwargs.items() if v is not None and str(v).strip()
    }
    try:
        st.query_params.clear()
        for k, v in clean.items():
            st.query_params[k] = v
    except Exception:
        # Fallback API legacy (compat)
        with contextlib.suppress(Exception):
            st.experimental_set_query_params(**clean)


def _app_url(page: str, **params: str) -> str:
    qp: dict[str, str] = {"page": page}
    for k, v in params.items():
        if v is None:
            continue
        s = str(v).strip()
        if s:
            qp[k] = s
    return "?" + urllib.parse.urlencode(qp)


def _clear_min_matches_maps_auto() -> None:
    st.session_state["_min_matches_maps_auto"] = False


def _clear_min_matches_maps_friends_auto() -> None:
    st.session_state["_min_matches_maps_friends_auto"] = False


# Alias pour les fonctions déplacées vers cache.py
_db_cache_key = db_cache_key
_top_medals = top_medals_smart
_clear_app_caches = clear_app_caches


def _aliases_cache_key() -> int | None:
    try:
        p = get_aliases_file_path()
        st_ = os.stat(p)
        return int(getattr(st_, "st_mtime_ns", int(st_.st_mtime * 1e9)))
    except OSError:
        return None


def _background_media_indexing(settings, db_path: str) -> None:
    """Lance l'indexation des médias en arrière-plan (non-bloquant).

    Args:
        settings: Paramètres de l'application.
        db_path: Chemin vers la DB DuckDB (utilisée pour stocker les médias).
    """
    import logging

    logger = logging.getLogger(__name__)

    # Vérifier si les médias sont activés
    if not bool(getattr(settings, "media_enabled", True)):
        logger.debug("Indexation médias désactivée dans les paramètres")
        return

    # Vérifier si les dossiers sont configurés
    videos_dir = str(getattr(settings, "media_videos_dir", "") or "").strip()
    screens_dir = str(getattr(settings, "media_screens_dir", "") or "").strip()

    if not videos_dir and not screens_dir:
        logger.debug("Aucun dossier média configuré - indexation ignorée")
        return

    # Vérifier si c'est une DB DuckDB v4
    if not db_path or not db_path.endswith(".duckdb"):
        logger.debug(f"DB non DuckDB ou invalide: {db_path} - indexation ignorée")
        return

    # Ne lancer qu'une fois par session
    if st.session_state.get("_media_indexing_started"):
        logger.debug("Indexation médias déjà démarrée dans cette session")
        return

    st.session_state["_media_indexing_started"] = True
    logger.info("🚀 Démarrage indexation médias en arrière-plan")

    def worker():
        """Worker thread pour l'indexation."""
        import logging

        logger = logging.getLogger(__name__)

        try:
            from pathlib import Path

            from src.data.media_indexer import MediaIndexer

            logger.info(f"📁 Indexation médias - DB: {db_path}")
            logger.info(f"   Vidéos: {videos_dir or '(non configuré)'}")
            logger.info(f"   Captures: {screens_dir or '(non configuré)'}")

            # Créer l'indexeur (utilise la DB fournie pour stocker les médias)
            indexer = MediaIndexer(Path(db_path))

            # Scanner les dossiers
            videos_path = Path(videos_dir) if videos_dir and os.path.exists(videos_dir) else None
            screens_path = (
                Path(screens_dir) if screens_dir and os.path.exists(screens_dir) else None
            )

            if not videos_path and not screens_path:
                logger.warning("Aucun dossier média valide trouvé - indexation ignorée")
                return

            logger.info("📂 Scan des dossiers médias...")
            result = indexer.scan_and_index(
                videos_dir=videos_path,
                screens_dir=screens_path,
                force_rescan=False,
            )

            logger.info(
                f"✅ Scan terminé: {result.n_scanned} scannés, "
                f"{result.n_new} nouveaux, {result.n_updated} mis à jour"
            )

            if result.errors:
                logger.warning(f"⚠️  {len(result.errors)} erreur(s) lors du scan")
                for err in result.errors[:5]:
                    logger.warning(f"   - {err}")

            # Associer avec les matchs de TOUS les joueurs
            tolerance = int(getattr(settings, "media_tolerance_minutes", 5) or 5)
            logger.info(f"🔗 Association avec les matchs (tolérance: {tolerance} min)...")
            n_associated = indexer.associate_with_matches(tolerance_minutes=tolerance)
            logger.info(f"✅ {n_associated} association(s) créée(s)")

            # Générer les thumbnails pour les nouvelles vidéos
            if videos_path:
                logger.info("🎬 Génération des thumbnails...")
                n_thumb_gen, n_thumb_errors = indexer.generate_thumbnails_for_new(videos_path)
                if n_thumb_gen > 0:
                    logger.info(f"✅ {n_thumb_gen} thumbnail(s) généré(s)")
                if n_thumb_errors > 0:
                    logger.warning(
                        f"⚠️  {n_thumb_errors} erreur(s) lors de la génération de thumbnails"
                    )
                if n_thumb_gen == 0 and n_thumb_errors == 0:
                    logger.info("ℹ️  Aucune vidéo sans thumbnail à générer")

            logger.info("✅ Indexation médias terminée avec succès")

        except Exception as e:
            logger.error(f"❌ Erreur indexation médias: {e}", exc_info=True)

    # Lancer en thread daemon (ne bloque pas l'app)
    thread = threading.Thread(target=worker, daemon=True, name="media-indexer")
    thread.start()
    logger.debug(f"Thread d'indexation démarré: {thread.name} (daemon={thread.daemon})")


# =============================================================================
# Application principale
# =============================================================================


def main() -> None:
    """Point d'entrée principal de l'application Streamlit."""
    st.set_page_config(page_title="LevelUp", layout="wide")

    perf_reset_run()

    # Nettoyage des fichiers temporaires orphelins (une fois par session)
    cleanup_orphan_tmp_dbs()

    with perf_section("css"):
        st.markdown(load_css(), unsafe_allow_html=True)

    # IMPORTANT: aucun accès réseau implicite.
    # La génération du référentiel Citations doit être explicite (opt-in via env).
    if str(os.environ.get("OPENSPARTAN_CITATIONS_AUTOGEN") or "").strip() in {"1", "true", "True"}:
        _ensure_h5g_commendations_repo()

    # Paramètres (persistés)
    settings: AppSettings = load_settings()
    st.session_state["app_settings"] = settings

    # Propage les defaults depuis secrets vers l'env et applique les overrides de chemins
    propagate_identity_to_env()
    apply_settings_overrides_main(settings)

    # ==========================================================================
    # Source (persistée via session_state) — UI dans l'onglet Paramètres
    # ==========================================================================

    DEFAULT_DB = get_default_db_path()
    _init_source_state(DEFAULT_DB, settings)

    # ==========================================================================
    # Indexation médias en arrière-plan (non-bloquant)
    # ==========================================================================
    _background_media_indexing(settings, DEFAULT_DB)

    # Support liens internes via query params (?page=...&match_id=...)
    try:
        qp = dict(st.query_params)
        qp_page = _qp_first(qp.get("page"))
        qp_mid = _qp_first(qp.get("match_id"))
    except Exception:
        qp_page = None
        qp_mid = None
    qp_params = (str(qp_page or "").strip(), str(qp_mid or "").strip())
    if any(qp_params) and st.session_state.get("_consumed_query_params") != qp_params:
        st.session_state["_consumed_query_params"] = qp_params
        if qp_params[0]:
            st.session_state["_pending_page"] = qp_params[0]
        if qp_params[1]:
            st.session_state["_pending_match_id"] = qp_params[1]
        # Nettoie l'URL après consommation pour ne pas forcer la page en boucle.
        try:
            st.query_params.clear()
        except Exception:
            with contextlib.suppress(Exception):
                st.experimental_set_query_params()

    db_path = str(st.session_state.get("db_path", "") or "").strip()
    xuid = str(st.session_state.get("xuid_input", "") or "").strip()
    waypoint_player = str(st.session_state.get("waypoint_player", "") or "").strip()

    with st.sidebar:
        # Logo en haut de la sidebar
        logo_path = os.path.join(os.path.dirname(__file__), "static", "logo.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width="stretch")

        st.markdown(
            "<div class='os-sidebar-brand' style='font-size: 2.5em;'>LevelUp</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div class='os-sidebar-divider'></div>", unsafe_allow_html=True)

        # Indicateur de dernière synchronisation
        if db_path and os.path.exists(db_path):
            render_sync_indicator(db_path)

        # Sélecteur multi-joueurs (Legacy SQLite + DuckDB v4)
        if db_path and os.path.exists(db_path):
            new_db_path, new_xuid = render_player_selector_unified(
                db_path, xuid, key="sidebar_player_selector"
            )
            if new_db_path or new_xuid:
                # Changement de joueur : sauvegarder les filtres de l'ancien joueur
                old_xuid = xuid
                old_db_path = db_path
                with contextlib.suppress(Exception):
                    # Ne pas bloquer le changement de joueur si la sauvegarde échoue
                    save_filter_preferences(old_xuid, old_db_path)

                # Nettoyer les filtres de session_state pour forcer le rechargement
                filter_keys_to_clear = [
                    "filter_mode",
                    "start_date_cal",
                    "end_date_cal",
                    "gap_minutes",
                    "picked_session_label",
                    "picked_sessions",
                    "filter_playlists",
                    "filter_modes",
                    "filter_maps",
                ]
                for key in filter_keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]

                # Réinitialiser les flags de chargement et sauvegarde pour l'ancien joueur
                old_player_key = _get_player_key(old_xuid, old_db_path)
                old_filters_loaded_key = f"_filters_loaded_{old_player_key}"
                old_last_saved_key = f"_last_saved_player_{old_player_key}"
                if old_filters_loaded_key in st.session_state:
                    del st.session_state[old_filters_loaded_key]
                if old_last_saved_key in st.session_state:
                    del st.session_state[old_last_saved_key]

                # Mettre à jour db_path et xuid pour le nouveau joueur
                if new_db_path:
                    st.session_state["db_path"] = new_db_path
                    db_path = new_db_path
                    # Pour DuckDB v4, mettre à jour le gamertag comme xuid_input
                    gamertag = get_gamertag_from_duckdb_v4_path(new_db_path)
                    if gamertag:
                        st.session_state["xuid_input"] = gamertag
                        st.session_state["waypoint_player"] = gamertag
                        xuid = gamertag
                if new_xuid:
                    st.session_state["xuid_input"] = new_xuid
                    xuid = new_xuid

                # Charger les filtres sauvegardés pour le nouveau joueur
                # Le flag _filters_loaded sera vérifié dans render_filters_sidebar()
                # et comme on l'a supprimé pour l'ancien joueur, les filtres seront rechargés
                apply_filter_preferences(xuid, db_path)
                st.rerun()

        # Bouton Sync pour toutes les DB SPNKr (multi-joueurs si DB fusionnée)
        if db_path and is_spnkr_db_path(db_path) and os.path.exists(db_path):  # noqa: SIM102
            if st.button(
                "🔄 Synchroniser",
                key="sidebar_sync_button",
                help="Synchronise tous les joueurs (nouveaux matchs, highlights, aliases).",
                width="stretch",
            ):
                with st.spinner("Synchronisation en cours..."):
                    ok, msg = sync_all_players(
                        db_path=db_path,
                        match_type=str(
                            getattr(settings, "spnkr_refresh_match_type", "matchmaking")
                            or "matchmaking"
                        ),
                        max_matches=int(getattr(settings, "spnkr_refresh_max_matches", 200) or 200),
                        rps=int(getattr(settings, "spnkr_refresh_rps", 5) or 5),
                        with_highlight_events=True,
                        with_aliases=True,
                        delta=True,
                        timeout_seconds=180,
                    )
                if ok:
                    st.success(msg)
                    _clear_app_caches()
                    # Force cache invalidation avec un token de session
                    st.session_state["_cache_buster"] = st.session_state.get("_cache_buster", 0) + 1
                    st.rerun()
                else:
                    st.error(msg)

    # Validation du chemin DB
    db_path = validate_and_fix_db_path(db_path, DEFAULT_DB)

    # Résolution du XUID
    xuid = resolve_xuid_from_input(xuid, db_path)

    me_name = display_name_from_xuid(xuid.strip()) if str(xuid or "").strip() else "(joueur)"
    aliases_key = _aliases_cache_key()

    # Auto-profil (SPNKr) et rendu du hero
    api_app, _api_err = load_profile_api(xuid, settings)
    render_profile_hero(xuid, settings, api_app)

    # ==========================================================================
    # Chargement des données
    # ==========================================================================

    # Cache buster pour forcer le rechargement après sync
    cache_buster = st.session_state.get("_cache_buster", 0)
    df, db_key = load_match_dataframe(db_path, xuid, cache_buster=cache_buster)

    # Debug: Informations sur le DataFrame complet (avant filtres)
    # Désactivé par défaut - peut être activé via session_state["_show_debug_info"] = True
    show_debug = st.session_state.get("_show_debug_info", False)

    # Convertir Polars en Pandas pour compatibilité avec le reste du code UI
    # TODO: Migrer progressivement les pages UI vers Polars dans les tâches suivantes
    import polars as pl

    if isinstance(df, pl.DataFrame):
        df = df.to_pandas()

    if show_debug and not df.empty:
        st.info("🔍 **Mode Debug activé** - Informations sur les données chargées")
        with st.expander("🔍 Debug - DataFrame complet (avant filtres)", expanded=True):
            st.write(f"**Nombre total de matchs dans df** : {len(df)}")
            st.write(f"**Date min dans df** : {df['start_time'].min()}")
            st.write(f"**Date max dans df** : {df['start_time'].max()}")
            # Vérifier les valeurs NULL
            null_count = df["start_time"].isna().sum()
            st.write(f"**Nombre de start_time NULL** : {null_count}")
            if null_count > 0:
                st.warning("⚠️ Il y a des valeurs NULL dans start_time !")
            # Afficher les 5 derniers matchs
            last_5_df = df.sort_values("start_time", ascending=False).head(5)
            st.write("**5 derniers matchs dans df (par date) :**")
            for _, row in last_5_df.iterrows():
                st.write(
                    f"- {row.get('start_time')} | Match ID: {row.get('match_id')} | Map: {row.get('map_name')}"
                )

    if df.empty:
        st.radio(
            "Navigation",
            options=["Paramètres"],
            horizontal=True,
            key="page",
            label_visibility="collapsed",
        )
        render_settings_page(
            settings,
            get_local_dbs_fn=cached_list_local_dbs,
            on_clear_caches_fn=_clear_app_caches,
        )
        return

    # ==========================================================================
    # Sidebar - Filtres
    # ==========================================================================

    with st.sidebar:
        filter_state = render_filters_sidebar(
            df=df,
            db_path=db_path,
            xuid=xuid,
            db_key=db_key,
            aliases_key=aliases_key,
            date_range_fn=_date_range,
            clean_asset_label_fn=_clean_asset_label,
            normalize_mode_label_fn=_normalize_mode_label,
            normalize_map_label_fn=_normalize_map_label,
            build_friends_opts_map_fn=_build_friends_opts_map,
        )

    # Base "globale" : toutes les parties (après inclusion/exclusion Firefight)
    base = df.copy()

    # ==========================================================================
    # Application des filtres
    # ==========================================================================

    dff = apply_filters(
        dff=df,
        filter_state=filter_state,
        db_path=db_path,
        xuid=xuid,
        db_key=db_key,
        clean_asset_label_fn=_clean_asset_label,
        normalize_mode_label_fn=_normalize_mode_label,
        normalize_map_label_fn=_normalize_map_label,
    )

    # Variables pour compatibilité avec le dispatch
    gap_minutes = filter_state.gap_minutes
    picked_session_labels = filter_state.picked_session_labels

    # ==========================================================================
    # KPIs
    # ==========================================================================

    render_kpis_section(dff)
    render_performance_info()

    # ==========================================================================
    # Pages (navigation)
    # ==========================================================================

    consume_pending_page()
    consume_pending_match_id()
    page = render_page_selector()

    # Paramètres communs pour les pages de match
    _match_view_params = build_match_view_params(
        db_path=db_path,
        xuid=xuid,
        waypoint_player=waypoint_player,
        db_key=db_key,
        settings=settings,
        df_full=df,
        render_match_view_fn=render_match_view,
        normalize_mode_label_fn=_normalize_mode_label,
        format_score_label_fn=format_score_label,
        score_css_color_fn=score_css_color,
        format_datetime_fn=format_datetime_fr_hm,
        load_player_match_result_fn=cached_load_player_match_result,
        load_match_medals_fn=cached_load_match_medals_for_player,
        load_highlight_events_fn=cached_load_highlight_events_for_match,
        load_match_gamertags_fn=cached_load_match_player_gamertags,
        load_match_rosters_fn=cached_load_match_rosters,
        paris_tz=PARIS_TZ,
    )

    # Dispatch vers la page appropriée
    dispatch_page(
        page=page,
        dff=dff,
        df=df,
        base=base,
        me_name=me_name,
        xuid=xuid,
        db_path=db_path,
        db_key=db_key,
        aliases_key=aliases_key,
        settings=settings,
        picked_session_labels=picked_session_labels,
        waypoint_player=waypoint_player,
        gap_minutes=gap_minutes,
        match_view_params=_match_view_params,
        # Fonctions de rendu
        render_last_match_page_fn=render_last_match_page,
        render_match_search_page_fn=render_match_search_page,
        render_citations_page_fn=render_citations_page,
        render_session_comparison_page_fn=render_session_comparison_page,
        render_timeseries_page_fn=render_timeseries_page,
        render_win_loss_page_fn=render_win_loss_page,
        render_teammates_page_fn=render_teammates_page,
        render_match_history_page_fn=render_match_history_page,
        render_media_library_page_fn=render_media_library_page,
        render_settings_page_fn=render_settings_page,
        # Fonctions utilitaires
        cached_compute_sessions_db_fn=cached_compute_sessions_db,
        top_medals_fn=_top_medals,
        build_friends_opts_map_fn=_build_friends_opts_map,
        assign_player_colors_fn=_assign_player_colors,
        plot_multi_metric_bars_fn=plot_multi_metric_bars_by_match,
        get_local_dbs_fn=cached_list_local_dbs,
        clear_caches_fn=_clear_app_caches,
    )


if __name__ == "__main__":
    main()
