"""Utilitaires partagés pour le projet OpenSpartan Graph."""

from src.utils.paths import (
    ARCHIVE_DIR,
    DATA_DIR,
    PLAYERS_DIR,
    REPO_ROOT,
    WAREHOUSE_DIR,
    get_metadata_db_path,
    get_player_archive_dir,
    get_player_db_path,
    list_player_gamertags,
)
from src.utils.profiles import (
    PROFILES_PATH,
    get_profiles_path,
    list_local_dbs,
    load_profiles,
    save_profiles,
)
from src.utils.xuid import (
    XUID_DIGITS_RE,
    extract_gamertag_from_player_id,
    extract_xuid_from_player_id,
    guess_xuid_from_db_path,
    infer_spnkr_player_from_db_path,
    parse_xuid_input,
    resolve_xuid_from_db,
)

__all__ = [
    # paths
    "REPO_ROOT",
    "DATA_DIR",
    "PLAYERS_DIR",
    "WAREHOUSE_DIR",
    "ARCHIVE_DIR",
    "get_player_db_path",
    "get_player_archive_dir",
    "get_metadata_db_path",
    "list_player_gamertags",
    # profiles
    "PROFILES_PATH",
    "get_profiles_path",
    "load_profiles",
    "save_profiles",
    "list_local_dbs",
    # xuid
    "parse_xuid_input",
    "extract_xuid_from_player_id",
    "extract_gamertag_from_player_id",
    "resolve_xuid_from_db",
    "infer_spnkr_player_from_db_path",
    "guess_xuid_from_db_path",
    "XUID_DIGITS_RE",
]
