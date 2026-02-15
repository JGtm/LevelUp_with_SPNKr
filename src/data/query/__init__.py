"""
Module de requêtage analytique avec DuckDB.
(Analytical query module with DuckDB)

Ce module fournit une interface de haut niveau pour exécuter des requêtes
analytiques complexes sur les données hybrides (SQLite + Parquet).

HOW IT WORKS:
1. QueryEngine : Moteur principal qui gère les connexions DuckDB
2. AnalyticsQueries : Requêtes prédéfinies pour les analyses courantes
3. TrendAnalyzer : Calculs de tendances et évolutions temporelles

Usage:
    from src.data.query import QueryEngine, AnalyticsQueries
    
    engine = QueryEngine("data/warehouse")
    analytics = AnalyticsQueries(engine, xuid="1234567890")
    
    # Évolution du KDA sur les 30 derniers jours
    kda_trend = analytics.get_kda_trend(days=30)
    
    # Top médailles avec noms
    top_medals = analytics.get_top_medals_with_names(limit=10)
    
    # Performance par carte
    map_stats = analytics.get_performance_by_map()
"""

from src.data.query.engine import QueryEngine
from src.data.query.analytics import AnalyticsQueries
from src.data.query.trends import TrendAnalyzer

__all__ = [
    "QueryEngine",
    "AnalyticsQueries", 
    "TrendAnalyzer",
]
