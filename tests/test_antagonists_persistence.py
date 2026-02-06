"""Tests d'intégration pour la persistance des antagonistes (Sprint 3.2).

Ces tests vérifient:
1. L'agrégation des données antagonistes sur plusieurs matchs
2. La sauvegarde/chargement depuis DuckDB
3. Les méthodes du DuckDBRepository
"""

from __future__ import annotations

import gc
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from src.analysis.antagonists import (
    AggregationResult,
    AntagonistEntry,
    aggregate_antagonists,
)
from src.analysis.killer_victim import (
    EstimatedCount,
    OpponentDuel,
)


@dataclass
class MockAntagonistsResult:
    """Mock pour AntagonistsResult."""

    nemesis: OpponentDuel | None = None
    bully: OpponentDuel | None = None
    my_deaths_total: int = 0
    my_deaths_assigned_certain: int = 0
    my_deaths_assigned_total: int = 0
    my_kills_total: int = 0
    my_kills_assigned_certain: int = 0
    my_kills_assigned_total: int = 0
    is_validated: bool = True
    validation_notes: str = ""


class TestAntagonistEntry:
    """Tests pour la classe AntagonistEntry."""

    def test_net_kills_positive(self) -> None:
        """net_kills est positif quand on a plus tué."""
        entry = AntagonistEntry(
            opponent_xuid="123",
            opponent_gamertag="Test",
            times_killed=10,
            times_killed_by=5,
        )
        assert entry.net_kills == 5

    def test_net_kills_negative(self) -> None:
        """net_kills est négatif quand on a été plus tué."""
        entry = AntagonistEntry(
            opponent_xuid="123",
            opponent_gamertag="Test",
            times_killed=3,
            times_killed_by=8,
        )
        assert entry.net_kills == -5

    def test_net_kills_zero(self) -> None:
        """net_kills est zéro quand c'est équilibré."""
        entry = AntagonistEntry(
            opponent_xuid="123",
            opponent_gamertag="Test",
            times_killed=5,
            times_killed_by=5,
        )
        assert entry.net_kills == 0


class TestAggregateAntagonists:
    """Tests pour la fonction aggregate_antagonists."""

    def test_empty_results(self) -> None:
        """Une liste vide retourne un résultat vide."""
        result = aggregate_antagonists([])
        assert result.matches_processed == 0
        assert len(result.entries) == 0

    def test_single_match_with_nemesis(self) -> None:
        """Un seul match avec un nemesis."""
        nemesis = OpponentDuel(
            xuid="2",
            gamertag="KillerA",
            opponent_killed_me=EstimatedCount(certain=3, estimated=0),
            me_killed_opponent=EstimatedCount(certain=1, estimated=0),
        )

        ar = MockAntagonistsResult(
            nemesis=nemesis,
            my_deaths_total=3,
            my_kills_total=1,
        )

        match_time = datetime(2026, 1, 15, 10, 0, 0)
        result = aggregate_antagonists([(match_time, ar)])

        assert result.matches_processed == 1
        assert len(result.entries) == 1

        entry = result.entries[0]
        assert entry.opponent_xuid == "2"
        assert entry.opponent_gamertag == "KillerA"
        assert entry.times_killed_by == 3
        assert entry.times_killed == 1
        assert entry.matches_against == 1
        assert entry.net_kills == -2

    def test_multiple_matches_same_opponent(self) -> None:
        """Plusieurs matchs contre le même adversaire."""
        match_time1 = datetime(2026, 1, 15, 10, 0, 0)
        match_time2 = datetime(2026, 1, 16, 14, 0, 0)

        nemesis1 = OpponentDuel(
            xuid="2",
            gamertag="KillerA",
            opponent_killed_me=EstimatedCount(certain=3, estimated=0),
            me_killed_opponent=EstimatedCount(certain=1, estimated=0),
        )
        ar1 = MockAntagonistsResult(nemesis=nemesis1, my_deaths_total=3, my_kills_total=1)

        nemesis2 = OpponentDuel(
            xuid="2",
            gamertag="KillerA",
            opponent_killed_me=EstimatedCount(certain=2, estimated=1),
            me_killed_opponent=EstimatedCount(certain=4, estimated=0),
        )
        ar2 = MockAntagonistsResult(nemesis=nemesis2, my_deaths_total=3, my_kills_total=4)

        result = aggregate_antagonists(
            [
                (match_time1, ar1),
                (match_time2, ar2),
            ]
        )

        assert result.matches_processed == 2
        assert len(result.entries) == 1

        entry = result.entries[0]
        assert entry.opponent_xuid == "2"
        assert entry.times_killed_by == 3 + 3  # 3 + (2+1)
        assert entry.times_killed == 1 + 4  # 1 + 4
        assert entry.matches_against == 2
        assert entry.last_encounter == match_time2

    def test_different_opponents(self) -> None:
        """Différents adversaires créent différentes entrées."""
        match_time = datetime(2026, 1, 15, 10, 0, 0)

        nemesis1 = OpponentDuel(
            xuid="2",
            gamertag="PlayerA",
            opponent_killed_me=EstimatedCount(certain=3, estimated=0),
            me_killed_opponent=EstimatedCount(certain=0, estimated=0),
        )
        bully1 = OpponentDuel(
            xuid="3",
            gamertag="PlayerB",
            opponent_killed_me=EstimatedCount(certain=0, estimated=0),
            me_killed_opponent=EstimatedCount(certain=5, estimated=0),
        )

        ar = MockAntagonistsResult(
            nemesis=nemesis1,
            bully=bully1,
            my_deaths_total=3,
            my_kills_total=5,
        )

        result = aggregate_antagonists([(match_time, ar)])

        assert len(result.entries) == 2

        xuids = {e.opponent_xuid for e in result.entries}
        assert xuids == {"2", "3"}

    def test_min_encounters_filter(self) -> None:
        """Le filtre min_encounters exclut les rencontres uniques."""
        match_time1 = datetime(2026, 1, 15, 10, 0, 0)
        match_time2 = datetime(2026, 1, 16, 14, 0, 0)

        # PlayerA: 2 matchs
        nemesis1 = OpponentDuel(
            xuid="2",
            gamertag="PlayerA",
            opponent_killed_me=EstimatedCount(certain=1, estimated=0),
            me_killed_opponent=EstimatedCount(certain=0, estimated=0),
        )
        nemesis2 = OpponentDuel(
            xuid="2",
            gamertag="PlayerA",
            opponent_killed_me=EstimatedCount(certain=2, estimated=0),
            me_killed_opponent=EstimatedCount(certain=0, estimated=0),
        )

        # PlayerB: 1 match seulement
        bully1 = OpponentDuel(
            xuid="3",
            gamertag="PlayerB",
            opponent_killed_me=EstimatedCount(certain=0, estimated=0),
            me_killed_opponent=EstimatedCount(certain=5, estimated=0),
        )

        ar1 = MockAntagonistsResult(
            nemesis=nemesis1, bully=bully1, my_deaths_total=1, my_kills_total=5
        )
        ar2 = MockAntagonistsResult(nemesis=nemesis2, my_deaths_total=2, my_kills_total=0)

        # Avec min_encounters=2, PlayerB (1 match) est exclu
        result = aggregate_antagonists(
            [(match_time1, ar1), (match_time2, ar2)],
            min_encounters=2,
        )

        assert len(result.entries) == 1
        assert result.entries[0].opponent_xuid == "2"

    def test_top_nemeses_sorting(self) -> None:
        """get_top_nemeses trie par times_killed_by décroissant."""
        entries = [
            AntagonistEntry("1", "A", times_killed=0, times_killed_by=5, matches_against=2),
            AntagonistEntry("2", "B", times_killed=0, times_killed_by=10, matches_against=3),
            AntagonistEntry("3", "C", times_killed=0, times_killed_by=3, matches_against=1),
        ]

        result = AggregationResult(entries=entries)
        top = result.get_top_nemeses(limit=2)

        assert len(top) == 2
        assert top[0].opponent_xuid == "2"  # 10 kills
        assert top[1].opponent_xuid == "1"  # 5 kills

    def test_top_victims_sorting(self) -> None:
        """get_top_victims trie par times_killed décroissant."""
        entries = [
            AntagonistEntry("1", "A", times_killed=8, times_killed_by=0, matches_against=2),
            AntagonistEntry("2", "B", times_killed=3, times_killed_by=0, matches_against=3),
            AntagonistEntry("3", "C", times_killed=12, times_killed_by=0, matches_against=1),
        ]

        result = AggregationResult(entries=entries)
        top = result.get_top_victims(limit=2)

        assert len(top) == 2
        assert top[0].opponent_xuid == "3"  # 12 kills
        assert top[1].opponent_xuid == "1"  # 8 kills


class TestDuckDBRepositorySaveAntagonists:
    """Tests pour save_antagonists et load_antagonists du DuckDBRepository."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path):
        """Crée une DB DuckDB temporaire pour les tests.

        Utilise tmp_path (pytest) au lieu de tempfile.TemporaryDirectory pour éviter
        les segfaults DuckDB sur Windows (WAL lockfiles, cleanup trop rapide).
        """
        db_path = tmp_path.resolve() / "stats.duckdb"
        conn = duckdb.connect(str(db_path))
        try:
            conn.execute("""
                CREATE TABLE match_stats (
                    match_id VARCHAR PRIMARY KEY,
                    start_time TIMESTAMP
                )
            """)
        finally:
            conn.close()
            del conn
            gc.collect()  # Aide à libérer les lockfiles WAL sur Windows
        return db_path

    def test_save_and_load_antagonists(self, temp_db: Path) -> None:
        """Sauvegarde et charge des antagonistes."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path=temp_db,
            xuid="123456789",
            read_only=False,
        )

        entries = [
            AntagonistEntry(
                opponent_xuid="111",
                opponent_gamertag="PlayerA",
                times_killed=10,
                times_killed_by=5,
                matches_against=3,
                last_encounter=datetime(2026, 1, 15, 10, 0, 0),
            ),
            AntagonistEntry(
                opponent_xuid="222",
                opponent_gamertag="PlayerB",
                times_killed=3,
                times_killed_by=8,
                matches_against=2,
                last_encounter=datetime(2026, 1, 16, 14, 0, 0),
            ),
        ]

        # Sauvegarder
        saved = repo.save_antagonists(entries)
        assert saved == 2

        # Charger
        loaded = repo.load_antagonists()
        assert len(loaded) == 2

        # Vérifier les données (triées par net_kills desc par défaut)
        # PlayerA: net_kills = 10 - 5 = 5
        # PlayerB: net_kills = 3 - 8 = -5
        assert loaded[0]["opponent_xuid"] == "111"
        assert loaded[0]["net_kills"] == 5

        assert loaded[1]["opponent_xuid"] == "222"
        assert loaded[1]["net_kills"] == -5

        repo.close()

    def test_upsert_updates_existing(self, temp_db: Path) -> None:
        """L'upsert met à jour les entrées existantes."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path=temp_db,
            xuid="123456789",
            read_only=False,
        )

        # Première insertion
        entries1 = [
            AntagonistEntry(
                opponent_xuid="111",
                opponent_gamertag="PlayerA",
                times_killed=5,
                times_killed_by=3,
                matches_against=2,
            ),
        ]
        repo.save_antagonists(entries1)

        # Mise à jour
        entries2 = [
            AntagonistEntry(
                opponent_xuid="111",
                opponent_gamertag="PlayerA_NewName",
                times_killed=15,
                times_killed_by=8,
                matches_against=5,
            ),
        ]
        repo.save_antagonists(entries2)

        # Vérifier
        loaded = repo.load_antagonists()
        assert len(loaded) == 1
        assert loaded[0]["opponent_gamertag"] == "PlayerA_NewName"
        assert loaded[0]["times_killed"] == 15
        assert loaded[0]["times_killed_by"] == 8
        assert loaded[0]["matches_against"] == 5

        repo.close()

    def test_replace_clears_existing(self, temp_db: Path) -> None:
        """L'option replace supprime les données existantes."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path=temp_db,
            xuid="123456789",
            read_only=False,
        )

        # Première insertion
        entries1 = [
            AntagonistEntry("111", "PlayerA", 5, 3, 2),
            AntagonistEntry("222", "PlayerB", 10, 5, 4),
        ]
        repo.save_antagonists(entries1)
        assert len(repo.load_antagonists()) == 2

        # Replace avec un seul
        entries2 = [
            AntagonistEntry("333", "PlayerC", 7, 7, 3),
        ]
        repo.save_antagonists(entries2, replace=True)

        loaded = repo.load_antagonists()
        assert len(loaded) == 1
        assert loaded[0]["opponent_xuid"] == "333"

        repo.close()

    def test_get_top_nemeses(self, temp_db: Path) -> None:
        """get_top_nemeses retourne triés par times_killed_by."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path=temp_db,
            xuid="123456789",
            read_only=False,
        )

        entries = [
            AntagonistEntry("111", "A", times_killed=10, times_killed_by=2, matches_against=2),
            AntagonistEntry("222", "B", times_killed=1, times_killed_by=15, matches_against=4),
            AntagonistEntry("333", "C", times_killed=5, times_killed_by=8, matches_against=3),
        ]
        repo.save_antagonists(entries)

        top = repo.get_top_nemeses(limit=2)
        assert len(top) == 2
        assert top[0]["opponent_xuid"] == "222"  # 15 deaths
        assert top[1]["opponent_xuid"] == "333"  # 8 deaths

        repo.close()

    def test_get_top_victims(self, temp_db: Path) -> None:
        """get_top_victims retourne triés par times_killed."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path=temp_db,
            xuid="123456789",
            read_only=False,
        )

        entries = [
            AntagonistEntry("111", "A", times_killed=10, times_killed_by=2, matches_against=2),
            AntagonistEntry("222", "B", times_killed=1, times_killed_by=15, matches_against=4),
            AntagonistEntry("333", "C", times_killed=20, times_killed_by=8, matches_against=3),
        ]
        repo.save_antagonists(entries)

        top = repo.get_top_victims(limit=2)
        assert len(top) == 2
        assert top[0]["opponent_xuid"] == "333"  # 20 kills
        assert top[1]["opponent_xuid"] == "111"  # 10 kills

        repo.close()


class TestDuckDBRepositoryEmptyTable:
    """Tests pour le comportement avec une table vide ou inexistante."""

    @pytest.fixture
    def temp_db(self):
        """Crée une DB DuckDB temporaire."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "stats.duckdb"
            conn = duckdb.connect(str(db_path))
            conn.execute("CREATE TABLE match_stats (match_id VARCHAR)")
            conn.close()
            yield db_path

    def test_load_from_nonexistent_table(self, temp_db: Path) -> None:
        """load_antagonists retourne une liste vide si la table n'existe pas."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path=temp_db,
            xuid="123456789",
            read_only=True,
        )

        # La table antagonists n'existe pas encore
        loaded = repo.load_antagonists()
        assert loaded == []

        repo.close()

    def test_save_creates_table(self, temp_db: Path) -> None:
        """save_antagonists crée la table si elle n'existe pas."""
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(
            player_db_path=temp_db,
            xuid="123456789",
            read_only=False,
        )

        entries = [AntagonistEntry("111", "Test", 5, 3, 2)]
        saved = repo.save_antagonists(entries)
        assert saved == 1

        # Vérifier que la table existe maintenant
        loaded = repo.load_antagonists()
        assert len(loaded) == 1

        repo.close()
