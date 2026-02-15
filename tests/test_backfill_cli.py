"""Tests pour scripts/backfill/cli.py — parsing des arguments CLI du backfill.

Vérifie create_argument_parser() (tous les arguments, defaults, choices)
et _get_usage_examples() (docstring contenant les exemples).
"""

from __future__ import annotations

import pytest

from scripts.backfill.cli import _get_usage_examples, create_argument_parser

# ── Fixture commune ─────────────────────────────────────────────────────────


@pytest.fixture
def parser():
    return create_argument_parser()


# ── Tests _get_usage_examples ────────────────────────────────────────────────


class TestGetUsageExamples:
    def test_returns_string(self):
        result = _get_usage_examples()
        assert isinstance(result, str)

    def test_contains_examples(self):
        result = _get_usage_examples()
        assert "Exemples:" in result
        assert "--player" in result
        assert "--all-data" in result

    def test_contains_workaround(self):
        result = _get_usage_examples()
        assert "Workaround" in result


# ── Tests create_argument_parser defaults ────────────────────────────────────


class TestParserDefaults:
    def test_player_default_none(self, parser):
        args = parser.parse_args([])
        assert args.player is None

    def test_all_default_false(self, parser):
        args = parser.parse_args([])
        assert args.all is False

    def test_dry_run_default_false(self, parser):
        args = parser.parse_args([])
        assert args.dry_run is False

    def test_max_matches_default_none(self, parser):
        args = parser.parse_args([])
        assert args.max_matches is None

    def test_requests_per_second_default(self, parser):
        args = parser.parse_args([])
        assert args.requests_per_second == 5

    def test_detection_mode_default_or(self, parser):
        args = parser.parse_args([])
        assert args.detection_mode == "or"


# ── Tests arguments de sélection joueur ──────────────────────────────────────


class TestPlayerArgs:
    def test_player_arg(self, parser):
        args = parser.parse_args(["--player", "TestGT"])
        assert args.player == "TestGT"

    def test_all_flag(self, parser):
        args = parser.parse_args(["--all"])
        assert args.all is True


# ── Tests arguments généraux ─────────────────────────────────────────────────


class TestGeneralArgs:
    def test_dry_run(self, parser):
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_max_matches(self, parser):
        args = parser.parse_args(["--max-matches", "100"])
        assert args.max_matches == 100

    def test_requests_per_second(self, parser):
        args = parser.parse_args(["--requests-per-second", "10"])
        assert args.requests_per_second == 10

    def test_detection_mode_and(self, parser):
        args = parser.parse_args(["--detection-mode", "and"])
        assert args.detection_mode == "and"

    def test_detection_mode_invalid(self, parser):
        with pytest.raises(SystemExit):
            parser.parse_args(["--detection-mode", "invalid"])


# ── Tests flags de données ───────────────────────────────────────────────────


class TestDataFlags:
    @pytest.mark.parametrize(
        "flag,attr",
        [
            ("--medals", "medals"),
            ("--events", "events"),
            ("--skill", "skill"),
            ("--personal-scores", "personal_scores"),
            ("--performance-scores", "performance_scores"),
            ("--aliases", "aliases"),
            ("--all-data", "all_data"),
            ("--accuracy", "accuracy"),
            ("--shots", "shots"),
            ("--enemy-mmr", "enemy_mmr"),
            ("--assets", "assets"),
            ("--participants", "participants"),
            ("--killer-victim", "killer_victim"),
            ("--end-time", "end_time"),
            ("--sessions", "sessions"),
            ("--citations", "citations"),
        ],
    )
    def test_data_flag_sets_true(self, parser, flag, attr):
        args = parser.parse_args([flag])
        assert getattr(args, attr) is True

    @pytest.mark.parametrize(
        "flag,attr",
        [
            ("--medals", "medals"),
            ("--events", "events"),
            ("--skill", "skill"),
            ("--personal-scores", "personal_scores"),
            ("--performance-scores", "performance_scores"),
            ("--aliases", "aliases"),
            ("--all-data", "all_data"),
            ("--accuracy", "accuracy"),
            ("--shots", "shots"),
            ("--enemy-mmr", "enemy_mmr"),
            ("--assets", "assets"),
            ("--participants", "participants"),
            ("--killer-victim", "killer_victim"),
            ("--end-time", "end_time"),
            ("--sessions", "sessions"),
            ("--citations", "citations"),
        ],
    )
    def test_data_flag_default_false(self, parser, flag, attr):
        args = parser.parse_args([])
        assert getattr(args, attr) is False


# ── Tests flags --force-* ────────────────────────────────────────────────────


class TestForceFlags:
    @pytest.mark.parametrize(
        "flag,attr",
        [
            ("--force-accuracy", "force_accuracy"),
            ("--force-shots", "force_shots"),
            ("--force-enemy-mmr", "force_enemy_mmr"),
            ("--force-assets", "force_assets"),
            ("--force-aliases", "force_aliases"),
            ("--force-medals", "force_medals"),
            ("--force-participants", "force_participants"),
            ("--force-participants-shots", "force_participants_shots"),
            ("--force-participants-damage", "force_participants_damage"),
            ("--force-end-time", "force_end_time"),
            ("--force-sessions", "force_sessions"),
            ("--force-citations", "force_citations"),
        ],
    )
    def test_force_flag_sets_true(self, parser, flag, attr):
        args = parser.parse_args([flag])
        assert getattr(args, attr) is True

    @pytest.mark.parametrize(
        "flag,attr",
        [
            ("--force-accuracy", "force_accuracy"),
            ("--force-shots", "force_shots"),
            ("--force-enemy-mmr", "force_enemy_mmr"),
            ("--force-assets", "force_assets"),
            ("--force-aliases", "force_aliases"),
            ("--force-medals", "force_medals"),
            ("--force-participants", "force_participants"),
            ("--force-participants-shots", "force_participants_shots"),
            ("--force-participants-damage", "force_participants_damage"),
            ("--force-end-time", "force_end_time"),
            ("--force-sessions", "force_sessions"),
            ("--force-citations", "force_citations"),
        ],
    )
    def test_force_flag_default_false(self, parser, flag, attr):
        args = parser.parse_args([])
        assert getattr(args, attr) is False


# ── Tests flags participants détaillés ───────────────────────────────────────


class TestParticipantDetailFlags:
    @pytest.mark.parametrize(
        "flag,attr",
        [
            ("--participants-scores", "participants_scores"),
            ("--participants-kda", "participants_kda"),
            ("--participants-shots", "participants_shots"),
            ("--participants-damage", "participants_damage"),
        ],
    )
    def test_participant_detail_flag(self, parser, flag, attr):
        args = parser.parse_args([flag])
        assert getattr(args, attr) is True


# ── Tests combinaisons ──────────────────────────────────────────────────────


class TestCombinations:
    def test_player_with_medals_and_events(self, parser):
        args = parser.parse_args(["--player", "GT", "--medals", "--events"])
        assert args.player == "GT"
        assert args.medals is True
        assert args.events is True
        assert args.skill is False

    def test_all_with_all_data(self, parser):
        args = parser.parse_args(["--all", "--all-data"])
        assert args.all is True
        assert args.all_data is True

    def test_full_combination(self, parser):
        args = parser.parse_args(
            [
                "--player",
                "JGtm",
                "--medals",
                "--events",
                "--skill",
                "--max-matches",
                "50",
                "--requests-per-second",
                "3",
                "--detection-mode",
                "and",
                "--dry-run",
            ]
        )
        assert args.player == "JGtm"
        assert args.medals is True
        assert args.events is True
        assert args.skill is True
        assert args.max_matches == 50
        assert args.requests_per_second == 3
        assert args.detection_mode == "and"
        assert args.dry_run is True

    def test_no_args_all_defaults(self, parser):
        """Vérifier que tous les flags sont False par défaut quand on passe rien."""
        args = parser.parse_args([])
        bool_attrs = [
            "all",
            "dry_run",
            "medals",
            "events",
            "skill",
            "personal_scores",
            "performance_scores",
            "aliases",
            "all_data",
            "accuracy",
            "force_accuracy",
            "shots",
            "force_shots",
            "enemy_mmr",
            "force_enemy_mmr",
            "assets",
            "force_assets",
            "force_aliases",
            "force_medals",
            "participants",
            "force_participants",
            "participants_scores",
            "participants_kda",
            "participants_shots",
            "force_participants_shots",
            "participants_damage",
            "force_participants_damage",
            "killer_victim",
            "end_time",
            "force_end_time",
            "sessions",
            "force_sessions",
            "citations",
            "force_citations",
        ]
        for attr in bool_attrs:
            assert getattr(args, attr) is False, f"{attr} should default to False"
