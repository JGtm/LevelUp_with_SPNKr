#!/usr/bin/env python3
"""
Analyse approfondie du byte shifting pour corriger l'extraction.

L'utilisateur confirme:
- sixxt tue ObscureGuide710 à 8:32 (512s) avec le Commando
- À 8:47 (527s), sixxt respawn (pas un kill)

Ce script analyse la structure complète autour de ces timestamps pour identifier
le bon offset et la structure réelle des données.
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


def hexdump_wide(data: bytes, start: int, length: int = 256) -> str:
    """Affiche un hexdump large."""
    end = min(start + length, len(data))
    lines = []
    for i in range(start, end, 16):
        hex_part = " ".join(f"{data[j]:02X}" for j in range(i, min(i + 16, end)))
        ascii_part = "".join(
            chr(data[j]) if 32 <= data[j] < 127 else "." for j in range(i, min(i + 16, end))
        )
        lines.append(f"{i:08X}: {hex_part:<48} | {ascii_part}")
    return "\n".join(lines)


def analyze_around_timestamps(
    chunk_path: Path, target_times: list[float], killer: str, victim: str
):
    """Analyse détaillée autour de timestamps spécifiques."""
    print("=== Analyse byte shifting ===\n")
    print(f"Timestamps cibles: {target_times}\n")
    print(f"Recherche: {killer} -> {victim}\n")

    data = chunk_path.read_bytes()
    try:
        data = zlib.decompress(data)
    except:
        pass

    gamertags = find_gamertags_utf16le(data)

    # Trouver toutes les positions de sixxt et ObscureGuide710
    killer_positions = [(pos, gt) for pos, gt in gamertags.items() if killer.lower() in gt.lower()]
    victim_positions = [(pos, gt) for pos, gt in gamertags.items() if victim.lower() in gt.lower()]

    print(f"Positions '{killer}': {len(killer_positions)}")
    for pos, gt in killer_positions[:5]:
        print(f"  {pos:08X}: {gt}")
    print(f"\nPositions '{victim}': {len(victim_positions)}")
    for pos, gt in victim_positions[:5]:
        print(f"  {pos:08X}: {gt}")
    print()

    # Pour chaque timestamp cible, chercher les events proches
    kill_pattern = bytes([0x00, 0x32, 0x00])
    death_pattern = bytes([0x00, 0x14, 0x00])

    for target_time in target_times:
        target_centisec = int(target_time * 100)
        print(f"\n{'='*70}")
        print(f"TIMESTAMP CIBLE: {target_time}s ({target_centisec} centisecondes)")
        print(f"{'='*70}\n")

        # Chercher tous les patterns kill et death autour de ce timestamp
        all_patterns = []

        for pattern, ptype in [(kill_pattern, "kill"), (death_pattern, "death")]:
            idx = 0
            while True:
                pos = data.find(pattern, idx)
                if pos == -1:
                    break

                # Tester plusieurs offsets pour le timestamp
                for ts_offset in range(3, 12):
                    ts_start = pos + ts_offset
                    if ts_start + 2 > len(data):
                        continue

                    ts_bytes = data[ts_start : ts_start + 2]
                    ts_centisec = ts_bytes[0] + ts_bytes[1] * 256
                    ts_sec = ts_centisec / 100

                    delta = abs(ts_sec - target_time)
                    if delta < 5:  # Dans les 5 secondes
                        # Chercher gamertags dans une large zone
                        nearby_tags = []
                        for gt_pos, gt in gamertags.items():
                            dist = abs(gt_pos - pos)
                            if dist < 500:  # Large zone
                                nearby_tags.append((gt_pos - pos, gt))

                        nearby_tags.sort(key=lambda x: abs(x[0]))

                        all_patterns.append(
                            {
                                "type": ptype,
                                "pos": pos,
                                "ts_offset": ts_offset,
                                "ts_sec": ts_sec,
                                "delta": delta,
                                "nearby_tags": nearby_tags[:10],
                            }
                        )

                idx = pos + 1

        # Trier par delta
        all_patterns.sort(key=lambda x: x["delta"])

        print(f"Events trouvés autour de {target_time}s:\n")
        for i, event in enumerate(all_patterns[:10]):
            print(f"--- Event #{i+1} ({event['type']}) ---")
            print(f"  Position: {event['pos']:08X}")
            print(f"  Offset TS: {event['ts_offset']}")
            print(f"  Timestamp: {event['ts_sec']:.2f}s (delta: {event['delta']:.2f}s)")
            print("  Gamertags proches:")
            for dist, gt in event["nearby_tags"][:5]:
                marker = ""
                if killer.lower() in gt.lower():
                    marker = " ← KILLER"
                if victim.lower() in gt.lower():
                    marker = " ← VICTIM"
                print(f"    {dist:+6d} bytes: {gt}{marker}")

            # Afficher hexdump
            print("\n  Hexdump:")
            print(hexdump_wide(data, max(0, event["pos"] - 80), 200))
            print()

            # Vérifier si c'est notre match
            has_killer = any(killer.lower() in gt.lower() for _, gt in event["nearby_tags"])
            has_victim = any(victim.lower() in gt.lower() for _, gt in event["nearby_tags"])

            if has_killer and has_victim and event["type"] == "kill":
                print("  ★★★ MATCH POTENTIEL TROUVÉ ★★★\n")


def main():
    parser = argparse.ArgumentParser(description="Analyser le byte shifting")
    parser.add_argument("--chunk", required=True, type=Path)
    parser.add_argument("--killer", default="sixxt")
    parser.add_argument("--victim", default="ObscureGuide710")
    parser.add_argument("--times", nargs="+", type=float, default=[512.0, 527.0])

    args = parser.parse_args()

    if not args.chunk.exists():
        print(f"Erreur: fichier non trouvé: {args.chunk}")
        return 1

    analyze_around_timestamps(args.chunk, args.times, args.killer, args.victim)

    return 0


if __name__ == "__main__":
    exit(main())
