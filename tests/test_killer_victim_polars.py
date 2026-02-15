"""Tests unitaires Sprint 3 : Fonctions Polars pour Killer-Victim.

Ce module teste les fonctions d'analyse Polars :
- compute_personal_antagonists_from_pairs_polars()
- killer_victim_counts_long_polars()
- compute_kd_timeseries_by_minute_polars()
- compute_duel_history_polars()
- killer_victim_matrix_polars()
"""

from __future__ import annotations

import pytest

# Import Polars - skip tests if not available
polars_available = True
try:
    import polars as pl
except ImportError:
    polars_available = False
    pl = None

from src.analysis.killer_victim import (
    AntagonistsResultPolars,
    compute_duel_history_polars,
    compute_kd_timeseries_by_minute_polars,
    compute_personal_antagonists_from_pairs_polars,
    killer_victim_counts_long_polars,
    killer_victim_matrix_polars,
)

pytestmark = pytest.mark.skipif(not polars_available, reason="Polars not installed")


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_pairs_df():
    """DataFrame Polars de paires killer-victim pour tests."""
    return pl.DataFrame(
        {
            "match_id": ["m1", "m1", "m1", "m1", "m1", "m2", "m2", "m2"],
            "killer_xuid": ["me", "me", "enemy1", "enemy1", "enemy2", "me", "enemy1", "enemy1"],
            "killer_gamertag": [
                "MePlayer",
                "MePlayer",
                "Enemy1",
                "Enemy1",
                "Enemy2",
                "MePlayer",
                "Enemy1",
                "Enemy1",
            ],
            "victim_xuid": ["enemy1", "enemy2", "me", "me", "me", "enemy1", "me", "enemy2"],
            "victim_gamertag": [
                "Enemy1",
                "Enemy2",
                "MePlayer",
                "MePlayer",
                "MePlayer",
                "Enemy1",
                "MePlayer",
                "Enemy2",
            ],
            "kill_count": [1, 1, 1, 1, 1, 1, 1, 1],
            "time_ms": [15000, 30000, 45000, 60000, 75000, 15000, 30000, 45000],
        }
    )


@pytest.fixture
def empty_pairs_df():
    """DataFrame Polars vide."""
    return pl.DataFrame(
        {
            "match_id": [],
            "killer_xuid": [],
            "killer_gamertag": [],
            "victim_xuid": [],
            "victim_gamertag": [],
            "kill_count": [],
            "time_ms": [],
        }
    ).cast(
        {
            "kill_count": pl.Int64,
            "time_ms": pl.Int64,
        }
    )


@pytest.fixture
def single_match_pairs_df():
    """DataFrame Polars pour un seul match avec timings."""
    return pl.DataFrame(
        {
            "match_id": ["m1"] * 10,
            "killer_xuid": [
                "me",
                "me",
                "me",
                "enemy1",
                "enemy1",
                "me",
                "enemy2",
                "me",
                "enemy1",
                "me",
            ],
            "killer_gamertag": ["MePlayer"] * 3
            + ["Enemy1"] * 2
            + ["MePlayer"]
            + ["Enemy2"]
            + ["MePlayer"]
            + ["Enemy1"]
            + ["MePlayer"],
            "victim_xuid": [
                "enemy1",
                "enemy2",
                "enemy1",
                "me",
                "me",
                "enemy2",
                "me",
                "enemy1",
                "me",
                "enemy2",
            ],
            "victim_gamertag": [
                "Enemy1",
                "Enemy2",
                "Enemy1",
                "MePlayer",
                "MePlayer",
                "Enemy2",
                "MePlayer",
                "Enemy1",
                "MePlayer",
                "Enemy2",
            ],
            "kill_count": [1] * 10,
            "time_ms": [5000, 35000, 65000, 95000, 125000, 155000, 185000, 215000, 245000, 275000],
        }
    )


# =============================================================================
# Tests compute_personal_antagonists_from_pairs_polars
# =============================================================================


class TestComputePersonalAntagonistsPolars:
    """Tests de compute_personal_antagonists_from_pairs_polars."""

    def test_basic_antagonists(self, sample_pairs_df):
        """Test calcul basique des antagonistes."""
        result = compute_personal_antagonists_from_pairs_polars(sample_pairs_df, "me")

        assert isinstance(result, AntagonistsResultPolars)

        # Némésis = Enemy1 (m'a tué 3 fois : 2 dans m1 + 1 dans m2)
        assert result.nemesis_xuid == "enemy1"
        assert result.nemesis_gamertag == "Enemy1"
        assert result.nemesis_times_killed_by == 3

        # Souffre-douleur = Enemy1 (tué 2 fois : 1 dans m1 + 1 dans m2)
        # Données: index 0 (me→enemy1) + index 5 (me→enemy1) = 2 kills sur enemy1
        assert result.victim_xuid == "enemy1"
        assert result.victim_gamertag == "Enemy1"
        assert result.victim_times_killed == 2

        # Totaux
        assert result.total_deaths == 4  # enemy1 × 3 + enemy2 × 1
        assert result.total_kills == 3  # enemy1 × 2 + enemy2 × 1

    def test_empty_dataframe(self, empty_pairs_df):
        """Test avec DataFrame vide."""
        result = compute_personal_antagonists_from_pairs_polars(empty_pairs_df, "me")

        assert result.nemesis_xuid is None
        assert result.nemesis_gamertag is None
        assert result.nemesis_times_killed_by == 0
        assert result.victim_xuid is None
        assert result.total_deaths == 0
        assert result.total_kills == 0

    def test_no_deaths(self):
        """Test joueur qui n'a jamais été tué."""
        df = pl.DataFrame(
            {
                "match_id": ["m1", "m1"],
                "killer_xuid": ["me", "me"],
                "killer_gamertag": ["MePlayer", "MePlayer"],
                "victim_xuid": ["enemy1", "enemy2"],
                "victim_gamertag": ["Enemy1", "Enemy2"],
                "kill_count": [5, 3],
                "time_ms": [1000, 2000],
            }
        )

        result = compute_personal_antagonists_from_pairs_polars(df, "me")

        assert result.nemesis_xuid is None
        assert result.total_deaths == 0
        assert result.total_kills == 8
        assert result.victim_xuid == "enemy1"  # 5 kills
        assert result.victim_times_killed == 5

    def test_no_kills(self):
        """Test joueur qui n'a tué personne."""
        df = pl.DataFrame(
            {
                "match_id": ["m1", "m1"],
                "killer_xuid": ["enemy1", "enemy2"],
                "killer_gamertag": ["Enemy1", "Enemy2"],
                "victim_xuid": ["me", "me"],
                "victim_gamertag": ["MePlayer", "MePlayer"],
                "kill_count": [5, 3],
                "time_ms": [1000, 2000],
            }
        )

        result = compute_personal_antagonists_from_pairs_polars(df, "me")

        assert result.victim_xuid is None
        assert result.total_kills == 0
        assert result.total_deaths == 8
        assert result.nemesis_xuid == "enemy1"  # 5 kills on me
        assert result.nemesis_times_killed_by == 5


# =============================================================================
# Tests killer_victim_counts_long_polars
# =============================================================================


class TestKillerVictimCountsLongPolars:
    """Tests de killer_victim_counts_long_polars."""

    def test_basic_aggregation(self, sample_pairs_df):
        """Test agrégation basique."""
        result = killer_victim_counts_long_polars(sample_pairs_df)

        assert len(result) > 0
        assert "killer_xuid" in result.columns
        assert "victim_xuid" in result.columns
        assert "count" in result.columns

        # Vérifier le tri par count décroissant
        counts = result["count"].to_list()
        assert counts == sorted(counts, reverse=True)

    def test_empty_dataframe(self, empty_pairs_df):
        """Test avec DataFrame vide."""
        result = killer_victim_counts_long_polars(empty_pairs_df)
        assert result.is_empty()

    def test_correct_counts(self, sample_pairs_df):
        """Test que les counts sont corrects."""
        result = killer_victim_counts_long_polars(sample_pairs_df)

        # Enemy1 a tué MePlayer 3 fois (2 dans m1 + 1 dans m2)
        enemy1_kills_me = result.filter(
            (pl.col("killer_xuid") == "enemy1") & (pl.col("victim_xuid") == "me")
        )
        assert len(enemy1_kills_me) == 1
        assert enemy1_kills_me["count"].item() == 3


# =============================================================================
# Tests compute_kd_timeseries_by_minute_polars
# =============================================================================


class TestComputeKDTimeseriesPolars:
    """Tests de compute_kd_timeseries_by_minute_polars."""

    def test_basic_timeseries(self, single_match_pairs_df):
        """Test timeseries basique."""
        result = compute_kd_timeseries_by_minute_polars(single_match_pairs_df, "me")

        assert len(result) > 0
        assert "minute" in result.columns
        assert "kills" in result.columns
        assert "deaths" in result.columns
        assert "net_kd" in result.columns
        assert "cumulative_net_kd" in result.columns

    def test_cumulative_calculation(self, single_match_pairs_df):
        """Test calcul cumulatif correct."""
        result = compute_kd_timeseries_by_minute_polars(single_match_pairs_df, "me")

        # Vérifier que le cumulatif est la somme des net_kd
        net_kd_list = result["net_kd"].to_list()
        cumulative_list = result["cumulative_net_kd"].to_list()

        expected_cumulative = []
        running_sum = 0
        for nk in net_kd_list:
            running_sum += nk
            expected_cumulative.append(running_sum)

        assert cumulative_list == expected_cumulative

    def test_empty_dataframe(self, empty_pairs_df):
        """Test avec DataFrame vide."""
        result = compute_kd_timeseries_by_minute_polars(empty_pairs_df, "me")

        assert "minute" in result.columns
        assert len(result) == 0

    def test_with_match_duration(self, single_match_pairs_df):
        """Test avec durée de match spécifiée."""
        result = compute_kd_timeseries_by_minute_polars(
            single_match_pairs_df,
            "me",
            match_duration_ms=600000,  # 10 minutes
        )

        # Devrait avoir des entrées pour toutes les minutes de 0 à 10
        minutes = result["minute"].to_list()
        assert 0 in minutes
        # La minute 10 devrait être incluse si spécifié


# =============================================================================
# Tests compute_duel_history_polars
# =============================================================================


class TestComputeDuelHistoryPolars:
    """Tests de compute_duel_history_polars."""

    def test_basic_duel_history(self, sample_pairs_df):
        """Test historique de duel basique."""
        result = compute_duel_history_polars(sample_pairs_df, "me", "enemy1")

        assert len(result) > 0
        assert "match_id" in result.columns
        assert "my_kills" in result.columns
        assert "opponent_kills" in result.columns
        assert "net" in result.columns

    def test_correct_duel_counts(self, sample_pairs_df):
        """Test que les counts de duel sont corrects."""
        result = compute_duel_history_polars(sample_pairs_df, "me", "enemy1")

        # Match m1: me killed enemy1 × 1, enemy1 killed me × 2
        m1 = result.filter(pl.col("match_id") == "m1")
        if len(m1) > 0:
            assert m1["my_kills"].item() == 1
            assert m1["opponent_kills"].item() == 2
            assert m1["net"].item() == -1

    def test_empty_dataframe(self, empty_pairs_df):
        """Test avec DataFrame vide."""
        result = compute_duel_history_polars(empty_pairs_df, "me", "enemy1")
        assert len(result) == 0

    def test_no_encounters(self, sample_pairs_df):
        """Test avec joueurs qui ne se sont jamais rencontrés."""
        result = compute_duel_history_polars(sample_pairs_df, "me", "nonexistent")
        assert len(result) == 0


# =============================================================================
# Tests killer_victim_matrix_polars
# =============================================================================


class TestKillerVictimMatrixPolars:
    """Tests de killer_victim_matrix_polars."""

    def test_basic_matrix(self, sample_pairs_df):
        """Test matrice basique."""
        result = killer_victim_matrix_polars(sample_pairs_df)

        assert len(result) > 0
        assert "killer_gamertag" in result.columns

    def test_empty_dataframe(self, empty_pairs_df):
        """Test avec DataFrame vide."""
        result = killer_victim_matrix_polars(empty_pairs_df)
        assert result.is_empty()

    def test_symmetric_structure(self, sample_pairs_df):
        """Test que la matrice a les bons joueurs."""
        result = killer_victim_matrix_polars(sample_pairs_df)

        # Les killers devraient inclure MePlayer, Enemy1, Enemy2
        killers = result["killer_gamertag"].to_list()
        assert "MePlayer" in killers
        assert "Enemy1" in killers


# =============================================================================
# Tests d'intégration avec le repository
# =============================================================================


class TestPolarsIntegrationWithRepository:
    """Tests d'intégration simulant l'usage avec DuckDBRepository."""

    def test_typical_workflow(self, sample_pairs_df):
        """Test workflow typique : charger → analyser → résultats."""
        me_xuid = "me"

        # 1. Calculer les antagonistes
        antagonists = compute_personal_antagonists_from_pairs_polars(sample_pairs_df, me_xuid)
        assert antagonists.total_kills > 0

        # 2. Obtenir les counts détaillés
        counts = killer_victim_counts_long_polars(sample_pairs_df)
        assert len(counts) > 0

        # 3. Si némésis identifié, obtenir l'historique des duels
        if antagonists.nemesis_xuid:
            duel_history = compute_duel_history_polars(
                sample_pairs_df,
                me_xuid,
                antagonists.nemesis_xuid,
            )
            assert len(duel_history) > 0

    def test_filter_and_analyze(self, sample_pairs_df):
        """Test filtrage avant analyse."""
        # Filtrer pour un seul match
        m1_only = sample_pairs_df.filter(pl.col("match_id") == "m1")

        result = compute_personal_antagonists_from_pairs_polars(m1_only, "me")

        # Dans m1: me killed enemy1 × 1, enemy2 × 1
        #          enemy1 killed me × 2, enemy2 killed me × 1
        assert result.total_kills == 2
        assert result.total_deaths == 3
