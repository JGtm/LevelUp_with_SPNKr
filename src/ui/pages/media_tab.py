"""Page Médias – grille par sections, carte + date, bouton Ouvrir le match (Sprint 5)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import polars as pl
import streamlit as st

from src.data.media_indexer import MediaIndexer
from src.ui.components.media_thumbnail import render_media_thumbnail
from src.ui.settings import AppSettings


def _format_short_date(ts) -> str:
    """Formate un timestamp en date courte (ex. 07/02/26)."""
    if ts is None:
        return ""
    try:
        if hasattr(ts, "strftime"):
            return ts.strftime("%d/%m/%y")
        s = str(ts)
        if " " in s:
            return s.split(" ")[0].replace("-", "/")[-8:]  # yy/mm/dd → dd/mm/yy
        return s[:10] if len(s) >= 10 else s
    except Exception:
        return str(ts)[:10]


def _render_media_grid(
    df: pl.DataFrame,
    *,
    cols_per_row: int = 4,
    thumb_width: int = 200,
    thumb_height: int = 200,
) -> None:
    """Affiche une grille de cartes média (carte + date, thumbnail, bouton match)."""
    if df.is_empty():
        return
    rows = df.to_dicts()
    for i in range(0, len(rows), cols_per_row):
        chunk = rows[i : i + cols_per_row]
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            with col:
                if j < len(chunk):
                    row = chunk[j]
                    file_path = row.get("file_path")
                    file_name = row.get("file_name") or ""
                    map_name = row.get("map_name")
                    capture_end = row.get("capture_end_utc")
                    match_id = row.get("match_id")
                    kind = row.get("kind") or "image"
                    thumbnail_path = row.get("thumbnail_path")
                    # Carte + date au-dessus du thumbnail
                    label = (map_name or "—") + " · " + _format_short_date(capture_end)
                    st.caption(label)
                    # Thumbnail (static = thumbnail_path ou file_path, hover = GIF si vidéo)
                    static_path = thumbnail_path or file_path
                    if static_path and Path(static_path).exists():
                        hover_path = None
                        if kind == "video" and str(thumbnail_path or "").lower().endswith(".gif"):
                            hover_path = thumbnail_path
                        render_media_thumbnail(
                            static_path=Path(static_path),
                            hover_path=Path(hover_path) if hover_path else None,
                            full_media_path=Path(file_path) if file_path else None,
                            kind=kind,
                            width=thumb_width,
                            height=thumb_height,
                            media_id=file_path,
                        )
                    else:
                        st.caption(f"Fichier absent : {file_name}")
                    # Bouton « Ouvrir le match »
                    if match_id and str(match_id).strip():
                        btn_key = hashlib.md5(
                            f"{file_path}_{match_id}_{i}_{j}".encode()
                        ).hexdigest()[:16]
                        if st.button(
                            "Ouvrir le match",
                            key=f"media_btn_{btn_key}",
                            use_container_width=True,
                        ):
                            st.session_state["_pending_page"] = "Match"
                            st.session_state["_pending_match_id"] = str(match_id).strip()
                            st.rerun()


def render_media_tab(
    *,
    df_full: pl.DataFrame | None = None,
    settings: AppSettings | None = None,
) -> None:
    """Rend la page Médias : sections Mes captures, Captures de XXX, Sans correspondance."""
    st.subheader("Médias")

    if not settings:
        settings = AppSettings()
    if not getattr(settings, "media_enabled", True):
        st.info("Les médias sont désactivés dans Paramètres → Médias.")
        return

    db_path = st.session_state.get("db_path", "")
    xuid_input = st.session_state.get("xuid_input", "")

    try:
        from src.app.profile import resolve_xuid
        from src.app.state import get_default_identity
    except ImportError:
        resolve_xuid = None
        get_default_identity = None

    current_xuid = None
    if get_default_identity and resolve_xuid:
        identity = get_default_identity()
        current_xuid = (
            resolve_xuid(xuid_input or identity.gamertag or "", db_path, identity)
            or identity.xuid
            or identity.xuid_fallback
        )

    if not db_path or not str(db_path).endswith(".duckdb"):
        st.info("Sélectionne un profil joueur (DB DuckDB) pour afficher les médias.")
        return

    media_df = MediaIndexer.load_media_for_ui(Path(db_path), current_xuid)
    if media_df.is_empty():
        st.info(
            "Aucun média indexé. Configure les dossiers dans Paramètres → Médias "
            "et lance un scan (ou utilise l’ancien onglet pour indexer)."
        )
        return

    # Filtres
    with st.expander("Filtres", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            kinds = st.multiselect(
                "Type",
                options=["image", "video"],
                default=["image", "video"],
                key="media_tab_kind",
            )
        with c2:
            name_filter = st.text_input(
                "Nom de fichier",
                value="",
                placeholder="ex: 2026-01",
                key="media_tab_name",
            )
        with c3:
            cols_per_row = st.slider(
                "Colonnes",
                min_value=2,
                max_value=6,
                value=4,
                step=1,
                key="media_tab_cols",
            )

    # Appliquer filtres
    if kinds:
        media_df = media_df.filter(pl.col("kind").is_in(kinds))
    if name_filter and name_filter.strip():
        media_df = media_df.filter(
            pl.col("file_name").str.to_lowercase().str.contains(name_filter.strip().lower())
        )

    # Dédupliquer par file_path pour "Mes captures" et "Sans correspondance" (une ligne par média)
    # Pour "Captures de XXX" on garde une ligne par (file_path, gamertag)
    mine = media_df.filter(pl.col("section") == "mine")
    teammate = media_df.filter(pl.col("section") == "teammate")
    unassigned = media_df.filter(pl.col("section") == "unassigned")

    # Une seule ligne par média pour mine et unassigned (prendre la première)
    if not mine.is_empty():
        mine = mine.unique(subset=["file_path"], keep="first")
    if not unassigned.is_empty():
        unassigned = unassigned.unique(subset=["file_path"], keep="first")

    thumb_width = 200
    thumb_height = 200

    # Section « Mes captures »
    st.markdown("### Mes captures")
    _render_media_grid(
        mine, cols_per_row=cols_per_row, thumb_width=thumb_width, thumb_height=thumb_height
    )

    # Section « Captures de XXX » par gamertag
    if not teammate.is_empty():
        for gamertag in teammate["gamertag"].unique().to_list():
            if not gamertag or (isinstance(gamertag, str) and not gamertag.strip()):
                continue
            st.markdown(f"### Captures de {gamertag}")
            sub = teammate.filter(pl.col("gamertag") == gamertag)
            sub = sub.unique(subset=["file_path"], keep="first")
            _render_media_grid(
                sub,
                cols_per_row=cols_per_row,
                thumb_width=thumb_width,
                thumb_height=thumb_height,
            )

    # Section « Sans correspondance »
    st.markdown("### Sans correspondance")
    _render_media_grid(
        unassigned,
        cols_per_row=cols_per_row,
        thumb_width=thumb_width,
        thumb_height=thumb_height,
    )
