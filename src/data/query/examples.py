"""
Exemples de requêtes analytiques complexes.
(Examples of complex analytical queries)

Ce fichier contient des exemples de requêtes SQL avancées utilisant DuckDB
pour analyser les données de matchs Halo Infinite.

HOW IT WORKS:
Chaque fonction est un exemple documenté montrant comment utiliser
DuckDB pour des analyses complexes combinant :
- Jointures SQLite (métadonnées) + Parquet (faits)
- Fonctions de fenêtrage (window functions)
- Agrégations conditionnelles
- CTEs (Common Table Expressions)

Ces exemples peuvent être utilisés comme base pour créer
vos propres requêtes analytiques.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.data.query.engine import QueryEngine


class QueryExamples:
    """
    Collection d'exemples de requêtes analytiques.
    (Collection of analytical query examples)
    """
    
    def __init__(self, engine: QueryEngine, xuid: str) -> None:
        self.engine = engine
        self.xuid = xuid
    
    def kd_evolution_last_500_matches(self) -> list[dict[str, Any]]:
        """
        EXEMPLE 1: Évolution du ratio K/D moyen sur les 500 derniers matchs.
        (K/D ratio evolution over last 500 matches)
        
        C'est la requête complexe demandée dans le cahier des charges.
        Utilise une moyenne mobile sur 20 matchs pour lisser les variations.
        
        Technique: Window function avec ROWS BETWEEN
        """
        sql = """
            -- Récupérer les 500 derniers matchs avec numéro de rang
            WITH ranked AS (
                SELECT 
                    match_id,
                    start_time,
                    kills,
                    deaths,
                    -- Calculer K/D (évite division par 0)
                    CASE WHEN deaths > 0 
                         THEN ROUND(kills * 1.0 / deaths, 2) 
                         ELSE kills 
                    END as kd_ratio,
                    -- Numéro de match (du plus récent au plus ancien)
                    ROW_NUMBER() OVER (ORDER BY start_time DESC) as match_num
                FROM {table}
            ),
            -- Garder seulement les 500 derniers
            last_500 AS (
                SELECT * FROM ranked WHERE match_num <= 500
            )
            -- Calculer la moyenne mobile sur 20 matchs
            SELECT 
                match_id,
                start_time,
                kills,
                deaths,
                kd_ratio,
                match_num,
                -- Moyenne mobile sur les 20 matchs précédents (inclus)
                ROUND(AVG(kd_ratio) OVER (
                    ORDER BY start_time 
                    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                ), 3) as rolling_avg_20,
                -- Moyenne mobile sur les 50 matchs pour tendance long terme
                ROUND(AVG(kd_ratio) OVER (
                    ORDER BY start_time 
                    ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
                ), 3) as rolling_avg_50
            FROM last_500
            ORDER BY start_time ASC
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def performance_by_map_with_trends(self) -> list[dict[str, Any]]:
        """
        EXEMPLE 2: Performance par carte avec tendances récentes.
        (Map performance with recent trends)
        
        Compare les performances globales sur une carte avec
        les performances des 30 derniers jours.
        
        Technique: Agrégation conditionnelle avec CASE WHEN + dates
        """
        cutoff = datetime.now() - timedelta(days=30)
        
        sql = f"""
            SELECT 
                COALESCE(map_name, map_id, 'Unknown') as map_name,
                
                -- Stats globales
                COUNT(*) as total_matches,
                ROUND(AVG(kda), 2) as global_avg_kda,
                ROUND(SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0 END) / 
                      NULLIF(COUNT(*), 0) * 100, 1) as global_win_rate,
                
                -- Stats 30 derniers jours
                SUM(CASE WHEN start_time >= '{cutoff.isoformat()}' THEN 1 ELSE 0 END) 
                    as recent_matches,
                ROUND(AVG(CASE WHEN start_time >= '{cutoff.isoformat()}' THEN kda END), 2) 
                    as recent_avg_kda,
                ROUND(
                    SUM(CASE WHEN start_time >= '{cutoff.isoformat()}' AND outcome = 2 THEN 1.0 ELSE 0 END) / 
                    NULLIF(SUM(CASE WHEN start_time >= '{cutoff.isoformat()}' THEN 1 ELSE 0 END), 0) * 100, 
                1) as recent_win_rate,
                
                -- Tendance (récent vs global)
                CASE 
                    WHEN AVG(CASE WHEN start_time >= '{cutoff.isoformat()}' THEN kda END) > AVG(kda) * 1.05 
                        THEN 'improving'
                    WHEN AVG(CASE WHEN start_time >= '{cutoff.isoformat()}' THEN kda END) < AVG(kda) * 0.95 
                        THEN 'declining'
                    ELSE 'stable'
                END as trend
            FROM {{table}}
            GROUP BY COALESCE(map_name, map_id, 'Unknown')
            HAVING COUNT(*) >= 5  -- Au moins 5 matchs sur la carte
            ORDER BY total_matches DESC
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def session_analysis(self) -> list[dict[str, Any]]:
        """
        EXEMPLE 3: Analyse des sessions de jeu.
        (Gaming session analysis)
        
        Détecte les sessions (gaps > 30 min entre matchs) et
        calcule les stats par session.
        
        Technique: Window function LAG + agrégation sur groupes dynamiques
        """
        sql = """
            -- Étape 1: Marquer les débuts de session (gap > 30 min)
            WITH match_gaps AS (
                SELECT 
                    match_id,
                    start_time,
                    kills, deaths, assists, kda, outcome,
                    LAG(start_time) OVER (ORDER BY start_time) as prev_match_time,
                    EXTRACT(EPOCH FROM (
                        start_time - LAG(start_time) OVER (ORDER BY start_time)
                    )) / 60 as gap_minutes
                FROM {table}
            ),
            -- Étape 2: Assigner un ID de session
            session_markers AS (
                SELECT 
                    *,
                    CASE WHEN gap_minutes > 30 OR gap_minutes IS NULL THEN 1 ELSE 0 END as is_new_session
                FROM match_gaps
            ),
            session_ids AS (
                SELECT 
                    *,
                    SUM(is_new_session) OVER (ORDER BY start_time) as session_id
                FROM session_markers
            )
            -- Étape 3: Agréger par session
            SELECT 
                session_id,
                MIN(start_time) as session_start,
                MAX(start_time) as session_end,
                COUNT(*) as match_count,
                ROUND(EXTRACT(EPOCH FROM (MAX(start_time) - MIN(start_time))) / 60, 0) as duration_minutes,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(assists) as total_assists,
                ROUND(AVG(kda), 2) as avg_kda,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 3 THEN 1 ELSE 0 END) as losses,
                ROUND(
                    SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0 END) / 
                    NULLIF(SUM(CASE WHEN outcome IN (2, 3) THEN 1 ELSE 0 END), 0) * 100, 
                1) as win_rate
            FROM session_ids
            GROUP BY session_id
            HAVING COUNT(*) >= 2  -- Au moins 2 matchs par session
            ORDER BY session_start DESC
            LIMIT 50
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def comeback_analysis(self) -> list[dict[str, Any]]:
        """
        EXEMPLE 4: Analyse des "comebacks" après série de défaites.
        (Comeback analysis after loss streaks)
        
        Identifie les matchs gagnés après une série de défaites
        et analyse comment le joueur se comporte dans ces situations.
        
        Technique: Multiple window functions + filtrage sur patterns
        """
        sql = """
            -- Marquer les séries de victoires/défaites
            WITH ordered_matches AS (
                SELECT 
                    match_id,
                    start_time,
                    outcome,
                    kills, deaths, kda,
                    map_name,
                    playlist_name,
                    -- Résultat du match précédent
                    LAG(outcome, 1) OVER (ORDER BY start_time) as prev_outcome_1,
                    LAG(outcome, 2) OVER (ORDER BY start_time) as prev_outcome_2,
                    LAG(outcome, 3) OVER (ORDER BY start_time) as prev_outcome_3,
                    -- Résultat du match suivant
                    LEAD(outcome, 1) OVER (ORDER BY start_time) as next_outcome
                FROM {table}
                WHERE outcome IN (2, 3)  -- Seulement V/D
            )
            -- Trouver les "comebacks" (victoire après 2+ défaites)
            SELECT 
                match_id,
                start_time,
                kills,
                deaths,
                kda,
                COALESCE(map_name, 'Unknown') as map_name,
                COALESCE(playlist_name, 'Unknown') as playlist_name,
                -- Nombre de défaites consécutives avant ce match
                CASE 
                    WHEN prev_outcome_1 = 3 AND prev_outcome_2 = 3 AND prev_outcome_3 = 3 THEN 3
                    WHEN prev_outcome_1 = 3 AND prev_outcome_2 = 3 THEN 2
                    WHEN prev_outcome_1 = 3 THEN 1
                    ELSE 0
                END as losses_before,
                -- Est-ce que le joueur a enchaîné après le comeback?
                CASE WHEN next_outcome = 2 THEN 'continued_winning' ELSE 'lost_next' END as momentum
            FROM ordered_matches
            WHERE outcome = 2  -- Victoires seulement
              AND prev_outcome_1 = 3 AND prev_outcome_2 = 3  -- Après 2+ défaites
            ORDER BY start_time DESC
            LIMIT 50
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def playlist_difficulty_ranking(self) -> list[dict[str, Any]]:
        """
        EXEMPLE 5: Classement des playlists par difficulté.
        (Playlist difficulty ranking)
        
        Classe les playlists selon les performances du joueur
        pour identifier les plus "difficiles" (KDA bas, win rate bas).
        
        Technique: Scoring composite + ranking
        """
        sql = """
            WITH playlist_stats AS (
                SELECT 
                    COALESCE(playlist_name, playlist_id, 'Unknown') as playlist_name,
                    COUNT(*) as matches,
                    AVG(kda) as avg_kda,
                    AVG(accuracy) as avg_accuracy,
                    SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0 END) / 
                        NULLIF(COUNT(*), 0) as win_rate,
                    AVG(enemy_mmr - team_mmr) as avg_mmr_diff  -- Différence MMR moyenne
                FROM {table}
                GROUP BY COALESCE(playlist_name, playlist_id, 'Unknown')
                HAVING COUNT(*) >= 10  -- Au moins 10 matchs
            ),
            -- Calculer un score de difficulté (0-100)
            difficulty_scores AS (
                SELECT 
                    *,
                    -- Score inversé: plus c'est difficile, plus le score est élevé
                    (
                        -- KDA inversé normalisé (0-40 points)
                        (1.0 - LEAST(avg_kda / 3.0, 1.0)) * 40 +
                        -- Win rate inversé (0-40 points)
                        (1.0 - win_rate) * 40 +
                        -- MMR diff positif = adversaires plus forts (0-20 points)
                        LEAST(GREATEST(COALESCE(avg_mmr_diff, 0) / 200 + 0.5, 0), 1) * 20
                    ) as difficulty_score
                FROM playlist_stats
            )
            SELECT 
                playlist_name,
                matches,
                ROUND(avg_kda, 2) as avg_kda,
                ROUND(avg_accuracy, 1) as avg_accuracy,
                ROUND(win_rate * 100, 1) as win_rate_percent,
                ROUND(difficulty_score, 1) as difficulty_score,
                RANK() OVER (ORDER BY difficulty_score DESC) as difficulty_rank,
                CASE 
                    WHEN difficulty_score >= 70 THEN 'Très difficile'
                    WHEN difficulty_score >= 50 THEN 'Difficile'
                    WHEN difficulty_score >= 30 THEN 'Moyen'
                    ELSE 'Facile'
                END as difficulty_label
            FROM difficulty_scores
            ORDER BY difficulty_score DESC
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def peak_performance_analysis(self) -> list[dict[str, Any]]:
        """
        EXEMPLE 6: Analyse des pics de performance.
        (Peak performance analysis)
        
        Identifie les périodes où le joueur a atteint ses meilleures
        performances et analyse les conditions (heure, jour, playlist).
        
        Technique: Percentiles + corrélation avec contexte
        """
        sql = """
            -- Calculer le percentile de chaque match
            WITH match_percentiles AS (
                SELECT 
                    match_id,
                    start_time,
                    kda,
                    kills,
                    accuracy,
                    outcome,
                    map_name,
                    playlist_name,
                    EXTRACT(HOUR FROM start_time) as hour_of_day,
                    EXTRACT(DOW FROM start_time) as day_of_week,
                    PERCENT_RANK() OVER (ORDER BY kda) as kda_percentile,
                    PERCENT_RANK() OVER (ORDER BY accuracy) as accuracy_percentile
                FROM {table}
                WHERE kda IS NOT NULL AND accuracy IS NOT NULL
            ),
            -- Top 10% des matchs
            peak_matches AS (
                SELECT * FROM match_percentiles
                WHERE kda_percentile >= 0.90  -- Top 10%
            )
            -- Analyser les conditions des peak performances
            SELECT 
                -- Conditions les plus fréquentes
                ROUND(AVG(kda), 2) as avg_peak_kda,
                ROUND(AVG(accuracy), 1) as avg_peak_accuracy,
                ROUND(AVG(kills), 1) as avg_peak_kills,
                
                -- Heures les plus fréquentes pour les peaks
                MODE() WITHIN GROUP (ORDER BY hour_of_day) as best_hour,
                MODE() WITHIN GROUP (ORDER BY day_of_week) as best_day,
                
                -- Playlists avec le plus de peaks
                MODE() WITHIN GROUP (ORDER BY COALESCE(playlist_name, 'Unknown')) as best_playlist,
                
                -- Cartes avec le plus de peaks
                MODE() WITHIN GROUP (ORDER BY COALESCE(map_name, 'Unknown')) as best_map,
                
                -- Stats
                COUNT(*) as peak_match_count,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as peak_wins
            FROM peak_matches
        """
        
        return self.engine.execute_with_parquet(sql, "match_facts", self.xuid)  # type: ignore
    
    def medals_per_match_analysis(self) -> list[dict[str, Any]]:
        """
        EXEMPLE 7: Analyse des médailles par match avec jointure SQLite.
        (Medal analysis per match with SQLite join)
        
        Montre comment joindre Parquet (match_facts, medals) avec
        SQLite (medal_definitions) pour des analyses enrichies.
        
        Technique: Multi-table join Parquet + SQLite
        """
        sql = """
            -- Agréger les médailles par match
            WITH match_medals AS (
                SELECT 
                    match_id,
                    COUNT(DISTINCT medal_name_id) as unique_medals,
                    SUM(count) as total_medals
                FROM {medals}
                GROUP BY match_id
            ),
            -- Joindre avec les faits de match
            enriched AS (
                SELECT 
                    f.match_id,
                    f.start_time,
                    f.kda,
                    f.kills,
                    f.outcome,
                    COALESCE(f.map_name, 'Unknown') as map_name,
                    COALESCE(m.unique_medals, 0) as unique_medals,
                    COALESCE(m.total_medals, 0) as total_medals
                FROM {match_facts} f
                LEFT JOIN match_medals m ON f.match_id = m.match_id
            )
            -- Analyser la corrélation médailles / performance
            SELECT 
                CASE 
                    WHEN total_medals = 0 THEN '0 médailles'
                    WHEN total_medals <= 5 THEN '1-5 médailles'
                    WHEN total_medals <= 10 THEN '6-10 médailles'
                    WHEN total_medals <= 20 THEN '11-20 médailles'
                    ELSE '20+ médailles'
                END as medal_category,
                COUNT(*) as matches,
                ROUND(AVG(kda), 2) as avg_kda,
                ROUND(AVG(kills), 1) as avg_kills,
                ROUND(SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0 END) / COUNT(*) * 100, 1) as win_rate
            FROM enriched
            GROUP BY 
                CASE 
                    WHEN total_medals = 0 THEN '0 médailles'
                    WHEN total_medals <= 5 THEN '1-5 médailles'
                    WHEN total_medals <= 10 THEN '6-10 médailles'
                    WHEN total_medals <= 20 THEN '11-20 médailles'
                    ELSE '20+ médailles'
                END
            ORDER BY 
                CASE medal_category
                    WHEN '0 médailles' THEN 1
                    WHEN '1-5 médailles' THEN 2
                    WHEN '6-10 médailles' THEN 3
                    WHEN '11-20 médailles' THEN 4
                    ELSE 5
                END
        """
        
        return self.engine.query_with_metadata_join(sql, self.xuid)
