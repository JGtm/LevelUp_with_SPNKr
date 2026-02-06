"""Gestion de la persistance des filtres par joueur.

Ce module permet de sauvegarder et charger les filtres activés/désactivés
pour chaque joueur, afin d'améliorer l'UX en conservant les préférences
entre les sessions et les changements de joueur.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import streamlit as st


@dataclass
class FilterPreferences:
    """Préférences de filtres pour un joueur.

    Toutes les valeurs sont optionnelles pour permettre une migration progressive.
    """

    # Mode de filtre ("Période" ou "Sessions")
    filter_mode: str | None = None

    # Mode Période
    start_date: str | None = None  # Format ISO: "YYYY-MM-DD"
    end_date: str | None = None  # Format ISO: "YYYY-MM-DD"

    # Mode Sessions
    gap_minutes: int | None = None
    picked_session_label: str | None = None

    # Filtres cascade (listes de strings)
    playlists_selected: list[str] | None = None
    modes_selected: list[str] | None = None
    maps_selected: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation JSON."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FilterPreferences:
        """Crée depuis un dictionnaire (désérialisation JSON)."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _get_filters_dir() -> Path:
    """Retourne le répertoire pour stocker les filtres."""
    project_root = Path(__file__).parent.parent.parent
    filters_dir = project_root / ".streamlit" / "filter_preferences"
    filters_dir.mkdir(parents=True, exist_ok=True)
    return filters_dir


def _get_player_key(xuid: str, db_path: str | None = None) -> str:
    """Génère une clé unique pour identifier un joueur.

    Pour DuckDB v4, utilise le gamertag depuis le chemin.
    Pour les autres cas, utilise le xuid.

    Args:
        xuid: XUID ou gamertag du joueur.
        db_path: Chemin vers la base de données (optionnel).

    Returns:
        Clé unique pour le joueur.
    """
    # Si c'est un chemin DuckDB v4 (data/players/{gamertag}/stats.duckdb),
    # extraire le gamertag
    if db_path:
        db_path_obj = Path(db_path)
        if "players" in db_path_obj.parts:
            try:
                players_idx = db_path_obj.parts.index("players")
                if players_idx + 1 < len(db_path_obj.parts):
                    gamertag = db_path_obj.parts[players_idx + 1]
                    return f"player_{gamertag}"
            except (ValueError, IndexError):
                pass

    # Sinon, utiliser le xuid
    return f"xuid_{xuid}"


def _get_filter_file_path(player_key: str) -> Path:
    """Retourne le chemin du fichier de filtres pour un joueur."""
    filters_dir = _get_filters_dir()
    # Nettoyer la clé pour éviter les caractères invalides dans les noms de fichiers
    safe_key = player_key.replace("/", "_").replace("\\", "_").replace(":", "_")
    return filters_dir / f"{safe_key}.json"


def save_filter_preferences(
    xuid: str,
    db_path: str | None = None,
    preferences: FilterPreferences | None = None,
) -> None:
    """Sauvegarde les préférences de filtres pour un joueur.

    Si preferences n'est pas fourni, lit depuis session_state.

    Args:
        xuid: XUID ou gamertag du joueur.
        db_path: Chemin vers la base de données (optionnel).
        preferences: Préférences à sauvegarder (optionnel, lit depuis session_state si None).
    """
    if preferences is None:
        preferences = FilterPreferences()

        # Mode de filtre
        filter_mode = st.session_state.get("filter_mode")
        if filter_mode in ("Période", "Sessions"):
            preferences.filter_mode = filter_mode

        # Mode Période
        start_date_val = st.session_state.get("start_date_cal")
        if isinstance(start_date_val, date):
            preferences.start_date = start_date_val.isoformat()
        end_date_val = st.session_state.get("end_date_cal")
        if isinstance(end_date_val, date):
            preferences.end_date = end_date_val.isoformat()

        # Mode Sessions
        gap_minutes_val = st.session_state.get("gap_minutes")
        if isinstance(gap_minutes_val, (int, float)):  # noqa: UP038
            preferences.gap_minutes = int(gap_minutes_val)
        picked_session_label_val = st.session_state.get("picked_session_label")
        if isinstance(picked_session_label_val, str):
            preferences.picked_session_label = picked_session_label_val

        # Filtres cascade
        playlists = st.session_state.get("filter_playlists")
        if isinstance(playlists, (set, list)):  # noqa: UP038
            preferences.playlists_selected = sorted(playlists)

        modes = st.session_state.get("filter_modes")
        if isinstance(modes, (set, list)):  # noqa: UP038
            preferences.modes_selected = sorted(modes)

        maps = st.session_state.get("filter_maps")
        if isinstance(maps, (set, list)):  # noqa: UP038
            preferences.maps_selected = sorted(maps)

    # Sauvegarder dans le fichier
    player_key = _get_player_key(xuid, db_path)
    file_path = _get_filter_file_path(player_key)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(preferences.to_dict(), f, indent=2, ensure_ascii=False)
    except Exception as e:
        # Ne pas bloquer l'application si la sauvegarde échoue
        st.warning(f"Impossible de sauvegarder les préférences de filtres: {e}")


def load_filter_preferences(
    xuid: str,
    db_path: str | None = None,
) -> FilterPreferences | None:
    """Charge les préférences de filtres pour un joueur.

    Args:
        xuid: XUID ou gamertag du joueur.
        db_path: Chemin vers la base de données (optionnel).

    Returns:
        Préférences chargées ou None si aucune préférence sauvegardée.
    """
    player_key = _get_player_key(xuid, db_path)
    file_path = _get_filter_file_path(player_key)

    if not file_path.exists():
        return None

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        return FilterPreferences.from_dict(data)
    except Exception:
        # Si le fichier est corrompu, retourner None
        return None


def apply_filter_preferences(
    xuid: str,
    db_path: str | None = None,
    preferences: FilterPreferences | None = None,
) -> None:
    """Applique les préférences de filtres dans session_state.

    Si preferences n'est pas fourni, charge depuis le fichier.

    Args:
        xuid: XUID ou gamertag du joueur.
        db_path: Chemin vers la base de données (optionnel).
        preferences: Préférences à appliquer (optionnel, charge depuis fichier si None).
    """
    if preferences is None:
        preferences = load_filter_preferences(xuid, db_path)
        if preferences is None:
            return

    # Mode de filtre
    if preferences.filter_mode:
        st.session_state["filter_mode"] = preferences.filter_mode

    # Mode Période
    if preferences.start_date:
        try:
            start_date_obj = date.fromisoformat(preferences.start_date)
            st.session_state["start_date_cal"] = start_date_obj
        except (ValueError, TypeError):
            pass

    if preferences.end_date:
        try:
            end_date_obj = date.fromisoformat(preferences.end_date)
            st.session_state["end_date_cal"] = end_date_obj
        except (ValueError, TypeError):
            pass

    # Mode Sessions
    if preferences.gap_minutes is not None:
        st.session_state["gap_minutes"] = preferences.gap_minutes

    if preferences.picked_session_label:
        st.session_state["picked_session_label"] = preferences.picked_session_label
        # Mettre à jour picked_sessions aussi
        if preferences.picked_session_label != "(toutes)":
            st.session_state["picked_sessions"] = [preferences.picked_session_label]
        else:
            st.session_state["picked_sessions"] = []

    # Filtres cascade
    if preferences.playlists_selected is not None:
        st.session_state["filter_playlists"] = set(preferences.playlists_selected)

    if preferences.modes_selected is not None:
        st.session_state["filter_modes"] = set(preferences.modes_selected)

    if preferences.maps_selected is not None:
        st.session_state["filter_maps"] = set(preferences.maps_selected)


def clear_filter_preferences(xuid: str, db_path: str | None = None) -> None:
    """Supprime les préférences de filtres sauvegardées pour un joueur.

    Args:
        xuid: XUID ou gamertag du joueur.
        db_path: Chemin vers la base de données (optionnel).
    """
    player_key = _get_player_key(xuid, db_path)
    file_path = _get_filter_file_path(player_key)

    if file_path.exists():
        with contextlib.suppress(Exception):
            file_path.unlink()
