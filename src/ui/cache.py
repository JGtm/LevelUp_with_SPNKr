"""Façade de rétro-compatibilité — re-export depuis cache_loaders / cache_filters.

DÉPRÉCIÉ : importer directement depuis src.ui.cache_loaders ou src.ui.cache_filters.
Ce fichier sera simplifié lors d'un futur sprint.

Extrait en Sprint 17 : cache.py (1337L) → cache_loaders.py (722L) + cache_filters.py (639L).
"""

from src.ui.cache_filters import (  # noqa: F401
    _get_repository_mode,
    _is_duckdb_analytics_enabled,
    cached_compute_sessions_db,
    cached_friend_matches_df,
    cached_get_global_stats_duckdb,
    cached_get_kda_trend_duckdb,
    cached_get_match_count_duckdb,
    cached_get_migration_status,
    cached_get_performance_by_map_duckdb,
    cached_load_matches_paginated,
    cached_load_recent_matches,
    load_df_hybrid,
)
from src.ui.cache_loaders import (  # noqa: F401
    PARIS_TZ_NAME,
    _is_duckdb_v4_path,
    _load_matches_duckdb_v4,
    _to_polars,
    cached_get_cache_stats,
    cached_get_match_session_info,
    cached_has_cache_tables,
    cached_list_local_dbs,
    cached_list_other_xuids,
    cached_list_top_teammates,
    cached_load_friends,
    cached_load_highlight_events_for_match,
    cached_load_match_medals_for_player,
    cached_load_match_player_gamertags,
    cached_load_match_rosters,
    cached_load_player_match_result,
    cached_load_top_medals,
    cached_load_top_teammates_optimized,
    cached_query_matches_with_friend,
    cached_same_team_match_ids_with_friend,
    clear_app_caches,
    db_cache_key,
    load_df_optimized,
    top_medals_smart,
)
