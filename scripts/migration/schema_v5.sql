-- =============================================================================
-- LevelUp v5.0 — Schéma shared_matches.duckdb
-- =============================================================================
-- Base de données partagée contenant TOUS les matchs de TOUS les joueurs.
-- Élimine la duplication des données entre joueurs partageant des matchs.
--
-- Date de création : 2026-02-14
-- Architecture : DuckDB v4 → v5 (shared matches)
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Table : match_registry
-- Description : Registre central de TOUS les matchs connus.
--   Contient les métadonnées du match (map, playlist, scores, durée).
--   Chaque match n'apparaît QU'UNE SEULE FOIS, quel que soit le nombre
--   de joueurs trackés y ayant participé.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE match_registry (
    match_id VARCHAR PRIMARY KEY,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,

    -- Métadonnées du match
    playlist_id VARCHAR,
    playlist_name VARCHAR,
    map_id VARCHAR,
    map_name VARCHAR,
    pair_id VARCHAR,
    pair_name VARCHAR,
    game_variant_id VARCHAR,
    game_variant_name VARCHAR,
    mode_category VARCHAR,
    is_ranked BOOLEAN DEFAULT FALSE,
    is_firefight BOOLEAN DEFAULT FALSE,
    duration_seconds INTEGER,

    -- Scores des équipes
    team_0_score SMALLINT,
    team_1_score SMALLINT,

    -- Métadonnées de backfill (bitmask, même sémantique que match_stats.backfill_completed)
    backfill_completed INTEGER DEFAULT 0,
    participants_loaded BOOLEAN DEFAULT FALSE,
    events_loaded BOOLEAN DEFAULT FALSE,
    medals_loaded BOOLEAN DEFAULT FALSE,

    -- Tracking de migration / sync
    first_sync_by VARCHAR,              -- Gamertag du 1er joueur ayant sync ce match
    first_sync_at TIMESTAMP,
    last_updated_at TIMESTAMP,
    player_count SMALLINT DEFAULT 0,    -- Nb de joueurs trackés ayant ce match

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_registry_time ON match_registry(start_time);
CREATE INDEX idx_registry_playlist ON match_registry(playlist_id);
CREATE INDEX idx_registry_map ON match_registry(map_id);
CREATE INDEX idx_registry_player_count ON match_registry(player_count);
CREATE INDEX idx_registry_mode_category ON match_registry(mode_category);


-- ─────────────────────────────────────────────────────────────────────────────
-- Table : match_participants
-- Description : TOUS les joueurs de TOUS les matchs.
--   Contient les statistiques individuelles de chaque joueur dans chaque match.
--   Clé primaire composite (match_id, xuid) pour garantir l'unicité.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE match_participants (
    match_id VARCHAR NOT NULL,
    xuid VARCHAR NOT NULL,

    -- Identité du joueur au moment du match
    gamertag VARCHAR,

    -- Position & résultat
    team_id INTEGER,
    outcome INTEGER,                    -- 1=Tie, 2=Win, 3=Loss, 4=Left
    rank SMALLINT,                      -- Classement dans le match
    score INTEGER,                      -- Personal score

    -- K/D/A
    kills SMALLINT,
    deaths SMALLINT,
    assists SMALLINT,

    -- Précision
    shots_fired INTEGER,
    shots_hit INTEGER,

    -- Dégâts
    damage_dealt FLOAT,
    damage_taken FLOAT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (match_id, xuid)
    -- FK logique : match_id → match_registry(match_id)
    -- Pas de FOREIGN KEY DuckDB : le moteur OLAP traite UPDATE comme DELETE+INSERT,
    -- violant la contrainte. L'intégrité est assurée par la logique de migration.
);

CREATE INDEX idx_participants_xuid ON match_participants(xuid);
CREATE INDEX idx_participants_match ON match_participants(match_id);
CREATE INDEX idx_participants_team ON match_participants(match_id, team_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- Table : highlight_events
-- Description : TOUS les événements filmés (kills, deaths, etc.) de TOUS
--   les matchs. Distingue killer et victim avec leurs xuids/gamertags.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE SEQUENCE IF NOT EXISTS highlight_events_id_seq;

CREATE TABLE highlight_events (
    id INTEGER PRIMARY KEY DEFAULT nextval('highlight_events_id_seq'),
    match_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,        -- 'kill', 'death', etc.
    time_ms INTEGER,

    -- Identifiants killer/victim
    killer_xuid VARCHAR,
    killer_gamertag VARCHAR,
    victim_xuid VARCHAR,
    victim_gamertag VARCHAR,

    type_hint INTEGER,
    raw_json VARCHAR,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- FK logique : match_id → match_registry(match_id)
);

CREATE INDEX idx_events_match ON highlight_events(match_id);
CREATE INDEX idx_events_killer ON highlight_events(killer_xuid);
CREATE INDEX idx_events_victim ON highlight_events(victim_xuid);


-- ─────────────────────────────────────────────────────────────────────────────
-- Table : killer_victim_pairs
-- Description : Paires killer→victim calculées depuis highlight_events.
--   Chaque ligne représente un kill individuel dans un match.
--   Permet de calculer némésis/souffre-douleur sans recalculer depuis
--   highlight_events à chaque fois.
--   Table mutualisée : identique quel que soit le joueur POV.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE killer_victim_pairs (
    match_id VARCHAR NOT NULL,
    killer_xuid VARCHAR NOT NULL,
    killer_gamertag VARCHAR,
    victim_xuid VARCHAR NOT NULL,
    victim_gamertag VARCHAR,
    kill_count INTEGER DEFAULT 1,
    time_ms INTEGER,
    is_validated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    -- FK logique : match_id → match_registry(match_id)
);

CREATE INDEX idx_kv_match ON killer_victim_pairs(match_id);
CREATE INDEX idx_kv_killer ON killer_victim_pairs(killer_xuid);
CREATE INDEX idx_kv_victim ON killer_victim_pairs(victim_xuid);


-- ─────────────────────────────────────────────────────────────────────────────
-- Table : medals_earned
-- Description : Médailles de TOUS les joueurs de TOUS les matchs.
--   Clé primaire composite (match_id, xuid, medal_name_id) pour stocker
--   les médailles de chaque joueur individuellement.
--   medal_name_id est BIGINT (cohérence avec migration v4.x).
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE medals_earned (
    match_id VARCHAR NOT NULL,
    xuid VARCHAR NOT NULL,              -- De QUEL joueur
    medal_name_id BIGINT NOT NULL,
    count SMALLINT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (match_id, xuid, medal_name_id)
    -- FK logique : match_id → match_registry(match_id)
);

CREATE INDEX idx_medals_match ON medals_earned(match_id);
CREATE INDEX idx_medals_xuid ON medals_earned(xuid);
CREATE INDEX idx_medals_composite ON medals_earned(match_id, xuid);


-- ─────────────────────────────────────────────────────────────────────────────
-- Table : xuid_aliases
-- Description : Mapping global xuid → gamertag.
--   Maintenu à jour à chaque sync/migration, permet la résolution
--   de gamertags sans appel API.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE xuid_aliases (
    xuid VARCHAR PRIMARY KEY,
    gamertag VARCHAR NOT NULL,
    last_seen TIMESTAMP,
    source VARCHAR,                     -- 'api', 'film', 'manual', 'migration'
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_aliases_gamertag ON xuid_aliases(gamertag);


-- ─────────────────────────────────────────────────────────────────────────────
-- Table : schema_version
-- Description : Versioning du schéma de la base partagée.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    description VARCHAR NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_version (version, description)
VALUES (1, 'v5.0 — Création initiale du schéma shared_matches');
