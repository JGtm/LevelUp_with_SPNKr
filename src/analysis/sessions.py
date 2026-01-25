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

from src.config import SESSION_CONFIG


# =============================================================================
# Configuration des sessions améliorées
# =============================================================================

# Gap de session en minutes (2h)
DEFAULT_SESSION_GAP_MINUTES = 120

# Heure de coupure pour les sessions "en cours" (8h du matin)
SESSION_CUTOFF_HOUR = 8


def compute_sessions(df: pd.DataFrame, gap_minutes: int | None = None) -> pd.DataFrame:
    """Regroupe les parties consécutives en sessions (mode legacy).
    
    ATTENTION: Cette fonction ne prend PAS en compte les coéquipiers.
    Pour des sessions plus précises, utiliser les données pré-calculées
    dans MatchCache (colonnes session_id, session_label).
    
    Une nouvelle session commence quand l'écart entre deux parties
    dépasse le seuil défini.
    
    Args:
        df: DataFrame avec colonne start_time.
        gap_minutes: Écart maximum entre parties (default: SESSION_CONFIG.default_gap_minutes).
        
    Returns:
        DataFrame avec colonnes session_id et session_label ajoutées.
    """
    if gap_minutes is None:
        gap_minutes = SESSION_CONFIG.default_gap_minutes
        
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
    if teammates_column and teammates_column in d.columns:
        teammates_break = (d[teammates_column] != d[teammates_column].shift(1)).astype(int)
        teammates_break.iloc[0] = 0  # Premier match : pas de rupture
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
