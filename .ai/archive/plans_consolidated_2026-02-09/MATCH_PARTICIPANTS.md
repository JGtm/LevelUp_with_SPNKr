# Table match_participants – Référence IA

> Pour les agents : schéma, usage (xuid = identifiant, gamertag via xuid_aliases), backfill.

## Rôle

- **Une ligne par (match_id, xuid)** : tous les joueurs du match (pas seulement le joueur principal).
- Colonnes : `team_id`, `outcome`, `rank`, `score`, `kills`, `deaths`, `assists` (et `gamertag`, souvent NULL).

## Identifiant des joueurs

- **Identifiant fiable** : **`xuid`** (clé avec `match_id`). Toujours utiliser `xuid` pour joindre ou identifier un joueur.
- **Nom affiché** : la colonne `gamertag` dans `match_participants` est souvent NULL. Pour obtenir le nom, **JOIN avec `xuid_aliases`** :
  ```sql
  COALESCE(p.gamertag, a.gamertag) AS gamertag
  FROM match_participants p
  LEFT JOIN xuid_aliases a ON a.xuid = p.xuid
  ```
- Ne pas considérer la table comme "inexploitable" sans gamertag : elle est exploitable via `xuid` + `xuid_aliases`.

## Schéma (DuckDB)

| Colonne   | Type    | Description                          |
|-----------|---------|--------------------------------------|
| match_id  | VARCHAR | PK avec xuid                         |
| xuid      | VARCHAR | PK – identifiant joueur              |
| team_id   | INTEGER | Équipe (0, 1, …)                     |
| outcome   | INTEGER | 1=Tie, 2=Win, 3=Loss, 4=Left         |
| gamertag  | VARCHAR | Souvent NULL → utiliser xuid_aliases |
| rank      | SMALLINT| Rang dans le match (1 = premier)     |
| score     | INTEGER | Score du joueur                      |
| kills     | SMALLINT| Kills (API CoreStats)                |
| deaths    | SMALLINT| Deaths                              |
| assists   | SMALLINT| Assists                              |

## Remplissage

| Source | Contenu |
|--------|--------|
| Sync (engine) | Lignes + rank, score, kills, deaths, assists (API prioritaire) |
| Backfill `--participants` | Création des lignes (match_id, xuid, team_id, outcome, gamertag, rank, score, k/d/a) |
| Backfill `--participants-scores` | UPDATE rank, score pour matchs où participants existent mais rank/score NULL |
| Backfill `--participants-kda` | UPDATE kills, deaths, assists idem |

Migration : `_ensure_match_participants_columns(conn)` ajoute rank, score, kills, deaths, assists si absents.

## Fichiers concernés

- `src/data/sync/engine.py` : schéma, migration, insertion.
- `src/data/sync/transformers.py` : `extract_participants()` (MatchParticipantRow avec rank, score, k/d/a).
- `src/db/loaders.py` : `_load_match_players_stats_from_duckdb()` lit match_participants (rank, score, k/d/a).
- `scripts/backfill_data.py` : `--participants`, `--participants-scores`, `--participants-kda`.

## Voir aussi

- `.ai/DATA_MATCH_RANK.md` : origine du rang (API vs tri par score).
- `.ai/BACKFILL_RANK_SCORE_AND_KDA_ARCHITECTURE.md` : options backfill score/rang et K/D/A.
- `docs/SQL_SCHEMA.md` : schéma utilisateur et exemple de requête avec xuid_aliases.
