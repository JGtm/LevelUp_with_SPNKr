"""Tests de contrats pour les services data (Sprint 14).

Vérifie que :
- Les services retournent des types corrects (dataclasses typées).
- Les contrats d'interface page → service sont respectés.
- Les services gèrent correctement les cas limites (vide, colonnes manquantes).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import polars as pl

from src.data.services.teammates_service import (
    EnrichedSeries,
    ImpactData,
    TeammatesService,
    TeammateStats,
)
from src.data.services.timeseries_service import (
    CumulativeMetrics,
    FirstEventData,
    PerfectKillsData,
    RollingWinRateData,
    ScorePerMinuteData,
    TimeseriesService,
)
from src.data.services.win_loss_service import (
    MapBreakdownResult,
    PeriodTable,
    WinLossService,
)

# ─── Fixtures ──────────────────────────────────────────────────────────


def _make_match_df(n: int = 20) -> pd.DataFrame:
    """Construit un DataFrame Pandas synthétique de matchs (pour compute_period_table)."""
    base_time = datetime(2026, 1, 1, 20, 0, 0)
    return pd.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(n)],
            "start_time": pd.to_datetime([base_time + timedelta(hours=i * 2) for i in range(n)]),
            "kills": [10 + i % 5 for i in range(n)],
            "deaths": [8 + i % 3 for i in range(n)],
            "assists": [3 + i % 4 for i in range(n)],
            "accuracy": [48.0 + i * 0.5 for i in range(n)],
            "ratio": [1.0 + (i % 5) * 0.1 for i in range(n)],
            "kda": [5.0 + i * 0.3 for i in range(n)],
            "outcome": [2 if i % 3 != 0 else 3 for i in range(n)],
            "time_played_seconds": [600 + i * 10 for i in range(n)],
            "average_life_seconds": [25.0 + i for i in range(n)],
            "personal_score": [1000 + i * 50 for i in range(n)],
            "map_name": [f"Map{i % 4}" for i in range(n)],
            "playlist_name": ["Ranked" if i % 2 == 0 else "Quick Play" for i in range(n)],
            "pair_name": ["Slayer" if i % 2 == 0 else "CTF" for i in range(n)],
            "team_mmr": [1500 + i * 10 for i in range(n)],
            "enemy_mmr": [1510 + i * 8 for i in range(n)],
        }
    )


def _make_match_pl(n: int = 20) -> pl.DataFrame:
    """Construit un DataFrame Polars synthétique de matchs."""
    base_time = datetime(2026, 1, 1, 20, 0, 0)
    return pl.DataFrame(
        {
            "match_id": [f"m{i}" for i in range(n)],
            "start_time": [base_time + timedelta(hours=i * 2) for i in range(n)],
            "kills": [10 + i % 5 for i in range(n)],
            "deaths": [8 + i % 3 for i in range(n)],
            "assists": [3 + i % 4 for i in range(n)],
            "accuracy": [48.0 + i * 0.5 for i in range(n)],
            "ratio": [1.0 + (i % 5) * 0.1 for i in range(n)],
            "kda": [5.0 + i * 0.3 for i in range(n)],
            "outcome": [2 if i % 3 != 0 else 3 for i in range(n)],
            "time_played_seconds": [600 + i * 10 for i in range(n)],
            "average_life_seconds": [25.0 + i for i in range(n)],
            "personal_score": [1000 + i * 50 for i in range(n)],
            "map_name": [f"Map{i % 4}" for i in range(n)],
            "playlist_name": ["Ranked" if i % 2 == 0 else "Quick Play" for i in range(n)],
            "pair_name": ["Slayer" if i % 2 == 0 else "CTF" for i in range(n)],
            "team_mmr": [1500 + i * 10 for i in range(n)],
            "enemy_mmr": [1510 + i * 8 for i in range(n)],
        }
    )


def _make_empty_df() -> pd.DataFrame:
    """Construit un DataFrame Pandas vide (pour compute_period_table)."""
    return pd.DataFrame()


def _make_minimal_df() -> pd.DataFrame:
    """Construit un DataFrame Pandas avec 3 matchs."""
    return _make_match_df(3)


# ═══════════════════════════════════════════════════════════════════════
# TimeseriesService — Contrats
# ═══════════════════════════════════════════════════════════════════════


class TestTimeseriesServiceContracts:
    """Contrats d'interface pour TimeseriesService."""

    def test_enrich_performance_score_adds_column(self) -> None:
        """Le service ajoute la colonne performance_score."""
        dff = _make_match_pl()
        result = TimeseriesService.enrich_performance_score(dff)
        assert "performance_score" in result.columns
        assert len(result) == len(dff)

    def test_enrich_performance_score_idempotent(self) -> None:
        """Un 2e appel ne modifie pas la colonne existante."""
        dff = _make_match_pl()
        result1 = TimeseriesService.enrich_performance_score(dff)
        result2 = TimeseriesService.enrich_performance_score(result1)
        assert result1["performance_score"].to_list() == result2["performance_score"].to_list()

    def test_compute_cumulative_metrics_returns_dataclass(self) -> None:
        """Le service retourne CumulativeMetrics avec les bonnes propriétés."""
        dff = _make_match_pl(20)
        result = TimeseriesService.compute_cumulative_metrics(dff)
        assert result is not None
        assert isinstance(result, CumulativeMetrics)
        assert isinstance(result.cumul_net, pl.DataFrame)
        assert isinstance(result.cumul_kd, pl.DataFrame)
        assert isinstance(result.rolling_kd, pl.DataFrame)
        assert result.has_enough_for_trend is True

    def test_compute_cumulative_metrics_missing_columns(self) -> None:
        """Retourne None si colonnes manquantes."""
        dff = pl.DataFrame({"x": [1, 2, 3]})
        result = TimeseriesService.compute_cumulative_metrics(dff)
        assert result is None

    def test_compute_cumulative_metrics_too_few_for_trend(self) -> None:
        """has_enough_for_trend=False avec < 4 matchs."""
        dff = _make_match_pl(3)
        result = TimeseriesService.compute_cumulative_metrics(dff)
        assert result is not None
        assert result.has_enough_for_trend is False

    def test_score_per_minute_with_data(self) -> None:
        """Retourne has_data=True avec assez de données."""
        dff = _make_match_pl(10)
        result = TimeseriesService.compute_score_per_minute(dff)
        assert isinstance(result, ScorePerMinuteData)
        assert result.has_data is True
        assert len(result.values) > 0

    def test_score_per_minute_missing_columns(self) -> None:
        """Retourne has_data=False si colonnes manquantes."""
        dff = pl.DataFrame({"kills": [1, 2, 3]})
        result = TimeseriesService.compute_score_per_minute(dff)
        assert result.has_data is False

    def test_rolling_win_rate_with_data(self) -> None:
        """Retourne has_data=True avec >= 10 matchs."""
        dff = _make_match_pl(20)
        result = TimeseriesService.compute_rolling_win_rate(dff)
        assert isinstance(result, RollingWinRateData)
        assert result.has_data is True
        assert result.missing_column is False

    def test_rolling_win_rate_missing_outcome(self) -> None:
        """Retourne missing_column=True sans outcome."""
        dff = pl.DataFrame({"kills": list(range(20))})
        result = TimeseriesService.compute_rolling_win_rate(dff)
        assert result.missing_column is True

    def test_rolling_win_rate_not_enough_matches(self) -> None:
        """Retourne not_enough_matches=True avec < 10 matchs."""
        dff = _make_match_pl(5)
        result = TimeseriesService.compute_rolling_win_rate(dff)
        assert result.not_enough_matches is True

    def test_load_first_events_no_db(self) -> None:
        """Retourne available=False sans DB."""
        result = TimeseriesService.load_first_event_times(None, None, [])
        assert isinstance(result, FirstEventData)
        assert result.available is False

    def test_load_perfect_kills_no_db(self) -> None:
        """Retourne counts=None sans DB."""
        result = TimeseriesService.load_perfect_kills(None, None, [])
        assert isinstance(result, PerfectKillsData)
        assert result.counts is None


# ═══════════════════════════════════════════════════════════════════════
# WinLossService — Contrats
# ═══════════════════════════════════════════════════════════════════════


class TestWinLossServiceContracts:
    """Contrats d'interface pour WinLossService."""

    def test_period_table_returns_dataclass(self) -> None:
        """Le service retourne un PeriodTable avec table non vide."""
        dff = _make_match_df(20)
        result = WinLossService.compute_period_table(dff, "semaine")
        assert isinstance(result, PeriodTable)
        assert result.is_empty is False
        assert isinstance(result.table, pd.DataFrame)
        assert "Victoires" in result.table.columns
        assert "Défaites" in result.table.columns
        assert "Total" in result.table.columns

    def test_period_table_empty_df(self) -> None:
        """Retourne is_empty=True pour un DataFrame vide."""
        dff = _make_empty_df()
        result = WinLossService.compute_period_table(dff, "semaine")
        assert result.is_empty is True

    def test_period_table_session_scope(self) -> None:
        """Le bucketing session produit un tableau valide."""
        dff = _make_match_df(10)
        result = WinLossService.compute_period_table(dff, "match", is_session_scope=True)
        assert result.is_empty is False
        assert len(result.table) > 0

    def test_map_breakdown_returns_dataclass(self) -> None:
        """Le service retourne MapBreakdownResult."""
        dff = _make_match_pl(20)
        result = WinLossService.compute_map_breakdown(dff, min_matches=1)
        assert isinstance(result, MapBreakdownResult)
        assert isinstance(result.breakdown, pl.DataFrame)

    def test_map_breakdown_high_min_matches(self) -> None:
        """Retourne is_empty=True si min_matches trop élevé."""
        dff = _make_match_pl(4)
        result = WinLossService.compute_map_breakdown(dff, min_matches=100)
        assert result.is_empty is True

    def test_get_friend_scope_default(self) -> None:
        """Le scope 'Moi (filtres actuels)' retourne dff."""
        dff = _make_match_pl(5)
        base = _make_match_pl(20)
        result = WinLossService.get_friend_scope_df(
            "Moi (filtres actuels)", dff, base, "", "", None
        )
        assert len(result) == len(dff)

    def test_get_friend_scope_all(self) -> None:
        """Le scope 'Moi (toutes les parties)' retourne base."""
        dff = _make_match_pl(5)
        base = _make_match_pl(20)
        result = WinLossService.get_friend_scope_df(
            "Moi (toutes les parties)", dff, base, "", "", None
        )
        assert len(result) == len(base)


# ═══════════════════════════════════════════════════════════════════════
# TeammatesService — Contrats
# ═══════════════════════════════════════════════════════════════════════


class TestTeammatesServiceContracts:
    """Contrats d'interface pour TeammatesService."""

    def test_load_teammate_stats_missing_db(self, tmp_path) -> None:
        """Retourne is_empty=True si la DB du coéquipier n'existe pas."""
        fake_db = str(tmp_path / "player" / "stats.duckdb")
        result = TeammatesService.load_teammate_stats("UnknownPlayer", {"m1", "m2"}, fake_db)
        assert isinstance(result, TeammateStats)
        assert result.is_empty is True
        assert result.gamertag == "UnknownPlayer"

    def test_enrich_series_empty(self) -> None:
        """Retourne une série vide inchangée."""
        series: list[tuple[str, pl.DataFrame]] = []
        result = TeammatesService.enrich_series_with_perfect_kills(series, "")
        assert isinstance(result, EnrichedSeries)
        assert len(result.series) == 0

    def test_enrich_series_no_duckdb(self) -> None:
        """Sans fichier .duckdb, retourne la série inchangée."""
        dff = _make_match_pl(5)
        series = [("Player1", dff)]
        result = TeammatesService.enrich_series_with_perfect_kills(series, "/tmp/nope.txt")
        assert len(result.series) == 1
        assert result.series[0][0] == "Player1"

    def test_load_impact_data_too_few_friends(self) -> None:
        """Retourne available=False avec < 2 amis."""
        result = TeammatesService.load_impact_data("/tmp/test.duckdb", "xuid1", ["m1"], ["friend1"])
        assert isinstance(result, ImpactData)
        assert result.available is False

    def test_load_impact_data_no_matches(self) -> None:
        """Retourne available=False sans matchs."""
        result = TeammatesService.load_impact_data("/tmp/test.duckdb", "xuid1", [], ["f1", "f2"])
        assert result.available is False


# ═══════════════════════════════════════════════════════════════════════
# Contrats d'interface — Normalisation retours (14.3)
# ═══════════════════════════════════════════════════════════════════════


class TestNormalizedReturns:
    """Vérifie que matches_to_polars retourne des pl.DataFrame typés."""

    def test_matches_to_polars_empty(self) -> None:
        """Retourne un pl.DataFrame vide pour une liste vide."""
        from src.data.integration.streamlit_bridge import matches_to_polars

        result = matches_to_polars([])
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()

    def test_matches_to_polars_columns(self) -> None:
        """Vérifie les colonnes du DataFrame Polars retourné."""
        from src.data.domain.models.stats import MatchRow
        from src.data.integration.streamlit_bridge import matches_to_polars

        match = MatchRow(
            match_id="test_m1",
            start_time=datetime(2026, 1, 1, 20, 0, 0),
            kills=10,
            deaths=5,
            assists=3,
            outcome=2,
            accuracy=55.0,
            kda=8.5,
            time_played_seconds=720,
            average_life_seconds=30.0,
            personal_score=1500,
            map_id="map1",
            map_name="Aquarius",
            playlist_id="pl1",
            playlist_name="Ranked",
            map_mode_pair_id="pair1",
            map_mode_pair_name="Slayer",
            team_mmr=1500,
            enemy_mmr=1480,
            last_team_id=0,
            max_killing_spree=5,
            headshot_kills=3,
        )
        result = matches_to_polars([match])
        assert isinstance(result, pl.DataFrame)
        assert len(result) == 1
        assert "kills_per_min" in result.columns
        assert "deaths_per_min" in result.columns
        assert "assists_per_min" in result.columns
        assert "ratio" in result.columns


# ═══════════════════════════════════════════════════════════════════════
# Contrats croisés — page consomme service (14.4)
# ═══════════════════════════════════════════════════════════════════════


class TestPageServiceIntegration:
    """Vérifie que les pages importent et utilisent les services."""

    def test_timeseries_imports_service(self) -> None:
        """timeseries.py importe TimeseriesService."""
        import src.ui.pages.timeseries as ts

        assert hasattr(ts, "TimeseriesService")

    def test_win_loss_imports_service(self) -> None:
        """win_loss.py importe WinLossService."""
        import src.ui.pages.win_loss as wl

        assert hasattr(wl, "WinLossService")

    def test_teammates_imports_service(self) -> None:
        """teammates.py importe TeammatesService."""
        import src.ui.pages.teammates as tm

        assert hasattr(tm, "TeammatesService")

    def test_services_module_exports(self) -> None:
        """Le module services exporte les 3 services."""
        from src.data.services import (
            TeammatesService,
            TimeseriesService,
            WinLossService,
        )

        assert TimeseriesService is not None
        assert WinLossService is not None
        assert TeammatesService is not None
