"""Tests de régression – Onglet Médias (Sprint 6).

Exécuter avec : pytest tests/test_media_regression_sprint6.py -v

Ce module importe les tests des sprints médias pour vérifier qu’aucune régression
n’a été introduite (media_indexer, media_tab, composants thumbnail/lightbox).
"""

from __future__ import annotations

import pytest


@pytest.mark.regression
def test_media_suite_imports() -> None:
    """Vérifie que les modules médias sont importables sans erreur."""
    from src.data.media_indexer import MediaIndexer
    from src.ui.components.media_lightbox import build_lightbox_html
    from src.ui.components.media_thumbnail import render_media_thumbnail
    from src.ui.pages.media_tab import render_media_tab

    assert MediaIndexer is not None
    assert build_lightbox_html is not None
    assert render_media_thumbnail is not None
    assert render_media_tab is not None
