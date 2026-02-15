"""Tests d'intégration pour les nouvelles statistiques.

Ce fichier valide les nouvelles fonctionnalités ajoutées au cours des sprints :
- Score de Performance v4
- Graphes temporels (timeseries)
- Corrélations de performance
- Analyse coéquipiers & impact
- Filtres et navigation
"""

from __future__ import annotations

import contextlib
import gc
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
import pytest

if TYPE_CHECKING:
    pass


@pytest.fixture
def integration_db(tmp_path: Path) -> tuple[Path, str]:
    """Crée une base de données d'intégration complète avec données réalistes.

    Cette fixture crée une DB avec 50+ matchs pour tester les fonctionnalités
    de manière réaliste.
    """
    db_path = tmp_path / "test_integration_player" / "stats.duckdb"
    db_path.parent.mkdir(parents=True)

    conn = duckdb.connect(str(db_path))
    try:
        # Créer les tables avec le schéma complet
        conn.execute("""
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                duration_seconds INTEGER,
                playlist_id VARCHAR,
                map_variant_id VARCHAR,
                game_variant_id VARCHAR,
                outcome INTEGER,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                kda FLOAT,
                accuracy FLOAT,
                headshot_percentage FLOAT,
                time_played_seconds INTEGER,
                avg_life_seconds FLOAT,
                performance_score FLOAT,
                personal_score INTEGER,
                damage_dealt INTEGER,
                damage_taken INTEGER,
                shots_fired INTEGER,
                shots_hit INTEGER,
                team_mmr FLOAT,
                enemy_mmr FLOAT,
                rank INTEGER,
                expected_kills FLOAT,
                expected_deaths FLOAT
            )
        """)

        conn.execute("""
            CREATE TABLE medals_earned (
                match_id VARCHAR,
                medal_id VARCHAR,
                count INTEGER,
                PRIMARY KEY (match_id, medal_id)
            )
        """)

        conn.execute("""
            CREATE TABLE highlight_events (
                match_id VARCHAR,
                event_type VARCHAR,
                time_ms INTEGER,
                player_gamertag VARCHAR,
                opponent_gamertag VARCHAR
            )
        """)

        conn.execute("""
            CREATE TABLE antagonists (
                opponent_gamertag VARCHAR PRIMARY KEY,
                kills_against INTEGER,
                deaths_against INTEGER,
                matches_against INTEGER,
                avg_kda_against FLOAT
            )
        """)

        conn.execute("""
            CREATE TABLE match_participants (
                match_id VARCHAR,
                player_gamertag VARCHAR,
                player_xuid VARCHAR,
                is_teammate BOOLEAN,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                kda FLOAT,
                accuracy FLOAT,
                damage_dealt INTEGER,
                damage_taken INTEGER,
                PRIMARY KEY (match_id, player_gamertag)
            )
        """)

        # Vues matérialisées
        conn.execute("""
            CREATE TABLE mv_sessions_daily (
                session_date DATE PRIMARY KEY,
                total_matches INTEGER,
                wins INTEGER,
                losses INTEGER,
                avg_kda FLOAT,
                total_kills INTEGER,
                total_deaths INTEGER
            )
        """)

        # Insérer des matchs réalistes
        import random

        random.seed(42)  # Reproductibilité

        base_time = datetime(2024, 6, 1, 18, 0, 0, tzinfo=timezone.utc)
        playlists = ["edfef3ac-9cbe-4fa2-b949-8f29deafd483", "3e7e7cc1-4ac8-4c7e-9c3b-8989b1b0c77e"]
        maps = ["map_001", "map_002", "map_003", "map_004"]
        modes = ["mode_001", "mode_002"]

        for i in range(100):
            # Variation temporelle (matchs sur plusieurs semaines)
            match_time = base_time.replace(day=1 + (i // 5), hour=18 + (i % 6), minute=(i * 7) % 60)

            kills = random.randint(5, 25)
            deaths = random.randint(3, 20)
            assists = random.randint(2, 10)
            kda = (kills + assists / 3) / max(deaths, 1)
            accuracy = round(random.uniform(0.30, 0.65), 3)

            # Score de performance (v4)
            perf_score = min(100, max(0, 50 + kda * 10 + accuracy * 20 - 5 * random.random()))

            conn.execute(
                """
                INSERT INTO match_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"match-{i:04d}",
                    match_time,
                    random.randint(300, 900),
                    random.choice(playlists),
                    random.choice(maps),
                    random.choice(modes),
                    random.choice([2, 3]),  # Win or loss
                    kills,
                    deaths,
                    assists,
                    kda,
                    accuracy,
                    round(random.uniform(0.10, 0.40), 3),
                    random.randint(300, 900),
                    round(random.uniform(15, 60), 1),
                    round(perf_score, 2),
                    kills * 100 + random.randint(0, 500),
                    random.randint(1000, 5000),
                    random.randint(800, 4000),
                    random.randint(50, 200),
                    int(random.randint(50, 200) * accuracy),
                    1400 + random.uniform(-100, 100),
                    1400 + random.uniform(-100, 100),
                    random.randint(1, 8),
                    kills * 0.8,
                    deaths * 0.9,
                ),
            )

            # Médailles (quelques-unes par match)
            for _ in range(random.randint(3, 8)):
                with contextlib.suppress(Exception):
                    conn.execute(
                        """
                        INSERT INTO medals_earned VALUES (?, ?, ?)
                    """,
                        (
                            f"match-{i:04d}",
                            f"medal_{random.randint(1, 50):03d}",
                            random.randint(1, 5),
                        ),
                    )

            # Événements (kills/deaths)
            for _ in range(random.randint(2, 6)):
                event_type = random.choice(["Kill", "Death"])
                conn.execute(
                    """
                    INSERT INTO highlight_events VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        f"match-{i:04d}",
                        event_type,
                        random.randint(10000, 600000),
                        "TestPlayer"
                        if event_type == "Kill"
                        else f"Opponent{random.randint(1, 10)}",
                        f"Opponent{random.randint(1, 10)}"
                        if event_type == "Kill"
                        else "TestPlayer",
                    ),
                )

            # Participants (joueur principal + coéquipier + adversaire)
            with contextlib.suppress(Exception):
                conn.execute(
                    "INSERT INTO match_participants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"match-{i:04d}",
                        "TestPlayer",
                        "1234567890123456",
                        True,
                        kills,
                        deaths,
                        assists,
                        round(kda, 2),
                        accuracy,
                        random.randint(1000, 5000),
                        random.randint(800, 4000),
                    ),
                )
                conn.execute(
                    "INSERT INTO match_participants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"match-{i:04d}",
                        f"Teammate{random.randint(1, 3)}",
                        f"xuid_team_{random.randint(1, 3)}",
                        True,
                        random.randint(5, 20),
                        random.randint(3, 15),
                        random.randint(1, 8),
                        round(random.uniform(0.8, 2.0), 2),
                        round(random.uniform(0.30, 0.60), 3),
                        random.randint(800, 4000),
                        random.randint(800, 4000),
                    ),
                )
                conn.execute(
                    "INSERT INTO match_participants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"match-{i:04d}",
                        f"Opponent{random.randint(1, 5)}",
                        f"xuid_opp_{random.randint(1, 5)}",
                        False,
                        random.randint(5, 20),
                        random.randint(3, 15),
                        random.randint(1, 8),
                        round(random.uniform(0.8, 2.0), 2),
                        round(random.uniform(0.30, 0.60), 3),
                        random.randint(800, 4000),
                        random.randint(800, 4000),
                    ),
                )

        # Sessions quotidiennes
        for day in range(1, 26):
            matches = random.randint(3, 10)
            wins = random.randint(1, matches)
            conn.execute(
                """
                INSERT INTO mv_sessions_daily VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"2024-06-{day:02d}",
                    matches,
                    wins,
                    matches - wins,
                    round(random.uniform(1.0, 2.0), 2),
                    random.randint(30, 100),
                    random.randint(25, 80),
                ),
            )

        conn.commit()
    finally:
        conn.close()
        gc.collect()

    return db_path, "1234567890123456"


# ─────────────────────────────────────────────────────────────────────────────
# Tests Score de Performance v4
# ─────────────────────────────────────────────────────────────────────────────


class TestPerformanceScoreIntegration:
    """Tests d'intégration du score de performance."""

    def test_all_matches_have_performance_score(self, integration_db: tuple[Path, str]):
        """Vérifie que tous les matchs ont un score de performance."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        result = conn.execute("""
            SELECT COUNT(*) as total,
                   COUNT(performance_score) as with_score
            FROM match_stats
        """).fetchone()

        conn.close()

        assert result[0] == result[1], "Tous les matchs doivent avoir un score de performance"
        assert result[0] >= 100, "Au moins 100 matchs dans la DB d'intégration"

    def test_performance_score_range(self, integration_db: tuple[Path, str]):
        """Vérifie que les scores sont dans une plage valide."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        result = conn.execute("""
            SELECT MIN(performance_score), MAX(performance_score), AVG(performance_score)
            FROM match_stats
        """).fetchone()

        conn.close()

        min_score, max_score, avg_score = result
        assert min_score >= 0, "Score minimum >= 0"
        assert max_score <= 100, "Score maximum <= 100"
        assert 30 < avg_score < 80, "Score moyen dans une plage raisonnable"


# ─────────────────────────────────────────────────────────────────────────────
# Tests Timeseries et Agrégations
# ─────────────────────────────────────────────────────────────────────────────


class TestTimeseriesIntegration:
    """Tests d'intégration des graphes temporels."""

    def test_sessions_daily_data_available(self, integration_db: tuple[Path, str]):
        """Vérifie que les sessions quotidiennes sont disponibles."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        result = conn.execute("""
            SELECT COUNT(*) FROM mv_sessions_daily
        """).fetchone()

        conn.close()

        assert result[0] >= 20, "Au moins 20 jours de sessions"

    def test_timeseries_metrics_computation(self, integration_db: tuple[Path, str]):
        """Vérifie le calcul de métriques temporelles."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        result = conn.execute("""
            SELECT
                DATE_TRUNC('day', start_time) as day,
                COUNT(*) as matches,
                AVG(kda) as avg_kda,
                SUM(kills) as total_kills
            FROM match_stats
            GROUP BY DATE_TRUNC('day', start_time)
            ORDER BY day
        """).fetchall()

        conn.close()

        assert len(result) >= 5, "Au moins 5 jours distincts"
        for row in result:
            assert row[1] > 0, "Chaque jour a des matchs"
            assert row[2] > 0, "KDA toujours positif"


# ─────────────────────────────────────────────────────────────────────────────
# Tests Coéquipiers et Comparaisons
# ─────────────────────────────────────────────────────────────────────────────


class TestTeammatesIntegration:
    """Tests d'intégration des fonctionnalités coéquipiers.

    Note: teammates_aggregate a été supprimée en v5.
    Les coéquipiers sont désormais calculés dynamiquement depuis
    shared.match_participants. Ces tests vérifient que match_participants
    contient les données nécessaires.
    """

    def test_match_participants_data_available(self, integration_db: tuple[Path, str]):
        """Vérifie que les données participants sont disponibles."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        result = conn.execute("SELECT COUNT(*) FROM match_participants").fetchone()

        conn.close()

        assert result[0] >= 3, "Au moins 3 participants enregistrés"

    def test_match_participants_team_data(self, integration_db: tuple[Path, str]):
        """Vérifie que les participants ont des données d'équipe."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        result = conn.execute("""
            SELECT DISTINCT player_gamertag
            FROM match_participants
            WHERE player_gamertag IS NOT NULL
        """).fetchall()

        conn.close()

        assert len(result) >= 1, "Au moins 1 joueur avec gamertag"


# ─────────────────────────────────────────────────────────────────────────────
# Tests Médailles et Événements
# ─────────────────────────────────────────────────────────────────────────────


class TestMedalsEventsIntegration:
    """Tests d'intégration des médailles et événements."""

    def test_medals_linked_to_matches(self, integration_db: tuple[Path, str]):
        """Vérifie que les médailles sont liées aux matchs."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        result = conn.execute("""
            SELECT COUNT(DISTINCT me.match_id)
            FROM medals_earned me
            JOIN match_stats ms ON me.match_id = ms.match_id
        """).fetchone()

        conn.close()

        assert result[0] >= 50, "Au moins 50 matchs avec médailles"

    def test_highlight_events_available(self, integration_db: tuple[Path, str]):
        """Vérifie que les événements sont disponibles."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        result = conn.execute("""
            SELECT event_type, COUNT(*)
            FROM highlight_events
            GROUP BY event_type
        """).fetchall()

        conn.close()

        event_types = {row[0]: row[1] for row in result}
        assert "Kill" in event_types, "Événements Kill présents"
        assert "Death" in event_types, "Événements Death présents"


# ─────────────────────────────────────────────────────────────────────────────
# Tests Repository DuckDB
# ─────────────────────────────────────────────────────────────────────────────


class TestDuckDBRepositoryIntegration:
    """Tests d'intégration du repository DuckDB."""

    def test_repository_loads_matches_direct_query(self, integration_db: tuple[Path, str]):
        """Vérifie que les matchs peuvent être chargés via requête directe."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        result = conn.execute("""
            SELECT match_id, start_time, kills, deaths, kda, performance_score
            FROM match_stats
            ORDER BY start_time DESC
            LIMIT 200
        """).fetchdf()

        conn.close()

        assert len(result) >= 100, "Au moins 100 matchs disponibles"
        required_cols = ["match_id", "start_time", "kills", "deaths", "kda"]
        for col in required_cols:
            assert col in result.columns, f"Colonne {col} présente"

    def test_repository_outcome_filter(self, integration_db: tuple[Path, str]):
        """Vérifie le filtrage par outcome via requête directe."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        # Test filtre par outcome
        wins = conn.execute("SELECT COUNT(*) FROM match_stats WHERE outcome = 2").fetchone()[0]
        losses = conn.execute("SELECT COUNT(*) FROM match_stats WHERE outcome = 3").fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM match_stats").fetchone()[0]

        conn.close()

        # Les victoires + défaites doivent correspondre au total
        assert wins + losses == total, "Filtrage par outcome cohérent"
        assert wins > 0, "Au moins une victoire"
        assert losses > 0, "Au moins une défaite"


# ─────────────────────────────────────────────────────────────────────────────
# Tests de charge (performance)
# ─────────────────────────────────────────────────────────────────────────────


class TestLoadPerformance:
    """Tests de charge pour vérifier les performances."""

    def test_query_performance_1000_matches(self, tmp_path: Path):
        """Vérifie la performance avec 1000 matchs."""
        import time

        db_path = tmp_path / "load_test_player" / "stats.duckdb"
        db_path.parent.mkdir(parents=True)

        conn = duckdb.connect(str(db_path))

        # Créer table avec 1000 matchs
        conn.execute("""
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                kda FLOAT,
                accuracy FLOAT,
                performance_score FLOAT,
                outcome INTEGER
            )
        """)

        # Insertion en batch
        import random

        random.seed(42)
        base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

        batch_data = []
        for i in range(1000):
            kills = random.randint(5, 25)
            deaths = random.randint(3, 20)
            kda = kills / max(deaths, 1)
            batch_data.append(
                (
                    f"match-{i:05d}",
                    base_time.replace(day=1 + (i // 50), hour=(i % 24)),
                    kills,
                    deaths,
                    random.randint(2, 10),
                    kda,
                    round(random.uniform(0.30, 0.65), 3),
                    round(50 + kda * 10, 2),
                    random.choice([2, 3]),
                )
            )

        conn.executemany("INSERT INTO match_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", batch_data)
        conn.commit()

        # Test de lecture complète
        start = time.time()
        result = conn.execute("SELECT * FROM match_stats").fetchall()
        query_time = time.time() - start

        conn.close()
        gc.collect()

        assert len(result) == 1000
        assert (
            query_time < 1.0
        ), f"Lecture 1000 matchs doit prendre < 1s (actual: {query_time:.3f}s)"

    def test_aggregation_performance(self, tmp_path: Path):
        """Vérifie la performance des agrégations sur 1000+ matchs."""
        import time
        from datetime import timedelta

        db_path = tmp_path / "agg_test_player" / "stats.duckdb"
        db_path.parent.mkdir(parents=True)

        conn = duckdb.connect(str(db_path))

        conn.execute("""
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                kills INTEGER,
                deaths INTEGER,
                kda FLOAT,
                performance_score FLOAT,
                outcome INTEGER
            )
        """)

        import random

        random.seed(42)
        base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

        batch_data = [
            (
                f"match-{i:05d}",
                base_time + timedelta(days=i // 50, hours=i % 24),
                random.randint(5, 25),
                random.randint(3, 20),
                round(random.uniform(0.8, 3.0), 2),
                round(random.uniform(30, 90), 2),
                random.choice([2, 3]),
            )
            for i in range(2000)
        ]

        conn.executemany("INSERT INTO match_stats VALUES (?, ?, ?, ?, ?, ?, ?)", batch_data)
        conn.commit()

        # Test agrégation complexe
        start = time.time()
        result = conn.execute("""
            SELECT
                DATE_TRUNC('day', start_time) as day,
                COUNT(*) as matches,
                AVG(kda) as avg_kda,
                AVG(performance_score) as avg_perf,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins,
                SUM(kills) as total_kills
            FROM match_stats
            GROUP BY DATE_TRUNC('day', start_time)
            ORDER BY day
        """).fetchall()
        agg_time = time.time() - start

        conn.close()
        gc.collect()

        assert len(result) > 0
        assert agg_time < 0.5, f"Agrégation doit prendre < 0.5s (actual: {agg_time:.3f}s)"


# ─────────────────────────────────────────────────────────────────────────────
# Tests de cohérence des données
# ─────────────────────────────────────────────────────────────────────────────


class TestDataConsistency:
    """Tests de cohérence des données entre tables."""

    def test_medals_match_ids_exist(self, integration_db: tuple[Path, str]):
        """Vérifie que tous les match_id des médailles existent dans match_stats."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        orphans = conn.execute("""
            SELECT COUNT(*)
            FROM medals_earned me
            WHERE me.match_id NOT IN (SELECT match_id FROM match_stats)
        """).fetchone()

        conn.close()

        assert orphans[0] == 0, "Pas de médailles orphelines"

    def test_events_match_ids_exist(self, integration_db: tuple[Path, str]):
        """Vérifie que tous les match_id des événements existent dans match_stats."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        orphans = conn.execute("""
            SELECT COUNT(*)
            FROM highlight_events he
            WHERE he.match_id NOT IN (SELECT match_id FROM match_stats)
        """).fetchone()

        conn.close()

        assert orphans[0] == 0, "Pas d'événements orphelins"

    def test_kda_computation_correct(self, integration_db: tuple[Path, str]):
        """Vérifie que le KDA est calculé correctement."""
        db_path, xuid = integration_db
        conn = duckdb.connect(str(db_path), read_only=True)

        # Vérifier quelques matchs
        result = conn.execute("""
            SELECT match_id, kills, deaths, assists, kda
            FROM match_stats
            LIMIT 20
        """).fetchall()

        conn.close()

        for row in result:
            match_id, kills, deaths, assists, kda = row
            expected_kda = (kills + assists / 3) / max(deaths, 1)
            # Tolérance pour arrondis
            assert abs(kda - expected_kda) < 0.5, f"KDA cohérent pour {match_id}"
