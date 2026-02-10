#!/usr/bin/env python3
"""
Script d'analyse bit-shifted des film chunks Halo Infinite.

Implémente la méthode Den Delimarsky pour extraire les events avec alignement au bit.

Structure documentée d'un event (72 bytes minimum) :
- 0-11    : Header (12 bytes - métadonnées inconnues)
- 12-43   : Gamertag (32 bytes - UTF-16 BE)
- 44-58   : Padding (15 bytes - 0x00)
- 59      : Type (1 byte - 10=mode, 20=death, 50=kill)
- 60-63   : Timestamp (4 bytes - millisecondes, little-endian)
- 64-66   : Padding (3 bytes)
- 67      : Medal marker (1 byte)
- 68-70   : Padding (3 bytes)
- 71      : Medal ID (1 byte)
- 72+     : Bytes additionnels (weapon_id potentiel)

Markers clés :
- 0x2D 0xC0 : Précède un XUID (8 bytes avant)
- 0x2E 0xE0 : Trouvé dans les events (observé)

Usage:
    # Télécharger et analyser les chunks d'un match
    python scripts/analyze_chunks_bitshifted.py --match-id 189d1c23-b006-421a-9515-f978edc0dc45

    # Analyser des chunks locaux
    python scripts/analyze_chunks_bitshifted.py --chunks-dir data/investigation/chunks_xxx/

    # Corréler avec les données théâtre (format: "MM:SS=event_type=weapon=victim")
    python scripts/analyze_chunks_bitshifted.py --chunks-dir ... \\
        --theatre-events "1:04=kill=Sniper=SP00KY MAGE,1:08=kill=Sniper=SimonGames64"

Références:
- https://den.dev/blog/extracting-stats-film-files-halo-infinite/
- https://github.com/OpenSpartan/film-event-extractor
"""

from __future__ import annotations

import argparse
import asyncio
import json
import struct
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore


# ============================================================================
# Constantes
# ============================================================================

MARKER_ROSTER = b"\x2d\xc0"  # Marker XUID/Gamertag
MARKER_EVENT = b"\x2e\xe0"  # Marker observé dans events (hypothèse)

# Structure Den Delimarsky
OFFSET_HEADER = 0
OFFSET_GAMERTAG = 12
OFFSET_PADDING1 = 44
OFFSET_EVENT_TYPE = 59
OFFSET_TIMESTAMP = 60
OFFSET_PADDING2 = 64
OFFSET_MEDAL_MARKER = 67
OFFSET_PADDING3 = 68
OFFSET_MEDAL_ID = 71
OFFSET_EXTRA = 72

# Event types
EVENT_TYPE_MODE = 10
EVENT_TYPE_DEATH = 20
EVENT_TYPE_KILL = 50

EVENT_TYPE_NAMES = {
    EVENT_TYPE_MODE: "mode",
    EVENT_TYPE_DEATH: "death",
    EVENT_TYPE_KILL: "kill",
}


# ============================================================================
# Dataclasses
# ============================================================================


@dataclass
class ExtractedEvent:
    """Event extrait avec la structure Den Delimarsky."""

    source_chunk: str
    offset_in_chunk: int
    bit_offset: int

    # Données extraites selon la structure
    gamertag: str
    event_type: int
    event_type_name: str
    timestamp_ms: int
    timestamp_formatted: str  # "MM:SS"
    medal_marker: int
    medal_id: int

    # Bytes bruts pour analyse
    header_bytes: list[int]
    extra_bytes: list[int]  # Bytes après offset 72

    # Hex dumps
    header_hex: str
    extra_hex: str
    full_hex: str


@dataclass
class TheatreEvent:
    """Event observé dans le mode théâtre (ground truth)."""

    timestamp_seconds: int
    timestamp_formatted: str
    event_type: str  # "kill", "death", "mode"
    weapon: str | None
    victim: str | None


@dataclass
class CorrelationResult:
    """Résultat de corrélation entre event extrait et théâtre."""

    theatre_event: TheatreEvent
    matched_event: ExtractedEvent | None
    timestamp_delta_ms: int | None
    confidence: str  # "high", "medium", "low", "no_match"


# ============================================================================
# Fonctions utilitaires
# ============================================================================


def shift_bytes(data: bytes, bit_offset: int) -> bytes:
    """Décale les bytes pour l'alignement bit-level (méthode Den Delimarsky)."""
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


def looks_like_gamertag(s: str, strict: bool = False) -> bool:
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

    if strict:
        # En mode strict, au moins 50% des caractères doivent être ASCII alphanumériques
        ascii_alnum_count = sum(1 for ch in v if ch.isascii() and ch.isalnum())
        if ascii_alnum_count < len(v) * 0.5:
            return False

    return True


def ms_to_mmss(ms: int) -> str:
    """Convertit des millisecondes en format MM:SS."""
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def mmss_to_seconds(mmss: str) -> int:
    """Convertit un format MM:SS en secondes."""
    parts = mmss.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


def safe_print(text: str) -> None:
    """Print avec gestion des caractères Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


# ============================================================================
# Extraction bit-shifted
# ============================================================================


def find_events_den_structure(
    chunk: bytes,
    chunk_name: str,
    gamertag_filter: str | None = None,
    max_timestamp_ms: int = 1800000,  # 30 minutes par défaut
    strict_validation: bool = True,
) -> list[ExtractedEvent]:
    """
    Extrait les events selon la structure Den Delimarsky avec recherche bit-shifted.

    Stratégie:
    1. Scanner tous les bit offsets (0-7)
    2. Chercher les types d'event (10, 20, 50) à l'offset 59
    3. Valider avec le padding et le gamertag
    4. Extraire les composants selon la structure documentée
    """
    events: list[ExtractedEvent] = []
    seen_offsets: set[tuple[int, int]] = set()

    for bit_off in range(8):
        view = shift_bytes(chunk, bit_off)

        # Scanner pour les types d'event valides
        for i in range(OFFSET_EVENT_TYPE, len(view) - 20):
            type_byte = view[i]

            if type_byte not in (EVENT_TYPE_MODE, EVENT_TYPE_DEATH, EVENT_TYPE_KILL):
                continue

            # Calculer le début de l'event
            event_start = i - OFFSET_EVENT_TYPE
            if event_start < 0:
                continue

            # Éviter les doublons
            key = (bit_off, event_start)
            if key in seen_offsets:
                continue

            # Vérifier qu'on a assez de données
            if event_start + OFFSET_EXTRA + 32 > len(view):
                continue

            # Vérifier le padding (offset 44-58 = 15 bytes)
            padding1 = view[event_start + OFFSET_PADDING1 : event_start + OFFSET_EVENT_TYPE]
            zero_count = sum(1 for b in padding1 if b == 0)
            if strict_validation and zero_count < 12:  # Au moins 80% de zeros
                continue

            # Extraire et décoder le gamertag (UTF-16 BE)
            gt_raw = view[event_start + OFFSET_GAMERTAG : event_start + OFFSET_PADDING1]
            try:
                gamertag = gt_raw.decode("utf-16-be", errors="ignore").strip("\x00").strip()
            except Exception:
                gamertag = ""

            if strict_validation and not looks_like_gamertag(gamertag):
                continue

            # Filtre gamertag si demandé
            if gamertag_filter and gamertag.lower() != gamertag_filter.lower():
                continue

            # Extraire le timestamp
            ts_bytes = view[event_start + OFFSET_TIMESTAMP : event_start + OFFSET_TIMESTAMP + 4]
            timestamp_ms = struct.unpack("<I", ts_bytes)[0] if len(ts_bytes) == 4 else 0

            # Valider le timestamp
            if strict_validation and (timestamp_ms < 0 or timestamp_ms > max_timestamp_ms):
                continue

            seen_offsets.add(key)

            # Extraire tous les composants
            header = list(view[event_start : event_start + OFFSET_GAMERTAG])
            event_type = type_byte
            medal_marker = (
                view[event_start + OFFSET_MEDAL_MARKER]
                if event_start + OFFSET_MEDAL_MARKER < len(view)
                else 0
            )
            medal_id = (
                view[event_start + OFFSET_MEDAL_ID]
                if event_start + OFFSET_MEDAL_ID < len(view)
                else 0
            )

            # Bytes additionnels (après offset 72)
            extra_start = event_start + OFFSET_EXTRA
            extra_bytes = list(view[extra_start : extra_start + 32])

            # Segment complet pour analyse
            full_segment = view[event_start : extra_start + 32]

            events.append(
                ExtractedEvent(
                    source_chunk=chunk_name,
                    offset_in_chunk=event_start,
                    bit_offset=bit_off,
                    gamertag=gamertag if gamertag else f"<unknown@{event_start}>",
                    event_type=event_type,
                    event_type_name=EVENT_TYPE_NAMES.get(event_type, f"type_{event_type}"),
                    timestamp_ms=timestamp_ms,
                    timestamp_formatted=ms_to_mmss(timestamp_ms),
                    medal_marker=medal_marker,
                    medal_id=medal_id,
                    header_bytes=header,
                    extra_bytes=extra_bytes,
                    header_hex=" ".join(f"{b:02x}" for b in header),
                    extra_hex=" ".join(f"{b:02x}" for b in extra_bytes[:16]),
                    full_hex=hex_dump(full_segment),
                )
            )

    # Trier par timestamp
    events.sort(key=lambda e: (e.timestamp_ms, e.offset_in_chunk))

    return events


def find_events_by_marker(
    chunk: bytes,
    chunk_name: str,
    marker: bytes = MARKER_EVENT,
    context_before: int = 72,
    context_after: int = 32,
) -> list[dict[str, Any]]:
    """
    Cherche les events par marker binaire avec extraction bit-shifted.

    Alternative à la recherche par type pour tester différentes hypothèses.
    """
    results: list[dict[str, Any]] = []

    for bit_off in range(8):
        view = shift_bytes(chunk, bit_off)

        pos = 0
        while True:
            idx = view.find(marker, pos)
            if idx < 0:
                break

            # Extraire le contexte
            start = max(0, idx - context_before)
            end = min(len(view), idx + len(marker) + context_after)

            context = view[start:end]
            marker_pos_in_context = idx - start

            results.append(
                {
                    "chunk": chunk_name,
                    "bit_offset": bit_off,
                    "marker_offset": idx,
                    "marker_hex": marker.hex(),
                    "context_hex": hex_dump(context),
                    "marker_pos_in_context": marker_pos_in_context,
                }
            )

            pos = idx + len(marker)

    return results


# ============================================================================
# Parsing des données théâtre
# ============================================================================


def parse_theatre_events(theatre_string: str) -> list[TheatreEvent]:
    """
    Parse les events théâtre depuis une chaîne.

    Format: "MM:SS=type=weapon=victim,MM:SS=type=weapon=victim,..."
    Exemple: "1:04=kill=Sniper=SP00KY MAGE,1:08=kill=Sniper=SimonGames64"
    """
    events: list[TheatreEvent] = []

    for part in theatre_string.split(","):
        part = part.strip()
        if not part:
            continue

        fields = part.split("=")
        if len(fields) < 2:
            continue

        timestamp_str = fields[0]
        event_type = fields[1] if len(fields) > 1 else "kill"
        weapon = fields[2] if len(fields) > 2 else None
        victim = fields[3] if len(fields) > 3 else None

        events.append(
            TheatreEvent(
                timestamp_seconds=mmss_to_seconds(timestamp_str),
                timestamp_formatted=timestamp_str,
                event_type=event_type,
                weapon=weapon,
                victim=victim,
            )
        )

    return events


# ============================================================================
# Corrélation
# ============================================================================


def correlate_events(
    extracted: list[ExtractedEvent],
    theatre: list[TheatreEvent],
    gamertag: str,
    tolerance_ms: int = 5000,  # 5 secondes de tolérance
) -> list[CorrelationResult]:
    """
    Corrèle les events extraits avec les observations théâtre.

    Retourne un résultat de corrélation pour chaque event théâtre.
    """
    results: list[CorrelationResult] = []

    # Filtrer les events du joueur
    player_events = [e for e in extracted if e.gamertag.lower() == gamertag.lower()]

    for t_event in theatre:
        theatre_ms = t_event.timestamp_seconds * 1000

        # Chercher le meilleur match
        best_match: ExtractedEvent | None = None
        best_delta: int | None = None

        for e_event in player_events:
            # Filtrer par type
            if t_event.event_type == "kill" and e_event.event_type != EVENT_TYPE_KILL:
                continue
            if t_event.event_type == "death" and e_event.event_type != EVENT_TYPE_DEATH:
                continue

            delta = abs(e_event.timestamp_ms - theatre_ms)
            if delta <= tolerance_ms:
                if best_delta is None or delta < best_delta:
                    best_match = e_event
                    best_delta = delta

        # Déterminer la confiance
        if best_match is None:
            confidence = "no_match"
        elif best_delta is not None and best_delta < 1000:  # < 1s
            confidence = "high"
        elif best_delta is not None and best_delta < 3000:  # < 3s
            confidence = "medium"
        else:
            confidence = "low"

        results.append(
            CorrelationResult(
                theatre_event=t_event,
                matched_event=best_match,
                timestamp_delta_ms=best_delta,
                confidence=confidence,
            )
        )

    return results


# ============================================================================
# Analyse des patterns weapon_id
# ============================================================================


def analyze_weapon_patterns(events: list[ExtractedEvent]) -> dict[str, Any]:
    """
    Analyse les patterns dans les extra_bytes pour identifier les weapon IDs potentiels.
    """
    kills = [e for e in events if e.event_type == EVENT_TYPE_KILL]

    if not kills:
        return {"error": "Aucun kill à analyser"}

    analysis: dict[str, Any] = {
        "total_kills": len(kills),
        "players": list(set(e.gamertag for e in kills)),
    }

    # Analyser chaque position des extra_bytes
    patterns_by_position: list[dict[str, Any]] = []

    for pos in range(min(16, min(len(e.extra_bytes) for e in kills))):
        values = [e.extra_bytes[pos] for e in kills]
        unique = sorted(set(values))

        patterns_by_position.append(
            {
                "position": pos + OFFSET_EXTRA,
                "unique_count": len(unique),
                "min": min(values),
                "max": max(values),
                "samples": unique[:10],
                "variance": "low" if len(unique) < 5 else "medium" if len(unique) < 15 else "high",
                "is_weapon_candidate": 3 <= len(unique) <= 20 and max(values) > 0,
            }
        )

    analysis["extra_byte_patterns"] = patterns_by_position

    # Identifier les meilleurs candidats weapon_id
    candidates = [p for p in patterns_by_position if p["is_weapon_candidate"]]
    analysis["weapon_id_candidates"] = candidates

    # Analyser les paires de bytes (uint16)
    pair_patterns: list[dict[str, Any]] = []
    for pos in range(0, min(14, min(len(e.extra_bytes) for e in kills) - 1), 2):
        values = [
            struct.unpack("<H", bytes(e.extra_bytes[pos : pos + 2]))[0]
            for e in kills
            if len(e.extra_bytes) > pos + 1
        ]
        unique = sorted(set(values))

        pair_patterns.append(
            {
                "position": f"{pos + OFFSET_EXTRA}-{pos + OFFSET_EXTRA + 1}",
                "format": "uint16_le",
                "unique_count": len(unique),
                "samples": [f"0x{v:04x}" for v in unique[:8]],
                "is_weapon_candidate": 3 <= len(unique) <= 20,
            }
        )

    analysis["uint16_patterns"] = pair_patterns

    return analysis


# ============================================================================
# Téléchargement des chunks (optionnel)
# ============================================================================


async def download_chunks(
    match_id: str,
    output_dir: Path,
    include_type2: bool = True,
    max_type2: int | None = 5,
) -> list[Path]:
    """
    Télécharge les chunks pour un match donné.

    Nécessite les tokens SPNKR dans l'environnement.
    """
    if aiohttp is None:
        raise RuntimeError(
            "aiohttp requis pour le téléchargement. Installez-le: pip install aiohttp"
        )

    # Importer les fonctions de refetch_film_roster
    sys.path.insert(0, str(Path(__file__).parent))
    from refetch_film_roster import (
        _get_tokens,
        _load_dotenv_if_present,
        download_and_decompress_chunks,
        fetch_manifest,
    )

    _load_dotenv_if_present()

    # Créer un namespace pour les arguments
    class Args:
        pass

    args = Args()
    args.spartan_token = None
    args.clearance_token = None
    args.azure_client_id = None
    args.azure_client_secret = None
    args.azure_redirect_uri = None
    args.oauth_refresh_token = None

    tokens = await _get_tokens(args)  # type: ignore
    headers = {
        "accept": "application/json",
        "x-343-authorization-spartan": tokens.spartan_token,
        "343-clearance": tokens.clearance_token,
        "user-agent": "levelup-halo/chunk-analysis",
    }

    print(f"Téléchargement du manifest pour match {match_id}...")
    manifest = await fetch_manifest(match_id=match_id, headers=headers)

    output_dir.mkdir(parents=True, exist_ok=True)

    type_ids = {1, 2, 3} if include_type2 else {1, 3}
    print(f"Téléchargement des chunks (types: {sorted(type_ids)})...")

    chunks = await download_and_decompress_chunks(
        manifest=manifest,
        headers=headers,
        file_type_ids=type_ids,
        out_dir=output_dir,
        max_type2_chunks=max_type2,
    )

    print(f"[OK] {len(chunks)} chunks telecharges dans {output_dir}")

    return list(output_dir.glob("*.bin"))


# ============================================================================
# Main
# ============================================================================


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Analyse bit-shifted des film chunks Halo Infinite (méthode Den Delimarsky)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Sources de données
    parser.add_argument("--chunks-dir", type=Path, help="Dossier contenant les chunks .bin")
    parser.add_argument("--match-id", help="ID du match pour télécharger les chunks")
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path("data/investigation/chunks"),
        help="Dossier de destination pour les chunks téléchargés",
    )

    # Filtres
    parser.add_argument("--gamertag", help="Filtrer par gamertag")
    parser.add_argument("--type", type=int, choices=[10, 20, 50], help="Filtrer par type d'event")
    parser.add_argument(
        "--max-timestamp",
        type=int,
        default=1800000,
        help="Timestamp max en ms (défaut: 1800000 = 30 min)",
    )

    # Corrélation théâtre
    parser.add_argument(
        "--theatre-events", help="Events théâtre (format: MM:SS=type=weapon=victim,...)"
    )
    parser.add_argument(
        "--correlation-tolerance",
        type=int,
        default=5000,
        help="Tolérance de corrélation en ms (défaut: 5000)",
    )

    # Options d'analyse
    parser.add_argument(
        "--analyze-weapons",
        action="store_true",
        help="Analyser les patterns pour identifier les weapon IDs",
    )
    parser.add_argument("--search-marker", help="Chercher un marker spécifique (hex, ex: 2ee0)")
    parser.add_argument("--strict", action="store_true", help="Mode strict de validation")

    # Sortie
    parser.add_argument("--output", type=Path, help="Fichier JSON de sortie")
    parser.add_argument("--limit", type=int, default=50, help="Nombre max d'events à afficher")
    parser.add_argument("--hex-dump", action="store_true", help="Afficher les hex dumps complets")
    parser.add_argument("--verbose", action="store_true", help="Mode verbose")

    args = parser.parse_args()

    # Collecter les fichiers chunks
    chunk_files: list[Path] = []

    if args.match_id:
        # Télécharger les chunks
        download_dir = args.download_dir / args.match_id[:8]
        try:
            chunk_files = asyncio.run(
                download_chunks(
                    args.match_id,
                    download_dir,
                    include_type2=True,
                    max_type2=5,
                )
            )
        except Exception as e:
            print(f"ERREUR téléchargement: {e}")
            print("Vérifiez que les tokens SPNKR sont configurés dans .env.local")
            return 1
    elif args.chunks_dir and args.chunks_dir.exists():
        chunk_files = sorted(args.chunks_dir.glob("*.bin"))

    if not chunk_files:
        print("ERREUR: Aucun fichier chunk trouvé.")
        print("Utilisez --chunks-dir pour spécifier un dossier ou --match-id pour télécharger.")
        return 1

    print(f"Analyse de {len(chunk_files)} fichier(s) chunk...")
    print(f"Mode: {'strict' if args.strict else 'standard'}")
    print()

    # Extraire les events
    all_events: list[ExtractedEvent] = []
    all_marker_hits: list[dict[str, Any]] = []

    for chunk_path in chunk_files:
        safe_print(f"--- {chunk_path.name} ---")

        try:
            chunk_data = chunk_path.read_bytes()
            safe_print(f"Taille: {len(chunk_data):,} bytes")
        except Exception as e:
            safe_print(f"Erreur lecture: {e}")
            continue

        # Extraction par structure Den Delimarsky
        events = find_events_den_structure(
            chunk_data,
            chunk_path.name,
            gamertag_filter=args.gamertag,
            max_timestamp_ms=args.max_timestamp,
            strict_validation=args.strict,
        )

        if args.type:
            events = [e for e in events if e.event_type == args.type]

        safe_print(f"Events extraits: {len(events)}")

        # Comptage par type
        by_type: dict[str, int] = defaultdict(int)
        for e in events:
            by_type[e.event_type_name] += 1
        for type_name, count in sorted(by_type.items()):
            safe_print(f"  - {type_name}: {count}")

        all_events.extend(events)

        # Recherche de marker optionnelle
        if args.search_marker:
            marker_bytes = bytes.fromhex(args.search_marker)
            hits = find_events_by_marker(chunk_data, chunk_path.name, marker_bytes)
            safe_print(f"Marker {args.search_marker}: {len(hits)} hits")
            all_marker_hits.extend(hits)

    print()
    print("=" * 60)
    print(f"TOTAL: {len(all_events)} events extraits")
    print("=" * 60)

    # Afficher les events
    for i, event in enumerate(all_events[: args.limit]):
        safe_print(f"\n[Event {i + 1}] {event.event_type_name.upper()} - {event.gamertag}")
        safe_print(f"  Timestamp: {event.timestamp_formatted} ({event.timestamp_ms} ms)")
        safe_print(f"  Offset: {event.offset_in_chunk} (bit_offset={event.bit_offset})")
        safe_print(f"  Medal: marker={event.medal_marker}, id={event.medal_id}")
        safe_print(f"  Header (12b): {event.header_hex}")
        safe_print(f"  Extra (16b): {event.extra_hex}")

        if args.hex_dump:
            safe_print(f"\n{event.full_hex}")

    if len(all_events) > args.limit:
        print(f"\n... ({len(all_events) - args.limit} events supplémentaires)")

    # Corrélation avec les données théâtre
    if args.theatre_events and args.gamertag:
        print()
        print("=" * 60)
        print("CORRÉLATION AVEC DONNÉES THÉÂTRE")
        print("=" * 60)

        theatre = parse_theatre_events(args.theatre_events)
        correlation = correlate_events(
            all_events,
            theatre,
            args.gamertag,
            tolerance_ms=args.correlation_tolerance,
        )

        matched = sum(1 for c in correlation if c.confidence != "no_match")
        print(f"\nRésultat: {matched}/{len(theatre)} events corrélés")

        for i, c in enumerate(correlation):
            t = c.theatre_event
            status = (
                "[OK]"
                if c.confidence in ("high", "medium")
                else "[?]"
                if c.confidence == "low"
                else "[X]"
            )

            safe_print(f"\n[{status}] Théâtre {t.timestamp_formatted} - {t.event_type}")
            if t.weapon:
                safe_print(f"    Arme: {t.weapon}")
            if t.victim:
                safe_print(f"    Victime: {t.victim}")

            if c.matched_event:
                e = c.matched_event
                safe_print(
                    f"    → Match trouvé: {e.timestamp_formatted} (delta={c.timestamp_delta_ms}ms)"
                )
                safe_print(f"       Extra bytes: {e.extra_hex}")
            else:
                safe_print("    → Aucun match trouvé")

    # Analyse des patterns weapon
    if args.analyze_weapons and all_events:
        print()
        print("=" * 60)
        print("ANALYSE DES PATTERNS WEAPON_ID")
        print("=" * 60)

        analysis = analyze_weapon_patterns(all_events)

        safe_print(f"\nKills analysés: {analysis['total_kills']}")
        safe_print(f"Joueurs: {', '.join(analysis['players'])}")

        if analysis.get("weapon_id_candidates"):
            print("\n[Positions candidates (bytes individuels)]")
            for c in analysis["weapon_id_candidates"]:
                safe_print(
                    f"  Offset {c['position']}: {c['unique_count']} valeurs - {c['samples']}"
                )

        if analysis.get("uint16_patterns"):
            print("\n[Patterns uint16 (paires de bytes)]")
            for p in analysis["uint16_patterns"]:
                if p["is_weapon_candidate"]:
                    safe_print(
                        f"  Offset {p['position']}: {p['unique_count']} valeurs - {p['samples']}"
                    )

    # Sauvegarder en JSON
    if args.output:
        output_data = {
            "total_events": len(all_events),
            "events": [asdict(e) for e in all_events],
        }

        if args.theatre_events and args.gamertag:
            output_data["correlation"] = [
                {
                    "theatre": asdict(c.theatre_event),
                    "matched": asdict(c.matched_event) if c.matched_event else None,
                    "delta_ms": c.timestamp_delta_ms,
                    "confidence": c.confidence,
                }
                for c in correlation
            ]

        if args.analyze_weapons:
            output_data["weapon_analysis"] = analyze_weapon_patterns(all_events)

        if all_marker_hits:
            output_data["marker_hits"] = all_marker_hits

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        safe_print(f"\nRésultats sauvegardés: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
