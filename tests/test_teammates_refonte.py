"""Tests Sprint 4 : refonte de la page coéquipiers."""

from __future__ import annotations


def test_teammates_page_entrypoint_exists() -> None:
    """Le point d'entrée de la page coéquipiers doit exister."""
    from src.ui.pages.teammates import render_teammates_page

    assert callable(render_teammates_page)


def test_teammates_multi_view_exists() -> None:
    """La vue multi-coéquipiers (comparaisons) doit être présente."""
    from src.ui.pages.teammates_views import render_multi_teammate_view

    assert callable(render_multi_teammate_view)
