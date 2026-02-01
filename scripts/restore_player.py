#!/usr/bin/env python3
"""Script de restauration des données joueur depuis Parquet.

Restaure les données d'un backup Parquet vers une DB DuckDB.
Supporte la restauration complète ou sélective.

Usage:
    python scripts/restore_player.py --gamertag Chocoboflor --backup ./backups/Chocoboflor
    python scripts/restore_player.py --gamertag JGtm --backup ./backups/JGtm --tables match_stats,medals_earned
    python scripts/restore_player.py --gamertag Chocoboflor --backup ./backups/Chocoboflor --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
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


def get_player_db_path(gamertag: str, create_parent: bool = False) -> Path:
    """Retourne le chemin vers la DB DuckDB d'un joueur."""
    db_path = REPO_ROOT / "data" / "players" / gamertag / "stats.duckdb"
    if create_parent:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def find_latest_backup(backup_dir: Path) -> tuple[Path | None, dict | None]:
    """Trouve le backup le plus récent dans un répertoire.

    Args:
        backup_dir: Répertoire contenant les fichiers de backup.

    Returns:
        Tuple (chemin du backup, métadonnées ou None).
    """
    if not backup_dir.exists():
        return None, None

    # Chercher les fichiers de métadonnées
    metadata_files = sorted(backup_dir.glob("backup_metadata_*.json"), reverse=True)

    if metadata_files:
        latest = metadata_files[0]
        with open(latest, encoding="utf-8") as f:
            metadata = json.load(f)
        return backup_dir, metadata

    # Pas de métadonnées, chercher les fichiers Parquet
    parquet_files = list(backup_dir.glob("*.parquet"))
    if parquet_files:
        return backup_dir, None

    return None, None


def list_backup_tables(backup_dir: Path) -> list[tuple[str, str, int]]:
    """Liste les tables disponibles dans un backup.

    Args:
        backup_dir: Répertoire de backup.

    Returns:
        Liste de tuples (nom_table, fichier_parquet, taille_bytes).
    """
    tables = []

    for parquet_file in backup_dir.glob("*.parquet"):
        # Extraire le nom de la table (format: tablename_timestamp.parquet)
        name = parquet_file.stem
        # Retirer le timestamp si présent
        parts = name.rsplit("_", 2)
        if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 6:
            # Format: tablename_YYYYMMDD_HHMMSS
            table_name = "_".join(parts[:-2]) if len(parts) > 2 else parts[0]
        elif len(parts) == 2 and parts[-1].isdigit():
            table_name = parts[0]
        else:
            table_name = name

        tables.append((table_name, parquet_file.name, parquet_file.stat().st_size))

    return sorted(tables, key=lambda x: x[0])


def restore_player(
    gamertag: str,
    backup_dir: Path,
    *,
    tables: list[str] | None = None,
    replace: bool = False,
    dry_run: bool = False,
) -> tuple[bool, str, dict]:
    """Restaure les données d'un joueur depuis un backup Parquet.

    Args:
        gamertag: Gamertag du joueur.
        backup_dir: Répertoire contenant les fichiers de backup.
        tables: Liste des tables à restaurer (None = toutes).
        replace: Si True, remplace les données existantes.
        dry_run: Si True, simule sans écrire.

    Returns:
        Tuple (success, message, stats).
    """
    import duckdb

    backup_path, metadata = find_latest_backup(backup_dir)
    if not backup_path:
        return False, f"Backup non trouvé dans {backup_dir}", {}

    # Lister les tables disponibles
    available_tables = list_backup_tables(backup_path)
    if not available_tables:
        return False, f"Aucun fichier Parquet trouvé dans {backup_dir}", {}

    logger.info(f"Backup trouvé: {len(available_tables)} tables")
    if metadata:
        logger.info(f"  Créé le: {metadata.get('backup_datetime', 'inconnu')}")
        logger.info(f"  Source: {metadata.get('source_db', 'inconnue')}")

    # Filtrer les tables si spécifié
    if tables:
        tables_lower = {t.lower() for t in tables}
        available_tables = [t for t in available_tables if t[0].lower() in tables_lower]
        if not available_tables:
            return False, f"Tables spécifiées non trouvées: {tables}", {}

    stats = {"tables_restored": {}, "total_rows": 0}

    if dry_run:
        logger.info("=== MODE DRY-RUN (simulation) ===")

    # Chemin de la DB destination
    db_path = get_player_db_path(gamertag, create_parent=True)

    if dry_run:
        logger.info(f"Destination: {db_path}")
        for table_name, _parquet_file, size in available_tables:
            size_mb = size / (1024 * 1024)
            logger.info(f"  Restaurerait: {table_name} ({size_mb:.2f} MB)")
        return True, f"Dry-run: {len(available_tables)} tables seraient restaurées", stats

    try:
        # Connexion à la DB (création si nécessaire)
        conn = duckdb.connect(str(db_path), read_only=False)

        for table_name, parquet_file, _size in available_tables:
            parquet_path = backup_path / parquet_file

            # Lire le schéma du Parquet
            temp_result = conn.execute(f"SELECT * FROM read_parquet('{parquet_path}') LIMIT 0")
            columns = [desc[0] for desc in temp_result.description]

            # Compter les lignes
            row_count = conn.execute(
                f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')"
            ).fetchone()[0]

            if replace:
                # Supprimer la table existante si elle existe
                conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                logger.info(f"  {table_name}: table existante supprimée")

            # Créer la table depuis le Parquet
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {table_name} AS "
                f"SELECT * FROM read_parquet('{parquet_path}')"
            )

            stats["tables_restored"][table_name] = {
                "rows": row_count,
                "columns": columns,
            }
            stats["total_rows"] += row_count

            logger.info(f"  {table_name}: {row_count} lignes restaurées")

        conn.close()

        msg = (
            f"Restauration {gamertag}: "
            f"{len(stats['tables_restored'])} tables, "
            f"{stats['total_rows']} lignes total"
        )
        logger.info(msg)
        return True, msg, stats

    except Exception as e:
        msg = f"Erreur restauration {gamertag}: {e}"
        logger.error(msg)
        return False, msg, stats


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Restauration des données joueur depuis Parquet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python scripts/restore_player.py --gamertag Chocoboflor --backup ./data/backups/Chocoboflor
  python scripts/restore_player.py --gamertag JGtm --backup ./backups/JGtm --dry-run
  python scripts/restore_player.py --gamertag JGtm --backup ./backups/JGtm --tables match_stats,medals_earned
  python scripts/restore_player.py --gamertag JGtm --backup ./backups/JGtm --replace

Notes:
  - Par défaut, si la table existe déjà, les données sont ajoutées (pas de remplacement)
  - Utilisez --replace pour remplacer complètement les tables existantes
  - Utilisez --dry-run pour simuler sans modifier les données
        """,
    )

    parser.add_argument(
        "--gamertag",
        "-g",
        type=str,
        required=True,
        help="Gamertag du joueur à restaurer",
    )
    parser.add_argument(
        "--backup",
        "-b",
        type=str,
        required=True,
        help="Répertoire contenant le backup Parquet",
    )
    parser.add_argument(
        "--tables",
        "-t",
        type=str,
        default=None,
        help="Tables à restaurer (séparées par des virgules)",
    )
    parser.add_argument(
        "--replace",
        "-r",
        action="store_true",
        help="Remplacer les tables existantes (au lieu d'ajouter)",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Simuler sans écrire",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="Lister les tables disponibles dans le backup et quitter",
    )

    args = parser.parse_args()

    backup_dir = Path(args.backup)

    # Lister les tables
    if args.list:
        tables = list_backup_tables(backup_dir)
        if tables:
            logger.info(f"Tables disponibles dans {backup_dir}:")
            total_size = 0
            for table_name, parquet_file, size in tables:
                size_mb = size / (1024 * 1024)
                total_size += size
                logger.info(f"  - {table_name}: {parquet_file} ({size_mb:.2f} MB)")
            logger.info(f"Total: {total_size / (1024 * 1024):.2f} MB")
        else:
            logger.info(f"Aucune table trouvée dans {backup_dir}")
        return 0

    # Parser les tables si spécifié
    tables = None
    if args.tables:
        tables = [t.strip() for t in args.tables.split(",") if t.strip()]

    # Restauration
    ok, msg, stats = restore_player(
        args.gamertag,
        backup_dir,
        tables=tables,
        replace=args.replace,
        dry_run=args.dry_run,
    )

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
