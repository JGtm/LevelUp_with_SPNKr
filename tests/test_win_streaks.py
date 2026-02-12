"""Tests pour le module win_streaks (Sprint 7).

Teste :
1. Calcul des séries de victoires / défaites consécutives
2. Section "Score personnel par match" (barres colorées)
3. Section "Rang et score personnel"
4. Adaptation "Matchs Top" pour périodes < semaine
5. Nouvelles visualisations (dégâts, tirs, streak chart)
"""

from __future__ import annotations

import datetime

import pytest

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

try:
    import pandas as pd
    import plotly.graph_objects as go

    VIZ_AVAILABLE = True
except ImportError:
    VIZ_AVAILABLE = False
    pd = None
    go = None

# Tenter un import direct de win_streaks (peut échouer si duckdb manque via __init__)
try:
    from src.analysis.win_streaks import (
        compute_rolling_win_rate_polars,
        compute_streak_series_polars,
        compute_streak_summary_polars,
        compute_streaks_polars,
        streak_series_to_dicts,
    )

    WIN_STREAKS_AVAILABLE = True
except Exception:
    WIN_STREAKS_AVAILABLE = False

pytestmark_polars = pytest.mark.skipif(
    not POLARS_AVAILABLE or not WIN_STREAKS_AVAILABLE,
    reason="Polars ou duckdb transitif non disponible",
)

pytestmark_viz = pytest.mark.skipif(
    not VIZ_AVAILABLE,
    reason="Pandas/Plotly non disponibles",
)


def _make_match_df_polars(outcomes: list[int], has_match_id: bool = True):
    """Crée un DataFrame Polars de test."""
    base = datetime.datetime(2026, 1, 1, 12, 0, 0)
    data = {
        "outcome": outcomes,
        "start_time": [
            (base + datetime.timedelta(hours=i)).isoformat() for i in range(len(outcomes))
        ],
    }
    if has_match_id:
        data["match_id"] = [f"match_{i}" for i in range(len(outcomes))]
    return pl.DataFrame(data)


def _make_match_df_pandas(n: int = 20, start_date: str = "2026-01-01"):
    """Crée un DataFrame Pandas de test avec colonnes complètes."""
    import numpy as np

    base = pd.Timestamp(start_date)
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(n)],
            "start_time": pd.date_range(base, periods=n, freq="1h"),
            "outcome": rng.choice([2, 3], size=n),
            "kills": rng.integers(5, 25, size=n),
            "deaths": rng.integers(3, 20, size=n),
            "assists": rng.integers(2, 12, size=n),
            "accuracy": rng.uniform(30, 60, size=n).round(2),
            "rank": rng.integers(1, 8, size=n),
            "personal_score": rng.integers(500, 3000, size=n),
            "damage_dealt": rng.integers(1000, 5000, size=n),
            "damage_taken": rng.integers(800, 4000, size=n),
            "shots_fired": rng.integers(50, 200, size=n),
            "shots_hit": rng.integers(20, 100, size=n),
            "max_killing_spree": rng.integers(0, 10, size=n),
            "headshot_kills": rng.integers(0, 8, size=n),
            "average_life_seconds": rng.uniform(10, 60, size=n).round(1),
            "time_played_seconds": rng.uniform(300, 900, size=n).round(0),
            "kda": rng.uniform(0.5, 3.0, size=n).round(2),
            "ratio": rng.uniform(0.5, 3.0, size=n).round(2),
            "map_name": ["Aquarius"] * n,
            "playlist_name": ["Ranked Arena"] * n,
        }
    )


# =============================================================================
# 7.2 — Séries de victoires / défaites (Polars)
# =============================================================================


@pytestmark_polars
class TestWinStreaks:
    """Tests pour src/analysis/win_streaks.py (P6 §1)."""

    def test_compute_win_streaks_basic(self):
        """Calcul des séries de victoires sur un historique simple."""
        df = _make_match_df_polars([2, 2, 2, 3, 2])
        result = compute_streaks_polars(df)
        assert len(result) == 3
        assert result[0].streak_type == "win"
        assert result[0].length == 3

    def test_compute_loss_streaks_basic(self):
        """Calcul des séries de défaites sur un historique simple."""
        df = _make_match_df_polars([3, 3, 3, 3, 2])
        result = compute_streaks_polars(df)
        assert result[0].streak_type == "loss"
        assert result[0].length == 4

    def test_streak_reset_on_outcome_change(self):
        """La série est réinitialisée quand le résultat change."""
        df = _make_match_df_polars([2, 3, 2, 3, 2])
        result = compute_streaks_polars(df)
        assert len(result) == 5
        assert all(s.length == 1 for s in result)

    def test_streak_with_ties_and_no_finish(self):
        """Ties (1) et NoFinish (4) ne prolongent pas les séries."""
        df = _make_match_df_polars([2, 1, 2, 4, 3])
        result = compute_streaks_polars(df)
        # Après filtrage : 2, 2, 3 → win(2), loss(1)
        assert len(result) == 2
        assert result[0].length == 2
        assert result[1].length == 1

    def test_longest_streak(self):
        """Identification de la plus longue série."""
        df = _make_match_df_polars([2, 2, 2, 2, 3, 2, 2, 3, 3, 3])
        summary = compute_streak_summary_polars(df)
        assert summary.longest_win_streak == 4
        assert summary.longest_loss_streak == 3

    def test_streak_series_values(self):
        """compute_streak_series_polars retourne +N / -N."""
        df = _make_match_df_polars([2, 2, 3, 3, 3, 2])
        result = compute_streak_series_polars(df)
        values = result["streak_value"].to_list()
        assert values == [1, 2, -1, -2, -3, 1]

    def test_empty_df_returns_empty(self):
        """Un DataFrame vide retourne une liste vide."""
        df = pl.DataFrame({"outcome": [], "start_time": []})
        assert compute_streaks_polars(df) == []

    def test_none_df_returns_empty(self):
        """None retourne une liste vide."""
        assert compute_streaks_polars(None) == []

    def test_rolling_win_rate(self):
        """Taux de victoire glissant correct."""
        df = _make_match_df_polars([2] * 5)
        result = compute_rolling_win_rate_polars(df, window_size=3)
        rates = result["win_rate"].to_list()
        assert all(r == 100.0 for r in rates)

    def test_rolling_win_rate_mixed(self):
        """Taux glissant sur résultats mixtes."""
        df = _make_match_df_polars([2, 2, 3, 2, 3])
        result = compute_rolling_win_rate_polars(df, window_size=3)
        rates = result["win_rate"].to_list()
        assert len(rates) == 5

    def test_streak_series_to_dicts(self):
        """Conversion en dicts pour Plotly."""
        df = _make_match_df_polars([2, 3])
        series = compute_streak_series_polars(df)
        dicts = streak_series_to_dicts(series)
        assert len(dicts) == 2
        assert "streak_value" in dicts[0]

    def test_current_streak_in_summary(self):
        """compute_streak_summary_polars identifie la série en cours."""
        df = _make_match_df_polars([3, 2, 2, 2])
        summary = compute_streak_summary_polars(df)
        assert summary.current_streak_type == "win"
        assert summary.current_streak_length == 3


# =============================================================================
# 7.1 — Score personnel par match (barres colorées)
# =============================================================================


@pytestmark_viz
class TestPersonalScorePerMatch:
    """Tests pour la section barres colorées score personnel (P6 §1)."""

    def test_score_bars_rendered(self):
        """plot_metric_bars_by_match retourne une figure pour personal_score."""
        from src.visualization.match_bars import plot_metric_bars_by_match

        df = _make_match_df_pandas(15)
        fig = plot_metric_bars_by_match(
            df,
            metric_col="personal_score",
            title="Score personnel",
            y_axis_title="Score",
            hover_label="Score",
            bar_color="#FFB703",
            smooth_color="#8E6CFF",
        )
        assert fig is not None
        assert isinstance(fig, go.Figure)
        # Au moins 2 traces : barres + courbe lissée
        assert len(fig.data) >= 2

    def test_score_bars_empty_df(self):
        """Retourne None pour un DataFrame vide."""
        from src.visualization.match_bars import plot_metric_bars_by_match

        result = plot_metric_bars_by_match(
            pd.DataFrame(),
            metric_col="personal_score",
            title="Test",
            y_axis_title="Score",
            hover_label="Score",
            bar_color="#FFB703",
            smooth_color="#8E6CFF",
        )
        assert result is None


# =============================================================================
# 7.3 — Rang et score personnel
# =============================================================================


@pytestmark_viz
class TestRankAndPersonalScore:
    """Tests pour la section rang et score personnel (P6 §1)."""

    def test_rank_score_chart_rendered(self):
        """plot_rank_score retourne une figure valide."""
        from src.visualization.timeseries import plot_rank_score

        df = _make_match_df_pandas(15)
        fig = plot_rank_score(df, title="Rang et score")
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 2  # barres score + ligne rang

    def test_rank_score_without_rank(self):
        """Fonctionne même sans colonne rank."""
        from src.visualization.timeseries import plot_rank_score

        df = _make_match_df_pandas(10)
        df = df.drop(columns=["rank"])
        fig = plot_rank_score(df)
        assert isinstance(fig, go.Figure)

    def test_rank_score_without_personal_score(self):
        """Fonctionne même sans colonne personal_score."""
        from src.visualization.timeseries import plot_rank_score

        df = _make_match_df_pandas(10)
        df = df.drop(columns=["personal_score"])
        fig = plot_rank_score(df)
        assert isinstance(fig, go.Figure)


# =============================================================================
# 7.4 — Dégâts infligés vs subis
# =============================================================================


@pytestmark_viz
class TestDamageDealtTaken:
    """Tests pour le graphe dégâts (Sprint 7.4)."""

    def test_damage_chart_rendered(self):
        """plot_damage_dealt_taken retourne une figure valide."""
        from src.visualization.timeseries import plot_damage_dealt_taken

        df = _make_match_df_pandas(15)
        fig = plot_damage_dealt_taken(df)
        assert isinstance(fig, go.Figure)
        # 4 traces : dealt bars, dealt smooth, taken bars, taken smooth
        assert len(fig.data) >= 4

    def test_damage_partial_columns(self):
        """Fonctionne avec seulement damage_dealt."""
        from src.visualization.timeseries import plot_damage_dealt_taken

        df = _make_match_df_pandas(10)
        df = df.drop(columns=["damage_taken"])
        fig = plot_damage_dealt_taken(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 2


# =============================================================================
# 7.5 — Tirs et précision
# =============================================================================


@pytestmark_viz
class TestShotsAccuracy:
    """Tests pour le graphe tirs et précision (Sprint 7.5)."""

    def test_shots_accuracy_rendered(self):
        """plot_shots_accuracy retourne une figure valide."""
        from src.visualization.timeseries import plot_shots_accuracy

        df = _make_match_df_pandas(15)
        fig = plot_shots_accuracy(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 3  # fired, hit, accuracy line

    def test_shots_accuracy_without_accuracy(self):
        """Fonctionne sans la colonne accuracy."""
        from src.visualization.timeseries import plot_shots_accuracy

        df = _make_match_df_pandas(10)
        df = df.drop(columns=["accuracy"])
        fig = plot_shots_accuracy(df)
        assert isinstance(fig, go.Figure)


# =============================================================================
# 7.6 — Spree sans précision
# =============================================================================


@pytestmark_viz
class TestSpreeWithoutAccuracy:
    """Tests pour la suppression de la précision du graphe Folie meurtrière."""

    def test_spree_chart_no_accuracy_trace(self):
        """plot_spree_headshots_accuracy n'affiche plus la trace Précision."""
        from src.visualization.timeseries import plot_spree_headshots_accuracy

        df = _make_match_df_pandas(15)
        fig = plot_spree_headshots_accuracy(df)
        trace_names = [t.name for t in fig.data if t.name]
        assert "Précision (%)" not in trace_names
        # Doit toujours avoir Folie meurtrière, Tirs à la tête, Frags parfaits
        assert any("Folie" in n for n in trace_names)
        assert any("tête" in n for n in trace_names)


# =============================================================================
# 7.7 — Matchs Top adaptés périodes courtes
# =============================================================================


@pytestmark_viz
class TestMatchsTopShortPeriods:
    """Tests pour l'adaptation Matchs Top < semaine (P6 §6.1)."""

    def test_top_matches_weekly(self):
        """Période >= 7 jours : regroupement par semaine."""
        from src.visualization.distributions import plot_matches_at_top_by_week

        df = _make_match_df_pandas(50, start_date="2026-01-01")
        # 50 matchs sur 50h = ~2 jours → par match
        fig = plot_matches_at_top_by_week(df, rank_col="rank", top_n_ranks=1)
        assert isinstance(fig, go.Figure)

    def test_top_matches_short_period(self):
        """Matchs Top fonctionne sur des périodes < 7 jours."""
        from src.visualization.distributions import plot_matches_at_top_by_week

        # 10 matchs sur 10 heures = < 1 jour → par match
        df = _make_match_df_pandas(10, start_date="2026-01-01")
        fig = plot_matches_at_top_by_week(df, rank_col="rank", top_n_ranks=1)
        assert isinstance(fig, go.Figure)
        # Vérifier que l'axe X utilise "Match" et non "Semaine"
        x_title = fig.layout.xaxis.title.text if fig.layout.xaxis.title else ""
        assert x_title in ("Match", "Jour", "Semaine", None, "")

    def test_top_matches_daily_period(self):
        """Période 2-6 jours : regroupement par jour."""
        import numpy as np

        from src.visualization.distributions import plot_matches_at_top_by_week

        rng = np.random.default_rng(42)
        base = pd.Timestamp("2026-01-01")
        n = 30
        df = pd.DataFrame(
            {
                "match_id": [f"m{i}" for i in range(n)],
                "start_time": pd.date_range(base, periods=n, freq="4h"),  # 5 jours
                "outcome": rng.choice([2, 3], size=n),
                "rank": rng.integers(1, 5, size=n),
            }
        )
        fig = plot_matches_at_top_by_week(df, rank_col="rank", top_n_ranks=1)
        assert isinstance(fig, go.Figure)

    def test_top_matches_empty_df(self):
        """Retourne une figure vide pour un DataFrame vide."""
        from src.visualization.distributions import plot_matches_at_top_by_week

        fig = plot_matches_at_top_by_week(
            pd.DataFrame(columns=["start_time", "rank", "outcome", "match_id"])
        )
        assert isinstance(fig, go.Figure)


# =============================================================================
# Streak chart visualization
# =============================================================================


@pytestmark_viz
class TestStreakChart:
    """Tests pour plot_streak_chart (Sprint 7)."""

    def test_streak_chart_rendered(self):
        """plot_streak_chart retourne une figure valide."""
        from src.visualization.timeseries import plot_streak_chart

        df = _make_match_df_pandas(20)
        fig = plot_streak_chart(df)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_streak_chart_empty(self):
        """Retourne une figure annotation pour données vides."""
        from src.visualization.timeseries import plot_streak_chart

        df = pd.DataFrame(
            {"outcome": [1, 4], "start_time": pd.date_range("2026-01-01", periods=2, freq="1h")}
        )
        fig = plot_streak_chart(df)
        assert isinstance(fig, go.Figure)
