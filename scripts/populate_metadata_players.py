#!/usr/bin/env python3
"""Peuple la table players de metadata.duckdb.

Sources :
1. db_profiles.json : les profils configurés
2. xuid_aliases : tous les joueurs rencontrés (depuis chaque stats.duckdb)

Usage:
    python scripts/populate_metadata_players.py
    python scripts/populate_metadata_players.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import duckdb
except ImportError:
    print("Error: duckdb not installed. Run: pip install duckdb")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
WAREHOUSE_DIR = DATA_DIR / "warehouse"
METADATA_PATH = WAREHOUSE_DIR / "metadata.duckdb"
PLAYERS_DIR = DATA_DIR / "players"
DB_PROFILES_PATH = PROJECT_ROOT / "db_profiles.json"


def _ensure_metadata_db() -> Path:
    """Crée le dossier warehouse et retourne le chemin metadata.duckdb."""
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    return METADATA_PATH


def _ensure_players_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Crée la table players si elle n'existe pas."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            xuid VARCHAR PRIMARY KEY,
            gamertag VARCHAR NOT NULL,
            service_tag VARCHAR,
            emblem_path VARCHAR,
            backdrop_path VARCHAR,
            career_rank INTEGER DEFAULT 0,
            last_seen_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_players_gamertag ON players(gamertag)")


def _load_from_profiles(profiles_path: Path) -> list[tuple[str, str]]:
    """Charge (xuid, gamertag) depuis db_profiles.json."""
    if not profiles_path.exists():
        logger.warning("db_profiles.json introuvable")
        return []

    with open(profiles_path, encoding="utf-8") as f:
        data = json.load(f)

    profiles = data.get("profiles") or {}
    result = []
    for gamertag, profile in profiles.items():
        xuid = profile.get("xuid") if isinstance(profile, dict) else None
        if xuid and str(xuid).strip():
            result.append((str(xuid).strip(), str(gamertag).strip()))
    return result


def _load_encountered_players() -> list[tuple[str, str]]:
    """Collecte (xuid, gamertag) depuis xuid_aliases de chaque stats.duckdb."""
    if not PLAYERS_DIR.exists():
        return []

    result: dict[str, str] = {}
    for player_dir in PLAYERS_DIR.iterdir():
        if not player_dir.is_dir():
            continue
        db_path = player_dir / "stats.duckdb"
        if not db_path.exists():
            continue

        try:
            conn = duckdb.connect(str(db_path), read_only=True)
            try:
                tables = conn.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_name = 'xuid_aliases'"
                ).fetchall()
                if not tables:
                    continue

                rows = conn.execute(
                    "SELECT xuid, gamertag FROM xuid_aliases WHERE xuid IS NOT NULL AND gamertag IS NOT NULL AND gamertag != ''"
                ).fetchall()

                for xuid, gamertag in rows:
                    xu = str(xuid or "").strip()
                    gt = str(gamertag or "").strip()
                    if (
                        xu
                        and gt
                        and xu.isdigit()
                        and len(xu) >= 10
                        and (xu not in result or len(gt) > len(result.get(xu, "")))
                    ):
                        result[xu] = gt
            finally:
                conn.close()
        except Exception as e:
            logger.warning("Erreur lecture %s: %s", db_path.name, e)

    return list(result.items())


def populate(dry_run: bool = False) -> dict:
    """Peuple la table players. Retourne les stats."""
    stats = {"from_profiles": 0, "from_encountered": 0, "inserted": 0, "updated": 0}

    # 1. Charger les données
    from_profiles = _load_from_profiles(DB_PROFILES_PATH)
    from_encountered = _load_encountered_players()

    stats["from_profiles"] = len(from_profiles)
    stats["from_encountered"] = len(from_encountered)

    merged: dict[str, str] = {}
    for xuid, gamertag in from_profiles:
        merged[xuid] = gamertag
    for xuid, gamertag in from_encountered:
        if xuid not in merged or (gamertag and len(gamertag) > len(merged.get(xuid, ""))):
            merged[xuid] = gamertag

    logger.info(
        "Profils: %d, Rencontres: %d, Total distinct: %d",
        stats["from_profiles"],
        stats["from_encountered"],
        len(merged),
    )

    if dry_run:
        logger.info("[DRY-RUN] %d joueurs à insérer/mettre à jour", len(merged))
        return stats

    # 2. Écrire dans metadata.duckdb
    meta_path = _ensure_metadata_db()
    conn = duckdb.connect(str(meta_path))

    try:
        _ensure_players_table(conn)

        for xuid, gamertag in merged.items():
            try:
                existing = conn.execute(
                    "SELECT gamertag FROM players WHERE xuid = ?", [xuid]
                ).fetchone()

                if not existing:
                    conn.execute(
                        """
                        INSERT INTO players (xuid, gamertag, last_seen_at, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        [xuid, gamertag],
                    )
                    stats["inserted"] += 1
                else:
                    conn.execute(
                        """
                        UPDATE players SET gamertag = ?, last_seen_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                        WHERE xuid = ?
                        """,
                        [gamertag, xuid],
                    )
                    stats["updated"] += 1
            except Exception as e:
                logger.warning("Erreur insert/update %s: %s", xuid, e)

    finally:
        conn.close()

    logger.info("Insérés: %d, Mis à jour: %d", stats["inserted"], stats["updated"])
    return stats


def main():
    parser = argparse.ArgumentParser(description="Peuple la table players de metadata.duckdb")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Afficher sans modifier")
    args = parser.parse_args()

    populate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
