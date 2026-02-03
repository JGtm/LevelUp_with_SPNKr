"""Tests pour les modules de refactoring Phase 6.

Ce fichier teste les nouveaux modules créés lors de la Phase 6 :
- profile_api_cache.py
- profile_api_urls.py
- profile_api_tokens.py
- teammates_charts.py
- teammates_helpers.py
- match_view_helpers.py
- match_view_charts.py
- match_view_players.py
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pandas as pd

# =============================================================================
# Tests profile_api_cache.py
# =============================================================================


class TestProfileApiCache:
    """Tests pour le module profile_api_cache."""

    def test_profile_appearance_dataclass(self):
        """Test création d'une ProfileAppearance."""
        from src.ui.profile_api_cache import ProfileAppearance

        pa = ProfileAppearance(
            service_tag="TEST",
            emblem_image_url="https://example.com/emblem.png",
            backdrop_image_url="https://example.com/backdrop.png",
            nameplate_image_url="https://example.com/nameplate.png",
            rank_label="Silver",
            rank_subtitle="Tier 2",
            rank_image_url="https://example.com/rank.png",
        )
        assert pa.service_tag == "TEST"
        assert pa.rank_label == "Silver"
        assert pa.emblem_image_url == "https://example.com/emblem.png"

    def test_profile_appearance_defaults(self):
        """Test ProfileAppearance avec valeurs par défaut."""
        from src.ui.profile_api_cache import ProfileAppearance

        pa = ProfileAppearance()
        assert pa.service_tag is None
        assert pa.rank_label is None
        assert pa.emblem_image_url is None

    def test_safe_read_json_missing_file(self):
        """Test lecture JSON fichier inexistant."""
        from pathlib import Path

        from src.ui.profile_api_cache import _safe_read_json

        result = _safe_read_json(Path("/nonexistent/path.json"))
        assert result is None

    def test_get_profile_api_cache_dir(self):
        """Test récupération du répertoire de cache."""
        from src.ui.profile_api_cache import get_profile_api_cache_dir

        cache_dir = get_profile_api_cache_dir()
        assert "profile_api" in str(cache_dir)
        assert "cache" in str(cache_dir)


# =============================================================================
# Tests profile_api_urls.py
# =============================================================================


class TestProfileApiUrls:
    """Tests pour le module profile_api_urls."""

    def test_to_image_url_none(self):
        """Test avec valeur None."""
        from src.ui.profile_api_urls import _to_image_url

        assert _to_image_url(None) is None

    def test_to_image_url_empty(self):
        """Test avec string vide."""
        from src.ui.profile_api_urls import _to_image_url

        assert _to_image_url("") is None
        assert _to_image_url("   ") is None

    def test_to_image_url_valid(self):
        """Test avec URL valide."""
        from src.ui.profile_api_urls import _to_image_url

        url = "https://example.com/image.png"
        assert _to_image_url(url) == url


# =============================================================================
# Tests profile_api_tokens.py
# =============================================================================


class TestProfileApiTokens:
    """Tests pour le module profile_api_tokens."""

    def test_is_probable_auth_error_401_message(self):
        """Test détection d'erreurs 401 dans le message."""
        from src.ui.profile_api_tokens import _is_probable_auth_error

        # La fonction prend une Exception, pas un code HTTP
        err_401 = Exception("HTTP 401 Unauthorized")
        assert _is_probable_auth_error(err_401) is True

    def test_is_probable_auth_error_forbidden(self):
        """Test détection d'erreurs Forbidden."""
        from src.ui.profile_api_tokens import _is_probable_auth_error

        err_forbidden = Exception("403 Forbidden: Access denied")
        assert _is_probable_auth_error(err_forbidden) is True

    def test_is_probable_auth_error_other(self):
        """Test avec erreur non liée à l'auth."""
        from src.ui.profile_api_tokens import _is_probable_auth_error

        err_404 = Exception("404 Not Found")
        assert _is_probable_auth_error(err_404) is False

    def test_load_dotenv_if_present_no_file(self):
        """Test chargement dotenv sans fichier."""
        from src.ui.profile_api_tokens import _load_dotenv_if_present

        # Ne doit pas lever d'exception
        _load_dotenv_if_present()


# =============================================================================
# Tests match_view_helpers.py
# =============================================================================


class TestMatchViewHelpers:
    """Tests pour le module match_view_helpers."""

    def test_safe_dt_with_none(self):
        """Test conversion avec None."""
        import pytz

        from src.ui.pages.match_view_helpers import safe_dt

        paris_tz = pytz.timezone("Europe/Paris")
        assert safe_dt(None, paris_tz) is None

    def test_safe_dt_with_valid_timestamp(self):
        """Test conversion avec timestamp valide."""
        import pytz

        from src.ui.pages.match_view_helpers import safe_dt

        paris_tz = pytz.timezone("Europe/Paris")
        ts = pd.Timestamp("2024-01-15 14:30:00", tz="UTC")
        result = safe_dt(ts, paris_tz)
        assert result is not None
        assert isinstance(result, datetime)

    def test_match_time_window_valid(self):
        """Test calcul fenêtre temporelle avec durée connue."""
        import pytz

        from src.ui.pages.match_view_helpers import match_time_window

        paris_tz = pytz.timezone("Europe/Paris")
        row = pd.Series(
            {
                "start_time": "2024-01-15 14:00:00",
                "time_played_seconds": 600,  # 10 minutes
            }
        )
        t0, t1, duration_known = match_time_window(row, tolerance_minutes=5, paris_tz=paris_tz)
        assert t0 is not None
        assert t1 is not None
        assert duration_known is True  # Durée réelle disponible
        # La fenêtre doit être plus large que la durée du match
        assert t1 > t0

    def test_match_time_window_missing_duration(self):
        """Test avec durée manquante (fallback 12 min)."""
        import pytz

        from src.ui.pages.match_view_helpers import match_time_window

        paris_tz = pytz.timezone("Europe/Paris")
        row = pd.Series(
            {
                "start_time": "2024-01-15 14:00:00",
                "time_played_seconds": None,  # Durée inconnue
            }
        )
        t0, t1, duration_known = match_time_window(row, tolerance_minutes=5, paris_tz=paris_tz)
        assert t0 is not None
        assert t1 is not None
        assert duration_known is False  # Durée estimée
        assert t1 > t0

    def test_match_time_window_missing_start(self):
        """Test avec start_time manquant."""
        import pytz

        from src.ui.pages.match_view_helpers import match_time_window

        paris_tz = pytz.timezone("Europe/Paris")
        row = pd.Series({"time_played_seconds": 600})
        t0, t1, duration_known = match_time_window(row, tolerance_minutes=5, paris_tz=paris_tz)
        assert t0 is None
        assert t1 is None
        assert duration_known is False


class TestOsCard:
    """Tests pour la fonction os_card."""

    @patch("streamlit.markdown")
    def test_os_card_basic(self, mock_markdown):
        """Test carte KPI basique."""
        from src.ui.pages.match_view_helpers import os_card

        os_card("Titre", "42")
        mock_markdown.assert_called_once()
        call_args = mock_markdown.call_args[0][0]
        assert "Titre" in call_args
        assert "42" in call_args

    @patch("streamlit.markdown")
    def test_os_card_with_accent(self, mock_markdown):
        """Test carte avec couleur d'accent."""
        from src.ui.pages.match_view_helpers import os_card

        os_card("Test", "100", accent="#FF0000")
        call_args = mock_markdown.call_args[0][0]
        assert "#FF0000" in call_args

    @patch("streamlit.markdown")
    def test_os_card_with_sub_html(self, mock_markdown):
        """Test carte avec sous-texte HTML."""
        from src.ui.pages.match_view_helpers import os_card

        os_card("Test", "50", sub_html="<span>Sous-texte</span>")
        call_args = mock_markdown.call_args[0][0]
        assert "Sous-texte" in call_args


# =============================================================================
# Tests teammates_helpers.py
# =============================================================================


class TestTeammatesHelpers:
    """Tests pour le module teammates_helpers."""

    def test_format_datetime_fr_hm(self):
        """Test formatage date/heure FR."""
        from src.ui.pages.teammates_helpers import _format_datetime_fr_hm

        dt = datetime(2024, 1, 15, 14, 30)
        result = _format_datetime_fr_hm(dt)
        assert "15" in result  # jour
        assert "14" in result or "14:30" in result  # heure

    def test_format_datetime_fr_hm_none(self):
        """Test formatage avec None."""
        from src.ui.pages.teammates_helpers import _format_datetime_fr_hm

        result = _format_datetime_fr_hm(None)
        assert result == "-"

    def test_app_url(self):
        """Test construction d'URL."""
        from src.ui.pages.teammates_helpers import _app_url

        url = _app_url(page="match_view", match_id="abc123")
        assert "page=match_view" in url
        assert "match_id=abc123" in url


# =============================================================================
# Tests match_view_charts.py (imports only)
# =============================================================================


class TestMatchViewChartsImports:
    """Tests d'import pour match_view_charts."""

    def test_render_expected_vs_actual_exists(self):
        """Test que la fonction est importable."""
        from src.ui.pages.match_view_charts import render_expected_vs_actual

        assert callable(render_expected_vs_actual)


# =============================================================================
# Tests match_view_players.py (imports only)
# =============================================================================


class TestMatchViewPlayersImports:
    """Tests d'import pour match_view_players."""

    def test_render_nemesis_section_exists(self):
        """Test que la fonction est importable."""
        from src.ui.pages.match_view_players import render_nemesis_section

        assert callable(render_nemesis_section)

    def test_render_roster_section_exists(self):
        """Test que la fonction est importable."""
        from src.ui.pages.match_view_players import render_roster_section

        assert callable(render_roster_section)


# =============================================================================
# Tests teammates_charts.py (imports only)
# =============================================================================


class TestTeammatesChartsImports:
    """Tests d'import pour teammates_charts."""

    def test_render_comparison_charts_exists(self):
        """Test que la fonction est importable."""
        from src.ui.pages.teammates_charts import render_comparison_charts

        assert callable(render_comparison_charts)

    def test_render_trio_charts_exists(self):
        """Test que la fonction est importable."""
        from src.ui.pages.teammates_charts import render_trio_charts

        assert callable(render_trio_charts)


# =============================================================================
# Tests d'intégration
# =============================================================================


class TestModuleIntegration:
    """Tests d'intégration entre les modules refactorisés."""

    def test_profile_api_imports_submodules(self):
        """Test que profile_api.py importe correctement ses sous-modules."""
        from src.ui.profile_api import (
            ProfileAppearance,
        )

        assert ProfileAppearance is not None

    def test_match_view_imports_submodules(self):
        """Test que match_view.py importe correctement ses sous-modules."""
        from src.ui.pages.match_view import (
            map_thumb_path,
            os_card,
            render_match_view,
        )

        assert callable(render_match_view)
        assert callable(os_card)
        assert callable(map_thumb_path)

    def test_teammates_imports_submodules(self):
        """Test que teammates.py importe correctement ses sous-modules."""
        from src.ui.pages.teammates import render_teammates_page

        assert callable(render_teammates_page)


# =============================================================================
# Tests filters_render.py
# =============================================================================


class TestFiltersRender:
    """Tests pour le module filters_render consolidé."""

    def test_filter_state_dataclass(self):
        """Test création d'un FilterState."""
        from datetime import date

        from src.app.filters_render import FilterState

        fs = FilterState(
            filter_mode="Période",
            start_d=date(2024, 1, 1),
            end_d=date(2024, 1, 31),
            gap_minutes=35,
            picked_session_labels=None,
            playlists_selected=["Arène classée"],
            modes_selected=[],
            maps_selected=[],
            base_s_ui=None,
        )
        assert fs.filter_mode == "Période"
        assert fs.playlists_selected == ["Arène classée"]
