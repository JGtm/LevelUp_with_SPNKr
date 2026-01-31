# Data Lineage - Traçabilité des Données Halo

> Ce fichier trace l'origine, les transformations et la destination de chaque flux de données.

## Flux de Données Principaux

### 1. API Halo → SQLite (Legacy)
```
Source: API Halo Infinite (via spnkr)
     ↓
Transform: src/db/loaders.py
     ↓
Destination: SQLite (*.db)
```

### 2. SQLite → Parquet (Migration)
```
Source: SQLite legacy
     ↓
Transform: scripts/migrate_to_parquet.py
     ↓
Destination: data/warehouse/**/*.parquet
```

### 3. Parquet + SQLite → DuckDB (Analyse)
```
Sources: Parquet (facts) + SQLite (metadata)
     ↓
Engine: src/data/query/QueryEngine
     ↓
Output: DataFrames Polars/Pandas
```

## Schéma des Tables

### Match Facts (Parquet)
| Colonne | Type | Description |
|---------|------|-------------|
| match_id | str | Identifiant unique du match |
| xuid | str | Identifiant Xbox du joueur |
| ... | ... | À compléter |

### Métadonnées (SQLite)
- `players` : Profils joueurs
- `playlists` : Modes de jeu
- `maps` : Cartes
- `medal_definitions` : Définitions des médailles

## Transformations Connues

### 1. JSON → SQLite (Référentiels)
**Script**: `scripts/ingest_halo_data.py`
**Date**: 2026-01-31
**Résultat**:

| Source | Table SQLite | Lignes |
|--------|--------------|--------|
| `Playlist_modes_translations.json` → playlists | `playlists` | 14 |
| `Playlist_modes_translations.json` → modes | `game_modes` | 313 |
| `Playlist_modes_translations.json` → categories | `categories` | 16 |
| `static/medals/medals_fr.json` | `medal_definitions` | 153 |

**Validation**: Pydantic v2 (`PlaylistTranslation`, `GameModeTranslation`, `MedalDefinition`)

### 2. API Halo → Parquet (À implémenter)
**Script**: `scripts/migrate_to_parquet.py` (existant)
**Status**: En attente de données API

## Qualité des Données

### Données validées (2026-01-31)
- [x] Playlists: 14 UUIDs uniques
- [x] Modes de jeu: 313 traductions EN/FR
- [x] Catégories: 16 mappings
- [x] Médailles: 153 définitions avec name_id

### Problèmes connus
- Aucun pour l'instant
