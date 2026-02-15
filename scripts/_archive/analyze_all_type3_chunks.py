#!/usr/bin/env python3
"""
Analyse TOUS les chunks type 3 disponibles pour identifier tous les weapon IDs.

Usage:
    python scripts/analyze_all_type3_chunks.py
"""

from __future__ import annotations

import json
import re
import zlib
from collections import defaultdict
from pathlib import Path

# Weapon IDs connus
KNOWN_WEAPON_IDS = {
    0xE02E: "Sidekick",
    0x7017: "MA40 AR",
}


def find_gamertags_utf16le(data: bytes) -> dict[int, str]:
    """Trouve tous les gamertags UTF-16 LE dans les données."""
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


def extract_weapon_ids_from_chunk(chunk_path: Path) -> list[dict]:
    """Extrait tous les weapon IDs d'un chunk type 3."""
    try:
        data = chunk_path.read_bytes()

        # Décompresser si nécessaire
        try:
            data = zlib.decompress(data)
        except:
            pass  # Déjà décompressé

        gamertag_positions = find_gamertags_utf16le(data)
        weapon_ids_found = []

        # Chercher les patterns d'event kill [00 0x32 00] = kill
        pattern = bytes([0x00, 0x32, 0x00])
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

            # Chercher le gamertag le plus proche
            gamertag = None
            for gt_pos, gt in gamertag_positions.items():
                dist = pos - gt_pos
                if 20 < dist < 100:
                    gamertag = gt
                    break

            # Chercher le weapon ID après le timestamp
            weapon_area = data[pos + 5 : pos + 45]
            weapon_id = None

            # Chercher le pattern [00 00 WID_LO WID_HI]
            for j in range(len(weapon_area) - 3):
                if weapon_area[j] == 0 and weapon_area[j + 1] == 0:
                    # Little-endian: byte[j+2] = low, byte[j+3] = high
                    wid = weapon_area[j + 2] + (weapon_area[j + 3] * 256)
                    # Filtrer les IDs plausibles (éviter le bruit)
                    if wid > 0 and (wid in KNOWN_WEAPON_IDS or 0x1000 < wid < 0xF000):
                        weapon_id = wid
                        break

            if weapon_id:
                weapon_ids_found.append(
                    {
                        "weapon_id": weapon_id,
                        "weapon_id_hex": f"0x{wid:04X}",
                        "timestamp_sec": round(ts_sec, 2),
                        "gamertag": gamertag,
                        "chunk": chunk_path.name,
                        "match_id": chunk_path.parent.parent.name
                        if "mapping" in str(chunk_path)
                        else "unknown",
                    }
                )

            idx = pos + 1

        return weapon_ids_found

    except Exception as e:
        print(f"Erreur avec {chunk_path}: {e}")
        return []


def main():
    """Analyse tous les chunks type 3 disponibles."""
    investigation_dir = Path("data/investigation")

    # Trouver tous les chunks type 3
    type3_chunks = []

    # Chercher dans tous les dossiers
    for chunk_path in investigation_dir.rglob("type3_*.bin"):
        type3_chunks.append(chunk_path)

    print(f"Trouve {len(type3_chunks)} chunks type 3 a analyser\n")

    # Analyser tous les chunks
    all_weapon_ids = []
    weapon_id_counts = defaultdict(int)
    weapon_id_samples = defaultdict(list)
    chunks_analyzed = 0

    for chunk_path in sorted(type3_chunks):
        print(f"Analyse de {chunk_path.name}...", end=" ")
        weapon_ids = extract_weapon_ids_from_chunk(chunk_path)
        all_weapon_ids.extend(weapon_ids)

        if weapon_ids:
            chunks_analyzed += 1
            print(f"{len(weapon_ids)} weapon IDs trouves")
        else:
            print("0 weapon IDs")

        for wid_data in weapon_ids:
            wid = wid_data["weapon_id"]
            weapon_id_counts[wid] += 1
            if len(weapon_id_samples[wid]) < 5:  # Garder max 5 échantillons
                weapon_id_samples[wid].append(
                    {
                        "timestamp_sec": wid_data["timestamp_sec"],
                        "gamertag": wid_data["gamertag"],
                        "chunk": wid_data["chunk"],
                        "match_id": wid_data.get("match_id", "unknown"),
                    }
                )

    print("\n=== RESULTATS ===\n")
    print(f"Chunks analyses: {chunks_analyzed}/{len(type3_chunks)}")
    print(f"Total d'events kill analyses: {len(all_weapon_ids)}")
    print(f"Weapon IDs uniques trouves: {len(weapon_id_counts)}\n")

    # Grouper par weapon ID connu/inconnu
    known = {}
    unknown = {}

    for wid, count in sorted(weapon_id_counts.items(), key=lambda x: -x[1]):
        if wid in KNOWN_WEAPON_IDS:
            known[wid] = {
                "weapon_id_hex": f"0x{wid:04X}",
                "weapon_id_dec": wid,
                "weapon_name": KNOWN_WEAPON_IDS[wid],
                "total_kills": count,
                "samples": weapon_id_samples[wid],
            }
        else:
            unknown[wid] = {
                "weapon_id_hex": f"0x{wid:04X}",
                "weapon_id_dec": wid,
                "weapon_name": None,
                "total_kills": count,
                "samples": weapon_id_samples[wid],
            }

    # Afficher les résultats
    print("=== WEAPON IDs CONNUS ===\n")
    if known:
        for wid, data in sorted(known.items(), key=lambda x: -x[1]["total_kills"]):
            print(
                f"  {data['weapon_name']:15} | 0x{wid:04X} ({wid:5}) | {data['total_kills']:3} kills"
            )
            if data["samples"]:
                sample = data["samples"][0]
                print(
                    f"    Exemple: {sample['gamertag']} a {sample['timestamp_sec']}s (match {sample['match_id']})"
                )
    else:
        print("  Aucun")

    print(f"\n=== WEAPON IDs INCONNUS ({len(unknown)}) ===\n")
    for wid, data in sorted(unknown.items(), key=lambda x: -x[1]["total_kills"]):
        print(f"  0x{wid:04X} ({wid:5}) | {data['total_kills']:3} kills")
        if data["samples"]:
            sample = data["samples"][0]
            print(
                f"    Exemple: {sample['gamertag']} a {sample['timestamp_sec']}s (match {sample['match_id']})"
            )

    # Sauvegarder les résultats
    results = {
        "metadata": {
            "total_chunks_found": len(type3_chunks),
            "total_chunks_analyzed": chunks_analyzed,
            "total_kills_analyzed": len(all_weapon_ids),
            "unique_weapon_ids": len(weapon_id_counts),
        },
        "known_weapons": known,
        "unknown_weapons": unknown,
        "summary": {
            "known_count": len(known),
            "unknown_count": len(unknown),
        },
    }

    output_path = Path(".ai/research/all_weapon_ids_complete.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    print(f"\n[OK] Resultats sauvegardes dans {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
