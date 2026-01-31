"""
Repository Shadow : Pont de migration entre Legacy et Hybrid.
(Shadow Repository: Migration bridge between Legacy and Hybrid)

HOW IT WORKS:
Le ShadowRepository implémente le pattern "Shadow Module" :

1. LECTURE : Lit TOUJOURS depuis le repository primaire (legacy par défaut)
2. ÉCRITURE SHADOW : Écrit aussi vers le repository secondaire (hybrid)
3. VALIDATION : Peut comparer les résultats pour valider la migration

Modes de fonctionnement:
- SHADOW_READ : Lit depuis legacy, écrit en shadow vers hybrid (migration)
- SHADOW_COMPARE : Lit depuis les deux et compare (validation)
- HYBRID_FIRST : Lit depuis hybrid si disponible, sinon legacy (post-migration)

Ce pattern permet une migration progressive sans risque :
- L'application continue de fonctionner avec les données legacy
- Les données sont progressivement migrées vers hybrid
- On peut valider la cohérence avant de basculer
"""
from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from src.data.repositories.legacy import LegacyRepository
from src.data.repositories.hybrid import HybridRepository
from src.data.infrastructure.parquet.writer import ParquetWriter
from src.data.domain.models.match import MatchFact, MatchFactInput, MatchOutcome
from src.models import MatchRow


logger = logging.getLogger(__name__)


class ShadowMode(Enum):
    """
    Modes de fonctionnement du ShadowRepository.
    (Shadow repository operating modes)
    """
    SHADOW_READ = "shadow_read"       # Lit legacy, écrit shadow vers hybrid
    SHADOW_COMPARE = "shadow_compare" # Lit les deux, compare
    HYBRID_FIRST = "hybrid_first"     # Lit hybrid si dispo, sinon legacy


class ShadowRepository:
    """
    Repository de migration avec pattern Shadow Module.
    (Migration repository with Shadow Module pattern)
    
    Orchestre la coexistence entre le système legacy et le nouveau système hybrid.
    Permet une migration progressive et sécurisée.
    """
    
    def __init__(
        self,
        db_path: str,
        xuid: str,
        *,
        warehouse_path: str | Path | None = None,
        mode: ShadowMode = ShadowMode.SHADOW_READ,
    ) -> None:
        """
        Initialise le repository shadow.
        (Initialize shadow repository)
        
        Args:
            db_path: Chemin vers la DB SQLite legacy
            xuid: XUID du joueur principal
            warehouse_path: Chemin vers le warehouse (défaut: data/warehouse à côté de la DB)
            mode: Mode de fonctionnement du shadow
        """
        self._db_path = db_path
        self._xuid = xuid
        self._mode = mode
        
        # Détermine le chemin du warehouse
        if warehouse_path is None:
            db_parent = Path(db_path).parent
            warehouse_path = db_parent / "warehouse"
        self._warehouse_path = Path(warehouse_path)
        
        # Repositories
        self._legacy = LegacyRepository(db_path, xuid)
        self._hybrid: HybridRepository | None = None
        
        # Writer pour l'écriture shadow
        self._parquet_writer: ParquetWriter | None = None
        
        # Stats de migration
        self._shadow_writes = 0
        self._validation_mismatches = 0
    
    @property
    def xuid(self) -> str:
        """XUID du joueur principal."""
        return self._xuid
    
    @property
    def db_path(self) -> str:
        """Chemin vers la base de données."""
        return self._db_path
    
    @property
    def mode(self) -> ShadowMode:
        """Mode de fonctionnement actuel."""
        return self._mode
    
    def _get_hybrid(self) -> HybridRepository:
        """Retourne le repository hybrid (lazy loading)."""
        if self._hybrid is None:
            self._hybrid = HybridRepository(
                self._warehouse_path,
                self._xuid,
                legacy_db_path=self._db_path,
            )
        return self._hybrid
    
    def _get_writer(self) -> ParquetWriter:
        """Retourne le writer Parquet (lazy loading)."""
        if self._parquet_writer is None:
            self._parquet_writer = ParquetWriter(self._warehouse_path)
        return self._parquet_writer
    
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
        Charge les matchs selon le mode configuré.
        (Load matches according to configured mode)
        """
        if self._mode == ShadowMode.HYBRID_FIRST:
            # Essaie d'abord hybrid
            if self.is_hybrid_available():
                return self._get_hybrid().load_matches(
                    playlist_filter=playlist_filter,
                    map_filter=map_filter,
                    include_firefight=include_firefight,
                )
            # Fallback legacy
            return self._legacy.load_matches(
                playlist_filter=playlist_filter,
                map_mode_pair_filter=map_mode_pair_filter,
                map_filter=map_filter,
                game_variant_filter=game_variant_filter,
                include_firefight=include_firefight,
            )
        
        elif self._mode == ShadowMode.SHADOW_COMPARE:
            # Charge depuis les deux et compare
            legacy_matches = self._legacy.load_matches(
                playlist_filter=playlist_filter,
                map_mode_pair_filter=map_mode_pair_filter,
                map_filter=map_filter,
                game_variant_filter=game_variant_filter,
                include_firefight=include_firefight,
            )
            
            if self.is_hybrid_available():
                hybrid_matches = self._get_hybrid().load_matches(
                    playlist_filter=playlist_filter,
                    map_filter=map_filter,
                    include_firefight=include_firefight,
                )
                self._compare_matches(legacy_matches, hybrid_matches)
            
            return legacy_matches
        
        else:  # SHADOW_READ (default)
            # Lit depuis legacy
            return self._legacy.load_matches(
                playlist_filter=playlist_filter,
                map_mode_pair_filter=map_mode_pair_filter,
                map_filter=map_filter,
                game_variant_filter=game_variant_filter,
                include_firefight=include_firefight,
            )
    
    def load_matches_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[MatchRow]:
        """Charge les matchs dans une plage de dates."""
        if self._mode == ShadowMode.HYBRID_FIRST and self.is_hybrid_available():
            return self._get_hybrid().load_matches_in_range(start_date, end_date)
        return self._legacy.load_matches_in_range(start_date, end_date)
    
    def get_match_count(self) -> int:
        """Retourne le nombre total de matchs."""
        if self._mode == ShadowMode.HYBRID_FIRST and self.is_hybrid_available():
            return self._get_hybrid().get_match_count()
        return self._legacy.get_match_count()
    
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
        if self._mode == ShadowMode.HYBRID_FIRST and self.is_hybrid_available():
            result = self._get_hybrid().load_top_medals(match_ids, top_n=top_n)
            if result:
                return result
        return self._legacy.load_top_medals(match_ids, top_n=top_n)
    
    def load_match_medals(self, match_id: str) -> list[dict[str, int]]:
        """Charge les médailles pour un match spécifique."""
        if self._mode == ShadowMode.HYBRID_FIRST and self.is_hybrid_available():
            result = self._get_hybrid().load_match_medals(match_id)
            if result:
                return result
        return self._legacy.load_match_medals(match_id)
    
    # =========================================================================
    # Coéquipiers
    # =========================================================================
    
    def list_top_teammates(
        self,
        limit: int = 20,
    ) -> list[tuple[str, int]]:
        """Liste les coéquipiers les plus fréquents."""
        # Toujours depuis legacy pour l'instant
        return self._legacy.list_top_teammates(limit)
    
    # =========================================================================
    # Métadonnées
    # =========================================================================
    
    def get_sync_metadata(self) -> dict[str, Any]:
        """Récupère les métadonnées de synchronisation."""
        metadata = self._legacy.get_sync_metadata()
        metadata["storage_mode"] = self._mode.value
        metadata["hybrid_available"] = self.is_hybrid_available()
        if self.is_hybrid_available():
            metadata["hybrid_row_count"] = self._get_hybrid().get_match_count()
        return metadata
    
    # =========================================================================
    # Shadow Write : Migration des données
    # =========================================================================
    
    def migrate_matches_to_parquet(
        self,
        *,
        batch_size: int = 1000,
        progress_callback: Any | None = None,
    ) -> dict[str, int]:
        """
        Migre les matchs legacy vers Parquet.
        (Migrate legacy matches to Parquet)
        
        Cette méthode lit tous les matchs depuis legacy et les écrit
        vers Parquet en mode append (dédupliqué sur match_id).
        
        Args:
            batch_size: Nombre de matchs par batch
            progress_callback: Callback optionnel (current, total)
            
        Returns:
            Stats de migration (rows_written, errors, etc.)
        """
        writer = self._get_writer()
        
        # Charger tous les matchs legacy
        legacy_matches = self._legacy.load_matches()
        total = len(legacy_matches)
        
        if total == 0:
            return {"rows_written": 0, "errors": 0, "total_legacy": 0}
        
        # Convertir en MatchFact
        facts: list[MatchFact] = []
        errors = 0
        
        for i, match in enumerate(legacy_matches):
            try:
                fact = self._match_row_to_fact(match)
                facts.append(fact)
            except Exception as e:
                logger.warning(f"Erreur conversion match {match.match_id}: {e}")
                errors += 1
            
            if progress_callback and (i + 1) % 100 == 0:
                progress_callback(i + 1, total)
        
        # Écrire en Parquet
        rows_written = writer.write_match_facts(facts, append=True)
        self._shadow_writes += rows_written
        
        # Mettre à jour les métadonnées
        from src.data.infrastructure.database.sqlite_metadata import SQLiteMetadataStore
        metadata_store = SQLiteMetadataStore(self._warehouse_path / "metadata.db")
        metadata_store.update_sync_status(
            self._xuid,
            total_parquet_rows=rows_written,
            sync_status="migrated",
        )
        
        return {
            "rows_written": rows_written,
            "errors": errors,
            "total_legacy": total,
        }
    
    def _match_row_to_fact(self, match: MatchRow) -> MatchFact:
        """Convertit un MatchRow en MatchFact."""
        input_data = MatchFactInput(
            match_id=match.match_id,
            xuid=self._xuid,
            start_time=match.start_time,
            playlist_id=match.playlist_id,
            map_id=match.map_id,
            game_variant_id=match.game_variant_id,
            outcome=MatchOutcome(match.outcome) if match.outcome else MatchOutcome.DID_NOT_FINISH,
            team_id=match.last_team_id or 0,
            kills=match.kills,
            deaths=match.deaths,
            assists=match.assists,
            kda=match.kda or 0.0,
            accuracy=match.accuracy,
            headshot_kills=match.headshot_kills or 0,
            max_killing_spree=match.max_killing_spree or 0,
            time_played_seconds=int(match.time_played_seconds or 0),
            avg_life_seconds=match.average_life_seconds,
            my_team_score=match.my_team_score or 0,
            enemy_team_score=match.enemy_team_score or 0,
            team_mmr=match.team_mmr,
            enemy_mmr=match.enemy_mmr,
            playlist_name=match.playlist_name,
            map_name=match.map_name,
            game_variant_name=match.game_variant_name,
        )
        return MatchFact.from_input(input_data)
    
    def _compare_matches(
        self,
        legacy: list[MatchRow],
        hybrid: list[MatchRow],
    ) -> None:
        """
        Compare les résultats legacy et hybrid.
        (Compare legacy and hybrid results)
        """
        legacy_ids = {m.match_id for m in legacy}
        hybrid_ids = {m.match_id for m in hybrid}
        
        missing_in_hybrid = legacy_ids - hybrid_ids
        extra_in_hybrid = hybrid_ids - legacy_ids
        
        if missing_in_hybrid:
            logger.warning(
                f"Shadow compare: {len(missing_in_hybrid)} matchs manquants dans hybrid"
            )
            self._validation_mismatches += len(missing_in_hybrid)
        
        if extra_in_hybrid:
            logger.info(
                f"Shadow compare: {len(extra_in_hybrid)} matchs supplémentaires dans hybrid"
            )
    
    # =========================================================================
    # Méthodes de diagnostic
    # =========================================================================
    
    def get_storage_info(self) -> dict[str, Any]:
        """Retourne des informations sur le stockage."""
        legacy_info = self._legacy.get_storage_info()
        
        info = {
            "type": "shadow",
            "mode": self._mode.value,
            "legacy": legacy_info,
            "warehouse_path": str(self._warehouse_path),
            "shadow_writes": self._shadow_writes,
            "validation_mismatches": self._validation_mismatches,
        }
        
        if self.is_hybrid_available():
            info["hybrid"] = self._get_hybrid().get_storage_info()
        
        return info
    
    def is_hybrid_available(self) -> bool:
        """Vérifie si les données hybrides sont disponibles."""
        try:
            return self._get_hybrid().is_hybrid_available()
        except Exception:
            return False
    
    def get_migration_progress(self) -> dict[str, Any]:
        """
        Retourne la progression de la migration.
        (Return migration progress)
        """
        legacy_count = self._legacy.get_match_count()
        hybrid_count = 0
        
        if self.is_hybrid_available():
            hybrid_count = self._get_hybrid().get_match_count()
        
        progress = (hybrid_count / legacy_count * 100) if legacy_count > 0 else 0
        
        return {
            "legacy_count": legacy_count,
            "hybrid_count": hybrid_count,
            "progress_percent": round(progress, 1),
            "is_complete": hybrid_count >= legacy_count,
            "mode": self._mode.value,
        }
    
    def close(self) -> None:
        """Ferme les connexions."""
        if self._hybrid is not None:
            self._hybrid.close()
            self._hybrid = None
    
    def __enter__(self) -> ShadowRepository:
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
