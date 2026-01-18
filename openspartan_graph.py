"""OpenSpartan Graph - CLI pour générer des graphiques.

Usage:
    python openspartan_graph.py --db path/to/db.db --last 80 --out out/graph.png
"""

import argparse
import os
import sys

# Ajoute le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db import load_matches, guess_xuid_from_db_path
from src.models import MatchRow
from typing import List, Optional


def plot_kills_deaths_ratio(
    matches: List[MatchRow],
    out_path: str,
    *,
    title: str,
    last_n: Optional[int] = None,
) -> None:
    """Génère un graphique Kills/Deaths/Ratio avec Matplotlib.
    
    Args:
        matches: Liste de MatchRow.
        out_path: Chemin de sortie PNG.
        title: Titre du graphique.
        last_n: Ne garder que les N derniers matchs.
    """
    if last_n is not None:
        matches = matches[-last_n:]

    if not matches:
        raise SystemExit("Aucun match trouvé (filtre trop strict ?)")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except Exception as e:
        raise SystemExit(
            "matplotlib est requis. Installe-le avec: pip install matplotlib\n"
            f"Détail: {e}"
        )

    x = [m.start_time for m in matches]
    kills = [m.kills for m in matches]
    deaths = [m.deaths for m in matches]
    ratio = [m.ratio for m in matches]

    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
    fig.suptitle(title)

    axes[0].plot(x, kills, label="Kills", color="#2E86AB")
    axes[0].set_ylabel("Kills")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(x, deaths, label="Deaths", color="#D1495B")
    axes[1].set_ylabel("Deaths")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(x, ratio, label="Ratio (K + A/2) / D", color="#3A7D44")
    axes[2].set_ylabel("Ratio")
    axes[2].grid(True, alpha=0.3)

    locator = mdates.AutoDateLocator(minticks=3, maxticks=8)
    formatter = mdates.ConciseDateFormatter(locator)
    axes[2].xaxis.set_major_locator(locator)
    axes[2].xaxis.set_major_formatter(formatter)

    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def main() -> int:
    """Point d'entrée CLI."""
    ap = argparse.ArgumentParser(
        description=(
            "Génère des graphes à partir de la DB OpenSpartan (SQLite).\n"
            "V2: Architecture refactorisée."
        )
    )
    ap.add_argument(
        "--db",
        required=True,
        help="Chemin vers le fichier .db (SQLite)",
    )
    ap.add_argument(
        "--xuid",
        default=None,
        help="Ton XUID (par défaut: déduit du nom du .db si possible)",
    )
    ap.add_argument(
        "--last",
        type=int,
        default=None,
        help="Ne garder que les N derniers matchs (après tri par date)",
    )
    ap.add_argument(
        "--playlist-id",
        default=None,
        help="Filtre sur MatchInfo.Playlist.AssetId (UUID)",
    )
    ap.add_argument(
        "--pair-id",
        default=None,
        help="Filtre sur MatchInfo.PlaylistMapModePair.AssetId (UUID)",
    )
    ap.add_argument(
        "--out",
        default=os.path.join("out", "kills_deaths_ratio.png"),
        help="Chemin de sortie PNG",
    )

    args = ap.parse_args()

    db_path = args.db
    if args.xuid is None:
        guessed = guess_xuid_from_db_path(db_path)
        if guessed is None:
            raise SystemExit("Impossible de deviner le XUID. Passe --xuid.")
        xuid = guessed
    else:
        xuid = str(args.xuid)

    matches = load_matches(
        db_path,
        xuid,
        playlist_filter=args.playlist_id,
        map_mode_pair_filter=args.pair_id,
    )

    title_parts = ["OpenSpartan", f"XUID {xuid}"]
    if args.playlist_id:
        title_parts.append(f"Playlist {args.playlist_id}")
    if args.pair_id:
        title_parts.append(f"Pair {args.pair_id}")
    title = " — ".join(title_parts)

    plot_kills_deaths_ratio(matches, args.out, title=title, last_n=args.last)
    print(f"OK: {args.out} ({len(matches)} matchs, last={args.last})")
    return 0


# Export pour rétrocompatibilité
def query_matches_with_friend(db_path: str, self_xuid: str, friend_xuid: str):
    """Wrapper de rétrocompatibilité."""
    from src.db import query_matches_with_friend as _query
    results = _query(db_path, self_xuid, friend_xuid)
    # Convertit en format dict pour compatibilité
    return [
        {
            "match_id": r.match_id,
            "start_time": r.start_time,
            "playlist_id": r.playlist_id,
            "playlist_name": r.playlist_name,
            "pair_id": r.pair_id,
            "pair_name": r.pair_name,
            "my_team_id": r.my_team_id,
            "my_outcome": r.my_outcome,
            "friend_team_id": r.friend_team_id,
            "friend_outcome": r.friend_outcome,
            "same_team": r.same_team,
        }
        for r in results
    ]


# Réexport pour rétrocompatibilité
_guess_xuid_from_db_path = guess_xuid_from_db_path


if __name__ == "__main__":
    raise SystemExit(main())
