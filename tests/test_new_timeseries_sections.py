"""Tests pour les nouvelles sections Timeseries + Corrélations (Sprint 6).

Teste :
1. Corrélations : Durée vie vs Morts, Kills vs Deaths, Team MMR vs Enemy MMR
2. Distribution "Score personnel par minute"
3. Distribution "Taux de victoire" (fenêtre glissante 10 matchs)
4. Performance cumulée : lignes verticales tous les ~8 min

Exécution :
    pytest tests/test_new_timeseries_sections.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

# Tenter l'import du package visualization complet.
# Sur les envs sans duckdb (MSYS2), l'__init__.py échoue mais les sous-modules
# restent partiellement en cache dans sys.modules.
try:
    from src.visualization.distributions import (  # noqa: F401
        plot_correlation_scatter,
        plot_histogram,
    )
    from src.visualization.performance import (  # noqa: F401
        plot_cumulative_kd,
        plot_cumulative_net_score,
    )

    VIZ_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    VIZ_AVAILABLE = False


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_match_df() -> pd.DataFrame:
    """DataFrame avec colonnes nécessaires pour Sprint 6."""
    np.random.seed(42)
    n = 30
    return pd.DataFrame(
        {
            "match_id": [f"match_{i}" for i in range(n)],
            "start_time": pd.date_range("2025-01-01", periods=n, freq="h"),
            "kills": np.random.randint(5, 25, n),
            "deaths": np.random.randint(3, 15, n),
            "assists": np.random.randint(2, 12, n),
            "accuracy": np.random.uniform(30, 60, n),
            "kda": np.random.uniform(-5, 10, n),
            "outcome": np.random.choice([1, 2, 3, 4], n),
            "average_life_seconds": np.random.uniform(20, 60, n),
            "avg_life_seconds": np.random.uniform(20, 60, n),
            "time_played_seconds": np.random.randint(300, 900, n),
            "team_mmr": np.random.uniform(1000, 2000, n),
            "enemy_mmr": np.random.uniform(1000, 2000, n),
            "personal_score": np.random.randint(500, 3000, n),
        }
    )


@pytest.fixture
def empty_df() -> pd.DataFrame:
    """DataFrame vide."""
    return pd.DataFrame(
        columns=[
            "match_id",
            "start_time",
            "kills",
            "deaths",
            "assists",
            "accuracy",
            "kda",
            "outcome",
            "average_life_seconds",
            "avg_life_seconds",
            "time_played_seconds",
            "team_mmr",
            "enemy_mmr",
            "personal_score",
        ]
    )


@pytest.fixture
def small_df() -> pd.DataFrame:
    """DataFrame trop petit pour le win rate glissant (< 10 matchs)."""
    np.random.seed(42)
    n = 5
    return pd.DataFrame(
        {
            "match_id": [f"match_{i}" for i in range(n)],
            "start_time": pd.date_range("2025-01-01", periods=n, freq="h"),
            "kills": np.random.randint(5, 25, n),
            "deaths": np.random.randint(3, 15, n),
            "outcome": np.random.choice([1, 2, 3], n),
            "time_played_seconds": np.random.randint(300, 900, n),
            "personal_score": np.random.randint(500, 3000, n),
        }
    )


def assert_valid_figure(fig: go.Figure, min_traces: int = 0) -> None:
    """Vérifie qu'une figure Plotly est valide."""
    assert isinstance(fig, go.Figure), f"Expected go.Figure, got {type(fig)}"
    assert fig.layout is not None
    if min_traces > 0:
        assert len(fig.data) >= min_traces, f"Expected >= {min_traces} traces, got {len(fig.data)}"


# =============================================================================
# 6.1 — Corrélations scatter plots
# =============================================================================


@pytest.mark.skipif(not VIZ_AVAILABLE, reason="src.visualization non importable (duckdb manquant)")
class TestCorrelationScatterPlots:
    """Tests pour les graphes de corrélation (P6 §2.1-2.3)."""

    def test_lifespan_vs_deaths_scatter(self, sample_match_df: pd.DataFrame) -> None:
        """Scatter durée de vie moyenne vs nombre de morts."""
        from src.visualization.distributions import plot_correlation_scatter

        fig = plot_correlation_scatter(
            sample_match_df,
            "avg_life_seconds",
            "deaths",
            color_col="outcome",
            title="Durée de vie vs morts",
            x_label="Durée de vie (s)",
            y_label="Morts",
            show_trendline=True,
        )
        assert_valid_figure(fig, min_traces=1)

    def test_kills_vs_deaths_scatter(self, sample_match_df: pd.DataFrame) -> None:
        """Scatter frags vs morts avec ligne de tendance."""
        from src.visualization.distributions import plot_correlation_scatter

        fig = plot_correlation_scatter(
            sample_match_df,
            "kills",
            "deaths",
            color_col="outcome",
            title="Frags vs morts",
            x_label="Frags",
            y_label="Morts",
            show_trendline=True,
        )
        assert_valid_figure(fig, min_traces=1)
        # Vérifier tendance (2 traces : scatter + trendline)
        assert len(fig.data) >= 2, "Devrait avoir scatter + trendline"

    def test_team_mmr_vs_enemy_mmr_scatter(self, sample_match_df: pd.DataFrame) -> None:
        """Scatter Team MMR vs Enemy MMR retourne figure valide."""
        from src.visualization.distributions import plot_correlation_scatter

        fig = plot_correlation_scatter(
            sample_match_df,
            "team_mmr",
            "enemy_mmr",
            color_col="outcome",
            title="MMR Équipe vs MMR Adversaire",
            x_label="MMR Équipe",
            y_label="MMR Adversaire",
            show_trendline=True,
        )
        assert_valid_figure(fig, min_traces=1)

    def test_scatter_empty_data(self, empty_df: pd.DataFrame) -> None:
        """Scatter gère DataFrame vide gracieusement."""
        from src.visualization.distributions import plot_correlation_scatter

        fig = plot_correlation_scatter(
            empty_df,
            "kills",
            "deaths",
            title="Vide",
        )
        assert_valid_figure(fig)

    @pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non disponible")
    def test_scatter_accepts_polars(self, sample_match_df: pd.DataFrame) -> None:
        """Scatter accepte un DataFrame Polars."""
        pytest.importorskip("pyarrow", reason="pyarrow requis pour Polars .to_pandas()")
        from src.visualization.distributions import plot_correlation_scatter

        pl_df = pl.from_pandas(sample_match_df)
        fig = plot_correlation_scatter(
            pl_df,
            "kills",
            "deaths",
            color_col="outcome",
        )
        assert_valid_figure(fig, min_traces=1)

    def test_scatter_trendline_has_r_squared(self, sample_match_df: pd.DataFrame) -> None:
        """Trendline contient la valeur R² dans le nom."""
        from src.visualization.distributions import plot_correlation_scatter

        fig = plot_correlation_scatter(
            sample_match_df,
            "kills",
            "deaths",
            show_trendline=True,
        )
        assert len(fig.data) >= 2
        assert "R²" in fig.data[1].name


# =============================================================================
# 6.2 — Distribution score personnel par minute
# =============================================================================


@pytest.mark.skipif(not VIZ_AVAILABLE, reason="src.visualization non importable (duckdb manquant)")
class TestPersonalScorePerMinuteDistribution:
    """Tests pour la distribution du score personnel / minute (P6 §2.4)."""

    def test_score_per_minute_histogram(self, sample_match_df: pd.DataFrame) -> None:
        """Histogramme du score personnel par minute avec médiane."""
        from src.visualization.distributions import plot_histogram

        ps = sample_match_df[["personal_score", "time_played_seconds"]].dropna()
        ps = ps[ps["time_played_seconds"] > 0]
        score_per_min = ps["personal_score"] / (ps["time_played_seconds"] / 60)

        fig = plot_histogram(
            score_per_min,
            title="Distribution Score Personnel / min",
            x_label="Score / min",
            y_label="Matchs",
            show_kde=True,
        )
        assert_valid_figure(fig, min_traces=1)

    def test_score_per_minute_excludes_zero_time(self) -> None:
        """Score/min exclut les matchs avec time_played_seconds == 0."""
        df = pd.DataFrame(
            {
                "personal_score": [100, 200, 300, 400, 500, 600, 700],
                "time_played_seconds": [0, 300, 0, 600, 450, 500, 0],
            }
        )
        ps = df[df["time_played_seconds"] > 0]
        score_per_min = ps["personal_score"] / (ps["time_played_seconds"] / 60)

        assert len(score_per_min) == 4  # 4 matchs avec time > 0
        assert all(v > 0 for v in score_per_min)

    def test_score_per_minute_empty(self) -> None:
        """Score/min gère données vides."""
        from src.visualization.distributions import plot_histogram

        fig = plot_histogram(
            pd.Series([], dtype=float),
            title="Score/min vide",
            x_label="Score / min",
        )
        assert_valid_figure(fig)


# =============================================================================
# 6.3 — Taux de victoire glissant
# =============================================================================


@pytest.mark.skipif(not VIZ_AVAILABLE, reason="src.visualization non importable (duckdb manquant)")
class TestWinRatioRollingDistribution:
    """Tests pour le taux de victoire en fenêtre glissante (P6 §2.5)."""

    def test_win_ratio_rolling_window(self, sample_match_df: pd.DataFrame) -> None:
        """Taux de victoire sur fenêtre glissante produit des valeurs valides."""
        df = sample_match_df.sort_values("start_time")
        wins = (df["outcome"] == 2).astype(float)
        win_rate_rolling = wins.rolling(window=10, min_periods=10).mean() * 100
        win_rate_clean = win_rate_rolling.dropna()

        # 30 matchs - 10 window + 1 = 21 valeurs
        assert len(win_rate_clean) == 21

    def test_win_ratio_rolling_histogram(self, sample_match_df: pd.DataFrame) -> None:
        """Histogramme du win rate glissant retourne figure valide."""
        from src.visualization.distributions import plot_histogram

        df = sample_match_df.sort_values("start_time")
        wins = (df["outcome"] == 2).astype(float)
        win_rate_rolling = wins.rolling(window=10, min_periods=10).mean() * 100
        win_rate_clean = win_rate_rolling.dropna()

        fig = plot_histogram(
            win_rate_clean,
            title="Distribution Win Rate Glissant (10 matchs)",
            x_label="Taux de victoire (%)",
            y_label="Fréquence",
            show_kde=True,
        )
        assert_valid_figure(fig, min_traces=1)

    def test_win_ratio_values_in_0_100(self, sample_match_df: pd.DataFrame) -> None:
        """Win rate glissant est borné entre 0 et 100%."""
        df = sample_match_df.sort_values("start_time")
        wins = (df["outcome"] == 2).astype(float)
        win_rate_rolling = wins.rolling(window=10, min_periods=10).mean() * 100
        win_rate_clean = win_rate_rolling.dropna()

        assert win_rate_clean.min() >= 0.0
        assert win_rate_clean.max() <= 100.0

    def test_win_ratio_too_few_matches(self, small_df: pd.DataFrame) -> None:
        """Win rate glissant ne produit rien avec < 10 matchs."""
        df = small_df.sort_values("start_time") if "start_time" in small_df.columns else small_df
        wins = (df["outcome"] == 2).astype(float)
        win_rate_rolling = wins.rolling(window=10, min_periods=10).mean() * 100
        win_rate_clean = win_rate_rolling.dropna()

        assert len(win_rate_clean) == 0

    def test_win_ratio_all_wins(self) -> None:
        """Win rate = 100% si tous gagnés."""
        n = 15
        df = pd.DataFrame(
            {
                "outcome": [2] * n,
                "start_time": pd.date_range("2025-01-01", periods=n, freq="h"),
            }
        )
        wins = (df["outcome"] == 2).astype(float)
        win_rate_rolling = wins.rolling(window=10, min_periods=10).mean() * 100
        win_rate_clean = win_rate_rolling.dropna()

        assert len(win_rate_clean) == 6
        assert all(v == 100.0 for v in win_rate_clean)


# =============================================================================
# 6.4 — Performance cumulée améliorée
# =============================================================================


@pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non disponible")
@pytest.mark.skipif(not VIZ_AVAILABLE, reason="src.visualization non importable (duckdb manquant)")
class TestCumulativePerformanceEnhanced:
    """Tests pour les améliorations performance cumulée (P6 §2.6)."""

    def _make_cumulative_df(self, n: int = 20) -> pl.DataFrame:
        """Crée un DataFrame cumulatif de test."""
        np.random.seed(42)
        kills = np.random.randint(5, 20, n)
        deaths = np.random.randint(3, 12, n)
        net_score = kills - deaths
        cumulative = np.cumsum(net_score)

        return pl.DataFrame(
            {
                "match_id": [f"match_{i}" for i in range(n)],
                "start_time": [f"2025-01-01T{i:02d}:00:00" for i in range(n)],
                "net_score": net_score.tolist(),
                "cumulative_net_score": cumulative.tolist(),
            }
        )

    def _make_cumulative_kd_df(self, n: int = 20) -> pl.DataFrame:
        """Crée un DataFrame K/D cumulatif de test."""
        np.random.seed(42)
        kills = np.random.randint(5, 20, n)
        deaths = np.random.randint(3, 12, n)
        kd = kills / np.maximum(deaths, 1)
        cumul_kills = np.cumsum(kills)
        cumul_deaths = np.cumsum(deaths)
        cumul_kd = cumul_kills / np.maximum(cumul_deaths, 1)

        return pl.DataFrame(
            {
                "match_id": [f"match_{i}" for i in range(n)],
                "start_time": [f"2025-01-01T{i:02d}:00:00" for i in range(n)],
                "kd": kd.tolist(),
                "cumulative_kd": cumul_kd.tolist(),
            }
        )

    def test_vertical_lines_interval(self) -> None:
        """Lignes verticales de repère temporel (~8 min)."""
        from src.visualization.performance import plot_cumulative_net_score

        df = self._make_cumulative_df(20)
        tps = [480] * 20  # 8 min chaque match

        fig = plot_cumulative_net_score(df, time_played_seconds=tps)
        assert_valid_figure(fig, min_traces=1)

    def test_cumulative_kd_with_markers(self) -> None:
        """K/D cumulé avec marqueurs retourne figure valide."""
        from src.visualization.performance import plot_cumulative_kd

        df = self._make_cumulative_kd_df(20)
        tps = [480] * 20

        fig = plot_cumulative_kd(df, time_played_seconds=tps)
        assert_valid_figure(fig, min_traces=1)

    def test_backward_compatible_no_markers(self) -> None:
        """Appel sans time_played_seconds reste compatible."""
        from src.visualization.performance import plot_cumulative_net_score

        df = self._make_cumulative_df(10)
        fig = plot_cumulative_net_score(df)
        assert_valid_figure(fig, min_traces=1)

    def test_markers_none_time_played(self) -> None:
        """time_played_seconds=None ne casse pas."""
        from src.visualization.performance import plot_cumulative_net_score

        df = self._make_cumulative_df(10)
        fig = plot_cumulative_net_score(df, time_played_seconds=None)
        assert_valid_figure(fig, min_traces=1)

    def test_markers_custom_interval(self) -> None:
        """Intervalle personnalisé (16 min) fonctionne."""
        from src.visualization.performance import plot_cumulative_net_score

        df = self._make_cumulative_df(20)
        tps = [480] * 20

        fig = plot_cumulative_net_score(df, time_played_seconds=tps, duration_marker_minutes=16.0)
        assert_valid_figure(fig, min_traces=1)

    def test_markers_empty_df(self) -> None:
        """Marqueurs sur DataFrame vide ne crashent pas."""
        from src.visualization.performance import plot_cumulative_net_score

        empty = pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "start_time": pl.Utf8,
                "net_score": pl.Int64,
                "cumulative_net_score": pl.Int64,
            }
        )
        fig = plot_cumulative_net_score(empty, time_played_seconds=[])
        assert_valid_figure(fig)


# =============================================================================
# 6.M1 — Vérification performance.py est Polars pur
# =============================================================================


class TestPolarsPerformanceModule:
    """Vérifie que performance.py n'importe pas pandas."""

    def test_no_pandas_import_in_performance(self) -> None:
        """performance.py n'importe pas pandas directement."""
        import inspect

        from src.visualization import performance

        source = inspect.getsource(performance)
        lines = source.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "import pandas" in stripped:
                pytest.fail(f"performance.py importe pandas: {stripped}")


# =============================================================================
# INTÉGRATION — personal_score dans MatchRow
# =============================================================================


class TestPersonalScoreField:
    """Vérifie que personal_score est disponible dans MatchRow."""

    def test_matchrow_has_personal_score(self) -> None:
        """MatchRow contient le champ personal_score."""
        from datetime import datetime

        from src.data.domain.models.stats import MatchRow

        row = MatchRow(
            match_id="test",
            start_time=datetime(2025, 1, 1),
            map_id=None,
            map_name=None,
            playlist_id=None,
            playlist_name=None,
            map_mode_pair_id=None,
            map_mode_pair_name=None,
            outcome=2,
            last_team_id=0,
            kda=1.5,
            max_killing_spree=3,
            headshot_kills=5,
            average_life_seconds=30.0,
            time_played_seconds=480,
            kills=10,
            deaths=5,
            assists=3,
            accuracy=45.0,
            personal_score=1500,
        )
        assert row.personal_score == 1500

    def test_matchrow_personal_score_default_none(self) -> None:
        """MatchRow.personal_score par défaut est None."""
        from datetime import datetime

        from src.data.domain.models.stats import MatchRow

        row = MatchRow(
            match_id="test",
            start_time=datetime(2025, 1, 1),
            map_id=None,
            map_name=None,
            playlist_id=None,
            playlist_name=None,
            map_mode_pair_id=None,
            map_mode_pair_name=None,
            outcome=2,
            last_team_id=0,
            kda=1.5,
            max_killing_spree=3,
            headshot_kills=5,
            average_life_seconds=30.0,
            time_played_seconds=480,
            kills=10,
            deaths=5,
            assists=3,
            accuracy=45.0,
        )
        assert row.personal_score is None
