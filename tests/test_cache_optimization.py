"""Tests pour le système de cache DB optimisé."""

from __future__ import annotations

import contextlib
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.db.loaders_cached import (
    get_cache_stats,
    has_cache_tables,
    load_friends,
)
from src.db.schema import (
    get_all_cache_table_ddl,
    get_cache_table_names,
)


class TestCacheSchema:
    """Tests pour le schéma des tables de cache."""

    def test_get_all_cache_table_ddl_returns_list(self):
        """DDL doit retourner une liste non vide."""
        ddl = get_all_cache_table_ddl()
        assert isinstance(ddl, list)
        assert len(ddl) > 0

    def test_get_cache_table_names_returns_expected_tables(self):
        """Les noms de tables attendus doivent être présents."""
        names = get_cache_table_names()
        assert "MatchCache" in names
        assert "Friends" in names
        assert "PerformanceScores" in names
        assert "TeammatesAggregate" in names
        assert "CacheMeta" in names

    def test_create_tables_in_memory_db(self):
        """Les tables doivent se créer sans erreur."""
        con = sqlite3.connect(":memory:")
        cur = con.cursor()

        for ddl in get_all_cache_table_ddl():
            try:
                cur.execute(ddl)
            except sqlite3.OperationalError as e:
                if "already exists" not in str(e).lower():
                    raise

        con.commit()

        # Vérifier que les tables existent
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}

        for expected in get_cache_table_names():
            assert expected in tables, f"Table {expected} non créée"

        con.close()


class TestHasCacheTables:
    """Tests pour has_cache_tables()."""

    def test_returns_false_for_nonexistent_file(self):
        """Doit retourner False pour un fichier inexistant."""
        result = has_cache_tables("/nonexistent/path/db.db")
        assert result is False

    def test_returns_false_for_empty_db(self):
        """Doit retourner False pour une DB sans MatchCache."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            con = sqlite3.connect(db_path)
            con.close()

            result = has_cache_tables(db_path)
            assert result is False
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_returns_true_for_populated_cache(self):
        """Doit retourner True si MatchCache contient des données."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()

            # Créer la table
            for ddl in get_all_cache_table_ddl():
                with contextlib.suppress(sqlite3.OperationalError):
                    cur.execute(ddl)

            # Insérer une ligne
            cur.execute("""
                INSERT INTO MatchCache (match_id, xuid, start_time, kills, deaths, assists)
                VALUES ('test-123', '12345', '2025-01-25T10:00:00Z', 10, 5, 3)
            """)
            con.commit()
            con.close()

            result = has_cache_tables(db_path)
            assert result is True
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestLoadFriends:
    """Tests pour load_friends()."""

    def test_returns_empty_list_for_no_friends(self):
        """Doit retourner une liste vide si pas d'amis."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()

            for ddl in get_all_cache_table_ddl():
                with contextlib.suppress(sqlite3.OperationalError):
                    cur.execute(ddl)

            con.commit()
            con.close()

            friends = load_friends(db_path, "12345")
            assert friends == []
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_returns_friends_for_owner(self):
        """Doit retourner les amis du propriétaire."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()

            for ddl in get_all_cache_table_ddl():
                with contextlib.suppress(sqlite3.OperationalError):
                    cur.execute(ddl)

            # Insérer des amis
            cur.execute("""
                INSERT INTO Friends (owner_xuid, friend_xuid, friend_gamertag, nickname)
                VALUES ('owner123', 'friend456', 'TestFriend', 'TF')
            """)
            con.commit()
            con.close()

            friends = load_friends(db_path, "owner123")
            assert len(friends) == 1
            assert friends[0]["gamertag"] == "TestFriend"
            assert friends[0]["nickname"] == "TF"
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestGetCacheStats:
    """Tests pour get_cache_stats()."""

    def test_returns_has_cache_false_for_empty_db(self):
        """Doit indiquer has_cache=False pour une DB sans cache."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            con = sqlite3.connect(db_path)
            con.close()

            stats = get_cache_stats(db_path, "12345")
            assert stats["has_cache"] is False
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_returns_stats_for_populated_cache(self):
        """Doit retourner des stats pour un cache peuplé."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()

            for ddl in get_all_cache_table_ddl():
                with contextlib.suppress(sqlite3.OperationalError):
                    cur.execute(ddl)

            # Insérer des matchs
            for i in range(5):
                cur.execute(
                    """
                    INSERT INTO MatchCache (
                        match_id, xuid, start_time, session_id, kills, deaths, assists
                    ) VALUES (?, '12345', ?, ?, 10, 5, 3)
                """,
                    (f"match-{i}", f"2025-01-25T{10+i}:00:00Z", i // 3),
                )

            # Version du schéma
            cur.execute("""
                INSERT INTO CacheMeta (key, value) VALUES ('schema_version', '1.0')
            """)

            con.commit()
            con.close()

            stats = get_cache_stats(db_path, "12345")
            assert stats["has_cache"] is True
            assert stats["match_count"] == 5
            assert stats["session_count"] == 2  # 0 et 1
            assert stats["schema_version"] == "1.0"
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestSessionCalculation:
    """Tests pour le calcul des sessions.

    Note: Ces tests sont skip car scripts/migrate_to_cache.py a été supprimé
    après la migration complète vers l'architecture DuckDB v4.
    """

    @pytest.mark.skip(reason="scripts/migrate_to_cache.py supprimé (migration terminée)")
    def test_session_gap_creates_new_session(self):
        """Un gap > 2h doit créer une nouvelle session."""
        from scripts.migrate_to_cache import (
            MatchForSession,
            compute_sessions_with_teammates,
        )

        now = datetime.now(timezone.utc)

        matches = [
            MatchForSession("m1", now - timedelta(hours=5), ""),
            MatchForSession("m2", now - timedelta(hours=4, minutes=50), ""),  # +10min
            MatchForSession("m3", now - timedelta(hours=2), ""),  # +2h50 → nouvelle session
            MatchForSession("m4", now - timedelta(hours=1, minutes=30), ""),  # +30min
        ]

        sessions = compute_sessions_with_teammates(matches, gap_minutes=120)

        # m1 et m2 dans session 0, m3 et m4 dans session 1
        assert sessions["m1"][0] == 0
        assert sessions["m2"][0] == 0
        assert sessions["m3"][0] == 1
        assert sessions["m4"][0] == 1

    @pytest.mark.skip(reason="scripts/migrate_to_cache.py supprimé (migration terminée)")
    def test_teammate_change_creates_new_session(self):
        """Un changement de coéquipiers doit créer une nouvelle session."""
        import scripts.migrate_to_cache as migrate_module
        from scripts.migrate_to_cache import (
            MatchForSession,
            compute_sessions_with_teammates,
        )

        now = datetime.now(timezone.utc)

        # Patcher FRIENDS_XUIDS pour le test avec nos XUIDs de test
        original_friends = migrate_module.FRIENDS_XUIDS
        migrate_module.FRIENDS_XUIDS = {"alice", "bob"}

        try:
            matches = [
                MatchForSession("m1", now - timedelta(hours=3), "alice,bob"),
                MatchForSession("m2", now - timedelta(hours=2, minutes=50), "alice,bob"),
                MatchForSession("m3", now - timedelta(hours=2, minutes=40), "alice"),  # bob parti
                MatchForSession("m4", now - timedelta(hours=2, minutes=30), "alice"),
            ]

            sessions = compute_sessions_with_teammates(matches, gap_minutes=120)

            # Selon la règle actuelle: un ami qui part ne crée PAS de nouvelle session
            # (sauf si on passe à "sans amis")
            # m3 a encore "alice" donc on reste dans la même session
            assert sessions["m1"][0] == 0
            assert sessions["m2"][0] == 0
            assert sessions["m3"][0] == 0  # alice est toujours là, même session
            assert sessions["m4"][0] == 0
        finally:
            migrate_module.FRIENDS_XUIDS = original_friends

    @pytest.mark.skip(reason="scripts/migrate_to_cache.py supprimé (migration terminée)")
    def test_friend_joining_creates_new_session(self):
        """Un ami qui rejoint doit créer une nouvelle session."""
        import scripts.migrate_to_cache as migrate_module
        from scripts.migrate_to_cache import (
            MatchForSession,
            compute_sessions_with_teammates,
        )

        now = datetime.now(timezone.utc)

        original_friends = migrate_module.FRIENDS_XUIDS
        migrate_module.FRIENDS_XUIDS = {"alice", "bob"}

        try:
            matches = [
                MatchForSession("m1", now - timedelta(hours=3), "alice"),
                MatchForSession("m2", now - timedelta(hours=2, minutes=50), "alice"),
                MatchForSession(
                    "m3", now - timedelta(hours=2, minutes=40), "alice,bob"
                ),  # bob rejoint
                MatchForSession("m4", now - timedelta(hours=2, minutes=30), "alice,bob"),
            ]

            sessions = compute_sessions_with_teammates(matches, gap_minutes=120)

            # Un ami qui rejoint crée une nouvelle session
            assert sessions["m1"][0] == 0
            assert sessions["m2"][0] == 0
            assert sessions["m3"][0] == 1  # Nouvelle session car bob rejoint
            assert sessions["m4"][0] == 1
        finally:
            migrate_module.FRIENDS_XUIDS = original_friends

    @pytest.mark.skip(reason="scripts/migrate_to_cache.py supprimé (migration terminée)")
    def test_going_solo_creates_new_session(self):
        """Passer de 'avec amis' à solo doit créer une nouvelle session."""
        import scripts.migrate_to_cache as migrate_module
        from scripts.migrate_to_cache import (
            MatchForSession,
            compute_sessions_with_teammates,
        )

        now = datetime.now(timezone.utc)

        original_friends = migrate_module.FRIENDS_XUIDS
        migrate_module.FRIENDS_XUIDS = {"alice", "bob"}

        try:
            matches = [
                MatchForSession("m1", now - timedelta(hours=3), "alice,bob"),
                MatchForSession("m2", now - timedelta(hours=2, minutes=50), "alice,bob"),
                MatchForSession("m3", now - timedelta(hours=2, minutes=40), ""),  # Passage à solo
                MatchForSession("m4", now - timedelta(hours=2, minutes=30), ""),
            ]

            sessions = compute_sessions_with_teammates(matches, gap_minutes=120)

            # Passage à solo (sans amis) crée une nouvelle session
            assert sessions["m1"][0] == 0
            assert sessions["m2"][0] == 0
            assert sessions["m3"][0] == 1  # Nouvelle session car passage à solo
            assert sessions["m4"][0] == 1
        finally:
            migrate_module.FRIENDS_XUIDS = original_friends

    @pytest.mark.skip(reason="scripts/migrate_to_cache.py supprimé (migration terminée)")
    def test_solo_play_is_single_session(self):
        """Jouer seul pendant plusieurs heures = une seule session (si gap < 2h)."""
        from scripts.migrate_to_cache import (
            MatchForSession,
            compute_sessions_with_teammates,
        )

        now = datetime.now(timezone.utc)

        matches = [
            MatchForSession("m1", now - timedelta(hours=3), ""),
            MatchForSession("m2", now - timedelta(hours=2, minutes=30), ""),
            MatchForSession("m3", now - timedelta(hours=2), ""),
            MatchForSession("m4", now - timedelta(hours=1, minutes=30), ""),
        ]

        sessions = compute_sessions_with_teammates(matches, gap_minutes=120)

        # Tous dans la même session (gap max = 30 min)
        assert all(sessions[m.match_id][0] == 0 for m in matches)


class TestMatchPerformanceScore:
    """Tests pour le score de performance par match.

    Note: Ces tests sont skip car scripts/migrate_to_cache.py a été supprimé
    après la migration complète vers l'architecture DuckDB v4.
    """

    @pytest.mark.skip(reason="scripts/migrate_to_cache.py supprimé (migration terminée)")
    def test_compute_match_performance_score_basic(self):
        """Score basique avec toutes les composantes."""
        from scripts.migrate_to_cache import compute_match_performance_score

        # Match moyen : KD=1, Win, Accuracy=50%
        score = compute_match_performance_score(
            kills=10,
            deaths=10,
            assists=5,
            accuracy=50.0,
            kda=1.5,
            outcome=2,
        )

        assert score is not None
        assert 50 <= score <= 80  # Score moyen-bon

    @pytest.mark.skip(reason="scripts/migrate_to_cache.py supprimé (migration terminée)")
    def test_compute_match_performance_score_high_kd(self):
        """Un bon KD doit donner un meilleur score."""
        from scripts.migrate_to_cache import compute_match_performance_score

        score_low = compute_match_performance_score(
            kills=5,
            deaths=10,
            assists=2,
            accuracy=50.0,
            kda=0.5,
            outcome=3,
        )

        score_high = compute_match_performance_score(
            kills=20,
            deaths=5,
            assists=5,
            accuracy=50.0,
            kda=5.0,
            outcome=2,
        )

        assert score_high > score_low

    @pytest.mark.skip(reason="scripts/migrate_to_cache.py supprimé (migration terminée)")
    def test_compute_match_performance_score_with_none(self):
        """Le score doit fonctionner avec des valeurs None."""
        from scripts.migrate_to_cache import compute_match_performance_score

        score = compute_match_performance_score(
            kills=10,
            deaths=5,
            assists=3,
            accuracy=None,
            kda=None,
            outcome=None,
        )

        # Seul KD est disponible → score basé uniquement sur ça
        assert score is not None
        assert score > 50  # KD=2 → bon score
