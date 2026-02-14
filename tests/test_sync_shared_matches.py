"""Tests unitaires pour le sync engine v5 — shared_matches.

Tests Sprint 3 :
- Détection des matchs partagés (known vs new)
- Sync allégée pour matchs existants dans shared
- Sync complète pour nouveaux matchs vers shared
- Insertions dans shared_matches.duckdb
- extract_match_registry_data()
- _extract_team_scores_by_id()
- Mode legacy v4 (pas de shared_matches.duckdb)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import duckdb
import pytest

from src.data.sync.engine import DuckDBSyncEngine
from src.data.sync.models import SyncOptions
from src.data.sync.transformers import (
    extract_all_medals,
    extract_match_registry_data,
    extract_participants,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_match_json() -> dict[str, Any]:
    """JSON d'exemple d'un match SPNKr avec 2 joueurs."""
    return {
        "MatchId": "shared-test-match-001",
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
                "Outcome": 2,  # Win
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
                "Outcome": 3,  # Loss
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
                                    {"NameId": 1003, "Count": 2},
                                ],
                            }
                        }
                    }
                ],
            },
        ],
    }


@pytest.fixture
def sample_highlight_events() -> list[dict[str, Any]]:
    """Liste d'exemple de highlight events."""
    return [
        {
            "event_type": "kill",
            "time_ms": 45000,
            "xuid": "2535423456789",
            "gamertag": "Chocoboflor",
            "type_hint": 1,
        },
        {
            "event_type": "death",
            "time_ms": 60000,
            "xuid": "2535423456789",
            "gamertag": "Chocoboflor",
            "type_hint": 2,
        },
    ]


@pytest.fixture
def tmp_shared_db(tmp_path: Path) -> Path:
    """Crée une shared_matches.duckdb temporaire avec le schéma v5."""
    db_path = tmp_path / "warehouse" / "shared_matches.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))
    # Schéma minimal pour les tests (cohérent avec schema_v5.sql)
    conn.execute("""
        CREATE TABLE match_registry (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            playlist_id VARCHAR,
            playlist_name VARCHAR,
            map_id VARCHAR,
            map_name VARCHAR,
            pair_id VARCHAR,
            pair_name VARCHAR,
            game_variant_id VARCHAR,
            game_variant_name VARCHAR,
            mode_category VARCHAR,
            is_ranked BOOLEAN DEFAULT FALSE,
            is_firefight BOOLEAN DEFAULT FALSE,
            duration_seconds INTEGER,
            team_0_score SMALLINT,
            team_1_score SMALLINT,
            backfill_completed INTEGER DEFAULT 0,
            participants_loaded BOOLEAN DEFAULT FALSE,
            events_loaded BOOLEAN DEFAULT FALSE,
            medals_loaded BOOLEAN DEFAULT FALSE,
            first_sync_by VARCHAR,
            first_sync_at TIMESTAMP,
            last_updated_at TIMESTAMP,
            player_count SMALLINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE match_participants (
            match_id VARCHAR NOT NULL,
            xuid VARCHAR NOT NULL,
            gamertag VARCHAR,
            team_id INTEGER,
            outcome INTEGER,
            rank SMALLINT,
            score INTEGER,
            kills SMALLINT,
            deaths SMALLINT,
            assists SMALLINT,
            shots_fired INTEGER,
            shots_hit INTEGER,
            damage_dealt FLOAT,
            damage_taken FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, xuid)
        )
    """)
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS highlight_events_id_seq;
        CREATE TABLE highlight_events (
            id INTEGER PRIMARY KEY DEFAULT nextval('highlight_events_id_seq'),
            match_id VARCHAR NOT NULL,
            event_type VARCHAR NOT NULL,
            time_ms INTEGER,
            xuid VARCHAR,
            gamertag VARCHAR,
            type_hint INTEGER,
            raw_json VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE medals_earned (
            match_id VARCHAR NOT NULL,
            xuid VARCHAR NOT NULL,
            medal_name_id BIGINT NOT NULL,
            count SMALLINT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, xuid, medal_name_id)
        )
    """)
    conn.execute("""
        CREATE TABLE xuid_aliases (
            xuid VARCHAR PRIMARY KEY,
            gamertag VARCHAR NOT NULL,
            last_seen TIMESTAMP,
            source VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.close()
    return db_path


@pytest.fixture
def tmp_player_db(tmp_path: Path) -> Path:
    """Crée un chemin pour la player DB (sera initialisée par le moteur)."""
    db_path = tmp_path / "players" / "Chocoboflor" / "stats.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


@pytest.fixture
def engine_with_shared(tmp_player_db: Path, tmp_shared_db: Path) -> DuckDBSyncEngine:
    """Crée un DuckDBSyncEngine configuré avec shared_matches."""
    engine = DuckDBSyncEngine(
        tmp_player_db,
        xuid="2535423456789",
        gamertag="Chocoboflor",
        shared_db_path=tmp_shared_db,
    )
    return engine


@pytest.fixture
def engine_without_shared(tmp_player_db: Path) -> DuckDBSyncEngine:
    """Crée un DuckDBSyncEngine SANS shared_matches (mode legacy v4)."""
    # Utiliser un chemin inexistant pour shared
    engine = DuckDBSyncEngine(
        tmp_player_db,
        xuid="2535423456789",
        gamertag="Chocoboflor",
        shared_db_path=Path("/nonexistent/shared_matches.duckdb"),
    )
    return engine


# =============================================================================
# Tests extract_match_registry_data()
# =============================================================================


class TestExtractMatchRegistryData:
    """Tests d'extraction des données communes de match_registry."""

    def test_basic_extraction(self, sample_match_json: dict) -> None:
        """Extraction basique des données communes."""
        data = extract_match_registry_data(sample_match_json)
        assert data is not None
        assert data["match_id"] == "shared-test-match-001"
        assert data["playlist_name"] == "Ranked Arena"
        assert data["map_name"] == "Recharge"
        assert data["pair_name"] == "Recharge - Slayer"
        assert data["game_variant_name"] == "Slayer"
        assert data["duration_seconds"] == 750  # 12m30s
        assert data["team_0_score"] == 50
        assert data["team_1_score"] == 47
        assert data["start_time"] is not None
        assert data["end_time"] is not None
        assert data["is_firefight"] is False

    def test_missing_match_id(self) -> None:
        """Retourne None si MatchId manquant."""
        result = extract_match_registry_data({})
        assert result is None

    def test_missing_match_info(self) -> None:
        """Retourne None si MatchInfo manquant."""
        result = extract_match_registry_data({"MatchId": "test"})
        assert result is None

    def test_missing_start_time(self) -> None:
        """Retourne None si StartTime manquant."""
        result = extract_match_registry_data(
            {
                "MatchId": "test",
                "MatchInfo": {},
            }
        )
        assert result is None

    def test_no_teams(self) -> None:
        """team_0_score et team_1_score sont None si pas d'équipes."""
        data = extract_match_registry_data(
            {
                "MatchId": "test-ffa",
                "MatchInfo": {
                    "StartTime": "2024-01-01T00:00:00Z",
                },
            }
        )
        assert data is not None
        assert data["team_0_score"] is None
        assert data["team_1_score"] is None

    def test_firefight_detection(self) -> None:
        """Détecte correctement un match Firefight."""
        data = extract_match_registry_data(
            {
                "MatchId": "test-ff",
                "MatchInfo": {
                    "StartTime": "2024-01-01T00:00:00Z",
                    "UgcGameVariant": {
                        "AssetId": "variant-ff",
                        "PublicName": "Firefight Heroic",
                    },
                },
            }
        )
        assert data is not None
        assert data["is_firefight"] is True


# =============================================================================
# Tests _extract_team_scores_by_id()
# =============================================================================


class TestExtractTeamScoresById:
    """Tests d'extraction des scores par team_id."""

    def test_two_teams(self) -> None:
        """Extraction correcte pour 2 équipes."""
        from src.data.sync.transformers import _extract_team_scores_by_id

        t0, t1 = _extract_team_scores_by_id(
            {
                "Teams": [
                    {"TeamId": 0, "TotalPoints": 50},
                    {"TeamId": 1, "TotalPoints": 45},
                ]
            }
        )
        assert t0 == 50
        assert t1 == 45

    def test_no_teams(self) -> None:
        """Retourne (None, None) si pas de teams."""
        from src.data.sync.transformers import _extract_team_scores_by_id

        t0, t1 = _extract_team_scores_by_id({})
        assert t0 is None
        assert t1 is None


# =============================================================================
# Tests extract_all_medals()
# =============================================================================


class TestExtractAllMedals:
    """Tests d'extraction des médailles de tous les joueurs."""

    def test_all_players_medals(self, sample_match_json: dict) -> None:
        """Extrait les médailles de TOUS les joueurs."""
        medals = extract_all_medals(sample_match_json)
        assert len(medals) > 0

        # Vérifier qu'on a des médailles pour les 2 joueurs
        xuids_with_medals = {m.xuid for m in medals}
        assert "2535423456789" in xuids_with_medals
        assert "2533987654321" in xuids_with_medals

        # Vérifier les attributs
        for medal in medals:
            assert medal.match_id == "shared-test-match-001"
            assert medal.medal_name_id > 0
            assert medal.count > 0

    def test_empty_match(self) -> None:
        """Retourne une liste vide pour un match sans MatchId."""
        medals = extract_all_medals({})
        assert medals == []


# =============================================================================
# Tests DuckDBSyncEngine — shared_enabled / connexion
# =============================================================================


class TestSyncEngineSharedConfig:
    """Tests de la configuration shared du sync engine."""

    def test_shared_enabled(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """shared_enabled est True quand la DB existe."""
        assert engine_with_shared.shared_enabled is True

    def test_shared_disabled_when_missing(self, engine_without_shared: DuckDBSyncEngine) -> None:
        """shared_enabled est False quand la DB n'existe pas."""
        assert engine_without_shared.shared_enabled is False

    def test_get_shared_connection(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """_get_shared_connection() retourne une connexion valide."""
        conn = engine_with_shared._get_shared_connection()
        assert conn is not None

        # Vérifier qu'on peut lire le schéma
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables " "WHERE table_schema = 'main'"
        ).fetchall()
        table_names = {r[0] for r in tables}
        assert "match_registry" in table_names
        assert "match_participants" in table_names

        engine_with_shared.close()

    def test_get_shared_connection_returns_none_when_missing(
        self, engine_without_shared: DuckDBSyncEngine
    ) -> None:
        """_get_shared_connection() retourne None si la DB n'existe pas."""
        conn = engine_without_shared._get_shared_connection()
        assert conn is None
        engine_without_shared.close()

    def test_close_closes_both_connections(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """close() ferme les deux connexions (player + shared)."""
        # Ouvrir les deux connexions
        engine_with_shared._get_connection()
        engine_with_shared._get_shared_connection()

        assert engine_with_shared._connection is not None
        assert engine_with_shared._shared_connection is not None

        engine_with_shared.close()

        assert engine_with_shared._connection is None
        assert engine_with_shared._shared_connection is None

    def test_auto_detection_shared_path(self, tmp_path: Path) -> None:
        """shared_db_path est auto-détecté depuis player_db_path."""
        player_db = tmp_path / "data" / "players" / "Test" / "stats.duckdb"
        player_db.parent.mkdir(parents=True, exist_ok=True)

        engine = DuckDBSyncEngine(
            player_db,
            xuid="123",
            gamertag="Test",
        )
        expected = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"
        assert engine._shared_db_path == expected
        engine.close()


# =============================================================================
# Tests DuckDBSyncEngine — Insertions shared
# =============================================================================


class TestSyncEngineSharedInsertions:
    """Tests d'insertion dans shared_matches.duckdb."""

    def test_insert_shared_registry(
        self, engine_with_shared: DuckDBSyncEngine, sample_match_json: dict
    ) -> None:
        """Insertion dans match_registry."""
        shared_conn = engine_with_shared._get_shared_connection()
        assert shared_conn is not None

        data = extract_match_registry_data(sample_match_json)
        assert data is not None

        engine_with_shared._insert_shared_registry(shared_conn, data)

        row = shared_conn.execute(
            "SELECT match_id, playlist_name, map_name, team_0_score, team_1_score "
            "FROM match_registry WHERE match_id = ?",
            ("shared-test-match-001",),
        ).fetchone()

        assert row is not None
        assert row[0] == "shared-test-match-001"
        assert row[1] == "Ranked Arena"
        assert row[2] == "Recharge"
        assert row[3] == 50
        assert row[4] == 47

        engine_with_shared.close()

    def test_insert_shared_participants(
        self, engine_with_shared: DuckDBSyncEngine, sample_match_json: dict
    ) -> None:
        """Insertion des participants dans shared."""
        shared_conn = engine_with_shared._get_shared_connection()
        assert shared_conn is not None

        participants = extract_participants(sample_match_json)
        engine_with_shared._insert_shared_participants(shared_conn, participants)

        rows = shared_conn.execute(
            "SELECT xuid, gamertag, kills, deaths FROM match_participants "
            "WHERE match_id = 'shared-test-match-001' ORDER BY rank"
        ).fetchall()

        assert len(rows) == 2
        # Premier par rang (Chocoboflor)
        assert rows[0][1] == "Chocoboflor"
        assert rows[0][2] == 20  # kills
        assert rows[0][3] == 10  # deaths

        engine_with_shared.close()

    def test_insert_shared_medals(
        self, engine_with_shared: DuckDBSyncEngine, sample_match_json: dict
    ) -> None:
        """Insertion des médailles de TOUS les joueurs dans shared."""
        shared_conn = engine_with_shared._get_shared_connection()
        assert shared_conn is not None

        medals = extract_all_medals(sample_match_json)
        engine_with_shared._insert_shared_medals(shared_conn, medals)

        rows = shared_conn.execute(
            "SELECT xuid, medal_name_id, count FROM medals_earned "
            "WHERE match_id = 'shared-test-match-001' ORDER BY xuid, medal_name_id"
        ).fetchall()

        assert len(rows) >= 4  # 2 médailles pour Choco + 2 pour Madina
        xuids = {r[0] for r in rows}
        assert "2535423456789" in xuids
        assert "2533987654321" in xuids

        engine_with_shared.close()

    def test_insert_shared_events(
        self,
        engine_with_shared: DuckDBSyncEngine,
        sample_highlight_events: list,
    ) -> None:
        """Insertion des highlight events dans shared."""
        shared_conn = engine_with_shared._get_shared_connection()
        assert shared_conn is not None

        from src.data.sync.transformers import transform_highlight_events

        event_rows = transform_highlight_events(sample_highlight_events, "shared-test-match-001")
        engine_with_shared._insert_shared_events(shared_conn, event_rows)

        count = shared_conn.execute(
            "SELECT COUNT(*) FROM highlight_events " "WHERE match_id = 'shared-test-match-001'"
        ).fetchone()[0]

        assert count == 2

        engine_with_shared.close()

    def test_insert_shared_aliases(
        self, engine_with_shared: DuckDBSyncEngine, sample_match_json: dict
    ) -> None:
        """Insertion des aliases dans shared."""
        shared_conn = engine_with_shared._get_shared_connection()
        assert shared_conn is not None

        from src.data.sync.transformers import extract_aliases

        aliases = extract_aliases(sample_match_json)
        engine_with_shared._insert_shared_aliases(shared_conn, aliases)

        rows = shared_conn.execute(
            "SELECT xuid, gamertag FROM xuid_aliases ORDER BY xuid"
        ).fetchall()

        assert len(rows) == 2
        gamertags = {r[1] for r in rows}
        assert "Chocoboflor" in gamertags
        assert "Madina97294" in gamertags

        engine_with_shared.close()

    def test_insert_shared_registry_idempotent(
        self, engine_with_shared: DuckDBSyncEngine, sample_match_json: dict
    ) -> None:
        """INSERT OR IGNORE : la 2e insertion ne crée pas de doublon."""
        shared_conn = engine_with_shared._get_shared_connection()
        assert shared_conn is not None

        data = extract_match_registry_data(sample_match_json)
        assert data is not None

        engine_with_shared._insert_shared_registry(shared_conn, data)
        engine_with_shared._insert_shared_registry(shared_conn, data)

        count = shared_conn.execute(
            "SELECT COUNT(*) FROM match_registry WHERE match_id = ?",
            ("shared-test-match-001",),
        ).fetchone()[0]

        assert count == 1

        engine_with_shared.close()


# =============================================================================
# Tests _process_new_match() et _process_known_match()
# =============================================================================


class TestProcessNewMatch:
    """Tests du flow de sync pour un nouveau match (v5)."""

    @pytest.fixture
    def mock_client(self, sample_match_json: dict, sample_highlight_events: list) -> AsyncMock:
        """Client API mocké."""
        client = AsyncMock()
        client.get_match_stats = AsyncMock(return_value=sample_match_json)
        client.get_highlight_events = AsyncMock(return_value=sample_highlight_events)
        client.get_skill_stats = AsyncMock(return_value=None)
        return client

    @pytest.mark.asyncio
    async def test_process_new_match_inserts_to_shared(
        self,
        engine_with_shared: DuckDBSyncEngine,
        mock_client: AsyncMock,
    ) -> None:
        """Un nouveau match s'insère dans shared ET dans player DB."""
        options = SyncOptions(
            with_highlight_events=True,
            with_skill=False,
            with_aliases=True,
            with_participants=True,
        )

        result = await engine_with_shared._process_new_match(
            mock_client,
            "shared-test-match-001",
            options,
        )

        assert result["inserted"] is True
        assert result["mode"] == "new_match"
        assert result.get("error") is None

        # Vérifier dans shared
        shared_conn = engine_with_shared._get_shared_connection()
        assert shared_conn is not None

        registry = shared_conn.execute(
            "SELECT match_id, player_count, participants_loaded, events_loaded, medals_loaded "
            "FROM match_registry WHERE match_id = 'shared-test-match-001'"
        ).fetchone()
        assert registry is not None
        assert registry[1] == 1  # player_count
        assert registry[2] is True  # participants_loaded
        assert registry[3] is True  # events_loaded
        assert registry[4] is True  # medals_loaded

        # Vérifier participants
        p_count = shared_conn.execute(
            "SELECT COUNT(*) FROM match_participants WHERE match_id = 'shared-test-match-001'"
        ).fetchone()[0]
        assert p_count == 2

        # Vérifier médailles (tous les joueurs)
        m_count = shared_conn.execute(
            "SELECT COUNT(DISTINCT xuid) FROM medals_earned WHERE match_id = 'shared-test-match-001'"
        ).fetchone()[0]
        assert m_count == 2

        # Vérifier dans player DB
        player_conn = engine_with_shared._get_connection()
        match = player_conn.execute(
            "SELECT match_id, kills, deaths FROM match_stats WHERE match_id = 'shared-test-match-001'"
        ).fetchone()
        assert match is not None
        assert match[1] == 20  # kills du joueur principal
        assert match[2] == 10

        engine_with_shared.close()

    @pytest.mark.asyncio
    async def test_process_new_match_without_events(
        self,
        engine_with_shared: DuckDBSyncEngine,
    ) -> None:
        """Nouveau match sans highlight events → events_loaded = False."""
        match_json = {
            "MatchId": "no-events-match",
            "MatchInfo": {
                "StartTime": "2024-06-15T19:00:00Z",
                "Playlist": {
                    "AssetId": "playlist-social",
                    "PublicName": "Social Slayer",
                },
                "MapVariant": {
                    "AssetId": "map-streets",
                    "PublicName": "Streets",
                },
                "PlaylistMapModePair": {
                    "AssetId": "pair-streets-slayer",
                    "PublicName": "Streets - Slayer",
                },
                "UgcGameVariant": {
                    "AssetId": "variant-slayer",
                    "PublicName": "Slayer",
                },
            },
            "Teams": [
                {"TeamId": 0, "TotalPoints": 25},
                {"TeamId": 1, "TotalPoints": 50},
            ],
            "Players": [
                {
                    "PlayerId": "xuid(2535423456789)",
                    "PlayerGamertag": "Chocoboflor",
                    "Outcome": 3,
                    "LastTeamId": 0,
                    "Rank": 2,
                    "PlayerTeamStats": [
                        {
                            "Stats": {
                                "CoreStats": {
                                    "Kills": 5,
                                    "Deaths": 15,
                                    "Assists": 2,
                                    "Accuracy": 0.30,
                                }
                            }
                        }
                    ],
                },
            ],
        }

        client = AsyncMock()
        client.get_match_stats = AsyncMock(return_value=match_json)
        client.get_highlight_events = AsyncMock(return_value=[])
        client.get_skill_stats = AsyncMock(return_value=None)

        options = SyncOptions(
            with_highlight_events=True,
            with_skill=False,
        )

        result = await engine_with_shared._process_new_match(
            client,
            "no-events-match",
            options,
        )
        assert result["inserted"] is True

        shared_conn = engine_with_shared._get_shared_connection()
        row = shared_conn.execute(
            "SELECT events_loaded FROM match_registry WHERE match_id = 'no-events-match'"
        ).fetchone()
        assert row is not None
        assert row[0] is False  # Pas d'events

        engine_with_shared.close()


class TestProcessKnownMatch:
    """Tests du flow de sync pour un match déjà connu (v5)."""

    @pytest.fixture
    def mock_client(self, sample_match_json: dict) -> AsyncMock:
        """Client API mocké."""
        client = AsyncMock()
        client.get_match_stats = AsyncMock(return_value=sample_match_json)
        client.get_highlight_events = AsyncMock(return_value=[])
        client.get_skill_stats = AsyncMock(return_value=None)
        return client

    @pytest.mark.asyncio
    async def test_process_known_match_increments_player_count(
        self,
        engine_with_shared: DuckDBSyncEngine,
        mock_client: AsyncMock,
        sample_match_json: dict,
    ) -> None:
        """Un match connu incrémente player_count dans shared."""
        # 1. Insérer d'abord comme nouveau match
        shared_conn = engine_with_shared._get_shared_connection()
        assert shared_conn is not None

        data = extract_match_registry_data(sample_match_json)
        assert data is not None
        engine_with_shared._insert_shared_registry(shared_conn, data)
        shared_conn.execute(
            "UPDATE match_registry SET player_count = 1, participants_loaded = TRUE, "
            "events_loaded = TRUE, medals_loaded = TRUE WHERE match_id = ?",
            ("shared-test-match-001",),
        )

        # 2. Traiter comme match connu
        registry = (0, True, True, True, 1)  # backfill, participants, events, medals, count
        options = SyncOptions(with_highlight_events=True)

        result = await engine_with_shared._process_known_match(
            mock_client,
            "shared-test-match-001",
            registry,
            options,
        )

        assert result["inserted"] is True
        assert result["mode"] == "known_match"

        # 3. Vérifier que player_count a été incrémenté
        row = shared_conn.execute(
            "SELECT player_count FROM match_registry WHERE match_id = 'shared-test-match-001'"
        ).fetchone()
        assert row is not None
        assert row[0] == 2  # 1 → 2

        engine_with_shared.close()

    @pytest.mark.asyncio
    async def test_process_known_match_saves_api_call_for_events(
        self,
        engine_with_shared: DuckDBSyncEngine,
        mock_client: AsyncMock,
        sample_match_json: dict,
    ) -> None:
        """Un match connu avec events_loaded=True économise l'appel API events."""
        shared_conn = engine_with_shared._get_shared_connection()
        assert shared_conn is not None

        data = extract_match_registry_data(sample_match_json)
        assert data is not None
        engine_with_shared._insert_shared_registry(shared_conn, data)
        shared_conn.execute(
            "UPDATE match_registry SET player_count = 1, participants_loaded = TRUE, "
            "events_loaded = TRUE, medals_loaded = TRUE WHERE match_id = ?",
            ("shared-test-match-001",),
        )

        registry = (0, True, True, True, 1)
        options = SyncOptions(with_highlight_events=True)

        result = await engine_with_shared._process_known_match(
            mock_client,
            "shared-test-match-001",
            registry,
            options,
        )

        assert result["api_calls_saved"] >= 1
        # get_highlight_events ne devrait PAS avoir été appelé
        mock_client.get_highlight_events.assert_not_awaited()

        engine_with_shared.close()

    @pytest.mark.asyncio
    async def test_process_known_match_backfills_missing_medals(
        self,
        engine_with_shared: DuckDBSyncEngine,
        mock_client: AsyncMock,
        sample_match_json: dict,
    ) -> None:
        """Un match connu avec medals_loaded=False fait le backfill des médailles."""
        shared_conn = engine_with_shared._get_shared_connection()
        assert shared_conn is not None

        data = extract_match_registry_data(sample_match_json)
        assert data is not None
        engine_with_shared._insert_shared_registry(shared_conn, data)
        shared_conn.execute(
            "UPDATE match_registry SET player_count = 1, participants_loaded = TRUE, "
            "events_loaded = TRUE, medals_loaded = FALSE WHERE match_id = ?",
            ("shared-test-match-001",),
        )

        registry = (0, True, True, False, 1)  # medals_loaded = False
        options = SyncOptions()

        result = await engine_with_shared._process_known_match(
            mock_client,
            "shared-test-match-001",
            registry,
            options,
        )

        assert result["inserted"] is True

        # Vérifier que les médailles ont été backfillées
        medal_count = shared_conn.execute(
            "SELECT COUNT(*) FROM medals_earned WHERE match_id = 'shared-test-match-001'"
        ).fetchone()[0]
        assert medal_count > 0

        # Vérifier que medals_loaded est maintenant TRUE
        loaded = shared_conn.execute(
            "SELECT medals_loaded FROM match_registry WHERE match_id = 'shared-test-match-001'"
        ).fetchone()[0]
        assert loaded is True

        engine_with_shared.close()


# =============================================================================
# Tests _process_single_match() — Dispatch shared vs legacy
# =============================================================================


class TestProcessSingleMatchDispatch:
    """Tests du dispatch entre new/known/legacy dans _process_single_match."""

    @pytest.mark.asyncio
    async def test_dispatches_to_new_match_when_not_in_registry(
        self,
        engine_with_shared: DuckDBSyncEngine,
    ) -> None:
        """Dispatche vers _process_new_match quand le match n'est pas dans le registre."""
        match_json = {
            "MatchId": "dispatch-new-test",
            "MatchInfo": {
                "StartTime": "2024-06-15T20:00:00Z",
                "Playlist": {"AssetId": "p1", "PublicName": "Test PL"},
                "MapVariant": {"AssetId": "m1", "PublicName": "Test Map"},
                "PlaylistMapModePair": {"AssetId": "pm1", "PublicName": "Test - Slayer"},
                "UgcGameVariant": {"AssetId": "gv1", "PublicName": "Slayer"},
            },
            "Teams": [{"TeamId": 0, "TotalPoints": 50}],
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
                                    "Kills": 10,
                                    "Deaths": 5,
                                    "Assists": 3,
                                    "Accuracy": 0.45,
                                }
                            }
                        }
                    ],
                }
            ],
        }

        client = AsyncMock()
        client.get_match_stats = AsyncMock(return_value=match_json)
        client.get_highlight_events = AsyncMock(return_value=[])
        client.get_skill_stats = AsyncMock(return_value=None)

        options = SyncOptions(with_highlight_events=False)

        result = await engine_with_shared._process_single_match(
            client,
            "dispatch-new-test",
            options,
        )

        assert result["inserted"] is True
        assert result["mode"] == "new_match"

        engine_with_shared.close()

    @pytest.mark.asyncio
    async def test_dispatches_to_known_match_when_in_registry(
        self,
        engine_with_shared: DuckDBSyncEngine,
        sample_match_json: dict,
    ) -> None:
        """Dispatche vers _process_known_match quand le match existe dans le registre."""
        # Pré-insérer le match dans le registre
        shared_conn = engine_with_shared._get_shared_connection()
        assert shared_conn is not None

        data = extract_match_registry_data(sample_match_json)
        assert data is not None
        engine_with_shared._insert_shared_registry(shared_conn, data)
        shared_conn.execute(
            "UPDATE match_registry SET player_count = 1, participants_loaded = TRUE, "
            "events_loaded = TRUE, medals_loaded = TRUE WHERE match_id = ?",
            ("shared-test-match-001",),
        )

        client = AsyncMock()
        client.get_match_stats = AsyncMock(return_value=sample_match_json)
        client.get_highlight_events = AsyncMock(return_value=[])
        client.get_skill_stats = AsyncMock(return_value=None)

        options = SyncOptions(with_highlight_events=True)

        result = await engine_with_shared._process_single_match(
            client,
            "shared-test-match-001",
            options,
        )

        assert result["inserted"] is True
        assert result["mode"] == "known_match"

        engine_with_shared.close()

    @pytest.mark.asyncio
    async def test_falls_back_to_legacy_without_shared(
        self,
        engine_without_shared: DuckDBSyncEngine,
    ) -> None:
        """Sin shared_matches.duckdb, utilise le mode legacy."""
        match_json = {
            "MatchId": "legacy-test",
            "MatchInfo": {
                "StartTime": "2024-06-15T20:00:00Z",
                "Playlist": {"AssetId": "p1", "PublicName": "Test PL"},
                "MapVariant": {"AssetId": "m1", "PublicName": "Test Map"},
                "PlaylistMapModePair": {"AssetId": "pm1", "PublicName": "Test - Slayer"},
                "UgcGameVariant": {"AssetId": "gv1", "PublicName": "Slayer"},
            },
            "Teams": [{"TeamId": 0, "TotalPoints": 50}],
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
                                    "Kills": 10,
                                    "Deaths": 5,
                                    "Assists": 3,
                                    "Accuracy": 0.45,
                                }
                            }
                        }
                    ],
                }
            ],
        }

        client = AsyncMock()
        client.get_match_stats = AsyncMock(return_value=match_json)
        client.get_highlight_events = AsyncMock(return_value=[])
        client.get_skill_stats = AsyncMock(return_value=None)

        options = SyncOptions(with_highlight_events=False)

        result = await engine_without_shared._process_single_match(
            client,
            "legacy-test",
            options,
        )

        assert result["inserted"] is True
        # Pas de clé "mode" dans le résultat legacy
        assert "mode" not in result

        engine_without_shared.close()


# =============================================================================
# Tests _compute_backfill_mask()
# =============================================================================


class TestComputeBackfillMask:
    """Tests du calcul de bitmask backfill."""

    def test_default_options(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """Le masque par défaut inclut medals, accuracy, shots, etc."""
        options = SyncOptions()
        mask = engine_with_shared._compute_backfill_mask(options)
        assert mask > 0

    def test_with_skill_option(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """L'option with_skill ajoute les flags skill et enemy_mmr."""
        from src.data.sync.migrations import BACKFILL_FLAGS

        options = SyncOptions(with_skill=True)
        mask = engine_with_shared._compute_backfill_mask(options)
        assert mask & BACKFILL_FLAGS["skill"]
        assert mask & BACKFILL_FLAGS["enemy_mmr"]
        engine_with_shared.close()

    def test_with_events_option(self, engine_with_shared: DuckDBSyncEngine) -> None:
        """L'option with_highlight_events ajoute le flag events."""
        from src.data.sync.migrations import BACKFILL_FLAGS

        options = SyncOptions(with_highlight_events=True)
        mask = engine_with_shared._compute_backfill_mask(options)
        assert mask & BACKFILL_FLAGS["events"]
        engine_with_shared.close()
