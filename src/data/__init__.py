"""
Module data : Architecture hybride SQLite + DuckDB + Parquet.
(Data module: Hybrid SQLite + DuckDB + Parquet architecture)

Ce module implémente le pattern "Shadow Module" pour permettre une migration
progressive de l'ancien système (JSON dans SQLite) vers le nouveau système
(SQLite métadonnées + Parquet faits + DuckDB requêtes).

HOW IT WORKS:
1. DataRepository : Interface abstraite définissant le contrat d'accès aux données
2. LegacyRepository : Implémentation utilisant le système actuel (src/db/loaders)
3. HybridRepository : Implémentation utilisant le système Parquet + DuckDB
4. DuckDBRepository : Implémentation v4 utilisant DuckDB natif (stats.duckdb)
5. ShadowRepository : Orchestrateur pour migration progressive

Usage (recommandé - v4 architecture):
    from src.data import get_repository_from_profile

    # Via gamertag (auto-détection du mode)
    repo = get_repository_from_profile("JGtm")
    matches = repo.load_matches()

Usage (explicite):
    from src.data import get_repository, RepositoryMode

    # Mode DuckDB natif (v4)
    repo = get_repository(
        "data/players/JGtm/stats.duckdb",
        xuid,
        mode=RepositoryMode.DUCKDB,
    )

    # Mode legacy (ancien système)
    repo = get_repository(db_path, xuid, mode=RepositoryMode.LEGACY)
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
