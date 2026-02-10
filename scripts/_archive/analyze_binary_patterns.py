#!/usr/bin/env python3
"""
Script d'analyse des patterns binaires pour identifier les weapon IDs.

Approche : Partir des gamertags connus et analyser le contexte binaire.

Structure observée dans les film chunks :
- Le marker 0x2D 0xC0 indique une paire XUID/Gamertag
- XUID: 8 bytes avant le marker (little-endian)
- Gamertag: avant le XUID (UTF-16 BE)
- HYPOTHÈSE: les bytes après le marker contiennent des infos (weapon, damage, etc.)

Usage:
    # Analyser les chunks d'un match avec les gamertags connus
    python scripts/analyze_binary_patterns.py \\
        --chunks-dir data/investigation/chunks_xxx/ \\
        --gamertags "XxDaemonGamerxX,JGtm,Madina97294"

    # Analyser avec les XUIDs
    python scripts/analyze_binary_patterns.py \\
        --chunks-dir data/investigation/chunks_xxx/ \\
        --xuids "2533274833178266,2533274823110022"
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Marker observé dans les film chunks (indique une structure XUID/Gamertag)
MARKER = b"\x2d\xc0"

# Structure alternative: marker pour les events
EVENT_MARKERS = [
    b"\x2d\xc0",  # Marker principal (roster)
    b"\x00\x32",  # Possible marker kill (type 50 = 0x32)
    b"\x00\x14",  # Possible marker death (type 20 = 0x14)
]


@dataclass
class BinaryContext:
    """Contexte binaire autour d'un gamertag/XUID."""

    chunk_name: str
    bit_offset: int
    marker_offset: int
    xuid: int
    gamertag: str

    # Bytes avant le gamertag (32 bytes)
    pre_gamertag_bytes: list[int]
    # Bytes après le marker (64 bytes)
    post_marker_bytes: list[int]

    # Hex dumps
    pre_hex: str
    post_hex: str


@dataclass
class EventCandidate:
    """Candidat event (kill/death) avec contexte binaire."""

    chunk_name: str
    offset: int
    bit_offset: int

    # Données de l'event
    event_type: int | None  # 50=kill, 20=death
    timestamp_ms: int | None

    # Contexte binaire
    surrounding_bytes: list[int]  # 64 bytes autour
    hex_dump: str


def shift_bytes(data: bytes, bit_offset: int) -> bytes:
    """Décale les bytes pour l'alignement bit-level."""
    if bit_offset == 0:
        return data
    if not (0 <= bit_offset <= 7):
        raise ValueError("bit_offset must be 0..7")

    out = bytearray(max(0, len(data) - 1))
    inv = 8 - bit_offset
    for i in range(len(out)):
        out[i] = ((data[i] << bit_offset) & 0xFF) | (data[i + 1] >> inv)
    return bytes(out)


def hex_dump(data: bytes, width: int = 16) -> str:
    """Génère un dump hexadécimal formaté."""
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i : i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:04x}: {hex_part:<{width * 3}} |{ascii_part}|")
    return "\n".join(lines)


def looks_like_xuid(x: int) -> bool:
    """Vérifie si une valeur ressemble à un XUID valide."""
    return 10**11 <= x <= 10**20


def decode_gamertag_utf16be(buf: bytes) -> str:
    """Décode un gamertag en UTF-16 BE."""
    try:
        s = buf.decode("utf-16-be", errors="ignore")
    except Exception:
        return ""
    return s.replace("\x00", "").strip()


def looks_like_gamertag(s: str) -> bool:
    """Vérifie si une chaîne ressemble à un gamertag valide."""
    v = (s or "").strip()
    if not v:
        return False
    if "\x00" in v:
        return False
    if any(ord(ch) < 32 for ch in v):
        return False
    if not v.isprintable():
        return False
    if not (3 <= len(v) <= 20):
        return False
    if not any(ch.isalnum() for ch in v):
        return False
    return True


def find_marker_contexts(
    chunk: bytes,
    chunk_name: str,
    expected_xuids: set[int] | None = None,
) -> list[BinaryContext]:
    """
    Trouve toutes les occurrences du marker et analyse le contexte.

    Pour chaque marker trouvé :
    - Extrait le XUID (8 bytes avant)
    - Extrait le gamertag (avant le XUID)
    - Extrait les bytes post-marker pour analyse
    """
    results: list[BinaryContext] = []
    seen: set[tuple[int, int]] = set()  # (bit_offset, offset)

    for bit_off in range(8):
        view = shift_bytes(chunk, bit_off)

        pos = 0
        while True:
            idx = view.find(MARKER, pos)
            if idx < 0:
                break

            # Vérifier qu'on n'a pas déjà traité
            key = (bit_off, idx)
            if key in seen:
                pos = idx + 2
                continue
            seen.add(key)

            # XUID: 8 bytes avant le marker
            xuid_pos = idx - 8
            if xuid_pos < 0:
                pos = idx + 2
                continue

            xuid_bytes = view[xuid_pos : xuid_pos + 8]
            if len(xuid_bytes) < 8:
                pos = idx + 2
                continue

            xuid = int.from_bytes(xuid_bytes, "little", signed=False)

            if not looks_like_xuid(xuid):
                pos = idx + 2
                continue

            # Filtrer par XUIDs attendus si fournis
            if expected_xuids and xuid not in expected_xuids:
                pos = idx + 2
                continue

            # Gamertag: fenêtre avant le XUID (160 bytes max)
            gt_start = max(0, xuid_pos - 160)
            gt_window = view[gt_start:xuid_pos]

            # Chercher le gamertag (UTF-16 BE)
            gamertag = ""
            for gt_len in range(40, 6, -2):  # Tailles décroissantes
                if gt_len > len(gt_window):
                    continue
                candidate = gt_window[-gt_len:]
                decoded = decode_gamertag_utf16be(candidate)
                if looks_like_gamertag(decoded):
                    gamertag = decoded
                    break

            if not gamertag:
                # Fallback: prendre les derniers 32 bytes et décoder
                raw = gt_window[-32:] if len(gt_window) >= 32 else gt_window
                gamertag = decode_gamertag_utf16be(raw)

            # Bytes avant le gamertag (32 bytes)
            pre_gt_start = max(0, gt_start - 32)
            pre_gt = list(view[pre_gt_start:gt_start])

            # Bytes après le marker (64 bytes)
            post_start = idx + 2
            post_end = min(post_start + 64, len(view))
            post_marker = list(view[post_start:post_end])

            results.append(
                BinaryContext(
                    chunk_name=chunk_name,
                    bit_offset=bit_off,
                    marker_offset=idx,
                    xuid=xuid,
                    gamertag=gamertag if looks_like_gamertag(gamertag) else f"XUID_{xuid}",
                    pre_gamertag_bytes=pre_gt,
                    post_marker_bytes=post_marker,
                    pre_hex=" ".join(f"{b:02x}" for b in pre_gt[:16]),
                    post_hex=" ".join(f"{b:02x}" for b in post_marker[:32]),
                )
            )

            pos = idx + 2

    return results


def find_gamertag_occurrences(
    chunk: bytes,
    chunk_name: str,
    gamertag: str,
) -> list[dict[str, Any]]:
    """
    Cherche toutes les occurrences d'un gamertag dans un chunk.

    Retourne le contexte binaire autour de chaque occurrence.
    """
    results: list[dict[str, Any]] = []

    # Encoder le gamertag en différents formats
    encodings = [
        ("utf-16-be", gamertag.encode("utf-16-be")),
        ("utf-16-le", gamertag.encode("utf-16-le")),
        ("ascii", gamertag.encode("ascii", errors="ignore")),
    ]

    for encoding_name, gt_bytes in encodings:
        if not gt_bytes:
            continue

        for bit_off in range(8):
            view = shift_bytes(chunk, bit_off)

            pos = 0
            while True:
                idx = view.find(gt_bytes, pos)
                if idx < 0:
                    break

                # Contexte: 32 bytes avant, 64 bytes après
                pre_start = max(0, idx - 32)
                post_end = min(idx + len(gt_bytes) + 64, len(view))

                pre_bytes = list(view[pre_start:idx])
                post_bytes = list(view[idx + len(gt_bytes) : post_end])

                results.append(
                    {
                        "chunk": chunk_name,
                        "encoding": encoding_name,
                        "bit_offset": bit_off,
                        "offset": idx,
                        "pre_bytes": pre_bytes,
                        "post_bytes": post_bytes,
                        "pre_hex": " ".join(f"{b:02x}" for b in pre_bytes[-16:]),
                        "post_hex": " ".join(f"{b:02x}" for b in post_bytes[:32]),
                    }
                )

                pos = idx + 1

    return results


def analyze_post_marker_patterns(contexts: list[BinaryContext]) -> dict[str, Any]:
    """
    Analyse les patterns dans les bytes après le marker.

    Objectif : Identifier des bytes qui pourraient encoder weapon_id, damage_type, etc.
    """
    if not contexts:
        return {"error": "Aucun contexte à analyser"}

    # Grouper par joueur
    by_player: dict[str, list[BinaryContext]] = defaultdict(list)
    for ctx in contexts:
        by_player[ctx.gamertag].append(ctx)

    analysis: dict[str, Any] = {
        "total_contexts": len(contexts),
        "players": list(by_player.keys()),
        "contexts_per_player": {k: len(v) for k, v in by_player.items()},
    }

    # Analyser chaque position des post_marker_bytes
    post_patterns: list[dict[str, Any]] = []
    for pos in range(
        min(32, min(len(c.post_marker_bytes) for c in contexts if c.post_marker_bytes))
    ):
        values = [c.post_marker_bytes[pos] for c in contexts if len(c.post_marker_bytes) > pos]
        if values:
            unique = sorted(set(values))
            post_patterns.append(
                {
                    "position": pos,
                    "unique_count": len(unique),
                    "min": min(values),
                    "max": max(values),
                    "samples": unique[:10],
                    "variance": "low"
                    if len(unique) < 5
                    else "medium"
                    if len(unique) < 20
                    else "high",
                    "candidate_type": _guess_field_type(unique),
                }
            )

    analysis["post_marker_patterns"] = post_patterns

    # Identifier les positions candidates pour weapon_id
    # Critères: variance moyenne (5-20 valeurs uniques), pas tous zeros
    weapon_candidates = []
    for p in post_patterns:
        if 3 <= p["unique_count"] <= 20 and p["max"] > 0:
            weapon_candidates.append(
                {
                    "position": p["position"],
                    "unique_values": p["unique_count"],
                    "samples": p["samples"],
                }
            )

    analysis["weapon_id_candidates"] = weapon_candidates

    return analysis


def _guess_field_type(values: list[int]) -> str:
    """Devine le type de champ basé sur les valeurs."""
    if not values:
        return "empty"

    if all(v == 0 for v in values):
        return "padding (all zeros)"

    if len(set(values)) == 1:
        return f"constant ({values[0]})"

    if len(set(values)) == 2:
        return "flag/boolean"

    if all(v < 16 for v in values):
        return "small_int (nibble)"

    if all(v < 100 for v in values):
        return "small_int"

    if len(set(values)) < 10:
        return "enum/type_id"

    return "variable"


def safe_print(text: str) -> None:
    """Print avec gestion des caractères Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Analyse des patterns binaires pour identifier les weapon IDs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--chunks-dir", type=Path, required=True, help="Dossier contenant les chunks .bin"
    )
    parser.add_argument("--gamertags", help="Gamertags à chercher (séparés par virgule)")
    parser.add_argument("--xuids", help="XUIDs à filtrer (séparés par virgule)")
    parser.add_argument("--output", type=Path, help="Fichier JSON de sortie")
    parser.add_argument("--limit", type=int, default=20, help="Nombre max de contextes à afficher")

    args = parser.parse_args()

    # Collecter les fichiers chunks
    chunk_files = sorted(args.chunks_dir.glob("*.bin")) if args.chunks_dir.exists() else []

    if not chunk_files:
        print("ERREUR: Aucun fichier chunk trouvé")
        return 1

    print(f"Analyse de {len(chunk_files)} fichier(s) chunk...")

    # Parser les filtres
    expected_xuids: set[int] | None = None
    if args.xuids:
        expected_xuids = set()
        for x in args.xuids.split(","):
            try:
                expected_xuids.add(int(x.strip()))
            except ValueError:
                pass
        print(f"Filtrage par XUIDs: {expected_xuids}")

    gamertags_to_search: list[str] = []
    if args.gamertags:
        gamertags_to_search = [g.strip() for g in args.gamertags.split(",")]
        print(f"Gamertags à chercher: {gamertags_to_search}")

    # Collecter les contextes
    all_contexts: list[BinaryContext] = []
    all_gamertag_occurrences: list[dict[str, Any]] = []

    for chunk_path in chunk_files:
        safe_print(f"\n--- {chunk_path.name} ---")

        try:
            chunk_data = chunk_path.read_bytes()
            safe_print(f"Taille: {len(chunk_data):,} bytes")
        except Exception as e:
            safe_print(f"Erreur lecture: {e}")
            continue

        # Trouver les contextes via marker
        contexts = find_marker_contexts(chunk_data, chunk_path.name, expected_xuids)
        safe_print(f"Marker contexts: {len(contexts)}")
        all_contexts.extend(contexts)

        # Chercher les gamertags spécifiques
        for gt in gamertags_to_search:
            occurrences = find_gamertag_occurrences(chunk_data, chunk_path.name, gt)
            if occurrences:
                safe_print(f"  Occurrences de '{gt}': {len(occurrences)}")
                all_gamertag_occurrences.extend(occurrences)

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {len(all_contexts)} contextes marker")
    if all_gamertag_occurrences:
        print(f"TOTAL: {len(all_gamertag_occurrences)} occurrences gamertag")
    print(f"{'=' * 60}")

    # Afficher les contextes
    for i, ctx in enumerate(all_contexts[: args.limit]):
        safe_print(f"\n[Context {i + 1}] {ctx.gamertag} (XUID: {ctx.xuid})")
        safe_print(f"  Chunk: {ctx.chunk_name}, offset={ctx.marker_offset}, bit={ctx.bit_offset}")
        safe_print(f"  Pre-gamertag (16b): {ctx.pre_hex}")
        safe_print(f"  Post-marker (32b): {ctx.post_hex}")

    if len(all_contexts) > args.limit:
        safe_print(f"\n... ({len(all_contexts) - args.limit} contextes supplémentaires)")

    # Analyser les patterns
    if all_contexts:
        print(f"\n{'=' * 60}")
        print("ANALYSE DES PATTERNS POST-MARKER")
        print(f"{'=' * 60}")

        analysis = analyze_post_marker_patterns(all_contexts)

        safe_print(f"\nTotal contextes: {analysis['total_contexts']}")
        safe_print(f"Joueurs: {len(analysis['players'])}")

        if analysis.get("weapon_id_candidates"):
            safe_print("\n[Positions candidates weapon_id]")
            for c in analysis["weapon_id_candidates"][:10]:
                safe_print(
                    f"  Position {c['position']}: {c['unique_values']} valeurs - {c['samples']}"
                )

        # Patterns intéressants
        safe_print("\n[Tous les patterns post-marker]")
        for p in analysis.get("post_marker_patterns", [])[:16]:
            safe_print(
                f"  Pos {p['position']:2d}: {p['unique_count']:3d} uniques, {p['candidate_type']}"
            )
            if p["unique_count"] < 10:
                safe_print(f"         -> {p['samples']}")

    # Sauvegarder en JSON
    if args.output:
        output_data = {
            "total_contexts": len(all_contexts),
            "contexts": [
                {
                    "chunk": c.chunk_name,
                    "bit_offset": c.bit_offset,
                    "marker_offset": c.marker_offset,
                    "xuid": c.xuid,
                    "gamertag": c.gamertag,
                    "pre_gamertag_bytes": c.pre_gamertag_bytes,
                    "post_marker_bytes": c.post_marker_bytes,
                }
                for c in all_contexts
            ],
            "gamertag_occurrences": all_gamertag_occurrences,
        }

        if all_contexts:
            output_data["analysis"] = analyze_post_marker_patterns(all_contexts)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        safe_print(f"\nRésultats sauvegardés: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
