"""Tests d'intégration pour les données refdata et antagonistes.

Sprint 9.2 - Ces tests vérifient :
1. Le pipeline complet highlight_events → killer_victim_pairs → Polars
2. La cohérence des fonctions d'analyse
3. Les méthodes du repository
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

import duckdb

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_duckdb(tmp_path):
    """Crée une base DuckDB temporaire avec des données de test."""
    db_path = tmp_path / "test_stats.duckdb"
    conn = duckdb.connect(str(db_path))

    # Créer les tables nécessaires
    conn.execute("""
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
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER,
            kda FLOAT,
            accuracy FLOAT,
            headshot_kills INTEGER,
            max_killing_spree INTEGER,
            time_played_seconds INTEGER,
            avg_life_seconds FLOAT,
            my_team_score INTEGER,
            enemy_team_score INTEGER,
            team_mmr FLOAT,
            enemy_mmr FLOAT,
            is_firefight BOOLEAN DEFAULT FALSE
        )
    """)

    conn.execute("""
        CREATE TABLE highlight_events (
            id INTEGER PRIMARY KEY,
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
        CREATE TABLE killer_victim_pairs (
            id INTEGER PRIMARY KEY,
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

    # Insérer des données de test
    now = datetime.now(timezone.utc)

    # Match 1
    conn.execute(
        "INSERT INTO match_stats (match_id, start_time, kills, deaths, assists, kda, outcome) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("match-001", now, 15, 10, 5, 1.5, 2),
    )

    # Highlight events pour match-001
    events = [
        # Mes kills (je suis xuid_me)
        ("match-001", "Kill", 10000, "xuid_me", "Me", 50),
        ("match-001", "Death", 10002, "xuid_enemy1", "Enemy1", 20),
        ("match-001", "Kill", 20000, "xuid_me", "Me", 50),
        ("match-001", "Death", 20003, "xuid_enemy1", "Enemy1", 20),
        ("match-001", "Kill", 30000, "xuid_me", "Me", 50),
        ("match-001", "Death", 30001, "xuid_enemy2", "Enemy2", 20),
        # Mes deaths
        ("match-001", "Death", 40000, "xuid_me", "Me", 20),
        ("match-001", "Kill", 40002, "xuid_enemy1", "Enemy1", 50),
        ("match-001", "Death", 50000, "xuid_me", "Me", 20),
        ("match-001", "Kill", 50001, "xuid_enemy1", "Enemy1", 50),
    ]
    for event in events:
        conn.execute(
            "INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag, type_hint) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            event,
        )

    # Paires killer_victim calculées
    kv_pairs = [
        ("match-001", "xuid_me", "Me", "xuid_enemy1", "Enemy1", 2, 15000),
        ("match-001", "xuid_me", "Me", "xuid_enemy2", "Enemy2", 1, 30000),
        ("match-001", "xuid_enemy1", "Enemy1", "xuid_me", "Me", 2, 45000),
    ]
    for pair in kv_pairs:
        conn.execute(
            "INSERT INTO killer_victim_pairs "
            "(match_id, killer_xuid, killer_gamertag, victim_xuid, victim_gamertag, kill_count, time_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            pair,
        )

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def mock_metadata_db(tmp_path):
    """Crée une base metadata.duckdb temporaire."""
    db_path = tmp_path / "metadata.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("CREATE TABLE playlists (asset_id VARCHAR PRIMARY KEY)")
    conn.close()
    return db_path


# =============================================================================
# Tests Repository
# =============================================================================


class TestDuckDBRepositoryPolars:
    """Tests pour les méthodes Polars du repository."""

    @pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non installé")
    def test_load_killer_victim_pairs_as_polars(self, temp_duckdb, mock_metadata_db):
        """Test du chargement des paires en Polars."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            temp_duckdb,
            xuid="xuid_me",
            metadata_db_path=mock_metadata_db,
            read_only=True,
        )

        df = repo.load_killer_victim_pairs_as_polars()

        assert len(df) == 3
        assert "killer_xuid" in df.columns
        assert "victim_xuid" in df.columns
        assert "kill_count" in df.columns

        repo.close()

    @pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non installé")
    def test_load_killer_victim_pairs_filtered(self, temp_duckdb, mock_metadata_db):
        """Test du chargement filtré par match_id."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            temp_duckdb,
            xuid="xuid_me",
            metadata_db_path=mock_metadata_db,
            read_only=True,
        )

        df = repo.load_killer_victim_pairs_as_polars(match_id="match-001")
        assert len(df) == 3

        df_empty = repo.load_killer_victim_pairs_as_polars(match_id="nonexistent")
        assert len(df_empty) == 0

        repo.close()

    @pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non installé")
    def test_load_match_stats_as_polars(self, temp_duckdb, mock_metadata_db):
        """Test du chargement des match_stats en Polars."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            temp_duckdb,
            xuid="xuid_me",
            metadata_db_path=mock_metadata_db,
            read_only=True,
        )

        df = repo.load_match_stats_as_polars()

        assert len(df) == 1
        assert "match_id" in df.columns
        assert "kills" in df.columns
        assert "deaths" in df.columns

        repo.close()

    @pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non installé")
    def test_get_antagonists_summary_polars(self, temp_duckdb, mock_metadata_db):
        """Test du résumé des antagonistes."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            temp_duckdb,
            xuid="xuid_me",
            metadata_db_path=mock_metadata_db,
            read_only=True,
        )

        summary = repo.get_antagonists_summary_polars(top_n=10)

        assert "nemeses" in summary
        assert "victims" in summary

        # Mes victimes (que j'ai tuées)
        victims = summary["victims"]
        assert len(victims) == 2  # Enemy1 (2 kills) et Enemy2 (1 kill)

        # Mes némésis (qui m'ont tué)
        nemeses = summary["nemeses"]
        assert len(nemeses) == 1  # Enemy1 (2 kills)

        repo.close()

    def test_has_killer_victim_pairs(self, temp_duckdb, mock_metadata_db):
        """Test de la vérification d'existence des paires."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            temp_duckdb,
            xuid="xuid_me",
            metadata_db_path=mock_metadata_db,
            read_only=True,
        )

        assert repo.has_killer_victim_pairs() is True

        repo.close()


# =============================================================================
# Tests Analyse Polars
# =============================================================================


@pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non installé")
class TestKillerVictimPolars:
    """Tests pour les fonctions d'analyse killer_victim avec Polars."""

    def test_compute_personal_antagonists_from_pairs_polars(self, temp_duckdb, mock_metadata_db):
        """Test du calcul des antagonistes depuis les paires."""
        from src.analysis.killer_victim import compute_personal_antagonists_from_pairs_polars
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            temp_duckdb,
            xuid="xuid_me",
            metadata_db_path=mock_metadata_db,
            read_only=True,
        )

        pairs_df = repo.load_killer_victim_pairs_as_polars()
        result = compute_personal_antagonists_from_pairs_polars(pairs_df, "xuid_me")

        # Némésis = Enemy1 (m'a tué 2 fois)
        assert result.nemesis_xuid == "xuid_enemy1"
        assert result.nemesis_gamertag == "Enemy1"
        assert result.nemesis_times_killed_by == 2

        # Victime = Enemy1 (je l'ai tué 2 fois)
        assert result.victim_xuid == "xuid_enemy1"
        assert result.victim_gamertag == "Enemy1"
        assert result.victim_times_killed == 2

        # Totaux
        assert result.total_deaths == 2  # Fois où je suis mort
        assert result.total_kills == 3  # Fois où j'ai tué

        repo.close()

    def test_killer_victim_counts_long_polars(self, temp_duckdb, mock_metadata_db):
        """Test de l'agrégation en format long."""
        from src.analysis.killer_victim import killer_victim_counts_long_polars
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            temp_duckdb,
            xuid="xuid_me",
            metadata_db_path=mock_metadata_db,
            read_only=True,
        )

        pairs_df = repo.load_killer_victim_pairs_as_polars()
        result = killer_victim_counts_long_polars(pairs_df)

        assert len(result) == 3
        assert "count" in result.columns

        # Vérifier le tri par count décroissant
        counts = result["count"].to_list()
        assert counts == sorted(counts, reverse=True)

        repo.close()

    def test_compute_kd_timeseries_by_minute_polars(self, temp_duckdb, mock_metadata_db):
        """Test du calcul K/D par minute."""
        from src.analysis.killer_victim import compute_kd_timeseries_by_minute_polars
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            temp_duckdb,
            xuid="xuid_me",
            metadata_db_path=mock_metadata_db,
            read_only=True,
        )

        pairs_df = repo.load_killer_victim_pairs_as_polars()
        result = compute_kd_timeseries_by_minute_polars(pairs_df, "xuid_me")

        assert "minute" in result.columns
        assert "kills" in result.columns
        assert "deaths" in result.columns
        assert "cumulative_net_kd" in result.columns

        repo.close()

    def test_killer_victim_matrix_polars(self, temp_duckdb, mock_metadata_db):
        """Test de la matrice pivot killer/victim."""
        from src.analysis.killer_victim import killer_victim_matrix_polars
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            temp_duckdb,
            xuid="xuid_me",
            metadata_db_path=mock_metadata_db,
            read_only=True,
        )

        pairs_df = repo.load_killer_victim_pairs_as_polars()
        result = killer_victim_matrix_polars(pairs_df)

        # La matrice doit avoir les killers en lignes
        assert "killer_gamertag" in result.columns

        repo.close()


# =============================================================================
# Tests Pipeline Complet
# =============================================================================


@pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non installé")
class TestEndToEndPipeline:
    """Tests du pipeline complet highlight_events → analyse."""

    def test_backfill_and_analyze(self):
        """Test du backfill puis analyse."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        from src.analysis.killer_victim import compute_killer_victim_pairs

        # Créer des events de test
        events = [
            {"event_type": "Kill", "time_ms": 1000, "xuid": "killer1", "gamertag": "Killer1"},
            {"event_type": "Death", "time_ms": 1002, "xuid": "victim1", "gamertag": "Victim1"},
            {"event_type": "Kill", "time_ms": 2000, "xuid": "killer1", "gamertag": "Killer1"},
            {"event_type": "Death", "time_ms": 2001, "xuid": "victim2", "gamertag": "Victim2"},
        ]

        # Calculer les paires
        pairs = compute_killer_victim_pairs(events, tolerance_ms=5)

        assert len(pairs) == 2
        assert pairs[0].killer_xuid == "killer1"
        assert pairs[0].victim_xuid == "victim1"
        assert pairs[1].killer_xuid == "killer1"
        assert pairs[1].victim_xuid == "victim2"

    def test_empty_events(self):
        """Test avec aucun event."""
        from src.analysis.killer_victim import compute_killer_victim_pairs

        pairs = compute_killer_victim_pairs([])
        assert pairs == []

    def test_only_kills_no_deaths(self):
        """Test avec des kills mais pas de deaths."""
        from src.analysis.killer_victim import compute_killer_victim_pairs

        events = [
            {"event_type": "Kill", "time_ms": 1000, "xuid": "killer1", "gamertag": "Killer1"},
            {"event_type": "Kill", "time_ms": 2000, "xuid": "killer1", "gamertag": "Killer1"},
        ]

        pairs = compute_killer_victim_pairs(events)
        assert pairs == []  # Pas de paires possibles sans deaths


# =============================================================================
# Main
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
