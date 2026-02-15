"""Tests unitaires pour DuckDBRepository v5 — shared_matches.

Teste le refactoring Sprint 4 :
- ATTACH de shared_matches.duckdb en READ_ONLY
- Lecture depuis shared.match_participants, shared.medals_earned, shared.highlight_events
- Fallback sur tables locales si shared indisponible
- Résolution de gamertags avec cascade shared → local
- Factory avec shared_db_path

Philosophie : chaque test est autonome avec des fixtures tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from src.data.repositories.duckdb_repo import DuckDBRepository
from src.data.repositories.factory import get_repository

# =============================================================================
# Helpers & Fixtures
# =============================================================================

PLAYER_XUID = "xuid_player_1"
TEAMMATE_XUID = "xuid_player_2"
MATCH_ID_1 = "match_001"
MATCH_ID_2 = "match_002"


def _create_player_db(db_path: Path) -> None:
    """Crée une DB joueur minimale (schéma v4) pour les tests."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP NOT NULL,
            map_id VARCHAR,
            map_name VARCHAR,
            playlist_id VARCHAR,
            playlist_name VARCHAR,
            pair_id VARCHAR,
            pair_name VARCHAR,
            game_variant_id VARCHAR,
            game_variant_name VARCHAR,
            outcome INTEGER,
            team_id INTEGER,
            kda FLOAT,
            max_killing_spree INTEGER,
            headshot_kills INTEGER,
            avg_life_seconds FLOAT,
            time_played_seconds INTEGER,
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER,
            accuracy FLOAT,
            my_team_score INTEGER,
            enemy_team_score INTEGER,
            team_mmr FLOAT,
            enemy_mmr FLOAT,
            personal_score INTEGER,
            is_firefight BOOLEAN DEFAULT FALSE
        )
    """)
    conn.execute("""
        CREATE TABLE medals_earned (
            match_id VARCHAR,
            medal_name_id BIGINT,
            count SMALLINT,
            PRIMARY KEY (match_id, medal_name_id)
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
            raw_json VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE match_participants (
            match_id VARCHAR NOT NULL,
            xuid VARCHAR NOT NULL,
            team_id INTEGER,
            outcome INTEGER,
            gamertag VARCHAR,
            rank SMALLINT,
            score INTEGER,
            kills SMALLINT,
            deaths SMALLINT,
            assists SMALLINT,
            shots_fired INTEGER,
            shots_hit INTEGER,
            damage_dealt FLOAT,
            damage_taken FLOAT,
            PRIMARY KEY (match_id, xuid)
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
    conn.execute("""
        CREATE TABLE antagonists (
            opponent_xuid VARCHAR PRIMARY KEY,
            opponent_gamertag VARCHAR,
            kills_dealt INTEGER DEFAULT 0,
            deaths_suffered INTEGER DEFAULT 0,
            net_kills INTEGER GENERATED ALWAYS AS (kills_dealt - deaths_suffered) VIRTUAL,
            matches_fought INTEGER DEFAULT 0
        )
    """)
    # Insérer un match de test
    conn.execute("""
        INSERT INTO match_stats VALUES (
            'match_001', '2025-01-15 10:00:00', 'map1', 'Aquarius', 'pl1',
            'Ranked Arena', 'pair1', 'Slayer', 'gv1', 'Slayer', 2, 0,
            2.5, 5, 3, 30.0, 600, 15, 6, 4, 55.0, 50, 48, 1500.0, 1480.0, 2500, FALSE
        )
    """)
    conn.execute("""
        INSERT INTO match_stats VALUES (
            'match_002', '2025-01-15 11:00:00', 'map2', 'Streets', 'pl2',
            'Quick Play', 'pair2', 'CTF', 'gv2', 'CTF', 3, 1,
            1.0, 2, 1, 20.0, 720, 8, 8, 2, 45.0, 1, 3, 1400.0, 1420.0, 1800, FALSE
        )
    """)
    conn.close()


def _create_shared_db(db_path: Path) -> None:
    """Crée une shared_matches.duckdb avec le schéma v5."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

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
            killer_xuid VARCHAR,
            killer_gamertag VARCHAR,
            victim_xuid VARCHAR,
            victim_gamertag VARCHAR,
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
    conn.execute("""
        CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY,
            description VARCHAR NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO schema_version (version, description) VALUES (1, 'v5.0 test')")

    # -- Données de test --

    # Registry
    conn.execute("""
        INSERT INTO match_registry (match_id, start_time, playlist_name, map_name, mode_category, player_count)
        VALUES ('match_001', '2025-01-15 10:00:00', 'Ranked Arena', 'Aquarius', 'pvp', 8)
    """)
    conn.execute("""
        INSERT INTO match_registry (match_id, start_time, playlist_name, map_name, mode_category, player_count)
        VALUES ('match_002', '2025-01-15 11:00:00', 'Quick Play', 'Streets', 'pvp', 8)
    """)

    # Participants (roster complet : 4 joueurs par match)
    for match_id in [MATCH_ID_1, MATCH_ID_2]:
        conn.execute(f"""
            INSERT INTO match_participants (match_id, xuid, gamertag, team_id, outcome, rank, score, kills, deaths, assists)
            VALUES ('{match_id}', '{PLAYER_XUID}', 'PlayerOne', 0, 2, 1, 2500, 15, 6, 4)
        """)
        conn.execute(f"""
            INSERT INTO match_participants (match_id, xuid, gamertag, team_id, outcome, rank, score, kills, deaths, assists)
            VALUES ('{match_id}', '{TEAMMATE_XUID}', 'TeammateTwo', 0, 2, 2, 2200, 12, 7, 5)
        """)
        conn.execute(f"""
            INSERT INTO match_participants (match_id, xuid, gamertag, team_id, outcome, rank, score, kills, deaths, assists)
            VALUES ('{match_id}', 'xuid_enemy_1', 'EnemyAlpha', 1, 3, 3, 1800, 8, 10, 2)
        """)
        conn.execute(f"""
            INSERT INTO match_participants (match_id, xuid, gamertag, team_id, outcome, rank, score, kills, deaths, assists)
            VALUES ('{match_id}', 'xuid_enemy_2', 'EnemyBeta', 1, 3, 4, 1500, 5, 12, 1)
        """)

    # Medals
    conn.execute(f"""
        INSERT INTO medals_earned (match_id, xuid, medal_name_id, count) VALUES
        ('{MATCH_ID_1}', '{PLAYER_XUID}', 1512363953, 3),
        ('{MATCH_ID_1}', '{PLAYER_XUID}', 100000001, 5),
        ('{MATCH_ID_1}', '{TEAMMATE_XUID}', 1512363953, 1),
        ('{MATCH_ID_2}', '{PLAYER_XUID}', 100000001, 2)
    """)

    # Highlight events (v5 structure: killer_xuid/victim_xuid)
    conn.execute(f"""
        INSERT INTO highlight_events (match_id, event_type, time_ms, killer_xuid, killer_gamertag, victim_xuid, victim_gamertag)
        VALUES ('{MATCH_ID_1}', 'kill', 5000, '{PLAYER_XUID}', 'PlayerOne', 'xuid_enemy_1', 'EnemyAlpha')
    """)
    conn.execute(f"""
        INSERT INTO highlight_events (match_id, event_type, time_ms, killer_xuid, killer_gamertag, victim_xuid, victim_gamertag)
        VALUES ('{MATCH_ID_1}', 'death', 8000, 'xuid_enemy_2', 'EnemyBeta', '{PLAYER_XUID}', 'PlayerOne')
    """)
    conn.execute(f"""
        INSERT INTO highlight_events (match_id, event_type, time_ms, killer_xuid, killer_gamertag, victim_xuid, victim_gamertag)
        VALUES ('{MATCH_ID_1}', 'kill', 12000, '{PLAYER_XUID}', 'PlayerOne', 'xuid_enemy_2', 'EnemyBeta')
    """)

    # xuid_aliases
    conn.execute(f"""
        INSERT INTO xuid_aliases (xuid, gamertag, source) VALUES
        ('{PLAYER_XUID}', 'PlayerOne', 'api'),
        ('{TEAMMATE_XUID}', 'TeammateTwo', 'api'),
        ('xuid_enemy_1', 'EnemyAlpha', 'api'),
        ('xuid_enemy_2', 'EnemyBeta', 'api')
    """)

    conn.close()


@pytest.fixture
def tmp_player_db(tmp_path: Path) -> Path:
    """Crée une DB joueur temporaire."""
    db_path = tmp_path / "data" / "players" / "TestPlayer" / "stats.duckdb"
    _create_player_db(db_path)
    return db_path


@pytest.fixture
def tmp_shared_db(tmp_path: Path) -> Path:
    """Crée une shared_matches.duckdb temporaire."""
    db_path = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"
    _create_shared_db(db_path)
    return db_path


@pytest.fixture
def repo_v5(tmp_player_db: Path, tmp_shared_db: Path) -> DuckDBRepository:
    """DuckDBRepository avec shared_matches attaché (mode v5)."""
    return DuckDBRepository(
        player_db_path=tmp_player_db,
        xuid=PLAYER_XUID,
        shared_db_path=tmp_shared_db,
        gamertag="TestPlayer",
        read_only=True,
    )


@pytest.fixture
def repo_v4(tmp_player_db: Path) -> DuckDBRepository:
    """DuckDBRepository sans shared_matches (mode v4 legacy)."""
    return DuckDBRepository(
        player_db_path=tmp_player_db,
        xuid=PLAYER_XUID,
        shared_db_path=Path("/nonexistent/shared_matches.duckdb"),
        gamertag="TestPlayer",
        read_only=True,
    )


# =============================================================================
# Tests ATTACH & Propriétés
# =============================================================================


class TestSharedAttach:
    """Tests de l'attachement de shared_matches.duckdb."""

    def test_has_shared_true_when_attached(self, repo_v5: DuckDBRepository):
        """shared_matches.duckdb est attaché correctement."""
        repo_v5._get_connection()  # Initialise la connexion
        assert repo_v5.has_shared is True

    def test_has_shared_false_when_not_available(self, repo_v4: DuckDBRepository):
        """Sans shared_matches, has_shared retourne False."""
        repo_v4._get_connection()
        assert repo_v4.has_shared is False

    def test_shared_db_path_auto_detection(self, tmp_path: Path):
        """Auto-détection de shared_matches.duckdb depuis le chemin joueur."""
        db_path = tmp_path / "data" / "players" / "TestPlayer" / "stats.duckdb"
        _create_player_db(db_path)
        repo = DuckDBRepository(
            player_db_path=db_path,
            xuid=PLAYER_XUID,
        )
        expected = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"
        assert repo._shared_db_path == expected

    def test_has_shared_table_true(self, repo_v5: DuckDBRepository):
        """_has_shared_table détecte les tables du schéma shared."""
        repo_v5._get_connection()
        assert repo_v5._has_shared_table("match_participants") is True
        assert repo_v5._has_shared_table("match_registry") is True
        assert repo_v5._has_shared_table("medals_earned") is True
        assert repo_v5._has_shared_table("highlight_events") is True
        assert repo_v5._has_shared_table("xuid_aliases") is True

    def test_has_shared_table_false_nonexistent(self, repo_v5: DuckDBRepository):
        """_has_shared_table retourne False pour une table inexistante."""
        repo_v5._get_connection()
        assert repo_v5._has_shared_table("nonexistent_table") is False

    def test_has_shared_table_false_when_not_attached(self, repo_v4: DuckDBRepository):
        """_has_shared_table retourne False sans shared attaché."""
        repo_v4._get_connection()
        assert repo_v4._has_shared_table("match_participants") is False

    def test_storage_info_includes_shared(self, repo_v5: DuckDBRepository):
        """get_storage_info inclut has_shared et shared_db_path."""
        info = repo_v5.get_storage_info()
        assert "has_shared" in info
        assert info["has_shared"] is True
        assert "shared_db_path" in info


# =============================================================================
# Tests Lecture Participants (v5 shared)
# =============================================================================


class TestSharedParticipants:
    """Tests de lecture depuis shared.match_participants."""

    def test_load_match_players_stats_from_shared(self, repo_v5: DuckDBRepository):
        """load_match_players_stats lit depuis shared (4 joueurs dans le roster)."""
        stats = repo_v5.load_match_players_stats(MATCH_ID_1)
        assert len(stats) == 4
        # Vérifier que les données sont complètes
        player = next(s for s in stats if s["xuid"] == PLAYER_XUID)
        assert player["gamertag"] == "PlayerOne"
        assert player["kills"] == 15
        assert player["deaths"] == 6
        assert player["rank"] == 1

    def test_load_match_players_stats_fallback_v4(self, repo_v4: DuckDBRepository):
        """Sans shared, fallback sur la table locale (vide ici)."""
        stats = repo_v4.load_match_players_stats(MATCH_ID_1)
        # La table locale match_participants est vide, donc 0 résultats
        assert stats == []

    def test_load_match_player_gamertags_from_shared(self, repo_v5: DuckDBRepository):
        """load_match_player_gamertags résout via shared."""
        gamertags = repo_v5.load_match_player_gamertags(MATCH_ID_1)
        assert gamertags[PLAYER_XUID] == "PlayerOne"
        assert gamertags[TEAMMATE_XUID] == "TeammateTwo"
        assert gamertags["xuid_enemy_1"] == "EnemyAlpha"
        assert len(gamertags) == 4

    def test_has_match_participants_with_shared(self, repo_v5: DuckDBRepository):
        """has_match_participants retourne True avec shared."""
        assert repo_v5.has_match_participants() is True

    def test_load_matches_with_teammate_shared(self, repo_v5: DuckDBRepository):
        """load_matches_with_teammate trouve les matchs communs via shared."""
        match_ids = repo_v5.load_matches_with_teammate(TEAMMATE_XUID)
        assert MATCH_ID_1 in match_ids
        assert MATCH_ID_2 in match_ids

    def test_load_same_team_match_ids_shared(self, repo_v5: DuckDBRepository):
        """load_same_team_match_ids utilise shared.match_participants (même team_id)."""
        match_ids = repo_v5.load_same_team_match_ids(TEAMMATE_XUID)
        assert MATCH_ID_1 in match_ids
        assert MATCH_ID_2 in match_ids

    def test_load_same_team_excludes_enemies(self, repo_v5: DuckDBRepository):
        """load_same_team_match_ids n'inclut pas les adversaires."""
        match_ids = repo_v5.load_same_team_match_ids("xuid_enemy_1")
        assert match_ids == []  # team_id différent


# =============================================================================
# Tests Médailles (v5 shared)
# =============================================================================


class TestSharedMedals:
    """Tests de lecture depuis shared.medals_earned."""

    def test_load_top_medals_from_shared(self, repo_v5: DuckDBRepository):
        """load_top_medals lit depuis shared.medals_earned (filtré par xuid)."""
        medals = repo_v5.load_top_medals([MATCH_ID_1, MATCH_ID_2])
        assert len(medals) >= 1
        # medal_name_id 100000001 : 5 + 2 = 7 au total
        medal_100 = next((m for m in medals if m[0] == 100000001), None)
        assert medal_100 is not None
        assert medal_100[1] == 7

    def test_load_match_medals_from_shared(self, repo_v5: DuckDBRepository):
        """load_match_medals lit les médailles du joueur principal depuis shared."""
        medals = repo_v5.load_match_medals(MATCH_ID_1)
        assert len(medals) == 2  # 2 médailles distinctes pour player dans match_001
        name_ids = {m["name_id"] for m in medals}
        assert 1512363953 in name_ids
        assert 100000001 in name_ids

    def test_count_medal_by_match_shared(self, repo_v5: DuckDBRepository):
        """count_medal_by_match filtre par xuid depuis shared."""
        counts = repo_v5.count_medal_by_match([MATCH_ID_1], medal_name_id=1512363953)
        assert counts.get(MATCH_ID_1) == 3

    def test_count_perfect_kills_shared(self, repo_v5: DuckDBRepository):
        """count_perfect_kills_by_match utilise shared."""
        counts = repo_v5.count_perfect_kills_by_match([MATCH_ID_1])
        assert counts.get(MATCH_ID_1) == 3

    def test_medals_fallback_v4(self, repo_v4: DuckDBRepository):
        """Sans shared, medals sont lues depuis la table locale (vide)."""
        medals = repo_v4.load_match_medals(MATCH_ID_1)
        assert medals == []


# =============================================================================
# Tests Highlight Events (v5 shared)
# =============================================================================


class TestSharedHighlightEvents:
    """Tests de lecture depuis shared.highlight_events."""

    def test_load_highlight_events_from_shared(self, repo_v5: DuckDBRepository):
        """load_highlight_events lit depuis shared avec mapping xuid/gamertag."""
        events = repo_v5.load_highlight_events(MATCH_ID_1)
        assert len(events) == 3
        # Vérifier le mapping xuid pour event_type='kill' → killer_xuid
        kill_events = [e for e in events if e["event_type"] == "kill"]
        assert len(kill_events) == 2
        assert kill_events[0]["xuid"] == PLAYER_XUID
        # Vérifier le mapping xuid pour event_type='death' → victim_xuid
        death_events = [e for e in events if e["event_type"] == "death"]
        assert len(death_events) == 1
        assert death_events[0]["xuid"] == PLAYER_XUID  # victim_xuid

    def test_load_first_event_times_kill_shared(self, repo_v5: DuckDBRepository):
        """load_first_event_times('Kill') utilise shared.highlight_events."""
        first_kills = repo_v5.load_first_event_times([MATCH_ID_1], event_type="Kill")
        assert MATCH_ID_1 in first_kills
        assert first_kills[MATCH_ID_1] == 5000  # Premier kill à 5000ms

    def test_load_first_event_times_death_shared(self, repo_v5: DuckDBRepository):
        """load_first_event_times('Death') utilise victim_xuid depuis shared."""
        first_deaths = repo_v5.load_first_event_times([MATCH_ID_1], event_type="Death")
        assert MATCH_ID_1 in first_deaths
        assert first_deaths[MATCH_ID_1] == 8000  # Première death à 8000ms

    def test_get_first_kill_death_times_shared(self, repo_v5: DuckDBRepository):
        """get_first_kill_death_times retourne les deux dicts."""
        first_kills, first_deaths = repo_v5.get_first_kill_death_times([MATCH_ID_1])
        assert first_kills[MATCH_ID_1] == 5000
        assert first_deaths[MATCH_ID_1] == 8000

    def test_highlight_events_fallback_v4(self, repo_v4: DuckDBRepository):
        """Sans shared, highlight_events lit depuis la table locale (vide)."""
        events = repo_v4.load_highlight_events(MATCH_ID_1)
        assert events == []


# =============================================================================
# Tests Résolution Gamertag (v5 shared)
# =============================================================================


class TestSharedGamertagResolution:
    """Tests de la cascade de résolution gamertag avec shared."""

    def test_resolve_gamertag_from_shared_participants(self, repo_v5: DuckDBRepository):
        """resolve_gamertag résout via shared.match_participants en priorité."""
        gt = repo_v5.resolve_gamertag(PLAYER_XUID, match_id=MATCH_ID_1)
        assert gt == "PlayerOne"

    def test_resolve_gamertag_from_shared_aliases(self, repo_v5: DuckDBRepository):
        """resolve_gamertag résout via shared.xuid_aliases (sans match_id)."""
        gt = repo_v5.resolve_gamertag(PLAYER_XUID)
        assert gt == "PlayerOne"

    def test_resolve_gamertag_enemy(self, repo_v5: DuckDBRepository):
        """resolve_gamertag fonctionne pour les adversaires."""
        gt = repo_v5.resolve_gamertag("xuid_enemy_1", match_id=MATCH_ID_1)
        assert gt == "EnemyAlpha"

    def test_resolve_gamertags_batch_shared(self, repo_v5: DuckDBRepository):
        """resolve_gamertags_batch résout plusieurs XUIDs."""
        result = repo_v5.resolve_gamertags_batch(
            [PLAYER_XUID, TEAMMATE_XUID, "xuid_enemy_1"],
            match_id=MATCH_ID_1,
        )
        assert result[PLAYER_XUID] == "PlayerOne"
        assert result[TEAMMATE_XUID] == "TeammateTwo"
        assert result["xuid_enemy_1"] == "EnemyAlpha"

    def test_resolve_gamertag_unknown_xuid(self, repo_v5: DuckDBRepository):
        """resolve_gamertag retourne None pour un XUID inconnu."""
        gt = repo_v5.resolve_gamertag("xuid_unknown_999")
        assert gt is None


# =============================================================================
# Tests list_other_player_xuids (v5 shared)
# =============================================================================


class TestSharedListPlayers:
    """Tests de list_other_player_xuids avec shared."""

    def test_list_other_xuids_shared(self, repo_v5: DuckDBRepository):
        """list_other_player_xuids utilise shared.match_participants."""
        xuids = repo_v5.list_other_player_xuids()
        assert TEAMMATE_XUID in xuids
        assert "xuid_enemy_1" in xuids
        assert "xuid_enemy_2" in xuids
        assert PLAYER_XUID not in xuids  # Exclut le joueur principal


# =============================================================================
# Tests Factory avec shared_db_path
# =============================================================================


class TestFactoryShared:
    """Tests de la factory avec shared_db_path."""

    def test_get_repository_with_shared(self, tmp_player_db: Path, tmp_shared_db: Path):
        """get_repository accepte shared_db_path."""
        repo = get_repository(
            str(tmp_player_db),
            PLAYER_XUID,
            shared_db_path=tmp_shared_db,
            gamertag="TestPlayer",
        )
        repo._get_connection()
        assert repo.has_shared is True

    def test_get_repository_without_shared(self, tmp_player_db: Path):
        """get_repository fonctionne sans shared_db_path (auto-détection)."""
        repo = get_repository(
            str(tmp_player_db),
            PLAYER_XUID,
            gamertag="TestPlayer",
        )
        # shared_db_path est auto-détecté mais le fichier n'existe pas
        repo._get_connection()
        assert repo.has_shared is False


# =============================================================================
# Tests Non-Régression v4 (fallback)
# =============================================================================


class TestV4Fallback:
    """Tests que le mode v4 (sans shared) fonctionne toujours."""

    def test_load_matches_still_works(self, repo_v4: DuckDBRepository):
        """load_matches fonctionne sans shared (lecture match_stats locale)."""
        matches = repo_v4.load_matches()
        assert len(matches) == 2
        assert matches[0].match_id == MATCH_ID_1

    def test_get_match_count_still_works(self, repo_v4: DuckDBRepository):
        """get_match_count fonctionne sans shared."""
        assert repo_v4.get_match_count() == 2

    def test_load_matches_v5_still_reads_match_stats(self, repo_v5: DuckDBRepository):
        """load_matches lit toujours depuis match_stats (pas modifié en Sprint 4)."""
        matches = repo_v5.load_matches()
        assert len(matches) == 2
        assert matches[0].map_name == "Aquarius"
