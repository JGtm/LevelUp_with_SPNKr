"""Pages Dernier match et Match (recherche).

Ce module contient les fonctions de rendu pour :
- La page "Dernier match" (dernière partie selon les filtres)
- La page "Match" (recherche par MatchId, date/heure ou sélection rapide)
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time
from typing import TYPE_CHECKING

import polars as pl
import streamlit as st

from src.visualization._compat import DataFrameLike, ensure_polars

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from src.ui.settings import AppSettings


def render_last_match_page(
    dff: DataFrameLike,
    db_path: str,
    xuid: str,
    waypoint_player: str,
    db_key: tuple[int, int] | None,
    settings: AppSettings,
    df_full: DataFrameLike | None,
    render_match_view_fn: Callable,
    normalize_mode_label_fn: Callable[[str | None], str | None],
    format_score_label_fn: Callable,
    score_css_color_fn: Callable,
    format_datetime_fn: Callable,
    load_player_match_result_fn: Callable,
    load_match_medals_fn: Callable,
    load_highlight_events_fn: Callable,
    load_match_gamertags_fn: Callable,
    load_match_rosters_fn: Callable,
    paris_tz: ZoneInfo,
) -> None:
    """Rend la page Dernier match.

    Affiche la dernière partie selon la sélection/filtres actuels.

    Args:
        dff: DataFrame filtré des matchs.
        db_path: Chemin vers la base de données.
        xuid: XUID du joueur.
        waypoint_player: Nom du joueur Waypoint.
        db_key: Clé de cache de la DB.
        settings: Paramètres de l'application.
        df_full: DataFrame complet pour le calcul du score relatif.
        render_match_view_fn: Fonction de rendu du match.
        normalize_mode_label_fn: Fonction de normalisation du label de mode.
        format_score_label_fn: Fonction de formatage du score.
        score_css_color_fn: Fonction de couleur CSS du score.
        format_datetime_fn: Fonction de formatage date/heure.
        load_player_match_result_fn: Fonction de chargement du résultat joueur.
        load_match_medals_fn: Fonction de chargement des médailles.
        load_highlight_events_fn: Fonction de chargement des événements.
        load_match_gamertags_fn: Fonction de chargement des gamertags.
        load_match_rosters_fn: Fonction de chargement des rosters.
        paris_tz: Timezone Paris.
    """
    st.caption("Dernière partie selon la sélection/filtres actuels.")

    dff = ensure_polars(dff)
    if dff.is_empty():
        st.info("Aucun match disponible avec les filtres actuels.")
        return

    last_row = dff.sort("start_time").row(-1, named=True)
    last_match_id = str(last_row.get("match_id", "")).strip()

    render_match_view_fn(
        row=last_row,
        match_id=last_match_id,
        db_path=db_path,
        xuid=xuid,
        waypoint_player=waypoint_player,
        db_key=db_key,
        settings=settings,
        df_full=df_full,
        normalize_mode_label_fn=normalize_mode_label_fn,
        format_score_label_fn=format_score_label_fn,
        score_css_color_fn=score_css_color_fn,
        format_datetime_fn=format_datetime_fn,
        load_player_match_result_fn=load_player_match_result_fn,
        load_match_medals_fn=load_match_medals_fn,
        load_highlight_events_fn=load_highlight_events_fn,
        load_match_gamertags_fn=load_match_gamertags_fn,
        load_match_rosters_fn=load_match_rosters_fn,
        paris_tz=paris_tz,
    )


def render_match_search_page(
    df: DataFrameLike,
    dff: DataFrameLike,
    db_path: str,
    xuid: str,
    waypoint_player: str,
    db_key: tuple[int, int] | None,
    settings: AppSettings,
    df_full: DataFrameLike | None,
    render_match_view_fn: Callable,
    normalize_mode_label_fn: Callable[[str | None], str | None],
    format_score_label_fn: Callable,
    score_css_color_fn: Callable,
    format_datetime_fn: Callable,
    load_player_match_result_fn: Callable,
    load_match_medals_fn: Callable,
    load_highlight_events_fn: Callable,
    load_match_gamertags_fn: Callable,
    load_match_rosters_fn: Callable,
    paris_tz: ZoneInfo,
) -> None:
    """Rend la page Match (recherche).

    Permet de rechercher un match par MatchId, date/heure ou sélection rapide.

    Args:
        df: DataFrame complet des matchs (non filtré).
        dff: DataFrame filtré des matchs.
        db_path: Chemin vers la base de données.
        xuid: XUID du joueur.
        waypoint_player: Nom du joueur Waypoint.
        db_key: Clé de cache de la DB.
        settings: Paramètres de l'application.
        df_full: DataFrame complet pour le calcul du score relatif.
        render_match_view_fn: Fonction de rendu du match.
        normalize_mode_label_fn: Fonction de normalisation du label de mode.
        format_score_label_fn: Fonction de formatage du score.
        score_css_color_fn: Fonction de couleur CSS du score.
        format_datetime_fn: Fonction de formatage date/heure.
        load_player_match_result_fn: Fonction de chargement du résultat joueur.
        load_match_medals_fn: Fonction de chargement des médailles.
        load_highlight_events_fn: Fonction de chargement des événements.
        load_match_gamertags_fn: Fonction de chargement des gamertags.
        load_match_rosters_fn: Fonction de chargement des rosters.
        paris_tz: Timezone Paris.
    """
    st.caption("Afficher un match précis via un MatchId, une date/heure, ou une sélection.")

    df = ensure_polars(df)
    dff = ensure_polars(dff)

    # Entrée MatchId
    match_id_input = st.text_input("MatchId", key="match_id_input")

    # Sélection rapide (sur les filtres actuels, triés du plus récent au plus ancien)
    quick_df = dff.sort("start_time", descending=True).head(200)
    quick_df = quick_df.with_columns(
        pl.col("start_time")
        .map_elements(format_datetime_fn, return_dtype=pl.Utf8)
        .alias("start_time_fr"),
    )
    if "mode_ui" not in quick_df.columns:
        quick_df = quick_df.with_columns(
            pl.col("pair_name")
            .map_elements(normalize_mode_label_fn, return_dtype=pl.Utf8)
            .alias("mode_ui"),
        )
    quick_df = quick_df.with_columns(
        (
            pl.col("start_time_fr").cast(pl.Utf8)
            + " — "
            + pl.col("map_name").cast(pl.Utf8)
            + " — "
            + pl.col("mode_ui").cast(pl.Utf8)
        ).alias("label"),
    )
    opts = {row["label"]: str(row["match_id"]) for row in quick_df.iter_rows(named=True)}
    st.selectbox(
        "Sélection rapide (filtres actuels)",
        options=["(aucun)"] + list(opts.keys()),
        index=0,
        key="match_quick_pick_label",
    )

    def _on_use_quick_match() -> None:
        picked = st.session_state.get("match_quick_pick_label")
        if isinstance(picked, str) and picked in opts:
            st.session_state["match_id_input"] = opts[picked]

    st.button("Utiliser ce match", width="stretch", on_click=_on_use_quick_match)

    # Recherche par date/heure
    with st.expander("Recherche par date/heure", expanded=False):
        dd = st.date_input("Date", value=date.today(), format="DD/MM/YYYY")
        tt = st.time_input("Heure", value=time(20, 0))
        tol_min = st.slider("Tolérance (minutes)", 0, 30, 10, 1)

        def _on_search_by_datetime() -> None:
            target = datetime.combine(dd, tt)
            # Conversion datetime si la colonne est en string
            if df.schema.get("start_time") == pl.Utf8:
                all_df = df.with_columns(
                    pl.col("start_time").str.to_datetime(strict=False).alias("_dt"),
                )
            else:
                all_df = df.with_columns(
                    pl.col("start_time").alias("_dt"),
                )
            all_df = all_df.drop_nulls(subset=["_dt"])
            if all_df.is_empty():
                st.warning("Aucune date exploitable dans la DB.")
                return

            all_df = all_df.with_columns(
                (pl.col("_dt").cast(pl.Datetime("us")) - pl.lit(target)).abs().alias("_diff"),
            )
            best = all_df.sort("_diff").row(0, named=True)
            diff_min = float(best["_diff"].total_seconds() / 60.0)
            if diff_min <= float(tol_min):
                st.session_state["match_id_input"] = str(best.get("match_id") or "").strip()
            else:
                st.warning(
                    f"Aucun match trouvé dans ±{tol_min} min (le plus proche est à {diff_min:.1f} min)."
                )

        st.button("Rechercher", width="stretch", on_click=_on_search_by_datetime)

    mid = str(match_id_input or "").strip()
    if not mid:
        st.info("Renseigne un MatchId ou utilise la sélection/recherche ci-dessus.")
    else:
        rows = df.filter(pl.col("match_id").cast(pl.Utf8) == mid)
        if rows.is_empty():
            st.warning("MatchId introuvable dans la DB actuelle.")
        else:
            match_row = rows.sort("start_time").row(-1, named=True)
            render_match_view_fn(
                row=match_row,
                match_id=mid,
                db_path=db_path,
                xuid=xuid,
                waypoint_player=waypoint_player,
                db_key=db_key,
                settings=settings,
                df_full=df_full,
                normalize_mode_label_fn=normalize_mode_label_fn,
                format_score_label_fn=format_score_label_fn,
                score_css_color_fn=score_css_color_fn,
                format_datetime_fn=format_datetime_fn,
                load_player_match_result_fn=load_player_match_result_fn,
                load_match_medals_fn=load_match_medals_fn,
                load_highlight_events_fn=load_highlight_events_fn,
                load_match_gamertags_fn=load_match_gamertags_fn,
                load_match_rosters_fn=load_match_rosters_fn,
                paris_tz=paris_tz,
            )
