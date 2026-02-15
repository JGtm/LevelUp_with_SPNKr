# Query Engine - Moteur DuckDB Unifié

## Résumé
Moteur de requêtes SQL haute performance basé sur DuckDB. Unifie l'accès aux métadonnées SQLite et aux faits Parquet via une interface simple. Supporte les jointures cross-sources, le filtrage par partitions, et la conversion automatique vers Polars ou listes de dicts.

## Inputs
- **warehouse_path** : Chemin vers le dossier warehouse (`data/warehouse/`)
- **Requêtes SQL** : Templates avec placeholders ({table}, {match_facts}, {players}, etc.)
- **Paramètres** : xuid, year, month pour filtrage par partition

## Outputs
- **list[dict]** : Résultats sous forme de liste de dictionnaires
- **pl.DataFrame** : DataFrame Polars pour traitement ultérieur
- **duckdb.DuckDBPyRelation** : Relation brute pour chaînage de requêtes
- **list[MatchRow]** : Objets métier typés

## Dépendances
- **Packages externes** :
  - `duckdb` : Moteur OLAP
  - `polars` : DataFrames
- **Modules internes** :
  - `src.models.MatchRow` : Modèle de résultat
  - `src.data.query.analytics` : Requêtes analytiques pré-définies
  - `src.data.query.trends` : Analyse de tendances

## Logique Métier

### Initialisation
```python
engine = QueryEngine("data/warehouse", memory_limit="1GB", threads=4)

# Automatiquement:
# 1. Crée connexion DuckDB in-memory
# 2. Configure optimisations (object_cache, progress_bar off)
# 3. Attache SQLite metadata en READ_ONLY si existe
```

### Construction des patterns Parquet
```python
# Génère le glob pour read_parquet()
engine.get_parquet_glob("match_facts", xuid="123", year=2025, month=1)
# → "data/warehouse/match_facts/player=123/year=2025/month=01/*.parquet"

engine.get_parquet_glob("match_facts", xuid="123")  
# → "data/warehouse/match_facts/player=123/year=*/month=*/*.parquet"
```

### Méthodes d'exécution

| Méthode | Usage |
|---------|-------|
| `execute(sql, params)` | Requête SQL directe avec placeholders |
| `execute_with_parquet(template, table, xuid)` | Remplace {table} par read_parquet() |
| `query_match_facts(xuid, select, where, order_by, limit)` | Requête simplifiée match_facts |
| `query_with_metadata_join(template, xuid)` | Jointures SQLite + Parquet |

### Placeholders disponibles
```sql
{match_facts}  → read_parquet('warehouse/match_facts/player={xuid}/**/*.parquet')
{medals}       → read_parquet('warehouse/medals/player={xuid}/**/*.parquet')
{players}      → meta.players (SQLite)
{playlists}    → meta.playlists (SQLite)
{maps}         → meta.maps (SQLite)
{game_variants} → meta.game_variants (SQLite)
{medal_definitions} → meta.medal_definitions (SQLite)
```

### Exemple de requête cross-source
```sql
SELECT 
    p.gamertag,
    pl.public_name as playlist,
    AVG(m.kda) as avg_kda,
    COUNT(*) as matches
FROM {match_facts} m
JOIN {players} p ON m.xuid = p.xuid
LEFT JOIN {playlists} pl ON m.playlist_id = pl.asset_id
WHERE m.outcome = 2  -- Victoires uniquement
GROUP BY p.gamertag, pl.public_name
ORDER BY avg_kda DESC
```

### Configuration DuckDB
```sql
SET memory_limit = '1GB';
SET threads = 4;  -- Auto-detect si non spécifié
SET enable_object_cache = true;  -- Cache les métadonnées Parquet
SET enable_progress_bar = false;  -- Pas de barre dans Streamlit
```

## Points d'Attention
- **Lazy loading** : Connexion créée au premier accès
- **Partition pruning** : Spécifier xuid/year/month réduit les fichiers scannés
- **Paramètres SQL** : Utiliser $name et `params={"name": value}` pour éviter injections
- **Nettoyage** : `engine.close()` ou context manager pour libérer ressources
- **Metadata absente** : Warning si SQLite non trouvée, jointures dégradées

## Fichiers Clés
| Fichier | Rôle |
|---------|------|
| `src/data/query/engine.py` | QueryEngine principal |
| `src/data/query/analytics.py` | AnalyticsQueries (KPIs, tendances) |
| `src/data/query/trends.py` | TrendAnalyzer (rolling averages) |
| `src/data/query/examples.py` | Exemples de requêtes |
