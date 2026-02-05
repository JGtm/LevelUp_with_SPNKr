# Analyse finale - Vérification complète DuckDB v4

**Date**: 2026-02-05  
**Auteur**: Analyse approfondie  
**Contexte**: Vérification que toutes les sections utilisent bien DuckDB v4 + Investigation problème #6

---

## ✅ Vérification complète de l'utilisation de DuckDB v4

### Fonctions de chargement vérifiées

Toutes les fonctions utilisées dans l'onglet "Dernier match" utilisent bien DuckDB v4 via `_is_duckdb_v4_path()` :

| Fonction | Fichier | Ligne | Support DuckDB v4 | Status |
|----------|---------|-------|-------------------|--------|
| `cached_load_player_match_result` | `src/ui/cache.py` | 155-189 | ✅ Via `DuckDBRepository.load_match_mmr_batch()` | ✅ |
| `cached_load_match_medals_for_player` | `src/ui/cache.py` | 193-214 | ✅ Via `DuckDBRepository.load_match_medals()` | ✅ |
| `cached_load_highlight_events_for_match` | `src/ui/cache.py` | 244-304 | ✅ Direct SQL sur `highlight_events` | ✅ |
| `cached_load_match_player_gamertags` | `src/ui/cache.py` | 308-358 | ✅ Direct SQL sur `highlight_events` ou `xuid_aliases` | ✅ |
| `cached_load_match_rosters` | `src/ui/cache.py` | 218-240 | ✅ Via `DuckDBRepository.load_match_rosters()` | ✅ |
| `load_df_optimized` | `src/ui/cache.py` | 613-699 | ✅ Via `_load_matches_duckdb_v4()` → `DuckDBRepository.load_matches()` | ✅ |
| `render_participation_section` | `src/ui/pages/match_view_participation.py` | 19-88 | ✅ Via `DuckDBRepository.load_personal_score_awards_as_polars()` | ✅ |

**Conclusion** : ✅ Toutes les fonctions utilisent bien DuckDB v4.

---

## ❌ Problèmes identifiés

### 1. `load_match_players_stats()` ne supporte PAS DuckDB v4

**Fichier** : `src/db/loaders.py:1404-1428`

```python
def load_match_players_stats(db_path: str, match_id: str) -> list[MatchPlayerStats]:
    # Les DBs DuckDB v4 n'ont pas le payload JSON brut avec tous les joueurs
    if db_path.endswith(".duckdb"):
        return []  # ⚠️ Retourne toujours une liste vide
```

**Impact** :
- Utilisé dans `render_nemesis_section()` (ligne 52 de `match_view_players.py`)
- Retourne toujours `[]` pour DuckDB v4
- Le calcul des antagonistes fonctionne sans validation, mais peut être moins précis

**Solution** : Cette fonction n'est pas critique car les antagonistes peuvent être calculés sans validation. Cependant, pour améliorer la précision, on pourrait charger les stats depuis `match_stats` pour le joueur principal.

---

### 2. `has_table()` ne supporte PAS DuckDB v4

**Fichier** : `src/db/loaders.py:178-187`

```python
def has_table(db_path: str, table_name: str) -> bool:
    with get_connection(db_path) as con:
        cur = con.cursor()
        cur.execute(queries.HAS_TABLE, (table_name,))  # ⚠️ Utilise sqlite_master
        return cur.fetchone() is not None
```

**Requête SQL** (`src/db/queries.py:91-96`) :
```sql
SELECT 1
FROM sqlite_master
WHERE type='table' AND name=?
```

**Problème** :
- `sqlite_master` est spécifique à SQLite
- DuckDB utilise `information_schema.tables`
- Résultat : `has_table(db_path, "HighlightEvents")` retourne toujours `False` pour DuckDB v4
- La section antagoniste retourne immédiatement avec "Indisponible"

**Solution** : Corriger `has_table()` pour supporter DuckDB v4.

---

## 🔍 Investigation approfondie - Problème #6 : Dernier match pointe vers le 17 janvier

### Contexte
- Les filtres de date sont bien à jour (2021 jusqu'au 3 février 2026)
- Le reset du cache n'a rien donné
- Le dernier match affiché est celui du 17 janvier

### Analyse du flux de données

**1. Chargement initial** :
```python
# streamlit_app.py:466
df, db_key = load_match_dataframe(db_path, xuid, cache_buster=cache_buster)
  └─> load_df_optimized() (src/ui/cache.py:613)
       └─> _load_matches_duckdb_v4() (src/ui/cache.py:595)
            └─> DuckDBRepository.load_matches() (src/data/repositories/duckdb_repo.py:154)
                 └─> ORDER BY start_time ASC (ligne 207)
```

**2. Application des filtres** :
```python
# streamlit_app.py:508
dff = apply_filters(dff=df, filter_state=filter_state, ...)
  └─> src/app/filters_render.py:475
       └─> Filtres de date appliqués (ligne 531-533)
```

**3. Sélection du dernier match** :
```python
# src/ui/pages/last_match.py:71
last_row = dff.sort_values("start_time").iloc[-1]
```

### Hypothèses restantes

**Hypothèse 1 : Le DataFrame n'est pas trié après les filtres**
- `apply_filters()` peut retourner un DataFrame non trié
- `sort_values("start_time")` devrait corriger cela, mais vérifions

**Hypothèse 2 : Problème de conversion de dates**
- Les dates peuvent être mal converties lors du chargement
- Vérifier la conversion dans `load_df_optimized()` ligne 687-689

**Hypothèse 3 : Le dernier match dans la DB est vraiment celui du 17 janvier**
- Les matchs après le 17 janvier ne sont peut-être pas dans la DB
- Vérifier directement dans la DB avec une requête SQL

**Hypothèse 4 : Problème avec le tri dans la requête SQL**
- La requête utilise `ORDER BY start_time ASC`
- Si les dates sont NULL ou mal formatées, le tri peut être incorrect

### Tests à effectuer

1. **Vérifier le dernier match dans la DB** :
   ```sql
   SELECT match_id, start_time 
   FROM match_stats 
   ORDER BY start_time DESC 
   LIMIT 10;
   ```

2. **Vérifier le DataFrame après chargement** :
   ```python
   # Dans render_last_match_page(), ajouter :
   st.write(f"Debug: Nombre de matchs dans dff: {len(dff)}")
   st.write(f"Debug: Date min: {dff['start_time'].min()}")
   st.write(f"Debug: Date max: {dff['start_time'].max()}")
   st.write(f"Debug: Dernier match_id: {last_match_id}")
   st.write(f"Debug: Dernier start_time: {last_row.get('start_time')}")
   ```

3. **Vérifier le DataFrame avant filtres** :
   ```python
   # Dans streamlit_app.py, avant apply_filters():
   st.write(f"Debug df: Date max avant filtres: {df['start_time'].max()}")
   ```

4. **Vérifier les valeurs NULL dans start_time** :
   ```python
   # Vérifier s'il y a des valeurs NULL
   null_count = df['start_time'].isna().sum()
   st.write(f"Debug: Nombre de start_time NULL: {null_count}")
   ```

### Solution recommandée

Ajouter un debug dans `render_last_match_page()` pour afficher :
- Le nombre de matchs dans `dff`
- La date min et max dans `dff`
- Le dernier `match_id` et `start_time` sélectionné
- Comparer avec le DataFrame `df` (non filtré) pour voir la différence

---

## 📋 Résumé des problèmes

| # | Problème | Fichier | Ligne | Impact | Priorité |
|---|----------|---------|-------|--------|----------|
| 1 | `has_table()` ne supporte pas DuckDB v4 | `src/db/loaders.py` | 178-187 | Section antagoniste vide | 🔴 Critique |
| 2 | `load_match_players_stats()` retourne `[]` pour DuckDB v4 | `src/db/loaders.py` | 1427-1428 | Validation antagonistes impossible | 🟡 Important |
| 3 | Liste de joueurs corrompue | `src/data/repositories/duckdb_repo.py` | 668-759 | Gamertags non nettoyés | 🔴 Critique |
| 4 | Données MMR null | `src/ui/cache.py` | 155-189 | MMR non affichées | 🔴 Critique |
| 5 | Ratio mal positionné | `src/ui/pages/match_view_charts.py` | 118-200 | Graphique confus | 🟢 Amélioration |
| 6 | Radar participation au max | `src/ui/components/radar_chart.py` | 290-383 | Normalisation incorrecte | 🟡 Important |
| 7 | Dernier match incorrect | `src/ui/pages/last_match.py` | 71 | Match du 17 janvier au lieu du 3 février | 🔴 Critique |

---

## 🔧 Fichiers à modifier (priorité)

### 🔴 Priorité 1 - Critique
1. **`src/db/loaders.py`** (ligne 178-187) : Corriger `has_table()` pour DuckDB v4
2. **`src/ui/pages/match_view_players.py`** (ligne 37) : Adapter la vérification de table pour DuckDB v4
3. **`src/data/repositories/duckdb_repo.py`** (ligne 668-759) : Nettoyer les gamertags dans `load_match_rosters()`
4. **`src/ui/cache.py`** (ligne 155-189) : Utiliser valeurs depuis `row` pour `kills`/`deaths`/`assists`
5. **`src/ui/pages/last_match.py`** (ligne 71) : Ajouter debug pour investiguer le problème #6

### 🟡 Priorité 2 - Important
6. **`src/ui/components/radar_chart.py`** (ligne 290-383) : Utiliser max historique pour normalisation
7. **`src/db/loaders.py`** (ligne 1427-1428) : Implémenter `load_match_players_stats()` pour DuckDB v4 (optionnel)

### 🟢 Priorité 3 - Amélioration
8. **`src/ui/pages/match_view_charts.py`** (ligne 118-200) : Repositionner le ratio

---

## ✅ Confirmation : Toutes les sections utilisent bien DuckDB v4

**Conclusion** : Toutes les fonctions de chargement utilisent bien DuckDB v4 via `_is_duckdb_v4_path()` et les repositories appropriés. Le problème vient de :
1. Fonctions utilitaires (`has_table()`, `load_match_players_stats()`) qui ne supportent pas DuckDB v4
2. Problèmes de données (gamertags corrompus, MMR null)
3. Problème de tri/sélection pour le dernier match (à investiguer avec debug)
