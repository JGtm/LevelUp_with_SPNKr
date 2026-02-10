#!/usr/bin/env python3
"""
Script utilitaire pour obtenir un match ID depuis la base de données.

Usage:
    python scripts/get_match_id.py --gamertag JGtm --limit 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import duckdb
except ImportError:
    print("ERREUR: duckdb non disponible")
    sys.exit(1)


def get_match_ids(gamertag: str, limit: int = 5) -> list[tuple[str, str]]:
    """Récupère les derniers match IDs depuis DuckDB."""
    db_path = Path(f"data/players/{gamertag}/stats.duckdb")
    if not db_path.exists():
        print(f"ERREUR: Base non trouvée: {db_path}")
        return []

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        results = con.execute(
            """
            SELECT match_id, start_time, map_name, playlist_name, kills, deaths
            FROM match_stats
            ORDER BY start_time DESC
            LIMIT ?
        """,
            [limit],
        ).fetchall()

        matches = []
        for row in results:
            match_id, start_time, map_name, playlist_name, kills, deaths = row
            matches.append(
                (
                    match_id,
                    str(start_time)[:19] if start_time else "N/A",
                    map_name or "N/A",
                    playlist_name or "N/A",
                    kills or 0,
                    deaths or 0,
                )
            )
        return matches
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Obtenir des match IDs depuis la base")
    parser.add_argument("--gamertag", required=True, help="Gamertag du joueur")
    parser.add_argument("--limit", type=int, default=5, help="Nombre de matchs à afficher")
    parser.add_argument(
        "--first-only", action="store_true", help="Afficher seulement le premier match ID"
    )

    args = parser.parse_args()

    matches = get_match_ids(args.gamertag, args.limit)

    if not matches:
        print(f"Aucun match trouvé pour {args.gamertag}")
        return 1

    if args.first_only:
        print(matches[0][0])
        return 0

    print(f"\n{len(matches)} matchs trouvés pour {args.gamertag}:\n")
    print(f"{'Match ID':<40} {'Date':<20} {'Map':<25} {'Playlist':<25} {'K/D'}")
    print("-" * 120)

    for match_id, start_time, map_name, playlist_name, kills, deaths in matches:
        kd = f"{kills}/{deaths}" if deaths > 0 else f"{kills}/0"
        print(f"{match_id:<40} {start_time:<20} {map_name[:24]:<25} {playlist_name[:24]:<25} {kd}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
