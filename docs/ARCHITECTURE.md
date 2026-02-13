# Architecture LevelUp

> Documentation technique de l'architecture du projet.

## Vue d'Ensemble

LevelUp utilise une architecture DuckDB unifiée pour des performances optimales sur les données analytiques.

```
levelup-halo/
├── streamlit_app.py              # Point d'entrée Streamlit
├── openspartan_launcher.py       # Launcher CLI
│
├── src/
│   ├── app/                      # Orchestration application
│   │   ├── state.py              # Gestion session_state
│   │   ├── routing.py            # Navigation
│   │   ├── sidebar.py            # Sidebar (filtres, sync)
│   │   ├── page_router.py        # Routeur de pages
│   │   ├── helpers.py            # Fonctions utilitaires
│   │   ├── filters.py            # Logique des filtres
│   │   ├── profile.py            # Gestion profil joueur
│   │   ├── kpis.py               # Calcul et affichage KPIs
│   │   └── data_loader.py        # Chargement données
│   │
│   ├── config.py                 # Configuration & constantes
│   ├── models.py                 # Dataclasses (entités)
│   │
│   ├── data/                     # Couche données
│   │   ├── repositories/         # Accès aux données
│   │   │   ├── duckdb_repo.py    # Repository DuckDB principal
│   │   │   └── factory.py        # Factory pattern
│   │   ├── services/             # Services métier (Sprint 14)
│   │   │   ├── timeseries_service.py  # Agrégats séries temporelles
│   │   │   ├── win_loss_service.py    # Bucketing V/D, breakdown cartes
│   │   │   └── teammates_service.py   # Stats coéquipiers multi-DB
│   │   ├── integration/          # Bridge Streamlit ↔ Data
│   │   │   └── streamlit_bridge.py # Conversion MatchRow → DataFrame
│   │   ├── sync/                 # Synchronisation API
│   │   │   ├── api_client.py     # Client SPNKr
│   │   │   ├── engine.py         # Moteur de sync
│   │   │   ├── transformers.py   # Transformations JSON→DB
│   │   │   └── models.py         # Modèles de sync
│   │   └── query/                # Requêtes analytiques
│   │       └── engine.py         # Query Engine DuckDB
│   │
│   ├── analysis/                 # Logique métier
│   │   ├── filters.py            # Filtres playlists/modes
│   │   ├── killer_victim.py      # Analyse confrontations
│   │   ├── antagonists.py        # Agrégation rivalités
│   │   ├── sessions.py           # Détection sessions
│   │   ├── stats.py              # Calculs statistiques
│   │   └── performance_score.py  # Score de performance
│   │
│   ├── db/                       # Accès legacy (déprécié)
│   │   ├── loaders.py            # DEPRECATED - DuckDBRepository
│   │   └── loaders_cached.py     # DEPRECATED - DuckDBRepository
│   │
│   ├── ui/                       # Interface utilisateur
│   │   ├── cache.py              # Cache Streamlit
│   │   ├── medals.py             # Affichage médailles
│   │   ├── translations.py       # Traductions FR
│   │   ├── sync.py               # UI de synchronisation
│   │   ├── components/           # Composants réutilisables
│   │   │   ├── radar_chart.py    # Graphes radar
│   │   │   └── chart_annotations.py # Annotations
│   │   └── pages/                # Pages du dashboard
│   │       ├── timeseries.py     # Séries temporelles
│   │       ├── session_compare.py # Comparaison sessions
│   │       ├── win_loss.py       # Victoires/Défaites
│   │       ├── match_history.py  # Historique parties
│   │       ├── teammates.py      # Coéquipiers
│   │       ├── citations.py      # Médailles
│   │       └── match_view.py     # Vue détaillée match
│   │
│   ├── visualization/            # Graphiques Plotly
│   │   ├── theme.py              # Thème Halo
│   │   ├── timeseries.py         # Graphiques temporels
│   │   ├── distributions.py      # Histogrammes, heatmaps
│   │   └── maps.py               # Stats cartes
│   │
│   └── utils/                    # Utilitaires
│       └── paths.py              # Chemins centralisés
│
├── scripts/                      # Scripts CLI
│   ├── sync.py                   # Synchronisation
│   ├── backup_player.py          # Backup Parquet
│   ├── restore_player.py         # Restauration
│   ├── archive_season.py         # Archivage temporel
│   └── migrate_*.py              # Scripts de migration
│
├── data/                         # Données (gitignored)
│   ├── players/                  # Données par joueur
│   │   └── {gamertag}/
│   │       ├── stats.duckdb      # Base principale
│   │       └── archive/          # Archives Parquet
│   └── warehouse/
│       └── metadata.duckdb       # Référentiels partagés
│
└── tests/                        # Tests pytest
    ├── test_duckdb_repository.py
    ├── test_sync_engine.py
    └── ...
```

---

## Architecture des Données v4

### Schéma DuckDB Unifié

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ARCHITECTURE v4 (DuckDB Unifié)                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   data/players/{gamertag}/stats.duckdb                              │
│   ════════════════════════════════════                              │
│   ├── match_stats ─────────► Faits des matchs                       │
│   ├── medals_earned ───────► Médailles par match                    │
│   ├── teammates_aggregate ─► Stats coéquipiers                      │
│   ├── antagonists ─────────► Top killers/victimes                   │
│   ├── player_match_stats ──► Données MMR/skill                      │
│   ├── highlight_events ────► Événements film                        │
│   ├── xuid_aliases ────────► Mapping XUID→Gamertag                  │
│   ├── career_progression ──► Historique rangs                       │
│   ├── sync_meta ───────────► Métadonnées de sync                    │
│   └── mv_* ────────────────► Vues matérialisées                     │
│                                                                     │
│   data/warehouse/metadata.duckdb                                    │
│   ══════════════════════════════                                    │
│   ├── playlists ───────────► Définitions des playlists              │
│   ├── maps ────────────────► Définitions des cartes                 │
│   ├── game_modes ──────────► Modes de jeu (FR/EN)                   │
│   ├── medal_definitions ───► Référentiel médailles                  │
│   └── career_ranks ────────► Traductions des rangs                  │
│                                                                     │
│   data/players/{gamertag}/archive/                                  │
│   ════════════════════════════════                                  │
│   ├── matches_2023.parquet ► Matchs archivés                        │
│   └── archive_index.json ──► Index des archives                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Avantages Architecture v4

| Critère | SQLite + Parquet | DuckDB Unifié |
|---------|------------------|---------------|
| Jointures cross-store | `ATTACH` + bridge | Natif |
| Requêtes OLAP | Via DuckDB | Direct |
| Transactions | SQLite seulement | ACID partout |
| Compression | Snappy | Zstd (2x mieux) |
| Complexité code | 2-3 technos | 1 techno |

---

## Flux de Données

### 1. Synchronisation (API → DuckDB)

```
API SPNKr ─► SPNKrAPIClient ─► Transformers ─► DuckDBSyncEngine ─► stats.duckdb
     │              │                │                │
     │              │                │                ├─► match_stats
     │              │                │                ├─► player_match_stats
     │              │                │                ├─► highlight_events
     │              │                │                └─► xuid_aliases
     │              │                │
     │              │                └─► JSON → Dataclasses (Pydantic)
     │              │
     │              └─► Async HTTP avec rate limiting
     │
     └─► Endpoints: matches, skill, film, economy
```

### 2. Lecture (DuckDB → UI)

```
Streamlit UI (Pages)
     │
     ▼
Services (Sprint 14)                    ← NOUVEAU
     │  TimeseriesService
     │  WinLossService
     │  TeammatesService
     │
     ▼
DuckDBRepository / Analysis
     │
     ├─► Lecture directe (match_stats, etc.)
     │
     ├─► Vues matérialisées (mv_map_stats, etc.)
     │   └─► Rafraîchies après chaque sync
     │
     └─► Lazy loading + Pagination
         └─► load_recent_matches(limit=50)
```

### Architecture Services (v4.5)

Les services encapsulent les calculs lourds entre la couche Data et les pages UI :

```
Page UI ──► Service ──► Repository / Analysis ──► DuckDB
  │              │
  │              └─► Retourne des dataclasses typées (frozen)
  │                  - CumulativeMetrics
  │                  - PeriodTable
  │                  - TeammateStats
  │                  - etc.
  │
  └─► N'a plus de calcul inline, consomme uniquement
      les dataclasses retournées par le service.
```

| Service | Page | Responsabilités |
|---------|------|-----------------|
| `TimeseriesService` | `timeseries.py` | Performance score, métriques cumulatives, score/min, win rate glissant, first events, perfect kills |
| `WinLossService` | `win_loss.py` | Bucketing temporel, breakdown cartes, scope amis |
| `TeammatesService` | `teammates.py` | Stats coéquipier multi-DB, enrichissement perfect kills, profils radar, impact |

---

## Composants Clés

### DuckDBRepository

Repository principal pour l'accès aux données :

```python
from src.data.repositories import DuckDBRepository

repo = DuckDBRepository(
    db_path="data/players/MonGamertag/stats.duckdb",
    xuid="2533274823110022"
)

# Lecture des matchs
matches = repo.load_matches(limit=100)

# Vues matérialisées
map_stats = repo.get_map_stats(min_matches=3)
global_stats = repo.get_global_stats()

# Pagination
matches, total_pages = repo.load_matches_paginated(page=1, page_size=50)
```

### DuckDBSyncEngine

Moteur de synchronisation API → DuckDB :

```python
from src.data.sync import DuckDBSyncEngine, SyncOptions

engine = DuckDBSyncEngine(
    db_path="data/players/MonGamertag/stats.duckdb",
    xuid="2533274823110022"
)

options = SyncOptions(
    match_type="matchmaking",
    max_matches=50,
    with_skill=True,
    with_events=True
)

result = await engine.sync_delta(options)
print(result.to_message())
```

### Vues Matérialisées

Tables de cache rafraîchies après chaque sync :

| Vue | Contenu | Usage |
|-----|---------|-------|
| `mv_map_stats` | Stats par carte | Page Cartes |
| `mv_mode_category_stats` | Stats par mode | Filtres |
| `mv_session_stats` | Stats par session | Sessions |
| `mv_global_stats` | KPIs globaux | Dashboard |

```python
# Rafraîchir les vues
repo.refresh_materialized_views()

# Lecture instantanée
stats = repo.get_map_stats()
```

---

## Stratégies de Performance

### 1. Lazy Loading

Chargement à la demande pour réduire la mémoire :

```python
# Au démarrage : seulement les 50 derniers matchs
recent = repo.load_recent_matches(limit=50)

# Navigation : pagination par 50
matches, pages = repo.load_matches_paginated(page=2, page_size=50)
```

### 2. Cache Streamlit

3 niveaux de cache :

| Niveau | Mécanisme | TTL |
|--------|-----------|-----|
| L1 | `@st.cache_data` | Session |
| L2 | Vues matérialisées DuckDB | Post-sync |
| L3 | Fichiers Parquet | Permanent |

### 3. Archivage Temporel

Pour les joueurs avec beaucoup de matchs :

```python
# Archiver les matchs > 1 an
python scripts/archive_season.py --gamertag X --older-than-days 365

# Vue unifiée DB + archives
all_matches = repo.load_all_matches_unified()
```

---

## Configuration

### db_profiles.json

```json
{
  "version": "2.1",
  "profiles": {
    "MonGamertag": {
      "xuid": "2533274823110022",
      "gamertag": "MonGamertag",
      "db_path": "data/players/MonGamertag/stats.duckdb",
      "is_default": true
    }
  }
}
```

### Variables d'Environnement

| Variable | Description |
|----------|-------------|
| `OPENSPARTAN_DB` | Chemin DB par défaut |
| `SPNKR_AZURE_CLIENT_ID` | Azure App ID |
| `SPNKR_OAUTH_REFRESH_TOKEN` | Token OAuth |

---

## Tests

```bash
# Tous les tests
pytest

# Tests spécifiques
pytest tests/test_duckdb_repository.py -v
pytest tests/test_sync_engine.py -v
pytest tests/test_materialized_views.py -v

# Avec couverture
pytest --cov=src --cov-report=html
```

---

## Stack Technique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Runtime | Python | 3.10+ |
| UI | Streamlit | 1.28+ |
| Base de données | DuckDB | 0.10+ |
| DataFrames | Polars | 0.20+ |
| Validation | Pydantic | 2.5+ |
| Graphiques | Plotly | 5.18+ |
| API Halo | SPNKr | 0.9+ |
