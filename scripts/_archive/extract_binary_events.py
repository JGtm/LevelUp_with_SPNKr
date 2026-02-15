#!/usr/bin/env python3
"""
Script d'extraction des events binaires depuis les chunks de film Halo Infinite.

Objectif : Analyser les bytes non documentés des events pour identifier les patterns d'armes.

Structure documentée d'un event (72 bytes) :
- 0-11    : Header (INCONNU - à analyser)
- 12-43   : Gamertag (UTF-16 BE, 32 bytes)
- 44-58   : Padding (0x00)
- 59      : Type (10=mode, 20=death, 50=kill)
- 60-63   : Timestamp (millisecondes, little-endian)
- 64-66   : Padding
- 67      : Medal marker
- 68-70   : Padding
- 71      : Medal ID
- 72+     : BYTES NON DOCUMENTÉS (à analyser)

Usage:
    # Analyser un chunk décompressé
    python scripts/extract_binary_events.py --chunk data/investigation/chunks_xxx/type2__filmChunk1.bin

    # Analyser tous les chunks d'un dossier
    python scripts/extract_binary_events.py --chunks-dir data/investigation/chunks_xxx/

    # Filtrer par gamertag
    python scripts/extract_binary_events.py --chunks-dir ... --gamertag XxDaemonGamerxX

Références :
- https://den.dev/blog/extracting-stats-film-files-halo-infinite/
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class ExtractedEvent:
    """Event extrait d'un chunk binaire."""

    offset_in_chunk: int
    bit_offset: int
    gamertag: str
    event_type: int  # 10=mode, 20=death, 50=kill
    event_type_name: str
    timestamp_ms: int
    medal_marker: int
    medal_id: int

    # Bytes non documentés pour analyse
    header_bytes: list[int]  # 12 bytes
    extra_bytes_32: list[int]  # 32 bytes après offset 72
    extra_bytes_64: list[int]  # 64 bytes après offset 72

    # Hex dumps pour visualisation
    header_hex: str
    extra_hex_32: str
    raw_segment_hex: str


def hex_dump(data: bytes, width: int = 16) -> str:
    """Génère un dump hexadécimal formaté."""
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i : i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:04x}: {hex_part:<{width * 3}} |{ascii_part}|")
    return "\n".join(lines)


def shift_bytes(data: bytes, bit_offset: int) -> bytes:
    """Décale les bytes pour l'alignement bit-level (comme dans refetch_film_roster.py)."""
    if bit_offset == 0:
        return data
    if not (0 <= bit_offset <= 7):
        raise ValueError("bit_offset must be 0..7")

    out = bytearray(max(0, len(data) - 1))
    inv = 8 - bit_offset
    for i in range(len(out)):
        out[i] = ((data[i] << bit_offset) & 0xFF) | (data[i + 1] >> inv)
    return bytes(out)


def looks_like_gamertag(s: str, strict: bool = False) -> bool:
    """
    Vérifie si une chaîne ressemble à un gamertag valide.

    Args:
        s: Chaîne à vérifier
        strict: Si True, exige que le gamertag soit principalement ASCII
    """
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

    if strict:
        # En mode strict, au moins 50% des caractères doivent être ASCII alphanumériques
        ascii_alnum_count = sum(1 for ch in v if ch.isascii() and ch.isalnum())
        if ascii_alnum_count < len(v) * 0.5:
            return False

    return True


def is_valid_timestamp(timestamp_ms: int, max_match_duration_ms: int = 1800000) -> bool:
    """
    Vérifie si un timestamp est valide pour un match Halo.

    Args:
        timestamp_ms: Timestamp en millisecondes
        max_match_duration_ms: Durée max d'un match (défaut: 30 min = 1800000 ms)
    """
    return 0 <= timestamp_ms <= max_match_duration_ms


def find_events_in_chunk(
    chunk: bytes,
    gamertag_filter: str | None = None,
    verbose: bool = False,
    strict_gamertag: bool = False,
    max_timestamp_ms: int | None = None,
) -> list[ExtractedEvent]:
    """
    Cherche tous les events dans un chunk décompressé.

    Stratégie :
    1. Scanner tous les bit offsets (0-7) pour l'alignement
    2. Chercher le pattern type=20 ou type=50 à l'offset 59
    3. Valider avec le gamertag (UTF-16 BE) à l'offset 12-43
    4. Extraire header (0-11) et extra bytes (72+)

    Args:
        chunk: Bytes du chunk décompressé
        gamertag_filter: Optionnel - ne garder que les events de ce joueur
        verbose: Afficher les détails de scan

    Returns:
        Liste d'ExtractedEvent
    """
    events: list[ExtractedEvent] = []
    seen_offsets: set[tuple[int, int]] = set()  # (bit_offset, chunk_offset)

    # Encoder le gamertag filter en UTF-16 BE si fourni
    gt_filter_bytes = None
    if gamertag_filter:
        try:
            gt_filter_bytes = gamertag_filter.encode("utf-16-be")
        except Exception:
            pass

    for bit_off in range(8):
        view = shift_bytes(chunk, bit_off)

        # Méthode 1: Chercher par type d'event (20, 50) à l'offset 59
        for i in range(60, len(view) - 40):
            # Position du byte type dans la vue
            type_byte = view[i]

            if type_byte not in (10, 20, 50):
                continue

            # Calculer le début de l'event (59 bytes avant le type)
            event_start = i - 59
            if event_start < 0:
                continue

            # Vérifier qu'on n'a pas déjà traité cet offset
            key = (bit_off, event_start)
            if key in seen_offsets:
                continue

            # Vérifier le padding avant le type (offset 44-58 = 15 bytes de 0x00)
            padding = view[event_start + 44 : event_start + 59]
            if len(padding) < 15:
                continue

            # Tolérance: au moins 80% de zeros dans le padding
            zero_count = sum(1 for b in padding if b == 0)
            if zero_count < 12:  # 12/15 = 80%
                continue

            # Extraire et décoder le gamertag (offset 12-43, UTF-16 BE)
            gt_raw = view[event_start + 12 : event_start + 44]
            try:
                gamertag = gt_raw.decode("utf-16-be", errors="ignore").strip("\x00").strip()
            except Exception:
                gamertag = ""

            if not looks_like_gamertag(gamertag, strict=strict_gamertag):
                continue

            # Filtre gamertag si demandé
            if gamertag_filter and gamertag.lower() != gamertag_filter.lower():
                continue

            # Extraire timestamp pour validation éventuelle
            ts_bytes = view[event_start + 60 : event_start + 64]
            if len(ts_bytes) == 4:
                timestamp_ms = struct.unpack("<I", ts_bytes)[0]
            else:
                timestamp_ms = 0

            # Filtrer par timestamp si demandé
            if max_timestamp_ms is not None and not is_valid_timestamp(
                timestamp_ms, max_timestamp_ms
            ):
                continue

            seen_offsets.add(key)

            # Extraire les composants
            header = view[event_start : event_start + 12]
            event_type = view[event_start + 59]
            # timestamp_ms déjà extrait plus haut

            # Medal marker et ID
            medal_marker = view[event_start + 67] if event_start + 67 < len(view) else 0
            medal_id = view[event_start + 71] if event_start + 71 < len(view) else 0

            # BYTES NON DOCUMENTÉS: après offset 72
            extra_start = event_start + 72
            extra_32 = view[extra_start : extra_start + 32]
            extra_64 = view[extra_start : extra_start + 64]

            # Segment complet pour analyse
            raw_segment = view[event_start : extra_start + 64]

            # Nom du type d'event
            type_names = {10: "mode", 20: "death", 50: "kill"}
            event_type_name = type_names.get(event_type, f"unknown_{event_type}")

            events.append(
                ExtractedEvent(
                    offset_in_chunk=event_start,
                    bit_offset=bit_off,
                    gamertag=gamertag,
                    event_type=event_type,
                    event_type_name=event_type_name,
                    timestamp_ms=timestamp_ms,
                    medal_marker=medal_marker,
                    medal_id=medal_id,
                    header_bytes=list(header),
                    extra_bytes_32=list(extra_32),
                    extra_bytes_64=list(extra_64),
                    header_hex=" ".join(f"{b:02x}" for b in header),
                    extra_hex_32=" ".join(f"{b:02x}" for b in extra_32),
                    raw_segment_hex=hex_dump(raw_segment),
                )
            )

    # Trier par timestamp
    events.sort(key=lambda e: (e.timestamp_ms, e.offset_in_chunk))

    return events


def analyze_patterns(events: list[ExtractedEvent]) -> dict[str, Any]:
    """
    Analyse les patterns dans les events extraits.

    Objectif: Identifier les bytes qui pourraient encoder l'arme.
    """
    if not events:
        return {"error": "Aucun event à analyser"}

    # Séparer kills et deaths
    kills = [e for e in events if e.event_type == 50]
    deaths = [e for e in events if e.event_type == 20]

    analysis: dict[str, Any] = {
        "total_events": len(events),
        "kills": len(kills),
        "deaths": len(deaths),
        "players": list(set(e.gamertag for e in events)),
    }

    # Analyser les patterns du header (12 bytes) pour les kills
    if kills:
        header_patterns = []
        for pos in range(12):
            values = [e.header_bytes[pos] for e in kills if len(e.header_bytes) > pos]
            if values:
                unique_values = sorted(set(values))
                header_patterns.append(
                    {
                        "position": pos,
                        "unique_count": len(unique_values),
                        "min": min(values),
                        "max": max(values),
                        "samples": unique_values[:10],
                        "variance": "low"
                        if len(unique_values) < 5
                        else "medium"
                        if len(unique_values) < 20
                        else "high",
                    }
                )
        analysis["header_patterns_kills"] = header_patterns

        # Analyser les extra bytes (32 premiers bytes après offset 72)
        extra_patterns = []
        for pos in range(32):
            values = [e.extra_bytes_32[pos] for e in kills if len(e.extra_bytes_32) > pos]
            if values:
                unique_values = sorted(set(values))
                extra_patterns.append(
                    {
                        "position": pos + 72,  # Offset réel dans l'event
                        "unique_count": len(unique_values),
                        "min": min(values),
                        "max": max(values),
                        "samples": unique_values[:10],
                        "variance": "low"
                        if len(unique_values) < 5
                        else "medium"
                        if len(unique_values) < 20
                        else "high",
                    }
                )
        analysis["extra_patterns_kills"] = extra_patterns

    # Comparer kills vs deaths pour trouver les différences
    if kills and deaths:
        kill_headers = defaultdict(list)
        death_headers = defaultdict(list)

        for k in kills:
            for i, b in enumerate(k.header_bytes):
                kill_headers[i].append(b)

        for d in deaths:
            for i, b in enumerate(d.header_bytes):
                death_headers[i].append(b)

        differences = []
        for pos in range(12):
            kill_vals = set(kill_headers.get(pos, []))
            death_vals = set(death_headers.get(pos, []))

            # Trouver les valeurs qui n'apparaissent que dans les kills
            kill_only = kill_vals - death_vals
            death_only = death_vals - kill_vals

            if kill_only or death_only:
                differences.append(
                    {
                        "position": pos,
                        "kill_only_values": sorted(kill_only)[:5],
                        "death_only_values": sorted(death_only)[:5],
                        "comment": "Candidat pour flag kill/death ou weapon_id"
                        if kill_only
                        else "",
                    }
                )

        analysis["header_kill_death_differences"] = differences

    # Hypothèses sur les weapon IDs
    # On cherche des bytes avec variance moyenne (pas constants, pas trop variables)
    potential_weapon_bytes = []
    for pos in range(32):
        if kills:
            values = [e.extra_bytes_32[pos] for e in kills if len(e.extra_bytes_32) > pos]
            if values:
                unique = len(set(values))
                # 3-15 valeurs uniques = potentiellement des weapon IDs
                if 3 <= unique <= 20:
                    potential_weapon_bytes.append(
                        {
                            "position": pos + 72,
                            "unique_values": unique,
                            "samples": sorted(set(values))[:10],
                            "comment": "Candidat weapon_id (variance moyenne)",
                        }
                    )

    analysis["potential_weapon_id_positions"] = potential_weapon_bytes

    return analysis


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Extraction et analyse des events binaires des chunks Halo Infinite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--chunk", type=Path, help="Chemin vers un chunk .bin décompressé")
    parser.add_argument("--chunks-dir", type=Path, help="Dossier contenant les chunks .bin")
    parser.add_argument("--gamertag", help="Filtrer par gamertag")
    parser.add_argument("--type", type=int, choices=[10, 20, 50], help="Filtrer par type d'event")
    parser.add_argument("--output", type=Path, help="Fichier JSON de sortie")
    parser.add_argument("--limit", type=int, default=50, help="Nombre max d'events à afficher")
    parser.add_argument("--verbose", action="store_true", help="Afficher les détails de scan")
    parser.add_argument("--analyze", action="store_true", help="Analyser les patterns")
    parser.add_argument("--hex-dump", action="store_true", help="Afficher les hex dumps complets")
    parser.add_argument(
        "--strict", action="store_true", help="Mode strict: gamertags majoritairement ASCII"
    )
    parser.add_argument(
        "--max-timestamp",
        type=int,
        default=None,
        help="Timestamp max en ms (défaut: pas de limite, suggéré: 1800000 pour 30 min)",
    )

    args = parser.parse_args()

    # Collecter les fichiers chunks
    chunk_files: list[Path] = []

    if args.chunk and args.chunk.exists():
        chunk_files.append(args.chunk)

    if args.chunks_dir and args.chunks_dir.exists():
        chunk_files.extend(sorted(args.chunks_dir.glob("*.bin")))

    if not chunk_files:
        print("ERREUR: Aucun fichier chunk trouvé. Utilisez --chunk ou --chunks-dir")
        return 1

    print(f"Analyse de {len(chunk_files)} fichier(s) chunk...")

    all_events: list[ExtractedEvent] = []

    for chunk_path in chunk_files:
        print(f"\n--- {chunk_path.name} ---")

        try:
            chunk_data = chunk_path.read_bytes()
            print(f"Taille: {len(chunk_data):,} bytes")
        except Exception as e:
            print(f"Erreur lecture: {e}")
            continue

        events = find_events_in_chunk(
            chunk_data,
            gamertag_filter=args.gamertag,
            verbose=args.verbose,
            strict_gamertag=args.strict,
            max_timestamp_ms=args.max_timestamp,
        )

        if args.type:
            events = [e for e in events if e.event_type == args.type]

        print(f"Events trouves: {len(events)}")

        if events:
            # Comptage par type
            by_type = defaultdict(list)
            for e in events:
                by_type[e.event_type_name].append(e)

            for type_name, type_events in by_type.items():
                print(f"  - {type_name}: {len(type_events)}")

        all_events.extend(events)

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {len(all_events)} events extraits")
    print(f"{'=' * 60}")

    # Afficher les events (avec gestion des caractères Unicode)
    def safe_print(text: str) -> None:
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode("ascii", errors="replace").decode("ascii"))

    for i, event in enumerate(all_events[: args.limit]):
        safe_print(f"\n[Event {i + 1}] {event.event_type_name.upper()} - {event.gamertag}")
        safe_print(f"  Timestamp: {event.timestamp_ms} ms ({event.timestamp_ms // 1000}s)")
        safe_print(f"  Offset: {event.offset_in_chunk} (bit_offset={event.bit_offset})")
        safe_print(f"  Medal: marker={event.medal_marker}, id={event.medal_id}")
        safe_print(f"  Header (12 bytes): {event.header_hex}")
        safe_print(f"  Extra (32 bytes @72): {event.extra_hex_32}")

        if args.hex_dump:
            safe_print(f"\n  Raw segment:\n{event.raw_segment_hex}")

    if len(all_events) > args.limit:
        print(f"\n... ({len(all_events) - args.limit} events supplémentaires non affichés)")

    # Analyse des patterns
    if args.analyze and all_events:
        print(f"\n{'=' * 60}")
        print("ANALYSE DES PATTERNS")
        print(f"{'=' * 60}")

        analysis = analyze_patterns(all_events)

        safe_print(f"\nTotal events: {analysis['total_events']}")
        safe_print(f"Kills: {analysis['kills']}")
        safe_print(f"Deaths: {analysis['deaths']}")
        players_str = ", ".join(p for p in analysis["players"] if p.isascii())
        safe_print(f"Joueurs (ASCII): {players_str or '(gamertags corrompus)'}")

        if "potential_weapon_id_positions" in analysis:
            print("\n[Positions candidates pour weapon_id]")
            for p in analysis["potential_weapon_id_positions"]:
                print(f"  Offset {p['position']}: {p['unique_values']} valeurs uniques")
                print(f"    Samples: {p['samples']}")

        if "header_kill_death_differences" in analysis:
            print("\n[Différences header kill vs death]")
            for d in analysis["header_kill_death_differences"]:
                print(
                    f"  Position {d['position']}: kill_only={d['kill_only_values']}, death_only={d['death_only_values']}"
                )

    # Sauvegarder en JSON
    if args.output:
        output_data = {
            "total_events": len(all_events),
            "events": [asdict(e) for e in all_events],
        }

        if args.analyze:
            output_data["analysis"] = analyze_patterns(all_events)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\nRésultats sauvegardés: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
