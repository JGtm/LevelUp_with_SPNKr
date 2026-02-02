#!/usr/bin/env python3
"""
Script pour corréler les kills connus avec les patterns binaires.

Données connues pour le match 7f1bbf06-d54d-4434-ad80-923fcabe8b1b:
- Killer: JGtm (XUID: 2533274823110022)
- Frag 2: ~169s, Sidekick, victime breizhbengp (2535454710220286)
- Frag 3: ~220s, Sidekick, victime breizhbengp
- Frag 4: ~231s, Sidekick, victime HJ Destroyer (2683394777983413)
- Frag 5: ~251s, Sidekick, victime Ecaru (2533274811165209)
- Frag 6: ~297s, Sidekick, victime breizhbengp
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Données du match
KILLER_XUID = 2533274823110022  # JGtm
VICTIMS = {
    "breizhbengp": 2535454710220286,
    "HJ Destroyer": 2683394777983413,
    "Ecaru": 2533274811165209,
}

# Kills connus avec timestamps approximatifs (en ms)
KNOWN_KILLS = [
    {"time_ms": 169000, "weapon": "Sidekick", "victim": "breizhbengp", "tolerance_ms": 5000},
    {"time_ms": 220000, "weapon": "Sidekick", "victim": "breizhbengp", "tolerance_ms": 5000},
    {"time_ms": 231000, "weapon": "Sidekick", "victim": "HJ Destroyer", "tolerance_ms": 5000},
    {"time_ms": 251000, "weapon": "Sidekick", "victim": "Ecaru", "tolerance_ms": 5000},
    {"time_ms": 297000, "weapon": "Sidekick", "victim": "breizhbengp", "tolerance_ms": 5000},
]


@dataclass
class KillCandidate:
    """Candidat kill trouvé dans les chunks."""

    chunk_name: str
    offset: int

    # XUIDs trouvés
    killer_xuid_found: bool
    victim_xuid: int | None
    victim_name: str | None

    # Timestamp
    timestamp_ms: int | None

    # Contexte binaire
    context_hex: str
    full_context: bytes


def find_victim_xuids_in_chunk(
    chunk: bytes,
    chunk_name: str,
    chunk_start_ms: int,
    chunk_end_ms: int,
) -> list[KillCandidate]:
    """
    Cherche les XUIDs des victimes connues dans un chunk.
    """
    results: list[KillCandidate] = []

    for victim_name, victim_xuid in VICTIMS.items():
        # Chercher le XUID en little-endian
        xuid_le = victim_xuid.to_bytes(8, "little")

        pos = 0
        while True:
            idx = chunk.find(xuid_le, pos)
            if idx < 0:
                break

            # Extraire le contexte (64 bytes avant et après)
            ctx_start = max(0, idx - 64)
            ctx_end = min(len(chunk), idx + 8 + 64)
            full_context = chunk[ctx_start:ctx_end]

            # Chercher un timestamp plausible dans le contexte
            # Tester différentes positions
            timestamp_ms = None
            for ts_offset in range(-32, 40, 4):
                ts_pos = idx + ts_offset
                if ts_pos < 0 or ts_pos + 4 > len(chunk):
                    continue

                ts = struct.unpack("<I", chunk[ts_pos : ts_pos + 4])[0]

                # Timestamp plausible pour ce chunk?
                if chunk_start_ms - 5000 <= ts <= chunk_end_ms + 5000:
                    timestamp_ms = ts
                    break

            # Vérifier si le killer XUID est aussi présent dans le contexte
            killer_xuid_le = KILLER_XUID.to_bytes(8, "little")
            killer_found = killer_xuid_le in full_context

            results.append(
                KillCandidate(
                    chunk_name=chunk_name,
                    offset=idx,
                    killer_xuid_found=killer_found,
                    victim_xuid=victim_xuid,
                    victim_name=victim_name,
                    timestamp_ms=timestamp_ms,
                    context_hex=" ".join(
                        f"{b:02x}" for b in chunk[idx - 16 : idx + 24] if idx >= 16
                    ),
                    full_context=full_context,
                )
            )

            pos = idx + 1

    return results


def find_kill_structure_near_timestamp(
    chunk: bytes,
    chunk_name: str,
    target_ts_ms: int,
    tolerance_ms: int = 5000,
) -> list[dict[str, Any]]:
    """
    Cherche des structures avec un timestamp proche de la cible.
    """
    results: list[dict[str, Any]] = []

    # Scanner le chunk pour trouver des timestamps
    for i in range(0, len(chunk) - 4, 1):
        ts = struct.unpack("<I", chunk[i : i + 4])[0]

        if abs(ts - target_ts_ms) <= tolerance_ms:
            # Timestamp trouvé ! Extraire le contexte
            ctx_start = max(0, i - 32)
            ctx_end = min(len(chunk), i + 36)
            context = chunk[ctx_start:ctx_end]

            # Position relative du timestamp dans le contexte
            ts_rel_pos = i - ctx_start

            # Chercher des XUIDs connus dans le contexte
            killer_found = KILLER_XUID.to_bytes(8, "little") in context
            victim_found = None
            for vname, vxuid in VICTIMS.items():
                if vxuid.to_bytes(8, "little") in context:
                    victim_found = vname
                    break

            results.append(
                {
                    "chunk": chunk_name,
                    "offset": i,
                    "timestamp_ms": ts,
                    "timestamp_sec": ts / 1000,
                    "ts_position_in_context": ts_rel_pos,
                    "killer_xuid_found": killer_found,
                    "victim_found": victim_found,
                    "context_hex": " ".join(f"{b:02x}" for b in context),
                    "context_before_ts": " ".join(f"{b:02x}" for b in context[:ts_rel_pos]),
                    "context_after_ts": " ".join(f"{b:02x}" for b in context[ts_rel_pos + 4 :]),
                }
            )

    return results


def safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Corréler les kills connus avec les patterns binaires"
    )
    parser.add_argument("--chunks-dir", type=Path, required=True, help="Dossier des chunks")
    parser.add_argument("--manifest", type=Path, required=True, help="Fichier manifest JSON")
    parser.add_argument("--output", type=Path, help="Fichier JSON de sortie")

    args = parser.parse_args()

    # Charger le manifest
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    chunks_info = {
        f"type{c['ChunkType']}___filmChunk{c['Index']}.bin": {
            "start_ms": c["ChunkStartTimeOffsetMilliseconds"],
            "end_ms": c["ChunkStartTimeOffsetMilliseconds"] + c["DurationMilliseconds"],
            "index": c["Index"],
        }
        for c in manifest["CustomData"]["Chunks"]
    }

    chunk_files = sorted(args.chunks_dir.glob("*.bin"))

    safe_print(f"Analyse de {len(chunk_files)} chunks...")
    safe_print("\nKills connus à rechercher:")
    for k in KNOWN_KILLS:
        safe_print(f"  {k['time_ms']/1000:.0f}s - {k['weapon']} -> {k['victim']}")

    # Pour chaque kill connu, trouver le chunk correspondant et chercher
    all_results: dict[str, list[dict]] = {}

    for kill in KNOWN_KILLS:
        kill_key = f"{kill['time_ms']/1000:.0f}s_{kill['victim']}"
        safe_print(f"\n{'=' * 60}")
        safe_print(f"Recherche kill: {kill['time_ms']/1000:.0f}s -> {kill['victim']}")
        safe_print(f"{'=' * 60}")

        all_results[kill_key] = []

        for chunk_path in chunk_files:
            info = chunks_info.get(chunk_path.name)
            if not info:
                continue

            # Ce chunk couvre-t-il le timestamp du kill?
            if not (info["start_ms"] - 5000 <= kill["time_ms"] <= info["end_ms"] + 5000):
                continue

            safe_print(
                f"\n  Chunk {chunk_path.name} ({info['start_ms']/1000:.0f}s - {info['end_ms']/1000:.0f}s)"
            )

            chunk_data = chunk_path.read_bytes()

            # Chercher des structures avec ce timestamp
            structures = find_kill_structure_near_timestamp(
                chunk_data,
                chunk_path.name,
                kill["time_ms"],
                kill["tolerance_ms"],
            )

            # Filtrer: garder seulement ceux qui ont le killer ou la victime
            relevant = [s for s in structures if s["killer_xuid_found"] or s["victim_found"]]

            if relevant:
                safe_print(f"    Structures pertinentes: {len(relevant)}")
                for s in relevant[:5]:
                    safe_print(
                        f"      @ {s['timestamp_sec']:.2f}s, killer={s['killer_xuid_found']}, victim={s['victim_found']}"
                    )
                    safe_print(f"        Before TS: {s['context_before_ts'][:50]}...")
                    safe_print(f"        After TS:  {s['context_after_ts'][:50]}...")
                all_results[kill_key].extend(relevant)
            else:
                # Montrer quand même quelques structures avec ce timestamp
                if structures:
                    safe_print(f"    Structures avec timestamp (sans XUID): {len(structures)}")
                    for s in structures[:3]:
                        safe_print(f"      @ {s['timestamp_sec']:.2f}s")
                        safe_print(f"        Context: {s['context_hex'][:80]}...")

    # Résumé
    safe_print(f"\n{'=' * 60}")
    safe_print("RÉSUMÉ")
    safe_print(f"{'=' * 60}")

    for kill_key, results in all_results.items():
        safe_print(f"\n{kill_key}: {len(results)} structures pertinentes")

        if results:
            # Analyser les patterns communs
            # Extraire les bytes avant le timestamp
            before_patterns = [
                r["context_before_ts"][-24:] for r in results if r.get("context_before_ts")
            ]
            if before_patterns:
                safe_print("  Patterns before TS:")
                for p in set(before_patterns):
                    count = before_patterns.count(p)
                    safe_print(f"    {count}x: {p}")

    # Sauvegarder
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        safe_print(f"\nRésultats sauvegardés: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
