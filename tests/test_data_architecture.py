"""
Tests pour l'architecture de données hybride.
(Tests for hybrid data architecture)

Ces tests valident :
1. Les modèles Pydantic (validation des données)
2. Le pattern Repository (interface commune)
3. L'écriture/lecture Parquet
4. Le Shadow Module (migration)
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

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
        from src.data.domain.models.match import MatchFactInput, MatchFact
        
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
    
    def test_get_repository_legacy(self, tmp_path):
        """Teste la création d'un LegacyRepository."""
        from src.data import get_repository, RepositoryMode
        from src.data.repositories.legacy import LegacyRepository
        
        # Créer une DB SQLite vide
        db_path = tmp_path / "test.db"
        db_path.touch()
        
        repo = get_repository(str(db_path), "1234567890", mode=RepositoryMode.LEGACY)
        
        assert isinstance(repo, LegacyRepository)
        assert repo.xuid == "1234567890"
    
    def test_get_repository_shadow(self, tmp_path):
        """Teste la création d'un ShadowRepository."""
        from src.data import get_repository, RepositoryMode
        from src.data.repositories.shadow import ShadowRepository
        
        db_path = tmp_path / "test.db"
        db_path.touch()
        
        repo = get_repository(str(db_path), "1234567890", mode=RepositoryMode.SHADOW)
        
        assert isinstance(repo, ShadowRepository)
        assert repo.xuid == "1234567890"
    
    def test_get_repository_mode_from_string(self, tmp_path):
        """Teste la création avec un mode en string."""
        from src.data import get_repository
        from src.data.repositories.legacy import LegacyRepository
        
        db_path = tmp_path / "test.db"
        db_path.touch()
        
        repo = get_repository(str(db_path), "1234567890", mode="legacy")
        
        assert isinstance(repo, LegacyRepository)


class TestParquetWriter:
    """Tests de l'écriture Parquet."""
    
    def test_write_match_facts(self, tmp_path):
        """Teste l'écriture de faits de match en Parquet."""
        from src.data.infrastructure.parquet.writer import ParquetWriter
        from src.data.domain.models.match import MatchFactInput, MatchFact
        
        warehouse_path = tmp_path / "warehouse"
        writer = ParquetWriter(warehouse_path)
        
        # Créer des faits de test
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        facts = [
            MatchFact.from_input(MatchFactInput(
                match_id=f"match-{i}",
                xuid="1234567890",
                start_time=now,
                kills=10 + i,
                deaths=5,
            ))
            for i in range(5)
        ]
        
        # Écrire en Parquet
        rows_written = writer.write_match_facts(facts)
        
        assert rows_written == 5
        
        # Vérifier que les fichiers existent
        parquet_files = list(warehouse_path.glob("match_facts/**/*.parquet"))
        assert len(parquet_files) == 1
    
    def test_write_stats(self, tmp_path):
        """Teste les statistiques du writer."""
        from src.data.infrastructure.parquet.writer import ParquetWriter
        
        warehouse_path = tmp_path / "warehouse"
        writer = ParquetWriter(warehouse_path)
        
        stats = writer.get_stats("match_facts")
        
        # Pas de données
        assert stats["exists"] is False
        assert stats["files"] == 0


class TestParquetReader:
    """Tests de la lecture Parquet."""
    
    def test_read_empty_warehouse(self, tmp_path):
        """Teste la lecture d'un warehouse vide."""
        from src.data.infrastructure.parquet.reader import ParquetReader
        
        warehouse_path = tmp_path / "warehouse"
        warehouse_path.mkdir()
        
        reader = ParquetReader(warehouse_path)
        
        assert not reader.has_data("1234567890")
        assert reader.count_rows("1234567890") == 0
    
    def test_read_match_facts_roundtrip(self, tmp_path):
        """Teste l'écriture puis lecture de faits."""
        from src.data.infrastructure.parquet.writer import ParquetWriter
        from src.data.infrastructure.parquet.reader import ParquetReader
        from src.data.domain.models.match import MatchFactInput, MatchFact
        
        warehouse_path = tmp_path / "warehouse"
        writer = ParquetWriter(warehouse_path)
        reader = ParquetReader(warehouse_path)
        
        # Écrire des données
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        facts = [
            MatchFact.from_input(MatchFactInput(
                match_id=f"match-{i}",
                xuid="1234567890",
                start_time=now,
                kills=10 + i,
                deaths=5,
            ))
            for i in range(3)
        ]
        writer.write_match_facts(facts)
        
        # Lire les données
        assert reader.has_data("1234567890")
        assert reader.count_rows("1234567890") == 3
        
        df = reader.read_match_facts("1234567890")
        assert len(df) == 3


class TestShadowRepository:
    """Tests du ShadowRepository."""
    
    def test_shadow_mode_values(self):
        """Teste les valeurs du ShadowMode."""
        from src.data.repositories.shadow import ShadowMode
        
        assert ShadowMode.SHADOW_READ.value == "shadow_read"
        assert ShadowMode.SHADOW_COMPARE.value == "shadow_compare"
        assert ShadowMode.HYBRID_FIRST.value == "hybrid_first"
    
    def test_shadow_storage_info(self, tmp_path):
        """Teste les informations de stockage du Shadow."""
        from src.data.repositories.shadow import ShadowRepository, ShadowMode
        
        # Créer une DB SQLite minimale
        import sqlite3
        db_path = tmp_path / "test.db"
        con = sqlite3.connect(str(db_path))
        con.execute("CREATE TABLE MatchStats (MatchId TEXT, ResponseBody TEXT)")
        con.close()
        
        shadow = ShadowRepository(
            str(db_path),
            "1234567890",
            warehouse_path=tmp_path / "warehouse",
            mode=ShadowMode.SHADOW_READ,
        )
        
        info = shadow.get_storage_info()
        
        assert info["type"] == "shadow"
        assert info["mode"] == "shadow_read"
        assert "legacy" in info
        
        shadow.close()


# Exécution des tests si lancé directement
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
