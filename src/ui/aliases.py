"""Gestion des alias XUID -> Gamertag.

Ce module gère les alias XUID->Gamertag depuis plusieurs sources :
- Table XuidAliases dans les DBs legacy SQLite
- Fichier xuid_aliases.json
- Constantes par défaut

NOTE: Dans l'architecture v4 (DuckDB), les alias peuvent être stockés
dans metadata.duckdb ou dans le fichier JSON.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

from src.config import XUID_ALIASES_DEFAULT, get_aliases_file_path
from src.utils import parse_xuid_input


def _is_duckdb_file(db_path: str) -> bool:
    """Détecte si le fichier est une base DuckDB."""
    return db_path.endswith(".duckdb")


def _safe_mtime(path: str) -> float | None:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def load_aliases_from_db(db_path: str) -> dict[str, str]:
    """Charge les alias depuis une DB DuckDB.

    Lit la table xuid_aliases si elle existe.

    Args:
        db_path: Chemin vers la DB (doit être .duckdb).

    Returns:
        Dictionnaire {xuid: gamertag}.
    """
    if not db_path or not os.path.exists(db_path):
        return {}

    # SQLite refusé
    if not _is_duckdb_file(db_path):
        return {}

    mtime = _safe_mtime(db_path)
    return dict(_load_aliases_from_duckdb_cached(db_path, mtime))


@lru_cache(maxsize=16)
def _load_aliases_from_duckdb_cached(db_path: str, mtime: float | None) -> dict[str, str]:
    """Version cachée pour DuckDB."""
    try:
        import duckdb

        con = duckdb.connect(db_path, read_only=True)
        # Vérifie si la table existe
        tables = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'xuid_aliases'"
        ).fetchall()
        if not tables:
            con.close()
            return {}

        result_rows = con.execute(
            "SELECT xuid, gamertag FROM xuid_aliases WHERE gamertag IS NOT NULL AND gamertag != ''"
        ).fetchall()
        result = {str(row[0]).strip(): str(row[1]).strip() for row in result_rows}
        con.close()
        return result
    except Exception:
        return {}


def clear_db_aliases_cache() -> None:
    """Invalide le cache des aliases DB (DuckDB uniquement)."""
    _load_aliases_from_duckdb_cached.cache_clear()


def load_aliases_file(path: str | None = None) -> dict[str, str]:
    """Charge les alias depuis un fichier JSON.

    Args:
        path: Chemin du fichier (default: xuid_aliases.json à la racine).

    Returns:
        Dictionnaire {xuid: gamertag}.
    """
    if path is None:
        path = get_aliases_file_path()

    return dict(_load_aliases_cached(path, _safe_mtime(path)))


@lru_cache(maxsize=16)
def _load_aliases_cached(path: str, mtime: float | None) -> dict[str, str]:
    try:
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return {}
        cleaned: dict[str, str] = {}
        for k, v in raw.items():
            kk = str(k).strip()
            vv = str(v).strip()
            if kk and vv:
                cleaned[kk] = vv
        return cleaned
    except Exception:
        return {}


def save_aliases_file(aliases: dict[str, str], path: str | None = None) -> None:
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

    # Invalide le cache (le contenu a changé)
    _load_aliases_cached.cache_clear()


def get_xuid_aliases(db_path: str | None = None) -> dict[str, str]:
    """Retourne les alias fusionnés (DB > fichier > défaut).

    L'ordre de priorité est:
    1. Table XuidAliases de la DB (si db_path fourni et table existe)
    2. Fichier xuid_aliases.json
    3. Constantes XUID_ALIASES_DEFAULT

    Args:
        db_path: Chemin optionnel vers une DB SQLite avec table XuidAliases.

    Returns:
        Dictionnaire {xuid: gamertag}.
    """
    merged = dict(XUID_ALIASES_DEFAULT)
    merged.update(load_aliases_file())

    # Les aliases de la DB ont la priorité (plus récents)
    if db_path:
        merged.update(load_aliases_from_db(db_path))

    return merged


def display_name_from_xuid(xuid: str, db_path: str | None = None) -> str:
    """Convertit un XUID en nom d'affichage.

    Args:
        xuid: XUID du joueur.
        db_path: Chemin optionnel vers une DB SQLite avec table XuidAliases.

    Returns:
        Gamertag si un alias existe, sinon le XUID tel quel.
    """
    raw = str(xuid or "").strip()
    # SPNKr/OpenSpartan stockent souvent l'identifiant sous forme "xuid(2533...)".
    # Normaliser ici permet aux alias (clés = XUID numérique) de fonctionner partout.
    normalized = parse_xuid_input(raw) or raw
    return get_xuid_aliases(db_path=db_path).get(normalized, normalized)
