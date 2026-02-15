"""Tests pour le helper centralisé src.visualization._compat.

Valide les conversions Polars ↔ Pandas aux frontières Plotly/Streamlit.
"""

from __future__ import annotations

import polars as pl

from src.visualization._compat import (
    DataFrameLike,
    ensure_polars,
    ensure_polars_series,
    to_pandas_for_plotly,
    to_pandas_for_st,
)

# ---------------------------------------------------------------------------
# ensure_polars
# ---------------------------------------------------------------------------


class TestEnsurePolars:
    """Garantit la normalisation vers pl.DataFrame."""

    def test_polars_passthrough(self) -> None:
        df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
        result = ensure_polars(df)
        assert isinstance(result, pl.DataFrame)
        assert result.shape == (2, 2)

    def test_pandas_to_polars(self) -> None:
        import pandas as pd

        pdf = pd.DataFrame({"x": [10, 20], "y": ["a", "b"]})
        result = ensure_polars(pdf)
        assert isinstance(result, pl.DataFrame)
        assert result.columns == ["x", "y"]
        assert result["x"].to_list() == [10, 20]

    def test_empty_polars(self) -> None:
        df = pl.DataFrame()
        result = ensure_polars(df)
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()

    def test_empty_pandas(self) -> None:
        import pandas as pd

        pdf = pd.DataFrame()
        result = ensure_polars(pdf)
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()


# ---------------------------------------------------------------------------
# ensure_polars_series
# ---------------------------------------------------------------------------


class TestEnsurePolarsSeries:
    """Garantit la normalisation vers pl.Series."""

    def test_polars_series_passthrough(self) -> None:
        s = pl.Series("val", [1, 2, 3])
        result = ensure_polars_series(s)
        assert isinstance(result, pl.Series)
        assert result.to_list() == [1, 2, 3]

    def test_pandas_series_to_polars(self) -> None:
        import pandas as pd

        ps = pd.Series([10, 20, 30], name="nums")
        result = ensure_polars_series(ps)
        assert isinstance(result, pl.Series)
        assert result.to_list() == [10, 20, 30]


# ---------------------------------------------------------------------------
# to_pandas_for_plotly / to_pandas_for_st
# ---------------------------------------------------------------------------


class TestToPandas:
    """Vérifie la conversion Polars → Pandas aux frontières."""

    def test_to_pandas_for_plotly(self) -> None:
        import pandas as pd

        df = pl.DataFrame({"metric": [1.5, 2.5], "label": ["A", "B"]})
        result = to_pandas_for_plotly(df)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["metric", "label"]
        assert result["metric"].tolist() == [1.5, 2.5]

    def test_to_pandas_for_st(self) -> None:
        import pandas as pd

        df = pl.DataFrame({"col": [True, False]})
        result = to_pandas_for_st(df)
        assert isinstance(result, pd.DataFrame)
        assert result["col"].tolist() == [True, False]

    def test_tolerates_already_pandas(self) -> None:
        """Pendant la migration, certains appelants passent du Pandas."""
        import pandas as pd

        pdf = pd.DataFrame({"a": [1]})
        result = to_pandas_for_plotly(pdf)
        assert isinstance(result, pd.DataFrame)

    def test_roundtrip_preserve_types(self) -> None:
        """Vérifie que int/float/string survivent au roundtrip."""

        df = pl.DataFrame(
            {
                "int_col": [1, 2, 3],
                "float_col": [1.1, 2.2, 3.3],
                "str_col": ["a", "b", "c"],
            }
        )
        pdf = to_pandas_for_plotly(df)
        assert pdf["int_col"].dtype in (int, "int64", "Int64")
        assert pdf["float_col"].dtype == "float64"
        assert pdf["str_col"].dtype == "object"


# ---------------------------------------------------------------------------
# DataFrameLike type alias
# ---------------------------------------------------------------------------


class TestDataFrameLike:
    """Vérifie que DataFrameLike accepte les deux types."""

    def test_polars_is_dataframelike(self) -> None:
        df: DataFrameLike = pl.DataFrame({"a": [1]})
        assert isinstance(ensure_polars(df), pl.DataFrame)

    def test_pandas_is_dataframelike(self) -> None:
        import pandas as pd

        df: DataFrameLike = pd.DataFrame({"a": [1]})
        assert isinstance(ensure_polars(df), pl.DataFrame)
