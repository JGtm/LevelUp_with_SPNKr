"""
Repository Legacy : Wrapper du système actuel.
(Legacy Repository: Wrapper for current system)

HOW IT WORKS:
Ce repository encapsule les appels aux loaders existants (src/db/loaders.py)
pour fournir une interface compatible avec le Protocol DataRepository.

Il ne modifie pas le comportement existant, juste l'expose via l'interface.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from src.db.loaders import (
    load_matches,
    load_top_medals,
    load_match_medals_for_player,
    list_top_teammates,
    get_sync_metadata,
    has_table,
)
from src.db.loaders_cached import (
    load_matches_cached,
    has_cache_tables,
    get_cache_stats,
)
from src.models import MatchRow


class LegacyRepository:
    """
    Repository utilisant le système de stockage actuel.
    (Repository using current storage system)
    
    Encapsule les appels à src/db/loaders.py et src/db/loaders_cached.py.
    Utilise le cache SQLite (MatchCache) si disponible, sinon le JSON brut.
    """
    
    def __init__(self, db_path: str, xuid: str) -> None:
        """
        Initialise le repository legacy.
        (Initialize legacy repository)
        
        Args:
            db_path: Chemin vers le fichier SQLite
            xuid: XUID du joueur principal
        """
        self._db_path = db_path
        self._xuid = xuid
        self._use_cache = has_cache_tables(db_path)
    
    @property
    def xuid(self) -> str:
        """XUID du joueur principal."""
        return self._xuid
    
    @property
    def db_path(self) -> str:
        """Chemin vers la base de données."""
        return self._db_path
    
    # =========================================================================
    # Chargement des matchs
    # =========================================================================
    
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
        Charge tous les matchs du joueur.
        (Load all player matches)
        
        Utilise le cache si disponible, sinon parse le JSON brut.
        """
        if self._use_cache:
            try:
                return load_matches_cached(
                    self._db_path,
                    self._xuid,
                    playlist_filter=playlist_filter,
                    map_mode_pair_filter=map_mode_pair_filter,
                    map_filter=map_filter,
                    game_variant_filter=game_variant_filter,
                    include_firefight=include_firefight,
                )
            except Exception:
                # Fallback si le cache n'est pas à jour (colonnes manquantes, etc.)
                pass
        
        # Chargement depuis JSON brut
        return load_matches(
            self._db_path,
            self._xuid,
            playlist_filter=playlist_filter,
            map_mode_pair_filter=map_mode_pair_filter,
            map_filter=map_filter,
            game_variant_filter=game_variant_filter,
        )
    
    def load_matches_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[MatchRow]:
        """
        Charge les matchs dans une plage de dates.
        (Load matches in a date range)
        """
        all_matches = self.load_matches()
        return [
            m for m in all_matches
            if start_date <= m.start_time <= end_date
        ]
    
    def get_match_count(self) -> int:
        """Retourne le nombre total de matchs."""
        metadata = self.get_sync_metadata()
        return metadata.get("total_matches", 0)
    
    # =========================================================================
    # Médailles
    # =========================================================================
    
    def load_top_medals(
        self,
        match_ids: list[str],
        *,
        top_n: int | None = 25,
    ) -> list[tuple[int, int]]:
        """Charge les médailles les plus fréquentes."""
        return load_top_medals(
            self._db_path,
            self._xuid,
            match_ids,
            top_n=top_n,
        )
    
    def load_match_medals(self, match_id: str) -> list[dict[str, int]]:
        """Charge les médailles pour un match spécifique."""
        return load_match_medals_for_player(
            self._db_path,
            match_id,
            self._xuid,
        )
    
    # =========================================================================
    # Coéquipiers
    # =========================================================================
    
    def list_top_teammates(
        self,
        limit: int = 20,
    ) -> list[tuple[str, int]]:
        """Liste les coéquipiers les plus fréquents."""
        return list_top_teammates(self._db_path, self._xuid, limit)
    
    # =========================================================================
    # Métadonnées
    # =========================================================================
    
    def get_sync_metadata(self) -> dict[str, Any]:
        """Récupère les métadonnées de synchronisation."""
        return get_sync_metadata(self._db_path)
    
    # =========================================================================
    # Méthodes de diagnostic
    # =========================================================================
    
    def get_storage_info(self) -> dict[str, Any]:
        """Retourne des informations sur le stockage."""
        info = {
            "type": "legacy",
            "db_path": self._db_path,
            "xuid": self._xuid,
            "uses_cache": self._use_cache,
            "has_match_stats": has_table(self._db_path, "MatchStats"),
            "has_match_cache": has_table(self._db_path, "MatchCache"),
        }
        
        if self._use_cache:
            cache_stats = get_cache_stats(self._db_path, self._xuid)
            info["cache_stats"] = cache_stats
        
        return info
    
    def is_hybrid_available(self) -> bool:
        """
        Le repository legacy n'a jamais de données hybrides.
        (Legacy repository never has hybrid data)
        """
        return False
