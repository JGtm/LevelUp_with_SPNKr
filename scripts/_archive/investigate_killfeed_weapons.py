#!/usr/bin/env python3
"""
Script d'investigation complet pour le kill feed et les weapon IDs.

Ce script explore toutes les pistes identifiées dans KILL_FEED_WEAPON_INVESTIGATION.md :
1. Assets Discovery UGC (Weapons, WeaponIcons, etc.)
2. Police d'icônes (Icon Font)
3. Kill Feed dans Film Chunks (extra bytes)
4. API Match Stats non documentée
5. Theatre Mode extraction

Usage:
    python scripts/investigate_killfeed_weapons.py --match-id <ID> --phase all
    python scripts/investigate_killfeed_weapons.py --explore-assets
    python scripts/investigate_killfeed_weapons.py --analyze-chunks --match-id <ID>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
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


# =============================================================================
# Phase 1 : Exploration Assets Discovery UGC
# =============================================================================


async def phase1_explore_discovery_ugc(client: SPNKrAPIClient) -> dict[str, Any]:
    """Phase 1 : Explorer les assets Discovery UGC pour les armes."""
    print("\n" + "=" * 70)
    print("PHASE 1 : EXPLORATION ASSETS DISCOVERY UGC")
    print("=" * 70 + "\n")

    results = {
        "known_types": [],
        "hypothetical_types": [],
        "tested_endpoints": [],
        "errors": [],
    }

    # Types connus
    known_types = ["Maps", "Playlists", "PlaylistMapModePairs", "GameVariants"]
    results["known_types"] = known_types

    print("Types d'assets connus:")
    for asset_type in known_types:
        print(f"  ✅ {asset_type}")

    # Types hypothétiques pour les armes
    hypothetical_types = [
        "Weapons",
        "WeaponIcons",
        "WeaponDefinitions",
        "Equipment",
        "Vehicles",
        "Medals",
    ]
    results["hypothetical_types"] = hypothetical_types

    print("\nTypes hypothétiques à explorer:")
    for asset_type in hypothetical_types:
        print(f"  ❓ {asset_type}")

    # Explorer le client SPNKr
    print("\n=== EXPLORATION CLIENT SPNKR ===\n")
    try:
        spnkr_client = client.client
        discovery_ugc = spnkr_client.discovery_ugc

        # Lister les méthodes disponibles
        print("Méthodes disponibles sur discovery_ugc:")
        methods = [m for m in dir(discovery_ugc) if not m.startswith("_")]
        for method in methods:
            print(f"  - {method}")
            results["tested_endpoints"].append(method)

        # Note: Pour tester réellement, il faudrait des asset IDs valides
        print("\n⚠️  Note: Pour tester les endpoints hypothétiques, il faudrait:")
        print("  1. Trouver des weapon IDs depuis les matchs")
        print("  2. Essayer de les utiliser comme asset_id dans get_asset()")
        print("  3. Tester avec différents version_id")

    except Exception as e:
        error_msg = f"Erreur lors de l'exploration: {e}"
        print(f"❌ {error_msg}")
        results["errors"].append(error_msg)

    return results


# =============================================================================
# Phase 2 : Analyse Kill Feed visuel
# =============================================================================


async def phase2_analyze_killfeed_visual(client: SPNKrAPIClient, match_id: str) -> dict[str, Any]:
    """Phase 2 : Analyser le kill feed visuel et corréler avec les kills."""
    print("\n" + "=" * 70)
    print("PHASE 2 : ANALYSE KILL FEED VISUEL")
    print("=" * 70 + "\n")

    results = {
        "match_id": match_id,
        "events_found": 0,
        "kills_found": 0,
        "weapon_fields": [],
        "icon_fields": [],
        "raw_json_structure": {},
    }

    try:
        match_data = await client.get_match_data(
            match_id, xuids=[], with_highlight_events=True, with_skill=False
        )

        if not match_data:
            print("❌ Impossible de récupérer les données du match")
            results["errors"] = ["Impossible de récupérer les données du match"]
            return results

        events = match_data.highlight_events
        results["events_found"] = len(events)

        kills = [e for e in events if e.get("type_hint") == 50]
        results["kills_found"] = len(kills)

        print(f"Events totaux: {len(events)}")
        print(f"Kills trouvés: {len(kills)}")

        # Analyser la structure des events
        if kills:
            sample_kill = kills[0]
            results["raw_json_structure"] = sample_kill

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
                print(f"Clés dans raw_json: {list(raw_json.keys())}")

                # Chercher récursivement
                def find_fields(obj: Any, path: str = "") -> list[str]:
                    paths = []
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            current_path = f"{path}.{k}" if path else k
                            if "weapon" in k.lower() or "icon" in k.lower():
                                paths.append(current_path)
                            paths.extend(find_fields(v, current_path))
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            paths.extend(find_fields(item, f"{path}[{i}]"))
                    return paths

                weapon_paths = find_fields(raw_json)
                if weapon_paths:
                    print("⚠️  Chemins potentiellement liés aux armes/icônes:")
                    for p in weapon_paths[:20]:
                        print(f"  - {p}")

        # Analyser les stats du match
        print("\n=== ANALYSE STATS MATCH ===\n")
        stats_json = match_data.stats_json
        if stats_json:

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
                print("⚠️  Chemins potentiellement liés aux armes dans stats:")
                for p in weapon_paths[:20]:
                    print(f"  - {p}")
            else:
                print("❌ Aucun champ 'weapon' ou 'icon' trouvé dans les stats")

        print("\n⚠️  Actions manuelles nécessaires:")
        print("  1. Capturer des screenshots du kill feed pendant un match")
        print("  2. Identifier les icônes d'armes visibles")
        print("  3. Corréler avec les kills extraits des highlight events")
        print("  4. Créer un mapping icône → arme")

    except Exception as e:
        error_msg = f"Erreur lors de l'analyse: {e}"
        print(f"❌ {error_msg}")
        results["errors"] = [error_msg]
        import traceback

        traceback.print_exc()

    return results


# =============================================================================
# Phase 3 : Extraction depuis Film Chunks
# =============================================================================


async def phase3_extract_film_chunks(client: SPNKrAPIClient, match_id: str) -> dict[str, Any]:
    """Phase 3 : Extraire et analyser les extra bytes des film chunks."""
    print("\n" + "=" * 70)
    print("PHASE 3 : EXTRACTION FILM CHUNKS (EXTRA BYTES)")
    print("=" * 70 + "\n")

    results = {
        "match_id": match_id,
        "weapon_ids_found": {},
        "extra_bytes_patterns": [],
        "known_weapon_ids": {},
    }

    try:
        # Charger les weapon IDs connus
        try:
            from src.data.weapon_ids import WEAPON_IDS

            results["known_weapon_ids"] = WEAPON_IDS
            print("Weapon IDs déjà identifiés:")
            for wid, name in WEAPON_IDS.items():
                print(f"  ✅ 0x{wid:04X} ({wid}) = {name}")
        except ImportError:
            print("⚠️  Module weapon_ids non disponible")

        # Récupérer les highlight events
        match_data = await client.get_match_data(
            match_id, xuids=[], with_highlight_events=True, with_skill=False
        )

        if not match_data or not match_data.highlight_events:
            print("❌ Aucun highlight event disponible")
            results["errors"] = ["Aucun highlight event disponible"]
            return results

        events = match_data.highlight_events
        kills = [e for e in events if e.get("type_hint") == 50]

        print(f"\nKills trouvés: {len(kills)}")

        # Analyser les patterns dans les extra bytes
        print("\n=== ANALYSE EXTRA BYTES ===\n")
        print("Hypothèse: Les extra bytes (position 72+) pourraient contenir")
        print("un weapon icon ID plutôt qu'un weapon ID brut.\n")

        # Compter les weapon IDs trouvés
        weapon_id_counts = defaultdict(int)
        for kill in kills:
            raw_json = kill.get("raw_json", {})
            if isinstance(raw_json, dict):
                # Chercher des patterns potentiels
                for key, value in raw_json.items():
                    if isinstance(value, (int, str)):
                        if "weapon" in key.lower():
                            weapon_id_counts[value] += 1
                            print(f"  ⚠️  Champ suspect: {key} = {value}")

        results["weapon_ids_found"] = dict(weapon_id_counts)

        print("\n⚠️  Actions nécessaires:")
        print("  1. Télécharger les film chunks bruts du match")
        print("  2. Extraire tous les events kill avec leurs extra bytes (position 72+)")
        print("  3. Chercher des patterns qui pourraient être des icon IDs")
        print("  4. Comparer avec les icônes visibles dans le kill feed")

        print("\n💡 Utiliser les scripts existants:")
        print("  - scripts/extract_events_v3.py")
        print("  - scripts/analyze_chunks_bitshifted.py")

    except Exception as e:
        error_msg = f"Erreur lors de l'extraction: {e}"
        print(f"❌ {error_msg}")
        results["errors"] = [error_msg]
        import traceback

        traceback.print_exc()

    return results


# =============================================================================
# Phase 4 : Exploration API non documentée
# =============================================================================


async def phase4_explore_undocumented_api(client: SPNKrAPIClient, match_id: str) -> dict[str, Any]:
    """Phase 4 : Explorer les endpoints API non documentés."""
    print("\n" + "=" * 70)
    print("PHASE 4 : EXPLORATION API NON DOCUMENTÉE")
    print("=" * 70 + "\n")

    results = {
        "match_id": match_id,
        "endpoints_tested": [],
        "hidden_fields": [],
        "errors": [],
    }

    try:
        # Récupérer les données complètes du match
        match_data = await client.get_match_data(
            match_id, xuids=[], with_highlight_events=True, with_skill=False
        )

        if not match_data:
            print("❌ Impossible de récupérer les données du match")
            results["errors"] = ["Impossible de récupérer les données du match"]
            return results

        # Inspecter les réponses complètes
        print("=== INSPECTION RÉPONSES API COMPLÈTES ===\n")

        stats_json = match_data.stats_json
        if stats_json:
            print("Structure complète des stats (premiers niveaux):")
            for key in list(stats_json.keys())[:20]:
                print(f"  - {key}")

            # Chercher des champs cachés
            def find_all_keys(obj: Any, path: str = "") -> list[str]:
                keys = []
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        current_path = f"{path}.{k}" if path else k
                        keys.append(current_path)
                        keys.extend(find_all_keys(v, current_path))
                elif isinstance(obj, list) and obj:
                    keys.extend(find_all_keys(obj[0], f"{path}[0]"))
                return keys

            all_keys = find_all_keys(stats_json)
            results["hidden_fields"] = all_keys[:50]  # Limiter

            print(f"\nTotal de champs trouvés: {len(all_keys)}")
            print("\nChamps suspects (contenant 'weapon', 'icon', 'killfeed'):")
            suspect_keys = [
                k
                for k in all_keys
                if any(term in k.lower() for term in ["weapon", "icon", "killfeed", "event"])
            ]
            for key in suspect_keys[:20]:
                print(f"  ⚠️  {key}")

        # Tester des endpoints hypothétiques
        print("\n=== ENDPOINTS HYPOTHÉTIQUES ===\n")
        hypothetical_endpoints = [
            f"/hi/matches/{match_id}/killfeed",
            f"/hi/matches/{match_id}/events",
            f"/hi/matches/{match_id}/weapons",
        ]

        print("Endpoints hypothétiques à tester:")
        for endpoint in hypothetical_endpoints:
            print(f"  ❓ {endpoint}")
            results["endpoints_tested"].append(endpoint)

        print("\n⚠️  Note: Ces endpoints nécessitent un accès direct au client HTTP")
        print("   et pourraient ne pas exister dans l'API publique.")

    except Exception as e:
        error_msg = f"Erreur lors de l'exploration: {e}"
        print(f"❌ {error_msg}")
        results["errors"] = [error_msg]
        import traceback

        traceback.print_exc()

    return results


# =============================================================================
# Phase 5 : Theatre Mode
# =============================================================================


async def phase5_explore_theatre_mode(client: SPNKrAPIClient, match_id: str) -> dict[str, Any]:
    """Phase 5 : Explorer le Theatre Mode pour extraire le kill feed."""
    print("\n" + "=" * 70)
    print("PHASE 5 : EXPLORATION THEATRE MODE")
    print("=" * 70 + "\n")

    results = {
        "match_id": match_id,
        "film_manifest": None,
        "chunk_types": [],
        "bootstrap_data": None,
        "errors": [],
    }

    try:
        # Récupérer le manifest du film
        print("=== RÉCUPÉRATION FILM MANIFEST ===\n")
        try:
            spnkr_client = client.client
            # Essayer d'accéder au manifest
            # Note: SPNKr pourrait avoir une méthode pour ça
            print("⚠️  Accès au film manifest nécessite:")
            print("  1. Endpoint: /hi/films/matches/{matchId}/spectate")
            print("  2. Parser les chunks disponibles")
            print("  3. Analyser les chunks type 1 (bootstrap)")

            # Chercher dans le client SPNKr
            if hasattr(spnkr_client, "film"):
                film_client = spnkr_client.film
                print("\nMéthodes disponibles sur film:")
                methods = [m for m in dir(film_client) if not m.startswith("_")]
                for method in methods:
                    print(f"  - {method}")

        except Exception as e:
            error_msg = f"Erreur lors de l'exploration Theatre Mode: {e}"
            print(f"❌ {error_msg}")
            results["errors"].append(error_msg)

        print("\n⚠️  Questions à explorer:")
        print("  1. Comment le Theatre Mode génère-t-il le kill feed ?")
        print("  2. Y a-t-il un endpoint API pour le Theatre Mode ?")
        print("  3. Peut-on extraire ces données depuis les film chunks type 1 (bootstrap) ?")

        print("\n💡 Utiliser les scripts existants:")
        print("  - scripts/refetch_film_roster.py")
        print("  - scripts/extract_events_v3.py")

    except Exception as e:
        error_msg = f"Erreur lors de l'exploration: {e}"
        print(f"❌ {error_msg}")
        results["errors"] = [error_msg]
        import traceback

        traceback.print_exc()

    return results


# =============================================================================
# Main
# =============================================================================


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Investigation complète du kill feed et weapon IDs"
    )
    parser.add_argument("--match-id", help="ID du match à analyser")
    parser.add_argument(
        "--phase",
        choices=["1", "2", "3", "4", "5", "all"],
        default="all",
        help="Phase à exécuter (1=Assets, 2=KillFeed, 3=Chunks, 4=API, 5=Theatre, all=tout)",
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
            all_results["phase1"] = await phase1_explore_discovery_ugc(client)

        # Phases nécessitant un match_id
        if args.match_id:
            if args.phase in ("2", "all"):
                all_results["phase2"] = await phase2_analyze_killfeed_visual(client, args.match_id)

            if args.phase in ("3", "all"):
                all_results["phase3"] = await phase3_extract_film_chunks(client, args.match_id)

            if args.phase in ("4", "all"):
                all_results["phase4"] = await phase4_explore_undocumented_api(client, args.match_id)

            if args.phase in ("5", "all"):
                all_results["phase5"] = await phase5_explore_theatre_mode(client, args.match_id)
        else:
            if args.phase in ("2", "3", "4", "5"):
                print(f"\n❌ --match-id requis pour la phase {args.phase}")

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
        else:
            print("  ✅ Complétée")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
