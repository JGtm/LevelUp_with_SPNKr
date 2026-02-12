"""Tests de non-régression navigation/état (session_state + query params)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.app import page_router, routing


@pytest.mark.regression
def test_consume_pending_page_applies_valid_and_pops(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une page en attente valide doit être appliquée et consommée."""
    fake_st = SimpleNamespace(session_state={"_pending_page": "Médias"})
    monkeypatch.setattr(page_router, "st", fake_st)

    page_router.consume_pending_page()

    assert fake_st.session_state.get("page") == "Médias"
    assert "_pending_page" not in fake_st.session_state


@pytest.mark.regression
def test_consume_pending_page_defaults_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans page active ni pending valide, la page par défaut est injectée."""
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(page_router, "st", fake_st)

    page_router.consume_pending_page()

    assert fake_st.session_state["page"] == "Séries temporelles"


@pytest.mark.regression
def test_consume_pending_page_ignores_invalid_keeps_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une pending page invalide ne doit pas écraser la page courante."""
    fake_st = SimpleNamespace(session_state={"_pending_page": "Inconnue", "page": "Citations"})
    monkeypatch.setattr(page_router, "st", fake_st)

    page_router.consume_pending_page()

    assert fake_st.session_state["page"] == "Citations"
    assert "_pending_page" not in fake_st.session_state


@pytest.mark.regression
def test_consume_pending_match_id_trims_and_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le match_id pending doit être trim puis stocké dans l'input."""
    fake_st = SimpleNamespace(session_state={"_pending_match_id": "  abc123  "})
    monkeypatch.setattr(page_router, "st", fake_st)

    page_router.consume_pending_match_id()

    assert fake_st.session_state.get("match_id_input") == "abc123"
    assert "_pending_match_id" not in fake_st.session_state


@pytest.mark.regression
def test_render_page_selector_uses_canonical_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le sélecteur doit être câblé sur la liste canonique des pages."""
    segmented_control = MagicMock(return_value="Carrière")
    fake_st = SimpleNamespace(segmented_control=segmented_control)
    monkeypatch.setattr(page_router, "st", fake_st)

    selected = page_router.render_page_selector()

    assert selected == "Carrière"
    segmented_control.assert_called_once()
    args, kwargs = segmented_control.call_args
    assert args[0] == "Onglets"
    assert kwargs["options"] == page_router.PAGES
    assert kwargs["key"] == "page"


@pytest.mark.regression
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("abc", "abc"),
        (["x", "y"], "x"),
        (("z",), "z"),
        ([], None),
    ],
)
def test_qp_first_behaviors(value, expected) -> None:
    """_qp_first gère scalaires/listes/vides sans régression."""
    assert routing._qp_first(value) == expected


class _QueryParamsDict(dict):
    def clear(self) -> None:
        super().clear()


@pytest.mark.regression
def test_set_query_params_primary_api_filters_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """_set_query_params garde uniquement les valeurs non vides via st.query_params."""
    qp = _QueryParamsDict({"legacy": "1"})
    fake_st = SimpleNamespace(query_params=qp, experimental_set_query_params=MagicMock())
    monkeypatch.setattr(routing, "st", fake_st)

    routing._set_query_params(page="Match", match_id="abc123", empty="", none_val=None)

    assert dict(qp) == {"page": "Match", "match_id": "abc123"}
    fake_st.experimental_set_query_params.assert_not_called()


@pytest.mark.regression
def test_set_query_params_fallbacks_to_legacy_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si l'API moderne échoue, fallback sur experimental_set_query_params."""

    class _BrokenQueryParams(dict):
        def clear(self) -> None:
            raise RuntimeError("query_params indisponible")

    legacy = MagicMock()
    fake_st = SimpleNamespace(
        query_params=_BrokenQueryParams(), experimental_set_query_params=legacy
    )
    monkeypatch.setattr(routing, "st", fake_st)

    routing._set_query_params(page="Carrière", match_id="m42")

    legacy.assert_called_once_with(page="Carrière", match_id="m42")
