# Diagnostic : noms des joueurs sur le graphe Killer–Victime

**Date** : 2026-02-06  
**Constat** : Les noms affichés sur le graphe killer–victime ne sont pas correctement formatés, alors qu’ils le sont dans le tableau du roster.

---

## 1. Où les noms sont affichés

| Endroit | Fichier / fonction | Source des noms |
|--------|--------------------|------------------|
| **Tableau roster** | `match_view_players.py` → `render_roster_section` | `_roster_name(xu, gt)` avec `gt_map` + `BOT_MAP` + `display_name_from_xuid` |
| **Graphe killer–victime** | `match_view_players.py` → `_render_antagonist_chart` puis `antagonist_charts.py` → `plot_killer_victim_stacked_bars` | Uniquement les colonnes `killer_gamertag` et `victim_gamertag` du DataFrame, **sans résolution** |

---

## 2. Pourquoi le roster est correct

Le roster utilise une logique dédiée pour le nom d’affichage :

- **`render_roster_section`** charge `gt_map = load_match_gamertags_fn(db_path, match_id, db_key)` (mapping xuid → gamertag du match).
- Pour chaque joueur, **`_roster_name(xu, gt)`** :
  1. Si le xuid correspond à un bot (`bid(...)`) → `BOT_MAP.get(bot_key)`
  2. Sinon si le xuid est dans `gt_map` → valeur du `gt_map`
  3. Sinon si le gamertag brut est valide (non vide, pas `"?"`, pas un nombre, pas `xuid(...)`) → ce gamertag
  4. Sinon → **`display_name_from_xuid(xu_s)`** (alias / résolution via metadata)

Résultat : noms cohérents (roster officiel + alias + bots).

---

## 3. Pourquoi le graphe affiche mal les noms

- **`_render_antagonist_chart`** construit un `pairs_df` (soit via `DuckDBRepository.load_killer_victim_pairs_as_polars(match_id)`, soit en fallback via `compute_killer_victim_pairs(highlight_events)`).
- Ce DataFrame contient `killer_xuid`, `killer_gamertag`, `victim_xuid`, `victim_gamertag`.
- **`_render_antagonist_chart`** ne reçoit **pas** `load_match_gamertags_fn` ni `db_key`, donc il n’a **pas** de `gt_map` et ne peut pas appliquer la même résolution que le roster.
- **`plot_killer_victim_stacked_bars`** utilise uniquement les colonnes `killer_gamertag` et `victim_gamertag` pour les libellés (lignes 134–159 de `antagonist_charts.py`) :
  - regroupement par `killer_gamertag` / `victim_gamertag`,
  - puis `gamertags = [p["gamertag"] for p in player_data]` pour l’axe du graphique.

Donc tout ce qui est stocké ou calculé dans ces colonnes est affiché tel quel :

- En **DuckDB** : valeurs enregistrées à l’import (souvent issues du film : vide, `"?"`, ou xuid si pas de gamertag).
- En **fallback** (`compute_killer_victim_pairs`) : `killer_gt = kill_event.get("gamertag") or killer_xuid or "?"`, idem pour la victime → souvent xuid brut ou `"?"`.

Aucune utilisation de `gt_map`, `BOT_MAP` ou `display_name_from_xuid` côté graphe.

---

## 4. Incohérence avec la section Némésis / Souffre-douleur

Dans la **même page** (`match_view_players.py`), la section **Némésis / Souffre-douleur** utilise **`_display_name_from_kv(xuid, gamertag)`**, qui :

- utilise `match_gt_map` (chargé via `load_match_gamertags_fn`),
- puis en secours `display_name_from_xuid`.

Donc les noms des cartes Némésis/Souffre-douleur sont bien formatés, alors que le graphe juste en dessous ne bénéficie pas de cette logique.

---

## 5. Synthèse (cause racine)

| Élément | Roster / Némésis | Graphe killer–victime |
|--------|-------------------|------------------------|
| Accès à `gt_map` (match) | Oui | **Non** |
| Utilisation de `display_name_from_xuid` | Oui (roster + Némésis) | **Non** |
| Utilisation de `BOT_MAP` | Oui (roster) | **Non** |
| Données utilisées pour les libellés | xuid + gt résolus | **Uniquement** `killer_gamertag` / `victim_gamertag` bruts |

**Cause racine** : le graphe killer–victime n’applique aucune résolution de noms (pas de `gt_map`, pas d’alias, pas de bots). Il affiche uniquement les champs `killer_gamertag` / `victim_gamertag` tels qu’ils sont dans les paires (souvent vides, `"?"` ou xuid brut), alors que le roster et la section Némésis utilisent la même logique de résolution.

---

## 6. Piste de correction (pour plus tard)

Pour aligner l’affichage du graphe sur le roster :

1. **Passer** `load_match_gamertags_fn` et `db_key` à `_render_antagonist_chart` (comme pour `render_nemesis_section` et `render_roster_section`).
2. Dans `_render_antagonist_chart`, charger **`gt_map = load_match_gamertags_fn(db_path, match_id, db_key=db_key)`**.
3. **Avant** d’appeler `plot_killer_victim_stacked_bars`, enrichir le DataFrame (ou construire un mapping) pour remplacer les libellés par les noms résolus :
   - pour chaque `killer_xuid` / `victim_xuid`, calculer le nom d’affichage avec la même logique que `_roster_name` ou `_display_name_from_kv` (gt_map, BOT_MAP, `display_name_from_xuid`),
   - et soit ajouter des colonnes `killer_display_name` / `victim_display_name` utilisées par le graphe, soit remplacer `killer_gamertag` / `victim_gamertag` par ces noms pour l’affichage uniquement.

Cela permettra d’afficher sur le graphe les mêmes noms que dans le tableau du roster.

---

## 7. Solution détaillée (implémentation proposée)

### Principe

- **Ne pas modifier** l’API de `plot_killer_victim_stacked_bars` : le module de viz reste générique et continue à recevoir un DataFrame avec `killer_gamertag` / `victim_gamertag`.
- **Enrichir** le DataFrame côté UI avant l’appel au chart : remplacer `killer_gamertag` et `victim_gamertag` par les noms résolus (même logique que le roster). Le chart reçoit donc des libellés déjà corrects.

### Étape 1 : Appelant de `_render_antagonist_chart`

**Fichier** : `src/ui/pages/match_view_players.py`

- **Où** : dans `render_nemesis_section`, l’appel actuel à `_render_antagonist_chart` (vers les lignes 220–225).
- **Changement** : ajouter les paramètres `load_match_gamertags_fn` et `db_key` pour que le graphe puisse résoudre les noms comme le roster.

**Avant :**
```python
_render_antagonist_chart(
    match_id=match_id,
    db_path=db_path,
    xuid=xuid,
    highlight_events=he,
)
```

**Après :**
```python
_render_antagonist_chart(
    match_id=match_id,
    db_path=db_path,
    xuid=xuid,
    db_key=db_key,
    load_match_gamertags_fn=load_match_gamertags_fn,
    highlight_events=he,
)
```

Aucun autre appel à `_render_antagonist_chart` dans le projet : pas d’autre site à modifier.

---

### Étape 2 : Signature et entrée de `_render_antagonist_chart`

**Fichier** : `src/ui/pages/match_view_players.py`

- **Signature** : ajouter `db_key: tuple[int, int] | None = None` et `load_match_gamertags_fn: Callable | None = None`.
- **Début de la fonction** : si `load_match_gamertags_fn` est fourni, appeler `gt_map = load_match_gamertags_fn(db_path, match_id.strip(), db_key=db_key)`. Sinon `gt_map = None` (comportement actuel : pas de résolution).

---

### Étape 3 : Helper de résolution du nom d’affichage

**Fichier** : `src/ui/pages/match_view_players.py`

- **Où** : dans le même module, soit en haut du fichier (fonction module-level), soit locale à `_render_antagonist_chart`.
- **Rôle** : une seule fonction `_display_name_for_chart(xuid: str, gamertag: str | None, gt_map: dict | None) -> str` qui reproduit la logique de `_roster_name` / `_display_name_from_kv` :
  1. Normaliser le xuid avec `parse_xuid_input`.
  2. Si xuid de type bot (`bid(...)`), retourner `BOT_MAP.get(bot_key)` si défini.
  3. Si `gt_map` et xuid dans `gt_map`, retourner `gt_map[xuid]`.
  4. Si `gamertag` valide (non vide, pas `"?"`, pas uniquement des chiffres, ne commence pas par `xuid(`), retourner ce gamertag.
  5. Sinon appeler `display_name_from_xuid(xuid)`.
  6. Fallback `"-"` si pas de xuid.

On réutilise les imports existants : `BOT_MAP`, `parse_xuid_input`, `display_name_from_xuid`.

---

### Étape 4 : Enrichissement du DataFrame avant le chart

**Fichier** : `src/ui/pages/match_view_players.py`, dans `_render_antagonist_chart`, juste avant l’appel à `plot_killer_victim_stacked_bars`.

- **Condition** : uniquement si `pairs_df` n’est pas vide et que l’on a soit `gt_map`, soit l’envie d’appliquer quand même les alias (en pratique : toujours appliquer la résolution si `load_match_gamertags_fn` a été passé ; si pas de `gt_map`, la helper utilisera `display_name_from_xuid` et `BOT_MAP`).
- **Méthode** :
  1. Récupérer les listes des xuid/gamertag : `killer_xuid`, `killer_gamertag`, `victim_xuid`, `victim_gamertag` (déjà dans le DF).
  2. Construire deux listes Python (même longueur que le DF) :
     - `killer_display = [_display_name_for_chart(xu, gt, gt_map) for xu, gt in zip(pairs_df["killer_xuid"], pairs_df["killer_gamertag"])]`
     - `victim_display = [_display_name_for_chart(xu, gt, gt_map) for xu, gt in zip(pairs_df["victim_xuid"], pairs_df["victim_gamertag"])]`
  3. Remplacer les colonnes d’affichage :  
     `pairs_df = pairs_df.with_columns(pl.Series("killer_gamertag", killer_display), pl.Series("victim_gamertag", victim_display))`  
     (Polars : `with_columns` pour overwrite les colonnes existantes par des séries de même nom).
  4. Passer ce `pairs_df` à `plot_killer_victim_stacked_bars` comme aujourd’hui.

Résultat : le chart fait ses `group_by("killer_gamertag")` / `group_by("victim_gamertag")` sur les noms résolus ; l’axe Y et les tooltips affichent les mêmes noms que le roster.

---

### Étape 5 : Cas sans résolution (rétrocompatibilité)

- Si `_render_antagonist_chart` est appelé sans `load_match_gamertags_fn` (ou avec `None`) : `gt_map = None`. La helper `_display_name_for_chart` continuera à utiliser le gamertag brut quand il est valide, et `display_name_from_xuid` + `BOT_MAP` en secours. Comportement au moins aussi bon qu’aujourd’hui.
- Aucun changement dans `src/visualization/antagonist_charts.py` : pas de nouveau paramètre, pas de colonnes optionnelles.

---

### Résumé des fichiers à modifier

| Fichier | Modifications |
|--------|----------------|
| `src/ui/pages/match_view_players.py` | 1) Appel à `_render_antagonist_chart` dans `render_nemesis_section` : ajouter `db_key`, `load_match_gamertags_fn`. 2) Signature et corps de `_render_antagonist_chart` : ajouter params, charger `gt_map`, ajouter helper `_display_name_for_chart`, enrichir `pairs_df` puis appeler le chart. |
| `src/visualization/antagonist_charts.py` | Aucun. |

---

### Tests à prévoir

- **Manuel** : ouvrir un match qui a des highlight events / paires killer–victim ; vérifier que les noms sur le graphe correspondent à ceux du roster (y compris alias et bots).
- **Unitaire (optionnel)** : test sur `_display_name_for_chart` avec `gt_map` vide / partiel, xuid bot, xuid avec alias, pour vérifier l’ordre des priorités (bot → gt_map → gamertag valide → display_name_from_xuid → "-").
