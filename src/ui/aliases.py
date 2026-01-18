"""Gestion des alias XUID -> Gamertag."""

import json
import os
from typing import Dict

from src.config import XUID_ALIASES_DEFAULT, get_aliases_file_path


def load_aliases_file(path: str | None = None) -> Dict[str, str]:
    """Charge les alias depuis un fichier JSON.
    
    Args:
        path: Chemin du fichier (default: xuid_aliases.json à la racine).
        
    Returns:
        Dictionnaire {xuid: gamertag}.
    """
    if path is None:
        path = get_aliases_file_path()
        
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return {}
        cleaned: Dict[str, str] = {}
        for k, v in raw.items():
            kk = str(k).strip()
            vv = str(v).strip()
            if kk and vv:
                cleaned[kk] = vv
        return cleaned
    except Exception:
        return {}


def save_aliases_file(aliases: Dict[str, str], path: str | None = None) -> None:
    """Sauvegarde les alias dans un fichier JSON.
    
    Args:
        aliases: Dictionnaire {xuid: gamertag}.
        path: Chemin du fichier (default: xuid_aliases.json à la racine).
    """
    if path is None:
        path = get_aliases_file_path()
        
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(aliases.items())), f, ensure_ascii=False, indent=2)


def get_xuid_aliases() -> Dict[str, str]:
    """Retourne les alias fusionnés (par défaut + fichier).
    
    Returns:
        Dictionnaire {xuid: gamertag}.
    """
    merged = dict(XUID_ALIASES_DEFAULT)
    merged.update(load_aliases_file())
    return merged


def display_name_from_xuid(xuid: str) -> str:
    """Convertit un XUID en nom d'affichage.
    
    Args:
        xuid: XUID du joueur.
        
    Returns:
        Gamertag si un alias existe, sinon le XUID tel quel.
    """
    xuid = (xuid or "").strip()
    return get_xuid_aliases().get(xuid, xuid)
