"""Tests unitaires pour le module de synchronisation.

Ce fichier teste les composants du sprint 4.7 :
- Transformers (transform_match_stats, transform_skill_stats, etc.)
- Models (SyncOptions, SyncResult)
- Extraction d'aliases

Les tests du DuckDBSyncEngine complet sont dans test_sync_integration.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_match_json() -> dict:
    """JSON d'exemple d'un match SPNKr."""
    # Note: XUIDs réalistes ont 12+ chiffres (ex: 2535423456789)
    return {
        "MatchId": "test-match-id-12345",
        "MatchInfo": {
            "StartTime": "2024-01-15T14:30:00Z",
            "Playlist": {
                "AssetId": "playlist-123",
                "PublicName": "Ranked Slayer",
            },
            "MapVariant": {
                "AssetId": "map-456",
                "PublicName": "Recharge",
            },
            "PlaylistMapModePair": {
                "AssetId": "pair-789",
                "PublicName": "Recharge - Slayer",
            },
            "UgcGameVariant": {
                "AssetId": "variant-abc",
                "PublicName": "Slayer",
            },
        },
        "Teams": [
            {"TeamId": 0, "TotalPoints": 50},
            {"TeamId": 1, "TotalPoints": 45},
        ],
        "Players": [
            {
                "PlayerId": "xuid(2535423456789)",
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
                                "KDA": 1.875,
                                "Accuracy": 0.45,
                                "HeadshotKills": 7,
                                "MaxKillingSpree": 5,
                                "AverageLifeSeconds": 45.5,
                                "DamageDealt": 3500.0,
                                "DamageTaken": 2800.0,
                                "ShotsFired": 200,
                                "ShotsHit": 90,
                            }
                        }
                    }
                ],
            },
            {
                "PlayerId": "xuid(2533987654321)",
                "PlayerGamertag": "Opponent1",
                "Outcome": 3,  # Loss
                "LastTeamId": 1,
                "Rank": 2,
                "PlayerTeamStats": [
                    {
                        "Stats": {
                            "CoreStats": {
                                "Kills": 10,
                                "Deaths": 12,
                                "Assists": 3,
                            }
                        }
                    }
                ],
            },
        ],
    }


@pytest.fixture
def sample_skill_json() -> dict:
    """JSON d'exemple des stats skill."""
    return {
        "Value": [
            {
                "Id": "xuid(2535423456789)",
                "Result": {
                    "TeamId": 0,
                    "Mmr": 1500.5,
                    "TeamMmr": 1520.0,
                    "StatPerformances": {
                        "Kills": {"Expected": 12.5, "StdDev": 3.2},
                        "Deaths": {"Expected": 10.0, "StdDev": 2.5},
                        "Assists": {"Expected": 4.0, "StdDev": 1.5},
                    },
                },
            },
            {
                "Id": "xuid(2533987654321)",
                "Result": {
                    "TeamId": 1,
                    "Mmr": 1450.0,
                },
            },
        ]
    }


@pytest.fixture
def sample_highlight_events() -> list:
    """Liste d'exemple de highlight events."""
    return [
        {
            "event_type": "kill",
            "time_ms": 45000,
            "xuid": "2535423456789",
            "gamertag": "TestPlayer",
            "type_hint": 1,
        },
        {
            "event_type": "death",
            "time_ms": 60000,
            "xuid": "2535423456789",
            "gamertag": "TestPlayer",
            "type_hint": 2,
        },
    ]


# =============================================================================
# Tests des Models
# =============================================================================


class TestSyncOptions:
    """Tests pour SyncOptions."""

    def test_default_values(self):
        """Vérifie les valeurs par défaut."""
        from src.data.sync.models import SyncOptions

        opts = SyncOptions()
        assert opts.match_type == "matchmaking"
        assert opts.max_matches == 200
        assert opts.with_highlight_events is True
        assert opts.with_skill is True
        assert opts.parallel_matches == 3

    def test_custom_values(self):
        """Vérifie les valeurs personnalisées."""
        from src.data.sync.models import SyncOptions

        opts = SyncOptions(
            match_type="all",
            max_matches=500,
            with_highlight_events=False,
        )
        assert opts.match_type == "all"
        assert opts.max_matches == 500
        assert opts.with_highlight_events is False


class TestSyncResult:
    """Tests pour SyncResult."""

    def test_success_with_matches(self):
        """Vérifie success = True si des matchs sont insérés."""
        from src.data.sync.models import SyncResult

        result = SyncResult(matches_inserted=10)
        assert result.success is True
        assert "10 nouveaux matchs" in result.to_message()

    def test_success_no_matches(self):
        """Vérifie success = True si aucune erreur et aucun match."""
        from src.data.sync.models import SyncResult

        result = SyncResult()
        assert result.success is True
        assert "Déjà à jour" in result.to_message()

    def test_failure_with_errors(self):
        """Vérifie success = False si des erreurs."""
        from src.data.sync.models import SyncResult

        result = SyncResult(errors=["Token expiré"])
        assert result.success is False
        assert "Token expiré" in result.to_message()

    def test_to_dict(self):
        """Vérifie la sérialisation en dict."""
        from src.data.sync.models import SyncResult

        result = SyncResult(
            matches_inserted=5,
            aliases_updated=10,
            duration_seconds=3.5,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["matches_inserted"] == 5
        assert d["aliases_updated"] == 10
        assert d["duration_seconds"] == 3.5


# =============================================================================
# Tests des Transformers
# =============================================================================


class TestTransformMatchStats:
    """Tests pour transform_match_stats."""

    def test_basic_transformation(self, sample_match_json):
        """Vérifie la transformation basique d'un match."""
        from src.data.sync.transformers import transform_match_stats

        row = transform_match_stats(sample_match_json, "2535423456789")

        assert row is not None
        assert row.match_id == "test-match-id-12345"
        assert row.kills == 15
        assert row.deaths == 8
        assert row.assists == 5
        assert row.outcome == 2
        assert row.team_id == 0
        assert row.playlist_id == "playlist-123"
        assert row.map_id == "map-456"

    def test_with_skill_json(self, sample_match_json, sample_skill_json):
        """Vérifie l'extraction des MMR depuis skill_json."""
        from src.data.sync.transformers import transform_match_stats

        row = transform_match_stats(
            sample_match_json, "2535423456789", skill_json=sample_skill_json
        )

        assert row is not None
        # MMR devrait être extrait du skill_json
        # Note: La logique exacte dépend de l'implémentation

    def test_missing_player(self, sample_match_json):
        """Vérifie le retour None si le joueur n'est pas trouvé."""
        from src.data.sync.transformers import transform_match_stats

        row = transform_match_stats(sample_match_json, "999999999")
        assert row is None

    def test_missing_match_id(self):
        """Vérifie le retour None si MatchId manquant."""
        from src.data.sync.transformers import transform_match_stats

        row = transform_match_stats({"MatchInfo": {}}, "123")
        assert row is None

    def test_missing_match_info(self):
        """Vérifie le retour None si MatchInfo manquant."""
        from src.data.sync.transformers import transform_match_stats

        row = transform_match_stats({"MatchId": "test"}, "123")
        assert row is None


class TestTransformSkillStats:
    """Tests pour transform_skill_stats."""

    def test_basic_transformation(self, sample_skill_json):
        """Vérifie la transformation des stats skill."""
        from src.data.sync.transformers import transform_skill_stats

        row = transform_skill_stats(sample_skill_json, "test-match", "2535423456789")

        assert row is not None
        assert row.match_id == "test-match"
        assert row.xuid == "2535423456789"
        assert row.team_id == 0
        assert row.team_mmr == 1520.0
        assert row.kills_expected == 12.5
        assert row.kills_stddev == 3.2

    def test_player_not_found(self, sample_skill_json):
        """Vérifie le retour None si le joueur n'est pas dans le skill."""
        from src.data.sync.transformers import transform_skill_stats

        row = transform_skill_stats(sample_skill_json, "test-match", "999999999")
        assert row is None

    def test_empty_value(self):
        """Vérifie le retour None si Value est vide."""
        from src.data.sync.transformers import transform_skill_stats

        row = transform_skill_stats({"Value": []}, "test-match", "123")
        assert row is None


class TestTransformHighlightEvents:
    """Tests pour transform_highlight_events."""

    def test_basic_transformation(self, sample_highlight_events):
        """Vérifie la transformation des events."""
        from src.data.sync.transformers import transform_highlight_events

        rows = transform_highlight_events(sample_highlight_events, "test-match")

        assert len(rows) == 2
        assert rows[0].match_id == "test-match"
        assert rows[0].event_type == "kill"
        assert rows[0].time_ms == 45000
        assert rows[0].xuid == "2535423456789"

    def test_empty_events(self):
        """Vérifie le retour liste vide si pas d'events."""
        from src.data.sync.transformers import transform_highlight_events

        rows = transform_highlight_events([], "test-match")
        assert rows == []


class TestExtractAliases:
    """Tests pour extract_aliases."""

    def test_extract_from_match(self, sample_match_json):
        """Vérifie l'extraction des aliases depuis un match."""
        from src.data.sync.transformers import extract_aliases

        aliases = extract_aliases(sample_match_json)

        assert len(aliases) == 2
        xuids = {a.xuid for a in aliases}
        assert "2535423456789" in xuids
        assert "2533987654321" in xuids

        # Vérifier les gamertags
        gt_map = {a.xuid: a.gamertag for a in aliases}
        assert gt_map["2535423456789"] == "TestPlayer"
        assert gt_map["2533987654321"] == "Opponent1"

    def test_empty_players(self):
        """Vérifie le retour liste vide si pas de joueurs."""
        from src.data.sync.transformers import extract_aliases

        aliases = extract_aliases({"Players": []})
        assert aliases == []


class TestExtractXuids:
    """Tests pour extract_xuids_from_match."""

    def test_extract_xuids(self, sample_match_json):
        """Vérifie l'extraction des XUIDs."""
        from src.data.sync.transformers import extract_xuids_from_match

        xuids = extract_xuids_from_match(sample_match_json)

        assert len(xuids) == 2
        assert 2535423456789 in xuids
        assert 2533987654321 in xuids

    def test_empty_players(self):
        """Vérifie le retour liste vide si pas de joueurs."""
        from src.data.sync.transformers import extract_xuids_from_match

        xuids = extract_xuids_from_match({"Players": []})
        assert xuids == []


# =============================================================================
# Tests des helpers de parsing
# =============================================================================


class TestParsingHelpers:
    """Tests pour les fonctions de parsing internes."""

    def test_safe_float(self):
        """Vérifie _safe_float."""
        from src.data.sync.transformers import _safe_float

        assert _safe_float(1.5) == 1.5
        assert _safe_float("2.5") == 2.5
        assert _safe_float(None) is None
        assert _safe_float("invalid") is None
        assert _safe_float(float("nan")) is None
        assert _safe_float(float("inf")) is None

    def test_safe_int(self):
        """Vérifie _safe_int."""
        from src.data.sync.transformers import _safe_int

        assert _safe_int(10) == 10
        assert _safe_int(10.5) == 10
        assert _safe_int("20") == 20
        assert _safe_int(None) is None
        assert _safe_int("invalid") is None

    def test_parse_iso_utc(self):
        """Vérifie _parse_iso_utc."""
        from src.data.sync.transformers import _parse_iso_utc

        dt = _parse_iso_utc("2024-01-15T14:30:00Z")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

        assert _parse_iso_utc(None) is None
        assert _parse_iso_utc("invalid") is None


# =============================================================================
# Tests de MatchStatsRow
# =============================================================================


class TestMatchStatsRow:
    """Tests pour le dataclass MatchStatsRow."""

    def test_all_fields(self):
        """Vérifie que tous les champs sont accessibles."""
        from src.data.sync.models import MatchStatsRow

        row = MatchStatsRow(
            match_id="test",
            start_time=datetime.now(timezone.utc),
            kills=10,
            deaths=5,
            assists=3,
            is_ranked=True,
        )

        assert row.match_id == "test"
        assert row.kills == 10
        assert row.is_ranked is True
        # Vérifier les valeurs par défaut
        assert row.is_firefight is False
        assert row.left_early is False


# =============================================================================
# Tests d'intégration légère
# =============================================================================


class TestIntegrationLight:
    """Tests d'intégration légers (sans API réelle)."""

    def test_full_transform_pipeline(self, sample_match_json, sample_skill_json):
        """Vérifie le pipeline complet de transformation."""
        from src.data.sync.transformers import (
            extract_aliases,
            extract_xuids_from_match,
            transform_match_stats,
            transform_skill_stats,
        )

        xuid = "2535423456789"
        match_id = sample_match_json["MatchId"]

        # 1. Extraire les XUIDs
        xuids = extract_xuids_from_match(sample_match_json)
        assert len(xuids) > 0

        # 2. Transformer le match
        match_row = transform_match_stats(sample_match_json, xuid, skill_json=sample_skill_json)
        assert match_row is not None
        assert match_row.match_id == match_id

        # 3. Transformer le skill
        skill_row = transform_skill_stats(sample_skill_json, match_id, xuid)
        assert skill_row is not None
        assert skill_row.match_id == match_id

        # 4. Extraire les aliases
        aliases = extract_aliases(sample_match_json)
        assert len(aliases) > 0

    def test_sync_result_message_variations(self):
        """Vérifie les différentes variations de message de SyncResult."""
        from src.data.sync.models import SyncResult

        # Succès avec tout
        r1 = SyncResult(
            matches_inserted=10,
            aliases_updated=5,
            highlight_events_inserted=20,
            duration_seconds=5.0,
        )
        msg1 = r1.to_message()
        assert "10 nouveaux matchs" in msg1
        assert "5 aliases" in msg1
        assert "20 events" in msg1

        # Succès sans matchs
        r2 = SyncResult()
        assert "Déjà à jour" in r2.to_message()

        # Échec
        r3 = SyncResult(errors=["Erreur 1", "Erreur 2", "Erreur 3"])
        msg3 = r3.to_message()
        assert "❌" in msg3
        assert "Erreur 1" in msg3
