"""Tests pour src/ui/sync.py — Sprint 7ter (7t.5).

Couvre les fonctions pures et helpers (pas les sync API qui nécessitent SPNKr).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

# ============================================================================
# pick_latest_spnkr_db_if_any
# ============================================================================


class TestPickLatestSpnkrDbIfAny:
    def test_no_data_dir(self, tmp_path):
        from src.ui.sync import pick_latest_spnkr_db_if_any

        result = pick_latest_spnkr_db_if_any(tmp_path)
        assert result == ""

    def test_no_candidates(self, tmp_path):
        from src.ui.sync import pick_latest_spnkr_db_if_any

        (tmp_path / "data").mkdir()
        result = pick_latest_spnkr_db_if_any(tmp_path)
        assert result == ""

    def test_finds_spnkr_db(self, tmp_path):
        from src.ui.sync import pick_latest_spnkr_db_if_any

        data = tmp_path / "data"
        data.mkdir()
        db = data / "spnkr_test.db"
        db.write_text("content")

        result = pick_latest_spnkr_db_if_any(tmp_path)
        assert result != ""
        assert "spnkr_test.db" in result

    def test_picks_most_recent(self, tmp_path):
        from src.ui.sync import pick_latest_spnkr_db_if_any

        data = tmp_path / "data"
        data.mkdir()
        old = data / "spnkr_old.db"
        old.write_text("old")
        time.sleep(0.05)
        new = data / "spnkr_new.db"
        new.write_text("new content here")

        result = pick_latest_spnkr_db_if_any(tmp_path)
        assert "spnkr_new.db" in result

    def test_skips_empty_files(self, tmp_path):
        from src.ui.sync import pick_latest_spnkr_db_if_any

        data = tmp_path / "data"
        data.mkdir()
        empty = data / "spnkr_empty.db"
        empty.write_bytes(b"")
        nonempty = data / "spnkr_valid.db"
        nonempty.write_text("content")

        result = pick_latest_spnkr_db_if_any(tmp_path)
        assert "spnkr_valid.db" in result


# ============================================================================
# is_spnkr_db_path
# ============================================================================


class TestIsSpnkrDbPath:
    def test_duckdb_extension(self):
        from src.ui.sync import is_spnkr_db_path

        assert is_spnkr_db_path("/path/to/stats.duckdb") is True

    def test_db_extension_rejected(self):
        from src.ui.sync import is_spnkr_db_path

        assert is_spnkr_db_path("/path/to/data.db") is False

    def test_no_extension(self):
        from src.ui.sync import is_spnkr_db_path

        assert is_spnkr_db_path("/path/to/data") is False

    def test_empty(self):
        from src.ui.sync import is_spnkr_db_path

        assert is_spnkr_db_path("") is False


# ============================================================================
# cleanup_orphan_tmp_dbs
# ============================================================================


class TestCleanupOrphanTmpDbs:
    def test_cleans_old_tmp_files(self, tmp_path, monkeypatch):
        from src.ui.sync import cleanup_orphan_tmp_dbs

        # Mock session_state
        session_state = {}
        monkeypatch.setattr("src.ui.sync.st.session_state", session_state)

        data = tmp_path / "data"
        data.mkdir()

        old_tmp = data / "spnkr_test.tmp.1234567890.12345.db"
        old_tmp.write_text("tmp")
        # Set mtime to 2 hours ago
        old_mtime = time.time() - 7200
        os.utime(str(old_tmp), (old_mtime, old_mtime))

        cleanup_orphan_tmp_dbs(tmp_path)

        assert not old_tmp.exists()
        assert session_state.get("_tmp_db_cleanup_done") is True

    def test_skips_recent_tmp_files(self, tmp_path, monkeypatch):
        from src.ui.sync import cleanup_orphan_tmp_dbs

        session_state = {}
        monkeypatch.setattr("src.ui.sync.st.session_state", session_state)

        data = tmp_path / "data"
        data.mkdir()

        recent_tmp = data / "spnkr_test.tmp.9999999999.99.db"
        recent_tmp.write_text("tmp")
        # mtime is now (recent)

        cleanup_orphan_tmp_dbs(tmp_path)

        assert recent_tmp.exists()

    def test_no_op_if_already_done(self, tmp_path, monkeypatch):
        from src.ui.sync import cleanup_orphan_tmp_dbs

        session_state = {"_tmp_db_cleanup_done": True}
        monkeypatch.setattr("src.ui.sync.st.session_state", session_state)

        # Should return immediately
        cleanup_orphan_tmp_dbs(tmp_path)


# ============================================================================
# _get_sync_metadata_smart
# ============================================================================


class TestGetSyncMetadataSmart:
    def test_sqlite_returns_empty(self):
        from src.ui.sync import _get_sync_metadata_smart

        result = _get_sync_metadata_smart("/path/to/data.db")
        assert result["last_sync_at"] is None
        assert result["total_matches"] == 0

    def test_duckdb_nonexistent(self):
        from src.ui.sync import _get_sync_metadata_smart

        result = _get_sync_metadata_smart("/nonexistent/stats.duckdb")
        assert result["last_sync_at"] is None


# ============================================================================
# get_player_duckdb_path / is_duckdb_player
# ============================================================================


class TestGetPlayerDuckdbPath:
    def test_existing_player(self):
        from src.ui.sync import get_player_duckdb_path

        result = get_player_duckdb_path("NonexistentPlayer12345XYZ")
        # Either None (no db) or a Path
        assert result is None or isinstance(result, Path)

    def test_returns_path_for_existing(self, tmp_path, monkeypatch):
        from src.ui.sync import get_player_duckdb_path

        player_dir = tmp_path / "data" / "players" / "TestPlayer"
        player_dir.mkdir(parents=True)
        db = player_dir / "stats.duckdb"
        db.write_text("db")

        result = get_player_duckdb_path("TestPlayer", repo_root=tmp_path)
        assert result is not None
        assert result.name == "stats.duckdb"


class TestIsDuckdbPlayer:
    def test_nonexistent(self):
        from src.ui.sync import is_duckdb_player

        assert is_duckdb_player("NonexistentPlayer12345XYZ") is False

    def test_existing(self, tmp_path):
        from src.ui.sync import is_duckdb_player

        player_dir = tmp_path / "data" / "players" / "TestPlayer"
        player_dir.mkdir(parents=True)
        (player_dir / "stats.duckdb").write_text("db")

        assert is_duckdb_player("TestPlayer", repo_root=tmp_path) is True
