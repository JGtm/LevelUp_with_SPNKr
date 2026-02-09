# Documentation : Rang d'un joueur lors d'un match

> Guide pour les IA : comment le **rang dans le match** (position/classement) est récupéré et utilisé.  
> Ne pas confondre avec le **rang de carrière** (0–272, Recrue/Bronze/…), documenté via `career_progression` et l’API reward tracks.

## Vue d'ensemble

Le **rang lors d’un match** désigne la **position** d’un joueur dans le classement de ce match (1 = meilleur score, 2 = deuxième, etc.).

| Contexte | Source | Stockage / usage |
|----------|--------|------------------|
| **Sync – joueur actuel** | Champ `Rank` API (joueur courant) | `match_stats.rank` (DuckDB) |
| **Sync – tous les joueurs** | Calcul lors du sync : tri par score sur `Players[]` | `match_participants.rank` et `.score` (DuckDB) |
| **Vue détaillée d’un match** | Lecture depuis `match_participants` (DuckDB) ou recalcul (legacy) | `MatchPlayerStats.rank` via `load_match_players_stats()` |

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

## 2. Rang pour tous les joueurs (sync → match_participants)

Lors du sync, **tous** les participants du match reçoivent un rang.

- **Module** : `src/data/sync/transformers.py`
- **Fonction** : `extract_participants(match_json)` — parcourt `MatchStats.Players[]`, extrait score (PersonalScore/Score), trie par score décroissant, assigne rank 1, 2, 3… à chaque participant.
- **Stockage** : table `match_participants` (colonnes `rank`, `score`). Migration : `_ensure_match_participants_rank_score()`.

## 3. Vue joueurs (load_match_players_stats)

- **DuckDB** : `_load_match_players_stats_from_duckdb()` lit `match_participants` (xuid, gamertag, team_id, rank, score) et retourne `MatchPlayerStats` avec rang pour **tous** les joueurs (kills/deaths/assists = 0).
- **Legacy** : payload JSON → tri par score → rang 1, 2, 3…

### Modèle

- **Modèle** : `MatchPlayerStats` (dans `src/db/loaders.py`) — champ `rank: int` (1 = meilleur score).

### Usage (ex. tie-breaker)

- **Module** : `src/analysis/killer_victim.py`
- **Fonction** : `get_player_rank(xuid, official_stats) -> int`  
  - Prend la liste `MatchPlayerStats` issue de `load_match_players_stats()`.  
  - Retourne le `rank` du joueur dont le `xuid` correspond, ou `999` si non trouvé.  
  - Utilisé comme **tie-breaker** (meilleur rang = priorité) dans le calcul des némésis/souffre-douleur.

## Résumé pour les IA

- **Rang “lors d’un match”** = classement/position dans ce match (1 = premier, etc.).
- **Sync joueur actuel** : `_extract_player_rank(me)` → `match_stats.rank` (API).
- **Sync tous les joueurs** : `extract_participants()` → tri par score → `match_participants.rank` et `.score` pour chaque participant.
- **Vue match (DuckDB)** : `load_match_players_stats()` lit `match_participants` → `MatchPlayerStats` avec rang pour tous.
- **Analyse** : `killer_victim.get_player_rank(xuid, official_stats)` utilise ce rang pour le tie-breaker.
- **Rang de carrière** (0–272) : autre concept (API reward tracks, `career_progression`).

## Fichiers de référence

| Fichier | Rôle |
|---------|------|
| `src/data/sync/transformers.py` | `_extract_player_rank()`, `extract_participants()` (score + rang pour tous) |
| `src/data/sync/models.py` | `MatchParticipantRow` (rank, score) |
| `src/data/sync/engine.py` | Schéma et migration `match_participants` (rank, score), `_insert_participant_rows` |
| `src/db/loaders.py` | `_load_match_players_stats_from_duckdb()`, `load_match_players_stats()`, `MatchPlayerStats` |
| `src/analysis/killer_victim.py` | `get_player_rank()` (tie-breaker) |
