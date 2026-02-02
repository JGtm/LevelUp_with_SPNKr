#!/usr/bin/env python3
"""
Script pour récupérer les weapon stats d'un match via l'API Halo.
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


async def get_tokens() -> tuple[str, str]:
    """Obtient les tokens d'authentification."""
    from spnkr import AzureApp, refresh_player_tokens

    azure_client_id = os.environ.get("SPNKR_AZURE_CLIENT_ID")
    azure_client_secret = os.environ.get("SPNKR_AZURE_CLIENT_SECRET")
    azure_redirect_uri = os.environ.get("SPNKR_AZURE_REDIRECT_URI", "https://localhost")
    oauth_refresh_token = os.environ.get("SPNKR_OAUTH_REFRESH_TOKEN")

    if not all([azure_client_id, azure_client_secret, oauth_refresh_token]):
        raise SystemExit("Tokens Azure manquants dans .env.local")

    app = AzureApp(azure_client_id, azure_client_secret, azure_redirect_uri)

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
        player = await refresh_player_tokens(session, app, oauth_refresh_token)
        return str(player.spartan_token.token), str(player.clearance_token.token)


async def fetch_match_stats(match_id: str, xuid: str) -> dict:
    """Récupère les stats détaillées d'un match pour un joueur."""
    _load_dotenv_if_present()

    spartan_token, clearance_token = await get_tokens()

    headers = {
        "accept": "application/json",
        "x-343-authorization-spartan": spartan_token,
        "343-clearance": clearance_token,
        "user-agent": "openspartan-graph/weapon-analysis",
    }

    # URL pour les stats détaillées du match
    url = f"https://halostats.svc.halowaypoint.com/hi/matches/{match_id}/stats"

    async with aiohttp.ClientSession(
        headers=headers, timeout=aiohttp.ClientTimeout(total=60)
    ) as session:
        async with session.get(url) as resp:
            if resp.status >= 400:
                text = await resp.text()
                print(f"Erreur HTTP {resp.status}: {text[:500]}")
                return {}

            data = await resp.json()
            return data


def extract_player_weapons(match_data: dict, xuid: str) -> list[dict]:
    """Extrait les weapon stats d'un joueur spécifique."""
    weapons = []

    # Chercher dans Results/MatchStats
    results = match_data.get("Results", [])

    for player in results:
        player_xuid = player.get("PlayerId", "")
        # XUID peut être "xuid(123456)" ou juste le nombre
        if str(xuid) in str(player_xuid):
            # Trouver les stats
            team_stats = player.get("PlayerTeamStats", [])
            if team_stats:
                stats = team_stats[0].get("Stats", {})
                core = stats.get("CoreStats", {})
                breakdowns = core.get("Breakdowns", {})

                for w in breakdowns.get("Weapons", []):
                    weapons.append(
                        {
                            "name": w.get("EquippedWeaponName", "Unknown"),
                            "kills": w.get("Kills", 0),
                            "headshots": w.get("Headshots", 0),
                            "damage_dealt": w.get("DamageDealt", 0),
                            "shots_fired": w.get("ShotsFired", 0),
                            "shots_hit": w.get("ShotsHit", 0),
                        }
                    )
            break

    return sorted(weapons, key=lambda x: x["kills"], reverse=True)


async def main():
    parser = argparse.ArgumentParser(description="Récupérer les weapon stats d'un match")
    parser.add_argument("--match-id", required=True, help="ID du match")
    parser.add_argument("--xuid", default="2533274823110022", help="XUID du joueur (défaut: JGtm)")
    parser.add_argument("--output", type=Path, help="Sauvegarder en JSON")

    args = parser.parse_args()

    print(f"Récupération des stats du match {args.match_id}...")

    match_data = await fetch_match_stats(args.match_id, args.xuid)

    if not match_data:
        print("Aucune donnée récupérée")
        return 1

    # Sauvegarder le raw si demandé
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(match_data, f, ensure_ascii=False, indent=2)
        print(f"Données brutes sauvegardées: {args.output}")

    # Extraire les weapons
    weapons = extract_player_weapons(match_data, args.xuid)

    print(f"\nArmes utilisées par XUID {args.xuid}:")
    for w in weapons:
        if w["kills"] > 0 or w["damage_dealt"] > 100:
            print(
                f"  - {w['name']}: {w['kills']} kills, {w['headshots']} headshots, {w['damage_dealt']:.0f} dmg"
            )

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
