#!/usr/bin/env python3
"""
Analyse un chunk avec hexdump pour identifier les structures exactes.

Cherche spécifiquement sixxt -> ObscureGuide710 à 8:32 (512 secondes)
avec le Commando dans le match 58d09c44.
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


def hexdump(data: bytes, start: int, length: int = 64) -> str:
    """Affiche un hexdump d'une zone."""
    end = min(start + length, len(data))
    hex_str = " ".join(f"{b:02X}" for b in data[start:end])
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data[start:end])
    return f"{start:08X}: {hex_str:<48} | {ascii_str}"


def find_all_patterns(data: bytes, pattern: bytes, max_results: int = 20) -> list[int]:
    """Trouve toutes les occurrences d'un pattern."""
    results = []
    idx = 0
    while len(results) < max_results:
        pos = data.find(pattern, idx)
        if pos == -1:
            break
        results.append(pos)
        idx = pos + 1
    return results


def analyze_chunk_detailed(
    chunk_path: Path, target_player: str, target_victim: str, target_time_sec: float
):
    """Analyse détaillée d'un chunk pour trouver un event spécifique."""
    print(f"=== Analyse détaillée: {chunk_path.name} ===\n")

    data = chunk_path.read_bytes()
    try:
        data = zlib.decompress(data)
        print("Chunk décompressé\n")
    except:
        print("Chunk non compressé\n")

    print(f"Taille: {len(data):,} bytes\n")

    # Trouver tous les gamertags
    gamertags = find_gamertags_utf16le(data)
    print(f"Gamertags trouvés: {len(gamertags)}\n")

    # Trouver les positions de sixxt et ObscureGuide710
    sixxt_positions = [pos for pos, gt in gamertags.items() if target_player.lower() in gt.lower()]
    victim_positions = [pos for pos, gt in gamertags.items() if target_victim.lower() in gt.lower()]

    print(f"Positions '{target_player}': {sixxt_positions}")
    print(f"Positions '{target_victim}': {victim_positions}\n")

    # Chercher les patterns kill [00 0x32 00]
    kill_pattern = bytes([0x00, 0x32, 0x00])
    kill_positions = find_all_patterns(data, kill_pattern, max_results=50)

    print(f"Patterns kill trouvés: {len(kill_positions)}\n")

    # Pour chaque kill, analyser la structure autour
    target_time_centisec = int(target_time_sec * 100)
    print(f"Timestamp cible: {target_time_sec}s ({target_time_centisec} centisecondes)\n")
    print(
        f"Timestamp cible (hex): {target_time_centisec:04X} (little-endian: {target_time_centisec & 0xFF:02X} {(target_time_centisec >> 8) & 0xFF:02X})\n"
    )

    # Chercher les timestamps proches
    for i, kill_pos in enumerate(kill_positions[:20]):
        print(f"\n--- Kill #{i+1} à offset {kill_pos:08X} ---")
        print(hexdump(data, max(0, kill_pos - 32), 96))

        # Tester différents offsets pour le timestamp
        for ts_offset in [3, 4, 5, 6, 7, 8, 9, 10]:
            ts_start = kill_pos + ts_offset
            if ts_start + 2 > len(data):
                continue

            ts_bytes = data[ts_start : ts_start + 2]
            ts_centisec = ts_bytes[0] + ts_bytes[1] * 256
            ts_sec = ts_centisec / 100

            delta = abs(ts_sec - target_time_sec)
            if delta < 10:  # Dans les 10 secondes
                print(
                    f"\n  [MATCH POTENTIEL] Offset TS={ts_offset}: {ts_sec:.2f}s (delta: {delta:.2f}s)"
                )
                print(f"    Bytes TS: {ts_bytes[0]:02X} {ts_bytes[1]:02X}")

                # Vérifier si un gamertag est proche
                for gt_pos, gt in gamertags.items():
                    dist_before = kill_pos - gt_pos
                    if 10 < dist_before < 150:
                        print(f"    Gamertag avant ({dist_before} bytes): {gt}")

                # Chercher weapon ID après le timestamp
                weapon_start = ts_start + 2
                weapon_end = min(weapon_start + 60, len(data))
                weapon_area = data[weapon_start:weapon_end]

                print(f"    Zone weapon ({weapon_start:08X}-{weapon_end:08X}):")
                for j in range(0, min(40, len(weapon_area)), 16):
                    print(f"      {hexdump(weapon_area, j, 16)}")

                # Chercher pattern [00 00 WID]
                for j in range(len(weapon_area) - 3):
                    if weapon_area[j] == 0 and weapon_area[j + 1] == 0:
                        wid = weapon_area[j + 2] + (weapon_area[j + 3] * 256)
                        if wid > 0 and (0x1000 < wid < 0xF000):
                            print(f"      Weapon ID trouvé à offset +{j}: 0x{wid:04X} ({wid})")


def main():
    parser = argparse.ArgumentParser(description="Analyse détaillée avec hexdump")
    parser.add_argument("--chunk", required=True, type=Path, help="Chemin vers le chunk")
    parser.add_argument("--player", default="sixxt", help="Joueur killer")
    parser.add_argument("--victim", default="ObscureGuide710", help="Victim")
    parser.add_argument(
        "--time", type=float, default=512.0, help="Timestamp en secondes (8:32 = 512)"
    )

    args = parser.parse_args()

    if not args.chunk.exists():
        print(f"Erreur: fichier non trouvé: {args.chunk}")
        return 1

    analyze_chunk_detailed(args.chunk, args.player, args.victim, args.time)

    return 0


if __name__ == "__main__":
    exit(main())
