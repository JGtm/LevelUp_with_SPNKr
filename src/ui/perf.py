"""Outils de mesure de performance (Streamlit).

Streamlit rerun le script à chaque interaction. Ce module fournit un mode
"perf" simple pour mesurer les sections clés (sidebar, chargement DB, filtres,
charts) sans dépendance externe.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

import polars as pl
import streamlit as st

# Type alias pour compatibilité DataFrame
try:
    import pandas as pd

    DataFrameType = pd.DataFrame | pl.DataFrame
except ImportError:
    pd = None  # type: ignore[assignment]
    DataFrameType = pl.DataFrame  # type: ignore[misc]


def _to_polars(df: DataFrameType) -> pl.DataFrame:
    """Convertit un DataFrame Pandas en Polars si nécessaire."""
    if isinstance(df, pl.DataFrame):
        return df
    if pd is not None and isinstance(df, pd.DataFrame):
        return pl.from_pandas(df)
    return pl.DataFrame()


_PERF_ENABLED_KEY = "perf_enabled"
_PERF_TIMINGS_KEY = "_perf_timings_ms"


def perf_enabled() -> bool:
    return bool(st.session_state.get(_PERF_ENABLED_KEY, False))


def perf_reset_run() -> None:
    if perf_enabled():
        st.session_state[_PERF_TIMINGS_KEY] = []


@contextmanager
def perf_section(name: str) -> Iterator[None]:
    if not perf_enabled():
        yield
        return

    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        rows = st.session_state.setdefault(_PERF_TIMINGS_KEY, [])
        rows.append({"section": str(name), "ms": float(dt_ms)})


def perf_dataframe() -> pl.DataFrame:
    """Retourne le DataFrame Polars des timings de performance."""
    rows = st.session_state.get(_PERF_TIMINGS_KEY, [])
    if not isinstance(rows, list) or not rows:
        return pl.DataFrame(schema={"section": pl.Utf8, "ms": pl.Float64})
    return pl.DataFrame(rows)


def render_perf_panel(*, location: str = "sidebar") -> None:
    if location == "sidebar":
        container = st.sidebar
    else:
        container = st

    container.checkbox("Mode perf", key=_PERF_ENABLED_KEY)

    if not perf_enabled():
        return

    c = container.columns(2)
    if c[0].button("Reset timings", width="stretch"):
        st.session_state[_PERF_TIMINGS_KEY] = []
        st.rerun()

    df_pl = perf_dataframe()
    if df_pl.is_empty():
        c[1].caption("En attente…")
        return

    total = df_pl.select(pl.col("ms").sum()).item()
    c[1].caption(f"Total: {total:.0f} ms")

    # Convertir en pandas pour st.dataframe (compatibilité Streamlit)
    container.dataframe(
        df_pl.to_pandas(),
        width="stretch",
        hide_index=True,
        column_config={
            "section": st.column_config.TextColumn("Section"),
            "ms": st.column_config.NumberColumn("ms", format="%.0f"),
        },
    )
