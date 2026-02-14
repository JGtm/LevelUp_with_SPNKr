"""Tests pour la page Victoires/Défaites (Sprint 7bis).

Couvre :
- Fonctions pures (_to_float, _style_map_table_row, _styler_map)
- render_win_loss_page avec MockStreamlit (flux de contrôle)
- Edge cases : DataFrame vide, que des victoires, que des défaites
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import polars as pl
import pytest

# =============================================================================
# Tests des fonctions pures
# =============================================================================


class TestToFloat:
    """Tests pour _to_float."""

    def test_none(self) -> None:
        from src.ui.pages.win_loss import _to_float

        assert _to_float(None) is None

    def test_int(self) -> None:
        from src.ui.pages.win_loss import _to_float

        assert _to_float(42) == 42.0

    def test_float(self) -> None:
        from src.ui.pages.win_loss import _to_float

        assert _to_float(3.14) == pytest.approx(3.14)

    def test_string_invalid(self) -> None:
        from src.ui.pages.win_loss import _to_float

        assert _to_float("not_a_number") is None

    def test_string_numeric(self) -> None:
        from src.ui.pages.win_loss import _to_float

        assert _to_float("42.5") == pytest.approx(42.5)

    def test_nan(self) -> None:
        from src.ui.pages.win_loss import _to_float

        assert _to_float(float("nan")) is None


class TestStylerMap:
    """Tests pour _styler_map."""

    def test_returns_styled(self) -> None:
        import pandas as pd

        from src.ui.pages.win_loss import _styler_map

        df = pd.DataFrame({"a": [1, 2]})
        styler = df.style
        result = _styler_map(styler, lambda _v: "", subset=["a"])
        assert result is not None


# =============================================================================
# Tests du rendu avec MockStreamlit
# =============================================================================


def _make_win_loss_df(
    n: int = 20, *, all_wins: bool = False, all_losses: bool = False
) -> pl.DataFrame:
    """Crée un DataFrame synthétique pour la page win_loss."""
    np.random.seed(42)
    start = datetime(2025, 1, 1)

    if all_wins:
        outcomes = [2] * n
    elif all_losses:
        outcomes = [3] * n
    else:
        outcomes = np.random.choice([1, 2, 3, 4], n).tolist()

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
            "outcome": outcomes,
            "map_name": np.random.choice(["Recharge", "Streets", "Live Fire"], n).tolist(),
            "playlist_name": np.random.choice(["Ranked", "Quick Play"], n).tolist(),
            "pair_name": np.random.choice(["Arena: Slayer", "Arena: CTF"], n).tolist(),
            "time_played_seconds": np.random.randint(300, 900, n).tolist(),
            "kills_per_min": np.random.uniform(0.3, 1.5, n).tolist(),
            "deaths_per_min": np.random.uniform(0.2, 1.0, n).tolist(),
            "assists_per_min": np.random.uniform(0.1, 0.8, n).tolist(),
            "headshot_kills": np.random.randint(1, 10, n).tolist(),
            "max_killing_spree": np.random.randint(0, 8, n).tolist(),
            "average_life_seconds": np.random.uniform(20, 60, n).tolist(),
            "mode_category": np.random.choice(["Slayer", "CTF", "Oddball"], n).tolist(),
            "personal_score": np.random.randint(800, 3000, n).tolist(),
            "rank": np.random.randint(1, 9, n).tolist(),
        }
    )


class TestRenderWinLossPage:
    """Tests de la render function avec MockStreamlit."""

    def test_empty_df_shows_warning(self, mock_st) -> None:
        """Un DataFrame vide affiche un warning."""
        from src.ui.pages import win_loss as mod

        ms = mock_st(mod)
        empty_df = pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "outcome": pl.Int64,
            }
        )
        mod.render_win_loss_page(empty_df, empty_df, None, "dummy.duckdb", "100", None)
        ms.calls["warning"].assert_called_once()

    def test_normal_flow(self, mock_st) -> None:
        """Parcours nominal : les sections sont rendues sans erreur."""
        from src.ui.pages import win_loss as mod

        ms = mock_st(mod)
        ms.set_columns_dynamic()
        ms.session_state["filter_mode"] = "Global"

        dff = _make_win_loss_df(20)

        # Mock les fonctions de visualisation pour éviter des dépendances lourdes
        with (
            patch.object(mod, "plot_outcomes_over_time", return_value=(MagicMock(), "semaine")),
            patch.object(mod, "plot_stacked_outcomes_by_category", return_value=MagicMock()),
            patch.object(mod, "plot_win_ratio_heatmap", return_value=MagicMock()),
            patch.object(mod, "plot_matches_at_top_by_week", return_value=MagicMock()),
            patch.object(mod, "plot_streak_chart", return_value=MagicMock()),
            patch.object(mod, "plot_metric_bars_by_match", return_value=MagicMock()),
            patch.object(mod, "WinLossService") as mock_svc,
        ):
            # Mock pour compute_period_table
            period_result = MagicMock()
            period_result.is_empty = True
            mock_svc.compute_period_table.return_value = period_result

            # Mock pour get_friend_scope_df
            mock_svc.get_friend_scope_df.return_value = dff

            # Mock pour compute_map_breakdown
            map_result = MagicMock()
            map_result.is_empty = True
            mock_svc.compute_map_breakdown.return_value = map_result

            mod.render_win_loss_page(dff, dff, None, "dummy.duckdb", "100", None)

        # Vérifie que des graphiques ont été rendus
        assert ms.calls["plotly_chart"].call_count >= 1

    def test_all_wins_flow(self, mock_st) -> None:
        """Fonctionne quand toutes les parties sont des victoires."""
        from src.ui.pages import win_loss as mod

        ms = mock_st(mod)
        ms.set_columns_dynamic()
        ms.session_state["filter_mode"] = "Global"

        dff = _make_win_loss_df(10, all_wins=True)

        with (
            patch.object(mod, "plot_outcomes_over_time", return_value=(MagicMock(), "semaine")),
            patch.object(mod, "plot_stacked_outcomes_by_category", return_value=MagicMock()),
            patch.object(mod, "plot_win_ratio_heatmap", return_value=MagicMock()),
            patch.object(mod, "plot_matches_at_top_by_week", return_value=MagicMock()),
            patch.object(mod, "plot_streak_chart", return_value=MagicMock()),
            patch.object(mod, "plot_metric_bars_by_match", return_value=MagicMock()),
            patch.object(mod, "WinLossService") as mock_svc,
        ):
            period_result = MagicMock()
            period_result.is_empty = True
            mock_svc.compute_period_table.return_value = period_result
            mock_svc.get_friend_scope_df.return_value = dff
            map_result = MagicMock()
            map_result.is_empty = True
            mock_svc.compute_map_breakdown.return_value = map_result

            mod.render_win_loss_page(dff, dff, None, "dummy.duckdb", "100", None)

        # Le warning "Pas assez de matchs par map" est attendu (map_result.is_empty=True)
        assert ms.calls["plotly_chart"].call_count >= 1

    def test_all_losses_flow(self, mock_st) -> None:
        """Fonctionne quand toutes les parties sont des défaites."""
        from src.ui.pages import win_loss as mod

        ms = mock_st(mod)
        ms.set_columns_dynamic()
        ms.session_state["filter_mode"] = "Global"

        dff = _make_win_loss_df(10, all_losses=True)

        with (
            patch.object(mod, "plot_outcomes_over_time", return_value=(MagicMock(), "semaine")),
            patch.object(mod, "plot_stacked_outcomes_by_category", return_value=MagicMock()),
            patch.object(mod, "plot_win_ratio_heatmap", return_value=MagicMock()),
            patch.object(mod, "plot_matches_at_top_by_week", return_value=MagicMock()),
            patch.object(mod, "plot_streak_chart", return_value=MagicMock()),
            patch.object(mod, "plot_metric_bars_by_match", return_value=MagicMock()),
            patch.object(mod, "WinLossService") as mock_svc,
        ):
            period_result = MagicMock()
            period_result.is_empty = True
            mock_svc.compute_period_table.return_value = period_result
            mock_svc.get_friend_scope_df.return_value = dff
            map_result = MagicMock()
            map_result.is_empty = True
            mock_svc.compute_map_breakdown.return_value = map_result

            mod.render_win_loss_page(dff, dff, None, "dummy.duckdb", "100", None)

        # Le warning "Pas assez de matchs par map" est attendu (map_result.is_empty=True)
        assert ms.calls["plotly_chart"].call_count >= 1


class TestRenderSubSections:
    """Tests des sous-sections individuelles."""

    def test_render_outcomes_over_time(self, mock_st) -> None:
        from src.ui.pages import win_loss as mod

        ms = mock_st(mod)
        dff = _make_win_loss_df(10)

        with patch.object(mod, "plot_outcomes_over_time", return_value=(MagicMock(), "jour")):
            result = mod._render_outcomes_over_time(dff, is_session_scope=False)

        assert result == "jour"
        ms.calls["plotly_chart"].assert_called_once()

    def test_render_streak_section_no_outcome(self, mock_st) -> None:
        from src.ui.pages import win_loss as mod

        ms = mock_st(mod)
        dff = pl.DataFrame({"match_id": ["m1"], "kills": [5]})
        mod._render_streak_section(dff)
        ms.calls["info"].assert_called()

    def test_render_personal_score_no_column(self, mock_st) -> None:
        from src.ui.pages import win_loss as mod

        ms = mock_st(mod)
        dff = pl.DataFrame({"match_id": ["m1"], "kills": [5]})
        # Ne devrait rien afficher (pas de personal_score)
        mod._render_personal_score_section(dff)
        ms.calls["divider"].assert_not_called()

    def test_render_heatmap_section_no_start_time(self, mock_st) -> None:
        from src.ui.pages import win_loss as mod

        ms = mock_st(mod)
        dff = pl.DataFrame({"match_id": ["m1"], "outcome": [2]})
        mod._render_heatmap_section(dff)
        ms.calls["info"].assert_called()
