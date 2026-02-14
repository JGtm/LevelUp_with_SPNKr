"""Tests pour src/ui/multiplayer.py — fonctions pures et avec mocks simples."""

from __future__ import annotations

from pathlib import Path

from src.ui.multiplayer import (
    DuckDBPlayerInfo,
    PlayerInfo,
    _is_duckdb_file,
    get_gamertag_from_duckdb_v4_path,
    get_player_display_name,
    get_unique_xuids_from_matchstats,
    is_duckdb_v4_path,
    is_multi_player_db,
    list_players_in_db,
)

# ============================================================================
# _is_duckdb_file  (pure)
# ============================================================================


class TestIsDuckdbFile:
    def test_duckdb_extension(self):
        assert _is_duckdb_file("stats.duckdb") is True

    def test_db_extension(self):
        assert _is_duckdb_file("player.db") is False

    def test_full_path(self):
        assert _is_duckdb_file("data/players/MyGT/stats.duckdb") is True

    def test_no_extension(self):
        assert _is_duckdb_file("noext") is False


# ============================================================================
# PlayerInfo dataclass properties  (pure)
# ============================================================================


class TestPlayerInfoDisplayName:
    def test_with_label(self):
        p = PlayerInfo(
            xuid="123",
            gamertag="GT",
            label="Custom",
            total_matches=5,
            first_match_date=None,
            last_match_date=None,
        )
        assert p.display_name == "Custom"

    def test_with_gamertag(self):
        p = PlayerInfo(
            xuid="123",
            gamertag="MyGamertag",
            label=None,
            total_matches=0,
            first_match_date=None,
            last_match_date=None,
        )
        assert p.display_name == "MyGamertag"

    def test_fallback_to_xuid(self):
        p = PlayerInfo(
            xuid="1234567890123456",
            gamertag=None,
            label=None,
            total_matches=0,
            first_match_date=None,
            last_match_date=None,
        )
        assert p.display_name == "123456789012345…"

    def test_display_with_stats_matches(self):
        p = PlayerInfo(
            xuid="123",
            gamertag="GT",
            label=None,
            total_matches=150,
            first_match_date=None,
            last_match_date=None,
        )
        assert "150 matchs" in p.display_with_stats

    def test_display_with_stats_no_matches(self):
        p = PlayerInfo(
            xuid="123",
            gamertag="GT",
            label=None,
            total_matches=0,
            first_match_date=None,
            last_match_date=None,
        )
        assert p.display_with_stats == "GT"


# ============================================================================
# DuckDBPlayerInfo dataclass properties  (pure)
# ============================================================================


class TestDuckDBPlayerInfoDisplay:
    def test_with_matches(self):
        p = DuckDBPlayerInfo(gamertag="TestPlayer", db_path=Path("x"), total_matches=42)
        assert "42 matchs" in p.display_with_stats

    def test_zero_matches(self):
        p = DuckDBPlayerInfo(gamertag="TestPlayer", db_path=Path("x"), total_matches=0)
        assert "0 matchs" in p.display_with_stats


# ============================================================================
# is_duckdb_v4_path  (pure)
# ============================================================================


class TestIsDuckdbV4Path:
    def test_valid_path(self):
        # Simule un chemin valide
        p = str(Path("data") / "players" / "MyGT" / "stats.duckdb")
        assert is_duckdb_v4_path(p) is True

    def test_wrong_filename(self):
        p = str(Path("data") / "players" / "MyGT" / "other.duckdb")
        assert is_duckdb_v4_path(p) is False

    def test_empty(self):
        assert is_duckdb_v4_path("") is False

    def test_none_like(self):
        assert is_duckdb_v4_path("") is False


# ============================================================================
# get_gamertag_from_duckdb_v4_path  (pure)
# ============================================================================


class TestGetGamertagFromDuckdbV4Path:
    def test_valid(self):
        p = str(Path("data") / "players" / "Chocoboflor" / "stats.duckdb")
        assert get_gamertag_from_duckdb_v4_path(p) == "Chocoboflor"

    def test_empty(self):
        assert get_gamertag_from_duckdb_v4_path("") is None

    def test_non_stats_file(self):
        p = str(Path("data") / "players" / "MyGT" / "archive.duckdb")
        # Devrait quand même retourner le parent car le code ne vérifie pas spécifiquement "stats.duckdb"
        result = get_gamertag_from_duckdb_v4_path(p)
        assert result is None or result == "MyGT"


# ============================================================================
# is_multi_player_db, list_players_in_db, get_unique_xuids (toujours False/vide en v4)
# ============================================================================


class TestLegacyFunctions:
    def test_is_multi_player_db_nonexistent(self):
        assert is_multi_player_db("/nonexistent/path.duckdb") is False

    def test_is_multi_player_db_empty(self):
        assert is_multi_player_db("") is False

    def test_list_players_nonexistent(self):
        assert list_players_in_db("/nonexistent/path.duckdb") == []

    def test_list_players_empty(self):
        assert list_players_in_db("") == []

    def test_get_unique_xuids_nonexistent(self):
        assert get_unique_xuids_from_matchstats("/nonexistent/path.duckdb") == []

    def test_get_unique_xuids_empty(self):
        assert get_unique_xuids_from_matchstats("") == []

    def test_get_player_display_name_none(self):
        assert get_player_display_name("", "123") is None

    def test_get_player_display_name_nonexistent(self):
        assert get_player_display_name("/nope.duckdb", "123") is None
