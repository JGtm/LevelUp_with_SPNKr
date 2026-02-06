# Analyse et planification : backfill score/rang et architecture K/D

> Document d’analyse et de planification uniquement. Aucune modification de code dans cette phase.

---

## 1. Backfill score et rang dans `backfill_data.py`

### 1.1 Vérification API : le rang est-il renvoyé pour tous les joueurs ?

**Documentation existante** (`.ai/research/API_REFDATA_FIELDS.md`, §5) :

```
Players[]
├── PlayerId: "xuid(2535461927511067)"
├── PlayerType: 1 (HUMAN)
├── LastTeamId: 1
├── Outcome: 2 (WIN)
├── Rank: 4          ← au niveau de chaque joueur
├── ParticipationInfo
└── PlayerTeamStats[]
    └── Stats
        └── CoreStats
            ├── PersonalScore: 1300
            ├── Score: ...
            └── Kills, Deaths, Assists, ...
```

**Conclusion** : La doc décrit un champ **`Rank`** par joueur dans `Players[]`. Il est donc cohérent de considérer que l’API peut retourner le rang pour chaque joueur, pas seulement pour le joueur actuel.

**À faire côté implémentation** :
- Vérifier sur un **payload réel** (log ou fixture) que `Players[].Rank` est bien présent pour plusieurs joueurs (et pas seulement pour `me`). Si un seul joueur a `Rank`, garder le fallback « calcul par tri score ».
- Dans `extract_participants` : utiliser `player.get("Rank")` quand il est présent, sinon garder le rang calculé (tri par score). Stocker les deux en base (ex. `rank` = valeur utilisée, optionnellement `rank_from_api` pour audit).

### 1.2 État actuel du backfill participants

- **`backfill_data.py`** a déjà l’option `--participants` qui :
  - appelle `extract_participants(stats_json)` (qui remplit désormais `rank` et `score` dans `MatchParticipantRow`) ;
  - insère via `_insert_participant_rows(conn, participant_rows)`.
- **Problème** : `_insert_participant_rows` dans le script :
  - crée la table **sans** les colonnes `rank` et `score` (lignes 279–284) ;
  - n’insère que `(match_id, xuid, team_id, outcome, gamertag)` (lignes 302–306).
- Donc même avec `extract_participants` qui remplit rank/score, le backfill **ne persiste pas** rank/score.

### 1.3 Options proposées pour le script `backfill_data.py`

| Option | Description | Comportement |
|--------|-------------|--------------|
| **Étendre `--participants`** | Inclure systématiquement score et rang dans le backfill participants. | Migration : s’assurer que `match_participants` a les colonnes `rank` et `score` (comme dans le sync engine). INSERT avec 7 colonnes : match_id, xuid, team_id, outcome, gamertag, **rank**, **score**. |
| **`--participants-scores`** (nouvelle option dédiée) | Backfill uniquement score et rang pour les matchs qui ont déjà des lignes dans `match_participants`. | Utile si on ne veut pas re-télécharger tout le roster. Requiert de re-télécharger le JSON du match (get_match_stats) pour extraire score/rank ; puis UPDATE ou INSERT OR REPLACE sur (match_id, xuid) avec rank, score. |
| **`--force-participants`** (existant) | Ré-insérer tous les participants pour tous les matchs. | Une fois le script aligné sur le schéma 7 colonnes, force-participants remplit aussi rank/score pour tous les matchs retraités. |

**Recommandation** :
1. **Aligner le backfill sur le sync** : dans `backfill_data.py`, `_insert_participant_rows` doit utiliser le même schéma que le sync engine (colonnes `rank`, `score`), avec migration (ADD COLUMN si absentes) et INSERT avec 7 colonnes.
2. **Ne pas ajouter une option séparée `--participants-scores`** pour l’instant : `--participants` (et `--force-participants`) suffisent pour « récupérer score et rang » en ré-insérant les participants à partir du JSON.
3. **Option future (optionnelle)** : `--use-api-rank` (ou comportement par défaut) : dans `extract_participants`, utiliser `_extract_player_rank(player)` pour chaque joueur ; si l’API renvoie `Rank`, l’utiliser ; sinon garder le rang calculé (tri par score). À valider après vérification sur un payload réel.

**Résumé des changements prévus (planification)** :
- Dans `backfill_data.py` :  
  - Vérifier/créer les colonnes `rank` et `score` sur `match_participants` (migration idempotente).  
  - Étendre `_insert_participant_rows` pour insérer `row.rank` et `row.score`.  
- Dans `extract_participants` (transformers) :  
  - Utiliser `player.get("Rank")` quand présent pour remplir `MatchParticipantRow.rank`, sinon garder le rang calculé (tri par score).  
- Vérification une fois en dev : logger ou inspecter un `Players[]` réel pour confirmer la présence de `Rank` sur plusieurs joueurs.

---

## 2. Où sont déjà stockés les morts et frags de tous les joueurs ?

### 2.1 Inventaire des sources

| Source | Contenu | Périmètre |
|--------|---------|-----------|
| **match_stats** | kills, deaths, assists, score, rank, … | **Un seul joueur par match** (le joueur principal). 1 ligne = 1 match. |
| **match_participants** | match_id, xuid, team_id, outcome, gamertag, **rank**, **score** | **Tous les joueurs** du match. Pas de kills/deaths/assists. |
| **killer_victim_pairs** | match_id, killer_xuid, victim_xuid, kill_count, time_ms | **Tous les joueurs** : pour chaque (match, xuid), kills = SUM(kill_count) WHERE killer_xuid=xuid, deaths = SUM(kill_count) WHERE victim_xuid=xuid. |
| **highlight_events** | match_id, event_type ('kill' / 'death'), xuid, time_ms, … | **Tous les joueurs** : kills(xuid) = nombre d’events `kill` avec ce xuid (tueur), deaths(xuid) = nombre d’events `death` avec ce xuid (victime). |

Donc **les morts et frags de tous les joueurs sont déjà représentés** :
- soit dans **killer_victim_pairs** (agrégation killer/victim par match),
- soit dans **highlight_events** (chaque event kill/death avec un xuid).

Aujourd’hui, **match_participants** ne contient pas kills/deaths/assists ; seul le joueur principal a ses K/D dans **match_stats**.

### 2.2 Qui consomme ces données ?

- **`load_match_players_stats()`** (loaders) : retourne une liste de `MatchPlayerStats` (xuid, gamertag, kills, deaths, assists, team_id, rank, score).  
  - En DuckDB : lecture depuis **match_participants** uniquement → aujourd’hui **kills=0, deaths=0, assists=0** pour tous.
- **`killer_victim.py`** :
  - **validate_and_adjust_pairs** : compare, par joueur, kills/deaths **reconstitués** (depuis les paires) aux kills/deaths **officiels** (`MatchPlayerStats.kills`, `MatchPlayerStats.deaths`). Si officiels = 0, la validation est triviale (0 vs 0).
  - **compute_personal_antagonists** : utilise `official_stats` pour le **tie-breaker par rang** et pour la **validation** (écart my_kills_assigned vs my_official.kills, idem deaths).
- **match_view_players.py** : appelle `load_match_players_stats` puis `compute_personal_antagonists(..., official_stats=official_stats)` et peut afficher les écarts reconstituted vs official.

Donc : **graphes et tableaux existants** s’appuient sur :
- **killer_victim_pairs** (et parfois highlight_events) pour le graphe killer/victim et la reconstitution des paires ;
- **official_stats** = `load_match_players_stats()` pour le rang (tie-breaker), la validation K/D et l’affichage des écarts.

Une architecture plus efficace doit **enrichir** ce que renvoie `load_match_players_stats()` (idéalement avec de vrais K/D pour tous les joueurs) **sans changer** les interfaces (`MatchPlayerStats`, `compute_personal_antagonists`, `validate_and_adjust_pairs`).

---

## 3. Architecture et logique proposées (sans casser graphes/tableaux)

### 3.1 Objectifs

- Avoir **une source claire** pour les K/D de **tous** les joueurs d’un match (pour validation et affichage).
- Réutiliser au maximum les données **déjà présentes** (killer_victim_pairs, ou API lors du sync/backfill).
- Ne pas casser : graphes killer/victim, tableaux némésis/souffre-douleur, validation reconstituted vs official.

### 3.2 Option A : Enrichir `match_participants` (K/D depuis l’API)

- **Sync / backfill** : pour chaque joueur dans `Players[]`, extraire CoreStats (Kills, Deaths, Assists) et les stocker dans **match_participants** : ajout des colonnes `kills`, `deaths`, `assists` (SMALLINT ou INTEGER, nullable).
- **Chargement** : `_load_match_players_stats_from_duckdb()` lit match_participants et remplit `MatchPlayerStats` avec ces K/D. Les graphes et la validation utilisent déjà `load_match_players_stats()` → aucun changement d’API côté UI/analyse.
- **Avantages** : source « officielle » (API), une seule table pour roster + rank + score + K/D.
- **Inconvénients** : schéma et sync/backfill à étendre ; backfill nécessaire pour les anciens matchs si on veut K/D rétroactifs.

### 3.3 Option B : Dériver K/D depuis `killer_victim_pairs` (sans colonnes supplémentaires)

- **Pas de nouvelle colonne** dans match_participants.
- Dans **`_load_match_players_stats_from_duckdb()`** : pour chaque (match_id, xuid) issu de match_participants, calculer :
  - kills = SUM(kill_count) FROM killer_victim_pairs WHERE match_id=? AND killer_xuid=xuid
  - deaths = SUM(kill_count) FROM killer_victim_pairs WHERE match_id=? AND victim_xuid=xuid
- Retourner des `MatchPlayerStats` avec rank, score (déjà en place) et ces kills/deaths dérivés. Assists restent à 0 (non dérivables depuis KVP).
- **Avantages** : pas de migration, pas de nouveau champ API ; réutilisation directe de killer_victim_pairs ; validation reconstituted vs “officiel” devient pertinente (même source que les paires).
- **Inconvénients** : les K/D “officiels” deviennent en fait **dérivés des paires** (pas l’API) ; si highlight_events/KVP sont incomplets, les totaux peuvent être sous-estimés ; **assists** non disponibles.

### 3.4 Option C : Hybride (recommandé)

- **match_participants** : ajouter **kills, deaths, assists** (nullable), remplis lors du **sync** et du **backfill** depuis l’API (`Players[].CoreStats`) quand disponibles.
- **Chargement** : `_load_match_players_stats_from_duckdb()` lit match_participants. Si kills/deaths/assists sont non NULL, les utiliser ; sinon **fallback** : dériver kills/deaths depuis killer_victim_pairs (assists restant 0 si non fournis).
- **Résultat** :  
  - Nouveaux matchs et matchs backfillés : K/D officiels pour tous.  
  - Anciens matchs sans backfill : K/D dérivés des paires, sans casser les graphes ni la validation.
- **Compatibilité** : même contrat `MatchPlayerStats` et mêmes appels côté UI/analyse ; aucun changement de signature des fonctions existantes.

### 3.5 Synthèse recommandée

- **Court terme (backfill)** :  
  - Aligner backfill_data sur le schéma sync (rank, score dans match_participants).  
  - Option script : récupérer score et rang (et vérifier utilisation de l’API Rank si présent).  
- **Architecture K/D** :  
  - **Option C (hybride)** : colonnes kills, deaths, assists dans match_participants (remplies par sync/backfill depuis l’API) ; dans le loader DuckDB, fallback sur killer_victim_pairs si K/D manquants.  
  - Ainsi : une seule source logique pour l’UI (`load_match_players_stats` → MatchPlayerStats), graphes et tableaux inchangés, validation améliorée quand les données API sont présentes.

---

## 4. Plan d’implémentation (à exécuter après validation)

### Phase 1 – Backfill score/rang (sans toucher au code tant que demandé)

1. Vérifier sur un payload réel `get_match_stats` que `Players[].Rank` est présent pour plusieurs joueurs.
2. Dans `backfill_data.py` :  
   - migration `match_participants` (colonnes rank, score si absentes) ;  
   - `_insert_participant_rows` : INSERT avec rank, score.
3. Dans `extract_participants` : utiliser `Rank` API quand présent, sinon rang calculé (tri par score).

### Phase 2 – Architecture K/D (après validation de la phase 1)

1. Schéma : ajouter à `match_participants` les colonnes `kills`, `deaths`, `assists` (nullable, type SMALLINT ou INTEGER).
2. Sync engine : dans `extract_participants` (ou dans un passage commun), extraire K/D/A depuis CoreStats pour chaque joueur et les inclure dans `MatchParticipantRow` ; insertion dans le sync et dans le backfill.
3. Loader : dans `_load_match_players_stats_from_duckdb()`, lire kills, deaths, assists depuis match_participants ; si NULL pour un joueur, fallback : agrégation depuis killer_victim_pairs (kills/deaths uniquement).
4. Ne pas modifier les signatures de `load_match_players_stats`, `compute_personal_antagonists`, `validate_and_adjust_pairs`, ni les composants UI qui les appellent.

---

## 5. Fichiers concernés (référence)

| Fichier | Rôle |
|---------|------|
| `scripts/backfill_data.py` | Options et logique backfill (participants, rank, score ; plus tard K/D). |
| `src/data/sync/transformers.py` | `extract_participants`, `_extract_player_rank`, `_extract_player_score` ; extraction K/D depuis CoreStats (phase 2). |
| `src/data/sync/models.py` | `MatchParticipantRow` (rank, score ; puis kills, deaths, assists). |
| `src/data/sync/engine.py` | Schéma et migration match_participants ; insertion des lignes. |
| `src/db/loaders.py` | `_load_match_players_stats_from_duckdb()` : lecture match_participants + fallback KVP (phase 2). |
| `src/analysis/killer_victim.py` | Consomme `official_stats` (rang, kills, deaths) ; pas de changement d’interface. |
| `src/ui/pages/match_view_players.py` | Appelle load_match_players_stats et compute_personal_antagonists ; inchangé. |
| `.ai/research/API_REFDATA_FIELDS.md` | Référence structure API (Rank, CoreStats). |

---

*Document créé pour analyse et planification. Aucun code modifié.*
