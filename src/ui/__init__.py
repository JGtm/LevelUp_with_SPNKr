"""Module UI - Gestion des alias, médailles et helpers d'interface."""

from src.ui.aliases import (
    display_name_from_xuid,
    get_xuid_aliases,
    load_aliases_file,
    save_aliases_file,
)
from src.ui.formatting import format_date_fr, format_mmss
from src.ui.medals import (
    get_local_medals_icons_dir,
    get_medals_cache_dir,
    load_medal_name_maps,
    medal_has_known_label,
    medal_icon_path,
    medal_label,
    render_medals_grid,
)
from src.ui.path_picker import directory_input, file_input
from src.ui.profile_api import ProfileAppearance, get_profile_appearance, get_xuid_for_gamertag
from src.ui.profile_api_tokens import ensure_spnkr_tokens
from src.ui.settings import AppSettings, load_settings, save_settings
from src.ui.styles import get_hero_html, load_css
from src.ui.translations import translate_pair_name, translate_playlist_name

__all__ = [
    # aliases
    "load_aliases_file",
    "save_aliases_file",
    "get_xuid_aliases",
    "display_name_from_xuid",
    # styles
    "load_css",
    "get_hero_html",
    # translations
    "translate_playlist_name",
    "translate_pair_name",
    # medals
    "load_medal_name_maps",
    "medal_has_known_label",
    "get_medals_cache_dir",
    "get_local_medals_icons_dir",
    "medal_label",
    "medal_icon_path",
    "render_medals_grid",
    # formatting
    "format_date_fr",
    "format_mmss",
    # settings
    "AppSettings",
    "load_settings",
    "save_settings",
    # profile api
    "ProfileAppearance",
    "get_profile_appearance",
    "get_xuid_for_gamertag",
    "ensure_spnkr_tokens",
    # path picker
    "directory_input",
    "file_input",
]
