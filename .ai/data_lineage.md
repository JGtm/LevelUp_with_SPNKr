# Data Lineage - Traçabilité des Données Halo

> Ce fichier trace l'origine, les transformations et la destination de chaque flux de données.
> Mis à jour : 2026-02-01

## Architecture v4 - DuckDB Unifié

```
┌─────────────────┐      ┌─────────────────────────────────────────────┐
│   API SPNKr     │      │              DuckDB Engine                  │
│  (Halo Infinite)│      │                                             │
└────────┬────────┘      │  ┌─────────────────────────────────────┐   │
         │               │  │  metadata.duckdb (global)           │   │
         ▼               │  │  - playlists, maps, game_modes      │   │
┌─────────────────┐      │  │  - medal_definitions, career_ranks  │   │
│  Pydantic v2    │      │  │  - players                          │   │
│  Validation     │      │  └─────────────────────────────────────┘   │
└────────┬────────┘      │                                             │
         │               │  ┌─────────────────────────────────────┐   │
         ▼               │  │  players/{gt}/stats.duckdb          │   │
┌─────────────────┐      │  │  - match_stats                      │   │
│  Transformation │──────│  │  - medals_earned                    │   │
│  Polars         │      │  │  - teammates_aggregate              │   │
└─────────────────┘      │  │  - antagonists, weapon_stats        │   │
                         │  │  - skill_history, sessions          │   │
                         │  └─────────────────────────────────────┘   │
                         │                                             │
                         │  ┌─────────────────────────────────────┐   │
                         │  │  archive/parquet/ (cold storage)    │   │
                         │  └─────────────────────────────────────┘   │
                         └─────────────────────────────────────────────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │   Streamlit UI  │
                                   │   (DataFrames)  │
                                   └─────────────────┘
```

## Flux de Données Principaux

### 1. API Halo → DuckDB (Production)
```
Source: API Halo Infinite (via spnkr)
     ↓
Validation: Pydantic v2 (MatchFact, MedalAward)
     ↓
Transform: Polars (src/data/infrastructure/)
     ↓
Destination: data/players/{gamertag}/stats.duckdb
```

### 2. JSON → DuckDB (Référentiels)
```
Source: Fichiers JSON locaux
     ↓
Script: scripts/ingest_halo_data.py
     ↓
Destination: data/warehouse/metadata.duckdb
```

### 3. DuckDB → Parquet (Archive)
```
Source: DuckDB (match_stats)
     ↓
Export: COPY ... TO 'file.parquet'
     ↓
Destination: data/archive/parquet/
```

## Structure des Données

### Métadonnées (metadata.duckdb)

| Table | Lignes | Description |
|-------|--------|-------------|
| `playlists` | 14 | Définitions des playlists |
| `game_modes` | 313 | Traductions EN/FR des modes |
| `categories` | 16 | Catégories de modes |
| `medal_definitions` | 153 | Définitions des médailles |
| `career_ranks` | 273 | Rangs de carrière (0-272) |
| `players` | variable | Profils des joueurs connus |

### Données Joueur (stats.duckdb)

| Table | Cardinalité | Description |
|-------|-------------|-------------|
| `match_stats` | 1:N par joueur | Faits des matchs |
| `medals_earned` | M:N | Médailles par match |
| `teammates_aggregate` | 1:N | Stats agrégées coéquipiers |
| `antagonists` | 1:N | Top killers/victimes |
| `weapon_stats` | 1:N | Stats par arme |
| `skill_history` | 1:N | Historique CSR |
| `sessions` | 1:N | Sessions de jeu |

## Transformations

### Ingestion Référentiels (2026-01-31)

| Source | Table DuckDB | Lignes |
|--------|--------------|--------|
| `Playlist_modes_translations.json` | `playlists` | 14 |
| `Playlist_modes_translations.json` | `game_modes` | 313 |
| `Playlist_modes_translations.json` | `categories` | 16 |
| `static/medals/medals_fr.json` | `medal_definitions` | 153 |

### Calculs Dérivés

| Donnée | Source | Formule |
|--------|--------|---------|
| `kda` | match_stats | `(kills + assists/3) / max(deaths, 1)` |
| `accuracy` | match_stats | `shots_hit / shots_fired * 100` |
| `net_kills` | antagonists | `times_killed - times_killed_by` |
| `headshot_rate` | weapon_stats | `headshot_kills / total_kills * 100` |

## Qualité des Données

### Validations Pydantic v2
- [x] Playlists : UUID format, noms non-vides
- [x] Modes de jeu : Traductions EN/FR présentes
- [x] Médailles : name_id unique, sprite_index valide
- [x] Matchs : Timestamps valides, outcome ∈ {1,2,3,4}

### Contraintes DuckDB
- Clés primaires sur toutes les tables
- Index sur colonnes fréquemment filtrées
- Colonnes GENERATED pour les calculs

## Problèmes Connus

- Aucun pour l'instant

## Références

- `docs/SQL_SCHEMA.md` : Schémas complets des tables
- `.ai/ARCHITECTURE_ROADMAP.md` : Roadmap de migration
- `src/data/domain/models/` : Modèles Pydantic
