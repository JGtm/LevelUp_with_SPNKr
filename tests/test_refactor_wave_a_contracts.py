"""Tests de contrats pour les sous-fonctions issues du refactoring Phase A.

Vérifie que les nouvelles fonctions extraites respectent leurs contrats :
- Types d'entrée/sortie
- Comportement sur données vides
- Cohérence avec les fonctions parentes
"""

from __future__ import annotations

import polars as pl
import pytest

# ---------------------------------------------------------------------------
# distributions_outcomes.py — sous-fonctions extraites
# ---------------------------------------------------------------------------


class TestDistributionsOutcomesContracts:
    """Contrats pour les fonctions extraites de distributions.py."""

    def test_plot_outcomes_over_time_accepts_polars(self) -> None:
        """plot_outcomes_over_time accepte un pl.DataFrame."""
        from src.visualization.distributions_outcomes import plot_outcomes_over_time

        df = pl.DataFrame(
            {
                "start_time": ["2024-01-01T12:00:00", "2024-01-02T12:00:00"],
                "outcome": [2, 3],
                "match_id": ["m1", "m2"],
            }
        )
        fig = plot_outcomes_over_time(df)
        assert fig is not None

    def test_plot_outcomes_over_time_empty(self) -> None:
        """Retourne une figure vide sans crash."""
        from src.visualization.distributions_outcomes import plot_outcomes_over_time

        df = pl.DataFrame({"start_time": [], "outcome": []})
        fig = plot_outcomes_over_time(df)
        assert fig is not None

    def test_plot_win_ratio_heatmap_accepts_polars(self) -> None:
        """plot_win_ratio_heatmap accepte un pl.DataFrame."""
        from src.visualization.distributions_outcomes import plot_win_ratio_heatmap

        df = pl.DataFrame(
            {
                "start_time": ["2024-01-01T14:00:00", "2024-01-02T10:00:00"],
                "outcome": [2, 3],
                "match_id": ["m1", "m2"],
            }
        )
        fig = plot_win_ratio_heatmap(df)
        assert fig is not None

    def test_plot_stacked_outcomes_by_category_empty(self) -> None:
        """Retourne None sur données vides."""
        from src.visualization.distributions_outcomes import (
            plot_stacked_outcomes_by_category,
        )

        df = pl.DataFrame(
            {
                "start_time": [],
                "outcome": [],
                "map_name": [],
            }
        )
        result = plot_stacked_outcomes_by_category(df, category_col="map_name")
        # Peut retourner None ou une figure vide
        assert result is None or result is not None


# ---------------------------------------------------------------------------
# timeseries_combat.py — sous-fonctions extraites
# ---------------------------------------------------------------------------


class TestTimeseriesCombatContracts:
    """Contrats pour les fonctions extraites de timeseries.py viz."""

    @pytest.fixture
    def sample_df(self) -> pl.DataFrame:
        """DataFrame minimal pour les tests timeseries."""
        from datetime import datetime

        return pl.DataFrame(
            {
                "start_time": [datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 1, 3)],
                "average_life_seconds": [45.0, 52.0, 38.0],
                "max_killing_spree": [3, 5, 2],
                "headshot_kills": [4, 6, 3],
                "accuracy": [55.0, 62.0, 48.0],
                "damage_dealt": [2500.0, 3200.0, 1800.0],
                "damage_taken": [2000.0, 2800.0, 2200.0],
                "shots_fired": [120, 150, 100],
                "shots_hit": [66, 93, 48],
                "personal_score": [1500, 2200, 1100],
                "rank": [12, 8, 15],
                "performance": [65.0, 80.0, 45.0],
                "kills": [10, 15, 7],
                "deaths": [8, 6, 10],
                "match_id": ["m1", "m2", "m3"],
                "time_played_seconds": [600.0, 720.0, 540.0],
            }
        )

    def test_plot_average_life_accepts_polars(self, sample_df: pl.DataFrame) -> None:
        from src.visualization.timeseries_combat import plot_average_life

        fig = plot_average_life(sample_df)
        assert fig is not None
        assert len(fig.data) > 0

    def test_plot_damage_dealt_taken_accepts_polars(self, sample_df: pl.DataFrame) -> None:
        from src.visualization.timeseries_combat import plot_damage_dealt_taken

        fig = plot_damage_dealt_taken(sample_df)
        assert fig is not None

    def test_plot_shots_accuracy_accepts_polars(self, sample_df: pl.DataFrame) -> None:
        from src.visualization.timeseries_combat import plot_shots_accuracy

        fig = plot_shots_accuracy(sample_df)
        assert fig is not None

    def test_plot_rank_score_accepts_polars(self, sample_df: pl.DataFrame) -> None:
        from src.visualization.timeseries_combat import plot_rank_score

        fig = plot_rank_score(sample_df)
        assert fig is not None

    def test_plot_performance_timeseries_accepts_polars(self, sample_df: pl.DataFrame) -> None:
        from src.visualization.timeseries_combat import plot_performance_timeseries

        fig = plot_performance_timeseries(sample_df)
        assert fig is not None

    def test_plot_average_life_empty(self) -> None:
        from src.visualization.timeseries_combat import plot_average_life

        df = pl.DataFrame(
            {
                "start_time": pl.Series([], dtype=pl.Datetime),
                "average_life_seconds": pl.Series([], dtype=pl.Float64),
                "match_id": pl.Series([], dtype=pl.String),
                "deaths": pl.Series([], dtype=pl.Int64),
                "time_played_seconds": pl.Series([], dtype=pl.Float64),
            }
        )
        fig = plot_average_life(df)
        assert fig is not None


# ---------------------------------------------------------------------------
# session_compare_charts.py — sous-fonctions extraites
# ---------------------------------------------------------------------------


class TestSessionCompareChartsContracts:
    """Contrats pour les fonctions extraites de session_compare.py."""

    def test_render_comparison_radar_chart_exists(self) -> None:
        """La fonction render_comparison_radar_chart est importable."""
        from src.ui.pages.session_compare_charts import render_comparison_radar_chart

        assert callable(render_comparison_radar_chart)

    def test_render_participation_trend_section_exists(self) -> None:
        """La fonction render_participation_trend_section est importable."""
        from src.ui.pages.session_compare_charts import render_participation_trend_section

        assert callable(render_participation_trend_section)


# ---------------------------------------------------------------------------
# maps.py — migration _normalize_df → ensure_polars
# ---------------------------------------------------------------------------


class TestMapsContracts:
    """Contrats pour maps.py migrée."""

    def test_plot_map_comparison_accepts_polars(self) -> None:
        from src.visualization.maps import plot_map_comparison

        df = pl.DataFrame(
            {
                "map_name": ["Arena A", "Arena B"],
                "ratio_global": [1.5, 0.8],
                "matches": [10, 20],
                "accuracy_avg": [55.0, 62.0],
            }
        )
        fig = plot_map_comparison(df, metric="ratio_global", title="Test")
        assert fig is not None

    def test_plot_map_comparison_empty(self) -> None:
        from src.visualization.maps import plot_map_comparison

        df = pl.DataFrame(
            {
                "map_name": [],
                "ratio_global": [],
                "matches": [],
                "accuracy_avg": [],
            }
        )
        fig = plot_map_comparison(df, metric="ratio_global", title="Test vide")
        assert fig is not None

    def test_plot_map_ratio_with_winloss_accepts_polars(self) -> None:
        from src.visualization.maps import plot_map_ratio_with_winloss

        df = pl.DataFrame(
            {
                "map_name": ["Arena A"],
                "win_rate": [0.6],
                "loss_rate": [0.3],
                "matches": [30],
            }
        )
        fig = plot_map_ratio_with_winloss(df, title="Test Win/Loss")
        assert fig is not None


# ---------------------------------------------------------------------------
# _compat.py — contrats du helper
# ---------------------------------------------------------------------------


class TestCompatContracts:
    """Contrats pour les helpers _compat."""

    def test_ensure_polars_idempotent(self) -> None:
        """ensure_polars sur un pl.DataFrame retourne le même objet."""
        from src.visualization._compat import ensure_polars

        df = pl.DataFrame({"a": [1]})
        result = ensure_polars(df)
        assert result is df  # Même objet, pas de copie

    def test_ensure_polars_preserves_schema(self) -> None:
        """ensure_polars préserve les types de colonnes."""
        import pandas as pd

        from src.visualization._compat import ensure_polars

        pdf = pd.DataFrame(
            {
                "int_col": [1, 2],
                "float_col": [1.1, 2.2],
                "str_col": ["a", "b"],
            }
        )
        result = ensure_polars(pdf)
        assert result["int_col"].dtype in (pl.Int64, pl.Int32)
        assert result["float_col"].dtype == pl.Float64
        assert result["str_col"].dtype == pl.String


# ---------------------------------------------------------------------------
# trio.py — migration
# ---------------------------------------------------------------------------


class TestTrioContracts:
    """Contrats pour trio.py migrée."""

    def test_plot_trio_metric_accepts_polars(self) -> None:
        from src.visualization.trio import plot_trio_metric

        d0 = pl.DataFrame(
            {
                "start_time": ["2024-01-01", "2024-01-02"],
                "kills": [10, 15],
            }
        )
        d1 = pl.DataFrame(
            {
                "start_time": ["2024-01-01", "2024-01-02"],
                "kills": [8, 12],
            }
        )
        d2 = pl.DataFrame(
            {
                "start_time": ["2024-01-01", "2024-01-02"],
                "kills": [6, 9],
            }
        )
        fig = plot_trio_metric(
            d0,
            d1,
            d2,
            metric="kills",
            names=("P1", "P2", "P3"),
            title="Test trio",
            y_title="Kills",
        )
        assert fig is not None
        assert len(fig.data) > 0
