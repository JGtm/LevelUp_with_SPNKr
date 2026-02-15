# Export des Schémas SQL — Baseline pré-v5

> Généré le 2026-02-14 17:33:51

---

## Sommaire

- metadata.duckdb
- JGtm
- Madina97294
- Chocoboflor
- XxDaemonGamerxX

---

## Metadata DB

### metadata.duckdb
⚠️ Base introuvable : C:\Users\Guillaume\Downloads\Scripts\Openspartan-graph\data\warehouse\metadata.duckdb


## Bases Joueurs

### Chocoboflor
- **Chemin** : `C:\Users\Guillaume\Downloads\Scripts\Openspartan-graph\data\players\Chocoboflor\stats.duckdb`
- **Taille** : 64.76 MB
- **Tables** : 21

#### `antagonists` (1 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `opponent_xuid` | `VARCHAR` | ✗ | - |
| `opponent_gamertag` | `VARCHAR` | ✓ | - |
| `times_killed` | `INTEGER` | ✓ | 0 |
| `times_killed_by` | `INTEGER` | ✓ | 0 |
| `matches_against` | `INTEGER` | ✓ | 0 |
| `last_encounter` | `TIMESTAMP` | ✓ | - |

#### `backfill_status` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `attempted_medals` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_events` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_skill` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_personal_scores` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_performance_scores` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_aliases` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_accuracy` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_shots` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_enemy_mmr` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_assets` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_scores` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_kda` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_shots` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_damage` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `last_attempt_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `career_progression` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `id` | `INTEGER` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `rank` | `INTEGER` | ✗ | - |
| `rank_name` | `VARCHAR` | ✓ | - |
| `rank_tier` | `VARCHAR` | ✓ | - |
| `current_xp` | `INTEGER` | ✓ | - |
| `xp_for_next_rank` | `INTEGER` | ✓ | - |
| `xp_total` | `INTEGER` | ✓ | - |
| `is_max_rank` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `adornment_path` | `VARCHAR` | ✓ | - |
| `recorded_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `highlight_events` (167858 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `id` | `INTEGER` | ✗ | nextval('highlight_events_id_seq') |
| `match_id` | `VARCHAR` | ✗ | - |
| `event_type` | `VARCHAR` | ✗ | - |
| `time_ms` | `INTEGER` | ✓ | - |
| `xuid` | `VARCHAR` | ✓ | - |
| `gamertag` | `VARCHAR` | ✓ | - |
| `type_hint` | `INTEGER` | ✓ | - |
| `raw_json` | `VARCHAR` | ✓ | - |

#### `killer_victim_pairs` (61362 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `killer_xuid` | `VARCHAR` | ✗ | - |
| `killer_gamertag` | `VARCHAR` | ✓ | - |
| `victim_xuid` | `VARCHAR` | ✗ | - |
| `victim_gamertag` | `VARCHAR` | ✓ | - |
| `kill_count` | `INTEGER` | ✓ | 1 |
| `time_ms` | `INTEGER` | ✓ | - |
| `is_validated` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `match_participants` (2049 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `team_id` | `INTEGER` | ✓ | - |
| `outcome` | `INTEGER` | ✓ | - |
| `gamertag` | `VARCHAR` | ✓ | - |
| `rank` | `SMALLINT` | ✓ | - |
| `score` | `INTEGER` | ✓ | - |
| `kills` | `SMALLINT` | ✓ | - |
| `deaths` | `SMALLINT` | ✓ | - |
| `assists` | `SMALLINT` | ✓ | - |
| `shots_fired` | `INTEGER` | ✓ | - |
| `shots_hit` | `INTEGER` | ✓ | - |
| `damage_dealt` | `FLOAT` | ✓ | - |
| `damage_taken` | `FLOAT` | ✓ | - |

#### `match_stats` (241 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `start_time` | `TIMESTAMP` | ✓ | - |
| `playlist_id` | `VARCHAR` | ✓ | - |
| `playlist_name` | `VARCHAR` | ✓ | - |
| `map_id` | `VARCHAR` | ✓ | - |
| `map_name` | `VARCHAR` | ✓ | - |
| `pair_id` | `VARCHAR` | ✓ | - |
| `pair_name` | `VARCHAR` | ✓ | - |
| `game_variant_id` | `VARCHAR` | ✓ | - |
| `game_variant_name` | `VARCHAR` | ✓ | - |
| `outcome` | `TINYINT` | ✓ | - |
| `team_id` | `TINYINT` | ✓ | - |
| `kills` | `SMALLINT` | ✓ | - |
| `deaths` | `SMALLINT` | ✓ | - |
| `assists` | `SMALLINT` | ✓ | - |
| `kda` | `FLOAT` | ✓ | - |
| `accuracy` | `FLOAT` | ✓ | - |
| `headshot_kills` | `SMALLINT` | ✓ | - |
| `max_killing_spree` | `SMALLINT` | ✓ | - |
| `time_played_seconds` | `INTEGER` | ✓ | - |
| `avg_life_seconds` | `FLOAT` | ✓ | - |
| `my_team_score` | `SMALLINT` | ✓ | - |
| `enemy_team_score` | `SMALLINT` | ✓ | - |
| `team_mmr` | `FLOAT` | ✓ | - |
| `enemy_mmr` | `FLOAT` | ✓ | - |
| `session_id` | `VARCHAR` | ✓ | - |
| `session_label` | `VARCHAR` | ✓ | - |
| `performance_score` | `FLOAT` | ✓ | - |
| `is_firefight` | `BOOLEAN` | ✓ | - |
| `teammates_signature` | `VARCHAR` | ✓ | - |
| `known_teammates_count` | `SMALLINT` | ✓ | - |
| `is_with_friends` | `BOOLEAN` | ✓ | - |
| `friends_xuids` | `VARCHAR` | ✓ | - |
| `created_at` | `TIMESTAMP` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |
| `rank` | `SMALLINT` | ✓ | - |
| `damage_dealt` | `FLOAT` | ✓ | - |
| `damage_taken` | `FLOAT` | ✓ | - |
| `shots_fired` | `INTEGER` | ✓ | - |
| `shots_hit` | `INTEGER` | ✓ | - |
| `grenade_kills` | `SMALLINT` | ✓ | - |
| `melee_kills` | `SMALLINT` | ✓ | - |
| `power_weapon_kills` | `SMALLINT` | ✓ | - |
| `score` | `INTEGER` | ✓ | - |
| `personal_score` | `INTEGER` | ✓ | - |
| `mode_category` | `VARCHAR` | ✓ | - |
| `is_ranked` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `left_early` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `end_time` | `TIMESTAMP` | ✓ | - |
| `backfill_completed` | `INTEGER` | ✓ | 0 |

#### `medals_earned` (502 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `medal_name_id` | `BIGINT` | ✗ | - |
| `count` | `SMALLINT` | ✓ | - |

#### `media_files` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `file_path` | `VARCHAR` | ✗ | - |
| `file_hash` | `VARCHAR` | ✗ | - |
| `file_name` | `VARCHAR` | ✗ | - |
| `file_size` | `BIGINT` | ✗ | - |
| `file_ext` | `VARCHAR` | ✗ | - |
| `kind` | `VARCHAR` | ✗ | - |
| `mtime` | `DOUBLE` | ✗ | - |
| `mtime_paris_epoch` | `DOUBLE` | ✗ | - |
| `thumbnail_path` | `VARCHAR` | ✓ | - |
| `thumbnail_generated_at` | `TIMESTAMP` | ✓ | - |
| `first_seen_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |
| `last_scan_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |
| `scan_version` | `INTEGER` | ✓ | 1 |
| `capture_start_utc` | `TIMESTAMP` | ✓ | - |
| `capture_end_utc` | `TIMESTAMP` | ✓ | - |
| `duration_seconds` | `DOUBLE` | ✓ | - |
| `title` | `VARCHAR` | ✓ | - |
| `status` | `VARCHAR` | ✓ | 'active' |

#### `media_match_associations` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `media_path` | `VARCHAR` | ✗ | - |
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `match_start_time` | `TIMESTAMP` | ✗ | - |
| `association_confidence` | `DOUBLE` | ✓ | 1.0 |
| `associated_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |
| `map_id` | `VARCHAR` | ✓ | - |
| `map_name` | `VARCHAR` | ✓ | - |

#### `mv_global_stats` (10 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `stat_key` | `VARCHAR` | ✗ | - |
| `stat_value` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_map_stats` (62 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `map_id` | `VARCHAR` | ✗ | - |
| `map_name` | `VARCHAR` | ✓ | - |
| `matches_played` | `INTEGER` | ✓ | - |
| `wins` | `INTEGER` | ✓ | - |
| `losses` | `INTEGER` | ✓ | - |
| `ties` | `INTEGER` | ✓ | - |
| `avg_kills` | `DOUBLE` | ✓ | - |
| `avg_deaths` | `DOUBLE` | ✓ | - |
| `avg_assists` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `avg_kda` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_mode_category_stats` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `mode_category` | `VARCHAR` | ✗ | - |
| `matches_played` | `INTEGER` | ✓ | - |
| `avg_kills` | `DOUBLE` | ✓ | - |
| `avg_deaths` | `DOUBLE` | ✓ | - |
| `avg_assists` | `DOUBLE` | ✓ | - |
| `avg_kda` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_session_stats` (214 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `session_id` | `INTEGER` | ✗ | - |
| `match_count` | `INTEGER` | ✓ | - |
| `start_time` | `TIMESTAMP` | ✓ | - |
| `end_time` | `TIMESTAMP` | ✓ | - |
| `total_kills` | `INTEGER` | ✓ | - |
| `total_deaths` | `INTEGER` | ✓ | - |
| `total_assists` | `INTEGER` | ✓ | - |
| `kd_ratio` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `avg_life_seconds` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `personal_score_awards` (2281 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `award_name` | `VARCHAR` | ✗ | - |
| `award_category` | `VARCHAR` | ✓ | - |
| `award_count` | `INTEGER` | ✓ | 1 |
| `award_score` | `INTEGER` | ✓ | 0 |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `player_match_stats` (241 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `team_id` | `TINYINT` | ✓ | - |
| `team_mmr` | `FLOAT` | ✓ | - |
| `enemy_mmr` | `FLOAT` | ✓ | - |
| `kills_expected` | `FLOAT` | ✓ | - |
| `kills_stddev` | `FLOAT` | ✓ | - |
| `deaths_expected` | `FLOAT` | ✓ | - |
| `deaths_stddev` | `FLOAT` | ✓ | - |
| `assists_expected` | `FLOAT` | ✓ | - |
| `assists_stddev` | `FLOAT` | ✓ | - |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `sessions` (214 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `session_id` | `VARCHAR` | ✗ | - |
| `start_time` | `TIMESTAMP` | ✓ | - |
| `end_time` | `TIMESTAMP` | ✓ | - |
| `match_count` | `INTEGER` | ✓ | - |
| `total_kills` | `INTEGER` | ✓ | - |
| `total_deaths` | `INTEGER` | ✓ | - |
| `total_assists` | `INTEGER` | ✓ | - |
| `avg_kda` | `FLOAT` | ✓ | - |
| `avg_accuracy` | `FLOAT` | ✓ | - |
| `performance_score` | `FLOAT` | ✓ | - |

#### `skill_history` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `playlist_id` | `VARCHAR` | ✗ | - |
| `recorded_at` | `TIMESTAMP` | ✗ | - |
| `csr` | `INTEGER` | ✓ | - |
| `tier` | `VARCHAR` | ✓ | - |
| `division` | `INTEGER` | ✓ | - |
| `matches_played` | `INTEGER` | ✓ | - |

#### `sync_meta` (3 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `key` | `VARCHAR` | ✗ | - |
| `value` | `VARCHAR` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `teammates_aggregate` (24 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `teammate_xuid` | `VARCHAR` | ✗ | - |
| `teammate_gamertag` | `VARCHAR` | ✓ | - |
| `matches_together` | `INTEGER` | ✓ | 0 |
| `same_team_count` | `INTEGER` | ✓ | 0 |
| `opposite_team_count` | `INTEGER` | ✓ | 0 |
| `wins_together` | `INTEGER` | ✓ | 0 |
| `losses_together` | `INTEGER` | ✓ | 0 |
| `first_played` | `TIMESTAMP` | ✓ | - |
| `last_played` | `TIMESTAMP` | ✓ | - |
| `computed_at` | `TIMESTAMP` | ✓ | - |

#### `xuid_aliases` (4875 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `xuid` | `VARCHAR` | ✗ | - |
| `gamertag` | `VARCHAR` | ✗ | - |
| `last_seen` | `TIMESTAMP` | ✓ | - |
| `source` | `VARCHAR` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### Index

| Nom | Table | Unique | SQL |
|-----|-------|--------|-----|
| `idx_aliases_gamertag` | `xuid_aliases` | ✗ | `CREATE INDEX idx_aliases_gamertag ON xuid_aliases(gamertag);` |
| `idx_assoc_match` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_match ON media_match_associations(match_id, xuid);` |
| `idx_assoc_media` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_media ON media_match_associations(media_path);` |
| `idx_assoc_time` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_time ON media_match_associations(match_start_time);` |
| `idx_assoc_xuid` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_xuid ON media_match_associations(xuid);` |
| `idx_career_date` | `career_progression` | ✗ | `CREATE INDEX idx_career_date ON career_progression(recorded_at);` |
| `idx_career_xuid` | `career_progression` | ✗ | `CREATE INDEX idx_career_xuid ON career_progression(xuid);` |
| `idx_highlight_match` | `highlight_events` | ✗ | `CREATE INDEX idx_highlight_match ON highlight_events(match_id);` |
| `idx_kv_killer` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_killer ON killer_victim_pairs(killer_xuid);` |
| `idx_kv_match` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_match ON killer_victim_pairs(match_id);` |
| `idx_kv_victim` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_victim ON killer_victim_pairs(victim_xuid);` |
| `idx_match_stats_outcome` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_outcome ON match_stats(outcome);` |
| `idx_match_stats_playlist` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_playlist ON match_stats(playlist_id);` |
| `idx_match_stats_session` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_session ON match_stats(session_id);` |
| `idx_match_stats_time` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_time ON match_stats(start_time);` |
| `idx_media_hash` | `media_files` | ✗ | `CREATE INDEX idx_media_hash ON media_files(file_hash);` |
| `idx_media_kind` | `media_files` | ✗ | `CREATE INDEX idx_media_kind ON media_files(kind);` |
| `idx_media_mtime` | `media_files` | ✗ | `CREATE INDEX idx_media_mtime ON media_files(mtime_paris_epoch);` |
| `idx_mp_team` | `match_participants` | ✗ | `CREATE INDEX idx_mp_team ON match_participants(match_id, team_id);` |
| `idx_mp_xuid` | `match_participants` | ✗ | `CREATE INDEX idx_mp_xuid ON match_participants(xuid);` |
| `idx_participants_team` | `match_participants` | ✗ | `CREATE INDEX idx_participants_team ON match_participants(match_id, team_id);` |
| `idx_participants_xuid` | `match_participants` | ✗ | `CREATE INDEX idx_participants_xuid ON match_participants(xuid);` |
| `idx_psa_category` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_category ON personal_score_awards(award_category);` |
| `idx_psa_match` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_match ON personal_score_awards(match_id);` |
| `idx_psa_xuid` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_xuid ON personal_score_awards(xuid);` |


### JGtm
- **Chemin** : `C:\Users\Guillaume\Downloads\Scripts\Openspartan-graph\data\players\JGtm\stats.duckdb`
- **Taille** : 73.76 MB
- **Tables** : 21

#### `antagonists` (58 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `opponent_xuid` | `VARCHAR` | ✗ | - |
| `opponent_gamertag` | `VARCHAR` | ✓ | - |
| `times_killed` | `INTEGER` | ✓ | 0 |
| `times_killed_by` | `INTEGER` | ✓ | 0 |
| `matches_against` | `INTEGER` | ✓ | 0 |
| `last_encounter` | `TIMESTAMP` | ✓ | - |

#### `backfill_status` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `attempted_medals` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_events` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_skill` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_personal_scores` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_performance_scores` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_aliases` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_accuracy` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_shots` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_enemy_mmr` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_assets` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_scores` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_kda` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_shots` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_damage` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `last_attempt_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `career_progression` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `id` | `INTEGER` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `rank` | `INTEGER` | ✗ | - |
| `rank_name` | `VARCHAR` | ✓ | - |
| `rank_tier` | `VARCHAR` | ✓ | - |
| `current_xp` | `INTEGER` | ✓ | - |
| `xp_for_next_rank` | `INTEGER` | ✓ | - |
| `xp_total` | `INTEGER` | ✓ | - |
| `is_max_rank` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `adornment_path` | `VARCHAR` | ✓ | - |
| `recorded_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `highlight_events` (170249 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `id` | `INTEGER` | ✗ | nextval('highlight_events_id_seq') |
| `match_id` | `VARCHAR` | ✗ | - |
| `event_type` | `VARCHAR` | ✗ | - |
| `time_ms` | `INTEGER` | ✓ | - |
| `xuid` | `VARCHAR` | ✓ | - |
| `gamertag` | `VARCHAR` | ✓ | - |
| `type_hint` | `INTEGER` | ✓ | - |
| `raw_json` | `VARCHAR` | ✓ | - |

#### `killer_victim_pairs` (60349 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `killer_xuid` | `VARCHAR` | ✗ | - |
| `killer_gamertag` | `VARCHAR` | ✓ | - |
| `victim_xuid` | `VARCHAR` | ✗ | - |
| `victim_gamertag` | `VARCHAR` | ✓ | - |
| `kill_count` | `INTEGER` | ✓ | 1 |
| `time_ms` | `INTEGER` | ✓ | - |
| `is_validated` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `match_participants` (4812 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `team_id` | `INTEGER` | ✓ | - |
| `outcome` | `INTEGER` | ✓ | - |
| `gamertag` | `VARCHAR` | ✓ | - |
| `rank` | `SMALLINT` | ✓ | - |
| `score` | `INTEGER` | ✓ | - |
| `kills` | `SMALLINT` | ✓ | - |
| `deaths` | `SMALLINT` | ✓ | - |
| `assists` | `SMALLINT` | ✓ | - |
| `shots_fired` | `INTEGER` | ✓ | - |
| `shots_hit` | `INTEGER` | ✓ | - |
| `damage_dealt` | `FLOAT` | ✓ | - |
| `damage_taken` | `FLOAT` | ✓ | - |

#### `match_stats` (518 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `start_time` | `TIMESTAMP` | ✓ | - |
| `playlist_id` | `VARCHAR` | ✓ | - |
| `playlist_name` | `VARCHAR` | ✓ | - |
| `map_id` | `VARCHAR` | ✓ | - |
| `map_name` | `VARCHAR` | ✓ | - |
| `pair_id` | `VARCHAR` | ✓ | - |
| `pair_name` | `VARCHAR` | ✓ | - |
| `game_variant_id` | `VARCHAR` | ✓ | - |
| `game_variant_name` | `VARCHAR` | ✓ | - |
| `outcome` | `TINYINT` | ✓ | - |
| `team_id` | `TINYINT` | ✓ | - |
| `kills` | `SMALLINT` | ✓ | - |
| `deaths` | `SMALLINT` | ✓ | - |
| `assists` | `SMALLINT` | ✓ | - |
| `kda` | `FLOAT` | ✓ | - |
| `accuracy` | `FLOAT` | ✓ | - |
| `headshot_kills` | `SMALLINT` | ✓ | - |
| `max_killing_spree` | `SMALLINT` | ✓ | - |
| `time_played_seconds` | `INTEGER` | ✓ | - |
| `avg_life_seconds` | `FLOAT` | ✓ | - |
| `my_team_score` | `SMALLINT` | ✓ | - |
| `enemy_team_score` | `SMALLINT` | ✓ | - |
| `team_mmr` | `FLOAT` | ✓ | - |
| `enemy_mmr` | `FLOAT` | ✓ | - |
| `session_id` | `VARCHAR` | ✓ | - |
| `session_label` | `VARCHAR` | ✓ | - |
| `performance_score` | `FLOAT` | ✓ | - |
| `is_firefight` | `BOOLEAN` | ✓ | - |
| `teammates_signature` | `VARCHAR` | ✓ | - |
| `known_teammates_count` | `SMALLINT` | ✓ | - |
| `is_with_friends` | `BOOLEAN` | ✓ | - |
| `friends_xuids` | `VARCHAR` | ✓ | - |
| `created_at` | `TIMESTAMP` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |
| `rank` | `SMALLINT` | ✓ | - |
| `damage_dealt` | `FLOAT` | ✓ | - |
| `damage_taken` | `FLOAT` | ✓ | - |
| `shots_fired` | `INTEGER` | ✓ | - |
| `shots_hit` | `INTEGER` | ✓ | - |
| `grenade_kills` | `SMALLINT` | ✓ | - |
| `melee_kills` | `SMALLINT` | ✓ | - |
| `power_weapon_kills` | `SMALLINT` | ✓ | - |
| `score` | `INTEGER` | ✓ | - |
| `personal_score` | `INTEGER` | ✓ | - |
| `mode_category` | `VARCHAR` | ✓ | - |
| `is_ranked` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `left_early` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `end_time` | `TIMESTAMP` | ✓ | - |
| `backfill_completed` | `INTEGER` | ✓ | 0 |

#### `medals_earned` (1584 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `medal_name_id` | `BIGINT` | ✗ | - |
| `count` | `SMALLINT` | ✓ | - |

#### `media_files` (41 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `file_path` | `VARCHAR` | ✗ | - |
| `file_hash` | `VARCHAR` | ✗ | - |
| `file_name` | `VARCHAR` | ✗ | - |
| `file_size` | `BIGINT` | ✗ | - |
| `file_ext` | `VARCHAR` | ✗ | - |
| `kind` | `VARCHAR` | ✗ | - |
| `mtime` | `DOUBLE` | ✗ | - |
| `mtime_paris_epoch` | `DOUBLE` | ✗ | - |
| `thumbnail_path` | `VARCHAR` | ✓ | - |
| `thumbnail_generated_at` | `TIMESTAMP` | ✓ | - |
| `first_seen_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |
| `last_scan_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |
| `scan_version` | `INTEGER` | ✓ | 1 |
| `capture_start_utc` | `TIMESTAMP` | ✓ | - |
| `capture_end_utc` | `TIMESTAMP` | ✓ | - |
| `duration_seconds` | `DOUBLE` | ✓ | - |
| `title` | `VARCHAR` | ✓ | - |
| `status` | `VARCHAR` | ✓ | 'active' |

#### `media_match_associations` (40 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `media_path` | `VARCHAR` | ✗ | - |
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `match_start_time` | `TIMESTAMP` | ✗ | - |
| `association_confidence` | `DOUBLE` | ✓ | 1.0 |
| `associated_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |
| `map_id` | `VARCHAR` | ✓ | - |
| `map_name` | `VARCHAR` | ✓ | - |

#### `mv_global_stats` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `stat_key` | `VARCHAR` | ✗ | - |
| `stat_value` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_map_stats` (75 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `map_id` | `VARCHAR` | ✗ | - |
| `map_name` | `VARCHAR` | ✓ | - |
| `matches_played` | `INTEGER` | ✓ | - |
| `wins` | `INTEGER` | ✓ | - |
| `losses` | `INTEGER` | ✓ | - |
| `ties` | `INTEGER` | ✓ | - |
| `avg_kills` | `DOUBLE` | ✓ | - |
| `avg_deaths` | `DOUBLE` | ✓ | - |
| `avg_assists` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `avg_kda` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_mode_category_stats` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `mode_category` | `VARCHAR` | ✗ | - |
| `matches_played` | `INTEGER` | ✓ | - |
| `avg_kills` | `DOUBLE` | ✓ | - |
| `avg_deaths` | `DOUBLE` | ✓ | - |
| `avg_assists` | `DOUBLE` | ✓ | - |
| `avg_kda` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_session_stats` (431 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `session_id` | `INTEGER` | ✗ | - |
| `match_count` | `INTEGER` | ✓ | - |
| `start_time` | `TIMESTAMP` | ✓ | - |
| `end_time` | `TIMESTAMP` | ✓ | - |
| `total_kills` | `INTEGER` | ✓ | - |
| `total_deaths` | `INTEGER` | ✓ | - |
| `total_assists` | `INTEGER` | ✓ | - |
| `kd_ratio` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `avg_life_seconds` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `personal_score_awards` (3018 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `award_name` | `VARCHAR` | ✗ | - |
| `award_category` | `VARCHAR` | ✓ | - |
| `award_count` | `INTEGER` | ✓ | 1 |
| `award_score` | `INTEGER` | ✓ | 0 |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `player_match_stats` (516 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `team_id` | `TINYINT` | ✓ | - |
| `team_mmr` | `FLOAT` | ✓ | - |
| `enemy_mmr` | `FLOAT` | ✓ | - |
| `kills_expected` | `FLOAT` | ✓ | - |
| `kills_stddev` | `FLOAT` | ✓ | - |
| `deaths_expected` | `FLOAT` | ✓ | - |
| `deaths_stddev` | `FLOAT` | ✓ | - |
| `assists_expected` | `FLOAT` | ✓ | - |
| `assists_stddev` | `FLOAT` | ✓ | - |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `sessions` (431 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `session_id` | `VARCHAR` | ✗ | - |
| `start_time` | `TIMESTAMP` | ✓ | - |
| `end_time` | `TIMESTAMP` | ✓ | - |
| `match_count` | `INTEGER` | ✓ | - |
| `total_kills` | `INTEGER` | ✓ | - |
| `total_deaths` | `INTEGER` | ✓ | - |
| `total_assists` | `INTEGER` | ✓ | - |
| `avg_kda` | `FLOAT` | ✓ | - |
| `avg_accuracy` | `FLOAT` | ✓ | - |
| `performance_score` | `FLOAT` | ✓ | - |

#### `skill_history` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `playlist_id` | `VARCHAR` | ✗ | - |
| `recorded_at` | `TIMESTAMP` | ✗ | - |
| `csr` | `INTEGER` | ✓ | - |
| `tier` | `VARCHAR` | ✓ | - |
| `division` | `INTEGER` | ✓ | - |
| `matches_played` | `INTEGER` | ✓ | - |

#### `sync_meta` (3 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `key` | `VARCHAR` | ✗ | - |
| `value` | `VARCHAR` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `teammates_aggregate` (853 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `teammate_xuid` | `VARCHAR` | ✗ | - |
| `teammate_gamertag` | `VARCHAR` | ✓ | - |
| `matches_together` | `INTEGER` | ✓ | 0 |
| `same_team_count` | `INTEGER` | ✓ | 0 |
| `opposite_team_count` | `INTEGER` | ✓ | 0 |
| `wins_together` | `INTEGER` | ✓ | 0 |
| `losses_together` | `INTEGER` | ✓ | 0 |
| `first_played` | `TIMESTAMP` | ✓ | - |
| `last_played` | `TIMESTAMP` | ✓ | - |
| `computed_at` | `TIMESTAMP` | ✓ | - |

#### `xuid_aliases` (5094 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `xuid` | `VARCHAR` | ✗ | - |
| `gamertag` | `VARCHAR` | ✗ | - |
| `last_seen` | `TIMESTAMP` | ✓ | - |
| `source` | `VARCHAR` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### Index

| Nom | Table | Unique | SQL |
|-----|-------|--------|-----|
| `idx_aliases_gamertag` | `xuid_aliases` | ✗ | `CREATE INDEX idx_aliases_gamertag ON xuid_aliases(gamertag);` |
| `idx_assoc_match` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_match ON media_match_associations(match_id, xuid);` |
| `idx_assoc_media` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_media ON media_match_associations(media_path);` |
| `idx_assoc_time` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_time ON media_match_associations(match_start_time);` |
| `idx_assoc_xuid` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_xuid ON media_match_associations(xuid);` |
| `idx_career_date` | `career_progression` | ✗ | `CREATE INDEX idx_career_date ON career_progression(recorded_at);` |
| `idx_career_xuid` | `career_progression` | ✗ | `CREATE INDEX idx_career_xuid ON career_progression(xuid);` |
| `idx_highlight_match` | `highlight_events` | ✗ | `CREATE INDEX idx_highlight_match ON highlight_events(match_id);` |
| `idx_kv_killer` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_killer ON killer_victim_pairs(killer_xuid);` |
| `idx_kv_match` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_match ON killer_victim_pairs(match_id);` |
| `idx_kv_victim` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_victim ON killer_victim_pairs(victim_xuid);` |
| `idx_match_stats_outcome` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_outcome ON match_stats(outcome);` |
| `idx_match_stats_playlist` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_playlist ON match_stats(playlist_id);` |
| `idx_match_stats_session` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_session ON match_stats(session_id);` |
| `idx_match_stats_time` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_time ON match_stats(start_time);` |
| `idx_media_hash` | `media_files` | ✗ | `CREATE INDEX idx_media_hash ON media_files(file_hash);` |
| `idx_media_kind` | `media_files` | ✗ | `CREATE INDEX idx_media_kind ON media_files(kind);` |
| `idx_media_mtime` | `media_files` | ✗ | `CREATE INDEX idx_media_mtime ON media_files(mtime_paris_epoch);` |
| `idx_mp_team` | `match_participants` | ✗ | `CREATE INDEX idx_mp_team ON match_participants(match_id, team_id);` |
| `idx_mp_xuid` | `match_participants` | ✗ | `CREATE INDEX idx_mp_xuid ON match_participants(xuid);` |
| `idx_participants_team` | `match_participants` | ✗ | `CREATE INDEX idx_participants_team ON match_participants(match_id, team_id);` |
| `idx_participants_xuid` | `match_participants` | ✗ | `CREATE INDEX idx_participants_xuid ON match_participants(xuid);` |
| `idx_psa_category` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_category ON personal_score_awards(award_category);` |
| `idx_psa_match` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_match ON personal_score_awards(match_id);` |
| `idx_psa_xuid` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_xuid ON personal_score_awards(xuid);` |


### Madina97294
- **Chemin** : `C:\Users\Guillaume\Downloads\Scripts\Openspartan-graph\data\players\Madina97294\stats.duckdb`
- **Taille** : 115.76 MB
- **Tables** : 21

#### `antagonists` (40 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `opponent_xuid` | `VARCHAR` | ✗ | - |
| `opponent_gamertag` | `VARCHAR` | ✓ | - |
| `times_killed` | `INTEGER` | ✓ | 0 |
| `times_killed_by` | `INTEGER` | ✓ | 0 |
| `matches_against` | `INTEGER` | ✓ | 0 |
| `last_encounter` | `TIMESTAMP` | ✓ | - |

#### `backfill_status` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `attempted_medals` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_events` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_skill` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_personal_scores` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_performance_scores` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_aliases` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_accuracy` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_shots` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_enemy_mmr` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_assets` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_scores` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_kda` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_shots` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `attempted_participants_damage` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `last_attempt_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `career_progression` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `id` | `INTEGER` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `rank` | `INTEGER` | ✗ | - |
| `rank_name` | `VARCHAR` | ✓ | - |
| `rank_tier` | `VARCHAR` | ✓ | - |
| `current_xp` | `INTEGER` | ✓ | - |
| `xp_for_next_rank` | `INTEGER` | ✓ | - |
| `xp_total` | `INTEGER` | ✓ | - |
| `is_max_rank` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `adornment_path` | `VARCHAR` | ✓ | - |
| `recorded_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `highlight_events` (374461 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `id` | `INTEGER` | ✗ | nextval('highlight_events_id_seq') |
| `match_id` | `VARCHAR` | ✗ | - |
| `event_type` | `VARCHAR` | ✗ | - |
| `time_ms` | `INTEGER` | ✓ | - |
| `xuid` | `VARCHAR` | ✓ | - |
| `gamertag` | `VARCHAR` | ✓ | - |
| `type_hint` | `INTEGER` | ✓ | - |
| `raw_json` | `VARCHAR` | ✓ | - |

#### `killer_victim_pairs` (137978 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `killer_xuid` | `VARCHAR` | ✗ | - |
| `killer_gamertag` | `VARCHAR` | ✓ | - |
| `victim_xuid` | `VARCHAR` | ✗ | - |
| `victim_gamertag` | `VARCHAR` | ✓ | - |
| `kill_count` | `INTEGER` | ✓ | 1 |
| `time_ms` | `INTEGER` | ✓ | - |
| `is_validated` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `match_participants` (18999 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `team_id` | `INTEGER` | ✓ | - |
| `outcome` | `INTEGER` | ✓ | - |
| `gamertag` | `VARCHAR` | ✓ | - |
| `rank` | `SMALLINT` | ✓ | - |
| `score` | `INTEGER` | ✓ | - |
| `kills` | `SMALLINT` | ✓ | - |
| `deaths` | `SMALLINT` | ✓ | - |
| `assists` | `SMALLINT` | ✓ | - |
| `shots_fired` | `INTEGER` | ✓ | - |
| `shots_hit` | `INTEGER` | ✓ | - |
| `damage_dealt` | `FLOAT` | ✓ | - |
| `damage_taken` | `FLOAT` | ✓ | - |

#### `match_stats` (971 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `start_time` | `TIMESTAMP` | ✓ | - |
| `playlist_id` | `VARCHAR` | ✓ | - |
| `playlist_name` | `VARCHAR` | ✓ | - |
| `map_id` | `VARCHAR` | ✓ | - |
| `map_name` | `VARCHAR` | ✓ | - |
| `pair_id` | `VARCHAR` | ✓ | - |
| `pair_name` | `VARCHAR` | ✓ | - |
| `game_variant_id` | `VARCHAR` | ✓ | - |
| `game_variant_name` | `VARCHAR` | ✓ | - |
| `outcome` | `TINYINT` | ✓ | - |
| `team_id` | `TINYINT` | ✓ | - |
| `kills` | `SMALLINT` | ✓ | - |
| `deaths` | `SMALLINT` | ✓ | - |
| `assists` | `SMALLINT` | ✓ | - |
| `kda` | `FLOAT` | ✓ | - |
| `accuracy` | `FLOAT` | ✓ | - |
| `headshot_kills` | `SMALLINT` | ✓ | - |
| `max_killing_spree` | `SMALLINT` | ✓ | - |
| `time_played_seconds` | `INTEGER` | ✓ | - |
| `avg_life_seconds` | `FLOAT` | ✓ | - |
| `my_team_score` | `SMALLINT` | ✓ | - |
| `enemy_team_score` | `SMALLINT` | ✓ | - |
| `team_mmr` | `FLOAT` | ✓ | - |
| `enemy_mmr` | `FLOAT` | ✓ | - |
| `session_id` | `VARCHAR` | ✓ | - |
| `session_label` | `VARCHAR` | ✓ | - |
| `performance_score` | `FLOAT` | ✓ | - |
| `is_firefight` | `BOOLEAN` | ✓ | - |
| `teammates_signature` | `VARCHAR` | ✓ | - |
| `known_teammates_count` | `SMALLINT` | ✓ | - |
| `is_with_friends` | `BOOLEAN` | ✓ | - |
| `friends_xuids` | `VARCHAR` | ✓ | - |
| `created_at` | `TIMESTAMP` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |
| `rank` | `SMALLINT` | ✓ | - |
| `damage_dealt` | `FLOAT` | ✓ | - |
| `damage_taken` | `FLOAT` | ✓ | - |
| `shots_fired` | `INTEGER` | ✓ | - |
| `shots_hit` | `INTEGER` | ✓ | - |
| `grenade_kills` | `SMALLINT` | ✓ | - |
| `melee_kills` | `SMALLINT` | ✓ | - |
| `power_weapon_kills` | `SMALLINT` | ✓ | - |
| `score` | `INTEGER` | ✓ | - |
| `personal_score` | `INTEGER` | ✓ | - |
| `mode_category` | `VARCHAR` | ✓ | - |
| `is_ranked` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `left_early` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `end_time` | `TIMESTAMP` | ✓ | - |
| `backfill_completed` | `INTEGER` | ✓ | 0 |

#### `medals_earned` (5056 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `medal_name_id` | `BIGINT` | ✗ | - |
| `count` | `SMALLINT` | ✓ | - |

#### `media_files` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `file_path` | `VARCHAR` | ✗ | - |
| `file_hash` | `VARCHAR` | ✗ | - |
| `file_name` | `VARCHAR` | ✗ | - |
| `file_size` | `BIGINT` | ✗ | - |
| `file_ext` | `VARCHAR` | ✗ | - |
| `kind` | `VARCHAR` | ✗ | - |
| `owner_xuid` | `VARCHAR` | ✗ | - |
| `mtime` | `DOUBLE` | ✗ | - |
| `mtime_paris_epoch` | `DOUBLE` | ✗ | - |
| `thumbnail_path` | `VARCHAR` | ✓ | - |
| `thumbnail_generated_at` | `TIMESTAMP` | ✓ | - |
| `first_seen_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |
| `last_scan_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |
| `scan_version` | `INTEGER` | ✓ | 1 |
| `capture_start_utc` | `TIMESTAMP` | ✓ | - |
| `capture_end_utc` | `TIMESTAMP` | ✓ | - |
| `duration_seconds` | `DOUBLE` | ✓ | - |
| `title` | `VARCHAR` | ✓ | - |
| `status` | `VARCHAR` | ✓ | 'active' |

#### `media_match_associations` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `media_path` | `VARCHAR` | ✗ | - |
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `match_start_time` | `TIMESTAMP` | ✗ | - |
| `association_confidence` | `DOUBLE` | ✓ | 1.0 |
| `associated_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |
| `map_id` | `VARCHAR` | ✓ | - |
| `map_name` | `VARCHAR` | ✓ | - |

#### `mv_global_stats` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `stat_key` | `VARCHAR` | ✗ | - |
| `stat_value` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_map_stats` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `map_id` | `VARCHAR` | ✗ | - |
| `map_name` | `VARCHAR` | ✓ | - |
| `matches_played` | `INTEGER` | ✓ | - |
| `wins` | `INTEGER` | ✓ | - |
| `losses` | `INTEGER` | ✓ | - |
| `ties` | `INTEGER` | ✓ | - |
| `avg_kills` | `DOUBLE` | ✓ | - |
| `avg_deaths` | `DOUBLE` | ✓ | - |
| `avg_assists` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `avg_kda` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_mode_category_stats` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `mode_category` | `VARCHAR` | ✗ | - |
| `matches_played` | `INTEGER` | ✓ | - |
| `avg_kills` | `DOUBLE` | ✓ | - |
| `avg_deaths` | `DOUBLE` | ✓ | - |
| `avg_assists` | `DOUBLE` | ✓ | - |
| `avg_kda` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_session_stats` (934 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `session_id` | `VARCHAR` | ✗ | - |
| `match_count` | `INTEGER` | ✓ | - |
| `start_time` | `TIMESTAMP` | ✓ | - |
| `end_time` | `TIMESTAMP` | ✓ | - |
| `total_kills` | `INTEGER` | ✓ | - |
| `total_deaths` | `INTEGER` | ✓ | - |
| `total_assists` | `INTEGER` | ✓ | - |
| `kd_ratio` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `avg_life_seconds` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `personal_score_awards` (5506 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `award_name` | `VARCHAR` | ✗ | - |
| `award_category` | `VARCHAR` | ✓ | - |
| `award_count` | `INTEGER` | ✓ | 1 |
| `award_score` | `INTEGER` | ✓ | 0 |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `player_match_stats` (962 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `team_id` | `TINYINT` | ✓ | - |
| `team_mmr` | `FLOAT` | ✓ | - |
| `enemy_mmr` | `FLOAT` | ✓ | - |
| `kills_expected` | `FLOAT` | ✓ | - |
| `kills_stddev` | `FLOAT` | ✓ | - |
| `deaths_expected` | `FLOAT` | ✓ | - |
| `deaths_stddev` | `FLOAT` | ✓ | - |
| `assists_expected` | `FLOAT` | ✓ | - |
| `assists_stddev` | `FLOAT` | ✓ | - |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `sessions` (934 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `session_id` | `VARCHAR` | ✗ | - |
| `start_time` | `TIMESTAMP` | ✓ | - |
| `end_time` | `TIMESTAMP` | ✓ | - |
| `match_count` | `INTEGER` | ✓ | - |
| `total_kills` | `INTEGER` | ✓ | - |
| `total_deaths` | `INTEGER` | ✓ | - |
| `total_assists` | `INTEGER` | ✓ | - |
| `avg_kda` | `FLOAT` | ✓ | - |
| `avg_accuracy` | `FLOAT` | ✓ | - |
| `performance_score` | `FLOAT` | ✓ | - |

#### `skill_history` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `playlist_id` | `VARCHAR` | ✗ | - |
| `recorded_at` | `TIMESTAMP` | ✗ | - |
| `csr` | `INTEGER` | ✓ | - |
| `tier` | `VARCHAR` | ✓ | - |
| `division` | `INTEGER` | ✓ | - |
| `matches_played` | `INTEGER` | ✓ | - |

#### `sync_meta` (3 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `key` | `VARCHAR` | ✗ | - |
| `value` | `VARCHAR` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `teammates_aggregate` (6472 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `teammate_xuid` | `VARCHAR` | ✗ | - |
| `teammate_gamertag` | `VARCHAR` | ✓ | - |
| `matches_together` | `INTEGER` | ✓ | 0 |
| `same_team_count` | `INTEGER` | ✓ | 0 |
| `opposite_team_count` | `INTEGER` | ✓ | 0 |
| `wins_together` | `INTEGER` | ✓ | 0 |
| `losses_together` | `INTEGER` | ✓ | 0 |
| `first_played` | `TIMESTAMP` | ✓ | - |
| `last_played` | `TIMESTAMP` | ✓ | - |
| `computed_at` | `TIMESTAMP` | ✓ | - |

#### `xuid_aliases` (13701 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `xuid` | `VARCHAR` | ✗ | - |
| `gamertag` | `VARCHAR` | ✗ | - |
| `last_seen` | `TIMESTAMP` | ✓ | - |
| `source` | `VARCHAR` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### Index

| Nom | Table | Unique | SQL |
|-----|-------|--------|-----|
| `idx_aliases_gamertag` | `xuid_aliases` | ✗ | `CREATE INDEX idx_aliases_gamertag ON xuid_aliases(gamertag);` |
| `idx_assoc_match` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_match ON media_match_associations(match_id, xuid);` |
| `idx_assoc_media` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_media ON media_match_associations(media_path);` |
| `idx_assoc_time` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_time ON media_match_associations(match_start_time);` |
| `idx_assoc_xuid` | `media_match_associations` | ✗ | `CREATE INDEX idx_assoc_xuid ON media_match_associations(xuid);` |
| `idx_career_date` | `career_progression` | ✗ | `CREATE INDEX idx_career_date ON career_progression(recorded_at);` |
| `idx_career_xuid` | `career_progression` | ✗ | `CREATE INDEX idx_career_xuid ON career_progression(xuid);` |
| `idx_highlight_match` | `highlight_events` | ✗ | `CREATE INDEX idx_highlight_match ON highlight_events(match_id);` |
| `idx_kv_killer` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_killer ON killer_victim_pairs(killer_xuid);` |
| `idx_kv_match` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_match ON killer_victim_pairs(match_id);` |
| `idx_kv_victim` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_victim ON killer_victim_pairs(victim_xuid);` |
| `idx_match_stats_outcome` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_outcome ON match_stats(outcome);` |
| `idx_match_stats_playlist` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_playlist ON match_stats(playlist_id);` |
| `idx_match_stats_session` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_session ON match_stats(session_id);` |
| `idx_match_stats_time` | `match_stats` | ✗ | `CREATE INDEX idx_match_stats_time ON match_stats(start_time);` |
| `idx_media_hash` | `media_files` | ✗ | `CREATE INDEX idx_media_hash ON media_files(file_hash);` |
| `idx_media_kind` | `media_files` | ✗ | `CREATE INDEX idx_media_kind ON media_files(kind);` |
| `idx_media_mtime` | `media_files` | ✗ | `CREATE INDEX idx_media_mtime ON media_files(mtime_paris_epoch);` |
| `idx_media_owner` | `media_files` | ✗ | `CREATE INDEX idx_media_owner ON media_files(owner_xuid);` |
| `idx_mp_team` | `match_participants` | ✗ | `CREATE INDEX idx_mp_team ON match_participants(match_id, team_id);` |
| `idx_mp_xuid` | `match_participants` | ✗ | `CREATE INDEX idx_mp_xuid ON match_participants(xuid);` |
| `idx_participants_team` | `match_participants` | ✗ | `CREATE INDEX idx_participants_team ON match_participants(match_id, team_id);` |
| `idx_participants_xuid` | `match_participants` | ✗ | `CREATE INDEX idx_participants_xuid ON match_participants(xuid);` |
| `idx_psa_category` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_category ON personal_score_awards(award_category);` |
| `idx_psa_match` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_match ON personal_score_awards(match_id);` |
| `idx_psa_xuid` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_xuid ON personal_score_awards(xuid);` |


### XxDaemonGamerxX
- **Chemin** : `C:\Users\Guillaume\Downloads\Scripts\Openspartan-graph\data\players\XxDaemonGamerxX\stats.duckdb`
- **Taille** : 8.01 MB
- **Tables** : 14

#### `career_progression` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `id` | `INTEGER` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `rank` | `INTEGER` | ✗ | - |
| `rank_name` | `VARCHAR` | ✓ | - |
| `rank_tier` | `VARCHAR` | ✓ | - |
| `current_xp` | `INTEGER` | ✓ | - |
| `xp_for_next_rank` | `INTEGER` | ✓ | - |
| `xp_total` | `INTEGER` | ✓ | - |
| `is_max_rank` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `adornment_path` | `VARCHAR` | ✓ | - |
| `recorded_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `highlight_events` (3784 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `id` | `INTEGER` | ✗ | nextval('highlight_events_id_seq') |
| `match_id` | `VARCHAR` | ✗ | - |
| `event_type` | `VARCHAR` | ✗ | - |
| `time_ms` | `INTEGER` | ✓ | - |
| `xuid` | `VARCHAR` | ✓ | - |
| `gamertag` | `VARCHAR` | ✓ | - |
| `type_hint` | `INTEGER` | ✓ | - |
| `raw_json` | `VARCHAR` | ✓ | - |

#### `killer_victim_pairs` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `id` | `INTEGER` | ✗ | - |
| `match_id` | `VARCHAR` | ✗ | - |
| `killer_xuid` | `VARCHAR` | ✗ | - |
| `killer_gamertag` | `VARCHAR` | ✓ | - |
| `victim_xuid` | `VARCHAR` | ✗ | - |
| `victim_gamertag` | `VARCHAR` | ✓ | - |
| `kill_count` | `INTEGER` | ✓ | 1 |
| `time_ms` | `INTEGER` | ✓ | - |
| `is_validated` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `match_participants` (151 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `team_id` | `INTEGER` | ✓ | - |
| `outcome` | `INTEGER` | ✓ | - |
| `gamertag` | `VARCHAR` | ✓ | - |
| `rank` | `SMALLINT` | ✓ | - |
| `score` | `INTEGER` | ✓ | - |
| `kills` | `SMALLINT` | ✓ | - |
| `deaths` | `SMALLINT` | ✓ | - |
| `assists` | `SMALLINT` | ✓ | - |
| `shots_fired` | `INTEGER` | ✓ | - |
| `shots_hit` | `INTEGER` | ✓ | - |
| `damage_dealt` | `FLOAT` | ✓ | - |
| `damage_taken` | `FLOAT` | ✓ | - |

#### `match_stats` (18 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `start_time` | `TIMESTAMP` | ✓ | - |
| `end_time` | `TIMESTAMP` | ✓ | - |
| `playlist_id` | `VARCHAR` | ✓ | - |
| `playlist_name` | `VARCHAR` | ✓ | - |
| `map_id` | `VARCHAR` | ✓ | - |
| `map_name` | `VARCHAR` | ✓ | - |
| `pair_id` | `VARCHAR` | ✓ | - |
| `pair_name` | `VARCHAR` | ✓ | - |
| `game_variant_id` | `VARCHAR` | ✓ | - |
| `game_variant_name` | `VARCHAR` | ✓ | - |
| `outcome` | `TINYINT` | ✓ | - |
| `team_id` | `TINYINT` | ✓ | - |
| `rank` | `SMALLINT` | ✓ | - |
| `kills` | `SMALLINT` | ✓ | - |
| `deaths` | `SMALLINT` | ✓ | - |
| `assists` | `SMALLINT` | ✓ | - |
| `kda` | `FLOAT` | ✓ | - |
| `accuracy` | `FLOAT` | ✓ | - |
| `headshot_kills` | `SMALLINT` | ✓ | - |
| `max_killing_spree` | `SMALLINT` | ✓ | - |
| `time_played_seconds` | `INTEGER` | ✓ | - |
| `avg_life_seconds` | `FLOAT` | ✓ | - |
| `my_team_score` | `SMALLINT` | ✓ | - |
| `enemy_team_score` | `SMALLINT` | ✓ | - |
| `team_mmr` | `FLOAT` | ✓ | - |
| `enemy_mmr` | `FLOAT` | ✓ | - |
| `damage_dealt` | `FLOAT` | ✓ | - |
| `damage_taken` | `FLOAT` | ✓ | - |
| `shots_fired` | `INTEGER` | ✓ | - |
| `shots_hit` | `INTEGER` | ✓ | - |
| `grenade_kills` | `SMALLINT` | ✓ | - |
| `melee_kills` | `SMALLINT` | ✓ | - |
| `power_weapon_kills` | `SMALLINT` | ✓ | - |
| `score` | `INTEGER` | ✓ | - |
| `personal_score` | `INTEGER` | ✓ | - |
| `mode_category` | `VARCHAR` | ✓ | - |
| `is_ranked` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `is_firefight` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `left_early` | `BOOLEAN` | ✓ | CAST('f' AS BOOLEAN) |
| `session_id` | `VARCHAR` | ✓ | - |
| `session_label` | `VARCHAR` | ✓ | - |
| `performance_score` | `FLOAT` | ✓ | - |
| `teammates_signature` | `VARCHAR` | ✓ | - |
| `known_teammates_count` | `SMALLINT` | ✓ | - |
| `is_with_friends` | `BOOLEAN` | ✓ | - |
| `friends_xuids` | `VARCHAR` | ✓ | - |
| `created_at` | `TIMESTAMP` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |
| `backfill_completed` | `INTEGER` | ✓ | 0 |

#### `medals_earned` (20 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `medal_name_id` | `BIGINT` | ✗ | - |
| `count` | `SMALLINT` | ✓ | - |

#### `mv_global_stats` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `stat_key` | `VARCHAR` | ✗ | - |
| `stat_value` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_map_stats` (16 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `map_id` | `VARCHAR` | ✗ | - |
| `map_name` | `VARCHAR` | ✓ | - |
| `matches_played` | `INTEGER` | ✓ | - |
| `wins` | `INTEGER` | ✓ | - |
| `losses` | `INTEGER` | ✓ | - |
| `ties` | `INTEGER` | ✓ | - |
| `avg_kills` | `DOUBLE` | ✓ | - |
| `avg_deaths` | `DOUBLE` | ✓ | - |
| `avg_assists` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `avg_kda` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_mode_category_stats` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `mode_category` | `VARCHAR` | ✗ | - |
| `matches_played` | `INTEGER` | ✓ | - |
| `avg_kills` | `DOUBLE` | ✓ | - |
| `avg_deaths` | `DOUBLE` | ✓ | - |
| `avg_assists` | `DOUBLE` | ✓ | - |
| `avg_kda` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `mv_session_stats` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `session_id` | `INTEGER` | ✗ | - |
| `match_count` | `INTEGER` | ✓ | - |
| `start_time` | `TIMESTAMP` | ✓ | - |
| `end_time` | `TIMESTAMP` | ✓ | - |
| `total_kills` | `INTEGER` | ✓ | - |
| `total_deaths` | `INTEGER` | ✓ | - |
| `total_assists` | `INTEGER` | ✓ | - |
| `kd_ratio` | `DOUBLE` | ✓ | - |
| `win_rate` | `DOUBLE` | ✓ | - |
| `avg_accuracy` | `DOUBLE` | ✓ | - |
| `avg_life_seconds` | `DOUBLE` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | - |

#### `personal_score_awards` (48 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `id` | `INTEGER` | ✗ | nextval('personal_score_awards_id_seq') |
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `award_name` | `VARCHAR` | ✗ | - |
| `award_category` | `VARCHAR` | ✓ | - |
| `award_count` | `INTEGER` | ✓ | 1 |
| `award_score` | `INTEGER` | ✓ | 0 |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `player_match_stats` (18 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `match_id` | `VARCHAR` | ✗ | - |
| `xuid` | `VARCHAR` | ✗ | - |
| `team_id` | `TINYINT` | ✓ | - |
| `team_mmr` | `FLOAT` | ✓ | - |
| `enemy_mmr` | `FLOAT` | ✓ | - |
| `kills_expected` | `FLOAT` | ✓ | - |
| `kills_stddev` | `FLOAT` | ✓ | - |
| `deaths_expected` | `FLOAT` | ✓ | - |
| `deaths_stddev` | `FLOAT` | ✓ | - |
| `assists_expected` | `FLOAT` | ✓ | - |
| `assists_stddev` | `FLOAT` | ✓ | - |
| `created_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `sync_meta` (3 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `key` | `VARCHAR` | ✗ | - |
| `value` | `VARCHAR` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### `xuid_aliases` (0 lignes)

| Colonne | Type | Nullable | Default |
|---------|------|----------|---------|
| `xuid` | `VARCHAR` | ✗ | - |
| `gamertag` | `VARCHAR` | ✗ | - |
| `last_seen` | `TIMESTAMP` | ✓ | - |
| `source` | `VARCHAR` | ✓ | - |
| `updated_at` | `TIMESTAMP` | ✓ | CURRENT_TIMESTAMP |

#### Index

| Nom | Table | Unique | SQL |
|-----|-------|--------|-----|
| `idx_aliases_gamertag` | `xuid_aliases` | ✗ | `CREATE INDEX idx_aliases_gamertag ON xuid_aliases(gamertag);` |
| `idx_career_date` | `career_progression` | ✗ | `CREATE INDEX idx_career_date ON career_progression(recorded_at);` |
| `idx_career_xuid` | `career_progression` | ✗ | `CREATE INDEX idx_career_xuid ON career_progression(xuid);` |
| `idx_highlight_match` | `highlight_events` | ✗ | `CREATE INDEX idx_highlight_match ON highlight_events(match_id);` |
| `idx_kv_killer` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_killer ON killer_victim_pairs(killer_xuid);` |
| `idx_kv_match` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_match ON killer_victim_pairs(match_id);` |
| `idx_kv_victim` | `killer_victim_pairs` | ✗ | `CREATE INDEX idx_kv_victim ON killer_victim_pairs(victim_xuid);` |
| `idx_participants_team` | `match_participants` | ✗ | `CREATE INDEX idx_participants_team ON match_participants(match_id, team_id);` |
| `idx_participants_xuid` | `match_participants` | ✗ | `CREATE INDEX idx_participants_xuid ON match_participants(xuid);` |
| `idx_psa_category` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_category ON personal_score_awards(award_category);` |
| `idx_psa_match` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_match ON personal_score_awards(match_id);` |
| `idx_psa_xuid` | `personal_score_awards` | ✗ | `CREATE INDEX idx_psa_xuid ON personal_score_awards(xuid);` |


## Résumé Comparatif

| Joueur | Tables | Matchs | Médailles | Events | Participants | Taille (MB) |
|--------|--------|--------|-----------|--------|-------------|-------------|
| Chocoboflor | 21 | 241 | 502 | 167858 | 2049 | 64.76 |
| JGtm | 21 | 518 | 1584 | 170249 | 4812 | 73.76 |
| Madina97294 | 21 | 971 | 5056 | 374461 | 18999 | 115.76 |
| XxDaemonGamerxX | 14 | 18 | 20 | 3784 | 151 | 8.01 |
