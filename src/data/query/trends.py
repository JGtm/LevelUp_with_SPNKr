"""
Analyse des tendances et évolutions temporelles.
(Trend and temporal evolution analysis)

HOW IT WORKS:
Ce module fournit des fonctions pour analyser les évolutions dans le temps :
- Moyennes mobiles (rolling averages)
- Tendances par période (jour, semaine, mois)
- Comparaisons de périodes
- Détection de progression ou régression

Toutes les requêtes utilisent les fonctions de fenêtrage (window functions)
de DuckDB pour des calculs efficaces sur de grands volumes.

Exemple:
    engine = QueryEngine("data/warehouse")
    trends = TrendAnalyzer(engine, xuid="1234567890")
    
    # KDA sur les 500 derniers matchs avec moyenne mobile sur 20 matchs
    kda_trend = trends.get_rolling_kda(window_size=20, last_n=500)
    
    # Évolution mensuelle
    monthly = trends.get_monthly_evolution()
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.data.query.engine import QueryEngine


@dataclass
class TrendPoint:
    """
    Point de données pour une tendance.
    (Data point for a trend)
    """
    timestamp: datetime
    value: float
    rolling_avg: float | None = None
    match_count: int = 1


@dataclass
class PeriodComparison:
    """
    Comparaison entre deux périodes.
    (Comparison between two periods)
    """
    current_value: float
    previous_value: float
    change: float
    change_percent: float
    trend: str  # "up", "down", "stable"


class TrendAnalyzer:
    """
    Analyseur de tendances temporelles.
    (Temporal trend analyzer)
    
    Fournit des méthodes pour calculer des évolutions
    et des moyennes mobiles sur les statistiques de jeu.
    """
    
    def __init__(self, engine: QueryEngine, xuid: str) -> None:
        """
        Initialise l'analyseur de tendances.
        (Initialize trend analyzer)
        
        Args:
            engine: Instance de QueryEngine
            xuid: XUID du joueur à analyser
        """
        self.engine = engine
        self.xuid = xuid
    
    def get_rolling_kda(
        self,
        *,
        window_size: int = 20,
        last_n: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Calcule l'évolution du KDA avec moyenne mobile.
        (Calculate KDA evolution with rolling average)
        
        C'est l'exemple demandé : "Évolution du ratio K/D moyen 
        sur les 500 derniers matchs".
        
        Args:
            window_size: Taille de la fenêtre pour la moyenne mobile
            last_n: Nombre de matchs à considérer
            
        Returns:
            Liste de dicts avec match_id, start_time, kda, rolling_avg_kda
        """
        sql = f"""
            WITH ranked_matches AS (
                SELECT 
                    match_id,
                    start_time,
                    kda,
                    kills,
                    deaths,
                    ROW_NUMBER() OVER (ORDER BY start_time DESC) as rn
                FROM {{table}}
            ),
            last_n_matches AS (
                SELECT * FROM ranked_matches WHERE rn <= {last_n}
            )
            SELECT 
                match_id,
                start_time,
                kda,
                kills,
                deaths,
                AVG(kda) OVER (
                    ORDER BY start_time 
                    ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
                ) as rolling_avg_kda,
                -- Ratio K/D simple (sans assists)
                CASE WHEN deaths > 0 THEN kills * 1.0 / deaths ELSE kills END as kd_ratio,
                AVG(CASE WHEN deaths > 0 THEN kills * 1.0 / deaths ELSE kills END) OVER (
                    ORDER BY start_time 
                    ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
                ) as rolling_avg_kd
            FROM last_n_matches
            ORDER BY start_time ASC
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def get_rolling_accuracy(
        self,
        *,
        window_size: int = 20,
        last_n: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Calcule l'évolution de la précision avec moyenne mobile.
        (Calculate accuracy evolution with rolling average)
        """
        sql = f"""
            WITH ranked_matches AS (
                SELECT 
                    match_id,
                    start_time,
                    accuracy,
                    ROW_NUMBER() OVER (ORDER BY start_time DESC) as rn
                FROM {{table}}
                WHERE accuracy IS NOT NULL
            ),
            last_n_matches AS (
                SELECT * FROM ranked_matches WHERE rn <= {last_n}
            )
            SELECT 
                match_id,
                start_time,
                accuracy,
                AVG(accuracy) OVER (
                    ORDER BY start_time 
                    ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
                ) as rolling_avg_accuracy
            FROM last_n_matches
            ORDER BY start_time ASC
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def get_rolling_win_rate(
        self,
        *,
        window_size: int = 20,
        last_n: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Calcule l'évolution du taux de victoire avec moyenne mobile.
        (Calculate win rate evolution with rolling average)
        """
        sql = f"""
            WITH ranked_matches AS (
                SELECT 
                    match_id,
                    start_time,
                    outcome,
                    CASE WHEN outcome = 2 THEN 1 ELSE 0 END as is_win,
                    ROW_NUMBER() OVER (ORDER BY start_time DESC) as rn
                FROM {{table}}
                WHERE outcome IN (2, 3)  -- Seulement victoires et défaites
            ),
            last_n_matches AS (
                SELECT * FROM ranked_matches WHERE rn <= {last_n}
            )
            SELECT 
                match_id,
                start_time,
                outcome,
                is_win,
                AVG(is_win) OVER (
                    ORDER BY start_time 
                    ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
                ) as rolling_win_rate
            FROM last_n_matches
            ORDER BY start_time ASC
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def get_daily_evolution(
        self,
        *,
        last_days: int = 30,
    ) -> list[dict[str, Any]]:
        """
        Calcule les statistiques agrégées par jour.
        (Calculate daily aggregated statistics)
        
        Args:
            last_days: Nombre de jours à considérer
            
        Returns:
            Liste de dicts avec date, matches, avg_kda, win_rate, etc.
        """
        cutoff = datetime.now() - timedelta(days=last_days)
        
        sql = f"""
            SELECT 
                DATE_TRUNC('day', start_time) as date,
                COUNT(*) as matches,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(assists) as total_assists,
                AVG(kda) as avg_kda,
                AVG(accuracy) as avg_accuracy,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 3 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) * 1.0 / 
                    NULLIF(SUM(CASE WHEN outcome IN (2, 3) THEN 1 ELSE 0 END), 0) as win_rate
            FROM {{table}}
            WHERE start_time >= '{cutoff.isoformat()}'
            GROUP BY DATE_TRUNC('day', start_time)
            ORDER BY date ASC
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def get_weekly_evolution(
        self,
        *,
        last_weeks: int = 12,
    ) -> list[dict[str, Any]]:
        """
        Calcule les statistiques agrégées par semaine.
        (Calculate weekly aggregated statistics)
        """
        cutoff = datetime.now() - timedelta(weeks=last_weeks)
        
        sql = f"""
            SELECT 
                DATE_TRUNC('week', start_time) as week_start,
                COUNT(*) as matches,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                AVG(kda) as avg_kda,
                AVG(accuracy) as avg_accuracy,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 3 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) * 1.0 / 
                    NULLIF(SUM(CASE WHEN outcome IN (2, 3) THEN 1 ELSE 0 END), 0) as win_rate
            FROM {{table}}
            WHERE start_time >= '{cutoff.isoformat()}'
            GROUP BY DATE_TRUNC('week', start_time)
            ORDER BY week_start ASC
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def get_monthly_evolution(
        self,
        *,
        last_months: int = 12,
    ) -> list[dict[str, Any]]:
        """
        Calcule les statistiques agrégées par mois.
        (Calculate monthly aggregated statistics)
        """
        cutoff = datetime.now() - timedelta(days=last_months * 30)
        
        sql = f"""
            SELECT 
                DATE_TRUNC('month', start_time) as month_start,
                COUNT(*) as matches,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(assists) as total_assists,
                SUM(time_played_seconds) / 3600.0 as hours_played,
                AVG(kda) as avg_kda,
                AVG(accuracy) as avg_accuracy,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 3 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) * 1.0 / 
                    NULLIF(SUM(CASE WHEN outcome IN (2, 3) THEN 1 ELSE 0 END), 0) as win_rate
            FROM {{table}}
            WHERE start_time >= '{cutoff.isoformat()}'
            GROUP BY DATE_TRUNC('month', start_time)
            ORDER BY month_start ASC
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def compare_periods(
        self,
        metric: str = "kda",
        period_days: int = 7,
    ) -> PeriodComparison:
        """
        Compare les performances entre deux périodes consécutives.
        (Compare performance between two consecutive periods)
        
        Args:
            metric: Métrique à comparer (kda, accuracy, win_rate)
            period_days: Durée de chaque période en jours
            
        Returns:
            PeriodComparison avec les valeurs et le changement
        """
        now = datetime.now()
        current_start = now - timedelta(days=period_days)
        previous_start = current_start - timedelta(days=period_days)
        
        if metric == "win_rate":
            agg = "SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*), 0)"
        else:
            agg = f"AVG({metric})"
        
        sql = f"""
            SELECT 
                CASE 
                    WHEN start_time >= '{current_start.isoformat()}' THEN 'current'
                    ELSE 'previous'
                END as period,
                {agg} as value,
                COUNT(*) as matches
            FROM {{table}}
            WHERE start_time >= '{previous_start.isoformat()}'
            GROUP BY period
        """
        
        results = self.engine.execute_with_parquet(sql, "match_facts", self.xuid)
        
        current_value = 0.0
        previous_value = 0.0
        
        for r in results:
            if r["period"] == "current":
                current_value = r["value"] or 0.0
            else:
                previous_value = r["value"] or 0.0
        
        change = current_value - previous_value
        change_percent = (change / previous_value * 100) if previous_value != 0 else 0.0
        
        if abs(change_percent) < 2:
            trend = "stable"
        elif change > 0:
            trend = "up"
        else:
            trend = "down"
        
        return PeriodComparison(
            current_value=current_value,
            previous_value=previous_value,
            change=change,
            change_percent=change_percent,
            trend=trend,
        )
    
    def get_performance_trend_summary(self) -> dict[str, Any]:
        """
        Génère un résumé des tendances de performance.
        (Generate performance trend summary)
        
        Calcule les tendances pour plusieurs métriques clés
        et identifie les points forts et faibles.
        
        Returns:
            Dict avec les tendances pour KDA, accuracy, win_rate
        """
        kda_trend = self.compare_periods("kda", 7)
        accuracy_trend = self.compare_periods("accuracy", 7)
        win_rate_trend = self.compare_periods("win_rate", 7)
        
        # Calculer les moyennes récentes
        recent_stats = self.engine.execute_with_parquet(
            """
            SELECT 
                AVG(kda) as recent_kda,
                AVG(accuracy) as recent_accuracy,
                SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0 END) / NULLIF(COUNT(*), 0) as recent_win_rate,
                COUNT(*) as match_count
            FROM {table}
            WHERE start_time >= NOW() - INTERVAL '7 days'
            """,
            "match_facts",
            self.xuid,
        )
        
        recent = recent_stats[0] if recent_stats else {}
        
        return {
            "kda": {
                "current": kda_trend.current_value,
                "previous": kda_trend.previous_value,
                "change_percent": kda_trend.change_percent,
                "trend": kda_trend.trend,
            },
            "accuracy": {
                "current": accuracy_trend.current_value,
                "previous": accuracy_trend.previous_value,
                "change_percent": accuracy_trend.change_percent,
                "trend": accuracy_trend.trend,
            },
            "win_rate": {
                "current": win_rate_trend.current_value,
                "previous": win_rate_trend.previous_value,
                "change_percent": win_rate_trend.change_percent,
                "trend": win_rate_trend.trend,
            },
            "recent_matches": recent.get("match_count", 0),
            "period_days": 7,
        }
    
    def get_mmr_evolution(
        self,
        *,
        last_n: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Calcule l'évolution du MMR (si disponible).
        (Calculate MMR evolution if available)
        """
        sql = f"""
            WITH ranked AS (
                SELECT 
                    match_id,
                    start_time,
                    team_mmr,
                    enemy_mmr,
                    outcome,
                    ROW_NUMBER() OVER (ORDER BY start_time DESC) as rn
                FROM {{table}}
                WHERE team_mmr IS NOT NULL
            )
            SELECT 
                match_id,
                start_time,
                team_mmr,
                enemy_mmr,
                enemy_mmr - team_mmr as mmr_diff,
                outcome
            FROM ranked
            WHERE rn <= {last_n}
            ORDER BY start_time ASC
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def detect_improvement_areas(self) -> list[dict[str, Any]]:
        """
        Identifie les domaines nécessitant une amélioration.
        (Identify areas needing improvement)
        
        Compare les performances actuelles aux performances historiques
        et identifie les régressions ou stagnations.
        
        Returns:
            Liste de domaines avec des suggestions
        """
        areas = []
        
        # Comparer KDA
        kda_comparison = self.compare_periods("kda", 14)
        if kda_comparison.trend == "down" and kda_comparison.change_percent < -5:
            areas.append({
                "area": "KDA",
                "status": "regression",
                "change_percent": kda_comparison.change_percent,
                "suggestion": "Votre KDA a baissé. Essayez de jouer plus prudemment.",
            })
        
        # Comparer accuracy
        acc_comparison = self.compare_periods("accuracy", 14)
        if acc_comparison.trend == "down" and acc_comparison.change_percent < -3:
            areas.append({
                "area": "Précision",
                "status": "regression",
                "change_percent": acc_comparison.change_percent,
                "suggestion": "Votre précision a baissé. Prenez votre temps pour viser.",
            })
        
        # Comparer win rate
        wr_comparison = self.compare_periods("win_rate", 14)
        if wr_comparison.trend == "down" and wr_comparison.change_percent < -5:
            areas.append({
                "area": "Taux de victoire",
                "status": "regression",
                "change_percent": wr_comparison.change_percent,
                "suggestion": "Votre taux de victoire a baissé. Essayez de jouer avec des amis.",
            })
        
        # Si tout est stable ou en hausse
        if not areas:
            areas.append({
                "area": "Global",
                "status": "stable",
                "suggestion": "Vos performances sont stables. Continuez ainsi !",
            })
        
        return areas
