# Exemples de Requêtes Analytiques

Ce document présente des exemples de requêtes SQL avancées utilisant DuckDB
pour analyser les données de matchs Halo Infinite.

## Configuration

```python
from src.data.query import QueryEngine, AnalyticsQueries, TrendAnalyzer

# Initialiser le moteur
engine = QueryEngine("data/warehouse")

# Classes de haut niveau
analytics = AnalyticsQueries(engine, xuid="VOTRE_XUID")
trends = TrendAnalyzer(engine, xuid="VOTRE_XUID")
```

---

## 1. Évolution du K/D sur les 500 derniers matchs

**Cas d'usage** : Visualiser la progression du joueur avec moyenne mobile.

```python
# Avec la classe TrendAnalyzer
kda_trend = trends.get_rolling_kda(window_size=20, last_n=500)

# Chaque entrée contient:
# - match_id, start_time
# - kda, kills, deaths
# - rolling_avg_kda (moyenne sur 20 matchs)
# - kd_ratio, rolling_avg_kd
```

**Requête SQL équivalente** :

```sql
WITH ranked AS (
    SELECT 
        match_id, start_time, kills, deaths,
        CASE WHEN deaths > 0 THEN kills * 1.0 / deaths ELSE kills END as kd_ratio,
        ROW_NUMBER() OVER (ORDER BY start_time DESC) as match_num
    FROM read_parquet('warehouse/match_facts/player=123/**/*.parquet')
),
last_500 AS (SELECT * FROM ranked WHERE match_num <= 500)
SELECT 
    *,
    AVG(kd_ratio) OVER (
        ORDER BY start_time ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) as rolling_avg_20
FROM last_500
ORDER BY start_time ASC
```

---

## 2. Performance par carte avec tendances

**Cas d'usage** : Identifier les cartes où le joueur progresse ou régresse.

```python
map_stats = analytics.get_performance_by_map(min_matches=5)

# Résultat: map_name, matches, avg_kda, win_rate, etc.
```

**Requête SQL avec comparaison récent/global** :

```sql
SELECT 
    COALESCE(map_name, 'Unknown') as map_name,
    COUNT(*) as total_matches,
    AVG(kda) as global_avg_kda,
    
    -- Stats 30 derniers jours
    AVG(CASE WHEN start_time >= NOW() - INTERVAL '30 days' THEN kda END) as recent_avg_kda,
    
    -- Tendance
    CASE 
        WHEN AVG(CASE WHEN start_time >= NOW() - INTERVAL '30 days' THEN kda END) > AVG(kda) * 1.05 
            THEN 'improving'
        WHEN AVG(CASE WHEN start_time >= NOW() - INTERVAL '30 days' THEN kda END) < AVG(kda) * 0.95 
            THEN 'declining'
        ELSE 'stable'
    END as trend
FROM read_parquet('warehouse/match_facts/player=123/**/*.parquet')
GROUP BY map_name
HAVING COUNT(*) >= 5
```

---

## 3. Détection automatique des sessions

**Cas d'usage** : Analyser les performances par session de jeu.

```sql
-- Gap > 30 min = nouvelle session
WITH match_gaps AS (
    SELECT 
        *, 
        LAG(start_time) OVER (ORDER BY start_time) as prev_time,
        EXTRACT(EPOCH FROM (start_time - LAG(start_time) OVER (ORDER BY start_time))) / 60 as gap_min
    FROM read_parquet('warehouse/match_facts/player=123/**/*.parquet')
),
sessions AS (
    SELECT *, SUM(CASE WHEN gap_min > 30 OR gap_min IS NULL THEN 1 ELSE 0 END) 
           OVER (ORDER BY start_time) as session_id
    FROM match_gaps
)
SELECT 
    session_id,
    MIN(start_time) as start,
    COUNT(*) as matches,
    AVG(kda) as avg_kda,
    SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins
FROM sessions
GROUP BY session_id
ORDER BY start DESC
```

---

## 4. Scores et K/D/A des joueurs d’un match (match_participants)

**Cas d’usage** : Afficher le rang, le score et les kills/deaths/assists de chaque joueur pour un match. L’identifiant des joueurs est **xuid** ; le nom s’obtient via **xuid_aliases** (la colonne `gamertag` de `match_participants` est souvent NULL).

**Dernier match d’un joueur (ex. Madina97294)** :

```sql
-- Connexion : data/players/Madina97294/stats.duckdb
SELECT
  p.match_id,
  p.xuid,
  COALESCE(p.gamertag, a.gamertag) AS gamertag,
  p.team_id,
  p.rank,
  p.score,
  p.kills,
  p.deaths,
  p.assists
FROM match_participants p
LEFT JOIN xuid_aliases a ON a.xuid = p.xuid
WHERE p.match_id = (
  SELECT match_id FROM match_stats ORDER BY start_time DESC LIMIT 1
)
ORDER BY p.rank NULLS LAST, p.score DESC NULLS LAST;
```

Voir aussi `docs/SQL_SCHEMA.md` (table `match_participants`) et `.ai/MATCH_PARTICIPANTS.md`.

---

## 5. Top médailles avec noms (jointure)

**Cas d'usage** : Afficher les médailles les plus fréquentes avec traduction.

```python
top_medals = analytics.get_top_medals_with_names(limit=10, language="fr")

# Résultat: medal_name_id, name, difficulty, total_count
```

**Requête SQL avec jointure** :

```sql
-- Attacher SQLite (automatique avec QueryEngine)
ATTACH 'warehouse/metadata.db' AS meta (TYPE SQLITE);

SELECT 
    m.medal_name_id,
    COALESCE(d.name_fr, d.name_en) as name,
    d.difficulty,
    SUM(m.count) as total
FROM read_parquet('warehouse/medals/player=123/**/*.parquet') m
LEFT JOIN meta.medal_definitions d ON m.medal_name_id = d.name_id
GROUP BY m.medal_name_id, d.name_fr, d.name_en, d.difficulty
ORDER BY total DESC
LIMIT 10
```

---

## 6. Analyse des comebacks

**Cas d'usage** : Identifier les victoires après plusieurs défaites.

```sql
WITH ordered AS (
    SELECT 
        *,
        LAG(outcome, 1) OVER (ORDER BY start_time) as prev_1,
        LAG(outcome, 2) OVER (ORDER BY start_time) as prev_2
    FROM read_parquet('warehouse/match_facts/player=123/**/*.parquet')
    WHERE outcome IN (2, 3)
)
SELECT 
    match_id, start_time, kills, deaths, kda, map_name
FROM ordered
WHERE outcome = 2 AND prev_1 = 3 AND prev_2 = 3  -- Victoire après 2 défaites
ORDER BY start_time DESC
```

---

## 7. Meilleures heures pour jouer

**Cas d'usage** : Identifier les créneaux horaires les plus performants.

```python
hourly = analytics.get_hourly_performance()
# Résultat: hour, matches, avg_kda, win_rate
```

**Requête SQL** :

```sql
SELECT 
    EXTRACT(HOUR FROM start_time) as hour,
    COUNT(*) as matches,
    AVG(kda) as avg_kda,
    SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0 END) / COUNT(*) as win_rate
FROM read_parquet('warehouse/match_facts/player=123/**/*.parquet')
GROUP BY hour
ORDER BY win_rate DESC
```

---

## 8. Comparaison de périodes

**Cas d'usage** : Comparer les performances cette semaine vs la semaine dernière.

```python
comparison = trends.compare_periods("kda", period_days=7)

print(f"KDA actuel: {comparison.current_value:.2f}")
print(f"KDA précédent: {comparison.previous_value:.2f}")
print(f"Tendance: {comparison.trend}")  # up, down, stable
```

---

## 9. Score de difficulté des playlists

**Cas d'usage** : Classer les playlists par difficulté perçue.

```sql
WITH stats AS (
    SELECT 
        playlist_name,
        COUNT(*) as matches,
        AVG(kda) as avg_kda,
        SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0 END) / COUNT(*) as win_rate
    FROM read_parquet('warehouse/match_facts/player=123/**/*.parquet')
    GROUP BY playlist_name
    HAVING COUNT(*) >= 10
)
SELECT 
    *,
    -- Score 0-100 (plus élevé = plus difficile)
    ((1 - LEAST(avg_kda / 3.0, 1)) * 50 + (1 - win_rate) * 50) as difficulty_score
FROM stats
ORDER BY difficulty_score DESC
```

---

## Utilisation avec Polars

Pour des manipulations avancées, retourner un DataFrame Polars :

```python
# Retour en DataFrame Polars
df = engine.execute(
    "SELECT * FROM read_parquet('warehouse/match_facts/**/*.parquet')",
    return_type="polars"
)

# Manipulations Polars
result = (
    df.filter(pl.col("outcome") == 2)
    .group_by("map_name")
    .agg([
        pl.col("kda").mean().alias("avg_kda"),
        pl.count().alias("wins")
    ])
    .sort("avg_kda", descending=True)
)
```

---

## Performance

| Requête | Legacy (JSON) | DuckDB + Parquet | Gain |
|---------|---------------|------------------|------|
| Stats globales 10K matchs | ~5s | ~0.2s | 25x |
| Rolling KDA 500 matchs | ~3s | ~0.1s | 30x |
| Jointure médailles | ~2s | ~0.1s | 20x |
| Session detection | ~4s | ~0.15s | 25x |
