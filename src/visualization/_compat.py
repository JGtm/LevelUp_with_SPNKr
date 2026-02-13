"""Couche de compatibilité Polars ↔ Pandas pour les visualisations.

Ce module centralise les conversions DataFrame aux frontières
Plotly / Streamlit, qui n'acceptent que Pandas.

Principe :
- Toute la logique interne travaille en **Polars**.
- La conversion vers Pandas se fait **uniquement** à la frontière
  Plotly (``to_pandas_for_plotly``) ou Streamlit (``to_pandas_for_st``).
- Les fonctions qui reçoivent un DataFrame d'origine incertaine
  (Polars ou Pandas) utilisent ``ensure_polars`` pour normaliser.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

import polars as pl

if TYPE_CHECKING:
    import pandas as pd

# ---------------------------------------------------------------------------
# Type alias public
# ---------------------------------------------------------------------------
DataFrameLike = Union[pl.DataFrame, "pd.DataFrame"]


# ---------------------------------------------------------------------------
# Conversions
# ---------------------------------------------------------------------------


def to_pandas_for_plotly(df: pl.DataFrame) -> pd.DataFrame:
    """Convertit un ``pl.DataFrame`` en ``pd.DataFrame`` pour Plotly.

    Utiliser **uniquement** juste avant de passer les données à
    ``go.Figure`` / ``px.*`` / ``st.plotly_chart``.
    """
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    # Déjà un pd.DataFrame (tolérance pendant la migration)
    return df  # type: ignore[return-value]


def to_pandas_for_st(df: pl.DataFrame) -> pd.DataFrame:
    """Convertit un ``pl.DataFrame`` en ``pd.DataFrame`` pour Streamlit.

    Utiliser pour ``st.dataframe()``, ``st.table()``, ``st.download_button(csv)``.
    """
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df  # type: ignore[return-value]


def ensure_polars(df: DataFrameLike) -> pl.DataFrame:
    """Garantit un ``pl.DataFrame`` en entrée de fonction.

    Accepte indifféremment un ``pl.DataFrame`` ou un ``pd.DataFrame``.
    Pendant la migration progressive, certains appelants passent encore
    du Pandas — cette fonction normalise sans casser.
    """
    if isinstance(df, pl.DataFrame):
        return df
    # pd.DataFrame → pl.DataFrame
    return pl.from_pandas(df)


def ensure_polars_series(s: Any) -> pl.Series:
    """Convertit une Series Pandas ou Polars en ``pl.Series``."""
    if isinstance(s, pl.Series):
        return s
    # pd.Series → pl.Series
    return pl.from_pandas(s)
