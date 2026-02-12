"""Utilitaires pour la page Coéquipiers.

Fonctions d'aide pour l'affichage des cartes joueurs et tableaux.
"""

from __future__ import annotations

import html as html_lib
import urllib.parse

import polars as pl

# Type alias pour compatibilité DataFrame
try:
    import pandas as pd

    DataFrameType = pd.DataFrame | pl.DataFrame
except ImportError:
    pd = None  # type: ignore[assignment]
    DataFrameType = pl.DataFrame  # type: ignore[misc]

import streamlit as st

from src.config import HALO_COLORS
from src.ui import (
    display_name_from_xuid,
    get_hero_html,
    get_profile_appearance,
    translate_playlist_name,
)
from src.ui.cache import cached_load_player_match_result
from src.ui.player_assets import ensure_local_image_path


def _format_datetime_fr_hm(dt: pd.Timestamp | None) -> str:
    """Formate une date FR avec heures/minutes."""
    if pd.isna(dt):
        return "-"
    try:
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(dt)


def _normalize_mode_label(pair_name: str | None) -> str | None:
    """Normalise un pair_name en label UI."""
    from src.ui.translations import translate_pair_name

    return translate_pair_name(pair_name) if pair_name else None


def _app_url(page: str, **params: str) -> str:
    """Génère une URL interne vers une page de l'app."""
    base = "/"
    qp = {"page": page, **params}
    return base + "?" + urllib.parse.urlencode(qp)


def _format_score_label(my_score: object, enemy_score: object) -> str:
    """Formate le score du match."""

    def _safe(v: object) -> str:
        if v is None:
            return "-"
        try:
            if v != v:  # NaN
                return "-"
        except Exception:
            pass
        try:
            return str(int(round(float(v))))
        except Exception:
            return str(v)

    return f"{_safe(my_score)} - {_safe(enemy_score)}"


def _clear_min_matches_maps_friends_auto() -> None:
    """Callback pour désactiver le mode auto du slider coéquipiers."""
    st.session_state["_min_matches_maps_friends_auto"] = False


@st.cache_data(show_spinner=False, ttl=300)
def _get_teammate_card_data(
    t_xuid: str,
    api_refresh_h: int,
) -> dict:
    """Récupère les données de carte d'un coéquipier (caché 5min).

    Cette fonction est cachée car get_profile_appearance peut être lente
    si les données ne sont pas en cache disque.
    """
    t_name = display_name_from_xuid(t_xuid)
    t_app, _ = get_profile_appearance(
        xuid=t_xuid,
        enabled=True,
        refresh_hours=api_refresh_h,
    )
    return {
        "name": t_name,
        "emblem_url": getattr(t_app, "emblem_image_url", None) if t_app else None,
        "backdrop_url": getattr(t_app, "backdrop_image_url", None) if t_app else None,
        "nameplate_url": getattr(t_app, "nameplate_image_url", None) if t_app else None,
        "service_tag": getattr(t_app, "service_tag", None) if t_app else None,
    }


def render_teammate_cards(picked_xuids: list[str], settings: object) -> None:
    """Affiche les cartes Spartan des coéquipiers sélectionnés.

    Args:
        picked_xuids: Liste des XUIDs des coéquipiers.
        settings: Paramètres de l'application.

    Note: Optimisé avec cache TTL pour éviter les appels API répétés.
    """
    if not picked_xuids:
        return

    teammate_cards_html = []
    dl_enabled = bool(getattr(settings, "profile_assets_download_enabled", False)) or bool(
        getattr(settings, "profile_api_enabled", False)
    )
    refresh_h = int(getattr(settings, "profile_assets_auto_refresh_hours", 0) or 0)
    api_refresh_h = int(getattr(settings, "profile_api_auto_refresh_hours", 0) or 0)

    for t_xuid in picked_xuids:
        # Utiliser la fonction cachée pour les données de profil
        card_data = _get_teammate_card_data(t_xuid, api_refresh_h)

        t_emblem_path = ensure_local_image_path(
            card_data["emblem_url"],
            prefix="emblem",
            download_enabled=dl_enabled,
            auto_refresh_hours=refresh_h,
        )
        t_backdrop_path = ensure_local_image_path(
            card_data["backdrop_url"],
            prefix="backdrop",
            download_enabled=dl_enabled,
            auto_refresh_hours=refresh_h,
        )
        t_nameplate_path = ensure_local_image_path(
            card_data["nameplate_url"],
            prefix="nameplate",
            download_enabled=dl_enabled,
            auto_refresh_hours=refresh_h,
        )

        card_html = get_hero_html(
            player_name=card_data["name"],
            service_tag=card_data["service_tag"],
            emblem_path=t_emblem_path,
            backdrop_path=t_backdrop_path,
            nameplate_path=t_nameplate_path,
            grid_mode=True,
        )
        teammate_cards_html.append(card_html)

    if teammate_cards_html:
        cols = st.columns(2)
        for i, card_html in enumerate(teammate_cards_html):
            with cols[i % 2]:
                st.markdown(card_html, unsafe_allow_html=True)


def render_friends_history_table(
    sub_all: pd.DataFrame,
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
    waypoint_player: str,
) -> None:
    """Affiche le tableau d'historique des matchs avec coéquipiers.

    Args:
        sub_all: DataFrame des matchs filtrés.
        db_path: Chemin vers la base de données.
        xuid: XUID du joueur principal.
        db_key: Clé de cache de la DB.
        waypoint_player: Nom Waypoint du joueur.
    """
    friends_table = sub_all.copy()
    friends_table["start_time_fr"] = friends_table["start_time"].apply(_format_datetime_fr_hm)
    if "playlist_fr" not in friends_table.columns:
        friends_table["playlist_fr"] = friends_table["playlist_name"].apply(translate_playlist_name)
    if "mode_ui" in friends_table.columns:
        friends_table["mode"] = friends_table["mode_ui"].apply(
            lambda x: x if (x is not None and str(x).strip()) else None
        )
    else:
        friends_table["mode"] = None
    if friends_table["mode"].isna().any() and "pair_name" in friends_table.columns:
        mask = friends_table["mode"].isna()
        friends_table.loc[mask, "mode"] = friends_table.loc[mask, "pair_name"].apply(
            lambda p: _normalize_mode_label(str(p) if p is not None else None)
        )
    friends_table["mode"] = friends_table["mode"].fillna("-")
    friends_table["outcome_label"] = (
        friends_table["outcome"]
        .map({2: "Victoire", 3: "Défaite", 1: "Égalité", 4: "Non terminé"})
        .fillna("-")
    )
    friends_table["score"] = friends_table.apply(
        lambda r: _format_score_label(r.get("my_team_score"), r.get("enemy_team_score")), axis=1
    )

    # Utiliser les colonnes MMR du DataFrame si elles existent (DuckDB v4 les charge déjà)
    # Sinon, fallback vers des requêtes individuelles (legacy ou colonnes manquantes)
    if "team_mmr" not in friends_table.columns or friends_table["team_mmr"].isna().all():

        def _mmr_tuple(match_id: str):
            pm = cached_load_player_match_result(
                db_path, str(match_id), xuid.strip(), db_key=db_key
            )
            if not isinstance(pm, dict):
                return (None, None)
            return (pm.get("team_mmr"), pm.get("enemy_mmr"))

        mmr_pairs = friends_table["match_id"].astype(str).apply(_mmr_tuple)
        friends_table["team_mmr"] = mmr_pairs.apply(lambda t: t[0])
        friends_table["enemy_mmr"] = mmr_pairs.apply(lambda t: t[1])

    # S'assurer que les colonnes existent
    if "team_mmr" not in friends_table.columns:
        friends_table["team_mmr"] = None
    if "enemy_mmr" not in friends_table.columns:
        friends_table["enemy_mmr"] = None

    friends_table["delta_mmr"] = friends_table.apply(
        lambda r: (float(r["team_mmr"]) - float(r["enemy_mmr"]))
        if (pd.notna(r.get("team_mmr")) and pd.notna(r.get("enemy_mmr")))
        else None,
        axis=1,
    )
    wp = str(waypoint_player or "").strip()
    if wp:
        friends_table["match_url"] = (
            "https://www.halowaypoint.com/halo-infinite/players/"
            + wp
            + "/matches/"
            + friends_table["match_id"].astype(str)
        )
    else:
        friends_table["match_url"] = ""

    view = friends_table.sort_values("start_time", ascending=False).head(250).reset_index(drop=True)

    def _fmt(v) -> str:
        if v is None:
            return "-"
        try:
            if v != v:
                return "-"
        except Exception:
            pass
        s = str(v)
        return s if s.strip() else "-"

    def _fmt_mmr_int(v) -> str:
        if v is None:
            return "-"
        try:
            if v != v:
                return "-"
        except Exception:
            pass
        try:
            return str(int(round(float(v))))
        except Exception:
            return _fmt(v)

    colors = HALO_COLORS.as_dict()

    def _outcome_style(label: str) -> str:
        v = str(label or "").strip().casefold()
        if v.startswith("victoire"):
            return f"color:{colors['green']}; font-weight:800"
        if v.startswith("défaite") or v.startswith("defaite"):
            return f"color:{colors['red']}; font-weight:800"
        if v.startswith("égalité") or v.startswith("egalite"):
            return f"color:{colors['violet']}; font-weight:800"
        if v.startswith("non"):
            return f"color:{colors['violet']}; font-weight:800"
        return "opacity:0.92"

    cols = [
        ("Match", "_app"),
        ("HaloWaypoint", "match_url"),
        ("Date", "start_time_fr"),
        ("Carte", "map_name"),
        ("Playlist", "playlist_fr"),
        ("Mode", "mode"),
        ("Résultat", "outcome_label"),
        ("Score", "score"),
        ("MMR équipe", "team_mmr"),
        ("MMR adverse", "enemy_mmr"),
        ("Écart MMR", "delta_mmr"),
    ]

    head = "".join(f"<th>{html_lib.escape(h)}</th>" for h, _ in cols)
    body_rows: list[str] = []
    for _, r in view.iterrows():
        mid = str(r.get("match_id") or "").strip()
        app = _app_url("Match", match_id=mid)
        match_link = f"<a href='{html_lib.escape(app)}' target='_self'>Ouvrir</a>" if mid else "-"
        hw = str(r.get("match_url") or "").strip()
        hw_link = (
            f"<a href='{html_lib.escape(hw)}' target='_blank' rel='noopener'>Ouvrir</a>"
            if hw
            else "-"
        )

        tds: list[str] = []
        for _h, key in cols:
            if key == "_app":
                tds.append(f"<td>{match_link}</td>")
            elif key == "match_url":
                tds.append(f"<td>{hw_link}</td>")
            elif key == "outcome_label":
                val = _fmt(r.get(key))
                tds.append(f"<td style='{_outcome_style(val)}'>{html_lib.escape(val)}</td>")
            elif key in ("team_mmr", "enemy_mmr", "delta_mmr"):
                val = _fmt_mmr_int(r.get(key))
                tds.append(f"<td>{html_lib.escape(val)}</td>")
            else:
                val = _fmt(r.get(key))
                tds.append(f"<td>{html_lib.escape(val)}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")

    st.markdown(
        "<div class='os-table-wrap'><table class='os-table'><thead><tr>"
        + head
        + "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table></div>",
        unsafe_allow_html=True,
    )
