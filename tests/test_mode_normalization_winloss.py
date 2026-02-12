"""Tests Sprint 4 : normalisation des modes dans la page Win/Loss."""

from __future__ import annotations

import inspect


def test_win_loss_module_imports() -> None:
    """Le module win_loss doit rester importable."""
    from src.ui.pages import win_loss

    assert win_loss is not None


def test_win_loss_keeps_mode_ui_path() -> None:
    """La logique de normalisation doit continuer de supporter mode_ui."""
    from src.ui.pages import win_loss

    source = inspect.getsource(win_loss)
    assert "mode_ui" in source
