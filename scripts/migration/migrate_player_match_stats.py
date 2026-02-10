#!/usr/bin/env python3
"""
Script de migration des PlayerMatchStats SQLite vers DuckDB.

Ce script migre la table PlayerMatchStats (contenant les données MMR/skill)
depuis les DBs SQLite legacy vers les DBs DuckDB v4.

Usage:
    python scripts/migrate_player_match_stats.py --gamertag JGtm
    python scripts/migrate_player_match_stats.py --all
    python scripts/migrate_player_match_stats.py --gamertag JGtm --dry-run

Structure source (SQLite):
    - PlayerMatchStats: MatchId VARCHAR, ResponseBody TEXT (JSON)

Structure cible (DuckDB):
    - player_match_stats: match_id, xuid, team_id, team_mmr, enemy_mmr,
                          kills_expected, kills_stddev, deaths_expected, deaths_stddev,
                          assists_expected, assists_stddev, created_at
"""

from __future__ import annotations

import argparse
import json
import logging
import math
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


def load_db_profiles() -> dict[str, Any]:
    """Charge la configuration des profils joueurs."""
    if not DB_PROFILES_PATH.exists():
        return {"profiles": {}}
    with open(DB_PROFILES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _safe_float(v: Any) -> float | None:
    """Convertit une valeur en float, gérant NaN et None."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    """Convertit une valeur en int."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(f)
    except (TypeError, ValueError):
        return None


def ensure_player_match_stats_table(conn: duckdb.DuckDBPyConnection) -> None:
    """S'assure que la table player_match_stats existe dans DuckDB."""
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


def load_player_match_stats_from_sqlite(
    legacy_db_path: Path,
    xuid: str,
) -> list[dict[str, Any]]:
    """Charge tous les PlayerMatchStats depuis SQLite.

    Args:
        legacy_db_path: Chemin vers la DB SQLite.
        xuid: XUID du joueur pour filtrer les données.

    Returns:
        Liste de dicts avec les données transformées.
    """
    results: list[dict[str, Any]] = []

    try:
        with sqlite3.connect(str(legacy_db_path)) as conn:
            cursor = conn.cursor()

            # Vérifier si la table existe
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='PlayerMatchStats'"
            )
            if not cursor.fetchone():
                logger.warning(f"Table PlayerMatchStats non trouvée dans {legacy_db_path}")
                return []

            # Charger tous les stats
            cursor.execute("SELECT MatchId, ResponseBody FROM PlayerMatchStats")
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
                    payload = json.loads(body_str)
                except Exception:
                    continue

                # Extraire les données pour notre joueur
                row = transform_player_match_stats(payload, str(match_id), xuid)
                if row:
                    results.append(row)

    except Exception as e:
        logger.error(f"Erreur lecture SQLite: {e}")

    return results


def transform_player_match_stats(
    payload: dict[str, Any],
    match_id: str,
    xuid: str,
) -> dict[str, Any] | None:
    """Transforme le JSON PlayerMatchStats en format DuckDB.

    Args:
        payload: JSON brut de l'API.
        match_id: ID du match.
        xuid: XUID du joueur à extraire.

    Returns:
        Dict avec les champs pour DuckDB ou None si joueur non trouvé.
    """
    values = payload.get("Value")
    if not isinstance(values, list) or not values:
        return None

    # Trouver notre joueur
    entry: dict[str, Any] | None = None
    for v in values:
        if not isinstance(v, dict):
            continue
        player_id = v.get("Id")
        if player_id and xuid in str(player_id):
            entry = v
            break

    if entry is None:
        return None

    result = entry.get("Result")
    if not isinstance(result, dict):
        return None

    # Extraire les données de base
    team_id = _safe_int(result.get("TeamId"))
    team_mmr = _safe_float(result.get("TeamMmr"))

    # Calculer enemy_mmr depuis TeamMmrs
    enemy_mmr: float | None = None
    team_mmrs_raw = result.get("TeamMmrs")
    if isinstance(team_mmrs_raw, dict) and team_id is not None:
        my_key = str(team_id)
        for k, v in team_mmrs_raw.items():
            if k != my_key:
                enemy_mmr = _safe_float(v)
                break

    # Si pas de TeamMmrs, essayer de calculer depuis les autres joueurs
    if enemy_mmr is None:
        enemy_mmrs = []
        for v in values:
            if not isinstance(v, dict):
                continue
            other_result = v.get("Result", {})
            other_team = other_result.get("TeamId")
            other_mmr = _safe_float(other_result.get("Mmr"))
            if other_team != team_id and other_mmr is not None:
                enemy_mmrs.append(other_mmr)
        if enemy_mmrs:
            enemy_mmr = sum(enemy_mmrs) / len(enemy_mmrs)

    # Extraire les StatPerformances (expected/stddev)
    kills_expected = None
    kills_stddev = None
    deaths_expected = None
    deaths_stddev = None
    assists_expected = None
    assists_stddev = None

    stat_performances = result.get("StatPerformances")
    if isinstance(stat_performances, dict):
        for stat_name, perf in stat_performances.items():
            if not isinstance(perf, dict):
                continue
            expected = _safe_float(perf.get("Expected"))
            stddev = _safe_float(perf.get("StdDev"))

            stat_lower = stat_name.lower()
            if stat_lower == "kills":
                kills_expected = expected
                kills_stddev = stddev
            elif stat_lower == "deaths":
                deaths_expected = expected
                deaths_stddev = stddev
            elif stat_lower == "assists":
                assists_expected = expected
                assists_stddev = stddev

    return {
        "match_id": match_id,
        "xuid": xuid,
        "team_id": team_id,
        "team_mmr": team_mmr,
        "enemy_mmr": enemy_mmr,
        "kills_expected": kills_expected,
        "kills_stddev": kills_stddev,
        "deaths_expected": deaths_expected,
        "deaths_stddev": deaths_stddev,
        "assists_expected": assists_expected,
        "assists_stddev": assists_stddev,
    }


def migrate_player_match_stats(
    gamertag: str,
    xuid: str,
    legacy_db_path: Path,
    target_db_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Migre les PlayerMatchStats d'un joueur de SQLite vers DuckDB.

    Returns:
        dict avec les statistiques de migration
    """
    results: dict[str, Any] = {
        "gamertag": gamertag,
        "success": False,
        "stats_count": 0,
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
        # Charger les stats depuis SQLite
        logger.info(f"Chargement des PlayerMatchStats depuis {legacy_db_path}...")
        all_stats = load_player_match_stats_from_sqlite(legacy_db_path, xuid)

        if not all_stats:
            logger.info("Aucun PlayerMatchStats trouvé dans la source")
            results["success"] = True
            return results

        results["stats_count"] = len(all_stats)
        logger.info(f"  -> {len(all_stats)} matchs avec données skill")

        if dry_run:
            logger.info("[DRY-RUN] Pas d'écriture effectuée")
            results["success"] = True
            return results

        # Connexion DuckDB
        conn = duckdb.connect(str(target_db_path))

        try:
            # S'assurer que la table existe
            ensure_player_match_stats_table(conn)

            # Insérer les stats (INSERT OR REPLACE)
            insert_sql = """
                INSERT OR REPLACE INTO player_match_stats
                (match_id, xuid, team_id, team_mmr, enemy_mmr,
                 kills_expected, kills_stddev, deaths_expected, deaths_stddev,
                 assists_expected, assists_stddev, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            now = datetime.now(timezone.utc)
            inserted = 0

            for row in all_stats:
                try:
                    conn.execute(
                        insert_sql,
                        (
                            row["match_id"],
                            row["xuid"],
                            row["team_id"],
                            row["team_mmr"],
                            row["enemy_mmr"],
                            row["kills_expected"],
                            row["kills_stddev"],
                            row["deaths_expected"],
                            row["deaths_stddev"],
                            row["assists_expected"],
                            row["assists_stddev"],
                            now,
                        ),
                    )
                    inserted += 1
                except Exception as e:
                    if verbose:
                        logger.warning(f"Erreur insertion stat: {e}")

            logger.info(f"  -> {inserted} stats insérées")

            # Validation
            check = conn.execute("SELECT COUNT(*) FROM player_match_stats").fetchone()[0]
            logger.info(f"  -> Total stats en BDD: {check}")

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
    print("RÉSUMÉ DE LA MIGRATION PLAYER MATCH STATS")
    print("=" * 60)

    success_count = sum(1 for r in all_results if r["success"])
    total_stats = sum(r["stats_count"] for r in all_results)

    print(f"\nJoueurs migrés: {success_count}/{len(all_results)}")
    print(f"Total stats skill: {total_stats}")

    print("\nDétail par joueur:")
    for result in all_results:
        status = "[OK]" if result["success"] else "[X]"
        print(f"  {status} {result['gamertag']}: {result['stats_count']} stats")
        if result["errors"]:
            for error in result["errors"]:
                print(f"      Erreur: {error}")

    print("\n" + "=" * 60)


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


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Migre les PlayerMatchStats de SQLite vers DuckDB",
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
    logger.info("Migration PlayerMatchStats SQLite -> DuckDB")
    logger.info("=" * 60)

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

        logger.info(f"\n--- Migration de {gamertag} ---")
        logger.info(f"Source: {legacy_path}")
        logger.info(f"Destination: {target_path}")
        logger.info(f"XUID: {xuid}")

        result = migrate_player_match_stats(
            gamertag=gamertag,
            xuid=xuid,
            legacy_db_path=legacy_path,
            target_db_path=target_path,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        all_results.append(result)

    print_summary(all_results)

    return 0 if any(r["success"] for r in all_results) else 1


if __name__ == "__main__":
    sys.exit(main())
