"""Tests complémentaires pour src/utils — Sprint 7ter (7t.1).

Couvre : xuid.py, paths.py, profiles.py.
"""

from __future__ import annotations

import json

# ============================================================================
# xuid.py
# ============================================================================
from src.utils.xuid import (
    XUID_DIGITS_RE,
    extract_gamertag_from_player_id,
    extract_xuid_from_player_id,
    guess_xuid_from_db_path,
    infer_spnkr_player_from_db_path,
    parse_xuid_input,
    resolve_xuid_from_db,
)


class TestParseXuidInput:
    def test_digit_string(self):
        assert parse_xuid_input("2533274823110022") == "2533274823110022"

    def test_xuid_wrapper(self):
        assert parse_xuid_input("xuid(2533274823110022)") == "2533274823110022"

    def test_none(self):
        assert parse_xuid_input(None) is None

    def test_empty(self):
        assert parse_xuid_input("") is None
        assert parse_xuid_input("   ") is None

    def test_non_digit(self):
        assert parse_xuid_input("Chocoboflor") is None

    def test_mixed_text(self):
        assert parse_xuid_input("hello123") is None

    def test_whitespace_stripping(self):
        assert parse_xuid_input("  2533274823110022  ") == "2533274823110022"


class TestExtractXuidFromPlayerId:
    def test_none(self):
        assert extract_xuid_from_player_id(None) is None

    def test_dict_xuid_key(self):
        assert extract_xuid_from_player_id({"Xuid": 2533274823110022}) == "2533274823110022"

    def test_dict_xuid_lowercase(self):
        assert extract_xuid_from_player_id({"xuid": "2533274823110022"}) == "2533274823110022"

    def test_dict_xuid_uppercase(self):
        assert extract_xuid_from_player_id({"XUID": "2533274823110022"}) == "2533274823110022"

    def test_dict_xuid_wrapper(self):
        assert extract_xuid_from_player_id({"Xuid": "xuid(2533274823110022)"}) == "2533274823110022"

    def test_integer(self):
        assert extract_xuid_from_player_id(2533274823110022) == "2533274823110022"

    def test_string(self):
        assert extract_xuid_from_player_id("2533274823110022") == "2533274823110022"

    def test_dict_no_xuid(self):
        assert extract_xuid_from_player_id({"name": "test"}) is None

    def test_dict_invalid_xuid(self):
        assert extract_xuid_from_player_id({"Xuid": "abc"}) is None

    def test_string_with_xuid_embedded(self):
        assert (
            extract_xuid_from_player_id("player_2533274823110022_something") == "2533274823110022"
        )


class TestExtractGamertagFromPlayerId:
    def test_none(self):
        assert extract_gamertag_from_player_id(None) is None

    def test_dict_gamertag(self):
        assert extract_gamertag_from_player_id({"Gamertag": "Chocoboflor"}) == "Chocoboflor"

    def test_dict_gamertag_lower(self):
        assert extract_gamertag_from_player_id({"gamertag": "Chocoboflor"}) == "Chocoboflor"

    def test_dict_gt(self):
        assert extract_gamertag_from_player_id({"GT": "Chocoboflor"}) == "Chocoboflor"

    def test_dict_no_gamertag(self):
        assert extract_gamertag_from_player_id({"Xuid": "123"}) is None

    def test_dict_empty_gamertag(self):
        assert extract_gamertag_from_player_id({"Gamertag": ""}) is None
        assert extract_gamertag_from_player_id({"Gamertag": "   "}) is None

    def test_string_input(self):
        assert extract_gamertag_from_player_id("Chocoboflor") is None  # not a dict

    def test_whitespace_stripping(self):
        assert extract_gamertag_from_player_id({"Gamertag": "  Chocoboflor  "}) == "Chocoboflor"


class TestResolveXuidFromDb:
    def test_empty_player(self):
        assert resolve_xuid_from_db("/db.duckdb", "") is None
        assert resolve_xuid_from_db("/db.duckdb", None) is None

    def test_player_is_xuid(self):
        assert resolve_xuid_from_db("/db.duckdb", "2533274823110022") == "2533274823110022"

    def test_player_is_xuid_wrapper(self):
        assert resolve_xuid_from_db("/db.duckdb", "xuid(2533274823110022)") == "2533274823110022"

    def test_default_gamertag_match(self):
        result = resolve_xuid_from_db(
            "/db.duckdb",
            "Chocoboflor",
            default_gamertag="Chocoboflor",
            default_xuid="2533274823110022",
        )
        assert result == "2533274823110022"

    def test_default_gamertag_case_insensitive(self):
        result = resolve_xuid_from_db(
            "/db.duckdb",
            "chocoboflor",
            default_gamertag="Chocoboflor",
            default_xuid="2533274823110022",
        )
        assert result == "2533274823110022"

    def test_default_gamertag_no_xuid(self):
        result = resolve_xuid_from_db(
            "/db.duckdb", "Chocoboflor", default_gamertag="Chocoboflor", default_xuid=None
        )
        assert result is None

    def test_env_variable_fallback(self, monkeypatch):
        monkeypatch.setenv("OPENSPARTAN_DEFAULT_GAMERTAG", "Chocoboflor")
        monkeypatch.setenv("OPENSPARTAN_DEFAULT_XUID", "2533274823110022")
        result = resolve_xuid_from_db("/nonexistent.duckdb", "Chocoboflor")
        assert result == "2533274823110022"

    def test_aliases_fallback(self):
        aliases = {"2533274823110022": "Chocoboflor"}
        result = resolve_xuid_from_db("/nonexistent.duckdb", "Chocoboflor", aliases=aliases)
        assert result == "2533274823110022"

    def test_aliases_case_insensitive(self):
        aliases = {"2533274823110022": "chocoboflor"}
        result = resolve_xuid_from_db("/nonexistent.duckdb", "Chocoboflor", aliases=aliases)
        assert result == "2533274823110022"

    def test_db_not_found(self):
        result = resolve_xuid_from_db("/nonexistent.duckdb", "Unknown")
        assert result is None

    def test_resolve_from_duckdb(self, tmp_path):
        """Teste la résolution depuis une vraie DB DuckDB."""
        import duckdb

        db_path = str(tmp_path / "stats.duckdb")
        conn = duckdb.connect(db_path)
        conn.execute("CREATE TABLE xuid_aliases (xuid VARCHAR, gamertag VARCHAR)")
        conn.execute("INSERT INTO xuid_aliases VALUES ('2533274823110022', 'Chocoboflor')")
        conn.close()

        result = resolve_xuid_from_db(db_path, "Chocoboflor")
        assert result == "2533274823110022"


class TestInferSpnkrPlayerFromDbPath:
    def test_spnkr_gt(self):
        assert infer_spnkr_player_from_db_path("spnkr_gt_Chocoboflor.db") == "Chocoboflor"

    def test_spnkr_xuid(self):
        assert (
            infer_spnkr_player_from_db_path("spnkr_xuid_2533274823110022.db") == "2533274823110022"
        )

    def test_spnkr_generic(self):
        assert infer_spnkr_player_from_db_path("spnkr_something.db") == "something"

    def test_non_spnkr(self):
        assert infer_spnkr_player_from_db_path("mydb.db") is None

    def test_empty(self):
        assert infer_spnkr_player_from_db_path("") is None
        assert infer_spnkr_player_from_db_path(None) is None

    def test_full_path(self):
        assert infer_spnkr_player_from_db_path("/data/spnkr_gt_Player.db") == "Player"

    def test_case_insensitive_prefix(self):
        assert infer_spnkr_player_from_db_path("SPNKR_GT_Player.db") == "Player"


class TestGuessXuidFromDbPath:
    def test_digit_filename(self):
        assert guess_xuid_from_db_path("2533274823110022.db") == "2533274823110022"

    def test_xuid_in_name(self):
        assert guess_xuid_from_db_path("spnkr_xuid_2533274823110022.db") == "2533274823110022"

    def test_gamertag_with_alias(self):
        aliases = {"2535469190789936": "Chocoboflor"}
        result = guess_xuid_from_db_path("spnkr_gt_Chocoboflor.db", aliases=aliases)
        assert result == "2535469190789936"

    def test_no_match(self):
        assert guess_xuid_from_db_path("random_name.db") is None

    def test_empty(self):
        assert guess_xuid_from_db_path("") is None
        assert guess_xuid_from_db_path(None) is None

    def test_gamertag_underscore_variant(self):
        """Les gamertags avec underscores sont testés avec variantes."""
        aliases = {"1234567890123": "the player"}
        result = guess_xuid_from_db_path("spnkr_gt_the_player.db", aliases=aliases)
        assert result == "1234567890123"


class TestXuidDigitsRegex:
    def test_match_valid(self):
        m = XUID_DIGITS_RE.search("player_2533274823110022_stats")
        assert m is not None
        assert m.group(1) == "2533274823110022"

    def test_no_match_short(self):
        assert XUID_DIGITS_RE.search("12345") is None


# ============================================================================
# paths.py
# ============================================================================

from src.utils.paths import (
    DATA_DIR,
    METADATA_DB_FILENAME,
    PLAYER_DB_FILENAME,
    PLAYERS_DIR,
    REPO_ROOT,
    WAREHOUSE_DIR,
    ensure_archive_dir,
    ensure_player_dir,
    get_metadata_db_path,
    get_player_archive_dir,
    get_player_db_path,
    list_player_gamertags,
    player_db_exists,
)


class TestPathConstants:
    def test_repo_root_exists(self):
        assert REPO_ROOT.exists()

    def test_data_dir_under_root(self):
        assert DATA_DIR == REPO_ROOT / "data"

    def test_players_dir(self):
        assert PLAYERS_DIR == DATA_DIR / "players"

    def test_warehouse_dir(self):
        assert WAREHOUSE_DIR == DATA_DIR / "warehouse"

    def test_filenames(self):
        assert PLAYER_DB_FILENAME == "stats.duckdb"
        assert METADATA_DB_FILENAME == "metadata.duckdb"


class TestGetPlayerDbPath:
    def test_basic(self):
        path = get_player_db_path("Chocoboflor")
        assert path == PLAYERS_DIR / "Chocoboflor" / "stats.duckdb"

    def test_with_spaces(self):
        path = get_player_db_path("My Player")
        assert "My Player" in str(path)


class TestGetPlayerArchiveDir:
    def test_basic(self):
        path = get_player_archive_dir("Chocoboflor")
        assert path == PLAYERS_DIR / "Chocoboflor" / "archive"


class TestGetMetadataDbPath:
    def test_prefer_duckdb(self):
        """Par défaut, retourne le chemin DuckDB."""
        path = get_metadata_db_path(prefer_duckdb=True)
        assert path.name == "metadata.duckdb"

    def test_prefer_legacy(self):
        path = get_metadata_db_path(prefer_duckdb=False)
        # Retourne soit metadata.db si existe, soit metadata.duckdb
        assert path.name in ("metadata.db", "metadata.duckdb")


class TestListPlayerGamertags:
    def test_returns_list(self):
        result = list_player_gamertags()
        assert isinstance(result, list)

    def test_sorted(self):
        result = list_player_gamertags()
        assert result == sorted(result)


class TestPlayerDbExists:
    def test_existing_player(self):
        """Les joueurs de test peuvent exister dans l'env local."""
        result = player_db_exists("Chocoboflor")
        assert isinstance(result, bool)

    def test_nonexistent_player(self):
        assert player_db_exists("NonexistentPlayer12345") is False


class TestEnsurePlayerDir:
    def test_creates_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.paths.PLAYERS_DIR", tmp_path)
        result = ensure_player_dir("TestPlayer")
        assert result.exists()
        assert result.is_dir()
        assert result.name == "TestPlayer"


class TestEnsureArchiveDir:
    def test_creates_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.paths.PLAYERS_DIR", tmp_path)
        result = ensure_archive_dir("TestPlayer")
        assert result.exists()
        assert result.is_dir()
        assert result.name == "archive"


# ============================================================================
# profiles.py
# ============================================================================

from src.utils.profiles import (
    get_profiles_path,
    list_local_dbs,
    load_profiles,
    save_profiles,
)


class TestGetProfilesPath:
    def test_default(self):
        path = get_profiles_path()
        assert path.endswith("db_profiles.json")

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("OPENSPARTAN_PROFILES_PATH", "/custom/path.json")
        path = get_profiles_path()
        assert path == "/custom/path.json"


class TestLoadProfiles:
    def test_valid_json(self, tmp_path, monkeypatch):
        profiles_data = {
            "profiles": {
                "Player1": {"db_path": "/db.duckdb", "xuid": "123", "waypoint_player": "P1"},
                "Player2": {"db_path": "/db2.duckdb"},
            }
        }
        fp = tmp_path / "profiles.json"
        fp.write_text(json.dumps(profiles_data), encoding="utf-8")
        monkeypatch.setenv("OPENSPARTAN_PROFILES_PATH", str(fp))
        # Clear cache
        from src.utils.profiles import _load_profiles_cached

        _load_profiles_cached.cache_clear()

        result = load_profiles()
        assert "Player1" in result
        assert result["Player1"]["xuid"] == "123"
        assert "Player2" in result

    def test_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENSPARTAN_PROFILES_PATH", str(tmp_path / "missing.json"))
        from src.utils.profiles import _load_profiles_cached

        _load_profiles_cached.cache_clear()
        result = load_profiles()
        assert result == {}

    def test_invalid_json(self, tmp_path, monkeypatch):
        fp = tmp_path / "bad.json"
        fp.write_text("not json", encoding="utf-8")
        monkeypatch.setenv("OPENSPARTAN_PROFILES_PATH", str(fp))
        from src.utils.profiles import _load_profiles_cached

        _load_profiles_cached.cache_clear()
        result = load_profiles()
        assert result == {}

    def test_no_profiles_key(self, tmp_path, monkeypatch):
        fp = tmp_path / "empty.json"
        fp.write_text('{"other": "data"}', encoding="utf-8")
        monkeypatch.setenv("OPENSPARTAN_PROFILES_PATH", str(fp))
        from src.utils.profiles import _load_profiles_cached

        _load_profiles_cached.cache_clear()
        result = load_profiles()
        assert result == {}

    def test_empty_profile_name_skipped(self, tmp_path, monkeypatch):
        data = {"profiles": {"  ": {"db_path": "/x"}, "Valid": {"db_path": "/x"}}}
        fp = tmp_path / "profiles.json"
        fp.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setenv("OPENSPARTAN_PROFILES_PATH", str(fp))
        from src.utils.profiles import _load_profiles_cached

        _load_profiles_cached.cache_clear()
        result = load_profiles()
        assert "Valid" in result
        assert len(result) == 1


class TestSaveProfiles:
    def test_save_success(self, tmp_path, monkeypatch):
        fp = tmp_path / "profiles.json"
        monkeypatch.setenv("OPENSPARTAN_PROFILES_PATH", str(fp))
        from src.utils.profiles import _load_profiles_cached

        _load_profiles_cached.cache_clear()

        ok, msg = save_profiles({"Player1": {"db_path": "/db.duckdb"}})
        assert ok is True
        assert msg == ""
        # Verify written
        data = json.loads(fp.read_text(encoding="utf-8"))
        assert "profiles" in data
        assert "Player1" in data["profiles"]

    def test_save_failure(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENSPARTAN_PROFILES_PATH", str(tmp_path / "nodir" / "p.json"))
        from src.utils.profiles import _load_profiles_cached

        _load_profiles_cached.cache_clear()
        ok, msg = save_profiles({})
        assert ok is False
        assert "Impossible" in msg


class TestListLocalDbs:
    def test_no_localappdata(self, monkeypatch):
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        assert list_local_dbs() == []

    def test_dir_missing(self, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", "/nonexistent_dir")
        assert list_local_dbs() == []

    def test_with_dbs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        base = tmp_path / "OpenSpartan.Workshop" / "data"
        base.mkdir(parents=True)
        (base / "a.db").write_text("test")
        (base / "b.DB").write_text("test")
        (base / "c.txt").write_text("test")

        result = list_local_dbs()
        assert len(result) == 2
        assert all(p.lower().endswith(".db") for p in result)
