#!/usr/bin/env python3
"""Benchmark de performance Polars vs Pandas.

Sprint 9.3 - Ce script mesure les performances des opérations courantes :
1. Chargement depuis DuckDB
2. Filtrage et agrégation
3. Calcul des antagonistes
4. Génération de graphiques

Usage:
    python scripts/benchmark_polars.py --gamertag MonGT
    python scripts/benchmark_polars.py --gamertag MonGT --iterations 10
"""

from __future__ import annotations

import argparse
import contextlib
import gc
import logging
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class BenchmarkResult:
    """Résultat d'un benchmark."""

    name: str
    iterations: int
    times_ms: list[float] = field(default_factory=list)

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.times_ms) if self.times_ms else 0.0

    @property
    def median_ms(self) -> float:
        return statistics.median(self.times_ms) if self.times_ms else 0.0

    @property
    def min_ms(self) -> float:
        return min(self.times_ms) if self.times_ms else 0.0

    @property
    def max_ms(self) -> float:
        return max(self.times_ms) if self.times_ms else 0.0

    @property
    def stdev_ms(self) -> float:
        return statistics.stdev(self.times_ms) if len(self.times_ms) > 1 else 0.0


def timeit(func, iterations: int = 5) -> BenchmarkResult:
    """Mesure le temps d'exécution d'une fonction."""
    name = func.__name__
    result = BenchmarkResult(name=name, iterations=iterations)

    # Warm-up
    with contextlib.suppress(Exception):
        func()

    # Mesures
    for _ in range(iterations):
        gc.collect()
        start = time.perf_counter()
        try:
            func()
        except Exception as e:
            logger.warning(f"Erreur dans {name}: {e}")
            continue
        end = time.perf_counter()
        result.times_ms.append((end - start) * 1000)

    return result


def run_polars_benchmarks(db_path: Path, xuid: str, iterations: int = 5) -> list[BenchmarkResult]:
    """Exécute les benchmarks Polars."""
    import polars as pl

    from src.analysis.killer_victim import (
        compute_personal_antagonists_from_pairs_polars,
        killer_victim_counts_long_polars,
        killer_victim_matrix_polars,
    )
    from src.data.repositories.duckdb_repo import DuckDBRepository

    results = []

    # Créer le repository
    repo = DuckDBRepository(db_path, xuid=xuid, read_only=True)

    # Benchmark 1: Chargement killer_victim_pairs
    def load_kv_pairs():
        return repo.load_killer_victim_pairs_as_polars()

    results.append(timeit(load_kv_pairs, iterations))

    # Benchmark 2: Chargement match_stats
    def load_match_stats():
        return repo.load_match_stats_as_polars()

    results.append(timeit(load_match_stats, iterations))

    # Benchmark 3: Calcul antagonistes
    pairs_df = repo.load_killer_victim_pairs_as_polars()

    def compute_antagonists():
        return compute_personal_antagonists_from_pairs_polars(pairs_df, xuid)

    if not pairs_df.is_empty():
        results.append(timeit(compute_antagonists, iterations))

    # Benchmark 4: Agrégation
    def aggregate_counts():
        return killer_victim_counts_long_polars(pairs_df)

    if not pairs_df.is_empty():
        results.append(timeit(aggregate_counts, iterations))

    # Benchmark 5: Matrice pivot
    def compute_matrix():
        return killer_victim_matrix_polars(pairs_df)

    if not pairs_df.is_empty():
        results.append(timeit(compute_matrix, iterations))

    # Benchmark 6: Filtrage + Agrégation chaîné
    match_stats_df = repo.load_match_stats_as_polars()

    def filter_aggregate():
        return (
            match_stats_df.filter(pl.col("outcome") == 2)
            .group_by("map_name")
            .agg(
                [
                    pl.col("kills").mean().alias("avg_kills"),
                    pl.col("deaths").mean().alias("avg_deaths"),
                    pl.len().alias("match_count"),
                ]
            )
            .sort("match_count", descending=True)
        )

    if not match_stats_df.is_empty():
        results.append(timeit(filter_aggregate, iterations))

    repo.close()
    return results


def run_pandas_benchmarks(db_path: Path, xuid: str, iterations: int = 5) -> list[BenchmarkResult]:
    """Exécute les benchmarks Pandas (pour comparaison)."""
    import duckdb

    results = []

    # Benchmark 1: Chargement killer_victim_pairs
    def load_kv_pairs_pandas():
        conn = duckdb.connect(str(db_path), read_only=True)
        df = conn.execute("SELECT * FROM killer_victim_pairs").fetchdf()
        conn.close()
        return df

    results.append(timeit(load_kv_pairs_pandas, iterations))

    # Benchmark 2: Chargement match_stats
    def load_match_stats_pandas():
        conn = duckdb.connect(str(db_path), read_only=True)
        df = conn.execute("SELECT * FROM match_stats").fetchdf()
        conn.close()
        return df

    results.append(timeit(load_match_stats_pandas, iterations))

    # Benchmark 3: Filtrage + Agrégation Pandas
    conn = duckdb.connect(str(db_path), read_only=True)
    match_stats_df = conn.execute("SELECT * FROM match_stats").fetchdf()
    conn.close()

    def filter_aggregate_pandas():
        filtered = match_stats_df[match_stats_df["outcome"] == 2]
        return (
            filtered.groupby("map_name")
            .agg(
                {
                    "kills": "mean",
                    "deaths": "mean",
                    "match_id": "count",
                }
            )
            .rename(columns={"match_id": "match_count"})
            .sort_values("match_count", ascending=False)
        )

    if len(match_stats_df) > 0:
        results.append(timeit(filter_aggregate_pandas, iterations))

    return results


def print_results(polars_results: list[BenchmarkResult], pandas_results: list[BenchmarkResult]):
    """Affiche les résultats comparatifs."""
    print("\n" + "=" * 80)
    print("BENCHMARK POLARS VS PANDAS")
    print("=" * 80)

    print("\n📊 Résultats Polars:")
    print("-" * 60)
    print(f"{'Opération':<40} {'Moyenne':>10} {'Médiane':>10} {'Min':>8}")
    print("-" * 60)
    for r in polars_results:
        print(f"{r.name:<40} {r.mean_ms:>8.2f}ms {r.median_ms:>8.2f}ms {r.min_ms:>6.2f}ms")

    print("\n📊 Résultats Pandas:")
    print("-" * 60)
    print(f"{'Opération':<40} {'Moyenne':>10} {'Médiane':>10} {'Min':>8}")
    print("-" * 60)
    for r in pandas_results:
        print(f"{r.name:<40} {r.mean_ms:>8.2f}ms {r.median_ms:>8.2f}ms {r.min_ms:>6.2f}ms")

    # Comparaison pour les opérations communes
    print("\n📈 Comparaison (même opération):")
    print("-" * 60)

    # Chargement
    if polars_results and pandas_results:
        polars_load = polars_results[0].mean_ms
        pandas_load = pandas_results[0].mean_ms
        if polars_load > 0:
            speedup = pandas_load / polars_load
            winner = "Polars" if speedup > 1 else "Pandas"
            print(f"Chargement KV pairs : {winner} est {abs(speedup):.2f}x plus rapide")

        if len(polars_results) > 1 and len(pandas_results) > 1:
            polars_stats = polars_results[1].mean_ms
            pandas_stats = pandas_results[1].mean_ms
            if polars_stats > 0:
                speedup = pandas_stats / polars_stats
                winner = "Polars" if speedup > 1 else "Pandas"
                print(f"Chargement match_stats : {winner} est {abs(speedup):.2f}x plus rapide")

    # Total
    total_polars = sum(r.mean_ms for r in polars_results)
    total_pandas = sum(r.mean_ms for r in pandas_results)

    print(f"\n⏱️ Temps total Polars  : {total_polars:.2f}ms")
    print(f"⏱️ Temps total Pandas  : {total_pandas:.2f}ms")

    if total_polars > 0:
        overall_speedup = total_pandas / total_polars
        overall_winner = "Polars" if overall_speedup > 1 else "Pandas"
        print(f"\n🏆 {overall_winner} est globalement {abs(overall_speedup):.2f}x plus rapide")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Polars vs Pandas pour les analyses killer_victim"
    )
    parser.add_argument(
        "--gamertag",
        "-g",
        required=True,
        help="Gamertag du joueur (dossier dans data/players/)",
    )
    parser.add_argument(
        "--db-path",
        "-d",
        help="Chemin direct vers stats.duckdb",
    )
    parser.add_argument(
        "--xuid",
        help="XUID du joueur (optionnel)",
    )
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=5,
        help="Nombre d'itérations par benchmark (défaut: 5)",
    )

    args = parser.parse_args()

    # Déterminer le chemin de la DB
    if args.db_path:
        db_path = Path(args.db_path)
    else:
        db_path = Path(__file__).parent.parent / "data" / "players" / args.gamertag / "stats.duckdb"

    if not db_path.exists():
        logger.error(f"Base de données non trouvée: {db_path}")
        sys.exit(1)

    # Récupérer le XUID si non fourni
    xuid = args.xuid
    if not xuid:
        import duckdb

        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            # Essayer de récupérer depuis sync_meta
            result = conn.execute("SELECT value FROM sync_meta WHERE key = 'xuid'").fetchone()
            if result:
                xuid = result[0]
        except Exception:
            pass

        if not xuid:
            # Fallback: utiliser le premier XUID dans killer_victim_pairs
            try:
                result = conn.execute(
                    "SELECT DISTINCT killer_xuid FROM killer_victim_pairs LIMIT 1"
                ).fetchone()
                if result:
                    xuid = result[0]
            except Exception:
                pass

        conn.close()

    if not xuid:
        logger.error("XUID non trouvé. Spécifiez --xuid")
        sys.exit(1)

    logger.info(f"Base de données: {db_path}")
    logger.info(f"XUID: {xuid}")
    logger.info(f"Itérations: {args.iterations}")

    # Vérifier les dépendances
    try:
        import polars as pl

        logger.info(f"Polars version: {pl.__version__}")
    except ImportError:
        logger.error("Polars non installé. Installez avec: pip install polars")
        sys.exit(1)

    try:
        import pandas as pd

        logger.info(f"Pandas version: {pd.__version__}")
    except ImportError:
        logger.error("Pandas non installé. Installez avec: pip install pandas")
        sys.exit(1)

    # Exécuter les benchmarks
    logger.info("\nExécution des benchmarks Polars...")
    polars_results = run_polars_benchmarks(db_path, xuid, args.iterations)

    logger.info("Exécution des benchmarks Pandas...")
    pandas_results = run_pandas_benchmarks(db_path, xuid, args.iterations)

    # Afficher les résultats
    print_results(polars_results, pandas_results)


if __name__ == "__main__":
    main()
