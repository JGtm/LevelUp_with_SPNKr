"""
Factory pour la création des repositories.
(Factory for repository creation)

HOW IT WORKS:
Ce module fournit une interface simple pour créer le bon repository.
Depuis la v4, seul DuckDBRepository est utilisé.

Architecture v4 (actuelle):
    Utiliser get_repository_from_profile() pour auto-détection.

Usage recommandé:
    from src.data.repositories.factory import get_repository_from_profile

    # Auto-détection depuis db_profiles.json (recommandé)
    repo = get_repository_from_profile("JGtm")

Usage explicite:
    from src.data import get_repository

    # DuckDB natif (architecture v4)
    repo = get_repository(
        "data/players/JGtm/stats.duckdb",
        xuid,
    )
"""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.data.repositories.duckdb_repo import DuckDBRepository

if TYPE_CHECKING:
    from src.data.repositories.protocol import DataRepository


class RepositoryMode(Enum):
    """
    Modes de repository disponibles.
    (Available repository modes)

    Note: Depuis v4, seul DUCKDB est supporté.
    Les autres modes sont conservés pour compatibilité de l'enum mais lèvent une erreur.
    """

    LEGACY = "legacy"  # @deprecated - Supprimé en v4
    HYBRID = "hybrid"  # @deprecated - Supprimé en v4
    SHADOW = "shadow"  # @deprecated - Supprimé en v4
    SHADOW_COMPARE = "compare"  # @deprecated - Supprimé en v4
    DUCKDB = "duckdb"  # Système v4 (DuckDB natif) - Seul mode supporté


def get_repository(
    db_path: str,
    xuid: str,
    *,
    mode: RepositoryMode | str = RepositoryMode.DUCKDB,
    warehouse_path: str | Path | None = None,  # @deprecated - ignoré
    gamertag: str | None = None,
) -> DataRepository:
    """
    Crée et retourne le repository approprié.
    (Create and return the appropriate repository)

    Depuis v4, seul le mode DUCKDB est supporté.

    Args:
        db_path: Chemin vers la DB DuckDB (stats.duckdb)
        xuid: XUID du joueur principal
        mode: Mode de repository (seul DUCKDB est supporté)
        warehouse_path: @deprecated - Ignoré depuis v4
        gamertag: Gamertag du joueur (optionnel)

    Returns:
        Instance de DataRepository (DuckDBRepository)

    Raises:
        ValueError: Si un mode legacy est demandé

    Exemple:
        # Mode DuckDB natif (v4)
        repo = get_repository(
            "data/players/JGtm/stats.duckdb",
            "1234567890",
        )
    """
    # Normalise le mode si c'est une string
    if isinstance(mode, str):
        mode = RepositoryMode(mode.lower())

    # Depuis v4, seul DUCKDB est supporté
    if mode in (
        RepositoryMode.LEGACY,
        RepositoryMode.HYBRID,
        RepositoryMode.SHADOW,
        RepositoryMode.SHADOW_COMPARE,
    ):
        raise ValueError(
            f"Mode '{mode.value}' n'est plus supporté depuis v4. "
            f"Utilisez RepositoryMode.DUCKDB. "
            f"Migrez vos données avec scripts/migrate_to_duckdb.py"
        )

    # Mode DuckDB natif - le db_path pointe vers stats.duckdb
    return DuckDBRepository(
        player_db_path=db_path,
        xuid=xuid,
        gamertag=gamertag,
    )


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
    mode: RepositoryMode | str | None = None,  # @deprecated - ignoré, toujours DUCKDB
    profiles_path: str | Path | None = None,
) -> DataRepository:
    """
    Crée un repository à partir du profil d'un joueur.
    (Create repository from player profile)

    Lit db_profiles.json et crée un DuckDBRepository.

    Args:
        gamertag: Gamertag du joueur
        mode: @deprecated - Ignoré depuis v4, toujours DUCKDB
        profiles_path: Chemin vers db_profiles.json

    Returns:
        Instance de DuckDBRepository configurée

    Exemple:
        repo = get_repository_from_profile("JGtm")
    """
    profiles = load_db_profiles(profiles_path)

    if gamertag not in profiles.get("profiles", {}):
        raise ValueError(f"Profil non trouvé pour: {gamertag}")

    profile = profiles["profiles"][gamertag]
    xuid = profile.get("xuid", "")

    return DuckDBRepository(
        player_db_path=profile["db_path"],
        xuid=xuid,
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

    @deprecated Depuis v4, cette fonction retourne toujours True car
    seul DuckDB est utilisé. Les migrations legacy → DuckDB sont terminées.
    """
    # En v4, on utilise uniquement DuckDB, donc pas de migration en cours
    return True
