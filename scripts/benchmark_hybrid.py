#!/usr/bin/env python3
"""
Benchmark Legacy vs Hybrid Repository Performance.

Ce script mesure et compare les performances entre les modes Legacy et Hybrid
pour différentes opérations de requêtes sur les données de match.

Usage:
    python scripts/benchmark_hybrid.py --db path/to/player.db
    python scripts/benchmark_hybrid.py --db path/to/player.db --xuid 2533274823110022
    python scripts/benchmark_hybrid.py --db path/to/player.db --iterations 5 --output report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data import RepositoryMode, get_repository
from src.data.repositories.shadow import ShadowMode, ShadowRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Résultat d'un benchmark individuel."""

    name: str
    mode: str
    iterations: int
    times_ms: list[float]
    mean_ms: float
    std_ms: float
    min_ms: float
    max_ms: float
    rows_returned: int
    success: bool
    error: str | None = None


@dataclass
class BenchmarkComparison:
    """Comparaison entre Legacy et Hybrid."""

    name: str
    legacy: BenchmarkResult
    hybrid: BenchmarkResult
    speedup: float  # >1 = Hybrid plus rapide
    diff_percent: float


@dataclass
class BenchmarkReport:
    """Rapport complet de benchmark."""

    timestamp: str
    db_path: str
    xuid: str
    warehouse_path: str
    iterations: int
    comparisons: list[BenchmarkComparison]
    summary: dict[str, Any]


def time_function(func: Callable[[], Any], iterations: int = 3) -> tuple[list[float], Any]:
    """
    Mesure le temps d'exécution d'une fonction sur plusieurs itérations.

    Returns:
        Tuple (liste des temps en ms, dernier résultat)
    """
    times: list[float] = []
    result = None

    for _ in range(iterations):
        t0 = time.perf_counter()
        result = func()
        dt_ms = (time.perf_counter() - t0) * 1000.0
        times.append(dt_ms)

    return times, result


def run_benchmark(
    name: str,
    mode: str,
    func: Callable[[], Any],
    iterations: int = 3,
) -> BenchmarkResult:
    """Exécute un benchmark et retourne les résultats."""
    try:
        times, result = time_function(func, iterations)

        # Compter les rows retournées
        if isinstance(result, list) or hasattr(result, "__len__"):
            rows = len(result)
        else:
            rows = 1 if result is not None else 0

        return BenchmarkResult(
            name=name,
            mode=mode,
            iterations=iterations,
            times_ms=times,
            mean_ms=statistics.mean(times),
            std_ms=statistics.stdev(times) if len(times) > 1 else 0.0,
            min_ms=min(times),
            max_ms=max(times),
            rows_returned=rows,
            success=True,
        )
    except Exception as e:
        logger.error(f"Erreur benchmark {name} ({mode}): {e}")
        return BenchmarkResult(
            name=name,
            mode=mode,
            iterations=iterations,
            times_ms=[],
            mean_ms=0.0,
            std_ms=0.0,
            min_ms=0.0,
            max_ms=0.0,
            rows_returned=0,
            success=False,
            error=str(e),
        )


def compare_benchmarks(
    name: str,
    legacy_result: BenchmarkResult,
    hybrid_result: BenchmarkResult,
) -> BenchmarkComparison:
    """Compare les résultats Legacy vs Hybrid."""
    if legacy_result.mean_ms > 0 and hybrid_result.mean_ms > 0:
        speedup = legacy_result.mean_ms / hybrid_result.mean_ms
        diff_percent = (
            (legacy_result.mean_ms - hybrid_result.mean_ms) / legacy_result.mean_ms
        ) * 100
    else:
        speedup = 0.0
        diff_percent = 0.0

    return BenchmarkComparison(
        name=name,
        legacy=legacy_result,
        hybrid=hybrid_result,
        speedup=speedup,
        diff_percent=diff_percent,
    )


def run_benchmark_suite(
    db_path: str,
    xuid: str,
    warehouse_path: str,
    iterations: int = 3,
) -> BenchmarkReport:
    """Exécute la suite complète de benchmarks."""
    comparisons: list[BenchmarkComparison] = []

    # Créer les repositories
    logger.info(f"Création des repositories pour xuid={xuid}")

    legacy_repo = get_repository(db_path, xuid, mode=RepositoryMode.LEGACY)

    shadow_repo = ShadowRepository(
        db_path,
        xuid,
        warehouse_path=warehouse_path,
        mode=ShadowMode.HYBRID_FIRST,
    )

    hybrid_available = shadow_repo.is_hybrid_available()
    logger.info(f"Hybrid disponible: {hybrid_available}")

    # ==== Benchmark 1: load_matches (tous) ====
    logger.info("Benchmark: load_matches (tous)")
    legacy_result = run_benchmark(
        "load_matches_all",
        "legacy",
        lambda: legacy_repo.load_matches(),
        iterations,
    )
    hybrid_result = run_benchmark(
        "load_matches_all",
        "hybrid",
        lambda: shadow_repo.load_matches(),
        iterations,
    )
    comparisons.append(compare_benchmarks("load_matches_all", legacy_result, hybrid_result))

    # ==== Benchmark 2: load_matches avec filtre playlist ====
    logger.info("Benchmark: load_matches (filtre playlist)")
    legacy_result = run_benchmark(
        "load_matches_ranked",
        "legacy",
        lambda: legacy_repo.load_matches(playlist_filter="Ranked"),
        iterations,
    )
    hybrid_result = run_benchmark(
        "load_matches_ranked",
        "hybrid",
        lambda: shadow_repo.load_matches(playlist_filter="Ranked"),
        iterations,
    )
    comparisons.append(compare_benchmarks("load_matches_ranked", legacy_result, hybrid_result))

    # ==== Benchmark 3: get_match_count ====
    logger.info("Benchmark: get_match_count")
    legacy_result = run_benchmark(
        "get_match_count",
        "legacy",
        lambda: legacy_repo.get_match_count(),
        iterations,
    )
    hybrid_result = run_benchmark(
        "get_match_count",
        "hybrid",
        lambda: shadow_repo.get_match_count(),
        iterations,
    )
    comparisons.append(compare_benchmarks("get_match_count", legacy_result, hybrid_result))

    # ==== Benchmark 4: get_storage_info ====
    logger.info("Benchmark: get_storage_info")
    legacy_result = run_benchmark(
        "get_storage_info",
        "legacy",
        lambda: legacy_repo.get_storage_info(),
        iterations,
    )
    hybrid_result = run_benchmark(
        "get_storage_info",
        "hybrid",
        lambda: shadow_repo.get_storage_info(),
        iterations,
    )
    comparisons.append(compare_benchmarks("get_storage_info", legacy_result, hybrid_result))

    # Fermer les repos (si la méthode existe)
    if hasattr(legacy_repo, "close"):
        legacy_repo.close()
    if hasattr(shadow_repo, "close"):
        shadow_repo.close()

    # Calculer le résumé
    successful = [c for c in comparisons if c.legacy.success and c.hybrid.success]
    avg_speedup = statistics.mean([c.speedup for c in successful]) if successful else 0.0

    summary = {
        "total_benchmarks": len(comparisons),
        "successful": len(successful),
        "failed": len(comparisons) - len(successful),
        "avg_speedup": avg_speedup,
        "hybrid_faster_count": sum(1 for c in successful if c.speedup > 1),
        "legacy_faster_count": sum(1 for c in successful if c.speedup < 1),
        "hybrid_available": hybrid_available,
    }

    return BenchmarkReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        db_path=db_path,
        xuid=xuid,
        warehouse_path=warehouse_path,
        iterations=iterations,
        comparisons=comparisons,
        summary=summary,
    )


def print_report(report: BenchmarkReport) -> None:
    """Affiche le rapport de benchmark de façon lisible."""
    print("\n" + "=" * 70)
    print("BENCHMARK LEGACY vs HYBRID")
    print("=" * 70)
    print(f"Timestamp: {report.timestamp}")
    print(f"DB: {report.db_path}")
    print(f"XUID: {report.xuid}")
    print(f"Warehouse: {report.warehouse_path}")
    print(f"Itérations: {report.iterations}")
    print(f"Hybrid disponible: {report.summary['hybrid_available']}")
    print("-" * 70)

    print(
        f"\n{'Benchmark':<25} {'Legacy (ms)':<15} {'Hybrid (ms)':<15} {'Speedup':<10} {'Winner':<10}"
    )
    print("-" * 70)

    for comp in report.comparisons:
        if comp.legacy.success and comp.hybrid.success:
            winner = "Hybrid *" if comp.speedup > 1 else "Legacy *" if comp.speedup < 1 else "Equal"
            print(
                f"{comp.name:<25} "
                f"{comp.legacy.mean_ms:>10.1f} ms   "
                f"{comp.hybrid.mean_ms:>10.1f} ms   "
                f"{comp.speedup:>6.2f}x    "
                f"{winner}"
            )
        else:
            status = "FAIL" if not comp.legacy.success else "HYBRID FAIL"
            print(f"{comp.name:<25} {status}")

    print("-" * 70)
    print("\nRésumé:")
    print(
        f"  - Benchmarks réussis: {report.summary['successful']}/{report.summary['total_benchmarks']}"
    )
    print(f"  - Speedup moyen: {report.summary['avg_speedup']:.2f}x")
    print(f"  - Hybrid plus rapide: {report.summary['hybrid_faster_count']} fois")
    print(f"  - Legacy plus rapide: {report.summary['legacy_faster_count']} fois")
    print("=" * 70 + "\n")


def export_report(report: BenchmarkReport, output_path: str) -> None:
    """Exporte le rapport en JSON."""

    def serialize(obj: Any) -> Any:
        if hasattr(obj, "__dict__"):
            return asdict(obj) if hasattr(obj, "__dataclass_fields__") else obj.__dict__
        return obj

    # Convertir en dict sérialisable
    data = {
        "timestamp": report.timestamp,
        "db_path": report.db_path,
        "xuid": report.xuid,
        "warehouse_path": report.warehouse_path,
        "iterations": report.iterations,
        "comparisons": [asdict(c) for c in report.comparisons],
        "summary": report.summary,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Rapport exporté: {output_path}")


def find_default_xuid(db_path: str) -> str | None:
    """Trouve un XUID par défaut depuis db_profiles.json ou la DB."""
    db_path_resolved = Path(db_path).resolve()

    # Essayer db_profiles.json d'abord
    profiles_path = Path(__file__).parent.parent / "db_profiles.json"
    if profiles_path.exists():
        try:
            with open(profiles_path, encoding="utf-8") as f:
                profiles = json.load(f).get("profiles", {})

            for profile_name, profile_data in profiles.items():
                profile_db = Path(profile_data.get("db_path", "")).resolve()
                # Essayer aussi avec le chemin relatif depuis le projet
                profile_db_alt = (
                    Path(__file__).parent.parent / profile_data.get("db_path", "")
                ).resolve()

                if db_path_resolved in (profile_db, profile_db_alt):
                    xuid = profile_data.get("xuid")
                    if xuid:
                        logger.info(
                            f"XUID trouvé dans db_profiles.json pour {profile_name}: {xuid}"
                        )
                        return xuid
        except Exception as e:
            logger.warning(f"Erreur lecture db_profiles.json: {e}")

    # Fallback: essayer PlayerMatchStats ou MatchCache
    import sqlite3

    try:
        with sqlite3.connect(db_path) as conn:
            # Essayer PlayerMatchStats
            try:
                cursor = conn.execute("SELECT DISTINCT xuid FROM PlayerMatchStats LIMIT 1")
                row = cursor.fetchone()
                if row and row[0]:
                    xuid = row[0]
                    if xuid.startswith("xuid("):
                        xuid = xuid[5:-1]
                    return xuid
            except sqlite3.OperationalError:
                pass

            # Essayer MatchCache
            try:
                cursor = conn.execute("SELECT DISTINCT xuid FROM MatchCache LIMIT 1")
                row = cursor.fetchone()
                if row and row[0]:
                    xuid = row[0]
                    if xuid.startswith("xuid("):
                        xuid = xuid[5:-1]
                    return xuid
            except sqlite3.OperationalError:
                pass
    except Exception as e:
        logger.warning(f"Impossible de trouver XUID dans la DB: {e}")

    return None


def main():
    parser = argparse.ArgumentParser(description="Benchmark Legacy vs Hybrid repositories")
    parser.add_argument("--db", required=True, help="Chemin vers player.db")
    parser.add_argument("--xuid", help="XUID du joueur (détecté auto si absent)")
    parser.add_argument("--warehouse", default="data/warehouse", help="Chemin warehouse Parquet")
    parser.add_argument("--iterations", type=int, default=3, help="Nombre d'itérations par test")
    parser.add_argument("--output", help="Fichier JSON de sortie (optionnel)")

    args = parser.parse_args()

    # Vérifier que la DB existe
    if not Path(args.db).exists():
        logger.error(f"DB introuvable: {args.db}")
        sys.exit(1)

    # Trouver XUID si non fourni
    xuid = args.xuid or find_default_xuid(args.db)
    if not xuid:
        logger.error("XUID non fourni et impossible à détecter")
        sys.exit(1)

    logger.info(f"Démarrage benchmark: db={args.db}, xuid={xuid}")

    # Exécuter les benchmarks
    report = run_benchmark_suite(
        db_path=args.db,
        xuid=xuid,
        warehouse_path=args.warehouse,
        iterations=args.iterations,
    )

    # Afficher les résultats
    print_report(report)

    # Exporter si demandé
    if args.output:
        export_report(report, args.output)

    # Code de sortie basé sur le succès
    if report.summary["failed"] > 0:
        sys.exit(1)

    return 0


if __name__ == "__main__":
    main()
