# Solution immédiate : Correction des métadonnées NULL

**Problème identifié** :
1. Les matchs synchronisés AVANT mes corrections ont des métadonnées NULL
2. Les filtres actifs excluent les matchs avec NULL
3. Donc le dernier match affiché est celui du 17 janvier au lieu du 3 février

**Solution** : Exécuter ces commandes SQL pour corriger les matchs existants.

---

## Commande Python rapide

Copiez-collez cette commande dans un terminal Python depuis le répertoire du projet :

```python
import duckdb

# Pour Chocoboflor - Match spécifique
conn = duckdb.connect("data/players/Chocoboflor/stats.duckdb", read_only=False)
conn.execute("""
    UPDATE match_stats
    SET 
        map_name = COALESCE(map_name, map_id),
        playlist_name = COALESCE(playlist_name, playlist_id),
        pair_name = COALESCE(pair_name, pair_id),
        game_variant_name = COALESCE(game_variant_name, game_variant_id)
    WHERE match_id = '410f1c01-aca6-4567-9df5-9b16bd550cb2'
""")
conn.commit()
conn.close()
print("✅ Match corrigé")

# Pour Chocoboflor - Tous les matchs NULL
conn = duckdb.connect("data/players/Chocoboflor/stats.duckdb", read_only=False)
conn.execute("""
    UPDATE match_stats
    SET 
        map_name = COALESCE(map_name, map_id),
        playlist_name = COALESCE(playlist_name, playlist_id),
        pair_name = COALESCE(pair_name, pair_id),
        game_variant_name = COALESCE(game_variant_name, game_variant_id)
    WHERE map_name IS NULL OR playlist_name IS NULL OR pair_name IS NULL OR game_variant_name IS NULL
""")
conn.commit()
conn.close()
print("✅ Tous les matchs NULL corrigés pour Chocoboflor")

# Pour JGtm - Tous les matchs NULL (pour voir les matchs du 3 février)
conn = duckdb.connect("data/players/JGtm/stats.duckdb", read_only=False)
conn.execute("""
    UPDATE match_stats
    SET 
        map_name = COALESCE(map_name, map_id),
        playlist_name = COALESCE(playlist_name, playlist_id),
        pair_name = COALESCE(pair_name, pair_id),
        game_variant_name = COALESCE(game_variant_name, game_variant_id)
    WHERE map_name IS NULL OR playlist_name IS NULL OR pair_name IS NULL OR game_variant_name IS NULL
""")
conn.commit()
conn.close()
print("✅ Tous les matchs NULL corrigés pour JGtm")
```

---

## Après correction

1. **Rafraîchir l'interface Streamlit** - Les matchs du 3 février devraient maintenant apparaître
2. **Vérifier le dernier match** - Il devrait être celui du 3 février pour JGtm

---

## Pourquoi ça marche maintenant ?

- Les matchs existants sont corrigés avec un fallback sur les IDs
- Les nouveaux matchs seront automatiquement résolus grâce aux modifications dans `transform_match_stats()`
- Les filtres ne pourront plus exclure les matchs car ils auront des valeurs (même si ce sont les IDs)

---

## Note

Si vous préférez résoudre depuis `metadata.duckdb` au lieu d'utiliser les IDs comme fallback, vous pouvez d'abord attacher metadata.duckdb :

```python
conn.execute("ATTACH 'data/warehouse/metadata.duckdb' AS meta (READ_ONLY)")
# Puis utiliser des requêtes avec JOIN sur meta.playlists, meta.maps, etc.
```

Mais le fallback sur les IDs fonctionne immédiatement et garantit qu'on n'a jamais de NULL si un ID est présent.
