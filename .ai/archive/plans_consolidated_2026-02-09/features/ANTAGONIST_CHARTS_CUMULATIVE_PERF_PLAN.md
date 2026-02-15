# Plan d'Implémentation : Persistance Killer-Victim + Antagonistes + Graphiques + Performance Cumulée

> Date : 2026-02-02  
> Statut : Plan d'implémentation révisé  
> Référence : ANTAGONISTS_FILM_CHUNKS_ANALYSIS.md, BINARY_CHUNK_ANALYSIS_V2_PLAN.md

---

## Changement d'architecture majeur

**Constat** : Les investigations validées montrent qu'on peut extraire avec précision *qui a tué qui et quand* à partir des film chunks. Ces données doivent être **persistées en DuckDB** pour chaque match, pour **tous les joueurs** (bots, joueurs qui quittent/rejoignent).

**Objectifs** :
1. **Source de vérité unique** : table `killer_victim_pairs` en DuckDB
2. **Abandon SQLite** pour cette fonctionnalité
3. **Refresh total acceptable** : l'utilisateur effectuera une resync complète si nécessaire
4. **Impact Némésis/Souffre-douleur** : calcul dérivé des paires persistées (plus de calcul à la volée depuis highlight_events)

---

## Phase 0 : Persistance des paires Killer-Victim en DuckDB

### 0.1 Nouvelle table `killer_victim_pairs`

**Fichier** : `data/players/{gamertag}/stats.duckdb`

```sql
-- Table killer_victim_pairs : qui a tué qui, quand (1 ligne = 1 kill)
CREATE TABLE IF NOT EXISTS killer_victim_pairs (
    match_id VARCHAR NOT NULL,
    killer_xuid VARCHAR NOT NULL,
    killer_gamertag VARCHAR,
    victim_xuid VARCHAR NOT NULL,
    victim_gamertag VARCHAR,
    time_ms INTEGER NOT NULL,
    PRIMARY KEY (match_id, time_ms, killer_xuid, victim_xuid)  -- unicité par kill
);

CREATE INDEX IF NOT EXISTS idx_kvp_match ON killer_victim_pairs(match_id);
CREATE INDEX IF NOT EXISTS idx_kvp_killer ON killer_victim_pairs(killer_xuid);
CREATE INDEX IF NOT EXISTS idx_kvp_victim ON killer_victim_pairs(victim_xuid);
```

**Note PK** : Un même (killer, victim) peut avoir plusieurs kills à des `time_ms` différents. La PK `(match_id, time_ms, killer_xuid, victim_xuid)` peut échouer si deux kills identiques au même ms (rare). Alternative : ajouter un `id INTEGER PRIMARY KEY` auto-incrémenté et un index unique sur `(match_id, time_ms, killer_xuid, victim_xuid)` avec `ON CONFLICT` ignore.

**Alternative plus robuste** :
```sql
CREATE TABLE IF NOT EXISTS killer_victim_pairs (
    id INTEGER PRIMARY KEY,
    match_id VARCHAR NOT NULL,
    killer_xuid VARCHAR NOT NULL,
    killer_gamertag VARCHAR,
    victim_xuid VARCHAR NOT NULL,
    victim_gamertag VARCHAR,
    time_ms INTEGER NOT NULL
);
CREATE UNIQUE INDEX idx_kvp_unique ON killer_victim_pairs(match_id, time_ms, killer_xuid, victim_xuid);
CREATE INDEX idx_kvp_match ON killer_victim_pairs(match_id);
```

### 0.2 Périmètre des données

| Type de joueur | Inclus | Remarque |
|----------------|--------|----------|
| Joueurs humains | Oui | XUID numérique ou xuid(...) |
| Bots | Oui | XUID `bid(...)` ou équivalent |
| Joueurs qui quittent | Oui | Toute kill/death avant leur départ |
| Joueurs qui rejoignent | Oui | Toute kill/death après leur arrivée |

Les paires sont **match-scoped** : tout kill enregistré dans les highlight_events du match est capturé, quel que soit le statut du joueur.

### 0.3 Intégration dans le pipeline de synchronisation

**Fichier** : `src/data/sync/engine.py`

Dans `_process_single_match()` :
1. Récupérer `highlight_events` (inchangé)
2. Transformer en `event_rows` et insérer dans `highlight_events` (inchangé)
3. **Nouveau** : appeler `compute_killer_victim_pairs(highlight_events, tolerance_ms=5)`
4. **Nouveau** : insérer les paires dans `killer_victim_pairs` via `_insert_killer_victim_pairs(pairs, match_id)`
5. Avant insertion : `DELETE FROM killer_victim_pairs WHERE match_id = ?` (idempotence si resync)

**Fichier** : `src/data/sync/engine.py` — méthode à ajouter :
```python
def _insert_killer_victim_pairs(self, pairs: list[KVPair], match_id: str) -> int:
    """Insère les paires killer-victim pour un match. Retourne le nombre inséré."""
```

### 0.4 Lecture depuis DuckDB

**Nouveau** : `DuckDBRepository.load_killer_victim_pairs(match_id: str) -> list[KVPair]`

Charge les paires depuis la table et les retourne comme `list[KVPair]` pour compatibilité avec l'existant.

**Adaptation du chargement** : L'UI des pages "Dernier match" et "Match" doit utiliser le **DuckDBRepository** (ou une couche unifiée) pour charger les paires. Si `db_path` pointe vers un `stats.duckdb`, on lit directement depuis `killer_victim_pairs`. Plus de dépendance à `load_highlight_events_for_match` (SQLite/HighlightEvents) pour les antagonistes.

### 0.5 Script de backfill

**Nouveau** : `scripts/backfill_killer_victim_pairs.py`

- Parcourt tous les matchs ayant des `highlight_events` dans la DB DuckDB
- Pour chaque match : `compute_killer_victim_pairs(events)` → `_insert_killer_victim_pairs`
- Utilisable après migration de schéma pour peupler les données existantes

### 0.6 Impact sur la définition Némésis / Souffre-douleur

| Avant | Après |
|-------|-------|
| Calcul à la volée depuis `highlight_events` | Lecture depuis `killer_victim_pairs` |
| Appariement kill/death avec tolérance 5ms | **Déjà apparié** — pas d'ambiguïté |
| `certain` vs `estimated` (cas ambigus) | **Toutes les paires sont certaines** |
| Dépendance `load_match_players_stats` pour validation | Validation possible via `match_stats.kills/deaths` du joueur principal |

**Nouvelle fonction** : `compute_personal_antagonists_from_pairs(pairs: list[KVPair], me_xuid: str) -> AntagonistsResult`

- Némésis : `victim_xuid == me_xuid` → grouper par `killer_xuid`, prendre le max
- Souffre-douleur : `killer_xuid == me_xuid` → grouper par `victim_xuid`, prendre le max
- `EstimatedCount` : `certain = total`, `estimated = 0` (toutes les paires sont certaines)
- Validation : comparer `SUM(kills où killer=me)` et `SUM(deaths où victim=me)` avec `match_stats` du joueur principal

---

## 1. Vérification des Antagonistes (Némésis / Souffre-douleur)

### 1.1 Source de données

- **Lecture** : `DuckDBRepository.load_killer_victim_pairs(match_id)`
- **Calcul** : `compute_personal_antagonists_from_pairs(pairs, me_xuid)`
- **Validation** : comparer totaux avec `match_stats.kills`, `match_stats.deaths` du joueur principal (disponible en DuckDB)

### 1.2 Actions de vérification

1. **Script de diagnostic** : `scripts/diagnose_antagonists.py` — charge les paires depuis DuckDB, vérifie cohérence avec match_stats
2. **Indicateur is_validated** : afficher un badge discret si les totaux ne correspondent pas

---

## 2. Graphiques Section Antagonistes (Dernier match / Match)

### 2.1 Source de données

**Uniquement** : `load_killer_victim_pairs(match_id)` depuis DuckDB.

Plus de calcul à partir de `highlight_events` dans l'UI.

### 2.2 Graphique A : Killer–Victim Pair Counts (barres empilées horizontales)

- **Données** : `killer_victim_counts_long(pairs)` — déjà implémenté, fonctionne sur `list[KVPair]`
- **Reste inchangé** par rapport au plan initial

### 2.3 Graphique B : Kills – Deaths Time Series

- **Données** : `compute_kd_timeseries_by_minute(pairs)` — à implémenter
- **Reste inchangé** par rapport au plan initial

---

## 3. Graphique de Performance Cumulée (Session / Mes coéquipiers)

Inchangé par rapport au plan initial. Source : `match_stats` (kills, deaths par match).

---

## 4. Ordre d'implémentation révisé

### Phase 0 : Persistance Killer-Victim (priorité critique)

| # | Tâche | Fichiers |
|---|-------|----------|
| 0.1 | Ajouter la table `killer_victim_pairs` au schéma DuckDB | `src/data/sync/engine.py` (DDL), `docs/SQL_SCHEMA.md` |
| 0.2 | Implémenter `_insert_killer_victim_pairs` dans le sync engine | `src/data/sync/engine.py` |
| 0.3 | Intégrer le calcul et l'insertion dans `_process_single_match` | `src/data/sync/engine.py` |
| 0.4 | Ajouter `load_killer_victim_pairs` à DuckDBRepository | `src/data/repositories/duckdb_repo.py` |
| 0.5 | Créer `compute_personal_antagonists_from_pairs` | `src/analysis/killer_victim.py` |
| 0.6 | Script de backfill pour DB existantes | `scripts/backfill_killer_victim_pairs.py` |

### Phase 1 : UI Antagonistes (lecture DuckDB)

| # | Tâche | Fichiers |
|---|-------|----------|
| 1.1 | Adapter le chargement des antagonistes pour utiliser DuckDB (killer_victim_pairs) | `streamlit_app.py`, couche de chargement |
| 1.2 | Remplacer `compute_personal_antagonists(events)` par `compute_personal_antagonists_from_pairs(pairs)` dans l'UI | `src/ui/pages/match_view_players.py` |
| 1.3 | Définir la source de chargement : repository selon `db_path` (.duckdb → DuckDBRepository) | Nouvelle fonction ou refactor `load_highlight_events_fn` → `load_killer_victim_pairs_fn` |

### Phase 2 : Graphiques Antagonistes

| # | Tâche | Fichiers |
|---|-------|----------|
| 2.1 | `compute_kd_timeseries_by_minute(pairs)` | `src/analysis/killer_victim.py` |
| 2.2 | `plot_killer_victim_stacked_bars()`, `plot_kd_timeseries()` | `src/visualization/antagonist_charts.py` (nouveau) |
| 2.3 | Intégrer les 2 graphiques après la section Némésis/Souffre-douleur | `src/ui/pages/match_view_players.py` |

### Phase 3 : Performance cumulée

| # | Tâche | Fichiers |
|---|-------|----------|
| 3.1 | `compute_cumulative_net_score_series()`, `plot_cumulative_net_score()` | `src/analysis/`, `src/visualization/` |
| 3.2 | Intégrer dans "Comparaison de sessions" | `src/ui/pages/session_compare.py` |

### Phase 4 : Nettoyage et robustesse

| # | Tâche | Fichiers |
|---|-------|----------|
| 4.1 | Conserver `highlight_events` pour debug/reprocess, ou documenter son rôle secondaire | - |
| 4.2 | Tests unitaires pour les nouvelles fonctions | `tests/` |
| 4.3 | Mise à jour de la documentation | `docs/`, `.ai/` |

---

## 5. Architecture des données (schéma révisé)

```
Film Chunks (API SPNKr)
    ↓
spnkr.film.read_highlight_events()
    ↓
highlight_events (brut, conservé pour debug)
    ↓
compute_killer_victim_pairs(events, tolerance_ms=5)
    ↓
killer_victim_pairs (table DuckDB)  ← SOURCE DE VÉRITÉ
    ↓
├── compute_personal_antagonists_from_pairs() → Némésis / Souffre-douleur
├── killer_victim_counts_long() → Graphique A (barres empilées)
└── compute_kd_timeseries_by_minute() → Graphique B (série temporelle)
```

---

## 6. Stratégie de migration / refresh

1. **Nouvelles DB** : Le schéma inclut `killer_victim_pairs`. La sync remplit la table automatiquement.
2. **DB existantes** :
   - Exécuter le script de migration de schéma (CREATE TABLE si not exists)
   - Exécuter `backfill_killer_victim_pairs.py` pour peupler à partir de `highlight_events`
   - Ou : **refresh total** — l'utilisateur relance une sync complète avec `--with-highlight-events` (ou équivalent)

---

## 7. Table `highlight_events` : rôle

| Option | Avantages | Inconvénients |
|--------|-----------|---------------|
| **Conserver** | Reprocessing, diagnostic, backfill | Redondance |
| **Supprimer** | Schéma plus simple | Impossible de recalculer les paires sans refetch API |

**Recommandation** : Conserver `highlight_events` pour le backfill et le diagnostic. La table `killer_victim_pairs` est la source utilisée par l'UI.

---

## 8. Glossaire et checklist (inchangés)

Voir sections 6 et 7 du plan initial pour le glossaire FR/EN et la checklist finale.
