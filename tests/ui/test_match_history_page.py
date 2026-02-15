"""Tests pour la page Historique des parties (Sprint 7bis).

Couvre :
- Fonctions pures (_format_datetime_fr_hm, _app_url, _format_score_label, _fmt, _fmt_mmr_int, _normalize_mode_label)
- render_match_history_page avec MockStreamlit
- Edge case : DataFrame vide
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
import polars as pl

# =============================================================================
# Tests des fonctions pures
# =============================================================================


class TestFormatDatetimeFrHm:
    """Tests pour _format_datetime_fr_hm."""

    def test_normal_date(self) -> None:
        from src.ui.pages.match_history import _format_datetime_fr_hm

        result = _format_datetime_fr_hm(datetime(2025, 6, 15, 14, 30))
        assert result == "15/06/2025 14:30"

    def test_none(self) -> None:
        from src.ui.pages.match_history import _format_datetime_fr_hm

        assert _format_datetime_fr_hm(None) == "-"

    def test_midnight(self) -> None:
        from src.ui.pages.match_history import _format_datetime_fr_hm

        result = _format_datetime_fr_hm(datetime(2025, 1, 1, 0, 0))
        assert "00:00" in result


class TestAppUrl:
    """Tests pour _app_url."""

    def test_basic(self) -> None:
        from src.ui.pages.match_history import _app_url

        url = _app_url("Match", match_id="abc123")
        assert "page=Match" in url
        assert "match_id=abc123" in url
        assert url.startswith("/")

    def test_no_params(self) -> None:
        from src.ui.pages.match_history import _app_url

        url = _app_url("Historique")
        assert "page=Historique" in url


class TestFormatScoreLabel:
    """Tests pour _format_score_label."""

    def test_normal(self) -> None:
        from src.ui.pages.match_history import _format_score_label

        assert _format_score_label(50, 30) == "50 - 30"

    def test_none_scores(self) -> None:
        from src.ui.pages.match_history import _format_score_label

        assert _format_score_label(None, None) == "- - -"

    def test_nan_score(self) -> None:
        from src.ui.pages.match_history import _format_score_label

        result = _format_score_label(float("nan"), 30)
        assert result == "- - 30"

    def test_float_scores(self) -> None:
        from src.ui.pages.match_history import _format_score_label

        assert _format_score_label(50.6, 30.2) == "51 - 30"


class TestFmt:
    """Tests pour _fmt."""

    def test_normal(self) -> None:
        from src.ui.pages.match_history import _fmt

        assert _fmt(42) == "42"

    def test_none(self) -> None:
        from src.ui.pages.match_history import _fmt

        assert _fmt(None) == "-"

    def test_nan(self) -> None:
        from src.ui.pages.match_history import _fmt

        assert _fmt(float("nan")) == "-"

    def test_empty_string(self) -> None:
        from src.ui.pages.match_history import _fmt

        assert _fmt("") == "-"

    def test_whitespace_string(self) -> None:
        from src.ui.pages.match_history import _fmt

        assert _fmt("   ") == "-"


class TestFmtMmrInt:
    """Tests pour _fmt_mmr_int."""

    def test_normal(self) -> None:
        from src.ui.pages.match_history import _fmt_mmr_int

        assert _fmt_mmr_int(1500.6) == "1501"

    def test_none(self) -> None:
        from src.ui.pages.match_history import _fmt_mmr_int

        assert _fmt_mmr_int(None) == "-"

    def test_nan(self) -> None:
        from src.ui.pages.match_history import _fmt_mmr_int

        assert _fmt_mmr_int(float("nan")) == "-"

    def test_int(self) -> None:
        from src.ui.pages.match_history import _fmt_mmr_int

        assert _fmt_mmr_int(1500) == "1500"


class TestNormalizeModeLabel:
    """Tests pour _normalize_mode_label."""

    def test_none(self) -> None:
        from src.ui.pages.match_history import _normalize_mode_label

        assert _normalize_mode_label(None) is None

    def test_string(self) -> None:
        from src.ui.pages.match_history import _normalize_mode_label

        result = _normalize_mode_label("Slayer")
        assert isinstance(result, str)


# =============================================================================
# Tests du rendu
# =============================================================================


def _make_history_df(n: int = 15) -> pl.DataFrame:
    """Crée un DataFrame synthétique pour match_history."""
    np.random.seed(42)
    start = datetime(2025, 1, 1)

    return pl.DataFrame(
        {
            "match_id": [f"match_{i}" for i in range(n)],
            "start_time": [start + timedelta(hours=i) for i in range(n)],
            "kills": np.random.randint(5, 25, n).tolist(),
            "deaths": np.random.randint(3, 15, n).tolist(),
            "assists": np.random.randint(2, 12, n).tolist(),
            "accuracy": np.random.uniform(30, 60, n).tolist(),
            "ratio": np.random.uniform(0.5, 2.5, n).tolist(),
            "kda": np.random.uniform(-5, 10, n).tolist(),
            "outcome": np.random.choice([1, 2, 3, 4], n).tolist(),
            "map_name": np.random.choice(["Recharge", "Streets", "Live Fire"], n).tolist(),
            "playlist_name": np.random.choice(["Ranked Arena", "Quick Play"], n).tolist(),
            "pair_name": np.random.choice(["Arena: Slayer", "Arena: CTF"], n).tolist(),
            "time_played_seconds": np.random.randint(300, 900, n).tolist(),
            "headshot_kills": np.random.randint(1, 10, n).tolist(),
            "max_killing_spree": np.random.randint(0, 8, n).tolist(),
            "average_life_seconds": np.random.uniform(20, 60, n).tolist(),
            "my_team_score": np.random.randint(0, 50, n).tolist(),
            "enemy_team_score": np.random.randint(0, 50, n).tolist(),
            "team_mmr": np.random.uniform(1200, 1800, n).tolist(),
            "enemy_mmr": np.random.uniform(1200, 1800, n).tolist(),
        }
    )


class TestRenderMatchHistoryPage:
    """Tests de la render function."""

    def test_empty_df_shows_warning(self, mock_st) -> None:
        from src.ui.pages import match_history as mod

        ms = mock_st(mod)
        empty_df = pl.DataFrame(schema={"match_id": pl.Utf8, "outcome": pl.Int64})
        mod.render_match_history_page(empty_df, "TestPlayer", "dummy.duckdb", "100", None)
        ms.calls["warning"].assert_called_once()

    def test_normal_flow(self, mock_st) -> None:
        from src.ui.pages import match_history as mod

        ms = mock_st(mod)
        dff = _make_history_df(15)

        with patch.object(mod, "compute_performance_series") as mock_perf:
            mock_perf.return_value = pl.Series("performance", [50.0] * 15)
            mod.render_match_history_page(dff, "TestPlayer", "dummy.duckdb", "100", None)

        # Le tableau HTML est rendu via markdown
        ms.calls["markdown"].assert_called()
        ms.calls["subheader"].assert_called()
        # Le bouton de téléchargement CSV est affiché
        ms.calls["download_button"].assert_called_once()

    def test_with_df_full(self, mock_st) -> None:
        """Teste avec un df_full différent pour le score relatif."""
        from src.ui.pages import match_history as mod

        ms = mock_st(mod)
        dff = _make_history_df(10)
        df_full = _make_history_df(50)

        with patch.object(mod, "compute_performance_series") as mock_perf:
            mock_perf.return_value = pl.Series("performance", [50.0] * 10)
            mod.render_match_history_page(
                dff, "TestPlayer", "dummy.duckdb", "100", None, df_full=df_full
            )

        ms.calls["markdown"].assert_called()
