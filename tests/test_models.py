"""Tests pour les modèles de données."""

import math
from datetime import datetime, timezone

import pytest

from src.data.domain.models.stats import (
    AggregatedStats,
    FriendMatch,
    MapBreakdown,
    MatchRow,
    OutcomeRates,
)


class TestMatchRow:
    """Tests pour la classe MatchRow."""

    def test_ratio_normal(self):
        """Test du calcul de ratio avec des valeurs normales."""
        match = MatchRow(
            match_id="test-123",
            start_time=datetime.now(timezone.utc),
            map_id=None,
            map_name=None,
            playlist_id=None,
            playlist_name=None,
            map_mode_pair_id=None,
            map_mode_pair_name=None,
            outcome=2,
            last_team_id=1,
            kda=1.5,
            max_killing_spree=5,
            headshot_kills=3,
            average_life_seconds=30.0,
            time_played_seconds=600.0,
            kills=10,
            deaths=5,
            assists=4,
            accuracy=45.5,
        )
        # (10 + 4/2) / 5 = 12 / 5 = 2.4
        assert match.ratio == pytest.approx(2.4)

    def test_ratio_zero_deaths(self):
        """Test du ratio quand deaths = 0 (doit retourner NaN)."""
        match = MatchRow(
            match_id="test-456",
            start_time=datetime.now(timezone.utc),
            map_id=None,
            map_name=None,
            playlist_id=None,
            playlist_name=None,
            map_mode_pair_id=None,
            map_mode_pair_name=None,
            outcome=2,
            last_team_id=1,
            kda=None,
            max_killing_spree=None,
            headshot_kills=None,
            average_life_seconds=None,
            time_played_seconds=None,
            kills=10,
            deaths=0,
            assists=4,
            accuracy=None,
        )
        assert math.isnan(match.ratio)

    def test_is_win(self):
        """Test de la propriété is_win."""
        win_match = MatchRow(
            match_id="win",
            start_time=datetime.now(timezone.utc),
            map_id=None,
            map_name=None,
            playlist_id=None,
            playlist_name=None,
            map_mode_pair_id=None,
            map_mode_pair_name=None,
            outcome=2,
            last_team_id=1,
            kda=None,
            max_killing_spree=None,
            headshot_kills=None,
            average_life_seconds=None,
            time_played_seconds=None,
            kills=10,
            deaths=5,
            assists=4,
            accuracy=None,
        )
        loss_match = MatchRow(
            match_id="loss",
            start_time=datetime.now(timezone.utc),
            map_id=None,
            map_name=None,
            playlist_id=None,
            playlist_name=None,
            map_mode_pair_id=None,
            map_mode_pair_name=None,
            outcome=3,
            last_team_id=1,
            kda=None,
            max_killing_spree=None,
            headshot_kills=None,
            average_life_seconds=None,
            time_played_seconds=None,
            kills=5,
            deaths=10,
            assists=2,
            accuracy=None,
        )

        assert win_match.is_win is True
        assert win_match.is_loss is False
        assert loss_match.is_win is False
        assert loss_match.is_loss is True


class TestAggregatedStats:
    """Tests pour la classe AggregatedStats."""

    def test_global_ratio(self):
        """Test du calcul du ratio global."""
        stats = AggregatedStats(
            total_kills=100,
            total_deaths=50,
            total_assists=40,
            total_matches=10,
            total_time_seconds=6000.0,
        )
        # (100 + 40/2) / 50 = 120 / 50 = 2.4
        assert stats.global_ratio == pytest.approx(2.4)

    def test_global_ratio_zero_deaths(self):
        """Test du ratio global avec 0 deaths."""
        stats = AggregatedStats(
            total_kills=100,
            total_deaths=0,
            total_assists=40,
            total_matches=10,
            total_time_seconds=6000.0,
        )
        assert stats.global_ratio is None

    def test_per_match_stats(self):
        """Test des moyennes par match."""
        stats = AggregatedStats(
            total_kills=100,
            total_deaths=50,
            total_assists=40,
            total_matches=10,
            total_time_seconds=6000.0,
        )
        assert stats.kills_per_match == 10.0
        assert stats.deaths_per_match == 5.0
        assert stats.assists_per_match == 4.0

    def test_per_minute_stats(self):
        """Test des stats par minute."""
        stats = AggregatedStats(
            total_kills=100,
            total_deaths=50,
            total_assists=40,
            total_matches=10,
            total_time_seconds=6000.0,  # 100 minutes
        )
        assert stats.kills_per_minute == 1.0
        assert stats.deaths_per_minute == 0.5
        assert stats.assists_per_minute == 0.4

    def test_empty_stats(self):
        """Test avec des stats vides."""
        stats = AggregatedStats()
        assert stats.global_ratio is None
        assert stats.kills_per_match is None
        assert stats.kills_per_minute is None


class TestOutcomeRates:
    """Tests pour la classe OutcomeRates."""

    def test_win_rate(self):
        """Test du calcul du taux de victoire."""
        rates = OutcomeRates(wins=6, losses=3, ties=1, no_finish=0, total=10)
        assert rates.win_rate == 0.6
        assert rates.loss_rate == 0.3

    def test_rates_zero_total(self):
        """Test avec aucun match."""
        rates = OutcomeRates(wins=0, losses=0, ties=0, no_finish=0, total=0)
        assert rates.win_rate is None
        assert rates.loss_rate is None


class TestFriendMatch:
    """Tests pour la classe FriendMatch."""

    def test_creation(self):
        """Test de création d'un FriendMatch."""
        fm = FriendMatch(
            match_id="test-123",
            start_time=datetime.now(timezone.utc),
            playlist_id="pl-1",
            playlist_name="Quick Play",
            pair_id="pair-1",
            pair_name="Slayer on Streets",
            my_team_id=1,
            my_outcome=2,
            friend_team_id=1,
            friend_outcome=2,
            same_team=True,
        )
        assert fm.match_id == "test-123"
        assert fm.same_team is True


class TestMapBreakdown:
    """Tests pour la classe MapBreakdown."""

    def test_creation(self):
        """Test de création d'un MapBreakdown."""
        mb = MapBreakdown(
            map_name="Streets",
            matches=50,
            accuracy_avg=45.5,
            win_rate=0.6,
            loss_rate=0.35,
            ratio_global=1.8,
        )
        assert mb.map_name == "Streets"
        assert mb.matches == 50
        assert mb.win_rate == 0.6
