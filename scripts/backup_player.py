#!/usr/bin/env python3
"""Script de backup des données joueur vers Parquet compressé.

Exporte les données DuckDB d'un joueur vers des fichiers Parquet
avec compression Zstd optimale pour archivage et partage.

Usage:
    python scripts/backup_player.py --gamertag Chocoboflor
    python scripts/backup_player.py --gamertag Chocoboflor --output ./backups
    python scripts/backup_player.py --all --compression-level 9
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_player_db_path(gamertag: str) -> Path | None:
    """Retourne le chemin vers la DB DuckDB d'un joueur."""
    db_path = REPO_ROOT / "data" / "players" / gamertag / "stats.duckdb"
    return db_path if db_path.exists() else None


def list_all_players() -> list[str]:
    """Liste tous les joueurs ayant une DB DuckDB."""
    players_dir = REPO_ROOT / "data" / "players"
    if not players_dir.exists():
        return []

    players = []
    for player_dir in players_dir.iterdir():
        if player_dir.is_dir() and (player_dir / "stats.duckdb").exists():
            players.append(player_dir.name)
    return sorted(players)


def backup_player(
    gamertag: str,
    output_dir: Path,
    *,
    compression_level: int = 9,
    include_metadata: bool = True,
) -> tuple[bool, str, dict]:
    """Sauvegarde les données d'un joueur vers Parquet compressé.

    Args:
        gamertag: Gamertag du joueur.
        output_dir: Répertoire de sortie.
        compression_level: Niveau de compression Zstd (1-22, 9 recommandé).
        include_metadata: Inclure un fichier de métadonnées JSON.

    Returns:
        Tuple (success, message, stats).
    """
    import duckdb

    db_path = get_player_db_path(gamertag)
    if not db_path:
        return False, f"DB non trouvée pour {gamertag}", {}

    # Créer le répertoire de sortie
    backup_dir = output_dir / gamertag
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stats = {"tables": {}, "total_bytes": 0, "compression_level": compression_level}

    try:
        conn = duckdb.connect(str(db_path), read_only=True)

        # Lister les tables à exporter
        tables_result = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_type = 'BASE TABLE'"
        ).fetchall()
        tables = [t[0] for t in tables_result]

        logger.info(f"Backup de {gamertag}: {len(tables)} tables trouvées")

        for table_name in tables:
            # Compter les lignes
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

            if row_count == 0:
                logger.info(f"  {table_name}: vide, skip")
                continue

            # Exporter vers Parquet avec compression Zstd
            output_file = backup_dir / f"{table_name}_{timestamp}.parquet"
            conn.execute(
                f"""
                COPY {table_name} TO '{output_file}'
                (FORMAT PARQUET, COMPRESSION 'zstd', COMPRESSION_LEVEL {compression_level})
                """
            )

            # Stats
            file_size = output_file.stat().st_size
            stats["tables"][table_name] = {
                "rows": row_count,
                "file_size_bytes": file_size,
                "file": str(output_file.name),
            }
            stats["total_bytes"] += file_size

            size_mb = file_size / (1024 * 1024)
            logger.info(f"  {table_name}: {row_count} lignes, {size_mb:.2f} MB")

        conn.close()

        # Métadonnées JSON
        if include_metadata:
            metadata = {
                "gamertag": gamertag,
                "backup_timestamp": timestamp,
                "backup_datetime": datetime.now().isoformat(),
                "source_db": str(db_path),
                "compression": "zstd",
                "compression_level": compression_level,
                "tables": stats["tables"],
                "total_size_bytes": stats["total_bytes"],
                "total_size_mb": round(stats["total_bytes"] / (1024 * 1024), 2),
            }

            metadata_file = backup_dir / f"backup_metadata_{timestamp}.json"
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            logger.info(f"  Métadonnées: {metadata_file.name}")

        total_mb = stats["total_bytes"] / (1024 * 1024)
        msg = f"Backup {gamertag}: {len(stats['tables'])} tables, {total_mb:.2f} MB total"
        logger.info(msg)

        return True, msg, stats

    except Exception as e:
        msg = f"Erreur backup {gamertag}: {e}"
        logger.error(msg)
        return False, msg, stats


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Backup des données joueur vers Parquet compressé (Zstd)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python scripts/backup_player.py --gamertag Chocoboflor
  python scripts/backup_player.py --gamertag JGtm --output ./backups
  python scripts/backup_player.py --all
  python scripts/backup_player.py --all --compression-level 15

Niveaux de compression Zstd:
  1-3   : Rapide, compression faible
  6-9   : Équilibré (recommandé, défaut: 9)
  15-19 : Lent, compression élevée
  20-22 : Très lent, compression maximale
        """,
    )

    parser.add_argument(
        "--gamertag",
        "-g",
        type=str,
        help="Gamertag du joueur à sauvegarder",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Sauvegarder tous les joueurs",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Répertoire de sortie (défaut: data/backups)",
    )
    parser.add_argument(
        "--compression-level",
        "-c",
        type=int,
        default=9,
        help="Niveau de compression Zstd (1-22, défaut: 9)",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Ne pas inclure le fichier de métadonnées JSON",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="Lister les joueurs disponibles et quitter",
    )

    args = parser.parse_args()

    # Lister les joueurs
    if args.list:
        players = list_all_players()
        if players:
            logger.info("Joueurs disponibles:")
            for p in players:
                db_path = get_player_db_path(p)
                if db_path:
                    size_mb = db_path.stat().st_size / (1024 * 1024)
                    logger.info(f"  - {p} ({size_mb:.1f} MB)")
        else:
            logger.info("Aucun joueur avec DB DuckDB trouvé")
        return 0

    # Validation des arguments
    if not args.gamertag and not args.all:
        parser.error("--gamertag ou --all requis")

    # Répertoire de sortie
    output_dir = Path(args.output) if args.output else REPO_ROOT / "data" / "backups"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Valider le niveau de compression
    compression_level = max(1, min(22, args.compression_level))

    # Liste des joueurs à traiter
    if args.all:
        gamertags = list_all_players()
        if not gamertags:
            logger.error("Aucun joueur trouvé")
            return 1
    else:
        gamertags = [args.gamertag]

    # Traitement
    success_count = 0
    error_count = 0
    total_size = 0

    for gamertag in gamertags:
        ok, msg, stats = backup_player(
            gamertag,
            output_dir,
            compression_level=compression_level,
            include_metadata=not args.no_metadata,
        )
        if ok:
            success_count += 1
            total_size += stats.get("total_bytes", 0)
        else:
            error_count += 1

    # Résumé
    total_mb = total_size / (1024 * 1024)
    logger.info("=" * 50)
    logger.info(f"Backup terminé: {success_count} réussi(s), {error_count} erreur(s)")
    logger.info(f"Taille totale: {total_mb:.2f} MB")
    logger.info(f"Sortie: {output_dir}")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
