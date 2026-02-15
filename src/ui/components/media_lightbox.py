"""Composant Lightbox – overlay fullscreen pour afficher image ou vidéo (Sprint 4)."""

from __future__ import annotations


def build_lightbox_html(
    *,
    media_src: str,
    kind: str,
    element_id: str,
) -> str:
    """Construit le HTML/JS de l'overlay lightbox (fullscreen).

    Args:
        media_src: Data URI ou URL du média à afficher (image ou vidéo).
        kind: "image" ou "video".
        element_id: Identifiant unique pour ce lightbox (éviter les conflits en grille).

    Returns:
        Fragment HTML contenant le div overlay et le script d'ouverture/fermeture.
    """
    overlay_id = f"media-lightbox-{element_id}"
    content_id = f"media-lightbox-content-{element_id}"
    # Échapper les guillemets dans le src pour l'injection dans HTML
    safe_src = media_src.replace("\\", "\\\\").replace('"', "&quot;").replace("<", "&lt;")

    if kind == "video":
        media_tag = f'<video controls autoplay src="{safe_src}" style="max-width:100%;max-height:100%;object-fit:contain;"></video>'
    else:
        media_tag = f'<img src="{safe_src}" style="max-width:100%;max-height:100%;object-fit:contain;" alt="Média" />'

    return f"""
<div id="{overlay_id}" class="media-lightbox-overlay" style="
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  z-index: 99999;
  background: rgba(0,0,0,0.9);
  justify-content: center;
  align-items: center;
  cursor: pointer;
">
  <div id="{content_id}" class="media-lightbox-content" style="
    max-width: 95vw;
    max-height: 95vh;
    display: flex;
    justify-content: center;
    align-items: center;
    cursor: default;
  " onclick="event.stopPropagation();">
    {media_tag}
  </div>
  <button type="button" class="media-lightbox-close" onclick="document.getElementById('{overlay_id}').style.display='none'" style="
    position: absolute;
    top: 12px;
    right: 16px;
    z-index: 100000;
    background: rgba(255,255,255,0.2);
    color: #fff;
    border: none;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 18px;
    cursor: pointer;
  ">&times;</button>
</div>
<script>
(function() {{
  var overlay = document.getElementById('{overlay_id}');
  if (!overlay) return;
  overlay.addEventListener('click', function(e) {{
    if (e.target === overlay) overlay.style.display = 'none';
  }});
  document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape' && overlay.style.display !== 'none') overlay.style.display = 'none';
  }});
}})();
</script>
"""


def open_lightbox_js(overlay_id: str) -> str:
    """Retourne une ligne JS pour ouvrir le lightbox par son id."""
    return f"document.getElementById('{overlay_id}').style.display='flex';"
