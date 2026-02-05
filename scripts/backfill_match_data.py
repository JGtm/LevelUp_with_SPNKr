#!/usr/bin/env python3
"""Backfill des données manquantes pour les matchs DuckDB existants.

Ce script récupère les données manquantes (time_played, avg_life, damage, etc.)
pour les matchs déjà présents dans la base DuckDB.

Usage:
    python scripts/backfill_match_data.py --gamertag JGtm
    python scripts/backfill_match_data.py --gamertag JGtm --limit 50
    python scripts/backfill_match_data.py --gamertag JGtm --with-events --with-medals
    python scripts/backfill_match_data.py --gamertag JGtm --force-accuracy
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ajouter le répertoire racine au path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import duckdb

from src.data.sync.api_client import SPNKrAPIClient, get_tokens_from_env
from src.data.sync.transformers import (
    extract_aliases,
    transform_highlight_events,
    transform_match_stats,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

PLAYERS_DIR = REPO_ROOT / "data" / "players"


def get_matches_needing_backfill(
    conn: duckdb.DuckDBPyConnection, limit: int = 0, force_accuracy: bool = False
) -> list[str]:
    """Récupère les IDs des matchs avec données manquantes."""
    conditions = [
        "time_played_seconds IS NULL",
        "avg_life_seconds IS NULL",
        "damage_dealt IS NULL",
    ]

    if force_accuracy:
        conditions.append("accuracy IS NULL")

    query = f"""
        SELECT match_id
        FROM match_stats
        WHERE {' OR '.join(conditions)}
        ORDER BY start_time DESC
    """
    if limit > 0:
        query += f" LIMIT {limit}"

    result = conn.execute(query).fetchall()
    return [r[0] for r in result if r[0]]


def get_matches_without_events(conn: duckdb.DuckDBPyConnection, limit: int = 0) -> list[str]:
    """Récupère les IDs des matchs sans highlight_events."""
    query = """
        SELECT m.match_id
        FROM match_stats m
        LEFT JOIN highlight_events h ON m.match_id = h.match_id
        WHERE h.match_id IS NULL
        ORDER BY m.start_time DESC
    """
    if limit > 0:
        query += f" LIMIT {limit}"

    result = conn.execute(query).fetchall()
    return [r[0] for r in result if r[0]]


async def backfill_match(
    client: SPNKrAPIClient,
    conn: duckdb.DuckDBPyConnection,
    match_id: str,
    xuid: str,
    *,
    with_events: bool = False,
    with_aliases: bool = False,
    force_accuracy: bool = False,
) -> dict:
    """Backfill un match unique."""
    result = {"updated": False, "events": 0, "aliases": 0, "error": None}

    try:
        # Récupérer les stats
        stats_json = await client.get_match_stats(match_id)
        if not stats_json:
            result["error"] = "Impossible de récupérer le match"
            return result

        # Transformer
        row = transform_match_stats(stats_json, xuid)
        if not row:
            result["error"] = "Transformation échouée"
            return result

        # Construire la requête UPDATE selon si on force accuracy ou non
        if force_accuracy:
            # Forcer la mise à jour de accuracy même si elle existe déjà
            update_query = """
                UPDATE match_stats SET
                    time_played_seconds = COALESCE(time_played_seconds, ?),
                    avg_life_seconds = COALESCE(avg_life_seconds, ?),
                    damage_dealt = COALESCE(damage_dealt, ?),
                    damage_taken = COALESCE(damage_taken, ?),
                    shots_fired = COALESCE(shots_fired, ?),
                    shots_hit = COALESCE(shots_hit, ?),
                    grenade_kills = COALESCE(grenade_kills, ?),
                    melee_kills = COALESCE(melee_kills, ?),
                    power_weapon_kills = COALESCE(power_weapon_kills, ?),
                    score = COALESCE(score, ?),
                    personal_score = COALESCE(personal_score, ?),
                    my_team_score = COALESCE(my_team_score, ?),
                    enemy_team_score = COALESCE(enemy_team_score, ?),
                    accuracy = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE match_id = ?
            """
            params = (
                row.time_played_seconds,
                row.avg_life_seconds,
                row.damage_dealt,
                row.damage_taken,
                row.shots_fired,
                row.shots_hit,
                row.grenade_kills,
                row.melee_kills,
                row.power_weapon_kills,
                row.score,
                row.personal_score,
                row.my_team_score,
                row.enemy_team_score,
                row.accuracy,
                match_id,
            )
        else:
            # Comportement normal : ne mettre à jour accuracy que si NULL
            update_query = """
                UPDATE match_stats SET
                    time_played_seconds = COALESCE(time_played_seconds, ?),
                    avg_life_seconds = COALESCE(avg_life_seconds, ?),
                    damage_dealt = COALESCE(damage_dealt, ?),
                    damage_taken = COALESCE(damage_taken, ?),
                    shots_fired = COALESCE(shots_fired, ?),
                    shots_hit = COALESCE(shots_hit, ?),
                    grenade_kills = COALESCE(grenade_kills, ?),
                    melee_kills = COALESCE(melee_kills, ?),
                    power_weapon_kills = COALESCE(power_weapon_kills, ?),
                    score = COALESCE(score, ?),
                    personal_score = COALESCE(personal_score, ?),
                    my_team_score = COALESCE(my_team_score, ?),
                    enemy_team_score = COALESCE(enemy_team_score, ?),
                    accuracy = COALESCE(accuracy, ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE match_id = ?
            """
            params = (
                row.time_played_seconds,
                row.avg_life_seconds,
                row.damage_dealt,
                row.damage_taken,
                row.shots_fired,
                row.shots_hit,
                row.grenade_kills,
                row.melee_kills,
                row.power_weapon_kills,
                row.score,
                row.personal_score,
                row.my_team_score,
                row.enemy_team_score,
                row.accuracy,
                match_id,
            )

        conn.execute(update_query, params)
        result["updated"] = True

        # Highlight events
        if with_events:
            events = await client.get_highlight_events(match_id)
            if events:
                event_rows = transform_highlight_events(events, match_id)
                # Récupérer le max id actuel pour auto-increment manuel
                max_id_result = conn.execute(
                    "SELECT COALESCE(MAX(id), 0) FROM highlight_events"
                ).fetchone()
                next_id = (max_id_result[0] or 0) + 1

                for ev in event_rows:
                    try:
                        conn.execute(
                            """INSERT INTO highlight_events
                               (id, match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                next_id,
                                ev.match_id,
                                ev.event_type,
                                ev.time_ms,
                                ev.xuid,
                                ev.gamertag,
                                ev.type_hint,
                                ev.raw_json,
                            ),
                        )
                        next_id += 1
                        result["events"] = result.get("events", 0) + 1
                    except Exception:
                        # Ignorer les doublons
                        pass

        # Aliases
        if with_aliases:
            alias_rows = extract_aliases(stats_json)
            for alias in alias_rows:
                conn.execute(
                    """INSERT OR REPLACE INTO xuid_aliases
                       (xuid, gamertag, last_seen)
                       VALUES (?, ?, CURRENT_TIMESTAMP)""",
                    (alias.xuid, alias.gamertag),
                )
            result["aliases"] = len(alias_rows)

    except Exception as e:
        result["error"] = str(e)

    return result


async def main_async(args: argparse.Namespace) -> int:
    """Point d'entrée async."""
    gamertag = args.gamertag
    db_path = PLAYERS_DIR / gamertag / "stats.duckdb"

    if not db_path.exists():
        logger.error(f"Base non trouvée: {db_path}")
        return 1

    # Connexion DuckDB
    conn = duckdb.connect(str(db_path), read_only=False)

    # Récupérer le XUID
    try:
        xuid_result = conn.execute(
            "SELECT xuid FROM xuid_aliases ORDER BY last_seen DESC LIMIT 1"
        ).fetchone()
        if xuid_result:
            xuid = str(xuid_result[0])
        else:
            # Essayer de le déduire depuis match_stats
            logger.warning("XUID non trouvé dans xuid_aliases, utilisation du paramètre")
            xuid = args.xuid or ""
    except Exception:
        xuid = args.xuid or ""

    if not xuid:
        logger.error("XUID requis (--xuid) car non trouvé dans la base")
        return 1

    # Identifier les matchs à backfill
    if args.with_events:
        match_ids = get_matches_without_events(conn, args.limit)
        logger.info(f"{len(match_ids)} matchs sans highlight_events")
    else:
        match_ids = get_matches_needing_backfill(
            conn, args.limit, force_accuracy=args.force_accuracy
        )
        if args.force_accuracy:
            logger.info(f"{len(match_ids)} matchs avec données manquantes (incluant accuracy NULL)")
        else:
            logger.info(f"{len(match_ids)} matchs avec données manquantes")

    if not match_ids:
        logger.info("Rien à backfill!")
        return 0

    # Récupérer les tokens
    try:
        tokens = await get_tokens_from_env()
    except Exception as e:
        logger.error(f"Erreur tokens: {e}")
        return 1

    # Backfill
    updated = 0
    errors = 0
    total_events = 0
    total_aliases = 0

    async with SPNKrAPIClient(tokens=tokens, requests_per_second=args.rps) as client:
        for i, match_id in enumerate(match_ids):
            result = await backfill_match(
                client,
                conn,
                match_id,
                xuid,
                with_events=args.with_events,
                with_aliases=args.with_aliases,
                force_accuracy=args.force_accuracy,
            )

            if result["updated"]:
                updated += 1
                total_events += result.get("events", 0)
                total_aliases += result.get("aliases", 0)
            if result.get("error"):
                errors += 1
                logger.warning(f"Erreur {match_id}: {result['error']}")

            # Commit périodique
            if (i + 1) % 10 == 0:
                conn.commit()
                logger.info(f"Progression: {i + 1}/{len(match_ids)} ({updated} mis à jour)")

    # Commit final
    conn.commit()
    conn.close()

    logger.info("=" * 60)
    logger.info("BACKFILL TERMINÉ")
    logger.info(f"  Matchs traités: {len(match_ids)}")
    logger.info(f"  Mis à jour: {updated}")
    logger.info(f"  Erreurs: {errors}")
    if args.force_accuracy:
        logger.info("  Mode: Force accuracy activé")
    if args.with_events:
        logger.info(f"  Events ajoutés: {total_events}")
    if args.with_aliases:
        logger.info(f"  Aliases ajoutés: {total_aliases}")

    return 0 if errors == 0 else 1


def main() -> int:
    """Point d'entrée."""
    parser = argparse.ArgumentParser(description="Backfill des données matchs DuckDB")
    parser.add_argument("--gamertag", required=True, help="Gamertag du joueur")
    parser.add_argument("--xuid", help="XUID du joueur (si non trouvé dans la base)")
    parser.add_argument("--limit", type=int, default=0, help="Limite de matchs (0=tous)")
    parser.add_argument("--rps", type=int, default=5, help="Requêtes par seconde")
    parser.add_argument("--with-events", action="store_true", help="Récupérer highlight_events")
    parser.add_argument("--with-aliases", action="store_true", help="Mettre à jour xuid_aliases")
    parser.add_argument(
        "--force-accuracy",
        action="store_true",
        help="Forcer la récupération de accuracy même si elle existe déjà (inclut les matchs avec accuracy NULL)",
    )

    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
