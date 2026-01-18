"""Gestion des sessions de jeu."""

import pandas as pd

from src.config import SESSION_CONFIG


def compute_sessions(df: pd.DataFrame, gap_minutes: int | None = None) -> pd.DataFrame:
    """Regroupe les parties consécutives en sessions.
    
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
