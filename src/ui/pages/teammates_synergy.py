"""Radars de complémentarité (synergy) pour la page Coéquipiers.

Extraits de teammates.py (Sprint 16 — refactoring Phase A).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import streamlit as st

from src.data.repositories import DuckDBRepository
from src.ui.components.radar_chart import create_participation_profile_radar
from src.visualization._compat import DataFrameLike, ensure_polars
from src.visualization.participation_radar import (
    RADAR_AXIS_LINES,
    compute_participation_profile,
    get_radar_thresholds,
)


def _compute_player_profile(
    repo: DuckDBRepository,
    df_player: DataFrameLike,
    shared_match_ids: list[str],
    name: str,
    color: str,
    thresholds: dict | None,
) -> dict | None:
    """Calcule le profil de participation d'un joueur pour le radar.

    Args:
        repo: Repository DuckDB ouvert.
        df_player: DataFrame des matchs du joueur.
        shared_match_ids: IDs des matchs partagés.
        name: Nom du joueur.
        color: Couleur assignée.
        thresholds: Seuils radar (ou None).

    Returns:
        Profil dict ou None si données indisponibles.
    """
    df_player = ensure_polars(df_player)
    if not repo.has_personal_score_awards():
        return None

    ps = repo.load_personal_score_awards_as_polars(match_ids=shared_match_ids)
    if ps.is_empty():
        return None

    match_row = {
        "deaths": int(df_player["deaths"].sum()) if "deaths" in df_player.columns else 0,
        "time_played_seconds": float(df_player["time_played_seconds"].sum())
        if "time_played_seconds" in df_player.columns
        else 600.0 * len(df_player),
        "pair_name": df_player["pair_name"].item(0)
        if "pair_name" in df_player.columns and len(df_player) > 0
        else None,
    }
    return compute_participation_profile(
        ps,
        match_row=match_row,
        name=name,
        color=color,
        pair_name=match_row.get("pair_name"),
        thresholds=thresholds,
    )


def _render_radar_display(
    profiles: list[dict],
    title: str = "🤝 Complémentarité",
) -> None:
    """Affiche le radar et la légende des axes."""
    if not profiles:
        st.subheader(title)
        st.info("Données de participation indisponibles (PersonalScores manquants).")
        return

    st.subheader(title)
    col_radar, col_legend = st.columns([2, 1])
    with col_radar:
        try:
            fig = create_participation_profile_radar(
                profiles,
                title="Profil de participation",
                height=380,
            )
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Impossible de générer le radar de participation.")
        except Exception as e:
            st.warning(f"Impossible d'afficher le radar de participation : {e}")
    with col_legend:
        st.markdown("**Axes**")
        for line in RADAR_AXIS_LINES:
            st.markdown(line)


def render_synergy_radar(
    sub: DataFrameLike,
    friend_sub: DataFrameLike,
    me_name: str,
    friend_name: str,
    colors_by_name: dict[str, str],
    *,
    db_path: str | None = None,
    xuid: str | None = None,
    friend_xuid: str | None = None,
) -> None:
    """Affiche le radar de complémentarité (6 axes) entre moi et un coéquipier.

    Objectifs, Combat, Support, Score, Impact, Survie.
    Utilise PersonalScores depuis ma DB et la DB du coéquipier.
    """
    sub = ensure_polars(sub)
    friend_sub = ensure_polars(friend_sub)
    if sub.is_empty() or friend_sub.is_empty():
        return

    if db_path is None:
        db_path = st.session_state.get("db_path", "")
    if xuid is None:
        xuid = st.session_state.get("xuid", "")

    shared_match_ids = list(
        set(sub["match_id"].cast(pl.Utf8).to_list())
        & set(friend_sub["match_id"].cast(pl.Utf8).to_list())
    )
    if not shared_match_ids:
        return

    thresholds = get_radar_thresholds(db_path) if db_path else None
    profiles: list[dict] = []

    # Mon profil
    try:
        repo = DuckDBRepository(db_path, xuid or "")
        profile = _compute_player_profile(
            repo,
            sub,
            shared_match_ids,
            me_name,
            colors_by_name.get(me_name, "#636EFA"),
            thresholds,
        )
        if profile:
            profiles.append(profile)
    except Exception:
        pass

    # Profil du coéquipier (depuis sa DB)
    base_dir = Path(db_path).parent.parent
    friend_db_path = base_dir / friend_name / "stats.duckdb"
    if friend_db_path.exists():
        try:
            friend_repo = DuckDBRepository(str(friend_db_path), "")
            profile = _compute_player_profile(
                friend_repo,
                friend_sub,
                shared_match_ids,
                friend_name,
                colors_by_name.get(friend_name, "#EF553B"),
                thresholds,
            )
            if profile:
                profiles.append(profile)
        except Exception:
            pass

    _render_radar_display(profiles)


def render_trio_synergy_radar(
    me_df: DataFrameLike,
    f1_df: DataFrameLike,
    f2_df: DataFrameLike,
    me_name: str,
    f1_name: str,
    f2_name: str,
    colors_by_name: dict[str, str],
    *,
    db_path: str | None = None,
) -> None:
    """Radar complémentarité trio (6 axes) : moi + 2 coéquipiers."""
    me_df = ensure_polars(me_df)
    f1_df = ensure_polars(f1_df)
    f2_df = ensure_polars(f2_df)
    if me_df.is_empty():
        return

    if db_path is None:
        db_path = st.session_state.get("db_path", "")

    shared_match_ids = list(
        set(me_df["match_id"].cast(pl.Utf8).to_list())
        & set(f1_df["match_id"].cast(pl.Utf8).to_list())
        & set(f2_df["match_id"].cast(pl.Utf8).to_list())
    )
    if not shared_match_ids:
        return

    thresholds = get_radar_thresholds(db_path) if db_path else None
    base_dir = Path(db_path).parent.parent
    profiles: list[dict] = []

    players = [
        (me_name, me_df, db_path, colors_by_name.get(me_name, "#636EFA")),
        (
            f1_name,
            f1_df,
            str(base_dir / f1_name / "stats.duckdb"),
            colors_by_name.get(f1_name, "#EF553B"),
        ),
        (
            f2_name,
            f2_df,
            str(base_dir / f2_name / "stats.duckdb"),
            colors_by_name.get(f2_name, "#00CC96"),
        ),
    ]

    for name, df_player, player_db, color in players:
        if ensure_polars(df_player).is_empty() or not Path(player_db).exists():
            continue
        try:
            repo = DuckDBRepository(player_db, "")
            profile = _compute_player_profile(
                repo,
                df_player,
                shared_match_ids,
                name,
                color,
                thresholds,
            )
            if profile:
                profiles.append(profile)
        except Exception:
            pass

    _render_radar_display(profiles, title="Complémentarité trio")
