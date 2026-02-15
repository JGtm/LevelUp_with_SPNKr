"""Tests unitaires pour src/analysis/objective_participation.py.

Sprint 4 - Tests des fonctions d'analyse de participation aux objectifs.
"""

from __future__ import annotations

import pytest

# Vérifier si Polars est disponible
try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False

from src.data.domain.refdata import (
    PersonalScoreNameId,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_awards_df():
    """DataFrame Polars avec des données d'awards de test."""
    if not POLARS_AVAILABLE:
        pytest.skip("Polars non disponible")

    return pl.DataFrame(
        {
            "match_id": [
                "match1",
                "match1",
                "match1",
                "match1",
                "match2",
                "match2",
                "match2",
                "match3",
                "match3",
            ],
            "xuid": [
                "xuid1",
                "xuid1",
                "xuid1",
                "xuid1",
                "xuid1",
                "xuid1",
                "xuid2",
                "xuid2",
                "xuid2",
            ],
            "award_name_id": [
                int(PersonalScoreNameId.KILLED_PLAYER),  # 100 pts - kill
                int(PersonalScoreNameId.KILL_ASSIST),  # 50 pts - assist
                int(PersonalScoreNameId.FLAG_CAPTURED),  # 300 pts - objective
                int(PersonalScoreNameId.MARK_ASSIST),  # 10 pts - assist
                int(PersonalScoreNameId.ZONE_CAPTURED_100),  # 100 pts - objective
                int(PersonalScoreNameId.ELIMINATED_PLAYER),  # 200 pts - kill
                int(PersonalScoreNameId.HILL_SCORED),  # 100 pts - objective
                int(PersonalScoreNameId.BALL_CONTROL),  # 50 pts - objective
                int(PersonalScoreNameId.DRIVER_ASSIST),  # 50 pts - assist
            ],
            "count": [5, 3, 2, 4, 1, 2, 3, 10, 2],
            "total_points": [500, 150, 600, 40, 100, 400, 300, 500, 100],
        }
    )


@pytest.fixture
def empty_awards_df():
    """DataFrame Polars vide."""
    if not POLARS_AVAILABLE:
        pytest.skip("Polars non disponible")

    return pl.DataFrame(
        {
            "match_id": [],
            "xuid": [],
            "award_name_id": [],
            "count": [],
            "total_points": [],
        }
    )


@pytest.fixture
def assist_only_df():
    """DataFrame avec uniquement des assistances."""
    if not POLARS_AVAILABLE:
        pytest.skip("Polars non disponible")

    return pl.DataFrame(
        {
            "match_id": ["match1"] * 4,
            "xuid": ["xuid1"] * 4,
            "award_name_id": [
                int(PersonalScoreNameId.KILL_ASSIST),  # 50 pts
                int(PersonalScoreNameId.MARK_ASSIST),  # 10 pts
                int(PersonalScoreNameId.EMP_ASSIST),  # 50 pts
                int(PersonalScoreNameId.DRIVER_ASSIST),  # 50 pts
            ],
            "count": [5, 10, 2, 3],
            "total_points": [250, 100, 100, 150],
        }
    )


# =============================================================================
# Tests compute_objective_participation_score_polars
# =============================================================================


@pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non disponible")
class TestComputeObjectiveParticipationScore:
    """Tests pour compute_objective_participation_score_polars."""

    def test_basic_calculation(self, sample_awards_df):
        """Teste le calcul basique de participation."""
        from src.analysis.objective_participation import (
            compute_objective_participation_score_polars,
        )

        result = compute_objective_participation_score_polars(sample_awards_df)

        # Vérifier que les totaux sont calculés
        assert result.total_score > 0
        assert result.objective_score >= 0
        assert result.assist_score >= 0
        assert result.kill_score >= 0

    def test_filter_by_match(self, sample_awards_df):
        """Teste le filtrage par match."""
        from src.analysis.objective_participation import (
            compute_objective_participation_score_polars,
        )

        result = compute_objective_participation_score_polars(
            sample_awards_df,
            match_id="match1",
        )

        assert result.match_id == "match1"
        # match1 contient : KILLED_PLAYER(500), KILL_ASSIST(150),
        # FLAG_CAPTURED(600), MARK_ASSIST(40) = 1290 total
        assert result.total_score == 1290

    def test_filter_by_xuid(self, sample_awards_df):
        """Teste le filtrage par joueur."""
        from src.analysis.objective_participation import (
            compute_objective_participation_score_polars,
        )

        result = compute_objective_participation_score_polars(
            sample_awards_df,
            xuid="xuid2",
        )

        assert result.xuid == "xuid2"
        # xuid2 a : HILL_SCORED(300), BALL_CONTROL(500), DRIVER_ASSIST(100) = 900 total
        assert result.total_score == 900

    def test_empty_dataframe(self, empty_awards_df):
        """Teste avec un DataFrame vide."""
        from src.analysis.objective_participation import (
            compute_objective_participation_score_polars,
        )

        result = compute_objective_participation_score_polars(empty_awards_df)

        assert result.total_score == 0
        assert result.objective_score == 0
        assert result.objective_ratio == 0.0

    def test_ratios_calculation(self, sample_awards_df):
        """Teste le calcul des ratios."""
        from src.analysis.objective_participation import (
            compute_objective_participation_score_polars,
        )

        result = compute_objective_participation_score_polars(
            sample_awards_df,
            match_id="match1",
            xuid="xuid1",
        )

        # Vérifier que les ratios sont entre 0 et 1
        assert 0 <= result.objective_ratio <= 1
        assert 0 <= result.assist_ratio <= 1

    def test_counts_tracked(self, sample_awards_df):
        """Teste que les counts sont bien tracés."""
        from src.analysis.objective_participation import (
            compute_objective_participation_score_polars,
        )

        result = compute_objective_participation_score_polars(
            sample_awards_df,
            match_id="match1",
            xuid="xuid1",
        )

        # match1/xuid1 : 5 kills, 7 assists (3+4), 2 flags
        assert result.kill_count == 5
        assert result.assist_count == 7
        assert result.objective_count == 2


# =============================================================================
# Tests rank_players_by_objective_contribution_polars
# =============================================================================


@pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non disponible")
class TestRankPlayersByObjectiveContribution:
    """Tests pour rank_players_by_objective_contribution_polars."""

    def test_basic_ranking(self, sample_awards_df):
        """Teste le classement basique des joueurs."""
        from src.analysis.objective_participation import (
            rank_players_by_objective_contribution_polars,
        )

        results = rank_players_by_objective_contribution_polars(sample_awards_df)

        # Vérifier que des joueurs sont retournés
        assert len(results) > 0

        # Vérifier que les résultats sont triés par contribution moyenne
        for i in range(len(results) - 1):
            assert results[i].avg_objective_per_match >= results[i + 1].avg_objective_per_match

    def test_filter_by_match_ids(self, sample_awards_df):
        """Teste le filtrage par liste de matchs."""
        from src.analysis.objective_participation import (
            rank_players_by_objective_contribution_polars,
        )

        results = rank_players_by_objective_contribution_polars(
            sample_awards_df,
            match_ids=["match1"],
        )

        # Seul xuid1 a des données dans match1
        assert len(results) >= 1

    def test_top_n_limit(self, sample_awards_df):
        """Teste la limite top_n."""
        from src.analysis.objective_participation import (
            rank_players_by_objective_contribution_polars,
        )

        results = rank_players_by_objective_contribution_polars(
            sample_awards_df,
            top_n=1,
        )

        assert len(results) <= 1

    def test_min_matches_filter(self, sample_awards_df):
        """Teste le filtre de matchs minimum."""
        from src.analysis.objective_participation import (
            rank_players_by_objective_contribution_polars,
        )

        # Avec min_matches=3, seul xuid1 devrait être retourné (a 2 matchs)
        results = rank_players_by_objective_contribution_polars(
            sample_awards_df,
            min_matches=3,
        )

        # Aucun joueur n'a 3+ matchs dans les données de test
        assert len(results) == 0

    def test_empty_dataframe(self, empty_awards_df):
        """Teste avec un DataFrame vide."""
        from src.analysis.objective_participation import (
            rank_players_by_objective_contribution_polars,
        )

        results = rank_players_by_objective_contribution_polars(empty_awards_df)

        assert len(results) == 0


# =============================================================================
# Tests compute_assist_breakdown_polars
# =============================================================================


@pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non disponible")
class TestComputeAssistBreakdown:
    """Tests pour compute_assist_breakdown_polars."""

    def test_basic_breakdown(self, assist_only_df):
        """Teste la décomposition basique des assistances."""
        from src.analysis.objective_participation import (
            compute_assist_breakdown_polars,
        )

        result = compute_assist_breakdown_polars(assist_only_df)

        # Vérifier les counts
        assert result.kill_assists == 5
        assert result.mark_assists == 10
        assert result.emp_assists == 2
        assert result.driver_assists == 3
        assert result.total_assists == 20
        assert result.total_assist_points == 600  # 250+100+100+150

    def test_high_value_ratio(self, assist_only_df):
        """Teste le calcul du ratio haute valeur."""
        from src.analysis.objective_participation import (
            compute_assist_breakdown_polars,
        )

        result = compute_assist_breakdown_polars(assist_only_df)

        # High value = kill + emp + driver + flag = 5 + 2 + 3 + 0 = 10
        # Total = 20
        # Ratio = 10/20 = 0.5
        assert result.high_value_ratio == 0.5

    def test_empty_dataframe(self, empty_awards_df):
        """Teste avec un DataFrame vide."""
        from src.analysis.objective_participation import (
            compute_assist_breakdown_polars,
        )

        result = compute_assist_breakdown_polars(empty_awards_df)

        assert result.total_assists == 0
        assert result.high_value_ratio == 0.0

    def test_filter_by_match_and_xuid(self, assist_only_df):
        """Teste le filtrage combiné."""
        from src.analysis.objective_participation import (
            compute_assist_breakdown_polars,
        )

        result = compute_assist_breakdown_polars(
            assist_only_df,
            match_id="match1",
            xuid="xuid1",
        )

        # Toutes les données de test sont pour match1/xuid1
        assert result.total_assists == 20


# =============================================================================
# Tests compute_objective_summary_by_match_polars
# =============================================================================


@pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non disponible")
class TestComputeObjectiveSummaryByMatch:
    """Tests pour compute_objective_summary_by_match_polars."""

    def test_basic_summary(self, sample_awards_df):
        """Teste le résumé basique par match."""
        from src.analysis.objective_participation import (
            compute_objective_summary_by_match_polars,
        )

        result = compute_objective_summary_by_match_polars(sample_awards_df)

        # Vérifier les colonnes
        assert "match_id" in result.columns
        assert "objective_score" in result.columns
        assert "assist_score" in result.columns
        assert "total_score" in result.columns
        assert "objective_ratio" in result.columns

        # Vérifier qu'on a des lignes
        assert len(result) > 0

    def test_filter_by_xuid(self, sample_awards_df):
        """Teste le filtrage par joueur."""
        from src.analysis.objective_participation import (
            compute_objective_summary_by_match_polars,
        )

        result = compute_objective_summary_by_match_polars(
            sample_awards_df,
            xuid="xuid1",
        )

        # xuid1 a des données dans match1 et match2
        match_ids = result["match_id"].to_list()
        assert "match1" in match_ids
        assert "match2" in match_ids

    def test_empty_dataframe(self, empty_awards_df):
        """Teste avec un DataFrame vide."""
        from src.analysis.objective_participation import (
            compute_objective_summary_by_match_polars,
        )

        result = compute_objective_summary_by_match_polars(empty_awards_df)

        assert len(result) == 0


# =============================================================================
# Tests compute_award_frequency_polars
# =============================================================================


@pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non disponible")
class TestComputeAwardFrequency:
    """Tests pour compute_award_frequency_polars."""

    def test_all_awards_frequency(self, sample_awards_df):
        """Teste la fréquence de tous les awards."""
        from src.analysis.objective_participation import (
            compute_award_frequency_polars,
        )

        result = compute_award_frequency_polars(sample_awards_df)

        # Vérifier les colonnes
        assert "award_name_id" in result.columns
        assert "display_name" in result.columns
        assert "count" in result.columns
        assert "total_points" in result.columns

    def test_filter_by_category(self, sample_awards_df):
        """Teste le filtrage par catégorie."""
        from src.analysis.objective_participation import (
            compute_award_frequency_polars,
        )

        # Objectifs seulement
        obj_result = compute_award_frequency_polars(
            sample_awards_df,
            category="objective",
        )

        # Vérifier que tous les awards sont des objectifs
        from src.data.domain.refdata import OBJECTIVE_SCORES

        for award_id in obj_result["award_name_id"].to_list():
            assert award_id in OBJECTIVE_SCORES

    def test_top_n_limit(self, sample_awards_df):
        """Teste la limite top_n."""
        from src.analysis.objective_participation import (
            compute_award_frequency_polars,
        )

        result = compute_award_frequency_polars(
            sample_awards_df,
            top_n=3,
        )

        assert len(result) <= 3

    def test_empty_dataframe(self, empty_awards_df):
        """Teste avec un DataFrame vide."""
        from src.analysis.objective_participation import (
            compute_award_frequency_polars,
        )

        result = compute_award_frequency_polars(empty_awards_df)

        assert len(result) == 0


# =============================================================================
# Tests fonctions utilitaires
# =============================================================================


class TestUtilityFunctions:
    """Tests pour les fonctions utilitaires."""

    def test_get_objective_mode_awards(self):
        """Teste la récupération des awards objectifs."""
        from src.analysis.objective_participation import (
            get_objective_mode_awards,
        )

        awards = get_objective_mode_awards()

        # Vérifier que c'est un dict non vide
        assert isinstance(awards, dict)
        assert len(awards) > 0

        # Vérifier la structure
        for award_id, name in awards.items():
            assert isinstance(award_id, int)
            assert isinstance(name, str)

    def test_get_assist_awards_with_points(self):
        """Teste la récupération des awards d'assistance avec points."""
        from src.analysis.objective_participation import (
            get_assist_awards_with_points,
        )

        awards = get_assist_awards_with_points()

        # Vérifier que c'est un dict non vide
        assert isinstance(awards, dict)
        assert len(awards) > 0

        # Vérifier la structure
        for award_id, (name, points) in awards.items():
            assert isinstance(award_id, int)
            assert isinstance(name, str)
            assert isinstance(points, int)

    def test_is_objective_mode_match(self):
        """Teste la détection de mode objectif."""
        from src.analysis.objective_participation import (
            is_objective_mode_match,
        )
        from src.data.domain.refdata import GameVariantCategory

        # CTF est un mode objectif
        assert is_objective_mode_match(GameVariantCategory.MULTIPLAYER_CTF) is True

        # Slayer n'est pas un mode objectif
        assert is_objective_mode_match(GameVariantCategory.MULTIPLAYER_SLAYER) is False


# =============================================================================
# Tests d'intégration avec le repository
# =============================================================================


@pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars non disponible")
class TestIntegrationWithRepository:
    """Tests d'intégration (mock) avec le repository."""

    def test_complete_analysis_flow(self, sample_awards_df):
        """Teste un flux d'analyse complet."""
        from src.analysis.objective_participation import (
            compute_assist_breakdown_polars,
            compute_award_frequency_polars,
            compute_objective_participation_score_polars,
            compute_objective_summary_by_match_polars,
            rank_players_by_objective_contribution_polars,
        )

        # 1. Calculer la participation globale
        global_result = compute_objective_participation_score_polars(sample_awards_df)
        assert global_result.total_score > 0

        # 2. Classer les joueurs
        rankings = rank_players_by_objective_contribution_polars(sample_awards_df)
        assert len(rankings) > 0

        # 3. Décomposer les assistances pour le top joueur
        if rankings:
            top_player_xuid = rankings[0].xuid
            assists = compute_assist_breakdown_polars(
                sample_awards_df,
                xuid=top_player_xuid,
            )
            assert assists.total_assists >= 0

        # 4. Résumé par match
        match_summary = compute_objective_summary_by_match_polars(sample_awards_df)
        assert len(match_summary) > 0

        # 5. Fréquence des awards
        frequency = compute_award_frequency_polars(sample_awards_df)
        assert len(frequency) > 0
