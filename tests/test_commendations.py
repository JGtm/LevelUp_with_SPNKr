"""Tests pour src/ui/commendations.py — fonctions pures de traitement des citations."""

from __future__ import annotations

from src.ui.commendations import (
    _compute_mastery_display,
    _display_citation_desc,
    _display_citation_name,
    _image_basename_from_item,
    _looks_english,
    _normalize_name,
    _prefer_parenthetical_fr,
)

# ============================================================================
# _normalize_name
# ============================================================================


class TestNormalizeName:
    def test_basic(self):
        assert _normalize_name("Hello World") == "hello world"

    def test_accents(self):
        # Les accents doivent être supprimés
        result = _normalize_name("Récompensé")
        assert "e" in result  # é → e
        assert "é" not in result

    def test_strip_whitespace(self):
        assert _normalize_name("  hello  ") == "hello"

    def test_multiple_spaces(self):
        assert _normalize_name("hello   world") == "hello world"

    def test_none(self):
        assert _normalize_name(None) == ""

    def test_empty(self):
        assert _normalize_name("") == ""

    def test_mixed_accents(self):
        result = _normalize_name("Tête-à-tête")
        assert result == "tete-a-tete"


# ============================================================================
# _looks_english
# ============================================================================


class TestLooksEnglish:
    def test_english_with_the(self):
        assert _looks_english("Kill the enemy") is True

    def test_english_with_kill(self):
        assert _looks_english("Get 10 kills") is True

    def test_english_with_match(self):
        assert _looks_english("Win a match") is True

    def test_english_with_assists(self):
        assert _looks_english("Earn 5 assists") is True

    def test_french_text(self):
        assert _looks_english("Obtenir 5 médailles") is False

    def test_empty(self):
        assert _looks_english("") is False

    def test_none(self):
        assert _looks_english(None) is False

    def test_short_no_keyword(self):
        assert _looks_english("xyz") is False

    def test_headshots(self):
        assert _looks_english("Get 10 headshots") is True

    def test_capture(self):
        assert _looks_english("Capture the flag") is True


# ============================================================================
# _prefer_parenthetical_fr
# ============================================================================


class TestPreferParentheticalFr:
    def test_english_with_french_parens(self):
        result = _prefer_parenthetical_fr("Kill 10 enemies (Tuer 10 ennemis)")
        assert result == "Tuer 10 ennemis"

    def test_french_text_unchanged(self):
        result = _prefer_parenthetical_fr("Obtenir 5 médailles")
        assert result == "Obtenir 5 médailles"

    def test_no_parens(self):
        result = _prefer_parenthetical_fr("Simple text")
        assert result == "Simple text"

    def test_empty(self):
        assert _prefer_parenthetical_fr("") == ""

    def test_none(self):
        assert _prefer_parenthetical_fr(None) == ""

    def test_obtener_correction(self):
        # Le code corrige "Obtener" → "Obtenir"
        result = _prefer_parenthetical_fr("Kill something (Obtener des médailles)")
        assert "Obtenir" in result


# ============================================================================
# _display_citation_name
# ============================================================================


class TestDisplayCitationName:
    def test_unknown_name(self):
        # Un nom inconnu est retourné tel quel
        assert _display_citation_name("Unknown Citation") == "Unknown Citation"

    def test_empty(self):
        assert _display_citation_name("") == ""

    def test_none(self):
        assert _display_citation_name(None) == ""


# ============================================================================
# _display_citation_desc
# ============================================================================


class TestDisplayCitationDesc:
    def test_french_desc(self):
        result = _display_citation_desc("Texte en français")
        assert result == "Texte en français"

    def test_english_with_parens(self):
        result = _display_citation_desc("Kill 10 enemies (Tuer 10 ennemis)")
        assert result == "Tuer 10 ennemis"

    def test_empty(self):
        assert _display_citation_desc("") == ""

    def test_none(self):
        assert _display_citation_desc(None) == ""


# ============================================================================
# _compute_mastery_display
# ============================================================================


class TestComputeMasteryDisplay:
    def test_master_achieved(self):
        tiers = [{"target_count": 10}, {"target_count": 50}, {"target_count": 100}]
        label, counter, is_master, ratio = _compute_mastery_display(150, tiers)
        assert label == "Maître"
        assert is_master is True
        assert ratio == 1.0
        assert "150" in counter

    def test_exactly_at_master(self):
        tiers = [{"target_count": 10}, {"target_count": 100}]
        label, counter, is_master, ratio = _compute_mastery_display(100, tiers)
        assert label == "Maître"
        assert is_master is True

    def test_level_1(self):
        tiers = [{"target_count": 10}, {"target_count": 50}]
        label, counter, is_master, ratio = _compute_mastery_display(5, tiers)
        assert label == "Niveau 1"
        assert is_master is False
        assert "5/10" in counter
        assert 0.0 <= ratio <= 1.0

    def test_level_2(self):
        tiers = [{"target_count": 10}, {"target_count": 50}]
        label, counter, is_master, ratio = _compute_mastery_display(30, tiers)
        assert label == "Niveau 2"
        assert is_master is False
        assert "30/50" in counter

    def test_no_tiers(self):
        label, counter, is_master, ratio = _compute_mastery_display(10, [])
        assert label == "—"
        assert is_master is False
        assert ratio == 0.0

    def test_zero_count(self):
        tiers = [{"target_count": 10}]
        label, counter, is_master, ratio = _compute_mastery_display(0, tiers)
        assert label == "Niveau 1"
        assert ratio == 0.0

    def test_negative_count(self):
        tiers = [{"target_count": 10}]
        label, counter, is_master, ratio = _compute_mastery_display(-5, tiers)
        assert ratio == 0.0

    def test_invalid_tier_values(self):
        tiers = [{"target_count": "invalid"}, {"target_count": None}]
        label, counter, is_master, ratio = _compute_mastery_display(10, tiers)
        assert label == "—"  # No valid tiers

    def test_duplicate_tiers(self):
        tiers = [{"target_count": 10}, {"target_count": 10}, {"target_count": 50}]
        label, counter, is_master, ratio = _compute_mastery_display(5, tiers)
        assert label == "Niveau 1"

    def test_progress_ratio_midway(self):
        tiers = [{"target_count": 100}]
        _, _, _, ratio = _compute_mastery_display(50, tiers)
        assert abs(ratio - 0.5) < 0.01


# ============================================================================
# _image_basename_from_item
# ============================================================================


class TestImageBasenameFromItem:
    def test_image_path(self):
        result = _image_basename_from_item({"image_path": "path/to/icon.png"})
        assert result == "icon.png"

    def test_image_url(self):
        result = _image_basename_from_item({"image_url": "https://example.com/medal.png"})
        assert result == "medal.png"

    def test_image_file(self):
        result = _image_basename_from_item({"image_file": "images\\medal.png"})
        assert result == "medal.png"

    def test_no_image(self):
        assert _image_basename_from_item({}) is None

    def test_empty_values(self):
        assert _image_basename_from_item({"image_path": "", "image_url": ""}) is None

    def test_priority_order(self):
        """image_path a la priorité sur image_url."""
        result = _image_basename_from_item({"image_path": "a.png", "image_url": "b.png"})
        assert result == "a.png"
