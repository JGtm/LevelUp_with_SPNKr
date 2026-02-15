"""Tests unitaires pour MetadataResolver.

Ce module teste :
- Résolution depuis metadata.duckdb
- Cache des résolutions
- Gestion des cas limites (asset non trouvé, DB absente, etc.)
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from src.data.sync.metadata_resolver import MetadataResolver, create_metadata_resolver_function


@pytest.fixture
def temp_metadata_db(tmp_path: Path) -> Path:
    """Crée une base metadata.duckdb temporaire pour les tests."""
    db_path = tmp_path / "metadata.duckdb"
    conn = duckdb.connect(str(db_path))

    # Créer les tables
    conn.execute(
        """
        CREATE TABLE playlists (
            asset_id VARCHAR NOT NULL,
            version_id VARCHAR NOT NULL,
            public_name VARCHAR,
            PRIMARY KEY (asset_id, version_id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE maps (
            asset_id VARCHAR NOT NULL,
            version_id VARCHAR NOT NULL,
            public_name VARCHAR,
            PRIMARY KEY (asset_id, version_id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE playlist_map_mode_pairs (
            asset_id VARCHAR NOT NULL,
            version_id VARCHAR NOT NULL,
            public_name VARCHAR,
            PRIMARY KEY (asset_id, version_id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE game_variants (
            asset_id VARCHAR NOT NULL,
            version_id VARCHAR NOT NULL,
            public_name VARCHAR,
            PRIMARY KEY (asset_id, version_id)
        )
        """
    )

    # Insérer des données de test
    conn.execute(
        "INSERT INTO playlists (asset_id, version_id, public_name) VALUES (?, ?, ?)",
        ["playlist-123", "v1", "Ranked Slayer"],
    )
    conn.execute(
        "INSERT INTO maps (asset_id, version_id, public_name) VALUES (?, ?, ?)",
        ["map-456", "v1", "Recharge"],
    )
    conn.execute(
        "INSERT INTO playlist_map_mode_pairs (asset_id, version_id, public_name) VALUES (?, ?, ?)",
        ["pair-789", "v1", "Recharge - Slayer"],
    )
    conn.execute(
        "INSERT INTO game_variants (asset_id, version_id, public_name) VALUES (?, ?, ?)",
        ["variant-abc", "v1", "Slayer"],
    )

    conn.close()
    return db_path


class TestMetadataResolver:
    """Tests pour la classe MetadataResolver."""

    def test_resolve_playlist(self, temp_metadata_db: Path):
        """Test résolution playlist depuis metadata.duckdb."""
        resolver = MetadataResolver(temp_metadata_db)
        name = resolver.resolve("playlist", "playlist-123")
        assert name == "Ranked Slayer"
        resolver.close()

    def test_resolve_map(self, temp_metadata_db: Path):
        """Test résolution map depuis metadata.duckdb."""
        resolver = MetadataResolver(temp_metadata_db)
        name = resolver.resolve("map", "map-456")
        assert name == "Recharge"
        resolver.close()

    def test_resolve_pair(self, temp_metadata_db: Path):
        """Test résolution pair depuis metadata.duckdb."""
        resolver = MetadataResolver(temp_metadata_db)
        name = resolver.resolve("pair", "pair-789")
        assert name == "Recharge - Slayer"
        resolver.close()

    def test_resolve_game_variant(self, temp_metadata_db: Path):
        """Test résolution game variant depuis metadata.duckdb."""
        resolver = MetadataResolver(temp_metadata_db)
        name = resolver.resolve("game_variant", "variant-abc")
        assert name == "Slayer"
        resolver.close()

    def test_resolve_not_found(self, temp_metadata_db: Path):
        """Test résolution asset non trouvé."""
        resolver = MetadataResolver(temp_metadata_db)
        name = resolver.resolve("playlist", "nonexistent-id")
        assert name is None
        resolver.close()

    def test_resolve_none_asset_id(self, temp_metadata_db: Path):
        """Test résolution avec asset_id None."""
        resolver = MetadataResolver(temp_metadata_db)
        name = resolver.resolve("playlist", None)
        assert name is None
        resolver.close()

    def test_resolve_empty_asset_id(self, temp_metadata_db: Path):
        """Test résolution avec asset_id vide."""
        resolver = MetadataResolver(temp_metadata_db)
        name = resolver.resolve("playlist", "")
        assert name is None
        resolver.close()

    def test_resolve_cache(self, temp_metadata_db: Path):
        """Test que le cache fonctionne."""
        resolver = MetadataResolver(temp_metadata_db)
        # Premier appel
        name1 = resolver.resolve("playlist", "playlist-123")
        assert name1 == "Ranked Slayer"
        # Deuxième appel (devrait utiliser le cache)
        name2 = resolver.resolve("playlist", "playlist-123")
        assert name2 == "Ranked Slayer"
        assert name1 == name2
        resolver.close()

    def test_resolve_invalid_type(self, temp_metadata_db: Path):
        """Test résolution avec type invalide."""
        resolver = MetadataResolver(temp_metadata_db)
        name = resolver.resolve("invalid_type", "some-id")
        assert name is None
        resolver.close()

    def test_resolve_db_not_exists(self):
        """Test résolution quand metadata.duckdb n'existe pas."""
        resolver = MetadataResolver(Path("/nonexistent/metadata.duckdb"))
        name = resolver.resolve("playlist", "playlist-123")
        assert name is None
        resolver.close()

    def test_context_manager(self, temp_metadata_db: Path):
        """Test utilisation comme context manager."""
        with MetadataResolver(temp_metadata_db) as resolver:
            name = resolver.resolve("playlist", "playlist-123")
            assert name == "Ranked Slayer"
        # La connexion devrait être fermée automatiquement


class TestCreateMetadataResolverFunction:
    """Tests pour la fonction create_metadata_resolver_function."""

    def test_create_resolver_function(self, temp_metadata_db: Path):
        """Test création d'une fonction resolver."""
        resolver_func = create_metadata_resolver_function(temp_metadata_db)
        assert resolver_func is not None

        name = resolver_func("playlist", "playlist-123")
        assert name == "Ranked Slayer"

    def test_create_resolver_function_db_not_exists(self):
        """Test création resolver quand DB n'existe pas."""
        resolver_func = create_metadata_resolver_function(Path("/nonexistent/metadata.duckdb"))
        assert resolver_func is None

    def test_resolver_function_playlist(self, temp_metadata_db: Path):
        """Test fonction resolver pour playlist."""
        resolver_func = create_metadata_resolver_function(temp_metadata_db)
        assert resolver_func is not None

        name = resolver_func("playlist", "playlist-123")
        assert name == "Ranked Slayer"

    def test_resolver_function_map(self, temp_metadata_db: Path):
        """Test fonction resolver pour map."""
        resolver_func = create_metadata_resolver_function(temp_metadata_db)
        assert resolver_func is not None

        name = resolver_func("map", "map-456")
        assert name == "Recharge"

    def test_resolver_function_not_found(self, temp_metadata_db: Path):
        """Test fonction resolver asset non trouvé."""
        resolver_func = create_metadata_resolver_function(temp_metadata_db)
        assert resolver_func is not None

        name = resolver_func("playlist", "nonexistent-id")
        assert name is None

    def test_resolver_function_none_asset_id(self, temp_metadata_db: Path):
        """Test fonction resolver avec asset_id None."""
        resolver_func = create_metadata_resolver_function(temp_metadata_db)
        assert resolver_func is not None

        name = resolver_func("playlist", None)
        assert name is None
