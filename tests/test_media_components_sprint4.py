"""Tests Sprint 4 – Composants UI Thumbnail et Lightbox (onglet Médias)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.ui.components.media_lightbox import build_lightbox_html, open_lightbox_js
from src.ui.components.media_thumbnail import (
    _mime_for_path,
    _path_to_data_uri,
    build_thumbnail_html,
    render_media_thumbnail,
)

# -----------------------------------------------------------------------------
# Lightbox
# -----------------------------------------------------------------------------


def test_build_lightbox_html_image() -> None:
    html = build_lightbox_html(
        media_src="data:image/png;base64,abc",
        kind="image",
        element_id="test1",
    )
    assert "media-lightbox-test1" in html
    assert "media-lightbox-overlay" in html
    assert "data:image/png;base64,abc" in html or "abc" in html
    assert "<img" in html
    assert "&times;" in html
    assert "display: none" in html
    assert "Escape" in html


def test_build_lightbox_html_video() -> None:
    html = build_lightbox_html(
        media_src="data:video/mp4;base64,xyz",
        kind="video",
        element_id="vid1",
    )
    assert "media-lightbox-vid1" in html
    assert "<video" in html
    assert "controls" in html
    assert "autoplay" in html


def test_open_lightbox_js() -> None:
    js = open_lightbox_js("media-lightbox-foo")
    assert "media-lightbox-foo" in js
    assert "display" in js


# -----------------------------------------------------------------------------
# Thumbnail – helpers
# -----------------------------------------------------------------------------


def test_mime_for_path_image() -> None:
    assert _mime_for_path(Path("a.png"), "image") == "image/png"
    assert _mime_for_path(Path("b.JPG"), "image") == "image/jpeg"
    assert _mime_for_path(Path("c.webp"), "image") == "image/webp"


def test_mime_for_path_video() -> None:
    assert _mime_for_path(Path("a.mp4"), "video") == "video/mp4"
    assert _mime_for_path(Path("b.webm"), "video") == "video/webm"


def test_path_to_data_uri_missing() -> None:
    assert _path_to_data_uri(Path("/nonexistent"), 1000, "image/png") is None


def test_path_to_data_uri_small_file(tmp_path: Path) -> None:
    f = tmp_path / "tiny.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    uri = _path_to_data_uri(f, 10_000, "image/png")
    assert uri is not None
    assert uri.startswith("data:image/png;base64,")


def test_path_to_data_uri_too_large(tmp_path: Path) -> None:
    f = tmp_path / "big.bin"
    f.write_bytes(b"x" * 2000)
    assert _path_to_data_uri(f, 500, "application/octet-stream") is None


# -----------------------------------------------------------------------------
# Thumbnail – build_thumbnail_html
# -----------------------------------------------------------------------------


def test_build_thumbnail_html_contains_static_and_lightbox() -> None:
    html = build_thumbnail_html(
        static_src="data:image/png;base64,s",
        hover_src=None,
        lightbox_src="data:image/png;base64,l",
        kind="image",
        width=200,
        height=200,
        element_id="t1",
    )
    assert "media-thumb-t1" in html
    assert "thumb-static-t1" in html
    assert "media-lightbox-t1" in html
    assert "200" in html
    assert "mouseenter" in html
    assert "mouseleave" in html
    assert "object-fit:cover" in html


def test_build_thumbnail_html_with_hover() -> None:
    html = build_thumbnail_html(
        static_src="data:image/png;base64,s",
        hover_src="data:image/gif;base64,g",
        lightbox_src="data:image/png;base64,l",
        kind="image",
        width=160,
        height=120,
        element_id="t2",
    )
    assert "thumb-hover-t2" in html
    assert "data:image/gif;base64,g" in html or "g" in html


# -----------------------------------------------------------------------------
# Thumbnail – render_media_thumbnail (intégration Streamlit)
# -----------------------------------------------------------------------------


def test_render_media_thumbnail_missing_file() -> None:
    """Si le fichier statique est absent, on affiche un message (sans planter)."""
    with patch("src.ui.components.media_thumbnail.st") as m_st:
        render_media_thumbnail(static_path=Path("/nonexistent/thumb.png"))
        m_st.caption.assert_called_once()
        caption_text = m_st.caption.call_args[0][0]
        assert "absent" in caption_text or "Fichier" in caption_text


def test_render_media_thumbnail_with_real_file(tmp_path: Path) -> None:
    """Avec un petit fichier image, le composant injecte du HTML et appelle st.components.v1.html."""
    thumb = tmp_path / "thumb.png"
    thumb.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)
    with (
        patch("src.ui.components.media_thumbnail.st"),
        patch("src.ui.components.media_thumbnail.st.components.v1.html") as m_html,
    ):
        render_media_thumbnail(
            static_path=thumb,
            kind="image",
            width=180,
            height=180,
            media_id="test-render",
        )
        m_html.assert_called_once()
        call_args = m_html.call_args
        html = call_args[0][0]
        assert "media-thumb-test-render" in html
        assert "media-lightbox-test-render" in html
        assert "data:image/png;base64," in html
