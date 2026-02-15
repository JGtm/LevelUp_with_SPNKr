"""Tests pour le module de performance cumulée (Sprint 6).

Teste les fonctions Polars pour :
- Calcul des séries cumulatives (net score, K/D, KDA)
- Métriques agrégées
- Rolling K/D
- Tendances de session
"""

from __future__ import annotations

import pytest

# Import conditionnel de Polars
try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

# Skip tous les tests si Polars n'est pas disponible
pytestmark = pytest.mark.skipif(
    not POLARS_AVAILABLE,
    reason="Polars non disponible",
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_match_stats_df() -> pl.DataFrame:
    """DataFrame de matchs pour les tests."""
    return pl.DataFrame(
        {
            "match_id": ["m1", "m2", "m3", "m4", "m5"],
            "start_time": [
                "2026-02-01T10:00:00",
                "2026-02-01T11:00:00",
                "2026-02-01T12:00:00",
                "2026-02-01T13:00:00",
                "2026-02-01T14:00:00",
            ],
            "kills": [10, 8, 12, 6, 15],
            "deaths": [5, 10, 8, 12, 5],
            "assists": [3, 2, 4, 1, 5],
        }
    )


@pytest.fixture
def sample_awards_df() -> pl.DataFrame:
    """DataFrame d'awards pour les tests."""
    return pl.DataFrame(
        {
            "match_id": ["m1", "m1", "m2", "m2", "m3"],
            "xuid": ["x1", "x1", "x1", "x1", "x1"],
            "score_category": ["objective", "kill", "objective", "mode", "objective"],
            "points": [100, 50, 150, 75, 200],
        }
    )


@pytest.fixture
def empty_df() -> pl.DataFrame:
    """DataFrame vide pour tester les cas limites."""
    return pl.DataFrame(
        schema={
            "match_id": pl.Utf8,
            "start_time": pl.Utf8,
            "kills": pl.Int64,
            "deaths": pl.Int64,
            "assists": pl.Int64,
        }
    )


@pytest.fixture
def improving_session_df() -> pl.DataFrame:
    """Session avec amélioration (K/D croissant)."""
    return pl.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(10)],
            "start_time": [f"2026-02-01T{10+i}:00:00" for i in range(10)],
            "kills": [5, 6, 6, 7, 7, 10, 11, 12, 13, 15],  # Croissant
            "deaths": [10, 9, 8, 8, 7, 6, 5, 5, 4, 4],  # Décroissant
            "assists": [2, 2, 3, 3, 3, 4, 4, 5, 5, 6],
        }
    )


@pytest.fixture
def declining_session_df() -> pl.DataFrame:
    """Session avec dégradation (K/D décroissant)."""
    return pl.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(10)],
            "start_time": [f"2026-02-01T{10+i}:00:00" for i in range(10)],
            "kills": [15, 14, 12, 10, 10, 8, 7, 6, 5, 4],  # Décroissant
            "deaths": [4, 5, 5, 6, 7, 8, 9, 10, 11, 12],  # Croissant
            "assists": [5, 5, 4, 4, 3, 3, 2, 2, 1, 1],
        }
    )


# =============================================================================
# Tests - Séries cumulatives
# =============================================================================


class TestCumulativeNetScore:
    """Tests pour compute_cumulative_net_score_series_polars."""

    def test_basic_cumulative(self, sample_match_stats_df: pl.DataFrame):
        """Test basique de calcul du net score cumulé."""
        from src.analysis.cumulative import compute_cumulative_net_score_series_polars

        result = compute_cumulative_net_score_series_polars(sample_match_stats_df)

        assert not result.is_empty()
        assert "cumulative_net_score" in result.columns
        assert "net_score" in result.columns

        # Vérifier les valeurs
        # Match 1: 10-5 = 5
        # Match 2: 8-10 = -2, cumul = 3
        # Match 3: 12-8 = 4, cumul = 7
        # Match 4: 6-12 = -6, cumul = 1
        # Match 5: 15-5 = 10, cumul = 11
        expected_net = [5, -2, 4, -6, 10]
        expected_cumul = [5, 3, 7, 1, 11]

        actual_net = result.get_column("net_score").to_list()
        actual_cumul = result.get_column("cumulative_net_score").to_list()

        assert actual_net == expected_net
        assert actual_cumul == expected_cumul

    def test_empty_dataframe(self, empty_df: pl.DataFrame):
        """Test avec DataFrame vide."""
        from src.analysis.cumulative import compute_cumulative_net_score_series_polars

        result = compute_cumulative_net_score_series_polars(empty_df)

        assert result.is_empty()
        assert "cumulative_net_score" in result.columns

    def test_single_match(self):
        """Test avec un seul match."""
        from src.analysis.cumulative import compute_cumulative_net_score_series_polars

        df = pl.DataFrame(
            {
                "match_id": ["m1"],
                "start_time": ["2026-02-01T10:00:00"],
                "kills": [10],
                "deaths": [5],
            }
        )

        result = compute_cumulative_net_score_series_polars(df)

        assert len(result) == 1
        assert result.get_column("net_score").item() == 5
        assert result.get_column("cumulative_net_score").item() == 5


class TestCumulativeKD:
    """Tests pour compute_cumulative_kd_series_polars."""

    def test_basic_cumulative_kd(self, sample_match_stats_df: pl.DataFrame):
        """Test basique de calcul du K/D cumulé."""
        from src.analysis.cumulative import compute_cumulative_kd_series_polars

        result = compute_cumulative_kd_series_polars(sample_match_stats_df)

        assert not result.is_empty()
        assert "cumulative_kd" in result.columns
        assert "kd" in result.columns

        # Vérifier le K/D final
        # Total kills: 10+8+12+6+15 = 51
        # Total deaths: 5+10+8+12+5 = 40
        # K/D final: 51/40 = 1.275 → arrondi 1.27 ou 1.28 selon la précision
        final_kd = result.get_column("cumulative_kd").to_list()[-1]
        assert round(final_kd, 2) in (1.27, 1.28)

    def test_zero_deaths_handling(self):
        """Test avec zéro mort (éviter division par zéro)."""
        from src.analysis.cumulative import compute_cumulative_kd_series_polars

        df = pl.DataFrame(
            {
                "match_id": ["m1", "m2"],
                "start_time": ["2026-02-01T10:00:00", "2026-02-01T11:00:00"],
                "kills": [10, 5],
                "deaths": [0, 0],
            }
        )

        result = compute_cumulative_kd_series_polars(df)

        # Avec 0 deaths, K/D devrait être kills / 1
        kd_values = result.get_column("cumulative_kd").to_list()
        assert kd_values[0] == 10.0  # 10 / 1
        assert kd_values[1] == 15.0  # 15 / 1

    def test_empty_dataframe(self, empty_df: pl.DataFrame):
        """Test avec DataFrame vide."""
        from src.analysis.cumulative import compute_cumulative_kd_series_polars

        result = compute_cumulative_kd_series_polars(empty_df)

        assert result.is_empty()


class TestCumulativeKDA:
    """Tests pour compute_cumulative_kda_series_polars."""

    def test_basic_cumulative_kda(self, sample_match_stats_df: pl.DataFrame):
        """Test basique de calcul du KDA cumulé."""
        from src.analysis.cumulative import compute_cumulative_kda_series_polars

        result = compute_cumulative_kda_series_polars(sample_match_stats_df)

        assert not result.is_empty()
        assert "cumulative_kda" in result.columns
        assert "kda" in result.columns

        # Vérifier le KDA final
        # Total kills: 51, Total assists: 15, Total deaths: 40
        # KDA final: (51+15)/40 = 1.65
        final_kda = result.get_column("cumulative_kda").to_list()[-1]
        assert round(final_kda, 2) == 1.65


class TestCumulativeObjective:
    """Tests pour compute_cumulative_objective_score_series_polars."""

    def test_basic_objective_score(
        self, sample_awards_df: pl.DataFrame, sample_match_stats_df: pl.DataFrame
    ):
        """Test basique de calcul du score objectifs cumulé."""
        from src.analysis.cumulative import (
            compute_cumulative_objective_score_series_polars,
        )

        result = compute_cumulative_objective_score_series_polars(
            sample_awards_df, sample_match_stats_df
        )

        assert not result.is_empty()
        assert "objective_score" in result.columns
        assert "cumulative_objective" in result.columns


# =============================================================================
# Tests - Métriques agrégées
# =============================================================================


class TestCumulativeMetrics:
    """Tests pour compute_cumulative_metrics_polars."""

    def test_basic_metrics(self, sample_match_stats_df: pl.DataFrame):
        """Test basique des métriques cumulées."""
        from src.analysis.cumulative import compute_cumulative_metrics_polars

        result = compute_cumulative_metrics_polars(sample_match_stats_df)

        assert result.total_kills == 51
        assert result.total_deaths == 40
        assert result.total_assists == 15
        assert result.cumulative_net_score == 11
        assert result.matches_count == 5
        assert result.cumulative_kd in (1.27, 1.28)
        assert result.cumulative_kda == 1.65

    def test_empty_dataframe(self, empty_df: pl.DataFrame):
        """Test avec DataFrame vide."""
        from src.analysis.cumulative import compute_cumulative_metrics_polars

        result = compute_cumulative_metrics_polars(empty_df)

        assert result.total_kills == 0
        assert result.total_deaths == 0
        assert result.matches_count == 0

    def test_properties(self, sample_match_stats_df: pl.DataFrame):
        """Test des propriétés calculées."""
        from src.analysis.cumulative import compute_cumulative_metrics_polars

        result = compute_cumulative_metrics_polars(sample_match_stats_df)

        # Moyenne kills: 51/5 = 10.2
        assert round(result.average_kills_per_match, 1) == 10.2
        # Moyenne deaths: 40/5 = 8.0
        assert result.average_deaths_per_match == 8.0


# =============================================================================
# Tests - Rolling K/D
# =============================================================================


class TestRollingKD:
    """Tests pour compute_rolling_kd_polars."""

    def test_basic_rolling(self, sample_match_stats_df: pl.DataFrame):
        """Test basique du K/D glissant."""
        from src.analysis.cumulative import compute_rolling_kd_polars

        result = compute_rolling_kd_polars(sample_match_stats_df, window_size=3)

        assert not result.is_empty()
        assert "rolling_kd" in result.columns
        assert "kd" in result.columns
        assert len(result) == 5

    def test_window_larger_than_data(self, sample_match_stats_df: pl.DataFrame):
        """Test avec fenêtre plus grande que les données."""
        from src.analysis.cumulative import compute_rolling_kd_polars

        result = compute_rolling_kd_polars(sample_match_stats_df, window_size=10)

        assert not result.is_empty()
        assert len(result) == 5


# =============================================================================
# Tests - Tendances de session
# =============================================================================


class TestSessionTrend:
    """Tests pour compute_session_trend_polars."""

    def test_improving_session(self, improving_session_df: pl.DataFrame):
        """Test d'une session en amélioration."""
        from src.analysis.cumulative import compute_session_trend_polars

        result = compute_session_trend_polars(improving_session_df)

        assert result["trend"] == "improving"
        assert result["kd_change"] > 0
        assert result["kd_change_pct"] > 10

    def test_declining_session(self, declining_session_df: pl.DataFrame):
        """Test d'une session en déclin."""
        from src.analysis.cumulative import compute_session_trend_polars

        result = compute_session_trend_polars(declining_session_df)

        assert result["trend"] == "declining"
        assert result["kd_change"] < 0
        assert result["kd_change_pct"] < -10

    def test_stable_session(self):
        """Test d'une session stable."""
        from src.analysis.cumulative import compute_session_trend_polars

        df = pl.DataFrame(
            {
                "match_id": [f"m{i}" for i in range(10)],
                "start_time": [f"2026-02-01T{10+i}:00:00" for i in range(10)],
                "kills": [10] * 10,  # Constant
                "deaths": [10] * 10,  # Constant
                "assists": [5] * 10,
            }
        )

        result = compute_session_trend_polars(df)

        assert result["trend"] == "stable"
        assert result["kd_change_pct"] < 10
        assert result["kd_change_pct"] > -10

    def test_not_enough_matches(self):
        """Test avec pas assez de matchs."""
        from src.analysis.cumulative import compute_session_trend_polars

        df = pl.DataFrame(
            {
                "match_id": ["m1", "m2"],
                "start_time": ["2026-02-01T10:00:00", "2026-02-01T11:00:00"],
                "kills": [10, 15],
                "deaths": [5, 3],
                "assists": [2, 3],
            }
        )

        result = compute_session_trend_polars(df)

        assert result["trend"] == "stable"
        assert result["first_half_kd"] is None


# =============================================================================
# Tests - Visualisations
# =============================================================================


class TestVisualizationFunctions:
    """Tests pour les fonctions de visualisation."""

    def test_plot_cumulative_net_score(self, sample_match_stats_df: pl.DataFrame):
        """Test du graphique net score cumulé."""
        import plotly.graph_objects as go

        from src.analysis.cumulative import compute_cumulative_net_score_series_polars
        from src.visualization.performance import plot_cumulative_net_score

        cumul_df = compute_cumulative_net_score_series_polars(sample_match_stats_df)
        fig = plot_cumulative_net_score(cumul_df)

        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_plot_cumulative_kd(self, sample_match_stats_df: pl.DataFrame):
        """Test du graphique K/D cumulé."""
        import plotly.graph_objects as go

        from src.analysis.cumulative import compute_cumulative_kd_series_polars
        from src.visualization.performance import plot_cumulative_kd

        cumul_df = compute_cumulative_kd_series_polars(sample_match_stats_df)
        fig = plot_cumulative_kd(cumul_df)

        assert isinstance(fig, go.Figure)

    def test_plot_rolling_kd(self, sample_match_stats_df: pl.DataFrame):
        """Test du graphique K/D glissant."""
        import plotly.graph_objects as go

        from src.analysis.cumulative import compute_rolling_kd_polars
        from src.visualization.performance import plot_rolling_kd

        rolling_df = compute_rolling_kd_polars(sample_match_stats_df, window_size=3)
        fig = plot_rolling_kd(rolling_df, window_size=3)

        assert isinstance(fig, go.Figure)

    def test_plot_session_trend(self, improving_session_df: pl.DataFrame):
        """Test du graphique de tendance."""
        import plotly.graph_objects as go

        from src.visualization.performance import plot_session_trend

        fig = plot_session_trend(improving_session_df)

        assert isinstance(fig, go.Figure)

    def test_plot_empty_dataframe(self, empty_df: pl.DataFrame):
        """Test des graphiques avec données vides."""
        import plotly.graph_objects as go

        from src.analysis.cumulative import compute_cumulative_net_score_series_polars
        from src.visualization.performance import plot_cumulative_net_score

        cumul_df = compute_cumulative_net_score_series_polars(empty_df)
        fig = plot_cumulative_net_score(cumul_df)

        assert isinstance(fig, go.Figure)
        # Devrait avoir une annotation "Aucune donnée"


# =============================================================================
# Tests - Utilitaires
# =============================================================================


class TestUtilities:
    """Tests pour les fonctions utilitaires."""

    def test_cumulative_series_to_dicts(self, sample_match_stats_df: pl.DataFrame):
        """Test de conversion en liste de dicts."""
        from src.analysis.cumulative import (
            compute_cumulative_net_score_series_polars,
            cumulative_series_to_dicts,
        )

        cumul_df = compute_cumulative_net_score_series_polars(sample_match_stats_df)
        dicts = cumulative_series_to_dicts(cumul_df)

        assert isinstance(dicts, list)
        assert len(dicts) == 5
        assert all(isinstance(d, dict) for d in dicts)
        assert "cumulative_net_score" in dicts[0]

    def test_get_performance_colors(self):
        """Test de récupération des couleurs."""
        from src.visualization.performance import get_performance_colors

        colors = get_performance_colors()

        assert isinstance(colors, dict)
        assert "positive" in colors
        assert "negative" in colors
        assert "kd_line" in colors
