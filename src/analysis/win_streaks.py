"""Module d'analyse des séries de victoires/défaites avec Polars.

Sprint 7: Fonctions pour calculer les séries de victoires (win streaks),
séries de défaites (loss streaks) et statistiques associées.
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
# Constantes
# =============================================================================

OUTCOME_WIN: int = 2
OUTCOME_LOSS: int = 3


# =============================================================================
# Dataclasses de résultats
# =============================================================================


@dataclass(frozen=True)
class StreakRecord:
    """Enregistrement d'une série (victoires ou défaites).

    Attributes:
        streak_type: Type de série ("win" ou "loss").
        length: Nombre de matchs consécutifs.
        start_index: Index du premier match de la série.
        end_index: Index du dernier match de la série.
        start_time: Timestamp du premier match.
        end_time: Timestamp du dernier match.
    """

    streak_type: str
    length: int
    start_index: int
    end_index: int
    start_time: str | None = None
    end_time: str | None = None


@dataclass(frozen=True)
class StreakSummary:
    """Résumé statistique des séries.

    Attributes:
        current_streak_type: Type de la série en cours ("win", "loss" ou "none").
        current_streak_length: Longueur de la série en cours.
        longest_win_streak: Plus longue série de victoires.
        longest_loss_streak: Plus longue série de défaites.
        avg_win_streak: Longueur moyenne des séries de victoires.
        avg_loss_streak: Longueur moyenne des séries de défaites.
        total_win_streaks: Nombre total de séries de victoires (>= 2).
        total_loss_streaks: Nombre total de séries de défaites (>= 2).
        total_matches: Nombre total de matchs analysés.
    """

    current_streak_type: str
    current_streak_length: int
    longest_win_streak: int
    longest_loss_streak: int
    avg_win_streak: float
    avg_loss_streak: float
    total_win_streaks: int
    total_loss_streaks: int
    total_matches: int


@dataclass(frozen=True)
class RollingStreakResult:
    """Résultat du calcul de séries glissantes pour visualisation.

    Contient le DataFrame Polars avec les colonnes de séries.
    """

    df: Any  # pl.DataFrame
    longest_win: int
    longest_loss: int


# =============================================================================
# Fonctions Polars - Séries de victoires/défaites
# =============================================================================


def compute_streaks_polars(
    match_stats_df: pl.DataFrame,
) -> list[StreakRecord]:
    """Calcule toutes les séries de victoires et défaites consécutives.

    Args:
        match_stats_df: DataFrame Polars avec colonnes outcome, start_time.

    Returns:
        Liste de StreakRecord triée chronologiquement.

    Raises:
        ValueError: Si Polars n'est pas disponible.
    """
    if not POLARS_AVAILABLE:
        raise ValueError("Polars est requis pour compute_streaks_polars")

    if match_stats_df is None or match_stats_df.is_empty():
        return []

    required_cols = {"outcome", "start_time"}
    available_cols = set(match_stats_df.columns)
    if not required_cols.issubset(available_cols):
        return []

    # Trier par date et ne garder que les V/D
    sorted_df = (
        match_stats_df.sort("start_time")
        .filter(pl.col("outcome").is_in([OUTCOME_WIN, OUTCOME_LOSS]))
        .with_row_index("_idx")
    )

    if sorted_df.is_empty():
        return []

    # Détecter les changements de résultat (début de nouvelle série)
    sorted_df = sorted_df.with_columns(
        (pl.col("outcome") != pl.col("outcome").shift(1)).fill_null(True).alias("_new_streak")
    )

    # Assigner un ID de groupe par série
    sorted_df = sorted_df.with_columns(pl.col("_new_streak").cum_sum().alias("_streak_group"))

    # Agréger par groupe de série
    streaks_agg = (
        sorted_df.group_by("_streak_group")
        .agg(
            pl.col("outcome").first().alias("outcome"),
            pl.col("_idx").count().alias("length"),
            pl.col("_idx").min().alias("start_index"),
            pl.col("_idx").max().alias("end_index"),
            pl.col("start_time").first().alias("first_time"),
            pl.col("start_time").last().alias("last_time"),
        )
        .sort("_streak_group")
    )

    records: list[StreakRecord] = []
    for row in streaks_agg.iter_rows(named=True):
        streak_type = "win" if row["outcome"] == OUTCOME_WIN else "loss"
        first_time = str(row["first_time"]) if row["first_time"] is not None else None
        last_time = str(row["last_time"]) if row["last_time"] is not None else None
        records.append(
            StreakRecord(
                streak_type=streak_type,
                length=row["length"],
                start_index=row["start_index"],
                end_index=row["end_index"],
                start_time=first_time,
                end_time=last_time,
            )
        )

    return records


def compute_streak_summary_polars(
    match_stats_df: pl.DataFrame,
) -> StreakSummary:
    """Calcule un résumé statistique des séries de victoires/défaites.

    Args:
        match_stats_df: DataFrame Polars avec colonnes outcome, start_time.

    Returns:
        StreakSummary avec statistiques agrégées.
    """
    if not POLARS_AVAILABLE:
        raise ValueError("Polars est requis pour compute_streak_summary_polars")

    streaks = compute_streaks_polars(match_stats_df)

    if not streaks:
        total = 0
        if match_stats_df is not None and not match_stats_df.is_empty():
            total = len(match_stats_df)
        return StreakSummary(
            current_streak_type="none",
            current_streak_length=0,
            longest_win_streak=0,
            longest_loss_streak=0,
            avg_win_streak=0.0,
            avg_loss_streak=0.0,
            total_win_streaks=0,
            total_loss_streaks=0,
            total_matches=total,
        )

    # Série en cours (dernière)
    current = streaks[-1]
    current_type = current.streak_type
    current_length = current.length

    # Filtrer par type
    win_streaks = [s for s in streaks if s.streak_type == "win"]
    loss_streaks = [s for s in streaks if s.streak_type == "loss"]

    longest_win = max((s.length for s in win_streaks), default=0)
    longest_loss = max((s.length for s in loss_streaks), default=0)

    # Séries significatives (>= 2 matchs)
    significant_wins = [s for s in win_streaks if s.length >= 2]
    significant_losses = [s for s in loss_streaks if s.length >= 2]

    avg_win = (
        sum(s.length for s in significant_wins) / len(significant_wins) if significant_wins else 0.0
    )
    avg_loss = (
        sum(s.length for s in significant_losses) / len(significant_losses)
        if significant_losses
        else 0.0
    )

    total = 0
    if match_stats_df is not None and not match_stats_df.is_empty():
        total = len(match_stats_df)

    return StreakSummary(
        current_streak_type=current_type,
        current_streak_length=current_length,
        longest_win_streak=longest_win,
        longest_loss_streak=longest_loss,
        avg_win_streak=round(avg_win, 1),
        avg_loss_streak=round(avg_loss, 1),
        total_win_streaks=len(significant_wins),
        total_loss_streaks=len(significant_losses),
        total_matches=total,
    )


def compute_streak_series_polars(
    match_stats_df: pl.DataFrame,
) -> pl.DataFrame:
    """Calcule une série temporelle des séries pour visualisation.

    Pour chaque match, calcule la longueur de la série en cours à ce point.
    Les victoires sont comptées positivement, les défaites négativement.

    Args:
        match_stats_df: DataFrame Polars avec colonnes outcome, start_time.

    Returns:
        DataFrame Polars avec colonnes:
            - start_time: Timestamp du match.
            - outcome: Résultat du match.
            - streak_value: Longueur de la série (+N pour victoires, -N pour défaites).
            - is_win: Booléen indiquant la victoire.
            - match_id: ID du match (si disponible).

    Raises:
        ValueError: Si Polars n'est pas disponible.
    """
    if not POLARS_AVAILABLE:
        raise ValueError("Polars est requis pour compute_streak_series_polars")

    if match_stats_df is None or match_stats_df.is_empty():
        return pl.DataFrame(
            schema={
                "start_time": pl.Utf8,
                "outcome": pl.Int64,
                "streak_value": pl.Int64,
                "is_win": pl.Boolean,
            }
        )

    required_cols = {"outcome", "start_time"}
    available_cols = set(match_stats_df.columns)
    if not required_cols.issubset(available_cols):
        return pl.DataFrame(
            schema={
                "start_time": pl.Utf8,
                "outcome": pl.Int64,
                "streak_value": pl.Int64,
                "is_win": pl.Boolean,
            }
        )

    # Colonnes à sélectionner
    select_cols = ["start_time", "outcome"]
    if "match_id" in available_cols:
        select_cols.append("match_id")

    # Trier et filtrer V/D uniquement
    sorted_df = (
        match_stats_df.select(select_cols)
        .sort("start_time")
        .filter(pl.col("outcome").is_in([OUTCOME_WIN, OUTCOME_LOSS]))
    )

    if sorted_df.is_empty():
        schema = {
            "start_time": pl.Utf8,
            "outcome": pl.Int64,
            "streak_value": pl.Int64,
            "is_win": pl.Boolean,
        }
        if "match_id" in select_cols:
            schema["match_id"] = pl.Utf8
        return pl.DataFrame(schema=schema)

    # Marquer les victoires
    sorted_df = sorted_df.with_columns((pl.col("outcome") == OUTCOME_WIN).alias("is_win"))

    # Détecter les changements de résultat
    sorted_df = sorted_df.with_columns(
        (pl.col("outcome") != pl.col("outcome").shift(1)).fill_null(True).alias("_new_streak")
    )

    # Assigner un groupe de série
    sorted_df = sorted_df.with_columns(pl.col("_new_streak").cum_sum().alias("_streak_group"))

    # Calculer le compteur cumulatif au sein de chaque groupe
    sorted_df = sorted_df.with_columns(
        pl.col("outcome").cum_count().over("_streak_group").cast(pl.Int64).alias("_streak_count")
    )

    # Valeur de la série : positif pour victoires, négatif pour défaites
    sorted_df = sorted_df.with_columns(
        pl.when(pl.col("is_win"))
        .then(pl.col("_streak_count"))
        .otherwise(-pl.col("_streak_count"))
        .alias("streak_value")
    )

    # Sélection finale
    output_cols = ["start_time", "outcome", "streak_value", "is_win"]
    if "match_id" in sorted_df.columns:
        output_cols.append("match_id")

    return sorted_df.select(output_cols)


def compute_rolling_win_rate_polars(
    match_stats_df: pl.DataFrame,
    window_size: int = 10,
) -> pl.DataFrame:
    """Calcule le taux de victoire glissant.

    Args:
        match_stats_df: DataFrame Polars avec colonnes outcome, start_time.
        window_size: Taille de la fenêtre glissante.

    Returns:
        DataFrame Polars avec colonnes:
            - start_time: Timestamp du match.
            - win_rate: Taux de victoire (0-100) sur la fenêtre.
            - match_index: Index du match.
    """
    if not POLARS_AVAILABLE:
        raise ValueError("Polars est requis pour compute_rolling_win_rate_polars")

    if match_stats_df is None or match_stats_df.is_empty():
        return pl.DataFrame(
            schema={
                "start_time": pl.Utf8,
                "win_rate": pl.Float64,
                "match_index": pl.UInt32,
            }
        )

    required_cols = {"outcome", "start_time"}
    if not required_cols.issubset(set(match_stats_df.columns)):
        return pl.DataFrame(
            schema={
                "start_time": pl.Utf8,
                "win_rate": pl.Float64,
                "match_index": pl.UInt32,
            }
        )

    sorted_df = (
        match_stats_df.select(["start_time", "outcome"])
        .sort("start_time")
        .filter(pl.col("outcome").is_in([OUTCOME_WIN, OUTCOME_LOSS]))
    )

    if sorted_df.is_empty():
        return pl.DataFrame(
            schema={
                "start_time": pl.Utf8,
                "win_rate": pl.Float64,
                "match_index": pl.UInt32,
            }
        )

    w = max(1, int(window_size))

    sorted_df = sorted_df.with_columns(
        (pl.col("outcome") == OUTCOME_WIN).cast(pl.Float64).alias("_is_win"),
    ).with_row_index("match_index")

    # Rolling mean via rolling_mean
    sorted_df = sorted_df.with_columns(
        (pl.col("_is_win").rolling_mean(window_size=w, min_periods=1) * 100.0).alias("win_rate")
    )

    return sorted_df.select(["start_time", "win_rate", "match_index"])


def streak_series_to_dicts(df: pl.DataFrame) -> list[dict[str, Any]]:
    """Convertit un DataFrame de séries en liste de dicts pour Plotly.

    Args:
        df: DataFrame Polars issu de compute_streak_series_polars.

    Returns:
        Liste de dictionnaires.
    """
    if df is None or df.is_empty():
        return []
    return df.to_dicts()
