"""Tests pour la page Coéquipiers Vues (Sprint 7bis).

Couvre :
- _merge_trio_dataframes (fonction pure, test unitaire)
- render_single_teammate_view (flux de contrôle avec mocks)
- Edge cases : DataFrames vides
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import polars as pl

# =============================================================================
# Tests de _merge_trio_dataframes (fonction pure)
# =============================================================================


def _make_player_df(
    player_prefix: str, n: int = 5, *, with_start_time: bool = False
) -> pl.DataFrame:
    """Crée un DataFrame de stats joueur pour les tests trio."""
    np.random.seed(42)
    start = datetime(2025, 1, 1)
    data = {
        "match_id": [f"match_{i}" for i in range(n)],
        "kills": np.random.randint(5, 25, n).tolist(),
        "deaths": np.random.randint(3, 15, n).tolist(),
        "assists": np.random.randint(2, 12, n).tolist(),
        "accuracy": np.random.uniform(30, 60, n).tolist(),
        "ratio": np.random.uniform(0.5, 2.5, n).tolist(),
        "average_life_seconds": np.random.uniform(20, 60, n).tolist(),
    }
    if with_start_time:
        data["start_time"] = [start + timedelta(hours=i) for i in range(n)]
        data["time_played_seconds"] = np.random.randint(300, 900, n).tolist()
    return pl.DataFrame(data)


class TestMergeTrioDataframes:
    """Tests pour _merge_trio_dataframes."""

    def test_basic_merge(self) -> None:
        from src.ui.pages.teammates_views import _merge_trio_dataframes

        me = _make_player_df("me", 5, with_start_time=True)
        f1 = _make_player_df("f1", 5)
        f2 = _make_player_df("f2", 5)

        merged = _merge_trio_dataframes(me, f1, f2)
        assert merged.height == 5  # 5 matchs communs
        assert "f1_kills" in merged.columns
        assert "f2_kills" in merged.columns
        assert "kills" in merged.columns  # kills du joueur principal
        assert "start_time" in merged.columns

    def test_partial_overlap(self) -> None:
        """Seuls les matchs communs apparaissent dans le merge."""
        from src.ui.pages.teammates_views import _merge_trio_dataframes

        me = _make_player_df("me", 5, with_start_time=True)
        # f1 a seulement les matchs 0 et 1
        f1 = _make_player_df("f1", 2)
        # f2 a seulement les matchs 0, 1, 2
        f2 = _make_player_df("f2", 3)

        merged = _merge_trio_dataframes(me, f1, f2)
        assert merged.height == 2  # intersection = match_0, match_1

    def test_no_overlap(self) -> None:
        from src.ui.pages.teammates_views import _merge_trio_dataframes

        me = _make_player_df("me", 5, with_start_time=True)
        f1 = pl.DataFrame(
            {
                "match_id": ["other_1", "other_2"],
                "kills": [5, 10],
                "deaths": [3, 5],
                "assists": [2, 3],
                "accuracy": [40.0, 50.0],
                "ratio": [1.0, 2.0],
                "average_life_seconds": [30.0, 40.0],
            }
        )
        f2 = _make_player_df("f2", 5)

        merged = _merge_trio_dataframes(me, f1, f2)
        assert merged.height == 0


# =============================================================================
# Tests render_single_teammate_view
# =============================================================================


def _make_match_df(n: int = 10) -> pl.DataFrame:
    """Crée un DataFrame de matchs pour les tests."""
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
            "outcome": np.random.choice([1, 2, 3], n).tolist(),
            "map_name": np.random.choice(["Recharge", "Streets"], n).tolist(),
            "time_played_seconds": np.random.randint(300, 900, n).tolist(),
            "average_life_seconds": np.random.uniform(20, 60, n).tolist(),
            "kills_per_min": np.random.uniform(0.3, 1.5, n).tolist(),
            "deaths_per_min": np.random.uniform(0.2, 1.0, n).tolist(),
            "assists_per_min": np.random.uniform(0.1, 0.8, n).tolist(),
        }
    )


class TestRenderSingleTeammateView:
    """Tests de render_single_teammate_view."""

    def test_no_matches_found_warning(self, mock_st) -> None:
        """Affiche un warning si aucun match trouvé avec le coéquipier."""
        from src.ui.pages import teammates_views as mod

        ms = mock_st(mod)
        ms.set_columns_dynamic()

        df = _make_match_df()

        # Mock cached_friend_matches_df pour retourner un DataFrame vide
        with patch.object(
            mod, "cached_friend_matches_df", return_value=pl.DataFrame(schema={"match_id": pl.Utf8})
        ):
            mod.render_single_teammate_view(
                df=df,
                dff=df,
                me_name="TestPlayer",
                xuid="100",
                db_path="dummy.duckdb",
                db_key=None,
                picked_xuids=["200"],
                apply_current_filters=False,
                same_team_only=True,
                show_smooth=True,
                assign_player_colors_fn=lambda *_a, **_kw: {},
                plot_multi_metric_bars_fn=lambda *_a, **_kw: MagicMock(),
                top_medals_fn=lambda *_a, **_kw: [],
                load_teammate_stats_fn=lambda *_a, **_kw: pl.DataFrame(),
                enrich_series_fn=lambda *_a, **_kw: {},
            )

        ms.calls["warning"].assert_called()

    def test_with_shared_matches(self, mock_st) -> None:
        """Flux nominal avec des matchs partagés."""
        from src.ui.pages import teammates_views as mod

        ms = mock_st(mod)
        ms.set_columns_dynamic()
        ms.session_state["player_xuid"] = "100"

        df = _make_match_df(10)
        friend_df = _make_match_df(10)

        # Préparer le DataFrame de matchs partagés
        shared_df = pl.DataFrame(
            {
                "match_id": df["match_id"].to_list(),
                "outcome": [2] * 10,
                "is_same_team": [True] * 10,
            }
        )

        with (
            patch.object(mod, "cached_friend_matches_df", return_value=shared_df),
            patch.object(mod, "render_outcome_bar_chart"),
            patch.object(mod, "_render_match_details_expander"),
            patch.object(mod, "_render_shared_stats_metrics"),
            patch.object(mod, "_render_shared_medals"),
            patch.object(mod, "display_name_from_xuid", return_value="FriendName"),
            patch.object(mod, "compute_aggregated_stats", return_value={}),
            patch.object(mod, "compute_global_ratio", return_value=1.5),
            patch.object(
                mod,
                "compute_outcome_rates",
                return_value=MagicMock(wins=5, losses=3, draws=2, total=10),
            ),
            patch.object(
                mod,
                "compute_map_breakdown",
                return_value=MagicMock(
                    breakdown=pl.DataFrame({"map_name": ["Streets"], "matches": [5]})
                ),
            ),
        ):
            mod.render_single_teammate_view(
                df=df,
                dff=df,
                me_name="TestPlayer",
                xuid="100",
                db_path="dummy.duckdb",
                db_key=None,
                picked_xuids=["200"],
                apply_current_filters=False,
                same_team_only=True,
                show_smooth=True,
                assign_player_colors_fn=lambda *_a, **_kw: {
                    "TestPlayer": "#00ff00",
                    "FriendName": "#ff0000",
                },
                plot_multi_metric_bars_fn=lambda *_a, **_kw: MagicMock(),
                top_medals_fn=lambda *_a, **_kw: [],
                load_teammate_stats_fn=lambda *_a, **_kw: friend_df,
                enrich_series_fn=lambda *_a, **_kw: {
                    "friend_names": {"200": "FriendName"},
                    "colors_by_name": {"TestPlayer": "#00ff00", "FriendName": "#ff0000"},
                    "series": [],
                },
            )

        # Pas de crash = OK
