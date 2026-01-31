"""
Requêtes analytiques prédéfinies.
(Predefined analytical queries)

HOW IT WORKS:
Cette classe fournit des méthodes de haut niveau pour les analyses courantes :
- Statistiques agrégées (K/D/A, win rate, etc.)
- Performance par carte/playlist/mode
- Top médailles avec noms traduits
- Analyses de coéquipiers

Toutes les requêtes utilisent DuckDB pour des performances optimales,
avec jointures automatiques entre Parquet (faits) et SQLite (métadonnées).

Exemple:
    engine = QueryEngine("data/warehouse")
    analytics = AnalyticsQueries(engine, xuid="1234567890")
    
    # Stats globales
    stats = analytics.get_global_stats()
    print(f"KDA moyen: {stats['avg_kda']:.2f}")
    
    # Performance par carte
    map_stats = analytics.get_performance_by_map()
    for m in map_stats:
        print(f"{m['map_name']}: {m['win_rate']:.1%}")
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.data.query.engine import QueryEngine


@dataclass
class GlobalStats:
    """
    Statistiques globales agrégées.
    (Aggregated global statistics)
    """
    total_matches: int
    total_kills: int
    total_deaths: int
    total_assists: int
    total_time_hours: float
    avg_kda: float
    avg_accuracy: float | None
    win_rate: float
    loss_rate: float
    wins: int
    losses: int


class AnalyticsQueries:
    """
    Requêtes analytiques prédéfinies.
    (Predefined analytical queries)
    
    Fournit des méthodes de haut niveau pour les analyses courantes.
    """
    
    def __init__(self, engine: QueryEngine, xuid: str) -> None:
        """
        Initialise les requêtes analytiques.
        (Initialize analytical queries)
        
        Args:
            engine: Instance de QueryEngine
            xuid: XUID du joueur à analyser
        """
        self.engine = engine
        self.xuid = xuid
    
    def get_global_stats(self) -> GlobalStats:
        """
        Calcule les statistiques globales du joueur.
        (Calculate global player statistics)
        
        Returns:
            GlobalStats avec toutes les métriques agrégées
        """
        sql = """
            SELECT 
                COUNT(*) as total_matches,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(assists) as total_assists,
                SUM(time_played_seconds) / 3600.0 as total_time_hours,
                AVG(kda) as avg_kda,
                AVG(accuracy) as avg_accuracy,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 3 THEN 1 ELSE 0 END) as losses
            FROM {table}
        """
        
        results = self.engine.execute_with_parquet(sql, "match_facts", self.xuid)
        
        if not results:
            return GlobalStats(
                total_matches=0, total_kills=0, total_deaths=0, total_assists=0,
                total_time_hours=0.0, avg_kda=0.0, avg_accuracy=None,
                win_rate=0.0, loss_rate=0.0, wins=0, losses=0,
            )
        
        r = results[0]
        total = r["total_matches"] or 0
        wins = r["wins"] or 0
        losses = r["losses"] or 0
        
        return GlobalStats(
            total_matches=total,
            total_kills=r["total_kills"] or 0,
            total_deaths=r["total_deaths"] or 0,
            total_assists=r["total_assists"] or 0,
            total_time_hours=r["total_time_hours"] or 0.0,
            avg_kda=r["avg_kda"] or 0.0,
            avg_accuracy=r["avg_accuracy"],
            win_rate=wins / total if total > 0 else 0.0,
            loss_rate=losses / total if total > 0 else 0.0,
            wins=wins,
            losses=losses,
        )
    
    def get_performance_by_map(
        self,
        *,
        min_matches: int = 3,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Calcule les performances par carte.
        (Calculate performance by map)
        
        Args:
            min_matches: Nombre minimum de matchs pour inclure une carte
            limit: Nombre maximum de cartes à retourner
            
        Returns:
            Liste de dicts avec map_name, matches, avg_kda, win_rate, etc.
        """
        sql = f"""
            SELECT 
                COALESCE(map_name, map_id, 'Unknown') as map_name,
                COUNT(*) as matches,
                AVG(kda) as avg_kda,
                AVG(accuracy) as avg_accuracy,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 3 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate
            FROM {{table}}
            GROUP BY COALESCE(map_name, map_id, 'Unknown')
            HAVING COUNT(*) >= {min_matches}
            ORDER BY matches DESC
            LIMIT {limit}
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def get_performance_by_playlist(
        self,
        *,
        min_matches: int = 5,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Calcule les performances par playlist.
        (Calculate performance by playlist)
        """
        sql = f"""
            SELECT 
                COALESCE(playlist_name, playlist_id, 'Unknown') as playlist_name,
                COUNT(*) as matches,
                AVG(kda) as avg_kda,
                AVG(accuracy) as avg_accuracy,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 3 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate
            FROM {{table}}
            GROUP BY COALESCE(playlist_name, playlist_id, 'Unknown')
            HAVING COUNT(*) >= {min_matches}
            ORDER BY matches DESC
            LIMIT {limit}
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def get_top_medals(
        self,
        *,
        limit: int = 25,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retourne les médailles les plus fréquentes.
        (Return most frequent medals)
        
        Args:
            limit: Nombre de médailles à retourner
            start_date: Date de début optionnelle
            end_date: Date de fin optionnelle
            
        Returns:
            Liste de dicts avec medal_name_id, total_count
        """
        where_clause = ""
        if start_date or end_date:
            conditions = []
            if start_date:
                conditions.append(f"start_time >= '{start_date.isoformat()}'")
            if end_date:
                conditions.append(f"start_time <= '{end_date.isoformat()}'")
            where_clause = "WHERE " + " AND ".join(conditions)
        
        sql = f"""
            SELECT 
                medal_name_id,
                SUM(count) as total_count
            FROM {{table}}
            {where_clause}
            GROUP BY medal_name_id
            ORDER BY total_count DESC
            LIMIT {limit}
        """
        
        if not self.engine.has_data("medals", self.xuid):
            return []
        
        return self.engine.execute_with_parquet(sql, "medals", self.xuid)  # type: ignore
    
    def get_top_medals_with_names(
        self,
        *,
        limit: int = 25,
        language: str = "fr",
    ) -> list[dict[str, Any]]:
        """
        Retourne les médailles les plus fréquentes avec leurs noms.
        (Return most frequent medals with names)
        
        Utilise une jointure avec SQLite pour les noms traduits.
        
        Args:
            limit: Nombre de médailles à retourner
            language: Langue pour les noms ("fr" ou "en")
            
        Returns:
            Liste de dicts avec medal_name_id, name, total_count
        """
        name_col = "name_fr" if language == "fr" else "name_en"
        
        sql = f"""
            SELECT 
                m.medal_name_id,
                COALESCE(d.{name_col}, d.name_en, CAST(m.medal_name_id AS VARCHAR)) as name,
                d.difficulty,
                d.sprite_path,
                SUM(m.count) as total_count
            FROM {{medals}} m
            LEFT JOIN {{medal_definitions}} d ON m.medal_name_id = d.name_id
            GROUP BY m.medal_name_id, d.{name_col}, d.name_en, d.difficulty, d.sprite_path
            ORDER BY total_count DESC
            LIMIT {limit}
        """
        
        return self.engine.query_with_metadata_join(sql, self.xuid)
    
    def get_recent_matches(
        self,
        *,
        limit: int = 50,
        include_stats: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Retourne les matchs récents.
        (Return recent matches)
        
        Args:
            limit: Nombre de matchs à retourner
            include_stats: Inclure les stats détaillées
            
        Returns:
            Liste de matchs triés par date décroissante
        """
        if include_stats:
            select = """
                match_id, start_time, 
                COALESCE(map_name, map_id) as map_name,
                COALESCE(playlist_name, playlist_id) as playlist_name,
                outcome, kills, deaths, assists, kda, accuracy,
                my_team_score, enemy_team_score
            """
        else:
            select = "match_id, start_time, outcome"
        
        return self.engine.query_match_facts(
            self.xuid,
            select=select,
            order_by="start_time DESC",
            limit=limit,
        )
    
    def get_matches_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        Retourne les matchs dans une plage de dates.
        (Return matches in a date range)
        """
        sql = f"""
            SELECT *
            FROM {{table}}
            WHERE start_time >= '{start_date.isoformat()}'
              AND start_time <= '{end_date.isoformat()}'
            ORDER BY start_time ASC
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def get_win_streak_stats(self) -> dict[str, Any]:
        """
        Calcule les statistiques de séries de victoires/défaites.
        (Calculate win/loss streak statistics)
        
        Returns:
            Dict avec current_streak, max_win_streak, max_loss_streak
        """
        sql = """
            WITH ordered_matches AS (
                SELECT 
                    match_id,
                    start_time,
                    outcome,
                    ROW_NUMBER() OVER (ORDER BY start_time) as rn
                FROM {table}
                WHERE outcome IN (2, 3)  -- Victoires et défaites uniquement
            ),
            streaks AS (
                SELECT 
                    *,
                    rn - ROW_NUMBER() OVER (PARTITION BY outcome ORDER BY start_time) as streak_group
                FROM ordered_matches
            ),
            streak_lengths AS (
                SELECT 
                    outcome,
                    streak_group,
                    COUNT(*) as streak_length,
                    MAX(start_time) as last_match_time
                FROM streaks
                GROUP BY outcome, streak_group
            )
            SELECT 
                MAX(CASE WHEN outcome = 2 THEN streak_length ELSE 0 END) as max_win_streak,
                MAX(CASE WHEN outcome = 3 THEN streak_length ELSE 0 END) as max_loss_streak
            FROM streak_lengths
        """
        
        results = self.engine.execute_with_parquet(sql, "match_facts", self.xuid)
        
        if not results:
            return {"max_win_streak": 0, "max_loss_streak": 0, "current_streak": 0}
        
        r = results[0]
        
        # Calculer la série actuelle
        recent = self.get_recent_matches(limit=20)
        current_streak = 0
        current_type = None
        
        for match in recent:
            outcome = match.get("outcome")
            if outcome not in (2, 3):
                continue
            
            if current_type is None:
                current_type = outcome
                current_streak = 1
            elif outcome == current_type:
                current_streak += 1
            else:
                break
        
        return {
            "max_win_streak": r["max_win_streak"] or 0,
            "max_loss_streak": r["max_loss_streak"] or 0,
            "current_streak": current_streak if current_type == 2 else -current_streak,
        }
    
    def get_best_matches(
        self,
        *,
        metric: str = "kda",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Retourne les meilleurs matchs selon une métrique.
        (Return best matches by a metric)
        
        Args:
            metric: Métrique à utiliser (kda, kills, accuracy, etc.)
            limit: Nombre de matchs à retourner
        """
        valid_metrics = {"kda", "kills", "accuracy", "max_killing_spree", "headshot_kills"}
        if metric not in valid_metrics:
            metric = "kda"
        
        # Pour accuracy, ignorer les valeurs NULL
        where = "accuracy IS NOT NULL" if metric == "accuracy" else None
        
        return self.engine.query_match_facts(
            self.xuid,
            select=f"""
                match_id, start_time,
                COALESCE(map_name, map_id) as map_name,
                COALESCE(playlist_name, playlist_id) as playlist_name,
                outcome, kills, deaths, assists, kda, accuracy,
                max_killing_spree, headshot_kills
            """,
            where=where,
            order_by=f"{metric} DESC",
            limit=limit,
        )
    
    def get_hourly_performance(self) -> list[dict[str, Any]]:
        """
        Calcule les performances par heure de la journée.
        (Calculate performance by hour of day)
        
        Utile pour identifier les meilleures heures pour jouer.
        """
        sql = """
            SELECT 
                EXTRACT(HOUR FROM start_time) as hour,
                COUNT(*) as matches,
                AVG(kda) as avg_kda,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate
            FROM {table}
            GROUP BY EXTRACT(HOUR FROM start_time)
            ORDER BY hour
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def get_weekday_performance(self) -> list[dict[str, Any]]:
        """
        Calcule les performances par jour de la semaine.
        (Calculate performance by day of week)
        """
        sql = """
            SELECT 
                EXTRACT(DOW FROM start_time) as day_of_week,
                CASE EXTRACT(DOW FROM start_time)
                    WHEN 0 THEN 'Dimanche'
                    WHEN 1 THEN 'Lundi'
                    WHEN 2 THEN 'Mardi'
                    WHEN 3 THEN 'Mercredi'
                    WHEN 4 THEN 'Jeudi'
                    WHEN 5 THEN 'Vendredi'
                    WHEN 6 THEN 'Samedi'
                END as day_name,
                COUNT(*) as matches,
                AVG(kda) as avg_kda,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate
            FROM {table}
            GROUP BY EXTRACT(DOW FROM start_time)
            ORDER BY day_of_week
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
