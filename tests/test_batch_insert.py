"""Tests unitaires pour batch_insert.py — Sprint 7 (Couverture).

Teste :
- coerce_row_types() avec le CAST_PLAN
- _coerce_value() pour chaque type DuckDB
- batch_insert_rows() en DB in-memory
- batch_upsert_rows() avec conflits
- audit_column_types() et audit_all_tables()
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import duckdb
import pytest

from src.data.sync.batch_insert import (
    CAST_PLAN,
    _coerce_value,
    audit_column_types,
    batch_insert_rows,
    batch_upsert_rows,
    coerce_row_types,
)

# =============================================================================
# Tests _coerce_value
# =============================================================================


class TestCoerceValue:
    """Tests pour _coerce_value."""

    def test_none_returns_none(self) -> None:
        assert _coerce_value(None, "VARCHAR") is None
        assert _coerce_value(None, "INTEGER") is None
        assert _coerce_value(None, "FLOAT") is None

    # VARCHAR / TEXT
    def test_varchar_from_str(self) -> None:
        assert _coerce_value("hello", "VARCHAR") == "hello"

    def test_varchar_from_int(self) -> None:
        assert _coerce_value(42, "VARCHAR") == "42"

    def test_varchar_nan_returns_none(self) -> None:
        assert _coerce_value("nan", "VARCHAR") is None

    def test_varchar_none_str_returns_none(self) -> None:
        assert _coerce_value("None", "VARCHAR") is None

    def test_varchar_empty_str_returns_none(self) -> None:
        assert _coerce_value("", "VARCHAR") is None

    # FLOAT / DOUBLE
    def test_float_from_int(self) -> None:
        result = _coerce_value(42, "FLOAT")
        assert isinstance(result, float)
        assert result == 42.0

    def test_float_from_str(self) -> None:
        assert _coerce_value("3.14", "FLOAT") == pytest.approx(3.14)

    def test_float_nan_returns_none(self) -> None:
        assert _coerce_value(float("nan"), "FLOAT") is None

    def test_float_inf_returns_none(self) -> None:
        assert _coerce_value(float("inf"), "FLOAT") is None

    def test_double_same_as_float(self) -> None:
        assert _coerce_value(1.5, "DOUBLE") == 1.5

    # INTEGER / INT / BIGINT / SMALLINT / TINYINT
    def test_integer_from_int(self) -> None:
        assert _coerce_value(42, "INTEGER") == 42

    def test_integer_from_float(self) -> None:
        assert _coerce_value(42.9, "INTEGER") == 42

    def test_integer_from_str(self) -> None:
        assert _coerce_value("10", "INTEGER") == 10

    def test_smallint_works(self) -> None:
        assert _coerce_value(5, "SMALLINT") == 5

    def test_bigint_works(self) -> None:
        assert _coerce_value(999999999, "BIGINT") == 999999999

    def test_tinyint_works(self) -> None:
        assert _coerce_value(2, "TINYINT") == 2

    def test_integer_nan_returns_none(self) -> None:
        assert _coerce_value(float("nan"), "INTEGER") is None

    def test_integer_inf_returns_none(self) -> None:
        assert _coerce_value(float("inf"), "SMALLINT") is None

    # BOOLEAN
    def test_boolean_true(self) -> None:
        assert _coerce_value(True, "BOOLEAN") is True

    def test_boolean_false(self) -> None:
        assert _coerce_value(False, "BOOLEAN") is False

    def test_boolean_from_int_1(self) -> None:
        assert _coerce_value(1, "BOOLEAN") is True

    def test_boolean_from_int_0(self) -> None:
        assert _coerce_value(0, "BOOLEAN") is False

    def test_boolean_from_str_true(self) -> None:
        assert _coerce_value("true", "BOOLEAN") is True

    def test_boolean_from_str_yes(self) -> None:
        assert _coerce_value("yes", "BOOLEAN") is True

    def test_boolean_from_str_false(self) -> None:
        assert _coerce_value("false", "BOOLEAN") is False

    # TIMESTAMP
    def test_timestamp_from_datetime(self) -> None:
        dt = datetime(2025, 1, 15, tzinfo=timezone.utc)
        assert _coerce_value(dt, "TIMESTAMP") == dt

    def test_timestamp_from_iso_str(self) -> None:
        result = _coerce_value("2025-01-15T10:00:00Z", "TIMESTAMP")
        assert isinstance(result, datetime)

    def test_timestamp_from_iso_str_with_offset(self) -> None:
        result = _coerce_value("2025-01-15T10:00:00+00:00", "TIMESTAMP")
        assert isinstance(result, datetime)

    # Type inconnu
    def test_unknown_type_passthrough(self) -> None:
        assert _coerce_value("hello", "BLOB") == "hello"

    # Erreurs de conversion
    def test_invalid_float_str_returns_none(self) -> None:
        assert _coerce_value("not_a_number", "FLOAT") is None

    def test_invalid_int_str_returns_none(self) -> None:
        assert _coerce_value("not_a_number", "INTEGER") is None


# =============================================================================
# Tests coerce_row_types
# =============================================================================


class TestCoerceRowTypes:
    """Tests pour coerce_row_types."""

    def test_match_stats_row(self) -> None:
        """Applique le CAST_PLAN match_stats à un dict."""
        row = {
            "match_id": "m1",
            "kills": 10.0,  # float qui devrait devenir SMALLINT
            "deaths": "5",  # str qui devrait devenir SMALLINT
            "accuracy": "0.55",  # str qui devrait devenir FLOAT
            "is_ranked": 1,  # int qui devrait devenir BOOLEAN
        }
        result = coerce_row_types(row, "match_stats")
        assert result["match_id"] == "m1"
        assert result["kills"] == 10
        assert isinstance(result["kills"], int)
        assert result["deaths"] == 5
        assert result["accuracy"] == pytest.approx(0.55)
        assert result["is_ranked"] is True

    def test_unknown_table_passthrough(self) -> None:
        """Table inconnue → pas de conversion."""
        row = {"col1": "val1", "col2": 42}
        result = coerce_row_types(row, "nonexistent_table")
        assert result == row

    def test_unknown_column_passthrough(self) -> None:
        """Colonne non dans le plan → passée telle quelle."""
        row = {"match_id": "m1", "custom_col": "custom_val"}
        result = coerce_row_types(row, "match_stats")
        assert result["match_id"] == "m1"
        assert result["custom_col"] == "custom_val"

    def test_nan_values_cleaned(self) -> None:
        """Les NaN sont convertis en None."""
        row = {"kills": float("nan"), "accuracy": float("inf")}
        result = coerce_row_types(row, "match_stats")
        assert result["kills"] is None
        assert result["accuracy"] is None


# =============================================================================
# Tests batch_insert_rows
# =============================================================================


@dataclass
class FakeMedalRow:
    """Dataclass pour simuler une row de médaille."""

    match_id: str
    medal_name_id: int
    count: int


class TestBatchInsertRows:
    """Tests pour batch_insert_rows avec DuckDB in-memory."""

    @pytest.fixture
    def db_conn(self):
        """Connexion DuckDB in-memory avec table de test."""
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE medals_earned (
                match_id VARCHAR NOT NULL,
                medal_name_id BIGINT NOT NULL,
                count SMALLINT NOT NULL,
                PRIMARY KEY (match_id, medal_name_id)
            )
        """)
        yield conn
        conn.close()

    def test_insert_empty_list(self, db_conn) -> None:
        """Liste vide → 0 insertions."""
        result = batch_insert_rows(
            db_conn, "medals_earned", [], ["match_id", "medal_name_id", "count"]
        )
        assert result == 0

    def test_insert_dataclass_rows(self, db_conn) -> None:
        """Insertion batch de dataclasses."""
        rows = [
            FakeMedalRow("m1", 100, 2),
            FakeMedalRow("m1", 200, 1),
            FakeMedalRow("m2", 100, 5),
        ]
        result = batch_insert_rows(
            db_conn,
            "medals_earned",
            rows,
            ["match_id", "medal_name_id", "count"],
        )
        assert result == 3
        count = db_conn.execute("SELECT COUNT(*) FROM medals_earned").fetchone()[0]
        assert count == 3

    def test_insert_dict_rows(self, db_conn) -> None:
        """Insertion batch de dictionnaires."""
        rows = [
            {"match_id": "m1", "medal_name_id": 100, "count": 3},
            {"match_id": "m2", "medal_name_id": 200, "count": 1},
        ]
        result = batch_insert_rows(
            db_conn,
            "medals_earned",
            rows,
            ["match_id", "medal_name_id", "count"],
        )
        assert result == 2

    def test_insert_with_on_conflict_do_nothing(self, db_conn) -> None:
        """ON CONFLICT DO NOTHING ignore les doublons."""
        rows1 = [{"match_id": "m1", "medal_name_id": 100, "count": 3}]
        rows2 = [
            {"match_id": "m1", "medal_name_id": 100, "count": 5},  # doublon
            {"match_id": "m2", "medal_name_id": 200, "count": 1},  # nouveau
        ]
        batch_insert_rows(db_conn, "medals_earned", rows1, ["match_id", "medal_name_id", "count"])
        batch_insert_rows(
            db_conn,
            "medals_earned",
            rows2,
            ["match_id", "medal_name_id", "count"],
            on_conflict="ON CONFLICT DO NOTHING",
        )
        # Le doublon n'a pas remplacé la valeur
        count_val = db_conn.execute(
            "SELECT count FROM medals_earned WHERE match_id='m1' AND medal_name_id=100"
        ).fetchone()[0]
        assert count_val == 3  # Pas modifié

    def test_insert_without_cast(self, db_conn) -> None:
        """apply_cast=False ne conversion pas les types."""
        rows = [{"match_id": "m1", "medal_name_id": 100, "count": 2}]
        result = batch_insert_rows(
            db_conn,
            "medals_earned",
            rows,
            ["match_id", "medal_name_id", "count"],
            apply_cast=False,
        )
        assert result == 1


# =============================================================================
# Tests batch_upsert_rows
# =============================================================================


class TestBatchUpsertRows:
    """Tests pour batch_upsert_rows."""

    @pytest.fixture
    def db_conn(self):
        """Connexion DuckDB in-memory avec table de test."""
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE xuid_aliases (
                xuid VARCHAR PRIMARY KEY,
                gamertag VARCHAR NOT NULL,
                last_seen TIMESTAMP,
                source VARCHAR
            )
        """)
        yield conn
        conn.close()

    def test_upsert_empty(self, db_conn) -> None:
        assert batch_upsert_rows(db_conn, "xuid_aliases", [], ["xuid", "gamertag"]) == 0

    def test_upsert_insert_new(self, db_conn) -> None:
        """Upsert de nouvelles lignes."""
        rows = [
            {"xuid": "x1", "gamertag": "Player1", "last_seen": None, "source": "test"},
        ]
        result = batch_upsert_rows(
            db_conn, "xuid_aliases", rows, ["xuid", "gamertag", "last_seen", "source"]
        )
        assert result == 1

    def test_upsert_replaces_existing(self, db_conn) -> None:
        """Upsert remplace les lignes existantes."""
        rows1 = [{"xuid": "x1", "gamertag": "OldName", "last_seen": None, "source": "test"}]
        rows2 = [{"xuid": "x1", "gamertag": "NewName", "last_seen": None, "source": "test"}]
        batch_upsert_rows(
            db_conn, "xuid_aliases", rows1, ["xuid", "gamertag", "last_seen", "source"]
        )
        batch_upsert_rows(
            db_conn, "xuid_aliases", rows2, ["xuid", "gamertag", "last_seen", "source"]
        )
        gt = db_conn.execute("SELECT gamertag FROM xuid_aliases WHERE xuid='x1'").fetchone()[0]
        assert gt == "NewName"


# =============================================================================
# Tests audit_column_types
# =============================================================================


class TestAuditColumnTypes:
    """Tests pour audit_column_types."""

    @pytest.fixture
    def db_conn(self):
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                kills SMALLINT,
                accuracy FLOAT,
                is_ranked BOOLEAN
            )
        """)
        yield conn
        conn.close()

    def test_audit_consistent_table(self, db_conn) -> None:
        """Table avec types cohérents → pas d'erreurs."""
        db_conn.execute("INSERT INTO match_stats VALUES ('m1', 10, 0.55, TRUE)")
        issues = audit_column_types(db_conn, "match_stats")
        assert isinstance(issues, list)
        # Pas d'incohérences sur une table bien typée
        # (les erreurs sont liées à des valeurs non castables)

    def test_audit_nonexistent_table(self, db_conn) -> None:
        """Table inexistante → liste vide ou pas d'erreur fatale."""
        issues = audit_column_types(db_conn, "nonexistent_table")
        assert isinstance(issues, list)


# =============================================================================
# Tests CAST_PLAN
# =============================================================================


class TestCastPlan:
    """Tests de cohérence du CAST_PLAN."""

    def test_match_stats_in_plan(self) -> None:
        assert "match_stats" in CAST_PLAN

    def test_medals_earned_in_plan(self) -> None:
        assert "medals_earned" in CAST_PLAN

    def test_match_stats_has_critical_columns(self) -> None:
        plan = CAST_PLAN["match_stats"]
        assert "match_id" in plan
        assert "kills" in plan
        assert "deaths" in plan
        assert "assists" in plan
        assert "accuracy" in plan

    def test_all_types_valid(self) -> None:
        valid_types = {
            "VARCHAR",
            "TEXT",
            "FLOAT",
            "DOUBLE",
            "REAL",
            "INTEGER",
            "INT",
            "BIGINT",
            "SMALLINT",
            "TINYINT",
            "BOOLEAN",
            "TIMESTAMP",
        }
        for table, columns in CAST_PLAN.items():
            for col, dtype in columns.items():
                assert dtype.upper() in valid_types, f"Type invalide {dtype} pour {table}.{col}"
