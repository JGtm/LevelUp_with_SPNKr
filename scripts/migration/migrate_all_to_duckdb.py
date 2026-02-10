#!/usr/bin/env python3
"""
Script unifié de migration complète vers DuckDB.

Ce script exécute toutes les migrations nécessaires pour passer
d'une architecture SQLite legacy à l'architecture DuckDB v4 :

1. MatchCache → match_stats (via migrate_player_to_duckdb.py)
2. HighlightEvents → highlight_events
3. PlayerMatchStats → player_match_stats
4. XuidAliases → xuid_aliases

Usage:
    python scripts/migrate_all_to_duckdb.py --gamertag JGtm
    python scripts/migrate_all_to_duckdb.py --all
    python scripts/migrate_all_to_duckdb.py --gamertag JGtm --dry-run
    python scripts/migrate_all_to_duckdb.py --all --skip-matchcache  # Si déjà migré
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
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

# Pattern pour nettoyer les gamertags
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

    s = _CTRL_RE.sub("", value)
    s = s.replace("\ufffd", "")
    s = " ".join(s.split()).strip()
    return s


def find_legacy_db(gamertag: str, profile: dict[str, Any]) -> Path | None:
    """Trouve le chemin de la DB legacy pour un joueur."""
    candidates = [
        Path(profile.get("legacy_db_path", "")),
        DATA_DIR / f"spnkr_gt_{gamertag}.db",
        Path(f"data/spnkr_gt_{gamertag}.db"),
        Path(f"spnkr_gt_{gamertag}.db"),
        DATA_DIR / "halo_unified.db",
        Path("data/halo_unified.db"),
    ]

    for path in candidates:
        if path and path.exists():
            return path

    return None


def ensure_all_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """S'assure que toutes les tables nécessaires existent dans DuckDB."""
    # Table highlight_events
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

    # Table player_match_stats
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_match_stats (
            match_id VARCHAR PRIMARY KEY,
            xuid VARCHAR NOT NULL,
            team_id TINYINT,
            team_mmr FLOAT,
            enemy_mmr FLOAT,
            kills_expected FLOAT,
            kills_stddev FLOAT,
            deaths_expected FLOAT,
            deaths_stddev FLOAT,
            assists_expected FLOAT,
            assists_stddev FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table xuid_aliases
    conn.execute("""
        CREATE TABLE IF NOT EXISTS xuid_aliases (
            xuid VARCHAR PRIMARY KEY,
            gamertag VARCHAR NOT NULL,
            last_seen TIMESTAMP,
            source VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    with contextlib.suppress(Exception):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_aliases_gamertag ON xuid_aliases(gamertag)")

    # Table sync_meta
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_meta (
            key VARCHAR PRIMARY KEY,
            value VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


# =============================================================================
# Migration des XuidAliases
# =============================================================================


def load_xuid_aliases_from_sqlite(legacy_db_path: Path) -> list[dict[str, Any]]:
    """Charge les XuidAliases depuis SQLite.

    Cherche dans plusieurs tables possibles :
    - XuidAliases (table dédiée)
    - Players (table des joueurs rencontrés)
    - Extraction depuis MatchStats (fallback)
    """
    results: list[dict[str, Any]] = []
    seen_xuids: set[str] = set()

    try:
        with sqlite3.connect(str(legacy_db_path)) as conn:
            cursor = conn.cursor()

            # 1. Essayer la table XuidAliases
            cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='XuidAliases'")
            if cursor.fetchone():
                try:
                    cursor.execute("SELECT xuid, gamertag, last_seen FROM XuidAliases")
                    for xuid, gamertag, last_seen in cursor.fetchall():
                        if not xuid or xuid in seen_xuids:
                            continue
                        gt = sanitize_gamertag(gamertag)
                        if not gt:
                            continue
                        seen_xuids.add(str(xuid))
                        results.append(
                            {
                                "xuid": str(xuid),
                                "gamertag": gt,
                                "last_seen": last_seen,
                                "source": "XuidAliases",
                            }
                        )
                except Exception:
                    pass

            # 2. Essayer la table Players
            cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='Players'")
            if cursor.fetchone():
                try:
                    cursor.execute("SELECT xuid, gamertag FROM Players")
                    for xuid, gamertag in cursor.fetchall():
                        if not xuid or xuid in seen_xuids:
                            continue
                        gt = sanitize_gamertag(gamertag)
                        if not gt:
                            continue
                        seen_xuids.add(str(xuid))
                        results.append(
                            {
                                "xuid": str(xuid),
                                "gamertag": gt,
                                "last_seen": None,
                                "source": "Players",
                            }
                        )
                except Exception:
                    pass

            # 3. Extraire depuis MatchStats (fallback)
            cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='MatchStats'")
            if cursor.fetchone():
                try:
                    cursor.execute("SELECT ResponseBody FROM MatchStats LIMIT 500")
                    for (body,) in cursor.fetchall():
                        if not body:
                            continue
                        try:
                            obj = json.loads(body) if isinstance(body, str) else None
                            if not obj:
                                continue
                            players = obj.get("Players", [])
                            for p in players:
                                if not isinstance(p, dict):
                                    continue
                                pid = p.get("PlayerId")
                                xuid = None
                                if isinstance(pid, str):
                                    m = re.search(r"(\d{12,20})", pid)
                                    if m:
                                        xuid = m.group(1)
                                elif isinstance(pid, dict):
                                    xuid = str(pid.get("Xuid") or pid.get("xuid") or "")

                                if not xuid or xuid in seen_xuids:
                                    continue

                                gt = sanitize_gamertag(p.get("PlayerGamertag") or p.get("Gamertag"))
                                if not gt:
                                    continue

                                seen_xuids.add(xuid)
                                results.append(
                                    {
                                        "xuid": xuid,
                                        "gamertag": gt,
                                        "last_seen": None,
                                        "source": "MatchStats",
                                    }
                                )
                        except Exception:
                            continue
                except Exception:
                    pass

    except Exception as e:
        logger.warning(f"Erreur extraction aliases: {e}")

    return results


# =============================================================================
# Migration unifiée
# =============================================================================


def migrate_all(
    gamertag: str,
    xuid: str,
    legacy_db_path: Path,
    target_db_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
    skip_matchcache: bool = False,
) -> dict[str, Any]:
    """
    Migre toutes les données d'un joueur de SQLite vers DuckDB.

    Returns:
        dict avec les statistiques de migration
    """
    results: dict[str, Any] = {
        "gamertag": gamertag,
        "success": False,
        "highlight_events": 0,
        "player_match_stats": 0,
        "xuid_aliases": 0,
        "errors": [],
    }

    if not legacy_db_path.exists():
        results["errors"].append(f"Base legacy non trouvée: {legacy_db_path}")
        logger.error(results["errors"][-1])
        return results

    # Créer le dossier du joueur si nécessaire
    target_db_path.parent.mkdir(parents=True, exist_ok=True)

    # Vérifier si on doit d'abord exécuter migrate_player_to_duckdb.py
    if not target_db_path.exists() and not skip_matchcache:
        logger.warning(f"Base DuckDB {target_db_path} n'existe pas.")
        logger.warning("Exécutez d'abord: python scripts/migrate_player_to_duckdb.py")
        results["errors"].append("Base DuckDB cible non trouvée")
        return results

    try:
        if dry_run:
            conn = duckdb.connect(":memory:")
            logger.info(f"[DRY-RUN] Migration de {gamertag} en mémoire")
        else:
            conn = duckdb.connect(str(target_db_path))
            logger.info(f"Connexion à: {target_db_path}")

        # S'assurer que toutes les tables existent
        ensure_all_tables(conn)

        # Attacher la base SQLite legacy
        conn.execute(f"ATTACH '{legacy_db_path}' AS legacy (TYPE SQLITE, READ_ONLY)")

        # =================================================================
        # 1. Migration des HighlightEvents
        # =================================================================
        logger.info("\n[1/3] Migration HighlightEvents...")
        try:
            # Vérifier si la table existe
            check = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='HighlightEvents'"
            )
            if check.fetchone()[0] > 0:
                # Compter les events source
                events_count = conn.execute(
                    "SELECT COUNT(*) FROM legacy.HighlightEvents"
                ).fetchone()[0]

                if events_count > 0:
                    # Charger et transformer les events
                    cursor = conn.execute(
                        "SELECT MatchId, ResponseBody FROM legacy.HighlightEvents"
                    )
                    inserted = 0
                    now = datetime.now(timezone.utc)

                    for match_id, body in cursor.fetchall():
                        if not match_id or not body:
                            continue

                        try:
                            obj = json.loads(body) if isinstance(body, str) else None
                            if not obj:
                                continue

                            events = [obj] if isinstance(obj, dict) else obj
                            for event in events:
                                if not isinstance(event, dict):
                                    continue

                                event_type = (
                                    event.get("event_type") or event.get("EventType") or "Unknown"
                                )
                                time_ms = int(
                                    event.get("time_ms")
                                    or event.get("TimestampMs")
                                    or event.get("TimeMs")
                                    or 0
                                )
                                evt_xuid = event.get("xuid") or event.get("Xuid")
                                evt_gamertag = sanitize_gamertag(
                                    event.get("gamertag") or event.get("Gamertag")
                                )
                                type_hint = event.get("type_hint") or event.get("TypeHint")

                                conn.execute(
                                    """INSERT INTO highlight_events
                                       (match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json)
                                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                    (
                                        str(match_id),
                                        str(event_type),
                                        time_ms,
                                        str(evt_xuid) if evt_xuid else None,
                                        evt_gamertag or None,
                                        int(type_hint) if type_hint else None,
                                        json.dumps(event, ensure_ascii=False),
                                    ),
                                )
                                inserted += 1
                        except Exception as e:
                            if verbose:
                                logger.warning(f"Erreur event: {e}")

                    results["highlight_events"] = inserted
                    logger.info(f"  -> {inserted} highlight events migrés")
                else:
                    logger.info("  -> Aucun HighlightEvent trouvé")
            else:
                logger.info("  -> Table HighlightEvents non trouvée")

        except Exception as e:
            error_msg = f"Erreur migration HighlightEvents: {e}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # =================================================================
        # 2. Migration des PlayerMatchStats
        # =================================================================
        logger.info("\n[2/3] Migration PlayerMatchStats...")
        try:
            check = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='PlayerMatchStats'"
            )
            if check.fetchone()[0] > 0:
                stats_count = conn.execute(
                    "SELECT COUNT(*) FROM legacy.PlayerMatchStats"
                ).fetchone()[0]

                if stats_count > 0:
                    cursor = conn.execute(
                        "SELECT MatchId, ResponseBody FROM legacy.PlayerMatchStats"
                    )
                    inserted = 0
                    now = datetime.now(timezone.utc)

                    for match_id, body in cursor.fetchall():
                        if not match_id or not body:
                            continue

                        try:
                            payload = json.loads(body) if isinstance(body, str) else None
                            if not payload:
                                continue

                            values = payload.get("Value", [])
                            if not isinstance(values, list):
                                continue

                            # Trouver notre joueur
                            entry = None
                            for v in values:
                                if not isinstance(v, dict):
                                    continue
                                pid = v.get("Id")
                                if pid and xuid in str(pid):
                                    entry = v
                                    break

                            if not entry:
                                continue

                            result_data = entry.get("Result", {})
                            team_id = result_data.get("TeamId")
                            team_mmr = result_data.get("TeamMmr")

                            # Calculer enemy_mmr
                            enemy_mmr = None
                            team_mmrs = result_data.get("TeamMmrs", {})
                            if isinstance(team_mmrs, dict) and team_id is not None:
                                for k, v in team_mmrs.items():
                                    if k != str(team_id):
                                        enemy_mmr = float(v) if v else None
                                        break

                            # Extraire StatPerformances
                            stat_perfs = result_data.get("StatPerformances", {})
                            kills_exp = deaths_exp = assists_exp = None
                            kills_std = deaths_std = assists_std = None

                            if isinstance(stat_perfs, dict):
                                for name, perf in stat_perfs.items():
                                    if not isinstance(perf, dict):
                                        continue
                                    nl = name.lower()
                                    if nl == "kills":
                                        kills_exp = perf.get("Expected")
                                        kills_std = perf.get("StdDev")
                                    elif nl == "deaths":
                                        deaths_exp = perf.get("Expected")
                                        deaths_std = perf.get("StdDev")
                                    elif nl == "assists":
                                        assists_exp = perf.get("Expected")
                                        assists_std = perf.get("StdDev")

                            conn.execute(
                                """INSERT OR REPLACE INTO player_match_stats
                                   (match_id, xuid, team_id, team_mmr, enemy_mmr,
                                    kills_expected, kills_stddev, deaths_expected, deaths_stddev,
                                    assists_expected, assists_stddev, created_at)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    str(match_id),
                                    xuid,
                                    int(team_id) if team_id is not None else None,
                                    float(team_mmr) if team_mmr else None,
                                    enemy_mmr,
                                    float(kills_exp) if kills_exp else None,
                                    float(kills_std) if kills_std else None,
                                    float(deaths_exp) if deaths_exp else None,
                                    float(deaths_std) if deaths_std else None,
                                    float(assists_exp) if assists_exp else None,
                                    float(assists_std) if assists_std else None,
                                    now,
                                ),
                            )
                            inserted += 1

                        except Exception as e:
                            if verbose:
                                logger.warning(f"Erreur stat: {e}")

                    results["player_match_stats"] = inserted
                    logger.info(f"  -> {inserted} player match stats migrés")
                else:
                    logger.info("  -> Aucun PlayerMatchStats trouvé")
            else:
                logger.info("  -> Table PlayerMatchStats non trouvée")

        except Exception as e:
            error_msg = f"Erreur migration PlayerMatchStats: {e}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # =================================================================
        # 3. Migration des XuidAliases
        # =================================================================
        logger.info("\n[3/3] Migration XuidAliases...")
        try:
            conn.execute("DETACH legacy")

            # Recharger via fonction Python (plus flexible)
            aliases = load_xuid_aliases_from_sqlite(legacy_db_path)

            if aliases:
                now = datetime.now(timezone.utc)
                inserted = 0

                for alias in aliases:
                    try:
                        conn.execute(
                            """INSERT INTO xuid_aliases (xuid, gamertag, last_seen, source, updated_at)
                               VALUES (?, ?, ?, ?, ?)
                               ON CONFLICT(xuid) DO UPDATE SET
                                   gamertag = CASE
                                       WHEN excluded.gamertag != '' THEN excluded.gamertag
                                       ELSE xuid_aliases.gamertag
                                   END,
                                   last_seen = COALESCE(excluded.last_seen, xuid_aliases.last_seen),
                                   updated_at = CURRENT_TIMESTAMP""",
                            (
                                alias["xuid"],
                                alias["gamertag"],
                                alias["last_seen"],
                                alias["source"],
                                now,
                            ),
                        )
                        inserted += 1
                    except Exception as e:
                        if verbose:
                            logger.warning(f"Erreur alias: {e}")

                results["xuid_aliases"] = inserted
                logger.info(f"  -> {inserted} aliases migrés")
            else:
                logger.info("  -> Aucun alias trouvé")

        except Exception as e:
            error_msg = f"Erreur migration XuidAliases: {e}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # Validation finale
        logger.info("\n=== Validation ===")
        events_check = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
        stats_check = conn.execute("SELECT COUNT(*) FROM player_match_stats").fetchone()[0]
        aliases_check = conn.execute("SELECT COUNT(*) FROM xuid_aliases").fetchone()[0]

        logger.info(f"  highlight_events: {events_check}")
        logger.info(f"  player_match_stats: {stats_check}")
        logger.info(f"  xuid_aliases: {aliases_check}")

        # Mettre à jour sync_meta
        now_str = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value, updated_at) VALUES (?, ?, ?)",
            ("migration_completed", now_str, now_str),
        )
        conn.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value, updated_at) VALUES (?, ?, ?)",
            ("migration_source", str(legacy_db_path), now_str),
        )

        conn.close()
        results["success"] = True

    except Exception as e:
        results["errors"].append(f"Erreur fatale: {e}")
        logger.error(f"Erreur fatale: {e}")
        if verbose:
            import traceback

            traceback.print_exc()

    return results


def print_summary(all_results: list[dict[str, Any]]) -> None:
    """Affiche un résumé de toutes les migrations."""
    print("\n" + "=" * 70)
    print("RÉSUMÉ DE LA MIGRATION COMPLÈTE VERS DUCKDB")
    print("=" * 70)

    success_count = sum(1 for r in all_results if r["success"])
    total_events = sum(r["highlight_events"] for r in all_results)
    total_stats = sum(r["player_match_stats"] for r in all_results)
    total_aliases = sum(r["xuid_aliases"] for r in all_results)

    print(f"\nJoueurs migrés: {success_count}/{len(all_results)}")
    print(f"Total highlight events: {total_events}")
    print(f"Total player match stats: {total_stats}")
    print(f"Total xuid aliases: {total_aliases}")

    print("\nDétail par joueur:")
    for result in all_results:
        status = "[OK]" if result["success"] else "[X]"
        print(f"\n  {status} {result['gamertag']}:")
        print(f"      Highlight Events: {result['highlight_events']}")
        print(f"      Player Match Stats: {result['player_match_stats']}")
        print(f"      XUID Aliases: {result['xuid_aliases']}")
        if result["errors"]:
            for error in result["errors"]:
                print(f"      [!] Erreur: {error}")

    print("\n" + "=" * 70)


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Migration complète SQLite -> DuckDB (HighlightEvents, PlayerMatchStats, XuidAliases)",
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
        "--skip-matchcache",
        action="store_true",
        help="Ne pas vérifier si match_stats a été migré",
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

    logger.info("=" * 70)
    logger.info("MIGRATION COMPLÈTE VERS DUCKDB")
    logger.info("=" * 70)
    logger.info("Tables migrées: HighlightEvents, PlayerMatchStats, XuidAliases")

    if args.dry_run:
        logger.info("[DRY-RUN] Aucune modification ne sera effectuée")

    all_results = []

    for gamertag in gamertags:
        if gamertag not in profiles["profiles"]:
            logger.warning(f"Joueur {gamertag} non trouvé dans db_profiles.json")
            continue

        profile = profiles["profiles"][gamertag]
        xuid = profile.get("xuid", "")
        target_path = Path(profile.get("db_path", f"data/players/{gamertag}/stats.duckdb"))
        legacy_path = find_legacy_db(gamertag, profile)

        if not legacy_path:
            logger.warning(f"Base legacy non trouvée pour {gamertag}")
            continue

        if not xuid:
            logger.warning(f"XUID non trouvé pour {gamertag}")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"Migration de {gamertag}")
        logger.info(f"{'='*60}")
        logger.info(f"Source: {legacy_path}")
        logger.info(f"Destination: {target_path}")
        logger.info(f"XUID: {xuid}")

        result = migrate_all(
            gamertag=gamertag,
            xuid=xuid,
            legacy_db_path=legacy_path,
            target_db_path=target_path,
            dry_run=args.dry_run,
            verbose=args.verbose,
            skip_matchcache=args.skip_matchcache,
        )
        all_results.append(result)

    print_summary(all_results)

    return 0 if any(r["success"] for r in all_results) else 1


if __name__ == "__main__":
    sys.exit(main())
