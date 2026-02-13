"""Tests Sprint 15 — Ingestion DuckDB-first.

Couvre :
- batch_insert / batch_upsert (remplaçant les boucles row-by-row)
- Plan de cast massif (CAST_PLAN)
- Audit de types incohérents
- Absence de flux SQLite intermédiaire
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

duckdb = pytest.importorskip("duckdb")


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db(tmp_path):
    """Crée une DB DuckDB temporaire avec le schéma sync complet."""
    db_path = tmp_path / "test_ingestion.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        # Tables minimales pour les tests d'insertion batch
        conn.execute("""
            CREATE TABLE medals_earned (
                match_id VARCHAR,
                medal_name_id BIGINT,
                count INTEGER,
                PRIMARY KEY (match_id, medal_name_id)
            )
        """)
        conn.execute("""
            CREATE TABLE highlight_events (
                match_id VARCHAR NOT NULL,
                event_type VARCHAR NOT NULL,
                time_ms INTEGER,
                xuid VARCHAR,
                gamertag VARCHAR,
                type_hint INTEGER,
                raw_json VARCHAR
            )
        """)
        conn.execute("""
            CREATE TABLE player_match_stats (
                match_id VARCHAR PRIMARY KEY,
                xuid VARCHAR NOT NULL,
                team_id TINYINT,
                team_mmr FLOAT,
                enemy_mmr FLOAT,
                kills_expected FLOAT,
                kills_stddev FLOAT,
                deaths_expected FLOAT,
                deaths_stddev FLOAT,
                assists_expected FLOAT,
                assists_stddev FLOAT,
                created_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE personal_score_awards (
                match_id VARCHAR NOT NULL,
                xuid VARCHAR NOT NULL,
                award_name VARCHAR NOT NULL,
                award_category VARCHAR,
                award_count INTEGER DEFAULT 1,
                award_score INTEGER DEFAULT 0,
                created_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE match_participants (
                match_id VARCHAR NOT NULL,
                xuid VARCHAR NOT NULL,
                team_id INTEGER,
                outcome INTEGER,
                gamertag VARCHAR,
                rank SMALLINT,
                score INTEGER,
                kills SMALLINT,
                deaths SMALLINT,
                assists SMALLINT,
                shots_fired INTEGER,
                shots_hit INTEGER,
                damage_dealt FLOAT,
                damage_taken FLOAT,
                PRIMARY KEY (match_id, xuid)
            )
        """)
        conn.execute("""
            CREATE TABLE xuid_aliases (
                xuid VARCHAR PRIMARY KEY,
                gamertag VARCHAR NOT NULL,
                last_seen TIMESTAMP,
                source VARCHAR,
                updated_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                playlist_id VARCHAR,
                playlist_name VARCHAR,
                map_id VARCHAR,
                map_name VARCHAR,
                pair_id VARCHAR,
                pair_name VARCHAR,
                game_variant_id VARCHAR,
                game_variant_name VARCHAR,
                outcome TINYINT,
                team_id TINYINT,
                rank SMALLINT,
                kills SMALLINT,
                deaths SMALLINT,
                assists SMALLINT,
                kda FLOAT,
                accuracy FLOAT,
                headshot_kills SMALLINT,
                max_killing_spree SMALLINT,
                time_played_seconds INTEGER,
                avg_life_seconds FLOAT,
                my_team_score SMALLINT,
                enemy_team_score SMALLINT,
                team_mmr FLOAT,
                enemy_mmr FLOAT,
                damage_dealt FLOAT,
                damage_taken FLOAT,
                shots_fired INTEGER,
                shots_hit INTEGER,
                grenade_kills SMALLINT,
                melee_kills SMALLINT,
                power_weapon_kills SMALLINT,
                score INTEGER,
                personal_score INTEGER,
                mode_category VARCHAR,
                is_ranked BOOLEAN DEFAULT FALSE,
                is_firefight BOOLEAN DEFAULT FALSE,
                left_early BOOLEAN DEFAULT FALSE,
                session_id VARCHAR,
                session_label VARCHAR,
                performance_score FLOAT,
                teammates_signature VARCHAR,
                known_teammates_count SMALLINT,
                is_with_friends BOOLEAN,
                friends_xuids VARCHAR,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
    finally:
        conn.close()

    return db_path


# =============================================================================
# Tests batch_insert_rows
# =============================================================================


class TestBatchInsertRows:
    """Tests pour l'insertion batch (remplace les boucles for row in rows)."""

    def test_batch_insert_medals(self, temp_db):
        """Vérifie l'insertion batch de médailles."""
        from src.data.sync.batch_insert import MEDAL_COLUMNS, batch_upsert_rows
        from src.data.sync.models import MedalEarnedRow

        conn = duckdb.connect(str(temp_db))
        try:
            rows = [
                MedalEarnedRow(match_id="m1", medal_name_id=1001, count=2),
                MedalEarnedRow(match_id="m1", medal_name_id=1002, count=1),
                MedalEarnedRow(match_id="m2", medal_name_id=1001, count=3),
            ]
            inserted = batch_upsert_rows(conn, "medals_earned", rows, MEDAL_COLUMNS)
            assert inserted == 3

            result = conn.execute("SELECT COUNT(*) FROM medals_earned").fetchone()[0]
            assert result == 3
        finally:
            conn.close()

    def test_batch_insert_events(self, temp_db):
        """Vérifie l'insertion batch de highlight events."""
        from src.data.sync.batch_insert import HIGHLIGHT_EVENT_COLUMNS, batch_insert_rows
        from src.data.sync.models import HighlightEventRow

        conn = duckdb.connect(str(temp_db))
        try:
            rows = [
                HighlightEventRow(
                    match_id="m1",
                    event_type="kill",
                    time_ms=1000,
                    xuid="x1",
                    gamertag="P1",
                    type_hint=1,
                    raw_json="{}",
                ),
                HighlightEventRow(
                    match_id="m1",
                    event_type="death",
                    time_ms=2000,
                    xuid="x1",
                    gamertag="P1",
                    type_hint=2,
                    raw_json="{}",
                ),
                HighlightEventRow(
                    match_id="m2",
                    event_type="kill",
                    time_ms=3000,
                    xuid="x2",
                    gamertag="P2",
                    type_hint=1,
                    raw_json="{}",
                ),
            ]
            inserted = batch_insert_rows(conn, "highlight_events", rows, HIGHLIGHT_EVENT_COLUMNS)
            assert inserted == 3

            result = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
            assert result == 3
        finally:
            conn.close()

    def test_batch_insert_participants(self, temp_db):
        """Vérifie l'insertion batch de participants."""
        from src.data.sync.batch_insert import PARTICIPANT_COLUMNS, batch_upsert_rows
        from src.data.sync.models import MatchParticipantRow

        conn = duckdb.connect(str(temp_db))
        try:
            rows = [
                MatchParticipantRow(
                    match_id="m1",
                    xuid="x1",
                    team_id=0,
                    outcome=2,
                    gamertag="Player1",
                    rank=1,
                    score=1500,
                    kills=15,
                    deaths=8,
                    assists=5,
                    shots_fired=200,
                    shots_hit=90,
                    damage_dealt=3500.0,
                    damage_taken=2800.0,
                ),
                MatchParticipantRow(
                    match_id="m1",
                    xuid="x2",
                    team_id=1,
                    outcome=3,
                    gamertag="Player2",
                    rank=2,
                    score=1200,
                    kills=10,
                    deaths=12,
                    assists=3,
                ),
            ]
            inserted = batch_upsert_rows(conn, "match_participants", rows, PARTICIPANT_COLUMNS)
            assert inserted == 2

            result = conn.execute(
                "SELECT gamertag, kills FROM match_participants ORDER BY rank"
            ).fetchall()
            assert result[0][0] == "Player1"
            assert result[0][1] == 15
            assert result[1][0] == "Player2"
        finally:
            conn.close()

    def test_batch_insert_empty_list(self, temp_db):
        """Vérifie que les listes vides sont gérées correctement."""
        from src.data.sync.batch_insert import MEDAL_COLUMNS, batch_insert_rows

        conn = duckdb.connect(str(temp_db))
        try:
            inserted = batch_insert_rows(conn, "medals_earned", [], MEDAL_COLUMNS)
            assert inserted == 0
        finally:
            conn.close()

    def test_batch_upsert_replaces_existing(self, temp_db):
        """Vérifie que l'upsert remplace les lignes existantes."""
        from src.data.sync.batch_insert import MEDAL_COLUMNS, batch_upsert_rows
        from src.data.sync.models import MedalEarnedRow

        conn = duckdb.connect(str(temp_db))
        try:
            # Première insertion
            rows = [MedalEarnedRow(match_id="m1", medal_name_id=1001, count=2)]
            batch_upsert_rows(conn, "medals_earned", rows, MEDAL_COLUMNS)

            # Upsert avec nouvelle valeur
            rows2 = [MedalEarnedRow(match_id="m1", medal_name_id=1001, count=5)]
            batch_upsert_rows(conn, "medals_earned", rows2, MEDAL_COLUMNS)

            result = conn.execute(
                "SELECT count FROM medals_earned WHERE match_id = 'm1' AND medal_name_id = 1001"
            ).fetchone()
            assert result[0] == 5
        finally:
            conn.close()

    def test_batch_insert_with_dicts(self, temp_db):
        """Vérifie l'insertion batch avec des dictionnaires."""
        from src.data.sync.batch_insert import MEDAL_COLUMNS, batch_insert_rows

        conn = duckdb.connect(str(temp_db))
        try:
            rows = [
                {"match_id": "m1", "medal_name_id": 2001, "count": 1},
                {"match_id": "m2", "medal_name_id": 2002, "count": 3},
            ]
            inserted = batch_insert_rows(conn, "medals_earned", rows, MEDAL_COLUMNS)
            assert inserted == 2
        finally:
            conn.close()

    def test_batch_insert_large_volume(self, temp_db):
        """Vérifie l'insertion batch sur un volume important (100+ rows)."""
        from src.data.sync.batch_insert import HIGHLIGHT_EVENT_COLUMNS, batch_insert_rows
        from src.data.sync.models import HighlightEventRow

        conn = duckdb.connect(str(temp_db))
        try:
            rows = [
                HighlightEventRow(
                    match_id=f"m{i % 10}",
                    event_type="kill" if i % 2 == 0 else "death",
                    time_ms=i * 1000,
                    xuid=f"x{i % 5}",
                    gamertag=f"Player{i % 5}",
                    type_hint=1 if i % 2 == 0 else 2,
                    raw_json="{}",
                )
                for i in range(200)
            ]
            inserted = batch_insert_rows(conn, "highlight_events", rows, HIGHLIGHT_EVENT_COLUMNS)
            assert inserted == 200

            result = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
            assert result == 200
        finally:
            conn.close()

    def test_batch_insert_personal_scores(self, temp_db):
        """Vérifie l'insertion batch des personal score awards."""
        from src.data.sync.batch_insert import PERSONAL_SCORE_COLUMNS, batch_insert_rows

        conn = duckdb.connect(str(temp_db))
        try:
            now = datetime.now(timezone.utc)
            rows = [
                {
                    "match_id": "m1",
                    "xuid": "x1",
                    "award_name": "KillLeader",
                    "award_category": "kill",
                    "award_count": 1,
                    "award_score": 100,
                    "created_at": now,
                },
                {
                    "match_id": "m1",
                    "xuid": "x1",
                    "award_name": "Assist",
                    "award_category": "assist",
                    "award_count": 3,
                    "award_score": 75,
                    "created_at": now,
                },
            ]
            inserted = batch_insert_rows(
                conn, "personal_score_awards", rows, PERSONAL_SCORE_COLUMNS
            )
            assert inserted == 2
        finally:
            conn.close()

    def test_batch_insert_aliases(self, temp_db):
        """Vérifie l'upsert batch des aliases."""
        from src.data.sync.batch_insert import ALIAS_COLUMNS, batch_upsert_rows

        conn = duckdb.connect(str(temp_db))
        try:
            now = datetime.now(timezone.utc)
            rows = [
                {
                    "xuid": "x1",
                    "gamertag": "Player1",
                    "last_seen": now,
                    "source": "sync",
                    "updated_at": now,
                },
                {
                    "xuid": "x2",
                    "gamertag": "Player2",
                    "last_seen": now,
                    "source": "sync",
                    "updated_at": now,
                },
            ]
            inserted = batch_upsert_rows(conn, "xuid_aliases", rows, ALIAS_COLUMNS)
            assert inserted == 2
        finally:
            conn.close()


# =============================================================================
# Tests CAST_PLAN (typage centralisé)
# =============================================================================


class TestCastPlan:
    """Tests pour le plan de cast massif (Sprint 15.3)."""

    def test_cast_plan_covers_critical_tables(self):
        """Le CAST_PLAN doit couvrir les tables critiques."""
        from src.data.sync.batch_insert import CAST_PLAN, CRITICAL_TABLES

        for table in CRITICAL_TABLES:
            assert table in CAST_PLAN, f"Table critique absente du CAST_PLAN: {table}"
            assert len(CAST_PLAN[table]) > 0, f"CAST_PLAN vide pour {table}"

    def test_cast_plan_match_stats_complete(self):
        """Le CAST_PLAN pour match_stats doit contenir les colonnes essentielles."""
        from src.data.sync.batch_insert import CAST_PLAN

        required = {
            "match_id",
            "start_time",
            "kills",
            "deaths",
            "assists",
            "kda",
            "accuracy",
            "team_mmr",
            "enemy_mmr",
            "outcome",
        }
        actual = set(CAST_PLAN["match_stats"].keys())
        missing = required - actual
        assert not missing, f"Colonnes manquantes dans CAST_PLAN[match_stats]: {missing}"

    def test_coerce_value_float(self):
        """Vérifie la conversion float."""
        from src.data.sync.batch_insert import _coerce_value

        assert _coerce_value(1.5, "FLOAT") == 1.5
        assert _coerce_value("3.14", "FLOAT") == 3.14
        assert _coerce_value(None, "FLOAT") is None
        assert _coerce_value(float("nan"), "FLOAT") is None
        assert _coerce_value(float("inf"), "FLOAT") is None

    def test_coerce_value_int(self):
        """Vérifie la conversion int."""
        from src.data.sync.batch_insert import _coerce_value

        assert _coerce_value(42, "INTEGER") == 42
        assert _coerce_value(3.7, "SMALLINT") == 3
        assert _coerce_value(None, "INTEGER") is None
        assert _coerce_value(float("nan"), "INTEGER") is None

    def test_coerce_value_varchar(self):
        """Vérifie la conversion varchar."""
        from src.data.sync.batch_insert import _coerce_value

        assert _coerce_value("hello", "VARCHAR") == "hello"
        assert _coerce_value(123, "VARCHAR") == "123"
        assert _coerce_value(None, "VARCHAR") is None
        assert _coerce_value("nan", "VARCHAR") is None
        assert _coerce_value("None", "VARCHAR") is None

    def test_coerce_value_boolean(self):
        """Vérifie la conversion boolean."""
        from src.data.sync.batch_insert import _coerce_value

        assert _coerce_value(True, "BOOLEAN") is True
        assert _coerce_value(False, "BOOLEAN") is False
        assert _coerce_value(1, "BOOLEAN") is True
        assert _coerce_value(0, "BOOLEAN") is False
        assert _coerce_value("true", "BOOLEAN") is True
        assert _coerce_value(None, "BOOLEAN") is None

    def test_coerce_value_timestamp(self):
        """Vérifie la conversion timestamp."""
        from src.data.sync.batch_insert import _coerce_value

        now = datetime.now(timezone.utc)
        assert _coerce_value(now, "TIMESTAMP") == now
        assert _coerce_value("2024-01-15T14:30:00Z", "TIMESTAMP") is not None
        assert _coerce_value(None, "TIMESTAMP") is None

    def test_coerce_row_types(self):
        """Vérifie la conversion d'une row complète."""
        from src.data.sync.batch_insert import coerce_row_types

        row = {
            "match_id": "m1",
            "kills": 15.0,  # float → SMALLINT
            "deaths": "8",  # str → SMALLINT
            "kda": "1.875",  # str → FLOAT
            "accuracy": float("nan"),  # nan → None
            "is_firefight": 0,  # int → BOOLEAN
        }
        result = coerce_row_types(row, "match_stats")

        assert result["match_id"] == "m1"
        assert result["kills"] == 15
        assert result["deaths"] == 8
        assert result["kda"] == 1.875
        assert result["accuracy"] is None
        assert result["is_firefight"] is False

    def test_coerce_row_unknown_table(self):
        """Les tables inconnues ne sont pas modifiées."""
        from src.data.sync.batch_insert import coerce_row_types

        row = {"col1": "val1", "col2": 42}
        result = coerce_row_types(row, "nonexistent_table")
        assert result == row


# =============================================================================
# Tests audit de types (Sprint 15.4)
# =============================================================================


class TestAuditTypes:
    """Tests pour l'audit de schéma."""

    def test_audit_no_issues_on_correct_schema(self, temp_db):
        """Un schéma correct ne doit pas produire d'issues (sauf EXTRA_COLUMN)."""
        from src.data.sync.batch_insert import audit_column_types

        conn = duckdb.connect(str(temp_db))
        try:
            issues = audit_column_types(conn, "match_stats")
            # Seules les EXTRA_COLUMN sont acceptables (colonnes en DB non dans CAST_PLAN)
            type_mismatches = [i for i in issues if i["status"] == "TYPE_MISMATCH"]
            missing_cols = [i for i in issues if i["status"] == "MISSING_COLUMN"]
            assert not type_mismatches, f"TYPE_MISMATCH détecté: {type_mismatches}"
            assert not missing_cols, f"MISSING_COLUMN détecté: {missing_cols}"
        finally:
            conn.close()

    def test_audit_detects_missing_column(self, tmp_path):
        """L'audit doit détecter une colonne manquante."""
        from src.data.sync.batch_insert import audit_column_types

        db_path = tmp_path / "missing_col.duckdb"
        conn = duckdb.connect(str(db_path))
        try:
            # Créer une table avec une colonne manquante
            conn.execute("""
                CREATE TABLE match_stats (
                    match_id VARCHAR PRIMARY KEY,
                    kills SMALLINT
                )
            """)
            issues = audit_column_types(conn, "match_stats")
            missing = [i for i in issues if i["status"] == "MISSING_COLUMN"]
            assert len(missing) > 0
            missing_cols = {i["column"] for i in missing}
            assert "deaths" in missing_cols
            assert "assists" in missing_cols
            assert "kda" in missing_cols
        finally:
            conn.close()

    def test_audit_detects_type_mismatch(self, tmp_path):
        """L'audit doit détecter un type incorrect."""
        from src.data.sync.batch_insert import audit_column_types

        db_path = tmp_path / "type_mismatch.duckdb"
        conn = duckdb.connect(str(db_path))
        try:
            # kills devrait être SMALLINT, pas VARCHAR
            conn.execute("""
                CREATE TABLE match_stats (
                    match_id VARCHAR PRIMARY KEY,
                    start_time TIMESTAMP,
                    kills VARCHAR
                )
            """)
            issues = audit_column_types(conn, "match_stats")
            type_issues = [
                i for i in issues if i["status"] == "TYPE_MISMATCH" and i["column"] == "kills"
            ]
            assert len(type_issues) == 1
            assert type_issues[0]["expected_type"] == "SMALLINT"
            assert type_issues[0]["actual_type"] == "VARCHAR"
        finally:
            conn.close()

    def test_audit_all_tables(self, temp_db):
        """audit_all_tables doit auditer toutes les tables connues."""
        from src.data.sync.batch_insert import audit_all_tables

        conn = duckdb.connect(str(temp_db))
        try:
            results = audit_all_tables(conn)
            # La DB de test a un schéma correct pour les tables présentes
            for table, issues in results.items():
                critical = [i for i in issues if i["status"] in ("TYPE_MISMATCH",)]
                assert not critical, f"Issues critiques inattendues sur {table}: {critical}"
        finally:
            conn.close()

    def test_audit_player_db_script(self, temp_db):
        """Le script diagnose_player_db.audit_player_db_types fonctionne."""
        from scripts.diagnose_player_db import audit_player_db_types

        result = audit_player_db_types(str(temp_db))
        assert "error" not in result
        assert isinstance(result["total_issues"], int)
        assert isinstance(result["critical_issues"], int)

    def test_audit_types_compatible_wider_int(self, tmp_path):
        """Un INTEGER pour un SMALLINT doit être accepté (type plus large)."""
        from src.data.sync.batch_insert import audit_column_types

        db_path = tmp_path / "wider_int.duckdb"
        conn = duckdb.connect(str(db_path))
        try:
            conn.execute("""
                CREATE TABLE match_stats (
                    match_id VARCHAR PRIMARY KEY,
                    kills INTEGER
                )
            """)
            issues = audit_column_types(conn, "match_stats")
            kills_issues = [
                i for i in issues if i["column"] == "kills" and i["status"] == "TYPE_MISMATCH"
            ]
            # INTEGER est plus large que SMALLINT → pas d'erreur
            assert not kills_issues
        finally:
            conn.close()


# =============================================================================
# Tests anti-régression : absence de SQLite intermédiaire
# =============================================================================


class TestNoSQLiteIntermediary:
    """Vérifie l'absence de flux SQLite dans la chaîne active."""

    def test_no_sqlite_import_in_sync(self):
        """Aucun import sqlite3 dans src/data/sync/."""
        import importlib
        import inspect

        modules = [
            "src.data.sync.engine",
            "src.data.sync.transformers",
            "src.data.sync.batch_insert",
            "src.data.sync.models",
        ]
        for mod_name in modules:
            try:
                mod = importlib.import_module(mod_name)
                source = inspect.getsource(mod)
                assert "import sqlite3" not in source, f"sqlite3 trouvé dans {mod_name}"
                assert "sqlite_master" not in source, f"sqlite_master trouvé dans {mod_name}"
            except ImportError:
                pass  # Module optionnel

    def test_no_sqlite_import_in_backfill_core(self):
        """Aucun import sqlite3 dans scripts/backfill/core.py."""
        import importlib
        import inspect

        mod = importlib.import_module("scripts.backfill.core")
        source = inspect.getsource(mod)
        assert "import sqlite3" not in source
        assert "sqlite_master" not in source


# =============================================================================
# Tests absence Parquet dans le flux d'ingestion
# =============================================================================


class TestNoParquetInIngestion:
    """Le flux d'ingestion ne dépend pas de Parquet."""

    def test_no_parquet_in_batch_insert(self):
        """batch_insert.py ne contient pas de code Parquet fonctionnel."""
        import importlib
        import inspect

        mod = importlib.import_module("src.data.sync.batch_insert")
        source = inspect.getsource(mod)
        # Vérifier qu'il n'y a pas de fonctions Parquet (read_parquet, to_parquet)
        # Les commentaires/docstrings mentionnant Parquet sont acceptés
        assert "read_parquet" not in source, "read_parquet dans batch_insert.py"
        assert "to_parquet" not in source, "to_parquet dans batch_insert.py"
        assert "import parquet" not in source.lower(), "import parquet dans batch_insert.py"

    def test_no_parquet_in_engine_sync_path(self):
        """Le moteur de sync n'utilise pas Parquet pour l'ingestion."""
        import importlib
        import inspect

        mod = importlib.import_module("src.data.sync.engine")
        source = inspect.getsource(mod)
        assert "read_parquet" not in source, "read_parquet dans engine.py"
        assert "to_parquet" not in source, "to_parquet dans engine.py"
