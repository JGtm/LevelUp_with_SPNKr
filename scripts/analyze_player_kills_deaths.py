#!/usr/bin/env python3
"""
Analyse les kills et deaths d'un joueur spécifique.

Usage:
    python scripts/analyze_player_kills_deaths.py --player sixxt
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


def extract_events_for_player(chunk_path: Path, player_name: str) -> list[dict]:
    """Extrait tous les events (kills et deaths) impliquant un joueur."""
    try:
        data = chunk_path.read_bytes()

        # Décompresser si nécessaire
        try:
            data = zlib.decompress(data)
        except:
            pass

        gamertag_positions = find_gamertags_utf16le(data)
        events_found = []

        # Chercher les patterns d'event kill [00 0x32 00] = kill
        kill_pattern = bytes([0x00, 0x32, 0x00])
        idx = 0

        while True:
            pos = data.find(kill_pattern, idx)
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
                    if wid > 0 and (0x1000 < wid < 0xF000):
                        weapon_id = wid
                        break

            if gamertag and player_name.lower() in gamertag.lower():
                events_found.append(
                    {
                        "type": "kill",
                        "timestamp_sec": round(ts_sec, 2),
                        "gamertag": gamertag,
                        "weapon_id": weapon_id,
                        "weapon_id_hex": f"0x{wid:04X}" if weapon_id else None,
                        "chunk": chunk_path.name,
                        "match_id": chunk_path.parent.parent.name
                        if "mapping" in str(chunk_path)
                        else "unknown",
                    }
                )

            idx = pos + 1

        # Chercher les patterns d'event death [00 0x14 00] = death
        death_pattern = bytes([0x00, 0x14, 0x00])
        idx = 0

        while True:
            pos = data.find(death_pattern, idx)
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

            # Chercher le gamertag le plus proche (victim)
            gamertag = None
            for gt_pos, gt in gamertag_positions.items():
                dist = pos - gt_pos
                if 20 < dist < 100:
                    gamertag = gt
                    break

            if gamertag and player_name.lower() in gamertag.lower():
                events_found.append(
                    {
                        "type": "death",
                        "timestamp_sec": round(ts_sec, 2),
                        "gamertag": gamertag,
                        "chunk": chunk_path.name,
                        "match_id": chunk_path.parent.parent.name
                        if "mapping" in str(chunk_path)
                        else "unknown",
                    }
                )

            idx = pos + 1

        return events_found

    except Exception as e:
        print(f"Erreur avec {chunk_path}: {e}")
        return []


def find_killer_victim_pairs(events: list[dict], tolerance_sec: float = 0.1) -> list[dict]:
    """Trouve les paires killer-victim en corrélant kills et deaths par timestamp."""
    kills = [e for e in events if e["type"] == "kill"]
    deaths = [e for e in events if e["type"] == "death"]

    pairs = []
    used_deaths = set()

    for kill in kills:
        kill_time = kill["timestamp_sec"]

        # Chercher un death proche dans le temps
        best_death = None
        best_delta = None

        for i, death in enumerate(deaths):
            if i in used_deaths:
                continue

            delta = abs(death["timestamp_sec"] - kill_time)
            if delta <= tolerance_sec:
                if best_delta is None or delta < best_delta:
                    best_delta = delta
                    best_death = (i, death)

        if best_death:
            idx, death = best_death
            used_deaths.add(idx)
            pairs.append(
                {
                    "killer": kill["gamertag"],
                    "victim": death["gamertag"],
                    "timestamp_sec": kill_time,
                    "weapon_id": kill.get("weapon_id"),
                    "weapon_id_hex": kill.get("weapon_id_hex"),
                    "match_id": kill.get("match_id"),
                }
            )

    return pairs


def main():
    parser = argparse.ArgumentParser(description="Analyser les kills et deaths d'un joueur")
    parser.add_argument("--player", required=True, help="Nom du joueur (gamertag)")

    args = parser.parse_args()

    investigation_dir = Path("data/investigation")
    type3_chunks = list(investigation_dir.rglob("type3_*.bin"))

    print(f"Analyse des events pour '{args.player}'...\n")
    print(f"Chunks type 3 a analyser: {len(type3_chunks)}\n")

    # Analyser tous les chunks
    all_events = []
    for chunk_path in sorted(type3_chunks):
        events = extract_events_for_player(chunk_path, args.player)
        all_events.extend(events)

    # Séparer kills et deaths
    kills = [e for e in all_events if e["type"] == "kill"]
    deaths = [e for e in all_events if e["type"] == "death"]

    print(f"=== EVENTS TROUVES POUR '{args.player}' ===\n")
    print(f"Kills: {len(kills)}")
    print(f"Deaths: {len(deaths)}\n")

    # Afficher les kills
    if kills:
        print(f"=== KILLS (qui {args.player} a tue) ===\n")
        print(f"{'Timestamp':<12} | {'Weapon ID':<12} | {'Match ID':<20}")
        print("-" * 50)
        for kill in sorted(kills, key=lambda x: x["timestamp_sec"]):
            mins = int(kill["timestamp_sec"] // 60)
            secs = int(kill["timestamp_sec"] % 60)
            time_str = f"{mins}:{secs:02d}"
            weapon = kill.get("weapon_id_hex", "?") or "?"
            match_id = kill.get("match_id", "unknown")
            print(f"{time_str:<12} | {weapon:<12} | {match_id:<20}")

    # Afficher les deaths
    if deaths:
        print(f"\n=== DEATHS (qui a tue {0}) ===\n".format(args.player))
        print(f"{'Timestamp':<12} | {'Match ID':<20}")
        print("-" * 35)
        for death in sorted(deaths, key=lambda x: x["timestamp_sec"]):
            mins = int(death["timestamp_sec"] // 60)
            secs = int(death["timestamp_sec"] % 60)
            time_str = f"{mins}:{secs:02d}"
            match_id = death.get("match_id", "unknown")
            print(f"{time_str:<12} | {match_id:<20}")

    # Essayer de trouver les paires killer-victim
    print("\n=== TENTATIVE DE CORRELATION KILLER-VICTIM ===\n")
    print("Note: La correlation necessite d'analyser tous les joueurs du match.")
    print(f"Pour trouver qui a tue {args.player}, il faut analyser les deaths de {args.player}")
    print("et les kills des autres joueurs au meme timestamp.\n")

    # Sauvegarder les résultats
    results = {
        "player": args.player,
        "kills": kills,
        "deaths": deaths,
        "summary": {
            "total_kills": len(kills),
            "total_deaths": len(deaths),
        },
    }

    output_path = Path(f".ai/research/player_{args.player}_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    print(f"[OK] Resultats sauvegardes dans {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
