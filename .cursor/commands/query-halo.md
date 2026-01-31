# Commande /query-halo

Exécute une requête SQL sur les données Halo via DuckDB.

## Prérequis
- MCP `duckdb` configuré dans Cursor Settings

## Usage
`/query-halo [description de ce que tu veux savoir]`

## Exemples

### Stats globales
```sql
SELECT COUNT(*) as total_matches,
       AVG(kda) as avg_kda,
       SUM(kills) as total_kills
FROM read_parquet('data/warehouse/match_facts/**/*.parquet')
```

### Jointure avec métadonnées
```sql
ATTACH 'data/warehouse/metadata.db' AS meta (TYPE sqlite);

SELECT m.name_fr as medal, COUNT(*) as count
FROM read_parquet('data/warehouse/medals/**/*.parquet') p
JOIN meta.medal_definitions m ON p.medal_name_id = m.name_id
GROUP BY m.name_fr
ORDER BY count DESC
LIMIT 10
```

### Stats par playlist
```sql
ATTACH 'data/warehouse/metadata.db' AS meta (TYPE sqlite);

SELECT p.name_fr as playlist, 
       COUNT(*) as matches,
       AVG(f.kda) as avg_kda
FROM read_parquet('data/warehouse/match_facts/**/*.parquet') f
JOIN meta.playlists p ON f.playlist_id = p.uuid
GROUP BY p.name_fr
ORDER BY matches DESC
```

## Si MCP non disponible
Utiliser le script Python :
```bash
python -c "
import duckdb
conn = duckdb.connect(':memory:')
result = conn.execute('[QUERY]').fetchall()
print(result)
"
```
