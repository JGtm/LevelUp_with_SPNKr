#!/usr/bin/env python3
"""Script de recalcul des scores de performance v4 pour DuckDB.

Recalcule tous les performance_score dans match_stats en utilisant la formule v4
(8 métriques : KPM, DPM deaths, APM, KDA, accuracy, PSPM, DPM damage, rank_perf).

Usage:
    # Simulation pour un joueur (affiche les stats sans modifier la DB)
    python scripts/recompute_performance_scores_duckdb.py --player JGtm --dry-run

    # Recalcul pour un joueur spécifique
    python scripts/recompute_performance_scores_duckdb.py --player JGtm

    # Recalcul pour tous les joueurs
    python scripts/recompute_performance_scores_duckdb.py --all

    # Forcer le recalcul même pour les matchs qui ont déjà un score
    python scripts/recompute_performance_scores_duckdb.py --player JGtm --force

    # Spécifier la taille des batches de commit
    python scripts/recompute_performance_scores_duckdb.py --all --batch-size 200
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import duckdb
import polars as pl

# Ajouter le répertoire racine du projet au path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.performance_config import (
    MIN_MATCHES_FOR_RELATIVE,
    PERFORMANCE_SCORE_VERSION,
)
from src.analysis.performance_score import compute_relative_performance_score

logger = logging.getLogger(__name__)

# Colonnes requises pour le calcul v4
HISTORY_COLUMNS = """
    match_id, start_time, kills, deaths, assists, kda, accuracy,
    time_played_seconds, avg_life_seconds,
    personal_score, damage_dealt,
    rank, team_mmr, enemy_mmr,
    performance_score
"""


def load_player_matches(db_path: Path) -> pl.DataFrame:
    """Charge tous les matchs d'un joueur depuis DuckDB."""
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        df = conn.execute(f"""
            SELECT {HISTORY_COLUMNS}
            FROM match_stats
            WHERE start_time IS NOT NULL
            ORDER BY start_time ASC
        """).pl()
        return df
    finally:
        conn.close()


def recompute_scores_for_player(
    db_path: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
    batch_size: int = 100,
) -> dict[str, int]:
    """Recalcule les scores de performance v4 pour un joueur.

    Args:
        db_path: Chemin vers stats.duckdb du joueur.
        dry_run: Si True, simule sans écrire.
        force: Si True, recalcule même les scores existants.
        batch_size: Nombre de mises à jour par commit.

    Returns:
        Dict avec les statistiques de traitement.
    """
    stats = {"total": 0, "computed": 0, "skipped": 0, "errors": 0, "insufficient": 0}

    # Charger tous les matchs
    df = load_player_matches(db_path)
    if df.is_empty():
        return stats

    stats["total"] = len(df)

    # Ouvrir connexion en écriture si pas dry-run
    conn = None
    if not dry_run:
        conn = duckdb.connect(str(db_path), read_only=False)

    batch_updates: list[tuple[float, str]] = []

    try:
        for idx in range(len(df)):
            row = df.row(idx, named=True)
            match_id = row["match_id"]

            # Skip si score existe déjà et pas force
            if not force and row.get("performance_score") is not None:
                stats["skipped"] += 1
                continue

            # Historique = tous les matchs AVANT celui-ci
            if idx < MIN_MATCHES_FOR_RELATIVE:
                stats["insufficient"] += 1
                continue

            history = df.slice(0, idx)

            # Calculer le score v4
            try:
                score = compute_relative_performance_score(row, history)

                if score is not None:
                    stats["computed"] += 1
                    if not dry_run and conn:
                        batch_updates.append((score, match_id))

                        # Commit par batch
                        if len(batch_updates) >= batch_size:
                            conn.executemany(
                                "UPDATE match_stats SET performance_score = ? WHERE match_id = ?",
                                batch_updates,
                            )
                            conn.commit()
                            batch_updates = []
                else:
                    stats["insufficient"] += 1
            except Exception as e:
                stats["errors"] += 1
                logger.warning(f"Erreur pour {match_id}: {e}")

        # Commit restant
        if batch_updates and not dry_run and conn:
            conn.executemany(
                "UPDATE match_stats SET performance_score = ? WHERE match_id = ?",
                batch_updates,
            )
            conn.commit()
    finally:
        if conn:
            conn.close()

    return stats


def find_player_dbs(player: str | None = None) -> list[tuple[str, Path]]:
    """Trouve les DB des joueurs à traiter.

    Args:
        player: Gamertag spécifique ou None pour tous.

    Returns:
        Liste de (gamertag, db_path).
    """
    profiles_path = PROJECT_ROOT / "db_profiles.json"

    if not profiles_path.exists():
        # Fallback : scanner data/players/
        players_dir = PROJECT_ROOT / "data" / "players"
        if not players_dir.exists():
            return []
        results = []
        for p in players_dir.iterdir():
            if p.is_dir():
                db = p / "stats.duckdb"
                if db.exists() and (player is None or p.name == player):
                    results.append((p.name, db))
        return results

    with open(profiles_path) as f:
        profiles = json.load(f)

    results = []
    for gt, info in profiles.get("profiles", {}).items():
        if player is not None and gt != player:
            continue
        db_path = PROJECT_ROOT / info["db_path"]
        if db_path.exists():
            results.append((gt, db_path))

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Recalcul des scores de performance {PERFORMANCE_SCORE_VERSION}"
    )
    parser.add_argument("--player", help="Gamertag spécifique")
    parser.add_argument("--all", action="store_true", help="Tous les joueurs")
    parser.add_argument("--dry-run", action="store_true", help="Simulation (pas d'écriture)")
    parser.add_argument("--force", action="store_true", help="Recalculer même les scores existants")
    parser.add_argument("--batch-size", type=int, default=100, help="Taille des batches de commit")
    args = parser.parse_args()

    if not args.player and not args.all:
        parser.error("Spécifier --player GAMERTAG ou --all")

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Trouver les DB à traiter
    player_dbs = find_player_dbs(args.player)

    if not player_dbs:
        print(f"Aucune DB trouvée{f' pour {args.player}' if args.player else ''}")
        sys.exit(1)

    mode = "DRY-RUN" if args.dry_run else "RECALCUL"
    print(f"\n=== {mode} Performance Score {PERFORMANCE_SCORE_VERSION} ===")
    print(f"Joueurs : {len(player_dbs)}")
    if args.force:
        print("Mode : FORCE (recalcul de tous les scores)")
    print()

    total_stats = {"total": 0, "computed": 0, "skipped": 0, "errors": 0, "insufficient": 0}

    for gamertag, db_path in player_dbs:
        print(f"  {gamertag} ({db_path.name})... ", end="", flush=True)

        stats = recompute_scores_for_player(
            db_path,
            dry_run=args.dry_run,
            force=args.force,
            batch_size=args.batch_size,
        )

        print(
            f"{stats['total']} matchs, "
            f"{stats['computed']} calculés, "
            f"{stats['skipped']} skippés, "
            f"{stats['insufficient']} insuffisants, "
            f"{stats['errors']} erreurs"
        )

        for k in total_stats:
            total_stats[k] += stats[k]

    print("\n=== Résumé ===")
    print(f"Total matchs : {total_stats['total']}")
    print(f"Scores calculés : {total_stats['computed']}")
    print(f"Skippés (déjà présents) : {total_stats['skipped']}")
    print(f"Historique insuffisant : {total_stats['insufficient']}")
    print(f"Erreurs : {total_stats['errors']}")

    if args.dry_run:
        print("\n(Mode dry-run — aucune modification effectuée)")


if __name__ == "__main__":
    main()
