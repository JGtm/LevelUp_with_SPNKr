"""
Protocole (interface) pour les repositories de données.
(Protocol/interface for data repositories)

HOW IT WORKS:
Ce Protocol définit le contrat que doivent respecter tous les repositories.
Il utilise le typing.Protocol de Python pour le duck typing structurel.

Cela permet d'avoir :
- LegacyRepository : utilise l'ancien système (loaders.py)
- HybridRepository : utilise le nouveau système (Parquet + DuckDB)
- ShadowRepository : orchestre la migration entre les deux
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from src.data.domain.models.stats import MatchRow


@runtime_checkable
class DataRepository(Protocol):
    """
    Interface abstraite pour l'accès aux données.
    (Abstract interface for data access)

    Toutes les implémentations (Legacy, Hybrid, Shadow) doivent
    respecter cette interface pour être interchangeables.
    """

    @property
    def xuid(self) -> str:
        """XUID du joueur principal. (Main player XUID)"""
        ...

    @property
    def db_path(self) -> str:
        """Chemin vers la base de données. (Database path)"""
        ...

    # =========================================================================
    # Chargement des matchs
    # =========================================================================

    @abstractmethod
    def load_matches(
        self,
        *,
        playlist_filter: str | None = None,
        map_mode_pair_filter: str | None = None,
        map_filter: str | None = None,
        game_variant_filter: str | None = None,
        include_firefight: bool = True,
    ) -> list[MatchRow]:
        """
        Charge tous les matchs du joueur avec filtres optionnels.
        (Load all player matches with optional filters)

        Args:
            playlist_filter: Filtre sur playlist_id
            map_mode_pair_filter: Filtre sur map_mode_pair_id
            map_filter: Filtre sur map_id
            game_variant_filter: Filtre sur game_variant_id
            include_firefight: Inclure les matchs PvE (Firefight)

        Returns:
            Liste de MatchRow triée par date croissante
        """
        ...

    @abstractmethod
    def load_matches_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[MatchRow]:
        """
        Charge les matchs dans une plage de dates.
        (Load matches in a date range)
        """
        ...

    @abstractmethod
    def get_match_count(self) -> int:
        """
        Retourne le nombre total de matchs.
        (Return total match count)
        """
        ...

    # =========================================================================
    # Médailles
    # =========================================================================

    @abstractmethod
    def load_top_medals(
        self,
        match_ids: list[str],
        *,
        top_n: int | None = 25,
    ) -> list[tuple[int, int]]:
        """
        Charge les médailles les plus fréquentes.
        (Load most frequent medals)

        Args:
            match_ids: Liste des match_id à considérer
            top_n: Nombre max de médailles à retourner

        Returns:
            Liste de tuples (name_id, count) triée par count desc
        """
        ...

    @abstractmethod
    def load_match_medals(self, match_id: str) -> list[dict[str, int]]:
        """
        Charge les médailles pour un match spécifique.
        (Load medals for a specific match)

        Returns:
            Liste de dicts {"name_id": int, "count": int}
        """
        ...

    # =========================================================================
    # Coéquipiers et social
    # =========================================================================

    @abstractmethod
    def list_top_teammates(
        self,
        limit: int = 20,
    ) -> list[tuple[str, int]]:
        """
        Liste les coéquipiers les plus fréquents.
        (List most frequent teammates)

        Returns:
            Liste de tuples (xuid, match_count)
        """
        ...

    # =========================================================================
    # Métadonnées
    # =========================================================================

    @abstractmethod
    def get_sync_metadata(self) -> dict[str, Any]:
        """
        Récupère les métadonnées de synchronisation.
        (Get sync metadata)

        Returns:
            Dict avec last_sync_at, total_matches, etc.
        """
        ...

    # =========================================================================
    # Méthodes de diagnostic
    # =========================================================================

    @abstractmethod
    def get_storage_info(self) -> dict[str, Any]:
        """
        Retourne des informations sur le stockage.
        (Return storage information)

        Utile pour le debugging et le monitoring.
        """
        ...

    @abstractmethod
    def is_hybrid_available(self) -> bool:
        """
        Vérifie si les données hybrides (Parquet) sont disponibles.
        (Check if hybrid data (Parquet) is available)
        """
        ...
