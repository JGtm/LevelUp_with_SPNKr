# Analyse des problèmes - Onglet "Dernier match"

**Date**: 2026-02-05  
**Auteur**: Analyse automatique  
**Contexte**: Problèmes multiples sur l'onglet "Dernier match" après migration DuckDB v4

---

## Résumé exécutif

L'onglet "Dernier match" présente plusieurs problèmes critiques liés à la migration vers DuckDB v4 :

1. ✅ **Les données proviennent bien de DuckDB v4** - Le flux de chargement est correct
2. ❌ **Liste de joueurs corrompue** - Caractères étranges dans les noms
3. ❌ **Données MMR null** - MMR d'équipe/adverse non chargées
4. ❌ **Ratio mal positionné** - Graphique F/D/A avec ratio au-dessus des barres
5. ❌ **Radar de participation au max** - Normalisation incorrecte
6. ❌ **Dernier match incorrect** - Pointe vers le 17 janvier au lieu de la dernière entrée (filtres de date probablement actifs)
7. ❌ **Section antagoniste vide** - `has_table()` ne fonctionne pas pour DuckDB v4 (utilise `sqlite_master` au lieu de `information_schema`)

---

## 1. Vérification du flux de données DuckDB v4

### ✅ Confirmation : Les données proviennent bien de DuckDB v4

**Flux de chargement** :
```
streamlit_app.py:466
  └─> load_match_dataframe()
       └─> load_df_optimized() (src/ui/cache.py:613)
            └─> _load_matches_duckdb_v4() (src/ui/cache.py:595)
                 └─> DuckDBRepository.load_matches() (src/data/repositories/duckdb_repo.py:154)
                      └─> SELECT FROM match_stats ORDER BY start_time ASC
```

**Conclusion** : Le DataFrame `dff` est bien chargé depuis DuckDB v4 via `DuckDBRepository`.

**Problème identifié** : L'ordre de tri est `ASC` (croissant), donc le dernier match devrait être `iloc[-1]` après tri. Cependant, si les données ne sont pas triées correctement dans le DataFrame final, cela peut expliquer le problème #6.

---

## 2. Liste de joueurs corrompue - Caractères étranges

### Problème observé
```
Mon équipe — Cobra (2)	Équipe adverse — Adversaires (14)
JGtm	0�����������ā
ă	arLemon79���
—	bengp�������
```

### Analyse du code

**Fonction responsable** : `render_roster_section()` dans `src/ui/pages/match_view_players.py:223`

**Chargement des rosters** :
```python
# src/ui/cache.py:218
cached_load_match_rosters()
  └─> DuckDBRepository.load_match_rosters() (src/data/repositories/duckdb_repo.py:668)
```

**Problème identifié dans `DuckDBRepository.load_match_rosters()`** :

```python:668:759:src/data/repositories/duckdb_repo.py
# Ligne 703-711 : Extraction depuis highlight_events
players_result = conn.execute(
    """
    SELECT DISTINCT xuid, gamertag
    FROM highlight_events
    WHERE match_id = ? AND xuid IS NOT NULL AND xuid != ''
    ORDER BY gamertag NULLS LAST, xuid
    """,
    [match_id],
).fetchall()
```

**Problèmes** :
1. **Pas de nettoyage des caractères** : Les gamertags extraits depuis `highlight_events` peuvent contenir des caractères non-UTF8 ou des séquences binaires
2. **Pas de validation** : Aucune validation que `gamertag` est une chaîne valide
3. **Pas de fallback** : Si `gamertag` est NULL ou invalide, on utilise directement `xuid` sans nettoyage

**Comparaison avec l'ancien code** (`src/db/loaders.py:308`) :
- L'ancien code utilisait `MatchStats.Players[]` qui contenait des données JSON déjà parsées et validées
- Le nouveau code utilise `highlight_events` qui peut contenir des données brutes non nettoyées

**Solution recommandée** :
1. Ajouter une fonction de nettoyage des gamertags (comme `_clean_name()` dans `match_view_players.py:134`)
2. Valider et nettoyer les gamertags lors de l'extraction depuis `highlight_events`
3. Utiliser `display_name_from_xuid()` comme fallback si le gamertag est invalide

---

## 3. Données MMR null

### Problème observé
- MMR d'équipe : `-`
- MMR adverse : `-`
- Écart MMR : `-`
- Réel vs attendu : Frags `-`, Morts `-`

### Analyse du code

**Fonction responsable** : `cached_load_player_match_result()` dans `src/ui/cache.py:155`

```python:155:189:src/ui/cache.py
def cached_load_player_match_result(...):
    if _is_duckdb_v4_path(db_path):
        repo = DuckDBRepository(db_path, str(xuid).strip())
        mmr_data = repo.load_match_mmr_batch([match_id])
        if match_id in mmr_data:
            team_mmr, enemy_mmr = mmr_data[match_id]
            return {
                "team_mmr": team_mmr,  # Peut être None
                "enemy_mmr": enemy_mmr,  # Peut être None
                "kills": {"count": None, "expected": None, "stddev": None},
                "deaths": {"count": None, "expected": None, "stddev": None},
                "assists": {"count": None, "expected": None, "stddev": None},
            }
```

**Problèmes identifiés** :

1. **MMR peut être NULL dans la DB** : `load_match_mmr_batch()` peut retourner `(None, None)` si les colonnes `team_mmr` ou `enemy_mmr` sont NULL dans `match_stats`

2. **Pas de valeurs réelles pour kills/deaths/assists** : Le code retourne toujours `None` pour `count`, alors que ces valeurs sont disponibles dans `row` (le DataFrame du match)

3. **Affichage dans `match_view_charts.py:28-43`** :
   ```python
   team_mmr = pm.get("team_mmr")  # Peut être None
   enemy_mmr = pm.get("enemy_mmr")  # Peut être None
   os_card("MMR d'équipe", f"{team_mmr:.1f}" if team_mmr is not None else "-")
   ```

**Vérification de la table `match_stats`** :
- Les colonnes `team_mmr` et `enemy_mmr` existent dans le schéma (ligne 203-204 de `duckdb_repo.py`)
- Mais elles peuvent être NULL si les données n'ont pas été synchronisées avec ces valeurs

**Solution recommandée** :
1. Vérifier pourquoi `team_mmr` et `enemy_mmr` sont NULL dans la DB
2. Utiliser les valeurs de `row` (DataFrame) pour `kills`, `deaths`, `assists` au lieu de retourner `None`
3. Ajouter un fallback pour récupérer les MMR depuis `row` si disponibles

---

## 4. Ratio mal positionné sur le graphique F/D/A

### Problème observé
Le ratio est affiché au-dessus des barres au lieu d'être sur un axe secondaire séparé.

### Analyse du code

**Fonction responsable** : `render_expected_vs_actual()` dans `src/ui/pages/match_view_charts.py:21`

```python:118:200:src/ui/pages/match_view_charts.py
exp_fig = make_subplots(specs=[[{"secondary_y": True}]])

# Barres F/D/A (axe principal)
exp_fig.add_trace(go.Bar(...), secondary_y=False)
exp_fig.add_trace(go.Bar(...), secondary_y=False)

# Ratio (axe secondaire)
exp_fig.add_trace(
    go.Scatter(
        x=labels,
        y=[real_ratio_f] * len(labels),  # ⚠️ Problème ici
        mode="lines+markers",
        name="Ratio réel",
    ),
    secondary_y=True,
)
```

**Problème identifié** :
- Le ratio est une valeur unique (ex: 1.5) mais elle est répétée pour chaque label `["F", "D", "A"]`
- Cela crée une ligne horizontale qui peut apparaître au-dessus des barres si l'échelle n'est pas correcte
- L'axe secondaire (`secondary_y=True`) devrait avoir une échelle différente, mais si les valeurs sont similaires, la ligne peut chevaucher les barres

**Solution recommandée** :
1. **Option 1** : Afficher le ratio comme annotation textuelle au lieu d'une ligne
2. **Option 2** : Ajuster l'échelle de l'axe secondaire pour qu'il soit visible mais ne chevauche pas
3. **Option 3** : Afficher le ratio dans une zone séparée (KPI card) plutôt que sur le graphique

**Recommandation data analyst** :
- Le ratio K/D/A est une métrique agrégée qui n'a pas besoin d'être superposée aux barres individuelles
- Mieux vaut l'afficher comme :
  - Une annotation textuelle au-dessus du graphique
  - Un indicateur séparé (KPI card)
  - Ou un graphique séparé si on veut comparer avec d'autres matchs

---

## 5. Graphe profil de participation tout au max

### Problème observé
Toutes les valeurs du radar de participation sont au maximum (100%).

### Analyse du code

**Fonction responsable** : `create_participation_radar()` dans `src/ui/components/radar_chart.py:290`

```python:332:357:src/ui/components/radar_chart.py
# Calculer les max pour normalisation (valeurs absolues)
max_kill = max(abs(p.get("kill_score") or 0) for p in participation_data) or 1
max_assist = max(abs(p.get("assist_score") or 0) for p in participation_data) or 1
max_obj = max(abs(p.get("objective_score") or 0) for p in participation_data) or 1
max_penalty = max(abs(p.get("penalty_score") or 0) for p in participation_data) or 1

# Normaliser (0-1)
kill_norm = kill_raw / max_kill if max_kill else 0
assist_norm = assist_raw / max_assist if max_assist else 0
obj_norm = obj_raw / max_obj if max_obj else 0
survival_norm = 1 - (abs(penalty_raw) / max_penalty) if max_penalty else 1
```

**Problème identifié** :
- La normalisation est faite **par axe individuellement** : chaque valeur est divisée par le max de **son propre axe**
- Si on n'a qu'**un seul match** dans `participation_data`, alors :
  - `max_kill = kill_raw` (du match)
  - `kill_norm = kill_raw / kill_raw = 1.0` (100%)
- Résultat : **toutes les valeurs sont normalisées à 1.0** car chaque valeur est divisée par elle-même

**Solution recommandée** :
1. **Option 1** : Utiliser des seuils fixes par catégorie au lieu de normaliser par le max
   - Ex: `kill_norm = min(kill_raw / 1000, 1.0)` (1000 pts = max théorique)
2. **Option 2** : Normaliser par le max historique de tous les matchs du joueur
   - Charger les max historiques depuis la DB
   - Utiliser ces max pour normaliser
3. **Option 3** : Ne pas normaliser si un seul match (afficher les valeurs brutes avec échelle adaptée)

**Recommandation** : Option 2 (max historique) pour avoir une comparaison contextuelle.

---

## 6. Dernier match pointe vers le 17 janvier

### Problème observé
Le dernier match affiché est celui du 17 janvier au lieu de la dernière entrée dans DuckDB v4.  
**Note** : Le reset du cache n'a rien donné, l'erreur doit être ailleurs.

### Analyse approfondie du code

**Fonction responsable** : `render_last_match_page()` dans `src/ui/pages/last_match.py:21`

```python:71:72:src/ui/pages/last_match.py
last_row = dff.sort_values("start_time").iloc[-1]
last_match_id = str(last_row.get("match_id", "")).strip()
```

**Flux de données** :
```
streamlit_app.py:466
  └─> load_match_dataframe()
       └─> load_df_optimized() (src/ui/cache.py:613)
            └─> _load_matches_duckdb_v4() (src/ui/cache.py:595)
                 └─> DuckDBRepository.load_matches() (src/data/repositories/duckdb_repo.py:154)
                      └─> ORDER BY start_time ASC (ligne 207)

streamlit_app.py:508
  └─> apply_filters(dff, filter_state, ...) (src/app/filters_render.py:475)
       └─> Filtres de date appliqués (ligne 531-533)

streamlit_app.py:562
  └─> render_last_match_page_fn(dff=dff, ...)
       └─> dff.sort_values("start_time").iloc[-1]
```

**Problèmes identifiés** :

1. **Filtres de date appliqués par défaut** :
   ```python:531:533:src/app/filters_render.py
   if filter_state.filter_mode == "Période":
       mask = (dff["date"] >= filter_state.start_d) & (dff["date"] <= filter_state.end_d)
       dff = dff.loc[mask].copy()
   ```
   - Si `filter_mode == "Période"` et qu'une plage de dates est sélectionnée qui exclut les matchs récents, alors `dff` ne contiendra que les matchs dans cette plage
   - Le "dernier match" sera donc le dernier de cette plage, pas le dernier absolu

2. **Tri dans la requête SQL** :
   ```python:207:src/data/repositories/duckdb_repo.py
   ORDER BY start_time ASC
   ```
   - Le tri est ASC (croissant), donc le dernier élément de la liste retournée est bien le plus récent
   - ✅ Cette partie est correcte

3. **Tri dans le DataFrame** :
   ```python:71:src/ui/pages/last_match.py
   last_row = dff.sort_values("start_time").iloc[-1]
   ```
   - Le tri est croissant (par défaut), donc `iloc[-1]` prend bien le dernier (le plus récent)
   - ✅ Cette partie est correcte aussi

4. **Mais** : Si `dff` est filtré par date et que la plage se termine au 17 janvier, alors le dernier match sera celui du 17 janvier

**Hypothèses principales** :

1. **Filtre de date actif** : Un filtre de période est appliqué qui limite les matchs jusqu'au 17 janvier
   - Vérifier dans la sidebar si un filtre de date est actif
   - Vérifier `filter_state.filter_mode` et `filter_state.start_d` / `filter_state.end_d`

2. **Données non synchronisées** : Les matchs après le 17 janvier ne sont pas dans la DB
   - Vérifier directement dans la DB :
     ```sql
     SELECT match_id, start_time 
     FROM match_stats 
     ORDER BY start_time DESC 
     LIMIT 10;
     ```

3. **Problème de conversion de date** : Les dates peuvent être mal converties lors du chargement
   - Vérifier la conversion dans `load_df_optimized()` ligne 687-689 :
     ```python
     df["start_time"] = (
         pd.to_datetime(df["start_time"], utc=True).dt.tz_convert(PARIS_TZ_NAME).dt.tz_localize(None)
     )
     ```

**Solution recommandée** :

1. **Vérifier les filtres actifs** :
   - Ajouter un debug pour afficher `filter_state.filter_mode` et les dates de filtre
   - Vérifier si un filtre de période est appliqué par défaut

2. **Vérifier les données dans la DB** :
   ```python
   # Dans render_last_match_page(), ajouter :
   st.write(f"Debug: Nombre de matchs dans dff: {len(dff)}")
   st.write(f"Debug: Date min: {dff['start_time'].min()}")
   st.write(f"Debug: Date max: {dff['start_time'].max()}")
   st.write(f"Debug: Dernier match_id: {last_match_id}")
   ```

3. **Vérifier le DataFrame complet** :
   - Comparer `df` (non filtré) avec `dff` (filtré) pour voir la différence
   - Vérifier si le problème vient des filtres ou des données

4. **Solution temporaire** : Utiliser `df` (non filtré) au lieu de `dff` pour déterminer le dernier match :
   ```python
   # Dans render_last_match_page(), utiliser df au lieu de dff
   last_row = df.sort_values("start_time").iloc[-1]
   ```
   Mais cela ignore les filtres, ce qui peut ne pas être souhaité.

---

## 7. Section antagoniste complètement vide

### Problème observé
La section "Antagonistes du match" (Némésis/Souffre-douleur) est complètement vide.

### Analyse du code

**Fonction responsable** : `render_nemesis_section()` dans `src/ui/pages/match_view_players.py:25`

```python:37:42:src/ui/pages/match_view_players.py
if not (match_id and match_id.strip() and has_table(db_path, "HighlightEvents")):
    st.caption(
        "Indisponible: la DB ne contient pas les highlight events. "
        "Si tu utilises une DB SPNKr, relance l'import avec `--with-highlight-events`."
    )
    return
```

**Problèmes identifiés** :

1. **`has_table()` ne fonctionne pas pour DuckDB v4** :
   - La fonction `has_table()` dans `src/db/loaders.py:178` utilise la requête SQLite :
     ```sql
     SELECT 1 FROM sqlite_master WHERE type='table' AND name=?
     ```
   - Cette requête ne fonctionne **pas** pour DuckDB qui utilise `information_schema.tables`
   - Résultat : `has_table(db_path, "HighlightEvents")` retourne toujours `False` pour DuckDB v4
   - La section antagoniste retourne immédiatement avec le message "Indisponible"

2. **Nom de table incorrect** :
   - Le code cherche `"HighlightEvents"` (PascalCase)
   - Mais DuckDB v4 utilise `highlight_events` (snake_case)
   - Même si `has_table()` fonctionnait, elle ne trouverait pas la table

3. **`load_match_players_stats()` retourne toujours `[]` pour DuckDB v4** :
   ```python:1426:1428:src/db/loaders.py
   # Les DBs DuckDB v4 n'ont pas le payload JSON brut avec tous les joueurs
   if db_path.endswith(".duckdb"):
       return []
   ```
   - Cette fonction est utilisée pour valider les antagonistes (ligne 52 de `match_view_players.py`)
   - Sans stats officielles, le calcul des antagonistes peut être moins précis mais devrait quand même fonctionner

**Solution recommandée** :
1. **Corriger `has_table()`** pour supporter DuckDB v4 :
   ```python
   def has_table(db_path: str, table_name: str) -> bool:
       if db_path.endswith(".duckdb"):
           # DuckDB utilise information_schema
           conn = duckdb.connect(db_path, read_only=True)
           result = conn.execute(
               "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_name = ?",
               [table_name.lower()]  # DuckDB utilise snake_case
           ).fetchone()
           conn.close()
           return result is not None
       else:
           # SQLite legacy
           ...
   ```

2. **Adapter le nom de table** : Chercher `highlight_events` au lieu de `HighlightEvents` pour DuckDB v4

3. **Vérifier que les highlight events sont bien chargés** : S'assurer que `cached_load_highlight_events_for_match()` retourne bien des données

---

## Recommandations prioritaires

### 🔴 Priorité 1 - Critique
1. **Corriger `has_table()` pour DuckDB v4** : Utiliser `information_schema` au lieu de `sqlite_master`
2. **Corriger le chargement des rosters** : Nettoyer les gamertags depuis `highlight_events`
3. **Corriger les données MMR** : Utiliser les valeurs depuis `row` si disponibles dans la DB
4. **Corriger la section antagoniste** : Adapter le nom de table et la vérification pour DuckDB v4

### 🟡 Priorité 2 - Important
5. **Corriger le radar de participation** : Utiliser max historique au lieu de normaliser par soi-même
6. **Vérifier le dernier match** : S'assurer que les données sont à jour et le cache invalidé

### 🟢 Priorité 3 - Amélioration
7. **Améliorer le graphique F/D/A** : Repositionner le ratio ou l'afficher séparément

---

## Fichiers à modifier

1. **`src/db/loaders.py`** (ligne 178-187) : `has_table()` - Ajouter support DuckDB v4
2. **`src/ui/pages/match_view_players.py`** (ligne 37) : Adapter le nom de table pour DuckDB v4
3. **`src/data/repositories/duckdb_repo.py`** (ligne 668-759) : `load_match_rosters()` - Nettoyer les gamertags
4. **`src/ui/cache.py`** (ligne 155-189) : `cached_load_player_match_result()` - Utiliser valeurs depuis `row`
5. **`src/ui/components/radar_chart.py`** (ligne 290-383) : `create_participation_radar()` - Utiliser max historique
6. **`src/ui/pages/match_view_charts.py`** (ligne 118-200) : `render_expected_vs_actual()` - Repositionner le ratio
7. **`src/ui/pages/last_match.py`** (ligne 71) : Ajouter debug pour vérifier les filtres
8. **`src/app/filters_render.py`** (ligne 475-535) : Vérifier les filtres par défaut

---

## Tests à effectuer

1. ✅ Vérifier que `dff` contient bien les données DuckDB v4
2. ✅ Vérifier que les rosters sont chargés depuis `highlight_events`
3. ✅ Vérifier que `team_mmr` et `enemy_mmr` sont présents dans `match_stats`
4. ✅ Vérifier que le dernier match dans `dff` correspond au dernier dans la DB
5. ✅ Tester avec un match récent pour vérifier que le cache est bien invalidé

---

## ✅ Vérification complète - Toutes les sections utilisent DuckDB v4

**Date de vérification** : 2026-02-05

### Résultat de la vérification

Toutes les fonctions de chargement utilisées dans l'onglet "Dernier match" utilisent bien DuckDB v4 :

| Fonction | Support DuckDB v4 | Status |
|----------|-------------------|--------|
| `cached_load_player_match_result` | ✅ Via `DuckDBRepository` | ✅ |
| `cached_load_match_medals_for_player` | ✅ Via `DuckDBRepository` | ✅ |
| `cached_load_highlight_events_for_match` | ✅ Direct SQL sur `highlight_events` | ✅ |
| `cached_load_match_player_gamertags` | ✅ Direct SQL sur `highlight_events`/`xuid_aliases` | ✅ |
| `cached_load_match_rosters` | ✅ Via `DuckDBRepository` | ✅ |
| `load_df_optimized` | ✅ Via `DuckDBRepository.load_matches()` | ✅ |
| `render_participation_section` | ✅ Via `DuckDBRepository` | ✅ |

**Conclusion** : ✅ Toutes les fonctions utilisent bien DuckDB v4.

### Fonctions utilitaires qui ne supportent PAS DuckDB v4

| Fonction | Problème | Impact |
|----------|----------|--------|
| `has_table()` | Utilise `sqlite_master` au lieu de `information_schema` | Section antagoniste vide |
| `load_match_players_stats()` | Retourne toujours `[]` pour DuckDB v4 | Validation antagonistes impossible |

Ces fonctions doivent être corrigées pour supporter DuckDB v4.

---

## 🔍 Investigation approfondie - Problème #6 (mise à jour)

### Contexte confirmé
- ✅ Les filtres de date sont bien à jour (2021 jusqu'au 3 février 2026)
- ✅ Le reset du cache n'a rien donné
- ❌ Le dernier match affiché est celui du 17 janvier

### Hypothèses restantes

1. **Le DataFrame n'est pas trié après les filtres** : `apply_filters()` peut retourner un DataFrame non trié, mais `sort_values("start_time")` devrait corriger cela.

2. **Problème de conversion de dates** : Les dates peuvent être mal converties lors du chargement (ligne 687-689 de `cache.py`).

3. **Le dernier match dans la DB est vraiment celui du 17 janvier** : Les matchs après le 17 janvier ne sont peut-être pas dans la DB.

4. **Problème avec le tri dans la requête SQL** : Si les dates sont NULL ou mal formatées, le tri peut être incorrect.

### Tests recommandés

Ajouter un debug dans `render_last_match_page()` pour afficher :
```python
st.write(f"Debug: Nombre de matchs dans dff: {len(dff)}")
st.write(f"Debug: Date min: {dff['start_time'].min()}")
st.write(f"Debug: Date max: {dff['start_time'].max()}")
st.write(f"Debug: Dernier match_id: {last_match_id}")
st.write(f"Debug: Dernier start_time: {last_row.get('start_time')}")
```

Vérifier directement dans la DB :
```sql
SELECT match_id, start_time 
FROM match_stats 
ORDER BY start_time DESC 
LIMIT 10;
```
