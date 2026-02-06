"""Tests d'intégration pour la résolution métadonnées end-to-end.

Ce module teste le flux complet :
1. API Discovery UGC → enrich_match_info_with_assets
2. transform_match_stats avec metadata_resolver
3. Insertion dans DuckDB
4. Vérification que les noms sont bien stockés
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import duckdb
import pytest

from src.data.sync.api_client import SPNKrAPIClient, enrich_match_info_with_assets
from src.data.sync.metadata_resolver import MetadataResolver
from src.data.sync.transformers import transform_match_stats


@pytest.fixture
def temp_player_db() -> Path:
    """Crée une base stats.duckdb temporaire pour les tests."""
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / "stats.duckdb"
    return db_path


@pytest.fixture
def temp_metadata_db() -> Path:
    """Crée une base metadata.duckdb temporaire pour les tests."""
    temp_dir = Path(tempfile.mkdtemp())
    db_path = temp_dir / "metadata.duckdb"
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

    # Insérer des données de test
    conn.execute(
        "INSERT INTO playlists (asset_id, version_id, public_name) VALUES (?, ?, ?)",
        ["playlist-123", "v1", "Ranked Slayer (from DB)"],
    )
    conn.execute(
        "INSERT INTO maps (asset_id, version_id, public_name) VALUES (?, ?, ?)",
        ["map-456", "v1", "Recharge (from DB)"],
    )

    conn.close()
    return db_path


@pytest.fixture
def sample_match_json() -> dict:
    """JSON de match de test."""
    return {
        "MatchId": "test-match-integration-001",
        "MatchInfo": {
            "StartTime": "2026-02-06T14:00:00Z",
            "Playlist": {
                "AssetId": "playlist-123",
                "VersionId": "v1",
                # Pas de PublicName initialement
            },
            "MapVariant": {
                "AssetId": "map-456",
                "VersionId": "v1",
                # Pas de PublicName initialement
            },
            "PlaylistMapModePair": {
                "AssetId": "pair-789",
                "VersionId": "v1",
            },
            "UgcGameVariant": {
                "AssetId": "variant-abc",
                "VersionId": "v1",
            },
        },
        "Players": [
            {
                "PlayerId": "xuid(2533274792546123)",
                "PlayerGamertag": "TestPlayer",
                "Outcome": 2,  # Win
                "LastTeamId": 0,
                "Rank": 1,
                "PlayerTeamStats": [
                    {
                        "Stats": {
                            "CoreStats": {
                                "Kills": 15,
                                "Deaths": 8,
                                "Assists": 5,
                                "KDA": 2.5,
                                "Accuracy": 45.0,
                                "HeadshotKills": 7,
                                "MaxKillingSpree": 5,
                                "AverageLifeSeconds": 45.5,
                                "TimePlayed": "PT600S",
                            }
                        }
                    }
                ],
            }
        ],
        "Teams": [
            {"TeamId": 0, "TotalPoints": 50},
            {"TeamId": 1, "TotalPoints": 45},
        ],
    }


class TestMetadataResolutionIntegration:
    """Tests d'intégration pour la résolution métadonnées."""

    @pytest.mark.asyncio
    async def test_enrich_match_info_with_assets(self, sample_match_json: dict):
        """Test enrichissement MatchInfo avec Discovery UGC."""
        # Mock du client API
        mock_client = MagicMock(spec=SPNKrAPIClient)

        # Mock get_asset pour retourner des PublicName
        async def mock_get_asset(asset_type: str, asset_id: str, version_id: str):
            if asset_type == "Playlists" and asset_id == "playlist-123":
                return {"PublicName": "Ranked Slayer (from API)", "VersionId": version_id}
            elif asset_type == "Maps" and asset_id == "map-456":
                return {"PublicName": "Recharge (from API)", "VersionId": version_id}
            return None

        mock_client.get_asset = AsyncMock(side_effect=mock_get_asset)

        # Enrichir
        await enrich_match_info_with_assets(mock_client, sample_match_json)

        # Vérifier que PublicName a été ajouté
        assert (
            sample_match_json["MatchInfo"]["Playlist"]["PublicName"] == "Ranked Slayer (from API)"
        )
        assert sample_match_json["MatchInfo"]["MapVariant"]["PublicName"] == "Recharge (from API)"

    def test_transform_with_enriched_match_info(self, sample_match_json: dict):
        """Test transformation avec MatchInfo enrichi."""
        # Enrichir manuellement (simule enrich_match_info_with_assets)
        sample_match_json["MatchInfo"]["Playlist"]["PublicName"] = "Ranked Slayer (enriched)"
        sample_match_json["MatchInfo"]["MapVariant"]["PublicName"] = "Recharge (enriched)"

        row = transform_match_stats(
            sample_match_json,
            "2533274792546123",
            metadata_resolver=None,
        )

        assert row is not None
        assert row.playlist_name == "Ranked Slayer (enriched)"
        assert row.map_name == "Recharge (enriched)"

    def test_transform_with_metadata_resolver_fallback(
        self, sample_match_json: dict, temp_metadata_db: Path
    ):
        """Test transformation avec fallback sur metadata_resolver."""
        # Pas de PublicName dans MatchInfo
        # Le resolver devrait être utilisé

        resolver = MetadataResolver(temp_metadata_db)

        def resolver_func(asset_type: str, asset_id: str | None) -> str | None:
            return resolver.resolve(asset_type, asset_id)

        row = transform_match_stats(
            sample_match_json,
            "2533274792546123",
            metadata_resolver=resolver_func,
        )

        assert row is not None
        # Devrait utiliser le resolver
        assert row.playlist_name == "Ranked Slayer (from DB)"
        assert row.map_name == "Recharge (from DB)"

        resolver.close()

    def test_end_to_end_sync_with_metadata(
        self, temp_player_db: Path, temp_metadata_db: Path, sample_match_json: dict
    ):
        """Test end-to-end : sync avec résolution métadonnées."""
        # Créer le resolver
        resolver = MetadataResolver(temp_metadata_db)

        # Transformer avec resolver
        row = transform_match_stats(
            sample_match_json,
            "2533274792546123",
            metadata_resolver=lambda asset_type, asset_id: resolver.resolve(asset_type, asset_id),
        )

        assert row is not None
        assert row.playlist_name == "Ranked Slayer (from DB)"
        assert row.map_name == "Recharge (from DB)"

        # Insérer dans DuckDB
        conn = duckdb.connect(str(temp_player_db))

        # Créer la table match_stats
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                playlist_id VARCHAR,
                playlist_name VARCHAR,
                map_id VARCHAR,
                map_name VARCHAR,
                pair_id VARCHAR,
                pair_name VARCHAR,
                game_variant_id VARCHAR,
                game_variant_name VARCHAR,
                outcome INTEGER,
                team_id INTEGER,
                rank INTEGER,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                kda FLOAT,
                accuracy FLOAT
            )
            """
        )

        # Insérer la ligne
        conn.execute(
            """
            INSERT INTO match_stats (
                match_id, start_time, playlist_id, playlist_name,
                map_id, map_name, pair_id, pair_name,
                game_variant_id, game_variant_name,
                outcome, team_id, rank, kills, deaths, assists, kda, accuracy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row.match_id,
                row.start_time,
                row.playlist_id,
                row.playlist_name,
                row.map_id,
                row.map_name,
                row.pair_id,
                row.pair_name,
                row.game_variant_id,
                row.game_variant_name,
                row.outcome,
                row.team_id,
                row.rank,
                row.kills,
                row.deaths,
                row.assists,
                row.kda,
                row.accuracy,
            ],
        )

        # Vérifier que les noms sont bien stockés
        result = conn.execute(
            "SELECT playlist_name, map_name FROM match_stats WHERE match_id = ?",
            [row.match_id],
        ).fetchone()

        assert result is not None
        assert result[0] == "Ranked Slayer (from DB)"
        assert result[1] == "Recharge (from DB)"

        conn.close()
        resolver.close()

    def test_metadata_resolver_priority(self, sample_match_json: dict, temp_metadata_db: Path):
        """Test priorité : PublicName dans MatchInfo > resolver > asset_id."""
        # Cas 1: PublicName présent dans MatchInfo
        sample_match_json["MatchInfo"]["Playlist"]["PublicName"] = "Ranked Slayer (from API)"

        resolver = MetadataResolver(temp_metadata_db)

        def resolver_func(asset_type: str, asset_id: str | None) -> str | None:
            return resolver.resolve(asset_type, asset_id)

        row = transform_match_stats(
            sample_match_json,
            "2533274792546123",
            metadata_resolver=resolver_func,
        )

        assert row is not None
        # PublicName dans MatchInfo devrait avoir priorité
        assert row.playlist_name == "Ranked Slayer (from API)"

        # Cas 2: Pas de PublicName, utiliser resolver
        del sample_match_json["MatchInfo"]["Playlist"]["PublicName"]

        row = transform_match_stats(
            sample_match_json,
            "2533274792546123",
            metadata_resolver=resolver_func,
        )

        assert row is not None
        # Devrait utiliser le resolver
        assert row.playlist_name == "Ranked Slayer (from DB)"

        # Cas 3: Pas de resolver, fallback sur asset_id
        row = transform_match_stats(
            sample_match_json,
            "2533274792546123",
            metadata_resolver=None,
        )

        assert row is not None
        # Devrait fallback sur asset_id
        assert row.playlist_name == "playlist-123"

        resolver.close()
