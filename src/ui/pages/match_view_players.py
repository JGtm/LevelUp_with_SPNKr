"""Section joueurs pour la page Match View - Némésis et Roster."""

from __future__ import annotations

import html
import logging
import os
import re
from collections.abc import Callable
from typing import Any

import streamlit as st

from src.analysis import compute_personal_antagonists
from src.config import BOT_MAP, TEAM_MAP
from src.ui import display_name_from_xuid
from src.ui.pages.match_view_helpers import os_card
from src.utils import parse_xuid_input

logger = logging.getLogger(__name__)


# =============================================================================
# Helper DuckDB v4
# =============================================================================


def _is_duckdb_v4_path(db_path: str) -> bool:
    """Détecte si le chemin est une DB joueur DuckDB v4."""
    return db_path.endswith(".duckdb") if db_path else False


def _has_table_duckdb(db_path: str, table_name: str) -> bool:
    """Vérifie si une table existe dans une DB DuckDB."""
    if not _is_duckdb_v4_path(db_path):
        return False
    try:
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(db_path, xuid="", read_only=True)
        return repo.has_table(table_name)
    except Exception:
        return False


def _load_match_players_stats(db_path: str, match_id: str) -> list[dict[str, Any]]:
    """Charge les stats des joueurs d'un match."""
    if not _is_duckdb_v4_path(db_path):
        return []
    try:
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(db_path, xuid="", read_only=True)
        return repo.load_match_players_stats(match_id)
    except Exception:
        return []


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
    if not (match_id and match_id.strip() and _has_table_duckdb(db_path, "highlight_events")):
        st.caption(
            "Indisponible: la DB ne contient pas les highlight events. "
            "Si tu utilises une DB SPNKr, relance l'import avec `--with-highlight-events`."
        )
        return

    with st.spinner("Chargement des highlight events (film)…"):
        he = load_highlight_events_fn(db_path, match_id.strip(), db_key=db_key)

    match_gt_map = load_match_gamertags_fn(db_path, match_id.strip(), db_key=db_key)

    me_xuid = str(parse_xuid_input(str(xuid or "").strip()) or str(xuid or "").strip()).strip()

    # Sprint 3.3: Charger les stats officielles pour validation des antagonistes
    official_stats = _load_match_players_stats(db_path, match_id.strip())

    res = compute_personal_antagonists(
        he, me_xuid=me_xuid, tolerance_ms=5, official_stats=official_stats
    )
    if (res.nemesis is None) and (res.bully is None):
        st.info("Impossible de déterminer Némésis/Souffre-douleur (timeline insuffisante).")
        # On continue pour afficher le graphique Killer-Victim si des données existent

    def _debug_enabled() -> bool:
        env_flag = str(os.environ.get("OPENSPARTAN_DEBUG_ANTAGONISTS") or "").strip().lower()
        if env_flag in {"1", "true", "yes", "y", "on"}:
            return True

        env_flag2 = str(os.environ.get("OPENSPARTAN_DEBUG") or "").strip().lower()
        if env_flag2 in {"1", "true", "yes", "y", "on"}:
            return True

        try:
            if bool(st.session_state.get("ui_debug_antagonists", False)):
                return True
        except Exception:
            pass

        # Query params (compatible Streamlit récent + fallback expérimental)
        try:
            if hasattr(st, "query_params"):
                qp = st.query_params
                v = qp.get("debug_antagonists") or qp.get("debug")
            else:
                qp = st.experimental_get_query_params()
                v = (qp.get("debug_antagonists") or qp.get("debug") or [""])[0]
            if isinstance(v, list | tuple):
                v = v[0] if v else ""
            if str(v or "").strip().lower() in {"1", "true", "yes", "y", "on"}:
                return True
        except Exception:
            pass

        return False

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

    # Afficher les cartes Némésis/Souffre-douleur uniquement si déterminés
    if (res.nemesis is not None) or (res.bully is not None):
        nemesis_name = "-"
        nemesis_killed_me: int | None = None
        nemesis_killed_me_approx = False
        me_killed_nemesis: int | None = None
        me_killed_nemesis_approx = False
        if res.nemesis is not None:
            nemesis_name = _display_name_from_kv(res.nemesis.xuid, res.nemesis.gamertag)
            nemesis_killed_me = int(res.nemesis.opponent_killed_me.total)
            nemesis_killed_me_approx = bool(res.nemesis.opponent_killed_me.has_estimated)
            me_killed_nemesis = int(res.nemesis.me_killed_opponent.total)
            me_killed_nemesis_approx = bool(res.nemesis.me_killed_opponent.has_estimated)

        bully_name = "-"
        bully_killed_me: int | None = None
        bully_killed_me_approx = False
        me_killed_bully: int | None = None
        me_killed_bully_approx = False
        if res.bully is not None:
            bully_name = _display_name_from_kv(res.bully.xuid, res.bully.gamertag)
            bully_killed_me = int(res.bully.opponent_killed_me.total)
            bully_killed_me_approx = bool(res.bully.opponent_killed_me.has_estimated)
            me_killed_bully = int(res.bully.me_killed_opponent.total)
            me_killed_bully_approx = bool(res.bully.me_killed_opponent.has_estimated)

        def _clean_name(v: str) -> str:
            s = str(v or "")
            s = s.replace("\ufffd", "")
            s = re.sub(r"[\x00-\x1f\x7f]", "", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s or "-"

        nemesis_name = _clean_name(nemesis_name)
        bully_name = _clean_name(bully_name)

        def _cmp_color(deaths_: int | None, kills_: int | None) -> str:
            if deaths_ is None or kills_ is None:
                return colors["slate"]
            if int(deaths_) > int(kills_):
                return colors["red"]
            if int(deaths_) < int(kills_):
                return colors["green"]
            return colors["violet"]

        def _fmt_count(label: str, value: int | None, approx: bool) -> str:
            if value is None:
                return "-"
            prefix = "≈ " if approx else ""
            if label == "deaths":
                return f"{prefix}{int(value)} morts"
            return f"{prefix}Tué {int(value)} fois"

        def _fmt_two_lines(
            deaths_: int | None, deaths_approx: bool, kills_: int | None, kills_approx: bool
        ) -> str:
            d = _fmt_count("deaths", deaths_, deaths_approx)
            k = _fmt_count("kills", kills_, kills_approx)
            return html.escape(d) + "<br/>" + html.escape(k)

        c = st.columns(2)
        with c[0]:
            os_card(
                "Némésis",
                nemesis_name,
                _fmt_two_lines(
                    nemesis_killed_me,
                    nemesis_killed_me_approx,
                    me_killed_nemesis,
                    me_killed_nemesis_approx,
                ),
                accent=_cmp_color(nemesis_killed_me, me_killed_nemesis),
                sub_style="color: rgba(245, 248, 255, 0.92); font-weight: 800; font-size: 16px; line-height: 1.15;",
                min_h=110,
            )
        with c[1]:
            os_card(
                "Souffre-douleur",
                bully_name,
                _fmt_two_lines(
                    bully_killed_me, bully_killed_me_approx, me_killed_bully, me_killed_bully_approx
                ),
                accent=_cmp_color(bully_killed_me, me_killed_bully),
                sub_style="color: rgba(245, 248, 255, 0.92); font-weight: 800; font-size: 16px; line-height: 1.15;",
                min_h=110,
            )

    if _debug_enabled():
        deaths_missing = max(0, int(res.my_deaths_total) - int(res.my_deaths_assigned_total))
        deaths_est = max(0, int(res.my_deaths_assigned_total) - int(res.my_deaths_assigned_certain))
        kills_missing = max(0, int(res.my_kills_total) - int(res.my_kills_assigned_total))
        kills_est = max(0, int(res.my_kills_assigned_total) - int(res.my_kills_assigned_certain))

        # Sprint 3.3: Indicateur visuel de confiance
        validation_icon = "✓" if res.is_validated else "⚠"
        validation_label = "Validé" if res.is_validated else "Non validé"

        st.caption(
            f"Debug antagonistes {validation_icon} {validation_label} — "
            f"Morts attribuées {res.my_deaths_assigned_total}/{res.my_deaths_total} "
            f"(certain {res.my_deaths_assigned_certain}, estimé {deaths_est}, manquantes {deaths_missing}) · "
            f"Kills attribués {res.my_kills_assigned_total}/{res.my_kills_total} "
            f"(certain {res.my_kills_assigned_certain}, estimé {kills_est}, manquants {kills_missing})"
        )

        # Sprint 3.3: Afficher validation_notes si présentes
        if res.validation_notes:
            st.caption(f"Validation: {res.validation_notes}")

    # Graphique barres empilées Killer-Victim (antagonist_charts)
    _render_antagonist_chart(
        match_id=match_id,
        db_path=db_path,
        xuid=xuid,
        db_key=db_key,
        load_match_gamertags_fn=load_match_gamertags_fn,
        highlight_events=he,
    )


def _display_name_for_chart(
    xuid: str,
    gamertag: str | None,
    gt_map: dict[str, str] | None,
) -> str:
    """Nom d'affichage pour le graphe killer-victime (même logique que le roster)."""
    xu_s = str(parse_xuid_input(str(xuid or "").strip()) or str(xuid or "").strip()).strip()

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

    g = str(gamertag or "").strip()
    if g and g != "?" and (not g.isdigit()) and (not g.lower().startswith("xuid(")):
        return g

    if xu_s:
        return display_name_from_xuid(xu_s)
    return "-"


def _render_antagonist_chart(
    *,
    match_id: str,
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None = None,
    load_match_gamertags_fn: Callable | None = None,
    highlight_events: list | None = None,
) -> None:
    """Affiche le graphique des interactions Killer-Victim du match."""
    if not match_id or not match_id.strip():
        return

    gt_map = None
    if load_match_gamertags_fn is not None:
        try:
            gt_map = load_match_gamertags_fn(db_path, match_id.strip(), db_key=db_key)
        except Exception:
            gt_map = None

    pairs_df = None
    if db_path and str(db_path).endswith(".duckdb"):
        try:
            from src.data.repositories.duckdb_repo import DuckDBRepository

            repo = DuckDBRepository(db_path, str(xuid).strip())
            pairs_df = repo.load_killer_victim_pairs_as_polars(match_id=match_id.strip())
        except Exception:
            pairs_df = None

    # Fallback : construire depuis highlight_events
    if (
        pairs_df is None or (hasattr(pairs_df, "is_empty") and pairs_df.is_empty())
    ) and highlight_events:
        try:
            import polars as pl

            from src.analysis import compute_killer_victim_pairs

            kv_pairs = compute_killer_victim_pairs(highlight_events, tolerance_ms=5)
            if kv_pairs:
                pairs_df = pl.DataFrame(
                    {
                        "match_id": [match_id] * len(kv_pairs),
                        "killer_xuid": [p.killer_xuid for p in kv_pairs],
                        "killer_gamertag": [p.killer_gamertag or "?" for p in kv_pairs],
                        "victim_xuid": [p.victim_xuid for p in kv_pairs],
                        "victim_gamertag": [p.victim_gamertag or "?" for p in kv_pairs],
                        "kill_count": [1] * len(kv_pairs),
                        "time_ms": [p.time_ms for p in kv_pairs],
                    }
                )
        except Exception:
            pass

    if pairs_df is not None and not (hasattr(pairs_df, "is_empty") and pairs_df.is_empty()):
        try:
            import polars as pl

            from src.visualization.antagonist_charts import plot_killer_victim_stacked_bars

            # Enrichir les libellés avec la même résolution que le roster (gt_map, BOT_MAP, alias)
            killer_displays = [
                _display_name_for_chart(row[0], row[1], gt_map)
                for row in pairs_df.select("killer_xuid", "killer_gamertag").iter_rows()
            ]
            victim_displays = [
                _display_name_for_chart(row[0], row[1], gt_map)
                for row in pairs_df.select("victim_xuid", "victim_gamertag").iter_rows()
            ]
            pairs_df = pairs_df.with_columns(
                pl.Series("killer_gamertag", killer_displays),
                pl.Series("victim_gamertag", victim_displays),
            )

            # Rangs pour tri des lignes (match_participants après backfill)
            official_stats = _load_match_players_stats(db_path, match_id.strip())
            rank_by_xuid = (
                {s["xuid"]: s["rank"] for s in official_stats} if official_stats else None
            )

            me_xuid = str(
                parse_xuid_input(str(xuid or "").strip()) or str(xuid or "").strip()
            ).strip()
            fig = plot_killer_victim_stacked_bars(
                pairs_df,
                match_id=match_id,
                me_xuid=me_xuid,
                rank_by_xuid=rank_by_xuid,
                title="Interactions Killer-Victim (match)",
                height=400,
            )
            st.plotly_chart(fig, width="stretch")
        except Exception:
            pass


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
        st.info(
            "Roster indisponible pour ce match (payload MatchStats manquant ou équipe introuvable)."
        )
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
        is_self = bool(me_xu and xu and (str(parse_xuid_input(xu) or xu).strip() == me_xu)) or bool(
            r.get("is_me")
        )
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
