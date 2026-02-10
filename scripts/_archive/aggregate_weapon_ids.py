#!/usr/bin/env python3
"""
Agrège tous les weapon IDs uniques des matchs analysés.

Output: JSON avec pour chaque weapon_id inconnu :
- weapon_id (hex et decimal)
- match_id
- timestamp_sec (converti depuis ticks Windows)
- gamertag du killer (si lisible)
- nombre d'occurrences total
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

# Import du mapping depuis src/data si disponible
try:
    from src.data.weapon_ids import TICKS_PER_SECOND
    from src.data.weapon_ids import WEAPON_IDS as KNOWN_WEAPONS
except ImportError:
    # Fallback si le module n'est pas accessible
    KNOWN_WEAPONS = {
        0xE02E: "Sidekick",  # 57390
        0x7017: "MA40 AR",  # 28695
    }
    TICKS_PER_SECOND = 10_000_000


def extract_weapon_id(extra_bytes: list[int]) -> int | None:
    """
    Extrait le weapon_id des extra_bytes.

    Le weapon ID est aux bytes 2-3 (offset 74-75 dans l'event complet).
    Format: uint16 little-endian
    """
    if len(extra_bytes) < 4:
        return None
    return extra_bytes[2] + extra_bytes[3] * 256  # little-endian


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Agrège les weapon IDs uniques depuis les events extraits",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("data/investigation/mapping"),
        help="Dossier de base contenant les sous-dossiers de matchs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Fichier JSON de sortie (défaut: base_dir/weapon_ids_summary.json)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Afficher plus de détails",
    )

    args = parser.parse_args()
    base_dir = args.base_dir

    if not base_dir.exists():
        print(f"ERREUR: Dossier {base_dir} non trouvé")
        return 1

    all_weapons: dict[int, list[dict]] = defaultdict(list)
    total_matches = 0
    total_kills = 0

    # Scanner tous les sous-dossiers
    for match_dir in sorted(base_dir.iterdir()):
        if not match_dir.is_dir():
            continue

        events_file = match_dir / "events.json"
        if not events_file.exists():
            if args.verbose:
                print(f"Skip: {match_dir.name} (pas de events.json)")
            continue

        total_matches += 1
        match_id = match_dir.name

        try:
            data = json.loads(events_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"ERREUR lecture {events_file}: {e}")
            continue

        events = data.get("events", [])

        for event in events:
            if event.get("event_type") != 50:  # kills only
                continue

            total_kills += 1
            weapon_id = extract_weapon_id(event.get("extra_bytes_32", []))

            if weapon_id is None:
                continue

            # Timestamp en ticks -> secondes
            ts_ticks = event.get("timestamp_ms", 0)
            ts_sec = ts_ticks / TICKS_PER_SECOND

            all_weapons[weapon_id].append(
                {
                    "match_id": match_id,
                    "timestamp_sec": round(ts_sec, 1),
                    "gamertag": event.get("gamertag", "???")[:20],
                }
            )

        if args.verbose:
            print(f"Traité: {match_id} ({len(events)} events)")

    # Séparer connus vs inconnus
    known = {}
    unknown = {}

    for weapon_id, occurrences in sorted(all_weapons.items()):
        weapon_name = KNOWN_WEAPONS.get(weapon_id)
        entry = {
            "weapon_id_hex": f"0x{weapon_id:04x}",
            "weapon_id_dec": weapon_id,
            "total_kills": len(occurrences),
            "weapon_name": weapon_name,
            "samples": occurrences[:3],  # 3 exemples max
        }

        if weapon_name:
            known[str(weapon_id)] = entry
        else:
            unknown[str(weapon_id)] = entry

    result = {
        "metadata": {
            "total_matches_analyzed": total_matches,
            "total_kills_analyzed": total_kills,
        },
        "known_weapons": known,
        "unknown_weapons": unknown,
        "summary": {
            "total_unique_ids": len(all_weapons),
            "known_count": len(known),
            "unknown_count": len(unknown),
        },
    }

    # Sauvegarder
    output_path = args.output or (base_dir / "weapon_ids_summary.json")
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRésultats sauvegardés: {output_path}")

    # Afficher résumé
    print(f"\n{'=' * 70}")
    print("RÉSUMÉ")
    print(f"{'=' * 70}")
    print(f"Matchs analysés: {total_matches}")
    print(f"Kills analysés: {total_kills}")
    print(f"Weapon IDs uniques: {len(all_weapons)}")
    print(f"  - Connus: {len(known)}")
    print(f"  - Inconnus: {len(unknown)}")

    # Armes connues
    if known:
        print(f"\n{'=' * 70}")
        print("ARMES CONNUES")
        print(f"{'=' * 70}")
        print(f"{'ID (hex)':<12} {'ID (dec)':<10} {'Kills':<8} {'Arme'}")
        print("-" * 50)
        for wid_str, entry in sorted(known.items(), key=lambda x: -x[1]["total_kills"]):
            print(
                f"{entry['weapon_id_hex']:<12} "
                f"{entry['weapon_id_dec']:<10} "
                f"{entry['total_kills']:<8} "
                f"{entry['weapon_name']}"
            )

    # Armes inconnues
    if unknown:
        print(f"\n{'=' * 70}")
        print("WEAPON IDs INCONNUS (à identifier)")
        print(f"{'=' * 70}")
        print(
            f"{'ID (hex)':<12} {'ID (dec)':<10} {'Kills':<8} {'Exemple (match @ timestamp - joueur)'}"
        )
        print("-" * 80)
        for wid_str, entry in sorted(unknown.items(), key=lambda x: -x[1]["total_kills"]):
            sample = entry["samples"][0] if entry["samples"] else {}
            match_short = sample.get("match_id", "?")[:8]
            ts_sec = sample.get("timestamp_sec", 0)
            gt = sample.get("gamertag", "?")
            print(
                f"{entry['weapon_id_hex']:<12} "
                f"{entry['weapon_id_dec']:<10} "
                f"{entry['total_kills']:<8} "
                f"{match_short}... @ {ts_sec:.1f}s - {gt}"
            )

    return 0


if __name__ == "__main__":
    exit(main())
