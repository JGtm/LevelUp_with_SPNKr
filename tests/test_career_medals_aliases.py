"""Tests pour src/ui/career_ranks.py, src/ui/medals.py et src/ui/aliases.py."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

# ============================================================================
# career_ranks.py
# ============================================================================
from src.ui.career_ranks import (
    CareerRankInfo,
    format_career_rank_label_fr,
)


class TestFormatCareerRankLabelFr:
    def test_recruit(self):
        assert format_career_rank_label_fr(tier=None, title="Recruit", grade=None) == "Recrue"

    def test_hero(self):
        assert format_career_rank_label_fr(tier=None, title="Hero", grade=None) == "Héros"

    def test_private_silver_2(self):
        result = format_career_rank_label_fr(tier="Silver", title="Private", grade="2")
        assert result == "Soldat - Argent II"

    def test_lt_colonel_gold_1(self):
        result = format_career_rank_label_fr(tier="Gold", title="Lt Colonel", grade="1")
        assert result == "Lieutenant-colonel - Or I"

    def test_brigadier_general_gold_3(self):
        result = format_career_rank_label_fr(tier="Gold", title="Brigadier General", grade="3")
        assert result == "Général de brigade - Or III"

    def test_title_only(self):
        result = format_career_rank_label_fr(tier=None, title="Captain", grade=None)
        assert result == "Capitaine"

    def test_title_and_tier_no_grade(self):
        result = format_career_rank_label_fr(tier="Bronze", title="Sergeant", grade=None)
        assert result == "Sergent - Bronze"

    def test_unknown_title(self):
        result = format_career_rank_label_fr(tier="Diamond", title="Unknown", grade="1")
        assert result == "Unknown - Diamant I"

    def test_empty_title(self):
        assert format_career_rank_label_fr(tier=None, title=None, grade=None) == ""

    def test_all_tiers_translated(self):
        """Vérifie que tous les tiers sont traduits."""
        for en, fr in [
            ("Bronze", "Bronze"),
            ("Silver", "Argent"),
            ("Gold", "Or"),
            ("Platinum", "Platine"),
            ("Diamond", "Diamant"),
            ("Onyx", "Onyx"),
        ]:
            result = format_career_rank_label_fr(tier=en, title="Private", grade="1")
            assert fr in result

    def test_all_titles_translated(self):
        """Vérifie quelques titres principaux."""
        for en, fr in [
            ("Cadet", "Cadet"),
            ("Lieutenant", "Lieutenant"),
            ("Colonel", "Colonel"),
            ("General", "Général"),
        ]:
            result = format_career_rank_label_fr(tier="Bronze", title=en, grade="1")
            assert fr in result


class TestCareerRankInfoProperties:
    def _make_info(self, **kwargs):
        defaults = {
            "rank_number": 1,
            "title": "Private",
            "subtitle": "Silver",
            "tier": "2",
            "xp_required": 1000,
            "icon_path_remote": "path/icon.png",
        }
        defaults.update(kwargs)
        return CareerRankInfo(**defaults)

    def test_full_label(self):
        info = self._make_info()
        label = info.full_label
        assert "Silver" in label
        assert "Private" in label

    def test_full_label_no_subtitle(self):
        info = self._make_info(subtitle=None, tier=None)
        assert info.full_label == "Private"

    def test_full_label_fr(self):
        info = self._make_info()
        label = info.full_label_fr
        assert "Soldat" in label  # Private → Soldat

    def test_display_label(self):
        info = self._make_info()
        assert "Private" in info.display_label

    def test_display_label_fr(self):
        info = self._make_info()
        assert "Soldat" in info.display_label_fr

    def test_recruit(self):
        info = self._make_info(title="Recruit", subtitle=None, tier=None)
        assert info.full_label_fr == "Recrue"


# ============================================================================
# medals.py — fonctions testables
# ============================================================================

from src.ui.medals import get_local_medals_icons_dir, get_medals_cache_dir


class TestMedalsCacheDir:
    def test_default_returns_string(self):
        result = get_medals_cache_dir()
        assert isinstance(result, str)

    def test_override_via_env(self, monkeypatch):
        monkeypatch.setenv("OPENSPARTAN_MEDALS_CACHE", "/custom/path")
        assert get_medals_cache_dir() == "/custom/path"

    def test_local_icons_dir(self):
        result = get_local_medals_icons_dir()
        assert isinstance(result, str)
        assert result.endswith(os.path.join("static", "medals", "icons"))


# ============================================================================
# aliases.py — fonctions testables
# ============================================================================

from src.ui.aliases import (
    _is_duckdb_file as aliases_is_duckdb,
)
from src.ui.aliases import (
    _safe_mtime,
    display_name_from_xuid,
    load_aliases_file,
    save_aliases_file,
)


class TestAliasesIsDuckdbFile:
    def test_duckdb(self):
        assert aliases_is_duckdb("test.duckdb") is True

    def test_db(self):
        assert aliases_is_duckdb("test.db") is False


class TestSafeMtime:
    def test_nonexistent(self):
        assert _safe_mtime("/nonexistent/file.txt") is None

    def test_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        result = _safe_mtime(str(f))
        assert isinstance(result, float)


class TestLoadAliasesFile:
    def test_load_from_file(self, tmp_path):
        alias_file = tmp_path / "aliases.json"
        alias_file.write_text(json.dumps({"123": "TestGT", "456": "OtherGT"}))
        result = load_aliases_file(str(alias_file))
        assert result["123"] == "TestGT"
        assert result["456"] == "OtherGT"

    def test_nonexistent_file(self, tmp_path):
        result = load_aliases_file(str(tmp_path / "nope.json"))
        assert result == {}

    def test_invalid_json(self, tmp_path):
        alias_file = tmp_path / "bad.json"
        alias_file.write_text("not json")
        result = load_aliases_file(str(alias_file))
        assert result == {}

    def test_not_dict(self, tmp_path):
        alias_file = tmp_path / "arr.json"
        alias_file.write_text(json.dumps([1, 2, 3]))
        result = load_aliases_file(str(alias_file))
        assert result == {}


class TestSaveAliasesFile:
    def test_save_and_load(self, tmp_path):
        alias_file = tmp_path / "aliases.json"
        data = {"111": "Player1", "222": "Player2"}
        save_aliases_file(data, str(alias_file))
        assert alias_file.exists()
        loaded = json.loads(alias_file.read_text(encoding="utf-8"))
        assert loaded == {"111": "Player1", "222": "Player2"}


class TestDisplayNameFromXuid:
    def test_known_xuid(self, tmp_path):
        alias_file = tmp_path / "aliases.json"
        alias_file.write_text(json.dumps({"1234567890": "KnownGT"}))
        with patch("src.ui.aliases.get_aliases_file_path", return_value=str(alias_file)):
            # Invalider le cache avant le test
            from src.ui.aliases import _load_aliases_cached

            _load_aliases_cached.cache_clear()
            result = display_name_from_xuid("1234567890")
            assert result == "KnownGT"

    def test_unknown_xuid(self, tmp_path):
        alias_file = tmp_path / "empty_aliases.json"
        alias_file.write_text(json.dumps({}))
        with patch("src.ui.aliases.get_aliases_file_path", return_value=str(alias_file)):
            from src.ui.aliases import _load_aliases_cached

            _load_aliases_cached.cache_clear()
            # Doit retourner le xuid brut
            result = display_name_from_xuid("9999999999")
            assert result == "9999999999"

    def test_xuid_format_normalization(self, tmp_path):
        """Le format xuid(123) est normalisé avant lookup."""
        alias_file = tmp_path / "norm_aliases.json"
        alias_file.write_text(json.dumps({"123": "NormGT"}))
        with patch("src.ui.aliases.get_aliases_file_path", return_value=str(alias_file)):
            from src.ui.aliases import _load_aliases_cached

            _load_aliases_cached.cache_clear()
            result = display_name_from_xuid("xuid(123)")
            assert result == "NormGT"
