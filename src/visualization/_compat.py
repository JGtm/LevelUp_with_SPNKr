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

import contextlib
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


# ---------------------------------------------------------------------------
# Plotly Scattergl conditionnel (Sprint 19 — tâche 19.5)
# ---------------------------------------------------------------------------

# Seuil de points au-delà duquel on bascule en WebGL (Scattergl).
# En dessous, go.Scatter (SVG) est privilégié pour meilleure qualité.
_SCATTERGL_THRESHOLD: int = 500


def smart_scatter(**kwargs: Any) -> go.BaseTraceType:  # noqa: F821
    """Retourne ``go.Scattergl`` si le nombre de points dépasse le seuil, sinon ``go.Scatter``.

    Même signature et même rendu visuel que ``go.Scatter``.
    Le basculement est transparent : Scattergl supporte les mêmes paramètres.

    Le seuil est défini par ``_SCATTERGL_THRESHOLD`` (500 points par défaut).

    Args:
        **kwargs: Paramètres identiques à ``go.Scatter`` / ``go.Scattergl``.

    Returns:
        Trace Plotly (Scatter ou Scattergl).
    """
    import plotly.graph_objects as _go

    n_points = 0
    x = kwargs.get("x")
    y = kwargs.get("y")
    if x is not None:
        with contextlib.suppress(TypeError):
            n_points = len(x)
    elif y is not None:
        with contextlib.suppress(TypeError):
            n_points = len(y)

    if n_points >= _SCATTERGL_THRESHOLD:
        return _go.Scattergl(**kwargs)
    return _go.Scatter(**kwargs)
