"""Tests des composants UI : checkbox_filter et duckdb_analytics.

Sprint 7bis – Tâche 7b.7
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ═══════════════════════════════════════════════════════════════════
# checkbox_filter – fonctions pures
# ═══════════════════════════════════════════════════════════════════


class TestInferCategory:
    """Tests pour _infer_category."""

    def test_arena_prefix(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Arène : Assassin") == "Assassin"

    def test_btb_prefix(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("BTB : CTF") == "BTB"

    def test_super_fiesta(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Super Fiesta : Assassin") == "Fiesta"

    def test_fiesta_in_content(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Communauté : Fiesta Assassin") == "Fiesta"

    def test_husky_raid(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Husky Raid : CDD") == "Fiesta"

    def test_castle_wars(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Castle Wars : Assassin") == "Fiesta"

    def test_ranked_prefix(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Ranked : Slayer") == "Ranked"

    def test_classé_prefix(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Classé : Slayer") == "Ranked"

    def test_firefight_prefix(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Firefight : Heroic") == "Firefight"

    def test_gruntpocalypse(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Gruntpocalypse : Solo") == "Firefight"

    def test_communauté_prefix(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Communauté : Oddball") == "Assassin"

    def test_unknown_mode(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Something Random") == "Other"

    def test_tactical_prefix(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Tactical : Slayer") == "Assassin"

    def test_event_prefix(self):
        from src.ui.components.checkbox_filter import _infer_category

        assert _infer_category("Event : Special") == "Other"


class TestTranslateCategory:
    """Tests pour _translate_category."""

    def test_known_categories(self):
        from src.ui.components.checkbox_filter import _translate_category

        assert _translate_category("Assassin") == "Assassin"
        assert _translate_category("Fiesta") == "Fiesta"
        assert _translate_category("BTB") == "Grande bataille en équipe"
        assert _translate_category("Ranked") == "Classé"
        assert _translate_category("Firefight") == "Baptême du feu"
        assert _translate_category("Other") == "Autre"

    def test_unknown_returns_input(self):
        from src.ui.components.checkbox_filter import _translate_category

        assert _translate_category("UnknownCat") == "UnknownCat"


class TestExtractModeName:
    """Tests pour _extract_mode_name."""

    def test_with_prefix(self):
        from src.ui.components.checkbox_filter import _extract_mode_name

        assert _extract_mode_name("Arène : Assassin") == "Assassin"

    def test_btb_ctf(self):
        from src.ui.components.checkbox_filter import _extract_mode_name

        assert _extract_mode_name("BTB : Capture du drapeau") == "Capture du drapeau"

    def test_super_husky(self):
        from src.ui.components.checkbox_filter import _extract_mode_name

        assert _extract_mode_name("Super Husky Raid : CDD") == "CDD"

    def test_no_prefix(self):
        from src.ui.components.checkbox_filter import _extract_mode_name

        assert _extract_mode_name("Slayer") == "Slayer"


class TestGetFirefightPlaylists:
    """Tests pour get_firefight_playlists."""

    def test_finds_firefight(self):
        from src.ui.components.checkbox_filter import get_firefight_playlists

        playlists = ["Quick Play", "Ranked Arena", "Firefight: Heroic", "BTB"]
        result = get_firefight_playlists(playlists)
        assert result == {"Firefight: Heroic"}

    def test_case_insensitive(self):
        from src.ui.components.checkbox_filter import get_firefight_playlists

        playlists = ["FIREFIGHT KOTH", "ranked"]
        result = get_firefight_playlists(playlists)
        assert result == {"FIREFIGHT KOTH"}

    def test_no_firefight(self):
        from src.ui.components.checkbox_filter import get_firefight_playlists

        playlists = ["Quick Play", "Ranked Arena"]
        result = get_firefight_playlists(playlists)
        assert result == set()

    def test_empty_list(self):
        from src.ui.components.checkbox_filter import get_firefight_playlists

        assert get_firefight_playlists([]) == set()


class TestRenderCheckboxFilter:
    """Tests pour render_checkbox_filter avec MockStreamlit."""

    def test_empty_options_returns_empty(self, mock_st):
        from src.ui.components import checkbox_filter as mod

        mock_st(mod)
        result = mod.render_checkbox_filter(
            label="Test",
            options=[],
            session_key="test_empty",
        )
        assert result == set()

    def test_all_selected_by_default(self, mock_st):
        from src.ui.components import checkbox_filter as mod

        ms = mock_st(mod)
        ms.calls["checkbox"] = MagicMock(return_value=True)
        ms._monkeypatch.setattr(mod.st, "checkbox", ms.calls["checkbox"])
        # Buttons return False (no click)
        cols = ms.columns
        for c in cols:
            c.button = MagicMock(return_value=False)

        options = ["Mode A", "Mode B", "Mode C"]
        result = mod.render_checkbox_filter(
            label="Modes",
            options=options,
            session_key="test_all_default",
        )
        assert result == set(options)

    def test_default_unchecked(self, mock_st):
        from src.ui.components import checkbox_filter as mod

        ms = mock_st(mod)
        # Le checkbox mock doit refléter la valeur 'value' passée en kwarg
        # (le checkbox Streamlit reçoit value=checked)
        ms.calls["checkbox"] = MagicMock(side_effect=lambda *_a, value=False, **_kw: value)
        ms._monkeypatch.setattr(mod.st, "checkbox", ms.calls["checkbox"])
        cols = ms.columns
        for c in cols:
            c.button = MagicMock(return_value=False)

        options = ["Quick Play", "Firefight: Heroic", "Ranked"]
        result = mod.render_checkbox_filter(
            label="Playlists",
            options=options,
            session_key="test_unch",
            default_unchecked={"Firefight: Heroic"},
        )
        # La session state initiale exclut Firefight
        assert "Quick Play" in result
        assert "Ranked" in result
        assert "Firefight: Heroic" not in result


# ═══════════════════════════════════════════════════════════════════
# duckdb_analytics – fonctions
# ═══════════════════════════════════════════════════════════════════


class TestIsAnalyticsEnabled:
    """Tests pour _is_analytics_enabled."""

    def test_disabled_by_default(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        mock_st(mod)
        # session_state vide → pas activé
        result = mod._is_analytics_enabled()
        assert result is False

    def test_enabled_with_settings(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        ms = mock_st(mod)
        settings_mock = MagicMock()
        settings_mock.enable_duckdb_analytics = True
        ms.session_state["app_settings"] = settings_mock
        result = mod._is_analytics_enabled()
        assert result is True

    def test_disabled_with_settings_false(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        ms = mock_st(mod)
        settings_mock = MagicMock()
        settings_mock.enable_duckdb_analytics = False
        ms.session_state["app_settings"] = settings_mock
        result = mod._is_analytics_enabled()
        assert result is False


class TestRenderGlobalStatsCard:
    """Tests pour render_global_stats_card."""

    def test_returns_false_when_disabled(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        mock_st(mod)
        # pas de app_settings → analytics disabled
        result = mod.render_global_stats_card("test.duckdb", "xuid123")
        assert result is False

    def test_returns_false_when_no_stats(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        ms = mock_st(mod)
        settings_mock = MagicMock()
        settings_mock.enable_duckdb_analytics = True
        ms.session_state["app_settings"] = settings_mock
        ms.set_columns_dynamic()

        with patch(
            "src.ui.components.duckdb_analytics.cached_get_global_stats_duckdb", create=True
        ):
            # Patch l'import interne
            with patch.dict("sys.modules", {}):
                pass
            with patch(
                "src.ui.cache.cached_get_global_stats_duckdb", return_value=None, create=True
            ):
                result = mod.render_global_stats_card("test.duckdb", "xuid123")
        # Analytics enabled mais pas de données → False
        # Le try/except dans le code va attraper l'erreur d'import
        assert result is False

    def test_returns_true_with_valid_stats(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        ms = mock_st(mod)
        settings_mock = MagicMock()
        settings_mock.enable_duckdb_analytics = True
        ms.session_state["app_settings"] = settings_mock
        ms.set_columns_dynamic()

        fake_stats = {
            "total_matches": 100,
            "win_rate": 55.0,
            "avg_kda": 1.5,
            "avg_accuracy": 45.0,
            "total_kills": 2000,
            "total_deaths": 1500,
            "total_assists": 800,
            "total_time_hours": 50,
        }

        with patch(
            "src.ui.cache.cached_get_global_stats_duckdb", return_value=fake_stats, create=True
        ):
            result = mod.render_global_stats_card("test.duckdb", "xuid123")

        assert result is True
        ms.calls["markdown"].assert_called()


class TestRenderAnalyticsSection:
    """Tests pour render_analytics_section."""

    def test_returns_false_when_disabled(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        mock_st(mod)
        result = mod.render_analytics_section("test.duckdb", "xuid123")
        assert result is False

    def test_returns_false_when_no_data(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        ms = mock_st(mod)
        settings_mock = MagicMock()
        settings_mock.enable_duckdb_analytics = True
        ms.session_state["app_settings"] = settings_mock
        ms.set_columns_dynamic()

        with (
            patch.object(mod, "render_global_stats_card", return_value=False),
            patch.object(mod, "render_kda_trend_chart", return_value=False),
            patch.object(mod, "render_performance_by_map", return_value=False),
        ):
            result = mod.render_analytics_section("test.duckdb", "xuid123")

        assert result is False
        # info affiché car rien rendu
        ms.calls["info"].assert_called()

    def test_returns_true_when_at_least_one_rendered(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        ms = mock_st(mod)
        settings_mock = MagicMock()
        settings_mock.enable_duckdb_analytics = True
        ms.session_state["app_settings"] = settings_mock
        ms.set_columns_dynamic()

        with (
            patch.object(mod, "render_global_stats_card", return_value=True),
            patch.object(mod, "render_kda_trend_chart", return_value=False),
            patch.object(mod, "render_performance_by_map", return_value=False),
        ):
            result = mod.render_analytics_section("test.duckdb", "xuid123")

        assert result is True


class TestRenderKdaTrendChart:
    """Tests pour render_kda_trend_chart."""

    def test_disabled_returns_false(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        mock_st(mod)
        result = mod.render_kda_trend_chart("test.duckdb", "xuid123")
        assert result is False

    def test_no_data_returns_false(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        ms = mock_st(mod)
        settings_mock = MagicMock()
        settings_mock.enable_duckdb_analytics = True
        ms.session_state["app_settings"] = settings_mock

        with patch("src.ui.cache.cached_get_kda_trend_duckdb", return_value=None, create=True):
            result = mod.render_kda_trend_chart("test.duckdb", "xuid123")

        assert result is False


class TestRenderPerformanceByMap:
    """Tests pour render_performance_by_map."""

    def test_disabled_returns_false(self, mock_st):
        from src.ui.components import duckdb_analytics as mod

        mock_st(mod)
        result = mod.render_performance_by_map("test.duckdb", "xuid123")
        assert result is False
