"""Tests de couverture exhaustive pour src/data/sync/transformers.py.

Couvre toutes les fonctions pures et extracteurs :
- Helpers de parsing (_safe_str, _parse_duration_to_seconds, _is_uuid, _normalize_gamertag)
- Extracteurs joueur (_find_player, _find_core_stats_dict, _extract_player_stats, etc.)
- Extracteurs match (_extract_team_scores, _is_ranked_playlist, _is_firefight_match, etc.)
- Médailles, personal scores, aliases, killer/victim, participants
- MMR (_extract_mmr_from_skill)
- Fonctions de haut niveau (transform_match_stats, transform_skill_stats, etc.)
"""

from __future__ import annotations

import json

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures communes
# ─────────────────────────────────────────────────────────────────────────────

XUID = "1234567890123456"
MATCH_ID = "test-match-001"


def _player_obj(
    xuid: str = XUID,
    kills: int = 10,
    deaths: int = 5,
    assists: int = 3,
    accuracy: float = 0.55,
    kda: float = 2.6,
    outcome: int = 2,
    team_id: int = 0,
    rank: int = 1,
    max_killing_spree: int = 5,
    headshot_kills: int = 4,
    time_played: str = "PT10M30S",
    avg_life: float = 25.0,
    gamertag: str = "TestPlayer",
    score: int = 1500,
    personal_score: int = 2000,
    shots_fired: int = 200,
    shots_hit: int = 110,
    damage_dealt: float = 3500.0,
    damage_taken: float = 2800.0,
    grenade_kills: int = 2,
    melee_kills: int = 1,
    power_weapon_kills: int = 3,
) -> dict:
    """Construit un objet joueur simulant la réponse API."""
    return {
        "PlayerId": f"xuid({xuid})",
        "PlayerGamertag": gamertag,
        "Outcome": outcome,
        "LastTeamId": team_id,
        "Rank": rank,
        "PlayerTeamStats": [
            {
                "Stats": {
                    "CoreStats": {
                        "Kills": kills,
                        "Deaths": deaths,
                        "Assists": assists,
                        "Accuracy": accuracy,
                        "KDA": kda,
                        "MaxKillingSpree": max_killing_spree,
                        "HeadshotKills": headshot_kills,
                        "AverageLifeSeconds": avg_life,
                        "TimePlayed": time_played,
                        "ShotsFired": shots_fired,
                        "ShotsHit": shots_hit,
                        "DamageDealt": damage_dealt,
                        "DamageTaken": damage_taken,
                        "GrenadeKills": grenade_kills,
                        "MeleeKills": melee_kills,
                        "PowerWeaponKills": power_weapon_kills,
                        "Score": score,
                        "PersonalScore": personal_score,
                        "Medals": [
                            {"NameId": 100, "Count": 3},
                            {"NameId": 200, "Count": 1},
                        ],
                    }
                }
            }
        ],
    }


def _match_json(
    match_id: str = MATCH_ID,
    xuid: str = XUID,
    start_time: str = "2024-01-15T10:00:00Z",
    players: list | None = None,
    teams: list | None = None,
    playlist_name: str | None = "Arena: Slayer",
    map_name: str | None = "Aquarius",
    pair_name: str | None = "Arena:Slayer on Aquarius",
    game_variant_name: str | None = "Slayer",
    playlist_id: str | None = "playlist-id-1",
    map_id: str | None = "map-id-1",
    pair_id: str | None = "pair-id-1",
    game_variant_id: str | None = "gv-id-1",
    duration: str | None = "PT10M30S",
) -> dict:
    """Construit un JSON de match complet simulant la réponse API."""
    if players is None:
        players = [_player_obj(xuid=xuid)]
    if teams is None:
        teams = [
            {"TeamId": 0, "TotalPoints": 50},
            {"TeamId": 1, "TotalPoints": 45},
        ]

    match_info = {
        "StartTime": start_time,
    }
    if duration:
        match_info["Duration"] = duration

    def _asset(asset_id, name):
        d = {}
        if asset_id:
            d["AssetId"] = asset_id
        if name:
            d["PublicName"] = name
        return d if d else None

    if playlist_id or playlist_name:
        match_info["Playlist"] = _asset(playlist_id, playlist_name)
    if map_id or map_name:
        match_info["MapVariant"] = _asset(map_id, map_name)
    if pair_id or pair_name:
        match_info["PlaylistMapModePair"] = _asset(pair_id, pair_name)
    if game_variant_id or game_variant_name:
        match_info["UgcGameVariant"] = _asset(game_variant_id, game_variant_name)

    return {
        "MatchId": match_id,
        "MatchInfo": match_info,
        "Players": players,
        "Teams": teams,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests _safe_str
# ─────────────────────────────────────────────────────────────────────────────


class TestSafeStr:
    def test_none_returns_none(self):
        from src.data.sync.transformers import _safe_str

        assert _safe_str(None) is None

    def test_string_pass_through(self):
        from src.data.sync.transformers import _safe_str

        assert _safe_str("hello") == "hello"

    def test_int_to_str(self):
        from src.data.sync.transformers import _safe_str

        assert _safe_str(42) == "42"

    def test_nan_string_returns_none(self):
        from src.data.sync.transformers import _safe_str

        assert _safe_str("nan") is None

    def test_none_string_returns_none(self):
        from src.data.sync.transformers import _safe_str

        assert _safe_str("None") is None

    def test_empty_string(self):
        from src.data.sync.transformers import _safe_str

        assert _safe_str("") == ""


# ─────────────────────────────────────────────────────────────────────────────
# Tests _parse_duration_to_seconds
# ─────────────────────────────────────────────────────────────────────────────


class TestParseDurationToSeconds:
    def test_full_format(self):
        from src.data.sync.transformers import _parse_duration_to_seconds

        assert _parse_duration_to_seconds("PT1H30M45S") == 5445

    def test_minutes_seconds(self):
        from src.data.sync.transformers import _parse_duration_to_seconds

        assert _parse_duration_to_seconds("PT10M30S") == 630

    def test_seconds_only(self):
        from src.data.sync.transformers import _parse_duration_to_seconds

        assert _parse_duration_to_seconds("PT49S") == 49

    def test_fractional_seconds(self):
        from src.data.sync.transformers import _parse_duration_to_seconds

        assert _parse_duration_to_seconds("PT49.3S") == 49

    def test_hours_only(self):
        from src.data.sync.transformers import _parse_duration_to_seconds

        assert _parse_duration_to_seconds("PT2H") == 7200

    def test_minutes_only(self):
        from src.data.sync.transformers import _parse_duration_to_seconds

        assert _parse_duration_to_seconds("PT5M") == 300

    def test_none_returns_none(self):
        from src.data.sync.transformers import _parse_duration_to_seconds

        assert _parse_duration_to_seconds(None) is None

    def test_empty_returns_none(self):
        from src.data.sync.transformers import _parse_duration_to_seconds

        assert _parse_duration_to_seconds("") is None

    def test_invalid_format_returns_none(self):
        from src.data.sync.transformers import _parse_duration_to_seconds

        assert _parse_duration_to_seconds("10 minutes") is None

    def test_case_insensitive(self):
        from src.data.sync.transformers import _parse_duration_to_seconds

        assert _parse_duration_to_seconds("pt10m30s") == 630


# ─────────────────────────────────────────────────────────────────────────────
# Tests _is_uuid
# ─────────────────────────────────────────────────────────────────────────────


class TestIsUuid:
    def test_valid_uuid(self):
        from src.data.sync.transformers import _is_uuid

        assert _is_uuid("a1b2c3d4-e5f6-7890-abcd-ef1234567890") is True

    def test_valid_uuid_uppercase(self):
        from src.data.sync.transformers import _is_uuid

        assert _is_uuid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890") is True

    def test_not_uuid(self):
        from src.data.sync.transformers import _is_uuid

        assert _is_uuid("Arena: Slayer") is False

    def test_none(self):
        from src.data.sync.transformers import _is_uuid

        assert _is_uuid(None) is False

    def test_empty(self):
        from src.data.sync.transformers import _is_uuid

        assert _is_uuid("") is False

    def test_uuid_with_spaces(self):
        from src.data.sync.transformers import _is_uuid

        # strip() is applied so leading/trailing spaces should work
        assert _is_uuid(" a1b2c3d4-e5f6-7890-abcd-ef1234567890 ") is True

    def test_short_string(self):
        from src.data.sync.transformers import _is_uuid

        assert _is_uuid("abc") is False


# ─────────────────────────────────────────────────────────────────────────────
# Tests _normalize_gamertag
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeGamertag:
    def test_normal_string(self):
        from src.data.sync.transformers import _normalize_gamertag

        assert _normalize_gamertag("TestPlayer") == "TestPlayer"

    def test_bytes(self):
        from src.data.sync.transformers import _normalize_gamertag

        assert _normalize_gamertag(b"TestPlayer") == "TestPlayer"

    def test_none(self):
        from src.data.sync.transformers import _normalize_gamertag

        assert _normalize_gamertag(None) is None

    def test_empty_string(self):
        from src.data.sync.transformers import _normalize_gamertag

        assert _normalize_gamertag("") is None

    def test_whitespace(self):
        from src.data.sync.transformers import _normalize_gamertag

        assert _normalize_gamertag("  TestPlayer  ") == "TestPlayer"

    def test_int_value(self):
        from src.data.sync.transformers import _normalize_gamertag

        assert _normalize_gamertag(12345) == "12345"


# ─────────────────────────────────────────────────────────────────────────────
# Tests _find_player
# ─────────────────────────────────────────────────────────────────────────────


class TestFindPlayer:
    def test_find_by_xuid_string(self):
        from src.data.sync.transformers import _find_player

        players = [_player_obj(xuid="111"), _player_obj(xuid="222")]
        result = _find_player(players, "222")
        assert result is not None
        assert "222" in json.dumps(result["PlayerId"])

    def test_not_found(self):
        from src.data.sync.transformers import _find_player

        players = [_player_obj(xuid="111")]
        assert _find_player(players, "999") is None

    def test_empty_list(self):
        from src.data.sync.transformers import _find_player

        assert _find_player([], "111") is None

    def test_player_with_dict_player_id(self):
        from src.data.sync.transformers import _find_player

        players = [{"PlayerId": {"Xuid": "555"}, "Outcome": 2}]
        result = _find_player(players, "555")
        assert result is not None

    def test_player_no_player_id(self):
        from src.data.sync.transformers import _find_player

        players = [{"Outcome": 2}]
        assert _find_player(players, "111") is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _find_core_stats_dict
# ─────────────────────────────────────────────────────────────────────────────


class TestFindCoreStatsDict:
    def test_standard_structure(self):
        from src.data.sync.transformers import _find_core_stats_dict

        p = _player_obj()
        result = _find_core_stats_dict(p)
        assert result is not None
        assert result["Kills"] == 10
        assert result["Deaths"] == 5

    def test_empty_player(self):
        from src.data.sync.transformers import _find_core_stats_dict

        assert _find_core_stats_dict({}) is None

    def test_no_player_team_stats(self):
        from src.data.sync.transformers import _find_core_stats_dict

        assert _find_core_stats_dict({"PlayerTeamStats": None}) is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_player_stats
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractPlayerStats:
    def test_normal(self):
        from src.data.sync.transformers import _extract_player_stats

        p = _player_obj(kills=15, deaths=8, assists=4, accuracy=0.6)
        kills, deaths, assists, accuracy = _extract_player_stats(p)
        assert kills == 15
        assert deaths == 8
        assert assists == 4
        assert accuracy == pytest.approx(0.6)

    def test_no_stats(self):
        from src.data.sync.transformers import _extract_player_stats

        kills, deaths, assists, accuracy = _extract_player_stats({})
        assert kills == 0
        assert deaths == 0
        assert assists == 0
        assert accuracy is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_player_outcome_team
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractPlayerOutcomeTeam:
    def test_normal(self):
        from src.data.sync.transformers import _extract_player_outcome_team

        p = _player_obj(outcome=2, team_id=0)
        outcome, team_id = _extract_player_outcome_team(p)
        assert outcome == 2
        assert team_id == 0

    def test_missing_fields(self):
        from src.data.sync.transformers import _extract_player_outcome_team

        outcome, team_id = _extract_player_outcome_team({})
        assert outcome is None
        assert team_id is None

    def test_string_values_return_none(self):
        from src.data.sync.transformers import _extract_player_outcome_team

        outcome, team_id = _extract_player_outcome_team({"Outcome": "win", "LastTeamId": "x"})
        assert outcome is None
        assert team_id is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_player_rank
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractPlayerRank:
    def test_normal(self):
        from src.data.sync.transformers import _extract_player_rank

        assert _extract_player_rank({"Rank": 3}) == 3

    def test_none(self):
        from src.data.sync.transformers import _extract_player_rank

        assert _extract_player_rank({}) is None

    def test_string_rank(self):
        from src.data.sync.transformers import _extract_player_rank

        assert _extract_player_rank({"Rank": "first"}) is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_kda
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractKDA:
    def test_normal(self):
        from src.data.sync.transformers import _extract_kda

        p = _player_obj(kda=2.5)
        assert _extract_kda(p) == pytest.approx(2.5)

    def test_no_stats(self):
        from src.data.sync.transformers import _extract_kda

        assert _extract_kda({}) is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_spree_headshots
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractSpreeHeadshots:
    def test_normal(self):
        from src.data.sync.transformers import _extract_spree_headshots

        p = _player_obj(max_killing_spree=7, headshot_kills=12)
        spree, headshots = _extract_spree_headshots(p)
        assert spree == 7
        assert headshots == 12

    def test_no_stats(self):
        from src.data.sync.transformers import _extract_spree_headshots

        spree, headshots = _extract_spree_headshots({})
        assert spree is None
        assert headshots is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_life_time_stats
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractLifeTimeStats:
    def test_normal(self):
        from src.data.sync.transformers import _extract_life_time_stats

        p = _player_obj(avg_life=25.0, time_played="PT10M30S")
        avg_life, time_played = _extract_life_time_stats(p)
        assert avg_life == pytest.approx(25.0)
        assert time_played == 630

    def test_no_stats(self):
        from src.data.sync.transformers import _extract_life_time_stats

        avg_life, time_played = _extract_life_time_stats({})
        assert avg_life is None
        assert time_played is None

    def test_average_life_duration_iso(self):
        """AverageLifeDuration au format ISO 'PT49.3S'."""
        from src.data.sync.transformers import _extract_life_time_stats

        player = {
            "PlayerTeamStats": [
                {
                    "Stats": {
                        "CoreStats": {
                            "Kills": 1,
                            "Deaths": 1,
                            "Assists": 0,
                            "AverageLifeDuration": "PT49.3S",
                        }
                    }
                }
            ]
        }
        avg_life, _ = _extract_life_time_stats(player)
        assert avg_life == pytest.approx(49.0, abs=1)

    def test_fallback_to_match_duration(self):
        """Fallback time_played depuis MatchInfo.Duration."""
        from src.data.sync.transformers import _extract_life_time_stats

        player = {
            "PlayerTeamStats": [
                {
                    "Stats": {
                        "CoreStats": {
                            "Kills": 1,
                            "Deaths": 1,
                            "Assists": 0,
                        }
                    }
                }
            ]
        }
        match_obj = {"MatchInfo": {"Duration": "PT5M"}}
        _, time_played = _extract_life_time_stats(player, match_obj)
        assert time_played == 300

    def test_time_played_seconds_field(self):
        """TimePlayedSeconds (numérique) au lieu de TimePlayed (ISO)."""
        from src.data.sync.transformers import _extract_life_time_stats

        player = {
            "PlayerTeamStats": [
                {
                    "Stats": {
                        "CoreStats": {
                            "Kills": 1,
                            "Deaths": 1,
                            "Assists": 0,
                            "TimePlayedSeconds": 450,
                        }
                    }
                }
            ]
        }
        _, time_played = _extract_life_time_stats(player)
        assert time_played == 450


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_player_score
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractPlayerScore:
    def test_personal_score(self):
        from src.data.sync.transformers import _extract_player_score

        p = _player_obj(personal_score=2500, score=1500)
        assert _extract_player_score(p) == 2500

    def test_fallback_score(self):
        from src.data.sync.transformers import _extract_player_score

        player = {
            "PlayerTeamStats": [
                {
                    "Stats": {
                        "CoreStats": {
                            "Kills": 1,
                            "Deaths": 0,
                            "Assists": 0,
                            "Score": 800,
                        }
                    }
                }
            ]
        }
        assert _extract_player_score(player) == 800

    def test_no_stats(self):
        from src.data.sync.transformers import _extract_player_score

        assert _extract_player_score({}) is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_team_scores
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractTeamScores:
    def test_normal(self):
        from src.data.sync.transformers import _extract_team_scores

        match = {
            "Teams": [
                {"TeamId": 0, "TotalPoints": 50},
                {"TeamId": 1, "TotalPoints": 45},
            ]
        }
        my, enemy = _extract_team_scores(match, 0)
        assert my == 50
        assert enemy == 45

    def test_no_teams(self):
        from src.data.sync.transformers import _extract_team_scores

        my, enemy = _extract_team_scores({}, 0)
        assert my is None
        assert enemy is None

    def test_no_team_id(self):
        from src.data.sync.transformers import _extract_team_scores

        match = {"Teams": [{"TeamId": 0, "TotalPoints": 50}]}
        my, enemy = _extract_team_scores(match, None)
        assert my is None
        assert enemy is None

    def test_multiple_enemy_teams(self):
        from src.data.sync.transformers import _extract_team_scores

        match = {
            "Teams": [
                {"TeamId": 0, "TotalPoints": 50},
                {"TeamId": 1, "TotalPoints": 30},
                {"TeamId": 2, "TotalPoints": 45},
            ]
        }
        my, enemy = _extract_team_scores(match, 0)
        assert my == 50
        assert enemy == 45  # max des ennemis

    def test_score_field_fallback(self):
        from src.data.sync.transformers import _extract_team_scores

        match = {
            "Teams": [
                {"TeamId": 0, "Score": 50},
                {"TeamId": 1, "Score": 45},
            ]
        }
        my, enemy = _extract_team_scores(match, 0)
        assert my == 50
        assert enemy == 45


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_asset_id / _extract_public_name
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractAsset:
    def test_asset_id(self):
        from src.data.sync.transformers import _extract_asset_id

        info = {"Playlist": {"AssetId": "abc123"}}
        assert _extract_asset_id(info, "Playlist") == "abc123"

    def test_asset_id_missing(self):
        from src.data.sync.transformers import _extract_asset_id

        assert _extract_asset_id({}, "Playlist") is None

    def test_public_name(self):
        from src.data.sync.transformers import _extract_public_name

        info = {"MapVariant": {"PublicName": "Aquarius"}}
        assert _extract_public_name(info, "MapVariant") == "Aquarius"

    def test_public_name_missing(self):
        from src.data.sync.transformers import _extract_public_name

        assert _extract_public_name({}, "MapVariant") is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _is_ranked_playlist
# ─────────────────────────────────────────────────────────────────────────────


class TestIsRankedPlaylist:
    def test_ranked_by_tag(self):
        from src.data.sync.transformers import _is_ranked_playlist

        info = {"Playlist": {"Tags": ["Ranked", "Arena"]}}
        assert _is_ranked_playlist(info) is True

    def test_ranked_by_name(self):
        from src.data.sync.transformers import _is_ranked_playlist

        info = {"Playlist": {"PublicName": "Ranked Arena"}}
        assert _is_ranked_playlist(info) is True

    def test_not_ranked(self):
        from src.data.sync.transformers import _is_ranked_playlist

        info = {"Playlist": {"PublicName": "Quick Play", "Tags": ["social"]}}
        assert _is_ranked_playlist(info) is False

    def test_no_playlist(self):
        from src.data.sync.transformers import _is_ranked_playlist

        assert _is_ranked_playlist({}) is False


# ─────────────────────────────────────────────────────────────────────────────
# Tests _is_firefight_match
# ─────────────────────────────────────────────────────────────────────────────


class TestIsFirefightMatch:
    def test_firefight_game_variant(self):
        from src.data.sync.transformers import _is_firefight_match

        info = {"UgcGameVariant": {"PublicName": "Firefight: King of the Hill"}}
        assert _is_firefight_match(info) is True

    def test_firefight_playlist(self):
        from src.data.sync.transformers import _is_firefight_match

        info = {"Playlist": {"PublicName": "Firefight"}}
        assert _is_firefight_match(info) is True

    def test_not_firefight(self):
        from src.data.sync.transformers import _is_firefight_match

        info = {"Playlist": {"PublicName": "Arena"}, "UgcGameVariant": {"PublicName": "Slayer"}}
        assert _is_firefight_match(info) is False

    def test_empty_match_info(self):
        from src.data.sync.transformers import _is_firefight_match

        assert _is_firefight_match({}) is False


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_mmr_from_skill
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractMmrFromSkill:
    def test_complete_skill_json(self):
        from src.data.sync.transformers import _extract_mmr_from_skill

        skill = {
            "Value": [
                {
                    "Id": f"xuid({XUID})",
                    "Result": {
                        "TeamId": 0,
                        "TeamMmr": 1250.5,
                        "TeamMmrs": {"0": 1250.5, "1": 1100.0},
                    },
                }
            ]
        }
        result = _extract_mmr_from_skill(skill, XUID, 0)
        assert result is not None
        team_mmr, enemy_mmr = result
        assert team_mmr == pytest.approx(1250.5)
        assert enemy_mmr == pytest.approx(1100.0)

    def test_player_not_found(self):
        from src.data.sync.transformers import _extract_mmr_from_skill

        skill = {"Value": [{"Id": "xuid(999)", "Result": {"TeamMmr": 1200}}]}
        assert _extract_mmr_from_skill(skill, XUID, 0) is None

    def test_no_value(self):
        from src.data.sync.transformers import _extract_mmr_from_skill

        assert _extract_mmr_from_skill({}, XUID, 0) is None

    def test_fallback_enemy_mmr_from_other_players(self):
        from src.data.sync.transformers import _extract_mmr_from_skill

        skill = {
            "Value": [
                {
                    "Id": f"xuid({XUID})",
                    "Result": {"TeamId": 0, "TeamMmr": 1200.0},
                },
                {
                    "Id": "xuid(9999)",
                    "Result": {"TeamId": 1, "TeamMmr": 1150.0},
                },
            ]
        }
        result = _extract_mmr_from_skill(skill, XUID, 0)
        assert result is not None
        team_mmr, enemy_mmr = result
        assert team_mmr == pytest.approx(1200.0)
        assert enemy_mmr == pytest.approx(1150.0)

    def test_team_id_from_param(self):
        from src.data.sync.transformers import _extract_mmr_from_skill

        skill = {
            "Value": [
                {
                    "Id": f"xuid({XUID})",
                    "Result": {
                        "TeamMmr": 1200.0,
                        "TeamMmrs": {"0": 1200.0, "1": 1100.0},
                    },
                }
            ]
        }
        result = _extract_mmr_from_skill(skill, XUID, 0)
        assert result is not None
        _, enemy_mmr = result
        assert enemy_mmr == pytest.approx(1100.0)

    def test_no_enemy_mmr(self):
        from src.data.sync.transformers import _extract_mmr_from_skill

        skill = {
            "Value": [
                {
                    "Id": f"xuid({XUID})",
                    "Result": {"TeamMmr": 1200.0},
                }
            ]
        }
        result = _extract_mmr_from_skill(skill, XUID, None)
        assert result is not None
        team_mmr, enemy_mmr = result
        assert team_mmr == pytest.approx(1200.0)
        assert enemy_mmr is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests extract_medals
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractMedals:
    def test_normal(self):
        from src.data.sync.transformers import extract_medals

        mj = _match_json()
        medals = extract_medals(mj, XUID)
        assert len(medals) == 2
        assert medals[0].match_id == MATCH_ID
        ids = {m.medal_name_id for m in medals}
        assert 100 in ids
        assert 200 in ids

    def test_no_player(self):
        from src.data.sync.transformers import extract_medals

        mj = _match_json()
        assert extract_medals(mj, "unknown_xuid") == []

    def test_no_match_id(self):
        from src.data.sync.transformers import extract_medals

        mj = {"Players": []}
        assert extract_medals(mj, XUID) == []

    def test_no_medals(self):
        from src.data.sync.transformers import extract_medals

        player = _player_obj()
        player["PlayerTeamStats"][0]["Stats"]["CoreStats"]["Medals"] = []
        mj = _match_json(players=[player])
        assert extract_medals(mj, XUID) == []

    def test_medal_aggregation(self):
        """Medals across multiple team stats are aggregated."""
        from src.data.sync.transformers import extract_medals

        player = _player_obj()
        player["PlayerTeamStats"].append(
            {
                "Stats": {
                    "CoreStats": {
                        "Kills": 0,
                        "Deaths": 0,
                        "Assists": 0,
                        "Medals": [{"NameId": 100, "Count": 2}],
                    }
                }
            }
        )
        mj = _match_json(players=[player])
        medals = extract_medals(mj, XUID)
        medal_100 = [m for m in medals if m.medal_name_id == 100]
        assert len(medal_100) == 1
        assert medal_100[0].count == 5  # 3 + 2


# ─────────────────────────────────────────────────────────────────────────────
# Tests extract_all_medals
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractAllMedals:
    def test_multiple_players(self):
        from src.data.sync.transformers import extract_all_medals

        p1 = _player_obj(xuid="1111111111111111", kills=5, deaths=3, assists=1)
        p2 = _player_obj(xuid="2222222222222222", kills=10, deaths=2, assists=5)
        mj = _match_json(players=[p1, p2])
        medals = extract_all_medals(mj)
        # Each player has 2 medals, total 4
        assert len(medals) >= 4
        xuids = {m.xuid for m in medals}
        assert "1111111111111111" in xuids
        assert "2222222222222222" in xuids

    def test_no_players(self):
        from src.data.sync.transformers import extract_all_medals

        mj = {"MatchId": "m1", "Players": []}
        assert extract_all_medals(mj) == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests extract_aliases
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractAliases:
    def test_normal(self):
        from src.data.sync.transformers import extract_aliases

        mj = _match_json(
            players=[
                _player_obj(xuid="1111111111111111", gamertag="Player1"),
                _player_obj(xuid="2222222222222222", gamertag="Player2"),
            ]
        )
        aliases = extract_aliases(mj)
        assert len(aliases) == 2
        xuids = {a.xuid for a in aliases}
        assert "1111111111111111" in xuids
        assert "2222222222222222" in xuids

    def test_deduplicate(self):
        from src.data.sync.transformers import extract_aliases

        mj = _match_json(
            players=[
                _player_obj(xuid="1111111111111111", gamertag="Player1"),
                _player_obj(xuid="1111111111111111", gamertag="Player1"),
            ]
        )
        aliases = extract_aliases(mj)
        assert len(aliases) == 1

    def test_no_players(self):
        from src.data.sync.transformers import extract_aliases

        mj = {"Players": "not_a_list"}
        assert extract_aliases(mj) == []

    def test_dict_player_id(self):
        from src.data.sync.transformers import extract_aliases

        mj = {
            "Players": [{"PlayerId": {"Xuid": "3333333333333333"}, "PlayerGamertag": "DictPlayer"}]
        }
        aliases = extract_aliases(mj)
        assert len(aliases) == 1
        assert aliases[0].xuid == "3333333333333333"
        assert aliases[0].gamertag == "DictPlayer"


# ─────────────────────────────────────────────────────────────────────────────
# Tests build_players_lookup
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildPlayersLookup:
    def test_normal(self):
        from src.data.sync.transformers import build_players_lookup

        mj = _match_json(
            players=[
                _player_obj(xuid="1111111111111111", gamertag="Alpha"),
                _player_obj(xuid="2222222222222222", gamertag="Bravo"),
            ]
        )
        lookup = build_players_lookup(mj)
        assert lookup["1111111111111111"] == "Alpha"
        assert lookup["2222222222222222"] == "Bravo"


# ─────────────────────────────────────────────────────────────────────────────
# Tests extract_killer_victim_pairs_from_highlight_events
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractKillerVictimPairs:
    def test_normal(self):
        from src.data.sync.transformers import extract_killer_victim_pairs_from_highlight_events

        events = [
            {
                "event_type": "Kill",
                "xuid": "1111111111111111",
                "gamertag": "Killer",
                "victim_xuid": "2222222222222222",
                "victim_gamertag": "Victim",
                "time_ms": 5000,
            },
        ]
        rows = extract_killer_victim_pairs_from_highlight_events(events, "m1")
        assert len(rows) == 1
        assert rows[0].killer_xuid == "1111111111111111"
        assert rows[0].victim_xuid == "2222222222222222"
        assert rows[0].time_ms == 5000

    def test_non_kill_events_ignored(self):
        from src.data.sync.transformers import extract_killer_victim_pairs_from_highlight_events

        events = [
            {
                "event_type": "Death",
                "xuid": "1111111111111111",
                "victim_xuid": "2222222222222222",
                "time_ms": 5000,
            },
        ]
        assert extract_killer_victim_pairs_from_highlight_events(events, "m1") == []

    def test_lookup_enrichment(self):
        from src.data.sync.transformers import extract_killer_victim_pairs_from_highlight_events

        events = [
            {
                "event_type": "Kill",
                "xuid": "1111111111111111",
                "victim_xuid": "2222222222222222",
                "time_ms": 5000,
            },
        ]
        lookup = {"1111111111111111": "Alpha", "2222222222222222": "Bravo"}
        rows = extract_killer_victim_pairs_from_highlight_events(
            events, "m1", players_lookup=lookup
        )
        assert rows[0].killer_gamertag == "Alpha"
        assert rows[0].victim_gamertag == "Bravo"

    def test_missing_xuid(self):
        from src.data.sync.transformers import extract_killer_victim_pairs_from_highlight_events

        events = [
            {
                "event_type": "Kill",
                "xuid": None,
                "victim_xuid": "2222222222222222",
                "time_ms": 5000,
            },
        ]
        assert extract_killer_victim_pairs_from_highlight_events(events, "m1") == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_xuid
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractXuid:
    def test_string_player_id(self):
        from src.data.sync.transformers import _extract_xuid

        assert _extract_xuid({"PlayerId": "xuid(12345678901234)"}) == "12345678901234"

    def test_dict_player_id(self):
        from src.data.sync.transformers import _extract_xuid

        assert _extract_xuid({"PlayerId": {"Xuid": "99999"}}) == "99999"

    def test_string_directly(self):
        from src.data.sync.transformers import _extract_xuid

        assert _extract_xuid("xuid(12345678901234)") == "12345678901234"

    def test_none(self):
        from src.data.sync.transformers import _extract_xuid

        assert _extract_xuid({}) is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests extract_personal_score_awards
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractPersonalScoreAwards:
    def test_normal(self):
        from src.data.sync.transformers import extract_personal_score_awards

        player = _player_obj()
        player["PlayerTeamStats"][0]["Stats"]["CoreStats"]["PersonalScores"] = [
            {"NameId": 1024030246, "Count": 7, "TotalPersonalScoreAwarded": 700},
            {"NameId": 1024069230, "Count": 3, "TotalPersonalScoreAwarded": 150},
        ]
        mj = _match_json(players=[player])
        awards = extract_personal_score_awards(mj, XUID)
        assert len(awards) == 2
        assert awards[0]["name_id"] == 1024030246
        assert awards[0]["count"] == 7
        assert awards[0]["total_score"] == 700

    def test_no_player(self):
        from src.data.sync.transformers import extract_personal_score_awards

        mj = _match_json()
        assert extract_personal_score_awards(mj, "unknown") == []

    def test_no_personal_scores(self):
        from src.data.sync.transformers import extract_personal_score_awards

        mj = _match_json()
        assert extract_personal_score_awards(mj, XUID) == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests categorize_personal_score
# ─────────────────────────────────────────────────────────────────────────────


class TestCategorizePersonalScore:
    def test_kill_score(self):
        from src.data.domain.refdata import KILL_SCORES
        from src.data.sync.transformers import categorize_personal_score

        if KILL_SCORES:
            score_id = next(iter(KILL_SCORES))
            assert categorize_personal_score(score_id) == "kill"

    def test_assist_score(self):
        from src.data.domain.refdata import ASSIST_SCORES
        from src.data.sync.transformers import categorize_personal_score

        if ASSIST_SCORES:
            score_id = next(iter(ASSIST_SCORES))
            assert categorize_personal_score(score_id) == "assist"

    def test_objective_score(self):
        from src.data.domain.refdata import ASSIST_SCORES, KILL_SCORES, OBJECTIVE_SCORES
        from src.data.sync.transformers import categorize_personal_score

        # Find an objective score that is NOT also in assist or kill
        pure_obj = [s for s in OBJECTIVE_SCORES if s not in ASSIST_SCORES and s not in KILL_SCORES]
        if pure_obj:
            assert categorize_personal_score(pure_obj[0]) == "objective"

    def test_vehicle_score(self):
        from src.data.domain.refdata import VEHICLE_DESTRUCTION_SCORES
        from src.data.sync.transformers import categorize_personal_score

        if VEHICLE_DESTRUCTION_SCORES:
            score_id = next(iter(VEHICLE_DESTRUCTION_SCORES))
            assert categorize_personal_score(score_id) == "vehicle"

    def test_penalty_score(self):
        from src.data.domain.refdata import PENALTY_SCORES
        from src.data.sync.transformers import categorize_personal_score

        if PENALTY_SCORES:
            score_id = next(iter(PENALTY_SCORES))
            assert categorize_personal_score(score_id) == "penalty"

    def test_unknown_score(self):
        from src.data.sync.transformers import categorize_personal_score

        assert categorize_personal_score(999999999) == "other"


# ─────────────────────────────────────────────────────────────────────────────
# Tests transform_personal_score_awards
# ─────────────────────────────────────────────────────────────────────────────


class TestTransformPersonalScoreAwards:
    def test_normal(self):
        from src.data.sync.transformers import transform_personal_score_awards

        ps = [
            {"name_id": 1024030246, "count": 7, "total_score": 700},
        ]
        rows = transform_personal_score_awards("m1", "xuid1", ps)
        assert len(rows) == 1
        assert rows[0].match_id == "m1"
        assert rows[0].xuid == "xuid1"
        assert rows[0].award_count == 7
        assert rows[0].award_score == 700

    def test_empty(self):
        from src.data.sync.transformers import transform_personal_score_awards

        assert transform_personal_score_awards("m1", "xuid1", []) == []

    def test_missing_name_id(self):
        from src.data.sync.transformers import transform_personal_score_awards

        ps = [{"count": 1, "total_score": 100}]
        assert transform_personal_score_awards("m1", "xuid1", ps) == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests _find_personal_scores
# ─────────────────────────────────────────────────────────────────────────────


class TestFindPersonalScores:
    def test_found(self):
        from src.data.sync.transformers import _find_personal_scores

        player = {
            "PlayerTeamStats": [
                {
                    "Stats": {
                        "CoreStats": {
                            "PersonalScores": [
                                {"NameId": 1, "Count": 5},
                            ]
                        }
                    }
                }
            ]
        }
        result = _find_personal_scores(player)
        assert len(result) == 1
        assert result[0]["NameId"] == 1

    def test_not_found(self):
        from src.data.sync.transformers import _find_personal_scores

        assert _find_personal_scores({}) == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests transform_match_stats (intégration)
# ─────────────────────────────────────────────────────────────────────────────


class TestTransformMatchStats:
    def test_full_transform(self):
        from src.data.sync.transformers import transform_match_stats

        mj = _match_json()
        result = transform_match_stats(mj, XUID)
        assert result is not None
        assert result.match_id == MATCH_ID
        assert result.kills == 10
        assert result.deaths == 5
        assert result.assists == 3
        assert result.playlist_name == "Arena: Slayer"
        assert result.map_name == "Aquarius"
        assert result.my_team_score == 50
        assert result.enemy_team_score == 45

    def test_no_match_id(self):
        from src.data.sync.transformers import transform_match_stats

        mj = _match_json()
        del mj["MatchId"]
        assert transform_match_stats(mj, XUID) is None

    def test_no_match_info(self):
        from src.data.sync.transformers import transform_match_stats

        mj = {"MatchId": "m1"}
        assert transform_match_stats(mj, XUID) is None

    def test_no_start_time(self):
        from src.data.sync.transformers import transform_match_stats

        mj = _match_json(start_time=None)
        mj["MatchInfo"]["StartTime"] = None
        assert transform_match_stats(mj, XUID) is None

    def test_player_not_found(self):
        from src.data.sync.transformers import transform_match_stats

        mj = _match_json()
        assert transform_match_stats(mj, "unknown") is None

    def test_with_metadata_resolver(self):
        from src.data.sync.transformers import transform_match_stats

        # Use UUID as name → resolver should replace it
        mj = _match_json(
            playlist_name="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            map_name="a1b2c3d4-e5f6-7890-abcd-ef1234567891",
        )

        def resolver(asset_type, asset_id):
            if asset_type == "playlist":
                return "Resolved Playlist"
            if asset_type == "map":
                return "Resolved Map"
            return None

        result = transform_match_stats(mj, XUID, metadata_resolver=resolver)
        assert result is not None
        assert result.playlist_name == "Resolved Playlist"
        assert result.map_name == "Resolved Map"

    def test_left_early(self):
        from src.data.sync.transformers import transform_match_stats

        player = _player_obj(outcome=4)  # DidNotFinish
        mj = _match_json(players=[player])
        result = transform_match_stats(mj, XUID)
        assert result is not None
        assert result.left_early is True

    def test_end_time_computed(self):
        from src.data.sync.transformers import transform_match_stats

        mj = _match_json()
        result = transform_match_stats(mj, XUID)
        assert result is not None
        assert result.end_time is not None

    def test_with_skill_json(self):
        from src.data.sync.transformers import transform_match_stats

        skill = {
            "Value": [
                {
                    "Id": f"xuid({XUID})",
                    "Result": {
                        "TeamId": 0,
                        "TeamMmr": 1250.0,
                        "TeamMmrs": {"0": 1250.0, "1": 1100.0},
                    },
                }
            ]
        }
        mj = _match_json()
        result = transform_match_stats(mj, XUID, skill_json=skill)
        assert result is not None
        assert result.team_mmr == pytest.approx(1250.0)
        assert result.enemy_mmr == pytest.approx(1100.0)


# ─────────────────────────────────────────────────────────────────────────────
# Tests transform_skill_stats
# ─────────────────────────────────────────────────────────────────────────────


class TestTransformSkillStats:
    def test_normal(self):
        from src.data.sync.transformers import transform_skill_stats

        skill = {
            "Value": [
                {
                    "Id": f"xuid({XUID})",
                    "Result": {
                        "TeamId": 0,
                        "TeamMmr": 1200.0,
                        "StatPerformances": {
                            "Kills": {"Expected": 10.5, "StdDev": 2.1},
                            "Deaths": {"Expected": 8.0, "StdDev": 1.5},
                            "Assists": {"Expected": 3.0, "StdDev": 1.0},
                        },
                    },
                }
            ]
        }
        result = transform_skill_stats(skill, MATCH_ID, XUID)
        assert result is not None
        assert result.match_id == MATCH_ID
        assert result.xuid == XUID
        assert result.team_mmr == pytest.approx(1200.0)
        assert result.kills_expected == pytest.approx(10.5)
        assert result.deaths_expected == pytest.approx(8.0)
        assert result.assists_expected == pytest.approx(3.0)

    def test_player_not_found(self):
        from src.data.sync.transformers import transform_skill_stats

        skill = {"Value": [{"Id": "xuid(999)", "Result": {"TeamMmr": 1200}}]}
        assert transform_skill_stats(skill, MATCH_ID, XUID) is None

    def test_no_value(self):
        from src.data.sync.transformers import transform_skill_stats

        assert transform_skill_stats({}, MATCH_ID, XUID) is None

    def test_no_result(self):
        from src.data.sync.transformers import transform_skill_stats

        skill = {"Value": [{"Id": f"xuid({XUID})"}]}
        assert transform_skill_stats(skill, MATCH_ID, XUID) is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests transform_highlight_events
# ─────────────────────────────────────────────────────────────────────────────


class TestTransformHighlightEvents:
    def test_dict_events(self):
        from src.data.sync.transformers import transform_highlight_events

        events = [
            {"event_type": "Kill", "time_ms": 5000, "xuid": "111", "gamertag": "P1"},
            {"event_type": "Death", "time_ms": 6000, "xuid": "222", "gamertag": "P2"},
        ]
        rows = transform_highlight_events(events, "m1")
        assert len(rows) == 2
        assert rows[0].event_type == "Kill"
        assert rows[0].time_ms == 5000
        assert rows[1].event_type == "Death"

    def test_skip_invalid(self):
        from src.data.sync.transformers import transform_highlight_events

        events = [
            {"event_type": None},  # should be skipped
            42,  # should be skipped
        ]
        assert transform_highlight_events(events, "m1") == []

    def test_empty(self):
        from src.data.sync.transformers import transform_highlight_events

        assert transform_highlight_events([], "m1") == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests compute_teammates_signature
# ─────────────────────────────────────────────────────────────────────────────


class TestComputeTeammatesSignature:
    def test_normal(self):
        from src.data.sync.transformers import compute_teammates_signature

        mj = _match_json(
            players=[
                _player_obj(xuid=XUID, team_id=0),
                _player_obj(xuid="2222222222222222", team_id=0),
                _player_obj(xuid="3333333333333333", team_id=0),
                _player_obj(xuid="4444444444444444", team_id=1),
            ]
        )
        sig = compute_teammates_signature(mj, XUID, 0)
        assert sig is not None
        assert "2222222222222222" in sig
        assert "3333333333333333" in sig
        assert "4444444444444444" not in sig

    def test_no_teammates(self):
        from src.data.sync.transformers import compute_teammates_signature

        mj = _match_json(players=[_player_obj(xuid=XUID, team_id=0)])
        sig = compute_teammates_signature(mj, XUID, 0)
        assert sig is None

    def test_no_team_id(self):
        from src.data.sync.transformers import compute_teammates_signature

        mj = _match_json()
        sig = compute_teammates_signature(mj, XUID, None)
        assert sig is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests extract_xuids_from_match
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractXuidsFromMatch:
    def test_normal(self):
        from src.data.sync.transformers import extract_xuids_from_match

        mj = _match_json(
            players=[
                _player_obj(xuid="1234567890123456"),
                _player_obj(xuid="9876543210987654"),
            ]
        )
        xuids = extract_xuids_from_match(mj)
        assert 1234567890123456 in xuids
        assert 9876543210987654 in xuids

    def test_no_players(self):
        from src.data.sync.transformers import extract_xuids_from_match

        assert extract_xuids_from_match({"Players": "bad"}) == []

    def test_dict_player_id(self):
        from src.data.sync.transformers import extract_xuids_from_match

        mj = {"Players": [{"PlayerId": {"Xuid": 5555555555555555}}]}
        xuids = extract_xuids_from_match(mj)
        assert 5555555555555555 in xuids

    def test_dedup(self):
        from src.data.sync.transformers import extract_xuids_from_match

        mj = _match_json(
            players=[
                _player_obj(xuid="1234567890123456"),
                _player_obj(xuid="1234567890123456"),
            ]
        )
        xuids = extract_xuids_from_match(mj)
        assert len(xuids) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Tests extract_participants
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractParticipants:
    def test_normal(self):
        from src.data.sync.transformers import extract_participants

        mj = _match_json(
            players=[
                _player_obj(xuid="1111111111111111", gamertag="Alpha", rank=1, score=1500),
                _player_obj(xuid="2222222222222222", gamertag="Bravo", rank=2, score=1200),
            ]
        )
        rows = extract_participants(mj)
        assert len(rows) == 2
        assert rows[0].score >= rows[1].score  # sorted by score desc

    def test_no_match_id(self):
        from src.data.sync.transformers import extract_participants

        assert extract_participants({"Players": []}) == []

    def test_auto_rank(self):
        """Rank is auto-assigned if not from API."""
        from src.data.sync.transformers import extract_participants

        p1 = _player_obj(xuid="1111111111111111", score=2000)
        p1["Rank"] = None  # No API rank
        p2 = _player_obj(xuid="2222222222222222", score=1000)
        p2["Rank"] = None
        mj = _match_json(players=[p1, p2])
        rows = extract_participants(mj)
        assert rows[0].rank == 1
        assert rows[1].rank == 2

    def test_dedup_xuids(self):
        from src.data.sync.transformers import extract_participants

        mj = _match_json(
            players=[
                _player_obj(xuid="1111111111111111"),
                _player_obj(xuid="1111111111111111"),
            ]
        )
        rows = extract_participants(mj)
        assert len(rows) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Tests extract_game_variant_category
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractGameVariantCategory:
    def test_direct(self):
        from src.data.sync.transformers import extract_game_variant_category

        mj = {"MatchInfo": {"GameVariantCategory": 6}}
        assert extract_game_variant_category(mj) == 6

    def test_ugc_fallback(self):
        from src.data.sync.transformers import extract_game_variant_category

        mj = {"MatchInfo": {"UgcGameVariant": {"Category": 15}}}
        assert extract_game_variant_category(mj) == 15

    def test_none(self):
        from src.data.sync.transformers import extract_game_variant_category

        assert extract_game_variant_category({"MatchInfo": {}}) is None

    def test_no_match_info(self):
        from src.data.sync.transformers import extract_game_variant_category

        assert extract_game_variant_category({}) is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests extract_match_registry_data (v5)
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractMatchRegistryData:
    def test_normal(self):
        from src.data.sync.transformers import extract_match_registry_data

        mj = _match_json()
        result = extract_match_registry_data(mj)
        assert result is not None
        assert result["match_id"] == MATCH_ID
        assert result["playlist_name"] == "Arena: Slayer"
        assert result["map_name"] == "Aquarius"
        assert result["duration_seconds"] == 630

    def test_no_match_id(self):
        from src.data.sync.transformers import extract_match_registry_data

        assert extract_match_registry_data({"MatchInfo": {}}) is None

    def test_no_start_time(self):
        from src.data.sync.transformers import extract_match_registry_data

        mj = _match_json()
        mj["MatchInfo"]["StartTime"] = None
        assert extract_match_registry_data(mj) is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _extract_team_scores_by_id
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractTeamScoresById:
    def test_normal(self):
        from src.data.sync.transformers import _extract_team_scores_by_id

        match = {
            "Teams": [
                {"TeamId": 0, "TotalPoints": 50},
                {"TeamId": 1, "TotalPoints": 45},
            ]
        }
        t0, t1 = _extract_team_scores_by_id(match)
        assert t0 == 50
        assert t1 == 45

    def test_no_teams(self):
        from src.data.sync.transformers import _extract_team_scores_by_id

        t0, t1 = _extract_team_scores_by_id({})
        assert t0 is None
        assert t1 is None

    def test_single_team(self):
        from src.data.sync.transformers import _extract_team_scores_by_id

        match = {"Teams": [{"TeamId": 0, "TotalPoints": 50}]}
        t0, t1 = _extract_team_scores_by_id(match)
        assert t0 == 50
        assert t1 is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _safe_float / _safe_int (helpers déjà testés mais couverture complète)
# ─────────────────────────────────────────────────────────────────────────────


class TestSafeHelpers:
    def test_safe_float_nan(self):
        from src.data.sync.transformers import _safe_float

        assert _safe_float(float("nan")) is None

    def test_safe_float_inf(self):
        from src.data.sync.transformers import _safe_float

        assert _safe_float(float("inf")) is None

    def test_safe_float_string(self):
        from src.data.sync.transformers import _safe_float

        assert _safe_float("3.14") == pytest.approx(3.14)

    def test_safe_float_invalid_string(self):
        from src.data.sync.transformers import _safe_float

        assert _safe_float("not_a_number") is None

    def test_safe_int_nan(self):
        from src.data.sync.transformers import _safe_int

        assert _safe_int(float("nan")) is None

    def test_safe_int_inf(self):
        from src.data.sync.transformers import _safe_int

        assert _safe_int(float("inf")) is None

    def test_safe_int_float_value(self):
        from src.data.sync.transformers import _safe_int

        assert _safe_int(3.7) == 3

    def test_safe_int_string(self):
        from src.data.sync.transformers import _safe_int

        assert _safe_int("42") == 42

    def test_safe_int_invalid_string(self):
        from src.data.sync.transformers import _safe_int

        assert _safe_int("abc") is None

    def test_safe_float_none(self):
        from src.data.sync.transformers import _safe_float

        assert _safe_float(None) is None

    def test_safe_int_none(self):
        from src.data.sync.transformers import _safe_int

        assert _safe_int(None) is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _parse_iso_utc
# ─────────────────────────────────────────────────────────────────────────────


class TestParseIsoUtc:
    def test_z_suffix(self):
        from src.data.sync.transformers import _parse_iso_utc

        result = _parse_iso_utc("2024-01-15T10:00:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1

    def test_offset(self):
        from src.data.sync.transformers import _parse_iso_utc

        result = _parse_iso_utc("2024-01-15T10:00:00+00:00")
        assert result is not None

    def test_none(self):
        from src.data.sync.transformers import _parse_iso_utc

        assert _parse_iso_utc(None) is None

    def test_empty(self):
        from src.data.sync.transformers import _parse_iso_utc

        assert _parse_iso_utc("") is None

    def test_invalid(self):
        from src.data.sync.transformers import _parse_iso_utc

        assert _parse_iso_utc("not a date") is None

    def test_int_value(self):
        from src.data.sync.transformers import _parse_iso_utc

        assert _parse_iso_utc(12345) is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests _determine_mode_category
# ─────────────────────────────────────────────────────────────────────────────


class TestDetermineModeCategory:
    def test_returns_string(self):
        from src.data.sync.transformers import _determine_mode_category

        result = _determine_mode_category("Arena:Slayer on Aquarius")
        assert isinstance(result, str)

    def test_none_returns_other(self):
        from src.data.sync.transformers import _determine_mode_category

        result = _determine_mode_category(None)
        assert result == "Other"
