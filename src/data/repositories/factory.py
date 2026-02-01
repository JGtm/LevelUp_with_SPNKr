"""
Factory pour la création des repositories.
(Factory for repository creation)

HOW IT WORKS:
Ce module fournit une interface simple pour créer le bon repository
selon le mode de fonctionnement souhaité.

Architecture v2.1 (recommandée):
    Le mode DUCKDB est maintenant le mode par défaut pour les profils v2.0+.
    Utiliser get_repository_from_profile() pour auto-détection.

Usage recommandé (v2.1+):
    from src.data.repositories.factory import get_repository_from_profile

    # Auto-détection depuis db_profiles.json (recommandé)
    repo = get_repository_from_profile("JGtm")

Usage legacy (compatibilité):
    from src.data import get_repository, RepositoryMode

    # Utiliser le système legacy (déprécié)
    repo = get_repository(db_path, xuid, mode=RepositoryMode.LEGACY)

    # Utiliser DuckDB natif (architecture v4)
    repo = get_repository(
        "data/players/JGtm/stats.duckdb",
        xuid,
        mode=RepositoryMode.DUCKDB,
    )
"""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.data.repositories.duckdb_repo import DuckDBRepository
from src.data.repositories.hybrid import HybridRepository
from src.data.repositories.legacy import LegacyRepository
from src.data.repositories.shadow import ShadowMode, ShadowRepository

if TYPE_CHECKING:
    from src.data.repositories.protocol import DataRepository


class RepositoryMode(Enum):
    """
    Modes de repository disponibles.
    (Available repository modes)
    """

    LEGACY = "legacy"  # Système actuel (JSON/SQLite)
    HYBRID = "hybrid"  # Système intermédiaire (Parquet/DuckDB)
    SHADOW = "shadow"  # Mode migration (lit legacy, écrit hybrid)
    SHADOW_COMPARE = "compare"  # Mode validation (compare legacy et hybrid)
    DUCKDB = "duckdb"  # Nouveau système v4 (DuckDB natif)


def get_repository(
    db_path: str,
    xuid: str,
    *,
    mode: RepositoryMode | str = RepositoryMode.LEGACY,
    warehouse_path: str | Path | None = None,
    gamertag: str | None = None,
) -> DataRepository:
    """
    Crée et retourne le repository approprié.
    (Create and return the appropriate repository)

    Args:
        db_path: Chemin vers la DB (SQLite legacy ou DuckDB)
        xuid: XUID du joueur principal
        mode: Mode de repository (legacy, hybrid, shadow, compare, duckdb)
        warehouse_path: Chemin optionnel vers le warehouse pour les modes hybrid/shadow
        gamertag: Gamertag du joueur (optionnel, pour le mode duckdb)

    Returns:
        Instance de DataRepository

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

        # Mode DuckDB natif (v4)
        repo = get_repository(
            "data/players/JGtm/stats.duckdb",
            "1234567890",
            mode=RepositoryMode.DUCKDB,
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

    elif mode == RepositoryMode.DUCKDB:
        # Mode DuckDB natif - le db_path pointe vers stats.duckdb
        return DuckDBRepository(
            player_db_path=db_path,
            xuid=xuid,
            gamertag=gamertag,
        )

    else:
        raise ValueError(f"Mode de repository inconnu: {mode}")


def load_db_profiles(profiles_path: str | Path | None = None) -> dict[str, Any]:
    """
    Charge la configuration des profils depuis db_profiles.json.
    (Load profile configuration from db_profiles.json)

    Returns:
        dict avec version, warehouse_path, profiles, etc.
    """
    if profiles_path is None:
        # Cherche dans le répertoire racine du projet
        profiles_path = Path(__file__).parent.parent.parent.parent / "db_profiles.json"

    profiles_path = Path(profiles_path)

    if not profiles_path.exists():
        return {"version": "1.0", "profiles": {}}

    with open(profiles_path, encoding="utf-8") as f:
        return json.load(f)


def get_repository_from_profile(
    gamertag: str,
    *,
    mode: RepositoryMode | str | None = None,
    profiles_path: str | Path | None = None,
) -> DataRepository:
    """
    Crée un repository à partir du profil d'un joueur.
    (Create repository from player profile)

    Lit db_profiles.json et crée le repository approprié.

    Args:
        gamertag: Gamertag du joueur
        mode: Mode de repository (si None, auto-détecté depuis version)
        profiles_path: Chemin vers db_profiles.json

    Returns:
        Instance de DataRepository configurée

    Exemple:
        # Auto-détection du mode selon la version du profil
        repo = get_repository_from_profile("JGtm")

        # Forcer le mode legacy
        repo = get_repository_from_profile("JGtm", mode=RepositoryMode.LEGACY)
    """
    profiles = load_db_profiles(profiles_path)

    if gamertag not in profiles.get("profiles", {}):
        raise ValueError(f"Profil non trouvé pour: {gamertag}")

    profile = profiles["profiles"][gamertag]
    xuid = profile.get("xuid", "")

    # Auto-détection du mode si non spécifié
    if mode is None:
        version = profiles.get("version", "1.0")
        if version >= "2.0" and Path(profile.get("db_path", "")).suffix == ".duckdb":
            mode = RepositoryMode.DUCKDB
        else:
            mode = RepositoryMode.LEGACY

    # Normalise le mode
    if isinstance(mode, str):
        mode = RepositoryMode(mode.lower())

    if mode == RepositoryMode.DUCKDB:
        return DuckDBRepository(
            player_db_path=profile["db_path"],
            xuid=xuid,
            gamertag=gamertag,
        )
    elif mode == RepositoryMode.LEGACY:
        legacy_path = profile.get("legacy_db_path", profile.get("db_path"))
        return LegacyRepository(legacy_path, xuid)
    else:
        # Pour hybrid/shadow, utiliser le legacy_db_path
        legacy_path = profile.get("legacy_db_path", profile.get("db_path"))
        warehouse_path = profiles.get("warehouse_path", "data/warehouse")
        return get_repository(
            legacy_path,
            xuid,
            mode=mode,
            warehouse_path=warehouse_path,
            gamertag=gamertag,
        )


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
