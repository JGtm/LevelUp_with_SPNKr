"""
Tests pour l'architecture de données DuckDB (v4).
(Tests for DuckDB data architecture)

Ces tests valident :
1. Les modèles Pydantic (validation des données)
2. Le pattern Repository (interface commune)
3. La factory de repositories
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


class TestMatchModels:
    """Tests des modèles Pydantic pour les matchs."""

    def test_match_fact_input_validation(self):
        """Teste la validation de base d'un MatchFactInput."""
        from src.data.domain.models.match import MatchFactInput, MatchOutcome

        # Données valides
        input_data = MatchFactInput(
            match_id="test-match-123",
            xuid="2533274823110022",
            start_time=datetime.now(timezone.utc),
            outcome=MatchOutcome.WIN,
            kills=10,
            deaths=5,
            assists=3,
        )

        assert input_data.match_id == "test-match-123"
        assert input_data.xuid == "2533274823110022"
        assert input_data.outcome == MatchOutcome.WIN
        assert input_data.kills == 10

    def test_match_fact_input_xuid_parsing(self):
        """Teste le parsing des différents formats de XUID."""
        from src.data.domain.models.match import MatchFactInput

        # Format xuid(...)
        input1 = MatchFactInput(
            match_id="m1",
            xuid="xuid(2533274823110022)",
            start_time=datetime.now(timezone.utc),
        )
        assert input1.xuid == "2533274823110022"

        # Format dict
        input2 = MatchFactInput(
            match_id="m2",
            xuid={"Xuid": "1234567890"},  # type: ignore
            start_time=datetime.now(timezone.utc),
        )
        assert input2.xuid == "1234567890"

    def test_match_fact_from_input(self):
        """Teste la création d'un MatchFact depuis MatchFactInput."""
        from src.data.domain.models.match import MatchFact, MatchFactInput

        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        input_data = MatchFactInput(
            match_id="test-match-456",
            xuid="1234567890",
            start_time=now,
            kills=15,
            deaths=10,
        )

        fact = MatchFact.from_input(input_data)

        assert fact.match_id == "test-match-456"
        assert fact.year == 2025
        assert fact.month == 1
        assert fact.kills == 15

    def test_match_outcome_values(self):
        """Teste les valeurs de l'enum MatchOutcome."""
        from src.data.domain.models.match import MatchOutcome

        assert MatchOutcome.TIE == 1
        assert MatchOutcome.WIN == 2
        assert MatchOutcome.LOSS == 3
        assert MatchOutcome.DID_NOT_FINISH == 4


class TestPlayerProfile:
    """Tests du modèle PlayerProfile."""

    def test_player_profile_creation(self):
        """Teste la création d'un profil joueur."""
        from src.data.domain.models.player import PlayerProfile

        profile = PlayerProfile(
            xuid="1234567890",
            gamertag="TestPlayer",
            career_rank=100,
        )

        assert profile.xuid == "1234567890"
        assert profile.gamertag == "TestPlayer"
        assert profile.career_rank == 100

    def test_player_profile_xuid_parsing(self):
        """Teste le parsing du XUID dans PlayerProfile."""
        from src.data.domain.models.player import PlayerProfile

        profile = PlayerProfile(
            xuid="xuid(9876543210)",
            gamertag="TestPlayer",
        )

        assert profile.xuid == "9876543210"


class TestMedalAward:
    """Tests du modèle MedalAward."""

    def test_medal_award_creation(self):
        """Teste la création d'un MedalAward."""
        from src.data.domain.models.medal import MedalAward

        now = datetime(2025, 1, 15, tzinfo=timezone.utc)
        medal = MedalAward.from_raw(
            match_id="match-123",
            xuid="1234567890",
            start_time=now,
            name_id=17866865,
            count=3,
        )

        assert medal.match_id == "match-123"
        assert medal.medal_name_id == 17866865
        assert medal.count == 3
        assert medal.year == 2025
        assert medal.month == 1


class TestRepositoryFactory:
    """Tests de la factory de repositories."""

    def test_get_repository_duckdb(self, tmp_path):
        """Teste la création d'un DuckDBRepository."""
        import uuid

        from src.data import RepositoryMode, get_repository
        from src.data.repositories.duckdb_repo import DuckDBRepository

        # Créer une DB DuckDB avec nom unique
        db_path = tmp_path / f"stats_{uuid.uuid4().hex[:8]}.duckdb"

        repo = get_repository(str(db_path), "1234567890", mode=RepositoryMode.DUCKDB)

        assert isinstance(repo, DuckDBRepository)
        assert repo.xuid == "1234567890"
        repo.close()

    def test_get_repository_default_mode_is_duckdb(self, tmp_path):
        """Teste que le mode par défaut est DUCKDB."""
        import uuid

        from src.data import get_repository
        from src.data.repositories.duckdb_repo import DuckDBRepository

        db_path = tmp_path / f"stats_{uuid.uuid4().hex[:8]}.duckdb"

        # Sans spécifier le mode, devrait être DUCKDB
        repo = get_repository(str(db_path), "1234567890")

        assert isinstance(repo, DuckDBRepository)
        repo.close()

    def test_legacy_modes_raise_error(self, tmp_path):
        """Teste que les modes legacy lèvent une erreur."""
        from src.data import RepositoryMode, get_repository

        db_path = tmp_path / "test.db"
        db_path.touch()

        # Les anciens modes doivent lever une ValueError
        for mode in [
            RepositoryMode.LEGACY,
            RepositoryMode.HYBRID,
            RepositoryMode.SHADOW,
            RepositoryMode.SHADOW_COMPARE,
        ]:
            with pytest.raises(ValueError, match="n'est plus supporté depuis v4"):
                get_repository(str(db_path), "1234567890", mode=mode)

    def test_repository_mode_values(self):
        """Teste les valeurs de l'enum RepositoryMode."""
        from src.data import RepositoryMode

        # Tous les modes existent encore pour compatibilité
        assert RepositoryMode.LEGACY.value == "legacy"
        assert RepositoryMode.HYBRID.value == "hybrid"
        assert RepositoryMode.SHADOW.value == "shadow"
        assert RepositoryMode.SHADOW_COMPARE.value == "compare"
        assert RepositoryMode.DUCKDB.value == "duckdb"


# Exécution des tests si lancé directement
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
