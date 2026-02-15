#!/usr/bin/env python3
"""
Script pour trouver les kill/death events par type byte.

Structure hypothétique :
- Type byte: 0x32 (50) = kill, 0x14 (20) = death
- Timestamp: 4 bytes (little-endian) proche du type byte
- Player index: 1 byte (0-15)
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EventCandidate:
    """Candidat event trouvé dans un chunk."""

    chunk_name: str
    chunk_start_ms: int
    chunk_end_ms: int
    offset: int
    event_type: int
    event_type_name: str

    # Timestamp candidat
    timestamp_ms: int
    timestamp_offset: int  # Offset relatif au type byte

    # Contexte
    context_before: list[int]
    context_after: list[int]

    # Score de confiance
    confidence: float


def find_events_in_chunk(
    chunk: bytes,
    chunk_name: str,
    chunk_start_ms: int,
    chunk_end_ms: int,
) -> list[EventCandidate]:
    """
    Cherche les events kill/death dans un chunk.

    Stratégie : chercher les bytes 0x32 (kill) ou 0x14 (death)
    puis vérifier si un timestamp plausible existe à proximité.
    """
    results: list[EventCandidate] = []

    type_bytes = {
        0x32: ("kill", 50),
        0x14: ("death", 20),
    }

    for type_byte, (type_name, type_value) in type_bytes.items():
        pos = 0
        while True:
            idx = chunk.find(bytes([type_byte]), pos)
            if idx < 0:
                break

            # Chercher un timestamp plausible à différents offsets
            for ts_offset in range(-8, 12, 1):  # -8 à +11 bytes
                ts_pos = idx + ts_offset
                if ts_pos < 0 or ts_pos + 4 > len(chunk):
                    continue

                ts_bytes = chunk[ts_pos : ts_pos + 4]
                ts_ms = struct.unpack("<I", ts_bytes)[0]

                # Vérifier si le timestamp est dans la plage du chunk
                # Avec une tolérance de 5000ms pour les événements de transition
                if chunk_start_ms - 5000 <= ts_ms <= chunk_end_ms + 5000:
                    # Calculer un score de confiance
                    confidence = 0.5

                    # Bonus si le timestamp est pile dans la plage
                    if chunk_start_ms <= ts_ms <= chunk_end_ms:
                        confidence += 0.3

                    # Bonus si le type byte est entouré de zeros (padding)
                    if idx > 0 and chunk[idx - 1] == 0:
                        confidence += 0.1
                    if idx + 1 < len(chunk) and chunk[idx + 1] == 0:
                        confidence += 0.1

                    # Extraire le contexte
                    ctx_start = max(0, idx - 16)
                    ctx_end = min(len(chunk), idx + 16)

                    results.append(
                        EventCandidate(
                            chunk_name=chunk_name,
                            chunk_start_ms=chunk_start_ms,
                            chunk_end_ms=chunk_end_ms,
                            offset=idx,
                            event_type=type_value,
                            event_type_name=type_name,
                            timestamp_ms=ts_ms,
                            timestamp_offset=ts_offset,
                            context_before=list(chunk[ctx_start:idx]),
                            context_after=list(chunk[idx:ctx_end]),
                            confidence=confidence,
                        )
                    )

            pos = idx + 1

    return results


def deduplicate_events(events: list[EventCandidate]) -> list[EventCandidate]:
    """
    Déduplique les events par timestamp et type.
    Garde celui avec la meilleure confiance.
    """
    # Grouper par (timestamp arrondi à 500ms, type)
    groups: dict[tuple[int, int], list[EventCandidate]] = defaultdict(list)

    for e in events:
        key = (e.timestamp_ms // 500, e.event_type)
        groups[key].append(e)

    # Garder le meilleur de chaque groupe
    best = []
    for group_events in groups.values():
        best_event = max(group_events, key=lambda x: x.confidence)
        best.append(best_event)

    return sorted(best, key=lambda x: x.timestamp_ms)


def safe_print(text: str) -> None:
    """Print avec gestion Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Trouver les kill/death events par type byte")
    parser.add_argument("--chunks-dir", type=Path, required=True, help="Dossier des chunks")
    parser.add_argument("--manifest", type=Path, required=True, help="Fichier manifest JSON")
    parser.add_argument("--min-confidence", type=float, default=0.7, help="Confiance minimale")
    parser.add_argument("--output", type=Path, help="Fichier JSON de sortie")

    args = parser.parse_args()

    # Charger le manifest pour les timestamps des chunks
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    chunks_info = {
        f"type{c['ChunkType']}___filmChunk{c['Index']}.bin": {
            "start_ms": c["ChunkStartTimeOffsetMilliseconds"],
            "end_ms": c["ChunkStartTimeOffsetMilliseconds"] + c["DurationMilliseconds"],
        }
        for c in manifest["CustomData"]["Chunks"]
    }

    chunk_files = sorted(args.chunks_dir.glob("*.bin"))

    if not chunk_files:
        print("ERREUR: Aucun chunk trouvé")
        return 1

    safe_print(f"Analyse de {len(chunk_files)} chunks...")

    all_events: list[EventCandidate] = []

    for chunk_path in chunk_files:
        chunk_data = chunk_path.read_bytes()

        # Trouver les infos de timing du chunk
        info = chunks_info.get(chunk_path.name, {"start_ms": 0, "end_ms": 0})

        events = find_events_in_chunk(
            chunk_data,
            chunk_path.name,
            info["start_ms"],
            info["end_ms"],
        )

        # Filtrer par confiance
        events = [e for e in events if e.confidence >= args.min_confidence]

        if events:
            safe_print(f"  {chunk_path.name}: {len(events)} events (conf >= {args.min_confidence})")

        all_events.extend(events)

    # Dédupliquer
    unique_events = deduplicate_events(all_events)

    safe_print(f"\n{'=' * 60}")
    safe_print(f"TOTAL: {len(all_events)} events bruts")
    safe_print(f"TOTAL: {len(unique_events)} events uniques")
    safe_print(f"{'=' * 60}")

    # Compter par type
    by_type = Counter(e.event_type_name for e in unique_events)
    safe_print(f"\nPar type: {dict(by_type)}")

    # Afficher les events
    safe_print("\n[Events triés par timestamp]")
    for e in unique_events[:30]:
        ctx_hex = " ".join(f"{b:02x}" for b in e.context_after[:8])
        safe_print(
            f"  {e.timestamp_ms/1000:6.1f}s {e.event_type_name:5s} (conf={e.confidence:.2f}) [{ctx_hex}]"
        )

    if len(unique_events) > 30:
        safe_print(f"  ... et {len(unique_events) - 30} autres")

    # Sauvegarder
    if args.output:
        output_data = {
            "total_raw": len(all_events),
            "total_unique": len(unique_events),
            "by_type": dict(by_type),
            "events": [
                {
                    "chunk": e.chunk_name,
                    "offset": e.offset,
                    "type": e.event_type_name,
                    "timestamp_ms": e.timestamp_ms,
                    "timestamp_sec": e.timestamp_ms / 1000,
                    "ts_offset": e.timestamp_offset,
                    "confidence": e.confidence,
                    "context_hex": " ".join(f"{b:02x}" for b in e.context_after[:16]),
                }
                for e in unique_events
            ],
        }

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        safe_print(f"\nRésultats sauvegardés: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
