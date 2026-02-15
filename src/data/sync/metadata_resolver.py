"""Résolveur de métadonnées pour DuckDB.

Ce module fournit MetadataResolver pour résoudre les noms d'assets (maps, playlists, etc.)
depuis metadata.duckdb ou depuis Discovery UGC en temps réel.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


class MetadataResolver:
    """Résolveur de métadonnées pour les assets Halo Infinite.

    Résout les noms d'assets (playlists, maps, pairs, game variants) depuis :
    1. metadata.duckdb (cache local)
    2. Discovery UGC API (si metadata.duckdb n'existe pas ou si l'asset n'est pas trouvé)

    Usage:
        resolver = MetadataResolver(metadata_db_path="data/warehouse/metadata.duckdb")
        name = resolver.resolve("playlist", "asset-id-123")
    """

    def __init__(
        self,
        metadata_db_path: Path | str | None = None,
        *,
        create_if_missing: bool = False,
    ) -> None:
        """Initialise le résolveur.

        Args:
            metadata_db_path: Chemin vers metadata.duckdb (auto-détecté si None).
            create_if_missing: Créer metadata.duckdb s'il n'existe pas.
        """
        if metadata_db_path is None:
            # Auto-détection : cherche dans data/warehouse/metadata.duckdb
            base_path = Path(__file__).parent.parent.parent.parent
            metadata_db_path = base_path / "data" / "warehouse" / "metadata.duckdb"
        else:
            metadata_db_path = Path(metadata_db_path)

        self.metadata_db_path = metadata_db_path
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._cache: dict[tuple[str, str], str | None] = {}

        # Créer le dossier parent si nécessaire
        if create_if_missing:
            metadata_db_path.parent.mkdir(parents=True, exist_ok=True)

        # Se connecter si la base existe ou si on doit la créer
        if metadata_db_path.exists() or create_if_missing:
            try:
                self._conn = duckdb.connect(str(metadata_db_path))
                logger.debug(f"Connecté à metadata.duckdb: {metadata_db_path}")
            except Exception as e:
                logger.warning(f"Impossible de se connecter à metadata.duckdb: {e}")
                self._conn = None
        else:
            logger.debug(f"metadata.duckdb non trouvé: {metadata_db_path}")

    def resolve(self, asset_type: str, asset_id: str | None) -> str | None:
        """Résout un nom depuis les référentiels.

        Args:
            asset_type: Type d'asset ('playlist', 'map', 'pair', 'game_variant').
            asset_id: ID de l'asset.

        Returns:
            Nom résolu ou None si non trouvé.
        """
        if not asset_id:
            return None

        # Vérifier le cache
        cache_key = (asset_type, asset_id)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Résoudre depuis metadata.duckdb si disponible
        if self._conn:
            name = self._resolve_from_db(asset_type, asset_id)
            if name:
                self._cache[cache_key] = name
                return name

        # Non trouvé
        self._cache[cache_key] = None
        return None

    def _resolve_from_db(self, asset_type: str, asset_id: str) -> str | None:
        """Résout depuis metadata.duckdb.

        Args:
            asset_type: Type d'asset.
            asset_id: ID de l'asset.

        Returns:
            Nom résolu ou None.
        """
        if not self._conn:
            return None

        # Déterminer la table selon le type
        table_map = {
            "playlist": ["playlists"],
            "map": ["maps"],
            "pair": [
                "map_mode_pairs",
                "playlist_map_mode_pairs",
            ],  # Essayer les deux noms possibles
            "game_variant": ["game_variants"],
        }

        table_candidates = table_map.get(asset_type.lower())
        if not table_candidates:
            return None

        try:
            # Vérifier si une des tables candidates existe
            tables_result = self._conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
            tables = {row[0] for row in tables_result}

            # Trouver la première table candidate qui existe
            table_name = None
            for candidate in table_candidates:
                if candidate in tables:
                    table_name = candidate
                    break

            if not table_name:
                logger.debug(f"Aucune table trouvée pour {asset_type} parmi {table_candidates}")
                return None

            # Détecter dynamiquement la colonne ID (asset_id ou uuid)
            id_column = None
            for col_candidate in ["asset_id", "uuid"]:
                try:
                    # Tester si la colonne existe
                    self._conn.execute(
                        f"SELECT {col_candidate} FROM {table_name} LIMIT 1"
                    ).fetchone()
                    id_column = col_candidate
                    break
                except Exception:
                    continue

            if not id_column:
                logger.debug(f"Aucune colonne ID trouvée dans {table_name} (essayé asset_id, uuid)")
                return None

            # Détecter dynamiquement la colonne de nom (public_name, name_fr, name_en, name)
            name_column = None
            for col_candidate in ["public_name", "name_fr", "name_en", "name"]:
                try:
                    # Tester si la colonne existe
                    self._conn.execute(
                        f"SELECT {col_candidate} FROM {table_name} LIMIT 1"
                    ).fetchone()
                    name_column = col_candidate
                    break
                except Exception:
                    continue

            if not name_column:
                logger.debug(f"Aucune colonne de nom trouvée dans {table_name}")
                return None

            # Requête pour récupérer le nom avec les colonnes détectées
            result = self._conn.execute(
                f"SELECT {name_column} FROM {table_name} WHERE {id_column} = ?",
                [asset_id],
            ).fetchone()

            if result and result[0]:
                name = str(result[0])
                logger.debug(
                    f"Résolu {asset_type} {asset_id} → {name} depuis {table_name}.{name_column}"
                )
                return name

            return None

        except Exception as e:
            logger.debug(f"Erreur résolution {asset_type} {asset_id}: {e}")
            return None

    def close(self) -> None:
        """Ferme la connexion DuckDB."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> MetadataResolver:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


def create_metadata_resolver_function(
    metadata_db_path: Path | str | None = None,
) -> Callable[[str, str | None], str | None] | None:
    """Crée une fonction de résolution compatible avec l'ancienne API.

    Cette fonction est un wrapper autour de MetadataResolver pour maintenir
    la compatibilité avec le code existant qui utilise create_metadata_resolver().

    Args:
        metadata_db_path: Chemin vers metadata.duckdb (auto-détecté si None).

    Returns:
        Fonction resolver(asset_type, asset_id) -> name | None, ou None si metadata.duckdb n'existe pas.
    """
    resolver = MetadataResolver(metadata_db_path=metadata_db_path)
    if resolver._conn is None:
        return None

    def resolve(asset_type: str, asset_id: str | None) -> str | None:
        return resolver.resolve(asset_type, asset_id)

    return resolve
