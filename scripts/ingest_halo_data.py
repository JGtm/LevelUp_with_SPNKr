#!/usr/bin/env python3
"""
Ingestion des données Halo JSON vers stockage hybride (SQLite + Parquet).
(Ingest Halo JSON data to hybrid storage - SQLite + Parquet)

HOW IT WORKS:
1. Lit les fichiers JSON de référentiel (playlists, médailles, etc.)
2. Valide avec des modèles Pydantic
3. Écrit les référentiels dans SQLite (données chaudes/relationnelles)
4. Prépare l'infrastructure pour les matchs en Parquet (données froides/volumineuses)

Usage:
    python scripts/ingest_halo_data.py --action all
    python scripts/ingest_halo_data.py --action playlists
    python scripts/ingest_halo_data.py --action medals
    python scripts/ingest_halo_data.py --action verify

Instructions de test:
    pytest scripts/ingest_halo_data.py -v  # Lance les tests intégrés
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Configuration du logging
# (Logging configuration)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Chemins par défaut
# (Default paths)
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
STATIC_DIR = PROJECT_ROOT / "static"
WAREHOUSE_DIR = DATA_DIR / "warehouse"
# Priorité à metadata.duckdb, fallback sur metadata.db (legacy SQLite)
METADATA_DB_DUCKDB = WAREHOUSE_DIR / "metadata.duckdb"
METADATA_DB_SQLITE = WAREHOUSE_DIR / "metadata.db"
METADATA_DB = METADATA_DB_SQLITE  # Ce script ingère vers SQLite (migration séparée vers DuckDB)


# =============================================================================
# MODÈLES PYDANTIC POUR LES RÉFÉRENTIELS
# (Pydantic models for reference data)
# =============================================================================


class PlaylistTranslation(BaseModel):
    """
    Traduction d'une playlist.
    (Playlist translation)
    """

    model_config = ConfigDict(extra="ignore")

    uuid: str | None = Field(default=None, description="UUID de la playlist")
    en: str = Field(..., min_length=1, description="Nom anglais")
    fr: str = Field(..., min_length=1, description="Nom français")


class GameModeTranslation(BaseModel):
    """
    Traduction d'un mode de jeu.
    (Game mode translation)
    """

    model_config = ConfigDict(extra="ignore")

    en: str = Field(..., min_length=1, description="Nom anglais")
    fr: str = Field(..., min_length=1, description="Nom français")
    category: str = Field(..., description="Catégorie du mode")


class MedalDefinition(BaseModel):
    """
    Définition d'une médaille.
    (Medal definition)
    """

    model_config = ConfigDict(extra="ignore")

    name_id: int = Field(..., description="ID numérique de la médaille")
    name_fr: str = Field(..., min_length=1, description="Nom français")
    name_en: str | None = Field(default=None, description="Nom anglais")

    @field_validator("name_id", mode="before")
    @classmethod
    def parse_name_id(cls, v: Any) -> int:
        """Parse le name_id depuis une string."""
        if isinstance(v, int):
            return v
        return int(str(v))


class PlaylistModesData(BaseModel):
    """
    Structure complète du fichier Playlist_modes_translations.json.
    (Complete structure of Playlist_modes_translations.json)
    """

    model_config = ConfigDict(extra="ignore")

    playlists: list[PlaylistTranslation] = Field(default_factory=list)
    modes: list[GameModeTranslation] = Field(default_factory=list)
    categories: dict[str, str] = Field(default_factory=dict)


# =============================================================================
# RÉSULTAT D'INGESTION
# (Ingestion result)
# =============================================================================


@dataclass
class IngestionResult:
    """Résultat d'une opération d'ingestion."""

    success: bool
    table_name: str
    rows_inserted: int
    errors: list[str]

    def __str__(self) -> str:
        status = "[OK]" if self.success else "[FAIL]"
        return f"{status} {self.table_name}: {self.rows_inserted} lignes"


# =============================================================================
# INGESTION VERS SQLITE
# (Ingestion to SQLite)
# =============================================================================


class MetadataIngester:
    """
    Ingère les données de référentiel dans SQLite.
    (Ingests reference data into SQLite)
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """
        Initialise l'ingester.

        Args:
            db_path: Chemin vers la base SQLite (défaut: data/warehouse/metadata.db)
        """
        self.db_path = db_path or METADATA_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Créer les tables si nécessaires
        # (Create tables if needed)
        self._init_schema()

    def _init_schema(self) -> None:
        """
        Crée le schéma SQLite.
        (Create SQLite schema)
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- Table des playlists
                -- (Playlists table)
                CREATE TABLE IF NOT EXISTS playlists (
                    uuid TEXT PRIMARY KEY,
                    name_en TEXT NOT NULL,
                    name_fr TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Table des modes de jeu
                -- (Game modes table)
                CREATE TABLE IF NOT EXISTS game_modes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name_en TEXT NOT NULL UNIQUE,
                    name_fr TEXT NOT NULL,
                    category TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Table des catégories
                -- (Categories table)
                CREATE TABLE IF NOT EXISTS categories (
                    name_en TEXT PRIMARY KEY,
                    name_fr TEXT NOT NULL
                );

                -- Table des définitions de médailles
                -- (Medal definitions table)
                CREATE TABLE IF NOT EXISTS medal_definitions (
                    name_id INTEGER PRIMARY KEY,
                    name_en TEXT,
                    name_fr TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Index pour les recherches
                -- (Indexes for lookups)
                CREATE INDEX IF NOT EXISTS idx_playlists_name_en ON playlists(name_en);
                CREATE INDEX IF NOT EXISTS idx_game_modes_category ON game_modes(category);
                CREATE INDEX IF NOT EXISTS idx_medal_definitions_name_fr ON medal_definitions(name_fr);
            """)
            conn.commit()

    def ingest_playlists(self, json_path: Path | None = None) -> IngestionResult:
        """
        Ingère les playlists depuis le JSON.
        (Ingest playlists from JSON)
        """
        json_path = json_path or (PROJECT_ROOT / "Playlist_modes_translations.json")
        errors: list[str] = []
        rows_inserted = 0

        try:
            with open(json_path, encoding="utf-8") as f:
                raw_data = json.load(f)

            # Valider avec Pydantic
            # (Validate with Pydantic)
            data = PlaylistModesData.model_validate(raw_data)

            with sqlite3.connect(self.db_path) as conn:
                # Insérer les playlists
                # (Insert playlists)
                for playlist in data.playlists:
                    if playlist.uuid:
                        try:
                            conn.execute(
                                """INSERT OR REPLACE INTO playlists (uuid, name_en, name_fr)
                                   VALUES (?, ?, ?)""",
                                (playlist.uuid, playlist.en, playlist.fr),
                            )
                            rows_inserted += 1
                        except Exception as e:
                            errors.append(f"Playlist {playlist.en}: {e}")

                # Insérer les modes
                # (Insert modes)
                for mode in data.modes:
                    try:
                        conn.execute(
                            """INSERT OR REPLACE INTO game_modes (name_en, name_fr, category)
                               VALUES (?, ?, ?)""",
                            (mode.en, mode.fr, mode.category),
                        )
                        rows_inserted += 1
                    except Exception as e:
                        errors.append(f"Mode {mode.en}: {e}")

                # Insérer les catégories
                # (Insert categories)
                for cat_en, cat_fr in data.categories.items():
                    try:
                        conn.execute(
                            """INSERT OR REPLACE INTO categories (name_en, name_fr)
                               VALUES (?, ?)""",
                            (cat_en, cat_fr),
                        )
                        rows_inserted += 1
                    except Exception as e:
                        errors.append(f"Catégorie {cat_en}: {e}")

                conn.commit()

            logger.info(f"Playlists ingérées: {rows_inserted} entrées")
            return IngestionResult(
                success=len(errors) == 0,
                table_name="playlists + game_modes + categories",
                rows_inserted=rows_inserted,
                errors=errors,
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'ingestion des playlists: {e}")
            return IngestionResult(
                success=False,
                table_name="playlists",
                rows_inserted=0,
                errors=[str(e)],
            )

    def ingest_medals(
        self,
        json_path_fr: Path | None = None,
        json_path_en: Path | None = None,
    ) -> IngestionResult:
        """
        Ingère les définitions de médailles depuis les JSON.
        (Ingest medal definitions from JSON files)
        """
        json_path_fr = json_path_fr or (STATIC_DIR / "medals" / "medals_fr.json")
        json_path_en = json_path_en or (STATIC_DIR / "medals" / "medals_en.json")
        errors: list[str] = []
        rows_inserted = 0

        try:
            # Charger les traductions FR
            # (Load FR translations)
            with open(json_path_fr, encoding="utf-8") as f:
                medals_fr: dict[str, str] = json.load(f)

            # Charger les traductions EN si disponibles
            # (Load EN translations if available)
            medals_en: dict[str, str] = {}
            if json_path_en.exists():
                try:
                    with open(json_path_en, encoding="utf-8") as f:
                        medals_en = json.load(f)
                except Exception as e:
                    logger.warning(f"Impossible de charger medals_en.json: {e}")

            # Valider et insérer
            # (Validate and insert)
            validated_medals: list[MedalDefinition] = []
            for name_id_str, name_fr in medals_fr.items():
                try:
                    medal = MedalDefinition(
                        name_id=name_id_str,
                        name_fr=name_fr,
                        name_en=medals_en.get(name_id_str),
                    )
                    validated_medals.append(medal)
                except Exception as e:
                    errors.append(f"Médaille {name_id_str}: {e}")

            with sqlite3.connect(self.db_path) as conn:
                for medal in validated_medals:
                    try:
                        conn.execute(
                            """INSERT OR REPLACE INTO medal_definitions
                               (name_id, name_en, name_fr)
                               VALUES (?, ?, ?)""",
                            (medal.name_id, medal.name_en, medal.name_fr),
                        )
                        rows_inserted += 1
                    except Exception as e:
                        errors.append(f"Médaille {medal.name_id}: {e}")

                conn.commit()

            logger.info(f"Médailles ingérées: {rows_inserted} entrées")
            return IngestionResult(
                success=len(errors) == 0,
                table_name="medal_definitions",
                rows_inserted=rows_inserted,
                errors=errors,
            )

        except Exception as e:
            logger.error(f"Erreur lors de l'ingestion des médailles: {e}")
            return IngestionResult(
                success=False,
                table_name="medal_definitions",
                rows_inserted=0,
                errors=[str(e)],
            )

    def verify_with_duckdb(self) -> dict[str, Any]:
        """
        Vérifie que les données sont lisibles avec DuckDB.
        (Verify that data is readable with DuckDB)

        Returns:
            Dict avec les stats de chaque table
        """
        try:
            import duckdb
        except ImportError:
            logger.error("DuckDB n'est pas installé. Installez-le avec: pip install duckdb")
            return {"error": "DuckDB not installed"}

        results: dict[str, Any] = {
            "db_path": str(self.db_path),
            "tables": {},
        }

        try:
            # Connexion DuckDB avec attachement SQLite
            # (DuckDB connection with SQLite attachment)
            conn = duckdb.connect(":memory:")
            conn.execute(f"ATTACH '{self.db_path}' AS meta (TYPE sqlite)")

            # Vérifier chaque table
            # (Check each table)
            tables = ["playlists", "game_modes", "categories", "medal_definitions"]

            for table in tables:
                try:
                    result = conn.execute(f"SELECT COUNT(*) FROM meta.{table}").fetchone()
                    count = result[0] if result else 0

                    # Exemple de données
                    # (Sample data)
                    sample = conn.execute(f"SELECT * FROM meta.{table} LIMIT 3").fetchall()

                    results["tables"][table] = {
                        "count": count,
                        "sample": sample[:3] if sample else [],
                    }
                    logger.info(f"  [OK] {table}: {count} lignes")

                except Exception as e:
                    results["tables"][table] = {"error": str(e)}
                    logger.error(f"  [FAIL] {table}: {e}")

            # Vérifier les fichiers Parquet s'ils existent
            # (Check Parquet files if they exist)
            parquet_dir = WAREHOUSE_DIR / "match_facts"
            if parquet_dir.exists():
                parquet_files = list(parquet_dir.glob("**/*.parquet"))
                if parquet_files:
                    try:
                        # Lire tous les Parquet
                        # (Read all Parquet files)
                        result = conn.execute(f"""
                            SELECT COUNT(*) as total_matches,
                                   COUNT(DISTINCT xuid) as players,
                                   MIN(start_time) as first_match,
                                   MAX(start_time) as last_match
                            FROM read_parquet('{parquet_dir}/**/*.parquet')
                        """).fetchone()

                        results["parquet"] = {
                            "files": len(parquet_files),
                            "total_matches": result[0] if result else 0,
                            "players": result[1] if result else 0,
                            "first_match": str(result[2]) if result and result[2] else None,
                            "last_match": str(result[3]) if result and result[3] else None,
                        }
                        logger.info(
                            f"  [OK] Parquet: {len(parquet_files)} fichiers, {result[0]} matchs"
                        )
                    except Exception as e:
                        results["parquet"] = {"error": str(e)}
                        logger.warning(f"  [WARN] Parquet: {e}")
            else:
                results["parquet"] = {
                    "status": "no_data",
                    "message": "Pas encore de matchs Parquet",
                }
                logger.info("  [INFO] Parquet: Pas encore de donnees")

            conn.close()
            results["success"] = True

        except Exception as e:
            logger.error(f"Erreur DuckDB: {e}")
            results["error"] = str(e)
            results["success"] = False

        return results

    def get_summary(self) -> dict[str, int]:
        """
        Retourne un résumé des données ingérées.
        (Return a summary of ingested data)
        """
        with sqlite3.connect(self.db_path) as conn:
            tables = ["playlists", "game_modes", "categories", "medal_definitions"]
            summary = {}
            for table in tables:
                try:
                    result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    summary[table] = result[0] if result else 0
                except Exception:
                    summary[table] = 0
            return summary


# =============================================================================
# POINT D'ENTRÉE
# (Entry point)
# =============================================================================


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Ingestion des données Halo vers stockage hybride",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--action",
        choices=["all", "playlists", "medals", "verify", "summary"],
        default="all",
        help="Action à effectuer (default: all)",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help=f"Chemin vers la base SQLite (default: {METADATA_DB})",
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

    ingester = MetadataIngester(db_path=args.db_path)
    results: list[IngestionResult] = []

    logger.info("=" * 60)
    logger.info("Ingestion des données Halo")
    logger.info(f"Base SQLite: {ingester.db_path}")
    logger.info("=" * 60)

    if args.action in ("all", "playlists"):
        logger.info("\n[1/3] Ingestion des playlists et modes...")
        result = ingester.ingest_playlists()
        results.append(result)
        print(f"  {result}")

    if args.action in ("all", "medals"):
        logger.info("\n[2/3] Ingestion des médailles...")
        result = ingester.ingest_medals()
        results.append(result)
        print(f"  {result}")

    if args.action in ("all", "verify"):
        logger.info("\n[3/3] Vérification avec DuckDB...")
        verification = ingester.verify_with_duckdb()
        if verification.get("success"):
            print("  [OK] Verification DuckDB reussie")
            for table, stats in verification.get("tables", {}).items():
                if "error" not in stats:
                    print(f"    - {table}: {stats.get('count', 0)} lignes")
        else:
            print(f"  [FAIL] Erreur: {verification.get('error', 'Unknown')}")

    if args.action == "summary":
        summary = ingester.get_summary()
        print("\nRésumé des données:")
        for table, count in summary.items():
            print(f"  - {table}: {count} lignes")

    # Résumé final
    # (Final summary)
    logger.info("\n" + "=" * 60)
    logger.info("RÉSUMÉ")
    logger.info("=" * 60)

    success_count = sum(1 for r in results if r.success)
    total_rows = sum(r.rows_inserted for r in results)

    print(f"\n[OK] {success_count}/{len(results)} operations reussies")
    print(f"[OK] {total_rows} lignes inserees au total")
    print(f"[OK] Base: {ingester.db_path}")

    # Retourner 0 si tout est OK, 1 sinon
    # (Return 0 if OK, 1 otherwise)
    return 0 if all(r.success for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
