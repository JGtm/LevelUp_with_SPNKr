"""Page Médias – grille par sections, carte + date, bouton Ouvrir le match (Sprint 5)."""

from __future__ import annotations

import hashlib
import urllib.parse
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


# Ratio 16:9 pour toutes les cartes (grille alignée)
MEDIA_THUMB_RATIO_W = 320
MEDIA_THUMB_RATIO_H = 180  # 320 * 9 / 16
MEDIA_THUMB_IFRAME_H = MEDIA_THUMB_RATIO_H + 24


def _render_media_grid(
    df: pl.DataFrame,
    *,
    cols_per_row: int = 4,
    thumb_width: int = 200,
    thumb_height: int = 200,
) -> None:
    """Affiche une grille de cartes média (carte + date, thumbnail, bouton match). Ratio 16:9."""
    if df.is_empty():
        return
    thumb_width = max(thumb_width, MEDIA_THUMB_RATIO_W)
    thumb_height = max(thumb_height, MEDIA_THUMB_RATIO_H)
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
                    # Thumbnail : ratio 16:9
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
                            height_iframe=MEDIA_THUMB_IFRAME_H,
                        )
                    else:
                        st.caption(f"Fichier absent : {file_name}")
                    # Bouton « Voir en grand » (lightbox en dialog Streamlit, le clic dans l'iframe ne pouvant pas ouvrir en plein écran)
                    if static_path and Path(static_path).exists():
                        lb_key = hashlib.md5(f"lightbox_{file_path}_{i}_{j}".encode()).hexdigest()[
                            :16
                        ]
                        if st.button("Voir en grand", key=f"media_lb_{lb_key}", width="stretch"):
                            st.session_state["_lightbox_media_path"] = file_path
                            st.session_state["_lightbox_media_kind"] = kind
                            st.rerun()
                    # Lien « Ouvrir le match » (nouvel onglet du navigateur)
                    if match_id and str(match_id).strip():
                        mid = str(match_id).strip()
                        match_url = "?" + urllib.parse.urlencode({"page": "Match", "match_id": mid})
                        st.markdown(
                            f'<a href="{match_url}" target="_blank" rel="noopener noreferrer" '
                            'style="display:block;width:100%;text-align:center;padding:0.35em 0.75em;margin-top:4px;'
                            "background:#1a73e8;color:#fff;text-decoration:none;border-radius:4px;"
                            'font-size:0.9em;">Ouvrir le match</a>',
                            unsafe_allow_html=True,
                        )


def render_media_tab(
    *,
    df_full: pl.DataFrame | None = None,
    settings: AppSettings | None = None,
) -> None:
    """Rend la page Médias : sections Mes captures, Captures de XXX, Sans correspondance."""
    st.subheader("Médias")

    # Lightbox « Voir en grand » : traiter en premier pour que le dialog s'ouvre bien après rerun
    _path = st.session_state.pop("_lightbox_media_path", None)
    _kind = st.session_state.pop("_lightbox_media_kind", "image")
    if _path is not None and Path(_path).exists():

        @st.dialog("Média", width="large")
        def _lightbox_dialog():
            # CSS pour maximiser la largeur sans débordement (cible le contenu du modal)
            st.markdown(
                "<style>"
                "[data-testid='stModal'] > div, [data-testid='stDialog'] > div {"
                "  max-width: 95vw !important; width: 95vw !important;"
                "}"
                "[data-testid='stModal'] img, [data-testid='stModal'] video, "
                "[data-testid='stDialog'] img, [data-testid='stDialog'] video, "
                "[role='dialog'] img, [role='dialog'] video {"
                "  max-width: 100%; width: 100%; height: auto; object-fit: contain;"
                "  max-height: 85vh;"
                "}"
                "</style>",
                unsafe_allow_html=True,
            )
            if _kind == "video":
                st.video(str(_path))
            else:
                st.image(str(_path), width="stretch")

        _lightbox_dialog()

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
            resolve_xuid(xuid_input or identity.xuid_or_gamertag or "", db_path, identity)
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
        mine = mine.unique(subset=["file_path"], keep="first").sort(
            "capture_end_utc", descending=True, nulls_last=True
        )
    if not unassigned.is_empty():
        unassigned = unassigned.unique(subset=["file_path"], keep="first").sort(
            "capture_end_utc", descending=True, nulls_last=True
        )

    # Section « Mes captures » (ratio 16:9) – du plus récent au plus vieux
    st.markdown("### Mes captures")
    if mine.is_empty():
        st.info("Aucune capture détectée.")
    else:
        _render_media_grid(
            mine,
            cols_per_row=cols_per_row,
            thumb_width=MEDIA_THUMB_RATIO_W,
            thumb_height=MEDIA_THUMB_RATIO_H,
        )

    # Section « Captures de XXX » par gamertag
    if not teammate.is_empty():
        for gamertag in teammate["gamertag"].unique().to_list():
            if not gamertag or (isinstance(gamertag, str) and not gamertag.strip()):
                continue
            st.markdown(f"### Captures de {gamertag}")
            sub = teammate.filter(pl.col("gamertag") == gamertag)
            sub = sub.unique(subset=["file_path"], keep="first").sort(
                "capture_end_utc", descending=True, nulls_last=True
            )
            _render_media_grid(
                sub,
                cols_per_row=cols_per_row,
                thumb_width=MEDIA_THUMB_RATIO_W,
                thumb_height=MEDIA_THUMB_RATIO_H,
            )

    # Section « Sans correspondance »
    st.markdown("### Sans correspondance")
    _render_media_grid(
        unassigned,
        cols_per_row=cols_per_row,
        thumb_width=MEDIA_THUMB_RATIO_W,
        thumb_height=MEDIA_THUMB_RATIO_H,
    )
