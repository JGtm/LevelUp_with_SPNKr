#!/usr/bin/env python3
"""
Script pour trouver les patterns de kill events dans les chunks binaires.

Approche : Chercher des structures qui contiennent le XUID du joueur
et des données qui varient (potentiellement weapon_id, damage, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class XuidContext:
    """Contexte binaire autour d'une occurrence de XUID."""

    chunk_name: str
    offset: int
    byte_order: str  # 'little' ou 'big'

    # Bytes autour du XUID
    pre_bytes: list[int]  # 32 bytes avant
    post_bytes: list[int]  # 64 bytes après

    # Données extraites
    post_uint32_0: int  # Premier uint32 après XUID
    post_uint32_1: int  # Deuxième uint32 après XUID
    post_uint16_0: int  # Premier uint16 après XUID


def find_xuid_in_chunk(chunk: bytes, xuid: int, chunk_name: str) -> list[XuidContext]:
    """
    Cherche toutes les occurrences d'un XUID dans un chunk.

    Teste les deux byte orders (little et big endian).
    """
    results: list[XuidContext] = []

    xuid_le = xuid.to_bytes(8, "little")
    xuid_be = xuid.to_bytes(8, "big")

    for xuid_bytes, byte_order in [(xuid_le, "little"), (xuid_be, "big")]:
        pos = 0
        while True:
            idx = chunk.find(xuid_bytes, pos)
            if idx < 0:
                break

            # Extraire le contexte
            pre_start = max(0, idx - 32)
            post_end = min(idx + 8 + 64, len(chunk))

            pre_bytes = list(chunk[pre_start:idx])
            post_bytes = list(chunk[idx + 8 : post_end])

            # Parser les premiers bytes après le XUID comme différents types
            post_uint32_0 = (
                int.from_bytes(chunk[idx + 8 : idx + 12], "little") if idx + 12 <= len(chunk) else 0
            )
            post_uint32_1 = (
                int.from_bytes(chunk[idx + 12 : idx + 16], "little")
                if idx + 16 <= len(chunk)
                else 0
            )
            post_uint16_0 = (
                int.from_bytes(chunk[idx + 8 : idx + 10], "little") if idx + 10 <= len(chunk) else 0
            )

            results.append(
                XuidContext(
                    chunk_name=chunk_name,
                    offset=idx,
                    byte_order=byte_order,
                    pre_bytes=pre_bytes,
                    post_bytes=post_bytes,
                    post_uint32_0=post_uint32_0,
                    post_uint32_1=post_uint32_1,
                    post_uint16_0=post_uint16_0,
                )
            )

            pos = idx + 1

    return results


def analyze_xuid_contexts(contexts: list[XuidContext]) -> dict[str, Any]:
    """
    Analyse les contextes pour trouver des patterns.

    Hypothèse : Les kill events ont des structures similaires avec
    quelques bytes qui varient (weapon_id, timestamp, etc.)
    """
    if not contexts:
        return {"error": "Aucun contexte"}

    analysis: dict[str, Any] = {
        "total_occurrences": len(contexts),
        "by_byte_order": Counter(c.byte_order for c in contexts),
        "by_chunk": Counter(c.chunk_name for c in contexts),
    }

    # Analyser les uint32 après le XUID
    uint32_0_values = Counter(c.post_uint32_0 for c in contexts)
    uint32_1_values = Counter(c.post_uint32_1 for c in contexts)

    analysis["post_uint32_0_unique"] = len(uint32_0_values)
    analysis["post_uint32_0_top"] = uint32_0_values.most_common(10)
    analysis["post_uint32_1_unique"] = len(uint32_1_values)
    analysis["post_uint32_1_top"] = uint32_1_values.most_common(10)

    # Chercher des patterns dans les bytes post-XUID
    # Regrouper par "signature" des 8 premiers bytes après XUID
    signatures: dict[tuple[int, ...], list[XuidContext]] = defaultdict(list)
    for c in contexts:
        sig = tuple(c.post_bytes[:8])
        signatures[sig].append(c)

    analysis["unique_8byte_signatures"] = len(signatures)

    # Signatures qui apparaissent plusieurs fois = potentiels patterns
    repeated_sigs = [(sig, ctxs) for sig, ctxs in signatures.items() if len(ctxs) > 1]
    analysis["repeated_signatures"] = len(repeated_sigs)

    # Détail des signatures répétées
    sig_details = []
    for sig, ctxs in sorted(repeated_sigs, key=lambda x: -len(x[1]))[:10]:
        sig_details.append(
            {
                "signature_hex": " ".join(f"{b:02x}" for b in sig),
                "count": len(ctxs),
                "chunks": list(set(c.chunk_name for c in ctxs)),
            }
        )
    analysis["top_repeated_signatures"] = sig_details

    return analysis


def find_potential_kill_structures(
    chunk: bytes,
    xuid: int,
    chunk_name: str,
    match_duration_ms: int = 330000,
) -> list[dict[str, Any]]:
    """
    Cherche des structures qui pourraient être des kill events.

    Critères :
    - Contient le XUID du killer
    - A un timestamp plausible (0 < t < match_duration)
    - A une structure cohérente
    """
    results: list[dict[str, Any]] = []

    xuid_le = xuid.to_bytes(8, "little")

    pos = 0
    while True:
        idx = chunk.find(xuid_le, pos)
        if idx < 0:
            break

        # Vérifier qu'on a assez de bytes après
        if idx + 32 > len(chunk):
            pos = idx + 1
            continue

        # Lire différentes interprétations des bytes après le XUID
        after = chunk[idx + 8 : idx + 40]

        # Hypothèse 1: timestamp uint32 à offset +0
        ts0 = int.from_bytes(after[0:4], "little")

        # Hypothèse 2: timestamp uint32 à offset +4
        ts4 = int.from_bytes(after[4:8], "little")

        # Hypothèse 3: timestamp uint32 à offset +8
        ts8 = int.from_bytes(after[8:12], "little")

        # Vérifier si un des timestamps est plausible
        for ts_name, ts_val in [("ts+0", ts0), ("ts+4", ts4), ("ts+8", ts8)]:
            if 0 < ts_val < match_duration_ms:
                # Possible kill event !
                results.append(
                    {
                        "chunk": chunk_name,
                        "offset": idx,
                        "timestamp_field": ts_name,
                        "timestamp_ms": ts_val,
                        "timestamp_sec": ts_val / 1000,
                        "after_bytes_hex": " ".join(f"{b:02x}" for b in after[:16]),
                        "before_bytes_hex": " ".join(
                            f"{b:02x}" for b in chunk[max(0, idx - 8) : idx]
                        ),
                    }
                )

        pos = idx + 1

    return results


def safe_print(text: str) -> None:
    """Print avec gestion des caractères Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Trouver les patterns de kill events dans les chunks binaires",
    )

    parser.add_argument("--chunks-dir", type=Path, required=True, help="Dossier des chunks")
    parser.add_argument("--xuid", type=int, required=True, help="XUID du joueur")
    parser.add_argument("--match-duration", type=int, default=330000, help="Durée du match en ms")
    parser.add_argument("--output", type=Path, help="Fichier JSON de sortie")

    args = parser.parse_args()

    chunk_files = sorted(args.chunks_dir.glob("*.bin")) if args.chunks_dir.exists() else []

    if not chunk_files:
        print("ERREUR: Aucun chunk trouvé")
        return 1

    safe_print(f"Analyse de {len(chunk_files)} chunks pour XUID {args.xuid}...")
    safe_print(f"Durée match: {args.match_duration} ms ({args.match_duration/1000:.1f}s)")

    all_contexts: list[XuidContext] = []
    all_potential_kills: list[dict[str, Any]] = []

    for chunk_path in chunk_files:
        chunk_data = chunk_path.read_bytes()

        # Chercher toutes les occurrences du XUID
        contexts = find_xuid_in_chunk(chunk_data, args.xuid, chunk_path.name)
        all_contexts.extend(contexts)

        # Chercher des structures de kill potentielles
        potential_kills = find_potential_kill_structures(
            chunk_data, args.xuid, chunk_path.name, args.match_duration
        )
        all_potential_kills.extend(potential_kills)

        safe_print(
            f"  {chunk_path.name}: {len(contexts)} XUID occurrences, {len(potential_kills)} potential kills"
        )

    safe_print(f"\n{'=' * 60}")
    safe_print(f"TOTAL: {len(all_contexts)} occurrences XUID")
    safe_print(f"TOTAL: {len(all_potential_kills)} structures potentiellement kill")
    safe_print(f"{'=' * 60}")

    # Analyser les contextes
    if all_contexts:
        analysis = analyze_xuid_contexts(all_contexts)

        safe_print("\n[Analyse des occurrences XUID]")
        safe_print(f"  Par byte order: {dict(analysis['by_byte_order'])}")
        safe_print(f"  Signatures 8-bytes uniques: {analysis['unique_8byte_signatures']}")
        safe_print(f"  Signatures répétées: {analysis['repeated_signatures']}")

        if analysis.get("top_repeated_signatures"):
            safe_print("\n  Top signatures répétées:")
            for sig in analysis["top_repeated_signatures"][:5]:
                safe_print(f"    {sig['count']}x: {sig['signature_hex']}")

    # Afficher les kills potentiels
    if all_potential_kills:
        safe_print("\n[Structures potentiellement kill]")

        # Trier par timestamp
        sorted_kills = sorted(all_potential_kills, key=lambda x: x["timestamp_ms"])

        # Dédupliquer par timestamp (même kill dans plusieurs chunks)
        seen_ts: set[int] = set()
        unique_kills = []
        for k in sorted_kills:
            ts = k["timestamp_ms"]
            # Tolérance de 100ms pour les doublons
            if not any(abs(ts - seen) < 100 for seen in seen_ts):
                unique_kills.append(k)
                seen_ts.add(ts)

        safe_print(f"  Kills uniques (par timestamp): {len(unique_kills)}")

        for k in unique_kills[:15]:
            safe_print(f"\n  @ {k['timestamp_sec']:.1f}s ({k['timestamp_field']})")
            safe_print(f"    Chunk: {k['chunk']}, offset: {k['offset']}")
            safe_print(f"    Before: {k['before_bytes_hex']}")
            safe_print(f"    After:  {k['after_bytes_hex']}")

    # Sauvegarder
    if args.output:
        output_data = {
            "xuid": args.xuid,
            "match_duration_ms": args.match_duration,
            "total_xuid_occurrences": len(all_contexts),
            "total_potential_kills": len(all_potential_kills),
            "xuid_analysis": analyze_xuid_contexts(all_contexts) if all_contexts else {},
            "potential_kills": all_potential_kills,
        }

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        safe_print(f"\nRésultats sauvegardés: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
