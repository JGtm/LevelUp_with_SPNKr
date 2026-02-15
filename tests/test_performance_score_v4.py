"""Tests pour le score de performance v4-relative.

Ce fichier teste :
- Les nouvelles métriques v4 : PSPM, DPM damage, Rank Performance
- La graceful degradation quand les nouvelles métriques sont absentes
- La compatibilité avec les données v3 (sans les colonnes v4)
- Le helper _compute_rank_performance()
- Le helper _prepare_history_metrics() avec les nouvelles colonnes
"""

from __future__ import annotations

import polars as pl
import pytest

from src.analysis.performance_config import (
    PERFORMANCE_SCORE_VERSION,
    RELATIVE_WEIGHTS,
)
from src.analysis.performance_score import (
    _compute_rank_performance,
    _prepare_history_metrics,
    compute_relative_performance_score,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def history_v3() -> pl.DataFrame:
    """Historique de matchs v3 (sans les colonnes v4 : personal_score, damage_dealt, rank, mmrs)."""
    n = 20
    return pl.DataFrame(
        {
            "kills": [10 + i for i in range(n)],
            "deaths": [8] * n,
            "assists": [3] * n,
            "kda": [1.5 + (i * 0.1) for i in range(n)],
            "accuracy": [0.50] * n,
            "time_played_seconds": [600] * n,
        }
    )


@pytest.fixture
def history_v4() -> pl.DataFrame:
    """Historique de matchs v4 (avec toutes les colonnes)."""
    n = 20
    return pl.DataFrame(
        {
            "kills": [10 + i for i in range(n)],
            "deaths": [8] * n,
            "assists": [3] * n,
            "kda": [1.5 + (i * 0.1) for i in range(n)],
            "accuracy": [0.50] * n,
            "time_played_seconds": [600] * n,
            "personal_score": [1000 + i * 50 for i in range(n)],
            "damage_dealt": [2000.0 + i * 100 for i in range(n)],
            "rank": [4 + (i % 5) for i in range(n)],
            "team_mmr": [1200.0 + i * 5 for i in range(n)],
            "enemy_mmr": [1200.0 + (n - i) * 5 for i in range(n)],
        }
    )


@pytest.fixture
def match_row_v3() -> dict:
    """Match courant sans les métriques v4."""
    return {
        "kills": 15,
        "deaths": 6,
        "assists": 4,
        "kda": 3.0,
        "accuracy": 0.55,
        "time_played_seconds": 600,
    }


@pytest.fixture
def match_row_v4() -> dict:
    """Match courant avec les métriques v4."""
    return {
        "kills": 15,
        "deaths": 6,
        "assists": 4,
        "kda": 3.0,
        "accuracy": 0.55,
        "time_played_seconds": 600,
        "personal_score": 1500,
        "damage_dealt": 3000.0,
        "rank": 2,
        "team_mmr": 1250.0,
        "enemy_mmr": 1300.0,
    }


# =============================================================================
# Tests de la version
# =============================================================================


class TestVersionConfig:
    """Tests sur la configuration v4."""

    def test_version_is_v4(self):
        assert PERFORMANCE_SCORE_VERSION == "v4-relative"

    def test_weights_have_8_metrics(self):
        assert len(RELATIVE_WEIGHTS) == 8

    def test_weights_sum_to_one(self):
        total = sum(RELATIVE_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Total des poids = {total}, attendu 1.0"

    def test_new_metrics_present(self):
        assert "pspm" in RELATIVE_WEIGHTS
        assert "dpm_damage" in RELATIVE_WEIGHTS
        assert "rank_perf" in RELATIVE_WEIGHTS

    def test_dpm_renamed_to_dpm_deaths(self):
        """L'ancienne clé 'dpm' n'existe plus, remplacée par 'dpm_deaths'."""
        assert "dpm" not in RELATIVE_WEIGHTS
        assert "dpm_deaths" in RELATIVE_WEIGHTS


# =============================================================================
# Tests _prepare_history_metrics
# =============================================================================


class TestPrepareHistoryMetrics:
    """Tests pour _prepare_history_metrics v4."""

    def test_returns_8_columns(self, history_v4: pl.DataFrame):
        result = _prepare_history_metrics(history_v4)
        expected_cols = {
            "kpm",
            "dpm_deaths",
            "apm",
            "kda",
            "accuracy",
            "pspm",
            "dpm_damage",
            "rank_perf_diff",
        }
        assert set(result.columns) == expected_cols

    def test_empty_df_returns_empty_with_correct_schema(self):
        result = _prepare_history_metrics(pl.DataFrame())
        assert result.is_empty()
        assert len(result.columns) == 8

    def test_v3_data_has_null_new_columns(self, history_v3: pl.DataFrame):
        """Avec des données v3 (sans personal_score etc.), les nouvelles colonnes sont nulles."""
        result = _prepare_history_metrics(history_v3)
        assert result.get_column("pspm").null_count() == len(result)
        assert result.get_column("dpm_damage").null_count() == len(result)
        assert result.get_column("rank_perf_diff").null_count() == len(result)

    def test_v4_data_has_values(self, history_v4: pl.DataFrame):
        """Avec des données v4, les nouvelles colonnes ont des valeurs."""
        result = _prepare_history_metrics(history_v4)
        assert result.get_column("pspm").null_count() == 0
        assert result.get_column("dpm_damage").null_count() == 0
        assert result.get_column("rank_perf_diff").null_count() == 0

    def test_pspm_calculation(self):
        """PSPM = personal_score / minutes."""
        df = pl.DataFrame(
            {
                "kills": [10],
                "deaths": [5],
                "assists": [3],
                "time_played_seconds": [600],
                "personal_score": [1200],
            }
        )
        result = _prepare_history_metrics(df)
        pspm = result.get_column("pspm")[0]
        assert abs(pspm - 120.0) < 0.1  # 1200 / 10 min = 120/min

    def test_dpm_damage_calculation(self):
        """DPM Damage = damage_dealt / minutes."""
        df = pl.DataFrame(
            {
                "kills": [10],
                "deaths": [5],
                "assists": [3],
                "time_played_seconds": [600],
                "damage_dealt": [3000.0],
            }
        )
        result = _prepare_history_metrics(df)
        dpm_damage = result.get_column("dpm_damage")[0]
        assert abs(dpm_damage - 300.0) < 0.1  # 3000 / 10 min = 300/min

    def test_rank_perf_diff_calculation(self):
        """rank_perf_diff = expected_rank - actual_rank."""
        df = pl.DataFrame(
            {
                "kills": [10],
                "deaths": [5],
                "assists": [3],
                "time_played_seconds": [600],
                "rank": [2],
                "team_mmr": [1200.0],
                "enemy_mmr": [1200.0],  # delta = 0 => expected = 4.5
            }
        )
        result = _prepare_history_metrics(df)
        rank_diff = result.get_column("rank_perf_diff")[0]
        # expected_rank = 4.5 - 0 = 4.5, actual = 2, diff = 4.5 - 2 = 2.5
        assert abs(rank_diff - 2.5) < 0.1


# =============================================================================
# Tests _compute_rank_performance
# =============================================================================


class TestComputeRankPerformance:
    """Tests pour _compute_rank_performance."""

    def test_returns_none_without_rank(self, history_v4: pl.DataFrame):
        metrics = _prepare_history_metrics(history_v4)
        result = _compute_rank_performance(None, 1200.0, 1200.0, metrics)
        assert result is None

    def test_returns_none_without_mmr(self, history_v4: pl.DataFrame):
        metrics = _prepare_history_metrics(history_v4)
        result = _compute_rank_performance(2, None, 1200.0, metrics)
        assert result is None

    def test_returns_none_without_history_column(self):
        """Sans la colonne rank_perf_diff dans l'historique."""
        metrics = pl.DataFrame({"kpm": [1.0], "dpm_deaths": [0.5]})
        result = _compute_rank_performance(2, 1200.0, 1200.0, metrics)
        assert result is None

    def test_good_rank_gets_high_percentile(self, history_v4: pl.DataFrame):
        """Un bon rang (1) avec MMR neutre devrait avoir un percentile élevé."""
        metrics = _prepare_history_metrics(history_v4)
        result = _compute_rank_performance(1, 1200.0, 1200.0, metrics)
        assert result is not None
        assert result >= 50  # Rang 1 = meilleur que la médiane

    def test_bad_rank_gets_low_percentile(self, history_v4: pl.DataFrame):
        """Un mauvais rang (8) avec MMR neutre devrait avoir un percentile faible."""
        metrics = _prepare_history_metrics(history_v4)
        result = _compute_rank_performance(8, 1200.0, 1200.0, metrics)
        assert result is not None
        assert result <= 50  # Rang 8 = pire que la médiane

    def test_returns_percentile_in_range(self, history_v4: pl.DataFrame):
        metrics = _prepare_history_metrics(history_v4)
        result = _compute_rank_performance(3, 1250.0, 1200.0, metrics)
        assert result is not None
        assert 0 <= result <= 100


# =============================================================================
# Tests compute_relative_performance_score v4
# =============================================================================


class TestComputeRelativePerformanceScoreV4:
    """Tests pour le calcul de score v4."""

    def test_returns_score_with_v4_data(self, match_row_v4: dict, history_v4: pl.DataFrame):
        """Avec toutes les données v4, un score est calculé."""
        score = compute_relative_performance_score(match_row_v4, history_v4)
        assert score is not None
        assert 0 <= score <= 100

    def test_graceful_degradation_v3_data(self, match_row_v3: dict, history_v3: pl.DataFrame):
        """Avec des données v3 uniquement, le score est quand même calculé (graceful degradation)."""
        score = compute_relative_performance_score(match_row_v3, history_v3)
        assert score is not None
        assert 0 <= score <= 100

    def test_v4_data_uses_more_metrics_than_v3(
        self,
        match_row_v4: dict,
        history_v4: pl.DataFrame,
        match_row_v3: dict,
        history_v3: pl.DataFrame,
    ):
        """Le score v4 utilise plus de métriques que le fallback v3."""
        # Ce test vérifie surtout que les deux modes fonctionnent sans erreur
        score_v4 = compute_relative_performance_score(match_row_v4, history_v4)
        score_v3 = compute_relative_performance_score(match_row_v3, history_v3)
        assert score_v4 is not None
        assert score_v3 is not None

    def test_returns_none_with_insufficient_history(self, match_row_v4: dict):
        """Retourne None avec moins de MIN_MATCHES_FOR_RELATIVE matchs."""
        small_history = pl.DataFrame(
            {
                "kills": [10, 12],
                "deaths": [8, 8],
                "assists": [3, 3],
                "kda": [1.5, 1.7],
                "accuracy": [0.50, 0.50],
                "time_played_seconds": [600, 600],
            }
        )
        score = compute_relative_performance_score(match_row_v4, small_history)
        assert score is None

    def test_returns_none_with_empty_history(self, match_row_v4: dict):
        score = compute_relative_performance_score(match_row_v4, pl.DataFrame())
        assert score is None

    def test_partial_v4_data(self, history_v4: pl.DataFrame):
        """Match avec seulement certaines métriques v4 (ex: personal_score mais pas damage_dealt)."""
        match_row = {
            "kills": 15,
            "deaths": 6,
            "assists": 4,
            "kda": 3.0,
            "accuracy": 0.55,
            "time_played_seconds": 600,
            "personal_score": 1500,
            # pas de damage_dealt, rank, mmrs
        }
        score = compute_relative_performance_score(match_row, history_v4)
        assert score is not None
        assert 0 <= score <= 100

    def test_high_pspm_increases_score(self, history_v4: pl.DataFrame):
        """Un PSPM très élevé devrait pousser le score vers le haut."""
        # Match avec très haut personal_score
        high_row = {
            "kills": 15,
            "deaths": 6,
            "assists": 4,
            "kda": 3.0,
            "accuracy": 0.55,
            "time_played_seconds": 600,
            "personal_score": 5000,  # Très élevé
            "damage_dealt": 3000.0,
            "rank": 3,
            "team_mmr": 1250.0,
            "enemy_mmr": 1250.0,
        }
        # Match avec personal_score normal
        normal_row = dict(high_row)
        normal_row["personal_score"] = 1000  # Normal

        score_high = compute_relative_performance_score(high_row, history_v4)
        score_normal = compute_relative_performance_score(normal_row, history_v4)
        assert score_high is not None
        assert score_normal is not None
        assert score_high > score_normal

    def test_high_damage_increases_score(self, history_v4: pl.DataFrame):
        """Un DPM damage élevé devrait pousser le score vers le haut."""
        high_row = {
            "kills": 15,
            "deaths": 6,
            "assists": 4,
            "kda": 3.0,
            "accuracy": 0.55,
            "time_played_seconds": 600,
            "personal_score": 1500,
            "damage_dealt": 10000.0,  # Très élevé
            "rank": 3,
            "team_mmr": 1250.0,
            "enemy_mmr": 1250.0,
        }
        normal_row = dict(high_row)
        normal_row["damage_dealt"] = 2000.0  # Normal

        score_high = compute_relative_performance_score(high_row, history_v4)
        score_normal = compute_relative_performance_score(normal_row, history_v4)
        assert score_high is not None
        assert score_normal is not None
        assert score_high > score_normal

    def test_accepts_pandas_history(self, match_row_v3: dict, history_v3: pl.DataFrame):
        """Le score accepte un DataFrame Pandas (converti en Polars en interne)."""
        pd_history = history_v3.to_pandas()
        score = compute_relative_performance_score(match_row_v3, pd_history)
        assert score is not None
        assert 0 <= score <= 100
