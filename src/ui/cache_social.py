"""Fonctions de cache Streamlit — Aspects sociaux (friends, teammates, sessions).

Ce module regroupe les fonctions @st.cache_data pour les données sociales :
- Chargement des amis
- Top coéquipiers optimisé
- Informations de session

Extrait de cache_loaders.py lors du Sprint 17 (réduction <800L).
"""

from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def _is_duckdb_v4_path(db_path: str) -> bool:
    """Détecte si le chemin est une DB joueur DuckDB v4."""
    if not db_path:
        return False
    return db_path.endswith(".duckdb") or db_path.endswith("stats.duckdb")


@st.cache_data(show_spinner=False)
def cached_load_friends(
    db_path: str,
    owner_xuid: str,
    db_key: tuple[int, int] | None = None,
) -> list[dict]:
    """Charge la liste des amis depuis la table Friends.

    DuckDB v4 n'a pas de table Friends, retourne liste vide.
    """
    _ = db_key
    # DuckDB v4 : pas de table Friends
    if _is_duckdb_v4_path(db_path):
        return []
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return []


@st.cache_data(show_spinner=False)
def cached_load_top_teammates_optimized(
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None = None,
    limit: int = 20,
) -> list[tuple[str, str | None, int, int, int]]:
    """Charge les top coéquipiers depuis TeammatesAggregate (optimisé).

    Returns:
        Liste de tuples (xuid, gamertag, matches, wins, losses)
    """
    _ = db_key

    # DuckDB v4 : utiliser le repository
    if _is_duckdb_v4_path(db_path):
        try:
            from src.data.repositories.duckdb_repo import DuckDBRepository

            repo = DuckDBRepository(db_path, str(xuid).strip())
            teammates = repo.list_top_teammates(limit=limit)
            # Convertir (xuid, count) → (xuid, None, count, 0, 0)
            return [(str(x), None, int(c), 0, 0) for x, c in teammates]
        except Exception:
            return []

    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return []


@st.cache_data(show_spinner=False)
def cached_get_match_session_info(
    db_path: str,
    match_id: str,
    db_key: tuple[int, int] | None = None,
) -> dict | None:
    """Récupère les infos de session pour un match spécifique.

    DuckDB v4 ne stocke pas les sessions de la même manière.
    """
    _ = db_key
    # DuckDB v4 : pas d'info session disponible de cette façon
    if _is_duckdb_v4_path(db_path):
        return None
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return None
