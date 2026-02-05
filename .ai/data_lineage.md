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
│ DuckDBSyncEngine│──────│  │  - player_match_stats               │   │
│  Transformers   │      │  │  - highlight_events                 │   │
└─────────────────┘      │  │  - xuid_aliases                     │   │
                         │  │  - teammates_aggregate              │   │
                         │  │  - antagonists                      │   │
                         │  │  - career_progression               │   │
                         │  │  - mv_* (vues matérialisées)        │   │
                         │  └─────────────────────────────────────┘   │
                         │                                             │
                         │  ┌─────────────────────────────────────┐   │
                         │  │  players/{gt}/archive/ (Parquet)    │   │
                         │  │  - matches_*.parquet                │   │
                         │  │  - archive_index.json               │   │
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

### 1. API Halo → DuckDB (Synchronisation)

```
Source: API Halo Infinite (via SPNKr)
     ↓
Client: SPNKrAPIClient (src/data/sync/api_client.py)
     ↓
Transformers: transform_match_stats(), transform_skill_stats(), etc.
     ↓
Engine: DuckDBSyncEngine (src/data/sync/engine.py)
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
Script: scripts/archive_season.py
     ↓
Destination: data/players/{gamertag}/archive/matches_*.parquet
```

### 4. Parquet → DuckDB (Restore)

```
Source: Backup Parquet
     ↓
Script: scripts/restore_player.py
     ↓
Destination: data/players/{gamertag}/stats.duckdb
```

## Tables et Cardinalité

### Métadonnées (metadata.duckdb)

| Table | Lignes | Description |
|-------|--------|-------------|
| `playlists` | ~14 | Définitions playlists |
| `game_modes` | ~313 | Modes de jeu (FR/EN) |
| `categories` | ~16 | Catégories de modes |
| `medal_definitions` | ~153 | Définitions médailles |
| `career_ranks` | 273 | Rangs (0-272) |
| `players` | Variable | Joueurs connus |

### Données Joueur (stats.duckdb)

| Table | Cardinalité | Description |
|-------|-------------|-------------|
| `match_stats` | 1:N par joueur | Faits des matchs |
| `medals_earned` | M:N | Médailles par match |
| `player_match_stats` | 1:1 | Données MMR par match |
| `highlight_events` | 1:N | Événements par match |
| `teammates_aggregate` | 1:N | Stats coéquipiers |
| `antagonists` | 1:N | Rivalités |
| `xuid_aliases` | 1:1 | Mapping XUID→Gamertag |
| `career_progression` | 1:N | Historique rangs |
| `sync_meta` | 1:1 | Métadonnées sync |

### Vues Matérialisées

| Vue | Description | Rafraîchissement |
|-----|-------------|------------------|
| `mv_map_stats` | Stats par carte | Post-sync |
| `mv_mode_category_stats` | Stats par mode | Post-sync |
| `mv_session_stats` | Stats par session | Post-sync |
| `mv_global_stats` | Stats globales | Post-sync |

## Transformations Clés

| Donnée | Source | Formule |
|--------|--------|---------|
| `kda` | match_stats | `(kills + assists/3) / max(deaths, 1)` |
| `accuracy` | match_stats | `shots_hit / shots_fired * 100` |
| `net_kills` | antagonists | `times_killed - times_killed_by` |
| `win_rate` | mv_global_stats | `wins / total_matches * 100` |
| `headshot_rate` | weapon_stats | `headshot_kills / total_kills * 100` |

## Validations

### Pydantic v2

- [x] MatchStatsRow : Validation des champs matchs
- [x] PlayerMatchStatsRow : Validation MMR
- [x] HighlightEventRow : Validation événements
- [x] XuidAliasRow : Validation XUID (16 chiffres)
- [x] CareerRankData : Validation progression

### Contraintes DuckDB

- Clés primaires sur toutes les tables
- Index sur colonnes fréquemment filtrées (`start_time`, `playlist_id`)
- Colonnes GENERATED pour les calculs (`net_kills`, `accuracy`)

## ⚠️ RÈGLE CRITIQUE : Chargement Stats Multi-Joueurs

Dans l'architecture DuckDB v4, **chaque joueur a sa propre DB**.

### ❌ Erreur fréquente

```python
# FAUX - le xuid est IGNORÉ pour DuckDB v4
teammate_df = load_df_optimized(db_path, teammate_xuid, db_key=db_key)
# → Charge toujours depuis db_path (joueur principal) !
```

### ✅ Bonne pratique

```python
# CORRECT - Charger depuis la DB du coéquipier
from pathlib import Path

def _load_teammate_stats_from_own_db(gamertag, match_ids, reference_db_path):
    base_dir = Path(reference_db_path).parent.parent
    teammate_db = base_dir / gamertag / "stats.duckdb"
    if not teammate_db.exists():
        return pd.DataFrame()
    df = load_df_optimized(str(teammate_db), "", db_key=None)
    return df[df["match_id"].isin(match_ids)]
```

### Flux correct pour afficher stats coéquipier

```
1. Identifier match_id communs (teammates_aggregate)
      ↓
2. Obtenir gamertag coéquipier (display_name_from_xuid)
      ↓
3. Construire chemin: data/players/{gamertag}/stats.duckdb
      ↓
4. Charger depuis cette DB
      ↓
5. Filtrer sur match_id communs
```

## Problèmes Connus

- Aucun problème majeur identifié

## Références

- `docs/SQL_SCHEMA.md` : Schémas complets
- `docs/SYNC_GUIDE.md` : Guide de synchronisation
- `.ai/ARCHITECTURE_ROADMAP.md` : Roadmap des phases
