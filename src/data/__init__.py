"""
Module data : Architecture hybride SQLite + DuckDB + Parquet.
(Data module: Hybrid SQLite + DuckDB + Parquet architecture)

Ce module implémente le pattern "Shadow Module" pour permettre une migration
progressive de l'ancien système (JSON dans SQLite) vers le nouveau système
(SQLite métadonnées + Parquet faits + DuckDB requêtes).

HOW IT WORKS:
1. DataRepository : Interface abstraite définissant le contrat d'accès aux données
2. LegacyRepository : Implémentation utilisant le système actuel (src/db/loaders)
3. HybridRepository : Implémentation utilisant le nouveau système (Parquet + DuckDB)
4. ShadowRepository : Orchestrateur qui lit depuis Legacy et écrit en shadow vers Hybrid

Usage:
    from src.data import get_repository, RepositoryMode
    
    # Mode legacy (par défaut) - utilise l'ancien système
    repo = get_repository(db_path, xuid, mode=RepositoryMode.LEGACY)
    
    # Mode shadow - lit depuis legacy, écrit aussi vers hybrid
    repo = get_repository(db_path, xuid, mode=RepositoryMode.SHADOW)
    
    # Mode hybrid - utilise uniquement le nouveau système
    repo = get_repository(db_path, xuid, mode=RepositoryMode.HYBRID)
"""

from src.data.repositories.factory import get_repository, RepositoryMode
from src.data.repositories.protocol import DataRepository

__all__ = [
    "get_repository",
    "RepositoryMode",
    "DataRepository",
]
