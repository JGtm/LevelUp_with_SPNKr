# Schéma shared_matches.duckdb — Architecture v5.0

> **Date** : 2026-02-14  
> **Version schéma** : 1  
> **Fichier DDL** : `scripts/migration/schema_v5.sql`  
> **Script de création** : `scripts/migration/create_shared_matches_db.py`

---

## Objectif

La base `data/warehouse/shared_matches.duckdb` est le **cœur de l'architecture v5**. Elle centralise toutes les données de matchs de tous les joueurs trackés, éliminant la duplication massive qui existait en v4 (chaque joueur avait sa propre copie complète de chaque match).

### Gains attendus

| Métrique | v4 (avant) | v5 (après) | Gain |
|----------|-----------|-----------|------|
| Stockage total | ~262 MB | ~81 MB | -69% |
| Appels API / sync | 100% | 28% | -72% |
| Temps de sync | 100% | 27% | -73% |

---

## Diagramme ER

```
┌─────────────────────────────┐
│       match_registry        │
│ ─────────────────────────── │
│ PK match_id (VARCHAR)       │
│    start_time (TIMESTAMP)   │──┐
│    end_time (TIMESTAMP)     │  │
│    playlist_id/name         │  │
│    map_id/name              │  │
│    pair_id/name             │  │
│    game_variant_id/name     │  │
│    mode_category            │  │
│    is_ranked, is_firefight  │  │
│    duration_seconds         │  │
│    team_0/1_score           │  │
│    backfill_completed       │  │
│    participants/events/     │  │
│    medals_loaded            │  │
│    first_sync_by/at         │  │
│    player_count             │  │
│    created_at, updated_at   │  │
└─────────────────────────────┘  │
         │                       │
         │ FK match_id           │
    ┌────┼───────────┬───────────┘
    │    │           │
    ▼    ▼           ▼
┌────────────┐ ┌──────────────┐ ┌──────────────┐
│ match_     │ │ highlight_   │ │ medals_      │
│participants│ │ events       │ │ earned       │
│ ────────── │ │ ──────────── │ │ ──────────── │
│PK match_id │ │PK id (SEQ)   │ │PK match_id   │
│PK xuid     │ │FK match_id   │ │PK xuid       │
│  gamertag  │ │  event_type  │ │PK medal_     │
│  team_id   │ │  time_ms     │ │   name_id    │
│  outcome   │ │  killer_xuid │ │  count       │
│  rank      │ │  killer_gt   │ │  created_at  │
│  score     │ │  victim_xuid │ └──────────────┘
│  kills     │ │  victim_gt   │
│  deaths    │ │  type_hint   │
│  assists   │ │  raw_json    │
│  shots_*   │ │  created_at  │
│  damage_*  │ └──────────────┘
│  created_at│
└────────────┘
         │
         │ xuid lookup
         ▼
┌──────────────┐     ┌──────────────────┐
│ xuid_aliases │     │ schema_version   │
│ ──────────── │     │ ──────────────── │
│PK xuid       │     │PK version (INT)  │
│  gamertag    │     │  description     │
│  last_seen   │     │  applied_at      │
│  source      │     └──────────────────┘
│  updated_at  │
└──────────────┘
```

---

## Tables

### 1. match_registry

**Registre central de tous les matchs connus.** Chaque match n'apparaît qu'une seule fois.

| Colonne | Type | Contrainte | Description |
|---------|------|-----------|-------------|
| `match_id` | VARCHAR | PK, NOT NULL | Identifiant unique du match (GUID Halo) |
| `start_time` | TIMESTAMP | NOT NULL | Heure de début du match |
| `end_time` | TIMESTAMP | | Heure de fin |
| `playlist_id` | VARCHAR | | ID de la playlist |
| `playlist_name` | VARCHAR | | Nom traduit de la playlist |
| `map_id` | VARCHAR | | ID de la carte |
| `map_name` | VARCHAR | | Nom traduit de la carte |
| `pair_id` | VARCHAR | | ID du pair (mode + carte) |
| `pair_name` | VARCHAR | | Nom du pair |
| `game_variant_id` | VARCHAR | | ID de la variante de jeu |
| `game_variant_name` | VARCHAR | | Nom de la variante |
| `mode_category` | VARCHAR | | Catégorie (pvp, bot, firefight) |
| `is_ranked` | BOOLEAN | DEFAULT FALSE | Match classé |
| `is_firefight` | BOOLEAN | DEFAULT FALSE | Mode Firefight |
| `duration_seconds` | INTEGER | | Durée en secondes |
| `team_0_score` | SMALLINT | | Score équipe 0 |
| `team_1_score` | SMALLINT | | Score équipe 1 |
| `backfill_completed` | INTEGER | DEFAULT 0 | Bitmask de backfill |
| `participants_loaded` | BOOLEAN | DEFAULT FALSE | Participants chargés |
| `events_loaded` | BOOLEAN | DEFAULT FALSE | Events chargés |
| `medals_loaded` | BOOLEAN | DEFAULT FALSE | Médailles chargées |
| `first_sync_by` | VARCHAR | | Gamertag du 1er sync |
| `first_sync_at` | TIMESTAMP | | Date du 1er sync |
| `last_updated_at` | TIMESTAMP | | Dernière mise à jour |
| `player_count` | SMALLINT | DEFAULT 0 | Nb joueurs trackés |
| `created_at` | TIMESTAMP | DEFAULT NOW | Date de création |
| `updated_at` | TIMESTAMP | DEFAULT NOW | Date de modification |

**Index** : `start_time`, `playlist_id`, `map_id`, `player_count`, `mode_category`

---

### 2. match_participants

**Tous les joueurs de tous les matchs.** PK composite `(match_id, xuid)`.

| Colonne | Type | Contrainte | Description |
|---------|------|-----------|-------------|
| `match_id` | VARCHAR | PK, FK → match_registry | Match |
| `xuid` | VARCHAR | PK, NOT NULL | Xbox User ID |
| `gamertag` | VARCHAR | | Gamertag au moment du match |
| `team_id` | INTEGER | | Numéro d'équipe |
| `outcome` | INTEGER | | 1=Tie, 2=Win, 3=Loss, 4=Left |
| `rank` | SMALLINT | | Classement dans le match |
| `score` | INTEGER | | Score personnel |
| `kills` | SMALLINT | | Kills |
| `deaths` | SMALLINT | | Deaths |
| `assists` | SMALLINT | | Assists |
| `shots_fired` | INTEGER | | Tirs effectués |
| `shots_hit` | INTEGER | | Tirs touchés |
| `damage_dealt` | FLOAT | | Dégâts infligés |
| `damage_taken` | FLOAT | | Dégâts subis |
| `created_at` | TIMESTAMP | DEFAULT NOW | Date de création |

**Index** : `xuid`, `match_id`, `(match_id, team_id)`

---

### 3. highlight_events

**Tous les événements filmés** (kills, deaths, etc.). Auto-incrémenté via séquence.

| Colonne | Type | Contrainte | Description |
|---------|------|-----------|-------------|
| `id` | INTEGER | PK, SEQ | Auto-incrémenté |
| `match_id` | VARCHAR | FK → match_registry | Match |
| `event_type` | VARCHAR | NOT NULL | Type d'événement |
| `time_ms` | INTEGER | | Timestamp en ms |
| `killer_xuid` | VARCHAR | | XUID du killer |
| `killer_gamertag` | VARCHAR | | Gamertag du killer |
| `victim_xuid` | VARCHAR | | XUID de la victime |
| `victim_gamertag` | VARCHAR | | Gamertag de la victime |
| `type_hint` | INTEGER | | Type hint API |
| `raw_json` | VARCHAR | | JSON brut de l'événement |
| `created_at` | TIMESTAMP | DEFAULT NOW | Date de création |

> **Note** : En v4, les highlight_events utilisaient `xuid` et `gamertag` (un seul acteur). En v5, on distingue `killer_*` et `victim_*` pour permettre les requêtes croisées.

**Index** : `match_id`, `killer_xuid`, `victim_xuid`

---

### 4. medals_earned

**Médailles de tous les joueurs de tous les matchs.** PK composite `(match_id, xuid, medal_name_id)`.

| Colonne | Type | Contrainte | Description |
|---------|------|-----------|-------------|
| `match_id` | VARCHAR | PK, FK → match_registry | Match |
| `xuid` | VARCHAR | PK, NOT NULL | Joueur ayant gagné la médaille |
| `medal_name_id` | BIGINT | PK, NOT NULL | ID de la médaille (BIGINT) |
| `count` | SMALLINT | NOT NULL | Nombre de fois obtenue |
| `created_at` | TIMESTAMP | DEFAULT NOW | Date de création |

> **Note** : En v4, `medals_earned` avait PK `(match_id, medal_name_id)` sans `xuid` (stockait uniquement les médailles du joueur propriétaire de la DB). En v5, `xuid` est ajouté à la PK pour stocker les médailles de **tous** les joueurs.

**Index** : `match_id`, `xuid`, `(match_id, xuid)`

---

### 5. xuid_aliases

**Mapping global xuid → gamertag.** Maintenu à jour à chaque sync.

| Colonne | Type | Contrainte | Description |
|---------|------|-----------|-------------|
| `xuid` | VARCHAR | PK | Xbox User ID |
| `gamertag` | VARCHAR | NOT NULL | Dernier gamertag connu |
| `last_seen` | TIMESTAMP | | Dernière apparition en match |
| `source` | VARCHAR | | Origine : api, film, manual, migration |
| `updated_at` | TIMESTAMP | DEFAULT NOW | Date de mise à jour |

**Index** : `gamertag`

---

### 6. schema_version

**Versioning du schéma** pour suivre les migrations futures.

| Colonne | Type | Contrainte | Description |
|---------|------|-----------|-------------|
| `version` | INTEGER | PK | N° de version |
| `description` | VARCHAR | NOT NULL | Description de la migration |
| `applied_at` | TIMESTAMP | DEFAULT NOW | Date d'application |

---

## Relations avec les DBs joueurs (v5)

Chaque joueur conserve sa propre DB `data/players/{gamertag}/stats.duckdb` pour les données **personnelles** uniquement :

| Table (player DB) | Contenu | Lien avec shared |
|-------------------|---------|-------------------|
| `player_match_enrichment` | performance_score, session_id, is_with_friends | match_id → match_registry |
| `teammates_aggregate` | Agrégats coéquipiers (perspective personnelle) | xuid → xuid_aliases |
| `antagonists` | Rivalités killer/victim | xuid → xuid_aliases |
| `media_files` | Fichiers médias personnels | — |
| `media_match_associations` | Associations média↔match | match_id → match_registry |

---

## Commandes utiles

```bash
# Créer la base
python scripts/migration/create_shared_matches_db.py

# Recréer (force)
python scripts/migration/create_shared_matches_db.py --force

# Dry-run
python scripts/migration/create_shared_matches_db.py --dry-run

# Valider le schéma
python scripts/migration/create_shared_matches_db.py --validate

# Tests
python -m pytest tests/migration/test_shared_schema.py -v
```

---

## Changelog

| Version | Date | Description |
|---------|------|-------------|
| 1 | 2026-02-14 | Création initiale (Sprint 1) |
