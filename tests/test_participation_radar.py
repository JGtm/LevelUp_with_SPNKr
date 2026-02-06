"""Tests pour src/visualization/participation_radar.py."""

from __future__ import annotations

import polars as pl
import pytest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def empty_awards() -> pl.DataFrame:
    """DataFrame PersonalScores vide."""
    return pl.DataFrame(schema={"award_category": pl.Utf8, "award_score": pl.Int64})


@pytest.fixture
def awards_mode_objective() -> pl.DataFrame:
    """PersonalScores typique mode objectif (CTF, etc.)."""
    return pl.DataFrame(
        {
            "award_category": ["kill", "assist", "objective", "vehicle", "penalty"],
            "award_score": [700, 150, 400, 50, -100],
        }
    )


@pytest.fixture
def awards_mode_slayer() -> pl.DataFrame:
    """PersonalScores typique mode Slayer (frags = objectif)."""
    return pl.DataFrame(
        {
            "award_category": ["kill", "assist", "vehicle", "penalty"],
            "award_score": [1200, 200, 0, -50],
        }
    )


@pytest.fixture
def match_row_10min() -> dict:
    """Ligne match_stats : 10 min, 5 morts."""
    return {
        "deaths": 5,
        "time_played_seconds": 600,
        "pair_name": "Arena:Slayer on Aquarius",
    }


# =============================================================================
# Tests compute_participation_profile
# =============================================================================


class TestComputeParticipationProfile:
    """Tests pour compute_participation_profile."""

    def test_empty_awards_returns_default_profile(self, empty_awards: pl.DataFrame) -> None:
        from src.visualization.participation_radar import compute_participation_profile

        profile = compute_participation_profile(empty_awards, name="Vide", color="#000")

        assert profile["name"] == "Vide"
        assert profile["color"] == "#000"
        assert profile["objectifs_raw"] == 0
        assert profile["combat_raw"] == 0
        assert profile["support_raw"] == 0
        assert profile["score_raw"] == 0

    def test_mode_objective_uses_objective_score(self, awards_mode_objective: pl.DataFrame) -> None:
        from src.visualization.participation_radar import compute_participation_profile

        profile = compute_participation_profile(
            awards_mode_objective,
            match_row=None,
            mode_is_objective=True,
        )

        assert profile["objectifs_raw"] == 400
        assert profile["combat_raw"] == 700
        assert profile["support_raw"] == 150
        assert profile["score_raw"] == 1200

    def test_mode_slayer_uses_kill_score_as_objectifs(
        self, awards_mode_slayer: pl.DataFrame
    ) -> None:
        from src.visualization.participation_radar import compute_participation_profile

        profile = compute_participation_profile(
            awards_mode_slayer,
            match_row=None,
            mode_is_objective=False,
        )

        assert profile["objectifs_raw"] == 1200
        assert profile["combat_raw"] == 1200

    def test_detect_mode_from_pair_name_slayer(self, awards_mode_slayer: pl.DataFrame) -> None:
        from src.visualization.participation_radar import compute_participation_profile

        profile = compute_participation_profile(
            awards_mode_slayer,
            pair_name="Arena:Slayer on Aquarius",
        )

        assert profile["objectifs_raw"] == 1200

    def test_detect_mode_from_pair_name_objective(
        self, awards_mode_objective: pl.DataFrame
    ) -> None:
        from src.visualization.participation_radar import compute_participation_profile

        profile = compute_participation_profile(
            awards_mode_objective,
            pair_name="BTB:CTF on Fragmentation",
        )

        assert profile["objectifs_raw"] == 400

    def test_impact_and_survie_with_match_row(
        self, awards_mode_objective: pl.DataFrame, match_row_10min: dict
    ) -> None:
        from src.visualization.participation_radar import compute_participation_profile

        profile = compute_participation_profile(
            awards_mode_objective,
            match_row=match_row_10min,
        )

        # 1200 pts positifs / 10 min = 120 pts/min
        assert profile["impact_raw"] == pytest.approx(120.0, rel=0.01)
        # 5 morts / 10 min = 0.5 mort/min, ref 2.0 → deaths_component = 1 - 0.5/2 = 0.75
        # pas d'avg_life → survie = deaths_component = 0.75
        assert profile["survie_raw"] == pytest.approx(0.75, rel=0.01)

    def test_normalized_values_in_range(
        self, awards_mode_objective: pl.DataFrame, match_row_10min: dict
    ) -> None:
        from src.visualization.participation_radar import compute_participation_profile

        profile = compute_participation_profile(
            awards_mode_objective,
            match_row=match_row_10min,
        )

        for key in (
            "objectifs_norm",
            "combat_norm",
            "support_norm",
            "score_norm",
            "impact_norm",
            "survie_norm",
        ):
            assert 0 <= profile[key] <= 1.1, f"{key} hors plage: {profile[key]}"
