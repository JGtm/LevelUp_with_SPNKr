"""
Module data : Architecture DuckDB native.
(Data module: Native DuckDB architecture)

Architecture v4 : Toutes les données sont stockées dans DuckDB.
Les anciens modes (Legacy, Hybrid, Shadow) ont été supprimés.

HOW IT WORKS:
1. DataRepository : Interface abstraite définissant le contrat d'accès aux données
2. DuckDBRepository : Implémentation v4 utilisant DuckDB natif (stats.duckdb)

Usage recommandé:
    from src.data import get_repository_from_profile

    # Via gamertag
    repo = get_repository_from_profile("JGtm")
    matches = repo.load_matches()

Usage explicite:
    from src.data import get_repository

    # Mode DuckDB natif (v4)
    repo = get_repository(
        "data/players/JGtm/stats.duckdb",
        xuid,
    )
"""

# Re-export du module d'intégration pour l'UI
from src.data.integration import (
    get_analytics_for_ui,
    get_repository_for_player,
    get_repository_for_ui,
    get_repository_mode_from_settings,
    get_trends_for_ui,
    load_matches_df,
    matches_to_dataframe,
)
from src.data.repositories.factory import (
    RepositoryMode,
    get_repository,
    get_repository_from_profile,
    load_db_profiles,
)
from src.data.repositories.protocol import DataRepository

__all__ = [
    # Core
    "get_repository",
    "get_repository_from_profile",
    "load_db_profiles",
    "RepositoryMode",
    "DataRepository",
    # Intégration UI
    "load_matches_df",
    "get_repository_for_ui",
    "get_repository_for_player",
    "get_analytics_for_ui",
    "get_trends_for_ui",
    "matches_to_dataframe",
    "get_repository_mode_from_settings",
]
