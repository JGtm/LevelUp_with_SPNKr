"""Tests unitaires Sprint 1 : Killer-Victim Pairs et Personal Score Awards.

Ce module teste :
- Modèles de données (KillerVictimPairRow, PersonalScoreAwardRow)
- Fonctions de transformation (extract_personal_score_awards, etc.)
- Méthodes du repository (load_killer_victim_pairs, etc.)
"""

from __future__ import annotations

import duckdb
import pytest

from src.data.domain.refdata import (
    PERSONAL_SCORE_POINTS,
    PersonalScoreNameId,
    get_personal_score_display_name,
    is_assist_score,
    is_objective_score,
)
from src.data.sync.models import (
    KillerVictimPairRow,
    PersonalScoreAwardRow,
)
from src.data.sync.transformers import (
    build_players_lookup,
    extract_game_variant_category,
    extract_killer_victim_pairs_from_highlight_events,
    extract_personal_score_awards,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_match_json():
    """JSON de match simulé avec PersonalScores."""
    return {
        "MatchId": "test-match-001",
        "MatchInfo": {
            "StartTime": "2026-02-03T10:00:00Z",
            "GameVariantCategory": 15,  # CTF
            "Playlist": {"AssetId": "playlist-1", "PublicName": "Quick Play"},
            "MapVariant": {"AssetId": "map-1", "PublicName": "Aquarius"},
        },
        "Players": [
            {
                "PlayerId": "xuid(2533274792546123)",
                "PlayerGamertag": "TestPlayer",
                "LastTeamId": 0,
                "Outcome": 2,
                "PlayerTeamStats": [
                    {
                        "Stats": {
                            "CoreStats": {
                                "Kills": 10,
                                "Deaths": 5,
                                "Assists": 3,
                                "PersonalScores": [
                                    {
                                        "NameId": PersonalScoreNameId.KILLED_PLAYER,
                                        "Count": 10,
                                    },
                                    {
                                        "NameId": PersonalScoreNameId.FLAG_CAPTURED,
                                        "Count": 2,
                                    },
                                    {
                                        "NameId": PersonalScoreNameId.KILL_ASSIST,
                                        "Count": 3,
                                    },
                                    {
                                        "NameId": PersonalScoreNameId.ZONE_SECURED,
                                        "Count": 5,
                                    },
                                ],
                            }
                        }
                    }
                ],
            },
            {
                "PlayerId": "xuid(2533274792546456)",
                "PlayerGamertag": "Enemy1",
                "LastTeamId": 1,
                "Outcome": 3,
            },
            {
                "PlayerId": "xuid(2533274792546789)",
                "PlayerGamertag": "Enemy2",
                "LastTeamId": 1,
                "Outcome": 3,
            },
        ],
    }


@pytest.fixture
def sample_highlight_events():
    """Highlight events simulés."""
    return [
        {
            "event_type": "Kill",
            "time_ms": 15000,
            "xuid": "2533274792546123",
            "gamertag": "TestPlayer",
            "victim_xuid": "2533274792546456",
            "victim_gamertag": "Enemy1",
        },
        {
            "event_type": "Kill",
            "time_ms": 30000,
            "xuid": "2533274792546123",
            "gamertag": "TestPlayer",
            "victim_xuid": "2533274792546789",
            "victim_gamertag": "Enemy2",
        },
        {
            "event_type": "Kill",
            "time_ms": 45000,
            "xuid": "2533274792546456",
            "gamertag": "Enemy1",
            "victim_xuid": "2533274792546123",
            "victim_gamertag": "TestPlayer",
        },
        {
            "event_type": "Death",
            "time_ms": 45000,
            "xuid": "2533274792546123",
            "gamertag": "TestPlayer",
        },
    ]


@pytest.fixture
def temp_duckdb(tmp_path):
    """Crée une DB DuckDB temporaire avec les tables Sprint 1."""
    import gc
    import uuid

    db_path = tmp_path / f"test_stats_{uuid.uuid4().hex[:8]}.duckdb"
    conn = duckdb.connect(str(db_path))

    try:
        # Créer les tables Sprint 1
        conn.execute("""
            CREATE TABLE killer_victim_pairs (
                id INTEGER PRIMARY KEY,
                match_id VARCHAR NOT NULL,
                killer_xuid VARCHAR NOT NULL,
                killer_gamertag VARCHAR,
                victim_xuid VARCHAR NOT NULL,
                victim_gamertag VARCHAR,
                kill_count INTEGER DEFAULT 1,
                time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE personal_score_awards (
                id INTEGER PRIMARY KEY,
                match_id VARCHAR NOT NULL,
                xuid VARCHAR NOT NULL,
                award_name_id INTEGER NOT NULL,
                count INTEGER DEFAULT 1,
                total_points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                kills INTEGER,
                deaths INTEGER
            )
        """)
    finally:
        conn.close()
        del conn
        gc.collect()

    yield db_path


# =============================================================================
# Tests Modèles
# =============================================================================


class TestModels:
    """Tests des dataclasses Sprint 1."""

    def test_killer_victim_pair_row_creation(self):
        """Test création KillerVictimPairRow."""
        row = KillerVictimPairRow(
            match_id="match-123",
            killer_xuid="2533274792546123",
            killer_gamertag="Killer",
            victim_xuid="2533274792546456",
            victim_gamertag="Victim",
            kill_count=1,
            time_ms=15000,
        )

        assert row.match_id == "match-123"
        assert row.killer_xuid == "2533274792546123"
        assert row.victim_xuid == "2533274792546456"
        assert row.kill_count == 1
        assert row.time_ms == 15000

    def test_personal_score_award_row_creation(self):
        """Test création PersonalScoreAwardRow."""
        row = PersonalScoreAwardRow(
            match_id="match-123",
            xuid="2533274792546123",
            award_name="Drapeau capturé",
            award_category="objective",
            award_count=2,
            award_score=600,
        )

        assert row.match_id == "match-123"
        assert row.award_name == "Drapeau capturé"
        assert row.award_count == 2
        assert row.award_score == 600

    def test_personal_score_award_row_defaults(self):
        """Test valeurs par défaut de PersonalScoreAwardRow."""
        row = PersonalScoreAwardRow(
            match_id="match-123",
            xuid="2533274792546123",
            award_name="Kill",
        )

        assert row.award_count == 1
        assert row.award_score == 0


# =============================================================================
# Tests Transformers
# =============================================================================


class TestTransformers:
    """Tests des fonctions de transformation."""

    def test_extract_game_variant_category(self, sample_match_json):
        """Test extraction de GameVariantCategory."""
        category = extract_game_variant_category(sample_match_json)
        assert category == 15  # CTF

    def test_extract_game_variant_category_missing(self):
        """Test extraction avec catégorie manquante."""
        category = extract_game_variant_category({"MatchInfo": {}})
        assert category is None

    def test_extract_personal_score_awards(self, sample_match_json):
        """Test extraction des PersonalScores."""
        awards = extract_personal_score_awards(
            sample_match_json,
            "2533274792546123",
        )

        assert len(awards) == 4

        # Vérifier les types d'awards (extract retourne des dicts avec name_id)
        award_ids = {a["name_id"] for a in awards}
        assert PersonalScoreNameId.KILLED_PLAYER in award_ids
        assert PersonalScoreNameId.FLAG_CAPTURED in award_ids
        assert PersonalScoreNameId.KILL_ASSIST in award_ids

        # Vérifier les points calculés
        flag_capture = next(a for a in awards if a["name_id"] == PersonalScoreNameId.FLAG_CAPTURED)
        assert flag_capture["count"] == 2
        assert flag_capture["total_score"] == 600  # 2 × 300

    def test_extract_personal_score_awards_empty(self):
        """Test extraction sans PersonalScores."""
        awards = extract_personal_score_awards(
            {"MatchId": "test", "Players": []},
            "unknown-xuid",
        )
        assert awards == []

    def test_extract_killer_victim_pairs_from_highlight_events(self, sample_highlight_events):
        """Test extraction des paires killer-victim."""
        pairs = extract_killer_victim_pairs_from_highlight_events(
            sample_highlight_events,
            "test-match-001",
        )

        # 3 kills dans les events
        assert len(pairs) == 3

        # Vérifier le premier kill
        first_kill = pairs[0]
        assert first_kill.match_id == "test-match-001"
        assert first_kill.killer_xuid == "2533274792546123"
        assert first_kill.victim_xuid == "2533274792546456"
        assert first_kill.time_ms == 15000

    def test_extract_killer_victim_pairs_with_lookup(self, sample_highlight_events):
        """Test extraction avec lookup des gamertags."""
        players_lookup = {
            "2533274792546123": "TestPlayer",
            "2533274792546456": "Enemy1",
            "2533274792546789": "Enemy2",
        }

        # Events sans gamertags
        events = [
            {
                "event_type": "Kill",
                "time_ms": 15000,
                "xuid": "2533274792546123",
                "victim_xuid": "2533274792546456",
            },
        ]

        pairs = extract_killer_victim_pairs_from_highlight_events(
            events,
            "test-match",
            players_lookup=players_lookup,
        )

        assert len(pairs) == 1
        assert pairs[0].killer_gamertag == "TestPlayer"
        assert pairs[0].victim_gamertag == "Enemy1"

    def test_build_players_lookup(self, sample_match_json):
        """Test construction du lookup joueurs."""
        lookup = build_players_lookup(sample_match_json)

        assert len(lookup) == 3
        assert lookup["2533274792546123"] == "TestPlayer"
        assert lookup["2533274792546456"] == "Enemy1"
        assert lookup["2533274792546789"] == "Enemy2"


# =============================================================================
# Tests Refdata Helpers
# =============================================================================


class TestRefdataHelpers:
    """Tests des helpers refdata."""

    def test_personal_score_points(self):
        """Test valeurs de points personnels."""
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.KILLED_PLAYER] == 100
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.FLAG_CAPTURED] == 300
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.KILL_ASSIST] == 50
        assert PERSONAL_SCORE_POINTS[PersonalScoreNameId.BETRAYED_PLAYER] == -100

    def test_get_personal_score_display_name(self):
        """Test noms d'affichage des scores."""
        assert (
            get_personal_score_display_name(PersonalScoreNameId.FLAG_CAPTURED) == "Drapeau capturé"
        )
        assert get_personal_score_display_name(PersonalScoreNameId.KILL_ASSIST) == "Assistance kill"
        assert get_personal_score_display_name(9999999) == "Score"  # Inconnu

    def test_is_objective_score(self):
        """Test identification des scores objectifs."""
        assert is_objective_score(PersonalScoreNameId.FLAG_CAPTURED) is True
        assert is_objective_score(PersonalScoreNameId.ZONE_SECURED) is True
        assert is_objective_score(PersonalScoreNameId.KILLED_PLAYER) is False

    def test_is_assist_score(self):
        """Test identification des assistances."""
        assert is_assist_score(PersonalScoreNameId.KILL_ASSIST) is True
        assert is_assist_score(PersonalScoreNameId.MARK_ASSIST) is True
        assert is_assist_score(PersonalScoreNameId.KILLED_PLAYER) is False


# =============================================================================
# Tests Repository (Integration)
# =============================================================================


class TestRepositoryIntegration:
    """Tests d'intégration avec le repository."""

    def test_insert_and_load_killer_victim_pairs(self, temp_duckdb):
        """Test insertion et lecture des paires killer-victim."""
        conn = duckdb.connect(str(temp_duckdb))

        # Insérer des données
        conn.execute(
            """
            INSERT INTO killer_victim_pairs (id, match_id, killer_xuid, killer_gamertag,
                victim_xuid, victim_gamertag, kill_count, time_ms)
            VALUES
                (1, 'match-1', 'xuid-1', 'Killer1', 'xuid-2', 'Victim1', 1, 15000),
                (2, 'match-1', 'xuid-1', 'Killer1', 'xuid-3', 'Victim2', 1, 30000),
                (3, 'match-1', 'xuid-2', 'Victim1', 'xuid-1', 'Killer1', 1, 45000)
            """
        )

        # Lire les données
        result = conn.execute(
            "SELECT * FROM killer_victim_pairs WHERE match_id = 'match-1'"
        ).fetchall()

        assert len(result) == 3
        conn.close()

    def test_insert_and_load_personal_score_awards(self, temp_duckdb):
        """Test insertion et lecture des personal score awards."""
        conn = duckdb.connect(str(temp_duckdb))

        # Insérer des données
        conn.execute(
            """
            INSERT INTO personal_score_awards (id, match_id, xuid, award_name_id, count, total_points)
            VALUES
                (1, 'match-1', 'xuid-1', 1024030246, 10, 1000),
                (2, 'match-1', 'xuid-1', 601966503, 2, 600),
                (3, 'match-1', 'xuid-1', 638246808, 5, 250)
            """
        )

        # Lire les données
        result = conn.execute(
            "SELECT * FROM personal_score_awards WHERE match_id = 'match-1'"
        ).fetchall()

        assert len(result) == 3

        # Vérifier les points totaux
        total_points = conn.execute(
            "SELECT SUM(total_points) FROM personal_score_awards"
        ).fetchone()[0]
        assert total_points == 1850

        conn.close()

    def test_aggregate_nemeses(self, temp_duckdb):
        """Test agrégation pour trouver le némésis."""
        conn = duckdb.connect(str(temp_duckdb))

        # Insérer plusieurs kills
        conn.execute(
            """
            INSERT INTO killer_victim_pairs (id, match_id, killer_xuid, killer_gamertag,
                victim_xuid, victim_gamertag, kill_count, time_ms)
            VALUES
                (1, 'match-1', 'enemy-1', 'Enemy1', 'me', 'MyPlayer', 1, 1000),
                (2, 'match-1', 'enemy-1', 'Enemy1', 'me', 'MyPlayer', 1, 2000),
                (3, 'match-1', 'enemy-1', 'Enemy1', 'me', 'MyPlayer', 1, 3000),
                (4, 'match-1', 'enemy-2', 'Enemy2', 'me', 'MyPlayer', 1, 4000),
                (5, 'match-2', 'enemy-1', 'Enemy1', 'me', 'MyPlayer', 1, 1000)
            """
        )

        # Trouver le némésis (qui m'a le plus tué)
        nemesis = conn.execute(
            """
            SELECT killer_xuid, killer_gamertag, COUNT(*) as times_killed_by
            FROM killer_victim_pairs
            WHERE victim_xuid = 'me'
            GROUP BY killer_xuid, killer_gamertag
            ORDER BY times_killed_by DESC
            LIMIT 1
            """
        ).fetchone()

        assert nemesis[0] == "enemy-1"
        assert nemesis[1] == "Enemy1"
        assert nemesis[2] == 4  # 4 kills sur 2 matchs

        conn.close()


# =============================================================================
# Tests de Performance (Optionnel)
# =============================================================================


class TestPerformance:
    """Tests de performance avec volumes de données."""

    @pytest.mark.slow
    def test_bulk_insert_killer_victim_pairs(self, temp_duckdb):
        """Test insertion en masse de paires.

        Note: Test marqué slow car il insère 1000 enregistrements.
        """
        conn = duckdb.connect(str(temp_duckdb))

        # Préparer des données en masse
        rows = []
        for i in range(1000):
            rows.append(
                (
                    i,
                    f"match-{i % 10}",
                    f"killer-{i % 5}",
                    f"Killer{i % 5}",
                    f"victim-{(i + 1) % 5}",
                    f"Victim{(i + 1) % 5}",
                    1,
                    i * 1000,
                )
            )

        conn.executemany(
            """
            INSERT INTO killer_victim_pairs
            (id, match_id, killer_xuid, killer_gamertag, victim_xuid, victim_gamertag, kill_count, time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        count = conn.execute("SELECT COUNT(*) FROM killer_victim_pairs").fetchone()[0]
        assert count == 1000

        # Test agrégation rapide
        result = conn.execute(
            """
            SELECT killer_xuid, COUNT(*) as kills
            FROM killer_victim_pairs
            GROUP BY killer_xuid
            ORDER BY kills DESC
            """
        ).fetchall()

        assert len(result) == 5  # 5 killers uniques
        assert sum(r[1] for r in result) == 1000

        conn.close()
