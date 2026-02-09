# Plan : graphe Killer–Victime (une ligne par joueur, barre empilée par victime, tri par rang)

**Date** : 2026-02-06  
**Contexte** : Tables mises à jour + backfill → rangs disponibles pour tous les joueurs via `match_participants`. Le graphe doit afficher une ligne par tueur, barre empilée (segments = victimes, plus grande victime en premier), lignes triées par rang.

---

## 1. Vérification : rangs exploitables pour tous les joueurs

### 1.1 Source des rangs

| Élément | Statut |
|--------|--------|
| **Table** | `match_participants` (colonnes `rank`, `score` ; optionnellement `kills`, `deaths`, `assists` après backfill) |
| **Migration** | `_ensure_match_participants_rank_score()` dans le sync engine (colonnes rank, score ajoutées si absentes) |
| **Remplissage** | Sync + backfill via `extract_participants()` → `player.get("Rank")` (API) ou rang calculé par tri score |
| **Chargement** | `load_match_players_stats(db_path, match_id)` → pour DuckDB appelle `_load_match_players_stats_from_duckdb()` |

### 1.2 Ce que fait le loader DuckDB

- **Fichier** : `src/db/loaders.py`, `_load_match_players_stats_from_duckdb()`.
- Vérifie la présence des colonnes `rank`, `score` (et optionnellement `kills`, `deaths`, `assists`).
- Requête : `SELECT xuid, gamertag, team_id, rank, score[, kills, deaths, assists] FROM match_participants WHERE match_id = ? ORDER BY rank ASC NULLS LAST`.
- Retourne une liste de **`MatchPlayerStats`** avec `rank` (int, 1 = meilleur) pour chaque joueur. Si `rank` absent en base, fallback `rank=999` ou tri par `rank_idx` (ordre de lecture).

**Conclusion** : Après backfill, `load_match_players_stats(db_path, match_id)` fournit bien un rang par joueur pour le match. On peut construire `rank_by_xuid = {s.xuid: s.rank for s in official_stats}` pour trier les lignes du graphe.

---

## 2. Comportement cible du graphe

- **Axe Y** : un libellé par **tueur** (joueur qui fait les kills), une ligne par joueur.
- **Axe X** : nombre de kills (total par ligne = somme des segments).
- **Barre empilée** : pour chaque tueur, une seule barre horizontale découpée en **segments** :
  - **1er segment (gauche)** = la victime qu’il a le plus tuée (nombre de kills sur cette victime),
  - **2e segment** = la 2e victime la plus tuée,
  - etc.
- **Ordre des lignes (Y)** : tri par **rang du joueur** (rang 1 en haut, puis 2, 3, …). Rang fourni par `match_participants` via `load_match_players_stats()`.
- **Légende** : une entrée par victime (nom du segment) pour les couleurs.

---

## 3. Représentation schématique

```
                    Victime A   Victime B   Victime C   Victime D
                    (segment 1) (segment 2) (segment 3) (segment 4)
                         ████       ██         █
Joueur rang 1       ──────████████████████████████──────  total: 7 kills
                         ███        ██
Joueur rang 2       ──────████████████████──────────────  total: 5 kills
                              ████   ██   █
Joueur rang 3       ──────────████████████████──────────  total: 4 kills
                         ██      ██
Joueur rang 4       ──────████████████──────────────────  total: 4 kills
                    ←─────────────────────────────────────→
                              Nombre de kills (axe X)
```

- Chaque ligne = un tueur (ordre = rang).
- Segments = répartition de ses kills par victime (ordre = kills décroissant sur chaque victime).

---

## 4. Données en entrée

- **`pairs_df`** (Polars) : colonnes `match_id`, `killer_xuid`, `killer_gamertag`, `victim_xuid`, `victim_gamertag`, `kill_count`. Déjà enrichi côté UI avec les noms d’affichage (roster/alias) dans `killer_gamertag` / `victim_gamertag`.
- **`rank_by_xuid`** (dict[str, int]) : mapping xuid → rang (1 = meilleur). À construire côté appelant à partir de `load_match_players_stats(db_path, match_id)` → `{s.xuid: s.rank for s in official_stats}`.

---

## 5. Algorithme (côté viz)

1. Filtrer `pairs_df` par `match_id` si fourni.
2. Agréger par (killer_xuid, killer_gamertag, victim_xuid, victim_gamertag) → somme des `kill_count`.
3. Pour chaque tueur, obtenir la liste (victim_gamertag, count) triée par count décroissant (ordre des segments de la barre).
4. Liste des tueurs : tous les killer_xuid distincts. **Trier par rang** : `sorted(killers, key=lambda x: rank_by_xuid.get(x, 999))`.
5. Liste des victimes distinctes : pour l’ordre des traces (stack), on peut fixer un ordre global (ex. toutes les victimes triées par total kills global, ou ordre d’apparition). Pour un stack cohérent visuellement, on garde pour chaque tueur l’ordre « sa plus grande victime d’abord », donc **une trace par victime** : pour chaque victime V, trace avec `x[i] = nombre de kills du tueur i sur V` (0 si pas de kill). L’ordre des traces (segments) peut être l’ordre des victimes par total kills global décroissant, pour avoir les « grosses » victimes en bas du stack.
6. Plotly : `go.Bar(orientation="h", y=killer_labels, x=counts_per_victim, name=victim_name)` par victime, avec `barmode="stack"`. `killer_labels` = liste des noms des tueurs dans l’ordre trié par rang.
7. Hauteur de figure : adapter (ex. `height = 80 + 22 * n_killers`) pour lisibilité.

---

## 6. Modifications à prévoir

### 6.1 `src/visualization/antagonist_charts.py` — `plot_killer_victim_stacked_bars()`

- **Signature** : ajouter un paramètre **`rank_by_xuid: dict[str, int] | None = None`** (mapping xuid → rang). Si `None`, tri des lignes par total kills décroissant (fallback).
- **Logique** :
  - Agrégation (killer, victim) → count.
  - Liste des tueurs triée par `rank_by_xuid` (puis par total kills si égalité).
  - Une trace par victime (nom = victim_gamertag), avec `x = [count(killer_i, victim)] pour chaque killer_i`, `y = liste des killer_gamertag dans l’ordre trié`.
  - `barmode="stack"`, axe Y = tueurs, axe X = nombre de kills.
- **Couleurs** : réutilisation de la palette existante (COLORS) ou palette cyclique pour les segments (une couleur par victime).

### 6.2 `src/ui/pages/match_view_players.py` — `_render_antagonist_chart()`

- Appeler **`load_match_players_stats(db_path, match_id)`** (déjà disponible via la section Némésis qui appelle `load_match_players_stats` ; on peut le faire dans `_render_antagonist_chart` pour ne pas dépendre de la section Némésis).
- Construire **`rank_by_xuid = {s.xuid: s.rank for s in official_stats}`**.
- Passer **`rank_by_xuid=rank_by_xuid`** à **`plot_killer_victim_stacked_bars(..., rank_by_xuid=rank_by_xuid)`**.

---

## 7. Fichiers impactés

| Fichier | Modification |
|---------|--------------|
| `src/visualization/antagonist_charts.py` | Réécriture de `plot_killer_victim_stacked_bars` : stacked bar par tueur, segments = victimes, tri des lignes par `rank_by_xuid`. |
| `src/ui/pages/match_view_players.py` | Dans `_render_antagonist_chart` : charger `official_stats = load_match_players_stats(...)`, construire `rank_by_xuid`, passer à `plot_killer_victim_stacked_bars`. |

---

## 8. Récap

- **Rangs** : bien exploitables pour tous les joueurs après backfill via `match_participants` et `load_match_players_stats()`.
- **Graphe** : une ligne = un tueur (tri par rang), une barre empilée = répartition des kills par victime (plus grande victime en premier dans le stack).
- **Plan** : implémenter selon §5–7 ci‑dessus.
