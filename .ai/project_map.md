# Project Map - OpenSpartan Graph

> Ce fichier est la cartographie vivante du projet. L'agent IA doit le consulter et le mettre à jour.

## État Actuel (2026-02-01)

### Migration DuckDB Unifiée

- **Phase 1 COMPLETE** : Référentiels JSON → SQLite ✅
- **Phase 2 EN COURS** : Migration vers DuckDB Unifiée 🚧
  - Nouvelle structure `data/players/{gamertag}/`
  - Migration `metadata.db` → `metadata.duckdb`
  - Suppression de la redondance MatchCache/Parquet

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

## Configuration

- `db_profiles.json` : Profils joueurs avec chemins vers `data/players/`
- `app_settings.json` : Configuration de l'application

## Dernière Mise à Jour
- **2026-02-01** : Migration vers architecture DuckDB unifiée, fusion des fichiers de planification
