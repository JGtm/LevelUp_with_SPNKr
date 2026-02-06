"""Gestion des sessions de jeu.

Ce module fournit deux modes de calcul de session :
1. compute_sessions() : Calcul à la volée (legacy, basé uniquement sur le gap temporel)
2. compute_sessions_with_context() : Calcul avancé (gap + coéquipiers + heure de coupure)

Pour la plupart des usages, préférer les données pré-calculées depuis MatchCache
(via load_sessions_cached ou le DataFrame enrichi).
"""

from __future__ import annotations

from datetime import datetime, time, timezone

import pandas as pd
import polars as pl

from src.config import SESSION_CONFIG

# =============================================================================
# Configuration des sessions améliorées
# =============================================================================

# Gap de session en minutes (2h)
DEFAULT_SESSION_GAP_MINUTES = 120

# Heure de coupure pour les sessions "en cours" (8h du matin)
SESSION_CUTOFF_HOUR = 8


def compute_sessions(
    df: pd.DataFrame | pl.DataFrame, gap_minutes: int | None = None
) -> pd.DataFrame | pl.DataFrame:
    """Regroupe les parties consécutives en sessions (mode legacy).

    ATTENTION: Cette fonction ne prend PAS en compte les coéquipiers.
    Pour des sessions plus précises, utiliser les données pré-calculées
    dans MatchCache (colonnes session_id, session_label).

    Une nouvelle session commence quand l'écart entre deux parties
    dépasse le seuil défini.

    Args:
        df: DataFrame (Pandas ou Polars) avec colonne start_time.
        gap_minutes: Écart maximum entre parties (default: SESSION_CONFIG.default_gap_minutes).

    Returns:
        DataFrame avec colonnes session_id et session_label ajoutées (même type que l'entrée).
    """
    if gap_minutes is None:
        gap_minutes = SESSION_CONFIG.default_gap_minutes

    # Détecter le type de DataFrame
    is_polars = isinstance(df, pl.DataFrame)

    if is_polars:
        return _compute_sessions_polars(df, gap_minutes)
    else:
        return _compute_sessions_pandas(df, gap_minutes)


def _compute_sessions_polars(df: pl.DataFrame, gap_minutes: int) -> pl.DataFrame:
    """Version Polars de compute_sessions()."""
    if df.is_empty():
        return df.with_columns(
            [
                pl.lit(None).cast(pl.Int64).alias("session_id"),
                pl.lit(None).cast(pl.Utf8).alias("session_label"),
            ]
        )

    df_sorted = df.sort("start_time")

    # Calculer les gaps entre matchs
    gaps = df_sorted["start_time"].diff().dt.total_seconds().fill_null(0)

    # Nouvelle session si gap > gap_minutes
    new_session = (gaps > (gap_minutes * 60)).cast(pl.Int64)
    session_id = new_session.cum_sum().cast(pl.Int64)

    df_with_sessions = df_sorted.with_columns([session_id.alias("session_id")])

    # Générer les labels de session
    session_stats = df_with_sessions.group_by("session_id").agg(
        [
            pl.col("start_time").min().alias("min_time"),
            pl.col("start_time").max().alias("max_time"),
            pl.count().alias("count"),
        ]
    )

    # Créer les labels
    labels = session_stats.with_columns(
        [
            pl.format(
                "{} {}–{} ({})",
                pl.col("min_time").dt.strftime("%d/%m/%Y"),
                pl.col("min_time").dt.strftime("%H:%M"),
                pl.col("max_time").dt.strftime("%H:%M"),
                pl.col("count").cast(pl.Utf8),
            ).alias("session_label")
        ]
    ).select(["session_id", "session_label"])

    # Joindre les labels
    result = df_with_sessions.join(labels, on="session_id", how="left")

    return result


def _compute_sessions_pandas(df: pd.DataFrame, gap_minutes: int) -> pd.DataFrame:
    """Version Pandas de compute_sessions() (legacy, à supprimer progressivement)."""
    if df.empty:
        d = df.copy()
        d["session_id"] = pd.Series(dtype=int)
        d["session_label"] = pd.Series(dtype=str)
        return d

    d = df.sort_values("start_time").copy()
    gaps = d["start_time"].diff().dt.total_seconds().fillna(0)
    new_session = (gaps > (gap_minutes * 60)).astype(int)
    d["session_id"] = new_session.cumsum().astype(int)

    # Génère les labels de session
    g = d.groupby("session_id")["start_time"].agg(["min", "max", "count"])
    labels = {}
    for sid, row in g.iterrows():
        start = row["min"]
        end = row["max"]
        cnt = int(row["count"])
        labels[sid] = f"{start:%d/%m/%Y} {start:%H:%M}–{end:%H:%M} ({cnt})"
    d["session_label"] = d["session_id"].map(labels)

    return d


def compute_sessions_with_context(
    df: pd.DataFrame,
    gap_minutes: int = DEFAULT_SESSION_GAP_MINUTES,
    cutoff_hour: int = SESSION_CUTOFF_HOUR,
    teammates_column: str | None = "teammates_signature",
) -> pd.DataFrame:
    """Regroupe les parties en sessions avec logique avancée.

    ⚠️ DÉPRÉCIÉ : Utiliser compute_sessions_with_context_polars() avec un DataFrame Polars.
    Cette fonction sera supprimée dans une future version.

    Règles :
    1. Un gap > gap_minutes entre deux matchs = nouvelle session
    2. Un changement de coéquipiers = nouvelle session (si teammates_column existe)
    3. Les matchs avant cutoff_hour sont regroupés avec la veille

    Args:
        df: DataFrame avec colonnes start_time et optionnellement teammates_signature.
        gap_minutes: Gap maximum entre matchs d'une même session.
        cutoff_hour: Heure de coupure (avant = session potentiellement de la veille).
        teammates_column: Nom de la colonne contenant la signature des coéquipiers.

    Returns:
        DataFrame avec colonnes session_id et session_label ajoutées.
    """
    if df.empty:
        d = df.copy()
        d["session_id"] = pd.Series(dtype=int)
        d["session_label"] = pd.Series(dtype=str)
        return d

    d = df.sort_values("start_time").copy()

    # Calcul des conditions de nouvelle session
    gaps = d["start_time"].diff().dt.total_seconds().fillna(0)
    gap_break = (gaps > (gap_minutes * 60)).astype(int)

    # Changement de coéquipiers ?
    # NaN/NULL traite comme valeur distincte (evite fusionner A, NULL, B en une session)
    if teammates_column and teammates_column in d.columns:
        col = d[teammates_column].fillna("__NULL__")
        prev = col.shift(1).fillna("__SENTINEL_FIRST__")
        teammates_break = (col != prev).astype(int)
        teammates_break.iloc[0] = (
            0  # Premier match : pas de rupture (sera new_session via iloc[0]=1)
        )
    else:
        teammates_break = pd.Series(0, index=d.index)

    # Nouvelle session si gap OU changement de coéquipiers
    new_session = ((gap_break == 1) | (teammates_break == 1)).astype(int)
    new_session.iloc[0] = 1  # Premier match = première session

    d["session_id"] = new_session.cumsum().astype(int) - 1  # Commence à 0

    # Génère les labels de session
    g = d.groupby("session_id")["start_time"].agg(["min", "max", "count"])
    labels = {}
    for sid, row in g.iterrows():
        start = row["min"]
        end = row["max"]
        cnt = int(row["count"])
        labels[sid] = f"{start:%d/%m/%y %H:%M}–{end:%H:%M} ({cnt})"
    d["session_label"] = d["session_id"].map(labels)

    return d


def is_session_potentially_active(
    last_match_time: datetime,
    cutoff_hour: int = SESSION_CUTOFF_HOUR,
) -> bool:
    """Détermine si une session est potentiellement encore en cours.

    Une session est considérée "potentiellement active" si :
    - Le dernier match est aujourd'hui après cutoff_hour
    - Ou le dernier match est hier après cutoff_hour et on est avant cutoff_hour aujourd'hui

    Args:
        last_match_time: Datetime du dernier match de la session.
        cutoff_hour: Heure de coupure.

    Returns:
        True si la session pourrait encore être en cours.
    """
    now = datetime.now(timezone.utc)

    # Convertir en aware datetime si nécessaire
    if last_match_time.tzinfo is None:
        last_match_time = last_match_time.replace(tzinfo=timezone.utc)

    # Si le dernier match est aujourd'hui
    if last_match_time.date() == now.date():
        return True

    # Si le dernier match est hier et on est avant l'heure de coupure
    yesterday = (now - pd.Timedelta(days=1)).date()
    today_cutoff = datetime.combine(now.date(), time(cutoff_hour, 0), tzinfo=timezone.utc)

    if last_match_time.date() == yesterday and now < today_cutoff:
        return True

    return False


def compute_sessions_with_context_polars(
    df: pl.DataFrame,
    gap_minutes: int = DEFAULT_SESSION_GAP_MINUTES,
    cutoff_hour: int = SESSION_CUTOFF_HOUR,
    teammates_column: str | None = "teammates_signature",
) -> pl.DataFrame:
    """Version Polars de compute_sessions_with_context.

    Règles :
    1. Gap > gap_minutes = nouvelle session
    2. Changement de teammates_signature = nouvelle session
    3. Heure de coupure pour sessions "en cours"

    Args:
        df: DataFrame Polars avec colonnes start_time et optionnellement teammates_signature.
        gap_minutes: Gap maximum entre matchs.
        cutoff_hour: Heure de coupure.
        teammates_column: Nom de la colonne teammates_signature.

    Returns:
        DataFrame avec colonnes session_id et session_label ajoutées.
    """
    if df.is_empty():
        return df.with_columns(
            [
                pl.lit(None).cast(pl.Int64).alias("session_id"),
                pl.lit(None).cast(pl.Utf8).alias("session_label"),
            ]
        )

    # Trier par start_time
    df_sorted = df.sort("start_time")

    # Calculer les gaps (en secondes)
    gaps = df_sorted["start_time"].diff().dt.total_seconds().fill_null(0)
    gap_break = (gaps > (gap_minutes * 60)).cast(pl.Int8)

    # Changement de coéquipiers ?
    # NULL est traité comme valeur distincte (evite de fusionner A, NULL, B en une session)
    if teammates_column and teammates_column in df_sorted.columns:
        col = df_sorted[teammates_column]
        prev = col.shift(1)
        col_fill = col.fill_null("__NULL__")
        # Seul le premier row (prev=null car pas de precedent) utilise la sentinelle
        row_idx = pl.int_range(0, pl.len())
        prev_fill = (
            pl.when(row_idx == 0)
            .then(pl.lit("__SENTINEL_FIRST__"))
            .otherwise(prev.fill_null("__NULL__"))
        )
        teammates_break = (col_fill != prev_fill).cast(pl.Int8)
    else:
        teammates_break = pl.lit(0).cast(pl.Int8)

    # Nouvelle session si gap OU changement de coéquipiers
    new_session_raw = ((gap_break == 1) | (teammates_break == 1)).cast(pl.Int8)
    new_session_raw = new_session_raw.fill_null(1)
    # Forcer le premier match = premiere session (comportement Pandas)
    row_idx = pl.int_range(0, pl.len())
    new_session = pl.when(row_idx == 0).then(1).otherwise(new_session_raw)

    # Calculer session_id (cum_sum en Polars)
    session_id = new_session.cum_sum() - 1

    # Générer les labels
    df_with_session = df_sorted.with_columns(session_id.alias("session_id"))

    session_labels = (
        df_with_session.group_by("session_id")
        .agg(
            [
                pl.col("start_time").min().alias("start"),
                pl.col("start_time").max().alias("end"),
                pl.len().alias("count"),
            ]
        )
        .with_columns(
            pl.format(
                "{} {}–{} ({})",
                pl.col("start").dt.strftime("%d/%m/%Y"),
                pl.col("start").dt.strftime("%H:%M"),
                pl.col("end").dt.strftime("%H:%M"),
                pl.col("count"),
            ).alias("session_label")
        )
        .select(["session_id", "session_label"])
    )

    # Joindre les labels
    df_result = df_with_session.join(
        session_labels,
        on="session_id",
        how="left",
    )

    return df_result


def get_bucket_label(days: float) -> tuple[str, str]:
    """Détermine le type de bucket temporel selon la plage de dates.

    Args:
        days: Nombre de jours dans la plage.

    Returns:
        Tuple (bucket_type, bucket_label) où bucket_type est utilisé
        pour le groupement pandas et bucket_label pour l'affichage.
    """
    cfg = SESSION_CONFIG

    if days < cfg.bucket_threshold_hourly:
        return "match", "partie"
    elif days <= cfg.bucket_threshold_daily:
        return "hour", "heure"
    elif days <= cfg.bucket_threshold_weekly:
        return "day", "jour"
    elif days <= cfg.bucket_threshold_monthly:
        return "week", "semaine"
    else:
        return "month", "mois"
