# Schémas de Données

## Vue d'ensemble

L'architecture hybride utilise deux types de stockage :

1. **SQLite** (`metadata.db`) : Données relationnelles/chaudes
2. **Parquet** : Données volumineuses/froides (faits)

---

## SQLite : Schéma des Métadonnées

### Table `players`

Profils des joueurs (dimension principale).

| Colonne | Type | Description |
|---------|------|-------------|
| `xuid` | TEXT PK | Xbox User ID unique |
| `gamertag` | TEXT | Nom d'affichage Xbox |
| `service_tag` | TEXT | Tag de service (4 chars) |
| `emblem_path` | TEXT | Chemin vers l'emblème |
| `backdrop_path` | TEXT | Chemin vers le backdrop |
| `career_rank` | INTEGER | Rang de carrière (0-272) |
| `last_seen_at` | TEXT | Dernier match joué (ISO 8601) |
| `created_at` | TEXT | Date de création |
| `updated_at` | TEXT | Date de mise à jour |

### Table `playlists`

Définitions des playlists (dimension).

| Colonne | Type | Description |
|---------|------|-------------|
| `asset_id` | TEXT PK | ID de l'asset |
| `version_id` | TEXT | Version de l'asset |
| `public_name` | TEXT | Nom affiché |
| `description` | TEXT | Description |
| `is_ranked` | INTEGER | 1 si ranked, 0 sinon |
| `category` | TEXT | Catégorie (ranked, social, btb, custom) |
| `raw_json` | TEXT | JSON brut pour backup |
| `created_at` | TEXT | Date de création |

### Table `maps`

Définitions des cartes (dimension).

| Colonne | Type | Description |
|---------|------|-------------|
| `asset_id` | TEXT PK | ID de l'asset |
| `version_id` | TEXT | Version de l'asset |
| `public_name` | TEXT | Nom affiché |
| `description` | TEXT | Description |
| `thumbnail_path` | TEXT | Chemin vers la miniature |
| `raw_json` | TEXT | JSON brut pour backup |
| `created_at` | TEXT | Date de création |

### Table `game_variants`

Variantes de jeu (dimension).

| Colonne | Type | Description |
|---------|------|-------------|
| `asset_id` | TEXT PK | ID de l'asset |
| `version_id` | TEXT | Version de l'asset |
| `public_name` | TEXT | Nom affiché |
| `description` | TEXT | Description |
| `category` | TEXT | Catégorie (slayer, ctf, oddball, etc.) |
| `raw_json` | TEXT | JSON brut |
| `created_at` | TEXT | Date de création |

### Table `friends`

Relations d'amitié.

| Colonne | Type | Description |
|---------|------|-------------|
| `owner_xuid` | TEXT PK | XUID du propriétaire |
| `friend_xuid` | TEXT PK | XUID de l'ami |
| `friend_gamertag` | TEXT | Gamertag de l'ami |
| `nickname` | TEXT | Surnom personnalisé |
| `added_at` | TEXT | Date d'ajout |

### Table `sessions`

Sessions de jeu détectées.

| Colonne | Type | Description |
|---------|------|-------------|
| `session_id` | TEXT PK | ID unique de session |
| `xuid` | TEXT | XUID du joueur |
| `start_time` | TEXT | Début de session (ISO 8601) |
| `end_time` | TEXT | Fin de session |
| `match_count` | INTEGER | Nombre de matchs |
| `total_kills` | INTEGER | Total kills |
| `total_deaths` | INTEGER | Total deaths |
| `total_assists` | INTEGER | Total assists |
| `avg_kda` | REAL | KDA moyen |
| `avg_accuracy` | REAL | Précision moyenne |
| `performance_score` | REAL | Score de performance |
| `created_at` | TEXT | Date de création |

### Table `sync_meta`

État de synchronisation par joueur.

| Colonne | Type | Description |
|---------|------|-------------|
| `xuid` | TEXT PK | XUID du joueur |
| `last_sync_at` | TEXT | Dernière synchronisation |
| `last_match_id` | TEXT | Dernier match importé |
| `total_matches` | INTEGER | Nombre total de matchs |
| `total_parquet_rows` | INTEGER | Lignes dans Parquet |
| `sync_status` | TEXT | Statut (idle, syncing, error) |
| `error_message` | TEXT | Message d'erreur |

### Table `medal_definitions`

Référentiel des médailles.

| Colonne | Type | Description |
|---------|------|-------------|
| `name_id` | INTEGER PK | ID de la médaille |
| `name_en` | TEXT | Nom anglais |
| `name_fr` | TEXT | Nom français |
| `description_en` | TEXT | Description anglaise |
| `description_fr` | TEXT | Description française |
| `difficulty` | TEXT | Difficulté (normal, heroic, legendary, mythic) |
| `sprite_path` | TEXT | Chemin vers le sprite |

### Table `migration_meta`

Suivi de la migration.

| Colonne | Type | Description |
|---------|------|-------------|
| `key` | TEXT PK | Clé de métadonnée |
| `value` | TEXT | Valeur |
| `updated_at` | TEXT | Date de mise à jour |

---

## Parquet : Schémas des Faits

### Table `match_facts`

Faits des matchs (1 ligne = 1 joueur dans 1 match).

| Colonne | Type Parquet | Description |
|---------|--------------|-------------|
| `match_id` | STRING | ID unique du match |
| `xuid` | STRING | XUID du joueur (partition) |
| `start_time` | TIMESTAMP[us, tz=UTC] | Début du match |
| `year` | INT16 | Année (partition) |
| `month` | INT8 | Mois (partition) |
| `playlist_id` | STRING | FK vers playlists |
| `map_id` | STRING | FK vers maps |
| `game_variant_id` | STRING | FK vers game_variants |
| `playlist_name` | STRING | Nom de playlist (dénormalisé) |
| `map_name` | STRING | Nom de carte (dénormalisé) |
| `game_variant_name` | STRING | Nom de variante (dénormalisé) |
| `outcome` | INT8 | 1=Tie, 2=Win, 3=Loss, 4=NoFinish |
| `team_id` | INT8 | ID de l'équipe |
| `kills` | INT16 | Nombre de kills |
| `deaths` | INT16 | Nombre de deaths |
| `assists` | INT16 | Nombre d'assists |
| `kda` | FLOAT32 | Ratio KDA |
| `accuracy` | FLOAT32 | Précision (%) |
| `headshot_kills` | INT16 | Kills en headshot |
| `max_killing_spree` | INT16 | Meilleure série |
| `time_played_seconds` | INT32 | Temps joué (s) |
| `avg_life_seconds` | FLOAT32 | Durée de vie moyenne (s) |
| `my_team_score` | INT16 | Score de mon équipe |
| `enemy_team_score` | INT16 | Score équipe adverse |
| `team_mmr` | FLOAT32 | MMR de mon équipe |
| `enemy_mmr` | FLOAT32 | MMR équipe adverse |
| `session_id` | STRING | ID de session (nullable) |
| `performance_score` | FLOAT32 | Score de performance (nullable) |

**Partitionnement** : `player={xuid}/year={YYYY}/month={MM}/data.parquet`

### Table `medals`

Médailles obtenues (1 ligne = 1 type de médaille par match).

| Colonne | Type Parquet | Description |
|---------|--------------|-------------|
| `match_id` | STRING | ID du match |
| `xuid` | STRING | XUID du joueur (partition) |
| `start_time` | TIMESTAMP[us, tz=UTC] | Début du match |
| `year` | INT16 | Année (partition) |
| `month` | INT8 | Mois (partition) |
| `medal_name_id` | INT32 | FK vers medal_definitions |
| `count` | INT16 | Nombre d'occurrences |

**Partitionnement** : `player={xuid}/year={YYYY}/month={MM}/data.parquet`

---

## Requêtes DuckDB

### Jointure SQLite + Parquet

```sql
-- Attacher la base SQLite
ATTACH DATABASE 'metadata.db' AS meta (TYPE SQLITE, READ_ONLY);

-- Requête avec jointure
SELECT 
    p.gamertag,
    AVG(m.kda) as avg_kda,
    COUNT(*) as match_count
FROM read_parquet('match_facts/player=*/year=*/month=*/*.parquet') m
JOIN meta.players p ON m.xuid = p.xuid
GROUP BY p.gamertag
ORDER BY avg_kda DESC;
```

### Filtrage par partition

```sql
-- Lecture optimisée (pruning de partition)
SELECT *
FROM read_parquet('match_facts/player=1234567890/year=2025/**/*.parquet')
WHERE outcome = 2  -- Victoires uniquement
ORDER BY start_time DESC
LIMIT 100;
```

### Agrégation de médailles

```sql
SELECT 
    d.name_fr,
    SUM(m.count) as total
FROM read_parquet('medals/player=1234567890/**/*.parquet') m
JOIN meta.medal_definitions d ON m.medal_name_id = d.name_id
GROUP BY d.name_fr
ORDER BY total DESC
LIMIT 25;
```

---

## Indexation

### SQLite

```sql
-- Index sur les tables de métadonnées
CREATE INDEX idx_players_gamertag ON players(gamertag);
CREATE INDEX idx_sessions_xuid ON sessions(xuid);
CREATE INDEX idx_sessions_start ON sessions(start_time);
```

### Parquet

Le partitionnement par `player/year/month` permet un pruning automatique des fichiers.
DuckDB n'a besoin de lire que les partitions correspondant aux filtres de la requête.
