#!/usr/bin/env python3
"""
Extracteur d'events v3 - Structure validée.

Structure d'un event dans le chunk type 3:
- Gamertag UTF-16 LE (variable)
- Padding (~24 bytes de 0x00)
- [00 TYPE 00] : TYPE = 0x32 (kill), 0x14 (death), 0x64 (assist)
- [TS_LO TS_HI] : Timestamp 2 bytes LE, en centisecondes
- Padding (~8 bytes)
- [00 00 WID_LO WID_HI] : Weapon ID avec prefix 00 00

Validé sur match 7f1bbf06 avec données de référence utilisateur.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

# Weapon IDs connus
WEAPON_IDS = {
    0xE02E: "Sidekick",
    0x7017: "MA40 AR",
}


def find_gamertags_utf16le(data: bytes) -> dict[int, str]:
    """Trouve tous les gamertags UTF-16 LE dans les données."""
    # Pattern: 3+ caractères ASCII séparés par \x00
    pattern = re.compile(rb"(?:[A-Za-z0-9 ]\x00){3,16}")

    gamertags = {}
    for m in pattern.finditer(data):
        try:
            gt = m.group().decode("utf-16-le")
            if 3 <= len(gt) <= 16 and gt.replace(" ", "").isalnum():
                gamertags[m.start()] = gt
        except Exception:
            pass

    return gamertags


def extract_events(data: bytes) -> list[dict]:
    """Extrait tous les events du chunk."""
    # Trouver tous les gamertags
    gamertag_positions = find_gamertags_utf16le(data)

    events = []

    # Chercher les patterns d'event type
    for event_code, event_type in [(0x32, "kill"), (0x14, "death"), (0x64, "assist")]:
        pattern = bytes([0x00, event_code, 0x00])

        idx = 0
        while True:
            pos = data.find(pattern, idx)
            if pos == -1:
                break

            # Extraire le timestamp (2 bytes après le pattern)
            ts_bytes = data[pos + 3 : pos + 5]
            if len(ts_bytes) < 2:
                idx = pos + 1
                continue

            ts_centisec = ts_bytes[0] + ts_bytes[1] * 256
            ts_sec = ts_centisec / 100

            # Filtrer les timestamps invalides
            if ts_sec < 10 or ts_sec > 1800:
                idx = pos + 1
                continue

            # Chercher le gamertag le plus proche avant ce pattern
            gamertag = None
            for gt_pos, gt in gamertag_positions.items():
                dist = pos - gt_pos
                if 20 < dist < 100:
                    gamertag = gt
                    break

            # Chercher le weapon ID après le timestamp
            weapon_area = data[pos + 5 : pos + 45]
            weapon_id = None
            weapon_name = None

            # Chercher le pattern [00 00 WID_LO WID_HI]
            for j in range(len(weapon_area) - 3):
                if weapon_area[j] == 0 and weapon_area[j + 1] == 0:
                    wid = weapon_area[j + 2] + weapon_area[j + 3] * 256
                    if wid in WEAPON_IDS:
                        weapon_id = wid
                        weapon_name = WEAPON_IDS[wid]
                        break

            events.append(
                {
                    "offset": pos,
                    "type": event_type,
                    "timestamp_sec": round(ts_sec, 2),
                    "gamertag": gamertag,
                    "weapon_id": weapon_id,
                    "weapon_name": weapon_name,
                }
            )

            idx = pos + 1

    return sorted(events, key=lambda x: x["timestamp_sec"])


def main():
    parser = argparse.ArgumentParser(description="Extraire les events d'un chunk type 3")
    parser.add_argument("--chunk", required=True, type=Path, help="Chemin vers le chunk .bin")
    parser.add_argument("--output", type=Path, help="Fichier JSON de sortie")
    parser.add_argument(
        "--filter-type", choices=["kill", "death", "assist"], help="Filtrer par type"
    )

    args = parser.parse_args()

    if not args.chunk.exists():
        print(f"Erreur: fichier non trouvé: {args.chunk}")
        return 1

    data = args.chunk.read_bytes()
    print(f"Chunk: {args.chunk.name} ({len(data):,} bytes)")

    events = extract_events(data)

    if args.filter_type:
        events = [e for e in events if e["type"] == args.filter_type]

    print(f"\n=== {len(events)} EVENTS EXTRAITS ===\n")
    print(f"{'Time':>8} | {'Type':<6} | {'Weapon':<10} | {'Joueur':<20}")
    print("-" * 55)

    for e in events:
        mins = int(e["timestamp_sec"] // 60)
        secs = int(e["timestamp_sec"] % 60)
        time_str = f"{mins}:{secs:02d}"
        weapon = e["weapon_name"] or "?"
        gamertag = e["gamertag"] or "???"
        print(f"{time_str:>8} | {e['type']:<6} | {weapon:<10} | {gamertag:<20}")

    # Stats
    print("\n=== STATISTIQUES ===")
    by_type = defaultdict(int)
    by_weapon = defaultdict(int)

    for e in events:
        by_type[e["type"]] += 1
        if e["weapon_name"]:
            by_weapon[e["weapon_name"]] += 1

    for t, c in sorted(by_type.items()):
        print(f"  {t}: {c}")

    if by_weapon:
        print("\nArmes:")
        for w, c in sorted(by_weapon.items(), key=lambda x: -x[1]):
            print(f"  {w}: {c}")

    # Sauvegarder si demandé
    if args.output:
        result = {
            "chunk": str(args.chunk),
            "total_events": len(events),
            "events": events,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\nSauvegardé: {args.output}")

    return 0


if __name__ == "__main__":
    exit(main())
