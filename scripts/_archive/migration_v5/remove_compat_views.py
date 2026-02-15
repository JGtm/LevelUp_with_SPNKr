"""Supprime les VIEWs de compatibilité v5 dans les DBs joueur.

Après le Sprint 5 (refactoring UI), les VIEWs de compatibilité ne sont plus
nécessaires car le code accède directement aux données shared via
DuckDBRepository._get_match_source().

VIEWs supprimées :
    - v_match_stats
    - v_medals_earned
    - v_highlight_events
    - v_match_participants

Usage :
    python scripts/migration/remove_compat_views.py [gamertag] [--all] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

PROFILES_PATH = PROJECT_ROOT / "db_profiles.json"

COMPAT_VIEWS = [
    "v_match_stats",
    "v_medals_earned",
    "v_highlight_events",
    "v_match_participants",
]

logger = logging.getLogger(__name__)


def remove_compat_views(
    gamertag: str,
    player_db_path: Path,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, bool]:
    """Supprime les VIEWs de compatibilité dans une DB joueur.

    Args:
        gamertag: Gamertag du joueur.
        player_db_path: Chemin vers la DB joueur.
        dry_run: Si True, affiche sans exécuter.
        verbose: Mode verbeux.

    Returns:
        Dict {view_name: success}.
    """
    results: dict[str, bool] = {}

    if not player_db_path.exists():
        raise FileNotFoundError(f"DB joueur introuvable : {player_db_path}")

    conn = duckdb.connect(str(player_db_path))

    try:
        # Lister les VIEWs existantes
        existing_views = {
            row[0]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_type = 'VIEW'"
            ).fetchall()
        }

        for view_name in COMPAT_VIEWS:
            if view_name not in existing_views:
                results[view_name] = True  # Déjà absente
                if verbose:
                    print(f"  ⏭️  Vue {view_name} n'existe pas (déjà supprimée)")
                continue

            sql = f"DROP VIEW IF EXISTS {view_name}"
            if dry_run:
                print(f"  [DRY-RUN] {sql}")
                results[view_name] = True
            else:
                try:
                    conn.execute(sql)
                    results[view_name] = True
                    if verbose:
                        print(f"  ✅ Vue {view_name} supprimée")
                except Exception as exc:
                    results[view_name] = False
                    logger.error(f"  ❌ Vue {view_name} : {exc}")

    finally:
        conn.close()

    return results


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(
        description="Supprime les VIEWs de compatibilité v5 des DBs joueur"
    )
    parser.add_argument("gamertag", nargs="?", help="Gamertag cible")
    parser.add_argument("--all", action="store_true", help="Tous les joueurs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8")).get("profiles", {})

    if args.all:
        gamertags = list(profiles.keys())
    elif args.gamertag:
        if args.gamertag not in profiles:
            print(f"❌ Gamertag '{args.gamertag}' inconnu dans db_profiles.json")
            sys.exit(1)
        gamertags = [args.gamertag]
    else:
        parser.print_help()
        sys.exit(1)

    total_removed = 0
    total_views = 0

    for gt in gamertags:
        profile = profiles[gt]
        db_path = PROJECT_ROOT / profile["db_path"]

        print(f"\n{'='*50}")
        print(f"Suppression VIEWs compat pour {gt}")
        print(f"{'='*50}")

        try:
            results = remove_compat_views(
                gamertag=gt,
                player_db_path=db_path,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )

            ok = sum(1 for v in results.values() if v)
            total = len(results)
            total_removed += ok
            total_views += total
            print(f"  → {ok}/{total} VIEWs traitées avec succès")

        except FileNotFoundError as e:
            print(f"  ⚠️  {e}")
        except Exception as e:
            print(f"  ❌ Erreur : {e}")

    print(f"\n{'='*50}")
    print(f"Total : {total_removed}/{total_views} VIEWs supprimées")
    if args.dry_run:
        print("  (mode dry-run — rien n'a été modifié)")


if __name__ == "__main__":
    main()
