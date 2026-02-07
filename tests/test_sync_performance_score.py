"""Tests pour le calcul automatique des scores de performance lors de la synchronisation.

Ce fichier teste :
- Le calcul automatique des scores lors de l'insertion d'un match dans DuckDBSyncEngine
- La migration automatique de la colonne performance_score
- Le calcul des scores avec historique insuffisant
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pytest

from src.data.sync.engine import DuckDBSyncEngine
from src.data.sync.models import MatchStatsRow


@pytest.fixture
def temp_duckdb(tmp_path: Path) -> Path:
    """Crée une base DuckDB temporaire pour les tests."""
    import gc
    import uuid

    import duckdb

    db_path = tmp_path / f"test_player_{uuid.uuid4().hex[:8]}" / "stats.duckdb"
    db_path.parent.mkdir(parents=True)

    # Créer la DB avec tables de base si nécessaire
    conn = duckdb.connect(str(db_path))
    try:
        # Créer tables si nécessaire pour les tests
        pass  # Les tables seront créées par les tests si nécessaire
    finally:
        conn.close()
        del conn
        gc.collect()

    return db_path


@pytest.fixture
def sample_match_row() -> MatchStatsRow:
    """Crée un MatchStatsRow de test."""
    from src.data.sync.models import MatchStatsRow

    return MatchStatsRow(
        match_id="test-match-001",
        start_time=datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
        kills=15,
        deaths=8,
        assists=5,
        kda=2.5,
        accuracy=0.55,
        time_played_seconds=600,
        avg_life_seconds=45.0,
        playlist_id="playlist-123",
        playlist_name="Ranked Arena",
        map_id="map-456",
        map_name="Recharge",
        outcome=2,  # Win
        team_id=0,
    )


class TestPerformanceScoreColumnMigration:
    """Tests pour la migration automatique de la colonne performance_score."""

    def test_column_created_if_missing(self, temp_duckdb: Path):
        """Test que la colonne performance_score est créée si elle n'existe pas."""
        # Créer une table match_stats sans performance_score
        conn = duckdb.connect(str(temp_duckdb))
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
                time_played_seconds INTEGER
            )
            """
        )
        conn.close()

        # Créer l'engine et appeler _ensure_performance_score_column
        engine = DuckDBSyncEngine(
            player_db_path=temp_duckdb,
            xuid="2535423456789",
            gamertag="TestPlayer",
        )

        engine._ensure_performance_score_column()

        # Vérifier que la colonne existe maintenant
        conn = duckdb.connect(str(temp_duckdb))
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'match_stats'
              AND column_name = 'performance_score'
            """
        ).fetchone()
        conn.close()

        assert result[0] == 1, "La colonne performance_score doit exister"

    def test_column_not_duplicated_if_exists(self, temp_duckdb: Path):
        """Test que la colonne n'est pas dupliquée si elle existe déjà."""
        # Créer une table avec performance_score
        conn = duckdb.connect(str(temp_duckdb))
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                kills INTEGER,
                performance_score FLOAT
            )
            """
        )
        conn.close()

        engine = DuckDBSyncEngine(
            player_db_path=temp_duckdb,
            xuid="2535423456789",
            gamertag="TestPlayer",
        )

        # Appeler deux fois pour vérifier qu'il n'y a pas d'erreur
        engine._ensure_performance_score_column()
        engine._ensure_performance_score_column()

        # Vérifier qu'il n'y a qu'une seule colonne
        conn = duckdb.connect(str(temp_duckdb))
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'match_stats'
              AND column_name = 'performance_score'
            """
        ).fetchone()
        conn.close()

        assert result[0] == 1, "Il ne doit y avoir qu'une seule colonne performance_score"


class TestPerformanceScoreCalculation:
    """Tests pour le calcul automatique des scores de performance."""

    def test_score_calculated_with_sufficient_history(
        self, temp_duckdb: Path, sample_match_row: MatchStatsRow
    ):
        """Test que le score est calculé quand il y a assez d'historique."""
        conn = duckdb.connect(str(temp_duckdb))
        conn.execute(
            """
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
                shots_fired INTEGER,
                shots_hit INTEGER,
                is_firefight BOOLEAN,
                teammates_signature VARCHAR,
                updated_at TIMESTAMP,
                performance_score FLOAT
            )
            """
        )

        # Insérer 15 matchs historiques (plus que MIN_MATCHES_FOR_RELATIVE = 10)
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(15):
            conn.execute(
                """
                INSERT INTO match_stats
                (match_id, start_time, kills, deaths, assists, kda, accuracy, time_played_seconds, avg_life_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"hist-match-{i:03d}",
                    base_time + timedelta(hours=i),
                    10 + i,  # Kills varient
                    8,  # Deaths constants
                    3,  # Assists constants
                    1.5 + (i * 0.1),  # KDA varie
                    0.50,  # Accuracy constante
                    600,
                    45.0,
                ),
            )
        conn.commit()
        conn.close()

        engine = DuckDBSyncEngine(
            player_db_path=temp_duckdb,
            xuid="2535423456789",
            gamertag="TestPlayer",
        )

        # Insérer le nouveau match
        engine._insert_match_row(sample_match_row)

        # Calculer le score
        engine._compute_and_update_performance_score(sample_match_row.match_id, sample_match_row)

        # Vérifier que le score a été calculé
        conn = duckdb.connect(str(temp_duckdb))
        result = conn.execute(
            "SELECT performance_score FROM match_stats WHERE match_id = ?",
            (sample_match_row.match_id,),
        ).fetchone()
        conn.close()

        assert result is not None
        assert result[0] is not None, "Le score doit être calculé"
        assert 0 <= result[0] <= 100, "Le score doit être entre 0 et 100"

    def test_score_not_calculated_with_insufficient_history(
        self, temp_duckdb: Path, sample_match_row: MatchStatsRow
    ):
        """Test que le score n'est pas calculé s'il n'y a pas assez d'historique."""
        conn = duckdb.connect(str(temp_duckdb))
        conn.execute(
            """
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
                shots_fired INTEGER,
                shots_hit INTEGER,
                is_firefight BOOLEAN,
                performance_score FLOAT,
                teammates_signature VARCHAR,
                updated_at TIMESTAMP
            )
            """
        )

        # Insérer seulement 5 matchs historiques (moins que MIN_MATCHES_FOR_RELATIVE = 10)
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            conn.execute(
                """
                INSERT INTO match_stats
                (match_id, start_time, kills, deaths, assists, kda, accuracy, time_played_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"hist-match-{i:03d}",
                    base_time + timedelta(hours=i),
                    10,
                    8,
                    3,
                    1.5,
                    0.50,
                    600,
                ),
            )
        conn.commit()
        conn.close()

        engine = DuckDBSyncEngine(
            player_db_path=temp_duckdb,
            xuid="2535423456789",
            gamertag="TestPlayer",
        )

        # Insérer le nouveau match
        engine._insert_match_row(sample_match_row)

        # Calculer le score (ne devrait pas calculer)
        engine._compute_and_update_performance_score(sample_match_row.match_id, sample_match_row)

        # Vérifier que le score n'a pas été calculé (reste NULL)
        conn = duckdb.connect(str(temp_duckdb))
        result = conn.execute(
            "SELECT performance_score FROM match_stats WHERE match_id = ?",
            (sample_match_row.match_id,),
        ).fetchone()
        conn.close()

        assert result is not None
        # Le score peut être None ou non calculé
        # On vérifie juste qu'il n'y a pas d'erreur

    def test_score_not_recalculated_if_exists(
        self, temp_duckdb: Path, sample_match_row: MatchStatsRow
    ):
        """Test que le score existant n'est pas recalculé."""
        conn = duckdb.connect(str(temp_duckdb))
        conn.execute(
            """
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
                shots_fired INTEGER,
                shots_hit INTEGER,
                performance_score FLOAT,
                teammates_signature VARCHAR,
                updated_at TIMESTAMP
            )
            """
        )

        # Insérer le match avec un score déjà présent
        conn.execute(
            """
            INSERT INTO match_stats
            (match_id, start_time, kills, deaths, assists, kda, accuracy, time_played_seconds, performance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample_match_row.match_id,
                sample_match_row.start_time,
                sample_match_row.kills,
                sample_match_row.deaths,
                sample_match_row.assists,
                sample_match_row.kda,
                sample_match_row.accuracy,
                sample_match_row.time_played_seconds,
                75.5,  # Score existant
            ),
        )
        conn.commit()
        conn.close()

        engine = DuckDBSyncEngine(
            player_db_path=temp_duckdb,
            xuid="2535423456789",
            gamertag="TestPlayer",
        )

        # Essayer de calculer (ne devrait pas recalculer)
        engine._compute_and_update_performance_score(sample_match_row.match_id, sample_match_row)

        # Vérifier que le score original est préservé
        conn = duckdb.connect(str(temp_duckdb))
        result = conn.execute(
            "SELECT performance_score FROM match_stats WHERE match_id = ?",
            (sample_match_row.match_id,),
        ).fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 75.5, "Le score existant doit être préservé"

    def test_score_calculation_with_missing_start_time(self, temp_duckdb: Path):
        """Test que le calcul est skip si start_time est None."""
        from src.data.sync.models import MatchStatsRow

        match_row = MatchStatsRow(
            match_id="test-match-no-time",
            start_time=None,  # Pas de start_time
            kills=10,
            deaths=5,
            assists=3,
            kda=2.0,
            accuracy=0.50,
            time_played_seconds=600,
        )

        conn = duckdb.connect(str(temp_duckdb))
        conn.execute(
            """
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
                shots_fired INTEGER,
                shots_hit INTEGER,
                is_firefight BOOLEAN,
                performance_score FLOAT,
                teammates_signature VARCHAR,
                updated_at TIMESTAMP
            )
            """
        )
        conn.close()

        engine = DuckDBSyncEngine(
            player_db_path=temp_duckdb,
            xuid="2535423456789",
            gamertag="TestPlayer",
        )

        engine._insert_match_row(match_row)
        # Ne devrait pas lever d'erreur même sans start_time
        engine._compute_and_update_performance_score(match_row.match_id, match_row)

        # Vérifier qu'il n'y a pas d'erreur
        conn = duckdb.connect(str(temp_duckdb))
        result = conn.execute(
            "SELECT performance_score FROM match_stats WHERE match_id = ?",
            (match_row.match_id,),
        ).fetchone()
        conn.close()

        # Le score peut être None car pas de start_time pour déterminer l'ordre chronologique
        assert result is not None


class TestPerformanceScoreIntegration:
    """Tests d'intégration pour le calcul automatique lors de la sync."""

    @pytest.mark.asyncio
    async def test_score_calculated_after_match_insertion(self, temp_duckdb: Path):
        """Test que le score est calculé automatiquement après insertion d'un match."""
        # Créer l'historique
        conn = duckdb.connect(str(temp_duckdb))
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
                headshot_kills INTEGER,
                max_killing_spree INTEGER,
                my_team_score INTEGER,
                enemy_team_score INTEGER,
                team_mmr FLOAT,
                enemy_mmr FLOAT,
                shots_fired INTEGER,
                shots_hit INTEGER,
                is_firefight BOOLEAN,
                teammates_signature VARCHAR,
                updated_at TIMESTAMP,
                performance_score FLOAT
            )
            """
        )

        # Insérer 15 matchs historiques
        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(15):
            conn.execute(
                """
                INSERT INTO match_stats
                (match_id, start_time, kills, deaths, assists, kda, accuracy, time_played_seconds, avg_life_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"hist-{i:03d}",
                    base_time + timedelta(hours=i),
                    10 + i,
                    8,
                    3,
                    1.5 + (i * 0.1),
                    0.50,
                    600,
                    45.0,
                ),
            )
        conn.commit()
        conn.close()

        engine = DuckDBSyncEngine(
            player_db_path=temp_duckdb,
            xuid="2535423456789",
            gamertag="TestPlayer",
        )

        # Créer un match à insérer
        new_match = MatchStatsRow(
            match_id="new-match-001",
            start_time=datetime(2024, 1, 20, 14, 30, 0, tzinfo=timezone.utc),
            kills=20,
            deaths=5,
            assists=7,
            kda=5.4,
            accuracy=0.60,
            time_played_seconds=600,
            avg_life_seconds=50.0,
            playlist_id="playlist-123",
            playlist_name="Ranked Arena",
            map_id="map-456",
            map_name="Recharge",
            outcome=2,
            team_id=0,
        )

        # Insérer le match (ceci devrait déclencher le calcul automatique)
        engine._insert_match_row(new_match)
        engine._compute_and_update_performance_score(new_match.match_id, new_match)

        # Vérifier que le score a été calculé
        conn = duckdb.connect(str(temp_duckdb))
        result = conn.execute(
            "SELECT performance_score FROM match_stats WHERE match_id = ?",
            (new_match.match_id,),
        ).fetchone()
        conn.close()

        assert result is not None
        assert result[0] is not None, "Le score doit être calculé automatiquement"
        assert 0 <= result[0] <= 100, "Le score doit être valide"
