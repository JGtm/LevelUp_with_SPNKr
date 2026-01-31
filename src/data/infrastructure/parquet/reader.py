"""
Lecteur Parquet optimisé.
(Optimized Parquet reader)

HOW IT WORKS:
1. Utilise le pruning de partitions pour ne lire que les données nécessaires
2. Projette uniquement les colonnes demandées
3. Pousse les filtres vers le bas pour optimiser les lectures

Note: Pour les requêtes complexes, préférer DuckDBEngine qui offre
plus de flexibilité (jointures, agrégations SQL).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

import polars as pl

from src.models import MatchRow


class ParquetReader:
    """
    Lecteur optimisé pour les fichiers Parquet partitionnés.
    (Optimized reader for partitioned Parquet files)
    """
    
    def __init__(self, warehouse_path: str | Path) -> None:
        """
        Initialise le lecteur Parquet.
        (Initialize Parquet reader)
        
        Args:
            warehouse_path: Chemin vers le dossier warehouse
        """
        self.warehouse_path = Path(warehouse_path)
    
    def read_match_facts(
        self,
        xuid: str,
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        columns: Sequence[str] | None = None,
    ) -> pl.DataFrame:
        """
        Lit les faits de match pour un joueur.
        (Read match facts for a player)
        
        Args:
            xuid: XUID du joueur
            start_date: Date de début optionnelle
            end_date: Date de fin optionnelle
            columns: Colonnes à lire (None = toutes)
            
        Returns:
            DataFrame Polars avec les données
        """
        player_path = self.warehouse_path / "match_facts" / f"player={xuid}"
        
        if not player_path.exists():
            return pl.DataFrame()
        
        # Construire le pattern de fichiers
        if start_date and end_date:
            # Pruning de partitions par date
            patterns = self._get_partition_patterns(player_path, start_date, end_date)
            if not patterns:
                return pl.DataFrame()
            
            dfs = []
            for pattern in patterns:
                files = list(player_path.glob(pattern))
                if files:
                    df = pl.read_parquet(files, columns=columns)
                    dfs.append(df)
            
            if not dfs:
                return pl.DataFrame()
            
            return pl.concat(dfs)
        else:
            # Lire toutes les partitions
            files = list(player_path.glob("**/*.parquet"))
            if not files:
                return pl.DataFrame()
            
            return pl.read_parquet(files, columns=columns)
    
    def read_medals(
        self,
        xuid: str,
        *,
        match_ids: Sequence[str] | None = None,
    ) -> pl.DataFrame:
        """
        Lit les médailles pour un joueur.
        (Read medals for a player)
        """
        player_path = self.warehouse_path / "medals" / f"player={xuid}"
        
        if not player_path.exists():
            return pl.DataFrame()
        
        files = list(player_path.glob("**/*.parquet"))
        if not files:
            return pl.DataFrame()
        
        df = pl.read_parquet(files)
        
        if match_ids:
            df = df.filter(pl.col("match_id").is_in(match_ids))
        
        return df
    
    def to_match_rows(self, df: pl.DataFrame) -> list[MatchRow]:
        """
        Convertit un DataFrame en liste de MatchRow.
        (Convert DataFrame to list of MatchRow)
        """
        if df.is_empty():
            return []
        
        return [
            MatchRow(
                match_id=row["match_id"],
                start_time=row["start_time"],
                map_id=row.get("map_id"),
                map_name=row.get("map_name"),
                playlist_id=row.get("playlist_id"),
                playlist_name=row.get("playlist_name"),
                map_mode_pair_id=None,
                map_mode_pair_name=None,
                game_variant_id=row.get("game_variant_id"),
                game_variant_name=row.get("game_variant_name"),
                outcome=row.get("outcome"),
                last_team_id=row.get("team_id"),
                kda=row.get("kda"),
                max_killing_spree=row.get("max_killing_spree"),
                headshot_kills=row.get("headshot_kills"),
                average_life_seconds=row.get("avg_life_seconds"),
                time_played_seconds=row.get("time_played_seconds"),
                kills=row.get("kills", 0),
                deaths=row.get("deaths", 0),
                assists=row.get("assists", 0),
                accuracy=row.get("accuracy"),
                my_team_score=row.get("my_team_score"),
                enemy_team_score=row.get("enemy_team_score"),
                team_mmr=row.get("team_mmr"),
                enemy_mmr=row.get("enemy_mmr"),
            )
            for row in df.iter_rows(named=True)
        ]
    
    def has_data(self, xuid: str, table: str = "match_facts") -> bool:
        """
        Vérifie si des données existent pour un joueur.
        (Check if data exists for a player)
        """
        player_path = self.warehouse_path / table / f"player={xuid}"
        if not player_path.exists():
            return False
        return bool(list(player_path.glob("**/*.parquet")))
    
    def count_rows(self, xuid: str, table: str = "match_facts") -> int:
        """
        Compte le nombre de lignes pour un joueur.
        (Count rows for a player)
        """
        player_path = self.warehouse_path / table / f"player={xuid}"
        if not player_path.exists():
            return 0
        
        files = list(player_path.glob("**/*.parquet"))
        if not files:
            return 0
        
        total = 0
        for f in files:
            # Lecture lazy pour compter sans charger les données
            total += pl.scan_parquet(f).select(pl.count()).collect().item()
        
        return total
    
    def _get_partition_patterns(
        self,
        player_path: Path,
        start_date: datetime,
        end_date: datetime,
    ) -> list[str]:
        """
        Génère les patterns de partition pour une plage de dates.
        (Generate partition patterns for a date range)
        """
        patterns = []
        current = start_date.replace(day=1)
        
        while current <= end_date:
            pattern = f"year={current.year}/month={current.month:02d}/*.parquet"
            patterns.append(pattern)
            
            # Mois suivant
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        return patterns
