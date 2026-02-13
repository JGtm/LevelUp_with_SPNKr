#!/usr/bin/env python
"""Benchmark reproductible des pages UI LevelUp.

Mesure le temps de chargement cold/warm des données et la préparation
des DataFrames pour les pages cibles (Timeseries, Coéquipiers, Carrière,
Win/Loss, Session Compare).

Usage:
    python scripts/benchmark_pages.py --baseline --output .ai/reports/benchmark_baseline_pre_s16.json
    python scripts/benchmark_pages.py --runs 5
    python scripts/benchmark_pages.py --compare .ai/reports/benchmark_baseline_pre_s16.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Ajouter la racine du projet au path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import polars as pl

from src.data.repositories import DuckDBRepository


# ---------------------------------------------------------------------------
# Structures de résultat
# ---------------------------------------------------------------------------
@dataclass
class BenchResult:
    """Résultat d'un benchmark individuel."""

    name: str
    times_ms: list[float] = field(default_factory=list)
    rows_returned: int = 0
    success: bool = True
    error: str | None = None

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.times_ms) if self.times_ms else 0.0

    @property
    def std_ms(self) -> float:
        return statistics.stdev(self.times_ms) if len(self.times_ms) > 1 else 0.0

    @property
    def min_ms(self) -> float:
        return min(self.times_ms) if self.times_ms else 0.0

    @property
    def max_ms(self) -> float:
        return max(self.times_ms) if self.times_ms else 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "times_ms": self.times_ms,
            "mean_ms": self.mean_ms,
            "std_ms": self.std_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "rows_returned": self.rows_returned,
            "success": self.success,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Résolution du profil joueur
# ---------------------------------------------------------------------------
def _resolve_profile() -> tuple[str, str]:
    """Retourne (db_path, xuid) du premier profil valide dans db_profiles.json."""
    profiles_path = PROJECT_ROOT / "db_profiles.json"
    if not profiles_path.exists():
        raise FileNotFoundError("db_profiles.json introuvable à la racine du projet")

    with open(profiles_path, encoding="utf-8") as f:
        data = json.load(f)

    for _gt, profile in data.get("profiles", {}).items():
        db_path = profile.get("db_path", "")
        xuid = profile.get("xuid", "")
        full_path = PROJECT_ROOT / db_path
        if full_path.exists() and xuid:
            return str(full_path), xuid

    raise FileNotFoundError("Aucun profil avec une DB valide trouvé dans db_profiles.json")


def _get_git_hash() -> str:
    """Retourne le hash court du commit courant."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Fonctions de chargement (sans Streamlit)
# ---------------------------------------------------------------------------
def _load_matches_raw(db_path: str, xuid: str) -> pl.DataFrame:
    """Charge le DataFrame complet via DuckDBRepository (cold load)."""
    repo = DuckDBRepository(db_path, xuid)
    try:
        matches = repo.load_matches()
        if not matches:
            return pl.DataFrame()
        return pl.DataFrame(matches)
    finally:
        repo.close()


def _load_top_medals(db_path: str, xuid: str, match_ids: list[str], limit: int = 20) -> list:
    """Charge le top-N des médailles."""
    repo = DuckDBRepository(db_path, xuid)
    try:
        return repo.load_top_medals(match_ids, top_n=limit)
    finally:
        repo.close()


def _load_top_teammates(db_path: str, xuid: str, limit: int = 20) -> list[dict]:
    """Charge le top-N des coéquipiers."""
    repo = DuckDBRepository(db_path, xuid)
    try:
        return repo.list_top_teammates(limit=limit)
    finally:
        repo.close()


# ---------------------------------------------------------------------------
# Benchmarks individuels
# ---------------------------------------------------------------------------
def bench_cold_load(db_path: str, xuid: str, runs: int) -> BenchResult:
    """Benchmark: chargement cold du DataFrame principal."""
    result = BenchResult(name="cold_load_matches")
    try:
        for _ in range(runs):
            t0 = time.perf_counter()
            df = _load_matches_raw(db_path, xuid)
            elapsed = (time.perf_counter() - t0) * 1000
            result.times_ms.append(elapsed)
            result.rows_returned = len(df)
    except Exception as e:
        result.success = False
        result.error = str(e)
    return result


def bench_warm_load(db_path: str, xuid: str, runs: int) -> BenchResult:
    """Benchmark: chargement warm (connexion réutilisée)."""
    result = BenchResult(name="warm_load_matches")
    try:
        repo = DuckDBRepository(db_path, xuid)
        try:
            for _ in range(runs):
                t0 = time.perf_counter()
                matches = repo.load_matches()
                elapsed = (time.perf_counter() - t0) * 1000
                result.times_ms.append(elapsed)
                result.rows_returned = len(matches) if matches else 0
        finally:
            repo.close()
    except Exception as e:
        result.success = False
        result.error = str(e)
    return result


def bench_medals_load(db_path: str, xuid: str, runs: int) -> BenchResult:
    """Benchmark: chargement top médailles."""
    result = BenchResult(name="load_top_medals")
    try:
        df = _load_matches_raw(db_path, xuid)
        if "match_id" in df.columns and len(df) > 0:
            match_ids = df["match_id"].head(100).to_list()
        else:
            match_ids = []
        for _ in range(runs):
            t0 = time.perf_counter()
            medals = _load_top_medals(db_path, xuid, match_ids, limit=20)
            elapsed = (time.perf_counter() - t0) * 1000
            result.times_ms.append(elapsed)
            result.rows_returned = len(medals) if medals else 0
    except Exception as e:
        result.success = False
        result.error = str(e)
    return result


def bench_teammates_load(db_path: str, xuid: str, runs: int) -> BenchResult:
    """Benchmark: chargement top coéquipiers."""
    result = BenchResult(name="load_top_teammates")
    try:
        for _ in range(runs):
            t0 = time.perf_counter()
            data = _load_top_teammates(db_path, xuid, limit=20)
            elapsed = (time.perf_counter() - t0) * 1000
            result.times_ms.append(elapsed)
            result.rows_returned = len(data) if data else 0
    except Exception as e:
        result.success = False
        result.error = str(e)
    return result


def bench_polars_filtering(db_path: str, xuid: str, runs: int) -> BenchResult:
    """Benchmark: filtrage Polars typique (simule filtres sidebar)."""
    result = BenchResult(name="polars_filter_chain")
    try:
        df = _load_matches_raw(db_path, xuid)
        for _ in range(runs):
            t0 = time.perf_counter()
            # Simule un pipeline de filtrage typique
            filtered = df
            if "outcome" in df.columns:
                filtered = filtered.filter(pl.col("outcome").is_not_null())
            if "kills" in df.columns:
                filtered = filtered.with_columns(
                    (pl.col("kills") / pl.col("deaths").clip(lower_bound=1)).alias("kd_ratio")
                )
            if "started_at" in df.columns:
                filtered = filtered.sort("started_at", descending=True)
            elapsed = (time.perf_counter() - t0) * 1000
            result.times_ms.append(elapsed)
            result.rows_returned = len(filtered)
    except Exception as e:
        result.success = False
        result.error = str(e)
    return result


def bench_to_pandas_conversion(db_path: str, xuid: str, runs: int) -> BenchResult:
    """Benchmark: coût de conversion Polars → Pandas (frontière Plotly)."""
    result = BenchResult(name="polars_to_pandas_conversion")
    try:
        df = _load_matches_raw(db_path, xuid)
        for _ in range(runs):
            t0 = time.perf_counter()
            _pdf = df.to_pandas()
            elapsed = (time.perf_counter() - t0) * 1000
            result.times_ms.append(elapsed)
            result.rows_returned = len(df)
    except Exception as e:
        result.success = False
        result.error = str(e)
    return result


# ---------------------------------------------------------------------------
# Orchestrateur
# ---------------------------------------------------------------------------
def run_all_benchmarks(db_path: str, xuid: str, runs: int = 5) -> dict:
    """Exécute tous les benchmarks et retourne le rapport complet."""
    print(f"🔧 Benchmark LevelUp — {runs} itérations")
    print(f"   DB: {db_path}")
    print(f"   XUID: {xuid}")
    print()

    benchmarks = [
        ("cold_load", bench_cold_load),
        ("warm_load", bench_warm_load),
        ("medals_100", bench_medals_load),
        ("teammates_top", bench_teammates_load),
        ("polars_filter", bench_polars_filtering),
        ("to_pandas", bench_to_pandas_conversion),
    ]

    results = []
    for label, func in benchmarks:
        print(f"  ⏱️  {label}...", end=" ", flush=True)
        res = func(db_path, xuid, runs)
        status = "✅" if res.success else "❌"
        print(f"{status} {res.mean_ms:.1f}ms (±{res.std_ms:.1f}ms) [{res.rows_returned} rows]")
        results.append(res.to_dict())

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_hash": _get_git_hash(),
        "db_path": db_path,
        "xuid": xuid,
        "iterations": runs,
        "python_version": sys.version,
        "benchmarks": results,
    }

    return report


def compare_reports(baseline_path: str, current: dict) -> None:
    """Affiche la comparaison entre le baseline et les résultats courants."""
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    print("\n📊 Comparaison avec le baseline")
    print(f"   Baseline: {baseline['timestamp']} (git: {baseline.get('git_hash', '?')})")
    print(f"   Courant:  {current['timestamp']} (git: {current.get('git_hash', '?')})")
    print()

    baseline_by_name = {b["name"]: b for b in baseline["benchmarks"]}
    current_by_name = {b["name"]: b for b in current["benchmarks"]}

    print(f"  {'Benchmark':<32} {'Baseline':>10} {'Courant':>10} {'Delta':>10} {'Statut':>8}")
    print(f"  {'─' * 32} {'─' * 10} {'─' * 10} {'─' * 10} {'─' * 8}")

    for name, cur in current_by_name.items():
        base = baseline_by_name.get(name)
        if not base:
            print(f"  {name:<32} {'N/A':>10} {cur['mean_ms']:>9.1f}ms {'NEW':>10} {'🆕':>8}")
            continue

        delta_ms = cur["mean_ms"] - base["mean_ms"]
        delta_pct = (delta_ms / base["mean_ms"] * 100) if base["mean_ms"] > 0 else 0

        if abs(delta_pct) < 10:
            status = "✅"
        elif delta_pct < 0:
            status = "🚀"
        else:
            status = "⚠️"

        print(
            f"  {name:<32} {base['mean_ms']:>9.1f}ms {cur['mean_ms']:>9.1f}ms "
            f"{delta_ms:>+9.1f}ms {status:>8}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark des pages LevelUp")
    parser.add_argument("--runs", type=int, default=5, help="Nombre d'itérations par benchmark")
    parser.add_argument("--output", "-o", type=str, help="Chemin du fichier JSON de sortie")
    parser.add_argument(
        "--baseline", action="store_true", help="Marquer comme baseline (tag dans le rapport)"
    )
    parser.add_argument("--compare", type=str, help="Chemin du baseline JSON pour comparaison")
    parser.add_argument(
        "--db-path", type=str, help="Chemin explicite vers la DB (sinon auto-détecté)"
    )
    parser.add_argument("--xuid", type=str, help="XUID explicite (sinon auto-détecté)")

    args = parser.parse_args()

    # Résoudre le profil
    if args.db_path and args.xuid:
        db_path, xuid = args.db_path, args.xuid
    else:
        db_path, xuid = _resolve_profile()

    # Exécuter
    report = run_all_benchmarks(db_path, xuid, runs=args.runs)

    if args.baseline:
        report["is_baseline"] = True

    # Comparaison
    if args.compare:
        compare_reports(args.compare, report)

    # Sauvegarde
    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = PROJECT_ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Rapport sauvegardé: {out_path}")

    # Vérification reproductibilité
    if len(report["benchmarks"]) > 0:
        max_cv = 0.0
        for b in report["benchmarks"]:
            if b["success"] and b["mean_ms"] > 0:
                cv = b["std_ms"] / b["mean_ms"]
                max_cv = max(max_cv, cv)
        if max_cv > 0.10:
            print(
                f"\n⚠️  Variabilité élevée détectée (CV max = {max_cv:.1%}). "
                f"Relancer dans un environnement plus calme."
            )
        else:
            print(f"\n✅ Reproductibilité OK (CV max = {max_cv:.1%} < 10%)")


if __name__ == "__main__":
    main()
