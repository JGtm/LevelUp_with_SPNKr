# Schémas de Données - Architecture DuckDB Unifiée

> Mis à jour : 2026-02-01
> Migration vers DuckDB natif avec support Parquet intégré

---

## Vue d'ensemble

L'architecture v4 utilise **DuckDB** comme moteur unique :

| Fichier | Contenu | Scope |
|---------|---------|-------|
| `data/warehouse/metadata.duckdb` | Référentiels partagés | Global |
| `data/players/{gamertag}/stats.duckdb` | Données du joueur | Par joueur |
| `data/archive/parquet/` | Cold storage (optionnel) | Backup |

---

## DuckDB : Métadonnées Globales

**Fichier** : `data/warehouse/metadata.duckdb`

### Table `playlists`

Définitions des playlists (dimension).

| Colonne | Type | Description |
|---------|------|-------------|
| `asset_id` | VARCHAR PK | ID de l'asset |
| `version_id` | VARCHAR | Version de l'asset |
| `public_name` | VARCHAR | Nom affiché |
| `description` | VARCHAR | Description |
| `is_ranked` | BOOLEAN | True si ranked |
| `category` | VARCHAR | ranked, social, btb, custom |
| `raw_json` | JSON | Backup du JSON brut |
| `created_at` | TIMESTAMP | Date de création |

### Table `maps`

Définitions des cartes (dimension).

| Colonne | Type | Description |
|---------|------|-------------|
| `asset_id` | VARCHAR PK | ID de l'asset |
| `version_id` | VARCHAR | Version |
| `public_name` | VARCHAR | Nom affiché |
| `description` | VARCHAR | Description |
| `thumbnail_path` | VARCHAR | Chemin miniature |
| `created_at` | TIMESTAMP | Date de création |

### Table `game_modes`

Modes de jeu (dimension).

| Colonne | Type | Description |
|---------|------|-------------|
| `asset_id` | VARCHAR PK | ID de l'asset |
| `name_en` | VARCHAR | Nom anglais |
| `name_fr` | VARCHAR | Nom français |
| `category` | VARCHAR | slayer, ctf, oddball, etc. |
| `created_at` | TIMESTAMP | Date de création |

### Table `medal_definitions`

Référentiel des médailles.

| Colonne | Type | Description |
|---------|------|-------------|
| `name_id` | INTEGER PK | ID de la médaille |
| `name_en` | VARCHAR | Nom anglais |
| `name_fr` | VARCHAR | Nom français |
| `description_en` | VARCHAR | Description EN |
| `description_fr` | VARCHAR | Description FR |
| `difficulty` | VARCHAR | normal, heroic, legendary, mythic |
| `sprite_index` | INTEGER | Index dans le sprite sheet |
| `sprite_path` | VARCHAR | Chemin vers l'image |

### Table `career_ranks` (NOUVELLE)

Traductions des rangs de carrière (0-272).

| Colonne | Type | Description |
|---------|------|-------------|
| `rank_id` | INTEGER PK | Rang (0 à 272) |
| `tier_name_en` | VARCHAR | "Recruit", "Bronze", etc. |
| `tier_name_fr` | VARCHAR | "Recrue", "Bronze", etc. |
| `grade` | INTEGER | Grade dans le tier (1 à N) |
| `xp_required` | INTEGER | XP cumulé requis |
| `sprite_path` | VARCHAR | Chemin vers l'icône |

### Table `players`

Profils des joueurs connus.

| Colonne | Type | Description |
|---------|------|-------------|
| `xuid` | VARCHAR PK | Xbox User ID |
| `gamertag` | VARCHAR | Nom d'affichage |
| `service_tag` | VARCHAR | Tag 4 chars |
| `emblem_path` | VARCHAR | Chemin emblème |
| `career_rank` | INTEGER | FK → career_ranks |
| `last_seen_at` | TIMESTAMP | Dernier match |
| `created_at` | TIMESTAMP | Date création |
| `updated_at` | TIMESTAMP | Dernière mise à jour |

---

## DuckDB : Données Joueur

**Fichier** : `data/players/{gamertag}/stats.duckdb`

### Table `match_stats`

Faits des matchs (1 ligne = 1 match joué).

| Colonne | Type | Description |
|---------|------|-------------|
| `match_id` | VARCHAR PK | ID unique du match |
| `start_time` | TIMESTAMP | Début du match (UTC) |
| `end_time` | TIMESTAMP | Fin du match (UTC), dérivé : start_time + time_played_seconds |
| `playlist_id` | VARCHAR | FK → playlists |
| `map_id` | VARCHAR | FK → maps |
| `game_variant_id` | VARCHAR | FK → game_modes |
| `playlist_name` | VARCHAR | Nom (dénormalisé) |
| `map_name` | VARCHAR | Nom (dénormalisé) |
| `game_variant_name` | VARCHAR | Nom (dénormalisé) |
| `outcome` | TINYINT | 1=Tie, 2=Win, 3=Loss, 4=NoFinish |
| `team_id` | TINYINT | ID de l'équipe |
| `kills` | SMALLINT | Nombre de kills |
| `deaths` | SMALLINT | Nombre de deaths |
| `assists` | SMALLINT | Nombre d'assists |
| `kda` | FLOAT | Ratio KDA |
| `accuracy` | FLOAT | Précision (%) |
| `headshot_kills` | SMALLINT | Kills en headshot |
| `max_killing_spree` | SMALLINT | Meilleure série |
| `time_played_seconds` | INTEGER | Temps joué (s) |
| `avg_life_seconds` | FLOAT | Durée vie moyenne |
| `my_team_score` | SMALLINT | Score équipe |
| `enemy_team_score` | SMALLINT | Score adversaire |
| `team_mmr` | FLOAT | MMR équipe |
| `enemy_mmr` | FLOAT | MMR adversaire |
| `session_id` | VARCHAR | ID session (nullable) |
| `performance_score` | FLOAT | Score perf (nullable) |
| `raw_json` | JSON | JSON brut API (archive) |

**Index** :
```sql
CREATE INDEX idx_match_stats_time ON match_stats(start_time);
CREATE INDEX idx_match_stats_playlist ON match_stats(playlist_id);
CREATE INDEX idx_match_stats_outcome ON match_stats(outcome);
```

### Table `medals_earned`

Médailles obtenues par match.

| Colonne | Type | Description |
|---------|------|-------------|
| `match_id` | VARCHAR | FK → match_stats |
| `medal_name_id` | INTEGER | FK → medal_definitions |
| `count` | SMALLINT | Nombre d'occurrences |
| PRIMARY KEY | | (match_id, medal_name_id) |

### Table `teammates_aggregate`

Statistiques agrégées des coéquipiers.

| Colonne | Type | Description |
|---------|------|-------------|
| `teammate_xuid` | VARCHAR PK | XUID du coéquipier |
| `teammate_gamertag` | VARCHAR | Gamertag |
| `matches_together` | INTEGER | Nombre de matchs |
| `wins_together` | INTEGER | Victoires |
| `losses_together` | INTEGER | Défaites |
| `total_kills` | INTEGER | Total kills du coéquipier |
| `last_played_at` | TIMESTAMP | Dernier match ensemble |

### Table `antagonists` (NOUVELLE)

Top killers et victimes - rivalités.

| Colonne | Type | Description |
|---------|------|-------------|
| `opponent_xuid` | VARCHAR PK | XUID de l'opposant |
| `opponent_gamertag` | VARCHAR | Gamertag |
| `times_killed` | INTEGER | Fois où on l'a tué |
| `times_killed_by` | INTEGER | Fois où il nous a tué |
| `matches_against` | INTEGER | Matchs en opposition |
| `last_encounter` | TIMESTAMP | Dernier match |
| `net_kills` | INTEGER | (GENERATED: times_killed - times_killed_by) |

```sql
CREATE TABLE antagonists (
    opponent_xuid VARCHAR PRIMARY KEY,
    opponent_gamertag VARCHAR,
    times_killed INTEGER DEFAULT 0,
    times_killed_by INTEGER DEFAULT 0,
    matches_against INTEGER DEFAULT 0,
    last_encounter TIMESTAMP,
    net_kills INTEGER GENERATED ALWAYS AS (times_killed - times_killed_by)
);
```

### Table `weapon_stats` (NOUVELLE)

Statistiques par arme.

| Colonne | Type | Description |
|---------|------|-------------|
| `weapon_id` | VARCHAR PK | ID de l'arme |
| `weapon_name` | VARCHAR | Nom affiché |
| `total_kills` | INTEGER | Total kills avec cette arme |
| `total_deaths` | INTEGER | Total deaths par cette arme |
| `headshot_kills` | INTEGER | Headshots |
| `shots_fired` | INTEGER | Tirs effectués |
| `shots_hit` | INTEGER | Tirs touchés |
| `accuracy` | FLOAT | (GENERATED: shots_hit/shots_fired*100) |
| `headshot_rate` | FLOAT | (GENERATED: headshot_kills/total_kills*100) |

```sql
CREATE TABLE weapon_stats (
    weapon_id VARCHAR PRIMARY KEY,
    weapon_name VARCHAR,
    total_kills INTEGER DEFAULT 0,
    total_deaths INTEGER DEFAULT 0,
    headshot_kills INTEGER DEFAULT 0,
    shots_fired INTEGER DEFAULT 0,
    shots_hit INTEGER DEFAULT 0,
    accuracy FLOAT GENERATED ALWAYS AS (
        CASE WHEN shots_fired > 0 
        THEN shots_hit * 100.0 / shots_fired 
        ELSE 0 END
    ),
    headshot_rate FLOAT GENERATED ALWAYS AS (
        CASE WHEN total_kills > 0 
        THEN headshot_kills * 100.0 / total_kills 
        ELSE 0 END
    )
);
```

### Table `skill_history` (NOUVELLE)

Historique du CSR par playlist.

| Colonne | Type | Description |
|---------|------|-------------|
| `playlist_id` | VARCHAR | FK → playlists |
| `recorded_at` | TIMESTAMP | Date de l'enregistrement |
| `csr` | INTEGER | Competitive Skill Rank |
| `tier` | VARCHAR | Onyx, Diamond, Platinum, etc. |
| `division` | INTEGER | Division dans le tier |
| `matches_played` | INTEGER | Matchs joués à ce moment |
| PRIMARY KEY | | (playlist_id, recorded_at) |

### Table `sessions`

Sessions de jeu détectées.

| Colonne | Type | Description |
|---------|------|-------------|
| `session_id` | VARCHAR PK | ID unique |
| `start_time` | TIMESTAMP | Début de session |
| `end_time` | TIMESTAMP | Fin de session |
| `match_count` | INTEGER | Nombre de matchs |
| `total_kills` | INTEGER | Total kills |
| `total_deaths` | INTEGER | Total deaths |
| `total_assists` | INTEGER | Total assists |
| `avg_kda` | FLOAT | KDA moyen |
| `avg_accuracy` | FLOAT | Précision moyenne |
| `performance_score` | FLOAT | Score de performance |

---

## Requêtes DuckDB Exemples

### Jointure avec métadonnées

```sql
-- Attacher la base de métadonnées
ATTACH 'data/warehouse/metadata.duckdb' AS meta (READ_ONLY);

-- Top 10 médailles avec noms FR
SELECT 
    m.name_fr,
    SUM(e.count) as total
FROM medals_earned e
JOIN meta.medal_definitions m ON e.medal_name_id = m.name_id
GROUP BY m.name_fr
ORDER BY total DESC
LIMIT 10;
```

### Stats par playlist

```sql
ATTACH 'data/warehouse/metadata.duckdb' AS meta (READ_ONLY);

SELECT 
    p.public_name AS playlist,
    COUNT(*) AS matches,
    SUM(CASE WHEN s.outcome = 2 THEN 1 ELSE 0 END) AS wins,
    ROUND(AVG(s.kda), 2) AS avg_kda
FROM match_stats s
JOIN meta.playlists p ON s.playlist_id = p.asset_id
GROUP BY p.public_name
ORDER BY matches DESC;
```

### Progression CSR

```sql
SELECT 
    recorded_at,
    csr,
    tier || ' ' || division AS rank
FROM skill_history
WHERE playlist_id = 'edfef3ac-9cbe-4fa2-b949-8f29deafd483'
ORDER BY recorded_at;
```

### Top rivalités

```sql
SELECT 
    opponent_gamertag,
    times_killed,
    times_killed_by,
    net_kills,
    CASE WHEN net_kills > 0 THEN '🟢' ELSE '🔴' END AS status
FROM antagonists
ORDER BY ABS(net_kills) DESC
LIMIT 20;
```

### Export Parquet (backup)

```sql
-- Exporter les matchs vers Parquet
COPY match_stats TO 'data/archive/parquet/player_matches.parquet' (FORMAT PARQUET);

-- Importer depuis Parquet
INSERT INTO match_stats SELECT * FROM read_parquet('backup.parquet');
```

---

## Migration SQLite → DuckDB

Script de migration pour les données existantes :

```sql
-- Attacher l'ancienne base SQLite
ATTACH 'data/spnkr_gt_Chocoboflor.db' AS legacy (TYPE SQLITE, READ_ONLY);

-- Migrer les données
INSERT INTO match_stats 
SELECT 
    match_id,
    start_time,
    playlist_id,
    ...
FROM legacy.MatchCache;

-- Détacher
DETACH legacy;
```

---

## Conventions de Nommage

| Type | Convention | Exemple |
|------|------------|---------|
| Tables | snake_case | `match_stats` |
| Colonnes | snake_case | `start_time` |
| Index | idx_{table}_{column} | `idx_match_stats_time` |
| Clés primaires | Colonne simple ou composite | `match_id` ou `(playlist_id, recorded_at)` |

---

*Dernière mise à jour : 2026-02-01*
