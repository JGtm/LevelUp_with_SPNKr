"""Tests du schéma shared_matches.duckdb (Sprint 1 — v5.0).

Valide la création de la base, les contraintes, les types,
les index et le versioning du schéma.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

# Ajouter la racine du projet au path pour les imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.migration.create_shared_matches_db import (
    EXPECTED_TABLES,
    _parse_sql_statements,
    create_shared_matches_db,
    validate_shared_schema,
)

SCHEMA_SQL_PATH = PROJECT_ROOT / "scripts" / "migration" / "schema_v5.sql"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def shared_db(tmp_path: Path) -> Path:
    """Crée une base shared_matches temporaire et retourne son chemin."""
    db_path = tmp_path / "shared_matches.duckdb"
    create_shared_matches_db(db_path=db_path)
    return db_path


@pytest.fixture
def conn(shared_db: Path) -> duckdb.DuckDBPyConnection:
    """Connexion en lecture seule à la base temporaire."""
    connection = duckdb.connect(str(shared_db), read_only=True)
    yield connection
    connection.close()


@pytest.fixture
def rw_conn(shared_db: Path) -> duckdb.DuckDBPyConnection:
    """Connexion en lecture/écriture à la base temporaire."""
    connection = duckdb.connect(str(shared_db))
    yield connection
    connection.close()


# ─────────────────────────────────────────────────────────────────────────────
# Tests de parsing SQL
# ─────────────────────────────────────────────────────────────────────────────


class TestSqlParsing:
    """Tests du parsing du fichier DDL."""

    def test_schema_file_exists(self) -> None:
        """Le fichier schema_v5.sql doit exister."""
        assert SCHEMA_SQL_PATH.exists(), f"Fichier DDL introuvable : {SCHEMA_SQL_PATH}"

    def test_parse_returns_statements(self) -> None:
        """Le parsing retourne des instructions SQL non vides."""
        statements = _parse_sql_statements(SCHEMA_SQL_PATH)
        assert len(statements) > 0, "Aucune instruction SQL parsée"

    def test_parse_no_comment_only_statements(self) -> None:
        """Les instructions parsées ne sont pas des commentaires."""
        statements = _parse_sql_statements(SCHEMA_SQL_PATH)
        for stmt in statements:
            assert not stmt.strip().startswith(
                "--"
            ), f"Instruction commentaire détectée : {stmt[:60]}"

    def test_all_statements_end_with_semicolon(self) -> None:
        """Chaque instruction se termine par un ';'."""
        statements = _parse_sql_statements(SCHEMA_SQL_PATH)
        for stmt in statements:
            assert stmt.strip().endswith(";"), f"Instruction sans ';' : {stmt[:60]}"


# ─────────────────────────────────────────────────────────────────────────────
# Tests de création de la base
# ─────────────────────────────────────────────────────────────────────────────


class TestDatabaseCreation:
    """Tests de la création de shared_matches.duckdb."""

    def test_db_created(self, shared_db: Path) -> None:
        """La base doit être créée sur le disque."""
        assert shared_db.exists()
        assert shared_db.stat().st_size > 0

    def test_all_expected_tables_exist(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Toutes les tables attendues doivent être présentes."""
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables " "WHERE table_schema = 'main'"
        ).fetchall()
        existing = {r[0] for r in rows}
        missing = EXPECTED_TABLES - existing
        assert not missing, f"Tables manquantes : {missing}"

    def test_idempotent_creation(self, shared_db: Path) -> None:
        """Recréer sur une base existante ne fait rien (sans --force)."""
        stats = create_shared_matches_db(db_path=shared_db)
        # Ne devrait pas planter, la base est déjà complète
        assert isinstance(stats, dict)

    def test_force_recreate(self, tmp_path: Path) -> None:
        """--force recrée correctement la base."""
        db_path = tmp_path / "test_force.duckdb"
        create_shared_matches_db(db_path=db_path)
        assert db_path.exists()

        stats = create_shared_matches_db(db_path=db_path, force=True)
        assert stats["created"] is True

    def test_dry_run_no_file_created(self, tmp_path: Path) -> None:
        """--dry-run ne crée pas de fichier."""
        db_path = tmp_path / "nofile.duckdb"
        stats = create_shared_matches_db(db_path=db_path, dry_run=True)
        assert not db_path.exists()
        assert stats["dry_run"] is True

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """Les répertoires parents sont créés automatiquement."""
        db_path = tmp_path / "sub" / "dir" / "shared.duckdb"
        create_shared_matches_db(db_path=db_path)
        assert db_path.exists()


# ─────────────────────────────────────────────────────────────────────────────
# Tests du schéma match_registry
# ─────────────────────────────────────────────────────────────────────────────


class TestMatchRegistry:
    """Tests de la table match_registry."""

    EXPECTED_COLUMNS = {
        "match_id",
        "start_time",
        "end_time",
        "playlist_id",
        "playlist_name",
        "map_id",
        "map_name",
        "pair_id",
        "pair_name",
        "game_variant_id",
        "game_variant_name",
        "mode_category",
        "is_ranked",
        "is_firefight",
        "duration_seconds",
        "team_0_score",
        "team_1_score",
        "backfill_completed",
        "participants_loaded",
        "events_loaded",
        "medals_loaded",
        "first_sync_by",
        "first_sync_at",
        "last_updated_at",
        "player_count",
        "created_at",
        "updated_at",
    }

    def test_all_columns_present(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Toutes les colonnes attendues de match_registry sont présentes."""
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = 'match_registry'"
        ).fetchall()
        existing = {r[0] for r in rows}
        missing = self.EXPECTED_COLUMNS - existing
        assert not missing, f"Colonnes manquantes dans match_registry : {missing}"

    def test_primary_key_match_id(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """match_id est la clé primaire (pas de doublons)."""
        rw_conn.execute(
            "INSERT INTO match_registry (match_id, start_time) "
            "VALUES ('test-001', '2025-01-01 12:00:00')"
        )
        with pytest.raises(duckdb.ConstraintException):
            rw_conn.execute(
                "INSERT INTO match_registry (match_id, start_time) "
                "VALUES ('test-001', '2025-01-02 12:00:00')"
            )

    def test_start_time_not_null(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """start_time ne peut pas être NULL."""
        with pytest.raises(duckdb.ConstraintException):
            rw_conn.execute(
                "INSERT INTO match_registry (match_id, start_time) " "VALUES ('test-null', NULL)"
            )

    def test_defaults(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """Les valeurs par défaut sont correctement appliquées."""
        rw_conn.execute(
            "INSERT INTO match_registry (match_id, start_time) "
            "VALUES ('test-defaults', '2025-01-01 12:00:00')"
        )
        row = rw_conn.execute(
            "SELECT is_ranked, is_firefight, backfill_completed, "
            "player_count, participants_loaded, events_loaded, medals_loaded "
            "FROM match_registry WHERE match_id = 'test-defaults'"
        ).fetchone()
        assert row is not None
        is_ranked, is_firefight, backfill, pcount, p_loaded, e_loaded, m_loaded = row
        assert is_ranked is False
        assert is_firefight is False
        assert backfill == 0
        assert pcount == 0
        assert p_loaded is False
        assert e_loaded is False
        assert m_loaded is False

    def test_insert_full_row(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """Insertion d'une ligne complète avec toutes les colonnes."""
        rw_conn.execute("""
            INSERT INTO match_registry (
                match_id, start_time, end_time,
                playlist_id, playlist_name, map_id, map_name,
                pair_id, pair_name,
                game_variant_id, game_variant_name,
                mode_category, is_ranked, is_firefight,
                duration_seconds, team_0_score, team_1_score,
                first_sync_by, first_sync_at, player_count
            ) VALUES (
                'match-full', '2025-06-15 20:00:00', '2025-06-15 20:12:00',
                'pl-001', 'BTB', 'map-001', 'Fragmentation',
                'pair-001', 'BTB Slayer',
                'gv-001', 'Slayer',
                'pvp', TRUE, FALSE,
                720, 50, 45,
                'Chocoboflor', '2025-06-16 10:00:00', 2
            )
        """)
        row = rw_conn.execute(
            "SELECT playlist_name, map_name, is_ranked, player_count "
            "FROM match_registry WHERE match_id = 'match-full'"
        ).fetchone()
        assert row == ("BTB", "Fragmentation", True, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Tests du schéma match_participants
# ─────────────────────────────────────────────────────────────────────────────


class TestMatchParticipants:
    """Tests de la table match_participants."""

    EXPECTED_COLUMNS = {
        "match_id",
        "xuid",
        "gamertag",
        "team_id",
        "outcome",
        "rank",
        "score",
        "kills",
        "deaths",
        "assists",
        "shots_fired",
        "shots_hit",
        "damage_dealt",
        "damage_taken",
        "created_at",
    }

    def test_all_columns_present(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Toutes les colonnes attendues sont présentes."""
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = 'match_participants'"
        ).fetchall()
        existing = {r[0] for r in rows}
        missing = self.EXPECTED_COLUMNS - existing
        assert not missing, f"Colonnes manquantes dans match_participants : {missing}"

    def test_composite_pk(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """Clé primaire composite (match_id, xuid)."""
        # Prérequis : un match dans le registre
        rw_conn.execute(
            "INSERT INTO match_registry (match_id, start_time) "
            "VALUES ('match-pk', '2025-01-01 12:00:00')"
        )
        rw_conn.execute(
            "INSERT INTO match_participants (match_id, xuid, kills, deaths, assists) "
            "VALUES ('match-pk', 'xuid-001', 10, 5, 3)"
        )
        # Même joueur dans le même match → doublon
        with pytest.raises(duckdb.ConstraintException):
            rw_conn.execute(
                "INSERT INTO match_participants (match_id, xuid, kills, deaths, assists) "
                "VALUES ('match-pk', 'xuid-001', 8, 6, 2)"
            )
        # Même joueur dans un autre match → OK
        rw_conn.execute(
            "INSERT INTO match_registry (match_id, start_time) "
            "VALUES ('match-pk2', '2025-01-02 12:00:00')"
        )
        rw_conn.execute(
            "INSERT INTO match_participants (match_id, xuid, kills, deaths, assists) "
            "VALUES ('match-pk2', 'xuid-001', 12, 3, 7)"
        )

    def test_foreign_key_to_registry(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """La clé étrangère vers match_registry est respectée."""
        with pytest.raises(duckdb.ConstraintException):
            rw_conn.execute(
                "INSERT INTO match_participants (match_id, xuid) "
                "VALUES ('match-inexistant', 'xuid-fk')"
            )

    def test_multi_players_per_match(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """Plusieurs joueurs peuvent participer au même match."""
        rw_conn.execute(
            "INSERT INTO match_registry (match_id, start_time) "
            "VALUES ('match-multi', '2025-01-01 12:00:00')"
        )
        for i in range(8):
            rw_conn.execute(
                "INSERT INTO match_participants (match_id, xuid, gamertag, "
                "team_id, outcome, kills, deaths, assists) "
                f"VALUES ('match-multi', 'xuid-{i:03d}', 'Player{i}', "
                f"{i % 2}, {2 if i % 2 == 0 else 3}, {10+i}, {5+i}, {3+i})"
            )
        count = rw_conn.execute(
            "SELECT COUNT(*) FROM match_participants WHERE match_id = 'match-multi'"
        ).fetchone()
        assert count[0] == 8


# ─────────────────────────────────────────────────────────────────────────────
# Tests du schéma highlight_events
# ─────────────────────────────────────────────────────────────────────────────


class TestHighlightEvents:
    """Tests de la table highlight_events."""

    EXPECTED_COLUMNS = {
        "id",
        "match_id",
        "event_type",
        "time_ms",
        "killer_xuid",
        "killer_gamertag",
        "victim_xuid",
        "victim_gamertag",
        "type_hint",
        "raw_json",
        "created_at",
    }

    def test_all_columns_present(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Toutes les colonnes attendues sont présentes."""
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = 'highlight_events'"
        ).fetchall()
        existing = {r[0] for r in rows}
        missing = self.EXPECTED_COLUMNS - existing
        assert not missing, f"Colonnes manquantes dans highlight_events : {missing}"

    def test_auto_increment_id(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """L'id est auto-incrémenté via séquence."""
        rw_conn.execute(
            "INSERT INTO match_registry (match_id, start_time) "
            "VALUES ('match-evt', '2025-01-01 12:00:00')"
        )
        rw_conn.execute(
            "INSERT INTO highlight_events (match_id, event_type, killer_xuid, victim_xuid) "
            "VALUES ('match-evt', 'kill', 'xuid-k1', 'xuid-v1')"
        )
        rw_conn.execute(
            "INSERT INTO highlight_events (match_id, event_type, killer_xuid, victim_xuid) "
            "VALUES ('match-evt', 'kill', 'xuid-k2', 'xuid-v2')"
        )
        rows = rw_conn.execute("SELECT id FROM highlight_events ORDER BY id").fetchall()
        assert len(rows) == 2
        assert rows[0][0] < rows[1][0]  # IDs croissants

    def test_foreign_key_to_registry(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """La clé étrangère vers match_registry est respectée."""
        with pytest.raises(duckdb.ConstraintException):
            rw_conn.execute(
                "INSERT INTO highlight_events (match_id, event_type) "
                "VALUES ('match-ghost', 'kill')"
            )

    def test_killer_victim_separation(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """Les colonnes killer/victim sont bien distinctes."""
        rw_conn.execute(
            "INSERT INTO match_registry (match_id, start_time) "
            "VALUES ('match-kv', '2025-01-01 12:00:00')"
        )
        rw_conn.execute(
            "INSERT INTO highlight_events "
            "(match_id, event_type, killer_xuid, killer_gamertag, "
            "victim_xuid, victim_gamertag, time_ms) "
            "VALUES ('match-kv', 'kill', 'xuid-k', 'Killer', "
            "'xuid-v', 'Victim', 12345)"
        )
        row = rw_conn.execute(
            "SELECT killer_gamertag, victim_gamertag "
            "FROM highlight_events WHERE match_id = 'match-kv'"
        ).fetchone()
        assert row == ("Killer", "Victim")


# ─────────────────────────────────────────────────────────────────────────────
# Tests du schéma medals_earned
# ─────────────────────────────────────────────────────────────────────────────


class TestMedalsEarned:
    """Tests de la table medals_earned."""

    EXPECTED_COLUMNS = {
        "match_id",
        "xuid",
        "medal_name_id",
        "count",
        "created_at",
    }

    def test_all_columns_present(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Toutes les colonnes attendues sont présentes."""
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = 'medals_earned'"
        ).fetchall()
        existing = {r[0] for r in rows}
        missing = self.EXPECTED_COLUMNS - existing
        assert not missing, f"Colonnes manquantes dans medals_earned : {missing}"

    def test_composite_pk_with_xuid(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """Clé primaire composite (match_id, xuid, medal_name_id)."""
        rw_conn.execute(
            "INSERT INTO match_registry (match_id, start_time) "
            "VALUES ('match-med', '2025-01-01 12:00:00')"
        )
        # Même médaille pour 2 joueurs différents → OK
        rw_conn.execute(
            "INSERT INTO medals_earned (match_id, xuid, medal_name_id, count) "
            "VALUES ('match-med', 'xuid-A', 1234567890, 3)"
        )
        rw_conn.execute(
            "INSERT INTO medals_earned (match_id, xuid, medal_name_id, count) "
            "VALUES ('match-med', 'xuid-B', 1234567890, 1)"
        )
        # Doublons → erreur
        with pytest.raises(duckdb.ConstraintException):
            rw_conn.execute(
                "INSERT INTO medals_earned (match_id, xuid, medal_name_id, count) "
                "VALUES ('match-med', 'xuid-A', 1234567890, 5)"
            )

    def test_medal_name_id_bigint(self, conn: duckdb.DuckDBPyConnection) -> None:
        """medal_name_id est BIGINT (pas INT32)."""
        rows = conn.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = 'medals_earned' "
            "AND column_name = 'medal_name_id'"
        ).fetchone()
        assert rows is not None
        assert rows[0].upper() == "BIGINT"

    def test_foreign_key_to_registry(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """La clé étrangère vers match_registry est respectée."""
        with pytest.raises(duckdb.ConstraintException):
            rw_conn.execute(
                "INSERT INTO medals_earned (match_id, xuid, medal_name_id, count) "
                "VALUES ('match-fantome', 'xuid-X', 999, 1)"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tests du schéma xuid_aliases
# ─────────────────────────────────────────────────────────────────────────────


class TestXuidAliases:
    """Tests de la table xuid_aliases."""

    EXPECTED_COLUMNS = {
        "xuid",
        "gamertag",
        "last_seen",
        "source",
        "updated_at",
    }

    def test_all_columns_present(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Toutes les colonnes attendues sont présentes."""
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = 'xuid_aliases'"
        ).fetchall()
        existing = {r[0] for r in rows}
        missing = self.EXPECTED_COLUMNS - existing
        assert not missing, f"Colonnes manquantes dans xuid_aliases : {missing}"

    def test_pk_xuid(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """xuid est la clé primaire."""
        rw_conn.execute(
            "INSERT INTO xuid_aliases (xuid, gamertag, source) "
            "VALUES ('xuid-001', 'Chocoboflor', 'api')"
        )
        with pytest.raises(duckdb.ConstraintException):
            rw_conn.execute(
                "INSERT INTO xuid_aliases (xuid, gamertag, source) "
                "VALUES ('xuid-001', 'AutreNom', 'manual')"
            )

    def test_gamertag_not_null(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """gamertag ne peut pas être NULL."""
        with pytest.raises(duckdb.ConstraintException):
            rw_conn.execute("INSERT INTO xuid_aliases (xuid, gamertag) " "VALUES ('xuid-nn', NULL)")

    def test_source_values(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """Les sources acceptées sont correctement stockées."""
        for src in ("api", "film", "manual", "migration"):
            rw_conn.execute(
                "INSERT INTO xuid_aliases (xuid, gamertag, source) "
                f"VALUES ('xuid-src-{src}', 'Player_{src}', '{src}')"
            )
        count = rw_conn.execute(
            "SELECT COUNT(*) FROM xuid_aliases WHERE source IS NOT NULL"
        ).fetchone()
        assert count[0] == 4


# ─────────────────────────────────────────────────────────────────────────────
# Tests du schema_version
# ─────────────────────────────────────────────────────────────────────────────


class TestSchemaVersion:
    """Tests de la table schema_version."""

    def test_version_1_exists(self, conn: duckdb.DuckDBPyConnection) -> None:
        """La version 1 est insérée à la création."""
        row = conn.execute(
            "SELECT version, description FROM schema_version WHERE version = 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 1
        assert "v5.0" in row[1]

    def test_applied_at_filled(self, conn: duckdb.DuckDBPyConnection) -> None:
        """applied_at est renseigné automatiquement."""
        row = conn.execute("SELECT applied_at FROM schema_version WHERE version = 1").fetchone()
        assert row is not None
        assert row[0] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Tests des index
# ─────────────────────────────────────────────────────────────────────────────


class TestIndexes:
    """Tests des index créés sur les tables."""

    def test_indexes_exist(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Des index sont créés."""
        rows = conn.execute("SELECT * FROM duckdb_indexes()").fetchall()
        assert len(rows) >= 10, f"Seulement {len(rows)} index trouvés, attendu >= 10"

    def test_registry_indexes(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Les index de match_registry existent."""
        rows = conn.execute(
            "SELECT index_name FROM duckdb_indexes() " "WHERE table_name = 'match_registry'"
        ).fetchall()
        index_names = {r[0] for r in rows}
        expected = {
            "idx_registry_time",
            "idx_registry_playlist",
            "idx_registry_map",
            "idx_registry_player_count",
            "idx_registry_mode_category",
        }
        missing = expected - index_names
        assert not missing, f"Index manquants sur match_registry : {missing}"

    def test_participants_indexes(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Les index de match_participants existent."""
        rows = conn.execute(
            "SELECT index_name FROM duckdb_indexes() " "WHERE table_name = 'match_participants'"
        ).fetchall()
        index_names = {r[0] for r in rows}
        expected = {
            "idx_participants_xuid",
            "idx_participants_match",
            "idx_participants_team",
        }
        missing = expected - index_names
        assert not missing, f"Index manquants sur match_participants : {missing}"

    def test_events_indexes(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Les index de highlight_events existent."""
        rows = conn.execute(
            "SELECT index_name FROM duckdb_indexes() " "WHERE table_name = 'highlight_events'"
        ).fetchall()
        index_names = {r[0] for r in rows}
        expected = {"idx_events_match", "idx_events_killer", "idx_events_victim"}
        missing = expected - index_names
        assert not missing, f"Index manquants sur highlight_events : {missing}"

    def test_medals_indexes(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Les index de medals_earned existent."""
        rows = conn.execute(
            "SELECT index_name FROM duckdb_indexes() " "WHERE table_name = 'medals_earned'"
        ).fetchall()
        index_names = {r[0] for r in rows}
        expected = {"idx_medals_match", "idx_medals_xuid", "idx_medals_composite"}
        missing = expected - index_names
        assert not missing, f"Index manquants sur medals_earned : {missing}"


# ─────────────────────────────────────────────────────────────────────────────
# Tests de validation
# ─────────────────────────────────────────────────────────────────────────────


class TestValidation:
    """Tests de la fonction validate_shared_schema."""

    def test_valid_schema(self, shared_db: Path) -> None:
        """La validation passe sur une base correcte."""
        result = validate_shared_schema(db_path=shared_db)
        assert result["valid"] is True
        assert len(result.get("errors", [])) == 0

    def test_schema_version_detected(self, shared_db: Path) -> None:
        """Le numéro de version est détecté."""
        result = validate_shared_schema(db_path=shared_db)
        assert result["schema_version"] == 1

    def test_validation_missing_file(self, tmp_path: Path) -> None:
        """La validation échoue si la base n'existe pas."""
        with pytest.raises(FileNotFoundError):
            validate_shared_schema(db_path=tmp_path / "missing.duckdb")

    def test_validation_incomplete_db(self, tmp_path: Path) -> None:
        """La validation détecte une base incomplète."""
        db_path = tmp_path / "incomplete.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute("CREATE TABLE match_registry (match_id VARCHAR PRIMARY KEY)")
        conn.close()

        result = validate_shared_schema(db_path=db_path)
        assert result["valid"] is False
        assert len(result.get("errors", [])) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Tests d'intégrité croisée (requêtes typiques prévues)
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossTableQueries:
    """Tests de requêtes croisées entre tables (cas d'usage réels)."""

    def test_join_registry_participants(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """Jointure match_registry ↔ match_participants."""
        rw_conn.execute(
            "INSERT INTO match_registry (match_id, start_time, playlist_name) "
            "VALUES ('match-join', '2025-06-15 20:00:00', 'BTB')"
        )
        rw_conn.execute(
            "INSERT INTO match_participants (match_id, xuid, gamertag, kills, deaths, assists) "
            "VALUES ('match-join', 'xuid-j1', 'Player1', 15, 8, 5)"
        )
        rw_conn.execute(
            "INSERT INTO match_participants (match_id, xuid, gamertag, kills, deaths, assists) "
            "VALUES ('match-join', 'xuid-j2', 'Player2', 10, 10, 7)"
        )
        result = rw_conn.execute("""
            SELECT r.playlist_name, p.gamertag, p.kills
            FROM match_registry r
            JOIN match_participants p ON r.match_id = p.match_id
            WHERE r.match_id = 'match-join'
            ORDER BY p.kills DESC
        """).fetchall()
        assert len(result) == 2
        assert result[0] == ("BTB", "Player1", 15)
        assert result[1] == ("BTB", "Player2", 10)

    def test_player_match_count(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """Comptage des matchs par joueur (cas d'usage principal)."""
        for i in range(5):
            rw_conn.execute(
                "INSERT INTO match_registry (match_id, start_time) "
                f"VALUES ('match-cnt-{i}', '2025-01-0{i+1} 12:00:00')"
            )
            rw_conn.execute(
                "INSERT INTO match_participants (match_id, xuid, gamertag) "
                f"VALUES ('match-cnt-{i}', 'xuid-main', 'MainPlayer')"
            )
            # Un 2e joueur participe à 3 matchs sur 5
            if i < 3:
                rw_conn.execute(
                    "INSERT INTO match_participants (match_id, xuid, gamertag) "
                    f"VALUES ('match-cnt-{i}', 'xuid-other', 'OtherPlayer')"
                )

        result = rw_conn.execute("""
            SELECT xuid, COUNT(*) as match_count
            FROM match_participants
            GROUP BY xuid
            ORDER BY match_count DESC
        """).fetchall()
        assert result[0] == ("xuid-main", 5)
        assert result[1] == ("xuid-other", 3)

    def test_shared_match_detection(self, rw_conn: duckdb.DuckDBPyConnection) -> None:
        """Détection de matchs partagés entre 2 joueurs."""
        rw_conn.execute(
            "INSERT INTO match_registry (match_id, start_time) "
            "VALUES ('match-shared', '2025-01-01 12:00:00')"
        )
        rw_conn.execute(
            "INSERT INTO match_participants (match_id, xuid, gamertag) "
            "VALUES ('match-shared', 'xuid-a', 'PlayerA')"
        )
        rw_conn.execute(
            "INSERT INTO match_participants (match_id, xuid, gamertag) "
            "VALUES ('match-shared', 'xuid-b', 'PlayerB')"
        )
        result = rw_conn.execute("""
            SELECT p1.gamertag, p2.gamertag, p1.match_id
            FROM match_participants p1
            JOIN match_participants p2
              ON p1.match_id = p2.match_id AND p1.xuid < p2.xuid
            WHERE p1.xuid = 'xuid-a' AND p2.xuid = 'xuid-b'
        """).fetchall()
        assert len(result) == 1
        assert result[0][2] == "match-shared"
