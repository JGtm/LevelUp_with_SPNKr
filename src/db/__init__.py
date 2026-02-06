"""Module de gestion de la base de données."""

from src.db.connection import (
    DatabaseConnection,
    SQLiteForbiddenError,
    get_connection,
)
from src.db.loaders import (
    get_players_from_db,
    get_sync_metadata,
    has_table,
    list_other_player_xuids,
    list_top_teammates,
    load_asset_name_map,
    load_highlight_events_for_match,
    load_match_medals_for_player,
    load_match_player_gamertags,
    load_match_rosters,
    load_matches,
    load_player_match_result,
    load_top_medals,
    query_matches_with_friend,
)
from src.db.loaders_cached import (
    get_cache_stats,
    get_match_session_info,
    has_cache_tables,
    load_friends,
    load_matches_cached,
    load_session_matches_cached,
    load_sessions_cached,
    load_top_teammates_cached,
)
from src.db.parsers import (
    guess_xuid_from_db_path,
    infer_spnkr_player_from_db_path,
    parse_iso_utc,
    resolve_xuid_from_db,
)
from src.db.profiles import (
    PROFILES_PATH,
    list_local_dbs,
    load_profiles,
    save_profiles,
)

__all__ = [
    # connection
    "get_connection",
    "DatabaseConnection",
    # loaders (original - JSON parsing)
    "load_matches",
    "load_asset_name_map",
    "load_player_match_result",
    "load_top_medals",
    "load_match_medals_for_player",
    "load_match_rosters",
    "has_table",
    "load_highlight_events_for_match",
    "load_match_player_gamertags",
    "query_matches_with_friend",
    "list_other_player_xuids",
    "list_top_teammates",
    "get_sync_metadata",
    "get_players_from_db",
    # loaders_cached (optimized - from cache tables)
    "load_matches_cached",
    "load_sessions_cached",
    "load_session_matches_cached",
    "load_top_teammates_cached",
    "load_friends",
    "has_cache_tables",
    "get_cache_stats",
    "get_match_session_info",
    # parsers
    "guess_xuid_from_db_path",
    "parse_iso_utc",
    "resolve_xuid_from_db",
    "infer_spnkr_player_from_db_path",
    # profiles
    "PROFILES_PATH",
    "load_profiles",
    "save_profiles",
    "list_local_dbs",
]
