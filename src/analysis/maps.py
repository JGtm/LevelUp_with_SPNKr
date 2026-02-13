"""Analyse par carte (map)."""

import polars as pl

from src.analysis.performance_score import compute_performance_series
from src.analysis.stats import compute_global_ratio, compute_outcome_rates
from src.data.domain.models.stats import MapBreakdown


def _to_polars(df: pl.DataFrame) -> pl.DataFrame:
    """Convertit un DataFrame en Polars si nécessaire (bridge transitoire)."""
    if isinstance(df, pl.DataFrame):
        return df
    return pl.from_pandas(df)


def compute_map_breakdown(df: pl.DataFrame, df_history: pl.DataFrame | None = None) -> pl.DataFrame:
    """Calcule les statistiques agrégées par carte.

    Args:
        df: DataFrame Polars de matchs.
        df_history: DataFrame complet Polars pour le calcul du score relatif.

    Returns:
        DataFrame Polars avec colonnes:
        - map_name
        - matches
        - accuracy_avg
        - win_rate
        - loss_rate
        - ratio_global
        - performance_avg
    """
    df_pl = _to_polars(df)
    history_pl = _to_polars(df_history) if df_history is not None else df_pl

    empty_schema = {
        "map_name": pl.Utf8,
        "matches": pl.Int64,
        "accuracy_avg": pl.Float64,
        "win_rate": pl.Float64,
        "loss_rate": pl.Float64,
        "ratio_global": pl.Float64,
        "performance_avg": pl.Float64,
    }

    if df_pl.is_empty():
        return pl.DataFrame(schema=empty_schema)

    # Filtrer les map_name vides
    d = df_pl.with_columns(pl.col("map_name").fill_null(""))
    d = d.filter(pl.col("map_name").str.strip_chars() != "")

    if d.is_empty():
        return pl.DataFrame(schema=empty_schema)

    rows: list[dict] = []
    for map_name in d.select("map_name").unique().to_series().to_list():
        g = d.filter(pl.col("map_name") == map_name)

        rates = compute_outcome_rates(g)
        total_out = max(1, rates.total)

        acc: float | None = None
        if "accuracy" in g.columns:
            acc_val = g.select(pl.col("accuracy").cast(pl.Float64, strict=False).mean()).item()
            acc = float(acc_val) if acc_val is not None else None

        # Calcul de la performance moyenne RELATIVE pour cette carte
        # compute_performance_series accepte Polars nativement
        perf_series = compute_performance_series(g, history_pl)
        if isinstance(perf_series, pl.Series):
            perf_clean = perf_series.drop_nulls()
            perf_avg = float(perf_clean.mean()) if len(perf_clean) > 0 else None
        else:
            # Fallback Pandas Series
            perf_scores = perf_series.dropna()
            perf_avg = float(perf_scores.mean()) if not perf_scores.empty else None

        rows.append(
            {
                "map_name": map_name,
                "matches": int(len(g)),
                "accuracy_avg": acc,
                "win_rate": rates.wins / total_out if rates.total else None,
                "loss_rate": rates.losses / total_out if rates.total else None,
                "ratio_global": compute_global_ratio(g),
                "performance_avg": perf_avg,
            }
        )

    out = pl.DataFrame(rows)
    out = out.sort(["matches", "ratio_global"], descending=[True, True])
    return out


def map_breakdown_to_models(df: pl.DataFrame) -> list[MapBreakdown]:
    """Convertit un DataFrame de breakdown en liste de MapBreakdown.

    Args:
        df: DataFrame Polars issu de compute_map_breakdown.

    Returns:
        Liste de MapBreakdown.
    """
    df_pl = _to_polars(df)

    return [
        MapBreakdown(
            map_name=row["map_name"],
            matches=int(row["matches"]),
            accuracy_avg=row["accuracy_avg"],
            win_rate=row["win_rate"],
            loss_rate=row["loss_rate"],
            ratio_global=row["ratio_global"],
        )
        for row in df_pl.iter_rows(named=True)
    ]
