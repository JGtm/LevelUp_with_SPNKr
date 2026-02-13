"""Tests de persistance des filtres entre pages/joueurs."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.app.filters_render import FilterState, apply_filters
from src.ui import filter_state
from src.ui.filter_state import FilterPreferences


@pytest.fixture
def fake_streamlit_state(monkeypatch: pytest.MonkeyPatch):
    """Injecte un faux objet streamlit avec session_state mutable."""
    fake_st = SimpleNamespace(session_state={}, warning=MagicMock())
    monkeypatch.setattr(filter_state, "st", fake_st)
    return fake_st


@pytest.fixture
def isolated_filters_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Isole les fichiers de préférences de filtres dans tmp_path."""
    base_dir = tmp_path / "filter_prefs"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(filter_state, "_get_filters_dir", lambda: base_dir)
    return base_dir


def test_save_then_load_filter_preferences_roundtrip(
    fake_streamlit_state,
    isolated_filters_dir,
) -> None:
    """Un jeu de filtres sauvegardé doit être relu à l'identique."""
    fake_streamlit_state.session_state.update(
        {
            "filter_mode": "Période",
            "start_date_cal": date(2026, 2, 1),
            "end_date_cal": date(2026, 2, 10),
            "gap_minutes": 120,
            "picked_session_label": "Session 3",
            "filter_playlists": {"Ranked Arena", "Quick Play"},
            "filter_modes": {"Slayer"},
            "filter_maps": {"Recharge"},
        }
    )

    filter_state.save_filter_preferences(
        xuid="x123",
        db_path="data/players/TestPlayer/stats.duckdb",
    )

    loaded = filter_state.load_filter_preferences(
        xuid="x123",
        db_path="data/players/TestPlayer/stats.duckdb",
    )

    assert isinstance(loaded, FilterPreferences)
    assert loaded.filter_mode == "Période"
    assert loaded.start_date == "2026-02-01"
    assert loaded.end_date == "2026-02-10"
    assert loaded.gap_minutes == 120
    assert loaded.picked_session_label == "Session 3"
    assert sorted(loaded.playlists_selected or []) == ["Quick Play", "Ranked Arena"]
    assert loaded.modes_selected == ["Slayer"]
    assert loaded.maps_selected == ["Recharge"]


def test_apply_filter_preferences_populates_session_state(
    fake_streamlit_state,
    isolated_filters_dir,
) -> None:
    """L'application des préférences doit remplir les clés attendues du session_state."""
    prefs = FilterPreferences(
        filter_mode="Sessions",
        start_date="2026-01-01",
        end_date="2026-01-31",
        gap_minutes=90,
        picked_session_label="Session 9",
        playlists_selected=["Ranked Arena"],
        modes_selected=["CTF"],
        maps_selected=["Aquarius"],
    )

    filter_state.apply_filter_preferences(
        xuid="x321",
        db_path="data/players/Another/stats.duckdb",
        preferences=prefs,
    )

    state = fake_streamlit_state.session_state
    assert state["filter_mode"] == "Sessions"
    assert state["start_date_cal"] == date(2026, 1, 1)
    assert state["end_date_cal"] == date(2026, 1, 31)
    assert state["gap_minutes"] == 90
    assert state["picked_session_label"] == "Session 9"
    assert state["picked_sessions"] == ["Session 9"]
    assert state["filter_playlists"] == {"Ranked Arena"}
    assert state["filter_modes"] == {"CTF"}
    assert state["filter_maps"] == {"Aquarius"}


def test_get_all_filter_keys_to_clear_includes_widget_prefixes() -> None:
    """Les clés widget préfixées doivent être ajoutées au nettoyage global."""
    state = {
        "filter_mode": "Période",
        "filter_playlists_x": True,
        "filter_modes_y": False,
        "filter_maps_z": True,
        "unrelated_key": 123,
    }

    keys = filter_state.get_all_filter_keys_to_clear(state)

    assert "filter_mode" in keys
    assert "filter_playlists_x" in keys
    assert "filter_modes_y" in keys
    assert "filter_maps_z" in keys
    assert "unrelated_key" not in keys


def test_filter_preferences_are_isolated_by_player_key(
    fake_streamlit_state,
    isolated_filters_dir,
) -> None:
    """Deux joueurs distincts (via db_path) ne doivent pas partager le même fichier."""
    prefs_a = FilterPreferences(filter_mode="Période", playlists_selected=["A"])
    prefs_b = FilterPreferences(filter_mode="Sessions", playlists_selected=["B"])

    filter_state.save_filter_preferences(
        xuid="x_same",
        db_path="data/players/Alpha/stats.duckdb",
        preferences=prefs_a,
    )
    filter_state.save_filter_preferences(
        xuid="x_same",
        db_path="data/players/Bravo/stats.duckdb",
        preferences=prefs_b,
    )

    loaded_a = filter_state.load_filter_preferences(
        xuid="x_same",
        db_path="data/players/Alpha/stats.duckdb",
    )
    loaded_b = filter_state.load_filter_preferences(
        xuid="x_same",
        db_path="data/players/Bravo/stats.duckdb",
    )

    assert loaded_a is not None and loaded_b is not None
    assert loaded_a.playlists_selected == ["A"]
    assert loaded_b.playlists_selected == ["B"]


def test_nr_003_filter_persistence_cross_pages_consistent_dataset() -> None:
    """NR-003: un même état de filtres doit produire le même dataset source sur plusieurs pages."""
    df = pd.DataFrame(
        {
            "match_id": ["m1", "m2", "m3", "m4"],
            "start_time": pd.to_datetime(
                [
                    "2026-01-01 20:00:00",
                    "2026-01-02 20:00:00",
                    "2026-01-03 20:00:00",
                    "2026-01-04 20:00:00",
                ]
            ),
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
            "playlist_name": ["PListA", "PListB", "PListB", "PListA"],
            "pair_name": ["ModeA", "ModeB", "ModeA", "ModeB"],
            "map_name": ["MapA", "MapB", "MapC", "MapA"],
        }
    )

    filter_state_value = FilterState(
        filter_mode="Période",
        start_d=date(2026, 1, 1),
        end_d=date(2026, 1, 31),
        gap_minutes=120,
        picked_session_labels=None,
        playlists_selected=["PListB"],
        modes_selected=["ModeB"],
        maps_selected=["MapB"],
        base_s_ui=None,
        friends_tuple=None,
    )

    # Même filtrage appliqué pour 3 pages data-driven (timeseries / win-loss / teammates)
    timeseries_df = apply_filters(
        dff=df,
        filter_state=filter_state_value,
        db_path="",
        xuid="",
        db_key=None,
        clean_asset_label_fn=lambda s: str(s),
        normalize_mode_label_fn=lambda s: str(s),
        normalize_map_label_fn=lambda s: str(s),
    )
    winloss_df = apply_filters(
        dff=df,
        filter_state=filter_state_value,
        db_path="",
        xuid="",
        db_key=None,
        clean_asset_label_fn=lambda s: str(s),
        normalize_mode_label_fn=lambda s: str(s),
        normalize_map_label_fn=lambda s: str(s),
    )
    teammates_df = apply_filters(
        dff=df,
        filter_state=filter_state_value,
        db_path="",
        xuid="",
        db_key=None,
        clean_asset_label_fn=lambda s: str(s),
        normalize_mode_label_fn=lambda s: str(s),
        normalize_map_label_fn=lambda s: str(s),
    )

    expected_ids = ["m2"]
    assert timeseries_df["match_id"].to_list() == expected_ids
    assert winloss_df["match_id"].to_list() == expected_ids
    assert teammates_df["match_id"].to_list() == expected_ids
