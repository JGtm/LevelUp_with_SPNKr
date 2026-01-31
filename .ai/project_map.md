# Project Map - OpenSpartan Graph

> Ce fichier est la cartographie vivante du projet. L'agent IA doit le consulter et le mettre à jour.

## État Actuel (2026-01-31)

### Migration Hybrid Storage
- **Phase 1 COMPLETE**: Référentiels JSON → SQLite
  - `data/warehouse/metadata.db` créé
  - 496 lignes ingérées (playlists, modes, médailles, catégories)
  - Validation Pydantic v2 fonctionnelle
  - Vérification DuckDB OK

- **Phase 2 PENDING**: Matchs API → Parquet
  - Infrastructure Parquet prête (`src/data/infrastructure/parquet/`)
  - Modèles MatchFact/MedalAward prêts
  - En attente de données API

## Architecture des Données

### Sources de Données
- **JSON** : Fichiers de configuration et assets (`data/`, `static/medals/*.json`)
- **SQLite** : Base relationnelle legacy (`src/db/`)
- **Parquet** : Données froides/volumineuses (`data/warehouse/`)

### Modules Clés

### Ingestion & Validation
- `scripts/ingest_halo_data.py` : Ingestion JSON → SQLite avec Pydantic
- `src/data/domain/models/` : Modèles Pydantic (MatchFact, MedalAward, PlayerProfile)

### Stockage Hybride
- `src/data/infrastructure/database/` : SQLite (metadata, hot data)
- `src/data/infrastructure/parquet/` : Parquet (match facts, cold data)
- `src/data/query/` : DuckDB engine pour jointures cross-store

### Repositories
- `src/data/repositories/legacy.py` : Accès legacy SQLite
- `src/data/repositories/hybrid.py` : Nouveau système Parquet+SQLite
- `src/data/repositories/shadow.py` : Migration progressive

## Dépendances Critiques

| Package | Version | Usage |
|---------|---------|-------|
| pydantic | >=2.5.0 | Validation données API |
| polars | >=0.20.0 | DataFrame haute performance |
| duckdb | >=0.10.0 | Jointures SQLite+Parquet |
| streamlit | >=1.28.0 | Interface utilisateur |

## Points d'Entrée
- `streamlit_app.py` : Application principale
- `openspartan_launcher.py` : Lanceur

## Dernière Mise à Jour
- **2026-01-31** : Initialisation workflow agentique, ingestion référentiels JSON → SQLite
