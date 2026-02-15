"""
Repositories : Accès aux données via DuckDB.
(Repositories: Data access via DuckDB)

Architecture v4 : Utiliser DuckDBRepository via get_repository_from_profile().
Les anciens modes (Legacy, Hybrid, Shadow) ont été supprimés.
"""

from src.data.repositories.duckdb_repo import DuckDBRepository
from src.data.repositories.factory import (
    RepositoryMode,
    get_repository,
    get_repository_from_profile,
    load_db_profiles,
)
from src.data.repositories.protocol import DataRepository

__all__ = [
    "DataRepository",
    "DuckDBRepository",
    "get_repository",
    "get_repository_from_profile",
    "load_db_profiles",
    "RepositoryMode",
]
