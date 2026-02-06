"""Fixtures communes pour les tests.

Ce fichier contient des fixtures partagées pour tous les tests, notamment
des fixtures Polars pour la migration Pandas → Polars.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

# Import Pandas pour compatibilité avec les tests existants
try:
    import pandas as pd
except ImportError:
    pd = None


# =============================================================================
# FIXTURES POLARS
# =============================================================================


@pytest.fixture
def sample_match_df_polars() -> pl.DataFrame:
    """DataFrame Polars type avec colonnes de match standard."""
    np.random.seed(42)  # Reproductibilité
    n = 20
    return pl.DataFrame(
        {
            "match_id": [f"match_{i}" for i in range(n)],
            "start_time": pl.date_range(
                start=pl.date(2025, 1, 1),
                end=pl.date(2025, 1, 1),
                interval="1h",
                eager=True,
            )[:n],
            "kills": np.random.randint(5, 25, n).tolist(),
            "deaths": np.random.randint(3, 15, n).tolist(),
            "assists": np.random.randint(2, 12, n).tolist(),
            "accuracy": np.random.uniform(30, 60, n).tolist(),
            "ratio": np.random.uniform(0.5, 2.5, n).tolist(),
            "kda": np.random.uniform(-5, 10, n).tolist(),
            "outcome": np.random.choice([1, 2, 3, 4], n).tolist(),
            "map_name": np.random.choice(["Recharge", "Streets", "Live Fire"], n).tolist(),
            "playlist_name": np.random.choice(["Ranked", "Quick Play"], n).tolist(),
            "time_played_seconds": np.random.randint(300, 900, n).tolist(),
            "kills_per_min": np.random.uniform(0.3, 1.5, n).tolist(),
            "deaths_per_min": np.random.uniform(0.2, 1.0, n).tolist(),
            "assists_per_min": np.random.uniform(0.1, 0.8, n).tolist(),
            "headshot_kills": np.random.randint(1, 10, n).tolist(),
            "max_killing_spree": np.random.randint(0, 8, n).tolist(),
            "average_life_seconds": np.random.uniform(20, 60, n).tolist(),
            "mode_category": np.random.choice(["Slayer", "CTF", "Oddball"], n).tolist(),
        }
    )


@pytest.fixture
def empty_df_polars() -> pl.DataFrame:
    """DataFrame Polars vide avec les colonnes attendues."""
    return pl.DataFrame(
        schema={
            "match_id": pl.Utf8,
            "start_time": pl.Datetime,
            "kills": pl.Int64,
            "deaths": pl.Int64,
            "assists": pl.Int64,
            "accuracy": pl.Float64,
            "ratio": pl.Float64,
            "kda": pl.Float64,
            "outcome": pl.Int64,
            "map_name": pl.Utf8,
            "time_played_seconds": pl.Int64,
            "kills_per_min": pl.Float64,
            "deaths_per_min": pl.Float64,
            "assists_per_min": pl.Float64,
            "headshot_kills": pl.Int64,
            "max_killing_spree": pl.Int64,
            "average_life_seconds": pl.Float64,
            "playlist_name": pl.Utf8,
            "mode_category": pl.Utf8,
        }
    )


@pytest.fixture
def df_with_nans_polars(sample_match_df_polars: pl.DataFrame) -> pl.DataFrame:
    """DataFrame Polars avec des valeurs NaN."""
    df = sample_match_df_polars.clone()
    # Remplacer certaines valeurs par None (équivalent NaN en Polars)
    df = df.with_columns(
        pl.when(pl.int_range(0, pl.count()) < 6)
        .then(None)
        .otherwise(pl.col("kills"))
        .alias("kills")
    )
    df = df.with_columns(
        pl.when((pl.int_range(0, pl.count()) >= 10) & (pl.int_range(0, pl.count()) < 16))
        .then(None)
        .otherwise(pl.col("accuracy"))
        .alias("accuracy")
    )
    df = df.with_columns(
        pl.when((pl.int_range(0, pl.count()) >= 5) & (pl.int_range(0, pl.count()) < 11))
        .then(None)
        .otherwise(pl.col("kda"))
        .alias("kda")
    )
    return df
