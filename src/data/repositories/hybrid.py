"""
Repository Hybride : Nouveau système SQLite + Parquet + DuckDB.
(Hybrid Repository: New SQLite + Parquet + DuckDB system)

HOW IT WORKS:
Ce repository utilise l'architecture hybride :
1. SQLite (metadata.db) : Données chaudes (joueurs, playlists, sessions)
2. Parquet : Données froides (matchs, médailles)
3. DuckDB : Moteur de requête pour joindre les deux

Les données sont lues depuis Parquet via DuckDB pour les performances.
Les métadonnées sont lues depuis SQLite.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from src.data.infrastructure.database.duckdb_engine import DuckDBEngine
from src.data.infrastructure.database.sqlite_metadata import SQLiteMetadataStore
from src.data.infrastructure.parquet.reader import ParquetReader
from src.models import MatchRow


class HybridRepository:
    """
    Repository utilisant l'architecture hybride.
    (Repository using hybrid architecture)
    
    Combine :
    - SQLite pour les métadonnées (via SQLiteMetadataStore)
    - Parquet pour les faits (via ParquetReader / DuckDBEngine)
    - DuckDB pour les requêtes complexes
    """
    
    def __init__(
        self,
        warehouse_path: str | Path,
        xuid: str,
        *,
        legacy_db_path: str | None = None,
    ) -> None:
        """
        Initialise le repository hybride.
        (Initialize hybrid repository)
        
        Args:
            warehouse_path: Chemin vers le dossier warehouse
            xuid: XUID du joueur principal
            legacy_db_path: Optionnel, chemin vers la DB legacy pour les données manquantes
        """
        self._warehouse_path = Path(warehouse_path)
        self._xuid = xuid
        self._legacy_db_path = legacy_db_path
        
        # Composants de l'architecture hybride
        self._metadata_db_path = self._warehouse_path / "metadata.db"
        self._metadata_store = SQLiteMetadataStore(self._metadata_db_path)
        self._parquet_reader = ParquetReader(self._warehouse_path)
        self._duckdb_engine: DuckDBEngine | None = None
    
    @property
    def xuid(self) -> str:
        """XUID du joueur principal."""
        return self._xuid
    
    @property
    def db_path(self) -> str:
        """Chemin vers la base de données metadata."""
        return str(self._metadata_db_path)
    
    def _get_duckdb(self) -> DuckDBEngine:
        """Retourne le moteur DuckDB (lazy loading)."""
        if self._duckdb_engine is None:
            self._duckdb_engine = DuckDBEngine(self._warehouse_path)
            self._duckdb_engine.attach_sqlite(self._metadata_db_path, "meta")
        return self._duckdb_engine
    
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
        Charge tous les matchs depuis Parquet via DuckDB.
        (Load all matches from Parquet via DuckDB)
        """
        # Vérifier si des données Parquet existent
        if not self._parquet_reader.has_data(self._xuid):
            return []
        
        return self._get_duckdb().load_matches(
            self._xuid,
            playlist_filter=playlist_filter,
            map_filter=map_filter,
        )
    
    def load_matches_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[MatchRow]:
        """Charge les matchs dans une plage de dates."""
        df = self._parquet_reader.read_match_facts(
            self._xuid,
            start_date=start_date,
            end_date=end_date,
        )
        return self._parquet_reader.to_match_rows(df)
    
    def get_match_count(self) -> int:
        """Retourne le nombre total de matchs."""
        return self._parquet_reader.count_rows(self._xuid)
    
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
        if not self._parquet_reader.has_data(self._xuid, "medals"):
            return []
        
        df = self._parquet_reader.read_medals(self._xuid, match_ids=match_ids)
        if df.is_empty():
            return []
        
        # Agrégation
        import polars as pl
        agg = (
            df.group_by("medal_name_id")
            .agg(pl.col("count").sum().alias("total"))
            .sort("total", descending=True)
        )
        
        if top_n:
            agg = agg.head(top_n)
        
        return [(row["medal_name_id"], row["total"]) for row in agg.iter_rows(named=True)]
    
    def load_match_medals(self, match_id: str) -> list[dict[str, int]]:
        """Charge les médailles pour un match spécifique."""
        df = self._parquet_reader.read_medals(self._xuid, match_ids=[match_id])
        if df.is_empty():
            return []
        
        return [
            {"name_id": row["medal_name_id"], "count": row["count"]}
            for row in df.iter_rows(named=True)
        ]
    
    # =========================================================================
    # Coéquipiers
    # =========================================================================
    
    def list_top_teammates(
        self,
        limit: int = 20,
    ) -> list[tuple[str, int]]:
        """
        Liste les coéquipiers les plus fréquents.
        (List most frequent teammates)
        
        Note: Requiert une table teammates_aggregate dans les métadonnées.
        Pour l'instant, retourne une liste vide.
        """
        # TODO: Implémenter avec une table d'agrégation des coéquipiers
        return []
    
    # =========================================================================
    # Métadonnées
    # =========================================================================
    
    def get_sync_metadata(self) -> dict[str, Any]:
        """Récupère les métadonnées de synchronisation."""
        sync_status = self._metadata_store.get_sync_status(self._xuid)
        return {
            "last_sync_at": sync_status.get("last_sync_at"),
            "last_match_time": None,
            "total_matches": self.get_match_count(),
            "player_xuid": self._xuid,
            "storage_type": "hybrid",
        }
    
    # =========================================================================
    # Méthodes de diagnostic
    # =========================================================================
    
    def get_storage_info(self) -> dict[str, Any]:
        """Retourne des informations sur le stockage."""
        from src.data.infrastructure.parquet.writer import ParquetWriter
        
        writer = ParquetWriter(self._warehouse_path)
        
        return {
            "type": "hybrid",
            "warehouse_path": str(self._warehouse_path),
            "metadata_db_path": str(self._metadata_db_path),
            "xuid": self._xuid,
            "match_facts_stats": writer.get_stats("match_facts"),
            "medals_stats": writer.get_stats("medals"),
            "has_parquet_data": self._parquet_reader.has_data(self._xuid),
            "parquet_row_count": self._parquet_reader.count_rows(self._xuid),
        }
    
    def is_hybrid_available(self) -> bool:
        """Vérifie si les données hybrides sont disponibles."""
        return self._parquet_reader.has_data(self._xuid)
    
    def close(self) -> None:
        """Ferme les connexions."""
        if self._duckdb_engine is not None:
            self._duckdb_engine.close()
            self._duckdb_engine = None
    
    def __enter__(self) -> HybridRepository:
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
