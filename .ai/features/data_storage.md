# Data Storage - Architecture DuckDB Unifiée (v4)

> **Features implémentées (S0-S5)** : P2 (migration Polars core), P3 (damage_dealt/damage_taken dans match_participants). Architecture v4 DuckDB complète.

## Résumé
Architecture de stockage DuckDB unifiée (v4) pour les analytics Halo Infinite. Chaque joueur a sa propre DB (`data/players/{gamertag}/stats.duckdb`). Les métadonnées partagées sont dans `data/warehouse/metadata.duckdb`. SQLite est proscrit (sauf scripts de migration legacy).

## Inputs
- **JSON de référentiels** :
  - `Playlist_modes_translations.json` : Playlists, modes, catégories
  - `static/medals/medals_fr.json` : Définitions médailles FR
  - `static/medals/medals_en.json` : Définitions médailles EN
- **Données de matchs** (via SPNKr ou import) :
  - Stats par match : kills, deaths, assists, accuracy, KDA, etc.
  - Médailles obtenues par match
  - Rosters et événements highlight

## Outputs
- **DuckDB** (`data/warehouse/metadata.duckdb`) : Référentiels partagés
- **DuckDB** (`data/players/{gamertag}/stats.duckdb`) : Stats par joueur
  - Tables : `match_stats`, `medals_earned`, `teammates_aggregate`, `antagonists`, `highlight_events`, `career_progression`, `mv_*`
- **Parquet** (`data/players/{gamertag}/archive/`) : Archives saison

## Dépendances
- **Packages externes** :
  - `polars` : DataFrames haute performance (Pandas proscrit)
  - `duckdb` : Moteur SQL OLAP (stockage et requêtes)
  - `pydantic` v2 : Validation des modèles
- **Modules internes** :
  - `src.data.repositories.duckdb_repo` : DuckDBRepository (accès unifié)
  - `src.data.sync.engine` : SyncEngine (synchronisation)
  - `src.data.sync.models` : Modèles Pydantic (MatchRow, MatchParticipantRow, etc.)

## Logique Métier

### Schéma SQLite (métadonnées chaudes)
```sql
-- Dimensions
players (xuid PK, gamertag, service_tag, emblem_path, backdrop_path, career_rank, last_seen_at)
playlists (asset_id PK, version_id, public_name, description, is_ranked, category)
maps (asset_id PK, version_id, public_name, description, thumbnail_path)
game_variants (asset_id PK, version_id, public_name, description, category)
medal_definitions (name_id PK, name_en, name_fr, description_en, description_fr, difficulty)

-- Relations
friends (owner_xuid, friend_xuid PK, friend_gamertag, nickname)
sessions (session_id PK, xuid, start_time, end_time, match_count, stats...)

-- Sync tracking
sync_meta (xuid PK, last_sync_at, last_match_id, total_matches, sync_status)
```

### Schéma Parquet (faits volumineux)
```
match_facts/
├── player=1234567890/
│   ├── year=2025/
│   │   ├── month=01/
│   │   │   └── data.parquet
│   │   └── month=02/
│   │       └── data.parquet
```

Colonnes Parquet (types optimisés) :
| Colonne | Type | Description |
|---------|------|-------------|
| match_id | String | UUID du match |
| xuid | String | Joueur |
| start_time | Datetime(us, UTC) | Début du match |
| year, month | Int16, Int8 | Partitionnement |
| kills, deaths, assists | Int16 | Stats |
| kda, accuracy | Float32 | Ratios |
| outcome | Int8 | 2=Win, 3=Loss, 1=Tie, 4=NoFinish |
| performance_score | Float32 | Score relatif 0-100 |

### Flux d'ingestion
```
1. Lire JSON de référentiel
2. Valider avec Pydantic (PlaylistTranslation, MedalDefinition, etc.)
3. Upsert dans SQLite (INSERT OR REPLACE)
4. Pour les matchs: Valider avec MatchFactInput
5. Transformer en MatchFact (ajout year, month, performance_score)
6. Écrire en Parquet partitionné (append + déduplique sur match_id)
```

## Points d'Attention
- **Dédoublonnage** : `write_match_facts()` fusionne avec l'existant sur `match_id`
- **Types stricts** : Casting explicite avant écriture Parquet (Int16, Float32)
- **Index SQLite** : Créés sur `gamertag`, `start_time` pour lookups rapides
- **Row groups** : 100,000 lignes par row group pour lecture optimale
- **SQLite attach** : DuckDB attache en READ_ONLY pour éviter locks

## Fichiers Clés
| Fichier | Rôle |
|---------|------|
| `src/data/infrastructure/database/sqlite_metadata.py` | Store SQLite |
| `src/data/infrastructure/parquet/writer.py` | Writer Parquet |
| `src/data/infrastructure/parquet/reader.py` | Reader Parquet |
| `src/data/domain/models/match.py` | MatchFactInput, MatchFact |
| `src/data/domain/models/medal.py` | MedalAward |
| `src/data/domain/models/player.py` | PlayerProfile |
| `scripts/ingest_halo_data.py` | Ingestion référentiels |
