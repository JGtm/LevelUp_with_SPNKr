"""Tests Sprint 4 : améliorations onglet médias."""

from __future__ import annotations

import inspect


def test_media_tab_module_imports() -> None:
    """Le module media_tab doit rester importable."""
    from src.ui.pages import media_tab

    assert media_tab is not None


def test_media_tab_keeps_lightbox_and_empty_message() -> None:
    """Les marqueurs UX Sprint 4 doivent rester présents."""
    from src.ui.pages import media_tab

    source = inspect.getsource(media_tab)
    assert "Voir en grand" in source
    assert "Aucune capture" in source
