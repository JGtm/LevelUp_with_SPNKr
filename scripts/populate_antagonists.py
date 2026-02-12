#!/usr/bin/env python3
"""Peuple la table antagonists pour un ou plusieurs joueurs.

Sprint 3.2 - Ce script parcourt les matchs d'un joueur, calcule les
antagonistes (killers/victimes) et les persiste dans la table DuckDB.

Usage:
    python scripts/populate_antagonists.py --gamertag JGtm
    python scripts/populate_antagonists.py --all
    python scripts/populate_antagonists.py --all --force
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.antagonists import AggregationResult, aggregate_antagonists
from src.analysis.killer_victim import compute_personal_antagonists
from src.data.repositories.factory import get_repository_from_profile, load_db_profiles


def load_highlight_events_for_match(db_path: str, match_id: str) -> list:
    """DEPRECATED: Charge les highlight events depuis une DB legacy (SQLite supprimé)."""
    raise NotImplementedError(
        "SQLite legacy supprimé. Utilisez DuckDBRepository.load_highlight_events()."
    )


def load_match_players_stats(db_path: str, match_id: str) -> list:
    """DEPRECATED: Charge les stats-joueurs depuis une DB legacy (SQLite supprimé)."""
    raise NotImplementedError(
        "SQLite legacy supprimé. Utilisez DuckDBRepository.load_match_players_stats()."
    )


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_legacy_db_path(gamertag: str) -> str | None:
    """Trouve le chemin vers la DB legacy pour un joueur.

    Les highlight events sont encore dans les DBs SQLite legacy.
    """
    # Chercher dans les chemins possibles
    possible_paths = [
        Path(f"data/spnkr_gt_{gamertag}.db"),
        Path(f"spnkr_gt_{gamertag}.db"),
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

    return None


def process_player(
    gamertag: str,
    profile: dict,
    *,
    force: bool = False,
    tolerance_ms: int = 5,
    min_encounters: int = 2,
) -> AggregationResult | None:
    """Calcule et persiste les antagonistes pour un joueur.

    Args:
        gamertag: Nom du joueur.
        profile: Profil depuis db_profiles.json.
        force: Si True, recalcule même si des données existent.
        tolerance_ms: Tolérance pour l'appariement kill/death.
        min_encounters: Nombre minimum de matchs pour inclure un adversaire.

    Returns:
        AggregationResult ou None si erreur.
    """
    logger.info(f"Traitement de {gamertag}...")

    xuid = profile.get("xuid", "")
    db_path = profile.get("db_path", "")

    if not xuid or not db_path:
        logger.error(f"Profil incomplet pour {gamertag}")
        return None

    # Vérifier si la DB DuckDB existe
    duckdb_path = Path(db_path)
    if not duckdb_path.exists():
        logger.error(f"Base DuckDB non trouvée: {duckdb_path}")
        return None

    # Chercher la DB legacy pour les highlight events
    legacy_db_path = get_legacy_db_path(gamertag)
    if not legacy_db_path:
        logger.warning(
            f"DB legacy non trouvée pour {gamertag}. "
            "Les highlight events ne sont pas disponibles."
        )
        return None

    # Obtenir le repository
    try:
        repo = get_repository_from_profile(gamertag)
    except Exception as e:
        logger.error(f"Erreur création repository pour {gamertag}: {e}")
        return None

    # Vérifier si des données existent déjà
    if not force:
        try:
            existing = repo.query(
                "SELECT COUNT(*) as cnt FROM antagonists WHERE times_killed > 0 OR times_killed_by > 0"
            )
            if existing and existing[0].get("cnt", 0) > 0:
                logger.info(
                    f"{gamertag}: {existing[0]['cnt']} antagonistes existants. "
                    "Utilisez --force pour recalculer."
                )
                return None
        except Exception:
            # Table n'existe peut-être pas encore
            pass

    # Charger tous les matchs
    matches = repo.load_matches()
    logger.info(f"{gamertag}: {len(matches)} matchs trouvés")

    if not matches:
        logger.warning(f"{gamertag}: Aucun match trouvé")
        return None

    # Calculer les antagonistes pour chaque match
    match_results = []
    matches_with_events = 0
    matches_with_errors = 0

    for i, match in enumerate(matches, 1):
        if i % 100 == 0:
            logger.info(f"{gamertag}: Traitement {i}/{len(matches)}...")

        try:
            # Charger les highlight events depuis la DB legacy
            events = load_highlight_events_for_match(legacy_db_path, match.match_id)

            if not events:
                continue

            # Charger les stats officielles pour validation
            official_stats = load_match_players_stats(legacy_db_path, match.match_id)

            # Calculer les antagonistes
            result = compute_personal_antagonists(
                events,
                me_xuid=xuid,
                tolerance_ms=tolerance_ms,
                official_stats=official_stats,
            )

            if result.my_kills_total > 0 or result.my_deaths_total > 0:
                match_results.append((match.start_time, result))
                matches_with_events += 1

        except Exception as e:
            matches_with_errors += 1
            logger.debug(f"Match {match.match_id}: erreur {e}")
            continue

    logger.info(
        f"{gamertag}: {matches_with_events} matchs avec events, " f"{matches_with_errors} erreurs"
    )

    if not match_results:
        logger.warning(f"{gamertag}: Aucun match avec des highlight events")
        return None

    # Agréger les résultats
    aggregated = aggregate_antagonists(match_results, min_encounters=min_encounters)
    aggregated.matches_processed = len(matches)
    aggregated.matches_with_events = matches_with_events
    aggregated.matches_with_errors = matches_with_errors

    logger.info(
        f"{gamertag}: {len(aggregated.entries)} adversaires agrégés, "
        f"{aggregated.total_duels_found} duels trouvés"
    )

    # Persister dans DuckDB
    try:
        # Utiliser une connexion en écriture
        repo.close()
        repo = get_repository_from_profile(gamertag)

        # Sauvegarder via la nouvelle méthode
        saved = repo.save_antagonists(aggregated.entries, replace=force)
        logger.info(f"{gamertag}: {saved} antagonistes sauvegardés")

    except Exception as e:
        logger.error(f"{gamertag}: Erreur lors de la sauvegarde: {e}")
        raise

    finally:
        repo.close()

    return aggregated


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Peuple la table antagonists depuis les highlight events"
    )
    parser.add_argument(
        "--gamertag",
        "-g",
        type=str,
        help="Gamertag du joueur à traiter",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Traiter tous les joueurs",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Recalculer même si des données existent",
    )
    parser.add_argument(
        "--tolerance",
        "-t",
        type=int,
        default=5,
        help="Tolérance en ms pour l'appariement kill/death (défaut: 5)",
    )
    parser.add_argument(
        "--min-encounters",
        "-m",
        type=int,
        default=2,
        help="Nombre minimum de matchs pour inclure un adversaire (défaut: 2)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Afficher plus de détails",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.gamertag and not args.all:
        parser.error("Spécifiez --gamertag ou --all")

    # Charger les profils
    try:
        profiles = load_db_profiles()
    except Exception as e:
        logger.error(f"Erreur chargement db_profiles.json: {e}")
        return 1

    profiles_dict = profiles.get("profiles", {})

    if not profiles_dict:
        logger.error("Aucun profil trouvé dans db_profiles.json")
        return 1

    # Déterminer les joueurs à traiter
    if args.all:
        gamertags = list(profiles_dict.keys())
    else:
        if args.gamertag not in profiles_dict:
            logger.error(f"Joueur '{args.gamertag}' non trouvé dans db_profiles.json")
            logger.info(f"Joueurs disponibles: {', '.join(profiles_dict.keys())}")
            return 1
        gamertags = [args.gamertag]

    # Traiter chaque joueur
    total_entries = 0
    total_matches = 0

    for gamertag in gamertags:
        profile = profiles_dict[gamertag]
        result = process_player(
            gamertag,
            profile,
            force=args.force,
            tolerance_ms=args.tolerance,
            min_encounters=args.min_encounters,
        )

        if result:
            total_entries += len(result.entries)
            total_matches += result.matches_with_events

    logger.info("=== Terminé ===")
    logger.info(f"Total: {total_entries} adversaires, {total_matches} matchs traités")

    return 0


if __name__ == "__main__":
    sys.exit(main())
