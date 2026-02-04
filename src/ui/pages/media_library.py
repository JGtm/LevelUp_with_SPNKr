"""Page Bibliothèque médias.

Objectif: proposer une vue "bibliothèque" qui scanne les dossiers de médias
(configurés dans les paramètres) et permet d'ouvrir rapidement le match associé.

L'association média → match se fait par proximité temporelle:
- on indexe les fichiers (mtime)
- on calcule pour chaque match une fenêtre [start - tol ; end + tol]
- on associe un média au match dont la fenêtre contient son mtime

Note: cette page ne dépend pas de métadonnées dans les noms de fichiers.
"""

from __future__ import annotations

import contextlib
import html
import os
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from src.ui.formatting import PARIS_TZ, format_datetime_fr_hm
from src.ui.pages.match_view_helpers import index_media_dir
from src.ui.settings import AppSettings


@dataclass(frozen=True)
class _MediaDirs:
    screens_dir: str
    videos_dir: str


def _coerce_dirs(settings: AppSettings) -> _MediaDirs:
    screens_dir = str(getattr(settings, "media_screens_dir", "") or "").strip()
    videos_dir = str(getattr(settings, "media_videos_dir", "") or "").strip()
    return _MediaDirs(screens_dir=screens_dir, videos_dir=videos_dir)


def _build_app_url(page: str, **params: str) -> str:
    qp: dict[str, str] = {"page": str(page)}
    for k, v in params.items():
        s = str(v or "").strip()
        if s:
            qp[str(k)] = s
    return "?" + urllib.parse.urlencode(qp)


def _open_match_button(match_id: str) -> None:
    mid = str(match_id or "").strip()
    if not mid:
        st.caption("Match inconnu")
        return

    url = _build_app_url("Match", match_id=mid)
    safe_url = html.escape(url, quote=True)
    st.markdown(
        f"""
        <a href="{safe_url}" target="_blank" rel="noopener noreferrer"
           style="display:block;text-align:center;padding:6px 10px;border-radius:10px;
                  border:1px solid rgba(255,255,255,0.18);text-decoration:none;"
        >Ouvrir le match</a>
        """,
        unsafe_allow_html=True,
    )


def _epoch_seconds_paris(dt_value: datetime | None) -> float | None:
    if dt_value is None:
        return None
    try:
        aware = (
            PARIS_TZ.localize(dt_value)
            if dt_value.tzinfo is None
            else dt_value.astimezone(PARIS_TZ)
        )
        return float(aware.timestamp())
    except Exception:
        return None


def _to_paris_naive(dt_value: object) -> datetime | None:
    try:
        ts = pd.to_datetime(dt_value, errors="coerce")
        if pd.isna(ts):
            return None
        if getattr(ts, "tzinfo", None) is None:
            return ts.to_pydatetime()
        return ts.tz_convert(PARIS_TZ).tz_localize(None).to_pydatetime()
    except Exception:
        return None


def _compute_match_windows(df_full: pd.DataFrame, settings: AppSettings) -> pd.DataFrame:
    """Construit les fenêtres temporelles des matchs (epoch seconds) pour l'association média.

    Améliorations:
    - Gère les start_time NULL avec un diagnostic
    - Utilise une durée par défaut de 12 minutes si time_played_seconds est NULL
    """
    if df_full is None or df_full.empty:
        return pd.DataFrame(columns=["match_id", "start_epoch", "end_epoch", "start_time"])

    tol_min = int(getattr(settings, "media_tolerance_minutes", 0) or 0)
    tol = timedelta(minutes=max(0, tol_min))

    cols = [c for c in ["match_id", "start_time", "time_played_seconds"] if c in df_full.columns]
    if "match_id" not in cols or "start_time" not in cols:
        return pd.DataFrame(columns=["match_id", "start_epoch", "end_epoch", "start_time"])

    base = df_full[cols].copy()

    # Filtrer les matchs avec start_time NULL pour diagnostic (mais ne pas les exclure complètement)
    # On les exclura seulement à la fin si on ne peut pas créer de fenêtre valide
    base["_start"] = base["start_time"].apply(_to_paris_naive)

    def _end_from_row(r: pd.Series) -> datetime | None:
        start = r.get("_start")
        if not isinstance(start, datetime):
            return None
        dur_s = r.get("time_played_seconds")
        try:
            dur = float(dur_s) if dur_s == dur_s else None
        except Exception:
            dur = None
        if dur is None or dur <= 0:
            # Fallback: durée typique d'un match (~12 min au lieu de 30)
            return start + timedelta(minutes=12)
        return start + timedelta(seconds=float(dur))

    base["_end"] = base.apply(_end_from_row, axis=1)
    base["_t0"] = base["_start"].apply(lambda d: (d - tol) if isinstance(d, datetime) else None)
    base["_t1"] = base["_end"].apply(lambda d: (d + tol) if isinstance(d, datetime) else None)

    base["start_epoch"] = base["_t0"].apply(_epoch_seconds_paris)
    base["end_epoch"] = base["_t1"].apply(_epoch_seconds_paris)

    out = base[["match_id", "start_epoch", "end_epoch", "_start"]].rename(
        columns={"_start": "start_time"}
    )
    # Exclure uniquement les lignes où on ne peut pas créer de fenêtre valide
    out = out.dropna(subset=["match_id", "start_epoch", "end_epoch"]).copy()
    if out.empty:
        return pd.DataFrame(columns=["match_id", "start_epoch", "end_epoch", "start_time"])

    out["match_id"] = out["match_id"].astype(str)
    out = out.sort_values("start_epoch", ascending=True).reset_index(drop=True)
    return out


def _index_all_media(settings: AppSettings) -> pd.DataFrame:
    """Indexe les médias configurés (captures + vidéos)."""
    dirs = _coerce_dirs(settings)
    frames: list[pd.DataFrame] = []

    if dirs.screens_dir and os.path.isdir(dirs.screens_dir):
        img_df = index_media_dir(dirs.screens_dir, ("png", "jpg", "jpeg", "webp"))
        if not img_df.empty:
            img_df = img_df.copy()
            img_df["kind"] = "image"
            frames.append(img_df)

    if dirs.videos_dir and os.path.isdir(dirs.videos_dir):
        vid_df = index_media_dir(dirs.videos_dir, ("mp4", "webm", "mkv", "mov"))
        if not vid_df.empty:
            vid_df = vid_df.copy()
            vid_df["kind"] = "video"
            frames.append(vid_df)

    if not frames:
        return pd.DataFrame(columns=["path", "mtime", "ext", "kind"])

    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        return df

    df["path"] = df["path"].astype(str)
    df["basename"] = df["path"].apply(lambda p: os.path.basename(str(p)))
    df["mtime"] = pd.to_numeric(df["mtime"], errors="coerce")
    df = df.dropna(subset=["mtime"]).copy()
    return df.sort_values("mtime", ascending=False).reset_index(drop=True)


def _associate_media_to_matches(media_df: pd.DataFrame, windows_df: pd.DataFrame) -> pd.DataFrame:
    """Associe chaque média à un match (best-effort) via merge_asof + check de fenêtre.

    Amélioration: utilise direction="nearest" pour capturer les médias pris
    légèrement AVANT le match (ex: pendant le chargement) ou APRÈS.
    Vérifie ensuite que le média est bien dans la fenêtre [start_epoch, end_epoch].
    """
    if media_df is None or media_df.empty:
        return (
            pd.DataFrame(columns=list(media_df.columns) + ["match_id", "match_start_time"])
            if media_df is not None
            else pd.DataFrame()
        )
    if windows_df is None or windows_df.empty:
        out = media_df.copy()
        out["match_id"] = None
        out["match_start_time"] = None
        return out

    m = media_df.copy()
    m["mtime"] = pd.to_numeric(m["mtime"], errors="coerce")
    m = m.dropna(subset=["mtime"]).copy()

    m_sorted = m.sort_values("mtime", ascending=True)
    w_sorted = windows_df.sort_values("start_epoch", ascending=True)

    # Utiliser direction="nearest" pour trouver le match le plus proche
    # Cela permet de capturer les médias pris avant le début officiel du match
    joined = pd.merge_asof(
        m_sorted,
        w_sorted,
        left_on="mtime",
        right_on="start_epoch",
        direction="nearest",
        allow_exact_matches=True,
    )

    # Vérifier que le média est dans la fenêtre [start_epoch, end_epoch]
    ok_mask = (
        (joined["start_epoch"].notna())
        & (joined["end_epoch"].notna())
        & (joined["mtime"] >= joined["start_epoch"])
        & (joined["mtime"] <= joined["end_epoch"])
    )
    joined.loc[~ok_mask, "match_id"] = None
    joined.loc[~ok_mask, "start_time"] = None

    joined = joined.rename(columns={"start_time": "match_start_time"})
    joined = joined.drop(
        columns=[c for c in ["start_epoch", "end_epoch"] if c in joined.columns], errors="ignore"
    )
    return joined.sort_values("mtime", ascending=False).reset_index(drop=True)


def _render_media_grid(items: pd.DataFrame, *, cols_per_row: int) -> None:
    if items is None or items.empty:
        st.info("Aucun média à afficher avec ces filtres.")
        return

    cols_per_row = int(cols_per_row)
    if cols_per_row < 2:
        cols_per_row = 2
    if cols_per_row > 8:
        cols_per_row = 8

    rows = items.to_dict(orient="records")
    for i in range(0, len(rows), cols_per_row):
        chunk = rows[i : i + cols_per_row]
        cols = st.columns(len(chunk))
        for c, rec in zip(cols, chunk, strict=False):
            with c:
                path = str(rec.get("path") or "").strip()
                kind = str(rec.get("kind") or "")
                base = str(rec.get("basename") or os.path.basename(path))
                mid = rec.get("match_id")

                if kind == "image" and path:
                    try:
                        st.image(path, width="stretch")
                    except Exception:
                        st.caption(base)
                else:
                    st.markdown(
                        "<div style='padding:18px;border-radius:12px;border:1px solid rgba(255,255,255,0.12);'>"
                        "<div style='font-size:34px;line-height:1'>🎬</div>"
                        "<div style='opacity:0.85;margin-top:6px'>" + html.escape(base) + "</div>"
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    if path:
                        preview_key = f"media_preview::{hash(path)}"
                        if st.button("Aperçu", key=preview_key, width="stretch"):
                            st.session_state[preview_key + "::open"] = True
                        if st.session_state.get(preview_key + "::open"):
                            try:
                                st.video(path)
                            except Exception:
                                st.caption(path)

                st.caption(base)
                if isinstance(mid, str) and mid.strip():
                    _open_match_button(mid)
                else:
                    st.caption("Match: non associé")


def _load_media_from_db(db_path: str, xuid: str) -> pd.DataFrame:
    """Charge les médias depuis la BDD DuckDB.

    Args:
        db_path: Chemin vers la DB DuckDB.
        xuid: XUID du propriétaire des médias.

    Returns:
        DataFrame avec colonnes: path, mtime, ext, kind, basename, match_id, match_start_time
    """
    try:
        import duckdb

        conn = duckdb.connect(db_path, read_only=True)
        try:
            # Vérifier si les tables existent
            tables = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                AND table_name = 'media_files'
                """
            ).fetchall()

            if not tables:
                return pd.DataFrame()

            # Charger les médias avec leurs associations
            result = conn.execute(
                """
                SELECT
                    mf.file_path AS path,
                    mf.mtime,
                    mf.mtime_paris_epoch,
                    mf.file_ext AS ext,
                    mf.kind,
                    mf.file_name AS basename,
                    mf.thumbnail_path,
                    mma.match_id,
                    mma.match_start_time,
                    mma.association_confidence
                FROM media_files mf
                LEFT JOIN media_match_associations mma
                    ON mf.file_path = mma.media_path
                    AND mf.owner_xuid = mma.xuid
                WHERE mf.owner_xuid = ?
                ORDER BY mf.mtime_paris_epoch DESC
                """,
                [xuid],
            ).fetchall()

            if not result:
                return pd.DataFrame()

            df = pd.DataFrame(
                result,
                columns=[
                    "path",
                    "mtime",
                    "mtime_paris_epoch",
                    "ext",
                    "kind",
                    "basename",
                    "thumbnail_path",
                    "match_id",
                    "match_start_time",
                    "association_confidence",
                ],
            )

            return df

        finally:
            conn.close()

    except Exception:
        return pd.DataFrame()


def render_media_library_page(*, df_full: pd.DataFrame, settings: AppSettings) -> None:
    """Rend la page Bibliothèque médias."""
    st.subheader("Bibliothèque médias")

    if not bool(getattr(settings, "media_enabled", True)):
        st.info("Les médias sont désactivés dans Paramètres → Médias.")
        return

    dirs = _coerce_dirs(settings)
    if not dirs.screens_dir and not dirs.videos_dir:
        st.info("Configure au moins un dossier dans Paramètres → Médias (captures et/ou vidéos).")
        return

    # Récupérer le XUID du joueur actuel
    db_path = st.session_state.get("db_path", "")
    xuid_input = st.session_state.get("xuid_input", "")

    # Résoudre le XUID
    from src.app.profile import resolve_xuid
    from src.app.state import get_default_identity

    identity = get_default_identity()
    xuid = (
        resolve_xuid(xuid_input or "JGtm", db_path, identity)
        or identity.xuid
        or identity.xuid_fallback
    )

    with st.expander("Options", expanded=True):
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        group_by_match = c1.toggle("Grouper par match", value=True)
        show_unassigned = c2.toggle("Afficher non associés", value=True)
        cols_per_row = c3.slider("Colonnes", min_value=2, max_value=6, value=4, step=1)
        max_items = c4.slider("Max médias", min_value=50, max_value=2000, value=400, step=50)

        kinds = st.multiselect(
            "Types",
            options=["image", "video"],
            default=["image", "video"],
        )
        name_filter = st.text_input("Filtre nom de fichier", value="", placeholder="ex: 2026-01")

        if st.button("Re-scanner les dossiers", width="stretch"):
            with contextlib.suppress(Exception):
                index_media_dir.clear()
            # Forcer re-indexation en BDD
            if "_media_indexing_started" in st.session_state:
                del st.session_state["_media_indexing_started"]

            # Lancer l'indexation manuellement si DB DuckDB disponible
            if db_path and db_path.endswith(".duckdb") and xuid:
                try:
                    from pathlib import Path

                    from src.data.media_indexer import MediaIndexer

                    videos_path = (
                        Path(dirs.videos_dir)
                        if dirs.videos_dir and os.path.exists(dirs.videos_dir)
                        else None
                    )
                    screens_path = (
                        Path(dirs.screens_dir)
                        if dirs.screens_dir and os.path.exists(dirs.screens_dir)
                        else None
                    )

                    if videos_path or screens_path:
                        with st.spinner("Indexation en cours..."):
                            indexer = MediaIndexer(Path(db_path), xuid)
                            result = indexer.scan_and_index(
                                videos_dir=videos_path,
                                screens_dir=screens_path,
                                force_rescan=True,
                            )
                            tolerance = int(getattr(settings, "media_tolerance_minutes", 5) or 5)
                            n_associated = indexer.associate_with_matches(
                                tolerance_minutes=tolerance
                            )
                            st.success(
                                f"Indexation terminée: {result.n_new} nouveaux, "
                                f"{result.n_updated} mis à jour, {n_associated} associés"
                            )
                except Exception as e:
                    st.error(f"Erreur lors de l'indexation: {e}")

            st.rerun()

    # Charger depuis BDD si disponible
    media_df = pd.DataFrame()
    using_db = False
    windows_df = pd.DataFrame()  # Initialiser pour le diagnostic
    if db_path and db_path.endswith(".duckdb") and xuid:
        media_df = _load_media_from_db(db_path, xuid)
        using_db = not media_df.empty

    # Fallback sur scan disque si BDD vide
    if media_df.empty:
        media_df = _index_all_media(settings)
        # Si on a scanné depuis disque, on peut essayer d'associer avec les matchs
        if not media_df.empty:
            windows_df = _compute_match_windows(df_full, settings)
            assoc_df = _associate_media_to_matches(media_df, windows_df)
        else:
            assoc_df = pd.DataFrame()
    else:
        # Les associations sont déjà dans la BDD
        assoc_df = media_df.copy()
        # S'assurer que match_id est bien présent même si NULL
        if "match_id" not in assoc_df.columns:
            assoc_df["match_id"] = None
        if "match_start_time" not in assoc_df.columns:
            assoc_df["match_start_time"] = None
        # Calculer windows_df pour le diagnostic même si on utilise la BDD
        windows_df = _compute_match_windows(df_full, settings)

    # Diagnostic : afficher info si médias non associés depuis BDD
    if using_db and not assoc_df.empty:
        unassigned_count = assoc_df["match_id"].isna().sum()
        if unassigned_count > 0:
            st.info(
                f"ℹ️ {unassigned_count} média(s) non associé(s) depuis la BDD. "
                "Cliquez sur 'Re-scanner les dossiers' pour forcer l'indexation et l'association."
            )

    if assoc_df.empty:
        st.info("Aucun média trouvé.")
        return

    assoc_df = assoc_df.head(int(max_items))

    if kinds:
        assoc_df = assoc_df.loc[assoc_df["kind"].isin([str(k) for k in kinds])].copy()

    if name_filter.strip():
        nf = name_filter.strip().lower()
        assoc_df = assoc_df.loc[
            assoc_df["basename"].astype(str).str.lower().str.contains(nf, na=False)
        ].copy()

    assigned = assoc_df.loc[assoc_df["match_id"].notna()].copy()
    unassigned = assoc_df.loc[assoc_df["match_id"].isna()].copy()

    # Diagnostic unifié : afficher un seul message informatif
    if not using_db:
        # Si on utilise le scan disque (fallback), informer l'utilisateur
        st.info(
            "ℹ️ Les médias sont chargés depuis le scan disque (pas encore indexés en BDD). "
            "Cliquez sur 'Re-scanner les dossiers' pour indexer en BDD et associer automatiquement."
        )
    elif windows_df.empty:
        # Compter combien de matchs ont start_time NULL pour diagnostic
        null_start_count = 0
        if df_full is not None and not df_full.empty and "start_time" in df_full.columns:
            null_start_count = df_full["start_time"].isna().sum()

        if null_start_count > 0:
            st.warning(
                f"⚠️ Aucune fenêtre temporelle disponible : {null_start_count} match(s) ont une date de départ manquante (`start_time` NULL). "
                "Vérifiez la synchronisation des données."
            )
        else:
            st.warning(
                "⚠️ Aucune fenêtre temporelle de match disponible pour l'association. "
                "Vérifiez que les matchs ont bien des dates de départ (`start_time`)."
            )
    elif assigned.empty and not unassigned.empty and using_db:
        # Seulement afficher ce message si windows_df n'est pas vide et qu'on utilise la BDD
        tolerance = int(getattr(settings, "media_tolerance_minutes", 5) or 5)
        st.warning(
            f"⚠️ Aucun média n'a pu être associé à un match depuis la BDD. "
            f"Tolérance actuelle: {tolerance} min. "
            "Essayez d'augmenter la tolérance dans Paramètres → Médias ou vérifiez que les dates des matchs correspondent."
        )

    # Affichage
    if not group_by_match:
        _render_media_grid(assoc_df, cols_per_row=int(cols_per_row))
        return
        st.subheader(f"Médias non associés ({len(unassigned)})")
        _render_media_grid(unassigned, cols_per_row=int(cols_per_row))
        return

    if not assigned.empty:
        # Tri: match le plus récent d'abord, puis médias par ordre chronologique (mtime asc)
        assigned["_match_sort"] = pd.to_datetime(assigned["match_start_time"], errors="coerce")
        groups = assigned.sort_values(["_match_sort", "mtime"], ascending=[False, True]).groupby(
            "match_id", sort=False
        )

        for match_id, g in groups:
            title_dt = None
            try:
                dt0 = g["match_start_time"].iloc[0]
                title_dt = format_datetime_fr_hm(dt0) if dt0 is not None else None
            except Exception:
                title_dt = None

            label = f"Match {match_id}" + (" — " + str(title_dt) if title_dt else "")
            with st.expander(label, expanded=False):
                _open_match_button(str(match_id))
                g2 = g.sort_values("mtime", ascending=True).copy()
                _render_media_grid(g2, cols_per_row=int(cols_per_row))

    if show_unassigned and not unassigned.empty:
        st.divider()
        st.subheader("Non associés")
        _render_media_grid(unassigned, cols_per_row=int(cols_per_row))
