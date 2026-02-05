# Diagnostic Critique : Données Manquantes en BDD

**Date** : 2026-02-05  
**Priorité** : HAUTE  
**Commit de référence** : `1a6115007272619985485be0f94cc69e6be5c2d2` (fonctionnait correctement)

---

## 🔴 Problèmes Identifiés

### 1. Noms des cartes, modes et playlists non enregistrés

**Symptôme** : Les colonnes `playlist_name`, `map_name`, `pair_name`, `game_variant_name` sont NULL en BDD.

**Code concerné** :
- `src/data/sync/transformers.py` : `transform_match_stats()` (lignes 526-686)
- `src/data/sync/engine.py` : `_insert_match_row()` (lignes 840-886)

**Analyse** :

1. **Extraction des noms** (lignes 577-583 de `transformers.py`) :
   ```python
   playlist_name = _extract_public_name(match_info, "Playlist")
   map_name = _extract_public_name(match_info, "MapVariant")
   pair_name = _extract_public_name(match_info, "PlaylistMapModePair")
   game_variant_name = _extract_public_name(match_info, "UgcGameVariant")
   ```

2. **Résolution depuis référentiels** (lignes 585-607) :
   - Le code essaie de résoudre depuis `metadata_resolver` si les noms sont NULL ou des UUIDs
   - **PROBLÈME POTENTIEL** : `metadata_resolver` peut être `None` si `metadata.duckdb` n'existe pas ou n'est pas accessible

3. **Fallback sur IDs** (lignes 609-613) :
   ```python
   playlist_name = playlist_name or playlist_id
   map_name = map_name or map_id
   pair_name = pair_name or pair_id
   game_variant_name = game_variant_name or game_variant_id
   ```
   - Si les noms sont NULL, on utilise les IDs comme fallback
   - **PROBLÈME** : Si les IDs sont aussi NULL ou si `_extract_public_name()` retourne toujours None, les noms restent NULL

4. **Insertion en BDD** (lignes 840-886 de `engine.py`) :
   - Les valeurs sont bien insérées dans `match_stats`
   - **VÉRIFICATION NÉCESSAIRE** : Vérifier si les valeurs sont réellement NULL ou si c'est un problème de récupération

**Hypothèses** :
- `_extract_public_name()` retourne `None` car `PublicName` n'est pas présent dans le JSON API
- `metadata_resolver` n'est pas initialisé correctement dans `DuckDBSyncEngine`
- Les données sont insérées mais la récupération via `DuckDBRepository` ne fonctionne pas correctement

---

### 2. Noms des joueurs par match non récupérés

**Symptôme** : Les noms des joueurs ne sont pas correctement récupérés depuis la BDD.

**Code concerné** :
- `src/data/sync/transformers.py` : `extract_aliases()` (lignes 933-995)
- `src/data/sync/engine.py` : `_insert_alias_rows()` (lignes 940-960)
- `src/db/loaders.py` : `load_match_rosters()` (lignes 341-520)
- `src/data/repositories/duckdb_repo.py` : `load_match_rosters()` (lignes 1180-1230)

**Analyse** :

1. **Extraction des aliases** (`extract_aliases()`) :
   - Extrait les paires XUID → Gamertag depuis `match_json["Players"]`
   - Stocke dans la table `xuid_aliases`
   - **PROBLÈME POTENTIEL** : L'extraction peut échouer si la structure JSON est différente

2. **Récupération des rosters** (`load_match_rosters()`) :
   - Pour DuckDB v4, `load_match_rosters()` dans `duckdb_repo.py` lit depuis `highlight_events` ou `xuid_aliases`
   - **PROBLÈME** : Si `highlight_events` est vide ou si `xuid_aliases` n'est pas peuplé, les noms ne sont pas récupérés

3. **Affectation à l'équipe adverse** :
   - Le code dans `load_match_rosters()` sépare les joueurs par `team_id`
   - **PROBLÈME** : Si `team_id` n'est pas correctement extrait depuis le JSON, les joueurs ne sont pas affectés aux bonnes équipes

**Hypothèses** :
- Les aliases ne sont pas extraits lors de la synchronisation (`with_aliases=False` par défaut ?)
- Les rosters sont stockés dans le JSON brut mais pas dans les tables DuckDB structurées
- La récupération depuis DuckDB v4 ne fonctionne pas car les données sont dans un format différent

---

### 3. Nom de l'équipe adverse non récupéré

**Symptôme** : Le nom de l'équipe adverse (`enemy_team_name`) n'est pas récupéré.

**Code concerné** :
- `src/db/loaders.py` : `load_match_rosters()` (lignes 506-516)
- `src/data/repositories/duckdb_repo.py` : `load_match_rosters()` (lignes 1224-1228)

**Analyse** :

1. **Extraction du nom d'équipe** (`loaders.py` lignes 506-516) :
   ```python
   enemy_team_ids = sorted({int(r["team_id"]) for r in enemy_team if r.get("team_id") is not None})
   enemy_team_names = [TEAM_MAP.get(tid) for tid in enemy_team_ids]
   enemy_team_names = [n for n in enemy_team_names if isinstance(n, str) and n]
   ```
   - Utilise `TEAM_MAP` pour convertir `team_id` en nom
   - **PROBLÈME** : Si `enemy_team` est vide ou si `team_id` n'est pas extrait, `enemy_team_names` sera vide

2. **Pour DuckDB v4** (`duckdb_repo.py`) :
   - Retourne `enemy_team_names: []` par défaut (ligne 1228)
   - **PROBLÈME** : Le code ne récupère pas les noms d'équipe depuis les données

**Hypothèses** :
- Les `team_id` ne sont pas correctement extraits depuis le JSON
- `TEAM_MAP` n'est pas défini ou ne contient pas les mappings nécessaires
- Pour DuckDB v4, les données d'équipe ne sont pas stockées de la même manière

---

### 4. Valeurs "attendues" (expected) pour frags et morts non récupérées

**Symptôme** : `kills_expected`, `deaths_expected`, `assists_expected` sont NULL en BDD.

**Code concerné** :
- `src/data/sync/transformers.py` : `transform_skill_stats()` (lignes 773-877)
- `src/data/sync/engine.py` : `_insert_skill_row()` (lignes 888-914)
- `src/data/repositories/duckdb_repo.py` : `load_player_match_stats()` (lignes 2100-2200)

**Analyse** :

1. **Extraction des valeurs attendues** (`transform_skill_stats()` lignes 837-861) :
   ```python
   stat_performances = result.get("StatPerformances")
   if isinstance(stat_performances, dict):
       for stat_name, perf in stat_performances.items():
           if stat_name.lower() == "kills":
               kills_expected = _safe_float(perf.get("Expected"))
   ```
   - Extrait depuis `skill_json["Value"][player]["Result"]["StatPerformances"]`
   - **PROBLÈME POTENTIEL** : Si `StatPerformances` n'existe pas ou est vide, les valeurs restent NULL

2. **Insertion en BDD** (`_insert_skill_row()` lignes 888-914) :
   - Les valeurs sont insérées dans `player_match_stats`
   - **VÉRIFICATION NÉCESSAIRE** : Vérifier si les valeurs sont réellement NULL ou si c'est un problème de récupération

3. **Récupération** (`load_player_match_stats()` dans `duckdb_repo.py`) :
   - Lit depuis `player_match_stats`
   - **PROBLÈME** : Si les valeurs sont NULL en BDD, elles seront NULL lors de la récupération

**Hypothèses** :
- `StatPerformances` n'est pas présent dans le JSON skill de l'API
- L'extraction échoue silencieusement
- Les données sont insérées mais avec des valeurs NULL

---

## 🔍 Comparaison avec le Commit de Référence

**Commit** : `1a6115007272619985485be0f94cc69e6be5c2d2` (2026-02-01)

**Différences identifiées** :

1. **Transformers** :
   - Le commit de référence n'avait **PAS** de `metadata_resolver` dans `transform_match_stats()`
   - Les noms étaient extraits directement depuis `PublicName` dans le JSON
   - **CHANGEMENT** : Ajout de la résolution depuis référentiels (lignes 585-607)

2. **Extraction des noms** :
   - Le commit de référence utilisait `_extract_public_name()` directement
   - Pas de fallback sur `metadata_resolver`
   - **CHANGEMENT** : Ajout de la logique de résolution depuis `metadata.duckdb`

3. **Aliases** :
   - Le commit de référence avait la même logique d'extraction
   - **VÉRIFICATION NÉCESSAIRE** : Vérifier si `with_aliases` était activé par défaut

4. **Valeurs attendues** :
   - Le commit de référence avait la même logique d'extraction
   - **VÉRIFICATION NÉCESSAIRE** : Vérifier si `with_skill` était activé par défaut

---

## 🔴 PROBLÈME CRITIQUE IDENTIFIÉ : Requêtes API Incomplètes

**Hypothèse principale** : Les endpoints Discovery UGC ne sont **PAS appelés** pour récupérer les noms des assets !

### Analyse du Code

**Dans `DuckDBSyncEngine._process_single_match()`** (lignes 614-719) :
- ✅ `get_match_stats(match_id)` est appelé
- ✅ `get_skill_stats(match_id, xuids)` est appelé si `with_skill=True`
- ✅ `get_highlight_events(match_id)` est appelé si `with_highlight_events=True`
- ❌ **`get_asset()` pour Discovery UGC N'EST JAMAIS APPELÉ !**

**Conséquence** :
- Les noms (`PublicName`) ne sont récupérés que depuis le JSON du match (`MatchInfo.Playlist.PublicName`, etc.)
- Si `PublicName` n'est pas présent dans le JSON du match, les noms restent NULL
- Le `metadata_resolver` essaie de résoudre depuis `metadata.duckdb`, mais cette DB peut ne pas être à jour

**Comparaison avec `scripts/spnkr_import_db.py`** :
- Le script legacy (`_import_assets_for_match_info()`) **appelle bien** les endpoints Discovery UGC :
  ```python
  resp = await client.discovery_ugc.get_map(map_aid, map_vid)
  resp = await client.discovery_ugc.get_playlist(pl_aid, pl_vid)
  resp = await client.discovery_ugc.get_map_mode_pair(mp_aid, mp_vid)
  resp = await client.discovery_ugc.get_ugc_game_variant(gv_aid, gv_vid)
  ```

**Conclusion** : `DuckDBSyncEngine` ne récupère **PAS** les métadonnées complètes depuis Discovery UGC !

**Note** : `SyncOptions` a bien `with_assets: bool = True` par défaut, mais cette option n'est **jamais utilisée** dans `_process_single_match()` !

---

## 📋 Points de Vérification

### 0. Vérifier si les endpoints Discovery UGC sont appelés

**Fichier** : `src/data/sync/engine.py`  
**Fonction** : `_process_single_match()`

**Vérification** :
- [ ] Vérifier si `client.get_asset()` est appelé pour récupérer les métadonnées
- [ ] Vérifier si `options.with_assets` est utilisé
- [ ] Comparer avec `scripts/spnkr_import_db.py` qui appelle bien Discovery UGC
- [ ] Vérifier si les `version_id` sont extraits depuis le JSON du match

**Action requise** : Ajouter les appels Discovery UGC dans `_process_single_match()` si absents.

---

### 1. Vérifier l'initialisation de `metadata_resolver`

**Fichier** : `src/data/sync/engine.py`

**Ligne** : ~250-280 (initialisation de `DuckDBSyncEngine`)

**Vérification** :
```python
# Vérifier si metadata_resolver est initialisé
self._metadata_resolver = create_metadata_resolver(metadata_db_path)
```

**Action** : Vérifier que `metadata.duckdb` existe et que `create_metadata_resolver()` retourne une fonction valide.

---

### 2. Vérifier l'extraction depuis le JSON API

**Fichier** : `src/data/sync/transformers.py`

**Fonction** : `_extract_public_name()`

**Vérification** :
- Ajouter des logs pour voir ce qui est extrait depuis le JSON
- Vérifier si `PublicName` est présent dans les réponses API

**Action** : Ajouter des logs de debug pour tracer l'extraction.

---

### 3. Vérifier l'insertion en BDD

**Fichier** : `src/data/sync/engine.py`

**Fonction** : `_insert_match_row()`

**Vérification** :
- Vérifier que les valeurs ne sont pas NULL avant insertion
- Vérifier que l'insertion réussit

**Action** : Ajouter des logs pour voir les valeurs insérées.

---

### 4. Vérifier la récupération depuis BDD

**Fichier** : `src/data/repositories/duckdb_repo.py`

**Fonction** : `load_matches()`

**Vérification** :
- Vérifier que les jointures métadonnées fonctionnent
- Vérifier que les valeurs sont bien récupérées

**Action** : Vérifier les requêtes SQL générées.

---

### 5. Vérifier l'extraction des aliases

**Fichier** : `src/data/sync/engine.py`

**Fonction** : `_process_single_match()`

**Vérification** :
- Vérifier que `options.with_aliases` est activé
- Vérifier que `extract_aliases()` retourne des données

**Action** : Vérifier les options de synchronisation par défaut.

---

### 6. Vérifier l'extraction des valeurs attendues

**Fichier** : `src/data/sync/engine.py`

**Fonction** : `_process_single_match()`

**Vérification** :
- Vérifier que `options.with_skill` est activé
- Vérifier que `transform_skill_stats()` retourne des données avec `kills_expected` non NULL

**Action** : Vérifier les options de synchronisation par défaut.

---

## 💡 Solutions Proposées

### Solution 1 : Corriger l'extraction des noms depuis le JSON

**Problème** : `_extract_public_name()` retourne `None`

**Solution** :
1. Vérifier que `PublicName` est présent dans le JSON API
2. Si absent, utiliser `metadata_resolver` pour résoudre depuis `metadata.duckdb`
3. Si `metadata_resolver` est `None`, logger un warning et utiliser l'ID comme fallback

**Fichiers à modifier** :
- `src/data/sync/transformers.py` : `transform_match_stats()`

---

### Solution 2 : S'assurer que `metadata_resolver` est initialisé

**Problème** : `metadata_resolver` peut être `None`

**Solution** :
1. Vérifier que `metadata.duckdb` existe avant la synchronisation
2. Si absent, logger un warning mais continuer (utiliser les noms depuis le JSON)
3. S'assurer que `create_metadata_resolver()` est appelé dans `DuckDBSyncEngine.__init__()`

**Fichiers à modifier** :
- `src/data/sync/engine.py` : `DuckDBSyncEngine.__init__()`

---

### Solution 3 : Activer l'extraction des aliases par défaut

**Problème** : Les aliases ne sont peut-être pas extraits

**Solution** :
1. Vérifier que `options.with_aliases` est `True` par défaut
2. Si non, l'activer dans les options par défaut
3. S'assurer que `extract_aliases()` est appelé pour chaque match

**Fichiers à modifier** :
- `src/data/sync/engine.py` : `SyncOptions` (classe de configuration)

---

### Solution 4 : Corriger la récupération des rosters depuis DuckDB

**Problème** : Les rosters ne sont pas récupérés depuis DuckDB v4

**Solution** :
1. Pour DuckDB v4, stocker les rosters dans une table dédiée (`match_rosters`)
2. Extraire les rosters depuis le JSON lors de la synchronisation
3. Stocker dans `match_rosters` avec les colonnes : `match_id`, `xuid`, `gamertag`, `team_id`, `is_bot`

**Fichiers à modifier** :
- `src/data/sync/engine.py` : Ajouter `_insert_roster_rows()`
- `src/data/sync/models.py` : Ajouter `MatchRosterRow`
- `src/data/repositories/duckdb_repo.py` : Modifier `load_match_rosters()` pour lire depuis `match_rosters`

---

### Solution 5 : Corriger l'extraction des valeurs attendues

**Problème** : `kills_expected`, `deaths_expected`, `assists_expected` sont NULL

**Solution** :
1. Vérifier que `StatPerformances` est présent dans le JSON skill
2. Ajouter des logs pour tracer l'extraction
3. Si absent, logger un warning mais continuer

**Fichiers à modifier** :
- `src/data/sync/transformers.py` : `transform_skill_stats()`

---

### Solution 6 : Stocker les données JSON brutes pour récupération ultérieure

**Problème** : Les données ne sont pas disponibles dans les tables structurées

**Solution** :
1. Stocker le JSON brut du match dans une colonne `raw_json` de `match_stats`
2. Permettre la récupération depuis `raw_json` si les données structurées sont NULL
3. Utiliser pour les rosters, les noms d'équipe, etc.

**Fichiers à modifier** :
- `src/data/sync/engine.py` : Ajouter `raw_json` à `match_stats`
- `src/data/repositories/duckdb_repo.py` : Utiliser `raw_json` comme fallback

---

## 🎯 Plan d'Action Recommandé

### Phase 1 : Diagnostic approfondi (SANS MODIFIER LE CODE)

1. ✅ Créer ce document de diagnostic
2. Vérifier les données en BDD :
   - Requête SQL pour voir les valeurs NULL dans `match_stats`
   - Vérifier si `player_match_stats` contient des données
   - Vérifier si `xuid_aliases` est peuplé
3. Vérifier les logs de synchronisation :
   - Voir si des warnings sont émis
   - Vérifier si `metadata_resolver` est initialisé
4. Comparer avec un match du commit de référence :
   - Voir comment les données étaient stockées avant
   - Identifier les différences

### Phase 2 : Corrections (APRÈS VALIDATION)

1. Corriger l'extraction des noms depuis le JSON
2. S'assurer que `metadata_resolver` est initialisé
3. Activer l'extraction des aliases par défaut
4. Corriger la récupération des rosters depuis DuckDB
5. Corriger l'extraction des valeurs attendues
6. Ajouter des logs pour tracer les problèmes futurs

---

## 📝 Notes pour l'IA

- **NE PAS MODIFIER LE CODE** pour le moment
- Ce document sert de référence pour comprendre les problèmes
- Toutes les hypothèses doivent être vérifiées avant de proposer des corrections
- Le commit de référence (`1a6115007272619985485be0f94cc69e6be5c2d2`) fonctionnait correctement
- Les changements architecturaux depuis ce commit peuvent avoir introduit des régressions

---

## 🔗 Fichiers Clés à Examiner

1. `src/data/sync/transformers.py` : Extraction des données depuis JSON
2. `src/data/sync/engine.py` : Synchronisation et insertion en BDD
3. `src/data/repositories/duckdb_repo.py` : Récupération depuis BDD
4. `src/db/loaders.py` : Récupération depuis SQLite (legacy)
5. `src/data/sync/models.py` : Modèles de données
6. `data/warehouse/metadata.duckdb` : Référentiels (playlists, maps, etc.)

---

**Prochaines étapes** : Valider les hypothèses avec des requêtes SQL et des logs avant de proposer des corrections.
