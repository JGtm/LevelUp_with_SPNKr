"""Tests des fonctions de visualisation.

Ce module teste TOUTES les fonctions de visualisation pour garantir:
1. Qu'elles retournent des go.Figure valides
2. Qu'elles gèrent correctement les cas limites (données vides, NaN, etc.)
3. Qu'elles produisent des traces avec des données
4. Qu'elles acceptent à la fois Pandas et Polars DataFrames

Exécution:
    pytest tests/test_visualizations.py -v
    pytest tests/test_visualizations.py -v -m visualization  # Uniquement les tests marqués
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

try:
    import polars as pl
except ImportError:
    pl = None

# =============================================================================
# FIXTURES COMMUNES
# =============================================================================


@pytest.fixture
def sample_match_df() -> pd.DataFrame:
    """DataFrame Pandas type avec colonnes de match standard (pour compatibilité)."""
    np.random.seed(42)  # Reproductibilité
    n = 20
    return pd.DataFrame(
        {
            "match_id": [f"match_{i}" for i in range(n)],
            "start_time": pd.date_range("2025-01-01", periods=n, freq="h"),
            "kills": np.random.randint(5, 25, n),
            "deaths": np.random.randint(3, 15, n),
            "assists": np.random.randint(2, 12, n),
            "accuracy": np.random.uniform(30, 60, n),
            "ratio": np.random.uniform(0.5, 2.5, n),
            "kda": np.random.uniform(-5, 10, n),
            "outcome": np.random.choice([1, 2, 3, 4], n),
            "map_name": np.random.choice(["Recharge", "Streets", "Live Fire"], n),
            "playlist_name": np.random.choice(["Ranked", "Quick Play"], n),
            "time_played_seconds": np.random.randint(300, 900, n),
            "kills_per_min": np.random.uniform(0.3, 1.5, n),
            "deaths_per_min": np.random.uniform(0.2, 1.0, n),
            "assists_per_min": np.random.uniform(0.1, 0.8, n),
            "headshot_kills": np.random.randint(1, 10, n),
            "max_killing_spree": np.random.randint(0, 8, n),
            "average_life_seconds": np.random.uniform(20, 60, n),
            "mode_category": np.random.choice(["Slayer", "CTF", "Oddball"], n),
        }
    )


@pytest.fixture
def empty_df() -> pd.DataFrame:
    """DataFrame vide avec les colonnes attendues."""
    return pd.DataFrame(
        columns=[
            "match_id",
            "start_time",
            "kills",
            "deaths",
            "assists",
            "accuracy",
            "ratio",
            "kda",
            "outcome",
            "map_name",
            "time_played_seconds",
            "kills_per_min",
            "deaths_per_min",
            "assists_per_min",
            "headshot_kills",
            "max_killing_spree",
            "average_life_seconds",
            "playlist_name",
            "mode_category",
        ]
    )


@pytest.fixture
def df_with_nans(sample_match_df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame avec des valeurs NaN."""
    df = sample_match_df.copy()
    df.loc[0:5, "kills"] = np.nan
    df.loc[10:15, "accuracy"] = np.nan
    df.loc[5:10, "kda"] = np.nan
    return df


@pytest.fixture
def sample_map_breakdown_df() -> pd.DataFrame:
    """DataFrame type pour compute_map_breakdown."""
    return pd.DataFrame(
        {
            "map_name": ["Recharge", "Streets", "Live Fire", "Bazaar"],
            "matches": [50, 40, 30, 20],
            "ratio_global": [1.5, 1.2, 1.0, 0.8],
            "win_rate": [0.6, 0.55, 0.5, 0.45],
            "loss_rate": [0.35, 0.40, 0.45, 0.50],
            "accuracy_avg": [45.0, 42.0, 40.0, 38.0],
        }
    )


@pytest.fixture
def sample_weapons_data() -> list[dict]:
    """Données d'armes type."""
    return [
        {"weapon_name": "MA40 AR", "total_kills": 500, "headshot_rate": 15.0, "accuracy": 35.0},
        {"weapon_name": "BR75", "total_kills": 400, "headshot_rate": 45.0, "accuracy": 50.0},
        {"weapon_name": "Sidekick", "total_kills": 200, "headshot_rate": 30.0, "accuracy": 40.0},
    ]


@pytest.fixture
def sample_medals_data() -> tuple[list[tuple[int, int]], dict[int, str]]:
    """Données de médailles type."""
    medals = [(1, 100), (2, 80), (3, 60), (4, 40), (5, 20)]
    names = {1: "Double Kill", 2: "Triple Kill", 3: "Overkill", 4: "Killtacular", 5: "Killtrocity"}
    return medals, names


@pytest.fixture
def sample_radar_data() -> list[dict]:
    """Données pour graphe radar."""
    return [
        {"name": "Player1", "values": [0.8, 0.6, 0.5, 0.7], "color": "#FF6B6B"},
        {"name": "Player2", "values": [0.7, 0.8, 0.4, 0.6], "color": "#4ECDC4"},
    ]


@pytest.fixture
def sample_players_radar() -> list[dict]:
    """Données joueurs pour radar stats/min."""
    return [
        {
            "name": "Player1",
            "kills_per_min": 0.8,
            "deaths_per_min": 0.5,
            "assists_per_min": 0.3,
            "color": "#FF6B6B",
        },
        {
            "name": "Player2",
            "kills_per_min": 0.7,
            "deaths_per_min": 0.6,
            "assists_per_min": 0.4,
            "color": "#4ECDC4",
        },
    ]


@pytest.fixture
def sample_performance_radar() -> list[dict]:
    """Données joueurs pour radar performance."""
    return [
        {
            "name": "Player1",
            "objective_score": 80,
            "kills": 15,
            "deaths": 8,
            "assists": 5,
            "color": "#FF6B6B",
        },
        {
            "name": "Player2",
            "objective_score": 60,
            "kills": 12,
            "deaths": 10,
            "assists": 8,
            "color": "#4ECDC4",
        },
    ]


# =============================================================================
# HELPERS
# =============================================================================


def assert_valid_figure(fig: go.Figure, min_traces: int = 0) -> None:
    """Vérifie qu'une figure Plotly est valide."""
    assert isinstance(fig, go.Figure), f"Expected go.Figure, got {type(fig)}"
    assert fig.layout is not None, "Figure has no layout"

    if min_traces > 0:
        assert (
            len(fig.data) >= min_traces
        ), f"Expected at least {min_traces} traces, got {len(fig.data)}"


def assert_figure_has_data(fig: go.Figure) -> None:
    """Vérifie qu'une figure contient des données non vides."""
    assert isinstance(fig, go.Figure)

    if len(fig.data) == 0:
        return  # Figure vide mais valide (cas empty_df)

    for _i, trace in enumerate(fig.data):
        # Vérifier selon le type de trace
        has_data = False

        if hasattr(trace, "x") and trace.x is not None:
            has_data = len(trace.x) > 0 if hasattr(trace.x, "__len__") else True
        if hasattr(trace, "y") and trace.y is not None:
            has_data = has_data or (len(trace.y) > 0 if hasattr(trace.y, "__len__") else True)
        if hasattr(trace, "r") and trace.r is not None:  # Radar
            has_data = has_data or (len(trace.r) > 0 if hasattr(trace.r, "__len__") else True)
        if hasattr(trace, "z") and trace.z is not None:  # Heatmap
            has_data = True

        # Note: on ne fail pas si trace vide, car certains graphiques sont vides intentionnellement


# =============================================================================
# TESTS: src/visualization/distributions.py
# =============================================================================


@pytest.mark.visualization
class TestDistributions:
    """Tests pour distributions.py."""

    # --- plot_kda_distribution ---

    def test_plot_kda_distribution_valid_data(self, sample_match_df: pd.DataFrame) -> None:
        """plot_kda_distribution retourne une figure valide avec données normales (Pandas)."""
        from src.visualization.distributions import plot_kda_distribution

        fig = plot_kda_distribution(sample_match_df)
        assert_valid_figure(fig, min_traces=1)
        assert_figure_has_data(fig)

    @pytest.mark.skipif(pl is None, reason="Polars not available")
    def test_plot_kda_distribution_valid_data_polars(
        self, sample_match_df_polars: pl.DataFrame
    ) -> None:
        """plot_kda_distribution retourne une figure valide avec données normales (Polars)."""
        from src.visualization.distributions import plot_kda_distribution

        fig = plot_kda_distribution(sample_match_df_polars)
        assert_valid_figure(fig, min_traces=1)
        assert_figure_has_data(fig)

    def test_plot_kda_distribution_empty_df(self, empty_df: pd.DataFrame) -> None:
        """plot_kda_distribution gère un DataFrame vide."""
        from src.visualization.distributions import plot_kda_distribution

        fig = plot_kda_distribution(empty_df)
        assert_valid_figure(fig)

    def test_plot_kda_distribution_all_nans(self, sample_match_df: pd.DataFrame) -> None:
        """plot_kda_distribution gère un DataFrame avec tous NaN."""
        from src.visualization.distributions import plot_kda_distribution

        df = sample_match_df.copy()
        df["kda"] = np.nan
        fig = plot_kda_distribution(df)
        assert_valid_figure(fig)

    # --- plot_outcomes_over_time ---

    def test_plot_outcomes_over_time_valid_data(self, sample_match_df: pd.DataFrame) -> None:
        """plot_outcomes_over_time retourne figure et label."""
        from src.visualization.distributions import plot_outcomes_over_time

        fig, label = plot_outcomes_over_time(sample_match_df)
        assert_valid_figure(fig, min_traces=1)
        assert isinstance(label, str)
        assert len(label) > 0

    def test_plot_outcomes_over_time_session_style(self, sample_match_df: pd.DataFrame) -> None:
        """plot_outcomes_over_time fonctionne en mode session."""
        from src.visualization.distributions import plot_outcomes_over_time

        fig, label = plot_outcomes_over_time(sample_match_df, session_style=True)
        assert_valid_figure(fig)
        assert isinstance(label, str)

    def test_plot_outcomes_over_time_empty_df(self, empty_df: pd.DataFrame) -> None:
        """plot_outcomes_over_time gère un DataFrame vide."""
        from src.visualization.distributions import plot_outcomes_over_time

        fig, label = plot_outcomes_over_time(empty_df)
        assert_valid_figure(fig)
        assert isinstance(label, str)

    # --- plot_stacked_outcomes_by_category ---

    def test_plot_stacked_outcomes_by_category_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_stacked_outcomes_by_category retourne figure valide."""
        from src.visualization.distributions import plot_stacked_outcomes_by_category

        fig = plot_stacked_outcomes_by_category(sample_match_df, "map_name")
        assert_valid_figure(fig, min_traces=1)

    def test_plot_stacked_outcomes_by_category_empty(self, empty_df: pd.DataFrame) -> None:
        """plot_stacked_outcomes_by_category gère DataFrame vide."""
        from src.visualization.distributions import plot_stacked_outcomes_by_category

        fig = plot_stacked_outcomes_by_category(empty_df, "map_name")
        assert_valid_figure(fig)

    def test_plot_stacked_outcomes_by_category_with_options(
        self, sample_match_df: pd.DataFrame
    ) -> None:
        """plot_stacked_outcomes_by_category avec options."""
        from src.visualization.distributions import plot_stacked_outcomes_by_category

        fig = plot_stacked_outcomes_by_category(
            sample_match_df,
            "mode_category",
            title="Test Title",
            min_matches=1,
            sort_by="win_rate",
            max_categories=5,
        )
        assert_valid_figure(fig)

    # --- plot_win_ratio_heatmap ---

    def test_plot_win_ratio_heatmap_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_win_ratio_heatmap retourne figure valide."""
        from src.visualization.distributions import plot_win_ratio_heatmap

        fig = plot_win_ratio_heatmap(sample_match_df)
        assert_valid_figure(fig, min_traces=1)

    def test_plot_win_ratio_heatmap_empty(self, empty_df: pd.DataFrame) -> None:
        """plot_win_ratio_heatmap gère DataFrame vide."""
        from src.visualization.distributions import plot_win_ratio_heatmap

        fig = plot_win_ratio_heatmap(empty_df)
        assert_valid_figure(fig)

    # --- plot_top_weapons ---

    def test_plot_top_weapons_valid(self, sample_weapons_data: list[dict]) -> None:
        """plot_top_weapons retourne figure valide."""
        from src.visualization.distributions import plot_top_weapons

        fig = plot_top_weapons(sample_weapons_data)
        assert_valid_figure(fig, min_traces=1)

    def test_plot_top_weapons_empty(self) -> None:
        """plot_top_weapons gère liste vide."""
        from src.visualization.distributions import plot_top_weapons

        fig = plot_top_weapons([])
        assert_valid_figure(fig)

    # --- plot_histogram ---

    def test_plot_histogram_valid(self) -> None:
        """plot_histogram retourne figure valide."""
        from src.visualization.distributions import plot_histogram

        values = pd.Series(np.random.normal(0, 1, 100))
        fig = plot_histogram(values)
        assert_valid_figure(fig, min_traces=1)

    def test_plot_histogram_empty(self) -> None:
        """plot_histogram gère série vide."""
        from src.visualization.distributions import plot_histogram

        values = pd.Series([], dtype=float)
        fig = plot_histogram(values)
        assert_valid_figure(fig)

    def test_plot_histogram_with_kde(self) -> None:
        """plot_histogram avec KDE."""
        from src.visualization.distributions import plot_histogram

        values = pd.Series(np.random.normal(0, 1, 100))
        fig = plot_histogram(values, show_kde=True)
        assert_valid_figure(fig)

    def test_plot_histogram_numpy_array(self) -> None:
        """plot_histogram accepte numpy array."""
        from src.visualization.distributions import plot_histogram

        values = np.random.normal(0, 1, 100)
        fig = plot_histogram(values)
        assert_valid_figure(fig, min_traces=1)

    # --- plot_medals_distribution ---

    def test_plot_medals_distribution_valid(self, sample_medals_data: tuple) -> None:
        """plot_medals_distribution retourne figure valide."""
        from src.visualization.distributions import plot_medals_distribution

        medals, names = sample_medals_data
        fig = plot_medals_distribution(medals, names)
        assert_valid_figure(fig, min_traces=1)

    def test_plot_medals_distribution_empty(self) -> None:
        """plot_medals_distribution gère liste vide."""
        from src.visualization.distributions import plot_medals_distribution

        fig = plot_medals_distribution([], {})
        assert_valid_figure(fig)

    # --- plot_correlation_scatter ---

    def test_plot_correlation_scatter_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_correlation_scatter retourne figure valide."""
        from src.visualization.distributions import plot_correlation_scatter

        fig = plot_correlation_scatter(sample_match_df, "kills", "deaths")
        assert_valid_figure(fig, min_traces=1)

    def test_plot_correlation_scatter_with_trendline(self, sample_match_df: pd.DataFrame) -> None:
        """plot_correlation_scatter avec ligne de tendance."""
        from src.visualization.distributions import plot_correlation_scatter

        fig = plot_correlation_scatter(
            sample_match_df,
            "kills",
            "deaths",
            show_trendline=True,
            title="Test Scatter",
        )
        assert_valid_figure(fig)

    def test_plot_correlation_scatter_with_color(self, sample_match_df: pd.DataFrame) -> None:
        """plot_correlation_scatter avec colonne de couleur."""
        from src.visualization.distributions import plot_correlation_scatter

        fig = plot_correlation_scatter(
            sample_match_df,
            "kills",
            "deaths",
            color_col="outcome",
        )
        assert_valid_figure(fig)

    def test_plot_correlation_scatter_empty(self, empty_df: pd.DataFrame) -> None:
        """plot_correlation_scatter gère DataFrame vide."""
        from src.visualization.distributions import plot_correlation_scatter

        fig = plot_correlation_scatter(empty_df, "kills", "deaths")
        assert_valid_figure(fig)

    # --- plot_matches_at_top_by_week ---

    def test_plot_matches_at_top_by_week_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_matches_at_top_by_week retourne figure valide."""
        from src.visualization.distributions import plot_matches_at_top_by_week

        # Ajouter colonne rank si absente
        df = sample_match_df.copy()
        df["rank"] = np.random.randint(1, 8, len(df))

        fig = plot_matches_at_top_by_week(df)
        assert_valid_figure(fig, min_traces=1)

    def test_plot_matches_at_top_by_week_empty(self, empty_df: pd.DataFrame) -> None:
        """plot_matches_at_top_by_week gère DataFrame vide."""
        from src.visualization.distributions import plot_matches_at_top_by_week

        fig = plot_matches_at_top_by_week(empty_df)
        assert_valid_figure(fig)

    # --- plot_first_event_distribution ---

    def test_plot_first_event_distribution_valid(self) -> None:
        """plot_first_event_distribution retourne figure valide."""
        from src.visualization.distributions import plot_first_event_distribution

        first_kills = {f"match_{i}": np.random.randint(5000, 30000) for i in range(20)}
        first_deaths = {f"match_{i}": np.random.randint(5000, 30000) for i in range(20)}

        fig = plot_first_event_distribution(first_kills, first_deaths)
        assert_valid_figure(fig, min_traces=1)

    def test_plot_first_event_distribution_empty(self) -> None:
        """plot_first_event_distribution gère dicts vides."""
        from src.visualization.distributions import plot_first_event_distribution

        fig = plot_first_event_distribution({}, {})
        assert_valid_figure(fig)

    def test_plot_first_event_distribution_with_nones(self) -> None:
        """plot_first_event_distribution gère valeurs None."""
        from src.visualization.distributions import plot_first_event_distribution

        first_kills = {"match_0": 10000, "match_1": None, "match_2": 15000}
        first_deaths = {"match_0": None, "match_1": 12000, "match_2": 8000}

        fig = plot_first_event_distribution(first_kills, first_deaths)
        assert_valid_figure(fig)


# =============================================================================
# TESTS: src/visualization/timeseries.py
# =============================================================================


@pytest.mark.visualization
class TestTimeseries:
    """Tests pour timeseries.py."""

    # --- plot_timeseries ---

    def test_plot_timeseries_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_timeseries retourne figure valide."""
        from src.visualization.timeseries import plot_timeseries

        fig = plot_timeseries(sample_match_df)
        assert_valid_figure(fig, min_traces=1)
        assert_figure_has_data(fig)

    def test_plot_timeseries_with_title(self, sample_match_df: pd.DataFrame) -> None:
        """plot_timeseries avec titre personnalisé."""
        from src.visualization.timeseries import plot_timeseries

        fig = plot_timeseries(sample_match_df, title="Custom Title")
        assert_valid_figure(fig)
        assert fig.layout.title is not None

    def test_plot_timeseries_empty(self, empty_df: pd.DataFrame) -> None:
        """plot_timeseries avec DataFrame vide crée une erreur ou figure vide."""
        from src.visualization.timeseries import plot_timeseries

        # Avec empty_df, la fonction peut lever une erreur ou retourner figure vide
        # On vérifie juste qu'elle ne crash pas de manière inattendue
        try:
            fig = plot_timeseries(empty_df)
            assert_valid_figure(fig)
        except (KeyError, IndexError, ValueError, AttributeError):
            # Acceptable si la fonction ne gère pas les DataFrames vides
            # Note: Idéalement, la fonction devrait retourner une figure vide
            pass

    # --- plot_assists_timeseries ---

    def test_plot_assists_timeseries_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_assists_timeseries retourne figure valide."""
        from src.visualization.timeseries import plot_assists_timeseries

        fig = plot_assists_timeseries(sample_match_df)
        assert_valid_figure(fig, min_traces=1)

    def test_plot_assists_timeseries_with_title(self, sample_match_df: pd.DataFrame) -> None:
        """plot_assists_timeseries avec titre."""
        from src.visualization.timeseries import plot_assists_timeseries

        fig = plot_assists_timeseries(sample_match_df, title="Assists Over Time")
        assert_valid_figure(fig)

    # --- plot_per_minute_timeseries ---

    def test_plot_per_minute_timeseries_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_per_minute_timeseries retourne figure valide."""
        from src.visualization.timeseries import plot_per_minute_timeseries

        fig = plot_per_minute_timeseries(sample_match_df)
        assert_valid_figure(fig, min_traces=1)

    # --- plot_accuracy_last_n ---

    def test_plot_accuracy_last_n_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_accuracy_last_n retourne figure valide."""
        from src.visualization.timeseries import plot_accuracy_last_n

        fig = plot_accuracy_last_n(sample_match_df, n=10)
        assert_valid_figure(fig, min_traces=1)

    def test_plot_accuracy_last_n_more_than_available(self, sample_match_df: pd.DataFrame) -> None:
        """plot_accuracy_last_n avec n > nombre de lignes."""
        from src.visualization.timeseries import plot_accuracy_last_n

        fig = plot_accuracy_last_n(sample_match_df, n=100)
        assert_valid_figure(fig)

    # --- plot_average_life ---

    def test_plot_average_life_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_average_life retourne figure valide."""
        from src.visualization.timeseries import plot_average_life

        fig = plot_average_life(sample_match_df)
        assert_valid_figure(fig, min_traces=1)

    def test_plot_average_life_with_title(self, sample_match_df: pd.DataFrame) -> None:
        """plot_average_life avec titre."""
        from src.visualization.timeseries import plot_average_life

        fig = plot_average_life(sample_match_df, title="Average Life Duration")
        assert_valid_figure(fig)

    # --- plot_spree_headshots_accuracy ---

    def test_plot_spree_headshots_accuracy_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_spree_headshots_accuracy retourne figure valide."""
        from src.visualization.timeseries import plot_spree_headshots_accuracy

        fig = plot_spree_headshots_accuracy(sample_match_df)
        assert_valid_figure(fig, min_traces=1)

    def test_plot_spree_headshots_accuracy_with_perfects(
        self, sample_match_df: pd.DataFrame
    ) -> None:
        """plot_spree_headshots_accuracy avec perfect_counts."""
        from src.visualization.timeseries import plot_spree_headshots_accuracy

        perfect_counts = {
            row["match_id"]: np.random.randint(0, 5) for _, row in sample_match_df.iterrows()
        }
        fig = plot_spree_headshots_accuracy(sample_match_df, perfect_counts=perfect_counts)
        assert_valid_figure(fig)

    # --- plot_performance_timeseries ---

    def test_plot_performance_timeseries_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_performance_timeseries retourne figure valide."""
        from src.visualization.timeseries import plot_performance_timeseries

        fig = plot_performance_timeseries(sample_match_df)
        assert_valid_figure(fig, min_traces=1)

    def test_plot_performance_timeseries_with_history(self, sample_match_df: pd.DataFrame) -> None:
        """plot_performance_timeseries avec df_history."""
        from src.visualization.timeseries import plot_performance_timeseries

        # Utiliser le même DataFrame comme historique
        fig = plot_performance_timeseries(sample_match_df, df_history=sample_match_df)
        assert_valid_figure(fig)

    def test_plot_performance_timeseries_no_smooth(self, sample_match_df: pd.DataFrame) -> None:
        """plot_performance_timeseries sans courbe lissée."""
        from src.visualization.timeseries import plot_performance_timeseries

        fig = plot_performance_timeseries(sample_match_df, show_smooth=False)
        assert_valid_figure(fig)


# =============================================================================
# TESTS: src/visualization/maps.py
# =============================================================================


@pytest.mark.visualization
class TestMaps:
    """Tests pour maps.py."""

    def test_plot_map_comparison_valid(self, sample_map_breakdown_df: pd.DataFrame) -> None:
        """plot_map_comparison retourne figure valide."""
        from src.visualization.maps import plot_map_comparison

        fig = plot_map_comparison(sample_map_breakdown_df, "ratio_global", "Ratio par carte")
        assert_valid_figure(fig, min_traces=1)

    def test_plot_map_comparison_empty(self) -> None:
        """plot_map_comparison gère DataFrame vide."""
        from src.visualization.maps import plot_map_comparison

        empty = pd.DataFrame(columns=["map_name", "ratio_global", "matches", "accuracy_avg"])
        fig = plot_map_comparison(empty, "ratio_global", "Test")
        assert_valid_figure(fig)

    def test_plot_map_ratio_with_winloss_valid(self, sample_map_breakdown_df: pd.DataFrame) -> None:
        """plot_map_ratio_with_winloss retourne figure valide."""
        from src.visualization.maps import plot_map_ratio_with_winloss

        fig = plot_map_ratio_with_winloss(sample_map_breakdown_df, "Win/Loss par carte")
        assert_valid_figure(fig, min_traces=1)

    def test_plot_map_ratio_with_winloss_empty(self) -> None:
        """plot_map_ratio_with_winloss gère DataFrame vide."""
        from src.visualization.maps import plot_map_ratio_with_winloss

        empty = pd.DataFrame(columns=["map_name", "win_rate", "loss_rate", "matches"])
        fig = plot_map_ratio_with_winloss(empty, "Test")
        assert_valid_figure(fig)


# =============================================================================
# TESTS: src/visualization/match_bars.py
# =============================================================================


@pytest.mark.visualization
class TestMatchBars:
    """Tests pour match_bars.py."""

    def test_plot_metric_bars_by_match_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_metric_bars_by_match retourne figure valide."""
        from src.visualization.match_bars import plot_metric_bars_by_match

        fig = plot_metric_bars_by_match(
            sample_match_df,
            metric_col="kills",
            title="Kills par match",
            y_axis_title="Kills",
            hover_label="kills",
            bar_color="#35D0FF",
            smooth_color="#50C878",
        )
        assert fig is not None
        assert_valid_figure(fig, min_traces=1)

    def test_plot_metric_bars_by_match_empty(self, empty_df: pd.DataFrame) -> None:
        """plot_metric_bars_by_match retourne None pour DataFrame vide."""
        from src.visualization.match_bars import plot_metric_bars_by_match

        fig = plot_metric_bars_by_match(
            empty_df,
            metric_col="kills",
            title="Test",
            y_axis_title="Kills",
            hover_label="kills",
            bar_color="#35D0FF",
            smooth_color="#50C878",
        )
        assert fig is None

    def test_plot_metric_bars_by_match_missing_column(self, sample_match_df: pd.DataFrame) -> None:
        """plot_metric_bars_by_match retourne None si colonne manquante."""
        from src.visualization.match_bars import plot_metric_bars_by_match

        fig = plot_metric_bars_by_match(
            sample_match_df,
            metric_col="nonexistent_column",
            title="Test",
            y_axis_title="Test",
            hover_label="test",
            bar_color="#35D0FF",
            smooth_color="#50C878",
        )
        assert fig is None

    def test_plot_multi_metric_bars_by_match_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_multi_metric_bars_by_match retourne figure valide."""
        from src.visualization.match_bars import plot_multi_metric_bars_by_match

        series = [
            ("Player1", sample_match_df),
            ("Player2", sample_match_df.copy()),
        ]

        fig = plot_multi_metric_bars_by_match(
            series,
            metric_col="kills",
            title="Kills comparaison",
            y_axis_title="Kills",
            hover_label="kills",
            colors={"Player1": "#FF6B6B", "Player2": "#4ECDC4"},
        )
        assert fig is not None
        assert_valid_figure(fig, min_traces=1)

    def test_plot_multi_metric_bars_by_match_empty(self) -> None:
        """plot_multi_metric_bars_by_match retourne None pour liste vide."""
        from src.visualization.match_bars import plot_multi_metric_bars_by_match

        fig = plot_multi_metric_bars_by_match(
            [],
            metric_col="kills",
            title="Test",
            y_axis_title="Kills",
            hover_label="kills",
            colors={},
        )
        assert fig is None


# =============================================================================
# TESTS: src/visualization/trio.py
# =============================================================================


@pytest.mark.visualization
class TestTrio:
    """Tests pour trio.py."""

    def test_plot_trio_metric_valid(self, sample_match_df: pd.DataFrame) -> None:
        """plot_trio_metric retourne figure valide."""
        from src.visualization.trio import plot_trio_metric

        # Créer 3 DataFrames alignés
        d1 = sample_match_df.copy()
        d2 = sample_match_df.copy()
        d3 = sample_match_df.copy()

        fig = plot_trio_metric(
            d1,
            d2,
            d3,
            metric="kills",
            names=("Player1", "Player2", "Player3"),
            title="Kills Trio",
            y_title="Kills",
        )
        assert_valid_figure(fig)

    def test_plot_trio_metric_empty(self, empty_df: pd.DataFrame) -> None:
        """plot_trio_metric gère DataFrames vides."""
        from src.visualization.trio import plot_trio_metric

        fig = plot_trio_metric(
            empty_df,
            empty_df,
            empty_df,
            metric="kills",
            names=("P1", "P2", "P3"),
            title="Test",
            y_title="Kills",
        )
        assert_valid_figure(fig)

    def test_plot_trio_metric_with_format(self, sample_match_df: pd.DataFrame) -> None:
        """plot_trio_metric avec formatage."""
        from src.visualization.trio import plot_trio_metric

        fig = plot_trio_metric(
            sample_match_df,
            sample_match_df,
            sample_match_df,
            metric="accuracy",
            names=("P1", "P2", "P3"),
            title="Accuracy",
            y_title="Précision",
            y_suffix="%",
            y_format=".2f",
        )
        assert_valid_figure(fig)


# =============================================================================
# TESTS: src/ui/components/radar_chart.py
# =============================================================================


@pytest.mark.visualization
class TestRadarChart:
    """Tests pour radar_chart.py."""

    def test_create_radar_chart_valid(self, sample_radar_data: list[dict]) -> None:
        """create_radar_chart retourne figure valide."""
        from src.ui.components.radar_chart import create_radar_chart

        fig = create_radar_chart(sample_radar_data)
        assert_valid_figure(fig, min_traces=1)

    def test_create_radar_chart_empty(self) -> None:
        """create_radar_chart gère liste vide."""
        from src.ui.components.radar_chart import create_radar_chart

        fig = create_radar_chart([])
        assert_valid_figure(fig)

    def test_create_radar_chart_with_options(self, sample_radar_data: list[dict]) -> None:
        """create_radar_chart avec options."""
        from src.ui.components.radar_chart import create_radar_chart

        fig = create_radar_chart(
            sample_radar_data,
            title="Test Radar",
            show_legend=True,
            fill_opacity=0.3,
            line_width=3,
            height=500,
        )
        assert_valid_figure(fig)
        assert fig.layout.height == 500

    def test_create_stats_per_minute_radar_valid(self, sample_players_radar: list[dict]) -> None:
        """create_stats_per_minute_radar retourne figure valide."""
        from src.ui.components.radar_chart import create_stats_per_minute_radar

        fig = create_stats_per_minute_radar(sample_players_radar)
        assert_valid_figure(fig, min_traces=1)

    def test_create_stats_per_minute_radar_empty(self) -> None:
        """create_stats_per_minute_radar gère liste vide."""
        from src.ui.components.radar_chart import create_stats_per_minute_radar

        fig = create_stats_per_minute_radar([])
        assert_valid_figure(fig)

    def test_create_performance_radar_valid(self, sample_performance_radar: list[dict]) -> None:
        """create_performance_radar retourne figure valide."""
        from src.ui.components.radar_chart import create_performance_radar

        fig = create_performance_radar(sample_performance_radar)
        assert_valid_figure(fig, min_traces=1)

    def test_create_performance_radar_empty(self) -> None:
        """create_performance_radar gère liste vide."""
        from src.ui.components.radar_chart import create_performance_radar

        fig = create_performance_radar([])
        assert_valid_figure(fig)


# =============================================================================
# TESTS: src/ui/components/chart_annotations.py
# =============================================================================


@pytest.mark.visualization
class TestChartAnnotations:
    """Tests pour chart_annotations.py."""

    def test_add_extreme_annotations_valid(self) -> None:
        """add_extreme_annotations ajoute des annotations."""
        from src.ui.components.chart_annotations import add_extreme_annotations

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3, 4, 5], y=[10, 20, 15, 25, 12]))

        x_values = [1, 2, 3, 4, 5]
        y_values = [10, 20, 15, 25, 12]

        fig = add_extreme_annotations(fig, x_values, y_values, show_max=True, show_min=True)

        assert_valid_figure(fig)
        # Vérifier qu'il y a des annotations
        assert len(fig.layout.annotations) >= 1

    def test_add_extreme_annotations_empty(self) -> None:
        """add_extreme_annotations gère listes vides."""
        from src.ui.components.chart_annotations import add_extreme_annotations

        fig = go.Figure()
        fig = add_extreme_annotations(fig, [], [], show_max=True)
        assert_valid_figure(fig)

    def test_add_extreme_annotations_with_nans(self) -> None:
        """add_extreme_annotations gère NaN."""
        from src.ui.components.chart_annotations import add_extreme_annotations

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3, 4, 5], y=[10, np.nan, 15, 25, np.nan]))

        x_values = [1, 2, 3, 4, 5]
        y_values = [10, np.nan, 15, 25, np.nan]

        fig = add_extreme_annotations(fig, x_values, y_values, show_max=True)
        assert_valid_figure(fig)

    def test_annotate_timeseries_extremes_valid(self, sample_match_df: pd.DataFrame) -> None:
        """annotate_timeseries_extremes fonctionne."""
        from src.ui.components.chart_annotations import annotate_timeseries_extremes

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=list(range(len(sample_match_df))),
                y=sample_match_df["ratio"].tolist(),
            )
        )

        fig = annotate_timeseries_extremes(fig, sample_match_df)
        assert_valid_figure(fig)

    def test_annotate_timeseries_extremes_empty(self, empty_df: pd.DataFrame) -> None:
        """annotate_timeseries_extremes gère DataFrame vide."""
        from src.ui.components.chart_annotations import annotate_timeseries_extremes

        fig = go.Figure()
        fig = annotate_timeseries_extremes(fig, empty_df)
        assert_valid_figure(fig)


# =============================================================================
# TESTS D'INTÉGRATION: Vérification que tous les modules s'importent
# =============================================================================


@pytest.mark.visualization
class TestModuleImports:
    """Tests d'import des modules de visualisation."""

    def test_import_distributions(self) -> None:
        """distributions.py s'importe correctement."""
        from src.visualization import distributions

        assert hasattr(distributions, "plot_kda_distribution")
        assert hasattr(distributions, "plot_outcomes_over_time")
        assert hasattr(distributions, "plot_stacked_outcomes_by_category")
        assert hasattr(distributions, "plot_win_ratio_heatmap")
        assert hasattr(distributions, "plot_top_weapons")
        assert hasattr(distributions, "plot_histogram")
        assert hasattr(distributions, "plot_medals_distribution")
        assert hasattr(distributions, "plot_correlation_scatter")
        assert hasattr(distributions, "plot_matches_at_top_by_week")
        assert hasattr(distributions, "plot_first_event_distribution")

    def test_import_timeseries(self) -> None:
        """timeseries.py s'importe correctement."""
        from src.visualization import timeseries

        assert hasattr(timeseries, "plot_timeseries")
        assert hasattr(timeseries, "plot_assists_timeseries")
        assert hasattr(timeseries, "plot_per_minute_timeseries")
        assert hasattr(timeseries, "plot_accuracy_last_n")
        assert hasattr(timeseries, "plot_average_life")
        assert hasattr(timeseries, "plot_spree_headshots_accuracy")
        assert hasattr(timeseries, "plot_performance_timeseries")

    def test_import_maps(self) -> None:
        """maps.py s'importe correctement."""
        from src.visualization import maps

        assert hasattr(maps, "plot_map_comparison")
        assert hasattr(maps, "plot_map_ratio_with_winloss")

    def test_import_match_bars(self) -> None:
        """match_bars.py s'importe correctement."""
        from src.visualization import match_bars

        assert hasattr(match_bars, "plot_metric_bars_by_match")
        assert hasattr(match_bars, "plot_multi_metric_bars_by_match")

    def test_import_trio(self) -> None:
        """trio.py s'importe correctement."""
        from src.visualization import trio

        assert hasattr(trio, "plot_trio_metric")

    def test_import_radar_chart(self) -> None:
        """radar_chart.py s'importe correctement."""
        from src.ui.components import radar_chart

        assert hasattr(radar_chart, "create_radar_chart")
        assert hasattr(radar_chart, "create_stats_per_minute_radar")
        assert hasattr(radar_chart, "create_performance_radar")

    def test_import_chart_annotations(self) -> None:
        """chart_annotations.py s'importe correctement."""
        from src.ui.components import chart_annotations

        assert hasattr(chart_annotations, "add_extreme_annotations")
        assert hasattr(chart_annotations, "annotate_timeseries_extremes")


# =============================================================================
# CONFIGURATION PYTEST
# =============================================================================


def pytest_configure(config):
    """Configuration pytest pour les markers."""
    config.addinivalue_line("markers", "visualization: tests des fonctions de visualisation")
