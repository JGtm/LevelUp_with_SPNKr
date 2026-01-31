"""
Tests pour le module de requêtes analytiques.
(Tests for analytical query module)

Ces tests valident :
1. Le QueryEngine et ses méthodes
2. Les requêtes analytiques prédéfinies
3. L'analyse des tendances
4. Les exemples de requêtes complexes
"""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


class TestQueryEngine:
    """Tests du QueryEngine."""
    
    def test_engine_initialization(self, tmp_path):
        """Teste l'initialisation du moteur."""
        from src.data.query.engine import QueryEngine
        
        warehouse = tmp_path / "warehouse"
        warehouse.mkdir()
        
        engine = QueryEngine(warehouse)
        
        assert engine.warehouse_path == warehouse
        assert not engine.has_data("match_facts")
        
        engine.close()
    
    def test_parquet_glob_construction(self, tmp_path):
        """Teste la construction des patterns glob."""
        from src.data.query.engine import QueryEngine
        
        warehouse = tmp_path / "warehouse"
        warehouse.mkdir()
        
        engine = QueryEngine(warehouse)
        
        # Test avec tous les paramètres
        glob = engine.get_parquet_glob("match_facts", "123", 2025, 1)
        assert "player=123" in glob
        assert "year=2025" in glob
        assert "month=01" in glob
        
        # Test sans filtre joueur
        glob = engine.get_parquet_glob("match_facts")
        assert "player=*" in glob
        
        engine.close()
    
    def test_execute_simple_query(self, tmp_path):
        """Teste l'exécution d'une requête simple."""
        from src.data.query.engine import QueryEngine
        
        warehouse = tmp_path / "warehouse"
        warehouse.mkdir()
        
        engine = QueryEngine(warehouse)
        
        # Requête simple sans Parquet
        result = engine.execute("SELECT 1 + 1 as result")
        
        assert len(result) == 1
        assert result[0]["result"] == 2
        
        engine.close()
    
    def test_execute_with_polars_return(self, tmp_path):
        """Teste le retour en DataFrame Polars."""
        from src.data.query.engine import QueryEngine
        import polars as pl
        
        warehouse = tmp_path / "warehouse"
        warehouse.mkdir()
        
        engine = QueryEngine(warehouse)
        
        df = engine.execute(
            "SELECT 1 as a, 2 as b UNION ALL SELECT 3, 4",
            return_type="polars"
        )
        
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 2
        assert df["a"].to_list() == [1, 3]
        
        engine.close()
    
    def test_sqlite_attachment(self, tmp_path):
        """Teste l'attachement d'une base SQLite."""
        from src.data.query.engine import QueryEngine
        
        warehouse = tmp_path / "warehouse"
        warehouse.mkdir()
        
        # Créer une base SQLite avec des données
        metadata_db = warehouse / "metadata.db"
        con = sqlite3.connect(str(metadata_db))
        con.execute("CREATE TABLE players (xuid TEXT, gamertag TEXT)")
        con.execute("INSERT INTO players VALUES ('123', 'TestPlayer')")
        con.commit()
        con.close()
        
        engine = QueryEngine(warehouse)
        
        # Vérifier que la base est attachée
        assert engine._metadata_attached
        
        # Requête sur la base attachée
        result = engine.execute("SELECT * FROM meta.players")
        
        assert len(result) == 1
        assert result[0]["gamertag"] == "TestPlayer"
        
        engine.close()


class TestQueryEngineWithData:
    """Tests du QueryEngine avec données Parquet."""
    
    @pytest.fixture
    def engine_with_data(self, tmp_path):
        """Crée un engine avec des données de test."""
        from src.data.query.engine import QueryEngine
        from src.data.infrastructure.parquet.writer import ParquetWriter
        from src.data.domain.models.match import MatchFactInput, MatchFact
        
        warehouse = tmp_path / "warehouse"
        writer = ParquetWriter(warehouse)
        
        # Créer des données de test
        now = datetime.now(timezone.utc)
        facts = []
        
        for i in range(50):
            input_data = MatchFactInput(
                match_id=f"match-{i:03d}",
                xuid="1234567890",
                start_time=now - timedelta(hours=i),
                kills=10 + (i % 10),
                deaths=5 + (i % 5),
                assists=3 + (i % 3),
                kda=1.5 + (i % 10) * 0.1,
                accuracy=40.0 + (i % 20),
                outcome=(2 if i % 3 != 0 else 3),  # 2/3 victoires
                playlist_name=f"Playlist {i % 3}",
                map_name=f"Map {i % 5}",
            )
            facts.append(MatchFact.from_input(input_data))
        
        writer.write_match_facts(facts)
        
        engine = QueryEngine(warehouse)
        yield engine
        engine.close()
    
    def test_has_data(self, engine_with_data):
        """Teste la détection de données."""
        assert engine_with_data.has_data("match_facts", "1234567890")
        assert not engine_with_data.has_data("match_facts", "nonexistent")
        assert not engine_with_data.has_data("medals", "1234567890")
    
    def test_query_match_facts(self, engine_with_data):
        """Teste les requêtes sur match_facts."""
        results = engine_with_data.query_match_facts(
            "1234567890",
            select="match_id, kills, deaths",
            limit=10,
        )
        
        assert len(results) == 10
        assert "match_id" in results[0]
        assert "kills" in results[0]
    
    def test_query_with_filter(self, engine_with_data):
        """Teste les requêtes avec filtre."""
        results = engine_with_data.query_match_facts(
            "1234567890",
            select="match_id, outcome",
            where="outcome = 2",
        )
        
        # Toutes les lignes ont outcome = 2
        assert all(r["outcome"] == 2 for r in results)
    
    def test_query_with_order(self, engine_with_data):
        """Teste les requêtes avec tri."""
        results = engine_with_data.query_match_facts(
            "1234567890",
            select="match_id, kda",
            order_by="kda DESC",
            limit=5,
        )
        
        # Vérifier l'ordre décroissant
        kdas = [r["kda"] for r in results]
        assert kdas == sorted(kdas, reverse=True)
    
    def test_to_match_rows(self, engine_with_data):
        """Teste la conversion en MatchRow."""
        from src.models import MatchRow
        
        results = engine_with_data.query_match_facts(
            "1234567890",
            limit=5,
        )
        
        match_rows = engine_with_data.to_match_rows(results)
        
        assert len(match_rows) == 5
        assert all(isinstance(r, MatchRow) for r in match_rows)


class TestAnalyticsQueries:
    """Tests des requêtes analytiques."""
    
    @pytest.fixture
    def analytics(self, tmp_path):
        """Crée des AnalyticsQueries avec données de test."""
        from src.data.query.engine import QueryEngine
        from src.data.query.analytics import AnalyticsQueries
        from src.data.infrastructure.parquet.writer import ParquetWriter
        from src.data.domain.models.match import MatchFactInput, MatchFact
        
        warehouse = tmp_path / "warehouse"
        writer = ParquetWriter(warehouse)
        
        now = datetime.now(timezone.utc)
        facts = []
        
        for i in range(100):
            input_data = MatchFactInput(
                match_id=f"match-{i:03d}",
                xuid="1234567890",
                start_time=now - timedelta(hours=i),
                kills=10 + (i % 15),
                deaths=5 + (i % 8),
                assists=3 + (i % 5),
                kda=1.2 + (i % 12) * 0.15,
                accuracy=35.0 + (i % 25),
                outcome=(2 if i % 3 != 0 else 3),
                playlist_name=f"Playlist {i % 4}",
                map_name=f"Map {i % 6}",
            )
            facts.append(MatchFact.from_input(input_data))
        
        writer.write_match_facts(facts)
        
        engine = QueryEngine(warehouse)
        analytics = AnalyticsQueries(engine, "1234567890")
        yield analytics
        engine.close()
    
    def test_get_global_stats(self, analytics):
        """Teste les statistiques globales."""
        stats = analytics.get_global_stats()
        
        assert stats.total_matches == 100
        assert stats.total_kills > 0
        assert stats.total_deaths > 0
        assert 0 <= stats.win_rate <= 1
        assert stats.wins + stats.losses <= stats.total_matches
    
    def test_get_performance_by_map(self, analytics):
        """Teste les performances par carte."""
        map_stats = analytics.get_performance_by_map(min_matches=5)
        
        assert len(map_stats) > 0
        
        for m in map_stats:
            assert "map_name" in m
            assert "matches" in m
            assert m["matches"] >= 5
            assert "win_rate" in m
    
    def test_get_performance_by_playlist(self, analytics):
        """Teste les performances par playlist."""
        playlist_stats = analytics.get_performance_by_playlist(min_matches=5)
        
        assert len(playlist_stats) > 0
        assert all(p["matches"] >= 5 for p in playlist_stats)
    
    def test_get_recent_matches(self, analytics):
        """Teste la récupération des matchs récents."""
        recent = analytics.get_recent_matches(limit=20)
        
        assert len(recent) == 20
        
        # Vérifier l'ordre décroissant
        times = [r["start_time"] for r in recent]
        assert times == sorted(times, reverse=True)
    
    def test_get_best_matches(self, analytics):
        """Teste les meilleurs matchs."""
        best = analytics.get_best_matches(metric="kda", limit=5)
        
        assert len(best) == 5
        
        # Vérifier l'ordre décroissant par KDA
        kdas = [b["kda"] for b in best]
        assert kdas == sorted(kdas, reverse=True)
    
    def test_get_hourly_performance(self, analytics):
        """Teste les performances par heure."""
        hourly = analytics.get_hourly_performance()
        
        assert len(hourly) > 0
        assert all(0 <= h["hour"] <= 23 for h in hourly)


class TestTrendAnalyzer:
    """Tests de l'analyseur de tendances."""
    
    @pytest.fixture
    def trends(self, tmp_path):
        """Crée un TrendAnalyzer avec données de test."""
        from src.data.query.engine import QueryEngine
        from src.data.query.trends import TrendAnalyzer
        from src.data.infrastructure.parquet.writer import ParquetWriter
        from src.data.domain.models.match import MatchFactInput, MatchFact
        
        warehouse = tmp_path / "warehouse"
        writer = ParquetWriter(warehouse)
        
        now = datetime.now(timezone.utc)
        facts = []
        
        # Créer des données avec une tendance visible
        for i in range(100):
            # KDA qui augmente avec le temps
            base_kda = 1.0 + (i / 100) * 0.5
            
            input_data = MatchFactInput(
                match_id=f"match-{i:03d}",
                xuid="1234567890",
                start_time=now - timedelta(hours=100 - i),
                kills=10 + (i % 10),
                deaths=8,
                assists=3,
                kda=base_kda + (i % 5) * 0.1,
                accuracy=40.0 + (i % 20),
                outcome=(2 if i % 2 == 0 else 3),
            )
            facts.append(MatchFact.from_input(input_data))
        
        writer.write_match_facts(facts)
        
        engine = QueryEngine(warehouse)
        trends = TrendAnalyzer(engine, "1234567890")
        yield trends
        engine.close()
    
    def test_get_rolling_kda(self, trends):
        """Teste le calcul du KDA avec moyenne mobile."""
        rolling = trends.get_rolling_kda(window_size=10, last_n=50)
        
        assert len(rolling) == 50
        assert "rolling_avg_kda" in rolling[0]
        assert "rolling_avg_kd" in rolling[0]
    
    def test_get_rolling_win_rate(self, trends):
        """Teste le calcul du win rate avec moyenne mobile."""
        rolling = trends.get_rolling_win_rate(window_size=10, last_n=50)
        
        assert len(rolling) > 0
        assert "rolling_win_rate" in rolling[0]
        assert all(0 <= r["rolling_win_rate"] <= 1 for r in rolling)
    
    def test_get_daily_evolution(self, trends):
        """Teste l'évolution quotidienne."""
        daily = trends.get_daily_evolution(last_days=7)
        
        # Au moins quelques jours de données
        assert len(daily) > 0
        assert "date" in daily[0]
        assert "avg_kda" in daily[0]
    
    def test_compare_periods(self, trends):
        """Teste la comparaison de périodes."""
        from src.data.query.trends import PeriodComparison
        
        comparison = trends.compare_periods("kda", period_days=3)
        
        assert isinstance(comparison, PeriodComparison)
        assert comparison.trend in ("up", "down", "stable")
    
    def test_performance_trend_summary(self, trends):
        """Teste le résumé des tendances."""
        summary = trends.get_performance_trend_summary()
        
        assert "kda" in summary
        assert "accuracy" in summary
        assert "win_rate" in summary
        assert "trend" in summary["kda"]


# Exécution des tests si lancé directement
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
