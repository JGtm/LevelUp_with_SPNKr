# Project Map - OpenSpartan Graph

> Ce fichier est la cartographie vivante du projet. L'agent IA doit le consulter et le mettre à jour.

## État Actuel (2026-02-01)

### Migration DuckDB Unifiée

- **Phase 1 COMPLETE** : Référentiels JSON → SQLite ✅
- **Phase 2 COMPLETE** : Migration vers DuckDB Unifiée ✅
- **Phase 3 COMPLETE** : Enrichissement des Données (antagonistes) ✅
- **Phase 4 COMPLETE** : Optimisations Avancées ✅
  - Vues matérialisées (mv_map_stats, mv_mode_category_stats, mv_global_stats, mv_session_stats)
  - Lazy loading et pagination (load_recent_matches, load_matches_paginated)
  - Backup/Restore Parquet avec compression Zstd

### Architecture Cible v4

```
data/
├── players/                    # Données par joueur
│   └── {gamertag}/
│       └── stats.duckdb       # DB DuckDB persistée
├── warehouse/
│   └── metadata.duckdb        # Référentiels partagés
└── archive/
    └── parquet/               # Cold storage (backup)
```

## Architecture des Données

### Sources de Données
- **DuckDB** : Moteur unifié pour toutes les données (v4)
- **JSON** : Fichiers de configuration (`static/medals/*.json`)
- **Parquet** : Archive/backup (`data/archive/parquet/`)

### Modules Clés

#### Ingestion & Validation
- `scripts/ingest_halo_data.py` : Ingestion JSON → DuckDB
- `src/data/domain/models/` : Modèles Pydantic (MatchFact, MedalAward, PlayerProfile)

#### Stockage DuckDB Unifié
- `src/data/infrastructure/database/duckdb_engine.py` : Moteur DuckDB
- `src/data/infrastructure/parquet/` : Lecture/écriture Parquet (archive)
- `src/data/query/` : Requêtes analytiques

#### Repositories
- `src/data/repositories/legacy.py` : Accès legacy SQLite (rétrocompat)
- `src/data/repositories/hybrid.py` : Nouveau système DuckDB
- `src/data/repositories/factory.py` : Factory avec modes

## Nouvelles Tables (v4)

| Table | Description |
|-------|-------------|
| `antagonists` | Top killers/victimes (rivalités) |
| `weapon_stats` | Stats par arme |
| `skill_history` | Historique CSR |
| `career_ranks` | Traductions des rangs |

## Dépendances Critiques

| Package | Version | Usage |
|---------|---------|-------|
| pydantic | >=2.5.0 | Validation données API |
| polars | >=0.20.0 | DataFrame haute performance |
| duckdb | >=0.10.0 | **Moteur unique** (requêtes + stockage) |
| streamlit | >=1.28.0 | Interface utilisateur |

## Points d'Entrée
- `streamlit_app.py` : Application principale
- `openspartan_launcher.py` : Lanceur

## Scripts Utilitaires

| Script | Description |
|--------|-------------|
| `scripts/sync.py` | Synchronisation SPNKr + refresh vues matérialisées |
| `scripts/backup_player.py` | Export Parquet avec compression Zstd |
| `scripts/restore_player.py` | Import depuis backup Parquet |
| `scripts/migrate_player_to_duckdb.py` | Migration SQLite → DuckDB |
| `scripts/populate_antagonists.py` | Calcul des antagonistes |

## Configuration

- `db_profiles.json` : Profils joueurs avec chemins vers `data/players/`
- `app_settings.json` : Configuration de l'application

## Documentation

| Document | Contenu |
|----------|---------|
| `docs/BACKUP_RESTORE.md` | Guide backup/restore Parquet |
| `docs/SQL_SCHEMA.md` | Schémas DuckDB |
| `docs/DATA_ARCHITECTURE.md` | Architecture des données |

## Dernière Mise à Jour
- **2026-02-01** : Phase 4 terminée (vues matérialisées, lazy loading, backup/restore)
