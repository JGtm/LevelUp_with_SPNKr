#!/usr/bin/env python3
"""
Script de backfill des métadonnées dans match_stats.

Ce script met à jour les colonnes playlist_name, map_name, pair_name, game_variant_name
dans match_stats en utilisant :
1. metadata.duckdb (si disponible)
2. Discovery UGC API (si metadata.duckdb n'a pas l'asset)

Usage:
    python scripts/backfill_metadata.py --player JGtm
    python scripts/backfill_metadata.py --all-players
    python scripts/backfill_metadata.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import duckdb
except ImportError:
    print("ERREUR: DuckDB non installé. Exécutez: pip install duckdb")
    sys.exit(1)

from src.data.sync.api_client import (
    SPNKrAPIClient,
    enrich_match_info_with_assets,
    get_tokens_from_env,
)
from src.data.sync.metadata_resolver import MetadataResolver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration des chemins
DATA_DIR = Path(__file__).parent.parent / "data"
WAREHOUSE_DIR = DATA_DIR / "warehouse"
METADATA_DB_PATH = WAREHOUSE_DIR / "metadata.duckdb"
PLAYERS_DIR = DATA_DIR / "players"


def get_match_ids_with_null_metadata(
    conn: duckdb.DuckDBPyConnection,
) -> list[tuple[str, str, str, str, str]]:
    """Récupère les match_ids avec métadonnées NULL.

    Returns:
        Liste de tuples (match_id, playlist_id, map_id, pair_id, game_variant_id).
    """
    try:
        result = conn.execute(
            """
            SELECT match_id, playlist_id, map_id, pair_id, game_variant_id
            FROM match_stats
            WHERE playlist_name IS NULL OR map_name IS NULL OR pair_name IS NULL OR game_variant_name IS NULL
            ORDER BY start_time DESC
            """
        ).fetchall()
        return [(row[0], row[1] or "", row[2] or "", row[3] or "", row[4] or "") for row in result]
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des match_ids: {e}")
        return []


async def backfill_match_metadata(
    conn: duckdb.DuckDBPyConnection,
    client: SPNKrAPIClient,
    metadata_resolver: MetadataResolver | None,
    match_ids: list[str],
    dry_run: bool = False,
) -> dict[str, int]:
    """Backfill les métadonnées pour une liste de matchs.

    Args:
        conn: Connexion DuckDB.
        client: Client API SPNKr.
        metadata_resolver: Resolver pour metadata.duckdb (peut être None).
        match_ids: Liste des match_ids à traiter.
        dry_run: Si True, ne fait que simuler.

    Returns:
        Dict avec les statistiques (updated, skipped, errors).
    """
    results: dict[str, int] = {
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    if not match_ids:
        return results

    logger.info(f"Traitement de {len(match_ids)} matchs...")

    # Récupérer les match_ids avec leurs asset IDs
    match_assets = get_match_ids_with_null_metadata(conn)

    # Filtrer pour ne garder que ceux dans match_ids si spécifié
    if match_ids:
        match_ids_set = set(match_ids)
        match_assets = [
            (mid, pl, m, p, gv) for mid, pl, m, p, gv in match_assets if mid in match_ids_set
        ]

    for match_id, playlist_id, map_id, pair_id, game_variant_id in match_assets:
        try:
            # Récupérer le JSON du match depuis l'API
            stats_json = await client.get_match_stats(match_id)
            if not stats_json:
                logger.debug(f"Match {match_id} non trouvé dans l'API")
                results["skipped"] += 1
                continue

            # Enrichir avec Discovery UGC
            await enrich_match_info_with_assets(client, stats_json)

            match_info = stats_json.get("MatchInfo", {})
            if not isinstance(match_info, dict):
                results["skipped"] += 1
                continue

            # Extraire les noms depuis MatchInfo (enrichi par enrich_match_info_with_assets)
            playlist_name = None
            map_name = None
            pair_name = None
            game_variant_name = None

            # Playlist
            playlist_obj = match_info.get("Playlist", {})
            if isinstance(playlist_obj, dict):
                playlist_name = playlist_obj.get("PublicName")
                if not playlist_name and playlist_id and metadata_resolver:
                    playlist_name = metadata_resolver.resolve("playlist", playlist_id)

            # Map
            map_obj = match_info.get("MapVariant", {})
            if isinstance(map_obj, dict):
                map_name = map_obj.get("PublicName")
                if not map_name and map_id and metadata_resolver:
                    map_name = metadata_resolver.resolve("map", map_id)

            # Pair
            pair_obj = match_info.get("PlaylistMapModePair", {})
            if isinstance(pair_obj, dict):
                pair_name = pair_obj.get("PublicName")
                if not pair_name and pair_id and metadata_resolver:
                    pair_name = metadata_resolver.resolve("pair", pair_id)

            # Game variant
            variant_obj = match_info.get("UgcGameVariant", {})
            if isinstance(variant_obj, dict):
                game_variant_name = variant_obj.get("PublicName")
                if not game_variant_name and game_variant_id and metadata_resolver:
                    game_variant_name = metadata_resolver.resolve("game_variant", game_variant_id)

            # Fallback sur les IDs si toujours NULL
            playlist_name = playlist_name or playlist_id
            map_name = map_name or map_id
            pair_name = pair_name or pair_id
            game_variant_name = game_variant_name or game_variant_id

            if not dry_run:
                # Mettre à jour dans la DB
                conn.execute(
                    """
                    UPDATE match_stats
                    SET playlist_name = ?,
                        map_name = ?,
                        pair_name = ?,
                        game_variant_name = ?
                    WHERE match_id = ?
                    """,
                    [
                        playlist_name,
                        map_name,
                        pair_name,
                        game_variant_name,
                        match_id,
                    ],
                )

            results["updated"] += 1
            if results["updated"] % 10 == 0:
                logger.info(f"  {results['updated']} matchs mis à jour...")

        except Exception as e:
            logger.warning(f"Erreur traitement match {match_id}: {e}")
            results["errors"] += 1

        # Petite pause pour ne pas surcharger l'API
        await asyncio.sleep(0.1)

    return results


async def backfill_player_metadata(
    gamertag: str,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """Backfill les métadonnées pour un joueur.

    Args:
        gamertag: Gamertag du joueur.
        dry_run: Si True, ne fait que simuler.
        limit: Limite du nombre de matchs à traiter (None = tous).

    Returns:
        Dict avec les résultats.
    """
    player_dir = PLAYERS_DIR / gamertag
    stats_db = player_dir / "stats.duckdb"

    if not stats_db.exists():
        logger.error(f"Base de données non trouvée: {stats_db}")
        return {"success": False, "error": "DB not found"}

    logger.info(f"Traitement de {gamertag}...")

    # Ouvrir la connexion
    conn = duckdb.connect(str(stats_db), read_only=False)

    # Créer le metadata resolver
    metadata_resolver = None
    if METADATA_DB_PATH.exists():
        metadata_resolver = MetadataResolver(METADATA_DB_PATH)
        logger.info(f"Metadata resolver créé depuis {METADATA_DB_PATH}")
    else:
        logger.warning(f"metadata.duckdb non trouvé: {METADATA_DB_PATH}")

    # Vérifier les tokens API
    tokens = get_tokens_from_env()
    if not tokens:
        logger.error("Tokens API non trouvés. Configurez HALO_SPARTAN_TOKEN et HALO_XBL_TOKEN")
        conn.close()
        return {"success": False, "error": "No API tokens"}

    client = SPNKrAPIClient(tokens)

    # Récupérer les match_ids à traiter
    match_assets = get_match_ids_with_null_metadata(conn)
    if limit:
        match_assets = match_assets[:limit]

    match_ids = [mid for mid, _, _, _, _ in match_assets]

    # Backfill
    results = await backfill_match_metadata(conn, client, metadata_resolver, match_ids, dry_run)

    if not dry_run:
        conn.commit()

    conn.close()

    return {
        "success": True,
        "gamertag": gamertag,
        **results,
    }


async def backfill_all_players_metadata(
    dry_run: bool = False,
    limit_per_player: int | None = None,
) -> dict[str, Any]:
    """Backfill les métadonnées pour tous les joueurs.

    Args:
        dry_run: Si True, ne fait que simuler.
        limit_per_player: Limite par joueur (None = tous).

    Returns:
        Dict avec les résultats globaux.
    """
    if not PLAYERS_DIR.exists():
        logger.error(f"Répertoire players non trouvé: {PLAYERS_DIR}")
        return {"success": False, "error": "Players dir not found"}

    player_dirs = [d for d in PLAYERS_DIR.iterdir() if d.is_dir()]
    if not player_dirs:
        logger.warning("Aucun joueur trouvé")
        return {"success": False, "error": "No players found"}

    logger.info(f"Traitement de {len(player_dirs)} joueurs...")

    all_results: dict[str, Any] = {
        "success": True,
        "players": {},
        "total_updated": 0,
        "total_skipped": 0,
        "total_errors": 0,
    }

    for player_dir in player_dirs:
        gamertag = player_dir.name
        result = await backfill_player_metadata(gamertag, dry_run=dry_run, limit=limit_per_player)

        if result.get("success"):
            all_results["players"][gamertag] = result
            all_results["total_updated"] += result.get("updated", 0)
            all_results["total_skipped"] += result.get("skipped", 0)
            all_results["total_errors"] += result.get("errors", 0)
        else:
            all_results["players"][gamertag] = result

    return all_results


async def main_async(
    gamertag: str | None = None,
    all_players: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
    verbose: bool = False,
) -> int:
    """Point d'entrée principal async."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 50)
    logger.info("Backfill métadonnées match_stats")
    logger.info("=" * 50)

    if all_players:
        results = await backfill_all_players_metadata(dry_run=dry_run, limit_per_player=limit)
    elif gamertag:
        results = await backfill_player_metadata(gamertag, dry_run=dry_run, limit=limit)
    else:
        logger.error("Spécifiez --player ou --all-players")
        return 1

    # Afficher le résumé
    logger.info("\n" + "=" * 50)
    logger.info("RÉSUMÉ")
    logger.info("=" * 50)

    if all_players:
        logger.info(f"Joueurs traités: {len(results.get('players', {}))}")
        logger.info(f"Total mis à jour: {results.get('total_updated', 0)}")
        logger.info(f"Total ignorés: {results.get('total_skipped', 0)}")
        logger.info(f"Total erreurs: {results.get('total_errors', 0)}")
    else:
        logger.info(f"Joueur: {results.get('gamertag', 'N/A')}")
        logger.info(f"Mis à jour: {results.get('updated', 0)}")
        logger.info(f"Ignorés: {results.get('skipped', 0)}")
        logger.info(f"Erreurs: {results.get('errors', 0)}")

    return 0 if results.get("success") else 1


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Backfill métadonnées dans match_stats",
    )
    parser.add_argument(
        "--player",
        help="Gamertag du joueur à traiter",
    )
    parser.add_argument(
        "--all-players",
        action="store_true",
        help="Traiter tous les joueurs",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limite du nombre de matchs à traiter",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule sans écrire",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Affiche plus de détails",
    )

    args = parser.parse_args()

    if not args.player and not args.all_players:
        parser.error("Spécifiez --player ou --all-players")

    return asyncio.run(
        main_async(
            gamertag=args.player,
            all_players=args.all_players,
            dry_run=args.dry_run,
            limit=args.limit,
            verbose=args.verbose,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
