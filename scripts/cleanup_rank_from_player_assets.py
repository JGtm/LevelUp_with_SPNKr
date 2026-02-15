"""Nettoyage one-shot : supprime les fichiers rank_* de player_assets/.

10C.4.4 — Les icônes de rang doivent provenir de data/cache/career_ranks/
et non de data/cache/player_assets/. Ce script supprime les doublons.

Usage:
    python scripts/cleanup_rank_from_player_assets.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Supprime les fichiers rank_* du cache player_assets."""
    ap = argparse.ArgumentParser(
        description="Supprime les fichiers rank_* de data/cache/player_assets/"
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les fichiers sans les supprimer.",
    )
    args = ap.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    assets_dir = repo_root / "data" / "cache" / "player_assets"

    if not assets_dir.exists():
        print(f"Répertoire inexistant: {assets_dir}")
        return 0

    rank_files = sorted(assets_dir.glob("rank_*"))

    if not rank_files:
        print("Aucun fichier rank_* trouvé dans player_assets/.")
        return 0

    print(f"Fichiers rank_* trouvés: {len(rank_files)}")

    removed = 0
    for f in rank_files:
        if args.dry_run:
            print(f"  [DRY-RUN] {f.name}")
        else:
            try:
                f.unlink()
                print(f"  Supprimé: {f.name}")
                removed += 1
            except Exception as e:
                print(f"  ERREUR {f.name}: {e}")

    if args.dry_run:
        print(f"\n{len(rank_files)} fichier(s) seraient supprimés. Relancez sans --dry-run.")
    else:
        print(f"\n{removed} fichier(s) supprimés.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
