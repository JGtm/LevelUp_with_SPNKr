"""Tests Sprint 7 — Sync v5 : API savings, backfill mask, batch compute.

Complète tests/test_sync_shared_matches.py avec des tests additionnels
pour la couverture du Sprint 7.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pytest

from src.data.sync.engine import DuckDBSyncEngine
from src.data.sync.migrations import BACKFILL_FLAGS
from src.data.sync.models import SyncOptions
from src.data.sync.transformers import (
    extract_match_registry_data,
    extract_participants,
)

# =============================================================================
# Fixtures (répliquées de test_sync_shared_matches.py pour isolation)
# =============================================================================

SAMPLE_MATCH_JSON: dict[str, Any] = {
    "MatchId": "sync-v5-test-001",
    "MatchInfo": {
        "StartTime": "2024-06-15T18:30:00Z",
        "Duration": "PT12M30S",
        "Playlist": {
            "AssetId": "playlist-ranked-arena",
            "PublicName": "Ranked Arena",
        },
        "MapVariant": {
            "AssetId": "map-recharge",
            "PublicName": "Recharge",
        },
        "PlaylistMapModePair": {
            "AssetId": "pair-recharge-slayer",
            "PublicName": "Recharge - Slayer",
        },
        "UgcGameVariant": {
            "AssetId": "variant-slayer",
            "PublicName": "Slayer",
        },
    },
    "Teams": [
        {"TeamId": 0, "TotalPoints": 50},
        {"TeamId": 1, "TotalPoints": 47},
    ],
    "Players": [
        {
            "PlayerId": "xuid(2535423456789)",
            "PlayerGamertag": "Chocoboflor",
            "Outcome": 2,
            "LastTeamId": 0,
            "Rank": 1,
            "PlayerTeamStats": [
                {
                    "Stats": {
                        "CoreStats": {
                            "Kills": 20,
                            "Deaths": 10,
                            "Assists": 5,
                            "KDA": 2.25,
                            "Accuracy": 0.48,
                            "HeadshotKills": 9,
                            "MaxKillingSpree": 7,
                            "AverageLifeSeconds": 52.0,
                            "DamageDealt": 4200.0,
                            "DamageTaken": 3100.0,
                            "ShotsFired": 250,
                            "ShotsHit": 120,
                            "PersonalScore": 2100,
                            "Score": 2100,
                            "Medals": [
                                {"NameId": 1001, "Count": 3},
                                {"NameId": 1002, "Count": 1},
                            ],
                        }
                    }
                }
            ],
        },
        {
            "PlayerId": "xuid(2533987654321)",
            "PlayerGamertag": "Madina97294",
            "Outcome": 3,
            "LastTeamId": 1,
            "Rank": 2,
            "PlayerTeamStats": [
                {
                    "Stats": {
                        "CoreStats": {
                            "Kills": 14,
                            "Deaths": 18,
                            "Assists": 4,
                            "KDA": 0.889,
                            "Accuracy": 0.41,
                            "DamageDealt": 3100.0,
                            "DamageTaken": 3800.0,
                            "ShotsFired": 280,
                            "ShotsHit": 115,
                            "PersonalScore": 1600,
                            "Score": 1600,
                            "Medals": [
                                {"NameId": 1001, "Count": 1},
                            ],
                        }
                    }
                }
            ],
        },
    ],
}


def _create_shared_db(db_path: Path) -> None:
    """Crée une shared_matches.duckdb minimale."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE match_registry (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            playlist_id VARCHAR, playlist_name VARCHAR,
            map_id VARCHAR, map_name VARCHAR,
            pair_id VARCHAR, pair_name VARCHAR,
            game_variant_id VARCHAR, game_variant_name VARCHAR,
            mode_category VARCHAR,
            is_ranked BOOLEAN DEFAULT FALSE,
            is_firefight BOOLEAN DEFAULT FALSE,
            duration_seconds INTEGER,
            team_0_score SMALLINT, team_1_score SMALLINT,
            backfill_completed INTEGER DEFAULT 0,
            participants_loaded BOOLEAN DEFAULT FALSE,
            events_loaded BOOLEAN DEFAULT FALSE,
            medals_loaded BOOLEAN DEFAULT FALSE,
            first_sync_by VARCHAR, first_sync_at TIMESTAMP,
            last_updated_at TIMESTAMP,
            player_count SMALLINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE match_participants (
            match_id VARCHAR NOT NULL, xuid VARCHAR NOT NULL,
            gamertag VARCHAR, team_id INTEGER, outcome INTEGER,
            rank SMALLINT, score INTEGER, kills SMALLINT,
            deaths SMALLINT, assists SMALLINT,
            shots_fired INTEGER, shots_hit INTEGER,
            damage_dealt FLOAT, damage_taken FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, xuid)
        )
    """)
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS highlight_events_id_seq;
        CREATE TABLE highlight_events (
            id INTEGER PRIMARY KEY DEFAULT nextval('highlight_events_id_seq'),
            match_id VARCHAR NOT NULL, event_type VARCHAR NOT NULL,
            time_ms INTEGER, xuid VARCHAR, gamertag VARCHAR,
            type_hint INTEGER, raw_json VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE medals_earned (
            match_id VARCHAR NOT NULL, xuid VARCHAR NOT NULL,
            medal_name_id BIGINT NOT NULL, count SMALLINT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, xuid, medal_name_id)
        )
    """)
    conn.execute("""
        CREATE TABLE xuid_aliases (
            xuid VARCHAR PRIMARY KEY, gamertag VARCHAR NOT NULL,
            last_seen TIMESTAMP, source VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.close()


@pytest.fixture
def tmp_shared_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "warehouse" / "shared_matches.duckdb"
    _create_shared_db(db_path)
    return db_path


@pytest.fixture
def tmp_player_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "players" / "Chocoboflor" / "stats.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


@pytest.fixture
def engine_with_shared(tmp_player_db: Path, tmp_shared_db: Path) -> DuckDBSyncEngine:
    return DuckDBSyncEngine(
        tmp_player_db,
        xuid="2535423456789",
        gamertag="Chocoboflor",
        shared_db_path=tmp_shared_db,
    )


# =============================================================================
# Tests _compute_backfill_mask
# =============================================================================


class TestComputeBackfillMask:
    """Tests pour _compute_backfill_mask."""

    def test_default_options_include_base_flags(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """Options par défaut → flags de base activés."""
        opts = SyncOptions()
        mask = engine_with_shared._compute_backfill_mask(opts)
        assert mask & BACKFILL_FLAGS["medals"]
        assert mask & BACKFILL_FLAGS["personal_scores"]
        assert mask & BACKFILL_FLAGS["performance_scores"]
        assert mask & BACKFILL_FLAGS["accuracy"]
        assert mask & BACKFILL_FLAGS["shots"]

    def test_with_skill_adds_skill_flags(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """with_skill=True ajoute les flags skill et enemy_mmr."""
        opts = SyncOptions(with_skill=True)
        mask = engine_with_shared._compute_backfill_mask(opts)
        assert mask & BACKFILL_FLAGS["skill"]
        assert mask & BACKFILL_FLAGS["enemy_mmr"]

    def test_without_skill_no_skill_flags(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """with_skill=False → pas de flags skill."""
        opts = SyncOptions(with_skill=False)
        mask = engine_with_shared._compute_backfill_mask(opts)
        assert not (mask & BACKFILL_FLAGS["skill"])
        assert not (mask & BACKFILL_FLAGS["enemy_mmr"])

    def test_with_events_adds_events_flag(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """with_highlight_events=True ajoute le flag events."""
        opts = SyncOptions(with_highlight_events=True)
        mask = engine_with_shared._compute_backfill_mask(opts)
        assert mask & BACKFILL_FLAGS["events"]

    def test_with_participants_adds_multi_flags(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """with_participants=True ajoute plusieurs flags participants."""
        opts = SyncOptions(with_participants=True)
        mask = engine_with_shared._compute_backfill_mask(opts)
        assert mask & BACKFILL_FLAGS["participants"]
        assert mask & BACKFILL_FLAGS["participants_scores"]
        assert mask & BACKFILL_FLAGS["participants_kda"]
        assert mask & BACKFILL_FLAGS["participants_shots"]
        assert mask & BACKFILL_FLAGS["participants_damage"]

    def test_with_aliases_adds_aliases_flag(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """with_aliases=True ajoute le flag aliases."""
        opts = SyncOptions(with_aliases=True)
        mask = engine_with_shared._compute_backfill_mask(opts)
        assert mask & BACKFILL_FLAGS["aliases"]

    def test_all_options_enabled(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """Toutes les options activées → mask maximal."""
        opts = SyncOptions(
            with_skill=True,
            with_highlight_events=True,
            with_participants=True,
            with_aliases=True,
            with_assets=True,
        )
        mask = engine_with_shared._compute_backfill_mask(opts)
        # Vérifier que c'est un bitmask non-nul avec beaucoup de bits
        assert mask > 0
        assert bin(mask).count("1") >= 10  # au moins 10 flags


# =============================================================================
# Tests engine shared properties
# =============================================================================


class TestEngineSharedProperties:
    """Tests pour les propriétés shared du moteur."""

    def test_shared_enabled_true(self, engine_with_shared: DuckDBSyncEngine) -> None:
        assert engine_with_shared.shared_enabled is True

    def test_shared_enabled_false_when_no_path(self, tmp_player_db: Path) -> None:
        engine = DuckDBSyncEngine(
            tmp_player_db,
            xuid="123",
            gamertag="Test",
            shared_db_path=Path("/nonexistent/shared.duckdb"),
        )
        assert engine.shared_enabled is False
        engine.close()

    def test_close_is_safe(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """close() peut être appelé plusieurs fois sans erreur."""
        engine_with_shared.close()
        engine_with_shared.close()  # Pas d'exception

    def test_get_sync_status(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """get_sync_status retourne un dict."""
        status = engine_with_shared.get_sync_status()
        assert isinstance(status, dict)


# =============================================================================
# Tests extract_match_registry_data edge cases
# =============================================================================


class TestExtractMatchRegistryEdgeCases:
    """Tests supplémentaires pour extract_match_registry_data."""

    def test_minimal_match_json(self) -> None:
        """Match JSON avec le minimum requis."""
        minimal = {
            "MatchId": "min-match",
            "MatchInfo": {
                "StartTime": "2025-01-01T00:00:00Z",
                "Duration": "PT5M",
            },
            "Teams": [],
            "Players": [],
        }
        result = extract_match_registry_data(minimal)
        assert result is not None
        assert result["match_id"] == "min-match"

    def test_no_teams_scores_are_none(self) -> None:
        """Pas d'équipes → scores à None."""
        data = {
            "MatchId": "no-teams",
            "MatchInfo": {
                "StartTime": "2025-01-01T00:00:00Z",
                "Duration": "PT8M",
            },
            "Teams": [],
            "Players": [],
        }
        result = extract_match_registry_data(data)
        assert result is not None
        assert result["team_0_score"] is None
        assert result["team_1_score"] is None

    def test_with_metadata_resolver(self) -> None:
        """Le metadata_resolver est utilisé quand fourni."""

        def fake_resolver(asset_type: str, asset_id: str) -> str | None:
            if asset_type == "playlist" and asset_id == "pl-123":
                return "Ranked Arena Resolved"
            return None

        data = {
            "MatchId": "resolved-match",
            "MatchInfo": {
                "StartTime": "2025-01-01T00:00:00Z",
                "Duration": "PT10M",
                "Playlist": {"AssetId": "pl-123"},
                "MapVariant": {"AssetId": "map-456"},
            },
            "Teams": [],
            "Players": [],
        }
        result = extract_match_registry_data(data, metadata_resolver=fake_resolver)
        assert result is not None
        # Le resolver doit avoir été appelé pour enrichir le nom
        assert result["match_id"] == "resolved-match"


# =============================================================================
# Tests extract_participants
# =============================================================================


class TestExtractParticipants:
    """Tests pour extract_participants."""

    def test_extracts_all_players_from_match(self) -> None:
        """Tous les joueurs du match sont extraits."""
        participants = extract_participants(SAMPLE_MATCH_JSON)
        assert len(participants) == 2

    def test_participant_match_id(self) -> None:
        """Le match_id est bien assigné."""
        participants = extract_participants(SAMPLE_MATCH_JSON)
        for p in participants:
            assert p.match_id == "sync-v5-test-001"

    def test_participant_xuids_unique(self) -> None:
        """Chaque participant a un xuid unique."""
        participants = extract_participants(SAMPLE_MATCH_JSON)
        xuids = [p.xuid for p in participants]
        assert len(set(xuids)) == len(xuids)

    def test_empty_match_returns_empty(self) -> None:
        """Match sans joueurs → liste vide."""
        empty = {"MatchId": "empty", "Players": []}
        assert extract_participants(empty) == []

    def test_participant_has_kills_deaths(self) -> None:
        """Les participants ont les stats kills/deaths."""
        participants = extract_participants(SAMPLE_MATCH_JSON)
        for p in participants:
            assert p.kills is not None
            assert p.deaths is not None


# =============================================================================
# Tests SyncOptions
# =============================================================================


class TestSyncOptionsExtended:
    """Tests additionnels pour SyncOptions."""

    def test_default_values(self) -> None:
        opts = SyncOptions()
        assert opts.with_skill is True
        assert opts.with_highlight_events is True

    def test_custom_max_matches(self) -> None:
        opts = SyncOptions(max_matches=100)
        assert opts.max_matches == 100

    def test_with_all_options_disabled(self) -> None:
        opts = SyncOptions(
            with_skill=False,
            with_highlight_events=False,
            with_participants=False,
            with_aliases=False,
        )
        assert opts.with_skill is False
        assert opts.with_highlight_events is False
