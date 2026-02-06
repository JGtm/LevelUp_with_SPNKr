from __future__ import annotations

import pandas as pd
import pytest

try:
    import polars as pl
except ImportError:
    pl = None

from src.analysis.performance_score import compute_session_performance_score_v2


class TestPerformanceScoreV2:
    """Tests pour le score de performance v2."""

    def test_v2_renormalizes_when_missing_accuracy(self):
        """Si la précision est absente, les poids sont renormalisés (pas de 50 neutre) - Pandas."""
        df = pd.DataFrame(
            {
                "kills": [10, 8],
                "deaths": [5, 4],
                "assists": [2, 1],
                "outcome": [2, 3],
                "kills_per_min": [0.6, 0.6],
                "average_life_seconds": [40.0, 40.0],
            }
        )

        perf = compute_session_performance_score_v2(df, include_mmr_adjustment=False)

        assert perf["score"] is not None
        weights = perf["weights_used"]
        assert "acc" not in weights
        # Les poids v2 sans accuracy : kd=0.20, win=0.15, kpm=0.15, life=0.10 = 0.60
        # (puis renormalisés à 1.0 lors du calcul)
        assert abs(sum(weights.values()) - (0.20 + 0.15 + 0.15 + 0.10)) < 1e-9

    @pytest.mark.skipif(pl is None, reason="Polars not available")
    def test_v2_renormalizes_when_missing_accuracy_polars(self):
        """Si la précision est absente, les poids sont renormalisés (pas de 50 neutre) - Polars."""
        df = pl.DataFrame(
            {
                "kills": [10, 8],
                "deaths": [5, 4],
                "assists": [2, 1],
                "outcome": [2, 3],
                "kills_per_min": [0.6, 0.6],
                "average_life_seconds": [40.0, 40.0],
            }
        )

        perf = compute_session_performance_score_v2(df, include_mmr_adjustment=False)

        assert perf["score"] is not None
        weights = perf["weights_used"]
        assert "acc" not in weights
        # Les poids v2 sans accuracy : kd=0.20, win=0.15, kpm=0.15, life=0.10 = 0.60
        # (puis renormalisés à 1.0 lors du calcul)
        assert abs(sum(weights.values()) - (0.20 + 0.15 + 0.15 + 0.10)) < 1e-9

    def test_v2_includes_objective_when_columns_present(self):
        """La composante objectif est incluse si une colonne objectif est présente - Pandas."""
        df = pd.DataFrame(
            {
                "kills": [10, 10],
                "deaths": [10, 10],
                "assists": [0, 0],
                "outcome": [2, 2],
                "accuracy": [50.0, 50.0],
                "kills_per_min": [0.5, 0.5],
                "average_life_seconds": [30.0, 30.0],
                "flag_captures": [1, 0],
            }
        )

        perf = compute_session_performance_score_v2(df, include_mmr_adjustment=False)

        assert perf["objective_score"] is not None
        assert "obj" in perf["components"]
        assert "flag_captures" in perf["objective_columns"]

    @pytest.mark.skipif(pl is None, reason="Polars not available")
    def test_v2_includes_objective_when_columns_present_polars(self):
        """La composante objectif est incluse si une colonne objectif est présente - Polars."""
        df = pl.DataFrame(
            {
                "kills": [10, 10],
                "deaths": [10, 10],
                "assists": [0, 0],
                "outcome": [2, 2],
                "accuracy": [50.0, 50.0],
                "kills_per_min": [0.5, 0.5],
                "average_life_seconds": [30.0, 30.0],
                "flag_captures": [1, 0],
            }
        )

        perf = compute_session_performance_score_v2(df, include_mmr_adjustment=False)

        assert perf["objective_score"] is not None
        assert "obj" in perf["components"]
        assert "flag_captures" in perf["objective_columns"]

    def test_v2_confidence_label(self):
        """Le label de confiance reflète la taille de session."""
        df_small = pd.DataFrame(
            {
                "kills": [1, 1, 1],
                "deaths": [1, 1, 1],
                "assists": [0, 0, 0],
                "outcome": [2, 3, 3],
                "accuracy": [40.0, 40.0, 40.0],
            }
        )
        perf_small = compute_session_performance_score_v2(df_small, include_mmr_adjustment=False)
        assert perf_small["confidence_label"] == "faible"

        df_big = pd.concat([df_small] * 4, ignore_index=True)
        perf_big = compute_session_performance_score_v2(df_big, include_mmr_adjustment=False)
        assert perf_big["confidence_label"] in ("moyenne", "élevée")
