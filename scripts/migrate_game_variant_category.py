#!/usr/bin/env python3
"""Migration pour ajouter la colonne game_variant_category à match_stats.

Sprint 8.3 - Ce script :
1. Ajoute la colonne game_variant_category (INTEGER) à match_stats si manquante
2. Optionnellement, re-calcule les valeurs depuis les données existantes

Note: game_variant_category est extrait de l'API lors de la sync.
Les matchs existants n'auront pas cette valeur (NULL) car elle n'était pas
extraite avant.

Usage:
    # Migrer un joueur
    python scripts/migrate_game_variant_category.py --gamertag MonGT

    # Migrer tous les joueurs
    python scripts/migrate_game_variant_category.py --all

    # Dry-run
    python scripts/migrate_game_variant_category.py --all --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Colonnes à ajouter à match_stats (Sprint 8)
COLUMNS_TO_ADD = [
    ("game_variant_category", "INTEGER", None),
    # Ajoutez d'autres colonnes si nécessaire
]


def get_existing_columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    """Retourne les noms des colonnes existantes d'une table."""
    try:
        result = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
        return {row[1].lower() for row in result}
    except Exception:
        return set()


def migrate_player_db(
    db_path: Path,
    *,
    dry_run: bool = False,
) -> dict:
    """Migre une base joueur.

    Args:
        db_path: Chemin vers stats.duckdb du joueur.
        dry_run: Si True, ne modifie pas la DB.

    Returns:
        Dict avec statistiques.
    """
    logger.info(f"Traitement de {db_path}")

    stats = {
        "db_path": str(db_path),
        "columns_added": 0,
        "errors": [],
    }

    if not db_path.exists():
        stats["errors"].append(f"Base non trouvée: {db_path}")
        return stats

    conn = duckdb.connect(str(db_path), read_only=dry_run)

    try:
        # Vérifier si la table match_stats existe
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='match_stats'"
        ).fetchall()

        if not tables:
            logger.warning("  Table match_stats non trouvée")
            stats["errors"].append("Table match_stats non trouvée")
            return stats

        # Récupérer les colonnes existantes
        existing_cols = get_existing_columns(conn, "match_stats")
        logger.info(f"  Colonnes existantes: {len(existing_cols)}")

        # Ajouter les colonnes manquantes
        for col_name, col_type, default_val in COLUMNS_TO_ADD:
            if col_name.lower() in existing_cols:
                logger.debug(f"  Colonne {col_name} existe déjà")
                continue

            if dry_run:
                logger.info(f"  [DRY-RUN] Ajouterait colonne {col_name} ({col_type})")
                stats["columns_added"] += 1
            else:
                try:
                    # Construire la requête ALTER TABLE
                    default_clause = f" DEFAULT {default_val}" if default_val is not None else ""
                    sql = (
                        f"ALTER TABLE match_stats ADD COLUMN {col_name} {col_type}{default_clause}"
                    )
                    conn.execute(sql)
                    logger.info(f"  Colonne {col_name} ajoutée")
                    stats["columns_added"] += 1
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.debug(f"  Colonne {col_name} existe déjà")
                    else:
                        stats["errors"].append(f"Colonne {col_name}: {e}")
                        logger.error(f"  Erreur ajout {col_name}: {e}")

        # Commit
        if not dry_run and stats["columns_added"] > 0:
            conn.commit()
            logger.info(f"  Migration terminée: {stats['columns_added']} colonnes ajoutées")

    except Exception as e:
        stats["errors"].append(str(e))
        logger.error(f"  Erreur: {e}")

    finally:
        conn.close()

    return stats


def find_all_player_dbs() -> list[Path]:
    """Trouve toutes les bases joueurs dans data/players/."""
    data_dir = Path(__file__).parent.parent / "data" / "players"
    if not data_dir.exists():
        return []

    dbs = []
    for player_dir in data_dir.iterdir():
        if player_dir.is_dir():
            db_path = player_dir / "stats.duckdb"
            if db_path.exists():
                dbs.append(db_path)

    return dbs


def main():
    parser = argparse.ArgumentParser(
        description="Migration pour ajouter game_variant_category à match_stats"
    )
    parser.add_argument(
        "--gamertag",
        "-g",
        help="Gamertag du joueur (dossier dans data/players/)",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Traiter tous les joueurs",
    )
    parser.add_argument(
        "--db-path",
        "-d",
        help="Chemin direct vers stats.duckdb",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulation sans modification",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Mode verbeux",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Déterminer les bases à traiter
    db_paths: list[Path] = []

    if args.db_path:
        db_paths.append(Path(args.db_path))
    elif args.gamertag:
        db_path = Path(__file__).parent.parent / "data" / "players" / args.gamertag / "stats.duckdb"
        db_paths.append(db_path)
    elif args.all:
        db_paths = find_all_player_dbs()
    else:
        parser.error("Spécifiez --gamertag, --all, ou --db-path")

    if not db_paths:
        logger.error("Aucune base de données trouvée")
        sys.exit(1)

    logger.info(f"Traitement de {len(db_paths)} base(s) de données")
    if args.dry_run:
        logger.info("Mode DRY-RUN activé (aucune modification)")

    # Statistiques globales
    total_stats = {
        "databases": len(db_paths),
        "columns_added": 0,
        "errors": [],
    }

    # Traiter chaque base
    for db_path in db_paths:
        stats = migrate_player_db(db_path, dry_run=args.dry_run)
        total_stats["columns_added"] += stats["columns_added"]
        total_stats["errors"].extend(stats["errors"])

    # Résumé final
    logger.info("=" * 60)
    logger.info("RÉSUMÉ MIGRATION GAME_VARIANT_CATEGORY")
    logger.info("=" * 60)
    logger.info(f"Bases traitées     : {total_stats['databases']}")
    logger.info(f"Colonnes ajoutées  : {total_stats['columns_added']}")
    if total_stats["errors"]:
        logger.warning(f"Erreurs            : {len(total_stats['errors'])}")
        for err in total_stats["errors"][:5]:
            logger.warning(f"  - {err}")

    if args.dry_run:
        logger.info("\n[DRY-RUN] Aucune donnée n'a été modifiée")


if __name__ == "__main__":
    main()
