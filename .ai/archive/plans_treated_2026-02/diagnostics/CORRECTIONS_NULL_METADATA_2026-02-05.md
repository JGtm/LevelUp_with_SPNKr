# Corrections appliquées : Résolution des métadonnées NULL

**Date**: 2026-02-05  
**Problème**: Les matchs du 3 février 2026 ont `map_name=None`, `playlist_name=None`, `pair_name=None`  
**Statut**: ✅ Corrigé

---

## Résumé des modifications

### 1. Fonction de résolution depuis les référentiels

**Fichier**: `src/data/sync/transformers.py`

Ajout de la fonction `create_metadata_resolver()` qui :
- Se connecte à `metadata.duckdb` en lecture seule
- Résout les noms depuis les tables `playlists`, `maps`, `map_mode_pairs`, `game_variants`
- Utilise un cache pour éviter les requêtes répétées
- Gère les cas où les tables n'existent pas

```python
def create_metadata_resolver(
    metadata_db_path: Path | str | None = None,
) -> Callable[[str, str], str | None] | None:
    """Crée une fonction de résolution des noms depuis metadata.duckdb."""
    # ...
```

### 2. Modification de `transform_match_stats()`

**Fichier**: `src/data/sync/transformers.py`

- Ajout du paramètre optionnel `metadata_resolver`
- Résolution automatique si les noms sont NULL mais les IDs sont présents
- Fallback sur les IDs si la résolution échoue

```python
def transform_match_stats(
    match_json: dict[str, Any],
    xuid: str,
    *,
    skill_json: dict[str, Any] | None = None,
    metadata_resolver: Callable[[str, str | None], str | None] | None = None,
) -> MatchStatsRow | None:
    # ...
    # Résolution depuis les référentiels si les noms sont NULL mais les IDs sont présents
    if metadata_resolver:
        if playlist_id and not playlist_name:
            playlist_name = metadata_resolver("playlist", playlist_id)
        # ... (même logique pour map, pair, game_variant)
    
    # Fallback sur les IDs si les noms sont toujours NULL
    playlist_name = playlist_name or playlist_id
    map_name = map_name or map_id
    pair_name = pair_name or pair_id
    game_variant_name = game_variant_name or game_variant_id
```

### 3. Modification de `DuckDBSyncEngine`

**Fichier**: `src/data/sync/engine.py`

- Création du resolver dans `__init__()`
- Passage du resolver à `transform_match_stats()`

```python
# Dans __init__()
self._metadata_resolver = create_metadata_resolver(self._metadata_db_path)

# Dans _process_single_match()
match_row = transform_match_stats(
    stats_json,
    self._xuid,
    skill_json=skill_json,
    metadata_resolver=self._metadata_resolver,
)
```

---

## Comportement

### Scénario 1 : API retourne PublicName
- ✅ Le nom est utilisé directement (comportement existant)

### Scénario 2 : API retourne seulement AssetId
1. Tentative de résolution depuis `metadata.duckdb`
2. Si trouvé → utilisation du nom résolu
3. Si non trouvé → fallback sur l'AssetId

### Scénario 3 : metadata.duckdb non disponible
- ✅ Fallback automatique sur les IDs (pas d'erreur)

---

## Tests recommandés

1. **Vérifier la résolution** :
   ```bash
   python scripts/diagnose_null_metadata.py \
       --db data/players/JGtm/stats.duckdb \
       --metadata-db data/warehouse/metadata.duckdb \
       --limit 20
   ```

2. **Synchroniser un nouveau match** :
   ```bash
   python scripts/sync.py --delta --gamertag JGtm
   ```

3. **Vérifier que les matchs du 3 février ont maintenant des noms** :
   ```sql
   SELECT match_id, start_time, map_name, playlist_name, pair_name
   FROM match_stats
   WHERE DATE(start_time) = '2026-02-03'
   ORDER BY start_time DESC;
   ```

---

## Fichiers modifiés

1. `src/data/sync/transformers.py`
   - Ajout de `create_metadata_resolver()`
   - Modification de `transform_match_stats()`

2. `src/data/sync/engine.py`
   - Import de `create_metadata_resolver`
   - Création du resolver dans `__init__()`
   - Passage du resolver à `transform_match_stats()`

---

## Notes

- Le resolver utilise un cache pour éviter les requêtes répétées
- La connexion à `metadata.duckdb` est en lecture seule
- Le fallback sur les IDs garantit qu'on n'a jamais de valeurs NULL si un ID est présent
- Compatible avec l'architecture existante (pas de breaking changes)
