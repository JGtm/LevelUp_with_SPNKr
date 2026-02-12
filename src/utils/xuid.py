"""Utilitaires pour la manipulation des XUIDs Xbox.

Ce module fournit des fonctions pour parser, extraire et valider
les identifiants Xbox (XUID) utilisés dans l'API Halo Infinite.
"""

from __future__ import annotations

import os
import re
from typing import Any

__all__ = [
    "parse_xuid_input",
    "extract_xuid_from_player_id",
    "extract_gamertag_from_player_id",
    "resolve_xuid_from_db",
    "infer_spnkr_player_from_db_path",
    "guess_xuid_from_db_path",
    "XUID_DIGITS_RE",
]

# Regex pour extraire un XUID (12-20 chiffres)
XUID_DIGITS_RE = re.compile(r"(\d{12,20})")


def parse_xuid_input(s: str | None) -> str | None:
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


def extract_xuid_from_player_id(player_id: Any) -> str | None:
    """Extrait le XUID d'un objet PlayerId de l'API Halo.

    Args:
        player_id: Objet PlayerId (dict, str, ou int).

    Returns:
        Le XUID extrait, ou None si non trouvé.
    """
    if player_id is None:
        return None
    if isinstance(player_id, dict):
        for k in ("Xuid", "xuid", "XUID"):
            if k in player_id:
                v = player_id.get(k)
                if isinstance(v, int | str):
                    parsed = parse_xuid_input(str(v))
                    if parsed:
                        return parsed
                    m = XUID_DIGITS_RE.search(str(v))
                    if m:
                        return m.group(1)
        return None
    if isinstance(player_id, int | str):
        s = str(player_id)
        parsed = parse_xuid_input(s)
        if parsed:
            return parsed
        m = XUID_DIGITS_RE.search(s)
        if m:
            return m.group(1)
    return None


def extract_gamertag_from_player_id(player_id: Any) -> str | None:
    """Extrait le gamertag d'un objet PlayerId de l'API Halo.

    Args:
        player_id: Objet PlayerId (dict avec clé Gamertag).

    Returns:
        Le gamertag, ou None si non trouvé.
    """
    if player_id is None:
        return None
    if isinstance(player_id, dict):
        for k in ("Gamertag", "gamertag", "GT"):
            v = player_id.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None
    return None


def resolve_xuid_from_db(
    db_path: str,
    player: str,
    *,
    default_gamertag: str | None = None,
    default_xuid: str | None = None,
    aliases: dict[str, str] | None = None,
) -> str | None:
    """Résout un XUID à partir d'une entrée utilisateur.

    - Si `player` est déjà un XUID (ou xuid(...)), renvoie le XUID.
    - Sinon, tente de retrouver le XUID depuis les alias ou la DB.
    - Fallback sur les variables d'environnement OPENSPARTAN_DEFAULT_*.

    Args:
        db_path: Chemin vers la base de données.
        player: Gamertag ou XUID à résoudre.
        default_gamertag: Gamertag par défaut (optionnel).
        default_xuid: XUID par défaut (optionnel).
        aliases: Dictionnaire d'alias XUID → gamertag (optionnel).

    Returns:
        Le XUID résolu, ou None si non trouvé.
    """
    p = (player or "").strip()
    if not p:
        return None

    # 1. Déjà un XUID ?
    parsed = parse_xuid_input(p)
    if parsed:
        return parsed

    # 2. Fallback valeurs par défaut passées en argument
    if default_gamertag and p.casefold() == default_gamertag.casefold():
        return default_xuid or None

    # 3. Fallback variables d'environnement
    env_gt = os.environ.get("OPENSPARTAN_DEFAULT_GAMERTAG", "").strip()
    env_xu = os.environ.get("OPENSPARTAN_DEFAULT_XUID", "").strip()
    if env_gt and env_xu and p.casefold() == env_gt.casefold():
        return env_xu

    # 4. Fallback aliases
    if aliases:
        for xuid, gt in aliases.items():
            if gt and gt.casefold() == p.casefold() and xuid.strip().isdigit():
                return xuid.strip()

    # 5. Rechercher dans la DB
    if not db_path or not os.path.exists(db_path):
        return None

    # DuckDB v4 : utiliser la table xuid_aliases
    if db_path.endswith(".duckdb"):
        try:
            import duckdb

            conn = duckdb.connect(db_path, read_only=True)
            result = conn.execute(
                "SELECT xuid FROM xuid_aliases WHERE LOWER(gamertag) = LOWER(?)",
                [p],
            ).fetchone()
            conn.close()
            if result and result[0]:
                return str(result[0])
        except Exception:
            pass

    return None


def infer_spnkr_player_from_db_path(db_path: str) -> str | None:
    """Déduit le paramètre --player à utiliser pour une DB SPNKr.

    Conventions supportées:
    - spnkr_gt_<Gamertag>.db  -> <Gamertag>
    - spnkr_xuid_<XUID>.db   -> <XUID>
    - spnkr_<something>.db   -> <something>

    Args:
        db_path: Chemin vers la DB SPNKr.

    Returns:
        Le paramètre player déduit, ou None.
    """
    base = os.path.basename(db_path or "")
    stem, _ = os.path.splitext(base)
    s = (stem or "").strip()
    if not s:
        return None
    low = s.lower()
    if low.startswith("spnkr_gt_"):
        out = s[len("spnkr_gt_") :]
    elif low.startswith("spnkr_xuid_"):
        out = s[len("spnkr_xuid_") :]
    elif low.startswith("spnkr_"):
        out = s[len("spnkr_") :]
    else:
        return None
    out = (out or "").strip().strip("_- ")
    return out or None


def guess_xuid_from_db_path(
    db_path: str,
    aliases: dict[str, str] | None = None,
) -> str | None:
    """Devine le XUID à partir du nom du fichier .db.

    La convention OpenSpartan Workshop nomme les fichiers <XUID>.db.
    Supporte aussi des noms comme spnkr_gt_<Gamertag>.db.

    Args:
        db_path: Chemin vers le fichier .db.
        aliases: Dictionnaire gamertag → xuid (optionnel).

    Returns:
        Le XUID si trouvé, None sinon.
    """
    base = os.path.basename(db_path or "")
    stem, _ = os.path.splitext(base)
    if stem.isdigit():
        return stem

    # Ex: spnkr_xuid_2533....db / name_2533....db
    m = XUID_DIGITS_RE.search(stem)
    if m:
        return m.group(1)

    # Ex: spnkr_gt_Chocoboflor.db -> Chocoboflor
    gt_guess = stem
    if gt_guess.lower().startswith("spnkr_gt_"):
        gt_guess = gt_guess[len("spnkr_gt_") :]
    elif gt_guess.lower().startswith("spnkr_gt-"):
        gt_guess = gt_guess[len("spnkr_gt-") :]
    elif gt_guess.lower().startswith("spnkr_"):
        gt_guess = gt_guess[len("spnkr_") :]

    gt_guess = (gt_guess or "").strip().strip("_-")
    if not gt_guess:
        return None

    # Variants avec espaces
    gt_candidates = {gt_guess, gt_guess.replace("_", " "), gt_guess.replace("_", "")}
    gt_candidates = {c.strip() for c in gt_candidates if c and c.strip()}
    if not gt_candidates:
        return None

    # Résolution via aliases
    if aliases:
        # Inversion gamertag → xuid
        gt_to_xuid = {gt.casefold(): x for x, gt in aliases.items() if gt}
        for candidate in gt_candidates:
            if candidate.casefold() in gt_to_xuid:
                return gt_to_xuid[candidate.casefold()]

    return None
