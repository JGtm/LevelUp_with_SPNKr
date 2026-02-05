"""Tests de validation des données pour prévenir les régressions.

Ces tests vérifient que les données critiques (accuracy, médailles, events)
sont correctement stockées et accessibles.
"""

from datetime import datetime, timezone

import duckdb
import pytest

from scripts.diagnose_player_db import diagnose


@pytest.fixture
def test_db_with_accuracy(tmp_path):
    """Crée une DB de test avec des données d'accuracy."""
    db_path = tmp_path / "test_accuracy.duckdb"
    conn = duckdb.connect(str(db_path))

    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP,
            accuracy DOUBLE,
            kills INTEGER,
            deaths INTEGER
        )
    """)

    # Insérer des matchs avec et sans accuracy
    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, accuracy, kills, deaths)
        VALUES (?, ?, ?, ?, ?)
    """,
        ["match_1", datetime.now(timezone.utc), 45.5, 10, 5],
    )

    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, accuracy, kills, deaths)
        VALUES (?, ?, ?, ?, ?)
    """,
        ["match_2", datetime.now(timezone.utc), 50.0, 15, 4],
    )

    conn.execute(
        """
        INSERT INTO match_stats (match_id, start_time, accuracy, kills, deaths)
        VALUES (?, ?, ?, ?, ?)
    """,
        ["match_3", datetime.now(timezone.utc), None, 20, 3],
    )  # NULL accuracy

    conn.commit()
    conn.close()

    yield str(db_path)


@pytest.fixture
def test_db_with_medals(tmp_path):
    """Crée une DB de test avec des médailles."""
    db_path = tmp_path / "test_medals.duckdb"
    conn = duckdb.connect(str(db_path))

    conn.execute("""
        CREATE TABLE medals_earned (
            match_id VARCHAR,
            medal_name_id INTEGER,
            count INTEGER
        )
    """)

    conn.execute(
        """
        INSERT INTO medals_earned (match_id, medal_name_id, count)
        VALUES (?, ?, ?)
    """,
        ["match_1", 1512363953, 2],
    )  # Perfect

    conn.execute(
        """
        INSERT INTO medals_earned (match_id, medal_name_id, count)
        VALUES (?, ?, ?)
    """,
        ["match_1", 1512363954, 1],
    )  # Killjoy

    conn.commit()
    conn.close()

    yield str(db_path)


@pytest.fixture
def test_db_with_events(tmp_path):
    """Crée une DB de test avec des highlight events."""
    db_path = tmp_path / "test_events.duckdb"
    conn = duckdb.connect(str(db_path))

    conn.execute("""
        CREATE TABLE highlight_events (
            match_id VARCHAR,
            event_type VARCHAR,
            time_ms INTEGER,
            xuid VARCHAR,
            gamertag VARCHAR
        )
    """)

    conn.execute(
        """
        INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag)
        VALUES (?, ?, ?, ?, ?)
    """,
        ["match_1", "Kill", 1000, "2533274823110022", "Player1"],
    )

    conn.execute(
        """
        INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag)
        VALUES (?, ?, ?, ?, ?)
    """,
        ["match_1", "Death", 2000, "2533274823110022", "Player1"],
    )

    conn.commit()
    conn.close()

    yield str(db_path)


def test_diagnose_detects_accuracy_data(test_db_with_accuracy):
    """Test que le diagnostic détecte correctement les données d'accuracy."""
    results = diagnose(test_db_with_accuracy)

    assert "match_stats" in results
    ms = results["match_stats"]

    assert ms["total"] == 3, "Doit détecter 3 matchs"
    assert ms["with_accuracy"] == 2, "Doit détecter 2 matchs avec accuracy"
    assert ms["null_accuracy"] == 1, "Doit détecter 1 match sans accuracy"
    assert ms["avg_accuracy"] is not None, "Doit calculer une moyenne d'accuracy"


def test_diagnose_detects_medals(test_db_with_medals):
    """Test que le diagnostic détecte correctement les médailles."""
    results = diagnose(test_db_with_medals)

    assert "medals" in results
    medals = results["medals"]

    assert medals["total"] == 2, "Doit détecter 2 médailles"
    assert medals["distinct_matches"] == 1, "Doit détecter 1 match distinct"
    assert medals["distinct_medals"] == 2, "Doit détecter 2 types de médailles distincts"


def test_diagnose_detects_highlight_events(test_db_with_events):
    """Test que le diagnostic détecte correctement les highlight events."""
    results = diagnose(test_db_with_events)

    assert "highlight_events" in results
    events = results["highlight_events"]

    assert events["total"] == 2, "Doit détecter 2 events"
    assert events["distinct_matches"] == 1, "Doit détecter 1 match distinct"
    assert events["distinct_types"] == 2, "Doit détecter 2 types d'événements"


def test_diagnose_handles_missing_tables(tmp_path):
    """Test que le diagnostic gère correctement les tables manquantes."""
    db_path = tmp_path / "test_minimal.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("CREATE TABLE match_stats (match_id VARCHAR PRIMARY KEY)")
    conn.commit()
    conn.close()

    results = diagnose(str(db_path))

    # medals_earned et highlight_events n'existent pas, mais le diagnostic ne doit pas crasher
    assert "match_stats" in results
    assert "medals" in results or "highlight_events" in results


def test_accuracy_not_all_null(test_db_with_accuracy):
    """Test que l'accuracy n'est pas NULL partout (régression critique)."""
    conn = duckdb.connect(test_db_with_accuracy)

    result = conn.execute("""
        SELECT COUNT(*) as total, COUNT(accuracy) as with_acc
        FROM match_stats
    """).fetchone()

    total, with_acc = result

    assert total > 0, "Doit avoir au moins un match"
    assert with_acc > 0, "Au moins certains matchs doivent avoir accuracy non-NULL"

    conn.close()
