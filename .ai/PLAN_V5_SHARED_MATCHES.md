# Plan Unifié — LevelUp v5.0 : Architecture Shared Matches

> **Date** : 2026-02-14  
> **Branche source** : `sprint14/isolation-backend-frontend`  
> **Branche cible** : `v5/shared-matches-migration`  
> **Tag final** : `v5.0.0`  
> **Statut** : Plan consolidé — Migration architecture radicale vers base de données partagée  
> **Durée estimée** : 14-18 jours ouvrés  

---

## 🎯 Objectif Global

**Migrer vers une architecture radicale avec base de données partagée** pour éliminer la duplication massive des données de matchs entre joueurs partageant des parties communes.

### Problématique Résolue

- ❌ **Avant** : Duplication de 75-100% des données (Madina97294/Chocoboflor = 95% matchs communs)
- ✅ **Après** : 1 match stocké 1 seule fois, accessible par tous les joueurs
- 📊 **Gains** : -69% stockage, -72% appels API, -73% temps de sync

### Architecture Cible

```
data/warehouse/
├── metadata.duckdb              # Référentiels (existant)
└── shared_matches.duckdb        # ⭐ NOUVEAU : Base unique pour TOUS les matchs
    ├── match_registry           # Registre central (1 ligne par match global)
    ├── match_participants       # TOUS les joueurs de TOUS les matchs
    ├── highlight_events         # TOUS les événements filmés
    ├── medals_earned            # Médailles de TOUS les joueurs
    └── xuid_aliases             # Mapping global xuid→gamertag

data/players/{gamertag}/
└── stats.duckdb                 # ⭐ SIMPLIFIÉ : Uniquement enrichissements personnels
    ├── player_match_enrichment  # performance_score, session_id, is_with_friends
    ├── teammates_aggregate      # Agrégats depuis mon point de vue
    ├── antagonists              # Rivalités depuis mon point de vue
    ├── media_files              # MES fichiers médias
    └── media_match_associations # MES associations média↔match
```

---

## 🚀 CHECKLIST DE DÉMARRAGE OBLIGATOIRE

> **À accomplir AVANT de lancer toute modification de code**

### 1. Préparation Environnement

```bash
# 1. Créer la branche depuis sprint14
git checkout sprint14/isolation-backend-frontend
git pull origin sprint14/isolation-backend-frontend
git checkout -b v5/shared-matches-migration

# 2. Vérifier l'état de base
python -m pytest -q --ignore=tests/integration

# 3. Créer un backup COMPLET des DBs actuelles
python scripts/backup_all_players.py --output backups/pre-v5-migration-$(date +%Y%m%d)

# 4. Documenter l'état de base
python scripts/diagnose_all_dbs.py > .ai/v5-baseline-state.txt
```

### 2. Backups Critiques (OBLIGATOIRE)

⚠️ **Cette migration est IRRÉVERSIBLE sans backup**

- [ ] Backup de `data/players/*/stats.duckdb` (TOUTES les DBs joueur)
- [ ] Backup de `data/warehouse/metadata.duckdb`
- [ ] Sauvegarde du schéma SQL actuel (`scripts/export_current_schema.sql`)
- [ ] Commit de référence tagué `pre-v5-migration`

### 3. Environnement Python Validé

- **Python** : 3.12.10 (`.venv` à la racine)
- **Commande** : `python -m ...` (jamais d'appel direct aux binaires)
- **Tests baseline** : `python -m pytest -q --ignore=tests/integration` → **DOIT PASSER**

### 4. Documentation des Plans en Attente

Plans à incorporer dans le sprint approprié :
- ✅ **PLAN_OPTIMISATION_SYNC.md** → Sprint 6 (optimisation API)
- ✅ **PLAN_AMELIORATION_TESTS.md** → Sprint 7 (couverture tests)

---

## 📋 Table des Matières

1. [Règles de Développement Strictes](#1-règles-de-développement-strictes)
2. [Stratégie de Migration](#2-stratégie-de-migration)
3. [Sprints Détaillés](#3-sprints-détaillés) (S0-S8)
4. [Protocole de Revue par Sprint](#4-protocole-de-revue-par-sprint)
5. [Matrice de Risques](#5-matrice-de-risques)
6. [Critères de Livraison Globaux](#6-critères-de-livraison-globaux)
7. [Plan de Rollback](#7-plan-de-rollback)

---

## 1. Règles de Développement Strictes

### 1.1 Principes Architecturaux Obligatoires

#### Modularité

- **1 module = 1 responsabilité claire**
- Max 500 lignes par module (800 si justifié et documenté)
- Pas de couplage circulaire entre modules
- Interfaces claires et documentées

#### Simplicité

- **KISS** : Toujours choisir la solution la plus simple qui fonctionne
- Pas d'abstraction prématurée
- Code auto-documenté (noms explicites > commentaires)
- Pas de "clever code" : préférer la lisibilité

#### Logique

- **DRY** : Pas de duplication de logique métier
- Séparation des préoccupations (DB / Business / UI)
- Flux de données unidirectionnel et prévisible
- Gestion d'erreurs exhaustive et explicite

### 1.2 Qualité Code Non Négociable

#### Tests

- **Avant modifications** : `pytest` DOIT passer à 100%
- **Après sprint** : `pytest` DOIT passer à 100% + nouveaux tests
- Couverture minimale : 80% sur code métier (`src/data/`, `src/analysis/`)
- Tests d'intégration pour chaque migration de données

#### Type Hints

- Type hints **OBLIGATOIRES** sur toutes les fonctions publiques
- Validation Pydantic v2 pour les modèles de données
- `mypy --strict` doit passer (sauf cas documentés)

#### Documentation

- Docstrings **OBLIGATOIRES** en français pour API publiques
- README à jour pour chaque nouvelle feature
- Changelog détaillé (format Conventional Commits)
- Diagrammes d'architecture à jour (`.ai/architecture/`)

### 1.3 Git Workflow

#### Commits

- Format : `<type>(<scope>): <description>`
- Types : `feat`, `fix`, `refactor`, `test`, `docs`, `perf`, `chore`
- 1 commit = 1 changement logique atomique
- Message explicite (pas de "fix", "update", "wip")

#### Revue de Code

- **Auto-revue obligatoire** avant commit
- Checklist de validation par sprint (voir §4)
- Tests passent localement ET en CI
- Pas de `# TODO` ou `# FIXME` sans ticket associé

### 1.4 Suivi de Progression

#### Marquage des tâches terminées

- **OBLIGATOIRE** : Chaque tâche terminée DOIT être marquée `[x]` dans ce plan
- Les tableaux de tâches utilisent ✅ en préfixe pour les tâches complétées
- Les livrables et gates de livraison utilisent `[x]` au lieu de `[ ]`
- Mettre à jour ce fichier **immédiatement** après chaque sprint terminé
- Un sprint n'est considéré terminé que quand TOUTES ses gates sont `[x]`

### 1.5 Migration de Données

#### Sécurité

- **TOUJOURS** créer un backup avant modification de schéma
- Scripts de migration **idempotents** (re-exécutables)
- Validation des données **AVANT** et **APRÈS** migration
- Journalisation exhaustive des opérations

#### Compatibilité

- Migration **progressive** : 1 joueur à la fois, validation, puis suivant
- VIEWs de compatibilité pour l'UI pendant la transition
- Rollback plan documenté et testé
- Pas de suppression de données avant validation finale

---

## 2. Stratégie de Migration

### 2.1 Philosophie : Big Bang Contrôlé

**Approche** : Migration complète en une seule phase BUT avec validation incrémentale

#### Pourquoi Big Bang ?

✅ **Avantages** :
- Pas de code de compatibilité hybride à maintenir
- Simplification immédiate de l'architecture
- ROI immédiat (pas d'attente de phases multiples)

⚠️ **Risques Atténués** :
- Validation joueur par joueur (Chocoboflor → Madina → JGtm → xxdame)
- Backups à chaque étape
- Tests de régression complets
- Rollback plan documenté

### 2.2 Ordre des Opérations

```
Sprint 0  : Audit & Backups                          (1j)
Sprint 1  : Infrastructure shared_matches.duckdb     (2j)
Sprint 2  : Migration des données (4 joueurs)        (3j)  ✅ TERMINÉ
Sprint 3  : Refactoring Sync Engine                  (3j)  ✅ TERMINÉ
Sprint 4  : Refactoring DuckDBRepository             (2j)
Sprint 5  : Refactoring UI (VIEWs → Queries natives) (3j)
Sprint 6  : Optimisation API (PLAN_OPTIMISATION)     (2j)
Sprint 7  : Tests & Couverture (PLAN_TESTS)          (2j)
Sprint 8  : Finalisation & Release v5.0              (2j)
```

**Total** : 18 jours ouvrés (peut descendre à 14j avec parallélisation S3/S4)

### 2.3 Données Partagées vs Personnelles

#### ✅ Stockage COMMUN (shared_matches.duckdb)

Toutes les données extraites de `MatchStats.Players[]` (API collective) :

| Table | Contenu | Source API |
|-------|---------|------------|
| `match_registry` | Métadonnées match (map, playlist, scores) | `MatchInfo` |
| `match_participants` | outcome, team_id, rank, score, K/D/A, accuracy | `Players[]` |
| `medals_earned` | Médailles de TOUS les joueurs | `Players[].Medals[]` |
| `highlight_events` | Tous les kills/deaths filmés | Films API |
| `xuid_aliases` | Mapping global xuid→gamertag | `Players[].Gamertag` |

#### ✅ Stockage PERSONNEL (players/{gt}/stats.duckdb)

Uniquement ce qui **NE PEUT PAS** être obtenu collectivement :

| Table | Contenu | Raison |
|-------|---------|--------|
| `player_match_enrichment` | performance_score, session_id, is_with_friends | Calculé depuis MON historique |
| `teammates_aggregate` | Stats coéquipiers agrégées | Depuis MON point de vue |
| `antagonists` | Rivalités | Depuis MON point de vue |
| `media_files` | MES fichiers médias | MES captures/vidéos |
| `media_match_associations` | MES associations | MES fichiers associés |

---

## 2bis. Analyses de Contexte Préliminaires (Sprints 3-8)

> **Objectif** : Accélérer le démarrage de chaque sprint en documentant à l'avance les fichiers concernés, les fonctions réutilisables, les dépendances et les points d'attention.

---

### Sprint 3 — Contexte Préliminaire : Refactoring Sync Engine

#### Fichiers Principaux Concernés

| Fichier | Taille | Rôle | Modifications Prévues |
|---------|--------|------|----------------------|
| `src/data/sync/engine.py` | 1249 lignes | Moteur de sync principal | Ajouter détection shared, méthodes `_process_known_match()` et `_process_new_match()` |
| `src/data/sync/transformers.py` | 1469 lignes | Transformations JSON→DuckDB | Créer/adapter `extract_all_medals()` pour TOUS les joueurs |
| `src/data/sync/batch_insert.py` | ~300 lignes | Insertions batch DuckDB | Nouvelles fonctions d'insertion vers shared |
| `src/data/sync/models.py` | ~200 lignes | Modèles Pydantic | Possiblement ajouter `SharedMatchStatus` model |

#### Fonctions Existantes Réutilisables

```python
# src/data/sync/engine.py
async def _process_single_match(self, client, match_id, options) -> dict
    # Ligne 654 - À splitter en _process_known_match() et _process_new_match()
    # Actuellement séquentiel : stats → skill → events

# src/data/sync/transformers.py (ligne 1095)
def extract_participants(match_json: dict) -> list[MatchParticipantRow]
    # DÉJÀ FONCTIONNEL - Extrait TOUS les joueurs depuis Players[]
    # Parfait pour peupler shared.match_participants

def extract_xuids_from_match(match_json: dict) -> list[int]  # ligne 1044
    # Utilisé pour les appels skill - À conserver

def extract_medals(stats_json: dict, xuid: str) -> list[MedalEarnedRow]  # ligne 1243
    # ACTUEL : 1 seul joueur
    # À CRÉER : extract_all_medals() pour TOUS les joueurs
```

#### Points d'Attention Critiques

**1. Parallélisation API (actuellement séquentiel)**

```python
# AVANT (ligne 685-691 engine.py)
if options.with_skill and xuids:
    skill_json = await client.get_skill_stats(match_id, xuids)

if options.with_highlight_events:
    highlight_events = await client.get_highlight_events(match_id)

# À REMPLACER PAR (asyncio.gather)
tasks = []
if options.with_skill and xuids:
    tasks.append(client.get_skill_stats(match_id, xuids))
else:
    tasks.append(asyncio.sleep(0))
    
if options.with_highlight_events:
    tasks.append(client.get_highlight_events(match_id))
else:
    tasks.append(asyncio.sleep(0))

results = await asyncio.gather(*tasks, return_exceptions=True)
skill_json = results[0] if not isinstance(results[0], Exception) else None
highlight_events = results[1] if not isinstance(results[1], Exception) else []
```

**2. Gestion du Lock DB (_db_lock)**

- `async with self._db_lock:` — Ligne 730  
- ⚠️ Faudra un second lock pour shared_matches ou partager le même ?  
- **Décision** : Lock séparé `_shared_db_lock` pour éviter contention

**3. Connexion Shared**

```python
# Ajouter dans __init__ (ligne 250)
self._shared_db_path: Path | None = None
self._shared_connection: duckdb.DuckDBPyConnection | None = None
self._shared_db_lock = asyncio.Lock()

# Nouvelle méthode
def _get_shared_connection(self) -> duckdb.DuckDBPyConnection:
    if self._shared_connection is None:
        self._shared_connection = duckdb.connect(str(self._shared_db_path))
        self._shared_connection.execute("SET enable_object_cache = true")
    return self._shared_connection
```

#### Dépendances Sprint 1 & 2

- ✅ `shared_matches.duckdb` créée (Sprint 1)
- ✅ Schema validé (6 tables) (Sprint 1)
- ⚠️ Données migrées pour 4 joueurs (Sprint 2) — **Blocker si non terminé**

#### Estimation de Complexité

| Tâche | Complexité | Risque | Temps estimé |
|-------|-----------|--------|--------------|
| Détection match partagé | Faible | Faible | 1h |
| `_process_known_match()` | Moyenne | Moyen | 3h |
| `_process_new_match()` | Moyenne | Moyen | 3h |
| `extract_all_medals()` | Faible | Faible | 2h |
| Insertions vers shared | Moyenne | Moyen | 4h |
| Tests unitaires | Moyenne | Faible | 3h |

**Total** : ~16h (sur 20-22h prévues)

---

### Sprint 4 — Contexte Préliminaire : Refactoring DuckDBRepository

#### Fichiers Principaux Concernés

| Fichier | Taille | Rôle | Modifications Prévues |
|---------|--------|------|----------------------|
| `src/data/repositories/duckdb_repo.py` | 1114 lignes | Repository principal | Ajouter ATTACH shared, refactorer queries |
| `src/data/repositories/_match_queries.py` | ~400 lignes | Queries matchs | Adapter pour lire depuis `shared.*` |
| `src/data/repositories/_roster_loader.py` | ~250 lignes | Chargement rosters | Modifier pour lire `shared.match_participants` |
| `src/data/repositories/_antagonists_repo.py` | ~200 lignes | Chargement antagonistes | Possiblement adapter si dépend du roster |

#### Pattern ATTACH Existant (Réutilisable)

```python
# DÉJÀ IMPLÉMENTÉ pour metadata (ligne 122-144)
def _get_connection(self) -> duckdb.DuckDBPyConnection:
    if self._connection is None:
        self._connection = duckdb.connect(str(self._player_db_path), read_only=self._read_only)
        
        # ATTACH metadata (existant)
        if self._metadata_db_path.exists() and "meta" not in self._attached_dbs:
            try:
                self._connection.execute(
                    f"ATTACH '{self._metadata_db_path}' AS meta (READ_ONLY)"
                )
                self._attached_dbs.add("meta")
            except Exception as e:
                # Gestion erreur "already attached"
                pass
    return self._connection

# À AJOUTER : ATTACH shared_matches (même pattern)
if self._shared_db_path.exists() and "shared" not in self._attached_dbs:
    self._connection.execute(
        f"ATTACH '{self._shared_db_path}' AS shared (READ_ONLY)"
    )
    self._attached_dbs.add("shared")
```

#### Queries Critiques à Adapter

**1. load_matches() — Ligne ~200**

```sql
-- AVANT (v4) : Tout depuis match_stats local
SELECT 
    match_id, xuid, kills, deaths, assists, accuracy,
    outcome, team_id, rank, score AS personal_score,
    start_time, map_name, playlist_name, mode_category
FROM match_stats
WHERE xuid = ?
ORDER BY start_time DESC

-- APRÈS (v5) : JOIN shared + enrichment
SELECT 
    -- Données communes depuis shared.match_participants
    p.match_id, p.xuid, p.kills, p.deaths, p.assists,
    p.outcome, p.team_id, p.rank, p.score AS personal_score,
    p.damage_dealt, p.damage_taken, p.shots_fired, p.shots_hit,
    
    -- Métadonnées depuis shared.match_registry
    r.start_time, r.end_time, r.map_name, r.playlist_name, 
    r.mode_category, r.is_ranked,
    
    -- Enrichissement personnel depuis player DB
    e.performance_score, e.session_id, e.session_label, e.is_with_friends
    
FROM shared.match_participants p
INNER JOIN shared.match_registry r ON r.match_id = p.match_id
LEFT JOIN player_match_enrichment e ON e.match_id = p.match_id
WHERE p.xuid = ?
ORDER BY r.start_time DESC
```

**2. load_match_participants() — Ligne ~300**

```sql
-- AVANT : match_participants local (seulement les joueurs déjà trackés)
SELECT * FROM match_participants WHERE match_id = ?

-- APRÈS : shared.match_participants (TOUS les joueurs du match)
SELECT 
    p.match_id, p.xuid, p.team_id, p.outcome, p.rank,
    p.score, p.kills, p.deaths, p.assists,
    COALESCE(a.gamertag, 'Unknown') as gamertag
FROM shared.match_participants p
LEFT JOIN shared.xuid_aliases a ON a.xuid = p.xuid
WHERE p.match_id = ?
ORDER BY p.rank ASC
```

**3. load_highlight_events()**

```sql
-- AVANT : highlight_events local
SELECT * FROM highlight_events WHERE match_id = ?

-- APRÈS : shared.highlight_events
SELECT * FROM shared.highlight_events WHERE match_id = ?
```

#### Points d'Attention Critiques

**1. Gestion des DB Absentes**

```python
# Cas où shared_matches.duckdb n'existe pas encore
# (transition progressive ou environnement de test)
if not self._shared_db_path.exists():
    logger.warning(f"shared_matches.duckdb absent : {self._shared_db_path}")
    # Fallback sur les queries v4 ? Ou erreur explicite ?
    # Décision : Erreur explicite (pas de fallback hybride)
```

**2. Performances ATTACH**

- DuckDB 1.4.4+ : 1 fichier = 1 connexion exclusive
- ATTACH en READ_ONLY économise la RAM
- `SET enable_object_cache = true` déjà utilisé (ligne ~130)

**3. Migration des Tests**

Tous les tests `test_duckdb_repository.py` (101 tests) devront être adaptés :
- Mocker `shared_matches.duckdb`
- Créer fixtures avec données partagées
- Valider les JOINs

#### Mixins Impactés

| Mixin | Fichier | Impact | Action |
|-------|---------|--------|--------|
| `MatchQueriesMixin` | `_match_queries.py` | ⭐ Fort | Refactorer toutes les queries |
| `RosterLoaderMixin` | `_roster_loader.py` | ⭐ Fort | Lire depuis `shared.match_participants` |
| `MaterializedViewsMixin` | `_materialized_views.py` | Moyen | Vérifier compatibilité |
| `AntagonistsMixin` | `_antagonists_repo.py` | Faible | Possiblement adapter |

#### Estimation de Complexité

| Tâche | Complexité | Risque | Temps estimé |
|-------|-----------|--------|--------------|
| ATTACH shared_matches | Faible | Faible | 1h |
| Adapter load_matches() | Moyenne | Moyen | 2h |
| Adapter load_participants() | Faible | Faible | 1h |
| Adapter load_events() | Faible | Faible | 30min |
| Adapter load_medals() | Faible | Faible | 1h |
| Tests repository | Moyenne | Moyen | 3h |
| Tests intégration UI | Forte | Élevé | 3h |

**Total** : ~11.5h (sur 13-15h prévues)

---

### Sprint 5 — Contexte Préliminaire : Refactoring UI Big Bang

#### Pages UI Inventoriées (24 fichiers)

| Page | Fichier | Taille | Utilise `repo.load_*` | Complexité |
|------|---------|--------|----------------------|-----------|
| Career | `career.py` | ~400 lignes | ✅ `load_career_progression()` | Faible |
| Match History | `match_history.py` | ~600 lignes | ✅ `load_matches()` | Moyenne |
| Match View | `match_view.py` + helpers | ~800 lignes | ✅ `load_match_participants()` | Forte |
| Timeseries | `timeseries.py` | ~220 lignes | ✅ `load_matches()` | Faible |
| Teammates | `teammates.py` + modules | ~1200 lignes | ✅ `load_matches_with_teammate()` | Forte |
| Maps | `maps.py` | ~350 lignes | ✅ `load_matches()` | Faible |
| Modes | `modes.py` | ~350 lignes | ✅ `load_matches()` | Faible |
| Medals | `medals.py` | ~300 lignes | ✅ `load_matches()`, `load_medals_*()` | Moyenne |
| Media Library | `media_library.py` | ~500 lignes | ✅ `load_matches()` | Moyenne |
| Session Compare | `session_compare.py` | ~450 lignes | ✅ `load_matches()` | Moyenne |
| Win/Loss | `win_loss.py` | ~200 lignes | ✅ `load_matches()` | Faible |
| Objective Analysis | `objective_analysis.py` | ~400 lignes | ✅ `load_matches()` | Moyenne |

**Total** : 12 pages principales + 10 modules helpers = **22 fichiers**

#### Pattern de Refactoring Type

**CAS 1 : Page simple (load_matches uniquement)**

```python
# AVANT (v4) - Pas de changement visible
def show_timeseries_page(repo: DuckDBRepository):
    df = repo.load_matches(limit=500)
    # ... graphiques avec df

# APRÈS (v5) - Aucun changement !
def show_timeseries_page(repo: DuckDBRepository):
    df = repo.load_matches(limit=500)  # Maintenant JOIN shared + enrichment en interne
    # ... graphiques avec df (même structure)
```

**CAS 2 : Page avec roster (match_participants)**

```python
# AVANT (v4) - Roster partiel (seulement joueurs trackés)
roster = repo.load_match_participants(match_id)
# roster.shape = (2, N) si seulement 2 joueurs trackés sur 8

# APRÈS (v5) - Roster complet (TOUS les joueurs du match)
roster = repo.load_match_participants(match_id)
# roster.shape = (8, N) systématiquement
# ⚠️ Adapter l'UI si elle supposait roster partiel
```

**CAS 3 : Page avec médailles**

```python
# AVANT (v4) - Médailles seulement du joueur principal
medals = repo.load_medals_for_match(match_id)

# APRÈS (v5) - Besoin de filtrer par xuid explicitement
medals = repo.load_medals_for_match(match_id, xuid=repo.xuid)
# Ou charger TOUTES les médailles du match
all_medals = repo.load_medals_for_match(match_id, xuid=None)  # Si implémenté
```

#### Points d'Attention Critiques

**1. Changements de Colonnes**

| Colonne v4 | Colonne v5 | Impact |
|-----------|------------|--------|
| `my_team_score` | `team_0_score` / `team_1_score` | ⚠️ Calcul à adapter |
| `enemy_team_score` | `team_0_score` / `team_1_score` | ⚠️ Calcul à adapter |
| `score` | `personal_score` | Renommage |
| - | `duration_seconds` | Nouvelle (depuis registry) |
| - | `player_count` | Nouvelle (depuis registry) |

**2. Rosters Complets (8 joueurs au lieu de 1-2)**

Pages impactées :
- `match_view.py` — Affichage tableau joueurs
- `teammates.py` — Détection coéquipiers
- `objective_analysis.py` — Analyse contributions

Action : Vérifier que les boucles et filtres gèrent bien 8+ joueurs.

**3. Performance `st.plotly_chart()`**

Rappel règle : **JAMAIS** `use_container_width=True` (déprécié).

```python
# ❌ INTERDIT
st.plotly_chart(fig, use_container_width=True)

# ✅ CORRECT
st.plotly_chart(fig, width="stretch")
```

#### VIEWs de Compatibilité à Supprimer (Sprint 5.11)

Si créées pendant Sprint 2-4 pour transition :

```sql
-- Exemple : VIEW match_stats pointant vers shared
DROP VIEW IF EXISTS match_stats;
DROP VIEW IF EXISTS match_participants;
-- etc.
```

**Script** : `scripts/remove_compat_views.py`

#### Tests UI Existants

Fichiers de tests UI à adapter :

| Test | Fichier | Assertions à vérifier |
|------|---------|----------------------|
| Career page | `test_career_page.py` | Affichage progression |
| Match View | `test_app_phase2.py` | Roster complet (8 joueurs) |
| Timeseries | `test_new_timeseries_sections.py` | Graphiques cumulatifs |
| Teammates | `test_teammates_refonte.py` | Détection coéquipiers |
| Filters | `test_cross_page_filter_persistence.py` | Filtres persistants |

**Nouveaux tests** : `tests/ui/test_all_pages_v5.py` (smoke tests complets)

#### Estimation de Complexité

| Tâche | Nb fichiers | Temps estimé |
|-------|-------------|--------------|
| Audit queries existantes | 22 | 1h |
| Refactoring pages simples (Career, Timeseries, Maps, Modes, Win/Loss) | 5 | 5×2h = 10h |
| Refactoring pages moyennes (Match History, Medals, Media, Objective) | 4 | 4×2h = 8h |
| Refactoring pages complexes (Match View, Teammates, Session) | 3 | 3×2.5h = 7.5h |
| Suppression VIEWs compat | 1 script | 1h |
| Tests UI automatisés | 1 fichier | 4h |

**Total** : ~31.5h → **Optimisation possible** : Paralléliser pages simples → ~22h réaliste

---

### Sprint 6 — Contexte Préliminaire : Optimisation API

#### Optimisations Identifiées (PLAN_OPTIMISATION_SYNC.md)

**1. Parallélisation Appels API**

```python
# ACTUELLEMENT (engine.py ligne 685-691)
# Séquentiel : skill → events (2×latence réseau)
skill_json = await client.get_skill_stats(match_id, xuids)
highlight_events = await client.get_highlight_events(match_id)

# CIBLE (asyncio.gather)
tasks = [
    client.get_skill_stats(match_id, xuids) if options.with_skill else asyncio.sleep(0),
    client.get_highlight_events(match_id) if options.with_highlight_events else asyncio.sleep(0),
]
results = await asyncio.gather(*tasks, return_exceptions=True)

# GAIN : -50% latence sur les appels parallélisables
```

**2. Désactivation Performance Score pendant Sync**

```python
# ACTUELLEMENT (engine.py ~ligne 900)
# Performance score calculé PENDANT le sync (bloque l'insertion)
if _PERF_SCORE_AVAILABLE:
    perf_score = compute_relative_performance_score(...)
    # Requiert charger TOUT l'historique → lent

# CIBLE (désactiver pendant sync)
# Marquer performance_score = NULL pendant sync
# Post-sync : batch_compute_performance_scores()
```

**Nouvelle fonction à créer** :

```python
async def batch_compute_performance_scores(self) -> int:
    """Calcule performance_score pour tous les matchs où NULL.
    
    Exécuté POST-sync pour ne pas bloquer l'insertion.
    Utilise Polars pour calcul vectorisé sur tout l'historique.
    
    Returns:
        Nombre de matchs mis à jour.
    """
    # 1. Charger TOUS les matchs depuis shared + enrichment
    # 2. Grouper par session
    # 3. Calculer perf scores en batch (Polars)
    # 4. UPDATE player_match_enrichment
```

**3. Batching des Insertions DB**

```python
# ACTUELLEMENT (engine.py ~ligne 730)
# Commit APRÈS CHAQUE match
async with self._db_lock:
    self._insert_match_row(match_row)
    conn.commit()  # ← Chaque match = 1 commit

# CIBLE (commit tous les 10 matchs)
batch_buffer = []
for match in matches:
    row = transform_match(match)
    batch_buffer.append(row)
    
    if len(batch_buffer) >= 10:
        async with self._db_lock:
            for row in batch_buffer:
                self._insert_match_row(row)
            conn.commit()  # ← 1 commit pour 10 matchs
        batch_buffer.clear()
```

**4. Rate Limit Augmenté**

```python
# ACTUELLEMENT (src/data/sync/api_client.py)
DEFAULT_RATE_LIMIT = 5  # req/s
parallel_matches = 3    # Matchs en parallèle

# CIBLE (selon PLAN_OPTIMISATION)
DEFAULT_RATE_LIMIT = 10  # req/s
parallel_matches = 5     # Matchs en parallèle

# Vérifier limites API Halo :
# - Pas de limite documentée stricte
# - Tests empiriques OK jusqu'à 10 req/s
```

#### Fichiers à Modifier

| Fichier | Modifications | Risque |
|---------|--------------|--------|
| `src/data/sync/engine.py` | Parallélisation API, batching commits, perf score désactivé | Moyen |
| `src/data/sync/api_client.py` | Rate limit augmenté | Faible |
| `src/data/sync/models.py` | Nouveau champ `defer_performance_score` dans SyncOptions | Faible |
| `src/analysis/performance_score.py` | Adapter pour calcul batch (Polars) | Faible |

#### Gains Attendus (Calculés)

| Métrique | v4 (avant Sprint 6) | v5 Sprint 6 | Gain |
|----------|---------------------|-------------|------|
| Temps/match (nouveau) | 3s | 2s | **-33%** |
| Temps/match (partagé 95%) | 1s | 0.5s | **-50%** |
| Sync 100 matchs nouveaux | 5 min | 3.5 min | **-30%** |
| Commits DB/100 matchs | 100 | 10 | **-90%** (I/O disque) |

#### Tests de Validation

```python
# tests/performance/test_sync_v5.py
@pytest.mark.benchmark
async def test_sync_100_matches_new():
    """Benchmark sync 100 matchs nouveaux."""
    start = time.time()
    result = await engine.sync_full(SyncOptions(max_matches=100))
    duration = time.time() - start
    
    assert duration < 180  # < 3 minutes
    assert result.matches_inserted == 100

@pytest.mark.benchmark
async def test_sync_100_matches_shared():
    """Benchmark re-sync 100 matchs partagés (détection économie API)."""
    # Pré-remplir shared_matches avec 100 matchs
    # Re-sync pour le même joueur
    start = time.time()
    result = await engine.sync_full(SyncOptions(max_matches=100))
    duration = time.time() - start
    
    assert duration < 60  # < 1 minute (10× plus rapide)
    assert result.api_calls_saved >= 150  # ~1.5 appels économisés par match
```

#### Estimation de Complexité

| Tâche | Complexité | Temps estimé |
|-------|-----------|--------------|
| Parallélisation API (asyncio.gather) | Faible | 2h |
| Désactiver perf score pendant sync | Faible | 1h |
| Créer batch_compute_performance_scores() | Moyenne | 3h |
| Batching commits DB | Moyenne | 2h |
| Rate limit augmenté | Faible | 30min |
| Tests benchmark | Moyenne | 2h |
| Documentation optimisations | Faible | 1h |

**Total** : ~11.5h (sur 11-13h prévues)

---

### Sprint 7 — Contexte Préliminaire : Tests & Couverture

#### État Actuel de la Couverture (Estimé baseline)

| Module | Fichiers | Couverture actuelle | Objectif v5 |
|--------|----------|---------------------|-------------|
| `src/data/sync/` | 8 fichiers | ~65% | **85%** |
| `src/data/repositories/` | 6 fichiers | ~70% | **85%** |
| `src/ui/pages/` | 24 fichiers | ~15% | **50%** |
| `src/analysis/` | 12 fichiers | ~75% | **80%** |
| `src/visualization/` | 6 fichiers | ~20% | **40%** |
| **Global** | ~80 fichiers | **~41%** | **65%** |

#### Tests Existants à Adapter (Inventaire)

**Migration Tests**

| Fichier | Tests | À adapter ? |
|---------|-------|------------|
| `test_shared_schema.py` | 45 tests | ✅ Déjà créé (Sprint 1) |
| `test_migrations.py` | 8 tests | ⚠️ Ajouter tests migration v4→v5 |

**Sync Tests**

| Fichier | Tests | À adapter ? |
|---------|-------|------------|
| `test_sync_engine.py` | 23 tests | ✅ Adapter pour shared_matches |
| `test_delta_sync.py` | 12 tests | ✅ Valider détection matchs partagés |
| `test_sync_performance_score.py` | 6 tests | ✅ Adapter pour batch compute |

**Repository Tests**

| Fichier | Tests | À adapter ? |
|---------|-------|------------|
| `test_duckdb_repository.py` | 101 tests | ⚠️ **CRITIQUE** - Adapter pour ATTACH shared |
| `test_duckdb_repository_schema_contract.py` | 15 tests | ✅ Valider nouveaux schémas |

**UI Tests** (Smoke tests, peu nombreux actuellement)

| Fichier | Tests | À créer/adapter ? |
|---------|-------|-------------------|
| `test_career_page.py` | 4 tests | ✅ Valider no regression |
| `test_app_phase2.py` | 8 tests | ✅ Adapter pour roster complet |
| `test_teammates_refonte.py` | 12 tests | ✅ Adapter pour shared data |
| `test_all_pages_v5.py` | 0 (à créer) | ⭐ **NOUVEAU** - Smoke tests toutes pages |

#### Nouveaux Tests à Créer

**1. Tests Migration (tests/migration/test_migration_v5.py)**

```python
def test_migrate_player_to_shared_idempotent():
    """Re-migrer un joueur ne duplique pas les données."""

def test_migrate_detects_shared_matches():
    """Migration détecte et incrémente player_count."""

def test_migrate_preserves_data_integrity():
    """Toutes les données migrées sont cohérentes."""

def test_rollback_migration():
    """Rollback restaure l'état v4 complet."""
```

**2. Tests Sync Shared (tests/test_sync_shared_v5.py)**

```python
async def test_process_known_match_saves_api_calls():
    """Match déjà dans shared économise 1-2 appels API."""

async def test_process_new_match_populates_shared():
    """Nouveau match insère dans shared.match_registry + participants."""

async def test_parallel_api_calls():
    """Skill et events appelés en parallèle (asyncio.gather)."""

async def test_batch_compute_performance_scores():
    """Calcul batch post-sync met à jour tous les NULL."""
```

**3. Tests Repository Shared (tests/test_repository_shared_v5.py)**

```python
def test_attach_shared_matches_success():
    """ATTACH shared_matches fonctionne."""

def test_load_matches_joins_shared_and_enrichment():
    """load_matches retourne données depuis JOIN shared + enrichment."""

def test_load_participants_returns_all_players():
    """load_match_participants retourne TOUS les joueurs (8+)."""

def test_shared_db_missing_raises_error():
    """Absence de shared_matches.duckdb lève une erreur explicite."""
```

**4. Tests UI (tests/ui/test_all_pages_v5.py)**

```python
@pytest.mark.parametrize("page_name", [
    "career", "match_history", "match_view", "timeseries",
    "teammates", "maps", "modes", "medals", "media_library"
])
def test_page_renders_without_error(page_name):
    """Chaque page se charge sans erreur."""

def test_match_view_displays_full_roster():
    """Match view affiche 8+ joueurs (roster complet)."""

def test_teammates_page_detects_shared_matches():
    """Page teammates détecte correctement les matchs partagés."""
```

**5. Tests de Charge (tests/performance/test_load_v5.py)**

```python
@pytest.mark.slow
def test_load_1000_matches():
    """Repository charge 1000 matchs en < 2s."""

@pytest.mark.slow
def test_sync_500_matches():
    """Sync 500 matchs en < 15 minutes."""
```

#### Outils de Couverture

```bash
# Couverture complète HTML
python -m pytest --cov=src --cov-report=html --cov-report=term-missing

# Couverture par module
python -m pytest --cov=src/data/sync --cov-report=term

# Vérifier seuil minimal
python scripts/check_coverage_threshold.py --min 65
```

#### Estimation de Complexité

| Tâche | Nb tests à créer/adapter | Temps estimé |
|-------|-------------------------|--------------|
| Tests migration v5 | ~15 tests | 3h |
| Tests sync shared | ~20 tests | 2h |
| Tests repository shared | ~25 tests | 2h |
| Tests UI (smoke tests) | ~30 tests | 4h |
| Tests de charge | ~10 tests | 2h |
| Adapter tests existants | ~50 tests | 2h |
| Rapport couverture final | 1 rapport | 1h |
| Documentation tests | 1 fichier | 1h |

**Total** : ~17h (sur 15-17h prévues)

---

### Sprint 8 — Contexte Préliminaire : Finalisation & Release

#### Code Mort à Nettoyer (Inventaire Préliminaire)

**1. VIEWs de Compatibilité (si créées)**

```sql
-- À supprimer si présentes dans player DBs
DROP VIEW IF EXISTS match_stats;
DROP VIEW IF EXISTS match_participants;
DROP VIEW IF EXISTS highlight_events;
DROP VIEW IF EXISTS medals_earned;
```

**Script** : `scripts/migration/remove_all_compat_views.py`

**2. Fonctions Legacy à Vérifier**

```python
# src/data/sync/engine.py
# Anciennes méthodes à vérifier si encore utilisées :
# - _insert_match_row_v4() (si créée pour transition)
# - _sync_without_shared() (si fallback créé)

# src/data/repositories/duckdb_repo.py
# - _load_matches_v4() (si fallback créé)
```

**3. Imports Inutilisés**

```bash
# Détecter imports inutilisés
ruff check src/ --select F401  # Unused imports
autoflake --remove-all-unused-imports --in-place src/**/*.py
```

**4. Code Commenté**

```bash
# Rechercher code commenté (à supprimer)
grep -rn "^[[:space:]]*#.*def \|^[[:space:]]*#.*class " src/
```

**5. Archivage Documentation Temporaire (.ai/)**

```bash
# Archiver les documents de travail v5.0
mkdir -p .ai/archive/v5.0/

# Plans de projet
mv .ai/PLAN_V5_SHARED_MATCHES.md .ai/archive/v5.0/
mv .ai/PLAN_UNIFIE.md .ai/archive/v5.0/  # Ancien plan v4.5 (obsolète après v5)

# Rapports et analyses v5
mv .ai/v5-*.md .ai/archive/v5.0/  # Tous les docs v5 (baseline, migration, retrospective)
mv .ai/reports/v5-*.* .ai/archive/v5.0/reports/  # Rapports benchmark/coverage v5

# Garder seulement les docs actifs
# - thought_log.md (journal permanent)
# - project_map.md (cartographie permanente)
# - SPRINT_EXPLORATION.md (catalogue données)
# - *.md actifs pour v6+
```

**Script** : `scripts/archive_v5_docs.sh`

**Documents à archiver** :
- `PLAN_V5_SHARED_MATCHES.md` (ce plan)
- `PLAN_UNIFIE.md` ⭐ **NOUVEAU** (ancien plan v4.5, obsolète)
- `v5-baseline-audit.md`
- `v5-match-overlap-analysis.md`
- `v5-migration-report.md`
- `v5-retrospective.md`
- `reports/v5-*` (tous les rapports benchmark/coverage v5)

**Documents à conserver** :
- `thought_log.md` (journal permanent)
- `project_map.md` (mise à jour pour v5)
- `SPRINT_EXPLORATION.md`
- `ARCHITECTURE_ROADMAP.md`
- Audits permanents (SQLITE_TO_DUCKDB_AUDIT.md, PANDAS_TO_POLARS_AUDIT.md)

**6. Archivage Scripts Spécifiques v5**

```bash
# Archiver les scripts de migration v5 (usage unique)
mkdir -p scripts/_archive/migration_v5/
mv scripts/migration/create_shared_matches_db.py scripts/_archive/migration_v5/
mv scripts/migration/schema_v5.sql scripts/_archive/migration_v5/
mv scripts/migration/migrate_player_to_shared.py scripts/_archive/migration_v5/
mv scripts/migration/validate_migration.py scripts/_archive/migration_v5/
mv scripts/migration/validate_shared_schema.py scripts/_archive/migration_v5/
mv scripts/migration/create_compat_views.py scripts/_archive/migration_v5/
mv scripts/migration/remove_all_compat_views.py scripts/_archive/migration_v5/

# Archiver les scripts benchmark v5 (comparaison ponctuelle)
mkdir -p scripts/_archive/benchmark_v5/
mv scripts/benchmark_v4_vs_v5.py scripts/_archive/benchmark_v5/
mv scripts/benchmark_sync_v4_vs_v5.py scripts/_archive/benchmark_v5/
mv scripts/validate_v5_improvements.py scripts/_archive/benchmark_v5/
mv scripts/test_e2e_v5.py scripts/_archive/benchmark_v5/

# CONSERVER les scripts réutilisables
# - scripts/backup_player.py
# - scripts/restore_player.py
# - scripts/diagnose_player_db.py
# - scripts/sync.py
# - scripts/backfill_data.py
# - etc.
```

**Raison** : Ces scripts sont spécifiques à la migration v4→v5 et n'ont plus d'utilité après la migration. Les archiver permet de conserver l'historique sans encombrer `scripts/` et `scripts/migration/`.

#### Documentation Obligatoire

| Document | Contenu | Statut |
|----------|---------|--------|
| `CHANGELOG.md` | Toutes les modifications v5.0 (format Keep a Changelog) | À mettre à jour |
| `README.md` | Section "Architecture v5" + gains de performance | À mettre à jour |
| `docs/ARCHITECTURE_V5.md` | Schéma complet shared_matches + flux de données | À créer |
| `docs/MIGRATION_V4_TO_V5.md` | Guide utilisateur pour migrer de v4 à v5 | À créer |
| `.ai/v5-retrospective.md` | Leçons apprises, difficultés rencontrées, améliorations futures | À créer |

#### Benchmark Final (Scripts à Créer)

**Script** : `scripts/benchmark_v4_vs_v5.py`

```python
def benchmark_storage():
    """Compare la taille des DBs v4 vs v5."""
    # v4 : 4 joueurs × 200 MB = 800 MB
    # v5 : shared (200 MB) + 4×30 MB = 320 MB
    # Gain : -60%

def benchmark_api_calls():
    """Compare le nombre d'appels API pour sync initiale."""
    # v4 : 4 joueurs × 3000 appels = 12000 appels
    # v5 : ~3300 appels (détection partage)
    # Gain : -72%

def benchmark_sync_time():
    """Compare le temps de sync pour 100 matchs."""
    # v4 : ~45 minutes
    # v5 : ~12 minutes
    # Gain : -73%

def benchmark_query_performance():
    """Compare les temps de query load_matches(limit=500)."""
    # v4 : ~80ms
    # v5 : ~60ms (ATTACH optimisé)
    # Gain : -25%
```

#### Checklist Revue de Code Complète

```bash
# 1. Formatage
black src/ tests/ scripts/
isort src/ tests/ scripts/

# 2. Linting
ruff check src/ tests/ scripts/ --fix

# 3. Type checking
mypy src/ --ignore-missing-imports

# 4. Tests
python -m pytest --cov=src --cov-report=html

# 5. Sécurité (secrets hardcodés)
git secrets --scan

# 6. Benchmark
python scripts/benchmark_v4_vs_v5.py --detailed

# 7. Validation schémas
python scripts/validate_all_schemas.py
```

#### Tag et Merge

```bash
# 1. Vérifier que tous les tests passent
python -m pytest

# 2. Créer le tag v5.0.0
git tag -a v5.0.0 -m "Release v5.0.0 - Shared Matches Architecture"

# 3. Push le tag
git push origin v5.0.0

# 4. Merge vers main
git checkout main
git merge v5/shared-matches-migration --no-ff
git push origin main

# 5. Créer la release GitHub
gh release create v5.0.0 \
  --title "LevelUp v5.0.0 - Shared Matches Architecture" \
  --notes-file docs/RELEASE_NOTES_V5.md
```

#### Estimation de Complexité

| Tâche | Temps estimé |
|-------|--------------|
| Nettoyage code mort | 2h |
| Mise à jour CHANGELOG.md | 1h |
| Mise à jour README.md | 1h |
| Documentation ARCHITECTURE_V5.md | 2h |
| Documentation MIGRATION_V4_TO_V5.md | 2h |
| Benchmark final | 2h |
| Revue de code complète | 3h |
| Archivage docs `.ai/` + PLAN_UNIFIE.md + scripts v5 | 45min |
| Tag + merge + release | 1h |

**Total** : ~14.75h (sur 14.5-16.5h prévues)

---

## 3. Sprints Détaillés

---

### Sprint 0 — Audit Baseline & Sécurisation (1 jour) ✅

**Objectif** : Établir l'état de référence et sécuriser les données existantes

#### Tâches

| # | Tâche | Fichier(s) | Durée |
|---|-------|-----------|-------|
| 0.1 | ✅ Créer branche `v5/shared-matches-migration` depuis `sprint14/isolation-backend-frontend` | Git | 15min |
| 0.2 | ✅ Backup COMPLET de toutes les DBs joueur + metadata | Scripts | 30min |
| 0.3 | ✅ Exporter schémas SQL actuels de toutes les DBs | `scripts/export_schemas.py` | 30min |
| 0.4 | ✅ Audit des données : comptage matchs, participants, events par joueur | `scripts/audit_current_data.py` | 1h |
| 0.5 | ✅ Documenter les taux de partage de matchs réels | `scripts/analyze_match_overlap.py` | 1h |
| 0.6 | ✅ Créer scripts de validation post-migration | `scripts/validate_migration.py` | 2h |
| 0.7 | ✅ Tagger commit de référence `pre-v5-migration` | Git | 10min |

#### Livrables

- [x] Fichier `.ai/v5-baseline-audit.md` (stats complètes)
- [x] Fichier `.ai/v5-match-overlap-analysis.md` (taux de partage)
- [x] Backup complet dans `backups/pre-v5-$(date)/`
- [x] Tag `pre-v5-migration` créé
- [x] Scripts de validation prêts

#### Tests de Validation

```bash
# Vérifier que les backups sont valides
python scripts/verify_backups.py backups/pre-v5-*/

# Vérifier baseline tests
python -m pytest -q --ignore=tests/integration

# Documenter le nombre de matchs par joueur
python scripts/audit_current_data.py --summary

# Analyser les matchs partagés
python scripts/analyze_match_overlap.py --matrix
```

#### Gate de Livraison

- [x] Backups validés (restoration testée sur 1 joueur)
- [x] Baseline tests passent à 100%
- [x] Documentation baseline complète
- [x] Tag `pre-v5-migration` créé

**Statut** : ✅ **TERMINÉ**  
**Estimation** : 1 jour (6-7h effectives)

---

### Sprint 1 — Infrastructure shared_matches.duckdb (2 jours) ✅

**Objectif** : Créer la base de données partagée avec schéma complet et index optimisés

#### Tâches

| # | Tâche | Fichier(s) | Durée |
|---|-------|-----------|-------|
| 1.1 | ✅ Créer DDL `match_registry` (table centrale) | `scripts/migration/schema_v5.sql` | 1h |
| 1.2 | ✅ Créer DDL `match_participants` (roster global) | Idem | 1h |
| 1.3 | ✅ Créer DDL `highlight_events` (events globaux) | Idem | 45min |
| 1.4 | ✅ Créer DDL `medals_earned` (médailles tous joueurs) | Idem | 45min |
| 1.5 | ✅ Créer DDL `xuid_aliases` (mapping global) | Idem | 30min |
| 1.6 | ✅ Créer index optimisés (match_id, xuid, start_time) | Idem | 1h |
| 1.7 | ✅ Script de création `create_shared_matches_db.py` | `scripts/migration/` | 2h |
| 1.8 | ✅ Tests unitaires du schéma (contraintes, types) | `tests/migration/test_shared_schema.py` | 2h |
| 1.9 | ✅ Documentation du schéma (diagramme ER) | `docs/SHARED_MATCHES_SCHEMA.md` | 1h |

#### Schéma SQL Principal

```sql
-- match_registry : Registre central de TOUS les matchs connus
CREATE TABLE match_registry (
    match_id VARCHAR PRIMARY KEY,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    
    -- Métadonnées du match
    playlist_id VARCHAR,
    playlist_name VARCHAR,
    map_id VARCHAR,
    map_name VARCHAR,
    pair_id VARCHAR,
    pair_name VARCHAR,
    game_variant_id VARCHAR,
    game_variant_name VARCHAR,
    mode_category VARCHAR,
    is_ranked BOOLEAN DEFAULT FALSE,
    is_firefight BOOLEAN DEFAULT FALSE,
    duration_seconds INTEGER,
    
    -- Scores des équipes
    team_0_score SMALLINT,
    team_1_score SMALLINT,
    
    -- Métadonnées de backfill (bitmask)
    backfill_completed INTEGER DEFAULT 0,
    participants_loaded BOOLEAN DEFAULT FALSE,
    events_loaded BOOLEAN DEFAULT FALSE,
    medals_loaded BOOLEAN DEFAULT FALSE,
    
    -- Tracking
    first_sync_by VARCHAR,              -- Gamertag du 1er joueur ayant sync ce match
    first_sync_at TIMESTAMP,
    last_updated_at TIMESTAMP,
    player_count SMALLINT DEFAULT 0,    -- Nb de joueurs trackés ayant ce match
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_registry_time ON match_registry(start_time);
CREATE INDEX idx_registry_playlist ON match_registry(playlist_id);
CREATE INDEX idx_registry_map ON match_registry(map_id);
CREATE INDEX idx_registry_player_count ON match_registry(player_count);

-- match_participants : TOUS les joueurs de TOUS les matchs
CREATE TABLE match_participants (
    match_id VARCHAR NOT NULL,
    xuid VARCHAR NOT NULL,
    
    -- Stats du joueur dans ce match (depuis MatchStats.Players[])
    team_id INTEGER,
    outcome INTEGER,                    -- 1=Tie, 2=Win, 3=Loss, 4=Left
    rank SMALLINT,                      -- Classement dans le match
    score INTEGER,                      -- Personal score
    
    -- K/D/A
    kills SMALLINT,
    deaths SMALLINT,
    assists SMALLINT,
    
    -- Précision
    shots_fired INTEGER,
    shots_hit INTEGER,
    
    -- Dégâts
    damage_dealt FLOAT,
    damage_taken FLOAT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (match_id, xuid),
    FOREIGN KEY (match_id) REFERENCES match_registry(match_id)
);

CREATE INDEX idx_participants_xuid ON match_participants(xuid);
CREATE INDEX idx_participants_match ON match_participants(match_id);
CREATE INDEX idx_participants_composite ON match_participants(match_id, xuid);

-- highlight_events : TOUS les événements filmés
CREATE SEQUENCE IF NOT EXISTS highlight_events_id_seq;
CREATE TABLE highlight_events (
    id INTEGER PRIMARY KEY DEFAULT nextval('highlight_events_id_seq'),
    match_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,        -- 'kill', 'death', etc.
    time_ms INTEGER,
    
    -- Identifiants
    killer_xuid VARCHAR,
    killer_gamertag VARCHAR,
    victim_xuid VARCHAR,
    victim_gamertag VARCHAR,
    
    type_hint INTEGER,
    raw_json VARCHAR,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (match_id) REFERENCES match_registry(match_id)
);

CREATE INDEX idx_events_match ON highlight_events(match_id);
CREATE INDEX idx_events_killer ON highlight_events(killer_xuid);
CREATE INDEX idx_events_victim ON highlight_events(victim_xuid);

-- medals_earned : Médailles de TOUS les joueurs
CREATE TABLE medals_earned (
    match_id VARCHAR NOT NULL,
    xuid VARCHAR NOT NULL,              -- De QUEL joueur
    medal_name_id INTEGER NOT NULL,
    count SMALLINT NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (match_id, xuid, medal_name_id),
    FOREIGN KEY (match_id) REFERENCES match_registry(match_id)
);

CREATE INDEX idx_medals_match ON medals_earned(match_id);
CREATE INDEX idx_medals_xuid ON medals_earned(xuid);
CREATE INDEX idx_medals_composite ON medals_earned(match_id, xuid);

-- xuid_aliases : Mapping global xuid→gamertag
CREATE TABLE xuid_aliases (
    xuid VARCHAR PRIMARY KEY,
    gamertag VARCHAR NOT NULL,
    last_seen TIMESTAMP,
    source VARCHAR,                     -- 'api', 'film', 'manual'
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_aliases_gamertag ON xuid_aliases(gamertag);
```

#### Livrables

- [x] Fichier `scripts/migration/schema_v5.sql` complet
- [x] Script `scripts/migration/create_shared_matches_db.py` fonctionnel
- [x] `data/warehouse/shared_matches.duckdb` créée et validée (via script, 45 tests passent)
- [x] Tests `tests/migration/test_shared_schema.py` passent (45/45)
- [x] Documentation `docs/SHARED_MATCHES_SCHEMA.md` complète

#### Tests de Validation

```bash
# Créer la DB shared_matches
python scripts/migration/create_shared_matches_db.py

# Vérifier le schéma
python -m pytest tests/migration/test_shared_schema.py -v

# Valider les contraintes et index
python scripts/migration/validate_shared_schema.py

# Vérifier la taille (doit être quasi-vide)
ls -lh data/warehouse/shared_matches.duckdb  # ~100-200 KB attendu
```

#### Gate de Livraison

- [x] `shared_matches.duckdb` créée avec toutes les tables (6 tables)
- [x] Tous les index créés et validés (14 index)
- [x] Contraintes de clés étrangères actives
- [x] Tests de schéma passent à 100% (45/45)
- [x] Documentation complète avec diagramme ER

**Statut** : ✅ **TERMINÉ** — Commit `980df98`  
**Estimation** : 2 jours (11-13h effectives)

---

### Sprint 2 — Migration des Données (3 jours) ✅ TERMINÉ

**Objectif** : Migrer les données des 4 joueurs vers `shared_matches.duckdb` avec validation incrémentale

#### Stratégie

Migration **séquentielle** avec validation à chaque joueur :

1. **Chocoboflor** (base de référence, ~1000 matchs)
2. **Madina97294** (95% partagés → ~50 nouveaux matchs)
3. **JGtm** (75% partagés → ~250 nouveaux matchs)
4. **xxdameongamerxx** (100% partagés → ~0 nouveaux matchs)

#### Tâches

| # | Tâche | Fichier(s) | Durée |
|---|-------|-----------|-------|
| 2.1 | ✅ Script de migration générique `migrate_player_to_shared.py` | `scripts/migration/` | 3h |
| 2.2 | ✅ Fonction `extract_all_medals()` (TOUS les joueurs) | `src/data/sync/transformers.py` | 2h |
| 2.3 | ✅ Migration Chocoboflor + validation | Script | 2h |
| 2.4 | ✅ Migration Madina97294 + validation taux partage | Script | 1.5h |
| 2.5 | ✅ Migration JGtm + validation | Script | 1.5h |
| 2.6 | ✅ Migration XxDaemonGamerxX + validation 100% partage | Script | 1h |
| 2.7 | ✅ Validation croisée (cohérence des données) | Script intégré | 2h |
| 2.8 | ✅ Audit post-migration (comptage, doublons, orphelins) | Script intégré | 1h |
| 2.9 | ✅ Création VIEWs de compatibilité dans player DBs | `scripts/migration/create_compat_views.py` | 2h |

#### Script de Migration Principal

```python
# scripts/migration/migrate_player_to_shared.py
"""
Migre les données d'un joueur vers shared_matches.duckdb.

Logique :
1. Lire tous les matchs de data/players/{gamertag}/stats.duckdb
2. Pour chaque match :
   - Si match_id existe dans shared.match_registry :
     → Incrémenter player_count
   - Sinon :
     → Insérer dans match_registry
     → Insérer roster complet (match_participants)
     → Insérer events (highlight_events)
     → Insérer médailles de TOUS (medals_earned)
     → Marquer first_sync_by = gamertag
"""

import duckdb
import polars as pl
from pathlib import Path
from datetime import datetime, timezone

def migrate_player_to_shared(
    gamertag: str,
    player_db_path: Path,
    shared_db_path: Path = Path("data/warehouse/shared_matches.duckdb"),
    *,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict:
    """Migre un joueur vers shared_matches."""
    
    stats = {
        "matches_processed": 0,
        "matches_new": 0,
        "matches_existing": 0,
        "participants_inserted": 0,
        "events_inserted": 0,
        "medals_inserted": 0,
    }
    
    conn_player = duckdb.connect(str(player_db_path), read_only=True)
    conn_shared = duckdb.connect(str(shared_db_path), read_only=dry_run)
    
    try:
        # 1. Charger tous les matchs du joueur
        matches_df = conn_player.execute("""
            SELECT 
                match_id, start_time, end_time,
                playlist_id, playlist_name,
                map_id, map_name,
                pair_id, pair_name,
                game_variant_id, game_variant_name,
                mode_category, is_ranked, is_firefight,
                time_played_seconds as duration_seconds,
                my_team_score as team_0_score,
                enemy_team_score as team_1_score
            FROM match_stats
            ORDER BY start_time ASC
        """).pl()
        
        for match_row in matches_df.iter_rows(named=True):
            match_id = match_row['match_id']
            stats["matches_processed"] += 1
            
            # 2. Vérifier si match existe dans shared
            exists = conn_shared.execute(
                "SELECT 1 FROM match_registry WHERE match_id = ?",
                (match_id,)
            ).fetchone()
            
            if exists:
                # Match déjà migré par un autre joueur
                if not dry_run:
                    conn_shared.execute("""
                        UPDATE match_registry 
                        SET player_count = player_count + 1,
                            last_updated_at = CURRENT_TIMESTAMP
                        WHERE match_id = ?
                    """, (match_id,))
                stats["matches_existing"] += 1
                
                if verbose:
                    print(f"  ✓ {match_id} (déjà connu)")
                    
            else:
                # Nouveau match → insérer toutes les données
                stats["matches_new"] += 1
                
                if not dry_run:
                    # 2a. Insérer dans match_registry
                    conn_shared.execute("""
                        INSERT INTO match_registry (
                            match_id, start_time, end_time,
                            playlist_id, playlist_name,
                            map_id, map_name,
                            pair_id, pair_name,
                            game_variant_id, game_variant_name,
                            mode_category, is_ranked, is_firefight,
                            duration_seconds,
                            team_0_score, team_1_score,
                            first_sync_by, first_sync_at, player_count,
                            participants_loaded, events_loaded, medals_loaded
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, TRUE, TRUE, TRUE)
                    """, (
                        match_id,
                        match_row['start_time'],
                        match_row['end_time'],
                        match_row['playlist_id'],
                        match_row['playlist_name'],
                        match_row['map_id'],
                        match_row['map_name'],
                        match_row['pair_id'],
                        match_row['pair_name'],
                        match_row['game_variant_id'],
                        match_row['game_variant_name'],
                        match_row['mode_category'],
                        match_row['is_ranked'],
                        match_row['is_firefight'],
                        match_row['duration_seconds'],
                        match_row['team_0_score'],
                        match_row['team_1_score'],
                        gamertag,
                        datetime.now(timezone.utc),
                    ))
                    
                    # 2b. Copier match_participants
                    participants_df = conn_player.execute(
                        "SELECT * FROM match_participants WHERE match_id = ?",
                        (match_id,)
                    ).pl()
                    
                    if not participants_df.is_empty():
                        # Insérer en batch via Polars → DuckDB
                        conn_shared.execute(
                            "INSERT INTO match_participants SELECT * FROM participants_df"
                        )
                        stats["participants_inserted"] += len(participants_df)
                    
                    # 2c. Copier highlight_events
                    events_df = conn_player.execute(
                        "SELECT match_id, event_type, time_ms, killer_xuid, killer_gamertag, victim_xuid, victim_gamertag, type_hint, raw_json FROM highlight_events WHERE match_id = ?",
                        (match_id,)
                    ).pl()
                    
                    if not events_df.is_empty():
                        conn_shared.execute(
                            "INSERT INTO highlight_events (match_id, event_type, time_ms, killer_xuid, killer_gamertag, victim_xuid, victim_gamertag, type_hint, raw_json) SELECT * FROM events_df"
                        )
                        stats["events_inserted"] += len(events_df)
                    
                    # 2d. Copier medals_earned (ATTENTION : anciennes DB n'ont que 1 joueur)
                    # Pour la migration, on extrait TOUTES les médailles depuis les participants
                    # Mais on ne peut pas les avoir rétroactivement sans re-sync
                    # Donc on copie ce qu'on a (1 joueur) et on marquera medals_loaded=PARTIAL
                    medals_df = conn_player.execute(
                        "SELECT * FROM medals_earned WHERE match_id = ?",
                        (match_id,)
                    ).pl()
                    
                    if not medals_df.is_empty():
                        # Ajouter la colonne xuid si absente (anciennes DBs)
                        if 'xuid' not in medals_df.columns:
                            # Récupérer le xuid du joueur depuis player_match_stats
                            xuid_row = conn_player.execute(
                                "SELECT xuid FROM player_match_stats LIMIT 1"
                            ).fetchone()
                            if xuid_row:
                                medals_df = medals_df.with_columns(
                                    pl.lit(xuid_row[0]).alias('xuid')
                                )
                        
                        conn_shared.execute(
                            "INSERT INTO medals_earned SELECT * FROM medals_df"
                        )
                        stats["medals_inserted"] += len(medals_df)
                
                if verbose:
                    print(f"  ⭐ {match_id} (nouveau match migré)")
        
        if not dry_run:
            conn_shared.commit()
        
    finally:
        conn_player.close()
        conn_shared.close()
    
    return stats
```

#### Ordre de Migration

```bash
# 1. Chocoboflor (base de référence)
python scripts/migration/migrate_player_to_shared.py Chocoboflor --verbose

# 2. Valider Chocoboflor
python scripts/migration/validate_migration.py Chocoboflor

# 3. Madina97294
python scripts/migration/migrate_player_to_shared.py Madina97294 --verbose

# 4. Valider taux de partage (doit être ~95%)
python scripts/migration/validate_overlap.py Madina97294 --expected-overlap 0.95

# 5. JGtm
python scripts/migration/migrate_player_to_shared.py JGtm --verbose

# 6. xxdameongamerxx
python scripts/migration/migrate_player_to_shared.py xxdameongamerxx --verbose

# 7. Validation globale
python scripts/migration/validate_all_migrations.py
```

#### Validation Post-Migration

```sql
-- Statistiques globales
SELECT 
    COUNT(*) as total_matches,
    SUM(player_count) as total_participations,
    AVG(player_count) as avg_players_per_match,
    SUM(CASE WHEN player_count > 1 THEN 1 ELSE 0 END) as shared_matches,
    SUM(CASE WHEN player_count = 1 THEN 1 ELSE 0 END) as unique_matches
FROM match_registry;

-- Résultat attendu :
-- total_matches: ~1050 (vs 4000 dupliqués avant)
-- avg_players_per_match: ~3.8
-- shared_matches: ~950 (90% partagés)
-- unique_matches: ~100

-- Vérifier l'intégrité référentielle
SELECT 
    COUNT(*) as orphan_participants
FROM match_participants p
LEFT JOIN match_registry r ON p.match_id = r.match_id
WHERE r.match_id IS NULL;
-- Doit retourner 0

-- Vérifier les médailles
SELECT 
    COUNT(DISTINCT match_id) as matches_with_medals,
    COUNT(*) as total_medal_records,
    COUNT(DISTINCT xuid) as unique_players_with_medals
FROM medals_earned;
```

#### Livrables

- [x] Script `migrate_player_to_shared.py` complet et testé
- [x] Fonction `extract_all_medals()` dans `transformers.py`
- [x] Chocoboflor migré et validé
- [x] Madina97294 migré (22% partage — 161 matchs communs)
- [x] JGtm migré
- [x] XxDaemonGamerxX migré (100% partage validé)
- [x] VIEWs de compatibilité créées (20/20)
- [x] Rapport de migration `.ai/v5-migration-report.md`

#### Tests de Validation

```bash
# Test migration sur Chocoboflor
python scripts/migration/migrate_player_to_shared.py Chocoboflor --dry-run
python scripts/migration/migrate_player_to_shared.py Chocoboflor --verbose

# Validation données
python scripts/migration/validate_migration.py Chocoboflor

# Migration complète
bash scripts/migration/migrate_all_players.sh

# Validation finale
python -m pytest tests/migration/test_migration_integrity.py -v
```

#### Gate de Livraison

- [x] 4 joueurs migrés sans erreur
- [x] Taux de partage validé (22.1% — 285 matchs partagés sur 1289)
- [x] 0 orphelins (intégrité assurée par logique de migration, FK retirées)
- [x] Comptage matchs cohérent (1004×1p, 129×2p, 138×3p, 18×4p)
- [x] VIEWs de compatibilité fonctionnelles (20/20)
- [x] Tests d'intégrité passent à 100% (25/25)

**Estimation** : 3 jours (18-20h effectives)

---

### Sprint 3 — Refactoring Sync Engine (3 jours)

**Objectif** : Adapter `DuckDBSyncEngine` pour détecter et exploiter les matchs partagés

#### Stratégie

1. **Détection des matchs connus** via `match_registry`
2. **Sync allégée** pour matchs existants (seulement stats perso)
3. **Sync complète** pour nouveaux matchs (tout dans shared)
4. **Extraction collective** des médailles (tous les joueurs)

#### Tâches

| # | Tâche | Fichier(s) | Durée |
|---|-------|-----------|-------|
| 3.1 | Ajouter `shared_db_path` param à `DuckDBSyncEngine.__init__` | `src/data/sync/engine.py` | 30min |
| 3.2 | Méthode `_get_shared_connection()` | Idem | 30min |
| 3.3 | Refactoring `_process_single_match()` : détection shared | Idem | 2h |
| 3.4 | Nouvelle méthode `_process_known_match()` (sync allégée) | Idem | 3h |
| 3.5 | Nouvelle méthode `_process_new_match()` (sync complète) | Idem | 3h |
| 3.6 | Méthodes d'insertion vers shared : `_insert_to_shared_registry()` | Idem | 2h |
| 3.7 | Méthodes d'insertion vers shared : `_insert_to_shared_participants()` | Idem | 1h |
| 3.8 | Méthodes d'insertion vers shared : `_insert_to_shared_events()` | Idem | 1h |
| 3.9 | Méthodes d'insertion vers shared : `_insert_to_shared_medals()` | Idem | 1h |
| 3.10 | Adapter `extract_all_medals()` pour extraire TOUS les joueurs | `src/data/sync/transformers.py` | 2h |
| 3.11 | Simplifier insertions player DB (seulement enrichment) | `src/data/sync/engine.py` | 2h |
| 3.12 | Tests unitaires du nouveau flow | `tests/test_sync_shared_matches.py` | 3h |

#### Code Principal

```python
# src/data/sync/engine.py

class DuckDBSyncEngine:
    def __init__(
        self,
        player_db_path: str | Path,
        xuid: str,
        gamertag: str,
        *,
        metadata_db_path: str | Path | None = None,
        shared_db_path: str | Path | None = None,  # ⭐ NOUVEAU
        tokens: Tokens | None = None,
    ):
        self._player_db_path = Path(player_db_path)
        self._xuid = xuid
        self._gamertag = gamertag
        
        # Auto-détection shared_matches.duckdb
        if shared_db_path is None:
            data_dir = self._player_db_path.parent.parent.parent
            self._shared_db_path = data_dir / "warehouse" / "shared_matches.duckdb"
        else:
            self._shared_db_path = Path(shared_db_path)
        
        self._shared_connection: duckdb.DuckDBPyConnection | None = None
        # ... reste de l'init
    
    def _get_shared_connection(self) -> duckdb.DuckDBPyConnection:
        """Obtient la connexion à shared_matches.duckdb."""
        if self._shared_connection is None:
            self._shared_connection = duckdb.connect(
                str(self._shared_db_path),
                read_only=False,
            )
            # Configuration optimale
            self._shared_connection.execute("SET enable_object_cache = true")
        return self._shared_connection
    
    async def _process_single_match(
        self,
        client: SPNKrAPIClient,
        match_id: str,
        options: SyncOptions,
    ) -> dict[str, Any]:
        """Version optimisée avec détection des matchs partagés."""
        
        # 1. Vérifier dans shared_matches
        shared_conn = self._get_shared_connection()
        registry = shared_conn.execute(
            """SELECT 
                backfill_completed, 
                participants_loaded, 
                events_loaded,
                medals_loaded,
                player_count
            FROM match_registry 
            WHERE match_id = ?""",
            (match_id,)
        ).fetchone()
        
        if registry:
            # ✅ Match connu → sync allégée
            logger.info(f"Match {match_id} déjà connu (player_count={registry[4]})")
            return await self._process_known_match(
                client, match_id, registry, options
            )
        else:
            # ⭐ Nouveau match → sync complète
            logger.info(f"Nouveau match {match_id}")
            return await self._process_new_match(
                client, match_id, options
            )
    
    async def _process_known_match(
        self,
        client: SPNKrAPIClient,
        match_id: str,
        registry: tuple,
        options: SyncOptions,
    ) -> dict[str, Any]:
        """Traite un match déjà connu (sync allégée)."""
        
        result = {
            "inserted": True,
            "mode": "known_match",
            "api_calls_saved": 0,
        }
        
        # 1. Télécharger SEULEMENT les stats (pour extraire mes données perso)
        stats_json = await client.get_match_stats(match_id)
        if not stats_json:
            result["error"] = f"Impossible de récupérer {match_id}"
            return result
        
        # 2. Extraire MES données personnelles depuis Players[]
        me = _find_player(stats_json.get("Players", []), self._xuid)
        if not me:
            result["error"] = f"Joueur {self._xuid} absent du match {match_id}"
            return result
        
        # 3. Calculer mon enrichissement personnel
        # (performance_score sera calculé post-sync)
        player_enrichment = {
            "match_id": match_id,
            "xuid": self._xuid,
            "performance_score": None,  # Calculé en batch après sync
            "session_id": None,          # Calculé après sync
            "session_label": None,
            "is_with_friends": False,    # TODO: détecter depuis friends list
            "friends_xuids": None,
        }
        
        # 4. Insérer dans player DB (seulement enrichment)
        async with self._db_lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT OR REPLACE INTO player_match_enrichment
                (match_id, xuid, performance_score, session_id, session_label, is_with_friends, friends_xuids)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                player_enrichment["match_id"],
                player_enrichment["xuid"],
                player_enrichment["performance_score"],
                player_enrichment["session_id"],
                player_enrichment["session_label"],
                player_enrichment["is_with_friends"],
                player_enrichment["friends_xuids"],
            ))
        
        # 5. Backfill sélectif si des données manquent dans shared
        backfill_needed = []
        
        if not registry[1]:  # participants_loaded
            participants = extract_participants(stats_json)
            self._insert_to_shared_participants(match_id, participants)
            backfill_needed.append("participants")
        
        if not registry[2] and options.with_highlight_events:  # events_loaded
            events = await client.get_highlight_events(match_id)
            self._insert_to_shared_events(match_id, events)
            backfill_needed.append("events")
        else:
            result["api_calls_saved"] += 1  # On a évité l'appel /film
        
        if not registry[3]:  # medals_loaded
            medals_all = extract_all_medals(stats_json)
            self._insert_to_shared_medals(match_id, medals_all)
            backfill_needed.append("medals")
        
        # 6. Incrémenter player_count dans shared
        shared_conn = self._get_shared_connection()
        shared_conn.execute("""
            UPDATE match_registry 
            SET player_count = player_count + 1,
                last_updated_at = CURRENT_TIMESTAMP
            WHERE match_id = ?
        """, (match_id,))
        
        if backfill_needed:
            logger.info(f"Backfill effectué pour {match_id}: {', '.join(backfill_needed)}")
        else:
            logger.info(f"Match {match_id} complet, aucun backfill nécessaire")
        
        # ÉCONOMIE : 1-2 appels API évités (events + éventuellement skill)
        result["api_calls_saved"] += len(backfill_needed) == 0 and 1 or 0
        
        return result
    
    async def _process_new_match(
        self,
        client: SPNKrAPIClient,
        match_id: str,
        options: SyncOptions,
    ) -> dict[str, Any]:
        """Traite un nouveau match (sync complète vers shared)."""
        
        result = {
            "inserted": True,
            "mode": "new_match",
        }
        
        # 1. Télécharger toutes les données
        stats_json = await client.get_match_stats(match_id)
        if not stats_json:
            result["error"] = f"Impossible de récupérer {match_id}"
            return result
        
        # Enrichir avec les assets si demandé
        if options.with_assets:
            await enrich_match_info_with_assets(client, stats_json)
        
        # 2. Télécharger events et skill en parallèle
        xuids = extract_xuids_from_match(stats_json)
        
        events = []
        skill_json = None
        
        if options.with_highlight_events or options.with_skill:
            tasks = []
            if options.with_highlight_events:
                tasks.append(client.get_highlight_events(match_id))
            else:
                tasks.append(asyncio.sleep(0))  # Placeholder
            
            if options.with_skill and xuids:
                tasks.append(client.get_skill_stats(match_id, xuids))
            else:
                tasks.append(asyncio.sleep(0))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            if options.with_highlight_events:
                events = results[0] if not isinstance(results[0], Exception) else []
            if options.with_skill and xuids:
                skill_json = results[1] if not isinstance(results[1], Exception) else None
        
        # 3. Extraire les données communes
        match_common = self._extract_match_common_data(stats_json, skill_json)
        participants = extract_participants(stats_json)
        medals_all = extract_all_medals(stats_json)  # ⭐ TOUS les joueurs
        
        # 4. Insérer dans shared_matches
        shared_conn = self._get_shared_connection()
        
        # 4a. match_registry
        shared_conn.execute("""
            INSERT INTO match_registry (
                match_id, start_time, end_time,
                playlist_id, playlist_name,
                map_id, map_name,
                pair_id, pair_name,
                game_variant_id, game_variant_name,
                mode_category, is_ranked, is_firefight,
                duration_seconds,
                team_0_score, team_1_score,
                first_sync_by, first_sync_at, player_count,
                participants_loaded, events_loaded, medals_loaded
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1, TRUE, ?, TRUE)
        """, (
            match_id,
            match_common["start_time"],
            match_common["end_time"],
            match_common["playlist_id"],
            match_common["playlist_name"],
            match_common["map_id"],
            match_common["map_name"],
            match_common["pair_id"],
            match_common["pair_name"],
            match_common["game_variant_id"],
            match_common["game_variant_name"],
            match_common["mode_category"],
            match_common["is_ranked"],
            match_common["is_firefight"],
            match_common["duration_seconds"],
            match_common["team_0_score"],
            match_common["team_1_score"],
            self._gamertag,
            len(events) > 0,  # events_loaded
        ))
        
        # 4b. Participants
        self._insert_to_shared_participants(match_id, participants)
        
        # 4c. Events
        if events:
            self._insert_to_shared_events(match_id, events)
        
        # 4d. Médailles de TOUS les joueurs
        self._insert_to_shared_medals(match_id, medals_all)
        
        # 5. Insérer enrichissement personnel dans player DB
        player_enrichment = {
            "match_id": match_id,
            "xuid": self._xuid,
            "performance_score": None,
            "session_id": None,
            "session_label": None,
            "is_with_friends": False,
            "friends_xuids": None,
        }
        
        async with self._db_lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT OR REPLACE INTO player_match_enrichment
                (match_id, xuid, performance_score, session_id, session_label, is_with_friends, friends_xuids)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                player_enrichment["match_id"],
                player_enrichment["xuid"],
                player_enrichment["performance_score"],
                player_enrichment["session_id"],
                player_enrichment["session_label"],
                player_enrichment["is_with_friends"],
                player_enrichment["friends_xuids"],
            ))
        
        logger.info(f"Match {match_id} entièrement sync vers shared_matches")
        
        return result
```

#### Livrables

- [x] `DuckDBSyncEngine` refactoré avec détection shared
- [x] Méthodes `_process_known_match()` et `_process_new_match()`
- [x] Méthodes d'insertion vers shared (registry, participants, events, medals, aliases)
- [x] `extract_all_medals()` dans `transformers.py` (déjà implémenté)
- [x] `extract_match_registry_data()` dans `transformers.py`
- [x] Tests `tests/test_sync_shared_matches.py` passent (33/33)
- [ ] Documentation `docs/SYNC_SHARED_MATCHES.md`

#### Tests de Validation

```bash
# Test unitaire du nouveau flow
python -m pytest tests/test_sync_shared_matches.py -v

# Test end-to-end sur un joueur
python scripts/sync.py --delta --player TestPlayer --max-matches 10

# Vérifier qu'un match partagé économise des appels API
python scripts/test_api_savings.py Chocoboflor Madina97294

# Validation complète
python -m pytest tests/ -v --ignore=tests/integration
```

#### Gate de Livraison

- [x] Détection des matchs partagés fonctionne
- [x] Sync allégée économise 1-2 appels API par match partagé
- [x] Sync complète insère dans shared correctement
- [x] Médailles de TOUS les joueurs extraites
- [x] Tests passent à 100% (76/76 : 43 v4 + 33 v5)
- [x] Aucune régression sur sync existant

**Estimation** : 3 jours (20-22h effectives)

---

### Sprint 4 — Refactoring DuckDBRepository (2 jours)

**Objectif** : Adapter `DuckDBRepository` pour lire depuis `shared_matches` via ATTACH

#### Stratégie

1. **ATTACH** de `shared_matches.duckdb` en lecture seule
2. **Queries natives** lisant depuis `shared.*`
3. **VIEWs temporaires** pour compatibilité
4. **Tests de non-régression** sur toutes les pages UI

#### Tâches

| # | Tâche | Fichier(s) | Durée |
|---|-------|-----------|-------|
| 4.1 | Ajouter `shared_db_path` param à `DuckDBRepository.__init__` | `src/data/repositories/duckdb_repo.py` | 30min |
| 4.2 | Modifier `_get_connection()` pour ATTACH shared_matches | Idem | 1h |
| 4.3 | Refactoring `load_match_participants()` → lecture depuis shared | Idem | 1h |
| 4.4 | Refactoring `load_highlight_events()` → lecture depuis shared | Idem | 1h |
| 4.5 | Refactoring `load_medals_for_match()` → lecture depuis shared | Idem | 1h |
| 4.6 | Nouvelle méthode `load_player_match_enrichment()` | Idem | 1h |
| 4.7 | Adapter `load_matches()` pour JOIN shared + enrichment | Idem | 2h |
| 4.8 | Créer VIEWs de compat si nécessaire | `scripts/create_compat_views.py` | 1h |
| 4.9 | Tests unitaires repository | `tests/test_duckdb_repository_v5.py` | 3h |
| 4.10 | Tests d'intégration (toutes les pages UI) | `tests/integration/test_ui_pages_v5.py` | 3h |

#### Code Principal

```python
# src/data/repositories/duckdb_repo.py

class DuckDBRepository:
    def __init__(
        self,
        player_db_path: str | Path,
        xuid: str,
        *,
        metadata_db_path: str | Path | None = None,
        shared_db_path: str | Path | None = None,  # ⭐ NOUVEAU
        gamertag: str | None = None,
        read_only: bool = True,
        memory_limit: str = "512MB",
    ):
        self._player_db_path = Path(player_db_path)
        self._xuid = xuid
        self._gamertag = gamertag
        self._read_only = read_only
        self._memory_limit = memory_limit
        
        # Auto-détection shared_matches.duckdb
        if shared_db_path is None:
            data_dir = self._player_db_path.parent.parent.parent
            self._shared_db_path = data_dir / "warehouse" / "shared_matches.duckdb"
        else:
            self._shared_db_path = Path(shared_db_path)
        
        # ... reste init
    
    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Connexion avec ATTACH de metadata ET shared_matches."""
        if self._connection is None:
            self._connection = duckdb.connect(
                str(self._player_db_path),
                read_only=self._read_only,
            )
            
            # ATTACH metadata (existant)
            if self._metadata_db_path.exists():
                self._connection.execute(
                    f"ATTACH DATABASE '{self._metadata_db_path}' AS meta (READ_ONLY)"
                )
                self._attached_dbs.add("meta")
            
            # ⭐ ATTACH shared_matches
            if self._shared_db_path.exists():
                self._connection.execute(
                    f"ATTACH DATABASE '{self._shared_db_path}' AS shared (READ_ONLY)"
                )
                self._attached_dbs.add("shared")
            
            # Configuration optimale
            self._connection.execute("SET enable_object_cache = true")
            self._connection.execute(f"SET memory_limit = '{self._memory_limit}'")
        
        return self._connection
    
    def load_matches(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        filters: dict | None = None,
    ) -> pl.DataFrame:
        """Charge les matchs avec JOIN shared + enrichment."""
        
        conn = self._get_connection()
        
        # ⭐ JOIN entre shared.match_participants et player_match_enrichment
        query = """
            SELECT 
                -- Données communes depuis shared.match_participants
                p.match_id,
                p.xuid,
                p.team_id,
                p.outcome,
                p.rank,
                p.score AS personal_score,
                p.kills,
                p.deaths,
                p.assists,
                p.shots_fired,
                p.shots_hit,
                CASE 
                    WHEN p.shots_fired > 0 
                    THEN (p.shots_hit * 100.0 / p.shots_fired)
                    ELSE 0 
                END AS accuracy,
                p.damage_dealt,
                p.damage_taken,
                
                -- Métadonnées depuis shared.match_registry
                r.start_time,
                r.end_time,
                r.playlist_id,
                r.playlist_name,
                r.map_id,
                r.map_name,
                r.mode_category,
                r.is_ranked,
                r.team_0_score,
                r.team_1_score,
                r.duration_seconds,
                
                -- Enrichissement personnel depuis player DB
                e.performance_score,
                e.session_id,
                e.session_label,
                e.is_with_friends
                
            FROM shared.match_participants p
            INNER JOIN shared.match_registry r ON r.match_id = p.match_id
            LEFT JOIN player_match_enrichment e ON e.match_id = p.match_id
            WHERE p.xuid = ?
        """
        
        params = [self._xuid]
        
        # Filtres (existant, à adapter)
        if filters:
            where_clauses = []
            # ... logique filtres adaptée aux nouvelles colonnes
        
        query += " ORDER BY r.start_time DESC"
        
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        
        return conn.execute(query, params).pl()
    
    def load_match_participants(
        self,
        match_id: str,
    ) -> pl.DataFrame:
        """Charge le roster complet depuis shared.match_participants."""
        
        conn = self._get_connection()
        
        # ⭐ Lecture directe depuis shared
        return conn.execute("""
            SELECT 
                p.match_id,
                p.xuid,
                p.team_id,
                p.outcome,
                p.rank,
                p.score,
                p.kills,
                p.deaths,
                p.assists,
                p.shots_fired,
                p.shots_hit,
                p.damage_dealt,
                p.damage_taken,
                COALESCE(a.gamertag, 'Unknown') as gamertag
            FROM shared.match_participants p
            LEFT JOIN shared.xuid_aliases a ON a.xuid = p.xuid
            WHERE p.match_id = ?
            ORDER BY p.rank ASC
        """, (match_id,)).pl()
    
    def load_highlight_events(
        self,
        match_id: str,
    ) -> pl.DataFrame:
        """Charge les events depuis shared.highlight_events."""
        
        conn = self._get_connection()
        
        return conn.execute("""
            SELECT * FROM shared.highlight_events
            WHERE match_id = ?
            ORDER BY time_ms ASC
        """, (match_id,)).pl()
    
    def load_medals_for_match(
        self,
        match_id: str,
        xuid: str | None = None,
    ) -> pl.DataFrame:
        """Charge les médailles depuis shared.medals_earned."""
        
        conn = self._get_connection()
        
        if xuid is None:
            xuid = self._xuid
        
        # ⭐ Filtrer par match_id ET xuid
        return conn.execute("""
            SELECT 
                m.match_id,
                m.xuid,
                m.medal_name_id,
                m.count,
                md.name_fr,
                md.description_fr,
                md.difficulty
            FROM shared.medals_earned m
            LEFT JOIN meta.medal_definitions md ON md.name_id = m.medal_name_id
            WHERE m.match_id = ? AND m.xuid = ?
        """, (match_id, xuid)).pl()
```

#### Livrables

- [ ] `DuckDBRepository` refactoré avec ATTACH shared
- [ ] Toutes les méthodes de lecture adaptées
- [ ] VIEWs de compatibilité si nécessaire
- [ ] Tests `tests/test_duckdb_repository_v5.py` passent
- [ ] Tests d'intégration UI passent

#### Tests de Validation

```bash
# Tests repository
python -m pytest tests/test_duckdb_repository_v5.py -v

# Tests d'intégration (toutes les pages)
python -m pytest tests/integration/test_ui_pages_v5.py -v

# Test manuel UI
streamlit run streamlit_app.py

# Valider queries
python scripts/validate_repository_queries.py
```

#### Gate de Livraison

- [ ] ATTACH shared_matches fonctionne
- [ ] Queries depuis shared correctes
- [ ] Aucune régression UI
- [ ] Performance acceptable (< 100ms par query)
- [ ] Tests passent à 100%

**Estimation** : 2 jours (13-15h effectives)

---

### Sprint 5 — Refactoring UI Big Bang (3 jours)

**Objectif** : Supprimer les VIEWs de compatibilité et adapter toutes les pages UI pour queries natives

#### Stratégie

**Big Bang** : Refactorer toutes les pages en une fois pour éviter le code hybride

#### Tâches

| # | Tâche | Fichier(s) | Durée |
|---|-------|-----------|-------|
| 5.1 | Audit de toutes les queries UI (inventaire) | `scripts/audit_ui_queries.py` | 1h |
| 5.2 | Refactoring page Career | `src/ui/pages/career.py` | 2h |
| 5.3 | Refactoring page Match History | `src/ui/pages/match_history.py` | 2h |
| 5.4 | Refactoring page Match View | `src/ui/pages/match_view.py` | 2h |
| 5.5 | Refactoring page Timeseries | `src/ui/pages/timeseries.py` | 2h |
| 5.6 | Refactoring page Teammates | `src/ui/pages/teammates.py` | 2h |
| 5.7 | Refactoring page Maps | `src/ui/pages/maps.py` | 1.5h |
| 5.8 | Refactoring page Modes | `src/ui/pages/modes.py` | 1.5h |
| 5.9 | Refactoring page Medals | `src/ui/pages/medals.py` | 1.5h |
| 5.10 | Refactoring page Media Library | `src/ui/pages/media_library.py` | 2h |
| 5.11 | Suppression VIEWs de compatibilité | `scripts/remove_compat_views.py` | 1h |
| 5.12 | Tests automatisés toutes les pages | `tests/ui/test_all_pages_v5.py` | 4h |

#### Exemple de Refactoring

```python
# AVANT (v4)
def load_match_data(repo, match_id):
    # Query attendait que match_stats contienne tout
    df = repo.load_matches(filters={"match_id": match_id})
    return df

# APRÈS (v5)
def load_match_data(repo, match_id):
    # Données depuis shared.match_participants + enrichment
    df = repo.load_matches(filters={"match_id": match_id})
    # La query a changé en interne (JOIN shared), mais l'API reste identique
    return df
```

#### Livrables

- [ ] Toutes les pages UI refactorées
- [ ] VIEWs de compatibilité supprimées
- [ ] Tests UI passent à 100%
- [ ] Guide de migration UI `.ai/v5-ui-migration-guide.md`

#### Tests de Validation

```bash
# Test toutes les pages
python -m pytest tests/ui/test_all_pages_v5.py -v

# Test manuel streamlit
streamlit run streamlit_app.py

# Vérifier aucune régression
python scripts/test_ui_regression.py
```

#### Gate de Livraison

- [ ] Toutes les pages fonctionnent
- [ ] Aucune régression visuelle
- [ ] Performance acceptable
- [ ] Tests UI passent à 100%

**Estimation** : 3 jours (20-22h effectives)

---

### Sprint 6 — Optimisation API (2 jours)

**Objectif** : Implémenter les optimisations du PLAN_OPTIMISATION_SYNC.md

#### Tâches

| # | Tâche | Fichier(s) | Durée |
|---|-------|-----------|-------|
| 6.1 | Paralléliser appels API skill+events (`asyncio.gather`) | `src/data/sync/engine.py` | 2h |
| 6.2 | Désactiver calcul performance_score pendant sync | `src/data/sync/engine.py` | 1h |
| 6.3 | Créer `batch_compute_performance_scores()` post-sync | `src/data/sync/engine.py` | 3h |
| 6.4 | Batching des insertions DB (commit tous les 10 matchs) | `src/data/sync/engine.py` | 2h |
| 6.5 | Augmenter rate limit (10 req/s, parallel_matches=5) | `src/data/sync/models.py` | 30min |
| 6.6 | Tests de performance (benchmark) | `tests/performance/test_sync_v5.py` | 2h |
| 6.7 | Documentation optimisations | `docs/SYNC_OPTIMIZATIONS_V5.md` | 1h |

#### Gains Attendus

| Métrique | Avant v5 | Après v5 | Gain |
|----------|----------|----------|------|
| Temps/match (nouveau) | 16s | 2-3s | **-81%** |
| Temps/match (partagé 95%) | 16s | 0.5s | **-97%** |
| API calls (sync 4 joueurs) | 12 000 | 3 300 | **-72%** |

#### Livrables

- [ ] Parallélisation API implémentée
- [ ] Perf scores calculés en batch post-sync
- [ ] Batching DB implémenté
- [ ] Rate limit optimisé
- [ ] Tests de performance validés
- [ ] Documentation complète

#### Tests de Validation

```bash
# Benchmark sync
python tests/performance/test_sync_v5.py --benchmark

# Comparaison v4 vs v5
python scripts/benchmark_sync_v4_vs_v5.py

# Validation gains
python scripts/validate_optimizations.py
```

#### Gate de Livraison

- [ ] Temps/match < 3s (nouveaux matchs)
- [ ] Temps/match < 1s (matchs partagés)
- [ ] Aucune régression de données
- [ ] Tests passent à 100%

**Estimation** : 2 jours (11-13h effectives)

---

### Sprint 7 — Tests & Couverture (2 jours)

**Objectif** : Atteindre 80% de couverture et implémenter PLAN_AMELIORATION_TESTS.md

#### Tâches

| # | Tâche | Fichier(s) | Durée |
|---|-------|-----------|-------|
| 7.1 | Tests migration (intégrité, rollback) | `tests/migration/` | 3h |
| 7.2 | Tests sync shared (détection, économies API) | `tests/test_sync_shared_v5.py` | 2h |
| 7.3 | Tests repository shared (ATTACH, queries) | `tests/test_repository_shared_v5.py` | 2h |
| 7.4 | Tests UI (toutes les pages, edge cases) | `tests/ui/` | 4h |
| 7.5 | Tests de charge (1000+ matchs) | `tests/performance/test_load_v5.py` | 2h |
| 7.6 | Rapport de couverture final | Coverage | 1h |
| 7.7 | Documentation tests | `docs/TESTING_V5.md` | 1h |

#### Couverture Cible

| Module | Cible | Actuel v4 | Objectif v5 |
|--------|-------|-----------|-------------|
| `src/data/sync/` | 80% | 65% | **85%** |
| `src/data/repositories/` | 80% | 70% | **85%** |
| `src/ui/pages/` | 40% | 15% | **50%** |
| Global | 60% | 41% | **65%** |

#### Livrables

- [ ] Couverture >= 65% globale
- [ ] Tests migration à 100%
- [ ] Tests UI >= 50%
- [ ] Rapport de couverture dans `.ai/v5-coverage-report.html`

#### Tests de Validation

```bash
# Suite complète avec couverture
python -m pytest --cov=src --cov-report=html --cov-report=term-missing

# Vérifier couverture minimale
python scripts/check_coverage_threshold.py --min 65

# Tests de charge
python -m pytest tests/performance/test_load_v5.py -v
```

#### Gate de Livraison

- [ ] Couverture >= 65%
- [ ] Tous les tests passent
- [ ] Aucun test ignoré sans justification
- [ ] Documentation tests complète

**Estimation** : 2 jours (15-17h effectives)

---

### Sprint 8 — Finalisation & Release v5.0 (2 jours)

**Objectif** : Stabilisation, documentation, et release officielle v5.0

#### Tâches

| # | Tâche | Fichier(s) | Durée |
|---|-------|-----------|-------|
| 8.1 | Nettoyage code mort (VIEWs, legacy) | Divers | 2h |
| 8.2 | Mise à jour CHANGELOG.md | `CHANGELOG.md` | 1h |
| 8.3 | Mise à jour README.md | `README.md` | 1h |
| 8.4 | Documentation architecture v5 | `docs/ARCHITECTURE_V5.md` | 2h |
| 8.5 | Guide de migration v4→v5 | `docs/MIGRATION_V4_TO_V5.md` | 2h |
| 8.6 | Benchmark final (comparaison v4 vs v5) | `scripts/benchmark_v4_vs_v5.py` | 2h |
| 8.7 | Revue de code complète | Tous | 3h |
| 8.8 | Archivage docs `.ai/` + PLAN_UNIFIE.md + scripts v5 | `scripts/archive_v5_all.sh` | 45min |
| 8.9 | Tag `v5.0.0` et merge vers `main` | Git | 1h |

#### Documentation Obligatoire

- [ ] `CHANGELOG.md` à jour
- [ ] `README.md` mis à jour
- [ ] `docs/ARCHITECTURE_V5.md` complet
- [ ] `docs/MIGRATION_V4_TO_V5.md` détaillé
- [ ] `.ai/v5-retrospective.md` (leçons apprises)

#### Benchmark Final

| Métrique | v4 | v5 | Amélioration |
|----------|----|----|--------------|
| **Stockage** (4 joueurs) | 800 MB | 250 MB | **-69%** |
| **Sync initiale** (4 joueurs) | 12 000 appels | 3 300 appels | **-72%** |
| **Temps sync** (100 matchs) | 45 min | 12 min | **-73%** |
| **DB size** (par joueur) | 200 MB | 30 MB | **-85%** |

#### Livrables

- [ ] Code nettoyé et optimisé
- [ ] Documentation complète
- [ ] Benchmark validé
- [ ] Documentation temporaire `.ai/` archivée dans `.ai/archive/v5.0/`
- [ ] `PLAN_UNIFIE.md` archivé (ancien plan v4.5 obsolète)
- [ ] Scripts migration v5 archivés dans `scripts/_archive/migration_v5/`
- [ ] Scripts benchmark v5 archivés dans `scripts/_archive/benchmark_v5/`
- [ ] Tag `v5.0.0` créé
- [ ] Merge vers `main` effectué

#### Tests de Validation

```bash
# Suite complète finale
python -m pytest --cov=src --cov-report=html

# Benchmark comparatif
python scripts/benchmark_v4_vs_v5.py --detailed

# Validation gains
python scripts/validate_v5_improvements.py

# Tests end-to-end
python scripts/test_e2e_v5.py
```

#### Gate de Livraison

- [ ] Tous les tests passent à 100%
- [ ] Couverture >= 65%
- [ ] Benchmark validé (gains >= objectifs)
- [ ] Documentation complète
- [ ] Aucun `# TODO` ou `# FIXME` sans ticket
- [ ] Dossier `.ai/` nettoyé (docs v5 + PLAN_UNIFIE.md archivés)
- [ ] Scripts v5 archivés (migration + benchmark)
- [ ] Tag `v5.0.0` créé
- [ ] Merge vers `main` effectué

**Estimation** : 2 jours (14.75-16.75h effectives)

---

## 4. Protocole de Revue par Sprint

### 4.1 Checklist Obligatoire Pré-Commit

**À exécuter AVANT CHAQUE commit** :

```bash
# 1. Tests locaux
python -m pytest -q --ignore=tests/integration

# 2. Type hints
mypy src/ --ignore-missing-imports

# 3. Formatage
black src/ tests/ scripts/
isort src/ tests/ scripts/

# 4. Linting
ruff check src/ tests/ scripts/

# 5. Validation schéma (si modif DB)
python scripts/validate_all_schemas.py
```

### 4.2 Checklist de Fin de Sprint

- [ ] **Tests** : `pytest` passe à 100%
- [ ] **Couverture** : Pas de baisse de couverture (minimum maintenu)
- [ ] **Documentation** : README/CHANGELOG/docs à jour
- [ ] **Git** : Commits propres avec messages Conventional Commits
- [ ] **Backups** : Backups de DB créés si modifications de schéma
- [ ] **Validation** : Tests manuels sur UI (smoke test)
- [ ] **Performance** : Pas de régression (bench si pertinent)
- [ ] **Code mort** : Aucun code commenté ou inutilisé

### 4.3 Validation Inter-Sprints

Avant de passer au sprint suivant :

1. **Revue auto-critique** : Relire son propre code 24h après
2. **Tests de régression** : Suite complète `pytest`
3. **Validation UI** : Tester manuellement les pages critiques
4. **Documentation** : Vérifier que tout est à jour
5. **Git** : Créer un tag de checkpoint `sprint-N-completed`

---

## 5. Matrice de Risques

### 5.1 Risques Techniques

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **Corruption shared_matches.duckdb** | Faible | Critique | Backups quotidiens + validation checksums |
| **Perte de données lors migration** | Faible | Critique | Migration incrémentale + validation à chaque joueur |
| **Régression UI** | Moyen | Élevé | Tests UI complets + validation manuelle |
| **Performance queries dégradées** | Moyen | Moyen | Benchmark avant/après + index optimisés |
| **Incompatibilité ATTACH multi-DB** | Faible | Moyen | Tests DuckDB version 1.4.4+ validés |

### 5.2 Risques Opérationnels

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **Rollback impossible** | Faible | Critique | Backups complets + plan de rollback testé |
| **Downtime prolongé** | Moyen | Moyen | Migration par joueur (autres accessibles) |
| **Bugs non détectés** | Moyen | Moyen | Couverture tests >= 65% + tests manuels |

---

## 6. Critères de Livraison Globaux

### 6.1 Critères Fonctionnels

- [ ] ✅ Tous les joueurs migrés vers shared_matches
- [ ] ✅ Aucune duplication de données de matchs
- [ ] ✅ Détection des matchs partagés fonctionnelle
- [ ] ✅ Sync allégée pour matchs connus
- [ ] ✅ Toutes les pages UI fonctionnelles
- [ ] ✅ Aucune régression de features

### 6.2 Critères Techniques

- [ ] ✅ Tests passent à 100% (`pytest`)
- [ ] ✅ Couverture >= 65%
- [ ] ✅ Aucun warning ou erreur lors du build
- [ ] ✅ Type hints complets sur code métier
- [ ] ✅ Documentation à jour (README, CHANGELOG, docs/)

### 6.3 Critères de Performance

- [ ] ✅ Stockage réduit de >= 65%
- [ ] ✅ Appels API réduits de >= 70%
- [ ] ✅ Temps de sync réduit de >= 70%
- [ ] ✅ Queries UI < 100ms (p95)

### 6.4 Critères Qualité

- [ ] ✅ Code modulaire (max 500 lignes/module)
- [ ] ✅ Pas de duplication de logique
- [ ] ✅ Gestion d'erreurs exhaustive
- [ ] ✅ Logs clairs et exploitables
- [ ] ✅ Aucun `# TODO` sans ticket associé

---

## 7. Plan de Rollback

### 7.1 Si Échec Critique Détecté

**Critères de rollback** :
- Perte de données > 1%
- Corruption de shared_matches.duckdb irréparable
- Régression UI bloquante (> 50% des pages cassées)
- Performance < -50% vs v4

**Procédure** :

```bash
# 1. Arrêter toutes les opérations
git stash

# 2. Restaurer depuis backup
python scripts/restore_all_from_backup.py backups/pre-v5-*/

# 3. Retour branche précédente
git checkout sprint14/isolation-backend-frontend

# 4. Vérifier l'état
python -m pytest -q
streamlit run streamlit_app.py

# 5. Documenter l'incident
# Créer .ai/v5-rollback-incident-$(date).md
```

### 7.2 Sauvegarde Continue

Pendant toute la migration :

- **Checkpoints Git** : Tag après chaque sprint
- **Backups DB** : Quotidiens dans `backups/v5-daily/`
- **Logs détaillés** : Journalisation de toutes les opérations

---

## 8. Métriques de Succès

### 8.1 Métriques Primaires

| Métrique | Objectif | Mesure |
|----------|----------|--------|
| **Réduction stockage** | >= 65% | (v4_size - v5_size) / v4_size |
| **Réduction API calls** | >= 70% | (v4_calls - v5_calls) / v4_calls |
| **Réduction temps sync** | >= 70% | (v4_time - v5_time) / v4_time |
| **Couverture tests** | >= 65% | Coverage report |
| **Tests passants** | 100% | Pytest exit code |

### 8.2 Métriques Secondaires

| Métrique | Objectif | Mesure |
|----------|----------|--------|
| **Taille player DB** | < 50 MB | `du -sh data/players/*/stats.duckdb` |
| **Temps query UI** | < 100ms (p95) | Benchmark Streamlit |
| **Partage de matchs détecté** | >= 90% | Statistiques match_registry |

---

## 9. Récapitulatif Timeline

```
┌─────────────────────────────────────────────────────────────┐
│                    LevelUp v5.0 Timeline                    │
├─────────────┬───────────────────────────────────────────────┤
│ Sprint 0    │ Audit & Backups                         (1j)  │
│ Sprint 1    │ Infrastructure shared_matches           (2j)  │
│ Sprint 2    │ Migration données                  (3j) ✅    │
│ Sprint 3    │ Refactoring Sync Engine            (3j) ✅    │
│ Sprint 4    │ Refactoring DuckDBRepository            (2j)  │
│ Sprint 5    │ Refactoring UI Big Bang                 (3j)  │
│ Sprint 6    │ Optimisation API                        (2j)  │
│ Sprint 7    │ Tests & Couverture                      (2j)  │
│ Sprint 8    │ Finalisation & Release v5.0             (2j)  │
├─────────────┴───────────────────────────────────────────────┤
│ TOTAL       │ 18 jours ouvrés (peut descendre à 14j)       │
└─────────────────────────────────────────────────────────────┘
```

### Parallélisation Possible

- **Sprints 3 & 4** : Peuvent se chevaucher (Sync Engine ≠ Repository)
- **Gain** : -4 jours → **14 jours total**

---

## 10. Commandes Rapides (Cheat Sheet)

### Avant de Commencer

```bash
# Backup complet
python scripts/backup_all_players.py --output backups/pre-v5-$(date +%Y%m%d)

# Baseline tests
python -m pytest -q --ignore=tests/integration

# Audit données
python scripts/audit_current_data.py --summary
```

### Pendant la Migration

```bash
# Créer shared_matches.duckdb
python scripts/migration/create_shared_matches_db.py

# Migrer un joueur
python scripts/migration/migrate_player_to_shared.py GAMERTAG --verbose

# Valider migration
python scripts/migration/validate_migration.py GAMERTAG

# Tests
python -m pytest tests/migration/ -v
```

### Validation Finale

```bash
# Suite complète
python -m pytest --cov=src --cov-report=html

# Benchmark
python scripts/benchmark_v4_vs_v5.py --detailed

# Check qualité
black src/ tests/ scripts/
ruff check src/
mypy src/ --ignore-missing-imports
```

---

## 11. Contact & Support

**Questions** : Créer une issue dans le repo  
**Bugs** : Tag `bug` + `v5-migration`  
**Documentation** : `.ai/` et `docs/`

---

**Fin du Plan v5.0** 🚀
