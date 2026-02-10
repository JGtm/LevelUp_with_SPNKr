#!/usr/bin/env python3
"""
Récupère les weapon stats d'un match Fiesta via l'API Halo.

Usage:
    # Avec tokens directs
    python scripts/fetch_fiesta_weapons.py --match-id <ID> \
        --spartan-token "v4=..." --clearance-token "..."

    # Ou via variables d'environnement (SPNKR_SPARTAN_TOKEN, SPNKR_CLEARANCE_TOKEN)
    python scripts/fetch_fiesta_weapons.py --match-id <ID>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import aiohttp
except ImportError:
    print("ERREUR: aiohttp non installé")
    sys.exit(1)


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


async def fetch_match_stats(
    match_id: str,
    spartan_token: str,
    clearance_token: str,
) -> dict | None:
    """Récupère les stats détaillées d'un match."""
    headers = {
        "accept": "application/json",
        "x-343-authorization-spartan": spartan_token,
        "343-clearance": clearance_token,
        "user-agent": "openspartan-graph/weapon-analysis",
    }

    url = f"https://halostats.svc.halowaypoint.com/hi/matches/{match_id}/stats"

    async with aiohttp.ClientSession(
        headers=headers, timeout=aiohttp.ClientTimeout(total=60)
    ) as session:
        async with session.get(url) as resp:
            if resp.status >= 400:
                text = await resp.text()
                print(f"Erreur HTTP {resp.status}: {text[:500]}")
                return None

            return await resp.json()


def extract_all_weapons(match_data: dict) -> dict[str, dict]:
    """Extrait les weapon stats de tous les joueurs."""
    all_weapons = {}

    for player in match_data.get("Results", []):
        # Obtenir le gamertag
        player_id = player.get("PlayerId", "")

        team_stats = player.get("PlayerTeamStats", [])
        if not team_stats:
            continue

        stats = team_stats[0].get("Stats", {})
        core = stats.get("CoreStats", {})
        breakdowns = core.get("Breakdowns", {})

        for w in breakdowns.get("Weapons", []):
            name = w.get("EquippedWeaponName", "Unknown")
            kills = w.get("Kills", 0)
            headshots = w.get("Headshots", 0)
            damage = w.get("DamageDealt", 0)

            if name not in all_weapons:
                all_weapons[name] = {
                    "name": name,
                    "total_kills": 0,
                    "total_headshots": 0,
                    "total_damage": 0,
                    "players_used": 0,
                }

            all_weapons[name]["total_kills"] += kills
            all_weapons[name]["total_headshots"] += headshots
            all_weapons[name]["total_damage"] += damage
            if kills > 0 or damage > 100:
                all_weapons[name]["players_used"] += 1

    return all_weapons


async def main():
    parser = argparse.ArgumentParser(description="Récupérer les weapon stats d'un match Fiesta")
    parser.add_argument("--match-id", required=True, help="ID du match")
    parser.add_argument("--spartan-token", help="Token Spartan (ou SPNKR_SPARTAN_TOKEN)")
    parser.add_argument("--clearance-token", help="Token Clearance (ou SPNKR_CLEARANCE_TOKEN)")
    parser.add_argument("--output", type=Path, help="Sauvegarder en JSON")

    args = parser.parse_args()
    _load_dotenv_if_present()

    # Obtenir les tokens
    spartan_token = args.spartan_token or os.environ.get("SPNKR_SPARTAN_TOKEN")
    clearance_token = args.clearance_token or os.environ.get("SPNKR_CLEARANCE_TOKEN")

    if not spartan_token or not clearance_token:
        print("ERREUR: Tokens manquants.")
        print("Fournissez --spartan-token et --clearance-token")
        print("ou définissez SPNKR_SPARTAN_TOKEN et SPNKR_CLEARANCE_TOKEN")
        return 1

    print(f"Récupération des stats du match {args.match_id}...")
    print()

    match_data = await fetch_match_stats(args.match_id, spartan_token, clearance_token)

    if not match_data:
        print("Aucune donnée récupérée")
        return 1

    # Sauvegarder le raw si demandé
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(match_data, f, ensure_ascii=False, indent=2)
        print(f"Données brutes sauvegardées: {args.output}")
        print()

    # Extraire les weapons
    weapons = extract_all_weapons(match_data)

    print("=== ARMES UTILISÉES DANS LE MATCH ===")
    print()
    print(f"{'Arme':<30} {'Kills':>6} {'HS':>4} {'Dégâts':>10}")
    print("-" * 55)

    for w in sorted(weapons.values(), key=lambda x: -x["total_kills"]):
        if w["total_kills"] > 0 or w["total_damage"] > 500:
            print(
                f"{w['name']:<30} {w['total_kills']:>6} {w['total_headshots']:>4} "
                f"{w['total_damage']:>10.0f}"
            )

    print()
    print(f"Total armes différentes: {len([w for w in weapons.values() if w['total_kills'] > 0])}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
