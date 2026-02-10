#!/usr/bin/env python3
"""Script pour réinitialiser les tables médias (media_files, media_match_associations).

Usage:
    python scripts/reset_media_db.py --gamertag PlayerA
    python scripts/reset_media_db.py --all
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

# Encodage UTF-8 pour la console Windows
if sys.stdout.encoding and sys.stdout.encoding.lower().startswith("cp"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.data.media_indexer import MediaIndexer
from src.utils.paths import PLAYER_DB_FILENAME, PLAYERS_DIR


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Réinitialise les tables médias (media_files, media_match_associations)"
    )
    parser.add_argument(
        "--gamertag",
        type=str,
        help="Gamertag du joueur à réinitialiser",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Réinitialiser toutes les DB joueurs",
    )

    args = parser.parse_args()

    if args.all:
        count = 0
        for player_dir in sorted(PLAYERS_DIR.iterdir(), key=lambda p: p.name):
            if not player_dir.is_dir():
                continue
            db_file = player_dir / PLAYER_DB_FILENAME
            if not db_file.exists():
                continue
            try:
                indexer = MediaIndexer(db_file)
                indexer.reset_media_tables()
                print(f"✅ {player_dir.name}: tables médias vidées")
                count += 1
            except Exception as e:
                print(f"⚠️  {player_dir.name}: {e}")
        print(f"\n✅ {count} joueur(s) réinitialisé(s)")
        return 0

    gamertag = args.gamertag
    if not gamertag:
        print("❌ Erreur: Spécifiez --gamertag ou --all")
        return 1

    db_path = PLAYERS_DIR / gamertag / PLAYER_DB_FILENAME
    if not db_path.exists():
        print(f"❌ Erreur: DB introuvable: {db_path}")
        return 1

    try:
        indexer = MediaIndexer(db_path)
        indexer.reset_media_tables()
        print(f"✅ Tables médias vidées pour {gamertag}")
        return 0
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
