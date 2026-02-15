"""Utilitaires pour la page Coéquipiers.

Fonctions d'aide pour l'affichage des cartes joueurs et tableaux.
"""

from __future__ import annotations

import html as html_lib
import urllib.parse

import polars as pl
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
from src.visualization._compat import DataFrameLike, ensure_polars


def _format_datetime_fr_hm(dt: object) -> str:
    """Formate une date FR avec heures/minutes."""
    if dt is None:
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
    sub_all: DataFrameLike,
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
    friends_table = ensure_polars(sub_all)
    friends_table = friends_table.with_columns(
        pl.col("start_time").dt.strftime("%d/%m/%Y %H:%M").fill_null("-").alias("start_time_fr")
    )
    if "playlist_fr" not in friends_table.columns:
        friends_table = friends_table.with_columns(
            pl.col("playlist_name")
            .map_elements(translate_playlist_name, return_dtype=pl.Utf8)
            .alias("playlist_fr")
        )
    if "mode_ui" in friends_table.columns:
        friends_table = friends_table.with_columns(
            pl.when(
                pl.col("mode_ui").is_not_null()
                & (pl.col("mode_ui").cast(pl.Utf8).str.strip_chars() != "")
            )
            .then(pl.col("mode_ui"))
            .otherwise(pl.lit(None))
            .alias("mode")
        )
    else:
        friends_table = friends_table.with_columns(pl.lit(None).cast(pl.Utf8).alias("mode"))
    if friends_table["mode"].is_null().any() and "pair_name" in friends_table.columns:
        friends_table = friends_table.with_columns(
            pl.when(pl.col("mode").is_null())
            .then(
                pl.col("pair_name").map_elements(
                    lambda p: _normalize_mode_label(str(p) if p is not None else None),
                    return_dtype=pl.Utf8,
                )
            )
            .otherwise(pl.col("mode"))
            .alias("mode")
        )
    friends_table = friends_table.with_columns(pl.col("mode").fill_null("-"))
    friends_table = friends_table.with_columns(
        pl.col("outcome")
        .replace_strict(
            {2: "Victoire", 3: "Défaite", 1: "Égalité", 4: "Non terminé"},
            default="-",
            return_dtype=pl.Utf8,
        )
        .alias("outcome_label")
    )
    # Calcul du score
    score_cols = ["my_team_score", "enemy_team_score"]
    if all(c in friends_table.columns for c in score_cols):
        friends_table = friends_table.with_columns(
            pl.struct(score_cols)
            .map_elements(
                lambda r: _format_score_label(r["my_team_score"], r["enemy_team_score"]),
                return_dtype=pl.Utf8,
            )
            .alias("score")
        )
    else:
        friends_table = friends_table.with_columns(pl.lit("-").alias("score"))

    # Utiliser les colonnes MMR du DataFrame si elles existent (DuckDB v4 les charge déjà)
    # Sinon, fallback vers des requêtes individuelles (legacy ou colonnes manquantes)
    if "team_mmr" not in friends_table.columns or friends_table["team_mmr"].is_null().all():
        match_ids_list = friends_table["match_id"].cast(pl.Utf8).to_list()
        team_mmrs: list[object] = []
        enemy_mmrs: list[object] = []
        for mid in match_ids_list:
            pm = cached_load_player_match_result(db_path, str(mid), xuid.strip(), db_key=db_key)
            if not isinstance(pm, dict):
                team_mmrs.append(None)
                enemy_mmrs.append(None)
            else:
                team_mmrs.append(pm.get("team_mmr"))
                enemy_mmrs.append(pm.get("enemy_mmr"))
        friends_table = friends_table.with_columns(
            [
                pl.Series("team_mmr", team_mmrs),
                pl.Series("enemy_mmr", enemy_mmrs),
            ]
        )

    # S'assurer que les colonnes existent
    if "team_mmr" not in friends_table.columns:
        friends_table = friends_table.with_columns(pl.lit(None).alias("team_mmr"))
    if "enemy_mmr" not in friends_table.columns:
        friends_table = friends_table.with_columns(pl.lit(None).alias("enemy_mmr"))

    friends_table = friends_table.with_columns(
        pl.when(pl.col("team_mmr").is_not_null() & pl.col("enemy_mmr").is_not_null())
        .then(pl.col("team_mmr").cast(pl.Float64) - pl.col("enemy_mmr").cast(pl.Float64))
        .otherwise(pl.lit(None))
        .alias("delta_mmr")
    )
    wp = str(waypoint_player or "").strip()
    if wp:
        friends_table = friends_table.with_columns(
            (
                pl.lit("https://www.halowaypoint.com/halo-infinite/players/" + wp + "/matches/")
                + pl.col("match_id").cast(pl.Utf8)
            ).alias("match_url")
        )
    else:
        friends_table = friends_table.with_columns(pl.lit("").alias("match_url"))

    view = friends_table.sort("start_time", descending=True).head(250)

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
    for r in view.to_dicts():
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
