"""Page Match View - Affichage détaillé d'un match.

Ce module a été refactorisé en sous-modules :
- match_view_helpers.py : Utilitaires date/heure, médias, composants UI
- match_view_charts.py : Graphiques Expected vs Actual
- match_view_players.py : Sections Némésis et Roster
"""

from __future__ import annotations

import html
from collections.abc import Callable
from datetime import datetime
from typing import Any

import polars as pl
import streamlit as st

from src.analysis.performance_config import SCORE_THRESHOLDS
from src.analysis.performance_score import compute_relative_performance_score
from src.app.helpers import normalize_map_label
from src.config import HALO_COLORS, OUTCOME_CODES
from src.ui import (
    AppSettings,
    translate_pair_name,
    translate_playlist_name,
)
from src.ui.formatting import format_date_fr
from src.ui.medals import medal_label, render_medals_grid
from src.ui.pages.match_view_charts import render_expected_vs_actual

# Imports depuis les sous-modules
from src.ui.pages.match_view_helpers import (
    map_thumb_path,
    os_card,
    render_media_section,
)
from src.ui.pages.match_view_participation import render_participation_section
from src.ui.pages.match_view_players import (
    render_nemesis_section,
    render_roster_section,
)
from src.visualization._compat import DataFrameLike, ensure_polars

# =============================================================================
# Fonction principale
# =============================================================================


def render_match_view(
    *,
    row: dict[str, Any],
    match_id: str,
    db_path: str,
    xuid: str,
    waypoint_player: str,
    db_key: tuple[int, int] | None,
    settings: AppSettings,
    df_full: DataFrameLike | None = None,
    # Fonctions injectées
    normalize_mode_label_fn: Callable[[str | None], str],
    format_score_label_fn: Callable[[Any, Any], str],
    score_css_color_fn: Callable[[Any, Any], str],
    format_datetime_fn: Callable[[datetime | None], str],
    load_player_match_result_fn: Callable,
    load_match_medals_fn: Callable,
    load_highlight_events_fn: Callable,
    load_match_gamertags_fn: Callable,
    load_match_rosters_fn: Callable,
    paris_tz,
) -> None:
    """Rend la vue détaillée d'un match.

    Parameters
    ----------
    row : dict[str, Any]
        Données du match (dict issu de iter_rows(named=True) ou to_dicts()).
    match_id : str
        Identifiant du match.
    db_path : str
        Chemin vers la base de données.
    xuid : str
        XUID du joueur principal.
    waypoint_player : str
        Gamertag pour les liens Waypoint.
    db_key : tuple[int, int] | None
        Clé de cache pour la base de données.
    settings : AppSettings
        Paramètres de l'application.
    df_full : DataFrameLike | None
        DataFrame complet pour le calcul du score relatif.
    normalize_mode_label_fn, format_score_label_fn, score_css_color_fn, format_datetime_fn
        Fonctions de formatage injectées.
    load_player_match_result_fn, load_match_medals_fn, load_highlight_events_fn,
    load_match_gamertags_fn, load_match_rosters_fn
        Fonctions de chargement de données injectées.
    paris_tz
        Timezone Paris.
    """
    # Normaliser df_full en Polars
    if df_full is not None:
        df_full = ensure_polars(df_full)

    match_id = str(match_id or "").strip()
    if not match_id:
        st.info("MatchId manquant.")
        return

    last_time = row.get("start_time")
    last_map = row.get("map_name")
    last_playlist = row.get("playlist_name")
    last_pair = row.get("pair_name")
    last_mode = row.get("game_variant_name")
    last_outcome = row.get("outcome")

    last_playlist_fr = translate_playlist_name(str(last_playlist)) if last_playlist else None
    last_pair_fr = translate_pair_name(str(last_pair)) if last_pair else None

    outcome_map = {2: "Victoire", 3: "Défaite", 1: "Égalité", 4: "Non terminé"}
    try:
        outcome_code = int(last_outcome) if last_outcome == last_outcome else None
    except Exception:
        outcome_code = None
    outcome_label = outcome_map.get(outcome_code, "?") if outcome_code is not None else "-"

    colors = HALO_COLORS.as_dict()
    if outcome_code == OUTCOME_CODES.WIN:
        outcome_color = colors["green"]
    elif outcome_code == OUTCOME_CODES.LOSS:
        outcome_color = colors["red"]
    elif outcome_code == OUTCOME_CODES.TIE or outcome_code == OUTCOME_CODES.NO_FINISH:
        outcome_color = colors["violet"]
    else:
        outcome_color = colors["slate"]

    last_my_score = row.get("my_team_score")
    last_enemy_score = row.get("enemy_team_score")
    score_label = format_score_label_fn(last_my_score, last_enemy_score)
    _ = score_css_color_fn(last_my_score, last_enemy_score)  # noqa: F841

    wp = str(waypoint_player or "").strip()
    match_url = None
    if wp and match_id and match_id.strip() and match_id.strip() != "-":
        match_url = (
            f"https://www.halowaypoint.com/halo-infinite/players/{wp}/matches/{match_id.strip()}"
        )

    # Calcul du score de performance RELATIF
    perf_score = None
    if df_full is not None and len(df_full) >= 10:
        perf_score = compute_relative_performance_score(row, df_full)
    perf_display = f"{perf_score:.0f}" if perf_score is not None else "-"
    perf_color = None
    if perf_score is not None:
        if perf_score >= SCORE_THRESHOLDS["excellent"]:
            perf_color = colors["green"]
        elif perf_score >= SCORE_THRESHOLDS["good"]:
            perf_color = colors["cyan"]
        elif perf_score >= SCORE_THRESHOLDS["average"]:
            perf_color = colors["amber"]
        elif perf_score >= SCORE_THRESHOLDS["below_average"]:
            perf_color = colors.get("orange", "#FF8C00")
        else:
            perf_color = colors["red"]

    # Cartes KPI - Date, Résultat, Performance
    top_cols = st.columns(3)
    with top_cols[0]:
        os_card("Date", format_date_fr(last_time))
    with top_cols[1]:
        outcome_class = (
            "text-win"
            if "victoire" in str(outcome_label).lower()
            else ("text-loss" if "défaite" in str(outcome_label).lower() else "text-tie")
        )
        os_card(
            "Résultats",
            str(outcome_label),
            f"<span class='{outcome_class} fw-bold'>{html.escape(str(score_label))}</span>",
            accent=str(outcome_color),
            kpi_color=str(outcome_color),
        )
    with top_cols[2]:
        os_card(
            "Performance",
            perf_display,
            "Relatif à ton historique" if perf_score is not None else "Historique insuffisant",
            accent=perf_color,
            kpi_color=perf_color,
        )

    last_mode_ui = row.get("mode_ui") or normalize_mode_label_fn(
        str(last_pair) if last_pair else None
    )

    # Normaliser les labels pour masquer les UUIDs non résolus
    map_display = normalize_map_label(last_map) if last_map else None
    if not map_display:
        map_display = "-"

    playlist_display = (
        last_playlist_fr
        or (translate_playlist_name(str(last_playlist)) if last_playlist else None)
        or "-"
    )
    mode_display = (
        last_mode_ui
        or last_pair_fr
        or (normalize_mode_label_fn(str(last_pair)) if last_pair else None)
        or last_mode
        or "-"
    )

    row_cols = st.columns(3)
    row_cols[0].metric(" ", map_display)
    row_cols[1].metric(" ", playlist_display)
    row_cols[2].metric(" ", mode_display)

    # Miniature de la carte
    map_id = row.get("map_id")
    thumb = map_thumb_path(row, str(map_id) if map_id else None)
    if thumb:
        import contextlib

        c = st.columns([1, 2, 1])
        with c[1], contextlib.suppress(Exception):
            st.image(thumb, width=400)

    # Stats détaillées
    with st.spinner("Lecture des stats détaillées (attendu vs réel, médailles)…"):
        pm = load_player_match_result_fn(db_path, match_id, xuid.strip(), db_key=db_key)
        medals_last = load_match_medals_fn(db_path, match_id, xuid.strip(), db_key=db_key)

    if not pm:
        st.info(
            "Stats détaillées indisponibles pour ce match (PlayerMatchStats manquant ou format inattendu)."
        )
    else:
        # Enrichir pm avec les valeurs réelles depuis row si elles sont manquantes (DuckDB v4)
        if pm.get("kills", {}).get("count") is None:
            kills_val = row.get("kills")
            if kills_val is not None:
                pm.setdefault("kills", {})["count"] = (
                    float(kills_val) if kills_val == kills_val else None
                )
        if pm.get("deaths", {}).get("count") is None:
            deaths_val = row.get("deaths")
            if deaths_val is not None:
                pm.setdefault("deaths", {})["count"] = (
                    float(deaths_val) if deaths_val == deaths_val else None
                )
        if pm.get("assists", {}).get("count") is None:
            assists_val = row.get("assists")
            if assists_val is not None:
                pm.setdefault("assists", {})["count"] = (
                    float(assists_val) if assists_val == assists_val else None
                )

        render_expected_vs_actual(row, pm, colors, df_full=df_full, db_path=db_path, xuid=xuid)

    # Section Participation (PersonalScores) - Radar unifié 6 axes
    render_participation_section(
        db_path=db_path,
        match_id=match_id,
        xuid=xuid,
        db_key=db_key,
        match_row=row,
    )

    # Némésis / Souffre-douleur
    render_nemesis_section(
        match_id=match_id,
        db_path=db_path,
        xuid=xuid,
        db_key=db_key,
        colors=colors,
        load_highlight_events_fn=load_highlight_events_fn,
        load_match_gamertags_fn=load_match_gamertags_fn,
    )

    # Roster
    render_roster_section(
        match_id=match_id,
        db_path=db_path,
        xuid=xuid,
        db_key=db_key,
        load_match_rosters_fn=load_match_rosters_fn,
        load_match_gamertags_fn=load_match_gamertags_fn,
    )

    # Médailles
    st.subheader("Médailles")
    if not medals_last:
        st.info("Médailles indisponibles pour ce match (ou aucune médaille).")
    else:
        md_df = pl.DataFrame(medals_last)
        md_df = md_df.with_columns(
            pl.col("name_id")
            .map_elements(lambda x: medal_label(int(x)), return_dtype=pl.Utf8)
            .alias("label")
        )
        md_df = md_df.sort(["count", "label"], descending=[True, False])
        render_medals_grid(md_df.select(["name_id", "count"]).to_dicts(), cols_per_row=8)

    # Médias
    render_media_section(
        row=row,
        settings=settings,
        format_datetime_fn=format_datetime_fn,
        paris_tz=paris_tz,
    )

    # Lien Waypoint
    if match_url:
        st.link_button("Ouvrir sur HaloWaypoint", match_url, width="stretch")


# =============================================================================
# Exports publics (rétrocompatibilité)
# =============================================================================

# Réexporter les fonctions helpers pour rétrocompatibilité
from src.ui.pages.match_view_charts import (
    render_expected_vs_actual as _render_expected_vs_actual,
)
from src.ui.pages.match_view_helpers import (
    index_media_dir as _index_media_dir,
)
from src.ui.pages.match_view_helpers import (
    map_thumb_path as _map_thumb_path,
)
from src.ui.pages.match_view_helpers import (
    match_time_window as _match_time_window,
)
from src.ui.pages.match_view_helpers import (
    os_card as _os_card,
)
from src.ui.pages.match_view_helpers import (
    paris_epoch_seconds_local as _paris_epoch_seconds_local,
)
from src.ui.pages.match_view_helpers import (
    render_media_section as _render_media_section,
)
from src.ui.pages.match_view_helpers import (
    safe_dt as _safe_dt,
)
from src.ui.pages.match_view_helpers import (
    to_paris_naive_local as _to_paris_naive_local,
)
from src.ui.pages.match_view_players import (
    render_nemesis_section as _render_nemesis_section,
)
from src.ui.pages.match_view_players import (
    render_roster_section as _render_roster_section,
)

__all__ = [
    "render_match_view",
    # Helpers (rétrocompatibilité)
    "_to_paris_naive_local",
    "_safe_dt",
    "_match_time_window",
    "_paris_epoch_seconds_local",
    "_index_media_dir",
    "_render_media_section",
    "_os_card",
    "_map_thumb_path",
    "_render_expected_vs_actual",
    "_render_nemesis_section",
    "_render_roster_section",
]
