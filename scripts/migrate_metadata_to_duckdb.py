#!/usr/bin/env python3
"""
Script de migration des métadonnées SQLite vers DuckDB.

Ce script migre metadata.db (SQLite) vers metadata.duckdb (DuckDB)
et ajoute la nouvelle table career_ranks depuis le JSON.

Usage:
    python scripts/migrate_metadata_to_duckdb.py
    python scripts/migrate_metadata_to_duckdb.py --dry-run
    python scripts/migrate_metadata_to_duckdb.py --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
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
WAREHOUSE_DIR = DATA_DIR / "warehouse"
SQLITE_PATH = WAREHOUSE_DIR / "metadata.db"
DUCKDB_PATH = WAREHOUSE_DIR / "metadata.duckdb"
CAREER_RANKS_JSON = DATA_DIR / "cache" / "career_ranks_metadata.json"


def load_career_ranks(json_path: Path) -> list[dict[str, Any]]:
    """Charge et transforme les rangs de carrière depuis le JSON."""
    if not json_path.exists():
        logger.warning(f"Fichier career_ranks non trouvé: {json_path}")
        return []

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    ranks = []
    for rank_data in data.get("Ranks", []):
        rank = {
            "rank_id": rank_data.get("Rank", 0),
            "tier_name_en": rank_data.get("RankTitle", {}).get("value", ""),
            "tier_name_fr": rank_data.get("RankTitle", {}).get(
                "value", ""
            ),  # TODO: ajouter traductions FR
            "tier_type": rank_data.get("TierType", ""),
            "grade": rank_data.get("RankGrade", 1),
            "xp_required": rank_data.get("XpRequiredForRank", 0),
            "sprite_path": rank_data.get("RankIcon", ""),
        }
        ranks.append(rank)

    return ranks


def migrate_metadata(dry_run: bool = False, verbose: bool = False) -> dict[str, Any]:
    """
    Migre les métadonnées de SQLite vers DuckDB.

    Returns:
        dict avec les statistiques de migration
    """
    results = {
        "success": False,
        "tables_migrated": [],
        "rows_per_table": {},
        "career_ranks_count": 0,
        "errors": [],
    }

    # Vérifier que le fichier source existe
    if not SQLITE_PATH.exists():
        results["errors"].append(f"Fichier source non trouvé: {SQLITE_PATH}")
        logger.error(results["errors"][-1])
        return results

    # Backup de l'ancien fichier DuckDB si existant
    if DUCKDB_PATH.exists():
        backup_path = DUCKDB_PATH.with_suffix(".duckdb.bak")
        if not dry_run:
            import shutil

            shutil.copy2(DUCKDB_PATH, backup_path)
            logger.info(f"Backup créé: {backup_path}")

    try:
        # Connexion DuckDB
        if dry_run:
            conn = duckdb.connect(":memory:")
            logger.info("[DRY-RUN] Utilisation d'une base en mémoire")
        else:
            # Supprimer l'ancien fichier pour repartir de zéro
            if DUCKDB_PATH.exists():
                DUCKDB_PATH.unlink()
            conn = duckdb.connect(str(DUCKDB_PATH))
            logger.info(f"Création de: {DUCKDB_PATH}")

        # Attacher la base SQLite source
        conn.execute(f"ATTACH '{SQLITE_PATH}' AS legacy (TYPE SQLITE, READ_ONLY)")
        logger.info(f"Source SQLite attachée: {SQLITE_PATH}")

        # Liste des tables à migrer (avec données)
        tables_to_migrate = [
            "playlists",
            "game_modes",
            "categories",
            "medal_definitions",
            "players",
            "maps",
            "game_variants",
            "friends",
            "sessions",
            "sync_meta",
            "migration_meta",
        ]

        for table in tables_to_migrate:
            try:
                # Vérifier si la table existe dans la source
                check = conn.execute(f"SELECT COUNT(*) FROM legacy.{table}").fetchone()
                row_count = check[0] if check else 0

                # Créer la table dans DuckDB avec les données
                conn.execute(f"CREATE TABLE {table} AS SELECT * FROM legacy.{table}")

                results["tables_migrated"].append(table)
                results["rows_per_table"][table] = row_count
                logger.info(f"  ✓ {table}: {row_count} lignes")

            except Exception as e:
                error_msg = f"Erreur migration {table}: {e}"
                results["errors"].append(error_msg)
                if verbose:
                    logger.warning(error_msg)

        # Détacher la source
        conn.execute("DETACH legacy")

        # Créer la table career_ranks
        logger.info("Création de la table career_ranks...")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS career_ranks (
                rank_id INTEGER PRIMARY KEY,
                tier_name_en VARCHAR,
                tier_name_fr VARCHAR,
                tier_type VARCHAR,
                grade INTEGER,
                xp_required INTEGER,
                sprite_path VARCHAR
            )
        """)

        # Charger les données career_ranks
        career_ranks = load_career_ranks(CAREER_RANKS_JSON)
        if career_ranks:
            for rank in career_ranks:
                conn.execute(
                    """
                    INSERT INTO career_ranks
                    (rank_id, tier_name_en, tier_name_fr, tier_type, grade, xp_required, sprite_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    [
                        rank["rank_id"],
                        rank["tier_name_en"],
                        rank["tier_name_fr"],
                        rank["tier_type"],
                        rank["grade"],
                        rank["xp_required"],
                        rank["sprite_path"],
                    ],
                )
            results["career_ranks_count"] = len(career_ranks)
            logger.info(f"  ✓ career_ranks: {len(career_ranks)} lignes")
        else:
            logger.warning("  ⚠ career_ranks: 0 lignes (fichier JSON non trouvé)")

        # Créer les index
        logger.info("Création des index...")
        try:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_game_modes_category ON game_modes(category)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_medal_definitions_name ON medal_definitions(name_id)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_players_gamertag ON players(gamertag)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_career_ranks_tier ON career_ranks(tier_type)"
            )
            logger.info("  ✓ Index créés")
        except Exception as e:
            logger.warning(f"  ⚠ Erreur création index: {e}")

        # Validation finale
        logger.info("Validation finale...")
        validation_ok = True
        for table in results["tables_migrated"] + ["career_ranks"]:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                expected = results["rows_per_table"].get(table, results["career_ranks_count"])
                if table == "career_ranks":
                    expected = results["career_ranks_count"]
                if count != expected and expected > 0:
                    logger.warning(f"  ⚠ {table}: attendu {expected}, obtenu {count}")
                    validation_ok = False
                elif verbose:
                    logger.info(f"  ✓ {table}: {count} lignes validées")
            except Exception as e:
                logger.warning(f"  ⚠ Erreur validation {table}: {e}")
                validation_ok = False

        conn.close()

        if validation_ok:
            results["success"] = True
            logger.info("Migration terminée avec succès!")
        else:
            logger.warning("Migration terminée avec des avertissements")

    except Exception as e:
        results["errors"].append(f"Erreur fatale: {e}")
        logger.error(f"Erreur fatale: {e}")
        import traceback

        if verbose:
            traceback.print_exc()

    return results


def print_summary(results: dict[str, Any]) -> None:
    """Affiche un résumé de la migration."""
    print("\n" + "=" * 50)
    print("RESUME DE LA MIGRATION")
    print("=" * 50)

    print(f"\nStatut: {'[OK] SUCCES' if results['success'] else '[X] ECHEC'}")
    print(f"Tables migrées: {len(results['tables_migrated'])}")

    total_rows = sum(results["rows_per_table"].values()) + results["career_ranks_count"]
    print(f"Lignes totales: {total_rows}")

    print("\nDétail par table:")
    for table, count in results["rows_per_table"].items():
        print(f"  - {table}: {count}")
    if results["career_ranks_count"] > 0:
        print(f"  - career_ranks: {results['career_ranks_count']} (nouvelle)")

    if results["errors"]:
        print(f"\nErreurs ({len(results['errors'])}):")
        for error in results["errors"]:
            print(f"  - {error}")

    print("\n" + "=" * 50)


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Migre les métadonnées de SQLite vers DuckDB",
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

    logger.info("=" * 50)
    logger.info("Migration metadata.db → metadata.duckdb")
    logger.info("=" * 50)
    logger.info(f"Source: {SQLITE_PATH}")
    logger.info(f"Destination: {DUCKDB_PATH}")
    logger.info(f"Career Ranks: {CAREER_RANKS_JSON}")

    if args.dry_run:
        logger.info("[DRY-RUN] Aucune modification ne sera effectuée")

    results = migrate_metadata(dry_run=args.dry_run, verbose=args.verbose)
    print_summary(results)

    return 0 if results["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
