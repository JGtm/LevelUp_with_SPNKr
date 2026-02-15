"""Helpers génériques pour la page Match View."""

from __future__ import annotations

import html
import os
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import streamlit as st

from src.config import get_repo_root
from src.ui import AppSettings

# =============================================================================
# Utilitaires de conversion date/heure
# =============================================================================


def to_paris_naive_local(dt_value, paris_tz) -> datetime | None:
    """Convertit une date en datetime naïf (sans tzinfo) en heure de Paris."""
    if dt_value is None:
        return None
    try:
        if isinstance(dt_value, datetime):
            ts = dt_value
        elif isinstance(dt_value, str):
            ts = datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
        elif hasattr(dt_value, "to_pydatetime"):
            # pd.Timestamp / np.datetime64 (tolérance migration)
            ts = dt_value.to_pydatetime()
        else:
            ts = datetime.fromisoformat(str(dt_value).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            return ts
        return ts.astimezone(paris_tz).replace(tzinfo=None)
    except Exception:
        return None


def safe_dt(v, paris_tz) -> datetime | None:
    """Alias pour to_paris_naive_local."""
    return to_paris_naive_local(v, paris_tz)


def match_time_window(
    row: dict[str, Any], *, tolerance_minutes: int, paris_tz
) -> tuple[datetime | None, datetime | None, bool]:
    """Calcule la fenêtre temporelle d'un match avec tolérance.

    Returns:
        Tuple (start_window, end_window, duration_known):
        - start_window: début de fenêtre (start_time - tolérance)
        - end_window: fin de fenêtre (end_time + tolérance)
        - duration_known: True si la durée réelle du match a été utilisée
    """
    start = safe_dt(row.get("start_time"), paris_tz)
    if start is None:
        return None, None, False

    dur_s = row.get("time_played_seconds")
    duration_known = False
    try:
        dur = float(dur_s) if dur_s == dur_s else None
    except Exception:
        dur = None

    if dur is not None and dur > 0:
        # Durée réelle du match disponible
        end = start + timedelta(seconds=float(dur))
        duration_known = True
    else:
        # Fallback: durée typique d'un match (~12 min au lieu de 30)
        end = start + timedelta(minutes=12)

    tol = max(0, int(tolerance_minutes))
    return start - timedelta(minutes=tol), end + timedelta(minutes=tol), duration_known


def paris_epoch_seconds_local(dt: datetime | None, paris_tz) -> float | None:
    """Convertit un datetime naïf Paris en epoch seconds."""
    if dt is None:
        return None
    try:
        aware = paris_tz.localize(dt) if dt.tzinfo is None else dt
        return aware.timestamp()
    except Exception:
        return None


# =============================================================================
# Indexation des médias
# =============================================================================


@st.cache_data(show_spinner=False, ttl=120)
def index_media_dir(dir_path: str, exts: tuple[str, ...]) -> pl.DataFrame:
    """Indexe un répertoire de médias par extension et date de modification."""
    _empty = pl.DataFrame(schema={"path": pl.Utf8, "mtime": pl.Float64, "ext": pl.Utf8})
    rows: list[dict[str, object]] = []
    p = str(dir_path or "").strip()
    if not p or not os.path.isdir(p):
        return _empty

    wanted = {e.lower().lstrip(".") for e in (exts or ()) if isinstance(e, str) and e.strip()}
    if not wanted:
        return _empty

    max_files = 12000
    try:
        for root, _dirs, files in os.walk(p):
            for fn in files:
                if len(rows) >= max_files:
                    break
                ext = os.path.splitext(fn)[1].lower().lstrip(".")
                if ext not in wanted:
                    continue
                full = os.path.join(root, fn)
                try:
                    st_ = os.stat(full)
                    mtime = float(st_.st_mtime)
                except Exception:
                    continue
                rows.append({"path": full, "mtime": mtime, "ext": ext})
            if len(rows) >= max_files:
                break
    except Exception:
        return _empty

    df = pl.DataFrame(rows)
    if df.is_empty():
        return df
    return df.sort("mtime", descending=True)


# =============================================================================
# Rendu de la section médias
# =============================================================================


def render_media_section(
    *,
    row: dict[str, Any],
    settings: AppSettings,
    format_datetime_fn: Callable[[datetime | None], str],
    paris_tz,
) -> None:
    """Rend la section médias (captures/vidéos) pour un match."""
    if not bool(getattr(settings, "media_enabled", True)):
        return

    tol = int(getattr(settings, "media_tolerance_minutes", 0) or 0)
    t0, t1, duration_known = match_time_window(row, tolerance_minutes=tol, paris_tz=paris_tz)
    if t0 is None or t1 is None:
        return

    screens_dir = str(getattr(settings, "media_screens_dir", "") or "").strip()
    videos_dir = str(getattr(settings, "media_videos_dir", "") or "").strip()

    if not screens_dir and not videos_dir:
        return

    st.subheader("Médias")
    # Afficher la fenêtre avec indication si durée exacte ou estimée
    window_info = f"Fenêtre: {format_datetime_fn(t0)} → {format_datetime_fn(t1)}"
    if not duration_known:
        window_info += " *(durée estimée)*"
    st.caption(window_info)

    try:
        t0_epoch = t0.timestamp() if t0 else None
        t1_epoch = t1.timestamp() if t1 else None
    except Exception:
        t0_epoch = t1_epoch = None

    if t0_epoch is None or t1_epoch is None:
        return

    found_any = False

    if screens_dir and os.path.isdir(screens_dir):
        img_df = index_media_dir(screens_dir, ("png", "jpg", "jpeg", "webp"))
        if not img_df.is_empty():
            hits = img_df.filter(
                (pl.col("mtime") >= t0_epoch) & (pl.col("mtime") <= t1_epoch)
            ).head(24)
            if not hits.is_empty():
                found_any = True
                st.caption("Captures")
                for p in hits["path"].to_list():
                    try:
                        st.image(p, caption=str(p))
                    except Exception:
                        st.write(str(p))

    if videos_dir and os.path.isdir(videos_dir):
        vid_df = index_media_dir(videos_dir, ("mp4", "webm", "mkv", "mov"))
        if not vid_df.is_empty():
            hits = vid_df.filter(
                (pl.col("mtime") >= t0_epoch) & (pl.col("mtime") <= t1_epoch)
            ).head(10)
            if not hits.is_empty():
                found_any = True
                st.caption("Vidéos")
                paths = [str(p) for p in hits["path"].to_list() if p]
                if paths:
                    labels = [os.path.basename(p) for p in paths]
                    picked = st.selectbox(
                        "Vidéo",
                        options=list(range(len(paths))),
                        format_func=lambda i: labels[i],
                        index=0,
                        key=f"media_video_pick_{row.get('match_id','')}",
                        label_visibility="collapsed",
                    )
                    p = paths[int(picked)]
                    try:
                        st.video(p)
                        st.caption(str(p))
                    except Exception:
                        st.write(str(p))

    if not found_any:
        st.info("Aucun média trouvé pour ce match.")


# =============================================================================
# Composants UI
# =============================================================================


def os_card(
    title: str,
    kpi: str,
    sub_html: str | None = None,
    *,
    accent: str | None = None,
    kpi_color: str | None = None,
    sub_style: str | None = None,
    min_h: int = 112,
) -> None:
    """Rend une carte KPI avec style OpenSpartan."""
    t = html.escape(str(title or ""))
    k = html.escape(str(kpi or "-"))
    s = "" if not sub_html else str(sub_html)
    style = "min-height:" + str(int(min_h)) + "px; margin-bottom:10px;"
    if accent and str(accent).startswith("#"):
        style += f"border-color:{accent}66;"
    kpi_style = (
        "" if not (kpi_color and str(kpi_color).startswith("#")) else f" style='color:{kpi_color}'"
    )
    sub_style_attr = (
        "" if not sub_style else ' style="' + html.escape(str(sub_style), quote=True) + '"'
    )
    st.markdown(
        "<div class='os-card' style='" + style + "'>"
        f"<div class='os-card-title'>{t}</div>"
        f"<div class='os-card-kpi'{kpi_style}>{k}</div>"
        + ("" if not s else f"<div class='os-card-sub'{sub_style_attr}>{s}</div>")
        + "</div>",
        unsafe_allow_html=True,
    )


def map_thumb_path(row: dict[str, Any], map_id: str | None) -> str | None:
    """Trouve le chemin vers la miniature de la carte."""

    def _safe_stem_from_name(name: str | None) -> str:
        s = str(name or "").strip()
        if not s:
            return ""
        s = re.sub(r'[<>:"/\\|?*]', " ", s)
        s = re.sub(r"[\x00-\x1f]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    repo = Path(get_repo_root(__file__))
    base_dirs = [repo / "static" / "maps" / "thumbs", repo / "thumbs"]

    candidates: list[str] = []
    mid = str(map_id or "").strip()
    if mid and mid != "-":
        candidates.append(mid)

    safe_name = _safe_stem_from_name(row.get("map_name"))
    if safe_name:
        candidates.append(safe_name)
        candidates.append(safe_name.replace(" ", "_"))

    uniq: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        if c and c not in seen:
            uniq.append(c)
            seen.add(c)

    for base in base_dirs:
        for stem in uniq:
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                p = base / f"{stem}{ext}"
                if p.exists():
                    return str(p)
    return None


# =============================================================================
# Exports publics
# =============================================================================

__all__ = [
    "to_paris_naive_local",
    "safe_dt",
    "match_time_window",
    "paris_epoch_seconds_local",
    "index_media_dir",
    "render_media_section",
    "os_card",
    "map_thumb_path",
]
