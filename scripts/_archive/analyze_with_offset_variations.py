#!/usr/bin/env python3
"""
Analyse les chunks avec variations d'offset pour gérer le byte shifting.

L'utilisateur a confirmé que sixxt tue ObscureGuide710 à 8:32 avec le Commando
dans le match 58d09c44-decc-4946-a630-e7916c5cd68c.
À 8:47, sixxt respawn (pas un kill).

Ce script teste différents offsets pour trouver la bonne structure.
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


def extract_with_offset(
    data: bytes, pattern: bytes, ts_offset: int, weapon_search_start: int, weapon_search_end: int
) -> list[dict]:
    """Extrait les events avec un offset spécifique."""
    gamertag_positions = find_gamertags_utf16le(data)
    events = []

    idx = 0
    while True:
        pos = data.find(pattern, idx)
        if pos == -1:
            break

        # Extraire le timestamp avec l'offset spécifié
        ts_start = pos + ts_offset
        ts_end = ts_start + 2

        if ts_end > len(data):
            idx = pos + 1
            continue

        ts_bytes = data[ts_start:ts_end]
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
            if 20 < dist < 200:  # Augmenter la plage
                gamertag = gt
                break

        # Chercher le weapon ID dans la zone spécifiée
        weapon_start = pos + weapon_search_start
        weapon_end = min(pos + weapon_search_end, len(data))
        weapon_area = data[weapon_start:weapon_end]
        weapon_id = None

        # Chercher le pattern [00 00 WID_LO WID_HI] ou variations
        for j in range(len(weapon_area) - 3):
            if weapon_area[j] == 0 and weapon_area[j + 1] == 0:
                wid = weapon_area[j + 2] + (weapon_area[j + 3] * 256)
                if wid > 0 and (0x1000 < wid < 0xF000):
                    weapon_id = wid
                    break

        events.append(
            {
                "offset": pos,
                "timestamp_sec": round(ts_sec, 2),
                "gamertag": gamertag,
                "weapon_id": weapon_id,
                "weapon_id_hex": f"0x{wid:04X}" if weapon_id else None,
                "ts_offset": ts_offset,
                "weapon_start": weapon_search_start,
            }
        )

        idx = pos + 1

    return events


def find_commando_weapon_id() -> int | None:
    """Cherche le weapon ID du Commando dans les références."""
    # Le Commando devrait être dans weapon_ids.py
    try:
        from src.data.weapon_ids import WEAPON_IDS

        for wid, name in WEAPON_IDS.items():
            if "commando" in name.lower():
                return wid
    except:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description="Analyser avec variations d'offset")
    parser.add_argument("--match-id", help="ID du match (partiel)")
    parser.add_argument("--player", default="sixxt", help="Joueur à chercher")
    parser.add_argument(
        "--target-time", type=float, help="Timestamp cible en secondes (ex: 512 pour 8:32)"
    )

    args = parser.parse_args()

    # Chercher les chunks pour ce match
    investigation_dir = Path("data/investigation")
    chunks = list(investigation_dir.rglob("type3_*.bin"))

    if args.match_id:
        chunks = [c for c in chunks if args.match_id in str(c)]

    print(f"Chunks trouvés: {len(chunks)}\n")

    commando_id = find_commando_weapon_id()
    print(
        f"Commando weapon ID (référence): {commando_id:04X}"
        if commando_id
        else "Commando weapon ID: non trouvé\n"
    )

    # Tester différents offsets
    kill_pattern = bytes([0x00, 0x32, 0x00])

    # Offsets à tester
    ts_offsets = [3, 4, 5, 6, 7, 8]  # Offset pour le timestamp
    weapon_starts = [5, 6, 7, 8, 9, 10, 12, 15, 20]  # Début de recherche weapon ID
    weapon_ends = [45, 50, 60, 80]  # Fin de recherche weapon ID

    best_matches = []

    for chunk_path in chunks:
        print(f"\n=== Analyse: {chunk_path.name} ===\n")

        try:
            data = chunk_path.read_bytes()
            try:
                data = zlib.decompress(data)
            except:
                pass

            # Tester toutes les combinaisons d'offsets
            for ts_off in ts_offsets:
                for ws in weapon_starts:
                    for we in weapon_ends:
                        if we <= ws:
                            continue

                        events = extract_with_offset(data, kill_pattern, ts_off, ws, we)

                        # Filtrer les events du joueur cible
                        player_events = [
                            e
                            for e in events
                            if args.player.lower() in (e["gamertag"] or "").lower()
                        ]

                        if not player_events:
                            continue

                        # Vérifier si on trouve un event proche du timestamp cible
                        if args.target_time:
                            for event in player_events:
                                delta = abs(event["timestamp_sec"] - args.target_time)
                                if delta < 5:  # Dans les 5 secondes
                                    best_matches.append(
                                        {
                                            "chunk": chunk_path.name,
                                            "event": event,
                                            "ts_offset": ts_off,
                                            "weapon_start": ws,
                                            "weapon_end": we,
                                            "delta_time": delta,
                                        }
                                    )
                        else:
                            # Afficher tous les events du joueur
                            for event in player_events:
                                mins = int(event["timestamp_sec"] // 60)
                                secs = int(event["timestamp_sec"] % 60)
                                time_str = f"{mins}:{secs:02d}"
                                weapon = event.get("weapon_id_hex", "?") or "?"
                                print(
                                    f"  Offset TS={ts_off}, WS={ws}: {time_str} | {event['gamertag']} | {weapon}"
                                )

        except Exception as e:
            print(f"Erreur: {e}")
            continue

    # Afficher les meilleurs matches
    if best_matches:
        print("\n=== MEILLEURS MATCHES (delta < 5s) ===\n")
        best_matches.sort(key=lambda x: x["delta_time"])

        for match in best_matches[:10]:
            event = match["event"]
            mins = int(event["timestamp_sec"] // 60)
            secs = int(event["timestamp_sec"] % 60)
            time_str = f"{mins}:{secs:02d}"
            print(f"Chunk: {match['chunk']}")
            print(f"  Time: {time_str} (delta: {match['delta_time']:.2f}s)")
            print(f"  Player: {event['gamertag']}")
            print(f"  Weapon: {event.get('weapon_id_hex', '?')}")
            print(f"  Offset TS: {match['ts_offset']}, Weapon start: {match['weapon_start']}")
            print()

    return 0


if __name__ == "__main__":
    exit(main())
