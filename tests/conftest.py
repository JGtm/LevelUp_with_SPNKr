"""Fixtures communes pour les tests.

Ce fichier contient des fixtures partagées pour tous les tests, notamment
des fixtures Polars pour la migration Pandas → Polars.
"""

from __future__ import annotations

import os
import sys
from contextlib import suppress


def _sanitize_windows_path_for_python_wheels() -> None:
    """Nettoie PATH sous Windows pour éviter les conflits de DLL.

    Sur certaines machines, la présence de répertoires MSYS2/MinGW dans PATH peut
    provoquer des crashes natifs non déterministes dans des extensions Python
    (DuckDB, Polars, etc.).

    On supprime donc, pour la durée du run pytest, les entrées clairement liées à
    MSYS2/MinGW (tout en conservant le reste de PATH).
    """

    if not sys.platform.startswith("win"):
        return

    path_value = os.environ.get("PATH")
    if not path_value:
        return

    parts = [p for p in path_value.split(";") if p]
    filtered: list[str] = []
    for part in parts:
        lower = part.lower()
        if "\\msys64\\" in lower:
            continue
        if "\\mingw" in lower and lower.endswith("\\bin"):
            continue
        filtered.append(part)

    os.environ["PATH"] = ";".join(filtered)


_sanitize_windows_path_for_python_wheels()

import numpy as np
import polars as pl
import pytest

# Import Pandas pour compatibilité avec les tests existants
try:
    import pandas as pd
except ImportError:
    pd = None


def pytest_addoption(parser: pytest.Parser) -> None:
    """Ajoute les options CLI custom pour les tests optionnels."""
    parser.addoption(
        "--run-e2e-browser",
        action="store_true",
        default=False,
        help="Exécute les tests E2E navigateur réel (Playwright).",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip des tests E2E navigateur sauf si explicitement demandés."""
    if config.getoption("--run-e2e-browser"):
        return

    skip_e2e = pytest.mark.skip(reason="E2E navigateur désactivé (utiliser --run-e2e-browser)")
    for item in items:
        if "e2e_browser" in item.keywords:
            item.add_marker(skip_e2e)


def pytest_configure(config: pytest.Config) -> None:
    """Configuration globale pytest.

    Sur Windows, DuckDB peut crasher de manière non déterministe (access violation)
    pendant des suites de tests longues. On force un mode mono-thread au moment de
    la connexion pour réduire ces crashes.
    """

    if not sys.platform.startswith("win"):
        return

    try:
        import duckdb  # noqa: F401
    except Exception:
        return

    original_connect = duckdb.connect

    def connect_patched(database=":memory:", read_only: bool = False, config=None, **kwargs):
        merged = {}
        if isinstance(config, dict):
            merged.update(config)
        merged.setdefault("threads", "1")

        conn = original_connect(database, read_only=read_only, config=merged, **kwargs)
        with suppress(Exception):
            conn.execute("SET threads=1")
        return conn

    duckdb.connect = connect_patched


# =============================================================================
# FIXTURES POLARS
# =============================================================================


@pytest.fixture
def sample_match_df_polars() -> pl.DataFrame:
    """DataFrame Polars type avec colonnes de match standard."""
    from datetime import datetime, timedelta

    np.random.seed(42)  # Reproductibilité
    n = 20
    start = datetime(2025, 1, 1, 0, 0, 0)
    end = start + timedelta(hours=n - 1)
    return pl.DataFrame(
        {
            "match_id": [f"match_{i}" for i in range(n)],
            "start_time": pl.datetime_range(
                start=start,
                end=end,
                interval="1h",
                eager=True,
            ),
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
        pl.when(pl.int_range(0, pl.len()) < 6).then(None).otherwise(pl.col("kills")).alias("kills")
    )
    df = df.with_columns(
        pl.when((pl.int_range(0, pl.len()) >= 10) & (pl.int_range(0, pl.len()) < 16))
        .then(None)
        .otherwise(pl.col("accuracy"))
        .alias("accuracy")
    )
    df = df.with_columns(
        pl.when((pl.int_range(0, pl.len()) >= 5) & (pl.int_range(0, pl.len()) < 11))
        .then(None)
        .otherwise(pl.col("kda"))
        .alias("kda")
    )
    return df


# =============================================================================
# FIXTURE MOCK STREAMLIT (Sprint 7bis)
# =============================================================================


class MockStreamlit:
    """Mock Streamlit réutilisable pour tests UI.

    Fournit un ensemble de MagicMock pour tous les widgets Streamlit courants,
    injectés via monkeypatch dans le module cible.

    Usage::

        def test_my_page(mock_st, sample_match_df_polars):
            from src.ui.pages import win_loss as mod
            ms = mock_st(mod)
            mod.render_win_loss_page(sample_match_df_polars, ...)
            ms.calls["plotly_chart"].assert_called()
    """

    def __init__(self, monkeypatch, module):
        from contextlib import contextmanager
        from unittest.mock import MagicMock

        self.calls: dict[str, MagicMock] = {}
        self._module = module
        self._monkeypatch = monkeypatch

        # Widgets de base — chaque appel est un MagicMock
        for name in [
            "write",
            "markdown",
            "title",
            "header",
            "subheader",
            "caption",
            "info",
            "warning",
            "error",
            "success",
            "metric",
            "plotly_chart",
            "dataframe",
            "table",
            "image",
            "button",
            "toggle",
            "checkbox",
            "slider",
            "selectbox",
            "multiselect",
            "radio",
            "text_input",
            "number_input",
            "tabs",
            "expander",
            "container",
            "spinner",
            "progress",
            "divider",
            "html",
            "download_button",
            "line_chart",
            "rerun",
        ]:
            mock = MagicMock(name=f"st.{name}")
            self.calls[name] = mock
            monkeypatch.setattr(module.st, name, mock)

        # st.columns → retourne des MagicMock avec les mêmes attrs
        self._setup_columns()

        # st.session_state → dict partagé
        self.session_state: dict = {}
        monkeypatch.setattr(module.st, "session_state", self.session_state)

        # st.spinner → context manager
        @contextmanager
        def _fake_spinner(*_a, **_kw):
            yield

        self.calls["spinner"] = MagicMock(side_effect=_fake_spinner)
        monkeypatch.setattr(module.st, "spinner", self.calls["spinner"])

        # st.expander → context manager retournant un MagicMock
        @contextmanager
        def _fake_expander(*_a, **_kw):
            col = MagicMock(name="expander_ctx")
            yield col

        self.calls["expander"] = MagicMock(side_effect=_fake_expander)
        monkeypatch.setattr(module.st, "expander", self.calls["expander"])

        # st.sidebar → MagicMock context manager
        sidebar_mock = MagicMock(name="st.sidebar")

        @contextmanager
        def _sidebar_ctx():
            yield

        sidebar_mock.__enter__ = lambda _s: None
        sidebar_mock.__exit__ = lambda _s, *_a: None
        self.calls["sidebar"] = sidebar_mock
        monkeypatch.setattr(module.st, "sidebar", sidebar_mock)

        # st.column_config (namespace pour NumberColumn etc.)
        col_config = MagicMock(name="st.column_config")
        self.calls["column_config"] = col_config
        with suppress(AttributeError):
            monkeypatch.setattr(module.st, "column_config", col_config)

    def _setup_columns(self, default_n: int = 3):
        from unittest.mock import MagicMock

        cols = [MagicMock(name=f"col_{i}") for i in range(default_n)]
        # Chaque colonne est un context manager
        for c in cols:
            c.__enter__ = lambda s: s
            c.__exit__ = lambda _s, *_a: None
        self.calls["columns"] = MagicMock(return_value=cols)
        self._monkeypatch.setattr(self._module.st, "columns", self.calls["columns"])
        self.columns = cols

    def set_columns(self, n: int):
        """Reconfigure le nombre de colonnes retournées."""
        self._setup_columns(n)

    def set_columns_dynamic(self):
        """Configure columns pour retourner dynamiquement N cols selon l'argument."""
        from unittest.mock import MagicMock

        def _dynamic_cols(n, *_a, **_kw):
            if isinstance(n, int):
                count = n
            elif isinstance(n, list | tuple):
                count = len(n)
            else:
                count = 3
            cols = [MagicMock(name=f"col_{i}") for i in range(count)]
            for c in cols:
                c.__enter__ = lambda s: s
                c.__exit__ = lambda _s, *_a: None
            return cols

        self.calls["columns"] = MagicMock(side_effect=_dynamic_cols)
        self._monkeypatch.setattr(self._module.st, "columns", self.calls["columns"])


@pytest.fixture
def mock_st(monkeypatch):
    """Factory fixture : mock_st(module) → MockStreamlit.

    Exemple::

        def test_page(mock_st):
            from src.ui.pages import win_loss as mod
            ms = mock_st(mod)
            # ... appeler la render function ...
    """

    def _factory(module):
        return MockStreamlit(monkeypatch, module)

    return _factory
