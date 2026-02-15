"""Tests Sprint 7 — Repository shared v5 : ATTACH, queries cross-DB, edge cases.

Complète tests/test_duckdb_repository_v5.py avec des tests additionnels
pour améliorer la couverture du Sprint 7.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb
import polars as pl
import pytest

from src.data.repositories.duckdb_repo import DuckDBRepository
from src.data.repositories.factory import get_repository

# =============================================================================
# Helpers (repris de test_duckdb_repository_v5.py pour isolation)
# =============================================================================

PLAYER_XUID = "xuid_test_s7"
MATCH_IDS = [f"s7_match_{i:03d}" for i in range(5)]


def _create_player_db(db_path: Path) -> None:
    """Crée une DB joueur minimale pour les tests Sprint 7."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP NOT NULL,
            map_id VARCHAR, map_name VARCHAR,
            playlist_id VARCHAR, playlist_name VARCHAR,
            pair_id VARCHAR, pair_name VARCHAR,
            game_variant_id VARCHAR, game_variant_name VARCHAR,
            outcome INTEGER, team_id INTEGER,
            kda FLOAT, max_killing_spree INTEGER,
            headshot_kills INTEGER, avg_life_seconds FLOAT,
            time_played_seconds INTEGER,
            kills INTEGER, deaths INTEGER, assists INTEGER,
            accuracy FLOAT,
            my_team_score INTEGER, enemy_team_score INTEGER,
            team_mmr FLOAT, enemy_mmr FLOAT,
            personal_score INTEGER,
            is_firefight BOOLEAN DEFAULT FALSE
        )
    """)
    conn.execute("""
        CREATE TABLE medals_earned (
            match_id VARCHAR, medal_name_id BIGINT, count SMALLINT,
            PRIMARY KEY (match_id, medal_name_id)
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
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS highlight_events_id_seq;
        CREATE TABLE highlight_events (
            id INTEGER PRIMARY KEY DEFAULT nextval('highlight_events_id_seq'),
            match_id VARCHAR NOT NULL,
            event_type VARCHAR NOT NULL,
            time_ms INTEGER, xuid VARCHAR,
            gamertag VARCHAR, type_hint INTEGER, raw_json VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE match_participants (
            match_id VARCHAR NOT NULL, xuid VARCHAR NOT NULL,
            team_id INTEGER, outcome INTEGER, gamertag VARCHAR,
            rank SMALLINT, score INTEGER,
            kills SMALLINT, deaths SMALLINT, assists SMALLINT,
            shots_fired INTEGER, shots_hit INTEGER,
            damage_dealt FLOAT, damage_taken FLOAT,
            PRIMARY KEY (match_id, xuid)
        )
    """)
    conn.execute("""
        CREATE TABLE xuid_aliases (
            xuid VARCHAR PRIMARY KEY,
            gamertag VARCHAR NOT NULL,
            last_seen TIMESTAMP, source VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insérer 5 matchs
    base_time = datetime(2025, 6, 1, 10, 0, tzinfo=timezone.utc)
    for i, mid in enumerate(MATCH_IDS):
        conn.execute(
            """INSERT INTO match_stats VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
            )""",
            (
                mid,
                base_time,
                f"map_{i}",
                f"Map{i}",
                f"pl_{i}",
                "Ranked Arena",
                None,
                None,
                None,
                None,
                2,
                0,
                2.0 + i * 0.1,
                i + 2,
                i + 1,
                30.0,
                600,
                10 + i,
                5 + i,
                3,
                50.0,
                50,
                48,
                1500.0,
                1480.0,
                2000,
                False,
            ),
        )

    # Antagonists
    conn.execute("""
        INSERT INTO antagonists (opponent_xuid, opponent_gamertag, kills_dealt, deaths_suffered, matches_fought)
        VALUES ('xuid_rival1', 'Rival1', 50, 30, 15)
    """)

    conn.close()


def _create_shared_db(db_path: Path) -> None:
    """Crée une shared_matches.duckdb avec le schéma v5."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE match_registry (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP NOT NULL, end_time TIMESTAMP,
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
            rank SMALLINT, score INTEGER,
            kills SMALLINT, deaths SMALLINT, assists SMALLINT,
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
            time_ms INTEGER,
            killer_xuid VARCHAR, killer_gamertag VARCHAR,
            victim_xuid VARCHAR, victim_gamertag VARCHAR,
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
    conn.execute("""
        CREATE TABLE killer_victim_pairs (
            match_id VARCHAR NOT NULL,
            killer_xuid VARCHAR NOT NULL,
            killer_gamertag VARCHAR,
            victim_xuid VARCHAR NOT NULL,
            victim_gamertag VARCHAR,
            kill_count INTEGER DEFAULT 1,
            time_ms INTEGER,
            is_validated BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY,
            description VARCHAR NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO schema_version VALUES (1, 'v5.0 s7 test', CURRENT_TIMESTAMP)")

    # Insérer les mêmes 5 matchs dans le registre + participants
    base_time = datetime(2025, 6, 1, 10, 0, tzinfo=timezone.utc)
    for i, mid in enumerate(MATCH_IDS):
        conn.execute(
            """INSERT INTO match_registry (
                match_id, start_time, playlist_name, map_name,
                mode_category, duration_seconds, team_0_score, team_1_score,
                player_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mid, base_time, "Ranked Arena", f"Map{i}", "Arena", 600, 50, 48, 3),
        )
        # Joueur principal + un adversaire
        conn.execute(
            """INSERT INTO match_participants VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
            )""",
            (
                mid,
                PLAYER_XUID,
                "TestPlayer",
                0,
                2,
                1,
                2000,
                10 + i,
                5 + i,
                3,
                200,
                100,
                3000.0,
                2500.0,
            ),
        )
        conn.execute(
            """INSERT INTO match_participants VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
            )""",
            (mid, "xuid_enemy1", "Enemy1", 1, 3, 2, 1800, 8, 12, 2, 180, 80, 2500.0, 3000.0),
        )
        # Coéquipier (même team_id=0 que le joueur principal)
        conn.execute(
            """INSERT INTO match_participants VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
            )""",
            (mid, "xuid_team1", "Teammate1", 0, 2, 2, 1500, 7, 6, 4, 150, 70, 2200.0, 2400.0),
        )

    # Médailles
    conn.execute("""
        INSERT INTO medals_earned VALUES
        ('s7_match_000', 'xuid_test_s7', 100, 3, CURRENT_TIMESTAMP),
        ('s7_match_000', 'xuid_test_s7', 200, 1, CURRENT_TIMESTAMP),
        ('s7_match_001', 'xuid_test_s7', 100, 2, CURRENT_TIMESTAMP)
    """)

    # Aliases
    conn.execute("""
        INSERT INTO xuid_aliases VALUES
        ('xuid_test_s7', 'TestPlayer', NULL, 'test', CURRENT_TIMESTAMP),
        ('xuid_enemy1', 'Enemy1', NULL, 'test', CURRENT_TIMESTAMP),
        ('xuid_team1', 'Teammate1', NULL, 'test', CURRENT_TIMESTAMP)
    """)

    conn.close()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def repo_with_shared(tmp_path: Path) -> DuckDBRepository:
    """Repository v5 avec shared_matches."""
    player_db = tmp_path / "player" / "stats.duckdb"
    shared_db = tmp_path / "shared_matches.duckdb"
    _create_player_db(player_db)
    _create_shared_db(shared_db)
    repo = DuckDBRepository(
        player_db,
        PLAYER_XUID,
        shared_db_path=shared_db,
        gamertag="TestPlayer",
    )
    yield repo
    repo.close()


@pytest.fixture
def repo_v4_only(tmp_path: Path) -> DuckDBRepository:
    """Repository v4 sans shared."""
    player_db = tmp_path / "player" / "stats.duckdb"
    _create_player_db(player_db)
    repo = DuckDBRepository(
        player_db,
        PLAYER_XUID,
        gamertag="TestPlayer",
    )
    yield repo
    repo.close()


# =============================================================================
# Tests Repository context manager
# =============================================================================


class TestRepositoryContextManager:
    """Tests pour l'utilisation en context manager."""

    def test_with_statement(self, tmp_path: Path) -> None:
        player_db = tmp_path / "player" / "stats.duckdb"
        _create_player_db(player_db)
        with DuckDBRepository(player_db, PLAYER_XUID, gamertag="Test") as repo:
            count = repo.get_match_count()
            assert count == 5

    def test_close_idempotent(self, repo_v4_only: DuckDBRepository) -> None:
        """Fermer 2 fois ne cause pas d'erreur."""
        repo_v4_only.close()
        repo_v4_only.close()


# =============================================================================
# Tests has_shared / storage_info
# =============================================================================


class TestSharedStatus:
    """Tests pour has_shared et get_storage_info."""

    def test_has_shared_true(self, repo_with_shared: DuckDBRepository) -> None:
        # Forcer l'initialisation de la connexion pour déclencher ATTACH
        _ = repo_with_shared.get_match_count()
        assert repo_with_shared.has_shared is True

    def test_has_shared_false(self, repo_v4_only: DuckDBRepository) -> None:
        assert repo_v4_only.has_shared is False

    def test_storage_info_structure(self, repo_with_shared: DuckDBRepository) -> None:
        info = repo_with_shared.get_storage_info()
        assert isinstance(info, dict)

    def test_xuid_property(self, repo_with_shared: DuckDBRepository) -> None:
        assert repo_with_shared.xuid == PLAYER_XUID


# =============================================================================
# Tests chargement matchs
# =============================================================================


class TestLoadMatchesShared:
    """Tests chargement de matchs via shared."""

    def test_load_all_matches(self, repo_with_shared: DuckDBRepository) -> None:
        matches = repo_with_shared.load_matches()
        assert len(matches) >= 5

    def test_load_matches_with_limit(self, repo_with_shared: DuckDBRepository) -> None:
        matches = repo_with_shared.load_matches(limit=3)
        assert len(matches) == 3

    def test_get_match_count(self, repo_with_shared: DuckDBRepository) -> None:
        count = repo_with_shared.get_match_count()
        assert count >= 5

    def test_load_recent_matches(self, repo_with_shared: DuckDBRepository) -> None:
        recent = repo_with_shared.load_recent_matches(limit=2)
        assert len(recent) == 2

    def test_load_matches_paginated(self, repo_with_shared: DuckDBRepository) -> None:
        matches, pages = repo_with_shared.load_matches_paginated(page=1, page_size=2)
        assert len(matches) == 2
        assert pages >= 3  # 5 matchs / 2 = 3 pages


class TestLoadMatchesFallbackV4:
    """Tests chargement en mode v4 (sans shared)."""

    def test_load_all_v4(self, repo_v4_only: DuckDBRepository) -> None:
        matches = repo_v4_only.load_matches()
        assert len(matches) == 5

    def test_get_match_count_v4(self, repo_v4_only: DuckDBRepository) -> None:
        assert repo_v4_only.get_match_count() == 5


# =============================================================================
# Tests Polars output
# =============================================================================


class TestPolarsOutput:
    """Tests pour les sorties Polars."""

    def test_load_matches_as_polars(self, repo_with_shared: DuckDBRepository) -> None:
        df = repo_with_shared.load_matches_as_polars()
        assert isinstance(df, pl.DataFrame)
        assert len(df) >= 5

    def test_load_match_stats_as_polars(self, repo_with_shared: DuckDBRepository) -> None:
        df = repo_with_shared.load_match_stats_as_polars()
        assert isinstance(df, pl.DataFrame)

    def test_polars_has_expected_columns(self, repo_with_shared: DuckDBRepository) -> None:
        """Les colonnes critiques sont présentes dans le DataFrame."""
        df = repo_with_shared.load_matches_as_polars()
        expected_cols = {"match_id", "kills", "deaths", "assists"}
        actual_cols = set(df.columns)
        assert expected_cols.issubset(
            actual_cols
        ), f"Colonnes manquantes : {expected_cols - actual_cols}"


# =============================================================================
# Tests médailles, coéquipiers, antagonistes
# =============================================================================


class TestMedalsShared:
    """Tests médailles depuis shared."""

    def test_load_top_medals(self, repo_with_shared: DuckDBRepository) -> None:
        medals = repo_with_shared.load_top_medals(MATCH_IDS, top_n=5)
        assert isinstance(medals, list)
        assert len(medals) > 0

    def test_load_match_medals(self, repo_with_shared: DuckDBRepository) -> None:
        medals = repo_with_shared.load_match_medals("s7_match_000")
        assert isinstance(medals, list)


class TestTeammatesAndAntagonists:
    """Tests coéquipiers et antagonistes."""

    def test_list_top_teammates(self, repo_with_shared: DuckDBRepository) -> None:
        teammates = repo_with_shared.list_top_teammates(limit=5)
        assert isinstance(teammates, list)
        assert len(teammates) > 0
        # Retourne list[tuple[xuid, matches_together]]
        assert teammates[0][0] == "xuid_team1"  # premier coéquipier par matches_together
        assert teammates[0][1] == 5  # 5 matchs en commun (un par match_id)

    def test_list_top_teammates_empty(self, tmp_path: Path) -> None:
        """Repo sans coéquipiers dans shared → liste vide."""
        player_db = tmp_path / "empty" / "stats.duckdb"
        player_db.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(player_db))
        conn.execute("""
            CREATE TABLE match_stats (match_id VARCHAR PRIMARY KEY, start_time TIMESTAMP NOT NULL,
            kills INTEGER, deaths INTEGER, assists INTEGER, outcome INTEGER,
            is_firefight BOOLEAN DEFAULT FALSE)
        """)
        conn.close()
        repo = DuckDBRepository(player_db, "xuid_empty", gamertag="Empty")
        teammates = repo.list_top_teammates()
        assert teammates == []
        repo.close()


# =============================================================================
# Tests query / query_df
# =============================================================================


class TestGenericQueries:
    """Tests pour query() et query_df()."""

    def test_query_returns_dicts(self, repo_with_shared: DuckDBRepository) -> None:
        results = repo_with_shared.query("SELECT match_id FROM match_stats LIMIT 3")
        assert isinstance(results, list)
        assert len(results) == 3
        assert "match_id" in results[0]

    def test_query_with_params(self, repo_with_shared: DuckDBRepository) -> None:
        results = repo_with_shared.query("SELECT match_id FROM match_stats WHERE outcome = ?", [2])
        assert all(r["match_id"].startswith("s7_") for r in results)

    def test_query_df_returns_polars(self, repo_with_shared: DuckDBRepository) -> None:
        df = repo_with_shared.query_df("SELECT match_id, kills FROM match_stats")
        assert isinstance(df, pl.DataFrame)
        assert "match_id" in df.columns
        assert "kills" in df.columns

    def test_has_table_existing(self, repo_with_shared: DuckDBRepository) -> None:
        assert repo_with_shared.has_table("match_stats") is True

    def test_has_table_nonexistent(self, repo_with_shared: DuckDBRepository) -> None:
        assert repo_with_shared.has_table("nonexistent_table") is False


# =============================================================================
# Tests factory
# =============================================================================


class TestFactory:
    """Tests pour get_repository et get_repository_from_profile."""

    def test_get_repository_creates_duckdb(self, tmp_path: Path) -> None:
        player_db = tmp_path / "factory" / "stats.duckdb"
        _create_player_db(player_db)
        repo = get_repository(player_db, PLAYER_XUID, gamertag="Factory")
        assert isinstance(repo, DuckDBRepository)
        repo.close()

    def test_get_repository_with_shared(self, tmp_path: Path) -> None:
        player_db = tmp_path / "factory" / "stats.duckdb"
        shared_db = tmp_path / "shared.duckdb"
        _create_player_db(player_db)
        _create_shared_db(shared_db)
        repo = get_repository(
            player_db,
            PLAYER_XUID,
            shared_db_path=shared_db,
            gamertag="FactoryShared",
        )
        # Forcer l'initialisation de connexion pour ATTACH
        _ = repo.get_match_count()
        assert repo.has_shared is True
        repo.close()
