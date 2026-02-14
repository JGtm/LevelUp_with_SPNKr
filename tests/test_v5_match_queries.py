"""Tests pour les requêtes de matchs v5 via shared_matches.

Valide que les méthodes load_matches*, get_match_count et load_match_stats_as_polars
lisent correctement depuis shared.match_registry + shared.match_participants
avec fallback v4 (table match_stats locale).

Sprint 5 — Refactoring UI Big Bang.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb
import polars as pl
import pytest

from src.data.repositories.duckdb_repo import DuckDBRepository

PLAYER_XUID = "xuid_player_main"
TEAMMATE_XUID = "xuid_teammate_2"
MATCH_ID_1 = "match_001"
MATCH_ID_2 = "match_002"
MATCH_ID_3 = "match_003"  # Extra match in shared, not in local


# =============================================================================
# Helpers de création de BD
# =============================================================================


def _create_player_db(db_path: Path, *, with_match_stats: bool = True) -> None:
    """Crée une DB joueur minimale pour les tests."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

    if with_match_stats:
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
                is_firefight BOOLEAN DEFAULT FALSE,
                is_ranked BOOLEAN DEFAULT FALSE
            )
        """)
        # Deux matchs locaux
        conn.execute("""
            INSERT INTO match_stats VALUES (
                'match_001', '2025-01-15 10:00:00', 'map1', 'Aquarius', 'pl1',
                'Ranked Arena', 'pair1', 'Slayer', 'gv1', 'Slayer', 2, 0,
                2.5, 5, 3, 30.0, 600, 15, 6, 4, 55.0, 50, 48, 1500.0, 1480.0, 2500,
                FALSE, TRUE
            )
        """)
        conn.execute("""
            INSERT INTO match_stats VALUES (
                'match_002', '2025-01-15 11:00:00', 'map2', 'Streets', 'pl2',
                'Quick Play', 'pair2', 'CTF', 'gv2', 'CTF', 3, 1,
                1.0, 2, 1, 20.0, 720, 8, 8, 2, 45.0, 1, 3, 1400.0, 1420.0, 1800,
                FALSE, FALSE
            )
        """)

    conn.close()


def _create_shared_db(db_path: Path) -> None:
    """Crée une shared_matches.duckdb avec données de test."""
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
        CREATE TABLE xuid_aliases (
            xuid VARCHAR PRIMARY KEY,
            gamertag VARCHAR NOT NULL,
            last_seen TIMESTAMP,
            source VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Registry : 3 matchs (dont 1 en plus par rapport à la DB locale)
    conn.execute("""
        INSERT INTO match_registry (
            match_id, start_time, playlist_id, playlist_name, map_id, map_name,
            pair_id, pair_name, game_variant_id, game_variant_name,
            is_ranked, is_firefight, duration_seconds, team_0_score, team_1_score,
            player_count
        ) VALUES
        ('match_001', '2025-01-15 10:00:00', 'pl1', 'Ranked Arena', 'map1', 'Aquarius',
         'pair1', 'Slayer', 'gv1', 'Slayer', TRUE, FALSE, 600, 50, 48, 8),
        ('match_002', '2025-01-15 11:00:00', 'pl2', 'Quick Play', 'map2', 'Streets',
         'pair2', 'CTF', 'gv2', 'CTF', FALSE, FALSE, 720, 1, 3, 8),
        ('match_003', '2025-01-15 12:00:00', 'pl2', 'Quick Play', 'map1', 'Aquarius',
         'pair1', 'Slayer', 'gv1', 'Slayer', FALSE, FALSE, 500, 25, 30, 8)
    """)

    # Participants pour les 3 matchs
    for match_id, kills, deaths, assists, score, outcome, team_id in [
        ("match_001", 15, 6, 4, 2500, 2, 0),
        ("match_002", 8, 8, 2, 1800, 3, 1),
        ("match_003", 20, 3, 6, 3000, 2, 0),
    ]:
        conn.execute(f"""
            INSERT INTO match_participants (match_id, xuid, gamertag, team_id, outcome, rank, score, kills, deaths, assists, shots_fired, shots_hit)
            VALUES ('{match_id}', '{PLAYER_XUID}', 'PlayerOne', {team_id}, {outcome}, 1, {score}, {kills}, {deaths}, {assists}, 100, 55)
        """)
        conn.execute(f"""
            INSERT INTO match_participants (match_id, xuid, gamertag, team_id, outcome, rank, score, kills, deaths, assists, shots_fired, shots_hit)
            VALUES ('{match_id}', '{TEAMMATE_XUID}', 'TeammateTwo', {team_id}, {outcome}, 2, 2200, 12, 7, 5, 80, 40)
        """)

    conn.close()


@pytest.fixture
def tmp_player_db(tmp_path: Path) -> Path:
    """DB joueur avec match_stats locale."""
    db_path = tmp_path / "data" / "players" / "TestPlayer" / "stats.duckdb"
    _create_player_db(db_path)
    return db_path


@pytest.fixture
def tmp_player_db_no_ms(tmp_path: Path) -> Path:
    """DB joueur SANS match_stats (transitoire v5)."""
    db_path = tmp_path / "data" / "players" / "TestPlayer" / "stats.duckdb"
    _create_player_db(db_path, with_match_stats=False)
    return db_path


@pytest.fixture
def tmp_shared_db(tmp_path: Path) -> Path:
    """shared_matches.duckdb avec données de test."""
    db_path = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"
    _create_shared_db(db_path)
    return db_path


@pytest.fixture
def repo_v5(tmp_player_db: Path, tmp_shared_db: Path) -> DuckDBRepository:
    """DuckDBRepository mode v5 : shared + local."""
    return DuckDBRepository(
        player_db_path=tmp_player_db,
        xuid=PLAYER_XUID,
        shared_db_path=tmp_shared_db,
        gamertag="TestPlayer",
        read_only=True,
    )


@pytest.fixture
def repo_v5_no_ms(tmp_player_db_no_ms: Path, tmp_shared_db: Path) -> DuckDBRepository:
    """DuckDBRepository mode v5 : shared SANS match_stats locale."""
    return DuckDBRepository(
        player_db_path=tmp_player_db_no_ms,
        xuid=PLAYER_XUID,
        shared_db_path=tmp_shared_db,
        gamertag="TestPlayer",
        read_only=True,
    )


@pytest.fixture
def repo_v4(tmp_player_db: Path) -> DuckDBRepository:
    """DuckDBRepository mode v4 : local uniquement, sans shared."""
    return DuckDBRepository(
        player_db_path=tmp_player_db,
        xuid=PLAYER_XUID,
        shared_db_path=Path("/nonexistent/shared_matches.duckdb"),
        gamertag="TestPlayer",
        read_only=True,
    )


# =============================================================================
# Tests load_matches() via shared
# =============================================================================


class TestLoadMatchesShared:
    """Tests load_matches() avec shared_matches.duckdb."""

    def test_load_matches_via_shared_returns_all(self, repo_v5: DuckDBRepository):
        """load_matches v5 retourne les 3 matchs (incluant match_003 non local)."""
        matches = repo_v5.load_matches()
        assert len(matches) == 3
        match_ids = {m.match_id for m in matches}
        assert MATCH_ID_1 in match_ids
        assert MATCH_ID_2 in match_ids
        assert MATCH_ID_3 in match_ids

    def test_load_matches_shared_preserves_column_names(self, repo_v5: DuckDBRepository):
        """Les colonnes v4 (my_team_score, enemy_team_score) sont présentes."""
        matches = repo_v5.load_matches()
        m1 = next(m for m in matches if m.match_id == MATCH_ID_1)
        # Scores team aliasés correctement
        assert m1.my_team_score is not None
        assert m1.enemy_team_score is not None
        # KDA calculé
        assert m1.kda is not None
        assert m1.kda > 0
        # Kills/deaths
        assert m1.kills == 15
        assert m1.deaths == 6
        assert m1.assists == 4

    def test_load_matches_shared_scores_from_registry(self, repo_v5: DuckDBRepository):
        """Les scores sont correctement mappés depuis match_registry.

        Pour le joueur team_id=0 : my_team_score=team_0_score, enemy=team_1_score.
        Pour le joueur team_id=1 : my_team_score=team_1_score, enemy=team_0_score.
        """
        matches = repo_v5.load_matches()
        # Match 1 : joueur team_id=0, registry: team_0=50, team_1=48
        m1 = next(m for m in matches if m.match_id == MATCH_ID_1)
        # COALESCE(ms.my_team_score, CASE...) → ms.my_team_score=50
        assert m1.my_team_score == 50
        assert m1.enemy_team_score == 48

    def test_load_matches_shared_personal_score(self, repo_v5: DuckDBRepository):
        """personal_score est récupéré via shared."""
        matches = repo_v5.load_matches()
        # Match 1: COALESCE(ms.personal_score, p.score)
        m1 = next(m for m in matches if m.match_id == MATCH_ID_1)
        assert m1.personal_score is not None
        assert m1.personal_score > 0

    def test_load_matches_shared_match_003_has_data(self, repo_v5: DuckDBRepository):
        """Match_003 (uniquement dans shared) a des données complètes."""
        matches = repo_v5.load_matches()
        m3 = next(m for m in matches if m.match_id == MATCH_ID_3)
        assert m3.kills == 20
        assert m3.deaths == 3
        assert m3.map_name == "Aquarius"
        assert m3.outcome == 2  # Win

    def test_load_matches_shared_with_limit(self, repo_v5: DuckDBRepository):
        """load_matches avec limit fonctionne en mode shared."""
        matches = repo_v5.load_matches(limit=2)
        assert len(matches) == 2

    def test_load_matches_shared_with_filter(self, repo_v5: DuckDBRepository):
        """load_matches avec playlist_filter fonctionne en mode shared."""
        matches = repo_v5.load_matches(playlist_filter="pl1")
        assert len(matches) == 1
        assert matches[0].match_id == MATCH_ID_1

    def test_load_matches_shared_firefight_filter(self, repo_v5: DuckDBRepository):
        """include_firefight=False filtre correctement en mode shared."""
        matches = repo_v5.load_matches(include_firefight=False)
        # Aucun match n'est firefight dans nos données de test
        assert len(matches) == 3


class TestLoadMatchesV4Fallback:
    """Tests du fallback v4 (sans shared)."""

    def test_load_matches_v4_returns_local_only(self, repo_v4: DuckDBRepository):
        """Sans shared, load_matches lit uniquement match_stats locale."""
        matches = repo_v4.load_matches()
        assert len(matches) == 2
        assert all(m.match_id in {MATCH_ID_1, MATCH_ID_2} for m in matches)

    def test_load_matches_v4_preserves_all_fields(self, repo_v4: DuckDBRepository):
        """Tous les champs MatchRow sont remplis en mode v4."""
        matches = repo_v4.load_matches()
        m1 = next(m for m in matches if m.match_id == MATCH_ID_1)
        assert m1.kills == 15
        assert m1.deaths == 6
        assert m1.kda == 2.5
        assert m1.map_name == "Aquarius"
        assert m1.my_team_score == 50


class TestLoadMatchesSharedNoLocalMS:
    """Tests shared sans table match_stats locale (état final v5)."""

    def test_load_matches_no_ms_uses_shared_only(self, repo_v5_no_ms: DuckDBRepository):
        """Sans match_stats locale, les matchs viennent uniquement de shared."""
        matches = repo_v5_no_ms.load_matches()
        assert len(matches) == 3

    def test_load_matches_no_ms_kda_computed(self, repo_v5_no_ms: DuckDBRepository):
        """KDA est calculé à la volée quand pas de match_stats locale."""
        matches = repo_v5_no_ms.load_matches()
        m1 = next(m for m in matches if m.match_id == MATCH_ID_1)
        # KDA = (kills + assists/3) / deaths = (15 + 4/3) / 6 ≈ 2.72
        assert m1.kda is not None
        assert 2.0 < m1.kda < 3.5

    def test_load_matches_no_ms_accuracy_computed(self, repo_v5_no_ms: DuckDBRepository):
        """accuracy est calculé depuis shots_fired/shots_hit quand pas de ms locale."""
        matches = repo_v5_no_ms.load_matches()
        m1 = next(m for m in matches if m.match_id == MATCH_ID_1)
        # acc = shots_hit * 100 / shots_fired = 55 * 100 / 100 = 55.0
        assert m1.accuracy is not None
        assert m1.accuracy == 55.0


# =============================================================================
# Tests load_matches_in_range() via shared
# =============================================================================


class TestLoadMatchesInRange:
    """Tests load_matches_in_range avec shared."""

    def test_in_range_shared(self, repo_v5: DuckDBRepository):
        """load_matches_in_range filtre par date en mode shared."""
        matches = repo_v5.load_matches_in_range(
            start_date=datetime(2025, 1, 15, 10, 30),
            end_date=datetime(2025, 1, 15, 12, 30),
        )
        # match_002 (11:00) et match_003 (12:00) dans l'intervalle
        assert len(matches) == 2
        match_ids = {m.match_id for m in matches}
        assert MATCH_ID_2 in match_ids
        assert MATCH_ID_3 in match_ids


# =============================================================================
# Tests get_match_count() via shared
# =============================================================================


class TestGetMatchCount:
    """Tests get_match_count avec shared."""

    def test_count_shared(self, repo_v5: DuckDBRepository):
        """get_match_count retourne le count shared (3 matchs)."""
        assert repo_v5.get_match_count() == 3

    def test_count_v4_fallback(self, repo_v4: DuckDBRepository):
        """get_match_count retourne le count local (2 matchs) sans shared."""
        assert repo_v4.get_match_count() == 2


# =============================================================================
# Tests load_recent_matches() via shared
# =============================================================================


class TestLoadRecentMatches:
    """Tests load_recent_matches avec shared."""

    def test_recent_matches_shared(self, repo_v5: DuckDBRepository):
        """load_recent_matches retourne les plus récents en mode shared."""
        matches = repo_v5.load_recent_matches(limit=2)
        assert len(matches) == 2
        # Plus récent en premier (DESC)
        assert matches[0].match_id == MATCH_ID_3

    def test_recent_matches_v4(self, repo_v4: DuckDBRepository):
        """load_recent_matches fonctionne en mode v4."""
        matches = repo_v4.load_recent_matches(limit=1)
        assert len(matches) == 1
        assert matches[0].match_id == MATCH_ID_2


# =============================================================================
# Tests load_matches_paginated() via shared
# =============================================================================


class TestLoadMatchesPaginated:
    """Tests load_matches_paginated avec shared."""

    def test_paginated_shared(self, repo_v5: DuckDBRepository):
        """load_matches_paginated fonctionne en mode shared."""
        matches, total_pages = repo_v5.load_matches_paginated(page=1, page_size=2)
        assert len(matches) == 2
        assert total_pages == 2  # 3 matchs / 2 par page = 2 pages

    def test_paginated_shared_page2(self, repo_v5: DuckDBRepository):
        """Page 2 retourne le 3eme match."""
        matches, total_pages = repo_v5.load_matches_paginated(page=2, page_size=2)
        assert len(matches) == 1


# =============================================================================
# Tests load_matches_as_polars() via shared
# =============================================================================


class TestLoadMatchesAsPolars:
    """Tests load_matches_as_polars avec shared."""

    def test_polars_shared_returns_all(self, repo_v5: DuckDBRepository):
        """load_matches_as_polars retourne un DataFrame avec les 3 matchs."""
        df = repo_v5.load_matches_as_polars()
        assert isinstance(df, pl.DataFrame)
        assert df.shape[0] == 3

    def test_polars_shared_has_ratio(self, repo_v5: DuckDBRepository):
        """Le ratio est calculé en Polars après chargement."""
        df = repo_v5.load_matches_as_polars()
        assert "ratio" in df.columns
        # match_001: (15 + 4/2) / 6 = 2.83
        m1 = df.filter(pl.col("match_id") == MATCH_ID_1)
        assert m1.shape[0] == 1

    def test_polars_shared_renames_avg_life(self, repo_v5: DuckDBRepository):
        """avg_life_seconds est renommé en average_life_seconds."""
        df = repo_v5.load_matches_as_polars()
        assert "average_life_seconds" in df.columns
        assert "avg_life_seconds" not in df.columns

    def test_polars_shared_column_projection(self, repo_v5: DuckDBRepository):
        """La projection de colonnes fonctionne en mode shared."""
        df = repo_v5.load_matches_as_polars(columns=["match_id", "kills", "deaths"])
        assert set(df.columns) == {"match_id", "kills", "deaths"}

    def test_polars_v4_fallback(self, repo_v4: DuckDBRepository):
        """load_matches_as_polars fonctionne en mode v4."""
        df = repo_v4.load_matches_as_polars()
        assert df.shape[0] == 2


# =============================================================================
# Tests load_match_stats_as_polars() via shared
# =============================================================================


class TestLoadMatchStatsAsPolars:
    """Tests load_match_stats_as_polars avec shared."""

    def test_stats_polars_shared(self, repo_v5: DuckDBRepository):
        """load_match_stats_as_polars retourne les 3 matchs via shared."""
        df = repo_v5.load_match_stats_as_polars()
        assert df.shape[0] == 3

    def test_stats_polars_shared_filter_ids(self, repo_v5: DuckDBRepository):
        """Filtrage par match_ids fonctionne en mode shared."""
        df = repo_v5.load_match_stats_as_polars(match_ids=[MATCH_ID_1, MATCH_ID_3])
        assert df.shape[0] == 2

    def test_stats_polars_shared_limit(self, repo_v5: DuckDBRepository):
        """Limit fonctionne en mode shared."""
        df = repo_v5.load_match_stats_as_polars(limit=1)
        assert df.shape[0] == 1

    def test_stats_polars_v4(self, repo_v4: DuckDBRepository):
        """load_match_stats_as_polars en mode v4."""
        df = repo_v4.load_match_stats_as_polars()
        assert df.shape[0] == 2


# =============================================================================
# Tests _get_match_source()
# =============================================================================


class TestGetMatchSource:
    """Tests de la méthode interne _get_match_source."""

    def test_v5_returns_subquery_with_params(self, repo_v5: DuckDBRepository):
        """En mode v5, retourne une sous-requête avec le xuid en paramètre."""
        conn = repo_v5._get_connection()
        source, params = repo_v5._get_match_source(conn)
        assert "shared.match_registry" in source
        assert "shared.match_participants" in source
        assert len(params) == 1
        assert params[0] == PLAYER_XUID

    def test_v4_returns_match_stats(self, repo_v4: DuckDBRepository):
        """En mode v4, retourne 'match_stats' sans paramètres."""
        conn = repo_v4._get_connection()
        source, params = repo_v4._get_match_source(conn)
        assert source == "match_stats"
        assert params == []

    def test_v5_no_ms_returns_subquery(self, repo_v5_no_ms: DuckDBRepository):
        """En mode v5 sans match_stats locale, retourne la sous-requête."""
        conn = repo_v5_no_ms._get_connection()
        source, params = repo_v5_no_ms._get_match_source(conn)
        assert "shared.match_registry" in source
        assert len(params) == 1


# =============================================================================
# Tests remove_compat_views
# =============================================================================


class TestRemoveCompatViews:
    """Tests du script remove_compat_views.py."""

    def test_remove_existing_views(self, tmp_path: Path):
        """Supprime les VIEWs existantes."""
        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE VIEW v_match_stats AS SELECT 1 AS x")
        conn.execute("CREATE VIEW v_medals_earned AS SELECT 1 AS x")
        conn.execute("CREATE VIEW v_highlight_events AS SELECT 1 AS x")
        conn.execute("CREATE VIEW v_match_participants AS SELECT 1 AS x")
        conn.close()

        from scripts.migration.remove_compat_views import remove_compat_views

        results = remove_compat_views("TestGT", db_path, verbose=True)
        assert all(v for v in results.values())

        # Vérifier qu'elles sont effectivement supprimées
        conn = duckdb.connect(str(db_path))
        views = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_type = 'VIEW'"
        ).fetchall()
        conn.close()
        assert len(views) == 0

    def test_remove_nonexistent_views(self, tmp_path: Path):
        """Ne plante pas si les VIEWs n'existent pas."""
        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.close()

        from scripts.migration.remove_compat_views import remove_compat_views

        results = remove_compat_views("TestGT", db_path)
        assert all(v for v in results.values())

    def test_dry_run(self, tmp_path: Path):
        """Le mode dry-run ne supprime rien."""
        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE VIEW v_match_stats AS SELECT 1 AS x")
        conn.close()

        from scripts.migration.remove_compat_views import remove_compat_views

        results = remove_compat_views("TestGT", db_path, dry_run=True)
        assert results["v_match_stats"] is True

        # La vue existe toujours
        conn = duckdb.connect(str(db_path))
        views = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_type = 'VIEW'"
        ).fetchall()
        conn.close()
        assert len(views) == 1
