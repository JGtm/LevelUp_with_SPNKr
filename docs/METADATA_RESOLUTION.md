# Résolution des Métadonnées - Guide Complet

> **Date** : 2026-02-06  
> Ce document explique comment fonctionne la résolution des noms d'assets (playlists, maps, pairs, game variants) dans LevelUp.

---

## Vue d'ensemble

Les colonnes `playlist_name`, `map_name`, `pair_name`, `game_variant_name` dans `match_stats` sont remplies via un système de résolution en cascade :

1. **Discovery UGC API** (priorité 1) : Enrichissement en temps réel lors de la synchronisation
2. **metadata.duckdb** (priorité 2) : Cache local des métadonnées
3. **asset_id** (priorité 3) : Fallback sur l'ID si aucun nom n'est trouvé

---

## Architecture

### Composants principaux

| Composant | Fichier | Rôle |
|-----------|---------|------|
| **MetadataResolver** | `src/data/sync/metadata_resolver.py` | Résout les noms depuis metadata.duckdb |
| **enrich_match_info_with_assets** | `src/data/sync/api_client.py` | Enrichit MatchInfo avec PublicName depuis Discovery UGC |
| **transform_match_stats** | `src/data/sync/transformers.py` | Transforme JSON → MatchStatsRow avec résolution métadonnées |
| **populate_metadata_from_discovery** | `scripts/populate_metadata_from_discovery.py` | Peuple metadata.duckdb depuis Discovery UGC |
| **backfill_metadata** | `scripts/backfill_metadata.py` | Backfill les métadonnées dans match_stats existants |

### Flux de données

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYNCHRONISATION                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. API SPNKr → get_match_stats(match_id)                        │
│    Retourne JSON avec MatchInfo (AssetId, VersionId)           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. enrich_match_info_with_assets()                              │
│    Appelle Discovery UGC pour chaque asset                       │
│    Ajoute PublicName dans MatchInfo[AssetType]                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. transform_match_stats()                                     │
│    Extrait PublicName depuis MatchInfo                          │
│    Si NULL → utilise metadata_resolver                           │
│    Si NULL → fallback sur asset_id                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Insertion dans match_stats                                   │
│    Colonnes playlist_name, map_name, etc. remplies             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Utilisation

### 1. Créer/populer metadata.duckdb

La première étape est de créer `metadata.duckdb` et de le peupler avec les métadonnées depuis Discovery UGC :

```bash
# Peupler depuis tous les joueurs
python scripts/populate_metadata_from_discovery.py --all-players

# Peupler depuis un seul joueur (plus rapide pour tester)
python scripts/populate_metadata_from_discovery.py

# Dry-run pour voir ce qui sera fait
python scripts/populate_metadata_from_discovery.py --all-players --dry-run
```

**Ce que fait le script** :
1. Parcourt les `match_stats` de tous les joueurs (ou du premier trouvé)
2. Extrait les asset IDs uniques (playlist_id, map_id, pair_id, game_variant_id)
3. Appelle Discovery UGC API pour chaque asset
4. Stocke les PublicName dans `metadata.duckdb`

**Résultat** : `data/warehouse/metadata.duckdb` créé avec les tables :
- `playlists` (asset_id, version_id, public_name, ...)
- `maps` (asset_id, version_id, public_name, ...)
- `playlist_map_mode_pairs` (asset_id, version_id, public_name, ...)
- `game_variants` (asset_id, version_id, public_name, ...)

### 2. Synchronisation avec métadonnées

Lors de la synchronisation normale, les métadonnées sont automatiquement résolues :

```python
from src.data.sync.engine import DuckDBSyncEngine, SyncOptions

engine = DuckDBSyncEngine(
    player_db_path="data/players/JGtm/stats.duckdb",
    xuid="2533274792546123",
    gamertag="JGtm",
)

# Sync avec assets (par défaut: with_assets=True)
result = await engine.sync_delta()
# ou
result = await engine.sync_full(SyncOptions(max_matches=100, with_assets=True))
```

**Ce qui se passe** :
1. `enrich_match_info_with_assets()` est appelé automatiquement si `options.with_assets=True`
2. Les PublicName sont ajoutés dans MatchInfo depuis Discovery UGC
3. `transform_match_stats()` extrait les PublicName et les stocke dans `match_stats`

### 3. Backfill des métadonnées existantes

Si vous avez déjà des matchs synchronisés sans métadonnées, utilisez le script de backfill :

```bash
# Backfill pour un joueur spécifique
python scripts/backfill_metadata.py --player JGtm

# Backfill pour tous les joueurs
python scripts/backfill_metadata.py --all-players

# Limiter le nombre de matchs traités
python scripts/backfill_metadata.py --player JGtm --limit 100

# Dry-run pour voir ce qui sera fait
python scripts/backfill_metadata.py --player JGtm --dry-run
```

**Ce que fait le script** :
1. Trouve tous les matchs avec `playlist_name IS NULL` ou autres colonnes NULL
2. Récupère le JSON du match depuis l'API SPNKr
3. Appelle `enrich_match_info_with_assets()` pour enrichir avec Discovery UGC
4. Utilise `metadata_resolver` si Discovery UGC ne retourne pas de nom
5. Met à jour les colonnes dans `match_stats`

---

## Résolution en cascade

### Priorité 1 : PublicName dans MatchInfo (Discovery UGC)

Lors de la synchronisation, `enrich_match_info_with_assets()` est appelé automatiquement :

```python
# Dans engine.py, ligne 672-673
if options.with_assets:
    await enrich_match_info_with_assets(client, stats_json)
```

Cette fonction :
- Extrait les AssetId et VersionId depuis MatchInfo
- Appelle `client.discovery_ugc.get_*()` pour chaque asset
- Ajoute `PublicName` dans `MatchInfo[AssetType]`

**Avantage** : Données toujours à jour depuis l'API officielle.

### Priorité 2 : metadata.duckdb (cache local)

Si `PublicName` n'est pas présent dans MatchInfo (ou est un UUID), `transform_match_stats()` utilise `metadata_resolver` :

```python
# Dans transformers.py, ligne 590-610
if metadata_resolver:
    if playlist_id and (not playlist_name or _is_uuid(playlist_name)):
        resolved = metadata_resolver("playlist", playlist_id)
        if resolved:
            playlist_name = resolved
```

**Avantage** : Rapide, pas besoin d'appeler l'API à chaque fois.

### Priorité 3 : asset_id (fallback)

Si aucun nom n'est trouvé, on utilise l'asset_id comme fallback :

```python
# Dans transformers.py, ligne 613-616
playlist_name = playlist_name or playlist_id
map_name = map_name or map_id
pair_name = pair_name or pair_id
game_variant_name = game_variant_name or game_variant_id
```

**Avantage** : Garantit qu'une valeur est toujours présente (même si c'est un UUID).

---

## Schéma metadata.duckdb

### Table `playlists`

```sql
CREATE TABLE playlists (
    asset_id VARCHAR NOT NULL,
    version_id VARCHAR NOT NULL,
    public_name VARCHAR,
    description VARCHAR,
    is_ranked BOOLEAN DEFAULT FALSE,
    category VARCHAR,
    raw_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, version_id)
);
```

### Table `maps`

```sql
CREATE TABLE maps (
    asset_id VARCHAR NOT NULL,
    version_id VARCHAR NOT NULL,
    public_name VARCHAR,
    description VARCHAR,
    thumbnail_path VARCHAR,
    raw_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, version_id)
);
```

### Table `playlist_map_mode_pairs`

```sql
CREATE TABLE playlist_map_mode_pairs (
    asset_id VARCHAR NOT NULL,
    version_id VARCHAR NOT NULL,
    public_name VARCHAR,
    description VARCHAR,
    raw_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, version_id)
);
```

### Table `game_variants`

```sql
CREATE TABLE game_variants (
    asset_id VARCHAR NOT NULL,
    version_id VARCHAR NOT NULL,
    public_name VARCHAR,
    description VARCHAR,
    category VARCHAR,
    raw_json JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, version_id)
);
```

---

## Troubleshooting

### Problème : Les noms sont toujours NULL

**Causes possibles** :
1. `metadata.duckdb` n'existe pas ou est vide
2. `options.with_assets=False` lors de la synchronisation
3. Discovery UGC API ne retourne pas de PublicName (asset supprimé)

**Solutions** :
```bash
# 1. Créer/populer metadata.duckdb
python scripts/populate_metadata_from_discovery.py --all-players

# 2. Vérifier que with_assets=True (par défaut)
# Dans votre code, assurez-vous que :
result = await engine.sync_full(SyncOptions(with_assets=True))

# 3. Backfill les matchs existants
python scripts/backfill_metadata.py --player JGtm
```

### Problème : Les noms sont des UUIDs

**Cause** : Les métadonnées n'ont pas été résolues et le fallback sur asset_id a été utilisé.

**Solution** :
```bash
# Backfill pour résoudre les UUIDs
python scripts/backfill_metadata.py --player JGtm
```

### Problème : metadata.duckdb n'est pas utilisé

**Cause** : Le chemin vers `metadata.duckdb` n'est pas correct ou la base n'existe pas.

**Vérification** :
```python
from src.data.sync.metadata_resolver import MetadataResolver
from pathlib import Path

metadata_path = Path("data/warehouse/metadata.duckdb")
resolver = MetadataResolver(metadata_path)

if resolver._conn is None:
    print("metadata.duckdb non trouvé ou inaccessible")
else:
    print("metadata.duckdb OK")
    name = resolver.resolve("playlist", "playlist-123")
    print(f"Résolution test: {name}")
```

### Problème : Discovery UGC API retourne 404

**Cause** : L'asset a été supprimé ou n'existe plus dans l'API.

**Solution** : Le système utilise automatiquement le fallback sur `metadata.duckdb` ou `asset_id`. Pas d'action nécessaire, mais vous pouvez mettre à jour `metadata.duckdb` périodiquement.

---

## Tests

Les tests sont disponibles dans :
- `tests/test_metadata_resolver.py` : Tests unitaires pour MetadataResolver
- `tests/test_transformers_metadata.py` : Tests pour transform_match_stats avec métadonnées
- `tests/integration/test_metadata_resolution.py` : Tests d'intégration end-to-end

Exécuter les tests :
```bash
# Tous les tests métadonnées
pytest tests/test_metadata_resolver.py tests/test_transformers_metadata.py tests/integration/test_metadata_resolution.py -v

# Un fichier spécifique
pytest tests/test_metadata_resolver.py -v
```

---

## Maintenance

### Mise à jour périodique de metadata.duckdb

Il est recommandé de mettre à jour `metadata.duckdb` périodiquement pour capturer les nouveaux assets :

```bash
# Mettre à jour depuis tous les joueurs (recommandé mensuellement)
python scripts/populate_metadata_from_discovery.py --all-players
```

### Vérification de l'intégrité

Pour vérifier que les métadonnées sont bien résolues :

```sql
-- Compter les matchs avec noms NULL
SELECT 
    COUNT(*) FILTER (WHERE playlist_name IS NULL) as null_playlists,
    COUNT(*) FILTER (WHERE map_name IS NULL) as null_maps,
    COUNT(*) FILTER (WHERE pair_name IS NULL) as null_pairs,
    COUNT(*) FILTER (WHERE game_variant_name IS NULL) as null_variants,
    COUNT(*) as total_matches
FROM match_stats;

-- Vérifier les UUIDs (fallback)
SELECT 
    COUNT(*) FILTER (WHERE playlist_name LIKE '%-%-%-%-%') as uuid_playlists,
    COUNT(*) FILTER (WHERE map_name LIKE '%-%-%-%-%') as uuid_maps
FROM match_stats;
```

---

## Références

- **Discovery UGC API** : Documentation SPNKr (endpoints `discovery_ugc.get_*()`)
- **Schéma SQL** : `docs/SQL_SCHEMA.md`
- **Architecture sync** : `docs/SYNC_GUIDE.md`
- **Code source** :
  - `src/data/sync/metadata_resolver.py`
  - `src/data/sync/api_client.py` (fonction `enrich_match_info_with_assets`)
  - `src/data/sync/transformers.py` (fonction `transform_match_stats`)

---

*Dernière mise à jour : 2026-02-06*
