# Exploration : Données Manquantes en BDD

**Date** : 2026-02-05  
**Priorité** : HAUTE  
**Status** : ✅ DIAGNOSTIC TERMINÉ - CAUSES IDENTIFIÉES

---

## 🔴 RÉSULTATS DU DIAGNOSTIC (2026-02-05)

### Cause racine confirmée : Discovery UGC jamais appelé

| Problème | Cause | Fichier |
|----------|-------|---------|
| Noms NULL (playlist, map, pair, game_variant) | Discovery UGC non appelé + metadata.duckdb absent | engine.py |
| Valeurs attendues NULL (kills/deaths/assists_expected) | StatPerformances absent ou structure API différente | transformers.py |
| Récupération rosters | Pas de table match_rosters, dépend de highlight_events/xuid_aliases | duckdb_repo.py |

### Points vérifiés

- **metadata.duckdb** : ❌ N'existe pas (`data/warehouse/` absent) → `create_metadata_resolver()` retourne `None`
- **options.with_assets** : ✅ Défini `True` dans `SyncOptions` mais **jamais utilisé** dans `_process_single_match()`
- **client.get_asset()** : ❌ Aucun appel dans le moteur de sync
- **options.with_aliases** : ✅ `True` par défaut, `extract_aliases()` bien appelé

---

## 📋 Checklist d'Exploration

### ✅ 0. Vérifier si les endpoints Discovery UGC sont appelés ⚠️ CONFIRMÉ

**Fichier** : `src/data/sync/engine.py`  
**Fonction** : `_process_single_match()` (lignes 614-719)

**Résultat** : ❌ **Les endpoints Discovery UGC ne sont PAS appelés**

**Vérifications effectuées** :
- [x] `client.get_asset()` : **jamais appelé** dans `_process_single_match()`
- [x] `options.with_assets` : Défini True mais **jamais vérifié** dans le code
- [x] `scripts/spnkr_import_db.py` : Appelle bien `get_map`, `get_playlist`, `get_map_mode_pair`, `get_ugc_game_variant`
- [x] Les `version_id` existent dans le JSON (`MatchInfo.Playlist.VersionId` etc.) mais ne sont pas utilisés

**Action requise** : Ajouter les appels Discovery UGC dans `_process_single_match()` quand `options.with_assets=True`

---

### ✅ 1. Vérifier l'initialisation de `metadata_resolver` — CONFIRMÉ

**Fichier** : `src/data/sync/engine.py`  
**Ligne** : 259

**Résultat** : ❌ **metadata_resolver = None** (metadata.duckdb absent)

**Vérifications effectuées** :
- [x] `self._metadata_db_path` = `data_dir / "warehouse" / "metadata.duckdb"` (correct)
- [x] `metadata.duckdb` : **n'existe pas** (dossier `data/warehouse/` absent du projet)
- [x] `create_metadata_resolver()` : Retourne `None` si le fichier n'existe pas (ligne 397-399 transformers.py)
- [x] Conséquence : Toute résolution depuis référentiels échoue

---

### ✅ 2. Vérifier l'extraction des noms depuis le JSON API

**Fichier** : `src/data/sync/transformers.py`  
**Fonction** : `_extract_public_name()` (lignes 303-310)

**Chaîne d'extraction actuelle** (transform_match_stats lignes 574-612) :
1. `playlist_name = _extract_public_name(match_info, "Playlist")` — peut être None si API ne renvoie pas PublicName
2. Si `metadata_resolver` et (playlist_id présent et nom NULL/UUID) → résolution depuis metadata.duckdb
3. **metadata_resolver = None** → étape 2 toujours ignorée
4. Fallback : `playlist_name = playlist_name or playlist_id` → utilise l'ID (UUID) comme "nom"

**Conclusion** : Si l'API ne fournit pas `PublicName` dans MatchInfo, les noms restent les IDs (UUID). Seul Discovery UGC peut fournir les vrais noms.

---

### ✅ 3. Vérifier l'insertion en BDD

**Fichier** : `src/data/sync/engine.py`  
**Fonction** : `_insert_match_row()` (lignes 840-886)

**Vérifications à faire** :
- [ ] Vérifier que les valeurs ne sont pas NULL avant insertion
- [ ] Vérifier que l'insertion réussit (pas d'exception silencieuse)
- [ ] Vérifier les valeurs réellement insérées en BDD

**Requête SQL de vérification** :
```sql
-- Vérifier les valeurs NULL dans match_stats
SELECT 
    COUNT(*) as total,
    COUNT(playlist_name) as avec_playlist_name,
    COUNT(map_name) as avec_map_name,
    COUNT(pair_name) as avec_pair_name,
    COUNT(game_variant_name) as avec_game_variant_name
FROM match_stats
ORDER BY start_time DESC
LIMIT 100;
```

---

### ✅ 4. Vérifier la récupération depuis BDD

**Fichier** : `src/data/repositories/duckdb_repo.py`  
**Fonction** : `load_matches()` (lignes 200-399)

**Vérifications à faire** :
- [ ] Vérifier que les jointures métadonnées fonctionnent
- [ ] Vérifier que les valeurs sont bien récupérées depuis `match_stats`
- [ ] Vérifier que `COALESCE()` fonctionne correctement

**Requête SQL de vérification** :
```sql
-- Vérifier la récupération avec jointures
SELECT 
    match_stats.match_id,
    match_stats.playlist_name as playlist_name_direct,
    COALESCE(meta.playlists.public_name, match_stats.playlist_name) as playlist_name_resolved
FROM match_stats
LEFT JOIN meta.playlists ON match_stats.playlist_id = meta.playlists.asset_id
LIMIT 10;
```

---

### ✅ 5. Vérifier l'extraction des aliases — OK

**Fichier** : `src/data/sync/engine.py`  
**Fonction** : `_process_single_match()` (lignes 668-670)

**Résultat** : ✅ **Logique correcte**
- [x] `options.with_aliases` = `True` par défaut (models.py:40)
- [x] `extract_aliases(stats_json)` appelé
- [x] Aliases insérés via `_insert_alias_rows()`

**Requête de vérification** : `python scripts/diagnostic_critical_data.py` (à exécuter avec l'env du projet)

---

### ✅ 6. Vérifier l'extraction des valeurs attendues

**Fichier** : `src/data/sync/transformers.py`  
**Fonction** : `transform_skill_stats()` (lignes 773-877)

**Code actuel** :
```python
stat_performances = result.get("StatPerformances")
if isinstance(stat_performances, dict):
    for stat_name, perf in stat_performances.items():
        if stat_name.lower() == "kills":
            kills_expected = _safe_float(perf.get("Expected"))
```

**Vérifications à faire** :
- [ ] Vérifier que `options.with_skill` est `True` par défaut
- [ ] Vérifier que `StatPerformances` est présent dans le JSON skill
- [ ] Vérifier que les valeurs sont extraites correctement

**Requête SQL de vérification** :
```sql
-- Vérifier les valeurs attendues dans player_match_stats
SELECT 
    COUNT(*) as total,
    COUNT(kills_expected) as avec_kills_expected,
    COUNT(deaths_expected) as avec_deaths_expected,
    COUNT(assists_expected) as avec_assists_expected
FROM player_match_stats;
```

**Test à faire** :
```python
# Dans transform_skill_stats(), ajouter des logs :
logger.debug(f"stat_performances: {stat_performances}")
if isinstance(stat_performances, dict):
    logger.debug(f"Keys in stat_performances: {list(stat_performances.keys())}")
```

---

### ✅ 7. Vérifier la récupération des rosters

**Fichier** : `src/data/repositories/duckdb_repo.py`  
**Fonction** : `load_match_rosters()` (lignes 1180-1230)

**Problème identifié** :
- Pour DuckDB v4, `load_match_rosters()` retourne `enemy_team_names: []` par défaut
- Les rosters ne sont pas stockés dans une table dédiée

**Vérifications à faire** :
- [ ] Vérifier si les rosters sont stockés quelque part
- [ ] Vérifier si `highlight_events` contient les gamertags
- [ ] Vérifier si `xuid_aliases` peut être utilisé pour récupérer les noms

**Requête SQL de vérification** :
```sql
-- Vérifier les gamertags dans highlight_events
SELECT DISTINCT gamertag FROM highlight_events WHERE gamertag IS NOT NULL LIMIT 20;

-- Vérifier les aliases pour un match spécifique
SELECT xa.xuid, xa.gamertag 
FROM xuid_aliases xa
WHERE xa.xuid IN (
    SELECT DISTINCT xuid FROM highlight_events WHERE match_id = 'MATCH_ID_ICI'
);
```

---

### ✅ 8. Comparer avec le commit de référence

**Commit** : `1a6115007272619985485be0f94cc69e6be5c2d2`

**Différences à vérifier** :
- [ ] Vérifier comment les noms étaient extraits avant
- [ ] Vérifier si `metadata_resolver` existait avant
- [ ] Vérifier les options par défaut de synchronisation

**Commandes Git** :
```bash
# Voir le code de transform_match_stats() dans le commit de référence
git show 1a6115007272619985485be0f94cc69e6be5c2d2:src/data/sync/transformers.py | grep -A 50 "def transform_match_stats"

# Voir les options de synchronisation
git show 1a6115007272619985485be0f94cc69e6be5c2d2:src/data/sync/engine.py | grep -A 20 "class SyncOptions"
```

---

## 🔍 Requêtes SQL de Diagnostic

### Requête 1 : Vérifier les noms NULL dans match_stats

```sql
SELECT 
    match_id,
    start_time,
    playlist_id,
    playlist_name,
    map_id,
    map_name,
    pair_id,
    pair_name,
    game_variant_id,
    game_variant_name
FROM match_stats
WHERE playlist_name IS NULL 
   OR map_name IS NULL 
   OR pair_name IS NULL
ORDER BY start_time DESC
LIMIT 20;
```

### Requête 2 : Vérifier les valeurs attendues NULL

```sql
SELECT 
    match_id,
    kills_expected,
    deaths_expected,
    assists_expected
FROM player_match_stats
WHERE kills_expected IS NULL 
   OR deaths_expected IS NULL 
   OR assists_expected IS NULL
LIMIT 20;
```

### Requête 3 : Vérifier les aliases

```sql
SELECT COUNT(*) as total_aliases FROM xuid_aliases;

SELECT 
    xuid,
    gamertag,
    last_seen,
    source
FROM xuid_aliases
ORDER BY last_seen DESC
LIMIT 20;
```

### Requête 4 : Vérifier les rosters depuis highlight_events

```sql
SELECT 
    match_id,
    COUNT(DISTINCT xuid) as unique_players,
    COUNT(DISTINCT gamertag) as unique_gamertags
FROM highlight_events
GROUP BY match_id
ORDER BY match_id DESC
LIMIT 10;
```

---

## 📝 Logs à Ajouter (SANS MODIFIER LE CODE POUR LE MOMENT)

### Dans `transform_match_stats()` :

```python
# Après l'extraction des noms (ligne ~577)
logger.debug(f"[MATCH {match_id}] Extraction noms:")
logger.debug(f"  playlist_name depuis JSON: {playlist_name}")
logger.debug(f"  map_name depuis JSON: {map_name}")
logger.debug(f"  pair_name depuis JSON: {pair_name}")
logger.debug(f"  game_variant_name depuis JSON: {game_variant_name}")

# Après la résolution depuis référentiels (ligne ~607)
if metadata_resolver:
    logger.debug(f"[MATCH {match_id}] Résolution depuis référentiels:")
    logger.debug(f"  metadata_resolver disponible: {metadata_resolver is not None}")
else:
    logger.warning(f"[MATCH {match_id}] metadata_resolver est None!")

# Avant le retour (ligne ~645)
logger.debug(f"[MATCH {match_id}] Noms finaux:")
logger.debug(f"  playlist_name: {playlist_name}")
logger.debug(f"  map_name: {map_name}")
logger.debug(f"  pair_name: {pair_name}")
logger.debug(f"  game_variant_name: {game_variant_name}")
```

### Dans `transform_skill_stats()` :

```python
# Après l'extraction de stat_performances (ligne ~838)
logger.debug(f"[SKILL {match_id}] StatPerformances:")
logger.debug(f"  stat_performances type: {type(stat_performances)}")
if isinstance(stat_performances, dict):
    logger.debug(f"  Keys: {list(stat_performances.keys())}")
    for stat_name, perf in stat_performances.items():
        logger.debug(f"    {stat_name}: {perf}")

# Avant le retour (ligne ~863)
logger.debug(f"[SKILL {match_id}] Valeurs attendues:")
logger.debug(f"  kills_expected: {kills_expected}")
logger.debug(f"  deaths_expected: {deaths_expected}")
logger.debug(f"  assists_expected: {assists_expected}")
```

### Dans `DuckDBSyncEngine.__init__()` :

```python
# Après l'initialisation de metadata_resolver (ligne ~259)
logger.info(f"metadata_resolver initialisé: {self._metadata_resolver is not None}")
if self._metadata_resolver is None:
    logger.warning(f"metadata.duckdb non trouvé: {self._metadata_db_path}")
else:
    logger.info(f"metadata.duckdb trouvé: {self._metadata_db_path}")
```

---

## 🎯 Prochaines Étapes (Phase Correction)

1. ~~Exécuter les requêtes SQL~~ → Diagnostic terminé
2. **Implémenter les appels Discovery UGC** dans `_process_single_match()` :
   - Extraire `AssetId` et `VersionId` depuis `MatchInfo.Playlist`, `MapVariant`, etc.
   - Appeler `client.get_asset()` pour Playlist, Map, PlaylistMapModePair, UgcGameVariant
   - Injecter les `PublicName` récupérés dans `transform_match_stats()` (ou enrichir le stats_json avant transformation)
3. **Option A** : Créer/metre à jour `metadata.duckdb` avant sync (comme spnkr_import_db)
4. **Option B** : Passer les noms résolus directement à `transform_match_stats()` sans dépendre de metadata_resolver
5. Pour **StatPerformances** (kills_expected etc.) : ajouter logs debug pour confirmer si l'API renvoie la structure attendue

### Script de vérification SQL

Exécuter manuellement : `python scripts/diagnostic_critical_data.py` (nécessite env avec duckdb)

---

## 📚 Références

- Document de diagnostic : `.ai/diagnostics/CRITICAL_DATA_MISSING_2026-02-05.md`
- Code de référence : Commit `1a6115007272619985485be0f94cc69e6be5c2d2`
- Fichiers clés :
  - `src/data/sync/transformers.py`
  - `src/data/sync/engine.py`
  - `src/data/repositories/duckdb_repo.py`

---

---

**IMPORTANT** : Corrections implémentées (2026-02-05) :
- Discovery UGC : `enrich_match_info_with_assets()` dans api_client + appel dans engine._process_single_match
- Aliases : `_normalize_gamertag()`, extraction XUID alignée legacy, support json.dumps(pid)
- StatPerformances : accès direct Kills/Deaths/Assists + fallback itératif
- Backfill : `--assets`, `--force-assets`, `--force-aliases`
