#!/usr/bin/env python3
"""
Exploration du kill feed pour identifier les weapon IDs.

Hypothèse : Le kill feed affiche les icônes d'armes, donc les données doivent
être disponibles quelque part (assets, film chunks, ou API).

Usage:
    python scripts/explore_killfeed_weapons.py --match-id <ID>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

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


async def explore_discovery_ugc(client: SPNKrAPIClient) -> None:
    """Explore les types d'assets disponibles dans Discovery UGC."""
    print("=== EXPLORATION DISCOVERY UGC ===\n")

    # Types connus
    known_types = ["Maps", "Playlists", "PlaylistMapModePairs", "GameVariants"]

    print("Types d'assets connus:")
    for asset_type in known_types:
        print(f"  - {asset_type}")

    print("\nRecherche de types non documentés...")
    print("(Note: L'API Discovery UGC ne semble pas avoir d'endpoint de listing)")

    # Hypothétiques types pour les armes
    hypothetical_types = [
        "Weapons",
        "WeaponIcons",
        "WeaponDefinitions",
        "Equipment",
        "Vehicles",
        "Medals",
    ]

    print("\nTypes hypothétiques à explorer:")
    for asset_type in hypothetical_types:
        print(f"  - {asset_type} (non testé)")

    # Tester l'accès direct au client SPNKr pour explorer les méthodes disponibles
    print("\n=== EXPLORATION CLIENT SPNKR ===\n")
    try:
        spnkr_client = client.client
        discovery_ugc = spnkr_client.discovery_ugc

        # Lister les méthodes disponibles
        print("Méthodes disponibles sur discovery_ugc:")
        methods = [m for m in dir(discovery_ugc) if not m.startswith("_")]
        for method in methods:
            print(f"  - {method}")

        # Essayer d'accéder à des endpoints hypothétiques
        print("\n=== TEST ENDPOINTS HYPOTHÉTIQUES ===\n")
        print("Note: Ces tests nécessitent des IDs d'assets valides.")
        print("Pour tester, il faudrait:")
        print("1. Trouver des weapon IDs depuis les matchs")
        print("2. Essayer de les utiliser comme asset_id dans get_asset()")

    except Exception as e:
        print(f"⚠️  Erreur lors de l'exploration: {e}")


async def analyze_match_killfeed(client: SPNKrAPIClient, match_id: str) -> None:
    """Analyse les données d'un match pour extraire les infos du kill feed."""
    print(f"\n=== ANALYSE KILL FEED - MATCH {match_id} ===\n")

    # Récupérer les données du match
    match_data = await client.get_match_data(
        match_id, xuids=[], with_highlight_events=True, with_skill=False
    )

    if not match_data:
        print("❌ Impossible de récupérer les données du match")
        return

    stats_json = match_data.stats_json
    highlight_events = match_data.highlight_events

    print(f"Highlight events: {len(highlight_events)}")

    # Analyser les events kill
    kills = [e for e in highlight_events if e.get("type_hint") == 50]
    deaths = [e for e in highlight_events if e.get("type_hint") == 20]

    print(f"Kills: {len(kills)}")
    print(f"Deaths: {len(deaths)}")

    # Chercher des patterns dans les events kill
    print("\n=== ANALYSE DES EVENTS KILL ===\n")

    # Extraire tous les champs disponibles
    if kills:
        sample_kill = kills[0]
        print("Structure d'un event kill:")
        print(json.dumps(sample_kill, indent=2, ensure_ascii=False))

        # Chercher des champs potentiellement liés aux armes
        weapon_related_keys = [
            k for k in sample_kill.keys() if "weapon" in k.lower() or "icon" in k.lower()
        ]
        if weapon_related_keys:
            print(f"\n⚠️  Champs potentiellement liés aux armes: {weapon_related_keys}")
        else:
            print("\n❌ Aucun champ 'weapon' ou 'icon' trouvé dans les events")

    # Analyser les stats du match pour voir s'il y a des données supplémentaires
    print("\n=== ANALYSE STATS MATCH ===\n")

    if stats_json:
        # Chercher récursivement des champs liés aux armes
        def find_weapon_fields(obj: Any, path: str = "") -> list[str]:
            paths = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    current_path = f"{path}.{k}" if path else k
                    if "weapon" in k.lower() or "icon" in k.lower():
                        paths.append(current_path)
                    paths.extend(find_weapon_fields(v, current_path))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    paths.extend(find_weapon_fields(item, f"{path}[{i}]"))
            return paths

        weapon_paths = find_weapon_fields(stats_json)
        if weapon_paths:
            print("⚠️  Chemins potentiellement liés aux armes:")
            for p in weapon_paths[:20]:  # Limiter l'affichage
                print(f"  - {p}")
        else:
            print("❌ Aucun champ 'weapon' ou 'icon' trouvé dans les stats")


async def explore_film_chunks_killfeed(client: SPNKrAPIClient, match_id: str) -> None:
    """Explore les film chunks pour trouver des données du kill feed."""
    print("\n=== EXPLORATION FILM CHUNKS POUR KILL FEED ===\n")

    print("Hypothèse: Les extra bytes (position 72+) pourraient contenir")
    print("un weapon icon ID plutôt qu'un weapon ID brut.\n")

    try:
        # Récupérer les highlight events avec leurs données brutes
        match_data = await client.get_match_data(
            match_id, xuids=[], with_highlight_events=True, with_skill=False
        )

        if not match_data or not match_data.highlight_events:
            print("❌ Aucun highlight event disponible")
            return

        events = match_data.highlight_events
        kills = [e for e in events if e.get("type_hint") == 50]

        print(f"Kills trouvés: {len(kills)}")

        # Analyser les extra bytes si disponibles
        print("\n=== ANALYSE EXTRA BYTES ===\n")

        # Chercher des patterns dans les events
        weapon_ids_found = {}
        for kill in kills[:20]:  # Analyser les 20 premiers
            # Chercher des champs potentiels
            raw_json = kill.get("raw_json", {})
            if isinstance(raw_json, dict):
                # Chercher des bytes ou patterns
                for key, value in raw_json.items():
                    if isinstance(value, (int, str)) and (
                        "weapon" in key.lower() or "icon" in key.lower()
                    ):
                        print(f"  ⚠️  Champ suspect: {key} = {value}")

        # Analyser les weapon IDs connus depuis les chunks type 3
        print("\n=== WEAPON IDs CONNUS ===\n")
        try:
            from src.data.weapon_ids import WEAPON_IDS

            print(f"Weapon IDs déjà identifiés: {len(WEAPON_IDS)}")
            for wid, name in WEAPON_IDS.items():
                print(f"  - 0x{wid:04X} ({wid}) = {name}")
        except ImportError:
            print("⚠️  Module weapon_ids non disponible")

        print("\nActions à faire:")
        print("1. Télécharger les film chunks bruts du match")
        print("2. Extraire tous les events kill avec leurs extra bytes (position 72+)")
        print("3. Comparer les patterns avec les icônes visibles dans le kill feed")
        print("4. Chercher des corrélations weapon_id → icon_id")

    except Exception as e:
        print(f"❌ Erreur lors de l'exploration: {e}")
        import traceback

        traceback.print_exc()


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explorer le kill feed pour identifier les weapon IDs"
    )
    parser.add_argument("--match-id", help="ID du match à analyser")
    parser.add_argument("--explore-assets", action="store_true", help="Explorer Discovery UGC")

    args = parser.parse_args()
    _load_dotenv_if_present()

    async with SPNKrAPIClient() as client:
        if args.explore_assets:
            await explore_discovery_ugc(client)

        if args.match_id:
            await analyze_match_killfeed(client, args.match_id)
            await explore_film_chunks_killfeed(client, args.match_id)
        else:
            print("Usage: python scripts/explore_killfeed_weapons.py --match-id <ID>")
            print("       python scripts/explore_killfeed_weapons.py --explore-assets")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
