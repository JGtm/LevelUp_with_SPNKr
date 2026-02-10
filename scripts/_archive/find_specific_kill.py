#!/usr/bin/env python3
"""
Trouve un kill spécifique : sixxt -> ObscureGuide710 à 8:32 (512s) avec Commando.

Analyse détaillée autour du timestamp cible pour identifier la structure exacte.
"""

from __future__ import annotations

import argparse
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
    """Affiche un hexdump d'une zone."""
    end = min(start + length, len(data))
    lines = []
    for i in range(start, end, 16):
        hex_part = " ".join(f"{data[j]:02X}" for j in range(i, min(i + 16, end)))
        ascii_part = "".join(
            chr(data[j]) if 32 <= data[j] < 127 else "." for j in range(i, min(i + 16, end))
        )
        lines.append(f"{i:08X}: {hex_part:<48} | {ascii_part}")
    return "\n".join(lines)


def find_kill_at_timestamp(chunk_path: Path, target_time_sec: float, killer: str, victim: str):
    """Trouve un kill spécifique dans un chunk."""
    print(f"=== Recherche: {killer} -> {victim} à {target_time_sec}s ===\n")

    data = chunk_path.read_bytes()
    try:
        data = zlib.decompress(data)
    except:
        pass

    print(f"Taille chunk: {len(data):,} bytes\n")

    # Trouver tous les gamertags
    gamertags = find_gamertags_utf16le(data)
    print(f"Gamertags trouvés: {len(gamertags)}\n")

    # Trouver les positions des joueurs cibles
    killer_positions = [pos for pos, gt in gamertags.items() if killer.lower() in gt.lower()]
    victim_positions = [pos for pos, gt in gamertags.items() if victim.lower() in gt.lower()]

    print(f"Positions '{killer}': {len(killer_positions)}")
    print(f"Positions '{victim}': {len(victim_positions)}\n")

    # Chercher les patterns kill [00 0x32 00]
    kill_pattern = bytes([0x00, 0x32, 0x00])
    target_time_centisec = int(target_time_sec * 100)

    print(f"Timestamp cible: {target_time_sec}s = {target_time_centisec} centisecondes")
    print(
        f"Bytes attendus (little-endian): {target_time_centisec & 0xFF:02X} {(target_time_centisec >> 8) & 0xFF:02X}\n"
    )

    idx = 0
    matches = []

    while True:
        pos = data.find(kill_pattern, idx)
        if pos == -1:
            break

        # Tester différents offsets pour le timestamp
        for ts_offset in range(3, 15):
            ts_start = pos + ts_offset
            if ts_start + 2 > len(data):
                continue

            ts_bytes = data[ts_start : ts_start + 2]
            ts_centisec = ts_bytes[0] + ts_bytes[1] * 256
            ts_sec = ts_centisec / 100

            delta = abs(ts_sec - target_time_sec)
            if delta < 2:  # Dans les 2 secondes
                # Chercher les gamertags autour (avant et après)
                nearby_gamertags_before = []
                nearby_gamertags_after = []

                for gt_pos, gt in gamertags.items():
                    dist_before = pos - gt_pos
                    dist_after = gt_pos - pos

                    if 10 < dist_before < 300:
                        nearby_gamertags_before.append((dist_before, gt))
                    if 10 < dist_after < 300:
                        nearby_gamertags_after.append((dist_after, gt))

                # Chercher weapon ID
                weapon_start = ts_start + 2
                weapon_end = min(weapon_start + 80, len(data))
                weapon_area = data[weapon_start:weapon_end]
                weapon_ids_found = []

                for j in range(len(weapon_area) - 3):
                    if weapon_area[j] == 0 and weapon_area[j + 1] == 0:
                        wid = weapon_area[j + 2] + (weapon_area[j + 3] * 256)
                        if wid > 0 and (0x1000 < wid < 0xF000):
                            weapon_ids_found.append((j, wid))

                matches.append(
                    {
                        "kill_pos": pos,
                        "ts_offset": ts_offset,
                        "ts_sec": ts_sec,
                        "delta": delta,
                        "gamertags_before": nearby_gamertags_before[:5],
                        "gamertags_after": nearby_gamertags_after[:5],
                        "weapon_ids": weapon_ids_found[:3],
                    }
                )

        idx = pos + 1

    # Afficher les meilleurs matches
    matches.sort(key=lambda x: x["delta"])

    print(f"=== {len(matches)} MATCHES TROUVÉS ===\n")

    for i, match in enumerate(matches[:5]):
        print(f"--- Match #{i+1} ---")
        print(f"  Position kill: {match['kill_pos']:08X}")
        print(f"  Offset TS: {match['ts_offset']}")
        print(f"  Timestamp: {match['ts_sec']:.2f}s (delta: {match['delta']:.2f}s)")
        print(f"  Gamertags avant: {match['gamertags_before']}")
        print(f"  Gamertags après: {match['gamertags_after']}")
        print(f"  Weapon IDs: {[f'0x{wid:04X}' for _, wid in match['weapon_ids']]}")

        # Afficher hexdump autour
        print(f"\n  Hexdump (offset {match['kill_pos']:08X}):")
        print(hexdump(data, max(0, match["kill_pos"] - 64), 192))
        print()

    # Chercher spécifiquement si killer et victim sont proches
    print(f"\n=== VÉRIFICATION PROXIMITÉ {killer} / {victim} ===\n")

    for match in matches[:3]:
        kill_pos = match["kill_pos"]

        # Vérifier si killer est avant le kill
        killer_found = False
        victim_found = False

        for dist, gt in match["gamertags_before"]:
            if killer.lower() in gt.lower():
                killer_found = True
                print(f"  ✓ {killer} trouvé à {dist} bytes avant le kill")
            if victim.lower() in gt.lower():
                victim_found = True
                print(f"  ✓ {victim} trouvé à {dist} bytes avant le kill")

        for dist, gt in match["gamertags_after"]:
            if killer.lower() in gt.lower():
                killer_found = True
                print(f"  ✓ {killer} trouvé à {dist} bytes après le kill")
            if victim.lower() in gt.lower():
                victim_found = True
                print(f"  ✓ {victim} trouvé à {dist} bytes après le kill")

        if killer_found and victim_found:
            print(f"\n  ★★★ MATCH CONFIRMÉ à offset {kill_pos:08X} ★★★\n")
            print(hexdump(data, max(0, kill_pos - 100), 250))
            break


def main():
    parser = argparse.ArgumentParser(description="Trouver un kill spécifique")
    parser.add_argument("--chunk", required=True, type=Path)
    parser.add_argument("--killer", default="sixxt")
    parser.add_argument("--victim", default="ObscureGuide710")
    parser.add_argument("--time", type=float, default=512.0)

    args = parser.parse_args()

    if not args.chunk.exists():
        print(f"Erreur: fichier non trouvé: {args.chunk}")
        return 1

    find_kill_at_timestamp(args.chunk, args.time, args.killer, args.victim)

    return 0


if __name__ == "__main__":
    exit(main())
