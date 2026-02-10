#!/usr/bin/env python3
"""
Script de migration des HighlightEvents SQLite vers DuckDB.

Ce script migre la table HighlightEvents (contenant les événements de film/replay)
depuis les DBs SQLite legacy vers les DBs DuckDB v4.

Usage:
    python scripts/migrate_highlight_events.py --gamertag JGtm
    python scripts/migrate_highlight_events.py --all
    python scripts/migrate_highlight_events.py --gamertag JGtm --dry-run

Structure source (SQLite):
    - HighlightEvents: MatchId VARCHAR, ResponseBody TEXT (JSON)

Structure cible (DuckDB):
    - highlight_events: match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import duckdb
except ImportError:
    print("ERREUR: DuckDB non installé. Exécutez: pip install duckdb")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Configuration des chemins
DATA_DIR = Path(__file__).parent.parent / "data"
PLAYERS_DIR = DATA_DIR / "players"
DB_PROFILES_PATH = Path(__file__).parent.parent / "db_profiles.json"

# Patterns pour nettoyer les gamertags
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def load_db_profiles() -> dict[str, Any]:
    """Charge la configuration des profils joueurs."""
    if not DB_PROFILES_PATH.exists():
        return {"profiles": {}}
    with open(DB_PROFILES_PATH, encoding="utf-8") as f:
        return json.load(f)


def sanitize_gamertag(value: Any) -> str:
    """Nettoie un gamertag en supprimant les caractères de contrôle."""
    if value is None:
        return ""
    if isinstance(value, bytes | bytearray | memoryview):
        raw = bytes(value)
        for enc in ("utf-8", "utf-16-le", "utf-16"):
            try:
                value = raw.decode(enc)
                break
            except Exception:
                continue
        else:
            value = raw.decode("utf-8", errors="replace")

    if not isinstance(value, str):
        return str(value) if value else ""

    # Supprimer les caractères de contrôle
    s = _CTRL_RE.sub("", value)
    s = s.replace("\ufffd", "")
    s = " ".join(s.split()).strip()
    return s


def ensure_highlight_events_table(conn: duckdb.DuckDBPyConnection) -> None:
    """S'assure que la table highlight_events existe dans DuckDB."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS highlight_events (
            id INTEGER PRIMARY KEY,
            match_id VARCHAR NOT NULL,
            event_type VARCHAR NOT NULL,
            time_ms INTEGER,
            xuid VARCHAR,
            gamertag VARCHAR,
            type_hint INTEGER,
            raw_json VARCHAR
        )
    """)
    with contextlib.suppress(Exception):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_highlight_match ON highlight_events(match_id)")


def load_highlight_events_from_sqlite(
    legacy_db_path: Path,
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Charge tous les HighlightEvents depuis SQLite.

    Returns:
        Liste de tuples (match_id, events_list) où events_list contient les JSON parsés.
    """
    results: list[tuple[str, list[dict[str, Any]]]] = []

    try:
        with sqlite3.connect(str(legacy_db_path)) as conn:
            cursor = conn.cursor()

            # Vérifier si la table existe
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='HighlightEvents'"
            )
            if not cursor.fetchone():
                logger.warning(f"Table HighlightEvents non trouvée dans {legacy_db_path}")
                return []

            # Charger tous les events
            cursor.execute("SELECT MatchId, ResponseBody FROM HighlightEvents")
            rows = cursor.fetchall()

            for match_id, body in rows:
                if not match_id or not body:
                    continue

                # Décoder le body si nécessaire
                body_str: str | None = None
                if isinstance(body, str):
                    body_str = body
                elif isinstance(body, bytes | bytearray | memoryview):
                    raw = bytes(body)
                    for enc in ("utf-8", "utf-16-le", "utf-16"):
                        try:
                            body_str = raw.decode(enc)
                            break
                        except Exception:
                            continue
                    if body_str is None:
                        body_str = raw.decode("utf-8", errors="replace")

                if not body_str:
                    continue

                try:
                    obj = json.loads(body_str)
                except Exception:
                    continue

                # Le body peut être un dict unique ou une liste d'events
                events: list[dict[str, Any]] = []
                if isinstance(obj, dict):
                    events = [obj]
                elif isinstance(obj, list):
                    events = [e for e in obj if isinstance(e, dict)]

                if events:
                    results.append((str(match_id), events))

    except Exception as e:
        logger.error(f"Erreur lecture SQLite: {e}")

    return results


def transform_event(event_dict: dict[str, Any], match_id: str) -> dict[str, Any] | None:
    """Transforme un event JSON en format DuckDB.

    Returns:
        Dict avec les champs pour DuckDB ou None si invalide.
    """
    # L'event peut avoir différentes structures selon la source
    # Structures possibles:
    # 1. {"event_type": "Kill", "time_ms": 1234, "xuid": "...", ...}
    # 2. {"EventType": "Kill", "TimestampMs": 1234, "PlayerId": "xuid(...)", ...}
    # 3. Autres variantes

    event_type = event_dict.get("event_type") or event_dict.get("EventType")
    if not event_type:
        # Essayer de déterminer le type depuis d'autres champs
        if "Killed" in str(event_dict) or "killed" in str(event_dict).lower():
            event_type = "Kill"
        elif "Death" in str(event_dict) or "died" in str(event_dict).lower():
            event_type = "Death"
        else:
            event_type = "Unknown"

    # Extraire le time_ms
    time_ms = (
        event_dict.get("time_ms")
        or event_dict.get("TimestampMs")
        or event_dict.get("TimeMs")
        or event_dict.get("timestamp_ms")
        or 0
    )
    try:
        time_ms = int(time_ms)
    except (TypeError, ValueError):
        time_ms = 0

    # Extraire le XUID
    xuid = event_dict.get("xuid") or event_dict.get("Xuid")
    if not xuid:
        player_id = event_dict.get("PlayerId") or event_dict.get("player_id")
        if player_id:
            if isinstance(player_id, str):
                # Format xuid(123456789)
                match = re.search(r"(\d{12,20})", player_id)
                if match:
                    xuid = match.group(1)
            elif isinstance(player_id, dict):
                xuid = str(player_id.get("Xuid") or player_id.get("xuid") or "")

    xuid = str(xuid) if xuid else None

    # Extraire le gamertag
    gamertag = event_dict.get("gamertag") or event_dict.get("Gamertag")
    gamertag = sanitize_gamertag(gamertag) if gamertag else None

    # Extraire le type_hint (indice supplémentaire sur le type d'event)
    type_hint = event_dict.get("type_hint") or event_dict.get("TypeHint")
    try:
        type_hint = int(type_hint) if type_hint is not None else None
    except (TypeError, ValueError):
        type_hint = None

    return {
        "match_id": match_id,
        "event_type": str(event_type),
        "time_ms": time_ms,
        "xuid": xuid,
        "gamertag": gamertag,
        "type_hint": type_hint,
        "raw_json": json.dumps(event_dict, ensure_ascii=False),
    }


def migrate_highlight_events(
    gamertag: str,
    legacy_db_path: Path,
    target_db_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Migre les HighlightEvents d'un joueur de SQLite vers DuckDB.

    Returns:
        dict avec les statistiques de migration
    """
    results: dict[str, Any] = {
        "gamertag": gamertag,
        "success": False,
        "matches_count": 0,
        "events_count": 0,
        "errors": [],
    }

    if not legacy_db_path.exists():
        results["errors"].append(f"Base legacy non trouvée: {legacy_db_path}")
        logger.error(results["errors"][-1])
        return results

    if not target_db_path.exists():
        results["errors"].append(f"Base DuckDB cible non trouvée: {target_db_path}")
        results["errors"].append("Exécutez d'abord migrate_player_to_duckdb.py")
        logger.error(results["errors"][0])
        return results

    try:
        # Charger les events depuis SQLite
        logger.info(f"Chargement des HighlightEvents depuis {legacy_db_path}...")
        all_events = load_highlight_events_from_sqlite(legacy_db_path)

        if not all_events:
            logger.info("Aucun HighlightEvent trouvé dans la source")
            results["success"] = True
            return results

        results["matches_count"] = len(all_events)
        logger.info(f"  -> {len(all_events)} matchs avec events")

        # Transformer les events
        transformed_events: list[dict[str, Any]] = []
        for match_id, events in all_events:
            for event in events:
                row = transform_event(event, match_id)
                if row:
                    transformed_events.append(row)

        results["events_count"] = len(transformed_events)
        logger.info(f"  -> {len(transformed_events)} events au total")

        if dry_run:
            logger.info("[DRY-RUN] Pas d'écriture effectuée")
            results["success"] = True
            return results

        # Connexion DuckDB
        conn = duckdb.connect(str(target_db_path))

        try:
            # S'assurer que la table existe
            ensure_highlight_events_table(conn)

            # Supprimer les events existants pour éviter les doublons
            existing_match_ids = {m for m, _ in all_events}
            placeholders = ",".join(["?"] * len(existing_match_ids))
            if existing_match_ids:
                conn.execute(
                    f"DELETE FROM highlight_events WHERE match_id IN ({placeholders})",
                    list(existing_match_ids),
                )
                logger.info(f"  -> {len(existing_match_ids)} matchs nettoyés")

            # Insérer les nouveaux events
            insert_sql = """
                INSERT INTO highlight_events
                (match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """

            inserted = 0
            for row in transformed_events:
                try:
                    conn.execute(
                        insert_sql,
                        (
                            row["match_id"],
                            row["event_type"],
                            row["time_ms"],
                            row["xuid"],
                            row["gamertag"],
                            row["type_hint"],
                            row["raw_json"],
                        ),
                    )
                    inserted += 1
                except Exception as e:
                    if verbose:
                        logger.warning(f"Erreur insertion event: {e}")

            logger.info(f"  -> {inserted} events insérés")

            # Validation
            check = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
            logger.info(f"  -> Total events en BDD: {check}")

            results["success"] = True

        finally:
            conn.close()

    except Exception as e:
        results["errors"].append(f"Erreur fatale: {e}")
        logger.error(f"Erreur fatale: {e}")
        if verbose:
            import traceback

            traceback.print_exc()

    return results


def print_summary(all_results: list[dict[str, Any]]) -> None:
    """Affiche un résumé de toutes les migrations."""
    print("\n" + "=" * 60)
    print("RÉSUMÉ DE LA MIGRATION HIGHLIGHT EVENTS")
    print("=" * 60)

    success_count = sum(1 for r in all_results if r["success"])
    total_matches = sum(r["matches_count"] for r in all_results)
    total_events = sum(r["events_count"] for r in all_results)

    print(f"\nJoueurs migrés: {success_count}/{len(all_results)}")
    print(f"Total matchs avec events: {total_matches}")
    print(f"Total events: {total_events}")

    print("\nDétail par joueur:")
    for result in all_results:
        status = "[OK]" if result["success"] else "[X]"
        print(
            f"  {status} {result['gamertag']}: {result['matches_count']} matchs, "
            f"{result['events_count']} events"
        )
        if result["errors"]:
            for error in result["errors"]:
                print(f"      Erreur: {error}")

    print("\n" + "=" * 60)


def find_legacy_db(gamertag: str, profile: dict[str, Any]) -> Path | None:
    """Trouve le chemin de la DB legacy pour un joueur."""
    # Chercher dans l'ordre de priorité
    candidates = [
        Path(profile.get("legacy_db_path", "")),
        DATA_DIR / f"spnkr_gt_{gamertag}.db",
        Path(f"data/spnkr_gt_{gamertag}.db"),
        Path(f"spnkr_gt_{gamertag}.db"),
        # DBs unifiées
        DATA_DIR / "halo_unified.db",
        Path("data/halo_unified.db"),
    ]

    for path in candidates:
        if path and path.exists():
            return path

    return None


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Migre les HighlightEvents de SQLite vers DuckDB",
    )
    parser.add_argument(
        "--gamertag",
        help="Gamertag du joueur à migrer",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrer tous les joueurs de db_profiles.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule la migration sans écrire",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Affiche plus de détails",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.gamertag and not args.all:
        parser.error("Spécifie --gamertag ou --all")
        return 1

    # Charger les profils
    profiles = load_db_profiles()

    if not profiles.get("profiles"):
        logger.error("Aucun profil trouvé dans db_profiles.json")
        return 1

    # Déterminer les joueurs à migrer
    gamertags = list(profiles["profiles"].keys()) if args.all else [args.gamertag]

    logger.info("=" * 60)
    logger.info("Migration HighlightEvents SQLite -> DuckDB")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("[DRY-RUN] Aucune modification ne sera effectuée")

    all_results = []

    for gamertag in gamertags:
        if gamertag not in profiles["profiles"]:
            logger.warning(f"Joueur {gamertag} non trouvé dans db_profiles.json")
            continue

        profile = profiles["profiles"][gamertag]
        target_path = Path(profile.get("db_path", f"data/players/{gamertag}/stats.duckdb"))
        legacy_path = find_legacy_db(gamertag, profile)

        if not legacy_path:
            logger.warning(f"Base legacy non trouvée pour {gamertag}")
            continue

        logger.info(f"\n--- Migration de {gamertag} ---")
        logger.info(f"Source: {legacy_path}")
        logger.info(f"Destination: {target_path}")

        result = migrate_highlight_events(
            gamertag=gamertag,
            legacy_db_path=legacy_path,
            target_db_path=target_path,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        all_results.append(result)

    print_summary(all_results)

    # Retourner 0 si au moins une migration a réussi
    return 0 if any(r["success"] for r in all_results) else 1


if __name__ == "__main__":
    sys.exit(main())
