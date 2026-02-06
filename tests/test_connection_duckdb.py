"""Tests pour src.db.connection - DuckDB uniquement, SQLite refusé."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.db.connection import SQLiteForbiddenError, get_connection


def test_sqlite_forbidden_raises():
    """Vérifie que les chemins .db lèvent SQLiteForbiddenError."""
    with pytest.raises(SQLiteForbiddenError) as exc_info, get_connection("/path/to/halo.db"):
        pass
    assert ".db" in str(exc_info.value)
    assert "SQLite" in str(exc_info.value)


def test_get_connection_duckdb_works():
    """Vérifie que get_connection accepte un fichier .duckdb."""
    import duckdb

    path = str(Path(tempfile.gettempdir()) / "test_connection.duckdb")
    try:
        # Créer un fichier DuckDB valide (connexion + close)
        duckdb.connect(path).close()
        with get_connection(path) as con:
            result = con.execute("SELECT 1").fetchone()
            assert result[0] == 1
    finally:
        Path(path).unlink(missing_ok=True)


def test_sqlite_forbidden_error_message():
    """Vérifie le message d'erreur SQLiteForbiddenError."""
    err = SQLiteForbiddenError("data/halo.db")
    assert "data/halo.db" in str(err)
    assert "migrate" in str(err).lower() or "sqlite" in str(err).lower()
