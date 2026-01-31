"""
Factory pour la création des repositories.
(Factory for repository creation)

HOW IT WORKS:
Ce module fournit une interface simple pour créer le bon repository
selon le mode de fonctionnement souhaité.

Usage:
    from src.data import get_repository, RepositoryMode
    
    # Utiliser le système legacy (par défaut)
    repo = get_repository(db_path, xuid, mode=RepositoryMode.LEGACY)
    
    # Utiliser le mode shadow pour migration progressive
    repo = get_repository(db_path, xuid, mode=RepositoryMode.SHADOW)
    
    # Utiliser le nouveau système hybrid
    repo = get_repository(db_path, xuid, mode=RepositoryMode.HYBRID)
"""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from src.data.repositories.legacy import LegacyRepository
from src.data.repositories.hybrid import HybridRepository
from src.data.repositories.shadow import ShadowRepository, ShadowMode

if TYPE_CHECKING:
    from src.data.repositories.protocol import DataRepository


class RepositoryMode(Enum):
    """
    Modes de repository disponibles.
    (Available repository modes)
    """
    LEGACY = "legacy"           # Système actuel (JSON/SQLite)
    HYBRID = "hybrid"           # Nouveau système (Parquet/DuckDB)
    SHADOW = "shadow"           # Mode migration (lit legacy, écrit hybrid)
    SHADOW_COMPARE = "compare"  # Mode validation (compare legacy et hybrid)


def get_repository(
    db_path: str,
    xuid: str,
    *,
    mode: RepositoryMode | str = RepositoryMode.LEGACY,
    warehouse_path: str | Path | None = None,
) -> "DataRepository":
    """
    Crée et retourne le repository approprié.
    (Create and return the appropriate repository)
    
    Args:
        db_path: Chemin vers la DB SQLite (legacy ou metadata)
        xuid: XUID du joueur principal
        mode: Mode de repository (legacy, hybrid, shadow, compare)
        warehouse_path: Chemin optionnel vers le warehouse pour les modes hybrid/shadow
        
    Returns:
        Instance de DataRepository (Legacy, Hybrid, ou Shadow)
        
    Exemple:
        # Mode par défaut (legacy)
        repo = get_repository("data/player.db", "1234567890")
        
        # Mode shadow pour migration
        repo = get_repository(
            "data/player.db",
            "1234567890",
            mode=RepositoryMode.SHADOW,
            warehouse_path="data/warehouse",
        )
    """
    # Normalise le mode si c'est une string
    if isinstance(mode, str):
        mode = RepositoryMode(mode.lower())
    
    # Détermine le warehouse_path par défaut
    if warehouse_path is None:
        db_parent = Path(db_path).parent
        warehouse_path = db_parent / "warehouse"
    
    if mode == RepositoryMode.LEGACY:
        return LegacyRepository(db_path, xuid)
    
    elif mode == RepositoryMode.HYBRID:
        return HybridRepository(warehouse_path, xuid, legacy_db_path=db_path)
    
    elif mode == RepositoryMode.SHADOW:
        return ShadowRepository(
            db_path,
            xuid,
            warehouse_path=warehouse_path,
            mode=ShadowMode.SHADOW_READ,
        )
    
    elif mode == RepositoryMode.SHADOW_COMPARE:
        return ShadowRepository(
            db_path,
            xuid,
            warehouse_path=warehouse_path,
            mode=ShadowMode.SHADOW_COMPARE,
        )
    
    else:
        raise ValueError(f"Mode de repository inconnu: {mode}")


def get_default_mode() -> RepositoryMode:
    """
    Retourne le mode par défaut basé sur la configuration.
    (Return default mode based on configuration)
    
    Lit la variable d'environnement OPENSPARTAN_REPOSITORY_MODE.
    """
    mode_str = os.environ.get("OPENSPARTAN_REPOSITORY_MODE", "legacy")
    try:
        return RepositoryMode(mode_str.lower())
    except ValueError:
        return RepositoryMode.LEGACY


def is_migration_complete(db_path: str, xuid: str) -> bool:
    """
    Vérifie si la migration est complète pour un joueur.
    (Check if migration is complete for a player)
    
    Une migration est considérée complète si :
    - Les données Parquet existent
    - Le nombre de lignes Parquet >= nombre legacy
    """
    try:
        shadow = ShadowRepository(db_path, xuid)
        progress = shadow.get_migration_progress()
        return progress.get("is_complete", False)
    except Exception:
        return False
