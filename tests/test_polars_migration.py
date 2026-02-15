"""Tests unitaires pour la migration Pandas → Polars.

Ce module teste spécifiquement que les fonctions migrées acceptent et fonctionnent
correctement avec Polars DataFrames, tout en maintenant la compatibilité avec Pandas.

Couverture cible : >80% des fonctions migrées.
"""

from __future__ import annotations

import pytest

try:
    import pandas as pd
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None
    pd = None

pytestmark = pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars not installed")


# =============================================================================
# TESTS: Couche données
# =============================================================================


class TestDataLayerPolars:
    """Tests pour la couche données avec Polars."""

    def test_load_df_optimized_returns_polars(self):
        """Vérifie que load_df_optimized retourne un DataFrame Polars."""
        # Note: Ce test nécessite une DB réelle, donc on skip si pas disponible
        # En pratique, on testerait avec une DB de test
        pytest.skip("Requires actual DuckDB database")

    def test_load_match_data_returns_polars(self):
        """Vérifie que load_match_data retourne un DataFrame Polars."""
        pytest.skip("Requires actual DuckDB database")


# =============================================================================
# TESTS: Analyses avec Polars
# =============================================================================


class TestAnalysisPolars:
    """Tests pour les fonctions d'analyse avec Polars."""

    def test_compute_aggregated_stats_polars(self):
        """Test compute_aggregated_stats avec Polars."""
        from src.analysis.stats import compute_aggregated_stats

        df = pl.DataFrame(
            {
                "kills": [10, 15, 20],
                "deaths": [5, 10, 10],
                "assists": [4, 6, 8],
                "accuracy": [40.0, 45.0, 50.0],
                "kda": [2.0, 1.5, 2.0],
            }
        )

        stats = compute_aggregated_stats(df)
        assert stats is not None
        assert "total_kills" in stats or "kills" in stats

    def test_compute_outcome_rates_polars(self):
        """Test compute_outcome_rates avec Polars."""
        from src.analysis.stats import compute_outcome_rates

        df = pl.DataFrame(
            {
                "outcome": [2, 2, 3, 1, 2, 3, 4],
            }
        )

        rates = compute_outcome_rates(df)
        assert rates.wins == 3
        assert rates.losses == 2
        assert rates.ties == 1
        assert rates.no_finish == 1
        assert rates.total == 7

    def test_compute_global_ratio_polars(self):
        """Test compute_global_ratio avec Polars."""
        from src.analysis.stats import compute_global_ratio

        df = pl.DataFrame(
            {
                "kills": [10, 15, 20],
                "deaths": [5, 10, 10],
                "assists": [4, 6, 8],
            }
        )

        result = compute_global_ratio(df)
        assert result == pytest.approx(2.16)

    def test_compute_map_breakdown_polars(self):
        """Test compute_map_breakdown avec Polars."""
        from src.analysis.maps import compute_map_breakdown

        df = pl.DataFrame(
            {
                "map_name": ["Recharge", "Streets", "Recharge", "Live Fire"],
                "kills": [10, 15, 12, 8],
                "deaths": [5, 10, 6, 4],
                "outcome": [2, 3, 2, 2],
            }
        )

        breakdown = compute_map_breakdown(df)
        assert breakdown is not None
        assert len(breakdown) > 0


# =============================================================================
# TESTS: Visualisations avec Polars
# =============================================================================


class TestVisualizationsPolars:
    """Tests pour les fonctions de visualisation avec Polars."""

    def test_plot_timeseries_polars(self, sample_match_df_polars: pl.DataFrame):
        """Test plot_timeseries avec Polars."""
        from src.visualization.timeseries import plot_timeseries

        fig = plot_timeseries(sample_match_df_polars, "kills")
        assert fig is not None

    def test_plot_kda_distribution_polars(self, sample_match_df_polars: pl.DataFrame):
        """Test plot_kda_distribution avec Polars."""
        from src.visualization.distributions import plot_kda_distribution

        fig = plot_kda_distribution(sample_match_df_polars)
        assert fig is not None

    def test_plot_outcomes_over_time_polars(self, sample_match_df_polars: pl.DataFrame):
        """Test plot_outcomes_over_time avec Polars."""
        from src.visualization.distributions import plot_outcomes_over_time

        fig, label = plot_outcomes_over_time(sample_match_df_polars)
        assert fig is not None
        assert isinstance(label, str)

    def test_plot_performance_timeseries_polars(self, sample_match_df_polars: pl.DataFrame):
        """Test plot_performance_timeseries avec Polars."""
        from src.visualization.timeseries import plot_performance_timeseries

        # Ajouter une colonne performance_score si nécessaire
        df = sample_match_df_polars.with_columns(pl.lit(50.0).alias("performance_score"))

        fig = plot_performance_timeseries(df)
        assert fig is not None


# =============================================================================
# TESTS: Helpers avec Polars
# =============================================================================


class TestHelpersPolars:
    """Tests pour les fonctions helpers avec Polars."""

    def test_apply_filters_polars(self, sample_match_df_polars: pl.DataFrame):
        """Test apply_filters avec Polars."""
        from src.app.filters_render import apply_filters

        filters = {}
        df_filtered = apply_filters(sample_match_df_polars, filters)
        assert df_filtered is not None

    def test_compute_kpi_stats_polars(self, sample_match_df_polars: pl.DataFrame):
        """Test compute_kpi_stats avec Polars."""
        from src.app.kpis import compute_kpi_stats

        stats = compute_kpi_stats(sample_match_df_polars)
        assert stats is not None

    def test_add_ui_columns_polars(self, sample_match_df_polars: pl.DataFrame):
        """Test add_ui_columns avec Polars."""
        from src.app.filters import add_ui_columns

        df_with_ui = add_ui_columns(sample_match_df_polars)
        assert df_with_ui is not None


# =============================================================================
# TESTS: Compatibilité Pandas/Polars
# =============================================================================


class TestPandasPolarsCompatibility:
    """Tests pour vérifier la compatibilité entre Pandas et Polars."""

    def test_compute_global_ratio_same_result(self):
        """Vérifie que compute_global_ratio donne le même résultat avec Pandas et Polars."""
        from src.analysis.stats import compute_global_ratio

        data = {
            "kills": [10, 15, 20],
            "deaths": [5, 10, 10],
            "assists": [4, 6, 8],
        }

        df_pandas = pd.DataFrame(data)
        df_polars = pl.DataFrame(data)

        result_pandas = compute_global_ratio(df_pandas)
        result_polars = compute_global_ratio(df_polars)

        assert result_pandas == pytest.approx(result_polars)

    def test_compute_outcome_rates_same_result(self):
        """Vérifie que compute_outcome_rates donne le même résultat avec Pandas et Polars."""
        from src.analysis.stats import compute_outcome_rates

        data = {
            "outcome": [2, 2, 3, 1, 2, 3, 4],
        }

        df_pandas = pd.DataFrame(data)
        df_polars = pl.DataFrame(data)

        rates_pandas = compute_outcome_rates(df_pandas)
        rates_polars = compute_outcome_rates(df_polars)

        assert rates_pandas.wins == rates_polars.wins
        assert rates_pandas.losses == rates_polars.losses
        assert rates_pandas.ties == rates_polars.ties
        assert rates_pandas.no_finish == rates_polars.no_finish
        assert rates_pandas.total == rates_polars.total

    def test_plot_functions_accept_both(self, sample_match_df_polars: pl.DataFrame):
        """Vérifie que les fonctions de plot acceptent Pandas et Polars."""
        from src.visualization.distributions import plot_kda_distribution

        # Test avec Polars
        fig_polars = plot_kda_distribution(sample_match_df_polars)
        assert fig_polars is not None

        # Test avec Pandas (conversion)
        df_pandas = sample_match_df_polars.to_pandas()
        fig_pandas = plot_kda_distribution(df_pandas)
        assert fig_pandas is not None

        # Les deux doivent produire des figures valides
        assert len(fig_polars.data) == len(fig_pandas.data)


# =============================================================================
# TESTS: Cas limites avec Polars
# =============================================================================


class TestEdgeCasesPolars:
    """Tests pour les cas limites avec Polars."""

    def test_empty_dataframe_polars(self, empty_df_polars: pl.DataFrame):
        """Test avec DataFrame Polars vide."""
        from src.analysis.stats import compute_global_ratio, compute_outcome_rates

        assert compute_global_ratio(empty_df_polars) is None

        rates = compute_outcome_rates(empty_df_polars)
        assert rates.total == 0

    def test_dataframe_with_nans_polars(self, df_with_nans_polars: pl.DataFrame):
        """Test avec DataFrame Polars contenant des valeurs None."""
        from src.visualization.distributions import plot_kda_distribution

        # La fonction doit gérer les None sans erreur
        fig = plot_kda_distribution(df_with_nans_polars)
        assert fig is not None

    def test_single_row_polars(self):
        """Test avec un DataFrame Polars d'une seule ligne."""
        from src.analysis.stats import compute_global_ratio

        df = pl.DataFrame(
            {
                "kills": [10],
                "deaths": [5],
                "assists": [4],
            }
        )

        result = compute_global_ratio(df)
        assert result is not None
        assert result == pytest.approx(2.4)  # (10 + 4/2) / 5 = 12 / 5 = 2.4
