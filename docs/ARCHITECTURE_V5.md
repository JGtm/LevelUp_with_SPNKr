# Architecture LevelUp v5.0 — Shared Matches

> **Date** : 2026-02-15
> **Version** : 5.0.0
> **Migration depuis** : v4.5 (DuckDB unifié, 1 DB par joueur)

---

## Vue d'Ensemble

LevelUp v5 introduit une architecture **Shared Matches** qui centralise les données de matchs
dans une base partagée unique (`shared_matches.duckdb`), éliminant la duplication massive
entre joueurs partageant des parties communes.

### Problématique résolue

En v4, chaque joueur avait sa propre copie complète de chaque match (stats, médailles, events).
Pour 4 joueurs partageant 95% de matchs, cela signifiait 4× les mêmes données.

| Métrique | v4 | v5 | Gain |
|----------|----|----|------|
| Stockage (4 joueurs) | 800 MB | 250 MB | **-69%** |
| DB size par joueur | 200 MB | 30 MB | **-85%** |
| Appels API (sync 4 joueurs) | 12 000 | 3 300 | **-72%** |
| Temps sync (100 matchs) | 45 min | 12 min | **-73%** |

---

## Diagramme d'Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Streamlit UI                        │
│  (pages/, components/, visualization/)               │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────┐
│              DuckDBRepository                         │
│  (src/data/repositories/duckdb_repo.py)              │
│                                                      │
│  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ _get_match_source│  │ ATTACH shared READ_ONLY  │   │
│  │ (sous-requête)   │  │ ATTACH meta READ_ONLY    │   │
│  └─────────────────┘  └──────────────────────────┘   │
└──────┬───────────────────────┬───────────────────────┘
       │                       │
       ▼                       ▼
┌──────────────┐   ┌───────────────────────────────────┐
│ stats.duckdb │   │     shared_matches.duckdb          │
│ (par joueur) │   │     (data/warehouse/)              │
│              │   │                                    │
│ ┌──────────┐ │   │ ┌────────────────┐ ┌────────────┐ │
│ │enrichment│ │   │ │match_registry  │ │match_      │ │
│ │teammates │ │   │ │(1 ligne/match) │ │participants│ │
│ │antagonist│ │   │ └────────────────┘ │(tous joueur│ │
│ │citations │ │   │ ┌────────────────┐ └────────────┘ │
│ └──────────┘ │   │ │highlight_events│ ┌────────────┐ │
└──────────────┘   │ │(tous events)   │ │medals_     │ │
                   │ └────────────────┘ │earned      │ │
┌──────────────┐   │ ┌────────────────┐ └────────────┘ │
│metadata.duckdb│  │ │xuid_aliases   │                 │
│(référentiels) │  │ └────────────────┘                 │
└──────────────┘   └───────────────────────────────────┘
```

---

## Structure des Fichiers

```
data/
├── warehouse/
│   ├── metadata.duckdb            # Référentiels (maps, playlists, medals, citations)
│   └── shared_matches.duckdb      # Base partagée - TOUS les matchs
│       ├── match_registry         # Registre central (1 ligne par match unique)
│       ├── match_participants     # Stats de TOUS les joueurs de TOUS les matchs
│       ├── highlight_events       # TOUS les événements filmés
│       ├── medals_earned          # Médailles de TOUS les joueurs
│       ├── xuid_aliases           # Mapping global xuid→gamertag
│       └── schema_version        # Versioning du schéma
│
├── players/
│   └── {gamertag}/
│       ├── stats.duckdb           # Enrichissements PERSONNELS uniquement
│       │   ├── player_match_enrichment  # performance_score, session_id, is_with_friends
│       │   ├── teammates_aggregate      # Stats coéquipiers (point de vue joueur)
│       │   ├── antagonists              # Rivalités (top killers/victimes)
│       │   ├── match_citations          # Citations calculées par match
│       │   ├── career_progression       # Historique rangs
│       │   ├── media_files              # Fichiers médias
│       │   └── media_match_associations # Associations média↔match
│       └── archive/               # Archives Parquet (saisons)
│
└── cache/                         # Cache temporaire (thumbnails, etc.)
```

---

## Composants Principaux

### 1. DuckDBRepository (`src/data/repositories/duckdb_repo.py`)

Le repository central d'accès aux données. En v5, il utilise **ATTACH** pour monter
plusieurs bases DuckDB simultanément :

```python
# Connexion multi-DB
conn = duckdb.connect(player_db_path)
conn.execute("ATTACH ? AS shared (READ_ONLY)", [shared_db_path])
conn.execute("ATTACH ? AS meta (READ_ONLY)", [metadata_db_path])
```

La sous-requête `_get_match_source()` abstrait la jointure entre `shared.match_registry`,
`shared.match_participants` et `player_match_enrichment`, exposant un alias `match_stats`
compatible avec toutes les pages UI existantes.

### 2. DuckDBSyncEngine (`src/data/sync/engine.py`)

Le moteur de synchronisation détecte automatiquement les matchs partagés :

- **Match connu** (`_process_known_match`) : Le match existe déjà dans `match_registry`.
  Seul l'enrichissement personnel est calculé (performance_score, session). Économie : 1-2 appels API.
- **Match nouveau** (`_process_new_match`) : Sync complète — insertion dans `match_registry`,
  `match_participants` (tous les joueurs), `highlight_events`, `medals_earned`.

### 3. Transformers (`src/data/sync/transformers.py`)

Fonctions d'extraction des données JSON de l'API Halo vers les structures DuckDB :

- `extract_match_registry_data()` : Données communes du match
- `extract_all_medals()` : Médailles de TOUS les joueurs (pas seulement le joueur courant)
- `extract_collective_stats()` : Stats de tous les participants

### 4. CitationEngine (`src/analysis/citations/engine.py`)

Moteur de calcul des citations (commendations) basé sur SQL :

- Lecture depuis `shared.medals_earned` et `shared.match_participants`
- Agrégation SQL performante (vs itérations row-by-row en v4)
- Stockage dans `match_citations` (player DB)
- 14 règles configurables via `citation_mappings` (metadata DB)

### 5. Factory (`src/data/repositories/factory.py`)

Pattern Factory pour créer des `DuckDBRepository` avec auto-détection des chemins :

- `shared_db_path` : Auto-détecté depuis `data/warehouse/shared_matches.duckdb`
- `metadata_db_path` : Auto-détecté depuis `data/warehouse/metadata.duckdb`
- Fallback v4 transparent si `shared_matches.duckdb` n'existe pas

---

## Flux de Données

### Synchronisation (Sync)

```
API Halo (SPNKr)
     │
     ▼
DuckDBSyncEngine
     │
     ├── Match nouveau ────────────────────────────────┐
     │   1. Fetch match_stats (API)                    │
     │   2. Fetch skill (API)                          │
     │   3. Fetch events (API)                         ▼
     │   4. extract_match_registry_data()     shared_matches.duckdb
     │   5. extract_collective_stats()        ├── match_registry
     │   6. extract_all_medals()              ├── match_participants
     │                                        ├── highlight_events
     │                                        └── medals_earned
     │
     └── Match connu ──────┐
         1. Calcul perf    │
         2. Session detect ▼
                      stats.duckdb (joueur)
                      └── player_match_enrichment
```

### Lecture (UI)

```
Page UI (ex: timeseries.py)
     │
     ▼
DuckDBRepository.load_matches()
     │
     ├── _get_match_source()
     │   └── JOIN shared.match_registry
     │         + shared.match_participants (WHERE xuid = ?)
     │         + player_match_enrichment
     │   → alias "match_stats"
     │
     └── Résultat : Polars DataFrame
```

---

## Modules Applicatifs

```
src/
├── app/                          # Orchestration application
│   ├── state.py                  # Gestion session_state Streamlit
│   ├── routing.py                # Navigation entre pages
│   ├── sidebar.py                # Sidebar (filtres, profil, sync)
│   ├── page_router.py            # Routeur de pages
│   ├── helpers.py                # Fonctions utilitaires
│   ├── filters.py                # Logique des filtres
│   ├── profile.py                # Gestion profil joueur
│   ├── kpis.py                   # Calcul et affichage KPIs
│   └── data_loader.py            # Chargement données
│
├── config.py                     # Configuration & constantes
│
├── data/                         # Couche données
│   ├── repositories/
│   │   ├── duckdb_repo.py        # Repository DuckDB principal (ATTACH multi-DB)
│   │   ├── _match_queries.py     # Requêtes matchs (_get_match_source)
│   │   ├── _roster_loader.py     # Chargement roster depuis shared
│   │   └── factory.py            # Factory pattern
│   ├── services/                 # Services métier
│   │   ├── timeseries_service.py # Agrégats séries temporelles
│   │   ├── win_loss_service.py   # Bucketing V/D, breakdown cartes
│   │   └── teammates_service.py  # Stats coéquipiers multi-DB
│   ├── sync/                     # Synchronisation API
│   │   ├── api_client.py         # Client SPNKr
│   │   ├── engine.py             # Moteur de sync (v5 shared)
│   │   ├── transformers.py       # Transformations JSON→DB
│   │   ├── migrations.py         # Migrations de schéma
│   │   └── models.py             # Modèles de sync
│   └── query/
│       └── engine.py             # Query Engine DuckDB
│
├── analysis/                     # Logique métier
│   ├── citations/                # Système de citations
│   │   ├── engine.py             # CitationEngine (SQL)
│   │   ├── custom_rules.py       # Règles custom (objectifs)
│   │   └── models.py             # Modèles citations
│   ├── filters.py                # Filtres playlists/modes
│   ├── killer_victim.py          # Analyse confrontations
│   ├── antagonists.py            # Agrégation rivalités
│   ├── sessions.py               # Détection sessions
│   ├── stats.py                  # Calculs statistiques
│   └── performance_score.py      # Score de performance
│
├── ui/                           # Interface utilisateur
│   ├── cache.py                  # Cache Streamlit
│   ├── medals.py                 # Affichage médailles
│   ├── translations.py           # Traductions FR
│   ├── sync.py                   # UI de synchronisation
│   ├── components/               # Composants réutilisables
│   └── pages/                    # Pages du dashboard (23 pages)
│
├── visualization/                # Graphiques Plotly (15 modules)
│
└── utils/                        # Utilitaires (paths, xuid, profiles)
```

---

## Tests

La suite de tests v5 comprend **2768 tests** répartis en :

| Catégorie | Tests | Couverture |
|-----------|-------|-----------|
| Schéma migration | 45 | 95%+ |
| Sync shared matches | 33 | 70%+ |
| Repository v5 | 77 | 75%+ |
| Match queries v5 | 35 | 80%+ |
| UI pages (MockStreamlit) | 147 | 35-84% (selon page) |
| Utils purs | 72 | 90% |
| Sync/backfill | 338 | 84% (transformers), 99% (core) |
| Autres (viz, profile, etc.) | ~2000+ | Variable |

Framework de test :
- **MockStreamlit** : Fixture `conftest.py` pour tester les pages UI en mode headless
- **DuckDB `:memory:`** : Tests isolation complète sans fichier disque
- **Polars DataFrames** : Données synthétiques pour tous les tests

```bash
# Suite complète
python -m pytest

# Hors intégration (recommandé quotidien)
python -m pytest -q --ignore=tests/integration

# Avec couverture
python -m pytest --cov=src --cov-report=html
```

---

## Configuration

### Profils joueurs (`db_profiles.json`)

```json
[
  {
    "gamertag": "MonGamertag",
    "xuid": "1234567890",
    "db_path": "data/players/MonGamertag/stats.duckdb"
  }
]
```

### Paramètres application (`app_settings.json`)

Configuration de l'application Streamlit (thème, langue, options d'affichage).

---

## Différences v4 → v5

| Aspect | v4 | v5 |
|--------|----|----|
| **Stockage matchs** | Dupliqué dans chaque player DB | Centralisé dans `shared_matches.duckdb` |
| **Sync match connu** | Re-sync complète | Skip (enrichissement perso uniquement) |
| **Repository** | 1 connexion (player DB) | ATTACH multi-DB (player + shared + meta) |
| **Pages UI** | `FROM match_stats` | `FROM _get_match_source()` (sous-requête) |
| **Médailles** | Par joueur dans player DB | Tous joueurs dans `shared.medals_earned` |
| **Events** | Par joueur dans player DB | Tous events dans `shared.highlight_events` |
| **Citations** | Calcul à la volée | `CitationEngine` SQL + `match_citations` table |

---

## Voir aussi

- [SHARED_MATCHES_SCHEMA.md](SHARED_MATCHES_SCHEMA.md) — Schéma DDL complet
- [MIGRATION_V4_TO_V5.md](MIGRATION_V4_TO_V5.md) — Guide de migration
- [SYNC_OPTIMIZATIONS_V5.md](SYNC_OPTIMIZATIONS_V5.md) — Optimisations sync
- [TESTING_V5.md](TESTING_V5.md) — Stratégie de tests
- [ARCHITECTURE.md](ARCHITECTURE.md) — Architecture v4 (référence historique)
