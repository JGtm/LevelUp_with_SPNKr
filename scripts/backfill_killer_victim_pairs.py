#!/usr/bin/env python3
"""Backfill des paires killer→victim depuis highlight_events.

Sprint 8.1 - Ce script :
1. Lit tous les highlight_events existants dans chaque DB joueur
2. Calcule les paires killer→victim avec compute_killer_victim_pairs()
3. Insère les paires dans la nouvelle table killer_victim_pairs

Usage:
    # Un joueur spécifique
    python scripts/backfill_killer_victim_pairs.py --gamertag MonGT

    # Tous les joueurs
    python scripts/backfill_killer_victim_pairs.py --all

    # Dry-run (simulation)
    python scripts/backfill_killer_victim_pairs.py --gamertag MonGT --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.killer_victim import compute_killer_victim_pairs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """S'assure que la table killer_victim_pairs existe."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS killer_victim_pairs (
            id INTEGER PRIMARY KEY,
            match_id VARCHAR NOT NULL,
            killer_xuid VARCHAR NOT NULL,
            killer_gamertag VARCHAR,
            victim_xuid VARCHAR NOT NULL,
            victim_gamertag VARCHAR,
            kill_count INTEGER DEFAULT 1,
            time_ms INTEGER,
            is_validated BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Index pour les requêtes
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kv_match ON killer_victim_pairs(match_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kv_killer ON killer_victim_pairs(killer_xuid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kv_victim ON killer_victim_pairs(victim_xuid)")
    except Exception:
        pass  # Index existe déjà


def get_processed_matches(conn: duckdb.DuckDBPyConnection) -> set[str]:
    """Retourne les match_id déjà traités."""
    try:
        result = conn.execute("SELECT DISTINCT match_id FROM killer_victim_pairs").fetchall()
        return {r[0] for r in result if r[0]}
    except Exception:
        return set()


def get_highlight_events_by_match(
    conn: duckdb.DuckDBPyConnection,
    match_id: str,
) -> list[dict]:
    """Récupère les highlight events pour un match."""
    try:
        result = conn.execute(
            """
            SELECT match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json
            FROM highlight_events
            WHERE match_id = ?
            ORDER BY time_ms
            """,
            [match_id],
        ).fetchall()

        events = []
        for row in result:
            events.append(
                {
                    "match_id": row[0],
                    "event_type": row[1],
                    "time_ms": row[2],
                    "xuid": row[3],
                    "gamertag": row[4],
                    "type_hint": row[5],
                    "raw_json": row[6],
                }
            )
        return events
    except Exception as e:
        logger.warning(f"Erreur lecture events match {match_id}: {e}")
        return []


def backfill_match(
    conn: duckdb.DuckDBPyConnection,
    match_id: str,
    *,
    tolerance_ms: int = 5,
    dry_run: bool = False,
) -> int:
    """Calcule et insère les paires pour un match.

    Returns:
        Nombre de paires insérées.
    """
    events = get_highlight_events_by_match(conn, match_id)
    if not events:
        return 0

    # Calculer les paires killer→victim
    pairs = compute_killer_victim_pairs(events, tolerance_ms=tolerance_ms)
    if not pairs:
        return 0

    if dry_run:
        logger.info(f"  [DRY-RUN] Match {match_id}: {len(pairs)} paires calculées")
        return len(pairs)

    # Insérer les paires
    now = datetime.now(timezone.utc)
    rows_inserted = 0

    for pair in pairs:
        try:
            conn.execute(
                """
                INSERT INTO killer_victim_pairs (
                    match_id, killer_xuid, killer_gamertag,
                    victim_xuid, victim_gamertag, kill_count, time_ms,
                    is_validated, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    pair.killer_xuid,
                    pair.killer_gamertag,
                    pair.victim_xuid,
                    pair.victim_gamertag,
                    1,  # kill_count = 1 par paire
                    pair.time_ms,
                    False,  # is_validated = False (pas de stats officielles ici)
                    now,
                ),
            )
            rows_inserted += 1
        except Exception as e:
            logger.warning(f"  Erreur insertion paire {pair}: {e}")

    return rows_inserted


def backfill_player_db(
    db_path: Path,
    *,
    tolerance_ms: int = 5,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    """Backfill une base joueur.

    Args:
        db_path: Chemin vers stats.duckdb du joueur.
        tolerance_ms: Tolérance pour la jointure kill/death.
        dry_run: Si True, ne modifie pas la DB.
        force: Si True, retraite tous les matchs (même déjà traités).

    Returns:
        Dict avec statistiques.
    """
    logger.info(f"Traitement de {db_path}")

    stats = {
        "db_path": str(db_path),
        "matches_processed": 0,
        "matches_skipped": 0,
        "pairs_inserted": 0,
        "errors": [],
    }

    if not db_path.exists():
        stats["errors"].append(f"Base non trouvée: {db_path}")
        return stats

    conn = duckdb.connect(str(db_path), read_only=dry_run)

    try:
        # S'assurer que le schéma existe
        if not dry_run:
            ensure_schema(conn)

        # Récupérer les matchs avec des highlight_events
        result = conn.execute(
            "SELECT DISTINCT match_id FROM highlight_events WHERE match_id IS NOT NULL"
        ).fetchall()
        all_match_ids = [r[0] for r in result if r[0]]

        if not all_match_ids:
            logger.info("  Aucun highlight_events trouvé")
            return stats

        # Filtrer les matchs déjà traités (sauf si force)
        if not force:
            processed = get_processed_matches(conn)
            match_ids = [m for m in all_match_ids if m not in processed]
            stats["matches_skipped"] = len(all_match_ids) - len(match_ids)
        else:
            match_ids = all_match_ids

        logger.info(
            f"  {len(match_ids)} matchs à traiter " f"({stats['matches_skipped']} déjà traités)"
        )

        # Traiter chaque match
        for i, match_id in enumerate(match_ids, 1):
            try:
                pairs_count = backfill_match(
                    conn,
                    match_id,
                    tolerance_ms=tolerance_ms,
                    dry_run=dry_run,
                )
                stats["pairs_inserted"] += pairs_count
                stats["matches_processed"] += 1

                if i % 50 == 0:
                    logger.info(f"  Progression: {i}/{len(match_ids)} matchs")

            except Exception as e:
                stats["errors"].append(f"Match {match_id}: {e}")

        # Commit
        if not dry_run:
            conn.commit()

        logger.info(
            f"  Terminé: {stats['matches_processed']} matchs, " f"{stats['pairs_inserted']} paires"
        )

    except Exception as e:
        stats["errors"].append(str(e))
        logger.error(f"  Erreur: {e}")

    finally:
        conn.close()

    return stats


def find_all_player_dbs() -> list[Path]:
    """Trouve toutes les bases joueurs dans data/players/."""
    data_dir = Path(__file__).parent.parent / "data" / "players"
    if not data_dir.exists():
        return []

    dbs = []
    for player_dir in data_dir.iterdir():
        if player_dir.is_dir():
            db_path = player_dir / "stats.duckdb"
            if db_path.exists():
                dbs.append(db_path)

    return dbs


def main():
    parser = argparse.ArgumentParser(
        description="Backfill des paires killer→victim depuis highlight_events"
    )
    parser.add_argument(
        "--gamertag",
        "-g",
        help="Gamertag du joueur (dossier dans data/players/)",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Traiter tous les joueurs",
    )
    parser.add_argument(
        "--db-path",
        "-d",
        help="Chemin direct vers stats.duckdb",
    )
    parser.add_argument(
        "--tolerance-ms",
        type=int,
        default=5,
        help="Tolérance jointure kill/death en ms (défaut: 5)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulation sans modification",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Retraiter tous les matchs (même déjà traités)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Mode verbeux",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Déterminer les bases à traiter
    db_paths: list[Path] = []

    if args.db_path:
        db_paths.append(Path(args.db_path))
    elif args.gamertag:
        db_path = Path(__file__).parent.parent / "data" / "players" / args.gamertag / "stats.duckdb"
        db_paths.append(db_path)
    elif args.all:
        db_paths = find_all_player_dbs()
    else:
        parser.error("Spécifiez --gamertag, --all, ou --db-path")

    if not db_paths:
        logger.error("Aucune base de données trouvée")
        sys.exit(1)

    logger.info(f"Traitement de {len(db_paths)} base(s) de données")
    if args.dry_run:
        logger.info("Mode DRY-RUN activé (aucune modification)")

    # Statistiques globales
    total_stats = {
        "databases": len(db_paths),
        "matches_processed": 0,
        "matches_skipped": 0,
        "pairs_inserted": 0,
        "errors": [],
    }

    # Traiter chaque base
    for db_path in db_paths:
        stats = backfill_player_db(
            db_path,
            tolerance_ms=args.tolerance_ms,
            dry_run=args.dry_run,
            force=args.force,
        )
        total_stats["matches_processed"] += stats["matches_processed"]
        total_stats["matches_skipped"] += stats["matches_skipped"]
        total_stats["pairs_inserted"] += stats["pairs_inserted"]
        total_stats["errors"].extend(stats["errors"])

    # Résumé final
    logger.info("=" * 60)
    logger.info("RÉSUMÉ BACKFILL KILLER_VICTIM_PAIRS")
    logger.info("=" * 60)
    logger.info(f"Bases traitées     : {total_stats['databases']}")
    logger.info(f"Matchs traités     : {total_stats['matches_processed']}")
    logger.info(f"Matchs ignorés     : {total_stats['matches_skipped']}")
    logger.info(f"Paires insérées    : {total_stats['pairs_inserted']}")
    if total_stats["errors"]:
        logger.warning(f"Erreurs            : {len(total_stats['errors'])}")
        for err in total_stats["errors"][:5]:
            logger.warning(f"  - {err}")

    if args.dry_run:
        logger.info("\n[DRY-RUN] Aucune donnée n'a été modifiée")


if __name__ == "__main__":
    main()
