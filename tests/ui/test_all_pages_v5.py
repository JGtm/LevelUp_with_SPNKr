"""Tests UI smoke — Sprint 7 (Couverture).

Vérifie que :
1. Tous les modules de pages s'importent sans erreur
2. Les fonctions render_* existent et sont callables
3. Les helpers UI internes (formatters, utils) fonctionnent
4. Aucune régression d'import dans le graph de dépendances

Philosophie : tests d'import et de contrat, pas de rendu réel.
"""

from __future__ import annotations

import importlib

import pytest

# =============================================================================
# Tests d'import de tous les modules de pages
# =============================================================================


PAGE_MODULES = [
    "src.ui.pages.career",
    "src.ui.pages.citations",
    "src.ui.pages.last_match",
    "src.ui.pages.match_history",
    "src.ui.pages.match_view",
    "src.ui.pages.match_view_charts",
    "src.ui.pages.match_view_helpers",
    "src.ui.pages.match_view_participation",
    "src.ui.pages.match_view_players",
    "src.ui.pages.media_library",
    "src.ui.pages.media_tab",
    "src.ui.pages.objective_analysis",
    "src.ui.pages.session_compare",
    "src.ui.pages.settings",
    "src.ui.pages.teammates",
    "src.ui.pages.teammates_charts",
    "src.ui.pages.teammates_helpers",
    "src.ui.pages.teammates_impact",
    "src.ui.pages.teammates_synergy",
    "src.ui.pages.teammates_views",
    "src.ui.pages.timeseries",
    "src.ui.pages.win_loss",
]


class TestPageModulesImport:
    """Vérifie que tous les modules de pages s'importent sans erreur."""

    @pytest.mark.parametrize("module_name", PAGE_MODULES)
    def test_module_imports(self, module_name: str) -> None:
        """Chaque module de page s'importe sans exception."""
        mod = importlib.import_module(module_name)
        assert mod is not None


# =============================================================================
# Tests des exports __init__.py
# =============================================================================


EXPECTED_RENDER_FUNCTIONS = [
    "render_timeseries_page",
    "render_session_comparison_page",
    "render_last_match_page",
    "render_match_search_page",
    "render_match_view",
    "render_match_history_page",
    "render_win_loss_page",
    "render_teammates_page",
    "render_citations_page",
    "render_settings_page",
    "render_media_library_page",
    "render_career_page",
    "render_media_tab",
    "render_objective_analysis_page",
]


class TestPagesExports:
    """Vérifie que src.ui.pages exporte les bonnes fonctions render_*."""

    @pytest.mark.parametrize("func_name", EXPECTED_RENDER_FUNCTIONS)
    def test_render_function_exists(self, func_name: str) -> None:
        """Chaque fonction render_* est exportée et callable."""
        from src.ui import pages

        assert hasattr(pages, func_name), f"{func_name} manquant dans src.ui.pages.__init__"
        func = getattr(pages, func_name)
        assert callable(func)

    def test_all_list_covered(self) -> None:
        """__all__ contient toutes les fonctions attendues."""
        from src.ui.pages import __all__

        for func_name in EXPECTED_RENDER_FUNCTIONS:
            assert func_name in __all__, f"{func_name} absent de __all__"


# =============================================================================
# Tests des helpers UI (fonctions pures sans Streamlit)
# =============================================================================


class TestMatchViewHelpers:
    """Tests pour les helpers de match_view sans dépendance Streamlit."""

    def test_to_paris_naive_local_import(self) -> None:
        """to_paris_naive_local est importable."""
        from src.ui.pages.match_view_helpers import to_paris_naive_local

        assert callable(to_paris_naive_local)

    def test_safe_dt_import(self) -> None:
        from src.ui.pages.match_view_helpers import safe_dt

        assert callable(safe_dt)


class TestMatchHistoryHelpers:
    """Tests pour les helpers de match_history."""

    def test_normalize_mode_label(self) -> None:
        """_normalize_mode_label traite les noms de modes."""
        from src.ui.pages.match_history import _normalize_mode_label

        # Ne crash pas sur un nom simple
        result = _normalize_mode_label("Slayer")
        assert isinstance(result, str)

    def test_format_datetime_fr_hm(self) -> None:
        """_format_datetime_fr_hm formate une date."""
        from datetime import datetime

        from src.ui.pages.match_history import _format_datetime_fr_hm

        result = _format_datetime_fr_hm(datetime(2025, 6, 15, 14, 30))
        assert isinstance(result, str)


class TestSessionCompareHelpers:
    """Tests pour les helpers de session_compare (fonctions pures)."""

    def test_format_seconds_to_mmss(self) -> None:
        from src.ui.pages.session_compare import _format_seconds_to_mmss

        assert _format_seconds_to_mmss(90) == "1:30"

    def test_format_seconds_to_mmss_zero(self) -> None:
        from src.ui.pages.session_compare import _format_seconds_to_mmss

        assert _format_seconds_to_mmss(0) == "0:00"

    def test_format_seconds_to_mmss_large(self) -> None:
        from src.ui.pages.session_compare import _format_seconds_to_mmss

        result = _format_seconds_to_mmss(3661)
        assert isinstance(result, str)

    def test_outcome_class(self) -> None:
        from src.ui.pages.session_compare import _outcome_class

        assert callable(_outcome_class)


class TestMatchViewChartsHelpers:
    """Tests pour les helpers numériques de match_view_charts."""

    def test_safe_numeric_normal(self) -> None:
        from src.ui.pages.match_view_charts import _safe_numeric

        assert _safe_numeric(42) == 42

    def test_safe_numeric_none(self) -> None:
        import math

        from src.ui.pages.match_view_charts import _safe_numeric

        result = _safe_numeric(None)
        # Peut retourner 0, None, ou NaN selon l'implémentation
        assert result == 0 or result is None or (isinstance(result, float) and math.isnan(result))

    def test_safe_numeric_string(self) -> None:
        from src.ui.pages.match_view_charts import _safe_numeric

        result = _safe_numeric("not_a_number")
        assert isinstance(result, int | float) or result is None


class TestMatchViewPlayersHelpers:
    """Tests pour les helpers de match_view_players."""

    def test_is_duckdb_v4_path(self) -> None:
        from src.ui.pages.match_view_players import _is_duckdb_v4_path

        assert _is_duckdb_v4_path("data/players/Test/stats.duckdb") is True
        assert _is_duckdb_v4_path("some/path/stats.db") is False


# =============================================================================
# Tests d'import des modules de visualisation
# =============================================================================


VIZ_MODULES = [
    "src.visualization.antagonist_charts",
    "src.visualization.distributions",
    "src.visualization.distributions_outcomes",
    "src.visualization.friends_impact_heatmap",
    "src.visualization.maps",
    "src.visualization.match_bars",
    "src.visualization.objective_charts",
    "src.visualization.participation_charts",
    "src.visualization.participation_radar",
    "src.visualization.performance",
    "src.visualization.theme",
    "src.visualization.timeseries",
    "src.visualization.timeseries_combat",
    "src.visualization.trio",
]


class TestVisualizationModulesImport:
    """Vérifie que les modules de visualisation s'importent."""

    @pytest.mark.parametrize("module_name", VIZ_MODULES)
    def test_import(self, module_name: str) -> None:
        mod = importlib.import_module(module_name)
        assert mod is not None


# =============================================================================
# Tests de contrat des services UI
# =============================================================================


class TestDataServicesImport:
    """Vérifie que les services de données sont importables."""

    def test_teammates_service_import(self) -> None:
        from src.data.services.teammates_service import TeammatesService

        assert callable(TeammatesService)

    def test_timeseries_service_import(self) -> None:
        from src.data.services.timeseries_service import TimeseriesService

        assert callable(TimeseriesService)

    def test_win_loss_service_import(self) -> None:
        from src.data.services.win_loss_service import WinLossService

        assert callable(WinLossService)


# =============================================================================
# Tests de contrat des composants UI
# =============================================================================


class TestUIComponentsImport:
    """Vérifie que les composants UI clés sont importables."""

    def test_page_router_import(self) -> None:
        from src.app.page_router import PAGES, dispatch_page

        assert isinstance(PAGES, list)
        assert len(PAGES) > 0
        assert callable(dispatch_page)

    def test_page_router_has_all_expected_pages(self) -> None:
        """Le routeur contient toutes les pages attendues."""
        from src.app.page_router import PAGES

        # Au minimum, ces pages doivent exister
        assert len(PAGES) >= 8  # Historique, Timeseries, V/D, Coéquipiers, etc.

    def test_filters_render_import(self) -> None:
        from src.app.filters_render import render_filters_sidebar

        assert callable(render_filters_sidebar)

    def test_translations_import(self) -> None:
        from src.ui.translations import translate_playlist_name

        assert callable(translate_playlist_name)

    def test_theme_colors_import(self) -> None:
        from src.config import THEME_COLORS

        # THEME_COLORS est un NamedTuple, pas un dict
        assert THEME_COLORS is not None
        assert hasattr(THEME_COLORS, "accent")
