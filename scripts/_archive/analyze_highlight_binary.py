#!/usr/bin/env python3
"""
Script expérimental : Analyse des Highlight Events pour identifier les patterns d'armes.

Objectif : Découvrir des champs non documentés (weapon_id, damage_type, etc.)
dans les highlight events Halo Infinite.

Phases d'analyse :
1. Analyse des raw_json existants dans DuckDB
2. Téléchargement et analyse binaire des film chunks
3. Corrélation avec les weapon_stats du match

Usage:
    # Phase 1 : Analyser les raw_json existants
    python scripts/analyze_highlight_binary.py --gamertag MonGT --analyze-json

    # Phase 2 : Télécharger et analyser les chunks binaires d'un match
    python scripts/analyze_highlight_binary.py --match-id <GUID> --analyze-binary

    # Phase 3 : Analyser tous les matchs d'un joueur (stats)
    python scripts/analyze_highlight_binary.py --gamertag MonGT --stats

Références :
- https://den.dev/blog/extracting-stats-film-files-halo-infinite/
- https://github.com/acurtis166/SPNKr
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import struct
import sys
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import duckdb
except ImportError:
    print("ERREUR: DuckDB non installé. Exécutez: pip install duckdb")
    sys.exit(1)

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore


# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
PLAYERS_DIR = DATA_DIR / "players"
DB_PROFILES_PATH = Path(__file__).parent.parent / "db_profiles.json"


# =============================================================================
# Structures de données
# =============================================================================


@dataclass
class BinaryEventAnalysis:
    """Résultat d'analyse d'un event binaire."""

    offset_in_chunk: int
    gamertag: str
    event_type: int  # 10, 20, 50
    timestamp_ms: int
    medal_id: int | None
    header_bytes: bytes  # 12 bytes de header
    extra_bytes: bytes  # Bytes au-delà de la structure connue
    raw_segment: bytes  # Segment complet


@dataclass
class WeaponCorrelation:
    """Corrélation entre un kill et une arme potentielle."""

    match_id: str
    time_ms: int
    killer_xuid: str
    killer_gamertag: str
    potential_weapon_bytes: bytes
    weapon_stats: dict[str, Any] | None


# =============================================================================
# Utilitaires
# =============================================================================


def load_db_profiles() -> dict[str, Any]:
    """Charge la configuration des profils joueurs."""
    if not DB_PROFILES_PATH.exists():
        return {"profiles": {}}
    with open(DB_PROFILES_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_player_db_path(gamertag: str) -> Path | None:
    """Retourne le chemin vers la DB DuckDB d'un joueur."""
    profiles = load_db_profiles()
    if gamertag in profiles.get("profiles", {}):
        profile = profiles["profiles"][gamertag]
        db_path = Path(profile.get("db_path", f"data/players/{gamertag}/stats.duckdb"))
        if db_path.exists():
            return db_path

    # Fallback
    fallback = PLAYERS_DIR / gamertag / "stats.duckdb"
    if fallback.exists():
        return fallback

    return None


def hex_dump(data: bytes, width: int = 16) -> str:
    """Affiche un dump hexadécimal formaté."""
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i : i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:04x}: {hex_part:<{width * 3}} |{ascii_part}|")
    return "\n".join(lines)


# =============================================================================
# Phase 1 : Analyse des raw_json existants
# =============================================================================


def analyze_json_fields(gamertag: str, limit: int = 1000) -> dict[str, Any]:
    """
    Analyse tous les champs présents dans les raw_json des highlight events.

    Objectif : Identifier des champs non utilisés qui pourraient contenir
    des informations sur les armes.
    """
    db_path = get_player_db_path(gamertag)
    if not db_path:
        print(f"ERREUR: Base non trouvée pour {gamertag}")
        return {}

    print(f"Analyse des raw_json pour {gamertag}...")
    print(f"Base: {db_path}")

    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        # Récupérer les raw_json
        query = f"""
            SELECT raw_json, event_type, type_hint
            FROM highlight_events
            WHERE raw_json IS NOT NULL AND raw_json != '{{}}'
            LIMIT {limit}
        """
        rows = conn.execute(query).fetchall()

        if not rows:
            print("Aucun event trouvé")
            return {}

        print(f"Analyse de {len(rows)} events...")

        # Analyser les champs
        all_fields: dict[str, Counter[Any]] = defaultdict(Counter)
        field_types: dict[str, set[str]] = defaultdict(set)
        sample_values: dict[str, list[Any]] = defaultdict(list)
        events_by_type: Counter[str] = Counter()

        for raw_json, event_type, type_hint in rows:
            try:
                data = json.loads(raw_json)
                if not isinstance(data, dict):
                    continue

                events_by_type[str(event_type)] += 1

                for key, value in data.items():
                    all_fields[key][str(type(value).__name__)] += 1
                    field_types[key].add(str(type(value).__name__))

                    # Garder des samples uniques
                    if len(sample_values[key]) < 10:
                        if value not in sample_values[key]:
                            sample_values[key].append(value)

            except Exception:
                continue

        # Rapport
        print("\n" + "=" * 60)
        print("CHAMPS TROUVÉS DANS LES RAW_JSON")
        print("=" * 60)

        # Champs connus (déjà mappés)
        known_fields = {"event_type", "time_ms", "xuid", "gamertag", "type_hint"}

        # Champs potentiellement intéressants (armes, dégâts, etc.)
        interesting_keywords = [
            "weapon",
            "damage",
            "killer",
            "victim",
            "assist",
            "melee",
            "grenade",
            "headshot",
            "gun",
            "rifle",
            "pistol",
            "sniper",
            "rocket",
            "projectile",
            "equipment",
        ]

        unknown_fields: list[str] = []
        potentially_interesting: list[str] = []

        for field in sorted(all_fields.keys()):
            types = ", ".join(field_types[field])
            count = sum(all_fields[field].values())
            samples = sample_values.get(field, [])[:3]

            is_known = field.lower() in known_fields or field in known_fields
            is_interesting = any(kw in field.lower() for kw in interesting_keywords)

            marker = ""
            if is_interesting:
                marker = " 🔥 POTENTIELLEMENT INTÉRESSANT"
                potentially_interesting.append(field)
            elif not is_known:
                marker = " ❓ NON MAPPÉ"
                unknown_fields.append(field)

            print(f"\n[{field}]{marker}")
            print(f"  Types: {types}")
            print(f"  Occurrences: {count}")
            print(f"  Samples: {samples}")

        print("\n" + "=" * 60)
        print("RÉSUMÉ")
        print("=" * 60)
        print(f"Total events analysés: {len(rows)}")
        print(f"Events par type: {dict(events_by_type)}")
        print(f"Champs connus: {known_fields & set(all_fields.keys())}")
        print(f"Champs non mappés: {unknown_fields}")
        print(f"Champs potentiellement intéressants: {potentially_interesting}")

        return {
            "total_events": len(rows),
            "events_by_type": dict(events_by_type),
            "all_fields": {k: dict(v) for k, v in all_fields.items()},
            "unknown_fields": unknown_fields,
            "potentially_interesting": potentially_interesting,
            "sample_values": {k: v[:5] for k, v in sample_values.items()},
        }

    finally:
        conn.close()


def compare_kill_death_events(gamertag: str) -> None:
    """
    Compare la structure des events kill vs death pour identifier des différences.

    Hypothèse : Les kills pourraient avoir des champs supplémentaires (arme).
    """
    db_path = get_player_db_path(gamertag)
    if not db_path:
        print(f"ERREUR: Base non trouvée pour {gamertag}")
        return

    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        # Events kill
        kills = conn.execute("""
            SELECT raw_json FROM highlight_events
            WHERE event_type = 'kill' AND raw_json IS NOT NULL
            LIMIT 100
        """).fetchall()

        # Events death
        deaths = conn.execute("""
            SELECT raw_json FROM highlight_events
            WHERE event_type = 'death' AND raw_json IS NOT NULL
            LIMIT 100
        """).fetchall()

        kill_fields: set[str] = set()
        death_fields: set[str] = set()

        for (raw,) in kills:
            try:
                data = json.loads(raw)
                kill_fields.update(data.keys())
            except Exception:
                continue

        for (raw,) in deaths:
            try:
                data = json.loads(raw)
                death_fields.update(data.keys())
            except Exception:
                continue

        print("\n" + "=" * 60)
        print("COMPARAISON KILL vs DEATH")
        print("=" * 60)
        print(f"Champs dans KILL uniquement: {kill_fields - death_fields}")
        print(f"Champs dans DEATH uniquement: {death_fields - kill_fields}")
        print(f"Champs communs: {kill_fields & death_fields}")

    finally:
        conn.close()


# =============================================================================
# Phase 2 : Analyse binaire des chunks
# =============================================================================


def analyze_event_structure(
    chunk: bytes, event_type_filter: int | None = None
) -> list[BinaryEventAnalysis]:
    """
    Analyse la structure binaire d'un chunk décompressé pour extraire les events.

    Structure documentée (72 bytes) :
    - Header: 12 bytes
    - Gamertag: 32 bytes (UTF-16)
    - Padding: 15 bytes
    - Type: 1 byte (10=mode, 20=death, 50=kill)
    - Timestamp: 4 bytes (little-endian)
    - Padding: 3 bytes
    - Medal marker: 1 byte
    - Padding: 3 bytes
    - Medal ID: 1 byte

    On cherche des bytes supplémentaires au-delà de ces 72 bytes.
    """
    results: list[BinaryEventAnalysis] = []

    # Rechercher le pattern des event types (10, 20, 50 à l'offset 59)
    # On scanne le chunk pour trouver des structures valides

    for bit_off in range(8):  # Test des 8 alignements possibles
        view = _shift_bytes(chunk, bit_off)

        # Chercher les patterns de type (20, 50 sont les plus fiables)
        for i in range(len(view) - 100):  # Assez d'espace pour un event complet
            # Vérifier si on a un type valide à l'offset attendu (59 depuis le header)
            if i < 59:
                continue

            potential_type = view[i]
            if potential_type not in (10, 20, 50):
                continue

            if event_type_filter and potential_type != event_type_filter:
                continue

            # Calculer l'offset du début de l'event
            event_start = i - 59
            if event_start < 0:
                continue

            # Vérifier le padding avant le type (15 bytes de 0x00 attendus)
            padding_start = event_start + 44
            padding = view[padding_start : padding_start + 15]
            if not all(b == 0 for b in padding):
                continue  # Pas un vrai event

            # Extraire les composants
            header = view[event_start : event_start + 12]
            gamertag_raw = view[event_start + 12 : event_start + 44]
            event_type = view[event_start + 59]

            # Timestamp (4 bytes little-endian à l'offset 60)
            ts_bytes = view[event_start + 60 : event_start + 64]
            if len(ts_bytes) == 4:
                timestamp_ms = struct.unpack("<I", ts_bytes)[0]
            else:
                continue

            # Medal ID (offset 71)
            medal_id = view[event_start + 71] if event_start + 71 < len(view) else None

            # Gamertag (UTF-16 BE)
            try:
                gamertag = gamertag_raw.decode("utf-16be", errors="ignore").strip("\x00")
            except Exception:
                gamertag = ""

            if not gamertag or len(gamertag) < 3:
                continue  # Probablement pas un vrai event

            # BYTES SUPPLÉMENTAIRES : au-delà de l'offset 72
            extra_start = event_start + 72
            extra_end = min(extra_start + 32, len(view))  # 32 bytes supplémentaires
            extra_bytes = view[extra_start:extra_end]

            results.append(
                BinaryEventAnalysis(
                    offset_in_chunk=event_start,
                    gamertag=gamertag,
                    event_type=event_type,
                    timestamp_ms=timestamp_ms,
                    medal_id=medal_id,
                    header_bytes=header,
                    extra_bytes=extra_bytes,
                    raw_segment=view[event_start:extra_end],
                )
            )

    return results


def _shift_bytes(data: bytes, bit_offset: int) -> bytes:
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


async def download_and_analyze_chunk(
    match_id: str,
    headers: dict[str, str],
    chunk_type: int = 3,  # Type 3 = summary avec kills/deaths
) -> list[BinaryEventAnalysis]:
    """
    Télécharge un chunk de film et analyse sa structure binaire.
    """
    if aiohttp is None:
        print("ERREUR: aiohttp non installé. Exécutez: pip install aiohttp")
        return []

    manifest_url = (
        f"https://discovery-infiniteugc.svc.halowaypoint.com"
        f"/hi/films/matches/{match_id}/spectate"
    )

    timeout = aiohttp.ClientTimeout(total=90)

    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        # Récupérer le manifest
        async with session.get(manifest_url) as resp:
            if resp.status >= 400:
                print(f"Erreur HTTP {resp.status} pour le manifest")
                return []
            manifest = await resp.json()

        prefix = manifest.get("BlobStoragePathPrefix")
        if not prefix:
            print("BlobStoragePathPrefix manquant dans le manifest")
            return []

        # Trouver le chunk du bon type
        chunks = manifest.get("CustomData", {}).get("Chunks", [])
        target_chunks = [c for c in chunks if c.get("ChunkType") == chunk_type]

        if not target_chunks:
            print(f"Aucun chunk de type {chunk_type} trouvé")
            return []

        all_results: list[BinaryEventAnalysis] = []

        for chunk_info in target_chunks:
            rel_path = chunk_info.get("FileRelativePath", "")
            url = f"{prefix.rstrip('/')}{rel_path}"

            print(f"Téléchargement: {rel_path}")

            async with session.get(url) as resp:
                if resp.status >= 400:
                    print(f"Erreur HTTP {resp.status} pour {rel_path}")
                    continue
                compressed = await resp.read()

            # Décompression zlib
            try:
                decompressed = zlib.decompress(compressed)
            except Exception:
                try:
                    decompressed = zlib.decompress(compressed, wbits=-zlib.MAX_WBITS)
                except Exception as e:
                    print(f"Erreur décompression: {e}")
                    continue

            print(f"  Taille décompressée: {len(decompressed)} bytes")

            # Analyser la structure
            events = analyze_event_structure(decompressed)
            all_results.extend(events)
            print(f"  Events trouvés: {len(events)}")

        return all_results


# =============================================================================
# Phase 3 : Statistiques et corrélations
# =============================================================================


def analyze_header_patterns(gamertag: str) -> None:
    """
    Analyse les patterns dans les headers des events pour identifier des constantes.

    Si le header contient un weapon_id, on devrait voir des patterns récurrents
    corrélés avec les armes utilisées.
    """
    db_path = get_player_db_path(gamertag)
    if not db_path:
        print(f"ERREUR: Base non trouvée pour {gamertag}")
        return

    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        # Récupérer les matchs avec leurs stats
        query = """
            SELECT DISTINCT match_id, start_time
            FROM match_stats
            ORDER BY start_time DESC
            LIMIT 50
        """
        matches = conn.execute(query).fetchall()

        print(f"\nAnalyse de {len(matches)} matchs récents...")

        for match_id, start_time in matches:
            # Récupérer les events de ce match
            events = conn.execute(
                """
                SELECT raw_json, event_type, time_ms
                FROM highlight_events
                WHERE match_id = ?
                ORDER BY time_ms
            """,
                [match_id],
            ).fetchall()

            if events:
                print(f"\nMatch {match_id}: {len(events)} events")

                # Analyser la distribution des types
                types = Counter(e[1] for e in events)
                print(f"  Types: {dict(types)}")

    finally:
        conn.close()


def generate_research_report(gamertag: str) -> None:
    """
    Génère un rapport complet de recherche sur les highlight events.
    """
    print("=" * 60)
    print("RAPPORT DE RECHERCHE - HIGHLIGHT EVENTS")
    print(f"Joueur: {gamertag}")
    print("=" * 60)

    # Phase 1: Analyse JSON
    print("\n[PHASE 1] Analyse des raw_json...")
    json_analysis = analyze_json_fields(gamertag, limit=500)

    # Phase 1b: Comparaison kill/death
    print("\n[PHASE 1b] Comparaison kill vs death...")
    compare_kill_death_events(gamertag)

    # Phase 3: Patterns
    print("\n[PHASE 3] Analyse des patterns...")
    analyze_header_patterns(gamertag)

    print("\n" + "=" * 60)
    print("CONCLUSIONS PRÉLIMINAIRES")
    print("=" * 60)

    if json_analysis.get("potentially_interesting"):
        print("\n🔥 Champs potentiellement liés aux armes trouvés:")
        for field in json_analysis["potentially_interesting"]:
            print(f"   - {field}")
    else:
        print("\n⚠️ Aucun champ évident lié aux armes dans le raw_json")
        print("   → Les données d'arme sont probablement dans les bytes binaires")
        print("   → Ou dans un event séparé corrélé par timestamp")

    print("\n📋 Prochaines étapes suggérées:")
    print("   1. Télécharger des chunks bruts avec --match-id et --analyze-binary")
    print("   2. Comparer les bytes non documentés entre différents types d'armes")
    print("   3. Corréler avec les weapon_stats de l'API match_stats")


# =============================================================================
# CLI
# =============================================================================


def _load_dotenv_if_present() -> None:
    """Charge les variables d'environnement depuis .env.local ou .env."""
    repo_root = Path(__file__).resolve().parent.parent
    for name in (".env.local", ".env"):
        p = repo_root / name
        if not p.exists():
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and os.environ.get(key) is None:
                os.environ[key] = value


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Analyse expérimentale des highlight events pour identifier les patterns d'armes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
    # Analyser les raw_json d'un joueur
    python scripts/analyze_highlight_binary.py --gamertag MonGT --analyze-json

    # Télécharger et analyser les chunks binaires d'un match
    python scripts/analyze_highlight_binary.py --match-id <GUID> --analyze-binary

    # Générer un rapport complet
    python scripts/analyze_highlight_binary.py --gamertag MonGT --report
        """,
    )

    parser.add_argument("--gamertag", help="Gamertag du joueur")
    parser.add_argument("--match-id", help="ID du match à analyser")
    parser.add_argument(
        "--analyze-json", action="store_true", help="Analyser les raw_json existants"
    )
    parser.add_argument(
        "--analyze-binary", action="store_true", help="Analyser les chunks binaires"
    )
    parser.add_argument("--compare-types", action="store_true", help="Comparer kill vs death")
    parser.add_argument("--report", action="store_true", help="Générer un rapport complet")
    parser.add_argument("--limit", type=int, default=500, help="Nombre d'events à analyser")

    args = parser.parse_args()

    _load_dotenv_if_present()

    if args.report:
        if not args.gamertag:
            parser.error("--report nécessite --gamertag")
        generate_research_report(args.gamertag)
        return 0

    if args.analyze_json:
        if not args.gamertag:
            parser.error("--analyze-json nécessite --gamertag")
        analyze_json_fields(args.gamertag, limit=args.limit)
        return 0

    if args.compare_types:
        if not args.gamertag:
            parser.error("--compare-types nécessite --gamertag")
        compare_kill_death_events(args.gamertag)
        return 0

    if args.analyze_binary:
        if not args.match_id:
            parser.error("--analyze-binary nécessite --match-id")

        # Vérifier les tokens
        spartan = os.environ.get("SPNKR_SPARTAN_TOKEN")
        clearance = os.environ.get("SPNKR_CLEARANCE_TOKEN")

        if not spartan or not clearance:
            print("ERREUR: Tokens manquants (SPNKR_SPARTAN_TOKEN, SPNKR_CLEARANCE_TOKEN)")
            print("Configurez-les dans .env.local ou via variables d'environnement")
            return 1

        headers = {
            "accept": "application/json",
            "x-343-authorization-spartan": spartan,
            "343-clearance": clearance,
            "user-agent": "openspartan-graph/highlight-analyzer",
        }

        print(f"Analyse binaire du match {args.match_id}...")
        events = asyncio.run(download_and_analyze_chunk(args.match_id, headers))

        if events:
            print(f"\n{len(events)} events extraits")

            # Afficher quelques exemples
            for i, ev in enumerate(events[:5]):
                print(f"\n--- Event {i + 1} ---")
                print(f"Gamertag: {ev.gamertag}")
                print(
                    f"Type: {ev.event_type} ({'kill' if ev.event_type == 50 else 'death' if ev.event_type == 20 else 'mode'})"
                )
                print(f"Timestamp: {ev.timestamp_ms} ms")
                print(f"Medal ID: {ev.medal_id}")
                print(f"Header (12 bytes):\n{hex_dump(ev.header_bytes)}")
                print(f"Bytes supplémentaires (32 bytes):\n{hex_dump(ev.extra_bytes)}")

        return 0

    # Par défaut, afficher l'aide
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
