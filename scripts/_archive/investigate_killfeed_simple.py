#!/usr/bin/env python3
"""
Script d'investigation simplifié pour le kill feed et weapon IDs.

Version standalone qui évite les imports complexes du projet.

Usage:
    python scripts/investigate_killfeed_simple.py --match-id <ID>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ajouter le chemin du projet
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import minimal - seulement ce qui est nécessaire
try:
    from src.data.sync.api_client import SPNKrAPIClient
except ImportError as e:
    print(f"ERREUR: Impossible d'importer SPNKrAPIClient: {e}")
    print("Assurez-vous que les dépendances sont installées.")
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


async def explore_discovery_ugc(client: SPNKrAPIClient) -> dict[str, Any]:
    """Explore les assets Discovery UGC."""
    print("\n" + "=" * 70)
    print("PHASE 1 : EXPLORATION ASSETS DISCOVERY UGC")
    print("=" * 70 + "\n")

    results = {
        "known_types": ["Maps", "Playlists", "PlaylistMapModePairs", "GameVariants"],
        "hypothetical_types": [
            "Weapons",
            "WeaponIcons",
            "WeaponDefinitions",
            "Equipment",
            "Vehicles",
            "Medals",
        ],
        "methods_found": [],
        "errors": [],
    }

    print("Types d'assets connus:")
    for asset_type in results["known_types"]:
        print(f"  ✅ {asset_type}")

    print("\nTypes hypothétiques à explorer:")
    for asset_type in results["hypothetical_types"]:
        print(f"  ❓ {asset_type}")

    try:
        spnkr_client = client.client
        discovery_ugc = spnkr_client.discovery_ugc

        print("\n=== MÉTHODES DISPONIBLES SUR DISCOVERY_UGC ===\n")
        methods = [m for m in dir(discovery_ugc) if not m.startswith("_")]
        for method in methods:
            print(f"  - {method}")
            results["methods_found"].append(method)

        print("\n⚠️  Note: Pour tester les types hypothétiques, il faudrait:")
        print("  1. Trouver des weapon IDs depuis les matchs")
        print("  2. Essayer de les utiliser comme asset_id dans get_asset()")

    except Exception as e:
        error_msg = f"Erreur lors de l'exploration: {e}"
        print(f"❌ {error_msg}")
        results["errors"].append(error_msg)
        import traceback

        traceback.print_exc()

    return results


async def analyze_match_events(client: SPNKrAPIClient, match_id: str) -> dict[str, Any]:
    """Analyse les events d'un match."""
    print("\n" + "=" * 70)
    print("PHASE 2 : ANALYSE EVENTS MATCH")
    print("=" * 70 + "\n")

    results = {
        "match_id": match_id,
        "events_found": 0,
        "kills_found": 0,
        "deaths_found": 0,
        "weapon_fields": [],
        "icon_fields": [],
        "sample_kill": None,
        "errors": [],
    }

    try:
        match_data = await client.get_match_data(
            match_id, xuids=[], with_highlight_events=True, with_skill=False
        )

        if not match_data:
            print("❌ Impossible de récupérer les données du match")
            results["errors"].append("Impossible de récupérer les données du match")
            return results

        events = match_data.highlight_events or []
        results["events_found"] = len(events)

        kills = [e for e in events if e.get("type_hint") == 50]
        deaths = [e for e in events if e.get("type_hint") == 20]

        results["kills_found"] = len(kills)
        results["deaths_found"] = len(deaths)

        print(f"Events totaux: {len(events)}")
        print(f"Kills: {len(kills)}")
        print(f"Deaths: {len(deaths)}")

        if kills:
            sample_kill = kills[0]
            results["sample_kill"] = sample_kill

            print("\n=== STRUCTURE D'UN EVENT KILL ===\n")
            print(json.dumps(sample_kill, indent=2, ensure_ascii=False))

            # Chercher des champs liés aux armes/icônes
            all_keys = list(sample_kill.keys())
            weapon_keys = [k for k in all_keys if "weapon" in k.lower()]
            icon_keys = [k for k in all_keys if "icon" in k.lower()]

            results["weapon_fields"] = weapon_keys
            results["icon_fields"] = icon_keys

            if weapon_keys:
                print(f"\n⚠️  Champs potentiellement liés aux armes: {weapon_keys}")
            else:
                print("\n❌ Aucun champ 'weapon' trouvé dans les events")

            if icon_keys:
                print(f"\n⚠️  Champs potentiellement liés aux icônes: {icon_keys}")
            else:
                print("\n❌ Aucun champ 'icon' trouvé dans les events")

            # Analyser raw_json si disponible
            raw_json = sample_kill.get("raw_json", {})
            if isinstance(raw_json, dict):
                print("\n=== ANALYSE RAW_JSON ===\n")
                print(f"Clés dans raw_json: {list(raw_json.keys())[:20]}")

        # Charger les weapon IDs connus
        print("\n=== WEAPON IDs CONNUS ===\n")
        try:
            from src.data.weapon_ids import WEAPON_IDS

            print(f"Weapon IDs déjà identifiés: {len(WEAPON_IDS)}")
            for wid, name in WEAPON_IDS.items():
                print(f"  ✅ 0x{wid:04X} ({wid}) = {name}")
            results["known_weapon_ids"] = WEAPON_IDS
        except ImportError:
            print("⚠️  Module weapon_ids non disponible")
            results["known_weapon_ids"] = {}

    except Exception as e:
        error_msg = f"Erreur lors de l'analyse: {e}"
        print(f"❌ {error_msg}")
        results["errors"].append(error_msg)
        import traceback

        traceback.print_exc()

    return results


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Investigation simplifiée du kill feed et weapon IDs"
    )
    parser.add_argument("--match-id", help="ID du match à analyser")
    parser.add_argument(
        "--phase",
        choices=["1", "2", "all"],
        default="all",
        help="Phase à exécuter (1=Assets, 2=Events, all=tout)",
    )
    parser.add_argument(
        "--output",
        help="Fichier JSON pour sauvegarder les résultats",
    )

    args = parser.parse_args()
    _load_dotenv_if_present()

    all_results = {}

    async with SPNKrAPIClient() as client:
        # Phase 1 : Assets Discovery UGC
        if args.phase in ("1", "all"):
            all_results["phase1"] = await explore_discovery_ugc(client)

        # Phase 2 : Analyse events (nécessite match_id)
        if args.match_id:
            if args.phase in ("2", "all"):
                all_results["phase2"] = await analyze_match_events(client, args.match_id)
        else:
            if args.phase == "2":
                print("\n❌ --match-id requis pour la phase 2")

    # Sauvegarder les résultats
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\n✅ Résultats sauvegardés dans {output_path}")

    # Résumé
    print("\n" + "=" * 70)
    print("RÉSUMÉ DE L'INVESTIGATION")
    print("=" * 70 + "\n")

    for phase_name, phase_results in all_results.items():
        print(f"{phase_name.upper()}:")
        if "errors" in phase_results and phase_results["errors"]:
            print(f"  ❌ Erreurs: {len(phase_results['errors'])}")
            for error in phase_results["errors"]:
                print(f"     - {error}")
        else:
            print("  ✅ Complétée")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
