"""
Écrivain Parquet avec partitionnement.
(Parquet writer with partitioning)

HOW IT WORKS:
1. Reçoit des MatchFact ou MedalAward depuis le transformateur
2. Convertit en DataFrame Polars
3. Écrit en Parquet avec partitionnement par player/year/month
4. Utilise la compression Snappy pour l'équilibre vitesse/taille

Structure des fichiers:
    warehouse/
    └── match_facts/
        └── player=1234567890/
            └── year=2025/
                └── month=01/
                    └── data.parquet
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import polars as pl

from src.data.domain.models.match import MatchFact
from src.data.domain.models.medal import MedalAward


class ParquetWriter:
    """
    Écrit les données en fichiers Parquet partitionnés.
    (Writes data to partitioned Parquet files)
    """

    def __init__(
        self,
        warehouse_path: str | Path,
        *,
        compression: str = "snappy",
        row_group_size: int = 100_000,
    ) -> None:
        """
        Initialise le writer Parquet.
        (Initialize Parquet writer)

        Args:
            warehouse_path: Chemin vers le dossier warehouse
            compression: Algorithme de compression (snappy, zstd, gzip, lz4)
            row_group_size: Taille des row groups pour optimiser les lectures
        """
        self.warehouse_path = Path(warehouse_path)
        self.compression = compression
        self.row_group_size = row_group_size

        # Créer le dossier warehouse
        self.warehouse_path.mkdir(parents=True, exist_ok=True)

    def write_match_facts(
        self,
        facts: Sequence[MatchFact],
        *,
        append: bool = True,
    ) -> int:
        """
        Écrit les faits de match en Parquet.
        (Write match facts to Parquet)

        Args:
            facts: Liste de MatchFact à écrire
            append: Si True, ajoute aux fichiers existants

        Returns:
            Nombre de lignes écrites
        """
        if not facts:
            return 0

        # Convertir en DataFrame Polars
        records = [f.model_dump() for f in facts]
        df = pl.DataFrame(records)

        # Convertir les types pour Parquet
        df = self._prepare_match_facts_schema(df)

        # Écrire avec partitionnement
        table_path = self.warehouse_path / "match_facts"

        # Obtenir les combinaisons uniques de partitions
        partitions = df.select(["xuid", "year", "month"]).unique()

        rows_written = 0
        for row in partitions.iter_rows(named=True):
            xuid = row["xuid"]
            year = row["year"]
            month = row["month"]

            # Extraire les données de cette partition
            partition_df = df.filter(
                (pl.col("xuid") == xuid) & (pl.col("year") == year) & (pl.col("month") == month)
            )

            # Chemin de la partition
            partition_path = table_path / f"player={xuid}" / f"year={year}" / f"month={month:02d}"
            partition_path.mkdir(parents=True, exist_ok=True)

            file_path = partition_path / "data.parquet"

            if append and file_path.exists():
                # Lire les données existantes et fusionner
                existing_df = pl.read_parquet(file_path)
                # Dédupliquer sur match_id
                combined_df = pl.concat([existing_df, partition_df]).unique(subset=["match_id"])
                combined_df.write_parquet(
                    file_path,
                    compression=self.compression,
                    row_group_size=self.row_group_size,
                )
                rows_written += len(partition_df)
            else:
                partition_df.write_parquet(
                    file_path,
                    compression=self.compression,
                    row_group_size=self.row_group_size,
                )
                rows_written += len(partition_df)

        return rows_written

    def write_medals(
        self,
        medals: Sequence[MedalAward],
        *,
        append: bool = True,
    ) -> int:
        """
        Écrit les médailles en Parquet.
        (Write medals to Parquet)
        """
        if not medals:
            return 0

        records = [m.model_dump() for m in medals]
        df = pl.DataFrame(records)

        # Convertir les types
        df = df.with_columns(
            [
                pl.col("start_time").cast(pl.Datetime("us", "UTC")),
                pl.col("year").cast(pl.Int16),
                pl.col("month").cast(pl.Int8),
                pl.col("medal_name_id").cast(pl.Int32),
                pl.col("count").cast(pl.Int16),
            ]
        )

        table_path = self.warehouse_path / "medals"

        # Grouper par partition
        partitions = df.select(["xuid", "year", "month"]).unique()

        rows_written = 0
        for row in partitions.iter_rows(named=True):
            xuid = row["xuid"]
            year = row["year"]
            month = row["month"]

            partition_df = df.filter(
                (pl.col("xuid") == xuid) & (pl.col("year") == year) & (pl.col("month") == month)
            )

            partition_path = table_path / f"player={xuid}" / f"year={year}" / f"month={month:02d}"
            partition_path.mkdir(parents=True, exist_ok=True)

            file_path = partition_path / "data.parquet"

            if append and file_path.exists():
                existing_df = pl.read_parquet(file_path)
                combined_df = pl.concat([existing_df, partition_df]).unique(
                    subset=["match_id", "medal_name_id"]
                )
                combined_df.write_parquet(file_path, compression=self.compression)
                rows_written += len(partition_df)
            else:
                partition_df.write_parquet(file_path, compression=self.compression)
                rows_written += len(partition_df)

        return rows_written

    def _prepare_match_facts_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Prépare le schéma du DataFrame pour Parquet.
        (Prepare DataFrame schema for Parquet)
        """
        return df.with_columns(
            [
                pl.col("start_time").cast(pl.Datetime("us", "UTC")),
                pl.col("year").cast(pl.Int16),
                pl.col("month").cast(pl.Int8),
                pl.col("outcome").cast(pl.Int8),
                pl.col("team_id").cast(pl.Int8),
                pl.col("kills").cast(pl.Int16),
                pl.col("deaths").cast(pl.Int16),
                pl.col("assists").cast(pl.Int16),
                pl.col("kda").cast(pl.Float32),
                pl.col("accuracy").cast(pl.Float32),
                pl.col("headshot_kills").cast(pl.Int16),
                pl.col("max_killing_spree").cast(pl.Int16),
                pl.col("time_played_seconds").cast(pl.Int32),
                pl.col("avg_life_seconds").cast(pl.Float32),
                pl.col("my_team_score").cast(pl.Int16),
                pl.col("enemy_team_score").cast(pl.Int16),
                pl.col("team_mmr").cast(pl.Float32),
                pl.col("enemy_mmr").cast(pl.Float32),
                pl.col("performance_score").cast(pl.Float32),
            ]
        )

    def get_stats(self, table: str = "match_facts") -> dict:
        """
        Retourne des statistiques sur les fichiers Parquet.
        (Return statistics about Parquet files)
        """
        table_path = self.warehouse_path / table
        if not table_path.exists():
            return {"exists": False, "files": 0, "total_size_mb": 0}

        files = list(table_path.glob("**/*.parquet"))
        total_size = sum(f.stat().st_size for f in files)

        return {
            "exists": True,
            "files": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "partitions": len(list(table_path.glob("player=*"))),
        }
