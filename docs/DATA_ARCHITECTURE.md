# Architecture des Données - LevelUp

> Documentation de l'architecture de données DuckDB unifiée.

## Vue d'Ensemble

LevelUp utilise une architecture DuckDB unifiée (v4) qui remplace l'ancienne architecture hybride SQLite + Parquet.

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
│  Transformation │──────│  │  - match_participants, medals_earned │   │
│  Polars         │      │  │  - teammates_aggregate              │   │
└─────────────────┘      │  │  - antagonists, player_match_stats  │   │
                         │  │  - highlight_events, xuid_aliases   │   │
                         │  │  - career_progression, sync_meta    │   │
                         │  │  - mv_* (vues matérialisées)        │   │
                         │  └─────────────────────────────────────┘   │
                         │                                             │
                         │  ┌─────────────────────────────────────┐   │
                         │  │  players/{gt}/archive/ (Parquet)    │   │
                         │  │  - matches_2023.parquet             │   │
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

---

## Structure du Warehouse

```
data/
├── players/                        # Données par joueur
│   ├── Chocoboflor/
│   │   ├── stats.duckdb           # DB principale
│   │   └── archive/
│   │       ├── matches_2023.parquet
│   │       └── archive_index.json
│   ├── JGtm/
│   │   └── stats.duckdb
│   └── Madina97294/
│       └── stats.duckdb
│
├── warehouse/
│   └── metadata.duckdb            # Référentiels partagés
│
└── backups/                       # Backups Parquet
    └── Chocoboflor_2026-02-01/
```

---

## Tables de Données

### Base Joueur (stats.duckdb)

#### match_stats

Statistiques principales de chaque match.

| Colonne | Type | Description |
|---------|------|-------------|
| `match_id` | VARCHAR | Identifiant unique (PK) |
| `xuid` | VARCHAR | XUID du joueur |
| `start_time` | TIMESTAMP | Date/heure de début |
| `duration_seconds` | INTEGER | Durée du match |
| `playlist_id` | VARCHAR | ID de la playlist |
| `playlist_name` | VARCHAR | Nom de la playlist |
| `map_id` | VARCHAR | ID de la carte |
| `map_name` | VARCHAR | Nom de la carte |
| `mode_id` | VARCHAR | ID du mode de jeu |
| `mode_name` | VARCHAR | Nom du mode |
| `mode_category` | VARCHAR | Catégorie (Slayer, CTF, etc.) |
| `kills` | INTEGER | Nombre de frags |
| `deaths` | INTEGER | Nombre de morts |
| `assists` | INTEGER | Nombre d'assistances |
| `accuracy` | DOUBLE | Précision (%) |
| `shots_fired` | INTEGER | Tirs effectués |
| `shots_hit` | INTEGER | Tirs touchés |
| `kda` | DOUBLE | (kills + assists/3) / max(deaths, 1) |
| `outcome` | INTEGER | 1=Tie, 2=Win, 3=Loss, 4=Left |
| `team_mmr` | DOUBLE | MMR de l'équipe |
| `enemy_mmr` | DOUBLE | MMR adverse |
| `session_id` | INTEGER | ID de la session de jeu |
| `avg_life_seconds` | DOUBLE | Durée de vie moyenne |

#### match_participants

Tous les joueurs de chaque match (une ligne par joueur). Contient **xuid** (identifiant), **team_id**, **outcome**, **rank** (rang dans le match), **score**, **kills**, **deaths**, **assists**. La colonne **gamertag** est souvent NULL : pour afficher le nom, faire un `LEFT JOIN xuid_aliases` sur `xuid`. Voir `docs/SQL_SCHEMA.md` et l’exemple de requête dans `docs/QUERY_EXAMPLES.md` (§ 4).

#### player_match_stats

Données MMR et skill détaillées.

| Colonne | Type | Description |
|---------|------|-------------|
| `match_id` | VARCHAR | FK vers match_stats |
| `xuid` | VARCHAR | XUID du joueur |
| `team_mmr` | DOUBLE | MMR de l'équipe |
| `enemy_mmr` | DOUBLE | MMR adverse |
| `expected_kills` | DOUBLE | Kills attendus (modèle) |
| `expected_deaths` | DOUBLE | Deaths attendus |
| `kills_std_dev` | DOUBLE | Écart-type kills |
| `deaths_std_dev` | DOUBLE | Écart-type deaths |

#### highlight_events

Événements marquants du match (kills, deaths, medals).

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | INTEGER | PK auto-incrémentée |
| `match_id` | VARCHAR | FK vers match_stats |
| `event_type` | VARCHAR | Type d'événement |
| `time_ms` | INTEGER | Timestamp (ms) |
| `xuid` | VARCHAR | XUID du joueur |
| `gamertag` | VARCHAR | Nom du joueur |
| `type_hint` | VARCHAR | Hint additionnel |
| `raw_json` | VARCHAR | JSON brut |

#### antagonists

Top killers et victimes (rivalités).

| Colonne | Type | Description |
|---------|------|-------------|
| `opponent_xuid` | VARCHAR | XUID adversaire (PK) |
| `opponent_gamertag` | VARCHAR | Nom adversaire |
| `times_killed` | INTEGER | Fois tué l'adversaire |
| `times_killed_by` | INTEGER | Fois tué par l'adversaire |
| `matches_against` | INTEGER | Nombre de matchs contre |
| `last_encounter` | TIMESTAMP | Dernière rencontre |
| `net_kills` | INTEGER | GENERATED (times_killed - times_killed_by) |

#### teammates_aggregate

Statistiques agrégées avec les coéquipiers.

| Colonne | Type | Description |
|---------|------|-------------|
| `teammate_xuid` | VARCHAR | XUID coéquipier (PK) |
| `teammate_gamertag` | VARCHAR | Nom du coéquipier |
| `matches_together` | INTEGER | Nombre de matchs |
| `wins_together` | INTEGER | Victoires ensemble |
| `avg_kda_together` | DOUBLE | KDA moyen ensemble |

#### career_progression

Historique de la progression de rang.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | INTEGER | PK auto-incrémentée |
| `xuid` | VARCHAR | XUID du joueur |
| `rank` | INTEGER | Rang actuel (0-272) |
| `rank_name` | VARCHAR | Nom du rang |
| `rank_tier` | VARCHAR | Tier (Bronze, Silver, etc.) |
| `current_xp` | INTEGER | XP dans le rang actuel |
| `xp_for_next_rank` | INTEGER | XP nécessaire |
| `xp_total` | INTEGER | XP total cumulé |
| `is_max_rank` | BOOLEAN | Rang maximum atteint |
| `adornment_path` | VARCHAR | Chemin du badge |
| `recorded_at` | TIMESTAMP | Date d'enregistrement |

#### xuid_aliases

Correspondances XUID ↔ Gamertag.

| Colonne | Type | Description |
|---------|------|-------------|
| `xuid` | VARCHAR | XUID (PK) |
| `gamertag` | VARCHAR | Dernier gamertag |
| `last_seen` | TIMESTAMP | Dernière apparition |

#### sync_meta

Métadonnées de synchronisation.

| Colonne | Type | Description |
|---------|------|-------------|
| `key` | VARCHAR | Clé (PK) |
| `value` | VARCHAR | Valeur |
| `updated_at` | TIMESTAMP | Date de mise à jour |

---

### Vues Matérialisées

Tables de cache rafraîchies après chaque sync.

#### mv_map_stats

Stats agrégées par carte.

| Colonne | Type | Description |
|---------|------|-------------|
| `map_id` | VARCHAR | ID carte (PK) |
| `map_name` | VARCHAR | Nom de la carte |
| `matches_played` | INTEGER | Nombre de matchs |
| `wins` | INTEGER | Victoires |
| `losses` | INTEGER | Défaites |
| `ties` | INTEGER | Égalités |
| `avg_kills` | DOUBLE | Moyenne kills |
| `avg_deaths` | DOUBLE | Moyenne deaths |
| `avg_assists` | DOUBLE | Moyenne assists |
| `avg_accuracy` | DOUBLE | Précision moyenne |
| `avg_kda` | DOUBLE | KDA moyen |
| `win_rate` | DOUBLE | Taux de victoire |
| `updated_at` | TIMESTAMP | Mise à jour |

#### mv_mode_category_stats

Stats par catégorie de mode.

| Colonne | Type | Description |
|---------|------|-------------|
| `mode_category` | VARCHAR | Catégorie (PK) |
| `matches_played` | INTEGER | Nombre de matchs |
| `avg_kills` | DOUBLE | Moyenne kills |
| `avg_deaths` | DOUBLE | Moyenne deaths |
| `avg_assists` | DOUBLE | Moyenne assists |
| `avg_ratio` | DOUBLE | Ratio moyen |
| `updated_at` | TIMESTAMP | Mise à jour |

#### mv_global_stats

Statistiques globales (key-value).

| Colonne | Type | Description |
|---------|------|-------------|
| `stat_key` | VARCHAR | Clé statistique (PK) |
| `stat_value` | DOUBLE | Valeur |
| `updated_at` | TIMESTAMP | Mise à jour |

Clés disponibles : `total_matches`, `total_wins`, `total_kills`, `total_deaths`, `win_rate`, `kd_ratio`, `avg_accuracy`, etc.

#### mv_session_stats

Stats par session de jeu.

| Colonne | Type | Description |
|---------|------|-------------|
| `session_id` | INTEGER | ID session (PK) |
| `match_count` | INTEGER | Nombre de matchs |
| `start_time` | TIMESTAMP | Début de session |
| `end_time` | TIMESTAMP | Fin de session |
| `kd_ratio` | DOUBLE | K/D de la session |
| `win_rate` | DOUBLE | Taux de victoire |
| `avg_accuracy` | DOUBLE | Précision moyenne |
| `is_with_friends` | BOOLEAN | Session avec amis |
| `updated_at` | TIMESTAMP | Mise à jour |

---

### Base Métadonnées (metadata.duckdb)

#### playlists

| Colonne | Type | Description |
|---------|------|-------------|
| `playlist_id` | VARCHAR | ID playlist (PK) |
| `name` | VARCHAR | Nom EN |
| `name_fr` | VARCHAR | Nom FR |

#### game_modes

| Colonne | Type | Description |
|---------|------|-------------|
| `mode_id` | VARCHAR | ID mode (PK) |
| `name` | VARCHAR | Nom EN |
| `name_fr` | VARCHAR | Nom FR |
| `category` | VARCHAR | Catégorie |

#### medal_definitions

| Colonne | Type | Description |
|---------|------|-------------|
| `medal_id` | INTEGER | ID médaille (PK) |
| `name_id` | VARCHAR | Nom technique |
| `name` | VARCHAR | Nom EN |
| `name_fr` | VARCHAR | Nom FR |
| `description_fr` | VARCHAR | Description FR |
| `sprite_index` | INTEGER | Index sprite |
| `difficulty` | VARCHAR | Difficulté |

#### career_ranks

| Colonne | Type | Description |
|---------|------|-------------|
| `rank` | INTEGER | Numéro de rang (PK) |
| `name` | VARCHAR | Nom EN |
| `name_fr` | VARCHAR | Nom FR |
| `tier` | VARCHAR | Tier |

---

## Flux de Données

### Import (API → DuckDB)

```
API SPNKr
    │
    ├─► MatchHistory endpoint
    │       └─► transform_match_stats() → match_stats
    │
    ├─► Skill endpoint
    │       └─► transform_skill_stats() → player_match_stats
    │
    ├─► Film endpoint
    │       └─► transform_highlight_events() → highlight_events
    │
    └─► Chaque match
            └─► extract_aliases() → xuid_aliases
```

### Transformations

| Donnée | Source | Formule |
|--------|--------|---------|
| `kda` | match_stats | `(kills + assists/3) / max(deaths, 1)` |
| `accuracy` | match_stats | `shots_hit / shots_fired * 100` |
| `net_kills` | antagonists | `times_killed - times_killed_by` |
| `win_rate` | mv_global_stats | `wins / matches * 100` |

---

## Archivage

### Structure Archives

```
data/players/{gamertag}/archive/
├── matches_2023.parquet       # Matchs 2023
├── matches_2024.parquet       # Matchs 2024
└── archive_index.json         # Index
```

### archive_index.json

```json
{
  "archives": [
    {
      "file": "matches_2023.parquet",
      "year": 2023,
      "match_count": 523,
      "date_range": ["2023-01-15", "2023-12-28"],
      "archived_at": "2026-02-01T10:30:00Z"
    }
  ]
}
```

### Vue Unifiée

```python
# Charger DB + archives
all_matches = repo.load_all_matches_unified()

# Compte total
total = repo.get_total_match_count_with_archives()
```

---

## Validation des Données

### Pydantic v2

Modèles pour validation à l'import :

```python
class MatchStatsRow(BaseModel):
    match_id: str
    xuid: str
    start_time: datetime
    kills: int = 0
    deaths: int = 0
    # ...

    @field_validator("xuid")
    def validate_xuid(cls, v):
        if not v.isdigit() or len(v) != 16:
            raise ValueError("XUID invalide")
        return v
```

### Contraintes DuckDB

- Clés primaires sur toutes les tables
- Index sur colonnes fréquemment filtrées
- Colonnes GENERATED pour les calculs
