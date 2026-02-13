"""Helper Arrow/Polars zero-copy pour DuckDB.

Ce module fournit des utilitaires pour convertir les résultats DuckDB
en DataFrames Polars via le transfert Arrow zero-copy (.pl()).

DuckDB.pl() utilise un buffer Arrow partagé sans copie mémoire,
ce qui est ~10× plus rapide que fetchall() + construction manuelle.

Usage dans les repositories :
    from src.data.repositories._arrow_bridge import result_to_polars

    result = conn.execute("SELECT ...")
    df = result_to_polars(result)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    import duckdb

logger = logging.getLogger(__name__)


def result_to_polars(result: duckdb.DuckDBPyResult) -> pl.DataFrame:
    """Convertit un résultat DuckDB en DataFrame Polars via Arrow zero-copy.

    Utilise .pl() (transfert Arrow sans copie mémoire) avec fallback
    sur fetchall() en cas d'erreur (ex: types non supportés).

    Args:
        result: Résultat d'une requête DuckDB (conn.execute(...)).

    Returns:
        DataFrame Polars. Vide en cas d'erreur.
    """
    try:
        return result.pl()
    except Exception as e:
        logger.debug(f"Arrow zero-copy échoué, fallback fetchall: {e}")
        try:
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            if not rows:
                return pl.DataFrame(schema={col: pl.Utf8 for col in columns})
            return pl.DataFrame({col: [row[i] for row in rows] for i, col in enumerate(columns)})
        except Exception as e2:
            logger.warning(f"Conversion DuckDB→Polars échouée: {e2}")
            return pl.DataFrame()


def ensure_polars(df: object) -> pl.DataFrame:
    """Garantit qu'un objet est un DataFrame Polars.

    Accepte: pl.DataFrame, pd.DataFrame, ou tout objet convertible.

    Args:
        df: DataFrame Polars, Pandas, ou autre.

    Returns:
        DataFrame Polars.
    """
    if isinstance(df, pl.DataFrame):
        return df
    try:
        return pl.from_pandas(df)  # type: ignore[arg-type]
    except Exception:
        return pl.DataFrame()
