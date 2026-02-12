"""Tests ciblés pour l'onglet Impact & Taquinerie (page coéquipiers)."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import polars as pl

from src.ui.pages import teammates


@contextmanager
def _fake_expander(*_args, **_kwargs):
    yield


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _FakeConn:
    def execute(self, query, _params=None):
        normalized_query = " ".join(str(query).split()).lower()

        if "information_schema.tables" in normalized_query:
            return _FakeResult([("highlight_events",)])
        if "from highlight_events" in normalized_query:
            return _FakeResult(
                [
                    ("m1", "100", "Alice", "Kill", 1000),
                    ("m2", "200", "Bob", "Kill", 1500),
                ]
            )
        if "from match_stats" in normalized_query:
            return _FakeResult([("m1", 2), ("m2", 3)])

        return _FakeResult([])


class _FakeRepo:
    def __init__(self, *_args, **_kwargs):
        self._conn = _FakeConn()

    def _get_connection(self):
        return self._conn


def _patch_streamlit(monkeypatch):
    info = MagicMock()
    warning = MagicMock()
    caption = MagicMock()
    subheader = MagicMock()
    plotly_chart = MagicMock()
    dataframe = MagicMock()

    metric_cols = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
    summary_cols = [MagicMock(), MagicMock()]
    columns = MagicMock(side_effect=[metric_cols, summary_cols])

    monkeypatch.setattr(teammates.st, "expander", _fake_expander)
    monkeypatch.setattr(teammates.st, "info", info)
    monkeypatch.setattr(teammates.st, "warning", warning)
    monkeypatch.setattr(teammates.st, "caption", caption)
    monkeypatch.setattr(teammates.st, "subheader", subheader)
    monkeypatch.setattr(teammates.st, "plotly_chart", plotly_chart)
    monkeypatch.setattr(teammates.st, "dataframe", dataframe)
    monkeypatch.setattr(teammates.st, "columns", columns)

    return {
        "info": info,
        "warning": warning,
        "caption": caption,
        "subheader": subheader,
        "plotly_chart": plotly_chart,
        "dataframe": dataframe,
        "columns": columns,
        "metric_cols": metric_cols,
        "summary_cols": summary_cols,
    }


def test_impact_tab_requires_at_least_two_friends(monkeypatch) -> None:
    """Affiche un message d'info si < 2 coéquipiers sont sélectionnés."""
    st_mocks = _patch_streamlit(monkeypatch)

    teammates._render_impact_taquinerie(
        db_path="dummy.duckdb",
        xuid="100",
        match_ids=["m1"],
        friend_xuids=["200"],
    )

    st_mocks["info"].assert_called_once()
    assert "au moins 2 coéquipiers" in st_mocks["info"].call_args[0][0]
    st_mocks["warning"].assert_not_called()


def test_impact_tab_warns_when_no_matches(monkeypatch) -> None:
    """Affiche un warning s'il n'y a aucun match à analyser."""
    st_mocks = _patch_streamlit(monkeypatch)

    teammates._render_impact_taquinerie(
        db_path="dummy.duckdb",
        xuid="100",
        match_ids=[],
        friend_xuids=["200", "300"],
    )

    st_mocks["warning"].assert_called_once()
    assert "Aucun match" in st_mocks["warning"].call_args[0][0]


def test_impact_tab_handles_missing_highlight_table(monkeypatch) -> None:
    """Affiche un message si highlight_events n'existe pas."""

    class _FakeConnNoEvents:
        def execute(self, query, _params=None):
            normalized_query = " ".join(str(query).split()).lower()
            if "information_schema.tables" in normalized_query:
                return _FakeResult([])
            return _FakeResult([])

    class _FakeRepoNoEvents:
        def __init__(self, *_args, **_kwargs):
            self._conn = _FakeConnNoEvents()

        def _get_connection(self):
            return self._conn

    st_mocks = _patch_streamlit(monkeypatch)
    monkeypatch.setattr("src.data.repositories.DuckDBRepository", _FakeRepoNoEvents)

    teammates._render_impact_taquinerie(
        db_path="dummy.duckdb",
        xuid="100",
        match_ids=["m1", "m2"],
        friend_xuids=["200", "300"],
    )

    st_mocks["info"].assert_called()
    assert "highlight_events" in st_mocks["info"].call_args[0][0]


def test_impact_tab_renders_heatmap_and_ranking(monkeypatch) -> None:
    """Parcours nominal : rendu heatmap + tableau + résumé MVP/Boulet."""
    st_mocks = _patch_streamlit(monkeypatch)

    monkeypatch.setattr("src.data.repositories.DuckDBRepository", _FakeRepo)

    first_bloods = {"m1": object()}
    clutch_finishers = {"m2": object()}
    last_casualties = {"m2": object()}
    scores = {"Alice": 3, "Bob": -1}

    monkeypatch.setattr(
        teammates,
        "get_all_impact_events",
        lambda *_args, **_kwargs: (first_bloods, clutch_finishers, last_casualties, scores),
    )
    monkeypatch.setattr(
        teammates,
        "build_impact_matrix",
        lambda *_args, **_kwargs: pl.DataFrame(
            {
                "match_id": ["m1", "m2"],
                "gamertag": ["Alice", "Bob"],
                "event_type": ["first_blood", "last_casualty"],
                "event_value": [1, -1],
            }
        ),
    )
    monkeypatch.setattr(
        teammates,
        "render_impact_summary_stats",
        lambda *_args, **_kwargs: {
            "total_fb": 1,
            "total_clutch": 1,
            "total_casualty": 1,
            "total_matches": 2,
        },
    )
    monkeypatch.setattr(
        teammates, "plot_friends_impact_heatmap", lambda *_args, **_kwargs: object()
    )
    monkeypatch.setattr(
        teammates, "count_events_by_player", lambda events: {"Alice": 1} if events else {}
    )
    monkeypatch.setattr(
        teammates,
        "build_impact_ranking_df",
        lambda *_args, **_kwargs: pl.DataFrame(
            {
                "rang": [1, 2],
                "gamertag": ["Alice", "Bob"],
                "score": [3, -1],
                "fb": [1, 0],
                "clutch": [1, 0],
                "boulet": [0, 1],
                "badge": ["🏆 MVP", "🍌 Boulet"],
            }
        ),
    )

    teammates._render_impact_taquinerie(
        db_path="dummy.duckdb",
        xuid="100",
        match_ids=["m1", "m2"],
        friend_xuids=["200", "300"],
    )

    assert st_mocks["plotly_chart"].called
    assert st_mocks["dataframe"].called
    assert st_mocks["columns"].call_count == 2

    metric_calls = sum(col.metric.call_count for col in st_mocks["metric_cols"])
    assert metric_calls == 4
    st_mocks["summary_cols"][0].success.assert_called_once()
    st_mocks["summary_cols"][1].error.assert_called_once()
