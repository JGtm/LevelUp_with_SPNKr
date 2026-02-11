from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import polars as pl

from src.analysis.performance_config import (
    MIN_MATCHES_FOR_RELATIVE,
    RELATIVE_WEIGHTS,
)


def _normalize_df(df: pl.DataFrame | Any) -> pl.DataFrame:
    """Convertit un DataFrame Pandas en Polars si nécessaire."""
    if isinstance(df, pl.DataFrame):
        return df
    # Assume Pandas-like — Polars gère l'import en interne
    return pl.from_pandas(df)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# =============================================================================
# Score de performance RELATIF par match (0-100)
# =============================================================================
#
# Ce score compare la performance du match à l'historique personnel du joueur.
# - 50 = match dans ta moyenne
# - 100 = meilleur match de ton historique
# - 0 = pire match de ton historique
#
# Configuration centralisée dans : src/analysis/performance_config.py
# =============================================================================


def _safe_float(value: Any) -> float | None:
    """Convertit une valeur en float, retourne None si impossible."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _compute_per_minute(value: float | None, duration_seconds: float | None) -> float | None:
    """Calcule une valeur par minute."""
    if value is None or duration_seconds is None:
        return None
    if duration_seconds <= 0:
        return None
    return float(value) / (float(duration_seconds) / 60.0)


def _percentile_rank(value: float, series: pl.Series) -> float:
    """Calcule le percentile d'une valeur dans une série (0-100).

    Args:
        value: Valeur à évaluer.
        series: Série Polars de référence (historique).

    Returns:
        Percentile 0-100 où 50 = médiane.
    """
    if series.is_empty() or len(series) < 2:
        return 50.0  # Pas assez de données, on retourne la moyenne

    # Nombre de valeurs inférieures ou égales
    below_or_equal = (series <= value).sum()
    # Pourcentage
    percentile = (below_or_equal / len(series)) * 100.0
    return _clamp(percentile, 0.0, 100.0)


def _percentile_rank_inverse(value: float, series: pl.Series) -> float:
    """Percentile inversé (pour les morts: moins = mieux)."""
    if series.is_empty() or len(series) < 2:
        return 50.0
    # Plus la valeur est basse, meilleur est le percentile
    above_or_equal = (series >= value).sum()
    percentile = (above_or_equal / len(series)) * 100.0
    return _clamp(percentile, 0.0, 100.0)


def _safe_col(df: pl.DataFrame, col: str, default: float = 0.0) -> pl.Expr:
    """Retourne une expression pour une colonne, ou un literal si absente."""
    if col in df.columns:
        return pl.col(col).cast(pl.Float64, strict=False).fill_null(default)
    return pl.lit(default)


def _prepare_history_metrics(df_history: pl.DataFrame) -> pl.DataFrame:
    """Prépare les métriques normalisées par minute pour l'historique.

    Args:
        df_history: DataFrame Polars de l'historique des matchs.

    Returns:
        DataFrame Polars avec colonnes:
        - kpm, dpm_deaths, apm, kda, accuracy (existants, dpm renommé en dpm_deaths)
        - pspm, dpm_damage, rank_perf_diff (nouveaux v4)
    """
    output_cols = [
        "kpm",
        "dpm_deaths",
        "apm",
        "kda",
        "accuracy",
        "pspm",
        "dpm_damage",
        "rank_perf_diff",
    ]

    if df_history.is_empty():
        return pl.DataFrame(schema={c: pl.Float64 for c in output_cols})

    # Durée du match en secondes
    duration_col = None
    for col in ["time_played_seconds", "duration_seconds", "match_duration_seconds"]:
        if col in df_history.columns:
            duration_col = col
            break

    if duration_col is None:
        df = df_history.with_columns(pl.lit(600.0).alias("_duration"))
    else:
        df = df_history.with_columns(
            pl.when(pl.col(duration_col).cast(pl.Float64, strict=False).fill_null(0.0) <= 0)
            .then(600.0)
            .otherwise(pl.col(duration_col).cast(pl.Float64, strict=False).fill_null(600.0))
            .alias("_duration")
        )

    # Calcul des métriques par minute
    minutes_expr = pl.col("_duration") / 60.0
    df = df.with_columns(
        [
            (_safe_col(df, "kills") / minutes_expr).alias("kpm"),
            (_safe_col(df, "deaths") / minutes_expr).alias("dpm_deaths"),
            (_safe_col(df, "assists") / minutes_expr).alias("apm"),
        ]
    )

    # KDA
    if "kda" in df.columns:
        df = df.with_columns(pl.col("kda").cast(pl.Float64, strict=False).alias("kda"))
    else:
        k = _safe_col(df, "kills")
        d = pl.when(_safe_col(df, "deaths") < 1.0).then(1.0).otherwise(_safe_col(df, "deaths"))
        a = _safe_col(df, "assists")
        df = df.with_columns(((k + a) / d).alias("kda"))

    # Accuracy
    if "accuracy" in df.columns:
        df = df.with_columns(pl.col("accuracy").cast(pl.Float64, strict=False).alias("accuracy"))
    else:
        df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("accuracy"))

    # PSPM — Personal Score Per Minute (v4)
    if "personal_score" in df.columns:
        df = df.with_columns((_safe_col(df, "personal_score") / minutes_expr).alias("pspm"))
    else:
        df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("pspm"))

    # DPM Damage — Damage Per Minute (v4)
    if "damage_dealt" in df.columns:
        df = df.with_columns((_safe_col(df, "damage_dealt") / minutes_expr).alias("dpm_damage"))
    else:
        df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("dpm_damage"))

    # Rank Performance Diff (v4) — expected_rank - actual_rank
    has_rank = "rank" in df.columns
    has_team_mmr = "team_mmr" in df.columns
    has_enemy_mmr = "enemy_mmr" in df.columns
    if has_rank and has_team_mmr and has_enemy_mmr:
        # expected_rank = 4.5 - (delta_mmr / 100) * 0.5
        # rank_perf_diff = expected_rank - rank (positif = mieux que prévu)
        delta_mmr = _safe_col(df, "team_mmr") - _safe_col(df, "enemy_mmr")
        expected_rank = pl.lit(4.5) - (delta_mmr / pl.lit(100.0)) * pl.lit(0.5)
        actual_rank = _safe_col(df, "rank")
        df = df.with_columns((expected_rank - actual_rank).alias("rank_perf_diff"))
    else:
        df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("rank_perf_diff"))

    return df.select(output_cols)


def _compute_rank_performance(
    rank: int | float,
    team_mmr: float,
    enemy_mmr: float,
    history_metrics: pl.DataFrame,
) -> float | None:
    """Calcule le percentile de performance du rang contextualisé par MMR.

    Args:
        rank: Rang réel dans le match (1 = meilleur).
        team_mmr: MMR de l'équipe.
        enemy_mmr: MMR de l'équipe adverse.
        history_metrics: DataFrame avec colonne rank_perf_diff.

    Returns:
        Percentile 0-100 ou None si données insuffisantes.
    """
    if rank is None or team_mmr is None or enemy_mmr is None:
        return None

    # Rang attendu basé sur l'écart MMR (formule simplifiée pour 4v4, rang moyen = 4.5)
    delta_mmr = float(team_mmr) - float(enemy_mmr)
    expected_rank = 4.5 - (delta_mmr / 100.0) * 0.5

    # Performance = différence entre rang attendu et réel
    # Positif = mieux que prévu
    rank_diff = expected_rank - float(rank)

    if "rank_perf_diff" not in history_metrics.columns:
        return None

    rank_diff_series = history_metrics.get_column("rank_perf_diff").drop_nulls()
    if rank_diff_series.is_empty():
        return None

    return _percentile_rank(rank_diff, rank_diff_series)


def compute_relative_performance_score(
    row: dict[str, Any],
    df_history: pl.DataFrame | Any,
) -> float | None:
    """Calcule le score de performance RELATIF d'un match (v4).

    Compare le match à l'historique personnel du joueur.
    Utilise 8 métriques avec graceful degradation si certaines sont absentes.

    Args:
        row: Dict du match avec kills, deaths, assists, kda, accuracy,
             time_played_seconds, personal_score, damage_dealt, rank,
             team_mmr, enemy_mmr.
        df_history: DataFrame (Polars ou Pandas) de l'historique complet du joueur.

    Returns:
        Score 0-100 où 50 = performance moyenne, 100 = meilleure perf, 0 = pire perf.
        None si pas assez de données.
    """
    # Normaliser en Polars
    df_history = _normalize_df(df_history)

    if df_history is None or df_history.is_empty():
        return None

    if len(df_history) < MIN_MATCHES_FOR_RELATIVE:
        return None

    # Préparer l'historique
    history_metrics = _prepare_history_metrics(df_history)

    # Extraire les valeurs du match actuel
    try:
        # Durée du match
        duration = None
        for col in ["time_played_seconds", "duration_seconds", "match_duration_seconds"]:
            val = row.get(col)
            if val is not None:
                try:
                    duration = float(val)
                    if duration > 0:
                        break
                except (ValueError, TypeError):
                    pass
        if duration is None or duration <= 0:
            duration = 600.0  # 10 min par défaut

        minutes = duration / 60.0

        kills = float(row.get("kills") or 0)
        deaths = float(row.get("deaths") or 0)
        assists = float(row.get("assists") or 0)

        # Métriques par minute
        kpm = kills / minutes
        dpm_deaths = deaths / minutes
        apm = assists / minutes

        # KDA
        kda = row.get("kda")
        if kda is not None:
            try:
                kda = float(kda)
            except (ValueError, TypeError):
                kda = (kills + assists) / max(1, deaths)
        else:
            kda = (kills + assists) / max(1, deaths)

        # Accuracy
        accuracy = _safe_float(row.get("accuracy"))

        # v4: Personal Score Per Minute
        personal_score = _safe_float(row.get("personal_score"))
        pspm = personal_score / minutes if personal_score is not None else None

        # v4: Damage Per Minute
        damage_dealt = _safe_float(row.get("damage_dealt"))
        dpm_damage = damage_dealt / minutes if damage_dealt is not None else None

        # v4: Rank Performance
        rank = _safe_float(row.get("rank"))
        team_mmr = _safe_float(row.get("team_mmr"))
        enemy_mmr = _safe_float(row.get("enemy_mmr"))

    except Exception:
        return None

    # Calculer les percentiles pour chaque métrique
    percentiles = {}
    weights_used = {}

    # KPM - plus c'est haut, mieux c'est
    kpm_series = history_metrics.get_column("kpm").drop_nulls()
    if not kpm_series.is_empty():
        percentiles["kpm"] = _percentile_rank(kpm, kpm_series)
        weights_used["kpm"] = RELATIVE_WEIGHTS["kpm"]

    # DPM Deaths - moins c'est haut, mieux c'est (inversé)
    dpm_deaths_series = history_metrics.get_column("dpm_deaths").drop_nulls()
    if not dpm_deaths_series.is_empty():
        percentiles["dpm_deaths"] = _percentile_rank_inverse(dpm_deaths, dpm_deaths_series)
        weights_used["dpm_deaths"] = RELATIVE_WEIGHTS["dpm_deaths"]

    # APM - plus c'est haut, mieux c'est
    apm_series = history_metrics.get_column("apm").drop_nulls()
    if not apm_series.is_empty():
        percentiles["apm"] = _percentile_rank(apm, apm_series)
        weights_used["apm"] = RELATIVE_WEIGHTS["apm"]

    # KDA - plus c'est haut, mieux c'est
    kda_series = history_metrics.get_column("kda").drop_nulls()
    if not kda_series.is_empty():
        percentiles["kda"] = _percentile_rank(kda, kda_series)
        weights_used["kda"] = RELATIVE_WEIGHTS["kda"]

    # Accuracy - plus c'est haut, mieux c'est
    if accuracy is not None:
        acc_series = history_metrics.get_column("accuracy").drop_nulls()
        if not acc_series.is_empty():
            percentiles["accuracy"] = _percentile_rank(accuracy, acc_series)
            weights_used["accuracy"] = RELATIVE_WEIGHTS["accuracy"]

    # v4: PSPM - plus c'est haut, mieux c'est
    if pspm is not None:
        pspm_series = history_metrics.get_column("pspm").drop_nulls()
        if not pspm_series.is_empty():
            percentiles["pspm"] = _percentile_rank(pspm, pspm_series)
            weights_used["pspm"] = RELATIVE_WEIGHTS["pspm"]

    # v4: DPM Damage - plus c'est haut, mieux c'est
    if dpm_damage is not None:
        dpm_damage_series = history_metrics.get_column("dpm_damage").drop_nulls()
        if not dpm_damage_series.is_empty():
            percentiles["dpm_damage"] = _percentile_rank(dpm_damage, dpm_damage_series)
            weights_used["dpm_damage"] = RELATIVE_WEIGHTS["dpm_damage"]

    # v4: Rank Performance (MMR-adjusted)
    if rank is not None and team_mmr is not None and enemy_mmr is not None:
        rank_perf = _compute_rank_performance(rank, team_mmr, enemy_mmr, history_metrics)
        if rank_perf is not None:
            percentiles["rank_perf"] = rank_perf
            weights_used["rank_perf"] = RELATIVE_WEIGHTS["rank_perf"]

    if not percentiles:
        return None

    # Moyenne pondérée des percentiles
    total_weight = sum(weights_used.values())
    if total_weight <= 0:
        return None

    score = sum(percentiles[k] * weights_used[k] for k in percentiles) / total_weight

    return round(score, 1)


def compute_performance_series(
    df: pl.DataFrame | Any,
    df_history: pl.DataFrame | Any | None = None,
) -> pl.Series | Any:
    """Calcule le score de performance pour chaque match d'un DataFrame.

    Args:
        df: DataFrame (Polars ou Pandas) des matchs à évaluer.
        df_history: Historique complet (Polars ou Pandas) pour le calcul relatif.
                    Si None, utilise df comme historique.

    Returns:
        Series avec les scores de performance (Polars si entrée Polars, Pandas sinon).
    """
    was_pandas = not isinstance(df, pl.DataFrame)

    # Normaliser en Polars
    df_pl = _normalize_df(df)
    history_pl = _normalize_df(df_history) if df_history is not None else None

    if df_pl.is_empty():
        result = pl.Series("performance", [], dtype=pl.Float64)
        if was_pandas:
            return result.to_pandas()
        return result

    # Si pas d'historique fourni, on utilise le DataFrame lui-même
    history = history_pl if history_pl is not None else df_pl

    if len(history) < MIN_MATCHES_FOR_RELATIVE:
        result = pl.Series("performance", [None] * len(df_pl), dtype=pl.Float64)
        if was_pandas:
            return result.to_pandas()
        return result

    # Calculer le score pour chaque ligne (dict via iter_rows)
    scores = [
        compute_relative_performance_score(row_dict, history)
        for row_dict in df_pl.iter_rows(named=True)
    ]

    result = pl.Series("performance", scores, dtype=pl.Float64)
    if was_pandas:
        return result.to_pandas()
    return result


# =============================================================================
# Helpers internes
# =============================================================================


def _mean_numeric(df: pl.DataFrame, column: str) -> float | None:
    if column not in df.columns:
        return None
    values = df.get_column(column).cast(pl.Float64, strict=False).drop_nulls()
    if values.is_empty():
        return None
    return float(values.mean())


def _sum_int(df: pl.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    values = df.get_column(column).cast(pl.Float64, strict=False).fill_null(0)
    return int(values.sum())


def _count_wins(df: pl.DataFrame) -> int:
    """Compte le nombre de victoires (outcome == 2) dans le DataFrame."""
    if "outcome" not in df.columns:
        return 0
    return int(df.get_column("outcome").cast(pl.Float64, strict=False).fill_null(0).eq(2.0).sum())


def _saturation_score(x: float, scale: float) -> float:
    """Score 0–100 avec saturation exponentielle.

    - x=0 -> 0
    - x ~= scale*ln(2) -> 50
    - x -> +inf -> 100

    Args:
        x: valeur positive.
        scale: échelle de la courbe (doit être > 0).

    Returns:
        Score entre 0 et 100.
    """
    if scale <= 0:
        return 0.0
    if x <= 0:
        return 0.0
    return _clamp(100.0 * (1.0 - math.exp(-x / scale)))


@dataclass(frozen=True)
class ScoreComponent:
    """Une composante de score (0–100) avec une pondération."""

    key: str
    label: str
    weight: float
    compute: Callable[[pl.DataFrame], tuple[float | None, dict[str, Any]]]


def _compute_kd_component(df: pl.DataFrame) -> tuple[float | None, dict[str, Any]]:
    kills = _sum_int(df, "kills")
    deaths = _sum_int(df, "deaths")
    if kills == 0 and deaths == 0:
        return None, {"kd_ratio": None}

    kd_ratio = (kills / deaths) if deaths > 0 else float(kills)
    kd_score = _clamp(kd_ratio * 50.0)
    return kd_score, {"kd_ratio": round(kd_ratio, 2)}


def _compute_win_component(df: pl.DataFrame) -> tuple[float | None, dict[str, Any]]:
    if "outcome" not in df.columns:
        return None, {"win_rate": None}

    n = len(df)
    if n <= 0:
        return None, {"win_rate": None}

    wins = _count_wins(df)
    win_rate = wins / n
    return _clamp(win_rate * 100.0), {"win_rate": round(win_rate * 100.0, 1)}


def _compute_accuracy_component(df: pl.DataFrame) -> tuple[float | None, dict[str, Any]]:
    acc = None
    if "accuracy" in df.columns:
        acc = _mean_numeric(df, "accuracy")
    elif "shots_accuracy" in df.columns:
        acc = _mean_numeric(df, "shots_accuracy")

    if acc is None:
        return None, {"accuracy": None}

    return _clamp(acc), {"accuracy": round(acc, 1)}


def _compute_kpm_component(df: pl.DataFrame) -> tuple[float | None, dict[str, Any]]:
    kpm = _mean_numeric(df, "kills_per_min")
    if kpm is None:
        return None, {"kills_per_min": None}

    # Calibration empirique : ~0.55 kpm ~50 pts.
    score = _saturation_score(kpm, scale=0.8)
    return score, {"kills_per_min": round(kpm, 2)}


def _compute_life_component(df: pl.DataFrame) -> tuple[float | None, dict[str, Any]]:
    life = _mean_numeric(df, "average_life_seconds")
    if life is None:
        return None, {"avg_life_seconds": None}

    # Calibration : ~35s ~50 pts.
    score = _saturation_score(life, scale=50.0)
    return score, {"avg_life_seconds": round(life, 1)}


_OBJECTIVE_COLUMN_WEIGHTS: dict[str, float] = {
    # CTF
    "flag_captures": 3.0,
    "flag_returns": 1.0,
    # Strongholds
    "zones_captured": 2.0,
    "zones_defended": 1.0,
    # Oddball
    "ball_time_seconds": 1.0 / 30.0,
    "time_with_ball_seconds": 1.0 / 30.0,
    # King of the Hill
    "hill_time_seconds": 1.0 / 30.0,
    "time_in_hill_seconds": 1.0 / 30.0,
    # Assault / autres (noms possibles)
    "core_captures": 3.0,
    "objective_carries": 1.0,
}


def _compute_objective_component(df: pl.DataFrame) -> tuple[float | None, dict[str, Any]]:
    used: dict[str, float] = {}
    total_points = 0.0

    for col, w in _OBJECTIVE_COLUMN_WEIGHTS.items():
        if col not in df.columns:
            continue
        values = df.get_column(col).cast(pl.Float64, strict=False).drop_nulls()
        if values.is_empty():
            continue
        mean_val = float(values.mean())
        if mean_val <= 0:
            continue
        used[col] = w
        total_points += mean_val * w

    if not used:
        return None, {
            "objective_score": None,
            "objective_points_per_match": None,
            "objective_columns": [],
        }

    # Calibration : ~2.1 points/match ~50 pts.
    score = _saturation_score(total_points, scale=3.0)
    return (
        score,
        {
            "objective_score": round(score, 1),
            "objective_points_per_match": round(total_points, 2),
            "objective_columns": sorted(used.keys()),
        },
    )


def _compute_mmr_performance_component(df: pl.DataFrame) -> tuple[float | None, dict[str, Any]]:
    """Calcule un score basé sur la performance vs l'écart MMR attendu.

    Utilise une formule style Elo pour calculer le "Expected Win Rate"
    basé sur l'écart MMR entre les équipes, puis compare au vrai Win Rate.

    Si le joueur gagne plus que prévu (surperformance), le score augmente.
    Si le joueur gagne moins que prévu (sous-performance), le score diminue.

    Returns:
        Tuple (score 0-100, métadonnées).
    """
    team_mmr = _mean_numeric(df, "team_mmr")
    enemy_mmr = _mean_numeric(df, "enemy_mmr")

    if team_mmr is None or enemy_mmr is None:
        return None, {
            "expected_win_rate": None,
            "actual_win_rate": None,
            "performance_vs_expected": None,
        }

    # Calculer l'Expected Win Rate (formule Elo-like)
    # 400 est le facteur d'échelle standard (comme aux échecs)
    mmr_diff = team_mmr - enemy_mmr
    expected_win_rate = 1.0 / (1.0 + math.pow(10, -mmr_diff / 400.0))

    # Calculer le vrai Win Rate
    if "outcome" not in df.columns:
        return None, {
            "expected_win_rate": round(expected_win_rate * 100, 1),
            "actual_win_rate": None,
            "performance_vs_expected": None,
        }

    n = len(df)
    if n <= 0:
        return None, {
            "expected_win_rate": round(expected_win_rate * 100, 1),
            "actual_win_rate": None,
            "performance_vs_expected": None,
        }

    wins = _count_wins(df)
    actual_win_rate = wins / n

    # Performance vs Expected : différence normalisée
    performance_diff = actual_win_rate - expected_win_rate

    # Convertir en score 0-100
    score = 50.0 + (performance_diff * 100.0)
    score = _clamp(score, 0.0, 100.0)

    return score, {
        "expected_win_rate": round(expected_win_rate * 100, 1),
        "actual_win_rate": round(actual_win_rate * 100, 1),
        "performance_vs_expected": round(performance_diff * 100, 1),
        "mmr_diff": round(mmr_diff, 1),
    }


def _compute_mmr_aggregates(df: pl.DataFrame) -> dict[str, float | None]:
    team = _mean_numeric(df, "team_mmr")
    enemy = _mean_numeric(df, "enemy_mmr")
    delta = (team - enemy) if (team is not None and enemy is not None) else None

    return {
        "team_mmr_avg": round(team, 1) if team is not None else None,
        "enemy_mmr_avg": round(enemy, 1) if enemy is not None else None,
        "delta_mmr_avg": round(delta, 1) if delta is not None else None,
    }


def _mmr_difficulty_multiplier(delta_mmr_avg: float | None) -> float:
    """Applique un ajustement léger selon la difficulté."""
    if delta_mmr_avg is None:
        return 1.0

    # ~ +/- 300 MMR => +/- 5%
    adj = _clamp((-delta_mmr_avg / 300.0) * 5.0, lo=-5.0, hi=5.0) / 100.0
    return 1.0 + adj


_EMPTY_V1_RESULT: dict[str, Any] = {
    "score": None,
    "kd_ratio": None,
    "kda": None,
    "win_rate": None,
    "accuracy": None,
    "avg_score": None,
    "avg_life_seconds": None,
    "matches": 0,
    "kills": 0,
    "deaths": 0,
    "assists": 0,
    "team_mmr_avg": None,
    "enemy_mmr_avg": None,
    "delta_mmr_avg": None,
}


def compute_session_performance_score_v1(df_session: pl.DataFrame | Any) -> dict[str, Any]:
    """Version historique du score (0-100).

    Cette fonction est gardée pour rétrocompatibilité.

    Args:
        df_session: DataFrame (Polars ou Pandas) des matchs de la session.

    Returns:
        Dict avec le score et les détails.
    """
    # Normaliser en Polars
    df_session = _normalize_df(df_session)

    if df_session is None or df_session.is_empty():
        return dict(_EMPTY_V1_RESULT)

    total_kills = _sum_int(df_session, "kills")
    total_deaths = _sum_int(df_session, "deaths")
    total_assists = _sum_int(df_session, "assists")
    n_matches = len(df_session)

    kd_ratio = total_kills / total_deaths if total_deaths > 0 else float(total_kills)
    kd_score = _clamp(kd_ratio * 50.0)

    kda = (
        (total_kills + total_assists) / total_deaths
        if total_deaths > 0
        else float(total_kills + total_assists)
    )

    wins = _count_wins(df_session) if "outcome" in df_session.columns else 0
    win_rate = wins / n_matches if n_matches > 0 else 0.0
    win_score = win_rate * 100.0

    accuracy = None
    if "accuracy" in df_session.columns:
        accuracy = _mean_numeric(df_session, "accuracy")
    elif "shots_accuracy" in df_session.columns:
        accuracy = _mean_numeric(df_session, "shots_accuracy")
    acc_score = accuracy if accuracy is not None else 50.0

    avg_life_seconds = _mean_numeric(df_session, "average_life_seconds")

    avg_score = _mean_numeric(df_session, "match_score")
    score_pts = _clamp((avg_score or 10.0) * 5.0) if avg_score is not None else 50.0

    mmr = _compute_mmr_aggregates(df_session)

    final_score = (kd_score * 0.30) + (win_score * 0.25) + (acc_score * 0.25) + (score_pts * 0.20)

    return {
        "score": round(final_score, 1),
        "kd_ratio": round(kd_ratio, 2),
        "kda": round(kda, 2),
        "win_rate": round(win_rate * 100.0, 1),
        "accuracy": round(accuracy, 1) if accuracy is not None else None,
        "avg_score": round(avg_score, 1) if avg_score is not None else None,
        "avg_life_seconds": round(avg_life_seconds, 1) if avg_life_seconds is not None else None,
        "matches": n_matches,
        "kills": total_kills,
        "deaths": total_deaths,
        "assists": total_assists,
        **mmr,
    }


def compute_session_performance_score_v2(
    df_session: pl.DataFrame | Any,
    *,
    include_mmr_adjustment: bool = True,
) -> dict[str, Any]:
    """Calcule un score de performance (0–100) plus robuste et modulaire.

    Principes :
    - On n'utilise que les composantes disponibles.
    - On renormalise les poids si une composante manque.
    - On peut ajouter une composante "objectif" quand des colonnes existent.

    Args:
        df_session: DataFrame (Polars ou Pandas) des matchs de la session.
        include_mmr_adjustment: Inclure l'ajustement MMR.

    Returns:
        Dict compatible avec la v1, + champs v2:
        - components: scores par composante (0-100)
        - weights_used: pondérations réellement utilisées
        - confidence: (0-1) indicateur simple basé sur le nombre de matchs
    """
    # Normaliser en Polars
    df_session = _normalize_df(df_session)

    if df_session is None or df_session.is_empty():
        base = compute_session_performance_score_v1(df_session)
        base.update(
            {
                "components": {},
                "weights_used": {},
                "confidence": 0.0,
                "confidence_label": "faible",
                "objective_score": None,
                "objective_points_per_match": None,
                "objective_columns": [],
                "version": "v2",
            }
        )
        return base

    total_kills = _sum_int(df_session, "kills")
    total_deaths = _sum_int(df_session, "deaths")
    total_assists = _sum_int(df_session, "assists")
    n_matches = len(df_session)

    kd_ratio = (total_kills / total_deaths) if total_deaths > 0 else float(total_kills)
    kda = (
        (total_kills + total_assists) / total_deaths
        if total_deaths > 0
        else float(total_kills + total_assists)
    )

    avg_life_seconds = _mean_numeric(df_session, "average_life_seconds")
    accuracy = _mean_numeric(df_session, "accuracy")
    if accuracy is None:
        accuracy = _mean_numeric(df_session, "shots_accuracy")

    mmr = _compute_mmr_aggregates(df_session)

    components: list[ScoreComponent] = [
        ScoreComponent(key="kd", label="K/D", weight=0.20, compute=_compute_kd_component),
        ScoreComponent(key="win", label="Victoires", weight=0.15, compute=_compute_win_component),
        ScoreComponent(
            key="acc", label="Précision", weight=0.15, compute=_compute_accuracy_component
        ),
        ScoreComponent(key="kpm", label="Kills/min", weight=0.15, compute=_compute_kpm_component),
        ScoreComponent(key="life", label="Survie", weight=0.10, compute=_compute_life_component),
        ScoreComponent(
            key="obj", label="Objectif", weight=0.10, compute=_compute_objective_component
        ),
        ScoreComponent(
            key="mmr_perf",
            label="MMR Performance",
            weight=0.15,
            compute=_compute_mmr_performance_component,
        ),
    ]

    computed_scores: dict[str, float] = {}
    component_meta: dict[str, Any] = {}
    weights_used: dict[str, float] = {}

    for comp in components:
        score, meta = comp.compute(df_session)
        component_meta[comp.key] = meta
        if score is None:
            continue
        computed_scores[comp.key] = float(score)
        weights_used[comp.key] = float(comp.weight)

    total_weight = sum(weights_used.values())
    if total_weight <= 0:
        final_score = None
    else:
        final_score = 0.0
        for key, w in weights_used.items():
            final_score += computed_scores[key] * (w / total_weight)

        if include_mmr_adjustment:
            final_score *= _mmr_difficulty_multiplier(mmr.get("delta_mmr_avg"))

        final_score = _clamp(final_score)

    # Confiance : simple, basé sur la taille d'échantillon.
    confidence = _clamp((n_matches / 10.0) * 100.0, lo=0.0, hi=100.0) / 100.0
    confidence_label = "faible" if n_matches < 4 else ("moyenne" if n_matches < 10 else "élevée")

    obj_meta = component_meta.get("obj", {})

    return {
        "score": round(final_score, 1) if final_score is not None else None,
        "kd_ratio": round(kd_ratio, 2),
        "kda": round(kda, 2),
        "win_rate": component_meta.get("win", {}).get("win_rate"),
        "accuracy": round(accuracy, 1) if accuracy is not None else None,
        "avg_score": None,
        "avg_life_seconds": round(avg_life_seconds, 1) if avg_life_seconds is not None else None,
        "matches": n_matches,
        "kills": total_kills,
        "deaths": total_deaths,
        "assists": total_assists,
        **mmr,
        "objective_score": obj_meta.get("objective_score"),
        "objective_points_per_match": obj_meta.get("objective_points_per_match"),
        "objective_columns": obj_meta.get("objective_columns", []),
        "components": {k: round(v, 1) for k, v in computed_scores.items()},
        "weights_used": weights_used,
        "confidence": round(confidence, 2),
        "confidence_label": confidence_label,
        "version": "v2",
    }
