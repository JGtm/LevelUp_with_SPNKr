#!/usr/bin/env python3
"""
Script pour créer et peupler metadata.duckdb depuis Discovery UGC.

Ce script :
1. Crée metadata.duckdb s'il n'existe pas
2. Crée les tables nécessaires (playlists, maps, playlist_map_mode_pairs, game_variants)
3. Récupère les asset IDs uniques depuis les match_stats de tous les joueurs
4. Peuple les tables depuis Discovery UGC API

Usage:
    python scripts/populate_metadata_from_discovery.py
    python scripts/populate_metadata_from_discovery.py --all-players
    python scripts/populate_metadata_from_discovery.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
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

from src.data.sync.api_client import SPNKrAPIClient, get_tokens_from_env

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration des chemins
DATA_DIR = Path(__file__).parent.parent / "data"
WAREHOUSE_DIR = DATA_DIR / "warehouse"
METADATA_DB_PATH = WAREHOUSE_DIR / "metadata.duckdb"
PLAYERS_DIR = DATA_DIR / "players"

# Schéma des tables metadata
METADATA_SCHEMA_DDL = """
-- Table playlists
CREATE TABLE IF NOT EXISTS playlists (
    asset_id VARCHAR NOT NULL,
    version_id VARCHAR NOT NULL,
    public_name VARCHAR,
    description VARCHAR,
    is_ranked BOOLEAN DEFAULT FALSE,
    category VARCHAR,
    raw_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, version_id)
);

-- Table maps
CREATE TABLE IF NOT EXISTS maps (
    asset_id VARCHAR NOT NULL,
    version_id VARCHAR NOT NULL,
    public_name VARCHAR,
    description VARCHAR,
    thumbnail_path VARCHAR,
    raw_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, version_id)
);

-- Table playlist_map_mode_pairs
CREATE TABLE IF NOT EXISTS playlist_map_mode_pairs (
    asset_id VARCHAR NOT NULL,
    version_id VARCHAR NOT NULL,
    public_name VARCHAR,
    description VARCHAR,
    raw_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, version_id)
);

-- Table game_variants
CREATE TABLE IF NOT EXISTS game_variants (
    asset_id VARCHAR NOT NULL,
    version_id VARCHAR NOT NULL,
    public_name VARCHAR,
    description VARCHAR,
    category VARCHAR,
    raw_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, version_id)
);

-- Index pour recherche rapide
CREATE INDEX IF NOT EXISTS idx_playlists_asset_id ON playlists(asset_id);
CREATE INDEX IF NOT EXISTS idx_maps_asset_id ON maps(asset_id);
CREATE INDEX IF NOT EXISTS idx_pairs_asset_id ON playlist_map_mode_pairs(asset_id);
CREATE INDEX IF NOT EXISTS idx_variants_asset_id ON game_variants(asset_id);
"""


def create_metadata_db(conn: duckdb.DuckDBPyConnection) -> None:
    """Crée le schéma metadata.duckdb."""
    logger.info("Création du schéma metadata.duckdb...")
    conn.execute(METADATA_SCHEMA_DDL)
    logger.info("✓ Schéma créé")


def get_unique_asset_ids_from_players(
    all_players: bool = False,
) -> dict[str, set[tuple[str, str]]]:
    """Récupère les asset IDs uniques depuis les match_stats de tous les joueurs.

    Args:
        all_players: Si True, parcourt tous les joueurs. Sinon, seulement le premier trouvé.

    Returns:
        Dict avec les clés 'playlists', 'maps', 'pairs', 'variants' et les sets de (asset_id, version_id).
    """
    assets: dict[str, set[tuple[str, str]]] = {
        "playlists": set(),
        "maps": set(),
        "pairs": set(),
        "variants": set(),
    }

    if not PLAYERS_DIR.exists():
        logger.warning(f"Répertoire players non trouvé: {PLAYERS_DIR}")
        return assets

    # Parcourir les dossiers de joueurs
    player_dirs = list(PLAYERS_DIR.iterdir())
    if not player_dirs:
        logger.warning("Aucun joueur trouvé dans data/players/")
        return assets

    if not all_players:
        player_dirs = player_dirs[:1]  # Seulement le premier joueur

    for player_dir in player_dirs:
        if not player_dir.is_dir():
            continue

        stats_db = player_dir / "stats.duckdb"
        if not stats_db.exists():
            continue

        logger.info(f"Analyse de {player_dir.name}...")
        try:
            conn = duckdb.connect(str(stats_db), read_only=True)

            # Récupérer les asset IDs depuis match_stats
            try:
                # Playlists
                result = conn.execute(
                    """
                    SELECT DISTINCT playlist_id, NULL as version_id
                    FROM match_stats
                    WHERE playlist_id IS NOT NULL
                    """
                ).fetchall()
                for row in result:
                    if row[0]:
                        # Pour l'instant, on n'a pas version_id dans match_stats
                        # On utilisera NULL et on récupérera version_id depuis l'API
                        assets["playlists"].add((row[0], ""))

                # Maps
                result = conn.execute(
                    """
                    SELECT DISTINCT map_id, NULL as version_id
                    FROM match_stats
                    WHERE map_id IS NOT NULL
                    """
                ).fetchall()
                for row in result:
                    if row[0]:
                        assets["maps"].add((row[0], ""))

                # Pairs
                result = conn.execute(
                    """
                    SELECT DISTINCT pair_id, NULL as version_id
                    FROM match_stats
                    WHERE pair_id IS NOT NULL
                    """
                ).fetchall()
                for row in result:
                    if row[0]:
                        assets["pairs"].add((row[0], ""))

                # Game variants
                result = conn.execute(
                    """
                    SELECT DISTINCT game_variant_id, NULL as version_id
                    FROM match_stats
                    WHERE game_variant_id IS NOT NULL
                    """
                ).fetchall()
                for row in result:
                    if row[0]:
                        assets["variants"].add((row[0], ""))

            except Exception as e:
                logger.warning(f"Erreur lors de la lecture de {stats_db}: {e}")

            conn.close()

        except Exception as e:
            logger.warning(f"Impossible d'ouvrir {stats_db}: {e}")

    logger.info(
        f"Asset IDs trouvés: {len(assets['playlists'])} playlists, "
        f"{len(assets['maps'])} maps, {len(assets['pairs'])} pairs, "
        f"{len(assets['variants'])} variants"
    )

    return assets


async def fetch_asset_from_api(
    client: SPNKrAPIClient,
    asset_type: str,
    asset_id: str,
    version_id: str,
) -> dict[str, Any] | None:
    """Récupère un asset depuis Discovery UGC API.

    Args:
        client: Client API SPNKr.
        asset_type: Type d'asset ('Playlists', 'Maps', 'PlaylistMapModePairs', 'GameVariants').
        asset_id: ID de l'asset.
        version_id: Version de l'asset (peut être vide).

    Returns:
        JSON de l'asset ou None si erreur.
    """
    try:
        asset = await client.get_asset(asset_type, asset_id, version_id)
        return asset
    except Exception as e:
        logger.debug(f"Erreur récupération {asset_type} {asset_id}: {e}")
        return None


async def populate_metadata_from_api(
    conn: duckdb.DuckDBPyConnection,
    client: SPNKrAPIClient,
    assets: dict[str, set[tuple[str, str]]],
    dry_run: bool = False,
) -> dict[str, int]:
    """Peuple metadata.duckdb depuis Discovery UGC API.

    Args:
        conn: Connexion DuckDB.
        client: Client API SPNKr.
        assets: Dict avec les asset IDs à récupérer.
        dry_run: Si True, ne fait que simuler.

    Returns:
        Dict avec le nombre d'assets insérés par type.
    """
    results: dict[str, int] = {
        "playlists": 0,
        "maps": 0,
        "pairs": 0,
        "variants": 0,
    }

    # Mapping des types vers les noms de tables et API
    type_map = {
        "playlists": ("Playlists", "playlists"),
        "maps": ("Maps", "maps"),
        "pairs": ("PlaylistMapModePairs", "playlist_map_mode_pairs"),
        "variants": ("GameVariants", "game_variants"),
    }

    for asset_key, (api_type, _table_name) in type_map.items():
        asset_set = assets.get(asset_key, set())
        if not asset_set:
            continue

        logger.info(f"Récupération de {len(asset_set)} {asset_key}...")

        for asset_id, version_id in asset_set:
            # Si version_id est vide, on essaie quand même (l'API peut gérer)
            asset_json = await fetch_asset_from_api(client, api_type, asset_id, version_id or "")

            if not asset_json:
                logger.debug(f"Asset non trouvé: {api_type} {asset_id}")
                continue

            # Extraire les informations
            public_name = asset_json.get("PublicName", "")
            description = asset_json.get("Description", "")
            actual_version_id = asset_json.get("VersionId", version_id or "")

            # Extraire des champs spécifiques selon le type
            is_ranked = False
            category = None
            thumbnail_path = None

            if asset_key == "playlists":
                tags = asset_json.get("Tags", [])
                is_ranked = "ranked" in [t.lower() for t in tags if isinstance(t, str)]
                category = asset_json.get("Category", "")

            if asset_key == "maps":
                thumbnail_path = asset_json.get("ThumbnailPath", "")

            if asset_key == "variants":
                category = asset_json.get("Category", "")

            if not dry_run:
                # Insérer ou mettre à jour
                try:
                    if asset_key == "playlists":
                        conn.execute(
                            """
                            INSERT INTO playlists (asset_id, version_id, public_name, description, is_ranked, category, raw_json, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT (asset_id, version_id) DO UPDATE SET
                                public_name = EXCLUDED.public_name,
                                description = EXCLUDED.description,
                                is_ranked = EXCLUDED.is_ranked,
                                category = EXCLUDED.category,
                                raw_json = EXCLUDED.raw_json,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            [
                                asset_id,
                                actual_version_id,
                                public_name,
                                description,
                                is_ranked,
                                category,
                                str(asset_json),  # JSON comme string
                            ],
                        )
                    elif asset_key == "maps":
                        conn.execute(
                            """
                            INSERT INTO maps (asset_id, version_id, public_name, description, thumbnail_path, raw_json, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT (asset_id, version_id) DO UPDATE SET
                                public_name = EXCLUDED.public_name,
                                description = EXCLUDED.description,
                                thumbnail_path = EXCLUDED.thumbnail_path,
                                raw_json = EXCLUDED.raw_json,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            [
                                asset_id,
                                actual_version_id,
                                public_name,
                                description,
                                thumbnail_path,
                                str(asset_json),
                            ],
                        )
                    elif asset_key == "pairs":
                        conn.execute(
                            """
                            INSERT INTO playlist_map_mode_pairs (asset_id, version_id, public_name, description, raw_json, updated_at)
                            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT (asset_id, version_id) DO UPDATE SET
                                public_name = EXCLUDED.public_name,
                                description = EXCLUDED.description,
                                raw_json = EXCLUDED.raw_json,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            [
                                asset_id,
                                actual_version_id,
                                public_name,
                                description,
                                str(asset_json),
                            ],
                        )
                    elif asset_key == "variants":
                        conn.execute(
                            """
                            INSERT INTO game_variants (asset_id, version_id, public_name, description, category, raw_json, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT (asset_id, version_id) DO UPDATE SET
                                public_name = EXCLUDED.public_name,
                                description = EXCLUDED.description,
                                category = EXCLUDED.category,
                                raw_json = EXCLUDED.raw_json,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            [
                                asset_id,
                                actual_version_id,
                                public_name,
                                description,
                                category,
                                str(asset_json),
                            ],
                        )

                    results[asset_key] += 1
                    if results[asset_key] % 10 == 0:
                        logger.info(f"  {results[asset_key]} {asset_key} insérés...")

                except Exception as e:
                    logger.warning(f"Erreur insertion {asset_key} {asset_id}: {e}")

            else:
                # Dry run: juste compter
                results[asset_key] += 1

            # Petite pause pour ne pas surcharger l'API
            await asyncio.sleep(0.1)

    return results


async def main_async(
    all_players: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Point d'entrée principal async."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 50)
    logger.info("Peuplement metadata.duckdb depuis Discovery UGC")
    logger.info("=" * 50)

    # Vérifier les tokens API
    tokens = get_tokens_from_env()
    if not tokens:
        logger.error("Tokens API non trouvés. Configurez HALO_SPARTAN_TOKEN et HALO_XBL_TOKEN")
        return 1

    # Créer le dossier warehouse si nécessaire
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)

    # Créer ou ouvrir metadata.duckdb
    if dry_run:
        conn = duckdb.connect(":memory:")
        logger.info("[DRY-RUN] Utilisation d'une base en mémoire")
    else:
        conn = duckdb.connect(str(METADATA_DB_PATH))
        logger.info(f"Ouverture de: {METADATA_DB_PATH}")

    # Créer le schéma si nécessaire
    create_metadata_db(conn)

    # Récupérer les asset IDs depuis les match_stats
    logger.info("Récupération des asset IDs depuis les match_stats...")
    assets = get_unique_asset_ids_from_players(all_players=all_players)

    if not any(assets.values()):
        logger.warning("Aucun asset ID trouvé. Assurez-vous d'avoir synchronisé des matchs.")
        conn.close()
        return 1

    # Créer le client API
    client = SPNKrAPIClient(tokens)

    # Peupler depuis l'API
    logger.info("Récupération des métadonnées depuis Discovery UGC...")
    results = await populate_metadata_from_api(conn, client, assets, dry_run=dry_run)

    if not dry_run:
        conn.commit()

    # Afficher le résumé
    logger.info("\n" + "=" * 50)
    logger.info("RÉSUMÉ")
    logger.info("=" * 50)
    for asset_type, count in results.items():
        logger.info(f"{asset_type}: {count} assets")

    conn.close()

    return 0


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Peuple metadata.duckdb depuis Discovery UGC",
    )
    parser.add_argument(
        "--all-players",
        action="store_true",
        help="Parcourir tous les joueurs (par défaut: seulement le premier)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule sans écrire",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Affiche plus de détails",
    )

    args = parser.parse_args()

    return asyncio.run(
        main_async(
            all_players=args.all_players,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
