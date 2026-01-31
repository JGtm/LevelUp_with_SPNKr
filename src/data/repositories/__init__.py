"""
Repositories : Accès aux données avec pattern Shadow Module.
(Repositories: Data access with Shadow Module pattern)

Ce module implémente le pattern "Shadow Module" pour permettre
une migration progressive de l'ancien vers le nouveau système.
"""

from src.data.repositories.protocol import DataRepository
from src.data.repositories.legacy import LegacyRepository
from src.data.repositories.hybrid import HybridRepository
from src.data.repositories.shadow import ShadowRepository
from src.data.repositories.factory import get_repository, RepositoryMode

__all__ = [
    "DataRepository",
    "LegacyRepository", 
    "HybridRepository",
    "ShadowRepository",
    "get_repository",
    "RepositoryMode",
]
