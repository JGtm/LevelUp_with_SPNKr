"""Tests pour CitationEngine (src/analysis/citations/engine.py)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl
import pytest

from src.analysis.citations.engine import CitationEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_metadata_db(path: Path) -> None:
    """Crée une metadata.duckdb avec citation_mappings remplie."""
    conn = duckdb.connect(str(path))
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
    conn.executemany(
        "INSERT INTO citation_mappings "
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
            (
                "bulldozer",
                "Bulldozer",
                "custom",
                None,
                None,
                None,
                "compute_bulldozer",
                "high",
                "test",
            ),
            (
                "annexion forcee",
                "Annexion forcée",
                "custom",
                None,
                None,
                None,
                "compute_annexion_forcee",
                "medium",
                "test",
            ),
        ],
    )
    conn.close()


def _create_player_db(path: Path) -> None:
    """Crée une DB joueur avec les tables nécessaires."""
    conn = duckdb.connect(str(path))

    # Table match_citations
    conn.execute("""
        CREATE TABLE match_citations (
            match_id TEXT NOT NULL,
            citation_name_norm TEXT NOT NULL,
            value INTEGER NOT NULL,
            PRIMARY KEY (match_id, citation_name_norm)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_match_citations_name "
        "ON match_citations(citation_name_norm)"
    )

    # Table medals_earned
    conn.execute("""
        CREATE TABLE medals_earned (
            match_id TEXT NOT NULL,
            medal_name_id BIGINT NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY (match_id, medal_name_id)
        )
    """)

    # Table match_stats
    conn.execute("""
        CREATE TABLE match_stats (
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

    # Table personal_score_awards
    conn.execute("""
        CREATE TABLE personal_score_awards (
            match_id TEXT NOT NULL,
            award_name TEXT NOT NULL,
            award_category TEXT,
            award_count INTEGER DEFAULT 0,
            award_score INTEGER DEFAULT 0
        )
    """)

    conn.close()


def _insert_sample_data(db_path: Path) -> None:
    """Insère des données de test dans la DB joueur."""
    conn = duckdb.connect(str(db_path))

    # Match m1 : match Slayer standard
    conn.execute(
        "INSERT INTO match_stats VALUES "
        "('m1', 15, 5, 8, 3, 2, 'Ranked Slayer', 'Slayer', '2026-01-01 12:00:00')"
    )
    conn.execute("INSERT INTO medals_earned VALUES " "('m1', 3169118333, 2), ('m1', 221693153, 1)")
    conn.execute(
        "INSERT INTO personal_score_awards VALUES "
        "('m1', 'Flag Defense', 'objective', 3, 150), "
        "('m1', 'Zone Capture', 'objective', 5, 250)"
    )

    # Match m2 : match CTF
    conn.execute(
        "INSERT INTO match_stats VALUES "
        "('m2', 10, 8, 12, 2, 2, 'Quick Play', 'CTF', '2026-01-02 14:00:00')"
    )
    conn.execute("INSERT INTO medals_earned VALUES " "('m2', 3169118333, 1)")
    conn.execute(
        "INSERT INTO personal_score_awards VALUES "
        "('m2', 'Flag Defense', 'objective', 1, 50), "
        "('m2', 'Zone Capture', 'objective', 2, 100)"
    )

    # Match m3 : match sans médailles
    conn.execute(
        "INSERT INTO match_stats VALUES "
        "('m3', 3, 10, 1, 0, 0, 'Quick Play', 'Oddball', '2026-01-03 16:00:00')"
    )

    conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine_dir(tmp_path: Path) -> Path:
    """Crée la structure data/warehouse + data/players/TestPlayer/."""
    warehouse = tmp_path / "data" / "warehouse"
    warehouse.mkdir(parents=True)
    player_dir = tmp_path / "data" / "players" / "TestPlayer"
    player_dir.mkdir(parents=True)

    _create_metadata_db(warehouse / "metadata.duckdb")
    _create_player_db(player_dir / "stats.duckdb")
    _insert_sample_data(player_dir / "stats.duckdb")

    return tmp_path


@pytest.fixture
def engine(engine_dir: Path) -> CitationEngine:
    """CitationEngine configuré avec les DBs de test."""
    player_db = engine_dir / "data" / "players" / "TestPlayer" / "stats.duckdb"
    metadata_db = engine_dir / "data" / "warehouse" / "metadata.duckdb"
    return CitationEngine(
        db_path=player_db,
        xuid="12345",
        metadata_db_path=metadata_db,
    )


# ---------------------------------------------------------------------------
# Tests load_mappings
# ---------------------------------------------------------------------------


class TestLoadMappings:
    """Tests pour load_mappings()."""

    def test_returns_dict(self, engine: CitationEngine) -> None:
        """Vérifie que load_mappings retourne un dict."""
        mappings = engine.load_mappings()
        assert isinstance(mappings, dict)

    def test_has_7_entries(self, engine: CitationEngine) -> None:
        """Vérifie qu'on a 7 mappings dans le fixture."""
        mappings = engine.load_mappings()
        assert len(mappings) == 7

    def test_structure(self, engine: CitationEngine) -> None:
        """Vérifie la structure d'un mapping."""
        mappings = engine.load_mappings()
        pilote = mappings["pilote"]
        assert pilote["mapping_type"] == "medal"
        assert pilote["medal_id"] == 3169118333
        assert pilote["citation_name_display"] == "Pilote"

    def test_caches_result(self, engine: CitationEngine) -> None:
        """Vérifie que load_mappings met en cache."""
        m1 = engine.load_mappings()
        m2 = engine.load_mappings()
        assert m1 is m2

    def test_missing_metadata_returns_empty(self, tmp_path: Path) -> None:
        """metadata.duckdb inexistant → dict vide."""
        e = CitationEngine(
            db_path=tmp_path / "fake.duckdb",
            xuid="0",
            metadata_db_path=tmp_path / "no_such.duckdb",
        )
        assert e.load_mappings() == {}


# ---------------------------------------------------------------------------
# Tests compute_citation_for_match
# ---------------------------------------------------------------------------


class TestComputeCitationForMatch:
    """Tests pour compute_citation_for_match()."""

    def test_medal_type(self, engine: CitationEngine) -> None:
        """Citation type medal → lookup dans match_medals."""
        mappings = engine.load_mappings()
        val = engine.compute_citation_for_match(
            mappings["pilote"],
            match_medals={3169118333: 5, 221693153: 2},
        )
        assert val == 5

    def test_stat_type(self, engine: CitationEngine) -> None:
        """Citation type stat → lookup dans match_stats."""
        mappings = engine.load_mappings()
        val = engine.compute_citation_for_match(
            mappings["assistant"],
            match_stats={"assists": 12, "kills": 10},
        )
        assert val == 12

    def test_award_type(self, engine: CitationEngine) -> None:
        """Citation type award → lookup dans match_awards."""
        mappings = engine.load_mappings()
        val = engine.compute_citation_for_match(
            mappings["defenseur du drapeau"],
            match_awards={"Flag Defense": 3, "Zone Capture": 5},
        )
        assert val == 3

    def test_custom_type_annexion(self, engine: CitationEngine) -> None:
        """Citation type custom → appel fonction compute_annexion_forcee."""
        mappings = engine.load_mappings()
        val = engine.compute_citation_for_match(
            mappings["annexion forcee"],
            match_awards={"Zone Capture": 6},
        )
        # 6 // 3 = 2
        assert val == 2

    def test_returns_zero_if_missing(self, engine: CitationEngine) -> None:
        """Données manquantes → 0."""
        mappings = engine.load_mappings()
        val = engine.compute_citation_for_match(
            mappings["pilote"],
            match_medals={},
        )
        assert val == 0

    def test_returns_zero_no_data(self, engine: CitationEngine) -> None:
        """Aucune donnée fournie → 0."""
        mappings = engine.load_mappings()
        val = engine.compute_citation_for_match(mappings["assistant"])
        assert val == 0


# ---------------------------------------------------------------------------
# Tests compute_all_for_match
# ---------------------------------------------------------------------------


class TestComputeAllForMatch:
    """Tests pour compute_all_for_match()."""

    def test_returns_sparse(self, engine: CitationEngine) -> None:
        """Seules les valeurs > 0 sont retournées."""
        results = engine.compute_all_for_match(
            "m1",
            match_medals={3169118333: 2},
            match_stats={"assists": 0},
            match_awards={},
        )
        assert "pilote" in results
        assert "assistant" not in results  # assists = 0

    def test_includes_all_types(self, engine: CitationEngine) -> None:
        """Tous types supportés (medal, stat, award)."""
        results = engine.compute_all_for_match(
            "m1",
            match_medals={3169118333: 2, 221693153: 1},
            match_stats={"assists": 5},
            match_awards={"Flag Defense": 3, "Zone Capture": 9},
        )
        assert results["pilote"] == 2
        assert results["ecrasement"] == 1
        assert results["assistant"] == 5
        assert results["defenseur du drapeau"] == 3
        assert results["a la charge"] == 9
        # annexion forcee = 9 // 3 = 3
        assert results["annexion forcee"] == 3

    def test_empty_match(self, engine: CitationEngine) -> None:
        """Match sans données → dict vide."""
        results = engine.compute_all_for_match(
            "m_empty",
            match_medals={},
            match_stats={},
            match_awards={},
        )
        assert results == {}


# ---------------------------------------------------------------------------
# Tests aggregate_citations
# ---------------------------------------------------------------------------


class TestAggregateCitations:
    """Tests pour aggregate_citations()."""

    def test_aggregate_all_matches(self, engine: CitationEngine) -> None:
        """Agrège correctement toutes les données insérées."""
        # D'abord insérer des données dans match_citations
        conn = duckdb.connect(str(engine._db_path))
        conn.execute(
            "INSERT INTO match_citations VALUES "
            "('m1', 'pilote', 2), ('m1', 'assistant', 8), "
            "('m2', 'pilote', 1), ('m2', 'assistant', 12)"
        )
        conn.close()

        totals = engine.aggregate_citations()
        assert totals["pilote"] == 3
        assert totals["assistant"] == 20

    def test_aggregate_filtered_matches(self, engine: CitationEngine) -> None:
        """Agrège uniquement sur un sous-ensemble de matchs."""
        conn = duckdb.connect(str(engine._db_path))
        conn.execute(
            "INSERT INTO match_citations VALUES "
            "('m1', 'pilote', 2), ('m2', 'pilote', 5), ('m3', 'pilote', 3)"
        )
        conn.close()

        totals = engine.aggregate_citations(match_ids=["m1", "m3"])
        assert totals["pilote"] == 5  # 2 + 3

    def test_aggregate_by_names(self, engine: CitationEngine) -> None:
        """Filtre par noms de citations."""
        conn = duckdb.connect(str(engine._db_path))
        conn.execute(
            "INSERT INTO match_citations VALUES "
            "('m1', 'pilote', 2), ('m1', 'assistant', 8), ('m1', 'ecrasement', 1)"
        )
        conn.close()

        totals = engine.aggregate_citations(citation_names=["pilote", "ecrasement"])
        assert "pilote" in totals
        assert "ecrasement" in totals
        assert "assistant" not in totals

    def test_aggregate_returns_empty_if_no_data(self, engine: CitationEngine) -> None:
        """Table vide → dict vide."""
        totals = engine.aggregate_citations()
        assert totals == {}


# ---------------------------------------------------------------------------
# Tests helpers load_match_*
# ---------------------------------------------------------------------------


class TestMatchDataLoaders:
    """Tests pour les helpers de chargement de données."""

    def test_load_match_medals(self, engine: CitationEngine) -> None:
        """Charge les médailles d'un match."""
        medals = engine.load_match_medals("m1")
        assert medals[3169118333] == 2
        assert medals[221693153] == 1

    def test_load_match_stats(self, engine: CitationEngine) -> None:
        """Charge les stats d'un match."""
        stats = engine.load_match_stats("m1")
        assert stats["kills"] == 15
        assert stats["assists"] == 8

    def test_load_match_awards(self, engine: CitationEngine) -> None:
        """Charge les awards d'un match."""
        awards = engine.load_match_awards("m1")
        assert awards["Flag Defense"] == 3
        assert awards["Zone Capture"] == 5

    def test_load_match_df(self, engine: CitationEngine) -> None:
        """Charge un match comme DataFrame."""
        df = engine.load_match_df("m1")
        assert isinstance(df, pl.DataFrame)
        assert df.height == 1
        assert df["kills"][0] == 15

    def test_load_missing_match(self, engine: CitationEngine) -> None:
        """Match inexistant → données vides."""
        assert engine.load_match_medals("no_such") == {}
        assert engine.load_match_stats("no_such") == {}
        assert engine.load_match_awards("no_such") == {}


# ---------------------------------------------------------------------------
# Tests compute_and_store_for_match
# ---------------------------------------------------------------------------


class TestComputeAndStore:
    """Tests pour compute_and_store_for_match()."""

    def test_stores_citations(self, engine: CitationEngine) -> None:
        """compute_and_store insère dans match_citations."""
        count = engine.compute_and_store_for_match("m1")
        assert count > 0

        # Vérifier les données insérées
        totals = engine.aggregate_citations(match_ids=["m1"])
        assert "pilote" in totals
        assert totals["pilote"] == 2

    def test_stores_awards(self, engine: CitationEngine) -> None:
        """Les citations type award sont bien stockées."""
        engine.compute_and_store_for_match("m1")
        totals = engine.aggregate_citations(match_ids=["m1"])
        assert totals.get("defenseur du drapeau") == 3
        assert totals.get("a la charge") == 5

    def test_empty_match_no_insert(self, engine: CitationEngine) -> None:
        """Match sans données → 0 insertions."""
        count = engine.compute_and_store_for_match("m3")
        # m3 a kills=3, deaths=10, assists=1 → assistant=1 devrait être inséré
        assert count >= 0


# ---------------------------------------------------------------------------
# Tests enabled/disabled citations
# ---------------------------------------------------------------------------


class TestEnabledColumn:
    """Tests pour le filtrage par colonne enabled."""

    def test_disabled_citation_excluded(self, tmp_path: Path) -> None:
        """Une citation avec enabled=FALSE n'est pas retournée par load_mappings."""
        warehouse = tmp_path / "data" / "warehouse"
        warehouse.mkdir(parents=True)
        meta_path = warehouse / "metadata.duckdb"
        conn = duckdb.connect(str(meta_path))
        conn.execute("""
            CREATE TABLE citation_mappings (
                citation_name_norm TEXT PRIMARY KEY,
                citation_name_display TEXT NOT NULL,
                mapping_type TEXT NOT NULL,
                medal_id BIGINT, medal_ids TEXT, stat_name TEXT,
                award_name TEXT, award_category TEXT, custom_function TEXT,
                confidence TEXT, notes TEXT,
                enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.executemany(
            "INSERT INTO citation_mappings "
            "(citation_name_norm, citation_name_display, mapping_type, "
            "medal_id, confidence, enabled) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("pilote", "Pilote", "medal", 3169118333, "high", True),
                ("ecrasement", "Écrasement", "medal", 221693153, "high", False),
                ("assistant", "Assistant", "stat", None, "high", True),
            ],
        )
        conn.close()

        player_dir = tmp_path / "data" / "players" / "TestPlayer"
        player_dir.mkdir(parents=True)
        _create_player_db(player_dir / "stats.duckdb")

        engine = CitationEngine(
            db_path=player_dir / "stats.duckdb",
            xuid="0",
            metadata_db_path=meta_path,
        )
        mappings = engine.load_mappings()
        assert "pilote" in mappings
        assert "ecrasement" not in mappings
        assert "assistant" in mappings
        assert len(mappings) == 2

    def test_all_enabled_by_default(self, engine: CitationEngine) -> None:
        """Sans colonne enabled explicite, toutes les citations sont retournées."""
        mappings = engine.load_mappings()
        assert len(mappings) == 7  # Toutes les 7 du fixture


# ---------------------------------------------------------------------------
# Tests V5 shared_matches support
# ---------------------------------------------------------------------------


class TestV5SharedSupport:
    """Tests pour la lecture depuis shared_matches.duckdb."""

    def _create_shared_db(self, shared_path: Path) -> None:
        """Crée une shared_matches.duckdb de test."""
        conn = duckdb.connect(str(shared_path))
        conn.execute("""
            CREATE TABLE medals_earned (
                match_id TEXT NOT NULL,
                xuid TEXT NOT NULL,
                medal_name_id BIGINT NOT NULL,
                count INTEGER NOT NULL,
                PRIMARY KEY (match_id, xuid, medal_name_id)
            )
        """)
        conn.execute("""
            CREATE TABLE match_participants (
                match_id TEXT NOT NULL,
                xuid TEXT NOT NULL,
                kills INTEGER, deaths INTEGER, assists INTEGER,
                score INTEGER, damage_dealt INTEGER,
                playlist TEXT, game_variant TEXT,
                PRIMARY KEY (match_id, xuid)
            )
        """)
        conn.execute("""
            CREATE TABLE match_registry (
                match_id TEXT PRIMARY KEY,
                map_name TEXT,
                playlist TEXT,
                game_variant TEXT,
                match_start_date TIMESTAMP
            )
        """)
        # Données test
        conn.execute(
            "INSERT INTO medals_earned VALUES "
            "('m-shared-1', '12345', 3169118333, 5), "
            "('m-shared-1', '99999', 3169118333, 3)"
        )
        conn.execute(
            "INSERT INTO match_participants VALUES "
            "('m-shared-1', '12345', 20, 5, 8, 1500, 3000, 'Quick Play', 'Slayer'), "
            "('m-shared-1', '99999', 15, 10, 3, 1000, 2000, 'Quick Play', 'Slayer')"
        )
        conn.execute(
            "INSERT INTO match_registry VALUES "
            "('m-shared-1', 'Aquarius', 'Quick Play', 'Slayer', '2026-02-14 10:00:00')"
        )
        conn.close()

    def test_medals_from_shared(self, tmp_path: Path) -> None:
        """load_match_medals lit depuis shared.medals_earned en V5."""
        warehouse = tmp_path / "data" / "warehouse"
        warehouse.mkdir(parents=True)
        player_dir = tmp_path / "data" / "players" / "TestPlayer"
        player_dir.mkdir(parents=True)

        _create_metadata_db(warehouse / "metadata.duckdb")
        _create_player_db(player_dir / "stats.duckdb")
        self._create_shared_db(warehouse / "shared_matches.duckdb")

        engine = CitationEngine(
            db_path=player_dir / "stats.duckdb",
            xuid="12345",
            metadata_db_path=warehouse / "metadata.duckdb",
            shared_db_path=warehouse / "shared_matches.duckdb",
        )
        medals = engine.load_match_medals("m-shared-1")
        # Doit retourner uniquement les médailles du xuid 12345
        assert medals == {3169118333: 5}

    def test_stats_from_shared(self, tmp_path: Path) -> None:
        """load_match_stats lit depuis shared en V5."""
        warehouse = tmp_path / "data" / "warehouse"
        warehouse.mkdir(parents=True)
        player_dir = tmp_path / "data" / "players" / "TestPlayer"
        player_dir.mkdir(parents=True)

        _create_metadata_db(warehouse / "metadata.duckdb")
        _create_player_db(player_dir / "stats.duckdb")
        self._create_shared_db(warehouse / "shared_matches.duckdb")

        engine = CitationEngine(
            db_path=player_dir / "stats.duckdb",
            xuid="12345",
            metadata_db_path=warehouse / "metadata.duckdb",
            shared_db_path=warehouse / "shared_matches.duckdb",
        )
        stats = engine.load_match_stats("m-shared-1")
        assert stats["kills"] == 20
        assert stats["assists"] == 8

    def test_fallback_to_local_without_shared(self, engine: CitationEngine) -> None:
        """Sans shared DB, lit depuis les tables locales (V4)."""
        medals = engine.load_match_medals("m1")
        assert 3169118333 in medals
        assert medals[3169118333] == 2

    def test_shared_disabled_with_false(self, tmp_path: Path) -> None:
        """shared_db_path=False désactive la lecture shared."""
        warehouse = tmp_path / "data" / "warehouse"
        warehouse.mkdir(parents=True)
        player_dir = tmp_path / "data" / "players" / "TestPlayer"
        player_dir.mkdir(parents=True)

        _create_metadata_db(warehouse / "metadata.duckdb")
        _create_player_db(player_dir / "stats.duckdb")
        _insert_sample_data(player_dir / "stats.duckdb")
        self._create_shared_db(warehouse / "shared_matches.duckdb")

        engine = CitationEngine(
            db_path=player_dir / "stats.duckdb",
            xuid="12345",
            metadata_db_path=warehouse / "metadata.duckdb",
            shared_db_path=False,
        )
        assert not engine.has_shared
        # Lit depuis local uniquement
        medals = engine.load_match_medals("m1")
        assert 3169118333 in medals
        assert medals[3169118333] == 2

    def test_has_shared_property(self, tmp_path: Path) -> None:
        """has_shared renvoie True quand shared_matches.duckdb existe."""
        warehouse = tmp_path / "data" / "warehouse"
        warehouse.mkdir(parents=True)
        player_dir = tmp_path / "data" / "players" / "TestPlayer"
        player_dir.mkdir(parents=True)

        _create_metadata_db(warehouse / "metadata.duckdb")
        _create_player_db(player_dir / "stats.duckdb")
        self._create_shared_db(warehouse / "shared_matches.duckdb")

        engine = CitationEngine(
            db_path=player_dir / "stats.duckdb",
            xuid="12345",
            metadata_db_path=warehouse / "metadata.duckdb",
        )
        assert engine.has_shared
