"""Calcul des statistiques agrégées."""

from __future__ import annotations

import polars as pl

from src.analysis.mode_categories import infer_custom_category_from_pair_name
from src.models import AggregatedStats, OutcomeRates
from src.ui.formatting import format_mmss

# Type alias pour compatibilité DataFrame
try:
    import pandas as pd

    DataFrameType = pd.DataFrame | pl.DataFrame
except ImportError:
    DataFrameType = pl.DataFrame  # type: ignore[misc]


def _to_polars(df: DataFrameType) -> pl.DataFrame:
    """Convertit un DataFrame Pandas en Polars si nécessaire."""
    if isinstance(df, pl.DataFrame):
        return df
    # Pandas DataFrame
    return pl.from_pandas(df)


def compute_aggregated_stats(df: DataFrameType) -> AggregatedStats:
    """Agrège les statistiques d'un DataFrame de matchs.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonnes kills, deaths, assists, time_played_seconds.

    Returns:
        AggregatedStats contenant les totaux.
    """
    df_pl = _to_polars(df)

    if df_pl.is_empty():
        return AggregatedStats()

    total_time = 0.0
    if "time_played_seconds" in df_pl.columns:
        time_col = df_pl.select(pl.col("time_played_seconds").cast(pl.Float64, strict=False))
        total_time = float(time_col.sum().item() or 0.0)

    return AggregatedStats(
        total_kills=int(df_pl.select(pl.col("kills").sum()).item() or 0),
        total_deaths=int(df_pl.select(pl.col("deaths").sum()).item() or 0),
        total_assists=int(df_pl.select(pl.col("assists").sum()).item() or 0),
        total_matches=len(df_pl),
        total_time_seconds=total_time,
    )


def compute_outcome_rates(df: DataFrameType) -> OutcomeRates:
    """Calcule les taux de victoire/défaite.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonne outcome.

    Returns:
        OutcomeRates avec les comptages.

    Note:
        Codes outcome: 2=Wins, 3=Losses, 1=Ties, 4=NoFinishes
    """
    df_pl = _to_polars(df)

    d = df_pl.drop_nulls(subset=["outcome"])
    total = len(d)

    if total == 0:
        return OutcomeRates(wins=0, losses=0, ties=0, no_finish=0, total=0)

    counts = d.group_by("outcome").agg(pl.len().alias("count"))
    counts_dict = {row["outcome"]: row["count"] for row in counts.iter_rows(named=True)}

    return OutcomeRates(
        wins=int(counts_dict.get(2, 0)),
        losses=int(counts_dict.get(3, 0)),
        ties=int(counts_dict.get(1, 0)),
        no_finish=int(counts_dict.get(4, 0)),
        total=total,
    )


def compute_global_ratio(df: DataFrameType) -> float | None:
    """Calcule le ratio global (K + A/2) / D sur un DataFrame.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonnes kills, deaths, assists.

    Returns:
        Le ratio global, ou None si pas de deaths.
    """
    df_pl = _to_polars(df)

    if df_pl.is_empty():
        return None
    kills = (
        float(df_pl.select(pl.col("kills").sum()).item() or 0) if "kills" in df_pl.columns else 0.0
    )
    assists = (
        float(df_pl.select(pl.col("assists").sum()).item() or 0)
        if "assists" in df_pl.columns
        else 0.0
    )
    deaths = (
        float(df_pl.select(pl.col("deaths").sum()).item() or 0)
        if "deaths" in df_pl.columns
        else 0.0
    )
    if deaths <= 0:
        return None
    return (kills + (assists / 2.0)) / deaths


def extract_mode_category(pair_name: str | None) -> str:
    """Infère la catégorie custom (alignée sidebar) depuis le `pair_name`.

    Catégories : Assassin, Fiesta, BTB, Ranked, Firefight, Other.

    Args:
        pair_name: Nom du couple mode/carte (ex: "Arena:Slayer on Aquarius").

    Returns:
        Catégorie custom.
    """
    return infer_custom_category_from_pair_name(pair_name)


def compute_mode_category_averages(
    df: DataFrameType,
    category: str,
) -> dict[str, float | None]:
    """Calcule les moyennes historiques pour une catégorie de mode.

    Args:
        df: DataFrame (Pandas ou Polars) des matchs avec colonnes pair_name, kills, deaths, assists.
        category: Catégorie custom (Assassin, Fiesta, BTB, Ranked, Firefight, Other).

    Returns:
        Dict avec les moyennes: avg_kills, avg_deaths, avg_assists, avg_ratio, match_count.
    """
    df_pl = _to_polars(df)

    empty_result = {
        "avg_kills": None,
        "avg_deaths": None,
        "avg_assists": None,
        "avg_ratio": None,
        "avg_max_killing_spree": None,
        "avg_headshot_kills": None,
        "match_count": 0,
    }

    if df_pl.is_empty():
        return empty_result

    # Filtrer par catégorie (alignée sidebar) - vectorisé pour performance
    filtered = df_pl.filter(
        pl.col("pair_name").map_elements(extract_mode_category, return_dtype=pl.Utf8) == category
    )

    if filtered.is_empty():
        return empty_result

    avg_kills = filtered.select(pl.col("kills").mean()).item()
    avg_deaths = filtered.select(pl.col("deaths").mean()).item()
    avg_assists = filtered.select(pl.col("assists").mean()).item()

    avg_max_killing_spree = None
    if "max_killing_spree" in filtered.columns:
        val = filtered.select(
            pl.col("max_killing_spree").cast(pl.Float64, strict=False).mean()
        ).item()
        avg_max_killing_spree = float(val) if val is not None else None

    avg_headshot_kills = None
    if "headshot_kills" in filtered.columns:
        val = filtered.select(pl.col("headshot_kills").cast(pl.Float64, strict=False).mean()).item()
        avg_headshot_kills = float(val) if val is not None else None

    # Ratio moyen (somme des frags / somme des morts)
    total_deaths = filtered.select(pl.col("deaths").sum()).item() or 0
    if total_deaths > 0:
        total_kills = filtered.select(pl.col("kills").sum()).item() or 0
        total_assists = filtered.select(pl.col("assists").sum()).item() or 0
        avg_ratio = (total_kills + total_assists / 2.0) / total_deaths
    else:
        avg_ratio = None

    return {
        "avg_kills": float(avg_kills) if avg_kills is not None else None,
        "avg_deaths": float(avg_deaths) if avg_deaths is not None else None,
        "avg_assists": float(avg_assists) if avg_assists is not None else None,
        "avg_ratio": float(avg_ratio) if avg_ratio is not None else None,
        "avg_max_killing_spree": avg_max_killing_spree,
        "avg_headshot_kills": avg_headshot_kills,
        "match_count": len(filtered),
    }


def format_selected_matches_summary(n: int, rates: OutcomeRates) -> str:
    """Formate un résumé des matchs sélectionnés pour l'UI.

    Args:
        n: Nombre de matchs.
        rates: OutcomeRates calculé.

    Returns:
        Chaîne formatée pour affichage.
    """
    if n <= 0:
        return "Aucun match sélectionné"

    def plural(n_: int, one: str, many: str) -> str:
        return one if int(n_) == 1 else many

    wins = rates.wins
    losses = rates.losses
    ties = rates.ties
    nofinish = rates.no_finish

    return (
        f"{plural(n, 'Partie', 'Parties')} sélectionnée{'' if n == 1 else 's'}: {n} | "
        f"{plural(wins, 'Victoire', 'Victoires')}: {wins} | "
        f"{plural(losses, 'Défaite', 'Défaites')}: {losses} | "
        f"{plural(ties, 'Égalité', 'Égalités')}: {ties} | "
        f"{plural(nofinish, 'Non terminé', 'Non terminés')}: {nofinish}"
    )


# NOTE: format_mmss est importé depuis src.ui.formatting pour éviter la duplication.
# Re-export pour rétrocompatibilité des imports existants.
__all__ = [
    "compute_aggregated_stats",
    "compute_outcome_rates",
    "compute_global_ratio",
    "format_selected_matches_summary",
    "format_mmss",
    "extract_mode_category",
    "compute_mode_category_averages",
]
