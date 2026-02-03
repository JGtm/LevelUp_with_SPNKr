#!/usr/bin/env python3
"""Backfill des PersonalScoreAwards depuis l'API.

Sprint 8.2 - Ce script :
1. Lit tous les match_ids existants dans la DB joueur
2. Pour chaque match, récupère les PersonalScores depuis l'API
3. Insère dans la table personal_score_awards

Usage:
    # Un joueur spécifique
    python scripts/backfill_personal_score_awards.py --gamertag MonGT

    # Limiter le nombre de matchs
    python scripts/backfill_personal_score_awards.py --gamertag MonGT --limit 100

    # Dry-run (simulation sans insertion)
    python scripts/backfill_personal_score_awards.py --gamertag MonGT --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.sync.api_client import SPNKrAPIClient, get_tokens_from_env
from src.data.sync.transformers import (
    extract_personal_score_awards,
    transform_personal_score_awards,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """S'assure que la table personal_score_awards existe."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS personal_score_awards (
            id INTEGER PRIMARY KEY,
            match_id VARCHAR NOT NULL,
            xuid VARCHAR NOT NULL,
            award_name VARCHAR NOT NULL,
            award_category VARCHAR,
            award_count INTEGER DEFAULT 1,
            award_score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Index pour les requêtes
    with contextlib.suppress(Exception):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_psa_match ON personal_score_awards(match_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_psa_xuid ON personal_score_awards(xuid)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_psa_category ON personal_score_awards(award_category)"
        )


def get_processed_matches(conn: duckdb.DuckDBPyConnection) -> set[str]:
    """Retourne les match_id déjà traités."""
    try:
        result = conn.execute("SELECT DISTINCT match_id FROM personal_score_awards").fetchall()
        return {r[0] for r in result if r[0]}
    except Exception:
        return set()


def get_all_match_ids(conn: duckdb.DuckDBPyConnection, limit: int | None = None) -> list[str]:
    """Récupère tous les match_ids de la DB."""
    try:
        sql = "SELECT match_id FROM match_stats ORDER BY start_time DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        result = conn.execute(sql).fetchall()
        return [r[0] for r in result if r[0]]
    except Exception:
        return []


def get_xuid_from_db(conn: duckdb.DuckDBPyConnection) -> str | None:
    """Récupère le XUID depuis sync_meta."""
    try:
        result = conn.execute("SELECT value FROM sync_meta WHERE key = 'xuid'").fetchone()
        return result[0] if result else None
    except Exception:
        return None


async def backfill_match(
    client: SPNKrAPIClient,
    conn: duckdb.DuckDBPyConnection,
    match_id: str,
    xuid: str,
    *,
    dry_run: bool = False,
) -> int:
    """Récupère et insère les PersonalScores pour un match.

    Returns:
        Nombre d'awards insérés.
    """
    # Récupérer les stats depuis l'API
    stats_json = await client.get_match_stats(match_id)
    if stats_json is None:
        return 0

    # Extraire les PersonalScores
    personal_scores = extract_personal_score_awards(stats_json, xuid)
    if not personal_scores:
        return 0

    if dry_run:
        logger.debug(f"  [DRY-RUN] Match {match_id}: {len(personal_scores)} awards")
        return len(personal_scores)

    # Transformer en rows
    rows = transform_personal_score_awards(match_id, xuid, personal_scores)

    # Insérer
    now = datetime.now(timezone.utc)
    inserted = 0

    for row in rows:
        try:
            conn.execute(
                """INSERT INTO personal_score_awards (
                    match_id, xuid, award_name, award_category,
                    award_count, award_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    row.match_id,
                    row.xuid,
                    row.award_name,
                    row.award_category,
                    row.award_count,
                    row.award_score,
                    now,
                ),
            )
            inserted += 1
        except Exception as e:
            logger.debug(f"  Erreur insertion: {e}")

    return inserted


async def backfill_player_db(
    db_path: Path,
    xuid: str | None,
    *,
    limit: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    requests_per_second: int = 3,
) -> dict:
    """Backfill une base joueur.

    Args:
        db_path: Chemin vers stats.duckdb du joueur.
        xuid: XUID du joueur (récupéré depuis DB si None).
        limit: Limite du nombre de matchs à traiter.
        dry_run: Si True, ne modifie pas la DB.
        force: Si True, retraite tous les matchs.
        requests_per_second: Rate limiting API.

    Returns:
        Dict avec statistiques.
    """
    logger.info(f"Traitement de {db_path}")

    stats = {
        "db_path": str(db_path),
        "matches_processed": 0,
        "matches_skipped": 0,
        "awards_inserted": 0,
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

        # Récupérer le XUID si non fourni
        if xuid is None:
            xuid = get_xuid_from_db(conn)

        if xuid is None:
            stats["errors"].append("XUID non trouvé dans la DB")
            return stats

        logger.info(f"  XUID: {xuid}")

        # Récupérer tous les match_ids
        all_match_ids = get_all_match_ids(conn, limit=limit)
        if not all_match_ids:
            logger.info("  Aucun match trouvé")
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

        if not match_ids:
            logger.info("  Tous les matchs sont déjà traités")
            return stats

        # Récupérer les tokens
        tokens = await get_tokens_from_env()

        # Traiter les matchs
        async with SPNKrAPIClient(
            tokens=tokens,
            requests_per_second=requests_per_second,
        ) as client:
            for i, match_id in enumerate(match_ids, 1):
                try:
                    awards_count = await backfill_match(
                        client,
                        conn,
                        match_id,
                        xuid,
                        dry_run=dry_run,
                    )
                    stats["awards_inserted"] += awards_count
                    stats["matches_processed"] += 1

                    if i % 20 == 0:
                        logger.info(f"  Progression: {i}/{len(match_ids)} matchs")
                        if not dry_run:
                            conn.commit()

                except Exception as e:
                    stats["errors"].append(f"Match {match_id}: {e}")
                    logger.warning(f"  Erreur match {match_id}: {e}")

        # Commit final
        if not dry_run:
            conn.commit()

        logger.info(
            f"  Terminé: {stats['matches_processed']} matchs, " f"{stats['awards_inserted']} awards"
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


async def main_async(args):
    """Fonction principale async."""
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
        logger.error("Spécifiez --gamertag, --all, ou --db-path")
        return

    if not db_paths:
        logger.error("Aucune base de données trouvée")
        return

    logger.info(f"Traitement de {len(db_paths)} base(s) de données")
    if args.dry_run:
        logger.info("Mode DRY-RUN activé (aucune modification)")

    # Statistiques globales
    total_stats = {
        "databases": len(db_paths),
        "matches_processed": 0,
        "matches_skipped": 0,
        "awards_inserted": 0,
        "errors": [],
    }

    # Traiter chaque base
    for db_path in db_paths:
        stats = await backfill_player_db(
            db_path,
            xuid=args.xuid,
            limit=args.limit,
            dry_run=args.dry_run,
            force=args.force,
            requests_per_second=args.rate_limit,
        )
        total_stats["matches_processed"] += stats["matches_processed"]
        total_stats["matches_skipped"] += stats["matches_skipped"]
        total_stats["awards_inserted"] += stats["awards_inserted"]
        total_stats["errors"].extend(stats["errors"])

    # Résumé final
    logger.info("=" * 60)
    logger.info("RÉSUMÉ BACKFILL PERSONAL_SCORE_AWARDS")
    logger.info("=" * 60)
    logger.info(f"Bases traitées     : {total_stats['databases']}")
    logger.info(f"Matchs traités     : {total_stats['matches_processed']}")
    logger.info(f"Matchs ignorés     : {total_stats['matches_skipped']}")
    logger.info(f"Awards insérés     : {total_stats['awards_inserted']}")
    if total_stats["errors"]:
        logger.warning(f"Erreurs            : {len(total_stats['errors'])}")
        for err in total_stats["errors"][:5]:
            logger.warning(f"  - {err}")

    if args.dry_run:
        logger.info("\n[DRY-RUN] Aucune donnée n'a été modifiée")


def main():
    parser = argparse.ArgumentParser(description="Backfill des PersonalScoreAwards depuis l'API")
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
        "--xuid",
        help="XUID du joueur (optionnel, récupéré depuis DB si non fourni)",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        help="Limite du nombre de matchs à traiter",
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=3,
        help="Requêtes par seconde (défaut: 3)",
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

    if not args.gamertag and not args.all and not args.db_path:
        parser.error("Spécifiez --gamertag, --all, ou --db-path")

    # Exécuter
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
