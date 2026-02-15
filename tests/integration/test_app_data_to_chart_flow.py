"""Tests d'intégration: flux BDD -> repository -> analyse -> graphes.

Valide un scénario minimal mais complet sur des données DuckDB temporaires.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

duckdb = pytest.importorskip("duckdb")
pytest.importorskip("polars")


@pytest.fixture
def app_flow_db(tmp_path):
    """Crée une DB temporaire couvrant les domaines data principaux."""
    db_path = tmp_path / "app_flow.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
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
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                kda DOUBLE,
                accuracy DOUBLE,
                headshot_kills INTEGER,
                max_killing_spree INTEGER,
                time_played_seconds INTEGER,
                avg_life_seconds DOUBLE,
                my_team_score INTEGER,
                enemy_team_score INTEGER,
                team_mmr DOUBLE,
                enemy_mmr DOUBLE,
                personal_score INTEGER,
                performance_score DOUBLE,
                shots_fired INTEGER,
                shots_hit INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE medals_earned (
                match_id VARCHAR,
                medal_name_id INTEGER,
                count INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE highlight_events (
                match_id VARCHAR,
                event_type VARCHAR,
                time_ms INTEGER,
                xuid VARCHAR,
                gamertag VARCHAR
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE match_participants (
                match_id VARCHAR,
                xuid VARCHAR,
                gamertag VARCHAR,
                rank INTEGER,
                personal_score INTEGER,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                shots_fired INTEGER,
                shots_hit INTEGER,
                damage_dealt INTEGER,
                damage_taken INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE xuid_aliases (
                xuid VARCHAR,
                gamertag VARCHAR
            )
            """
        )

        t0 = datetime.now(timezone.utc)
        rows_match_stats = [
            (
                "m1",
                t0,
                "map1",
                "Recharge",
                "pl1",
                "Ranked Arena",
                "pair1",
                "Slayer on Recharge",
                "gv1",
                "Slayer",
                2,
                1,
                15,
                9,
                6,
                1.67,
                45.0,
                6,
                4,
                600,
                42.0,
                50,
                42,
                1500.0,
                1480.0,
                1900,
                72.0,
                220,
                100,
            ),
            (
                "m2",
                t0 + timedelta(minutes=20),
                "map2",
                "Live Fire",
                "pl2",
                "Quick Play",
                "pair2",
                "Oddball on Live Fire",
                "gv2",
                "Oddball",
                3,
                1,
                10,
                12,
                5,
                0.92,
                39.0,
                3,
                3,
                620,
                35.0,
                38,
                50,
                1460.0,
                1510.0,
                1500,
                58.0,
                200,
                78,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO match_stats (
                match_id, start_time, map_id, map_name, playlist_id, playlist_name,
                pair_id, pair_name, game_variant_id, game_variant_name, outcome, team_id,
                kills, deaths, assists, kda, accuracy, headshot_kills, max_killing_spree,
                time_played_seconds, avg_life_seconds, my_team_score, enemy_team_score,
                team_mmr, enemy_mmr, personal_score, performance_score, shots_fired, shots_hit
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_match_stats,
        )

        conn.execute(
            """
            INSERT INTO medals_earned (match_id, medal_name_id, count)
            VALUES ('m1', 1512363953, 1), ('m1', 1512363954, 2), ('m2', 1512363953, 1)
            """
        )

        conn.execute(
            """
            INSERT INTO highlight_events (match_id, event_type, time_ms, xuid, gamertag)
            VALUES
                ('m1', 'Kill', 1000, 'x_me', 'Me'),
                ('m1', 'Kill', 2500, 'x_friend', 'Friend'),
                ('m2', 'Death', 1800, 'x_friend', 'Friend'),
                ('m2', 'Death', 3000, 'x_me', 'Me')
            """
        )

        conn.execute(
            """
            INSERT INTO match_participants (
                match_id, xuid, gamertag, rank, personal_score, kills, deaths, assists,
                shots_fired, shots_hit, damage_dealt, damage_taken
            ) VALUES
                ('m1', 'x_me', 'Me', 1, 1900, 15, 9, 6, 220, 100, 3200, 2600),
                ('m1', 'x_friend', 'Friend', 2, 1700, 12, 11, 8, 210, 95, 2800, 2900),
                ('m2', 'x_me', 'Me', 3, 1500, 10, 12, 5, 200, 78, 2500, 3000)
            """
        )

        conn.execute(
            """
            INSERT INTO xuid_aliases (xuid, gamertag)
            VALUES ('x_me', 'Me'), ('x_friend', 'Friend')
            """
        )
    finally:
        conn.close()

    return db_path


def test_app_data_to_chart_flow(app_flow_db) -> None:
    """Valide le flux complet depuis DuckDB jusqu'aux graphes."""
    from src.analysis.friends_impact import build_impact_matrix, get_all_impact_events
    from src.data.repositories.duckdb_repo import DuckDBRepository
    from src.visualization.distributions import plot_histogram, plot_win_ratio_heatmap
    from src.visualization.friends_impact_heatmap import plot_friends_impact_heatmap

    repo = DuckDBRepository(str(app_flow_db), xuid="x_me", read_only=True)
    try:
        # 1) Chargement repository (contrat data applicatif)
        stats_df = repo.load_match_stats_as_polars()
        assert not stats_df.is_empty()
        assert {"match_id", "outcome", "start_time"}.issubset(stats_df.columns)

        top_medals = repo.load_top_medals(["m1", "m2"], top_n=5)
        assert len(top_medals) >= 1

        # 2) Domaine Timeseries/Distribution
        stats_pd = pd.DataFrame(stats_df.to_dicts())
        conn = duckdb.connect(str(app_flow_db), read_only=True)
        try:
            score_rows = conn.execute(
                "SELECT match_id, personal_score FROM match_stats ORDER BY start_time ASC"
            ).fetchall()
        finally:
            conn.close()

        score_map = {
            str(match_id): float(personal_score) for match_id, personal_score in score_rows
        }
        stats_pd["personal_score"] = stats_pd["match_id"].map(score_map)
        fig_hist = plot_histogram(
            stats_pd["personal_score"],
            title="Score personnel",
            x_label="Score",
        )
        assert len(fig_hist.data) >= 1

        fig_heat_win = plot_win_ratio_heatmap(
            stats_pd,
            title="Win Ratio",
            min_matches=1,
        )
        assert len(fig_heat_win.data) >= 1

        # 3) Domaine Impact coéquipiers
        conn = duckdb.connect(str(app_flow_db), read_only=True)
        try:
            events_rows = conn.execute(
                "SELECT match_id, xuid, gamertag, event_type, time_ms FROM highlight_events"
            ).fetchall()
            match_rows = conn.execute("SELECT match_id, outcome FROM match_stats").fetchall()
        finally:
            conn.close()

        import polars as pl

        events_df = pl.DataFrame(
            {
                "match_id": [r[0] for r in events_rows],
                "xuid": [r[1] for r in events_rows],
                "gamertag": [r[2] for r in events_rows],
                "event_type": [r[3] for r in events_rows],
                "time_ms": [r[4] for r in events_rows],
            }
        )
        matches_df = pl.DataFrame(
            {
                "match_id": [r[0] for r in match_rows],
                "outcome": [r[1] for r in match_rows],
            }
        )

        fb, clutch, casualty, scores = get_all_impact_events(
            events_df,
            matches_df,
            friend_xuids={"x_me", "x_friend"},
        )
        assert len(scores) >= 1

        impact_matrix = build_impact_matrix(
            fb,
            clutch,
            casualty,
            match_ids=["m1", "m2"],
            gamertags=sorted(scores.keys()),
        )
        assert not impact_matrix.is_empty()

        fig_impact = plot_friends_impact_heatmap(impact_matrix, max_matches=10)
        assert len(fig_impact.data) >= 1
    finally:
        repo.close()
