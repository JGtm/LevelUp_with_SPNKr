"""Section joueurs pour la page Match View - Némésis et Roster."""

from __future__ import annotations

import html
import re
from typing import Callable

import pandas as pd
import streamlit as st

from src.config import BOT_MAP, TEAM_MAP
from src.db import has_table
from src.db.parsers import parse_xuid_input
from src.analysis import compute_killer_victim_pairs, killer_victim_counts_long
from src.ui import display_name_from_xuid
from src.ui.pages.match_view_helpers import os_card


# =============================================================================
# Section Némésis / Souffre-douleur
# =============================================================================


def render_nemesis_section(
    *,
    match_id: str,
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
    colors: dict,
    load_highlight_events_fn: Callable,
    load_match_gamertags_fn: Callable,
) -> None:
    """Rend la section Némésis / Souffre-douleur."""
    st.subheader("Antagonistes du match")
    if not (match_id and match_id.strip() and has_table(db_path, "HighlightEvents")):
        st.caption(
            "Indisponible: la DB ne contient pas les highlight events. "
            "Si tu utilises une DB SPNKr, relance l'import avec `--with-highlight-events`."
        )
        return

    with st.spinner("Chargement des highlight events (film)…"):
        he = load_highlight_events_fn(db_path, match_id.strip(), db_key=db_key)

    match_gt_map = load_match_gamertags_fn(db_path, match_id.strip(), db_key=db_key)

    pairs = compute_killer_victim_pairs(he, tolerance_ms=5)
    if not pairs:
        st.info("Aucune paire kill/death trouvée (ou match sans timeline exploitable).")
        return

    kv_long = killer_victim_counts_long(pairs)

    me_xuid = str(xuid).strip()
    killed_me = kv_long[kv_long["victim_xuid"].astype(str) == me_xuid]
    i_killed = kv_long[kv_long["killer_xuid"].astype(str) == me_xuid]

    def _display_name_from_kv(xuid_value, gamertag_value) -> str:
        gt = str(gamertag_value or "").strip()
        xu_raw = str(xuid_value or "").strip()
        xu = parse_xuid_input(xu_raw) or xu_raw

        xu_key = str(xu).strip() if xu is not None else ""
        if xu_key and isinstance(match_gt_map, dict):
            mapped = match_gt_map.get(xu_key)
            if isinstance(mapped, str) and mapped.strip():
                return mapped.strip()

        if (not gt) or gt == "?" or gt.isdigit() or gt.lower().startswith("xuid("):
            if xu:
                return display_name_from_xuid(str(xu).strip())
            return "-"
        return gt

    nemesis_name = "-"
    nemesis_kills = None
    if not killed_me.empty:
        top = (
            killed_me[["killer_xuid", "killer_gamertag", "count"]]
            .rename(columns={"count": "Kills"})
            .sort_values(["Kills"], ascending=[False])
            .iloc[0]
        )
        nemesis_name = _display_name_from_kv(top.get("killer_xuid"), top.get("killer_gamertag"))
        nemesis_kills = int(top.get("Kills")) if top.get("Kills") is not None else None

    bully_name = "-"
    bully_kills = None
    if not i_killed.empty:
        top = (
            i_killed[["victim_xuid", "victim_gamertag", "count"]]
            .rename(columns={"count": "Kills"})
            .sort_values(["Kills"], ascending=[False])
            .iloc[0]
        )
        bully_name = _display_name_from_kv(top.get("victim_xuid"), top.get("victim_gamertag"))
        bully_kills = int(top.get("Kills")) if top.get("Kills") is not None else None

    def _clean_name(v: str) -> str:
        s = str(v or "")
        s = s.replace("\ufffd", "")
        s = re.sub(r"[\x00-\x1f\x7f]", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s or "-"

    nemesis_name = _clean_name(nemesis_name)
    bully_name = _clean_name(bully_name)

    def _count_kills(df_: pd.DataFrame, *, col: str, xuid_value: str) -> int | None:
        if df_ is None or df_.empty or not xuid_value:
            return None
        try:
            mask = df_[col].astype(str) == str(xuid_value)
            hit = df_.loc[mask]
            if hit.empty:
                return None
            return int(hit["count"].iloc[0])
        except Exception:
            return None

    nemesis_xu = ""
    bully_xu = ""
    if not killed_me.empty:
        try:
            nemesis_xu = str(killed_me.sort_values(["count"], ascending=[False]).iloc[0].get("killer_xuid") or "").strip()
        except Exception:
            nemesis_xu = ""
    if not i_killed.empty:
        try:
            bully_xu = str(i_killed.sort_values(["count"], ascending=[False]).iloc[0].get("victim_xuid") or "").strip()
        except Exception:
            bully_xu = ""

    nemesis_killed_me = nemesis_kills
    me_killed_nemesis = _count_kills(i_killed, col="victim_xuid", xuid_value=nemesis_xu)
    me_killed_bully = bully_kills
    bully_killed_me = _count_kills(killed_me, col="killer_xuid", xuid_value=bully_xu)

    def _cmp_color(deaths_: int | None, kills_: int | None) -> str:
        if deaths_ is None or kills_ is None:
            return colors["slate"]
        if int(deaths_) > int(kills_):
            return colors["red"]
        if int(deaths_) < int(kills_):
            return colors["green"]
        return colors["violet"]

    def _fmt_two_lines(deaths_: int | None, kills_: int | None) -> str:
        d = "-" if deaths_ is None else f"{int(deaths_)} morts"
        k = "-" if kills_ is None else f"Tué {int(kills_)} fois"
        return html.escape(d) + "<br/>" + html.escape(k)

    c = st.columns(2)
    with c[0]:
        os_card(
            "Némésis",
            nemesis_name,
            _fmt_two_lines(nemesis_killed_me, me_killed_nemesis),
            accent=_cmp_color(nemesis_killed_me, me_killed_nemesis),
            sub_style="color: rgba(245, 248, 255, 0.92); font-weight: 800; font-size: 16px; line-height: 1.15;",
            min_h=110,
        )
    with c[1]:
        os_card(
            "Souffre-douleur",
            bully_name,
            _fmt_two_lines(bully_killed_me, me_killed_bully),
            accent=_cmp_color(bully_killed_me, me_killed_bully),
            sub_style="color: rgba(245, 248, 255, 0.92); font-weight: 800; font-size: 16px; line-height: 1.15;",
            min_h=110,
        )


# =============================================================================
# Section Roster
# =============================================================================


def render_roster_section(
    *,
    match_id: str,
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
    load_match_rosters_fn: Callable,
    load_match_gamertags_fn: Callable,
) -> None:
    """Rend la section Joueurs (roster)."""
    st.subheader("Joueurs")
    rosters = load_match_rosters_fn(db_path, match_id.strip(), xuid.strip(), db_key=db_key)
    if not rosters:
        st.info("Roster indisponible pour ce match (payload MatchStats manquant ou équipe introuvable).")
        return

    gt_map = load_match_gamertags_fn(db_path, match_id.strip(), db_key=db_key)
    me_xu = str(parse_xuid_input(str(xuid or "").strip()) or str(xuid or "").strip()).strip()

    my_team_id = rosters.get("my_team_id")
    my_team_name = rosters.get("my_team_name")
    enemy_team_ids = rosters.get("enemy_team_ids") or []
    enemy_team_names = rosters.get("enemy_team_names") or []

    def _team_label(team_id_value) -> str:
        try:
            tid = int(team_id_value)
        except Exception:
            return "-"
        return TEAM_MAP.get(tid) or f"Team {tid}"

    def _roster_name(xu: str, gt: str | None) -> str:
        xu_s = str(parse_xuid_input(str(xu or "").strip()) or str(xu or "").strip()).strip()

        if xu_s:
            bot_key = xu_s.strip()
            if bot_key.lower().startswith("bid("):
                bot_name = BOT_MAP.get(bot_key)
                if isinstance(bot_name, str) and bot_name.strip():
                    return bot_name.strip()

        if xu_s and isinstance(gt_map, dict):
            mapped = gt_map.get(xu_s)
            if isinstance(mapped, str) and mapped.strip():
                return mapped.strip()

        g = str(gt or "").strip()
        if g and g != "?" and (not g.isdigit()) and (not g.lower().startswith("xuid(")):
            return g

        if xu_s:
            return display_name_from_xuid(xu_s)
        return "-"

    my_rows = rosters.get("my_team") or []
    en_rows = rosters.get("enemy_team") or []

    my_names: list[tuple[str, bool]] = []
    en_names: list[tuple[str, bool]] = []

    for r in my_rows:
        xu = str(r.get("xuid") or "").strip()
        name = str(r.get("display_name") or "").strip() or _roster_name(xu, r.get("gamertag"))
        is_self = bool(me_xu and xu and (str(parse_xuid_input(xu) or xu).strip() == me_xu)) or bool(r.get("is_me"))
        my_names.append((name, is_self))

    for r in en_rows:
        xu = str(r.get("xuid") or "").strip()
        name = str(r.get("display_name") or "").strip() or _roster_name(xu, r.get("gamertag"))
        en_names.append((name, False))

    rows_n = max(len(my_names), len(en_names), 1)
    my_names += [("", False)] * (rows_n - len(my_names))
    en_names += [("", False)] * (rows_n - len(en_names))

    def _pill_html(name: str, *, side: str, is_self: bool) -> str:
        if not name:
            return "<span class='os-roster-empty'>—</span>"
        safe = html.escape(str(name))
        extra = " os-roster-pill--self" if is_self else ""
        return (
            f"<span class='os-roster-pill os-roster-pill--{side}{extra}'>"
            "<span class='os-roster-pill__dot'></span>"
            f"<span>{safe}</span>"
            "</span>"
        )

    body_rows = []
    for i in range(rows_n):
        n_me, is_self = my_names[i]
        n_en, _ = en_names[i]
        body_rows.append(
            "<tr>"
            f"<td>{_pill_html(n_me, side='me', is_self=is_self)}</td>"
            f"<td>{_pill_html(n_en, side='enemy', is_self=False)}</td>"
            "</tr>"
        )

    st.markdown(
        "<div class='os-table-wrap os-roster-wrap'>"
        "<table class='os-table os-roster'>"
        "<thead><tr>"
        f"<th class='os-roster-th os-roster-th--me'>Mon équipe — {html.escape(str(my_team_name or _team_label(my_team_id)))} ({len([n for n, _ in my_names if n])})</th>"
        f"<th class='os-roster-th os-roster-th--enemy'>Équipe adverse — {html.escape(str(enemy_team_names[0] if (isinstance(enemy_team_names, list) and len(enemy_team_names)==1 and enemy_team_names[0]) else (' / '.join([_team_label(t) for t in enemy_team_ids]) if enemy_team_ids else 'Adversaires')))} ({len([n for n, _ in en_names if n])})</th>"
        "</tr></thead>"
        "<tbody>" + "".join(body_rows) + "</tbody>"
        "</table>"
        "</div>",
        unsafe_allow_html=True,
    )


# =============================================================================
# Exports publics
# =============================================================================

__all__ = [
    "render_nemesis_section",
    "render_roster_section",
]
