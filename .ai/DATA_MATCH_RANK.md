# Documentation : Rang d'un joueur lors d'un match

> Guide pour les IA : comment le **rang dans le match** (position/classement) est récupéré et utilisé.  
> Ne pas confondre avec le **rang de carrière** (0–272, Recrue/Bronze/…), documenté via `career_progression` et l’API reward tracks.

## Vue d'ensemble

Le **rang lors d’un match** désigne la **position** d’un joueur dans le classement de ce match (1 = meilleur score, 2 = deuxième, etc.). Il existe deux sources dans le projet :

| Contexte | Source | Stockage / usage |
|----------|--------|------------------|
| **Sync / persistance** | Champ `Rank` fourni par l’API sur chaque joueur du match | Colonne `match_stats.rank` (DuckDB) |
| **Vue détaillée d’un match** | Recalcul local (tri par score) | `MatchPlayerStats.rank` via `load_match_players_stats()` |

## 1. Rang fourni par l’API (sync)

Lors de la synchronisation, le rang **dans le match** est extrait depuis l’objet joueur renvoyé par l’API (ex. `MatchStats.Players[]`).

### Extraction

- **Module** : `src/data/sync/transformers.py`
- **Fonction** : `_extract_player_rank(player_obj)`  
  - Lit `player_obj.get("Rank")`, retourne `int` ou `None`.
- **Utilisation** : dans la construction de `MatchStatsRow` pour le joueur courant (`me`), le champ `rank` est passé au row puis inséré en base.

### Stockage

- **Table** : `match_stats` (DuckDB, `data/players/{gamertag}/stats.duckdb`)
- **Colonne** : `rank` (SMALLINT) — rang du joueur **pour ce match**, tel que fourni par l’API.

C’est la **source de vérité persistée** pour le rang “officiel” du joueur dans ce match (quand l’API le fournit).

## 2. Rang recalculé (vue joueurs d’un match)

Pour l’affichage de la liste des joueurs d’un match (qui a fini 1er, 2e, etc.), le rang **n’est pas** relu depuis l’API ni depuis `match_stats` : il est **recalculé** à partir des scores.

### Calcul

- **Module** : `src/db/loaders.py`
- **Fonction** : `load_match_players_stats(db_path, match_id)`
  1. Récupère les joueurs du match et leurs stats (kills, deaths, assists, score).
  2. Trie par **score décroissant** (fallback : kills si score absent).
  3. Assigne les rangs **1, 2, 3, …** selon l’ordre trié (`rank_idx` dans une boucle `enumerate(results, start=1)`).
  4. Retourne une liste de `MatchPlayerStats` avec `rank` rempli.

### Modèle

- **Modèle** : `MatchPlayerStats` (dans `src/db/loaders.py`)  
  - Champ `rank: int` — **Rang dans le match (1 = meilleur score)**.

### Usage (ex. tie-breaker)

- **Module** : `src/analysis/killer_victim.py`
- **Fonction** : `get_player_rank(xuid, official_stats) -> int`  
  - Prend la liste `MatchPlayerStats` issue de `load_match_players_stats()`.  
  - Retourne le `rank` du joueur dont le `xuid` correspond, ou `999` si non trouvé.  
  - Utilisé comme **tie-breaker** (meilleur rang = priorité) dans le calcul des némésis/souffre-douleur.

## Résumé pour les IA

- **Rang “lors d’un match”** = classement/position dans ce match (1 = premier, etc.).
- **Sync** : `transformers._extract_player_rank(me)` → `match_stats.rank` (donnée API).
- **Vue match** : `loaders.load_match_players_stats()` → tri par score → `MatchPlayerStats.rank` (recalculé).
- **Analyse** : `killer_victim.get_player_rank(xuid, official_stats)` utilise le rang recalculé pour le tie-breaker.
- **Rang de carrière** (0–272) est un autre concept : API reward tracks, table `career_progression`, profil joueur — voir `profile_api._get_career_rank_for_player` et `api_client.get_career_rank_progression`.

## Fichiers de référence

| Fichier | Rôle |
|---------|------|
| `src/data/sync/transformers.py` | `_extract_player_rank()`, utilisation dans `MatchStatsRow.rank` |
| `src/data/sync/engine.py` | Schéma `match_stats` (colonne `rank`) |
| `src/db/loaders.py` | `MatchPlayerStats`, `load_match_players_stats()` (tri + assignation rang) |
| `src/analysis/killer_victim.py` | `get_player_rank()` (tie-breaker) |
