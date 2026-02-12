#!/usr/bin/env python3
"""Script de backfill pour remplir les données manquantes.

Ce script identifie les matchs existants qui ont des données manquantes
(medals, highlight_events, skill stats, personal_scores, performance_scores)
et les remplit en re-téléchargeant les données nécessaires depuis l'API SPNKr.

Usage:
    # Backfill toutes les données pour un joueur
    python scripts/backfill_data.py --player JGtm --all-data

    # Mode strict (pas de re-téléchargement si partiellement rempli)
    python scripts/backfill_data.py --player JGtm --all-data --detection-mode and

    # Backfill uniquement les médailles
    python scripts/backfill_data.py --player JGtm --medals

    # Calculer les scores de performance manquants
    python scripts/backfill_data.py --player JGtm --performance-scores

    # Backfill pour tous les joueurs
    python scripts/backfill_data.py --all --all-data

    # Mode dry-run (liste seulement)
    python scripts/backfill_data.py --player JGtm --dry-run

    # Limiter le nombre de matchs
    python scripts/backfill_data.py --player JGtm --max-matches 100

Note: Pour combiner sync + backfill en une seule commande, utilisez :
    python scripts/sync.py --delta --player JGtm --with-backfill

Architecture (Sprint 10B) :
    scripts/backfill/
    ├── __init__.py
    ├── core.py          — Fonctions d'insertion de base
    ├── detection.py     — Détection des matchs manquants (AND/OR configurable)
    ├── strategies.py    — Stratégies spécifiques (killer/victim, end_time, perf_score)
    ├── orchestrator.py  — Orchestration du backfill
    └── cli.py           — Parsing des arguments CLI
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# ─────────────────────────────────────────────────────────────────────────────
# Rétro-compatibilité : les imports existants restent fonctionnels
#   from scripts.backfill_data import backfill_player_data
#   from scripts.backfill_data import backfill_all_players
#   from scripts.backfill_data import _find_matches_missing_data
#   etc.
# ─────────────────────────────────────────────────────────────────────────────
from scripts.backfill.cli import create_argument_parser  # noqa: E402
from scripts.backfill.orchestrator import (  # noqa: E402
    backfill_all_players,
    backfill_player_data,
)

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Point d'entrée principal."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Validation
    if not args.all and not args.player:
        parser.error("--player ou --all est requis")

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
                    performance_scores=args.performance_scores,
                    aliases=args.aliases,
                    accuracy=args.accuracy,
                    enemy_mmr=args.enemy_mmr,
                    assets=args.assets,
                    participants=args.participants,
                    participants_scores=args.participants_scores,
                    participants_kda=args.participants_kda,
                    participants_shots=args.participants_shots,
                    participants_damage=args.participants_damage,
                    killer_victim=args.killer_victim,
                    end_time=args.end_time,
                    all_data=args.all_data,
                    force_medals=args.force_medals,
                    force_accuracy=args.force_accuracy,
                    shots=args.shots,
                    force_shots=args.force_shots,
                    force_participants_shots=args.force_participants_shots,
                    force_participants_damage=args.force_participants_damage,
                    force_enemy_mmr=args.force_enemy_mmr,
                    force_aliases=args.force_aliases,
                    force_assets=args.force_assets,
                    force_participants=args.force_participants,
                    force_end_time=args.force_end_time,
                    sessions=args.sessions,
                    force_sessions=args.force_sessions,
                    detection_mode=args.detection_mode,
                )
            )
            _print_summary_all(result, args)
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
                    performance_scores=args.performance_scores,
                    aliases=args.aliases,
                    accuracy=args.accuracy,
                    enemy_mmr=args.enemy_mmr,
                    assets=args.assets,
                    participants=args.participants,
                    participants_scores=args.participants_scores,
                    participants_kda=args.participants_kda,
                    participants_shots=args.participants_shots,
                    participants_damage=args.participants_damage,
                    killer_victim=args.killer_victim,
                    end_time=args.end_time,
                    all_data=args.all_data,
                    force_medals=args.force_medals,
                    force_accuracy=args.force_accuracy,
                    shots=args.shots,
                    force_shots=args.force_shots,
                    force_participants_shots=args.force_participants_shots,
                    force_participants_damage=args.force_participants_damage,
                    force_enemy_mmr=args.force_enemy_mmr,
                    force_aliases=args.force_aliases,
                    force_assets=args.force_assets,
                    force_participants=args.force_participants,
                    force_end_time=args.force_end_time,
                    sessions=args.sessions,
                    force_sessions=args.force_sessions,
                    detection_mode=args.detection_mode,
                )
            )
            _print_summary_player(result, args)

        return 0

    except KeyboardInterrupt:
        logger.info("\nInterrompu par l'utilisateur")
        return 1
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        import traceback

        traceback.print_exc()
        return 1


def _print_summary_all(result: dict, args: object) -> None:
    """Affiche le résumé global pour tous les joueurs."""
    logger.info("\n" + "=" * 60)
    logger.info("=== RÉSUMÉ GLOBAL ===")
    logger.info("=" * 60)
    logger.info(f"Joueurs traités: {result['players_processed']}")
    totals = result["total_results"]
    _print_totals(totals, args)


def _print_summary_player(result: dict, args: object) -> None:
    """Affiche le résumé pour un joueur."""
    logger.info("\n=== Résumé ===")
    _print_totals(result, args)


def _print_totals(totals: dict, args: object) -> None:
    """Affiche les totaux du backfill."""
    logger.info(f"Matchs vérifiés: {totals.get('matches_checked', 0)}")
    logger.info(f"Matchs avec données manquantes: {totals.get('matches_missing_data', 0)}")
    logger.info(f"Médailles insérées: {totals.get('medals_inserted', 0)}")
    logger.info(f"Events insérés: {totals.get('events_inserted', 0)}")
    logger.info(f"Skill inséré: {totals.get('skill_inserted', 0)}")
    logger.info(f"Personal scores insérés: {totals.get('personal_scores_inserted', 0)}")
    logger.info(f"Scores de performance calculés: {totals.get('performance_scores_inserted', 0)}")
    logger.info(f"Aliases insérés: {totals.get('aliases_inserted', 0)}")

    if getattr(args, "accuracy", False):
        logger.info(f"Accuracy mis à jour: {totals.get('accuracy_updated', 0)}")
    if getattr(args, "shots", False):
        logger.info(f"Shots mis à jour: {totals.get('shots_updated', 0)}")
    if getattr(args, "enemy_mmr", False):
        logger.info(f"Enemy MMR mis à jour: {totals.get('enemy_mmr_updated', 0)}")
    if getattr(args, "assets", False):
        logger.info(f"Noms assets mis à jour: {totals.get('assets_updated', 0)}")
    if getattr(args, "participants", False):
        logger.info(f"Participants insérés: {totals.get('participants_inserted', 0)}")
    if getattr(args, "participants_scores", False):
        logger.info(f"Scores/rang participants: {totals.get('participants_scores_updated', 0)}")
    if getattr(args, "participants_kda", False):
        logger.info(f"K/D/A participants: {totals.get('participants_kda_updated', 0)}")
    if getattr(args, "participants_shots", False):
        logger.info(f"Shots participants: {totals.get('participants_shots_updated', 0)}")
    if getattr(args, "participants_damage", False):
        logger.info(f"Damage participants: {totals.get('participants_damage_updated', 0)}")
    if getattr(args, "killer_victim", False):
        logger.info(f"Paires killer/victim: {totals.get('killer_victim_pairs_inserted', 0)}")
    if getattr(args, "end_time", False):
        logger.info(f"End time mis à jour: {totals.get('end_time_updated', 0)}")
    if getattr(args, "sessions", False):
        logger.info(f"Sessions mises à jour: {totals.get('sessions_updated', 0)}")


if __name__ == "__main__":
    sys.exit(main())
