#!/usr/bin/env python3
"""
Cherche spécifiquement les kills de sixxt autour de 512s.

Analyse toutes les positions de sixxt et cherche les patterns kill proches.
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path


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


def hexdump(data: bytes, start: int, length: int = 128) -> str:
    """Affiche un hexdump."""
    end = min(start + length, len(data))
    lines = []
    for i in range(start, end, 16):
        hex_part = " ".join(f"{data[j]:02X}" for j in range(i, min(i + 16, end)))
        ascii_part = "".join(
            chr(data[j]) if 32 <= data[j] < 127 else "." for j in range(i, min(i + 16, end))
        )
        lines.append(f"{i:08X}: {hex_part:<48} | {ascii_part}")
    return "\n".join(lines)


def main():
    chunk_path = Path("data/investigation/mapping/btb_58d09c44/chunks/type3___filmChunk58.bin")

    data = chunk_path.read_bytes()
    try:
        data = zlib.decompress(data)
    except:
        pass

    gamertags = find_gamertags_utf16le(data)

    # Trouver toutes les positions de sixxt
    sixxt_positions = [pos for pos, gt in gamertags.items() if "sixxt" in gt.lower()]

    print(f"=== Positions de sixxt: {len(sixxt_positions)} ===\n")
    for pos in sixxt_positions:
        print(f"  {pos:08X}: {gamertags[pos]}")
    print()

    # Pour chaque position de sixxt, chercher les patterns kill dans une zone autour
    kill_pattern = bytes([0x00, 0x32, 0x00])
    target_time = 512.0
    target_centisec = int(target_time * 100)

    print("=== Recherche kills autour des positions sixxt ===\n")
    print(f"Timestamp cible: {target_time}s ({target_centisec} centisecondes)\n")

    for sixxt_pos in sixxt_positions:
        print(f"\n{'='*70}")
        print(f"Position sixxt: {sixxt_pos:08X}")
        print(f"{'='*70}\n")

        # Chercher les kills dans une zone de ±500 bytes autour
        search_start = max(0, sixxt_pos - 500)
        search_end = min(len(data), sixxt_pos + 500)
        search_area = data[search_start:search_end]

        idx = 0
        kills_found = []

        while True:
            pos_in_area = search_area.find(kill_pattern, idx)
            if pos_in_area == -1:
                break

            kill_pos_absolute = search_start + pos_in_area
            dist_from_sixxt = kill_pos_absolute - sixxt_pos

            # Tester différents offsets pour le timestamp
            for ts_offset in range(3, 12):
                ts_start = kill_pos_absolute + ts_offset
                if ts_start + 2 > len(data):
                    continue

                ts_bytes = data[ts_start : ts_start + 2]
                ts_centisec = ts_bytes[0] + ts_bytes[1] * 256
                ts_sec = ts_centisec / 100

                delta = abs(ts_sec - target_time)
                if delta < 10:  # Dans les 10 secondes
                    # Chercher gamertags autour
                    nearby_tags = []
                    for gt_pos, gt in gamertags.items():
                        dist = abs(gt_pos - kill_pos_absolute)
                        if dist < 300:
                            nearby_tags.append((gt_pos - kill_pos_absolute, gt))

                    nearby_tags.sort(key=lambda x: abs(x[0]))

                    # Chercher weapon ID
                    weapon_start = ts_start + 2
                    weapon_end = min(weapon_start + 60, len(data))
                    weapon_area = data[weapon_start:weapon_end]
                    weapon_ids = []

                    for j in range(len(weapon_area) - 3):
                        if weapon_area[j] == 0 and weapon_area[j + 1] == 0:
                            wid = weapon_area[j + 2] + (weapon_area[j + 3] * 256)
                            if wid > 0 and (0x1000 < wid < 0xF000):
                                weapon_ids.append((j, wid))

                    kills_found.append(
                        {
                            "kill_pos": kill_pos_absolute,
                            "dist_from_sixxt": dist_from_sixxt,
                            "ts_offset": ts_offset,
                            "ts_sec": ts_sec,
                            "delta": delta,
                            "nearby_tags": nearby_tags[:8],
                            "weapon_ids": weapon_ids[:3],
                        }
                    )

            idx = pos_in_area + 1

        if kills_found:
            kills_found.sort(key=lambda x: x["delta"])
            print(f"Kills trouvés: {len(kills_found)}\n")

            for i, kill in enumerate(kills_found[:5]):
                print(f"--- Kill #{i+1} ---")
                print(f"  Position kill: {kill['kill_pos']:08X}")
                print(f"  Distance de sixxt: {kill['dist_from_sixxt']:+d} bytes")
                print(f"  Offset TS: {kill['ts_offset']}")
                print(f"  Timestamp: {kill['ts_sec']:.2f}s (delta: {kill['delta']:.2f}s)")
                print("  Gamertags proches:")
                for dist, gt in kill["nearby_tags"]:
                    marker = ""
                    if "obscure" in gt.lower():
                        marker = " ← VICTIM"
                    print(f"    {dist:+6d} bytes: {gt}{marker}")
                print(f"  Weapon IDs: {[f'0x{wid:04X}' for _, wid in kill['weapon_ids']]}")
                print("\n  Hexdump:")
                print(hexdump(data, max(0, kill["kill_pos"] - 64), 192))
                print()


if __name__ == "__main__":
    main()
