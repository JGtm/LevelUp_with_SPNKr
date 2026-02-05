# Audit SQLite → DuckDB

> **Règle projet** : SQLite est **PROSCRIT**. Aucun fallback SQLite. Tout le code applicatif doit utiliser DuckDB v4 uniquement.
> Les seules exceptions sont les **scripts de migration** qui lisent l’ancien SQLite pour alimenter DuckDB.

## Résumé

| Catégorie | Fichiers | Action |
|-----------|----------|--------|
| **À migrer vers DuckDB** | scripts, src/db, src/ui | Remplacer connexions et requêtes SQLite par DuckDB / `DuckDBRepository` |
| **Scripts migration uniquement** | `recover_from_sqlite.py`, `migrate_player_to_duckdb.py` | Garder SQLite en lecture seule, documenter comme "migration only" |
| **Déprécié / ne plus utiliser** | `src/db/loaders.py`, `src/db/connection.py` | Remplacer par DuckDB partout, puis supprimer |
| **Tests** | `test_cache_integrity.py` | Adapter pour DuckDB ou marquer legacy / skip si .db |

---

## 1. Points à migrer vers DuckDB

### 1.1 `scripts/sync.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 36 | `import sqlite3` | Remplacer par `duckdb` pour les chemins `.duckdb` ; ne plus ouvrir de `.db` |
| 73-84 | `_update_sync_meta`, `_get_sync_meta(con: sqlite3.Connection)` | Utiliser table `sync_meta` (ou équivalent) en DuckDB + `duckdb.connect()` |
| 229-245 | `_has_table(con, table)`, `_count_rows(con, table)` avec `sqlite_master` | Pour DuckDB : `information_schema.tables` et requêtes DuckDB |
| 275, 324, 421, 652, 920, 1386 | `get_connection(db_path)` | Si `db_path.endswith(".duckdb")` → `duckdb.connect()` ; **ne plus accepter .db** |
| 286, 335 | `sqlite3.OperationalError` | Remplacer par `duckdb.Error` pour les branches DuckDB |
| 1276, 1386 | Commentaires "SQLite legacy" | Supprimer la branche SQLite : sync uniquement sur DuckDB |

**Objectif** : Sync ne travaille que sur `stats.duckdb`. Supprimer toute logique qui ouvre une base `.db` (SQLite).

---

### 1.2 `src/db/connection.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 1-43 | Module "Gestion des connexions SQLite", `_connect_sqlite`, `get_connection` | **À remplacer** : fournir `get_connection(db_path)` qui pour DuckDB utilise `duckdb.connect(db_path)` et pour `.db` **ne plus ouvrir** (ou lever une erreur explicite "SQLite interdit, migrer vers DuckDB"). |
| 46-74 | `DatabaseConnection` (SQLite) | Soit déprécié, soit double implémentation DuckDB/SQLite avec SQLite interdit par défaut. |

**Recommandation** : Un seul type de connexion supporté = DuckDB. Pour les rares scripts de migration (voir §3), ils ouvrent SQLite eux-mêmes.

---

### 1.3 `src/db/loaders.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 1-34 | Module "bases legacy (SQLite)", `import sqlite3` | **Déjà déprécié.** Ne plus utiliser. Tous les appels doivent passer par `DuckDBRepository`. |
| 181, 214-216 | `has_table()` : branche SQLite avec `get_connection`, `queries.HAS_TABLE` | Supprimer la branche SQLite ; ne garder que DuckDB (information_schema). |
| 533, 764, 777, 1029, 1402 | Autres usages SQLite / `sqlite_master` | Migrer vers DuckDB ou retirer si module voué à suppression. |

**Recommandation** : Marquer le module comme "à supprimer", migrer tous les appelants vers DuckDB, puis supprimer.

---

### 1.4 `src/ui/multiplayer.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 4, 12-14 | Docstring "Legacy SQLite", "table Players" | Préciser : "DuckDB v4 uniquement ; plus de support SQLite." |
| 41-45 | `_get_sqlite_connection(db_path)` | **Supprimer** ou remplacer par connexion DuckDB si besoin (ex. `xuid_aliases`). |
| 98-101 | `is_multi_player_db` : `sqlite_master`, table `Players` | Pour DuckDB v4 : toujours `False` (une DB = un joueur). **Supprimer** le chemin SQLite. |
| 122-143 | `list_players_in_db` : lecture table `Players` en SQLite | Pour DuckDB : retourner `[]` (pas de table Players). **Supprimer** branche SQLite. |
| 176-195 | `get_unique_xuids_from_matchstats` : SQLite MatchCache / MatchStats | Garder uniquement la branche DuckDB (`match_stats`). |
| 269 | `get_player_display_name` : SQLite `Players` | Pour DuckDB : utiliser `xuid_aliases` ou autre source DuckDB ; **supprimer** SQLite. |
| 461, 495 | Commentaires "Legacy SQLite" | Remplacer par "DuckDB v4 uniquement". |

**Objectif** : Plus de connexion SQLite dans ce module ; tout passe par DuckDB ou par structure de dossiers (un joueur = un `stats.duckdb`).

---

### 1.5 `src/ui/sync.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 61, 67 | "Supporte SQLite (.db) et DuckDB (.duckdb)" | Supporter **uniquement** `.duckdb`. Retourner False ou refuser les `.db`. |
| 141 | `# Legacy SQLite` → `get_sync_metadata(db_path)` | Ne plus appeler pour `.db` ; uniquement DuckDB (repository). |
| 488-490 | `get_players_from_db(db_path)` (table Players SQLite) | Ne plus utiliser pour la sync ; joueurs déduits depuis `db_profiles.json` + dossiers DuckDB. |
| 534 | "SQLite legacy : utiliser le script spnkr_import_db.py" | Supprimer cette branche ; sync uniquement via DuckDBSyncEngine / scripts sync DuckDB. |

**Objectif** : Sync UI ne parle qu’à des bases DuckDB.

---

### 1.6 `src/ui/pages/session_compare.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 97, 119 | "Détection DuckDB vs SQLite", "SQLite legacy" | Supprimer la branche SQLite ; tout en DuckDB. |

---

### 1.7 `src/ui/cache.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 137, 262, 287, 313, 335, 377, 437, 466, 500, 616, 704, 726 | Commentaires "Legacy SQLite" | Vérifier qu’aucun code actif ne lit une base `.db`. Si tout est déjà DuckDB, garder les commentaires comme rappel historique ou les raccourcir. |

---

### 1.8 `src/db/parsers.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 6 | `import sqlite3` | À retirer si plus utilisé, ou garder uniquement pour `recover_from_sqlite` / scripts de migration. |
| 343 | `except (sqlite3.Error, OSError)` | Remplacer par une exception plus générique (ex. `Exception`) ou `duckdb.Error` si le code n’est utilisé qu’avec DuckDB. |

---

### 1.9 `src/data/infrastructure/database/duckdb_engine.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 7-15, 41-42, 92-115 | `attach_sqlite()`, doc "Attache une base SQLite" | Si le référentiel est désormais en DuckDB (`metadata.duckdb`), **déprécier** `attach_sqlite` ou le retirer. Sinon, documenter "Uniquement pour métadonnées legacy ; pas pour données joueur." |

---

### 1.10 Scripts divers

| Fichier | Usage | Action |
|---------|--------|--------|
| `scripts/validate_refdata_integrity.py` | 113 : `sqlite_master` | Utiliser `information_schema.tables` et connexion DuckDB. |
| `scripts/refetch_film_roster.py` | 38, 606, 646, 697, 742 : `sqlite3.connect`, `--db` SQLite | Ajouter support DuckDB (lecture/écriture `stats.duckdb`) et privilégier DuckDB. |
| `scripts/migrate_game_variant_category.py` | 86 : `sqlite_master` | Utiliser DuckDB + `information_schema` si le script cible des bases DuckDB. |
| `scripts/migrate_add_columns.py` | 79 : `sqlite_master` | Idem : DuckDB + `information_schema`. |

---

## 2. Tests

| Fichier | Usage | Action |
|---------|--------|--------|
| `tests/test_cache_integrity.py` | `sqlite3`, `halo_unified.db`, `sqlite_master` | Adapter pour une base DuckDB de test (ex. `stats.duckdb`) ou marquer comme tests legacy et skip si pas de `.db`. |
| `tests/test_sync_ui.py` | 4, 316, 321 : commentaires "SQLite legacy" | Aligner les tests sur DuckDB uniquement ; supprimer références SQLite. |
| `tests/test_duckdb_repo_regressions.py` | 243, 267 : test que `sqlite_master` n’est pas utilisé | Garder : vérification que le repo utilise bien `information_schema`. |
| `tests/test_cache_duckdb_regressions.py` | 245-266 : idem | Garder. |

---

## 3. Scripts de migration (exception : lecture SQLite autorisée)

Ces scripts **lisent** l’ancien SQLite **uniquement** pour alimenter DuckDB. Ils restent les seuls à pouvoir utiliser SQLite.

| Fichier | Rôle | Action |
|---------|------|--------|
| `scripts/recover_from_sqlite.py` | Récupère données depuis `spnkr_gt_*.db` vers DuckDB | Garder `sqlite3` en **lecture seule**. En-tête : "Script de migration uniquement ; ne pas utiliser pour le flux normal." |
| `scripts/migrate_player_to_duckdb.py` | Migre un joueur SQLite → DuckDB | Idem : garder SQLite en lecture, documenter "migration only". |

---

## 4. Références documentation / pensée

À mettre à jour pour interdire explicitement SQLite et tout fallback :

- **CLAUDE.md** : règle "SQLite PROSCRIT" déjà présente ; à renforcer (voir §5).
- **.cursorrules** : ajouter "Interdit : SQLite, fallback SQLite".
- **.ai/project_map.md** : déjà "SQLite PROSCRIT" ; OK.
- **.ai/thought_log.md** : déjà rappel "SQLite PROSCRIT" ; OK.
- **.cursor/rules/** : ajouter une règle dédiée "pas de SQLite" (voir §5).

Fichiers de sprint / features qui mentionnent SQLite (contexte historique uniquement, pas de changement de code) :  
`.ai/sprints/SPRINT_DATA_RECOVERY_PLAN.md`, `LOGIC_LEGACY_SESSIONS.md`, `SPRINT_GAMERTAG_ROSTER_FIX.md`, `diagnose_migration_gaps.py`, etc.  
À laisser en l’état comme documentation de la migration.

---

## 5. Instructions IA mises à jour

- **CLAUDE.md** : section dédiée "SQLite interdit", aucun fallback.
- **.cursorrules** : interdiction explicite SQLite + fallback.
- **.cursor/rules/** : nouvelle règle `no-sqlite.md` (ou équivalent) pour rappel systématique.

---

## 6. Dépendance `aiosqlite` (pyproject.toml)

- Ligne 60 : `aiosqlite` pour `aiohttp-client-cache`.  
- C’est un **backend de cache HTTP**, pas une base de données applicative.  
- À conserver sauf si vous supprimez ce cache. Pas considéré comme violation de la règle "pas de SQLite pour les données métier".

---

*Dernière mise à jour : 2026-02-05*
