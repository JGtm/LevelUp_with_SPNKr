"""
Repositories : Accès aux données avec pattern Shadow Module.
(Repositories: Data access with Shadow Module pattern)

Ce module implémente le pattern "Shadow Module" pour permettre
une migration progressive de l'ancien vers le nouveau système.

Architecture v4 : Utiliser DuckDBRepository via get_repository_from_profile().
"""

from src.data.repositories.duckdb_repo import DuckDBRepository
from src.data.repositories.factory import (
    RepositoryMode,
    get_repository,
    get_repository_from_profile,
    load_db_profiles,
)
from src.data.repositories.hybrid import HybridRepository
from src.data.repositories.legacy import LegacyRepository
from src.data.repositories.protocol import DataRepository
from src.data.repositories.shadow import ShadowRepository

__all__ = [
    "DataRepository",
    "LegacyRepository",
    "HybridRepository",
    "ShadowRepository",
    "DuckDBRepository",
    "get_repository",
    "get_repository_from_profile",
    "load_db_profiles",
    "RepositoryMode",
]
