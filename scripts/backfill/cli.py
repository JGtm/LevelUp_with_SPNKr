"""Parsing des arguments CLI pour le backfill.

Ce module centralise la définition de tous les arguments CLI,
séparant la logique de parsing de la logique métier.
"""

from __future__ import annotations

import argparse


def create_argument_parser() -> argparse.ArgumentParser:
    """Crée le parser d'arguments pour le CLI backfill.

    Returns:
        Parser configuré avec tous les arguments.
    """
    parser = argparse.ArgumentParser(
        description="Backfill des données manquantes pour DuckDB v4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_get_usage_examples(),
    )

    # ── Sélection du joueur ──
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

    # ── Options générales ──
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
    parser.add_argument(
        "--detection-mode",
        choices=["or", "and"],
        default="or",
        help=(
            "Mode de détection des matchs manquants: "
            "'or' = manque AU MOINS UNE donnée (défaut, compatible), "
            "'and' = manque TOUTES les données (strict, évite re-traitement)"
        ),
    )

    # ── Options de données à backfill ──
    parser.add_argument("--medals", action="store_true", help="Backfill les médailles")
    parser.add_argument("--events", action="store_true", help="Backfill les highlight events")
    parser.add_argument("--skill", action="store_true", help="Backfill les stats skill/MMR")
    parser.add_argument(
        "--personal-scores",
        action="store_true",
        help="Backfill les personal score awards",
    )
    parser.add_argument(
        "--performance-scores",
        action="store_true",
        help="Calculer les scores de performance manquants",
    )
    parser.add_argument("--aliases", action="store_true", help="Mettre à jour les aliases XUID")
    parser.add_argument(
        "--all-data",
        action="store_true",
        help="Backfill toutes les données",
    )

    # ── Accuracy ──
    parser.add_argument(
        "--accuracy",
        action="store_true",
        help="Backfill la précision (accuracy) pour les matchs avec accuracy NULL",
    )
    parser.add_argument(
        "--force-accuracy",
        action="store_true",
        help="Force la récupération de accuracy pour TOUS les matchs",
    )

    # ── Shots ──
    parser.add_argument(
        "--shots",
        action="store_true",
        help="Backfill shots_fired/shots_hit pour les matchs où ils sont NULL",
    )
    parser.add_argument(
        "--force-shots",
        action="store_true",
        help="Force la mise à jour de shots_fired/shots_hit pour TOUS les matchs",
    )

    # ── Enemy MMR ──
    parser.add_argument(
        "--enemy-mmr",
        action="store_true",
        help="Backfill enemy_mmr pour les matchs avec enemy_mmr NULL",
    )
    parser.add_argument(
        "--force-enemy-mmr",
        action="store_true",
        help="Force la récupération de enemy_mmr pour TOUS les matchs",
    )

    # ── Assets ──
    parser.add_argument(
        "--assets",
        action="store_true",
        help="Récupérer les noms (playlist, map, pair, game_variant) via Discovery UGC",
    )
    parser.add_argument(
        "--force-assets",
        action="store_true",
        help="Force la récupération des noms pour TOUS les matchs",
    )

    # ── Aliases ──
    parser.add_argument(
        "--force-aliases",
        action="store_true",
        help="Force la ré-extraction des aliases pour tous les matchs",
    )
    parser.add_argument(
        "--force-medals",
        action="store_true",
        help="Force le rescan de TOUS les matchs pour les médailles",
    )

    # ── Participants ──
    parser.add_argument(
        "--participants",
        action="store_true",
        help="Backfill les participants de match (table match_participants)",
    )
    parser.add_argument(
        "--force-participants",
        action="store_true",
        help="Force la ré-extraction des participants pour tous les matchs",
    )
    parser.add_argument(
        "--participants-scores",
        action="store_true",
        help="Backfill score et rang des participants",
    )
    parser.add_argument(
        "--participants-kda",
        action="store_true",
        help="Backfill kills, deaths, assists des participants",
    )
    parser.add_argument(
        "--participants-shots",
        action="store_true",
        help="Backfill shots_fired/shots_hit des participants",
    )
    parser.add_argument(
        "--force-participants-shots",
        action="store_true",
        help="Force shots pour tous les participants de tous les matchs",
    )
    parser.add_argument(
        "--participants-damage",
        action="store_true",
        help="Backfill damage_dealt/damage_taken des participants",
    )
    parser.add_argument(
        "--force-participants-damage",
        action="store_true",
        help="Force damage pour tous les participants de tous les matchs",
    )

    # ── Killer/victim ──
    parser.add_argument(
        "--killer-victim",
        action="store_true",
        help="Backfill les paires killer/victim depuis highlight_events",
    )

    # ── End time ──
    parser.add_argument(
        "--end-time",
        action="store_true",
        help="Remplir end_time (start_time + time_played_seconds)",
    )
    parser.add_argument(
        "--force-end-time",
        action="store_true",
        help="Recalculer end_time pour tous les matchs",
    )

    # ── Sessions ──
    parser.add_argument(
        "--sessions",
        action="store_true",
        help="Backfill session_id et session_label (matchs stables ≥ 4h)",
    )
    parser.add_argument(
        "--force-sessions",
        action="store_true",
        help="Recalculer les sessions même si session_id déjà rempli",
    )

    # ── Citations ──
    parser.add_argument(
        "--citations",
        action="store_true",
        help="Calculer et insérer les citations pour les matchs existants",
    )
    parser.add_argument(
        "--force-citations",
        action="store_true",
        help="Recalculer les citations même si déjà présentes",
    )

    return parser


def _get_usage_examples() -> str:
    """Retourne les exemples d'usage pour l'aide CLI."""
    return """
Exemples:
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

Workaround OR — Exécution par étapes:
    python scripts/backfill_data.py --player JGtm --medals
    python scripts/backfill_data.py --player JGtm --sessions
    python scripts/backfill_data.py --player JGtm --participants-kda
    """
