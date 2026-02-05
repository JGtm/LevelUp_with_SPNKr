# Diagnostic : Pourquoi certains matchs ont map_name/playlist_name/pair_name = NULL

**Date**: 2026-02-05  
**Problème**: Les matchs du 3 février 2026 ont `map_name=None`, `playlist_name=None`, `pair_name=None`

---

## Analyse du problème

### Observations
- Les matchs du 3 février 2026 ont des valeurs NULL pour les métadonnées
- Ces matchs sont exclus par les filtres actifs (playlists, modes, cartes)
- Résultat : Le dernier match affiché est celui du 17 janvier au lieu du 3 février

### Flux de données

**1. Synchronisation** :
```
_process_single_match()
  └─> client.get_match_stats(match_id) → stats_json
       └─> transform_match_stats(stats_json, xuid) → MatchStatsRow
            └─> _extract_public_name(match_info, "Playlist/MapVariant/PlaylistMapModePair")
                 └─> match_info.get(key).get("PublicName")
```

**2. Extraction des métadonnées** (`src/data/sync/transformers.py:296-303`) :
```python
def _extract_public_name(match_info: dict[str, Any], key: str) -> str | None:
    obj = match_info.get(key)
    if isinstance(obj, dict):
        name = obj.get("PublicName")
        if isinstance(name, str):
            return name
    return None
```

**3. Insertion dans DuckDB** (`src/data/sync/engine.py:831-870`) :
- Les valeurs NULL sont insérées directement dans `match_stats`
- Pas de fallback ou de résolution depuis les référentiels

---

## Causes possibles

### 1. L'API SPNKr ne retourne pas toujours PublicName

**Hypothèse** : Pour certains matchs récents, l'API SPNKr peut retourner :
- `MatchInfo.Playlist` avec seulement `AssetId` mais pas `PublicName`
- `MatchInfo.MapVariant` avec seulement `AssetId` mais pas `PublicName`
- `MatchInfo.PlaylistMapModePair` avec seulement `AssetId` mais pas `PublicName`

**Vérification nécessaire** : Vérifier le JSON brut de l'API pour ces matchs spécifiques.

### 2. Structure JSON différente pour les matchs récents

**Hypothèse** : La structure JSON peut avoir changé récemment dans l'API SPNKr.

**Vérification nécessaire** : Comparer la structure JSON d'un match du 17 janvier (qui fonctionne) avec un match du 3 février (qui a NULL).

### 3. Problème de résolution des assets

**Hypothèse** : Les `AssetId` sont présents mais les noms ne sont pas résolus depuis les référentiels.

**Vérification nécessaire** : Vérifier si les `map_id`, `playlist_id`, `pair_id` sont présents dans la DB pour ces matchs.

---

## Scripts de diagnostic créés

### 1. `scripts/diagnose_null_metadata.py`

Ce script vérifie directement dans la DB DuckDB :
- Les matchs avec métadonnées NULL
- Si les IDs sont présents mais pas les noms
- Comparaison avec les matchs récents qui fonctionnent
- **NOUVEAU** : Vérifie si on peut résoudre les noms depuis les référentiels (`metadata.duckdb`)

**Usage** :
```bash
# Diagnostic de base
python scripts/diagnose_null_metadata.py --db data/players/JGtm/stats.duckdb --limit 20

# Avec vérification de résolution depuis les référentiels
python scripts/diagnose_null_metadata.py \
    --db data/players/JGtm/stats.duckdb \
    --metadata-db data/warehouse/metadata.duckdb \
    --limit 20
```

**Ce que le script affiche** :
1. Liste des matchs avec métadonnées NULL
2. Statistiques : combien ont des IDs mais pas de noms
3. Comparaison avec les 5 matchs les plus récents
4. **Si `--metadata-db` est fourni** : vérifie si les noms peuvent être résolus depuis les référentiels

---

## Solutions possibles

### Solution 1 : Résolution depuis les référentiels

Si les `AssetId` sont présents mais les noms sont NULL, on peut résoudre les noms depuis les référentiels (`metadata.duckdb`) :

```python
# Dans transform_match_stats(), après extraction :
if map_id and not map_name:
    map_name = resolve_map_name_from_refdata(map_id)
if playlist_id and not playlist_name:
    playlist_name = resolve_playlist_name_from_refdata(playlist_id)
if pair_id and not pair_name:
    pair_name = resolve_pair_name_from_refdata(pair_id)
```

### Solution 2 : Fallback sur les IDs si les noms sont absents

Si les référentiels ne contiennent pas ces assets, utiliser les IDs comme fallback :

```python
map_name = map_name or map_id
playlist_name = playlist_name or playlist_id
pair_name = pair_name or pair_id
```

### Solution 3 : Requête UPDATE pour backfill

Créer un script pour mettre à jour les matchs avec valeurs NULL en résolvant depuis les référentiels ou en récupérant depuis l'API.

---

## Prochaines étapes

1. **Exécuter le script de diagnostic** pour voir exactement ce qui se passe dans la DB
2. **Vérifier le JSON brut de l'API** pour un match du 3 février pour voir si PublicName est présent
3. **Comparer avec un match du 17 janvier** qui fonctionne pour voir la différence
4. **Implémenter la solution** selon les résultats du diagnostic

---

## Fichiers à vérifier

1. `src/data/sync/transformers.py` - Fonctions d'extraction des métadonnées
2. `src/data/sync/engine.py` - Insertion dans DuckDB
3. `scripts/diagnose_null_metadata.py` - Script de diagnostic (à exécuter)
