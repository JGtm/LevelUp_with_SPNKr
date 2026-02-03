"""Module d'analyse des performances cumulées avec Polars.

Sprint 6: Fonctions pour calculer les séries cumulées (net score, K/D, objectifs).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

# Import conditionnel de Polars
try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None  # type: ignore

if TYPE_CHECKING:
    import polars as pl


# =============================================================================
# Dataclasses de résultats
# =============================================================================


@dataclass(frozen=True)
class CumulativeSeriesResult:
    """Résultat d'une série cumulative.

    Attributes:
        match_id: ID du match.
        start_time: Timestamp du match.
        value: Valeur pour ce match.
        cumulative: Valeur cumulative jusqu'à ce match.
    """

    match_id: str
    start_time: str
    value: float
    cumulative: float


@dataclass(frozen=True)
class CumulativeMetricsResult:
    """Métriques cumulées pour une session.

    Attributes:
        total_kills: Total des kills.
        total_deaths: Total des morts.
        total_assists: Total des assistances.
        cumulative_net_score: Net score cumulé final.
        cumulative_kd: K/D cumulé final.
        cumulative_kda: KDA cumulé final.
        matches_count: Nombre de matchs.
    """

    total_kills: int
    total_deaths: int
    total_assists: int
    cumulative_net_score: int
    cumulative_kd: float
    cumulative_kda: float
    matches_count: int

    @property
    def average_kills_per_match(self) -> float:
        """Kills moyens par match."""
        if self.matches_count == 0:
            return 0.0
        return self.total_kills / self.matches_count

    @property
    def average_deaths_per_match(self) -> float:
        """Morts moyennes par match."""
        if self.matches_count == 0:
            return 0.0
        return self.total_deaths / self.matches_count


# =============================================================================
# Fonctions Polars - Séries cumulatives
# =============================================================================


def compute_cumulative_net_score_series_polars(
    match_stats_df: pl.DataFrame,
) -> pl.DataFrame:
    """Calcule la série cumulative du net score avec Polars.

    Le net score est défini comme : kills - deaths.

    Args:
        match_stats_df: DataFrame Polars avec colonnes start_time, kills, deaths.

    Returns:
        DataFrame avec colonnes: match_id, start_time, net_score, cumulative_net_score.

    Raises:
        ValueError: Si Polars n'est pas disponible.

    Example:
        >>> df = repo.query_df("SELECT * FROM match_stats ORDER BY start_time")
        >>> result = compute_cumulative_net_score_series_polars(df)
        >>> print(result.head())
    """
    if not POLARS_AVAILABLE:
        msg = "Polars n'est pas disponible. Installez-le avec: pip install polars"
        raise ValueError(msg)

    if match_stats_df.is_empty():
        return pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "start_time": pl.Utf8,
                "net_score": pl.Int64,
                "cumulative_net_score": pl.Int64,
            }
        )

    # S'assurer que les colonnes requises existent
    required_cols = {"start_time", "kills", "deaths"}
    available_cols = set(match_stats_df.columns)
    if not required_cols.issubset(available_cols):
        missing = required_cols - available_cols
        msg = f"Colonnes manquantes: {missing}"
        raise ValueError(msg)

    # Calculer net score et cumul
    result = (
        match_stats_df.sort("start_time")
        .with_columns(
            [
                # Net score = kills - deaths
                (pl.col("kills").fill_null(0) - pl.col("deaths").fill_null(0)).alias("net_score"),
            ]
        )
        .with_columns(
            [
                # Cumul du net score
                pl.col("net_score").cum_sum().alias("cumulative_net_score"),
            ]
        )
    )

    # Sélectionner les colonnes de sortie
    output_cols = ["start_time", "net_score", "cumulative_net_score"]
    if "match_id" in result.columns:
        output_cols = ["match_id"] + output_cols

    return result.select(output_cols)


def compute_cumulative_kd_series_polars(
    match_stats_df: pl.DataFrame,
) -> pl.DataFrame:
    """Calcule la série cumulative du K/D avec Polars.

    Le K/D cumulé est calculé comme: sum(kills) / max(1, sum(deaths)).

    Args:
        match_stats_df: DataFrame Polars avec colonnes start_time, kills, deaths.

    Returns:
        DataFrame avec colonnes: match_id, start_time, kd, cumulative_kills,
        cumulative_deaths, cumulative_kd.
    """
    if not POLARS_AVAILABLE:
        msg = "Polars n'est pas disponible."
        raise ValueError(msg)

    if match_stats_df.is_empty():
        return pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "start_time": pl.Utf8,
                "kd": pl.Float64,
                "cumulative_kills": pl.Int64,
                "cumulative_deaths": pl.Int64,
                "cumulative_kd": pl.Float64,
            }
        )

    result = (
        match_stats_df.sort("start_time")
        .with_columns(
            [
                # K/D du match
                (
                    pl.col("kills").fill_null(0)
                    / pl.when(pl.col("deaths").fill_null(0) == 0)
                    .then(1)
                    .otherwise(pl.col("deaths").fill_null(0))
                ).alias("kd"),
                # Cumuls
                pl.col("kills").fill_null(0).cum_sum().alias("cumulative_kills"),
                pl.col("deaths").fill_null(0).cum_sum().alias("cumulative_deaths"),
            ]
        )
        .with_columns(
            [
                # K/D cumulé
                (
                    pl.col("cumulative_kills")
                    / pl.when(pl.col("cumulative_deaths") == 0)
                    .then(1)
                    .otherwise(pl.col("cumulative_deaths"))
                ).alias("cumulative_kd"),
            ]
        )
    )

    # Sélectionner les colonnes de sortie
    output_cols = [
        "start_time",
        "kd",
        "cumulative_kills",
        "cumulative_deaths",
        "cumulative_kd",
    ]
    if "match_id" in result.columns:
        output_cols = ["match_id"] + output_cols

    return result.select(output_cols)


def compute_cumulative_kda_series_polars(
    match_stats_df: pl.DataFrame,
) -> pl.DataFrame:
    """Calcule la série cumulative du KDA avec Polars.

    Le KDA cumulé est calculé comme: (sum(kills) + sum(assists)) / max(1, sum(deaths)).

    Args:
        match_stats_df: DataFrame Polars avec colonnes start_time, kills, deaths, assists.

    Returns:
        DataFrame avec colonnes: match_id, start_time, kda, cumulative_kda.
    """
    if not POLARS_AVAILABLE:
        msg = "Polars n'est pas disponible."
        raise ValueError(msg)

    if match_stats_df.is_empty():
        return pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "start_time": pl.Utf8,
                "kda": pl.Float64,
                "cumulative_kda": pl.Float64,
            }
        )

    result = (
        match_stats_df.sort("start_time")
        .with_columns(
            [
                # KDA du match: (K + A) / max(1, D)
                (
                    (pl.col("kills").fill_null(0) + pl.col("assists").fill_null(0))
                    / pl.when(pl.col("deaths").fill_null(0) == 0)
                    .then(1)
                    .otherwise(pl.col("deaths").fill_null(0))
                ).alias("kda"),
                # Cumuls
                pl.col("kills").fill_null(0).cum_sum().alias("_cum_kills"),
                pl.col("deaths").fill_null(0).cum_sum().alias("_cum_deaths"),
                pl.col("assists").fill_null(0).cum_sum().alias("_cum_assists"),
            ]
        )
        .with_columns(
            [
                # KDA cumulé
                (
                    (pl.col("_cum_kills") + pl.col("_cum_assists"))
                    / pl.when(pl.col("_cum_deaths") == 0).then(1).otherwise(pl.col("_cum_deaths"))
                ).alias("cumulative_kda"),
            ]
        )
    )

    # Sélectionner les colonnes de sortie
    output_cols = ["start_time", "kda", "cumulative_kda"]
    if "match_id" in result.columns:
        output_cols = ["match_id"] + output_cols

    return result.select(output_cols)


def compute_cumulative_objective_score_series_polars(
    awards_df: pl.DataFrame,
    match_stats_df: pl.DataFrame,
) -> pl.DataFrame:
    """Calcule la série cumulative du score objectifs avec Polars.

    Utilise les personal_score_awards pour calculer le score objectifs.

    Args:
        awards_df: DataFrame des personal_score_awards.
        match_stats_df: DataFrame des match_stats (pour start_time).

    Returns:
        DataFrame avec colonnes: match_id, start_time, objective_score, cumulative_objective.
    """
    if not POLARS_AVAILABLE:
        msg = "Polars n'est pas disponible."
        raise ValueError(msg)

    if awards_df.is_empty() or match_stats_df.is_empty():
        return pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "start_time": pl.Utf8,
                "objective_score": pl.Float64,
                "cumulative_objective": pl.Float64,
            }
        )

    # Catégories d'objectifs (depuis refdata)
    objective_categories = ["objective", "mode"]

    # Calculer score objectifs par match
    objective_by_match = (
        awards_df.filter(pl.col("score_category").is_in(objective_categories))
        .group_by("match_id")
        .agg(pl.col("points").sum().alias("objective_score"))
    )

    # Joindre avec match_stats pour avoir start_time
    result = (
        match_stats_df.select(["match_id", "start_time"])
        .join(objective_by_match, on="match_id", how="left")
        .with_columns([pl.col("objective_score").fill_null(0)])
        .sort("start_time")
        .with_columns([pl.col("objective_score").cum_sum().alias("cumulative_objective")])
    )

    return result.select(["match_id", "start_time", "objective_score", "cumulative_objective"])


# =============================================================================
# Fonctions Polars - Métriques agrégées
# =============================================================================


def compute_cumulative_metrics_polars(
    match_stats_df: pl.DataFrame,
) -> CumulativeMetricsResult:
    """Calcule les métriques cumulées finales pour une session.

    Args:
        match_stats_df: DataFrame Polars des matchs.

    Returns:
        CumulativeMetricsResult avec toutes les métriques.
    """
    if not POLARS_AVAILABLE:
        msg = "Polars n'est pas disponible."
        raise ValueError(msg)

    if match_stats_df.is_empty():
        return CumulativeMetricsResult(
            total_kills=0,
            total_deaths=0,
            total_assists=0,
            cumulative_net_score=0,
            cumulative_kd=0.0,
            cumulative_kda=0.0,
            matches_count=0,
        )

    # Calculer les totaux
    totals = match_stats_df.select(
        [
            pl.col("kills").fill_null(0).sum().alias("total_kills"),
            pl.col("deaths").fill_null(0).sum().alias("total_deaths"),
            pl.col("assists").fill_null(0).sum().alias("total_assists"),
            pl.len().alias("matches_count"),
        ]
    ).row(0, named=True)

    total_kills = int(totals["total_kills"])
    total_deaths = int(totals["total_deaths"])
    total_assists = int(totals["total_assists"])
    matches_count = int(totals["matches_count"])

    # Calculs dérivés
    net_score = total_kills - total_deaths
    kd = total_kills / max(1, total_deaths)
    kda = (total_kills + total_assists) / max(1, total_deaths)

    return CumulativeMetricsResult(
        total_kills=total_kills,
        total_deaths=total_deaths,
        total_assists=total_assists,
        cumulative_net_score=net_score,
        cumulative_kd=round(kd, 2),
        cumulative_kda=round(kda, 2),
        matches_count=matches_count,
    )


def compute_rolling_kd_polars(
    match_stats_df: pl.DataFrame,
    window_size: int = 5,
) -> pl.DataFrame:
    """Calcule le K/D glissant sur une fenêtre de matchs.

    Args:
        match_stats_df: DataFrame Polars des matchs.
        window_size: Taille de la fenêtre glissante.

    Returns:
        DataFrame avec colonnes: match_id, start_time, kd, rolling_kd.
    """
    if not POLARS_AVAILABLE:
        msg = "Polars n'est pas disponible."
        raise ValueError(msg)

    if match_stats_df.is_empty():
        return pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "start_time": pl.Utf8,
                "kd": pl.Float64,
                "rolling_kd": pl.Float64,
            }
        )

    result = (
        match_stats_df.sort("start_time")
        .with_columns(
            [
                # K/D du match
                (
                    pl.col("kills").fill_null(0)
                    / pl.when(pl.col("deaths").fill_null(0) == 0)
                    .then(1)
                    .otherwise(pl.col("deaths").fill_null(0))
                ).alias("kd"),
                # Rolling sum
                pl.col("kills")
                .fill_null(0)
                .rolling_sum(window_size=window_size)
                .alias("_rolling_kills"),
                pl.col("deaths")
                .fill_null(0)
                .rolling_sum(window_size=window_size)
                .alias("_rolling_deaths"),
            ]
        )
        .with_columns(
            [
                # K/D glissant
                (
                    pl.col("_rolling_kills")
                    / pl.when(pl.col("_rolling_deaths") == 0)
                    .then(1)
                    .otherwise(pl.col("_rolling_deaths"))
                ).alias("rolling_kd"),
            ]
        )
    )

    # Sélectionner les colonnes de sortie
    output_cols = ["start_time", "kd", "rolling_kd"]
    if "match_id" in result.columns:
        output_cols = ["match_id"] + output_cols

    return result.select(output_cols)


def compute_session_trend_polars(
    match_stats_df: pl.DataFrame,
) -> dict[str, Any]:
    """Calcule la tendance d'une session (amélioration ou dégradation).

    Compare la première et la seconde moitié de la session.

    Args:
        match_stats_df: DataFrame Polars des matchs triés par start_time.

    Returns:
        Dict avec:
        - trend: "improving", "declining", ou "stable"
        - first_half_kd: K/D de la première moitié
        - second_half_kd: K/D de la seconde moitié
        - kd_change: Différence de K/D
        - kd_change_pct: Changement en pourcentage
    """
    if not POLARS_AVAILABLE:
        msg = "Polars n'est pas disponible."
        raise ValueError(msg)

    if match_stats_df.is_empty() or len(match_stats_df) < 4:
        return {
            "trend": "stable",
            "first_half_kd": None,
            "second_half_kd": None,
            "kd_change": None,
            "kd_change_pct": None,
        }

    df = match_stats_df.sort("start_time")
    mid = len(df) // 2

    # Première moitié
    first_half = df.head(mid)
    first_kills = first_half.select(pl.col("kills").fill_null(0).sum()).item()
    first_deaths = first_half.select(pl.col("deaths").fill_null(0).sum()).item()
    first_kd = first_kills / max(1, first_deaths)

    # Seconde moitié
    second_half = df.tail(len(df) - mid)
    second_kills = second_half.select(pl.col("kills").fill_null(0).sum()).item()
    second_deaths = second_half.select(pl.col("deaths").fill_null(0).sum()).item()
    second_kd = second_kills / max(1, second_deaths)

    # Calcul de la tendance
    kd_change = second_kd - first_kd
    kd_change_pct = (kd_change / first_kd * 100) if first_kd > 0 else 0

    # Seuil de 10% pour considérer un changement significatif
    if kd_change_pct > 10:
        trend = "improving"
    elif kd_change_pct < -10:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "first_half_kd": round(first_kd, 2),
        "second_half_kd": round(second_kd, 2),
        "kd_change": round(kd_change, 2),
        "kd_change_pct": round(kd_change_pct, 1),
    }


# =============================================================================
# Fonctions de compatibilité pour l'intégration UI
# =============================================================================


def cumulative_series_to_dicts(
    df: pl.DataFrame,
) -> list[dict[str, Any]]:
    """Convertit un DataFrame Polars en liste de dicts pour Plotly.

    Args:
        df: DataFrame Polars de série cumulative.

    Returns:
        Liste de dictionnaires pour utilisation avec Plotly.
    """
    if not POLARS_AVAILABLE:
        return []

    if df.is_empty():
        return []

    return df.to_dicts()
