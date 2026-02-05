#!/usr/bin/env python3
"""Backfill de teammates_signature depuis l'API.

Ce script :
1. Lit tous les match_ids existants dans la DB joueur sans teammates_signature
2. Pour chaque match, récupère le JSON depuis l'API
3. Calcule et met à jour teammates_signature dans match_stats

Usage:
    # Un joueur spécifique
    python scripts/backfill_teammates_signature.py --gamertag MonGT

    # Tous les joueurs
    python scripts/backfill_teammates_signature.py --all

    # Limiter le nombre de matchs
    python scripts/backfill_teammates_signature.py --gamertag MonGT --limit 100

    # Dry-run (simulation sans mise à jour)
    python scripts/backfill_teammates_signature.py --gamertag MonGT --dry-run

    # Forcer le recalcul même si teammates_signature existe
    python scripts/backfill_teammates_signature.py --gamertag MonGT --force
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import duckdb

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.sync.api_client import SPNKrAPIClient, get_tokens_from_env
from src.data.sync.transformers import compute_teammates_signature
from src.ui.multiplayer import list_duckdb_v4_players
from src.ui.sync import get_player_duckdb_path, is_duckdb_player

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_matches_without_signature(
    conn: duckdb.DuckDBPyConnection, limit: int | None = None, force: bool = False
) -> list[tuple[str, str, int | None]]:
    """Récupère les matchs sans teammates_signature.

    Args:
        conn: Connexion DuckDB.
        limit: Limite le nombre de matchs.
        force: Si True, recalcule même si teammates_signature existe.

    Returns:
        Liste de tuples (match_id, xuid, team_id).
    """
    try:
        if force:
            sql = """
                SELECT match_id, team_id
                FROM match_stats
                WHERE start_time IS NOT NULL
                ORDER BY start_time DESC
            """
        else:
            sql = """
                SELECT match_id, team_id
                FROM match_stats
                WHERE start_time IS NOT NULL
                  AND teammates_signature IS NULL
                ORDER BY start_time DESC
            """

        if limit:
            sql += f" LIMIT {int(limit)}"

        result = conn.execute(sql).fetchall()
        return [(r[0], r[1]) for r in result if r[0]]
    except Exception as e:
        logger.error(f"Erreur récupération matchs: {e}")
        return []


async def backfill_match(
    client: SPNKrAPIClient,
    conn: duckdb.DuckDBPyConnection,
    match_id: str,
    xuid: str,
    team_id: int | None,
    *,
    dry_run: bool = False,
) -> bool:
    """Récupère et met à jour teammates_signature pour un match.

    Returns:
        True si mis à jour avec succès.
    """
    # Récupérer les stats depuis l'API
    stats_json = await client.get_match_stats(match_id)
    if stats_json is None:
        logger.debug(f"  Match {match_id}: JSON non disponible")
        return False

    # Calculer la signature
    signature = compute_teammates_signature(stats_json, xuid, team_id)

    if dry_run:
        logger.debug(f"  [DRY-RUN] Match {match_id}: signature = {signature}")
        return True

    # Mettre à jour
    try:
        conn.execute(
            "UPDATE match_stats SET teammates_signature = ? WHERE match_id = ?",
            [signature, match_id],
        )
        return True
    except Exception as e:
        logger.warning(f"  Erreur mise à jour {match_id}: {e}")
        return False


async def backfill_player_db(
    db_path: Path,
    xuid: str | None,
    *,
    limit: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    requests_per_second: int = 3,
) -> dict:
    """Backfill teammates_signature pour une DB joueur.

    Args:
        db_path: Chemin vers stats.duckdb.
        xuid: XUID du joueur (auto-détecté si None).
        limit: Limite le nombre de matchs.
        dry_run: Mode simulation.
        force: Recalculer même si signature existe.
        requests_per_second: Rate limiting API.

    Returns:
        Dict avec résultats.
    """
    results = {
        "db_path": str(db_path),
        "xuid": xuid,
        "matches_found": 0,
        "matches_updated": 0,
        "matches_failed": 0,
        "errors": [],
    }

    if not db_path.exists():
        results["errors"].append(f"DB non trouvée: {db_path}")
        return results

    # Connexion DuckDB
    conn = duckdb.connect(str(db_path))

    try:
        # Récupérer le XUID si non fourni
        if not xuid:
            # Essayer de le récupérer depuis la DB
            try:
                result = conn.execute("SELECT DISTINCT xuid FROM xuid_aliases LIMIT 1").fetchone()
                if result and result[0]:
                    xuid = str(result[0])
            except Exception:
                pass

        if not xuid:
            results["errors"].append("XUID non trouvé")
            return results

        results["xuid"] = xuid

        # Récupérer les matchs sans signature
        matches = get_matches_without_signature(conn, limit=limit, force=force)
        results["matches_found"] = len(matches)

        if not matches:
            logger.info("  Aucun match à traiter")
            return results

        logger.info(f"  {len(matches)} matchs à traiter")

        if dry_run:
            logger.info("[DRY-RUN] Pas de mise à jour effectuée")
            return results

        # Client API (get_tokens_from_env est async)
        tokens = await get_tokens_from_env()
        if not tokens:
            results["errors"].append("Tokens API non disponibles")
            return results

        # SPNKrAPIClient n'accepte que des arguments nommés et s'utilise en context manager
        semaphore = asyncio.Semaphore(requests_per_second)
        updated = 0
        failed = 0

        async def process_one(client: SPNKrAPIClient, match_id: str, team_id: int | None):
            nonlocal updated, failed
            async with semaphore:
                success = await backfill_match(
                    client, conn, match_id, xuid, team_id, dry_run=dry_run
                )
                if success:
                    updated += 1
                else:
                    failed += 1

        async with SPNKrAPIClient(
            tokens=tokens,
            requests_per_second=requests_per_second,
        ) as client:
            tasks = [process_one(client, match_id, team_id) for match_id, team_id in matches]
            await asyncio.gather(*tasks)

        results["matches_updated"] = updated
        results["matches_failed"] = failed

        logger.info(f"  -> {updated} matchs mis à jour, {failed} échecs")

    finally:
        conn.close()

    return results


async def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Backfill teammates_signature depuis l'API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--gamertag", type=str, help="Gamertag du joueur")
    group.add_argument("--all", action="store_true", help="Traiter tous les joueurs")

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limiter le nombre de matchs traités",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode simulation (pas de mise à jour)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recalculer même si teammates_signature existe",
    )
    parser.add_argument(
        "--requests-per-second",
        type=int,
        default=3,
        help="Rate limiting API (défaut: 3)",
    )

    args = parser.parse_args()

    if args.all:
        player_infos = list_duckdb_v4_players()
        players = [(p.gamertag, p.xuid) for p in player_infos]
        logger.info(f"Joueurs trouvés: {[p[0] for p in players]}")
    else:
        gamertag = args.gamertag
        if not is_duckdb_player(gamertag):
            logger.error(f"{gamertag} n'est pas un joueur DuckDB v4")
            return 1

        db_path = get_player_duckdb_path(gamertag)
        if not db_path or not Path(db_path).exists():
            logger.error(f"DB non trouvée pour {gamertag}")
            return 1

        # Récupérer le xuid depuis la liste des joueurs DuckDB (ou None, sera lu depuis la DB)
        player_infos = [p for p in list_duckdb_v4_players() if p.gamertag == gamertag]
        xuid = player_infos[0].xuid if player_infos else None
        players = [(gamertag, xuid)]

    all_results = []
    for gamertag, xuid in players:
        logger.info(f"\n=== Traitement de {gamertag} ===")

        db_path = get_player_duckdb_path(gamertag)
        if not db_path:
            logger.warning(f"DB non trouvée pour {gamertag}")
            continue

        result = await backfill_player_db(
            Path(db_path),
            xuid,
            limit=args.limit,
            dry_run=args.dry_run,
            force=args.force,
            requests_per_second=args.requests_per_second,
        )
        result["gamertag"] = gamertag
        all_results.append(result)

    # Résumé
    logger.info("\n=== RÉSUMÉ ===")
    for r in all_results:
        gamertag = r.get("gamertag", "?")
        found = r.get("matches_found", 0)
        updated = r.get("matches_updated", 0)
        failed = r.get("matches_failed", 0)

        if r.get("errors"):
            logger.warning(f"{gamertag}: Erreurs - {r['errors']}")
        else:
            logger.info(f"{gamertag}: {found} trouvés, {updated} mis à jour, {failed} échecs")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
