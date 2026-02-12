"""Tests de non-régression dédiés à la navigation en attente (_pending_page)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.app import routing


@pytest.mark.regression
def test_router_consume_pending_applies_target_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """Router.consume_pending applique la page en attente et la supprime de l'état."""
    fake_st = SimpleNamespace(
        session_state={"current_page": "Accueil", "_pending_page": "Historique"}
    )
    monkeypatch.setattr(routing, "st", fake_st)

    router = routing.Router.from_session()
    changed = router.consume_pending()

    assert changed is True
    assert router.current_page == routing.Page.from_string("Historique")
    assert fake_st.session_state["current_page"] == "Historique"
    assert "_pending_page" not in fake_st.session_state


@pytest.mark.regression
def test_router_consume_pending_is_noop_without_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans pending_page, consume_pending ne doit rien modifier."""
    fake_st = SimpleNamespace(session_state={"current_page": "Historique"})
    monkeypatch.setattr(routing, "st", fake_st)

    router = routing.Router.from_session()
    changed = router.consume_pending()

    assert changed is False
    assert router.current_page == routing.Page.HISTORIQUE


@pytest.mark.regression
def test_navigate_to_sets_pending_match_and_clears_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """navigate_to doit positionner la page, stocker le match pending, puis nettoyer l'URL."""
    clear_mock = MagicMock()
    monkeypatch.setattr(routing, "_clear_query_params", clear_mock)

    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(routing, "st", fake_st)

    routing.navigate_to(routing.Page.MATCH_VIEW, match_id="abc123")

    assert fake_st.session_state["current_page"] == routing.Page.MATCH_VIEW.value
    assert fake_st.session_state["_pending_match_id"] == "abc123"
    clear_mock.assert_called_once()


@pytest.mark.regression
def test_navigate_to_accepts_string_page_and_normalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    """navigate_to accepte une string et la convertit via Page.from_string."""
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(routing, "st", fake_st)

    routing.navigate_to("paramètres")

    assert fake_st.session_state["current_page"] == routing.Page.PARAMETRES.value
