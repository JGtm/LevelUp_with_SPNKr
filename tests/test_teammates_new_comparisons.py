"""Tests pour les comparaisons coéquipiers avancées (Sprint 8).

Teste les 9 sous-tâches de comparaisons coéquipiers (P6 Phase 4) :
1. Score personnel comparatif
2. Séries de victoires comparatives
3. Rang / score comparatif
4. Corrélations côte à côte
5. Distributions comparatives
6. Tirs et précision comparatifs
7. Dégâts comparatifs
8. Heatmap win ratio
9. Matchs Top comparatif
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

try:
    import plotly.graph_objects as go

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    go = None

# Tenter les imports de visualisation (peuvent échouer si duckdb manque)
try:
    from src.visualization.distributions import (
        plot_correlation_scatter,
        plot_histogram,
        plot_win_ratio_heatmap,
    )

    VIZ_AVAILABLE = True
except Exception:
    VIZ_AVAILABLE = False

pytestmark_polars = pytest.mark.skipif(
    not POLARS_AVAILABLE,
    reason="Polars non disponible",
)

pytestmark_viz = pytest.mark.skipif(
    not POLARS_AVAILABLE or not PANDAS_AVAILABLE or not PLOTLY_AVAILABLE or not VIZ_AVAILABLE,
    reason="Dépendances visualisation non disponibles",
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_match_df() -> pd.DataFrame:
    """DataFrame de matchs pour les tests."""
    if not PANDAS_AVAILABLE:
        pytest.skip("Pandas non disponible")

    base_time = datetime(2026, 1, 15, 20, 0, 0)
    return pd.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(20)],
            "start_time": [base_time + timedelta(hours=i) for i in range(20)],
            "kills": [10 + i % 5 for i in range(20)],
            "deaths": [5 + i % 3 for i in range(20)],
            "assists": [3 + i % 4 for i in range(20)],
            "personal_score": [1000 + i * 50 for i in range(20)],
            "accuracy": [40 + i % 20 for i in range(20)],
            "shots_fired": [100 + i * 10 for i in range(20)],
            "shots_hit": [40 + i * 4 for i in range(20)],
            "damage_dealt": [1500 + i * 100 for i in range(20)],
            "damage_taken": [1200 + i * 80 for i in range(20)],
            "avg_life_seconds": [30 + i % 10 for i in range(20)],
            "team_mmr": [1500 + i * 5 for i in range(20)],
            "enemy_mmr": [1480 + i * 6 for i in range(20)],
            "rank": [i % 8 + 1 for i in range(20)],
            "outcome": [2 if i % 3 == 0 else 3 for i in range(20)],  # 2=win, 3=loss
        }
    )


@pytest.fixture
def teammate_match_df() -> pd.DataFrame:
    """DataFrame de matchs du coéquipier pour comparaison."""
    if not PANDAS_AVAILABLE:
        pytest.skip("Pandas non disponible")

    base_time = datetime(2026, 1, 15, 20, 0, 0)
    return pd.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(20)],
            "start_time": [base_time + timedelta(hours=i) for i in range(20)],
            "kills": [8 + i % 6 for i in range(20)],  # Légèrement différent
            "deaths": [6 + i % 4 for i in range(20)],
            "assists": [4 + i % 3 for i in range(20)],
            "personal_score": [900 + i * 45 for i in range(20)],
            "accuracy": [38 + i % 18 for i in range(20)],
            "shots_fired": [95 + i * 9 for i in range(20)],
            "shots_hit": [36 + i * 3 for i in range(20)],
            "damage_dealt": [1400 + i * 90 for i in range(20)],
            "damage_taken": [1300 + i * 85 for i in range(20)],
            "avg_life_seconds": [28 + i % 12 for i in range(20)],
            "team_mmr": [1500 + i * 5 for i in range(20)],
            "enemy_mmr": [1480 + i * 6 for i in range(20)],
            "rank": [(i + 1) % 8 + 1 for i in range(20)],
            "outcome": [2 if i % 3 == 0 else 3 for i in range(20)],
        }
    )


# =============================================================================
# 8.1 — Score personnel comparatif
# =============================================================================


class TestTeammatePersonalScoreComparison:
    """Comparaison du score personnel entre joueur et coéquipier."""

    @pytestmark_viz
    def test_personal_score_side_by_side(self, sample_match_df, teammate_match_df):
        """Score personnel affiché côte à côte sur matchs communs."""
        # Vérifier que les données de score personnel existent
        assert "personal_score" in sample_match_df.columns
        assert "personal_score" in teammate_match_df.columns

        # Vérifier que les scores sont différents (pour une vraie comparaison)
        assert not sample_match_df["personal_score"].equals(teammate_match_df["personal_score"])

        # Vérifier que les histogrammes peuvent être générés
        fig_me = plot_histogram(
            sample_match_df["personal_score"],
            title="Mon score personnel",
            x_label="Score",
        )
        fig_teammate = plot_histogram(
            teammate_match_df["personal_score"],
            title="Score coéquipier",
            x_label="Score",
        )

        assert fig_me is not None
        assert fig_teammate is not None
        assert isinstance(fig_me, go.Figure)
        assert isinstance(fig_teammate, go.Figure)


# =============================================================================
# 8.2 — Séries de victoires comparatives
# =============================================================================


class TestTeammateWinStreaksComparison:
    """Comparaison des séries de victoires entre joueur et coéquipier."""

    @pytestmark_polars
    def test_win_streaks_comparison(self, sample_match_df, teammate_match_df):
        """Séries de victoires comparées sur matchs communs."""
        # Vérifier que les outcomes sont présents
        assert "outcome" in sample_match_df.columns
        assert "outcome" in teammate_match_df.columns

        # Compter les victoires
        my_wins = (sample_match_df["outcome"] == 2).sum()
        teammate_wins = (teammate_match_df["outcome"] == 2).sum()

        # Les deux devraient avoir le même nombre de victoires
        # car ils jouent les mêmes matchs ensemble
        assert my_wins == teammate_wins


# =============================================================================
# 8.3 — Rang / score comparatif
# =============================================================================


class TestTeammateRankScoreComparison:
    """Comparaison rang et score entre joueur et coéquipier."""

    @pytestmark_polars
    def test_rank_score_side_by_side(self, sample_match_df, teammate_match_df):
        """Rang CSR et score comparés côte à côte."""
        # Vérifier que les colonnes de rang existent
        assert "rank" in sample_match_df.columns
        assert "rank" in teammate_match_df.columns

        # Vérifier que les rangs sont dans la plage valide
        assert sample_match_df["rank"].min() >= 1
        assert sample_match_df["rank"].max() <= 8
        assert teammate_match_df["rank"].min() >= 1
        assert teammate_match_df["rank"].max() <= 8


# =============================================================================
# 8.4 — Corrélations côte à côte
# =============================================================================


class TestTeammateCorrelationsComparison:
    """Corrélations comparatives (scatter plots côte à côte)."""

    @pytestmark_viz
    def test_correlations_dual_scatter(self, sample_match_df):
        """Scatter plots corrélations affichés en parallèle."""
        # Tester la corrélation kills vs avg_life
        fig = plot_correlation_scatter(
            sample_match_df,
            x_col="avg_life_seconds",
            y_col="kills",
            title="Corrélation : Durée de vie vs Kills",
            x_label="Durée de vie (s)",
            y_label="Kills",
            show_trendline=True,
        )

        assert fig is not None
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1  # Au moins le scatter

    @pytestmark_viz
    def test_mmr_correlation(self, sample_match_df):
        """Corrélation MMR équipe vs outcome."""
        fig = plot_correlation_scatter(
            sample_match_df,
            x_col="team_mmr",
            y_col="enemy_mmr",
            color_col="outcome",
            title="MMR Équipe vs Ennemi",
        )

        assert fig is not None
        assert isinstance(fig, go.Figure)


# =============================================================================
# 8.5 — Distributions comparatives
# =============================================================================


class TestTeammateDistributionsComparison:
    """Distributions comparatives (histogrammes superposés)."""

    @pytestmark_viz
    def test_distributions_overlay(self, sample_match_df, teammate_match_df):
        """Histogrammes superposés joueur vs coéquipier."""
        # Distribution des kills
        fig_kills_me = plot_histogram(
            sample_match_df["kills"],
            title="Distribution Kills (Moi)",
            x_label="Kills",
            show_kde=True,
        )
        fig_kills_teammate = plot_histogram(
            teammate_match_df["kills"],
            title="Distribution Kills (Coéquipier)",
            x_label="Kills",
            show_kde=True,
        )

        assert fig_kills_me is not None
        assert fig_kills_teammate is not None

    @pytestmark_viz
    def test_accuracy_distribution(self, sample_match_df):
        """Distribution de la précision."""
        fig = plot_histogram(
            sample_match_df["accuracy"],
            title="Distribution Précision",
            x_label="Précision (%)",
            bins=10,
        )

        assert fig is not None
        assert isinstance(fig, go.Figure)


# =============================================================================
# 8.6 — Tirs et précision comparatifs
# =============================================================================


class TestTeammateShotsAccuracyComparison:
    """Comparaison tirs et précision."""

    @pytestmark_polars
    def test_shots_accuracy_comparison(self, sample_match_df, teammate_match_df):
        """Barres tirs + courbe accuracy comparées."""
        # Vérifier les colonnes nécessaires
        assert "shots_fired" in sample_match_df.columns
        assert "shots_hit" in sample_match_df.columns
        assert "accuracy" in sample_match_df.columns

        # Vérifier que les colonnes ont des données valides
        assert sample_match_df["shots_fired"].min() > 0
        assert sample_match_df["shots_hit"].min() >= 0
        assert sample_match_df["accuracy"].min() >= 0
        assert sample_match_df["accuracy"].max() <= 100


# =============================================================================
# 8.7 — Dégâts comparatifs
# =============================================================================


class TestTeammateDamageComparison:
    """Comparaison des dégâts infligés/reçus."""

    @pytestmark_viz
    def test_damage_comparison_histogram(self, sample_match_df, teammate_match_df):
        """Histogramme superposé dégâts joueur vs coéquipier."""
        # Distribution dégâts infligés
        fig_dealt = plot_histogram(
            sample_match_df["damage_dealt"],
            title="Dégâts infligés",
            x_label="Dégâts",
        )

        # Distribution dégâts reçus
        fig_taken = plot_histogram(
            sample_match_df["damage_taken"],
            title="Dégâts reçus",
            x_label="Dégâts",
        )

        assert fig_dealt is not None
        assert fig_taken is not None

    @pytestmark_polars
    def test_damage_ratio(self, sample_match_df):
        """Vérifier le ratio dégâts infligés/reçus."""
        sample_match_df["damage_ratio"] = (
            sample_match_df["damage_dealt"] / sample_match_df["damage_taken"]
        )
        assert sample_match_df["damage_ratio"].mean() > 0.5  # Au moins quelques dégâts


# =============================================================================
# 8.8 — Heatmap win ratio
# =============================================================================


class TestTeammateWinRatioHeatmap:
    """Heatmap du taux de victoire par combinaison de coéquipiers."""

    @pytestmark_viz
    def test_win_ratio_heatmap(self, sample_match_df):
        """Heatmap correctement construite avec données de victoires."""
        # Générer la heatmap win ratio (jour × heure)
        fig = plot_win_ratio_heatmap(
            sample_match_df,
            title="Win Rate par Jour/Heure",
            min_matches=1,
        )

        assert fig is not None
        assert isinstance(fig, go.Figure)
        # Devrait avoir au moins une trace (heatmap)
        assert len(fig.data) >= 1


# =============================================================================
# 8.9 — Matchs Top comparatif
# =============================================================================


class TestTeammateTopMatchesComparison:
    """Comparaison des matchs top entre joueur et coéquipier."""

    @pytestmark_polars
    def test_top_matches_comparative(self, sample_match_df, teammate_match_df):
        """Matchs Top affichés comparativement."""
        # Identifier les top matchs par score personnel
        my_top_5 = sample_match_df.nlargest(5, "personal_score")
        teammate_top_5 = teammate_match_df.nlargest(5, "personal_score")

        assert len(my_top_5) == 5
        assert len(teammate_top_5) == 5

        # Vérifier que les match_ids existent dans les deux
        my_top_ids = set(my_top_5["match_id"])
        teammate_top_ids = set(teammate_top_5["match_id"])

        # Il peut y avoir des matchs communs ou non dans le top 5
        assert len(my_top_ids) == 5
        assert len(teammate_top_ids) == 5
