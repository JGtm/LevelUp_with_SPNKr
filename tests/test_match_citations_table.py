"""Tests pour les tables DuckDB des citations (citation_mappings et match_citations)."""

from pathlib import Path

import duckdb
import pytest

from scripts.create_match_citations_table import create_match_citations_table

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def metadata_conn(tmp_path: Path):
    """Connexion à une DB metadata temporaire avec citation_mappings."""
    db_path = tmp_path / "metadata.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE citation_mappings (
            citation_name_norm TEXT PRIMARY KEY,
            citation_name_display TEXT NOT NULL,
            mapping_type TEXT NOT NULL,
            medal_id BIGINT,
            medal_ids TEXT,
            stat_name TEXT,
            award_name TEXT,
            award_category TEXT,
            custom_function TEXT,
            confidence TEXT,
            notes TEXT,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        INSERT INTO citation_mappings
        (citation_name_norm, citation_name_display, mapping_type, medal_id,
         stat_name, award_name, custom_function, confidence, notes)
        VALUES
        ('pilote', 'Pilote', 'medal', 3169118333, NULL, NULL, NULL, 'high', 'test'),
        ('assistant', 'Assistant', 'stat', NULL, 'assists', NULL, NULL, 'high', 'test'),
        ('defenseur du drapeau', 'Défenseur du drapeau', 'award', NULL, NULL, 'Flag Defense', NULL, 'high', 'test'),
        ('bulldozer', 'Bulldozer', 'custom', NULL, NULL, NULL, 'compute_bulldozer', 'high', 'test')
    """)
    yield conn
    conn.close()


@pytest.fixture
def player_conn(tmp_path: Path):
    """Connexion à une DB joueur temporaire avec match_citations."""
    db_path = tmp_path / "stats.duckdb"
    conn = duckdb.connect(str(db_path))
    create_match_citations_table(conn)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Tests citation_mappings
# ---------------------------------------------------------------------------


class TestCitationMappingsTable:
    """Tests pour la table citation_mappings."""

    def test_table_exists(self, metadata_conn: duckdb.DuckDBPyConnection) -> None:
        """Vérifie que la table citation_mappings existe."""
        count = metadata_conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'citation_mappings'"
        ).fetchone()[0]
        assert count == 1

    def test_row_count(self, metadata_conn: duckdb.DuckDBPyConnection) -> None:
        """Vérifie le nombre de lignes insérées dans le fixture."""
        count = metadata_conn.execute("SELECT COUNT(*) FROM citation_mappings").fetchone()[0]
        assert count == 4

    def test_schema_columns(self, metadata_conn: duckdb.DuckDBPyConnection) -> None:
        """Vérifie les colonnes de la table."""
        cols = metadata_conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'citation_mappings' "
            "ORDER BY ordinal_position"
        ).fetchall()
        col_names = [c[0] for c in cols]
        expected = [
            "citation_name_norm",
            "citation_name_display",
            "mapping_type",
            "medal_id",
            "medal_ids",
            "stat_name",
            "award_name",
            "award_category",
            "custom_function",
            "confidence",
            "notes",
            "enabled",
            "created_at",
            "updated_at",
        ]
        assert col_names == expected

    def test_mapping_types(self, metadata_conn: duckdb.DuckDBPyConnection) -> None:
        """Vérifie les 4 types de mapping."""
        types = metadata_conn.execute(
            "SELECT DISTINCT mapping_type FROM citation_mappings ORDER BY mapping_type"
        ).fetchall()
        assert [t[0] for t in types] == ["award", "custom", "medal", "stat"]

    def test_medal_id_bigint(self, metadata_conn: duckdb.DuckDBPyConnection) -> None:
        """Vérifie que medal_id supporte des valeurs > 2^31 (BIGINT)."""
        val = metadata_conn.execute(
            "SELECT medal_id FROM citation_mappings WHERE citation_name_norm = 'pilote'"
        ).fetchone()[0]
        assert val == 3169118333


# ---------------------------------------------------------------------------
# Tests match_citations
# ---------------------------------------------------------------------------


class TestMatchCitationsTable:
    """Tests pour la table match_citations."""

    def test_table_exists(self, player_conn: duckdb.DuckDBPyConnection) -> None:
        """Vérifie que la table match_citations existe."""
        count = player_conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables " "WHERE table_name = 'match_citations'"
        ).fetchone()[0]
        assert count == 1

    def test_schema_columns(self, player_conn: duckdb.DuckDBPyConnection) -> None:
        """Vérifie les colonnes match_id, citation_name_norm, value."""
        cols = player_conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'match_citations' "
            "ORDER BY ordinal_position"
        ).fetchall()
        col_names = [c[0] for c in cols]
        assert col_names == ["match_id", "citation_name_norm", "value"]

    def test_primary_key(self, player_conn: duckdb.DuckDBPyConnection) -> None:
        """Vérifie la PK composite (match_id, citation_name_norm)."""
        # Insérer une ligne
        player_conn.execute("INSERT INTO match_citations VALUES ('m1', 'pilote', 2)")
        # Le doublon sur la PK doit lever une erreur
        with pytest.raises(duckdb.ConstraintException):
            player_conn.execute("INSERT INTO match_citations VALUES ('m1', 'pilote', 5)")

    def test_index_exists(self, player_conn: duckdb.DuckDBPyConnection) -> None:
        """Vérifie que l'index sur citation_name_norm existe."""
        indexes = player_conn.execute(
            "SELECT index_name FROM duckdb_indexes() " "WHERE table_name = 'match_citations'"
        ).fetchall()
        idx_names = [i[0] for i in indexes]
        assert "idx_match_citations_name" in idx_names

    def test_insert_and_query(self, player_conn: duckdb.DuckDBPyConnection) -> None:
        """Vérifie INSERT et agrégation basique."""
        player_conn.execute(
            "INSERT INTO match_citations VALUES "
            "('m1', 'pilote', 2), ('m1', 'assistant', 5), "
            "('m2', 'pilote', 1), ('m2', 'assistant', 3)"
        )
        totals = player_conn.execute(
            "SELECT citation_name_norm, SUM(value) as total "
            "FROM match_citations "
            "GROUP BY citation_name_norm "
            "ORDER BY citation_name_norm"
        ).fetchall()
        assert totals == [("assistant", 8), ("pilote", 3)]

    def test_create_idempotent(self, tmp_path: Path) -> None:
        """Vérifie que create_match_citations_table est idempotent."""
        db_path = tmp_path / "idempotent.duckdb"
        conn = duckdb.connect(str(db_path))
        assert create_match_citations_table(conn) is True  # 1ère fois
        assert create_match_citations_table(conn) is False  # 2ème fois
        conn.close()
