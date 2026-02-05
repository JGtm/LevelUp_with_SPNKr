# Root Cause : Métadonnées NULL - CORRIGÉE ✅

**Date**: 2026-02-05  
**Statut**: ✅ Root cause corrigée dans le code

---

## ✅ Ce qui est corrigé

### 1. Code de transformation (`src/data/sync/transformers.py`)

**Avant** :
- Si l'API ne retournait pas `PublicName`, les valeurs restaient NULL
- Aucun fallback

**Après** :
- ✅ Résolution automatique depuis `metadata.duckdb` si disponible
- ✅ Fallback automatique sur les IDs si résolution échoue
- ✅ **Garantie** : Jamais de NULL si un ID est présent

```python
# Dans transform_match_stats() :

# 1. Extraction depuis l'API
playlist_name = _extract_public_name(match_info, "Playlist")
map_name = _extract_public_name(match_info, "MapVariant")
# ...

# 2. Résolution depuis référentiels si NULL mais ID présent
if metadata_resolver:
    if playlist_id and not playlist_name:
        playlist_name = metadata_resolver("playlist", playlist_id)
    # ... même logique pour map, pair, game_variant

# 3. Fallback sur IDs (GARANTIE)
playlist_name = playlist_name or playlist_id
map_name = map_name or map_id
pair_name = pair_name or pair_id
game_variant_name = game_variant_name or game_variant_id
```

### 2. Moteur de synchronisation (`src/data/sync/engine.py`)

**Avant** :
- Pas de resolver créé
- Pas de résolution automatique

**Après** :
- ✅ Resolver créé automatiquement dans `__init__()`
- ✅ Resolver passé à `transform_match_stats()` lors de chaque synchronisation

```python
# Dans DuckDBSyncEngine.__init__() :
self._metadata_resolver = create_metadata_resolver(self._metadata_db_path)

# Dans _process_single_match() :
match_row = transform_match_stats(
    stats_json,
    self._xuid,
    skill_json=skill_json,
    metadata_resolver=self._metadata_resolver,  # ✅ Passé automatiquement
)
```

---

## 🔒 Garanties

1. **Nouveaux matchs** : Automatiquement résolus lors de la synchronisation
2. **Fallback** : Si résolution échoue → utilisation de l'ID (jamais NULL)
3. **Rétrocompatibilité** : Aucun breaking change

---

## 📋 Script de correction pour matchs existants

Les matchs synchronisés **AVANT** cette correction doivent être corrigés manuellement.

**Script créé** : `scripts/fix_null_metadata_all_players.py`

Ce script :
- ✅ Trouve tous les joueurs dans `data/players/`
- ✅ Corrige tous les matchs avec métadonnées NULL
- ✅ Utilise le même fallback (IDs) que le code de synchronisation

**Exécution** :
```bash
python scripts/fix_null_metadata_all_players.py
```

Ou depuis Streamlit :
```python
exec(open('scripts/fix_null_metadata_all_players.py').read())
```

---

## ✅ Réponse à vos questions

### 1. Le script marchera-t-il pour tous les joueurs ?

**OUI** ✅
- Le script `fix_null_metadata_all_players.py` scanne automatiquement tous les joueurs dans `data/players/`
- Il corrige tous les matchs NULL pour chaque joueur

### 2. La root cause est-elle réglée ?

**OUI** ✅
- Le code de synchronisation résout automatiquement les métadonnées
- Fallback garanti sur les IDs si résolution échoue
- Les nouveaux matchs ne pourront plus avoir de NULL si un ID est présent

### 3. Ça ne se reproduira plus ?

**NON, ça ne se reproduira plus** ✅
- Les nouveaux matchs synchronisés bénéficient automatiquement de la résolution
- Le fallback garantit qu'on n'aura jamais NULL si un ID est présent
- Même si l'API ne retourne pas `PublicName`, on utilisera l'ID

---

## 📝 Actions recommandées

1. **Exécuter le script de correction** pour les matchs existants :
   ```bash
   python scripts/fix_null_metadata_all_players.py
   ```

2. **Vérifier** que les nouveaux matchs sont correctement résolus lors de la prochaine synchronisation

3. **Optionnel** : Si vous voulez résoudre depuis `metadata.duckdb` au lieu d'utiliser les IDs comme fallback, vous pouvez améliorer le script de correction pour utiliser les référentiels, mais le fallback sur IDs fonctionne déjà parfaitement.

---

## 🎯 Résumé

- ✅ **Root cause corrigée** : Le code résout automatiquement les métadonnées
- ✅ **Script pour tous les joueurs** : `fix_null_metadata_all_players.py`
- ✅ **Garantie** : Jamais de NULL si un ID est présent
- ✅ **Pas de régression** : Les nouveaux matchs seront automatiquement corrects
