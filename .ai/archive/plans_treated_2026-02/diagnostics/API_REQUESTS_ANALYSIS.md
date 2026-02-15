# Analyse des Requêtes API - Données Manquantes

**Date** : 2026-02-05  
**Priorité** : HAUTE  
**Status** : 🔍 EN ANALYSE

---

## 🔴 Problème Identifié : Requêtes API Incomplètes

### Hypothèse

Les endpoints Discovery UGC ne sont **PAS appelés** dans `DuckDBSyncEngine._process_single_match()`, ce qui explique pourquoi les noms des cartes, modes et playlists sont NULL.

---

## Analyse du Code Actuel

### Endpoints Appelés dans `_process_single_match()`

**Fichier** : `src/data/sync/engine.py` (lignes 614-719)

```python
async def _process_single_match(self, client, match_id, options):
    # ✅ Appelé
    stats_json = await client.get_match_stats(match_id)
    
    # ✅ Appelé si with_skill=True
    if options.with_skill and xuids:
        skill_json = await client.get_skill_stats(match_id, xuids)
    
    # ✅ Appelé si with_highlight_events=True
    if options.with_highlight_events:
        highlight_events = await client.get_highlight_events(match_id)
    
    # ❌ JAMAIS APPELÉ !
    # client.get_asset() pour Discovery UGC
```

### Endpoints Disponibles mais Non Utilisés

**Fichier** : `src/data/sync/api_client.py` (lignes 513-548)

```python
async def get_asset(self, asset_type, asset_id, version_id):
    """Récupère un asset (map, playlist, variant)."""
    if asset_type == "Maps":
        resp = await self.client.discovery_ugc.get_map(asset_id, version_id)
    elif asset_type == "Playlists":
        resp = await self.client.discovery_ugc.get_playlist(asset_id, version_id)
    elif asset_type == "PlaylistMapModePairs":
        resp = await self.client.discovery_ugc.get_map_mode_pair(asset_id, version_id)
    elif asset_type == "GameVariants":
        resp = await self.client.discovery_ugc.get_ugc_game_variant(asset_id, version_id)
    return await resp.json()
```

**Problème** : Cette méthode existe mais n'est **jamais appelée** dans `_process_single_match()` !

---

## Comparaison avec le Script Legacy

**Fichier** : `scripts/spnkr_import_db.py` (lignes 564-641)

Le script legacy **appelle bien** les endpoints Discovery UGC :

```python
async def _import_assets_for_match_info(mi, client, con, ...):
    # MapVariant
    map_aid, map_vid = _asset_ref(mi, "MapVariant")
    if map_aid and map_vid:
        resp = await client.discovery_ugc.get_map(map_aid, map_vid)
        obj = await resp.json()
        # Stocke dans la DB
    
    # Playlist
    pl_aid, pl_vid = _asset_ref(mi, "Playlist")
    if pl_aid and pl_vid:
        resp = await client.discovery_ugc.get_playlist(pl_aid, pl_vid)
        obj = await resp.json()
        # Stocke dans la DB
    
    # PlaylistMapModePair
    mp_aid, mp_vid = _asset_ref(mi, "PlaylistMapModePair")
    if mp_aid and mp_vid:
        resp = await client.discovery_ugc.get_map_mode_pair(mp_aid, mp_vid)
        obj = await resp.json()
        # Stocke dans la DB
    
    # UgcGameVariant
    gv_aid, gv_vid = _asset_ref(mi, "UgcGameVariant")
    if gv_aid and gv_vid:
        resp = await client.discovery_ugc.get_ugc_game_variant(gv_aid, gv_vid)
        obj = await resp.json()
        # Stocke dans la DB
```

**Conclusion** : Le script legacy récupère bien les métadonnées depuis Discovery UGC, mais `DuckDBSyncEngine` ne le fait pas !

---

## Options de Synchronisation

**Fichier** : `src/data/sync/models.py` (lignes 21-44)

```python
@dataclass
class SyncOptions:
    with_highlight_events: bool = True
    with_skill: bool = True
    with_aliases: bool = True
    with_assets: bool = True  # ✅ Option existe
    ...
```

**Problème** : `with_assets=True` par défaut, mais cette option n'est **jamais vérifiée** dans `_process_single_match()` !

---

## Extraction des Noms Actuelle

**Fichier** : `src/data/sync/transformers.py` (lignes 575-613)

```python
# Extraire les identifiants d'assets
playlist_id = _extract_asset_id(match_info, "Playlist")
playlist_name = _extract_public_name(match_info, "Playlist")  # ❌ Peut être NULL

# Résolution depuis référentiels si les noms sont NULL
if metadata_resolver:
    if playlist_id and (not playlist_name or _is_uuid(playlist_name)):
        resolved = metadata_resolver("playlist", playlist_id)  # ❌ Peut échouer si metadata.duckdb n'est pas à jour
        if resolved:
            playlist_name = resolved

# Fallback sur les IDs si les noms sont toujours NULL
playlist_name = playlist_name or playlist_id  # ❌ Utilise l'ID au lieu du nom
```

**Problème** : Si `PublicName` n'est pas dans le JSON du match ET que `metadata_resolver` échoue, on utilise l'ID au lieu du nom.

---

## Solution Proposée

### Option 1 : Appeler Discovery UGC dans `_process_single_match()`

```python
async def _process_single_match(self, client, match_id, options):
    # ... récupération stats_json ...
    
    # Récupérer les assets si demandé
    if options.with_assets:
        match_info = stats_json.get("MatchInfo", {})
        
        # Extraire les asset IDs et version IDs
        playlist_ref = match_info.get("Playlist", {})
        playlist_id = playlist_ref.get("AssetId")
        playlist_version = playlist_ref.get("VersionId")
        
        if playlist_id and playlist_version:
            playlist_asset = await client.get_asset("Playlists", playlist_id, playlist_version)
            if playlist_asset:
                playlist_name = playlist_asset.get("PublicName")
                # Utiliser playlist_name au lieu de celui du JSON
        
        # Répéter pour MapVariant, PlaylistMapModePair, UgcGameVariant
```

### Option 2 : Mettre à jour `metadata.duckdb` avant la synchronisation

- Appeler Discovery UGC pour tous les assets référencés
- Stocker dans `metadata.duckdb`
- Utiliser `metadata_resolver` pour résoudre les noms

---

## Vérifications à Faire

1. **Vérifier si `PublicName` est présent dans le JSON du match** :
   - Examiner un JSON réel de `get_match_stats()`
   - Vérifier si `MatchInfo.Playlist.PublicName` existe

2. **Vérifier si `metadata.duckdb` est à jour** :
   - Vérifier si les assets sont présents dans `metadata.duckdb`
   - Vérifier si `metadata_resolver` fonctionne correctement

3. **Vérifier si `with_assets` est utilisé** :
   - Chercher dans `_process_single_match()` si `options.with_assets` est vérifié
   - Vérifier si les appels Discovery UGC sont faits

---

## Impact

**Si les endpoints Discovery UGC ne sont pas appelés** :
- ❌ Les noms des cartes, modes et playlists ne peuvent pas être récupérés
- ❌ On dépend uniquement de `PublicName` dans le JSON du match (peut être absent)
- ❌ On dépend de `metadata.duckdb` qui peut ne pas être à jour
- ❌ Les noms restent NULL ou sont remplacés par les IDs

**C'est probablement la cause racine du problème !**

---

## Prochaines Étapes

1. ✅ Documenter le problème (ce fichier)
2. Vérifier si `PublicName` est présent dans les JSON réels
3. Vérifier si `metadata.duckdb` contient les assets
4. Proposer une correction pour appeler Discovery UGC dans `_process_single_match()`
