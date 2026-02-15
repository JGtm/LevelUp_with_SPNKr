#!/usr/bin/env python3
"""
Analyse les weapon IDs par joueur pour identifier quels joueurs utilisent quelles armes.

Usage:
    python scripts/analyze_weapon_ids_by_player.py
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


def extract_weapon_ids_with_players(chunk_path: Path) -> list[dict]:
    """Extrait tous les weapon IDs avec les joueurs associés."""
    try:
        data = chunk_path.read_bytes()

        # Décompresser si nécessaire
        try:
            data = zlib.decompress(data)
        except:
            pass

        gamertag_positions = find_gamertags_utf16le(data)
        weapon_ids_found = []

        # Chercher les patterns d'event kill [00 0x32 00] = kill
        pattern = bytes([0x00, 0x32, 0x00])
        idx = 0

        while True:
            pos = data.find(pattern, idx)
            if pos == -1:
                break

            # Extraire le timestamp
            ts_bytes = data[pos + 3 : pos + 5]
            if len(ts_bytes) < 2:
                idx = pos + 1
                continue

            ts_centisec = ts_bytes[0] + ts_bytes[1] * 256
            ts_sec = ts_centisec / 100

            if ts_sec < 10 or ts_sec > 1800:
                idx = pos + 1
                continue

            # Chercher le gamertag le plus proche (killer)
            gamertag = None
            for gt_pos, gt in gamertag_positions.items():
                dist = pos - gt_pos
                if 20 < dist < 100:
                    gamertag = gt
                    break

            # Chercher le weapon ID
            weapon_area = data[pos + 5 : pos + 45]
            weapon_id = None

            for j in range(len(weapon_area) - 3):
                if weapon_area[j] == 0 and weapon_area[j + 1] == 0:
                    wid = weapon_area[j + 2] + (weapon_area[j + 3] * 256)
                    if wid > 0 and (wid in KNOWN_WEAPON_IDS or 0x1000 < wid < 0xF000):
                        weapon_id = wid
                        break

            if weapon_id and gamertag:
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
    """Analyse tous les chunks et associe les joueurs aux weapon IDs."""
    investigation_dir = Path("data/investigation")

    # Trouver tous les chunks type 3
    type3_chunks = list(investigation_dir.rglob("type3_*.bin"))

    print(f"Analyse de {len(type3_chunks)} chunks type 3...\n")

    # Analyser tous les chunks
    all_kills = []
    for chunk_path in sorted(type3_chunks):
        kills = extract_weapon_ids_with_players(chunk_path)
        all_kills.extend(kills)

    # Grouper par weapon ID puis par joueur
    weapon_player_stats = defaultdict(lambda: defaultdict(int))
    weapon_player_samples = defaultdict(lambda: defaultdict(list))

    for kill in all_kills:
        wid = kill["weapon_id"]
        player = kill["gamertag"]
        if player:
            weapon_player_stats[wid][player] += 1
            if len(weapon_player_samples[wid][player]) < 3:
                weapon_player_samples[wid][player].append(
                    {
                        "timestamp_sec": kill["timestamp_sec"],
                        "match_id": kill["match_id"],
                    }
                )

    # Afficher les résultats
    print("=== WEAPON IDs PAR JOUEUR ===\n")

    for wid in sorted(
        weapon_player_stats.keys(), key=lambda x: sum(weapon_player_stats[x].values()), reverse=True
    ):
        total_kills = sum(weapon_player_stats[wid].values())
        weapon_name = KNOWN_WEAPON_IDS.get(wid, "Inconnu")

        print(f"Weapon ID: 0x{wid:04X} ({wid}) - {weapon_name}")
        print(f"  Total kills: {total_kills}")
        print(f"  Joueurs uniques: {len(weapon_player_stats[wid])}")

        # Top joueurs pour ce weapon ID
        top_players = sorted(weapon_player_stats[wid].items(), key=lambda x: x[1], reverse=True)[
            :5
        ]  # Top 5

        print("  Top joueurs:")
        for player, count in top_players:
            samples = weapon_player_samples[wid][player]
            match_ids = ", ".join(set(s["match_id"] for s in samples))
            print(f"    - {player:20} : {count:3} kills (matchs: {match_ids})")

        print()

    # Sauvegarder les résultats
    results = {
        "metadata": {
            "total_kills": len(all_kills),
            "unique_weapon_ids": len(weapon_player_stats),
            "unique_players": len(set(kill["gamertag"] for kill in all_kills if kill["gamertag"])),
        },
        "weapon_player_stats": {
            f"0x{wid:04X}": {
                "weapon_id": wid,
                "weapon_name": KNOWN_WEAPON_IDS.get(wid),
                "total_kills": sum(weapon_player_stats[wid].values()),
                "players": {
                    player: {
                        "kills": count,
                        "samples": weapon_player_samples[wid][player],
                    }
                    for player, count in weapon_player_stats[wid].items()
                },
            }
            for wid in weapon_player_stats.keys()
        },
    }

    output_path = Path(".ai/research/weapon_ids_by_player.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    print(f"[OK] Resultats sauvegardes dans {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
