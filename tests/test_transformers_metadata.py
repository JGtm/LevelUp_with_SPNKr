"""Tests unitaires pour les transformers avec résolution métadonnées.

Ce module teste :
- transform_match_stats avec metadata_resolver
- Extraction des PublicName depuis MatchInfo enrichi
- Fallback sur metadata.duckdb si PublicName manquant
- Fallback sur asset_id si tout échoue
"""

from __future__ import annotations

import pytest

from src.data.sync.transformers import transform_match_stats


@pytest.fixture
def sample_match_json_with_public_names() -> dict:
    """JSON de match avec PublicName dans MatchInfo (enrichi par Discovery UGC)."""
    return {
        "MatchId": "test-match-001",
        "MatchInfo": {
            "StartTime": "2026-02-06T10:00:00Z",
            "Playlist": {
                "AssetId": "playlist-123",
                "VersionId": "v1",
                "PublicName": "Ranked Slayer",  # Enrichi par Discovery UGC
            },
            "MapVariant": {
                "AssetId": "map-456",
                "VersionId": "v1",
                "PublicName": "Recharge",  # Enrichi par Discovery UGC
            },
            "PlaylistMapModePair": {
                "AssetId": "pair-789",
                "VersionId": "v1",
                "PublicName": "Recharge - Slayer",  # Enrichi par Discovery UGC
            },
            "UgcGameVariant": {
                "AssetId": "variant-abc",
                "VersionId": "v1",
                "PublicName": "Slayer",  # Enrichi par Discovery UGC
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
                                "DamageDealt": 3500.0,
                                "DamageTaken": 2800.0,
                                "ShotsFired": 200,
                                "ShotsHit": 90,
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


@pytest.fixture
def sample_match_json_without_public_names() -> dict:
    """JSON de match SANS PublicName (cas où Discovery UGC n'a pas été appelé)."""
    return {
        "MatchId": "test-match-002",
        "MatchInfo": {
            "StartTime": "2026-02-06T11:00:00Z",
            "Playlist": {
                "AssetId": "playlist-123",
                "VersionId": "v1",
                # Pas de PublicName
            },
            "MapVariant": {
                "AssetId": "map-456",
                "VersionId": "v1",
                # Pas de PublicName
            },
            "PlaylistMapModePair": {
                "AssetId": "pair-789",
                "VersionId": "v1",
                # Pas de PublicName
            },
            "UgcGameVariant": {
                "AssetId": "variant-abc",
                "VersionId": "v1",
                # Pas de PublicName
            },
        },
        "Players": [
            {
                "PlayerId": "xuid(2533274792546123)",
                "PlayerGamertag": "TestPlayer",
                "Outcome": 2,
                "LastTeamId": 0,
                "Rank": 1,
                "PlayerTeamStats": [
                    {
                        "Stats": {
                            "CoreStats": {
                                "Kills": 10,
                                "Deaths": 10,
                                "Assists": 5,
                                "KDA": 1.5,
                                "Accuracy": 40.0,
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


def mock_metadata_resolver(asset_type: str, asset_id: str | None) -> str | None:
    """Mock resolver qui retourne des noms depuis metadata.duckdb."""
    if not asset_id:
        return None

    # Simuler les résolutions depuis metadata.duckdb
    mock_data = {
        ("playlist", "playlist-123"): "Ranked Slayer (from DB)",
        ("map", "map-456"): "Recharge (from DB)",
        ("pair", "pair-789"): "Recharge - Slayer (from DB)",
        ("game_variant", "variant-abc"): "Slayer (from DB)",
    }

    return mock_data.get((asset_type, asset_id))


class TestTransformMatchStatsWithMetadata:
    """Tests pour transform_match_stats avec résolution métadonnées."""

    def test_transform_with_public_names(self, sample_match_json_with_public_names: dict):
        """Test transformation avec PublicName déjà présent dans MatchInfo."""
        row = transform_match_stats(
            sample_match_json_with_public_names,
            "2533274792546123",
            metadata_resolver=None,  # Pas besoin de resolver car PublicName déjà présent
        )

        assert row is not None
        assert row.playlist_name == "Ranked Slayer"
        assert row.map_name == "Recharge"
        assert row.pair_name == "Recharge - Slayer"
        assert row.game_variant_name == "Slayer"

    def test_transform_without_public_names_with_resolver(
        self, sample_match_json_without_public_names: dict
    ):
        """Test transformation SANS PublicName mais AVEC metadata_resolver."""
        row = transform_match_stats(
            sample_match_json_without_public_names,
            "2533274792546123",
            metadata_resolver=mock_metadata_resolver,
        )

        assert row is not None
        # Devrait utiliser le resolver pour résoudre depuis metadata.duckdb
        assert row.playlist_name == "Ranked Slayer (from DB)"
        assert row.map_name == "Recharge (from DB)"
        assert row.pair_name == "Recharge - Slayer (from DB)"
        assert row.game_variant_name == "Slayer (from DB)"

    def test_transform_without_public_names_without_resolver(
        self, sample_match_json_without_public_names: dict
    ):
        """Test transformation SANS PublicName et SANS resolver (fallback sur asset_id)."""
        row = transform_match_stats(
            sample_match_json_without_public_names,
            "2533274792546123",
            metadata_resolver=None,
        )

        assert row is not None
        # Devrait fallback sur les asset_id
        assert row.playlist_name == "playlist-123"
        assert row.map_name == "map-456"
        assert row.pair_name == "pair-789"
        assert row.game_variant_name == "variant-abc"

    def test_transform_public_name_priority(self, sample_match_json_with_public_names: dict):
        """Test que PublicName dans MatchInfo a priorité sur resolver."""

        # Créer un resolver qui retournerait un nom différent
        def conflicting_resolver(asset_type: str, asset_id: str | None) -> str | None:
            return "Different Name from DB"

        row = transform_match_stats(
            sample_match_json_with_public_names,
            "2533274792546123",
            metadata_resolver=conflicting_resolver,
        )

        assert row is not None
        # PublicName dans MatchInfo devrait avoir priorité
        assert row.playlist_name == "Ranked Slayer"  # Pas "Different Name from DB"
        assert row.map_name == "Recharge"

    def test_transform_uuid_fallback(self):
        """Test que les UUIDs sont détectés et résolus via resolver."""
        match_json = {
            "MatchId": "test-match-003",
            "MatchInfo": {
                "StartTime": "2026-02-06T12:00:00Z",
                "Playlist": {
                    "AssetId": "playlist-123",
                    "VersionId": "v1",
                    "PublicName": "12345678-1234-1234-1234-123456789012",  # UUID (fallback précédent)
                },
            },
            "Players": [
                {
                    "PlayerId": "xuid(2533274792546123)",
                    "PlayerGamertag": "TestPlayer",
                    "Outcome": 2,
                    "LastTeamId": 0,
                    "Rank": 1,
                    "PlayerTeamStats": [
                        {
                            "Stats": {
                                "CoreStats": {
                                    "Kills": 10,
                                    "Deaths": 10,
                                    "Assists": 5,
                                }
                            }
                        }
                    ],
                }
            ],
            "Teams": [{"TeamId": 0, "TotalPoints": 50}, {"TeamId": 1, "TotalPoints": 45}],
        }

        row = transform_match_stats(
            match_json,
            "2533274792546123",
            metadata_resolver=mock_metadata_resolver,
        )

        assert row is not None
        # Devrait détecter que c'est un UUID et utiliser le resolver
        assert row.playlist_name == "Ranked Slayer (from DB)"

    def test_transform_partial_metadata(self):
        """Test transformation avec métadonnées partielles."""
        match_json = {
            "MatchId": "test-match-004",
            "MatchInfo": {
                "StartTime": "2026-02-06T13:00:00Z",
                "Playlist": {
                    "AssetId": "playlist-123",
                    "PublicName": "Ranked Slayer",  # Présent
                },
                "MapVariant": {
                    "AssetId": "map-456",
                    # Pas de PublicName
                },
            },
            "Players": [
                {
                    "PlayerId": "xuid(2533274792546123)",
                    "PlayerGamertag": "TestPlayer",
                    "Outcome": 2,
                    "LastTeamId": 0,
                    "Rank": 1,
                    "PlayerTeamStats": [
                        {
                            "Stats": {
                                "CoreStats": {
                                    "Kills": 10,
                                    "Deaths": 10,
                                    "Assists": 5,
                                }
                            }
                        }
                    ],
                }
            ],
            "Teams": [{"TeamId": 0, "TotalPoints": 50}, {"TeamId": 1, "TotalPoints": 45}],
        }

        row = transform_match_stats(
            match_json,
            "2533274792546123",
            metadata_resolver=mock_metadata_resolver,
        )

        assert row is not None
        assert row.playlist_name == "Ranked Slayer"  # Depuis MatchInfo
        assert row.map_name == "Recharge (from DB)"  # Depuis resolver
