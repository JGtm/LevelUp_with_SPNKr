#!/usr/bin/env python3
"""Trouve un match avec weapon breakdowns pour un joueur."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.sync.api_client import SPNKrAPIClient


async def main():
    gamertag = sys.argv[1] if len(sys.argv) > 1 else "JGtm"

    async with SPNKrAPIClient() as client:
        # Récupérer les 25 derniers matchs
        history = await client.get_match_history(gamertag, count=25)

        if not history:
            print(f"Pas d'historique pour {gamertag}")
            return

        print(f"Joueur: {gamertag}")
        print(f"Matchs trouvés: {len(history)}")
        print()
        print("Recherche de matchs avec weapon breakdowns...")
        print()

        for i, m in enumerate(history[:15]):  # Tester les 15 premiers
            match_id = m.match_id

            # Récupérer les stats détaillées
            stats = await client.get_match_stats(match_id)

            if not stats:
                print(f"Match {i+1}: {match_id[:8]} | [erreur API]")
                continue

            # Chercher les breakdowns
            players = stats.get("Players", [])
            has_weapons = False
            player_weapons = None

            for p in players:
                team_stats = p.get("PlayerTeamStats", [])
                if team_stats:
                    core = team_stats[0].get("Stats", {}).get("CoreStats", {})
                    breakdowns = core.get("Breakdowns", {})
                    weapons = breakdowns.get("Weapons", [])
                    if weapons:
                        has_weapons = True
                        # Garder pour le joueur focal (premier trouvé avec gamertag)
                        pid = p.get("PlayerId", "")
                        if gamertag.lower() in pid.lower() or not player_weapons:
                            player_weapons = {
                                "player_id": pid,
                                "kills": core.get("Kills", 0),
                                "deaths": core.get("Deaths", 0),
                                "weapons": weapons,
                            }

            match_info = stats.get("MatchInfo", {})
            mode = match_info.get("GameVariantCategory", 0)

            status = "[WEAPONS]" if has_weapons else "[no weapons]"
            print(f"Match {i+1}: {match_id[:8]} | Mode: {mode} | {status}")

            if has_weapons and player_weapons:
                print(f"\n{'='*60}")
                print(f">>> MATCH AVEC WEAPONS: {match_id}")
                print(f"Joueur: {player_weapons['player_id']}")
                print(f"K/D: {player_weapons['kills']}/{player_weapons['deaths']}")
                print(f"{'='*60}")

                print(f"\n{'Arme':<35} {'Kills':>6} {'HS':>4} {'Dégâts':>10} {'Préc.':>7}")
                print("-" * 68)

                for w in sorted(player_weapons["weapons"], key=lambda x: -x.get("Kills", 0)):
                    name = w.get("EquippedWeaponName", "Unknown")
                    kills = w.get("Kills", 0)
                    hs = w.get("Headshots", 0)
                    dmg = w.get("DamageDealt", 0)
                    shots_fired = w.get("ShotsFired", 0)
                    shots_hit = w.get("ShotsHit", 0)
                    acc = (shots_hit / shots_fired * 100) if shots_fired > 0 else 0

                    if kills > 0 or dmg > 100:
                        print(f"{name:<35} {kills:>6} {hs:>4} {dmg:>10.0f} {acc:>6.1f}%")

                print()
                return  # On a trouvé un match, on s'arrête

        print("\n[!] Aucun match avec weapon breakdowns trouve dans les 15 derniers matchs.")
        print("Note: Les weapon breakdowns ne sont pas disponibles pour tous les modes de jeu.")


if __name__ == "__main__":
    asyncio.run(main())
