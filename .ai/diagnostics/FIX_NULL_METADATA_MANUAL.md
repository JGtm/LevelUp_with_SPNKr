# Correction manuelle des métadonnées NULL

**Date**: 2026-02-05  
**Problème**: Les matchs ont des métadonnées NULL et sont exclus des filtres

---

## Solution immédiate : SQL direct

Exécutez ces commandes SQL directement dans votre client DuckDB ou via Python :

### 1. Pour Chocoboflor - Match spécifique

```python
import duckdb

# Ouvrir la base
conn = duckdb.connect("data/players/Chocoboflor/stats.duckdb", read_only=False)

# Attacher metadata.duckdb si disponible
try:
    conn.execute("ATTACH 'data/warehouse/metadata.duckdb' AS meta (READ_ONLY)")
except:
    pass

# Corriger le match spécifique
match_id = "410f1c01-aca6-4567-9df5-9b16bd550cb2"

# Fallback sur les IDs (toujours fonctionne)
conn.execute(f"""
    UPDATE match_stats
    SET 
        map_name = COALESCE(map_name, map_id),
        playlist_name = COALESCE(playlist_name, playlist_id),
        pair_name = COALESCE(pair_name, pair_id),
        game_variant_name = COALESCE(game_variant_name, game_variant_id)
    WHERE match_id = ?
""", [match_id])

conn.commit()
conn.close()
```

### 2. Pour tous les matchs NULL (Chocoboflor)

```python
import duckdb

conn = duckdb.connect("data/players/Chocoboflor/stats.duckdb", read_only=False)

try:
    conn.execute("ATTACH 'data/warehouse/metadata.duckdb' AS meta (READ_ONLY)")
except:
    pass

# Fallback simple sur les IDs
conn.execute("""
    UPDATE match_stats
    SET 
        map_name = COALESCE(map_name, map_id),
        playlist_name = COALESCE(playlist_name, playlist_id),
        pair_name = COALESCE(pair_name, pair_id),
        game_variant_name = COALESCE(game_variant_name, game_variant_id)
    WHERE map_name IS NULL 
       OR playlist_name IS NULL 
       OR pair_name IS NULL
       OR game_variant_name IS NULL
""")

conn.commit()
conn.close()
```

### 3. Pour JGtm - Tous les matchs NULL

```python
import duckdb

conn = duckdb.connect("data/players/JGtm/stats.duckdb", read_only=False)

try:
    conn.execute("ATTACH 'data/warehouse/metadata.duckdb' AS meta (READ_ONLY)")
except:
    pass

# Fallback sur les IDs
conn.execute("""
    UPDATE match_stats
    SET 
        map_name = COALESCE(map_name, map_id),
        playlist_name = COALESCE(playlist_name, playlist_id),
        pair_name = COALESCE(pair_name, pair_id),
        game_variant_name = COALESCE(game_variant_name, game_variant_id)
    WHERE map_name IS NULL 
       OR playlist_name IS NULL 
       OR pair_name IS NULL
       OR game_variant_name IS NULL
""")

conn.commit()
conn.close()
```

---

## Pourquoi ça ne marche pas pour JGtm ?

Le problème est probablement que :
1. Les matchs du 3 février ont des métadonnées NULL
2. Les filtres actifs (playlists, modes, cartes) excluent les matchs avec NULL
3. Donc le dernier match affiché est celui du 17 janvier

**Solution**: Exécuter le script ci-dessus pour JGtm, puis rafraîchir l'interface.

---

## Vérification après correction

```python
import duckdb

conn = duckdb.connect("data/players/JGtm/stats.duckdb", read_only=True)

# Vérifier les matchs récents
result = conn.execute("""
    SELECT match_id, start_time, map_name, playlist_name, pair_name
    FROM match_stats
    ORDER BY start_time DESC
    LIMIT 10
""").fetchall()

for row in result:
    print(f"{row[1]} | {row[2]} | {row[3]} | {row[4]}")

conn.close()
```

---

## Note importante

Les corrections que j'ai faites dans le code (`transform_match_stats`) fonctionneront pour les **nouveaux matchs** synchronisés. Mais les matchs **existants** doivent être corrigés avec ce script SQL.

Une fois corrigés, les nouveaux matchs seront automatiquement résolus grâce aux modifications dans `transform_match_stats()`.
