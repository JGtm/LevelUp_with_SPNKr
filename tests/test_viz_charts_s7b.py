"""Tests pour les modules de visualisation (antagonist_charts + objective_charts).

Sprint 7bis – Tâche 7b.9
Toutes les fonctions retournent un go.Figure — pas de mock Streamlit nécessaire.
"""

from __future__ import annotations

import plotly.graph_objects as go
import polars as pl

# ═══════════════════════════════════════════════════════════════════
# antagonist_charts
# ═══════════════════════════════════════════════════════════════════


class TestPlotKillerVictimStackedBars:
    """Tests pour plot_killer_victim_stacked_bars."""

    def test_empty_df_returns_figure(self):
        from src.visualization.antagonist_charts import plot_killer_victim_stacked_bars

        df = pl.DataFrame(
            schema={
                "killer_xuid": pl.Utf8,
                "killer_gamertag": pl.Utf8,
                "victim_xuid": pl.Utf8,
                "victim_gamertag": pl.Utf8,
                "kill_count": pl.Int64,
                "match_id": pl.Utf8,
            }
        )
        fig = plot_killer_victim_stacked_bars(df)
        assert isinstance(fig, go.Figure)

    def test_with_data_returns_figure(self):
        from src.visualization.antagonist_charts import plot_killer_victim_stacked_bars

        df = pl.DataFrame(
            {
                "killer_xuid": ["x1", "x1", "x2"],
                "killer_gamertag": ["Alice", "Alice", "Bob"],
                "victim_xuid": ["x2", "x3", "x1"],
                "victim_gamertag": ["Bob", "Charlie", "Alice"],
                "kill_count": [5, 3, 2],
                "match_id": ["m1", "m1", "m1"],
            }
        )
        fig = plot_killer_victim_stacked_bars(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_filter_by_match_id(self):
        from src.visualization.antagonist_charts import plot_killer_victim_stacked_bars

        df = pl.DataFrame(
            {
                "killer_xuid": ["x1", "x1"],
                "killer_gamertag": ["Alice", "Alice"],
                "victim_xuid": ["x2", "x2"],
                "victim_gamertag": ["Bob", "Bob"],
                "kill_count": [5, 3],
                "match_id": ["m1", "m2"],
            }
        )
        fig = plot_killer_victim_stacked_bars(df, match_id="m1")
        assert isinstance(fig, go.Figure)

    def test_nonexistent_match_returns_empty_figure(self):
        from src.visualization.antagonist_charts import plot_killer_victim_stacked_bars

        df = pl.DataFrame(
            {
                "killer_xuid": ["x1"],
                "killer_gamertag": ["Alice"],
                "victim_xuid": ["x2"],
                "victim_gamertag": ["Bob"],
                "kill_count": [5],
                "match_id": ["m1"],
            }
        )
        fig = plot_killer_victim_stacked_bars(df, match_id="nonexistent")
        assert isinstance(fig, go.Figure)
        # Pas de données → annotation "Aucune donnée"
        assert len(fig.data) == 0

    def test_with_rank_map(self):
        from src.visualization.antagonist_charts import plot_killer_victim_stacked_bars

        df = pl.DataFrame(
            {
                "killer_xuid": ["x1", "x2"],
                "killer_gamertag": ["Alice", "Bob"],
                "victim_xuid": ["x2", "x1"],
                "victim_gamertag": ["Bob", "Alice"],
                "kill_count": [5, 3],
                "match_id": ["m1", "m1"],
            }
        )
        fig = plot_killer_victim_stacked_bars(df, rank_by_xuid={"x1": 1, "x2": 2})
        assert isinstance(fig, go.Figure)


class TestPlotKdTimeseries:
    """Tests pour plot_kd_timeseries."""

    def test_empty_df(self):
        from src.visualization.antagonist_charts import plot_kd_timeseries

        df = pl.DataFrame(
            schema={
                "minute": pl.Int64,
                "kills": pl.Int64,
                "deaths": pl.Int64,
                "net_kd": pl.Int64,
                "cumulative_net_kd": pl.Int64,
            }
        )
        fig = plot_kd_timeseries(df)
        assert isinstance(fig, go.Figure)

    def test_with_data(self):
        from src.visualization.antagonist_charts import plot_kd_timeseries

        df = pl.DataFrame(
            {
                "minute": [1, 2, 3, 4],
                "kills": [2, 1, 3, 0],
                "deaths": [1, 2, 0, 1],
                "net_kd": [1, -1, 3, -1],
                "cumulative_net_kd": [1, 0, 3, 2],
            }
        )
        fig = plot_kd_timeseries(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 2  # Barres kills + barres deaths


class TestPlotNemesisVictimSummary:
    """Tests pour plot_nemesis_victim_summary."""

    def test_returns_figure(self):
        from src.visualization.antagonist_charts import plot_nemesis_victim_summary

        nemesis = {"gamertag": "Bob", "times_killed_by": 10, "matches": 5}
        victim = {"gamertag": "Charlie", "times_killed": 8, "matches": 4}
        fig = plot_nemesis_victim_summary(nemesis, victim)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 2

    def test_empty_data(self):
        from src.visualization.antagonist_charts import plot_nemesis_victim_summary

        nemesis = {"gamertag": "N/A", "times_killed_by": 0}
        victim = {"gamertag": "N/A", "times_killed": 0}
        fig = plot_nemesis_victim_summary(nemesis, victim)
        assert isinstance(fig, go.Figure)


class TestPlotTopAntagonistsBars:
    """Tests pour plot_top_antagonists_bars."""

    def test_returns_figure(self):
        from src.visualization.antagonist_charts import plot_top_antagonists_bars

        nemeses = [
            {"killer_gamertag": "Nem1", "times_killed_by": 12},
            {"killer_gamertag": "Nem2", "times_killed_by": 8},
        ]
        victims = [
            {"victim_gamertag": "Vic1", "times_killed": 15},
            {"victim_gamertag": "Vic2", "times_killed": 10},
        ]
        fig = plot_top_antagonists_bars(nemeses, victims)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 2

    def test_empty_lists(self):
        from src.visualization.antagonist_charts import plot_top_antagonists_bars

        fig = plot_top_antagonists_bars([], [])
        assert isinstance(fig, go.Figure)


# ═══════════════════════════════════════════════════════════════════
# objective_charts
# ═══════════════════════════════════════════════════════════════════


class TestPlotObjectiveVsKillsScatter:
    """Tests pour plot_objective_vs_kills_scatter."""

    def test_empty_awards(self):
        from src.visualization.objective_charts import plot_objective_vs_kills_scatter

        awards_df = pl.DataFrame(
            schema={"match_id": pl.Utf8, "score_category": pl.Utf8, "points": pl.Int64}
        )
        stats_df = pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "kills": pl.Int64,
                "map_name": pl.Utf8,
                "start_time": pl.Utf8,
            }
        )
        fig = plot_objective_vs_kills_scatter(awards_df, stats_df)
        assert isinstance(fig, go.Figure)

    def test_with_data(self):
        from src.visualization.objective_charts import plot_objective_vs_kills_scatter

        awards_df = pl.DataFrame(
            {
                "match_id": ["m1", "m1", "m2"],
                "score_category": ["objective", "kill", "objective"],
                "points": [100, 50, 200],
            }
        )
        stats_df = pl.DataFrame(
            {
                "match_id": ["m1", "m2"],
                "kills": [10, 15],
                "map_name": ["Recharge", "Streets"],
                "start_time": ["2025-01-01", "2025-01-02"],
            }
        )
        fig = plot_objective_vs_kills_scatter(awards_df, stats_df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1


class TestPlotObjectiveBreakdownBars:
    """Tests pour plot_objective_breakdown_bars."""

    def test_empty_df(self):
        from src.visualization.objective_charts import plot_objective_breakdown_bars

        df = pl.DataFrame(schema={"score_category": pl.Utf8, "points": pl.Int64})
        fig = plot_objective_breakdown_bars(df)
        assert isinstance(fig, go.Figure)

    def test_with_categories(self):
        from src.visualization.objective_charts import plot_objective_breakdown_bars

        df = pl.DataFrame(
            {
                "score_category": ["objective", "kill", "assist", "objective"],
                "points": [100, 50, 30, 150],
            }
        )
        fig = plot_objective_breakdown_bars(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1


class TestPlotTopPlayersObjectiveBars:
    """Tests pour plot_top_players_objective_bars."""

    def test_empty_list(self):
        from src.visualization.objective_charts import plot_top_players_objective_bars

        fig = plot_top_players_objective_bars([])
        assert isinstance(fig, go.Figure)

    def test_with_dict_rankings(self):
        from src.visualization.objective_charts import plot_top_players_objective_bars

        rankings = [
            {"gamertag": "Alice", "total_objective_score": 5000, "matches_count": 50},
            {"gamertag": "Bob", "total_objective_score": 3000, "matches_count": 30},
        ]
        fig = plot_top_players_objective_bars(rankings, top_n=5)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1


class TestPlotObjectiveRatioGauge:
    """Tests pour plot_objective_ratio_gauge."""

    def test_zero_ratio(self):
        from src.visualization.objective_charts import plot_objective_ratio_gauge

        fig = plot_objective_ratio_gauge(0.0)
        assert isinstance(fig, go.Figure)

    def test_half_ratio(self):
        from src.visualization.objective_charts import plot_objective_ratio_gauge

        fig = plot_objective_ratio_gauge(0.5)
        assert isinstance(fig, go.Figure)

    def test_full_ratio(self):
        from src.visualization.objective_charts import plot_objective_ratio_gauge

        fig = plot_objective_ratio_gauge(1.0)
        assert isinstance(fig, go.Figure)


class TestPlotAssistBreakdownPie:
    """Tests pour plot_assist_breakdown_pie."""

    def test_with_dict(self):
        from src.visualization.objective_charts import plot_assist_breakdown_pie

        data = {
            "kill_assists": 50,
            "mark_assists": 20,
            "emp_assists": 10,
            "other_assists": 5,
        }
        fig = plot_assist_breakdown_pie(data)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_all_zero(self):
        from src.visualization.objective_charts import plot_assist_breakdown_pie

        data = {
            "kill_assists": 0,
            "mark_assists": 0,
            "emp_assists": 0,
            "other_assists": 0,
        }
        fig = plot_assist_breakdown_pie(data)
        assert isinstance(fig, go.Figure)

    def test_unknown_format(self):
        from src.visualization.objective_charts import plot_assist_breakdown_pie

        fig = plot_assist_breakdown_pie("invalid data")
        assert isinstance(fig, go.Figure)
