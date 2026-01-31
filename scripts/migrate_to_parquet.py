#!/usr/bin/env python3
"""
Script de migration des données legacy vers Parquet.
(Migration script from legacy to Parquet)

HOW IT WORKS:
1. Lit les matchs depuis le système legacy (SQLite avec JSON)
2. Valide et transforme les données avec Pydantic
3. Écrit les données en fichiers Parquet partitionnés
4. Met à jour les métadonnées de synchronisation

Usage:
    python scripts/migrate_to_parquet.py --db data/player.db --xuid 1234567890
    
    # Avec warehouse personnalisé
    python scripts/migrate_to_parquet.py --db data/player.db --xuid 1234567890 --warehouse data/warehouse
    
    # Mode dry-run (sans écriture)
    python scripts/migrate_to_parquet.py --db data/player.db --xuid 1234567890 --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.repositories.shadow import ShadowRepository, ShadowMode


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Point d'entrée principal. (Main entry point)"""
    parser = argparse.ArgumentParser(
        description="Migre les données legacy vers Parquet",
    )
    parser.add_argument(
        "--db",
        required=True,
        help="Chemin vers la base de données SQLite legacy",
    )
    parser.add_argument(
        "--xuid",
        required=True,
        help="XUID du joueur à migrer",
    )
    parser.add_argument(
        "--warehouse",
        default=None,
        help="Chemin vers le warehouse (défaut: à côté de la DB)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche ce qui serait fait sans écrire",
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
    
    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"Base de données non trouvée: {db_path}")
        return 1
    
    logger.info(f"Début de la migration pour XUID: {args.xuid}")
    logger.info(f"Source: {db_path}")
    
    # Créer le repository shadow
    shadow = ShadowRepository(
        str(db_path),
        args.xuid,
        warehouse_path=args.warehouse,
        mode=ShadowMode.SHADOW_READ,
    )
    
    # Vérifier l'état initial
    progress = shadow.get_migration_progress()
    logger.info(f"État initial:")
    logger.info(f"  - Matchs legacy: {progress['legacy_count']}")
    logger.info(f"  - Matchs Parquet: {progress['hybrid_count']}")
    logger.info(f"  - Progression: {progress['progress_percent']}%")
    
    if progress["is_complete"]:
        logger.info("Migration déjà complète!")
        return 0
    
    if args.dry_run:
        logger.info("[DRY-RUN] Aucune écriture effectuée")
        return 0
    
    # Effectuer la migration
    def progress_callback(current: int, total: int) -> None:
        logger.info(f"  Progression: {current}/{total} ({current/total*100:.1f}%)")
    
    logger.info("Démarrage de la migration...")
    result = shadow.migrate_matches_to_parquet(
        progress_callback=progress_callback,
    )
    
    logger.info(f"Migration terminée:")
    logger.info(f"  - Lignes écrites: {result['rows_written']}")
    logger.info(f"  - Erreurs: {result['errors']}")
    logger.info(f"  - Total legacy: {result['total_legacy']}")
    
    # Vérifier l'état final
    final_progress = shadow.get_migration_progress()
    logger.info(f"État final:")
    logger.info(f"  - Matchs Parquet: {final_progress['hybrid_count']}")
    logger.info(f"  - Progression: {final_progress['progress_percent']}%")
    logger.info(f"  - Complète: {final_progress['is_complete']}")
    
    shadow.close()
    
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
