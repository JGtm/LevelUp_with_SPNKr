"""Tests du bridge Arrow/Polars zero-copy (Sprint 17).

Vérifie que result_to_polars et ensure_polars fonctionnent correctement
pour la conversion DuckDB → Polars sans copie mémoire.
"""

from __future__ import annotations

import polars as pl


class TestResultToPolars:
    """Tests pour result_to_polars (DuckDB → Polars via Arrow)."""

    def test_basic_query_returns_polars(self, tmp_path):
        """result_to_polars convertit un résultat DuckDB en pl.DataFrame."""
        import duckdb

        from src.data.repositories._arrow_bridge import result_to_polars

        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INT, name VARCHAR)")
        conn.execute("INSERT INTO t VALUES (1, 'alpha'), (2, 'beta')")
        result = conn.execute("SELECT * FROM t ORDER BY id")
        df = result_to_polars(result)
        conn.close()

        assert isinstance(df, pl.DataFrame)
        assert df.shape == (2, 2)
        assert df.columns == ["id", "name"]
        assert df["id"].to_list() == [1, 2]
        assert df["name"].to_list() == ["alpha", "beta"]

    def test_empty_result_returns_empty_dataframe(self, tmp_path):
        """result_to_polars retourne un DataFrame vide pour un résultat vide."""
        import duckdb

        from src.data.repositories._arrow_bridge import result_to_polars

        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INT, name VARCHAR)")
        result = conn.execute("SELECT * FROM t")
        df = result_to_polars(result)
        conn.close()

        assert isinstance(df, pl.DataFrame)
        assert df.is_empty()

    def test_various_dtypes(self, tmp_path):
        """result_to_polars gère les types DuckDB variés."""
        import duckdb

        from src.data.repositories._arrow_bridge import result_to_polars

        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("""
            CREATE TABLE multi (
                i INTEGER,
                f FLOAT,
                b BOOLEAN,
                t TIMESTAMP,
                v VARCHAR
            )
        """)
        conn.execute("""
            INSERT INTO multi VALUES
            (42, 3.14, TRUE, '2024-01-01 12:00:00', 'hello')
        """)
        result = conn.execute("SELECT * FROM multi")
        df = result_to_polars(result)
        conn.close()

        assert isinstance(df, pl.DataFrame)
        assert df.shape == (1, 5)
        assert df["i"][0] == 42
        assert df["b"][0] is True


class TestEnsurePolars:
    """Tests pour ensure_polars (conversion Pandas/Polars → Polars)."""

    def test_polars_passthrough(self):
        """ensure_polars retourne un pl.DataFrame inchangé."""
        from src.data.repositories._arrow_bridge import ensure_polars

        df = pl.DataFrame({"a": [1, 2, 3]})
        result = ensure_polars(df)
        assert result is df  # Même objet, aucune copie

    def test_pandas_conversion(self):
        """ensure_polars convertit un pd.DataFrame en pl.DataFrame."""
        import pandas as pd

        from src.data.repositories._arrow_bridge import ensure_polars

        pdf = pd.DataFrame({"x": [10, 20], "y": ["a", "b"]})
        result = ensure_polars(pdf)
        assert isinstance(result, pl.DataFrame)
        assert result["x"].to_list() == [10, 20]

    def test_invalid_input_returns_empty(self):
        """ensure_polars retourne un DataFrame vide pour un type inconnu."""
        from src.data.repositories._arrow_bridge import ensure_polars

        result = ensure_polars("not a dataframe")
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()

    def test_none_returns_empty(self):
        """ensure_polars retourne un DataFrame vide pour None."""
        from src.data.repositories._arrow_bridge import ensure_polars

        result = ensure_polars(None)
        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()


class TestQueryDfUsesArrowBridge:
    """Vérifie que DuckDBRepository.query_df utilise le bridge Arrow."""

    def test_query_df_returns_polars(self, tmp_path):
        """query_df retourne un DataFrame Polars via result_to_polars."""
        import duckdb

        db_path = tmp_path / "stats.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE TABLE match_stats (match_id VARCHAR, kills INT)")
        conn.execute("INSERT INTO match_stats VALUES ('m1', 10), ('m2', 20)")
        conn.close()

        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(str(db_path), "test_xuid")
        df = repo.query_df("SELECT * FROM match_stats ORDER BY match_id")
        repo.close()

        assert isinstance(df, pl.DataFrame)
        assert df.shape == (2, 2)
        assert df["match_id"].to_list() == ["m1", "m2"]
