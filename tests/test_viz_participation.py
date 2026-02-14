"""Tests pour src/visualization/participation_charts.py et participation_radar.py — Sprint 7ter (7t.3).

Couvre les fonctions de visualisation de participation (Plotly pur).
"""

from __future__ import annotations

import plotly.graph_objects as go
import polars as pl
import pytest

from src.visualization.participation_charts import (
    CATEGORY_COLORS,
    aggregate_participation_for_radar,
    compute_participation_percentages,
    create_participation_indicator,
    get_participation_colors,
    plot_participation_bars,
    plot_participation_by_match,
    plot_participation_pie,
    plot_participation_sunburst,
)
from src.visualization.participation_radar import (
    RADAR_AXIS_LINES,
    RADAR_THRESHOLDS,
    _extract_scores_from_awards,
    _get_match_stats_values,
    _is_objective_mode_from_pair_name,
    compute_participation_profile,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def awards_df() -> pl.DataFrame:
    """DataFrame de PersonalScores typique."""
    return pl.DataFrame(
        {
            "award_category": ["kill", "kill", "assist", "objective", "vehicle", "penalty"],
            "award_name": ["Kill", "HeadShot", "Assist", "Flag Capture", "Vehicle Kill", "Suicide"],
            "award_count": [10, 5, 8, 3, 2, 1],
            "award_score": [1000, 500, 400, 600, 200, -100],
        }
    )


@pytest.fixture
def awards_df_per_match() -> pl.DataFrame:
    """DataFrame avec match_id pour tests par match."""
    return pl.DataFrame(
        {
            "match_id": ["m1", "m1", "m1", "m2", "m2", "m3"],
            "award_category": ["kill", "assist", "objective", "kill", "assist", "kill"],
            "award_name": ["Kill", "Assist", "Flag", "Kill", "Assist", "Kill"],
            "award_count": [5, 3, 1, 8, 2, 3],
            "award_score": [500, 150, 200, 800, 100, 300],
        }
    )


@pytest.fixture
def empty_awards_df() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "award_category": pl.Utf8,
            "award_name": pl.Utf8,
            "award_count": pl.Int64,
            "award_score": pl.Int64,
        }
    )


# ============================================================================
# participation_charts.py
# ============================================================================


class TestGetParticipationColors:
    def test_returns_dict(self):
        colors = get_participation_colors()
        assert isinstance(colors, dict)

    def test_all_categories_present(self):
        colors = get_participation_colors()
        for cat in ("kill", "assist", "objective", "vehicle", "penalty", "other"):
            assert cat in colors

    def test_returns_copy(self):
        colors = get_participation_colors()
        colors["kill"] = "black"
        assert CATEGORY_COLORS["kill"] != "black"


class TestPlotParticipationPie:
    def test_returns_figure(self, awards_df):
        fig = plot_participation_pie(awards_df)
        assert isinstance(fig, go.Figure)

    def test_empty_df(self, empty_awards_df):
        fig = plot_participation_pie(empty_awards_df)
        assert isinstance(fig, go.Figure)

    def test_custom_title(self, awards_df):
        fig = plot_participation_pie(awards_df, title="Test Title")
        assert isinstance(fig, go.Figure)

    def test_no_values(self, awards_df):
        fig = plot_participation_pie(awards_df, show_values=False)
        assert isinstance(fig, go.Figure)


class TestPlotParticipationBars:
    def test_returns_figure(self, awards_df):
        fig = plot_participation_bars(awards_df)
        assert isinstance(fig, go.Figure)

    def test_empty_df(self, empty_awards_df):
        fig = plot_participation_bars(empty_awards_df)
        assert isinstance(fig, go.Figure)

    def test_vertical(self, awards_df):
        fig = plot_participation_bars(awards_df, orientation="v")
        assert isinstance(fig, go.Figure)

    def test_top_n(self, awards_df):
        fig = plot_participation_bars(awards_df, top_n=2)
        assert isinstance(fig, go.Figure)


class TestPlotParticipationByMatch:
    def test_returns_figure(self, awards_df_per_match):
        fig = plot_participation_by_match(awards_df_per_match)
        assert isinstance(fig, go.Figure)

    def test_last_n(self, awards_df_per_match):
        fig = plot_participation_by_match(awards_df_per_match, last_n=2)
        assert isinstance(fig, go.Figure)


class TestCreateParticipationIndicator:
    def test_returns_figure(self, awards_df):
        fig = create_participation_indicator(awards_df)
        assert isinstance(fig, go.Figure)

    def test_has_4_traces(self, awards_df):
        fig = create_participation_indicator(awards_df)
        assert len(fig.data) == 4

    def test_empty_df(self, empty_awards_df):
        fig = create_participation_indicator(empty_awards_df)
        assert isinstance(fig, go.Figure)


class TestPlotParticipationSunburst:
    def test_returns_figure(self, awards_df):
        fig = plot_participation_sunburst(awards_df)
        assert isinstance(fig, go.Figure)

    def test_empty_df(self, empty_awards_df):
        fig = plot_participation_sunburst(empty_awards_df)
        assert isinstance(fig, go.Figure)

    def test_all_negative_scores(self):
        df = pl.DataFrame(
            {
                "award_category": ["penalty"],
                "award_name": ["Suicide"],
                "award_count": [1],
                "award_score": [-100],
            }
        )
        fig = plot_participation_sunburst(df)
        assert isinstance(fig, go.Figure)


class TestAggregateParticipationForRadar:
    def test_basic(self, awards_df):
        result = aggregate_participation_for_radar(awards_df)
        assert result["name"] == "Match"
        assert result["kill_score"] == 1500  # 1000 + 500
        assert result["assist_score"] == 400
        assert result["objective_score"] == 600
        assert result["penalty_score"] == -100

    def test_empty(self, empty_awards_df):
        result = aggregate_participation_for_radar(empty_awards_df)
        assert result["kill_score"] == 0
        assert result["assist_score"] == 0

    def test_custom_name_color(self, awards_df):
        result = aggregate_participation_for_radar(awards_df, name="Session 1", color="#FF0000")
        assert result["name"] == "Session 1"
        assert result["color"] == "#FF0000"


class TestComputeParticipationPercentages:
    def test_basic(self, awards_df):
        result = compute_participation_percentages(awards_df)
        assert "kills_pct" in result
        assert "assists_pct" in result
        assert "objectives_pct" in result
        assert "vehicles_pct" in result
        # Total should be ~100% (positive scores only)
        total = (
            result["kills_pct"]
            + result["assists_pct"]
            + result["objectives_pct"]
            + result["vehicles_pct"]
        )
        assert 90 < total <= 100  # might not be 100 if "other" exists

    def test_empty(self, empty_awards_df):
        result = compute_participation_percentages(empty_awards_df)
        assert result["kills_pct"] == 0

    def test_all_zero(self):
        df = pl.DataFrame(
            {
                "award_category": ["kill", "assist"],
                "award_name": ["Kill", "Assist"],
                "award_count": [0, 0],
                "award_score": [0, 0],
            }
        )
        result = compute_participation_percentages(df)
        assert result["kills_pct"] == 0


# ============================================================================
# participation_radar.py
# ============================================================================


class TestIsObjectiveModeFromPairName:
    @pytest.mark.parametrize(
        "pair_name,expected",
        [
            ("Arena:CTF on Aquarius", True),
            ("Arena:Capture the Flag on Streets", True),
            ("Arena:Oddball on Live Fire", True),
            ("Arena:Strongholds on Recharge", True),
            ("Arena:Total Control on Breaker", True),
            ("Arena:King of the Hill on Streets", True),
            ("Arena:Zone on Streets", True),
            ("Arena:Stockpile on Fragmentation", True),
            ("Arena:Extraction on Streets", True),
            ("Arena:Land Grab on Live Fire", True),
            # Slayer modes (not objective)
            ("Arena:Slayer on Streets", False),
            ("Arena:Fiesta Slayer on Live Fire", False),
            ("Arena:Team Slayer on Aquarius", False),
            # None → default to objective
            (None, True),
            ("", True),
        ],
    )
    def test_detection(self, pair_name, expected):
        assert _is_objective_mode_from_pair_name(pair_name) == expected


class TestExtractScoresFromAwards:
    def test_basic(self, awards_df):
        scores = _extract_scores_from_awards(awards_df)
        assert scores["kill"] == 1500  # 1000 + 500
        assert scores["assist"] == 400
        assert scores["objective"] == 600
        assert scores["vehicle"] == 200
        assert scores["penalty"] == -100

    def test_empty(self, empty_awards_df):
        scores = _extract_scores_from_awards(empty_awards_df)
        assert all(v == 0 for v in scores.values())

    def test_missing_column(self):
        df = pl.DataFrame({"award_category": ["kill"], "other_col": [100]})
        scores = _extract_scores_from_awards(df)
        assert all(v == 0 for v in scores.values())


class TestGetMatchStatsValues:
    def test_basic(self):
        row = {"deaths": 5, "time_played_seconds": 600}
        deaths, dur, avg = _get_match_stats_values(row)
        assert deaths == 5
        assert dur == 10.0

    def test_none(self):
        deaths, dur, avg = _get_match_stats_values(None)
        assert deaths == 0
        assert dur == 10.0
        assert avg == 0.0

    def test_with_avg_life(self):
        row = {"deaths": 3, "time_played_seconds": 300, "avg_life_seconds": 45.0}
        deaths, dur, avg = _get_match_stats_values(row)
        assert deaths == 3
        assert dur == 5.0
        assert avg == 45.0

    def test_zero_duration(self):
        row = {"deaths": 1, "time_played_seconds": 0}
        deaths, dur, avg = _get_match_stats_values(row)
        assert dur == 10.0  # default

    def test_invalid_values(self):
        row = {"deaths": "abc", "time_played_seconds": None}
        deaths, dur, avg = _get_match_stats_values(row)
        assert deaths == 0
        assert dur == 10.0


class TestComputeParticipationProfile:
    def test_basic_slayer(self, awards_df):
        result = compute_participation_profile(
            awards_df,
            match_row={"deaths": 5, "time_played_seconds": 600},
            name="Test",
            pair_name="Arena:Slayer on Streets",
        )
        assert result["name"] == "Test"
        # Slayer → objectifs_raw = kill_score
        assert result["objectifs_raw"] == 1500  # kill total

    def test_basic_objective(self, awards_df):
        result = compute_participation_profile(
            awards_df,
            match_row={"deaths": 5, "time_played_seconds": 600},
            name="Test",
            pair_name="Arena:CTF on Aquarius",
        )
        assert result["objectifs_raw"] == 600  # objective score

    def test_normalization_range(self, awards_df):
        result = compute_participation_profile(awards_df, name="Test")
        for key in (
            "objectifs_norm",
            "combat_norm",
            "support_norm",
            "score_norm",
            "impact_norm",
            "survie_norm",
        ):
            assert 0.0 <= result[key] <= 1.0, f"{key} out of range: {result[key]}"

    def test_empty_awards(self, empty_awards_df):
        result = compute_participation_profile(empty_awards_df, name="Empty")
        assert result["combat_raw"] == 0
        assert result["support_raw"] == 0
        assert result["score_raw"] == 0

    def test_custom_thresholds(self, awards_df):
        th = {k: 100.0 for k in RADAR_THRESHOLDS}
        result = compute_participation_profile(awards_df, thresholds=th, name="Custom")
        # With very low thresholds, norms should be 1.0 (capped)
        assert result["combat_norm"] == 1.0

    def test_with_color(self, awards_df):
        result = compute_participation_profile(awards_df, color="#FF0000")
        assert result["color"] == "#FF0000"

    def test_with_no_match_row(self, awards_df):
        result = compute_participation_profile(awards_df)
        assert result["survie_raw"] >= 0

    def test_survie_with_avg_life(self, awards_df):
        result = compute_participation_profile(
            awards_df,
            match_row={
                "deaths": 2,
                "time_played_seconds": 600,
                "avg_life_seconds": 60.0,
            },
        )
        # avg_life > 0 → blend
        assert result["survie_raw"] > 0

    def test_explicit_mode_is_objective(self, awards_df):
        result_obj = compute_participation_profile(awards_df, mode_is_objective=True)
        result_slay = compute_participation_profile(awards_df, mode_is_objective=False)
        # Objective mode uses objective_score, Slayer uses kill_score
        assert result_obj["objectifs_raw"] != result_slay["objectifs_raw"]


class TestRadarConstants:
    def test_thresholds_keys(self):
        expected_keys = {
            "objectifs",
            "combat",
            "support",
            "score",
            "impact_pts_per_min",
            "survie_deaths_per_min_ref",
            "survie_avg_life_ref_seconds",
        }
        assert set(RADAR_THRESHOLDS.keys()) == expected_keys

    def test_thresholds_positive(self):
        for k, v in RADAR_THRESHOLDS.items():
            assert v > 0, f"{k} should be positive"

    def test_axis_lines(self):
        assert len(RADAR_AXIS_LINES) == 6
        assert all(isinstance(line, str) for line in RADAR_AXIS_LINES)
