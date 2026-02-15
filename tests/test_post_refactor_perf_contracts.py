"""Tests de contrats de performance Sprint 19.

Vérifie que les optimisations S19 sont correctement en place :
- Data path DuckDB → Polars zero-copy (tâche 19.1)
- Projection de colonnes (tâche 19.3)
- Cache invalidation unifiée (tâche 19.4)
- Scattergl conditionnel (tâche 19.5)
"""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import polars as pl
import pytest

# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_duckdb(tmp_path):
    """Crée une DB DuckDB minimale avec des matchs de test."""
    db_path = str(tmp_path / "stats.duckdb")
    conn = duckdb.connect(db_path)
    conn.execute("""
        CREATE TABLE match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP WITH TIME ZONE,
            map_id VARCHAR,
            map_name VARCHAR,
            playlist_id VARCHAR,
            playlist_name VARCHAR,
            pair_id VARCHAR,
            pair_name VARCHAR,
            game_variant_id VARCHAR,
            game_variant_name VARCHAR,
            outcome INTEGER,
            team_id INTEGER,
            kda DOUBLE,
            max_killing_spree INTEGER,
            headshot_kills INTEGER,
            avg_life_seconds DOUBLE,
            time_played_seconds DOUBLE,
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER,
            accuracy DOUBLE,
            my_team_score INTEGER,
            enemy_team_score INTEGER,
            team_mmr DOUBLE,
            enemy_mmr DOUBLE,
            personal_score INTEGER,
            is_firefight BOOLEAN DEFAULT FALSE
        )
    """)

    # Insérer 20 matchs de test
    for i in range(20):
        conn.execute(
            """
            INSERT INTO match_stats (
                match_id, start_time, map_id, map_name, playlist_id,
                playlist_name, pair_id, pair_name, game_variant_id,
                game_variant_name, outcome, team_id, kda, max_killing_spree,
                headshot_kills, avg_life_seconds, time_played_seconds,
                kills, deaths, assists, accuracy, my_team_score,
                enemy_team_score, team_mmr, enemy_mmr, personal_score
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                f"match_{i:03d}",
                datetime(2025, 1, 1 + i, 12, 0, 0, tzinfo=timezone.utc),
                f"map_{i % 3}",
                f"Map {i % 3}",
                f"playlist_{i % 2}",
                f"Playlist {i % 2}",
                f"pair_{i % 4}",
                f"Pair {i % 4}",
                f"gv_{i % 2}",
                f"GameVariant {i % 2}",
                2 if i % 3 != 0 else 3,  # outcome
                i % 2,  # team_id
                1.5 + (i % 5) * 0.2,  # kda
                i % 7,  # max_killing_spree
                i % 4,  # headshot_kills
                25.0 + i,  # avg_life_seconds
                300.0 + i * 10,  # time_played_seconds
                10 + i,  # kills
                5 + i % 3,  # deaths
                3 + i % 2,  # assists
                35.0 + i * 0.5,  # accuracy
                50 + i,  # my_team_score
                45 + i,  # enemy_team_score
                1200.0 + i * 5,  # team_mmr
                1190.0 + i * 4,  # enemy_mmr
                100 + i * 10,  # personal_score
            ],
        )
    conn.close()
    return db_path


# ─────────────────────────────────────────────────────────────────────
# 19.1 — Data path DuckDB → Polars zero-copy
# ─────────────────────────────────────────────────────────────────────


class TestZeroCopyArrowPath:
    """Vérifie que load_matches_as_polars retourne un DataFrame Polars directement."""

    def test_load_matches_as_polars_returns_dataframe(self, sample_duckdb):
        """La méthode retourne un pl.DataFrame, pas une list[MatchRow]."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(sample_duckdb, xuid="", read_only=True)
        try:
            df = repo.load_matches_as_polars(include_firefight=True)
            assert isinstance(df, pl.DataFrame)
            assert df.height == 20
        finally:
            repo.close()

    def test_load_matches_as_polars_has_ratio(self, sample_duckdb):
        """Le ratio est calculé en Polars (pas via MatchRow.ratio)."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(sample_duckdb, xuid="", read_only=True)
        try:
            df = repo.load_matches_as_polars()
            assert "ratio" in df.columns
            # Vérifier que le ratio est correct pour le premier match
            first = df.row(0, named=True)
            expected_ratio = (first["kills"] + first["assists"] / 2.0) / first["deaths"]
            assert abs(first["ratio"] - expected_ratio) < 0.001
        finally:
            repo.close()

    def test_load_matches_as_polars_columns_aligned_with_legacy(self, sample_duckdb):
        """Les colonnes essentielles sont identiques au chemin legacy."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(sample_duckdb, xuid="", read_only=True)
        try:
            df = repo.load_matches_as_polars()
            # Vérifier les colonnes essentielles
            essential = {
                "match_id",
                "start_time",
                "map_id",
                "map_name",
                "playlist_id",
                "playlist_name",
                "pair_id",
                "pair_name",
                "outcome",
                "kda",
                "kills",
                "deaths",
                "assists",
                "accuracy",
                "average_life_seconds",
                "time_played_seconds",
                "ratio",
                "team_mmr",
                "enemy_mmr",
            }
            assert essential.issubset(set(df.columns))
        finally:
            repo.close()

    def test_avg_life_seconds_renamed(self, sample_duckdb):
        """avg_life_seconds est renommé en average_life_seconds pour compat."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(sample_duckdb, xuid="", read_only=True)
        try:
            df = repo.load_matches_as_polars()
            assert "average_life_seconds" in df.columns
            assert "avg_life_seconds" not in df.columns
        finally:
            repo.close()

    def test_kills_deaths_coalesced_to_zero(self, sample_duckdb):
        """kills et deaths ne contiennent pas de NULL (COALESCE appliqué)."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(sample_duckdb, xuid="", read_only=True)
        try:
            df = repo.load_matches_as_polars()
            assert df["kills"].null_count() == 0
            assert df["deaths"].null_count() == 0
            assert df["assists"].null_count() == 0
        finally:
            repo.close()


# ─────────────────────────────────────────────────────────────────────
# 19.3 — Projection de colonnes
# ─────────────────────────────────────────────────────────────────────


class TestColumnProjection:
    """Vérifie que la projection de colonnes fonctionne."""

    def test_projection_reduces_columns(self, sample_duckdb):
        """Passer columns= réduit le nombre de colonnes retournées."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(sample_duckdb, xuid="", read_only=True)
        try:
            df_full = repo.load_matches_as_polars()
            df_proj = repo.load_matches_as_polars(columns=["match_id", "kills", "deaths", "ratio"])
            assert df_proj.columns == ["match_id", "kills", "deaths", "ratio"]
            assert df_proj.height == df_full.height
        finally:
            repo.close()

    def test_projection_ignores_unknown_columns(self, sample_duckdb):
        """Les colonnes inconnues sont ignorées silencieusement."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(sample_duckdb, xuid="", read_only=True)
        try:
            df = repo.load_matches_as_polars(columns=["match_id", "nonexistent_col"])
            assert "match_id" in df.columns
            assert "nonexistent_col" not in df.columns
        finally:
            repo.close()

    def test_column_constants_defined(self):
        """Les constantes COLUMNS_COMMON et COLUMNS_COMPUTED sont définies."""
        from src.ui.cache_loaders import COLUMNS_COMMON, COLUMNS_COMPUTED

        assert isinstance(COLUMNS_COMMON, list)
        assert isinstance(COLUMNS_COMPUTED, list)
        assert "match_id" in COLUMNS_COMMON
        assert "kills" in COLUMNS_COMMON
        assert "ratio" in COLUMNS_COMPUTED
        assert "date" in COLUMNS_COMPUTED


# ─────────────────────────────────────────────────────────────────────
# 19.4 — Cache invalidation unifiée
# ─────────────────────────────────────────────────────────────────────


class TestCacheInvalidation:
    """Vérifie que l'invalidation cache est cohérente."""

    def test_db_cache_key_returns_tuple(self, sample_duckdb):
        """db_cache_key retourne (mtime_ns, size)."""
        from src.ui.cache_loaders import db_cache_key

        key = db_cache_key(sample_duckdb)
        assert key is not None
        assert isinstance(key, tuple)
        assert len(key) == 2
        assert key[0] > 0  # mtime_ns
        assert key[1] > 0  # size

    def test_db_cache_key_none_for_missing(self):
        """db_cache_key retourne None pour un fichier inexistant."""
        from src.ui.cache_loaders import db_cache_key

        key = db_cache_key("/nonexistent/path.duckdb")
        assert key is None

    def test_state_delegates_to_cache_loaders(self, sample_duckdb):
        """get_db_cache_key dans state.py délègue à db_cache_key dans cache_loaders."""
        from src.app.state import get_db_cache_key
        from src.ui.cache_loaders import db_cache_key

        key_state = get_db_cache_key(sample_duckdb)
        key_cache = db_cache_key(sample_duckdb)
        assert key_state == key_cache


# ─────────────────────────────────────────────────────────────────────
# 19.5 — Scattergl conditionnel
# ─────────────────────────────────────────────────────────────────────


class TestSmartScatter:
    """Vérifie que smart_scatter bascule en WebGL au-delà du seuil."""

    def test_small_data_returns_scatter(self):
        """Avec peu de points, retourne go.Scatter (SVG)."""
        import plotly.graph_objects as go

        from src.visualization._compat import smart_scatter

        trace = smart_scatter(x=list(range(100)), y=list(range(100)), mode="lines")
        assert isinstance(trace, go.Scatter)

    def test_large_data_returns_scattergl(self):
        """Avec beaucoup de points (>=500), retourne go.Scattergl (WebGL)."""
        import plotly.graph_objects as go

        from src.visualization._compat import smart_scatter

        large_x = list(range(1000))
        large_y = list(range(1000))
        trace = smart_scatter(x=large_x, y=large_y, mode="lines")
        assert isinstance(trace, go.Scattergl)

    def test_threshold_boundary(self):
        """Exactement au seuil (500), bascule en Scattergl."""
        import plotly.graph_objects as go

        from src.visualization._compat import smart_scatter

        trace = smart_scatter(x=list(range(500)), y=list(range(500)), mode="lines")
        assert isinstance(trace, go.Scattergl)

    def test_below_threshold(self):
        """Juste en dessous du seuil (499), reste en Scatter."""
        import plotly.graph_objects as go

        from src.visualization._compat import smart_scatter

        trace = smart_scatter(x=list(range(499)), y=list(range(499)), mode="lines")
        assert isinstance(trace, go.Scatter)

    def test_smart_scatter_preserves_kwargs(self):
        """Les kwargs sont passés intacts au constructeur."""
        from src.visualization._compat import smart_scatter

        trace = smart_scatter(
            x=[1, 2, 3],
            y=[4, 5, 6],
            mode="lines+markers",
            name="test",
            line={"width": 2, "color": "red"},
        )
        assert trace.name == "test"
        assert trace.mode == "lines+markers"

    def test_timeseries_uses_smart_scatter(self):
        """Vérifie que timeseries.py utilise smart_scatter au lieu de go.Scatter."""
        import inspect

        from src.visualization import timeseries

        source = inspect.getsource(timeseries)

        # smart_scatter est utilisé
        assert "smart_scatter" in source
        # go.Scatter direct n'est plus utilisé (sauf dans les imports)
        lines = source.split("\n")
        scatter_direct = [
            line for line in lines if "go.Scatter(" in line and "smart_scatter" not in line
        ]
        assert (
            len(scatter_direct) == 0
        ), f"go.Scatter() encore utilisé directement : {scatter_direct}"


# ─────────────────────────────────────────────────────────────────────
# Enrichissement DataFrame
# ─────────────────────────────────────────────────────────────────────


class TestEnrichMatchesDf:
    """Vérifie la fonction _enrich_matches_df extraite en S19."""

    def test_enrich_adds_computed_columns(self, sample_duckdb):
        """_enrich_matches_df ajoute date, kills_per_min, etc."""
        from src.data.repositories.duckdb_repo import DuckDBRepository
        from src.ui.cache_loaders import _enrich_matches_df

        repo = DuckDBRepository(sample_duckdb, xuid="", read_only=True)
        try:
            df_raw = repo.load_matches_as_polars()
            df_enriched = _enrich_matches_df(df_raw)

            assert "date" in df_enriched.columns
            assert "kills_per_min" in df_enriched.columns
            assert "deaths_per_min" in df_enriched.columns
            assert "assists_per_min" in df_enriched.columns
        finally:
            repo.close()

    def test_enrich_empty_df(self):
        """_enrich_matches_df gère un DataFrame vide."""
        from src.ui.cache_loaders import _enrich_matches_df

        df = pl.DataFrame()
        result = _enrich_matches_df(df)
        assert result.is_empty()

    def test_enrich_timezone_conversion(self, sample_duckdb):
        """start_time est converti en timezone Paris (naïf)."""
        from src.data.repositories.duckdb_repo import DuckDBRepository
        from src.ui.cache_loaders import _enrich_matches_df

        repo = DuckDBRepository(sample_duckdb, xuid="", read_only=True)
        try:
            df = repo.load_matches_as_polars()
            df_enriched = _enrich_matches_df(df)

            # Le type doit être Datetime naïf (sans timezone)
            st_dtype = df_enriched.schema["start_time"]
            assert st_dtype == pl.Datetime("us") or "UTC" not in str(st_dtype)
        finally:
            repo.close()
