"""Composant Thumbnail média – affichage statique, survol animé (HTML/JS), dimensions fixes (Sprint 4)."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
from pathlib import Path

import streamlit as st

from src.ui.components.media_lightbox import build_lightbox_html

logger = logging.getLogger(__name__)

# Taille max pour embarquer en data URI (éviter iframe trop lourd)
# Les GIF de captures Halo peuvent être volumineux → limites assouplies
MAX_STATIC_BYTES = 3_000_000  # ~3 MB pour miniature statique (dont GIF)
MAX_HOVER_BYTES = 4_000_000  # ~4 MB pour version survol (GIF animé)
MAX_LIGHTBOX_BYTES = 5_000_000  # ~5 MB pour lightbox (sinon on affiche la miniature)


def _gif_first_frame_to_data_uri(gif_path: Path) -> str | None:
    """Extrait la première frame d'un GIF et retourne une data URI PNG (statique, ne s'anime pas)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(gif_path) as img:
            img.seek(0)
            frame = img.convert("RGBA")
            buf = io.BytesIO()
            frame.save(buf, format="PNG", optimize=True)
            data = buf.getvalue()
            if len(data) > MAX_STATIC_BYTES:
                return None
            b64 = base64.standard_b64encode(data).decode("ascii")
            return f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.debug("GIF first frame %s: %s", gif_path, e)
        return None


def _path_to_data_uri(path: Path, max_bytes: int, mime: str) -> str | None:
    """Lit un fichier et retourne une data URI, ou None si fichier absent / trop gros."""
    if not path.exists():
        return None
    try:
        data = path.read_bytes()
        if len(data) > max_bytes:
            return None
        b64 = base64.standard_b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        logger.debug("Data URI %s: %s", path, e)
        return None


def _mime_for_path(path: Path, kind: str) -> str:
    ext = (path.suffix or "").lower()
    if kind == "video":
        if ext in (".webm",):
            return "video/webm"
        if ext in (".mkv",):
            return "video/x-matroska"
        return "video/mp4"
    if ext in (".png",):
        return "image/png"
    if ext in (
        ".jpg",
        ".jpeg",
    ):
        return "image/jpeg"
    if ext in (".webp",):
        return "image/webp"
    return "image/png"


def build_thumbnail_html(
    *,
    static_src: str,
    hover_src: str | None,
    lightbox_src: str,
    kind: str,
    width: int = 200,
    height: int = 200,
    element_id: str,
) -> str:
    """Construit le HTML complet : zone thumbnail (static + survol) + lightbox.

    - Affichage par défaut : static_src.
    - Au survol uniquement : chargement et affichage de hover_src (GIF ne charge qu'au hover).
    - Ratio uniforme : boîte fixe 16:9 avec aspect-ratio, object-fit: cover.
    - Au clic : ouverture du lightbox.
    """
    overlay_id = f"media-lightbox-{element_id}"
    container_id = f"media-thumb-{element_id}"
    static_id = f"thumb-static-{element_id}"
    hover_id = f"thumb-hover-{element_id}"

    safe_static = static_src.replace("\\", "\\\\").replace('"', "&quot;").replace("<", "&lt;")
    # hover_src n'est pas mis dans le src initial : on l'injecte au mouseenter pour que le GIF ne s'anime qu'au survol
    hover_js = json.dumps(hover_src) if hover_src else "null"
    hover_img = (
        f'<img id="{hover_id}" src="" alt="" style="width:100%;height:100%;object-fit:cover;object-position:center;position:absolute;top:0;left:0;display:none;" />'
        if hover_src
        else ""
    )

    lightbox_html = build_lightbox_html(
        media_src=lightbox_src,
        kind=kind,
        element_id=element_id,
    )

    # Ratio 16:9 pour toutes les captures (grille alignée), contenu recadré
    return f"""
<div id="{container_id}" class="media-thumb-container" style="
  width: 100%;
  max-width: {width}px;
  aspect-ratio: 16 / 9;
  position: relative;
  overflow: hidden;
  border-radius: 8px;
  cursor: pointer;
  background: #1a1a1a;
  flex-shrink: 0;
  margin: 0 auto;
">
  <img id="{static_id}" src="{safe_static}" alt="" style="width:100%;height:100%;object-fit:cover;object-position:center;display:block;" />
  {hover_img}
</div>
{lightbox_html}
<script>
(function() {{
  var c = document.getElementById('{container_id}');
  var s = document.getElementById('{static_id}');
  var h = document.getElementById('{hover_id}');
  var overlay = document.getElementById('{overlay_id}');
  var hoverSrc = {hover_js};
  if (!c || !overlay) return;
  c.addEventListener('mouseenter', function() {{
    if (h && hoverSrc) {{
      h.src = hoverSrc;
      s.style.display = 'none';
      h.style.display = 'block';
    }}
  }});
  c.addEventListener('mouseleave', function() {{
    if (h) {{
      h.src = '';
      h.style.display = 'none';
      s.style.display = 'block';
    }}
  }});
  c.addEventListener('click', function() {{
    overlay.style.display = 'flex';
  }});
}})();
</script>
"""


def render_media_thumbnail(
    *,
    static_path: Path | str,
    hover_path: Path | str | None = None,
    full_media_path: Path | str | None = None,
    kind: str = "image",
    width: int = 200,
    height: int = 200,
    media_id: str | None = None,
    height_iframe: int | None = None,
) -> None:
    """Affiche un thumbnail média dans Streamlit (dimensions fixes, survol animé, clic → lightbox).

    Args:
        static_path: Chemin de la miniature statique (affichée par défaut).
        hover_path: Chemin de la version « survol » (GIF animé ou image). Si absent, pas de changement au survol.
        full_media_path: Chemin du média plein (lightbox). Si absent ou fichier trop gros, utilise la miniature.
        kind: "image" ou "video" (pour le lecteur dans le lightbox).
        width: Largeur du thumbnail (px).
        height: Hauteur du thumbnail (px).
        media_id: Identifiant unique (pour clés Streamlit / ids HTML). Généré si absent.
        height_iframe: Hauteur de l'iframe HTML (défaut: height + marge).
    """
    static_path = Path(static_path)
    if not static_path.exists():
        st.caption(f"Fichier absent : {static_path.name}")
        return

    element_id = media_id or hashlib.md5(str(static_path.resolve()).encode()).hexdigest()[:12]

    # Pour les GIF (vidéos) : utiliser la première frame en statique, le GIF uniquement au survol
    is_gif_thumbnail = str(static_path).lower().endswith(".gif") and hover_path
    static_uri: str | None = None
    if is_gif_thumbnail:
        static_uri = _gif_first_frame_to_data_uri(static_path)
    if not static_uri:
        static_uri = _path_to_data_uri(
            static_path, MAX_STATIC_BYTES, _mime_for_path(static_path, "image")
        )
    if not static_uri:
        # Fallback : afficher via st.image (pas d'embed data URI) pour fichiers trop volumineux
        try:
            st.image(str(static_path), width=width)
        except Exception:
            st.caption(f"Miniature trop volumineuse : {static_path.name}")
        return

    hover_uri: str | None = None
    if hover_path:
        hover_path = Path(hover_path)
        if hover_path.exists():
            hover_uri = _path_to_data_uri(
                hover_path,
                MAX_HOVER_BYTES,
                "image/gif"
                if str(hover_path).lower().endswith(".gif")
                else _mime_for_path(hover_path, "image"),
            )

    full_path = Path(full_media_path) if full_media_path else static_path
    lightbox_uri = _path_to_data_uri(full_path, MAX_LIGHTBOX_BYTES, _mime_for_path(full_path, kind))
    if not lightbox_uri:
        lightbox_uri = static_uri
        kind = "image"

    html = build_thumbnail_html(
        static_src=static_uri,
        hover_src=hover_uri,
        lightbox_src=lightbox_uri,
        kind=kind,
        width=width,
        height=height,
        element_id=element_id,
    )
    iframe_h = height_iframe if height_iframe is not None else height + 24
    st.components.v1.html(html, height=iframe_h)
