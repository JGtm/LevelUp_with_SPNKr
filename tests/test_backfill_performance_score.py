"""Tests pour le backfill des scores de performance.

Ce fichier teste :
- La détection des matchs sans score de performance
- Le calcul des scores manquants via backfill
- L'intégration avec backfill_data.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest

from scripts.backfill.detection import find_matches_missing_data
from scripts.backfill.strategies import compute_performance_score_for_match
from src.data.sync.migrations import ensure_performance_score_column


@pytest.fixture
def temp_duckdb_with_matches(tmp_path: Path) -> tuple[Path, str]:
    """Crée une base DuckDB temporaire avec des matchs de test."""
    import gc
    import uuid

    import duckdb

    db_path = tmp_path / f"test_player_{uuid.uuid4().hex[:8]}" / "stats.duckdb"
    db_path.parent.mkdir(parents=True)

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                kda FLOAT,
                accuracy FLOAT,
                time_played_seconds INTEGER,
                avg_life_seconds FLOAT,
                performance_score FLOAT
            )
            """
        )

        # Insérer 20 matchs historiques
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(20):
            conn.execute(
                """
                INSERT INTO match_stats
                (match_id, start_time, kills, deaths, assists, kda, accuracy, time_played_seconds, avg_life_seconds, performance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"match-{i:03d}",
                    base_time + timedelta(hours=i),
                    10 + i,
                    8,
                    3,
                    1.5 + (i * 0.1),
                    0.50,
                    600,
                    45.0,
                    None,  # Pas de score pour certains
                ),
            )

        # Insérer quelques matchs avec score
        for i in range(20, 25):
            conn.execute(
                """
                INSERT INTO match_stats
                (match_id, start_time, kills, deaths, assists, kda, accuracy, time_played_seconds, avg_life_seconds, performance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"match-{i:03d}",
                    base_time + timedelta(hours=i),
                    15,
                    6,
                    4,
                    3.0,
                    0.55,
                    600,
                    50.0,
                    75.5,  # Score déjà présent
                ),
            )
    finally:
        conn.close()
        del conn
        gc.collect()

    xuid = "2535423456789"
    return db_path, xuid


class TestFindMatchesMissingPerformanceScore:
    """Tests pour la détection des matchs sans score de performance."""

    def test_finds_matches_without_score(self, temp_duckdb_with_matches: tuple[Path, str]):
        """Test que find_matches_missing_data trouve les matchs sans score."""
        db_path, xuid = temp_duckdb_with_matches

        conn = duckdb.connect(str(db_path))

        match_ids = find_matches_missing_data(
            conn,
            xuid,
            performance_scores=True,
        )

        conn.close()

        # Devrait trouver les 20 premiers matchs (sans score)
        assert len(match_ids) == 20
        assert "match-000" in match_ids
        assert "match-019" in match_ids
        assert "match-020" not in match_ids  # Celui-ci a déjà un score

    def test_finds_all_matches_if_column_missing(self, tmp_path: Path):
        """Test que tous les matchs sont trouvés si la colonne n'existe pas."""
        db_path = tmp_path / "test_player" / "stats.duckdb"
        db_path.parent.mkdir(parents=True)

        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                kills INTEGER
            )
            """
        )

        # Insérer quelques matchs
        for i in range(5):
            conn.execute(
                "INSERT INTO match_stats (match_id, start_time, kills) VALUES (?, ?, ?)",
                (f"match-{i}", datetime(2024, 1, 1, 12 + i, tzinfo=timezone.utc), 10),
            )
        conn.commit()

        match_ids = find_matches_missing_data(
            conn,
            "123",
            performance_scores=True,
        )

        conn.close()

        # Devrait trouver tous les matchs car la colonne n'existe pas
        assert len(match_ids) == 5


class TestComputePerformanceScoreForMatch:
    """Tests pour le calcul d'un score de performance pour un match."""

    def test_computes_score_with_sufficient_history(
        self, temp_duckdb_with_matches: tuple[Path, str]
    ):
        """Test que le score est calculé avec assez d'historique."""
        db_path, xuid = temp_duckdb_with_matches

        conn = duckdb.connect(str(db_path))

        # Calculer le score pour un match sans score
        result = compute_performance_score_for_match(conn, "match-010")

        conn.close()

        assert result is True, "Le score doit être calculé"
        # Vérifier que le score a été inséré
        conn = duckdb.connect(str(db_path))
        score_result = conn.execute(
            "SELECT performance_score FROM match_stats WHERE match_id = ?",
            ("match-010",),
        ).fetchone()
        conn.close()

        assert score_result is not None
        assert score_result[0] is not None
        assert 0 <= score_result[0] <= 100

    def test_does_not_recalculate_existing_score(self, temp_duckdb_with_matches: tuple[Path, str]):
        """Test que le score existant n'est pas recalculé."""
        db_path, xuid = temp_duckdb_with_matches

        conn = duckdb.connect(str(db_path))

        # Essayer de calculer pour un match qui a déjà un score
        result = compute_performance_score_for_match(conn, "match-020")

        conn.close()

        assert result is False, "Ne doit pas recalculer un score existant"

    def test_returns_false_with_insufficient_history(self, tmp_path: Path):
        """Test que False est retourné s'il n'y a pas assez d'historique."""
        db_path = tmp_path / "test_player" / "stats.duckdb"
        db_path.parent.mkdir(parents=True)

        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                kda FLOAT,
                accuracy FLOAT,
                time_played_seconds INTEGER,
                avg_life_seconds FLOAT,
                performance_score FLOAT
            )
            """
        )

        # Insérer seulement 5 matchs (pas assez)
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            conn.execute(
                """
                INSERT INTO match_stats
                (match_id, start_time, kills, deaths, assists, kda, accuracy, time_played_seconds, avg_life_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"match-{i:03d}",
                    base_time + timedelta(hours=i),
                    10,
                    8,
                    3,
                    1.5,
                    0.50,
                    600,
                    45.0,
                ),
            )

        # Match à calculer
        conn.execute(
            """
            INSERT INTO match_stats
            (match_id, start_time, kills, deaths, assists, kda, accuracy, time_played_seconds, avg_life_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "target-match",
                base_time.replace(hour=18),
                15,
                5,
                4,
                3.0,
                0.55,
                600,
                50.0,
            ),
        )
        conn.commit()

        result = compute_performance_score_for_match(conn, "target-match")

        conn.close()

        assert result is False, "Ne doit pas calculer avec historique insuffisant"

    def test_handles_missing_start_time(self, temp_duckdb_with_matches: tuple[Path, str]):
        """Test que le calcul gère correctement les matchs sans start_time."""
        db_path, xuid = temp_duckdb_with_matches

        conn = duckdb.connect(str(db_path))

        # Insérer un match sans start_time
        conn.execute(
            """
            INSERT INTO match_stats
            (match_id, start_time, kills, deaths, assists, kda, accuracy, time_played_seconds, avg_life_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "match-no-time",
                None,
                10,
                8,
                3,
                1.5,
                0.50,
                600,
                45.0,
            ),
        )
        conn.commit()

        result = compute_performance_score_for_match(conn, "match-no-time")

        conn.close()

        # Ne devrait pas lever d'erreur, mais retourner False car pas de start_time
        assert result is False


class TestEnsurePerformanceScoreColumn:
    """Tests pour ensure_performance_score_column."""

    def test_creates_column_if_missing(self, tmp_path: Path):
        """Test que la colonne est créée si elle n'existe pas."""
        db_path = tmp_path / "test_player" / "stats.duckdb"
        db_path.parent.mkdir(parents=True)

        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                kills INTEGER
            )
            """
        )

        ensure_performance_score_column(conn)

        # Vérifier que la colonne existe
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'match_stats'
              AND column_name = 'performance_score'
            """
        ).fetchone()

        conn.close()

        assert result[0] == 1, "La colonne doit être créée"

    def test_does_not_error_if_column_exists(self, tmp_path: Path):
        """Test qu'il n'y a pas d'erreur si la colonne existe déjà."""
        db_path = tmp_path / "test_player" / "stats.duckdb"
        db_path.parent.mkdir(parents=True)

        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                kills INTEGER,
                performance_score FLOAT
            )
            """
        )

        # Appeler deux fois
        ensure_performance_score_column(conn)
        ensure_performance_score_column(conn)

        # Vérifier qu'il n'y a qu'une seule colonne
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'match_stats'
              AND column_name = 'performance_score'
            """
        ).fetchone()

        conn.close()

        assert result[0] == 1, "Il ne doit y avoir qu'une seule colonne"
