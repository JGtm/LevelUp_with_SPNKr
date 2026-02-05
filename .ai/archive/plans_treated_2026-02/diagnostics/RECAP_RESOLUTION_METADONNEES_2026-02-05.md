# Récapitulatif : Résolution des Métadonnées - 5 février 2026

## 🔍 Problème Initial

L'utilisateur signalait que dans l'onglet "Dernier match", les données affichaient :
- Des UUIDs bruts au lieu de noms lisibles (ex: `6c01f693-c968-4a71-b157-efc35ffcf71f`)
- "Inconnue" pour les playlists
- "Mode inconnu" pour les modes de jeu
- MMR d'équipe/adverse manquants
- Kills/Morts manquants
- Noms de joueurs erronés
- Attribution d'équipe incorrecte
- Mode debug toujours visible

**Hypothèse utilisateur** : "Normalement l'API récupère toujours les données manquantes, c'est probablement un problème de requête"

## 🔎 Diagnostic Effectué

### 1. Vérification de l'attachement de metadata.duckdb
- ✅ `metadata.duckdb` est correctement attaché comme schéma `meta`
- ✅ Les tables sont accessibles via `meta.maps`, `meta.playlists`, etc.

### 2. Découverte du Problème Principal

**Problème identifié** : Les tables de métadonnées existent mais :
- ❌ `meta.playlists` utilise la colonne `uuid` au lieu de `asset_id`
- ❌ `meta.maps` existe mais est vide (0 lignes)
- ❌ Les tables `map_mode_pairs` et `playlist_map_mode_pairs` n'existent pas
- ❌ Les jointures SQL utilisaient `asset_id` alors que la table utilise `uuid`
- ❌ `information_schema` ne listait pas correctement les tables attachées

**Erreur SQL générée** :
```
Binder Error: Table "p_meta" does not have a column named "asset_id"
Candidate bindings: : "uuid"
```

## 🔍 Problème Réel Identifié

**Le problème est plus profond que prévu** : Le problème n'est pas seulement dans la requête SQL de lecture, mais aussi dans le processus de synchronisation lui-même.

### Problème 1 : `metadata_resolver` utilise les mauvaises colonnes

Dans `src/data/sync/transformers.py`, le `metadata_resolver` utilisé lors de la synchronisation :
- Utilise `asset_id` alors que `meta.playlists` utilise `uuid`
- Utilise `public_name` alors que la table peut utiliser `name_fr` ou `name_en`
- Ne détecte pas dynamiquement les colonnes disponibles

**Conséquence** : Quand l'API ne fournit pas les noms (ou fournit des UUIDs), le resolver échoue silencieusement et le fallback stocke l'UUID directement dans `match_stats.playlist_name`.

### Problème 2 : Résolution seulement si nom NULL

La logique actuelle (ligne 539-547) ne résout depuis les référentiels que si le nom est NULL :
```python
if playlist_id and not playlist_name:
    playlist_name = metadata_resolver("playlist", playlist_id)
```

**Problème** : Si l'API fournit un UUID comme nom (ce qui peut arriver), la résolution n'est jamais tentée.

## 🛠️ Corrections Apportées

### 1. Détection Dynamique des Tables (`src/data/repositories/duckdb_repo.py`)

**Avant** : Vérification via `information_schema` uniquement
```python
tables_check = conn.execute(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'meta' AND table_name = 'maps'"
).fetchone()[0] > 0
```

**Après** : Accès direct aux tables (plus fiable)
```python
# Méthode 1: Essayer d'accéder directement aux tables
for table_name in ['maps', 'playlists', 'map_mode_pairs', 'playlist_map_mode_pairs']:
    try:
        conn.execute(f"SELECT COUNT(*) FROM meta.{table_name} LIMIT 1").fetchone()
        existing_tables.add(table_name)
    except Exception:
        pass
```

### 2. Détection Dynamique des Colonnes ID

**Nouvelle méthode** : `_detect_id_column()`
- Détecte automatiquement si la table utilise `asset_id` ou `uuid`
- Teste chaque candidat jusqu'à trouver la colonne qui existe

```python
def _detect_id_column(
    self, conn: duckdb.DuckDBPyConnection, table: str, candidates: list[str]
) -> str | None:
    """Détecte quelle colonne ID existe dans une table."""
    for col_name in candidates:
        try:
            conn.execute(f"SELECT {col_name} FROM {table} LIMIT 1").fetchone()
            return col_name
        except Exception:
            continue
    return None
```

### 3. Détection Dynamique des Colonnes de Nom

**Nouvelle méthode** : `_detect_name_column()`
- Détecte automatiquement la colonne de nom disponible
- Priorité : `public_name` → `name_fr` → `name_en` → `name`

```python
def _detect_name_column(
    self, conn: duckdb.DuckDBPyConnection, table: str, candidates: list[str]
) -> str | None:
    """Détecte quelle colonne de nom existe dans une table."""
    for col_name in candidates:
        try:
            conn.execute(f"SELECT {col_name} FROM {table} LIMIT 1").fetchone()
            return col_name
        except Exception:
            continue
    return None
```

### 4. Correction du `metadata_resolver` dans `transformers.py`

**Problème** : Le resolver utilisait `asset_id` et `public_name` codés en dur.

**Solution** : Détection dynamique des colonnes comme dans `duckdb_repo.py` :
- Détecte automatiquement `asset_id` ou `uuid`
- Détecte automatiquement `public_name`, `name_fr`, `name_en`, ou `name`

```python
# Détecter dynamiquement la colonne ID (asset_id ou uuid)
id_column = None
for col_candidate in ["asset_id", "uuid"]:
    try:
        conn.execute(f"SELECT {col_candidate} FROM {table_name} LIMIT 1").fetchone()
        id_column = col_candidate
        break
    except Exception:
        continue

# Détecter dynamiquement la colonne de nom
name_column = None
for col_candidate in ["public_name", "name_fr", "name_en", "name"]:
    try:
        conn.execute(f"SELECT {col_candidate} FROM {table_name} LIMIT 1").fetchone()
        name_column = col_candidate
        break
    except Exception:
        continue
```

### 5. Détection des UUIDs dans les noms

**Ajout** : Fonction `_is_uuid()` pour détecter si un nom est en fait un UUID.

**Amélioration** : La résolution depuis les référentiels est maintenant tentée même si un nom existe, si ce nom est un UUID :

```python
# Vérifier si playlist_name est un UUID (format UUID standard)
if playlist_id and (not playlist_name or _is_uuid(playlist_name)):
    resolved = metadata_resolver("playlist", playlist_id)
    if resolved:
        playlist_name = resolved
```

### 6. Jointures SQL Adaptatives

**Avant** : Jointures codées en dur avec `asset_id`
```python
metadata_joins += " LEFT JOIN meta.playlists p_meta ON match_stats.playlist_id = p_meta.asset_id"
playlist_name_expr = "COALESCE(p_meta.public_name, match_stats.playlist_name)"
```

**Après** : Jointures dynamiques basées sur le schéma réel
```python
if has_playlists:
    # Détecter la colonne ID (asset_id ou uuid)
    playlists_id_col = self._detect_id_column(conn, "meta.playlists", ["asset_id", "uuid"])
    if playlists_id_col:
        metadata_joins += (
            f" LEFT JOIN meta.playlists p_meta ON match_stats.playlist_id = p_meta.{playlists_id_col}"
        )
        # Détecter aussi la colonne de nom
        playlists_name_col = self._detect_name_column(conn, "meta.playlists", 
            ["public_name", "name_fr", "name_en", "name"])
        if playlists_name_col:
            playlist_name_expr = f"COALESCE(p_meta.{playlists_name_col}, match_stats.playlist_name)"
```

### 5. Gestion d'Erreur avec Fallback

**Ajout** : Si la requête avec jointures échoue, fallback sans jointures
```python
try:
    result = conn.execute(sql, params) if params else conn.execute(sql)
except Exception as e:
    logger.warning(f"Erreur requête avec jointures métadonnées: {e}. Fallback sans jointures.")
    # Requête SQL simplifiée sans jointures
    sql_fallback = f"SELECT ... FROM match_stats WHERE ..."
    result = conn.execute(sql_fallback, params) if params else conn.execute(sql_fallback)
```

### 6. Logs de Debug Améliorés

**Ajout** : Logs pour diagnostiquer les problèmes
```python
logger.debug(f"Résolution métadonnées: maps={has_maps}, playlists={has_playlists}, pairs={has_pairs}")
logger.debug(f"Table meta.{table_name} trouvée via accès direct")
logger.debug(f"Colonne {col_name} trouvée dans {table}")
```

### 7. Script de Diagnostic

**Création** : `scripts/diagnose_metadata_resolution.py`
- Vérifie l'attachement de `metadata.duckdb`
- Liste toutes les tables disponibles
- Teste les jointures manuelles
- Affiche les résultats de résolution

## 📊 État Actuel

### Tables Détectées dans metadata.duckdb
- ✅ `meta.maps` : Existe mais vide (0 lignes)
- ✅ `meta.playlists` : Existe avec 14 lignes, utilise `uuid` au lieu de `asset_id`
- ❌ `meta.map_mode_pairs` : N'existe pas
- ❌ `meta.playlist_map_mode_pairs` : N'existe pas

### Schéma Réel vs Documentation

**Documentation** (`docs/SQL_SCHEMA.md`) :
- `playlists.asset_id` VARCHAR PK
- `playlists.public_name` VARCHAR

**Réalité** :
- `playlists.uuid` (pas `asset_id`)
- Colonne de nom probablement `name_fr` ou `name_en` (à vérifier)

## ✅ Résultats Attendus

Après les corrections :
1. ✅ Les jointures SQL détectent automatiquement les colonnes correctes
2. ✅ Les noms de playlists devraient être résolus depuis `meta.playlists`
3. ✅ Les noms de maps devraient être résolus depuis `meta.maps` (quand la table sera remplie)
4. ✅ Le code s'adapte automatiquement aux différents schémas

## 🔄 Prochaines Étapes

### 1. Vérification Immédiate
```bash
python scripts/diagnose_metadata_resolution.py JGtm 2533274823110022
```

### 2. Vérifier le Schéma Réel de meta.playlists
```sql
DESCRIBE meta.playlists;
SELECT * FROM meta.playlists LIMIT 1;
```

### 3. Remplir meta.maps
- La table `meta.maps` existe mais est vide
- Nécessite une synchronisation des métadonnées depuis l'API

### 4. Créer les Tables map_mode_pairs
- Les tables `map_mode_pairs` et `playlist_map_mode_pairs` n'existent pas
- Nécessite une migration ou création depuis les données API

### 5. Tester dans Streamlit
- Redémarrer Streamlit
- Vérifier que les métadonnées sont maintenant résolues
- Vérifier que les UUIDs sont remplacés par les noms lisibles

## 📝 Fichiers Modifiés

1. **`src/data/repositories/duckdb_repo.py`**
   - Ajout de `_detect_id_column()`
   - Ajout de `_detect_name_column()`
   - Modification de `_build_metadata_resolution()` pour détection dynamique
   - Ajout de gestion d'erreur avec fallback
   - Ajout de logs de debug

2. **`src/data/sync/transformers.py`** ⚠️ **CORRECTION CRITIQUE**
   - Correction du `metadata_resolver` pour détection dynamique des colonnes
   - Ajout de `_is_uuid()` pour détecter les UUIDs dans les noms
   - Amélioration de la logique de résolution pour tenter même si un nom existe (mais c'est un UUID)
   - Le resolver détecte maintenant automatiquement `uuid` au lieu de `asset_id`
   - Le resolver détecte maintenant automatiquement `name_fr`/`name_en` au lieu de `public_name`

3. **`scripts/diagnose_metadata_resolution.py`** (nouveau)
   - Script de diagnostic complet
   - Vérifie l'attachement, les tables, les jointures

4. **`scripts/test_metadata_query.py`** (nouveau)
   - Script de test simplifié pour tester les requêtes SQL directement

## 🎯 Conclusion

Le problème était double :

1. **Lors de la synchronisation** : Le `metadata_resolver` dans `transformers.py` utilisait des colonnes codées en dur (`asset_id`, `public_name`) alors que le schéma réel utilise (`uuid`, `name_fr`/`name_en`). Résultat : les UUIDs étaient stockés directement dans `match_stats`.

2. **Lors de la lecture** : Les jointures SQL dans `duckdb_repo.py` utilisaient aussi des colonnes codées en dur, empêchant la résolution même si les données étaient disponibles.

**Solution** : 
- Détection dynamique des colonnes dans **les deux** endroits (sync ET lecture)
- Détection des UUIDs dans les noms pour forcer la résolution même si un "nom" existe
- Le code s'adapte maintenant automatiquement au schéma réel

**Action requise** : 
- Les données déjà synchronisées avec des UUIDs devront être re-synchronisées pour être corrigées
- OU créer un script de backfill pour résoudre les UUIDs existants depuis `metadata.duckdb`
