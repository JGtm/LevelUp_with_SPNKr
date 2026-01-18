"""Fonctions de parsing et utilitaires pour la DB."""

import os
import re
from datetime import datetime, timezone
from typing import Any, Optional


def guess_xuid_from_db_path(db_path: str) -> Optional[str]:
    """Devine le XUID à partir du nom du fichier .db.
    
    La convention OpenSpartan Workshop nomme les fichiers <XUID>.db.
    
    Args:
        db_path: Chemin vers le fichier .db.
        
    Returns:
        Le XUID si le nom de fichier est numérique, None sinon.
    """
    base = os.path.basename(db_path)
    stem, _ = os.path.splitext(base)
    return stem if stem.isdigit() else None


def parse_iso_utc(s: str) -> datetime:
    """Parse une date ISO 8601 en datetime UTC.
    
    Gère le format utilisé par l'API Halo: 2026-01-02T20:18:01.293Z
    
    Args:
        s: Chaîne de date au format ISO 8601.
        
    Returns:
        datetime en timezone UTC.
    """
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def coerce_number(v: Any) -> Optional[float]:
    """Convertit une valeur en float de manière robuste.
    
    Gère différents formats vus dans l'API Halo:
    - Nombres directs (int, float)
    - Chaînes numériques
    - Dictionnaires avec clés Count, Value, Seconds, etc.
    
    Args:
        v: Valeur à convertir.
        
    Returns:
        La valeur en float, ou None si la conversion échoue.
    """
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except Exception:
            return None
    if isinstance(v, dict):
        # Formats vus dans certaines APIs: {"Count": 19} ou {"Value": 19}
        for k in ("Count", "Value", "value", "Seconds", "Milliseconds", "Ms"):
            if k in v:
                return coerce_number(v.get(k))
    return None


# Regex pour les durées ISO 8601 (ex: PT31.5S)
_ISO8601_DURATION_RE = re.compile(
    r"^PT(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+(?:\.\d+)?)S)?$"
)


def coerce_duration_seconds(v: Any) -> Optional[float]:
    """Convertit une durée en secondes.
    
    Gère différents formats:
    - Nombres directs (déjà en secondes)
    - Chaînes ISO 8601 (ex: "PT31.5S")
    - Dictionnaires avec Seconds ou Milliseconds
    
    Args:
        v: Valeur de durée à convertir.
        
    Returns:
        La durée en secondes, ou None si la conversion échoue.
    """
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        if "Milliseconds" in v or "Ms" in v:
            ms = coerce_number(v.get("Milliseconds") if "Milliseconds" in v else v.get("Ms"))
            return (ms / 1000.0) if ms is not None else None
        if "Seconds" in v:
            return coerce_number(v.get("Seconds"))
        return coerce_number(v)
    if isinstance(v, str):
        s = v.strip()
        m = _ISO8601_DURATION_RE.match(s)
        if not m:
            return None
        hours = float(m.group("h") or 0)
        minutes = float(m.group("m") or 0)
        seconds = float(m.group("s") or 0)
        return (hours * 3600.0) + (minutes * 60.0) + seconds
    return None


def parse_xuid_input(s: str) -> Optional[str]:
    """Parse une entrée utilisateur de XUID.
    
    Accepte:
    - Un nombre direct: "2533274823110022"
    - Le format xuid(): "xuid(2533274823110022)"
    
    Args:
        s: Entrée utilisateur.
        
    Returns:
        Le XUID extrait, ou None si invalide.
    """
    s = (s or "").strip()
    if not s:
        return None
    if s.isdigit():
        return s
    m = re.fullmatch(r"xuid\((\d+)\)", s)
    if m:
        return m.group(1)
    return None
