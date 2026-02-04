#!/usr/bin/env python3
"""Script de backfill pour remplir les médailles manquantes.

Ce script identifie les matchs existants qui n'ont pas de médailles dans
la table `medals_earned` et les remplit en re-téléchargeant les données
nécessaires depuis l'API SPNKr.

Usage:
    python scripts/backfill_medals.py --player JGtm
    python scripts/backfill_medals.py --player JGtm --dry-run
    python scripts/backfill_medals.py --player JGtm --max-matches 100
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.data.sync.api_client import SPNKrAPIClient, get_tokens_from_env
from src.data.sync.transformers import extract_medals
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
                (
                    row.match_id,
                    row.medal_name_id,
                    row.count,
                ),
            )
            inserted += 1
        except Exception as e:
            logger.warning(
                f"Erreur insertion médaille {row.medal_name_id} pour {row.match_id}: {e}"
            )

    return inserted


async def backfill_medals(
    gamertag: str,
    *,
    dry_run: bool = False,
    max_matches: int | None = None,
    requests_per_second: int = 5,
) -> dict[str, int]:
    """Remplit les médailles manquantes pour un joueur.

    Args:
        gamertag: Gamertag du joueur.
        dry_run: Si True, ne fait que lister les matchs sans médailles.
        max_matches: Nombre maximum de matchs à traiter (None = tous).
        requests_per_second: Rate limiting API.

    Returns:
        Dict avec les statistiques (matches_checked, matches_missing_medals, medals_inserted).
    """
    # Vérifier que c'est un joueur DuckDB v4
    if not is_duckdb_player(gamertag):
        logger.error(
            f"{gamertag} n'a pas de DB DuckDB v4. Ce script ne fonctionne que pour DuckDB v4."
        )
        return {"matches_checked": 0, "matches_missing_medals": 0, "medals_inserted": 0}

    # Obtenir le chemin de la DB
    db_path = get_player_duckdb_path(gamertag)
    if not db_path or not db_path.exists():
        logger.error(f"DB DuckDB introuvable pour {gamertag}")
        return {"matches_checked": 0, "matches_missing_medals": 0, "medals_inserted": 0}

    # Obtenir le XUID depuis la DB
    import duckdb

    conn = duckdb.connect(str(db_path), read_only=False)

    try:
        # Récupérer le XUID depuis xuid_aliases
        xuid_result = conn.execute(
            "SELECT xuid FROM xuid_aliases ORDER BY last_seen DESC LIMIT 1"
        ).fetchone()

        if not xuid_result or not xuid_result[0]:
            logger.error(f"XUID introuvable pour {gamertag}")
            return {"matches_checked": 0, "matches_missing_medals": 0, "medals_inserted": 0}

        xuid = str(xuid_result[0])
        logger.info(f"XUID résolu: {xuid}")

        # Trouver les matchs sans médailles
        # Note: medals_earned n'a pas de colonne xuid, donc on vérifie juste l'existence
        query = """
            SELECT DISTINCT ms.match_id
            FROM match_stats ms
            LEFT JOIN medals_earned me ON ms.match_id = me.match_id
            WHERE me.match_id IS NULL
            ORDER BY ms.start_time DESC
        """

        if max_matches:
            query += f" LIMIT {max_matches}"

        matches_without_medals = conn.execute(query, (xuid,)).fetchall()
        match_ids = [row[0] for row in matches_without_medals]

        logger.info(f"Matchs trouvés sans médailles: {len(match_ids)}")

        if dry_run:
            logger.info("Mode dry-run: aucun traitement effectué")
            return {
                "matches_checked": len(match_ids),
                "matches_missing_medals": len(match_ids),
                "medals_inserted": 0,
            }

        if not match_ids:
            logger.info("Tous les matchs ont déjà des médailles")
            return {
                "matches_checked": 0,
                "matches_missing_medals": 0,
                "medals_inserted": 0,
            }

        # Récupérer les tokens
        tokens = get_tokens_from_env()
        if not tokens:
            logger.error("Tokens SPNKr non disponibles")
            return {"matches_checked": 0, "matches_missing_medals": 0, "medals_inserted": 0}

        # Traiter les matchs
        total_medals_inserted = 0

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

                    # Extraire les médailles
                    medal_rows = extract_medals(stats_json, xuid)

                    if medal_rows:
                        # Insérer les médailles
                        inserted = _insert_medal_rows(conn, medal_rows)
                        conn.commit()
                        total_medals_inserted += inserted
                        logger.info(f"  ✅ {inserted} médaille(s) insérée(s)")
                    else:
                        logger.info("  ⚠️  Aucune médaille trouvée")

                except Exception as e:
                    logger.error(f"Erreur traitement {match_id}: {e}")
                    continue

        logger.info(f"Backfill terminé: {total_medals_inserted} médaille(s) insérée(s)")

        return {
            "matches_checked": len(match_ids),
            "matches_missing_medals": len(match_ids),
            "medals_inserted": total_medals_inserted,
        }

    finally:
        conn.close()


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Backfill des médailles manquantes pour DuckDB v4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--player",
        type=str,
        required=True,
        help="Gamertag du joueur",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode dry-run (ne fait que lister les matchs sans médailles)",
    )

    parser.add_argument(
        "--max-matches",
        type=int,
        default=None,
        help="Nombre maximum de matchs à traiter (défaut: tous)",
    )

    parser.add_argument(
        "--requests-per-second",
        type=int,
        default=5,
        help="Rate limiting API (défaut: 5 req/s)",
    )

    args = parser.parse_args()

    # Exécuter le backfill
    try:
        result = asyncio.run(
            backfill_medals(
                args.player,
                dry_run=args.dry_run,
                max_matches=args.max_matches,
                requests_per_second=args.requests_per_second,
            )
        )

        logger.info("\n=== Résumé ===")
        logger.info(f"Matchs vérifiés: {result['matches_checked']}")
        logger.info(f"Matchs sans médailles: {result['matches_missing_medals']}")
        logger.info(f"Médailles insérées: {result['medals_inserted']}")

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
