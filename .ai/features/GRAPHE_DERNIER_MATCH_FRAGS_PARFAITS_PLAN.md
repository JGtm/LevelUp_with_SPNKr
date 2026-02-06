# Planification : Frags parfaits sur le graphe « Folie meurtrière / Tirs à la tête » (Dernier match)

> Document d’analyse et de planification uniquement. Aucune modification de code dans cette phase.

---

## 1. Contexte et objectif

- **Onglet** : Dernier match (ou page Match après recherche).
- **Graphe concerné** : « Folie meurtrière / Tirs à la tête » (barres groupées : Réel + optionnellement Moyenne historique).
- **Objectif** : ajouter une troisième métrique sur ce graphe :
  1. **Nombre de frags parfaits du match** : comptage des médailles « Frag parfait » (Perfect) reçues pendant le match.
  2. **Moyenne historique de médailles Frag parfait par match** : même logique que pour Folie meurtrière et Tirs à la tête (moyenne par catégorie de mode, si ≥ 10 matchs).

---

## 2. Analyse du graphe actuel

### 2.1 Emplacement dans le code

| Élément | Fichier | Fonction / zone |
|--------|---------|------------------|
| Point d’entrée (Dernier match) | `src/ui/pages/last_match.py` | `render_last_match_page` → `render_match_view_fn(...)` |
| Vue match | `src/ui/pages/match_view.py` | `render_match_view` → `render_expected_vs_actual(row, pm, colors, df_full=df_full)` |
| Section graphiques Réel vs Attendu | `src/ui/pages/match_view_charts.py` | `render_expected_vs_actual` |
| Graphe Folie meurtrière / Tirs à la tête | `src/ui/pages/match_view_charts.py` | `_render_spree_headshots(row, df_full=df_full)` |

### 2.2 Données utilisées aujourd’hui

- **Réel (match courant)** :
  - `row["max_killing_spree"]` → barre « Folie meurtrière (max) »
  - `row["headshot_kills"]` → barre « Tirs à la tête »
- **Moyenne historique** (si `df_full` fourni et `len(df_full) >= 10`) :
  - `compute_mode_category_averages(df_full, mode_category)` dans `src/analysis/stats.py`
  - Retourne notamment : `avg_max_killing_spree`, `avg_headshot_kills`, `match_count`
  - Catégorie de mode : `extract_mode_category(row["pair_name"])` (Assassin, Fiesta, BTB, Ranked, Firefight, Other)

### 2.3 Structure actuelle du graphe

- **Plotly** : `go.Figure()` avec `barmode="group"`.
- **Labels X** : `["Folie meurtrière (max)", "Tirs à la tête"]`.
- **Deux traces Bar** :
  1. « Réel » : 2 barres (couleurs violet / cyan, opacité 0.85).
  2. « Moyenne hist. {mode_category} (N matchs) » : 2 barres en motif pointillé (opacité 0.35), affichée seulement si `match_count >= 10`.
- **Layout** : hauteur 260, légende en bas (horizontale), `rangemode="tozero"`.

Les valeurs **max_killing_spree** et **headshot_kills** viennent de `match_stats` (ou du DataFrame dérivé). Les **frags parfaits** ne sont pas dans `match_stats` : ils proviennent de la table **médailles**.

---

## 3. Source des données « Frag parfait »

### 3.1 Définition

- **Médaille** : « Parfait » (FR) / « Perfect » (EN).
- **ID** : `1512363953` (déjà utilisé dans le projet).
- **Règle** : un kill sans avoir pris de dégâts = une médaille Perfect.

### 3.2 Stockage et API existante

| Élément | Détail |
|--------|--------|
| Table | `medals_earned` (DuckDB par joueur : `data/players/{gamertag}/stats.duckdb`) |
| Colonnes utilisées | `match_id`, `medal_name_id`, `count` (ou équivalent) |
| Repository | `src/data/repositories/duckdb_repo.py` |
| Méthode | `count_perfect_kills_by_match(match_ids: list[str]) -> dict[str, int]` |
| Implémentation | Délègue à `count_medal_by_match(match_ids, medal_name_id=1512363953)` |

Cette méthode est déjà utilisée sur l’onglet **Séries temporelles** pour le graphe « Folie meurtrière / Tirs à la tête / Précision / Frags parfaits » (`src/ui/pages/timeseries.py` : chargement de `perfect_counts` via le repo, puis `plot_spree_headshots_accuracy(dff, perfect_counts=perfect_counts)`).

### 3.3 Ce qu’il faut pour le Dernier match

- **Valeur « Réel »** : nombre de médailles Perfect pour le **match courant** uniquement.
  - Appel : `count_perfect_kills_by_match([match_id])` → `perfect_count_current = result.get(match_id, 0)`.
- **Moyenne historique** : moyenne du nombre de médailles Perfect par match sur les matchs de la **même catégorie de mode** que le match courant.
  - Filtrer `df_full` par `extract_mode_category(pair_name) == mode_category` (comme pour spree/headshots).
  - Récupérer la liste des `match_id` de ce sous-ensemble.
  - Appel : `count_perfect_kills_by_match(match_ids)` → pour chaque match, puis `avg_perfect = sum(counts) / len(match_ids)` (avec `len(match_ids) >= 10` pour afficher la barre « moyenne hist. », comme aujourd’hui).

La moyenne historique des frags parfaits **ne peut pas** être dérivée de `compute_mode_category_averages` en l’état : cette fonction travaille sur le DataFrame des matchs (colonnes `match_stats`), pas sur `medals_earned`. Il faut donc utiliser le **repository DuckDB** avec les `match_id` filtrés par catégorie.

---

## 4. Incohérence actuelle : pas d’accès au repository dans le graphe

- `_render_spree_headshots(row, df_full=df_full)` ne reçoit **ni** `db_path` **ni** `xuid` **ni** une instance de repository.
- `render_expected_vs_actual(row, pm, colors, df_full=df_full)` est appelée depuis `match_view.py` qui, lui, dispose de `db_path` et `xuid`.

Donc, pour pouvoir appeler `count_perfect_kills_by_match` depuis le graphe (pour le match courant et pour les matchs de la catégorie), il faut **faire remonter** soit `db_path` + `xuid`, soit une instance de repository (ou un dict pré-calculé), jusqu’à `_render_spree_headshots`.

---

## 5. Planification des changements (sans toucher au code)

### 5.1 Données

1. **Médaille** : continuer à utiliser l’ID `1512363953` (Perfect / Frag parfait). Aucun changement de schéma.
2. **Valeur du match courant** : obtenue via `DuckDBRepository(db_path, xuid).count_perfect_kills_by_match([match_id])` → `count = result.get(match_id, 0)`.
3. **Moyenne historique** :
   - Filtrer `df_full` par `extract_mode_category(pair_name) == mode_category` (comme pour les autres moyennes).
   - Extraire les `match_id` de ce sous-ensemble.
   - Si `len(match_ids) >= 10` : appeler `count_perfect_kills_by_match(match_ids)`, puis `avg = sum(counts.values()) / len(match_ids)` (ou équivalent en gérant les matchs absents du dict → count 0).
   - Afficher la barre « Moyenne hist. » pour les frags parfaits seulement si cette condition est respectée (aligné sur le seuil actuel).

### 5.2 UI / Graphe

1. **Labels X** : passer de 2 à 3 :  
   `["Folie meurtrière (max)", "Tirs à la tête", "Frags parfaits"]`.
2. **Couleur** : choisir une couleur cohérente avec la charte (ex. vert comme dans `plot_spree_headshots_accuracy` pour « Frags parfaits », ou une couleur dédiée documentée dans `HALO_COLORS` si pertinent).
3. **Traces « Réel »** : ajouter une 3e barre avec la valeur `perfect_count_current` (0 si pas de médailles ou pas de données).
4. **Traces « Moyenne hist. »** : ajouter une 3e barre avec la valeur `avg_perfect` (même condition d’affichage que pour les deux autres : `match_count >= 10`).
5. **Hovertemplate** : adapter pour la 3e barre (libellé « Frags parfaits » + valeur réelle ou moyenne selon la trace).
6. **Cas sans données médailles** : si le repository n’a pas la table `medals_earned` ou si l’appel échoue, afficher 0 pour le match courant et ne pas afficher la moyenne historique pour les frags parfaits (ou afficher 0), sans casser le graphe.

### 5.3 Signatures et flux

1. **`render_expected_vs_actual`**  
   - Ajouter des paramètres optionnels : `db_path: str | None = None`, `xuid: str | None = None` (ou un seul paramètre `repo` si on préfère injecter le repository).  
   - Les passer à `_render_spree_headshots`.

2. **`_render_spree_headshots`**  
   - Ajouter des paramètres optionnels : `db_path: str | None = None`, `xuid: str | None = None` (ou `repo`).  
   - Si `db_path` et `xuid` (ou `repo`) sont fournis :  
     - Instancier le repository si besoin.  
     - Récupérer `match_id` depuis `row`.  
     - Appeler `count_perfect_kills_by_match([match_id])` pour le match courant.  
     - Si `df_full` est fourni et filtre par catégorie donne au moins 10 matchs : appeler `count_perfect_kills_by_match(match_ids)` et calculer la moyenne.  
   - Étendre les listes de valeurs et labels comme ci-dessus (3 barres, 3 labels).

3. **`match_view.py`**  
   - À l’appel de `render_expected_vs_actual(..., df_full=df_full)`, ajouter `db_path=db_path` et `xuid=xuid` (ou le repo si vous choisissez cette variante).

Aucun changement nécessaire dans `last_match.py` : il délègue déjà tout à `render_match_view_fn`, qui reçoit déjà `db_path` et `xuid`.

### 5.4 Analyse / Stats (optionnel)

- **`compute_mode_category_averages`** : ne pas l’enrichir avec une moyenne de frags parfaits pour l’instant, car cette moyenne nécessite des appels à la table `medals_earned` (par match), pas seulement au DataFrame des matchs. Garder le calcul de la moyenne historique des frags parfaits **local** à `_render_spree_headshots` (ou à une petite fonction helper dédiée qui prend le repo + `df_full` + `mode_category`).

### 5.5 Règles projet

- Pas de Pandas en nouveau code métier : si des calculs sur séries sont nécessaires, utiliser Polars ; à la frontière Streamlit/Plotly, conversion au dernier moment si besoin.
- Pas de SQLite : tout reste sur DuckDB (repository existant).
- Référentiel de couleurs : `HALO_COLORS` dans `src/config`.

### 5.6 Tests (à prévoir lors de l’implémentation)

- Test unitaire ou d’intégration : avec une base de test contenant `medals_earned` et des médailles 1512363953 pour quelques matchs, vérifier que la valeur du match courant et la moyenne historique sont correctes.
- Test de non-régression : graphe avec seulement 2 barres (spree, headshots) si `db_path`/`xuid` non fournis ou si `medals_earned` absente (comportement actuel conservé pour les 2 premières métriques).

---

## 6. Résumé des fichiers concernés (au moment de coder)

| Fichier | Action prévue |
|---------|----------------|
| `src/ui/pages/match_view_charts.py` | Étendre `_render_spree_headshots` (3e barre, récupération perfect count + moyenne via repo) ; étendre `render_expected_vs_actual` (signature + passage db_path/xuid). |
| `src/ui/pages/match_view.py` | Passer `db_path` et `xuid` à `render_expected_vs_actual`. |
| `src/data/repositories/duckdb_repo.py` | Aucun changement (déjà `count_perfect_kills_by_match`). |
| `src/analysis/stats.py` | Aucun changement obligatoire (moyenne frags parfaits calculée côté UI/charts). |

---

## 7. Référence : graphe Séries temporelles

Le graphe « Folie meurtrière / Tirs à la tête / Précision / Frags parfaits » dans `src/visualization/timeseries.py` (`plot_spree_headshots_accuracy`) et son appel dans `src/ui/pages/timeseries.py` servent de référence : même source de vérité (`count_perfect_kills_by_match`), même médaille 1512363953. Rester cohérent avec les libellés (« Frags parfaits ») et le comportement en cas d’absence de données (0, pas d’erreur).

---

*Document rédigé pour une implémentation ultérieure, sans modification du code à ce stade.*
