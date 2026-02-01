"""Module application - Orchestration du dashboard.

Ce module contient la logique d'orchestration extraite de streamlit_app.py :
- state.py : Gestion centralisée du session_state
- routing.py : Navigation entre pages
- sidebar.py : Logique et rendu de la sidebar
- filters.py : Logique des filtres globaux
- helpers.py : Fonctions utilitaires génériques
- profile.py : Gestion du profil joueur
- kpis.py : Calcul et affichage des KPIs
- data_loader.py : Chargement et initialisation des données
- navigation.py : Rendu des pages
"""

from __future__ import annotations

from src.app.data_loader import (
    apply_settings_path_overrides as apply_settings_overrides,
)
from src.app.data_loader import (
    default_identity_from_secrets,
    ensure_h5g_commendations_repo,
    load_match_data,
    propagate_identity_env,
    resolve_xuid_input,
    validate_db_path,
)
from src.app.data_loader import (
    get_aliases_cache_key as aliases_cache_key,
)
from src.app.data_loader import (
    get_db_cache_key as db_cache_key,
)
from src.app.data_loader import (
    init_source_state as init_db_state,
)
from src.app.filters import (
    add_ui_columns,
    apply_checkbox_filters,
    apply_date_filter,
    build_friends_opts_map,
    consume_pending_filter_state,
    render_cascade_filters,
    render_date_filters,
    render_session_filters,
    reset_auto_min_matches,
)
from src.app.filters_render import (
    FilterState,
    apply_filters,
    render_filters_sidebar,
)
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
from src.app.kpis import (
    KPIStats,
    compute_kpi_stats,
    render_all_kpis,
    render_career_kpis,
    render_matches_summary,
)
from src.app.kpis_render import (
    render_kpis_section,
    render_performance_info,
)
from src.app.main_helpers import (
    apply_settings_path_overrides as apply_settings_overrides_main,
)
from src.app.main_helpers import (
    load_match_dataframe,
    load_profile_api,
    render_profile_hero,
    render_sidebar_header,
    resolve_xuid_from_input,
    validate_and_fix_db_path,
)

# navigation.py supprimé - remplacé par page_router.py
from src.app.main_helpers import (
    propagate_identity_to_env as propagate_identity_env_main,
)
from src.app.page_router import (
    PAGES as PAGES_ROUTER,
)
from src.app.page_router import (
    build_match_view_params,
    consume_pending_match_id,
    consume_pending_page,
    dispatch_page,
    render_page_selector,
)
from src.app.profile import (
    ProfileAssets,
    get_identity_from_secrets,
    load_profile_assets,
    propagate_identity_to_env,
    render_profile_header,
    resolve_xuid,
    warn_missing_assets,
)
from src.app.routing import (
    Page,
    Router,
    build_app_url,
    consume_query_params,
    get_current_page,
    navigate_to,
)
from src.app.sidebar import (
    render_player_selector_sidebar,
    render_sidebar,
    render_sync_button,
)
from src.app.state import (
    AppState,
    PlayerIdentity,
    apply_settings_path_overrides,
    get_aliases_cache_key,
    get_db_cache_key,
    get_default_identity,
    init_source_state,
    propagate_env_defaults,
)

__all__ = [
    # State
    "AppState",
    "PlayerIdentity",
    "init_source_state",
    "get_default_identity",
    "get_db_cache_key",
    "get_aliases_cache_key",
    "propagate_env_defaults",
    "apply_settings_path_overrides",
    # Routing
    "Page",
    "Router",
    "get_current_page",
    "navigate_to",
    "consume_query_params",
    "build_app_url",
    # Sidebar
    "render_sidebar",
    "render_sync_button",
    "render_player_selector_sidebar",
    # Helpers
    "clean_asset_label",
    "normalize_mode_label",
    "normalize_map_label",
    "assign_player_colors",
    "date_range",
    "styler_map",
    "compute_session_span_seconds",
    "compute_total_play_seconds",
    "avg_match_duration_seconds",
    # Filters
    "build_friends_opts_map",
    "add_ui_columns",
    "apply_date_filter",
    "apply_checkbox_filters",
    "render_date_filters",
    "render_session_filters",
    "render_cascade_filters",
    "consume_pending_filter_state",
    "reset_auto_min_matches",
    # Profile
    "ProfileAssets",
    "get_identity_from_secrets",
    "resolve_xuid",
    "propagate_identity_to_env",
    "load_profile_assets",
    "warn_missing_assets",
    "render_profile_header",
    # KPIs
    "KPIStats",
    "compute_kpi_stats",
    "render_matches_summary",
    "render_career_kpis",
    "render_all_kpis",
    # Data Loader
    "default_identity_from_secrets",
    "propagate_identity_env",
    "apply_settings_overrides",
    "init_db_state",
    "resolve_xuid_input",
    "validate_db_path",
    "db_cache_key",
    "aliases_cache_key",
    "load_match_data",
    "ensure_h5g_commendations_repo",
    # Navigation (voir page_router.py pour les nouvelles fonctions)
    # Main helpers
    "propagate_identity_env_main",
    "apply_settings_overrides_main",
    "validate_and_fix_db_path",
    "resolve_xuid_from_input",
    "render_sidebar_header",
    "load_profile_api",
    "render_profile_hero",
    "load_match_dataframe",
    # Page router
    "PAGES_ROUTER",
    "build_match_view_params",
    "consume_pending_page",
    "consume_pending_match_id",
    "render_page_selector",
    "dispatch_page",
    # KPIs render
    "render_kpis_section",
    "render_performance_info",
    # Filters render
    "FilterState",
    "render_filters_sidebar",
    "apply_filters",
]
