"""Tests unitaires Sprint 2 : Transformers Refdata et GameVariantCategory.

Ce module teste :
- Extraction de GameVariantCategory dans transform_match_stats()
- Intégration des fonctions refdata dans le pipeline de transformation
- Fallbacks et cas limites
"""

from __future__ import annotations

import pytest

from src.data.domain.refdata import (
    GameVariantCategory,
    PersonalScoreNameId,
)
from src.data.sync.transformers import (
    extract_game_variant_category,
    extract_personal_score_awards,
    transform_match_stats,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def slayer_match_json():
    """JSON de match Slayer (GameVariantCategory=6)."""
    return {
        "MatchId": "slayer-match-001",
        "MatchInfo": {
            "StartTime": "2026-02-03T10:00:00Z",
            "GameVariantCategory": 6,  # Slayer
            "Playlist": {"AssetId": "playlist-1", "PublicName": "Arena: Slayer"},
            "MapVariant": {"AssetId": "map-1", "PublicName": "Aquarius"},
            "UgcGameVariant": {"AssetId": "mode-1", "PublicName": "Slayer"},
            "PlaylistMapModePair": {"AssetId": "pair-1", "PublicName": "Arena:Slayer on Aquarius"},
        },
        "Players": [
            {
                "PlayerId": "xuid(2533274792546123)",
                "PlayerGamertag": "TestPlayer",
                "LastTeamId": 0,
                "Outcome": 2,  # Win
                "Rank": 1,
                "PlayerTeamStats": [
                    {
                        "Stats": {
                            "CoreStats": {
                                "Kills": 15,
                                "Deaths": 8,
                                "Assists": 5,
                                "KDA": 2.5,
                                "Accuracy": 45.0,
                                "HeadshotKills": 7,
                                "MaxKillingSpree": 5,
                            }
                        }
                    }
                ],
            }
        ],
    }


@pytest.fixture
def ctf_match_json():
    """JSON de match CTF (GameVariantCategory=15)."""
    return {
        "MatchId": "ctf-match-001",
        "MatchInfo": {
            "StartTime": "2026-02-03T11:00:00Z",
            "GameVariantCategory": 15,  # CTF
            "Playlist": {"AssetId": "playlist-2", "PublicName": "CTF"},
            "MapVariant": {"AssetId": "map-2", "PublicName": "Bazaar"},
            "UgcGameVariant": {"AssetId": "mode-2", "PublicName": "Capture The Flag"},
        },
        "Players": [
            {
                "PlayerId": "xuid(2533274792546123)",
                "PlayerGamertag": "TestPlayer",
                "LastTeamId": 0,
                "Outcome": 3,  # Loss
                "Rank": 3,
                "PlayerTeamStats": [
                    {
                        "Stats": {
                            "CoreStats": {
                                "Kills": 10,
                                "Deaths": 12,
                                "Assists": 8,
                                "KDA": 1.0,
                                "Accuracy": 38.0,
                                "PersonalScores": [
                                    {"NameId": PersonalScoreNameId.KILLED_PLAYER, "Count": 10},
                                    {"NameId": PersonalScoreNameId.FLAG_CAPTURED, "Count": 1},
                                    {"NameId": PersonalScoreNameId.FLAG_RETURNED, "Count": 3},
                                ],
                            }
                        }
                    }
                ],
            }
        ],
    }


@pytest.fixture
def oddball_match_json():
    """JSON de match Oddball (GameVariantCategory=18)."""
    return {
        "MatchId": "oddball-match-001",
        "MatchInfo": {
            "StartTime": "2026-02-03T12:00:00Z",
            "GameVariantCategory": 18,  # Oddball
            "Playlist": {"AssetId": "playlist-3", "PublicName": "Oddball"},
            "MapVariant": {"AssetId": "map-3", "PublicName": "Streets"},
        },
        "Players": [
            {
                "PlayerId": "xuid(2533274792546123)",
                "PlayerGamertag": "TestPlayer",
                "LastTeamId": 0,
                "Outcome": 2,
                "Rank": 2,
                "PlayerTeamStats": [
                    {
                        "Stats": {
                            "CoreStats": {
                                "Kills": 8,
                                "Deaths": 10,
                                "Assists": 2,
                            }
                        }
                    }
                ],
            }
        ],
    }


@pytest.fixture
def match_without_category():
    """JSON de match sans GameVariantCategory (fallback)."""
    return {
        "MatchId": "no-category-match-001",
        "MatchInfo": {
            "StartTime": "2026-02-03T13:00:00Z",
            # Pas de GameVariantCategory
            "Playlist": {"AssetId": "playlist-custom", "PublicName": "Custom Game"},
            "MapVariant": {"AssetId": "map-custom", "PublicName": "Forge Map"},
            "UgcGameVariant": {
                "AssetId": "mode-custom",
                "PublicName": "Custom Mode",
                "Category": 6,  # Fallback dans UgcGameVariant
            },
        },
        "Players": [
            {
                "PlayerId": "xuid(2533274792546123)",
                "PlayerGamertag": "TestPlayer",
                "LastTeamId": 0,
                "Outcome": 1,
                "PlayerTeamStats": [
                    {
                        "Stats": {
                            "CoreStats": {
                                "Kills": 5,
                                "Deaths": 5,
                                "Assists": 0,
                            }
                        }
                    }
                ],
            }
        ],
    }


# =============================================================================
# Tests extract_game_variant_category
# =============================================================================


class TestExtractGameVariantCategory:
    """Tests de la fonction extract_game_variant_category."""

    def test_extract_slayer_category(self, slayer_match_json):
        """Test extraction catégorie Slayer (6)."""
        category = extract_game_variant_category(slayer_match_json)
        assert category == GameVariantCategory.SLAYER
        assert category == 6

    def test_extract_ctf_category(self, ctf_match_json):
        """Test extraction catégorie CTF (15)."""
        category = extract_game_variant_category(ctf_match_json)
        assert category == GameVariantCategory.CAPTURE_THE_FLAG
        assert category == 15

    def test_extract_oddball_category(self, oddball_match_json):
        """Test extraction catégorie Oddball (18)."""
        category = extract_game_variant_category(oddball_match_json)
        assert category == GameVariantCategory.ODDBALL
        assert category == 18

    def test_fallback_to_ugc_variant(self, match_without_category):
        """Test fallback vers UgcGameVariant.Category."""
        category = extract_game_variant_category(match_without_category)
        assert category == 6  # Depuis UgcGameVariant.Category

    def test_missing_category_returns_none(self):
        """Test catégorie manquante retourne None."""
        match_json = {
            "MatchId": "test",
            "MatchInfo": {
                "Playlist": {"AssetId": "test"},
            },
        }
        category = extract_game_variant_category(match_json)
        assert category is None

    def test_invalid_match_info_returns_none(self):
        """Test MatchInfo invalide retourne None."""
        category = extract_game_variant_category({"MatchId": "test"})
        assert category is None

    def test_empty_json_returns_none(self):
        """Test JSON vide retourne None."""
        category = extract_game_variant_category({})
        assert category is None


# =============================================================================
# Tests transform_match_stats avec game_variant_category
# =============================================================================


class TestTransformMatchStatsWithCategory:
    """Tests de transform_match_stats avec game_variant_category."""

    def test_slayer_match_has_category(self, slayer_match_json):
        """Test match Slayer contient game_variant_category=6."""
        row = transform_match_stats(slayer_match_json, "2533274792546123")

        assert row is not None
        assert row.game_variant_category == 6
        assert row.match_id == "slayer-match-001"
        assert row.kills == 15
        assert row.deaths == 8

    def test_ctf_match_has_category(self, ctf_match_json):
        """Test match CTF contient game_variant_category=15."""
        row = transform_match_stats(ctf_match_json, "2533274792546123")

        assert row is not None
        assert row.game_variant_category == 15
        assert row.match_id == "ctf-match-001"

    def test_oddball_match_has_category(self, oddball_match_json):
        """Test match Oddball contient game_variant_category=18."""
        row = transform_match_stats(oddball_match_json, "2533274792546123")

        assert row is not None
        assert row.game_variant_category == 18

    def test_match_without_category_uses_fallback(self, match_without_category):
        """Test match sans catégorie directe utilise le fallback."""
        row = transform_match_stats(match_without_category, "2533274792546123")

        assert row is not None
        # Fallback depuis UgcGameVariant.Category
        assert row.game_variant_category == 6

    def test_category_independent_of_mode_category(self, slayer_match_json):
        """Test game_variant_category est indépendant de mode_category."""
        row = transform_match_stats(slayer_match_json, "2533274792546123")

        assert row is not None
        # game_variant_category vient de l'API (int)
        assert row.game_variant_category == 6
        # mode_category vient de notre logique (str)
        assert row.mode_category is not None  # Calculé depuis pair_name


# =============================================================================
# Tests extract_personal_score_awards
# =============================================================================


class TestExtractPersonalScoreAwards:
    """Tests de la fonction extract_personal_score_awards."""

    def test_extract_ctf_awards(self, ctf_match_json):
        """Test extraction des awards CTF."""
        awards = extract_personal_score_awards(ctf_match_json, "2533274792546123")

        assert len(awards) == 3

        # Vérifier les types d'awards
        award_ids = {a.award_name_id for a in awards}
        assert PersonalScoreNameId.KILLED_PLAYER in award_ids
        assert PersonalScoreNameId.FLAG_CAPTURED in award_ids
        assert PersonalScoreNameId.FLAG_RETURNED in award_ids

    def test_extract_awards_with_points(self, ctf_match_json):
        """Test extraction des points calculés."""
        awards = extract_personal_score_awards(ctf_match_json, "2533274792546123")

        # FLAG_CAPTURED = 300 points × 1 = 300
        flag_capture = next(
            a for a in awards if a.award_name_id == PersonalScoreNameId.FLAG_CAPTURED
        )
        assert flag_capture.count == 1
        assert flag_capture.total_points == 300

        # FLAG_RETURNED = 100 points × 3 = 300
        flag_return = next(
            a for a in awards if a.award_name_id == PersonalScoreNameId.FLAG_RETURNED
        )
        assert flag_return.count == 3
        assert flag_return.total_points == 300

    def test_no_awards_for_slayer(self, slayer_match_json):
        """Test pas d'awards si pas de PersonalScores dans le JSON."""
        awards = extract_personal_score_awards(slayer_match_json, "2533274792546123")
        # Le fixture slayer_match_json n'a pas de PersonalScores
        assert awards == []

    def test_no_awards_for_unknown_player(self, ctf_match_json):
        """Test pas d'awards pour joueur inconnu."""
        awards = extract_personal_score_awards(ctf_match_json, "unknown-xuid")
        assert awards == []


# =============================================================================
# Tests GameVariantCategory enum
# =============================================================================


class TestGameVariantCategoryEnum:
    """Tests de l'enum GameVariantCategory."""

    def test_common_categories(self):
        """Test valeurs des catégories communes."""
        assert GameVariantCategory.SLAYER == 6
        assert GameVariantCategory.CAPTURE_THE_FLAG == 15
        assert GameVariantCategory.ODDBALL == 18
        assert GameVariantCategory.STRONGHOLDS == 22
        assert GameVariantCategory.FIREFIGHT_PVE == 27

    def test_category_from_value(self):
        """Test création depuis valeur."""
        cat = GameVariantCategory(6)
        assert cat == GameVariantCategory.SLAYER
        assert cat.name == "SLAYER"

    def test_invalid_category(self):
        """Test catégorie invalide lève ValueError."""
        with pytest.raises(ValueError):
            GameVariantCategory(9999)


# =============================================================================
# Tests intégration complète
# =============================================================================


class TestRefDataIntegration:
    """Tests d'intégration refdata."""

    def test_full_pipeline_ctf_match(self, ctf_match_json):
        """Test pipeline complet pour un match CTF."""
        xuid = "2533274792546123"

        # 1. Transformer le match
        row = transform_match_stats(ctf_match_json, xuid)
        assert row is not None
        assert row.game_variant_category == 15  # CTF

        # 2. Extraire les awards
        awards = extract_personal_score_awards(ctf_match_json, xuid)
        assert len(awards) == 3

        # 3. Vérifier la cohérence
        total_points = sum(a.total_points for a in awards)
        assert total_points > 0

        # 4. Vérifier les kills
        kills_award = next(
            (a for a in awards if a.award_name_id == PersonalScoreNameId.KILLED_PLAYER), None
        )
        assert kills_award is not None
        assert kills_award.count == row.kills
