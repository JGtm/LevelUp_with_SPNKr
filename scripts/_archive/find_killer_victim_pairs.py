#!/usr/bin/env python3
"""
Trouve les paires killer-victim pour un joueur spécifique en analysant tous les events.

Usage:
    python scripts/find_killer_victim_pairs.py --player sixxt
"""

from __future__ import annotations

import argparse
import json
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


def extract_all_events(chunk_path: Path) -> list[dict]:
    """Extrait tous les events (kills et deaths) d'un chunk."""
    try:
        data = chunk_path.read_bytes()

        try:
            data = zlib.decompress(data)
        except:
            pass

        gamertag_positions = find_gamertags_utf16le(data)
        events = []

        # Chercher les kills [00 0x32 00]
        kill_pattern = bytes([0x00, 0x32, 0x00])
        idx = 0

        while True:
            pos = data.find(kill_pattern, idx)
            if pos == -1:
                break

            ts_bytes = data[pos + 3 : pos + 5]
            if len(ts_bytes) < 2:
                idx = pos + 1
                continue

            ts_centisec = ts_bytes[0] + ts_bytes[1] * 256
            ts_sec = ts_centisec / 100

            if ts_sec < 10 or ts_sec > 1800:
                idx = pos + 1
                continue

            gamertag = None
            for gt_pos, gt in gamertag_positions.items():
                dist = pos - gt_pos
                if 20 < dist < 100:
                    gamertag = gt
                    break

            weapon_area = data[pos + 5 : pos + 45]
            weapon_id = None

            for j in range(len(weapon_area) - 3):
                if weapon_area[j] == 0 and weapon_area[j + 1] == 0:
                    wid = weapon_area[j + 2] + (weapon_area[j + 3] * 256)
                    if wid > 0 and (0x1000 < wid < 0xF000):
                        weapon_id = wid
                        break

            if gamertag:
                events.append(
                    {
                        "type": "kill",
                        "timestamp_sec": round(ts_sec, 2),
                        "gamertag": gamertag,
                        "weapon_id": weapon_id,
                        "weapon_id_hex": f"0x{wid:04X}" if weapon_id else None,
                    }
                )

            idx = pos + 1

        # Chercher les deaths [00 0x14 00]
        death_pattern = bytes([0x00, 0x14, 0x00])
        idx = 0

        while True:
            pos = data.find(death_pattern, idx)
            if pos == -1:
                break

            ts_bytes = data[pos + 3 : pos + 5]
            if len(ts_bytes) < 2:
                idx = pos + 1
                continue

            ts_centisec = ts_bytes[0] + ts_bytes[1] * 256
            ts_sec = ts_centisec / 100

            if ts_sec < 10 or ts_sec > 1800:
                idx = pos + 1
                continue

            gamertag = None
            for gt_pos, gt in gamertag_positions.items():
                dist = pos - gt_pos
                if 20 < dist < 100:
                    gamertag = gt
                    break

            if gamertag:
                events.append(
                    {
                        "type": "death",
                        "timestamp_sec": round(ts_sec, 2),
                        "gamertag": gamertag,
                    }
                )

            idx = pos + 1

        return events

    except Exception:
        return []


def find_pairs_for_player(
    all_events: list[dict], player_name: str, tolerance_sec: float = 0.1
) -> list[dict]:
    """Trouve les paires killer-victim impliquant un joueur."""
    # Séparer kills et deaths
    kills = [e for e in all_events if e["type"] == "kill"]
    deaths = [e for e in all_events if e["type"] == "death"]

    # Trouver les kills du joueur (qui il a tué)
    player_kills = [k for k in kills if player_name.lower() in k["gamertag"].lower()]

    # Trouver les deaths du joueur (qui l'a tué)
    player_deaths = [d for d in deaths if player_name.lower() in d["gamertag"].lower()]

    pairs_killed_by_player = []
    pairs_killed_player = []

    # Qui le joueur a tué
    used_deaths = set()
    for kill in player_kills:
        kill_time = kill["timestamp_sec"]

        best_death = None
        best_delta = None
        best_idx = None

        for i, death in enumerate(deaths):
            if i in used_deaths:
                continue

            delta = abs(death["timestamp_sec"] - kill_time)
            if delta <= tolerance_sec:
                if best_delta is None or delta < best_delta:
                    best_delta = delta
                    best_death = death
                    best_idx = i

        if best_death:
            used_deaths.add(best_idx)
            pairs_killed_by_player.append(
                {
                    "killer": kill["gamertag"],
                    "victim": best_death["gamertag"],
                    "timestamp_sec": kill_time,
                    "weapon_id": kill.get("weapon_id"),
                    "weapon_id_hex": kill.get("weapon_id_hex"),
                }
            )

    # Qui a tué le joueur
    used_kills = set()
    for death in player_deaths:
        death_time = death["timestamp_sec"]

        best_kill = None
        best_delta = None
        best_idx = None

        for i, kill in enumerate(kills):
            if i in used_kills:
                continue

            delta = abs(kill["timestamp_sec"] - death_time)
            if delta <= tolerance_sec:
                if best_delta is None or delta < best_delta:
                    best_delta = delta
                    best_kill = kill
                    best_idx = i

        if best_kill:
            used_kills.add(best_idx)
            pairs_killed_player.append(
                {
                    "killer": best_kill["gamertag"],
                    "victim": death["gamertag"],
                    "timestamp_sec": death_time,
                    "weapon_id": best_kill.get("weapon_id"),
                    "weapon_id_hex": best_kill.get("weapon_id_hex"),
                }
            )

    return pairs_killed_by_player, pairs_killed_player


def main():
    parser = argparse.ArgumentParser(description="Trouver les paires killer-victim pour un joueur")
    parser.add_argument("--player", required=True, help="Nom du joueur (gamertag)")

    args = parser.parse_args()

    investigation_dir = Path("data/investigation")
    type3_chunks = list(investigation_dir.rglob("type3_*.bin"))

    print(f"Analyse des paires killer-victim pour '{args.player}'...\n")

    # Extraire tous les events de tous les chunks
    all_events = []
    for chunk_path in sorted(type3_chunks):
        events = extract_all_events(chunk_path)
        for event in events:
            event["match_id"] = (
                chunk_path.parent.parent.name if "mapping" in str(chunk_path) else "unknown"
            )
            event["chunk"] = chunk_path.name
        all_events.extend(events)

    # Trouver les paires
    killed_by_player, killed_player = find_pairs_for_player(all_events, args.player)

    print(f"=== QUI {args.player.upper()} A TUE ===\n")
    if killed_by_player:
        print(f"{'Timestamp':<12} | {'Victim':<20} | {'Weapon ID':<12}")
        print("-" * 50)
        for pair in sorted(killed_by_player, key=lambda x: x["timestamp_sec"]):
            mins = int(pair["timestamp_sec"] // 60)
            secs = int(pair["timestamp_sec"] % 60)
            time_str = f"{mins}:{secs:02d}"
            victim = pair["victim"]
            weapon = pair.get("weapon_id_hex", "?") or "?"
            print(f"{time_str:<12} | {victim:<20} | {weapon:<12}")
    else:
        print("Aucun kill trouve")

    print(f"\n=== QUI A TUE {args.player.upper()} ===\n")
    if killed_player:
        print(f"{'Timestamp':<12} | {'Killer':<20} | {'Weapon ID':<12}")
        print("-" * 50)
        for pair in sorted(killed_player, key=lambda x: x["timestamp_sec"]):
            mins = int(pair["timestamp_sec"] // 60)
            secs = int(pair["timestamp_sec"] % 60)
            time_str = f"{mins}:{secs:02d}"
            killer = pair["killer"]
            weapon = pair.get("weapon_id_hex", "?") or "?"
            print(f"{time_str:<12} | {killer:<20} | {weapon:<12}")
    else:
        print("Aucun death trouve")

    # Sauvegarder
    results = {
        "player": args.player,
        "killed_by_player": killed_by_player,
        "killed_player": killed_player,
        "summary": {
            "kills": len(killed_by_player),
            "deaths": len(killed_player),
        },
    }

    output_path = Path(f".ai/research/pairs_{args.player}.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    print(f"\n[OK] Resultats sauvegardes dans {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
