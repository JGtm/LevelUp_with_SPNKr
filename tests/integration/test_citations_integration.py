"""Tests d'intégration pour le pipeline citations.

Workflow complet : création tables → backfill → agrégation → cohérence.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from src.analysis.citations.engine import CitationEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_full_player_db(db_path: Path, meta_path: Path, *, n_matches: int = 20) -> None:
    """Crée une DB joueur et metadata complètes pour les tests d'intégration."""
    # 1) Metadata
    meta_conn = duckdb.connect(str(meta_path))
    meta_conn.execute("""
        CREATE TABLE IF NOT EXISTS citation_mappings (
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
    meta_conn.executemany(
        "INSERT OR REPLACE INTO citation_mappings "
        "(citation_name_norm, citation_name_display, mapping_type, "
        "medal_id, stat_name, award_name, custom_function, confidence, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("pilote", "Pilote", "medal", 3169118333, None, None, None, "high", "test"),
            ("ecrasement", "Écrasement", "medal", 221693153, None, None, None, "high", "test"),
            ("assistant", "Assistant", "stat", None, "assists", None, None, "high", "test"),
            (
                "defenseur du drapeau",
                "Défenseur du drapeau",
                "award",
                None,
                None,
                "Flag Defense",
                None,
                "high",
                "test",
            ),
            (
                "a la charge",
                "À la charge",
                "award",
                None,
                None,
                "Zone Capture",
                None,
                "high",
                "test",
            ),
        ],
    )
    meta_conn.close()

    # 2) Player DB
    conn = duckdb.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS match_citations (
            match_id TEXT NOT NULL,
            citation_name_norm TEXT NOT NULL,
            value INTEGER NOT NULL,
            PRIMARY KEY (match_id, citation_name_norm)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mc_name ON match_citations(citation_name_norm)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS match_stats (
            match_id TEXT PRIMARY KEY,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            headshot_kills INTEGER DEFAULT 0,
            outcome INTEGER DEFAULT 0,
            playlist_name TEXT,
            game_variant_name TEXT,
            start_time TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS medals_earned (
            match_id TEXT NOT NULL,
            medal_name_id BIGINT NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY (match_id, medal_name_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS personal_score_awards (
            match_id TEXT NOT NULL,
            award_name TEXT NOT NULL,
            award_category TEXT,
            award_count INTEGER DEFAULT 0,
            award_score INTEGER DEFAULT 0
        )
    """)

    # Générer n matchs
    from datetime import datetime, timedelta

    base_date = datetime(2026, 1, 1, 12, 0, 0)
    for i in range(1, n_matches + 1):
        mid = f"match-{i:04d}"
        dt = base_date + timedelta(days=i - 1)
        conn.execute(
            "INSERT INTO match_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [mid, 10 + i, 5, i * 2, i, 2, "Quick Play", "Slayer", dt.strftime("%Y-%m-%d %H:%M:%S")],
        )
        # Médailles : pilote tous les 3 matchs, écrasement tous les 5
        if i % 3 == 0:
            conn.execute("INSERT INTO medals_earned VALUES (?, 3169118333, ?)", [mid, 1 + i // 3])
        if i % 5 == 0:
            conn.execute("INSERT INTO medals_earned VALUES (?, 221693153, 1)", [mid])
        # Awards : Flag Defense tous les 4 matchs
        if i % 4 == 0:
            conn.execute(
                "INSERT INTO personal_score_awards VALUES (?, 'Flag Defense', 'objective', ?, 50)",
                [mid, 2],
            )

    conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def integ_env(tmp_path: Path) -> tuple[Path, Path]:
    """Crée un environnement complet pour les tests d'intégration."""
    warehouse = tmp_path / "data" / "warehouse"
    warehouse.mkdir(parents=True)
    player_dir = tmp_path / "data" / "players" / "TestPlayer"
    player_dir.mkdir(parents=True)

    db_path = player_dir / "stats.duckdb"
    meta_path = warehouse / "metadata.duckdb"

    _setup_full_player_db(db_path, meta_path, n_matches=50)
    return db_path, meta_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCitationsWorkflow:
    """Test du workflow complet : backfill → agrégation → cohérence."""

    def test_backfill_then_aggregate(self, integ_env: tuple[Path, Path]) -> None:
        """Backfill des citations puis agrégation correcte."""
        db_path, _meta = integ_env

        conn = duckdb.connect(str(db_path))
        engine = CitationEngine(str(db_path), "12345", conn=conn)

        # Vérifier mappings chargés
        mappings = engine.load_mappings()
        assert len(mappings) == 5

        # Backfill via compute_and_store
        n_matches = conn.execute("SELECT COUNT(*) FROM match_stats").fetchone()[0]
        assert n_matches == 50

        match_ids = [
            r[0]
            for r in conn.execute("SELECT match_id FROM match_stats ORDER BY start_time").fetchall()
        ]

        processed = 0
        for mid in match_ids:
            n = engine.compute_and_store_for_match(mid, conn=conn)
            if n > 0:
                processed += 1

        assert processed > 0

        # Vérifier l'agrégation
        totals = engine.aggregate_for_display()
        assert "assistant" in totals
        assert totals["assistant"] > 0

        # Vérifier pilote (tous les 3 matchs)
        assert "pilote" in totals
        assert totals["pilote"] > 0

        conn.close()

    def test_filtered_aggregation(self, integ_env: tuple[Path, Path]) -> None:
        """L'agrégation filtrée retourne un sous-ensemble."""
        db_path, _meta = integ_env

        conn = duckdb.connect(str(db_path))
        engine = CitationEngine(str(db_path), "12345", conn=conn)

        # Backfill tout
        match_ids = [
            r[0]
            for r in conn.execute("SELECT match_id FROM match_stats ORDER BY start_time").fetchall()
        ]
        for mid in match_ids:
            engine.compute_and_store_for_match(mid, conn=conn)

        # Agrégation totale
        totals_full = engine.aggregate_for_display()

        # Agrégation filtrée (10 premiers matchs)
        subset = match_ids[:10]
        totals_filtered = engine.aggregate_for_display(match_ids=subset)

        # Le filtré doit être <= au total pour chaque citation
        for name, val in totals_filtered.items():
            assert val <= totals_full.get(
                name, 0
            ), f"{name}: filtré ({val}) > total ({totals_full.get(name, 0)})"

        conn.close()

    def test_incremental_backfill(self, integ_env: tuple[Path, Path]) -> None:
        """Backfill incrémental ne retraite pas les matchs existants."""
        db_path, _meta = integ_env

        conn = duckdb.connect(str(db_path))
        engine = CitationEngine(str(db_path), "12345", conn=conn)

        # Backfill les 10 premiers
        match_ids = [
            r[0]
            for r in conn.execute("SELECT match_id FROM match_stats ORDER BY start_time").fetchall()
        ]
        for mid in match_ids[:10]:
            engine.compute_and_store_for_match(mid, conn=conn)

        n_after_first = conn.execute("SELECT COUNT(*) FROM match_citations").fetchone()[0]
        assert n_after_first > 0

        # Vérifier quels matchs n'ont pas de citations
        missing = conn.execute(
            "SELECT COUNT(*) FROM match_stats ms "
            "WHERE NOT EXISTS (SELECT 1 FROM match_citations mc WHERE mc.match_id = ms.match_id)"
        ).fetchone()[0]
        assert missing == 40  # 50 - 10

        # Backfill le reste
        for mid in match_ids[10:]:
            engine.compute_and_store_for_match(mid, conn=conn)

        n_after_second = conn.execute("SELECT COUNT(*) FROM match_citations").fetchone()[0]
        assert n_after_second > n_after_first

        conn.close()

    def test_data_coherence(self, integ_env: tuple[Path, Path]) -> None:
        """Cohérence : chaque match a des citations cohérentes avec ses données."""
        db_path, _meta = integ_env

        conn = duckdb.connect(str(db_path))
        engine = CitationEngine(str(db_path), "12345", conn=conn)

        # Backfill un match spécifique avec des données connues
        mid = "match-0006"  # 6ème match : assists=12, pilote (car 6%3==0), pas écrasement

        engine.compute_and_store_for_match(mid, conn=conn)

        # Vérifier assistant = assists du match
        stats = conn.execute("SELECT assists FROM match_stats WHERE match_id = ?", [mid]).fetchone()
        citation_assistant = conn.execute(
            "SELECT value FROM match_citations WHERE match_id = ? AND citation_name_norm = 'assistant'",
            [mid],
        ).fetchone()
        assert citation_assistant is not None
        assert citation_assistant[0] == stats[0]

        # Vérifier pilote présent (match 6 = multiple de 3)
        citation_pilote = conn.execute(
            "SELECT value FROM match_citations WHERE match_id = ? AND citation_name_norm = 'pilote'",
            [mid],
        ).fetchone()
        assert citation_pilote is not None
        assert citation_pilote[0] > 0

        conn.close()


class TestPerformance:
    """Tests de performance de l'agrégation."""

    def test_aggregation_under_100ms(self, integ_env: tuple[Path, Path]) -> None:
        """L'agrégation de 50 matchs doit prendre < 100ms."""
        import time

        db_path, _meta = integ_env

        conn = duckdb.connect(str(db_path))
        engine = CitationEngine(str(db_path), "12345", conn=conn)

        # Backfill tout
        match_ids = [
            r[0]
            for r in conn.execute("SELECT match_id FROM match_stats ORDER BY start_time").fetchall()
        ]
        for mid in match_ids:
            engine.compute_and_store_for_match(mid, conn=conn)

        # Mesurer l'agrégation
        start = time.perf_counter()
        for _ in range(10):
            engine.aggregate_for_display()
        elapsed = (time.perf_counter() - start) / 10

        conn.close()

        assert elapsed < 0.1, f"Agrégation trop lente : {elapsed:.3f}s (cible < 0.1s)"
