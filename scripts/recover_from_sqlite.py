#!/usr/bin/env python3
"""Récupère les données depuis les anciennes bases SQLite vers DuckDB v4.

Ce script extrait :
1. match_participants : XUID, team_id, outcome pour TOUS les matchs
2. xuid_aliases : gamertags depuis HighlightEvents et TeammatesAggregate

Usage:
    # Récupérer pour un joueur
    python scripts/recover_from_sqlite.py --gamertag Madina97294

    # Récupérer pour tous les joueurs
    python scripts/recover_from_sqlite.py --all

    # Mode dry-run (affiche sans modifier)
    python scripts/recover_from_sqlite.py --all --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import duckdb
except ImportError:
    print("Error: duckdb not installed. Run: pip install duckdb")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Chemins
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PLAYERS_DIR = DATA_DIR / "players"


def find_sqlite_db(gamertag: str) -> Path | None:
    """Trouve la base SQLite legacy pour un gamertag."""
    sqlite_path = DATA_DIR / f"spnkr_gt_{gamertag}.db"
    if sqlite_path.exists():
        return sqlite_path
    return None


def find_duckdb_path(gamertag: str) -> Path | None:
    """Trouve la base DuckDB v4 pour un gamertag."""
    duckdb_path = PLAYERS_DIR / gamertag / "stats.duckdb"
    if duckdb_path.exists():
        return duckdb_path
    return None


def ensure_tables_exist(duck_conn) -> None:
    """S'assure que les tables nécessaires existent dans DuckDB."""
    # Table match_participants
    duck_conn.execute("""
        CREATE TABLE IF NOT EXISTS match_participants (
            match_id VARCHAR NOT NULL,
            xuid VARCHAR NOT NULL,
            team_id INTEGER,
            outcome INTEGER,
            gamertag VARCHAR,
            PRIMARY KEY (match_id, xuid)
        )
    """)
    duck_conn.execute("CREATE INDEX IF NOT EXISTS idx_mp_xuid ON match_participants(xuid)")
    duck_conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mp_team ON match_participants(match_id, team_id)"
    )

    # Table xuid_aliases
    duck_conn.execute("""
        CREATE TABLE IF NOT EXISTS xuid_aliases (
            xuid VARCHAR PRIMARY KEY,
            gamertag VARCHAR NOT NULL,
            last_seen TIMESTAMP,
            source VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def extract_participants_from_sqlite(
    sqlite_conn: sqlite3.Connection,
) -> list[dict]:
    """Extrait tous les participants depuis MatchStats SQLite."""
    participants = []

    cursor = sqlite_conn.execute("SELECT ResponseBody FROM MatchStats")
    for (response_body,) in cursor:
        try:
            data = json.loads(response_body)
            match_id = data.get("MatchId")
            if not match_id:
                continue

            for player in data.get("Players", []):
                player_id = player.get("PlayerId", "")
                xuid = player_id.replace("xuid(", "").replace(")", "")
                if not xuid:
                    continue

                team_id = player.get("LastTeamId")
                outcome = player.get("Outcome")
                gamertag = player.get("PlayerGamertag")  # Souvent None

                participants.append(
                    {
                        "match_id": match_id,
                        "xuid": xuid,
                        "team_id": team_id,
                        "outcome": outcome,
                        "gamertag": gamertag,
                    }
                )
        except (json.JSONDecodeError, TypeError):
            continue

    return participants


def extract_aliases_from_highlight_events(
    sqlite_conn: sqlite3.Connection,
) -> dict[str, str]:
    """Extrait les mapping XUID -> Gamertag depuis HighlightEvents."""
    xuid_to_gt: dict[str, str] = {}

    try:
        cursor = sqlite_conn.execute("SELECT ResponseBody FROM HighlightEvents")
        for (response_body,) in cursor:
            try:
                data = json.loads(response_body)
                xuid = str(data.get("xuid", ""))
                gamertag = (data.get("gamertag") or "").strip()

                if xuid and gamertag:
                    # Garder le gamertag le plus récent (dernier vu)
                    xuid_to_gt[xuid] = gamertag
            except (json.JSONDecodeError, TypeError):
                continue
    except sqlite3.OperationalError:
        logger.warning("Table HighlightEvents non trouvée")

    return xuid_to_gt


def extract_aliases_from_teammates(
    sqlite_conn: sqlite3.Connection,
) -> dict[str, str]:
    """Extrait les mapping XUID -> Gamertag depuis TeammatesAggregate."""
    xuid_to_gt: dict[str, str] = {}

    try:
        cursor = sqlite_conn.execute("""
            SELECT teammate_xuid, teammate_gamertag
            FROM TeammatesAggregate
            WHERE teammate_gamertag IS NOT NULL AND teammate_gamertag != ''
        """)
        for xuid, gamertag in cursor:
            if xuid and gamertag:
                xuid_to_gt[str(xuid)] = gamertag.strip()
    except sqlite3.OperationalError:
        logger.warning("Table TeammatesAggregate non trouvée")

    return xuid_to_gt


def extract_aliases_from_xuid_aliases(
    sqlite_conn: sqlite3.Connection,
) -> dict[str, str]:
    """Extrait les mapping depuis la table XuidAliases existante."""
    xuid_to_gt: dict[str, str] = {}

    try:
        cursor = sqlite_conn.execute("""
            SELECT Xuid, Gamertag
            FROM XuidAliases
            WHERE Gamertag IS NOT NULL AND Gamertag != ''
        """)
        for xuid, gamertag in cursor:
            if xuid and gamertag:
                xuid_to_gt[str(xuid)] = gamertag.strip()
    except sqlite3.OperationalError:
        logger.warning("Table XuidAliases non trouvée")

    return xuid_to_gt


def insert_participants(
    duck_conn,
    participants: list[dict],
    dry_run: bool = False,
) -> int:
    """Insère les participants dans DuckDB."""
    if dry_run:
        return len(participants)

    inserted = 0
    for p in participants:
        try:
            duck_conn.execute(
                """
                INSERT INTO match_participants (match_id, xuid, team_id, outcome, gamertag)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (match_id, xuid) DO UPDATE SET
                    team_id = COALESCE(excluded.team_id, match_participants.team_id),
                    outcome = COALESCE(excluded.outcome, match_participants.outcome),
                    gamertag = COALESCE(excluded.gamertag, match_participants.gamertag)
            """,
                [p["match_id"], p["xuid"], p["team_id"], p["outcome"], p["gamertag"]],
            )
            inserted += 1
        except Exception as e:
            if inserted == 0:
                logger.warning(f"Erreur insertion participant: {e}")

    return inserted


def insert_aliases(
    duck_conn,
    xuid_to_gt: dict[str, str],
    source: str,
    dry_run: bool = False,
) -> int:
    """Insère les aliases dans DuckDB."""
    if dry_run:
        return len(xuid_to_gt)

    inserted = 0
    for xuid, gamertag in xuid_to_gt.items():
        try:
            # Vérifier si existe déjà
            existing = duck_conn.execute(
                "SELECT gamertag FROM xuid_aliases WHERE xuid = ?", [xuid]
            ).fetchone()

            if existing:
                # Update seulement si le nouveau gamertag est meilleur
                old_gt = existing[0] or ""
                if gamertag and len(gamertag) >= len(old_gt):
                    duck_conn.execute(
                        """
                        UPDATE xuid_aliases
                        SET gamertag = ?, source = ?, updated_at = NOW()
                        WHERE xuid = ?
                    """,
                        [gamertag, source, xuid],
                    )
            else:
                # Insert nouveau
                duck_conn.execute(
                    """
                    INSERT INTO xuid_aliases (xuid, gamertag, source, updated_at)
                    VALUES (?, ?, ?, NOW())
                """,
                    [xuid, gamertag, source],
                )
            inserted += 1
        except Exception as e:
            if inserted == 0:
                logger.warning(f"Erreur insertion alias: {e}")

    return inserted


def recover_player(gamertag: str, dry_run: bool = False) -> dict:
    """Récupère les données pour un joueur."""
    result = {
        "gamertag": gamertag,
        "participants_found": 0,
        "participants_inserted": 0,
        "aliases_found": 0,
        "aliases_inserted": 0,
        "errors": [],
    }

    # Trouver les DBs
    sqlite_path = find_sqlite_db(gamertag)
    if not sqlite_path:
        result["errors"].append(f"SQLite DB non trouvée: spnkr_gt_{gamertag}.db")
        return result

    duckdb_path = find_duckdb_path(gamertag)
    if not duckdb_path:
        result["errors"].append(f"DuckDB non trouvée: {gamertag}/stats.duckdb")
        return result

    logger.info(f"SQLite: {sqlite_path}")
    logger.info(f"DuckDB: {duckdb_path}")

    # Connexions
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    duck_conn = duckdb.connect(str(duckdb_path))

    try:
        # Créer les tables si nécessaire
        if not dry_run:
            ensure_tables_exist(duck_conn)

        # 1. Extraire et insérer les participants
        logger.info("Extraction des participants depuis MatchStats...")
        participants = extract_participants_from_sqlite(sqlite_conn)
        result["participants_found"] = len(participants)
        logger.info(f"  Trouvé {len(participants)} participants")

        if participants:
            inserted = insert_participants(duck_conn, participants, dry_run)
            result["participants_inserted"] = inserted
            logger.info(f"  {'[DRY-RUN] ' if dry_run else ''}Inséré {inserted} participants")

        # 2. Extraire les aliases de toutes les sources
        logger.info("Extraction des aliases...")

        # Source 1: HighlightEvents
        aliases_he = extract_aliases_from_highlight_events(sqlite_conn)
        logger.info(f"  HighlightEvents: {len(aliases_he)} aliases")

        # Source 2: TeammatesAggregate
        aliases_ta = extract_aliases_from_teammates(sqlite_conn)
        logger.info(f"  TeammatesAggregate: {len(aliases_ta)} aliases")

        # Source 3: XuidAliases existante
        aliases_xa = extract_aliases_from_xuid_aliases(sqlite_conn)
        logger.info(f"  XuidAliases: {len(aliases_xa)} aliases")

        # Fusionner (priorité: XuidAliases > TeammatesAggregate > HighlightEvents)
        all_aliases: dict[str, str] = {}
        all_aliases.update(aliases_he)  # Base
        all_aliases.update(aliases_ta)  # Override avec teammates
        all_aliases.update(aliases_xa)  # Override avec xuid_aliases (source la plus fiable)

        result["aliases_found"] = len(all_aliases)
        logger.info(f"  Total aliases uniques: {len(all_aliases)}")

        if all_aliases:
            inserted = insert_aliases(duck_conn, all_aliases, "sqlite_recovery", dry_run)
            result["aliases_inserted"] = inserted
            logger.info(f"  {'[DRY-RUN] ' if dry_run else ''}Inséré {inserted} aliases")

    except Exception as e:
        result["errors"].append(str(e))
        logger.error(f"Erreur: {e}")
    finally:
        sqlite_conn.close()
        duck_conn.close()

    return result


def find_all_players() -> list[str]:
    """Trouve tous les joueurs avec à la fois SQLite et DuckDB."""
    players = []

    if not PLAYERS_DIR.exists():
        return players

    for player_dir in PLAYERS_DIR.iterdir():
        if not player_dir.is_dir():
            continue

        gamertag = player_dir.name
        duckdb_path = player_dir / "stats.duckdb"
        sqlite_path = DATA_DIR / f"spnkr_gt_{gamertag}.db"

        if duckdb_path.exists() and sqlite_path.exists():
            players.append(gamertag)

    return players


def main():
    parser = argparse.ArgumentParser(
        description="Récupère les données depuis SQLite vers DuckDB v4"
    )
    parser.add_argument("--gamertag", "-g", help="Gamertag du joueur à traiter")
    parser.add_argument("--all", "-a", action="store_true", help="Traiter tous les joueurs")
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Affiche ce qui serait fait sans modifier"
    )

    args = parser.parse_args()

    if not args.gamertag and not args.all:
        parser.error("Spécifiez --gamertag ou --all")

    # Déterminer les joueurs à traiter
    if args.all:
        players = find_all_players()
        if not players:
            logger.error("Aucun joueur trouvé avec SQLite + DuckDB")
            return
        logger.info(f"Trouvé {len(players)} joueur(s) avec SQLite + DuckDB")
    else:
        players = [args.gamertag]

    # Traiter chaque joueur
    total_results = {
        "participants_inserted": 0,
        "aliases_inserted": 0,
        "errors": 0,
    }

    for i, gamertag in enumerate(players, 1):
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"[{i}/{len(players)}] Récupération pour {gamertag}")
        logger.info("=" * 60)

        result = recover_player(gamertag, dry_run=args.dry_run)

        total_results["participants_inserted"] += result["participants_inserted"]
        total_results["aliases_inserted"] += result["aliases_inserted"]
        if result["errors"]:
            total_results["errors"] += len(result["errors"])
            for err in result["errors"]:
                logger.error(f"  ❌ {err}")

    # Résumé final
    logger.info("")
    logger.info("=" * 60)
    logger.info("RÉSUMÉ")
    logger.info("=" * 60)
    prefix = "[DRY-RUN] " if args.dry_run else ""
    logger.info(f"{prefix}Participants insérés: {total_results['participants_inserted']}")
    logger.info(f"{prefix}Aliases insérés: {total_results['aliases_inserted']}")
    if total_results["errors"]:
        logger.warning(f"Erreurs: {total_results['errors']}")


if __name__ == "__main__":
    main()
