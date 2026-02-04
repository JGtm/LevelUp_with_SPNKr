#!/usr/bin/env python3
"""Script de backfill pour remplir les données manquantes.

Ce script identifie les matchs existants qui ont des données manquantes
(medals, highlight_events, skill stats, personal_scores) et les remplit
en re-téléchargeant les données nécessaires depuis l'API SPNKr.

Usage:
    # Backfill toutes les données pour un joueur
    python scripts/backfill_data.py --player JGtm

    # Backfill uniquement les médailles
    python scripts/backfill_data.py --player JGtm --medals

    # Backfill pour tous les joueurs
    python scripts/backfill_data.py --all

    # Mode dry-run (liste seulement)
    python scripts/backfill_data.py --player JGtm --dry-run

    # Limiter le nombre de matchs
    python scripts/backfill_data.py --player JGtm --max-matches 100
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

# Ajouter le répertoire parent au path pour les imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.data.sync.api_client import SPNKrAPIClient, get_tokens_from_env
from src.data.sync.transformers import (
    extract_aliases,
    extract_medals,
    extract_personal_score_awards,
    extract_xuids_from_match,
    transform_highlight_events,
    transform_personal_score_awards,
    transform_skill_stats,
)
from src.db.parsers import resolve_xuid_from_db
from src.ui.multiplayer import list_duckdb_v4_players
from src.ui.sync import get_player_duckdb_path, is_duckdb_player

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _insert_medal_rows(conn, rows: list) -> int:
    """Insère les médailles dans la table medals_earned."""
    if not rows:
        return 0

    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO medals_earned
                   (match_id, medal_name_id, count)
                   VALUES (?, ?, ?)""",
                (row.match_id, row.medal_name_id, row.count),
            )
            inserted += 1
        except Exception as e:
            logger.warning(
                f"Erreur insertion médaille {row.medal_name_id} pour {row.match_id}: {e}"
            )

    return inserted


def _insert_event_rows(conn, rows: list) -> int:
    """Insère les highlight events."""
    if not rows:
        return 0

    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT INTO highlight_events
                   (match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    row.match_id,
                    row.event_type,
                    row.time_ms,
                    row.xuid,
                    row.gamertag,
                    row.type_hint,
                    row.raw_json,
                ),
            )
            inserted += 1
        except Exception as e:
            logger.warning(f"Erreur insertion event pour {row.match_id}: {e}")

    return inserted


def _insert_skill_row(conn, row: Any, xuid: str) -> int:
    """Insère les stats skill/MMR."""
    if not row:
        return 0

    try:
        conn.execute(
            """INSERT OR REPLACE INTO player_match_stats
               (match_id, xuid, team_id, team_mmr, enemy_mmr,
                kills_expected, kills_stddev,
                deaths_expected, deaths_stddev,
                assists_expected, assists_stddev)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row.match_id,
                xuid,
                row.team_id,
                row.team_mmr,
                row.enemy_mmr,
                row.kills_expected,
                row.kills_stddev,
                row.deaths_expected,
                row.deaths_stddev,
                row.assists_expected,
                row.assists_stddev,
            ),
        )
        return 1
    except Exception as e:
        logger.warning(f"Erreur insertion skill pour {row.match_id}: {e}")
        return 0


def _insert_personal_score_rows(conn, rows: list) -> int:
    """Insère les personal score awards."""
    if not rows:
        return 0

    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT INTO personal_score_awards
                   (match_id, xuid, award_name, award_category,
                    award_count, award_score, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    row.match_id,
                    row.xuid,
                    row.award_name,
                    row.award_category,
                    row.award_count,
                    row.award_score,
                    row.created_at.isoformat() if row.created_at else None,
                ),
            )
            inserted += 1
        except Exception as e:
            logger.warning(f"Erreur insertion personal_score pour {row.match_id}: {e}")

    return inserted


def _insert_alias_rows(conn, rows: list) -> int:
    """Insère les aliases XUID."""
    if not rows:
        return 0

    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO xuid_aliases
                   (xuid, gamertag, last_seen, source, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    row.xuid,
                    row.gamertag,
                    row.last_seen.isoformat() if row.last_seen else None,
                    row.source,
                    row.updated_at.isoformat() if row.updated_at else None,
                ),
            )
            inserted += 1
        except Exception as e:
            logger.warning(f"Erreur insertion alias {row.xuid}: {e}")

    return inserted


def _find_matches_missing_data(
    conn,
    xuid: str,
    *,
    medals: bool = False,
    events: bool = False,
    skill: bool = False,
    personal_scores: bool = False,
    max_matches: int | None = None,
) -> list[str]:
    """Trouve les matchs avec des données manquantes."""
    conditions = []
    params = []

    if medals:
        conditions.append("""
            ms.match_id NOT IN (
                SELECT DISTINCT match_id FROM medals_earned
            )
        """)

    if events:
        conditions.append("""
            ms.match_id NOT IN (
                SELECT DISTINCT match_id FROM highlight_events
            )
        """)

    if skill:
        conditions.append("""
            ms.match_id NOT IN (
                SELECT DISTINCT match_id FROM player_match_stats WHERE xuid = ?
            )
        """)
        params.append(xuid)

    if personal_scores:
        conditions.append("""
            ms.match_id NOT IN (
                SELECT DISTINCT match_id FROM personal_score_awards WHERE xuid = ?
            )
        """)
        params.append(xuid)

    if not conditions:
        return []

    where_clause = " OR ".join(conditions)
    query = f"""
        SELECT DISTINCT ms.match_id
        FROM match_stats ms
        WHERE ({where_clause})
        ORDER BY ms.start_time DESC
    """

    if max_matches:
        query += f" LIMIT {max_matches}"

    result = conn.execute(query, params).fetchall() if params else conn.execute(query).fetchall()

    return [row[0] for row in result]


async def backfill_player_data(
    gamertag: str,
    *,
    dry_run: bool = False,
    max_matches: int | None = None,
    requests_per_second: int = 5,
    medals: bool = False,
    events: bool = False,
    skill: bool = False,
    personal_scores: bool = False,
    aliases: bool = False,
    all_data: bool = False,
) -> dict[str, int]:
    """Remplit les données manquantes pour un joueur.

    Args:
        gamertag: Gamertag du joueur.
        dry_run: Si True, ne fait que lister les matchs sans données.
        max_matches: Nombre maximum de matchs à traiter (None = tous).
        requests_per_second: Rate limiting API.
        medals: Backfill les médailles.
        events: Backfill les highlight events.
        skill: Backfill les stats skill/MMR.
        personal_scores: Backfill les personal score awards.
        aliases: Mettre à jour les aliases.
        all_data: Backfill toutes les données.

    Returns:
        Dict avec les statistiques.
    """
    # Si all_data, activer toutes les options
    if all_data:
        medals = True
        events = True
        skill = True
        personal_scores = True
        aliases = True

    # Vérifier qu'au moins une option est activée
    if not any([medals, events, skill, personal_scores, aliases]):
        logger.warning(
            "Aucune option de backfill activée. Utilisez --all ou spécifiez des options."
        )
        return {
            "matches_checked": 0,
            "matches_missing_data": 0,
            "medals_inserted": 0,
            "events_inserted": 0,
            "skill_inserted": 0,
            "personal_scores_inserted": 0,
            "aliases_inserted": 0,
        }

    # Vérifier que c'est un joueur DuckDB v4
    if not is_duckdb_player(gamertag):
        logger.error(
            f"{gamertag} n'a pas de DB DuckDB v4. Ce script ne fonctionne que pour DuckDB v4."
        )
        return {
            "matches_checked": 0,
            "matches_missing_data": 0,
            "medals_inserted": 0,
            "events_inserted": 0,
            "skill_inserted": 0,
            "personal_scores_inserted": 0,
            "aliases_inserted": 0,
        }

    # Obtenir le chemin de la DB
    db_path = get_player_duckdb_path(gamertag)
    if not db_path or not db_path.exists():
        logger.error(f"DB DuckDB introuvable pour {gamertag}")
        return {
            "matches_checked": 0,
            "matches_missing_data": 0,
            "medals_inserted": 0,
            "events_inserted": 0,
            "skill_inserted": 0,
            "personal_scores_inserted": 0,
            "aliases_inserted": 0,
        }

    # Obtenir le XUID depuis la DB
    import duckdb

    # Résoudre le XUID depuis le gamertag
    xuid = resolve_xuid_from_db(str(db_path), gamertag)

    if not xuid:
        logger.warning(f"XUID introuvable dans xuid_aliases pour {gamertag}")
        logger.info("Tentative d'extraction depuis les matchs existants...")

        # Fallback : essayer d'extraire depuis highlight_events
        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            # Essayer depuis highlight_events (contient gamertag + xuid)
            result = conn.execute(
                """
                SELECT DISTINCT xuid
                FROM highlight_events
                WHERE LOWER(gamertag) = LOWER(?)
                  AND xuid IS NOT NULL
                  AND xuid != ''
                LIMIT 1
                """,
                [gamertag],
            ).fetchone()

            if result and result[0]:
                xuid = str(result[0])
                logger.info(f"✅ XUID trouvé depuis highlight_events: {xuid}")
            else:
                logger.error(f"❌ Impossible de résoudre le XUID pour {gamertag}")
                logger.error("")
                logger.error(
                    "La table xuid_aliases est vide et aucun match avec highlight_events trouvé."
                )
                logger.error("")
                logger.error(
                    "💡 Solution: Faites une synchronisation complète pour remplir xuid_aliases:"
                )
                logger.error(f"   python scripts/sync.py --gamertag {gamertag} --delta")
                logger.error("")
                return {
                    "matches_checked": 0,
                    "matches_missing_data": 0,
                    "medals_inserted": 0,
                    "events_inserted": 0,
                    "skill_inserted": 0,
                    "personal_scores_inserted": 0,
                    "aliases_inserted": 0,
                }
        finally:
            conn.close()
    else:
        logger.info(f"✅ XUID résolu depuis xuid_aliases: {xuid}")

    # Ouvrir la connexion en écriture pour les insertions
    conn = duckdb.connect(str(db_path), read_only=False)

    try:
        # Trouver les matchs avec données manquantes
        match_ids = _find_matches_missing_data(
            conn,
            xuid,
            medals=medals,
            events=events,
            skill=skill,
            personal_scores=personal_scores,
            max_matches=max_matches,
        )

        logger.info(f"Matchs trouvés avec données manquantes: {len(match_ids)}")

        if dry_run:
            logger.info("Mode dry-run: aucun traitement effectué")
            return {
                "matches_checked": len(match_ids),
                "matches_missing_data": len(match_ids),
                "medals_inserted": 0,
                "events_inserted": 0,
                "skill_inserted": 0,
                "personal_scores_inserted": 0,
                "aliases_inserted": 0,
            }

        if not match_ids:
            logger.info("Tous les matchs ont déjà toutes les données demandées")
            return {
                "matches_checked": 0,
                "matches_missing_data": 0,
                "medals_inserted": 0,
                "events_inserted": 0,
                "skill_inserted": 0,
                "personal_scores_inserted": 0,
                "aliases_inserted": 0,
            }

        # Récupérer les tokens
        tokens = get_tokens_from_env()
        if not tokens:
            logger.error("Tokens SPNKr non disponibles")
            return {
                "matches_checked": 0,
                "matches_missing_data": 0,
                "medals_inserted": 0,
                "events_inserted": 0,
                "skill_inserted": 0,
                "personal_scores_inserted": 0,
                "aliases_inserted": 0,
            }

        # Traiter les matchs
        total_medals = 0
        total_events = 0
        total_skill = 0
        total_personal_scores = 0
        total_aliases = 0

        async with SPNKrAPIClient(
            tokens=tokens,
            requests_per_second=requests_per_second,
        ) as client:
            for i, match_id in enumerate(match_ids, 1):
                try:
                    logger.info(f"[{i}/{len(match_ids)}] Traitement {match_id}...")

                    # Récupérer les stats du match
                    stats_json = await client.get_match_stats(match_id)
                    if not stats_json:
                        logger.warning(f"Impossible de récupérer {match_id}")
                        continue

                    # Extraire les XUIDs pour skill
                    xuids = extract_xuids_from_match(stats_json)

                    # Récupérer skill et events si nécessaire
                    skill_json = None
                    highlight_events = []

                    if skill and xuids:
                        skill_json = await client.get_skill_stats(match_id, xuids)

                    if events:
                        highlight_events = await client.get_highlight_events(match_id)

                    # Transformer les données
                    inserted_this_match = {
                        "medals": 0,
                        "events": 0,
                        "skill": 0,
                        "personal_scores": 0,
                        "aliases": 0,
                    }

                    # Médailles
                    if medals:
                        medal_rows = extract_medals(stats_json, xuid)
                        if medal_rows:
                            inserted_this_match["medals"] = _insert_medal_rows(conn, medal_rows)
                            total_medals += inserted_this_match["medals"]

                    # Events
                    if events and highlight_events:
                        event_rows = transform_highlight_events(highlight_events, match_id)
                        if event_rows:
                            inserted_this_match["events"] = _insert_event_rows(conn, event_rows)
                            total_events += inserted_this_match["events"]

                    # Skill
                    if skill and skill_json:
                        skill_row = transform_skill_stats(skill_json, match_id, xuid)
                        if skill_row:
                            inserted_this_match["skill"] = _insert_skill_row(conn, skill_row, xuid)
                            total_skill += inserted_this_match["skill"]

                    # Personal scores
                    if personal_scores:
                        personal_scores_data = extract_personal_score_awards(stats_json, xuid)
                        if personal_scores_data:
                            personal_score_rows = transform_personal_score_awards(
                                match_id, xuid, personal_scores_data
                            )
                            if personal_score_rows:
                                inserted_this_match["personal_scores"] = (
                                    _insert_personal_score_rows(conn, personal_score_rows)
                                )
                                total_personal_scores += inserted_this_match["personal_scores"]

                    # Aliases
                    if aliases:
                        alias_rows = extract_aliases(stats_json)
                        if alias_rows:
                            inserted_this_match["aliases"] = _insert_alias_rows(conn, alias_rows)
                            total_aliases += inserted_this_match["aliases"]

                    # Commit après chaque match
                    conn.commit()

                    # Log des insertions
                    parts = []
                    if inserted_this_match["medals"] > 0:
                        parts.append(f"{inserted_this_match['medals']} médaille(s)")
                    if inserted_this_match["events"] > 0:
                        parts.append(f"{inserted_this_match['events']} event(s)")
                    if inserted_this_match["skill"] > 0:
                        parts.append("skill")
                    if inserted_this_match["personal_scores"] > 0:
                        parts.append(f"{inserted_this_match['personal_scores']} personal_score(s)")
                    if inserted_this_match["aliases"] > 0:
                        parts.append(f"{inserted_this_match['aliases']} alias(es)")

                    if parts:
                        logger.info(f"  ✅ {', '.join(parts)} inséré(s)")
                    else:
                        logger.info("  ⚠️  Aucune donnée insérée")

                except Exception as e:
                    logger.error(f"Erreur traitement {match_id}: {e}")
                    import traceback

                    traceback.print_exc()
                    continue

        logger.info(f"Backfill terminé pour {gamertag}")

        return {
            "matches_checked": len(match_ids),
            "matches_missing_data": len(match_ids),
            "medals_inserted": total_medals,
            "events_inserted": total_events,
            "skill_inserted": total_skill,
            "personal_scores_inserted": total_personal_scores,
            "aliases_inserted": total_aliases,
        }

    finally:
        conn.close()


async def backfill_all_players(
    *,
    dry_run: bool = False,
    max_matches: int | None = None,
    requests_per_second: int = 5,
    medals: bool = False,
    events: bool = False,
    skill: bool = False,
    personal_scores: bool = False,
    aliases: bool = False,
    all_data: bool = False,
) -> dict[str, Any]:
    """Backfill pour tous les joueurs DuckDB v4."""
    players = list_duckdb_v4_players()

    if not players:
        logger.warning("Aucun joueur DuckDB v4 trouvé")
        return {"players_processed": 0, "total_results": {}}

    logger.info(f"Trouvé {len(players)} joueur(s) DuckDB v4")

    total_results = {
        "matches_checked": 0,
        "matches_missing_data": 0,
        "medals_inserted": 0,
        "events_inserted": 0,
        "skill_inserted": 0,
        "personal_scores_inserted": 0,
        "aliases_inserted": 0,
    }

    for i, player_info in enumerate(players, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"[{i}/{len(players)}] Traitement de {player_info.gamertag}")
        logger.info(f"{'='*60}")

        result = await backfill_player_data(
            player_info.gamertag,
            dry_run=dry_run,
            max_matches=max_matches,
            requests_per_second=requests_per_second,
            medals=medals,
            events=events,
            skill=skill,
            personal_scores=personal_scores,
            aliases=aliases,
            all_data=all_data,
        )

        # Agréger les résultats
        for key in total_results:
            total_results[key] += result.get(key, 0)

    return {
        "players_processed": len(players),
        "total_results": total_results,
    }


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Backfill des données manquantes pour DuckDB v4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--player",
        type=str,
        default=None,
        help="Gamertag du joueur (ignoré si --all)",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Traiter tous les joueurs DuckDB v4",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode dry-run (ne fait que lister les matchs sans données)",
    )

    parser.add_argument(
        "--max-matches",
        type=int,
        default=None,
        help="Nombre maximum de matchs à traiter par joueur (défaut: tous)",
    )

    parser.add_argument(
        "--requests-per-second",
        type=int,
        default=5,
        help="Rate limiting API (défaut: 5 req/s)",
    )

    # Options de données à backfill
    parser.add_argument(
        "--medals",
        action="store_true",
        help="Backfill les médailles",
    )

    parser.add_argument(
        "--events",
        action="store_true",
        help="Backfill les highlight events",
    )

    parser.add_argument(
        "--skill",
        action="store_true",
        help="Backfill les stats skill/MMR",
    )

    parser.add_argument(
        "--personal-scores",
        action="store_true",
        help="Backfill les personal score awards",
    )

    parser.add_argument(
        "--aliases",
        action="store_true",
        help="Mettre à jour les aliases XUID",
    )

    parser.add_argument(
        "--all-data",
        action="store_true",
        help="Backfill toutes les données (équivalent à --medals --events --skill --personal-scores --aliases)",
    )

    args = parser.parse_args()

    # Validation
    if not args.all and not args.player:
        parser.error("--player ou --all est requis")

    # Exécuter le backfill
    try:
        if args.all:
            result = asyncio.run(
                backfill_all_players(
                    dry_run=args.dry_run,
                    max_matches=args.max_matches,
                    requests_per_second=args.requests_per_second,
                    medals=args.medals,
                    events=args.events,
                    skill=args.skill,
                    personal_scores=args.personal_scores,
                    aliases=args.aliases,
                    all_data=args.all_data,
                )
            )

            logger.info("\n" + "=" * 60)
            logger.info("=== RÉSUMÉ GLOBAL ===")
            logger.info("=" * 60)
            logger.info(f"Joueurs traités: {result['players_processed']}")
            totals = result["total_results"]
            logger.info(f"Matchs vérifiés: {totals['matches_checked']}")
            logger.info(f"Matchs avec données manquantes: {totals['matches_missing_data']}")
            logger.info(f"Médailles insérées: {totals['medals_inserted']}")
            logger.info(f"Events insérés: {totals['events_inserted']}")
            logger.info(f"Skill inséré: {totals['skill_inserted']}")
            logger.info(f"Personal scores insérés: {totals['personal_scores_inserted']}")
            logger.info(f"Aliases insérés: {totals['aliases_inserted']}")
        else:
            result = asyncio.run(
                backfill_player_data(
                    args.player,
                    dry_run=args.dry_run,
                    max_matches=args.max_matches,
                    requests_per_second=args.requests_per_second,
                    medals=args.medals,
                    events=args.events,
                    skill=args.skill,
                    personal_scores=args.personal_scores,
                    aliases=args.aliases,
                    all_data=args.all_data,
                )
            )

            logger.info("\n=== Résumé ===")
            logger.info(f"Matchs vérifiés: {result['matches_checked']}")
            logger.info(f"Matchs avec données manquantes: {result['matches_missing_data']}")
            logger.info(f"Médailles insérées: {result['medals_inserted']}")
            logger.info(f"Events insérés: {result['events_inserted']}")
            logger.info(f"Skill inséré: {result['skill_inserted']}")
            logger.info(f"Personal scores insérés: {result['personal_scores_inserted']}")
            logger.info(f"Aliases insérés: {result['aliases_inserted']}")

        return 0

    except KeyboardInterrupt:
        logger.info("\nInterrompu par l'utilisateur")
        return 1
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
