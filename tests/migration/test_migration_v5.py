"""Tests Sprint 7 — Migration v5 : idempotence, rollback, cas limites.

Complète tests/migration/test_migration_integrity.py avec des scénarios
avancés : double migration, données vides, edge cases.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from scripts.migration.create_shared_matches_db import (
    create_shared_matches_db,
)
from scripts.migration.migrate_player_to_shared import (
    migrate_player_to_shared,
    recalculate_player_counts,
)

# Réutiliser le helper _create_player_db du module existant
from tests.migration.test_migration_integrity import _create_player_db

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def shared_db(tmp_dir: Path) -> Path:
    db_path = tmp_dir / "shared_matches.duckdb"
    create_shared_matches_db(db_path, force=True)
    return db_path


# =============================================================================
# Tests d'idempotence
# =============================================================================


class TestMigrationIdempotency:
    """Vérifier que re-migrer un joueur ne duplique pas les données."""

    def test_double_migration_same_player(self, tmp_dir: Path, shared_db: Path) -> None:
        """Migrer 2x le même joueur ne crée pas de doublons."""
        player_db = _create_player_db(
            tmp_dir,
            "Idempotent",
            "xuid_idem",
            matches=[{"match_id": "m1"}, {"match_id": "m2"}],
            participants=[
                {"match_id": "m1", "xuid": "xuid_idem", "gamertag": "Idempotent"},
                {"match_id": "m2", "xuid": "xuid_idem", "gamertag": "Idempotent"},
            ],
            medals=[{"match_id": "m1", "medal_name_id": 100, "count": 2}],
            aliases=[{"xuid": "xuid_idem", "gamertag": "Idempotent"}],
        )

        # Première migration
        stats1 = migrate_player_to_shared(
            "Idempotent", "xuid_idem", player_db, shared_db, verbose=False
        )
        assert stats1["matches_new"] == 2

        # Deuxième migration — idempotente
        stats2 = migrate_player_to_shared(
            "Idempotent", "xuid_idem", player_db, shared_db, verbose=False
        )
        assert stats2["matches_new"] == 0
        assert stats2["matches_existing"] == 2

        # Vérifier pas de doublons
        conn = duckdb.connect(str(shared_db), read_only=True)
        try:
            reg = conn.execute("SELECT COUNT(*) FROM match_registry").fetchone()[0]
            assert reg == 2  # Pas 4

            parts = conn.execute("SELECT COUNT(*) FROM match_participants").fetchone()[0]
            assert parts == 2  # Pas 4

            medals = conn.execute("SELECT COUNT(*) FROM medals_earned").fetchone()[0]
            assert medals == 1  # Pas 2

            aliases = conn.execute("SELECT COUNT(*) FROM xuid_aliases").fetchone()[0]
            assert aliases == 1  # Pas 2
        finally:
            conn.close()

    def test_triple_migration_stability(self, tmp_dir: Path, shared_db: Path) -> None:
        """3 migrations successives ne changent pas le résultat."""
        player_db = _create_player_db(
            tmp_dir,
            "Triple",
            "xuid_tri",
            matches=[{"match_id": "m1"}],
            participants=[
                {"match_id": "m1", "xuid": "xuid_tri", "gamertag": "Triple"},
            ],
        )

        for _ in range(3):
            migrate_player_to_shared("Triple", "xuid_tri", player_db, shared_db, verbose=False)

        conn = duckdb.connect(str(shared_db), read_only=True)
        try:
            assert conn.execute("SELECT COUNT(*) FROM match_registry").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM match_participants").fetchone()[0] == 1
        finally:
            conn.close()


# =============================================================================
# Tests cas limites
# =============================================================================


class TestMigrationEdgeCases:
    """Cas limites de la migration."""

    def test_empty_player_db(self, tmp_dir: Path, shared_db: Path) -> None:
        """Joueur avec 0 match → migration réussie sans données."""
        player_db = _create_player_db(
            tmp_dir,
            "Empty",
            "xuid_empty",
            matches=[],
        )

        stats = migrate_player_to_shared("Empty", "xuid_empty", player_db, shared_db, verbose=False)
        assert stats["matches_new"] == 0
        assert stats["matches_existing"] == 0

    def test_player_with_only_medals_no_participants(self, tmp_dir: Path, shared_db: Path) -> None:
        """Joueur avec médailles mais pas de participants."""
        player_db = _create_player_db(
            tmp_dir,
            "MedalsOnly",
            "xuid_medals",
            matches=[{"match_id": "m1"}],
            medals=[{"match_id": "m1", "medal_name_id": 100, "count": 3}],
        )

        stats = migrate_player_to_shared(
            "MedalsOnly", "xuid_medals", player_db, shared_db, verbose=False
        )
        assert stats["matches_new"] == 1
        assert stats["medals_inserted"] >= 1

    def test_large_match_count(self, tmp_dir: Path, shared_db: Path) -> None:
        """Migration de 50 matchs s'exécute correctement."""
        matches = [{"match_id": f"m_{i}"} for i in range(50)]
        participants = [
            {"match_id": f"m_{i}", "xuid": "xuid_lg", "gamertag": "LargePlayer"} for i in range(50)
        ]

        player_db = _create_player_db(
            tmp_dir,
            "LargePlayer",
            "xuid_lg",
            matches=matches,
            participants=participants,
        )

        stats = migrate_player_to_shared(
            "LargePlayer", "xuid_lg", player_db, shared_db, verbose=False
        )
        assert stats["matches_new"] == 50

        conn = duckdb.connect(str(shared_db), read_only=True)
        try:
            count = conn.execute("SELECT COUNT(*) FROM match_registry").fetchone()[0]
            assert count == 50
        finally:
            conn.close()


# =============================================================================
# Tests recalculate_player_counts
# =============================================================================


class TestRecalculatePlayerCounts:
    """Tests pour recalculate_player_counts."""

    def test_recalculate_shared_match_counts(self, tmp_dir: Path, shared_db: Path) -> None:
        """player_count est correctement recalculé après migrations multiples."""
        p1_db = _create_player_db(
            tmp_dir,
            "P1",
            "xuid_p1",
            matches=[{"match_id": "shared_m"}, {"match_id": "exclusive_p1"}],
            participants=[
                {"match_id": "shared_m", "xuid": "xuid_p1", "gamertag": "P1"},
                {"match_id": "exclusive_p1", "xuid": "xuid_p1", "gamertag": "P1"},
            ],
        )
        p2_db = _create_player_db(
            tmp_dir,
            "P2",
            "xuid_p2",
            matches=[{"match_id": "shared_m"}, {"match_id": "exclusive_p2"}],
            participants=[
                {"match_id": "shared_m", "xuid": "xuid_p2", "gamertag": "P2"},
                {"match_id": "exclusive_p2", "xuid": "xuid_p2", "gamertag": "P2"},
            ],
        )

        migrate_player_to_shared("P1", "xuid_p1", p1_db, shared_db, verbose=False)
        migrate_player_to_shared("P2", "xuid_p2", p2_db, shared_db, verbose=False)

        profiles = {
            "P1": {"db_path": str(p1_db)},
            "P2": {"db_path": str(p2_db)},
        }
        recalculate_player_counts(shared_db, profiles=profiles)

        conn = duckdb.connect(str(shared_db), read_only=True)
        try:
            # Match partagé → player_count = 2
            pc = conn.execute(
                "SELECT player_count FROM match_registry WHERE match_id='shared_m'"
            ).fetchone()[0]
            assert pc == 2

            # Matchs exclusifs → player_count = 1
            pc1 = conn.execute(
                "SELECT player_count FROM match_registry WHERE match_id='exclusive_p1'"
            ).fetchone()[0]
            assert pc1 == 1

            pc2 = conn.execute(
                "SELECT player_count FROM match_registry WHERE match_id='exclusive_p2'"
            ).fetchone()[0]
            assert pc2 == 1
        finally:
            conn.close()


# =============================================================================
# Tests shared_matches.duckdb création
# =============================================================================


class TestCreateSharedMatchesDb:
    """Tests pour create_shared_matches_db."""

    def test_creates_db_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "new_shared.duckdb"
        create_shared_matches_db(db_path)
        assert db_path.exists()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        db_path = tmp_path / "sub" / "dir" / "shared.duckdb"
        create_shared_matches_db(db_path)
        assert db_path.exists()

    def test_force_recreate(self, tmp_path: Path) -> None:
        """force=True recrée la DB même si elle existe."""
        db_path = tmp_path / "shared.duckdb"
        create_shared_matches_db(db_path)
        # Ajouter des données
        conn = duckdb.connect(str(db_path))
        conn.execute("""
            INSERT INTO match_registry (match_id, start_time)
            VALUES ('m1', '2025-01-01')
        """)
        conn.close()

        # Force recreate
        create_shared_matches_db(db_path, force=True)

        # Vérifier que les données ont été effacées
        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            count = conn.execute("SELECT COUNT(*) FROM match_registry").fetchone()[0]
            assert count == 0
        finally:
            conn.close()

    def test_idempotent_creation(self, tmp_path: Path) -> None:
        """Créer 2x sans force ne crash pas."""
        db_path = tmp_path / "shared.duckdb"
        create_shared_matches_db(db_path)
        create_shared_matches_db(db_path)  # Pas d'erreur
        assert db_path.exists()

    def test_all_required_tables_exist(self, tmp_path: Path) -> None:
        """La DB créée contient toutes les tables attendues."""
        db_path = tmp_path / "shared.duckdb"
        create_shared_matches_db(db_path)

        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
                ).fetchall()
            }
            expected = {
                "match_registry",
                "match_participants",
                "highlight_events",
                "medals_earned",
                "xuid_aliases",
            }
            assert expected.issubset(tables), f"Tables manquantes : {expected - tables}"
        finally:
            conn.close()
