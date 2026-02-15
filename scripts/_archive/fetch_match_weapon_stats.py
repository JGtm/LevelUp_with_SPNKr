#!/usr/bin/env python3
"""
Récupère les weapon stats détaillées d'un match pour un joueur spécifique.

Usage:
    python scripts/fetch_match_weapon_stats.py --match-id <ID> --gamertag <GT>
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.sync.api_client import SPNKrAPIClient


def _load_dotenv_if_present() -> None:
    """Charge les variables d'environnement depuis .env.local ou .env."""
    repo_root = Path(__file__).resolve().parent.parent
    for name in (".env.local", ".env"):
        p = repo_root / name
        if not p.exists():
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and os.environ.get(key) is None:
                os.environ[key] = value


async def main():
    parser = argparse.ArgumentParser(description="Récupérer les weapon stats d'un match")
    parser.add_argument("--match-id", required=True, help="ID du match")
    parser.add_argument("--gamertag", help="Gamertag à filtrer (optionnel)")
    parser.add_argument("--all", action="store_true", help="Afficher tous les joueurs")

    args = parser.parse_args()
    _load_dotenv_if_present()

    print(f"Récupération des stats du match {args.match_id}...")
    print()

    async with SPNKrAPIClient() as client:
        match_data = await client.get_match_stats(args.match_id)

    if not match_data:
        print("Aucune donnée récupérée")
        return 1

    # Chercher les joueurs
    players = match_data.get("Players", [])

    for player in players:
        player_id = player.get("PlayerId", "")

        # Filtrer par gamertag si spécifié
        if args.gamertag and args.gamertag.lower() not in player_id.lower():
            if not args.all:
                continue

        team_stats = player.get("PlayerTeamStats", [])
        if not team_stats:
            continue

        stats = team_stats[0].get("Stats", {})
        core = stats.get("CoreStats", {})
        breakdowns = core.get("Breakdowns", {})
        weapons = breakdowns.get("Weapons", [])

        if not weapons and not args.all:
            continue

        # Afficher le header joueur
        print(f"{'='*60}")
        print(f"JOUEUR: {player_id}")
        print(
            f"Kills: {core.get('Kills', 0)} | Deaths: {core.get('Deaths', 0)} | "
            f"Assists: {core.get('Assists', 0)}"
        )
        print(f"{'='*60}")
        print()

        if weapons:
            print(f"{'Arme':<35} {'Kills':>6} {'HS':>4} {'Dégâts':>10} {'Préc.':>7}")
            print("-" * 68)

            for w in sorted(weapons, key=lambda x: -x.get("Kills", 0)):
                name = w.get("EquippedWeaponName", "Unknown")
                kills = w.get("Kills", 0)
                headshots = w.get("Headshots", 0)
                damage = w.get("DamageDealt", 0)
                shots_fired = w.get("ShotsFired", 0)
                shots_hit = w.get("ShotsHit", 0)

                accuracy = (shots_hit / shots_fired * 100) if shots_fired > 0 else 0

                if kills > 0 or damage > 100:
                    print(
                        f"{name:<35} {kills:>6} {headshots:>4} "
                        f"{damage:>10.0f} {accuracy:>6.1f}%"
                    )

            print()
        else:
            print("(Pas de données d'armes)")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
