#!/usr/bin/env python3
"""Résout les XUIDs manquants vers gamertags via l'API SPNKr.

Ce script utilise `client.profile.get_users_by_id()` pour résoudre
les XUIDs qui n'ont pas de gamertag dans xuid_aliases.

Usage:
    # Pour un joueur
    python scripts/resolve_missing_gamertags.py --gamertag Madina97294

    # Pour tous les joueurs
    python scripts/resolve_missing_gamertags.py --all

    # Dry-run (affiche sans modifier)
    python scripts/resolve_missing_gamertags.py --all --dry-run

    # Limiter le nombre de XUIDs à résoudre
    python scripts/resolve_missing_gamertags.py --all --limit 100
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Charger .env.local puis .env si présents
try:
    from dotenv import load_dotenv

    project_root = Path(__file__).resolve().parent.parent
    # .env.local a priorité sur .env
    for env_file in [".env.local", ".env"]:
        env_path = project_root / env_file
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

# Charger secrets.toml si présent
try:
    import tomllib

    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        with open(secrets_path, "rb") as f:
            secrets = tomllib.load(f)
        # Injecter dans l'environnement si pas déjà présent
        for key in [
            "SPNKR_SPARTAN_TOKEN",
            "SPNKR_CLEARANCE_TOKEN",
            "SPNKR_AZURE_CLIENT_ID",
            "SPNKR_AZURE_CLIENT_SECRET",
            "SPNKR_OAUTH_REFRESH_TOKEN",
        ]:
            if key not in os.environ and key in secrets:
                os.environ[key] = str(secrets[key])
except Exception:
    pass

try:
    import duckdb
except ImportError:
    print("Error: duckdb not installed")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PLAYERS_DIR = DATA_DIR / "players"


def is_valid_xuid(xuid: str) -> bool:
    """Vérifie si un XUID est valide (16 chiffres)."""
    if not xuid:
        return False
    # XUID valide = 16-20 chiffres (format Xbox Live)
    return xuid.isdigit() and 10 <= len(xuid) <= 20


def find_missing_xuids(db_path: Path, limit: int | None = None) -> list[str]:
    """Trouve les XUIDs sans gamertag dans xuid_aliases."""
    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        # XUIDs dans match_participants sans alias
        query = """
            SELECT DISTINCT mp.xuid
            FROM match_participants mp
            LEFT JOIN xuid_aliases xa ON mp.xuid = xa.xuid
            WHERE xa.xuid IS NULL
              AND mp.xuid IS NOT NULL
              AND mp.xuid != ''
        """

        result = conn.execute(query).fetchall()
        # Filtrer les XUIDs valides
        valid_xuids = [row[0] for row in result if is_valid_xuid(row[0])]

        if limit:
            return valid_xuids[:limit]
        return valid_xuids
    finally:
        conn.close()


async def resolve_xuids_batch(
    xuids: list[str],
    batch_size: int = 20,  # Réduit pour éviter rate limiting
) -> dict[str, str]:
    """Résout une liste de XUIDs vers gamertags via SPNKr."""
    from src.data.sync.api_client import SPNKrAPIClient

    resolved: dict[str, str] = {}

    async with SPNKrAPIClient(requests_per_second=1) as api_client:
        client = api_client.client

        # Traiter par batches
        total_batches = (len(xuids) + batch_size - 1) // batch_size
        for i in range(0, len(xuids), batch_size):
            batch = xuids[i : i + batch_size]
            batch_num = (i // batch_size) + 1

            retries = 3
            for attempt in range(retries):
                try:
                    logger.info(f"  Batch {batch_num}/{total_batches}: {len(batch)} XUIDs...")
                    resp = await client.profile.get_users_by_id(batch)

                    # Extraire les données
                    if hasattr(resp, "data"):
                        users = resp.data
                    else:
                        users = await resp.parse()

                    count = 0
                    for user in users:
                        xuid = str(getattr(user, "xuid", "") or "").strip()
                        gamertag = str(getattr(user, "gamertag", "") or "").strip()
                        if xuid and gamertag:
                            resolved[xuid] = gamertag
                            count += 1

                    logger.info(f"    Resolu {count} gamertags")
                    break  # Succès, sortir de la boucle retry

                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str and attempt < retries - 1:
                        wait_time = 10 * (attempt + 1)  # 10s, 20s, 30s
                        logger.warning(f"    Rate limited, attente {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning(f"    Erreur batch {batch_num}: {e}")
                        break

            # Pause entre batches (2 secondes)
            await asyncio.sleep(2)

    return resolved


def insert_aliases(db_path: Path, aliases: dict[str, str], dry_run: bool = False) -> int:
    """Insère les aliases résolus dans DuckDB."""
    if dry_run or not aliases:
        return len(aliases)

    conn = duckdb.connect(str(db_path))
    inserted = 0

    try:
        for xuid, gamertag in aliases.items():
            try:
                existing = conn.execute(
                    "SELECT gamertag FROM xuid_aliases WHERE xuid = ?", [xuid]
                ).fetchone()

                if not existing:
                    conn.execute(
                        """
                        INSERT INTO xuid_aliases (xuid, gamertag, source, updated_at)
                        VALUES (?, ?, 'api_resolve', NOW())
                        """,
                        [xuid, gamertag],
                    )
                    inserted += 1
            except Exception:
                pass
    finally:
        conn.close()

    return inserted


def resolve_for_player(
    gamertag: str,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    """Résout les gamertags manquants pour un joueur."""
    result = {
        "gamertag": gamertag,
        "missing_xuids": 0,
        "resolved": 0,
        "inserted": 0,
        "errors": [],
    }

    db_path = PLAYERS_DIR / gamertag / "stats.duckdb"
    if not db_path.exists():
        result["errors"].append(f"DB non trouvée: {db_path}")
        return result

    # Trouver les XUIDs manquants
    missing = find_missing_xuids(db_path, limit=limit)
    result["missing_xuids"] = len(missing)

    if not missing:
        logger.info(f"  Aucun XUID manquant pour {gamertag}")
        return result

    logger.info(f"  {len(missing)} XUIDs sans gamertag")

    if dry_run:
        logger.info(f"  [DRY-RUN] Résolution de {len(missing)} XUIDs...")
        result["resolved"] = len(missing)
        return result

    # Résoudre via API
    try:
        resolved = asyncio.run(resolve_xuids_batch(missing))
        result["resolved"] = len(resolved)
        logger.info(f"  {len(resolved)}/{len(missing)} XUIDs résolus")

        # Insérer dans la DB
        if resolved:
            inserted = insert_aliases(db_path, resolved, dry_run=dry_run)
            result["inserted"] = inserted
            logger.info(f"  {inserted} aliases insérés")

    except Exception as e:
        result["errors"].append(str(e))
        logger.error(f"  Erreur: {e}")

    return result


def find_all_players() -> list[str]:
    """Trouve tous les joueurs avec DuckDB."""
    players = []
    if not PLAYERS_DIR.exists():
        return players

    for player_dir in PLAYERS_DIR.iterdir():
        if player_dir.is_dir() and (player_dir / "stats.duckdb").exists():
            players.append(player_dir.name)

    return sorted(players)


def main():
    parser = argparse.ArgumentParser(
        description="Résout les XUIDs manquants vers gamertags via SPNKr"
    )
    parser.add_argument("--gamertag", "-g", help="Gamertag du joueur")
    parser.add_argument("--all", "-a", action="store_true", help="Tous les joueurs")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Mode simulation")
    parser.add_argument("--limit", "-l", type=int, help="Limiter le nombre de XUIDs")

    args = parser.parse_args()

    if not args.gamertag and not args.all:
        parser.error("Spécifiez --gamertag ou --all")

    # Joueurs à traiter
    if args.all:
        players = find_all_players()
        if not players:
            logger.error("Aucun joueur trouvé")
            return
        logger.info(f"Trouvé {len(players)} joueur(s)")
    else:
        players = [args.gamertag]

    # Traiter chaque joueur
    total_resolved = 0
    total_inserted = 0

    for i, player in enumerate(players, 1):
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"[{i}/{len(players)}] {player}")
        logger.info("=" * 60)

        result = resolve_for_player(
            player,
            dry_run=args.dry_run,
            limit=args.limit,
        )

        total_resolved += result["resolved"]
        total_inserted += result["inserted"]

        for err in result["errors"]:
            logger.error(f"  Erreur: {err}")

    # Résumé
    logger.info("")
    logger.info("=" * 60)
    logger.info("RÉSUMÉ")
    logger.info("=" * 60)
    prefix = "[DRY-RUN] " if args.dry_run else ""
    logger.info(f"{prefix}XUIDs résolus: {total_resolved}")
    logger.info(f"{prefix}Aliases insérés: {total_inserted}")


if __name__ == "__main__":
    main()
