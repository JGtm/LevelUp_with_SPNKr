"""Tests de non-régression query params <-> routing."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.app import routing


class _QueryParamsDict(dict):
    """Mapping query_params minimal avec clear explicite."""

    def clear(self) -> None:
        super().clear()


@pytest.mark.regression
def test_consume_query_params_sets_pending_and_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    """consume_query_params doit hydrater les pending states et vider les query params."""
    qp = _QueryParamsDict({"page": ["Match"], "match_id": ["m-42"]})
    fake_st = SimpleNamespace(session_state={}, query_params=qp)
    monkeypatch.setattr(routing, "st", fake_st)

    page, match_id = routing.consume_query_params()

    assert (page, match_id) == ("Match", "m-42")
    assert fake_st.session_state["_pending_page"] == "Match"
    assert fake_st.session_state["_pending_match_id"] == "m-42"
    assert dict(fake_st.query_params) == {}


@pytest.mark.regression
def test_consume_query_params_is_idempotent_for_same_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un token déjà consommé ne doit pas être retraité."""
    qp = _QueryParamsDict({"page": "Match", "match_id": "m-42"})
    fake_st = SimpleNamespace(
        session_state={"_consumed_query_params": ("Match", "m-42")},
        query_params=qp,
    )
    monkeypatch.setattr(routing, "st", fake_st)

    page, match_id = routing.consume_query_params()

    assert (page, match_id) == (None, None)
    assert fake_st.session_state["_consumed_query_params"] == ("Match", "m-42")


@pytest.mark.regression
def test_consume_query_params_handles_missing_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """En cas d'erreur d'accès query_params, la fonction retourne (None, None)."""

    class _BrokenSt:
        session_state = {}

        @property
        def query_params(self):
            raise RuntimeError("query_params indisponible")

    monkeypatch.setattr(routing, "st", _BrokenSt())

    page, match_id = routing.consume_query_params()

    assert page is None
    assert match_id is None


@pytest.mark.regression
def test_build_app_url_encodes_special_chars() -> None:
    """L'URL générée doit encoder proprement les caractères spéciaux."""
    url = routing.build_app_url("Historique des parties", match_id="abc 123/é")

    assert url.startswith("?")
    assert "page=Historique+des+parties" in url
    assert "match_id=abc+123%2F%C3%A9" in url
