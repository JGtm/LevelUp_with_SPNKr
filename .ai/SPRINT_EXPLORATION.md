# Exploration Codebase — Sprints 6 à 11

> **Date** : 2026-02-12
> **Objectif** : Documenter l'état actuel du code pour accélérer chaque sprint restant
> **Basé sur** : Exploration exhaustive de 142 fichiers Python

---

## Table des matières

1. [Catalogue de données disponibles](#1-catalogue-de-données-disponibles)
2. [Sprint 6 — Timeseries + Corrélations](#2-sprint-6)
3. [Sprint 7 — V/D + Dernier match](#3-sprint-7)
4. [Sprint 8 — Coéquipiers comparaisons](#4-sprint-8)
5. [Sprint 9 — Legacy removal + Pandas complet](#5-sprint-9)
6. [Sprint 10 — Données + backfill refactoring](#6-sprint-10)
7. [Sprint 11 — Finalisation](#7-sprint-11)
8. [Audit Pandas complet (35 fichiers)](#8-audit-pandas)
9. [Audit SQLite (5 fichiers)](#9-audit-sqlite)
10. [Audit src/db/ dépendants (33 fichiers)](#10-audit-srcdb)

---

## 1. Catalogue de données disponibles

### 1.1 Colonnes `match_stats`

```
match_id, start_time, end_time, playlist_id, playlist_name,
map_id, map_name, pair_id, pair_name, game_variant_id, game_variant_name,
outcome, team_id, rank, kills, deaths, assists, kda, accuracy,
headshot_kills, max_killing_spree, time_played_seconds, avg_life_seconds,
my_team_score, enemy_team_score, team_mmr, enemy_mmr,
damage_dealt, damage_taken, shots_fired, shots_hit,
grenade_kills, melee_kills, power_weapon_kills, score, personal_score,
mode_category, game_variant_category, is_ranked, is_firefight, left_early,
session_id, session_label, performance_score,
teammates_signature, known_teammates_count, is_with_friends, friends_xuids,
created_at, updated_at
```

### 1.2 Colonnes `match_participants`

```
match_id, xuid (composite PK), team_id, outcome, gamertag, rank, score,
kills, deaths, assists, shots_fired, shots_hit, damage_dealt, damage_taken
```

### 1.3 Colonnes `career_progression`

```
id (PK), xuid, rank, rank_name, rank_tier, current_xp, xp_for_next_rank,
xp_total, is_max_rank, adornment_path, recorded_at
```

### 1.4 Autres tables

| Table | Colonnes clés |
|-------|--------------|
| `killer_victim_pairs` | match_id, killer_xuid, killer_gamertag, victim_xuid, victim_gamertag, kill_count, time_ms |
| `personal_score_awards` | match_id, xuid, award_name, award_category, award_count, award_score |
| `highlight_events` | match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json |
| `medals_earned` | match_id, medal_name_id, count |
| `xuid_aliases` | xuid, gamertag, last_seen, source |
| `sync_meta` | key, value, updated_at |

### 1.5 Vues matérialisées

`mv_map_stats`, `mv_mode_category_stats`, `mv_playlist_stats`, `mv_session_stats`

### 1.6 Méthodes DuckDBRepository clés

| Méthode | Retour | Usage |
|---------|--------|-------|
| `load_matches()` | `list[MatchRow]` | Avec filtres playlist/map/mode |
| `load_match_stats_as_polars()` | `pl.DataFrame` | Toutes les colonnes match_stats |
| `load_killer_victim_pairs_as_polars()` | `pl.DataFrame` | Paires K/V |
| `load_personal_score_awards_as_polars()` | `pl.DataFrame` | Awards détaillés |
| `load_match_rosters()` | `dict[str, list]` | Tous joueurs par match |
| `load_matches_with_teammate(xuid)` | `list[MatchRow]` | Matchs communs |
| `load_same_team_match_ids(xuid)` | `set[str]` | IDs matchs même équipe |
| `load_antagonists()` | `dict` | Top killers/victimes |

### 1.7 Fonctions d'analyse existantes (Polars)

| Module | Fonctions clés |
|--------|---------------|
| `cumulative.py` | `compute_cumulative_net_score_series_polars()`, `compute_cumulative_kd_series_polars()`, `compute_rolling_kd_polars()` |
| `performance_score.py` | `compute_relative_performance_score()`, `_prepare_history_metrics()`, `compute_performance_series()` |
| `killer_victim.py` | `compute_personal_antagonists_from_pairs_polars()`, `compute_duel_history_polars()` |
| `sessions.py` | `compute_sessions()`, `compute_sessions_with_context_polars()` |
| `objective_participation.py` | `compute_objective_participation_score_polars()`, `compute_player_profile_polars()` |
| `stats.py` | `compute_aggregated_stats()`, `compute_outcome_rates()`, `compute_global_ratio()` |

### 1.8 Config Performance Score v4

```python
RELATIVE_WEIGHTS = {
    "kpm": 0.22, "dpm_deaths": 0.18, "apm": 0.10, "kda": 0.15,
    "accuracy": 0.08, "pspm": 0.12, "dpm_damage": 0.10, "rank_perf": 0.05
}
SCORE_THRESHOLDS = {"excellent": 75, "good": 60, "average": 45, "below_average": 30}
```

---

## 2. Sprint 6 — Timeseries + Corrélations

### 2.1 Fichiers concernés

| Fichier | Lignes | Pandas ? | Rôle |
|---------|--------|----------|------|
| `src/visualization/distributions.py` | 1 075 | Oui (L6) | Histogrammes, scatter — **a déjà `plot_correlation_scatter()`** |
| `src/visualization/performance.py` | 645 | **Non (Polars pur)** | Cumul, rolling — prêt |
| `src/visualization/timeseries.py` | 728 | Oui (L3) | Timeseries par minute — mixte |
| `src/analysis/cumulative.py` | ~300 | **Non (Polars pur)** | Fonctions cumulatives |
| `src/ui/pages/timeseries.py` | 356 | Oui (L8) | Page UI timeseries |

### 2.2 Fonctions réutilisables (aucun code à écrire)

| Tâche S6 | Fonction existante | Module |
|----------|-------------------|--------|
| **6.1** Corrélations (3 scatter) | `plot_correlation_scatter()` | distributions.py |
| **6.2** Distribution Score/min | `plot_histogram()` | distributions.py |
| **6.3** Distribution Win rate | `plot_histogram()` | distributions.py |
| **6.4** Perf cumulée + marqueurs | `plot_cumulative_net_score()`, `plot_cumulative_kd()` | performance.py |

### 2.3 Colonnes nécessaires (toutes disponibles)

| Tâche | Colonnes | Statut |
|-------|----------|--------|
| 6.1 Corrélations | `avg_life_seconds`, `kills`, `deaths`, `team_mmr`, `enemy_mmr`, `outcome` | OK |
| 6.2 Score/min | `personal_score`, `time_played_seconds` | OK |
| 6.3 Win rate glissant | `outcome`, `start_time` | OK |
| 6.4 Marqueurs durée | `start_time`, `time_played_seconds` | OK |

### 2.4 Migration Pandas (6.M1)

`performance.py` est **déjà Polars pur** — rien à faire.

### 2.5 Estimation

| Tâche | Effort |
|-------|--------|
| 6.1 Corrélations (3 paires) | 2-3h (réutilise `plot_correlation_scatter()`) |
| 6.2 Score/min distribution | 1h (compute colonne + `plot_histogram()`) |
| 6.3 Win rate distribution | 2h (rolling computation + `plot_histogram()`) |
| 6.4 Marqueurs cumulatifs | 2-3h (enhance fonctions existantes) |
| 6.M1 Migration Polars | 0h (déjà fait) |
| **Total** | **~7-9h** |

### 2.6 Blockers

**Aucun.** Données, fonctions, et structure UI sont prêts.

---

## 3. Sprint 7 — V/D + Dernier match

### 3.1 Fichiers concernés

| Fichier | Lignes | Pandas ? | Rôle |
|---------|--------|----------|------|
| `src/ui/pages/win_loss.py` | 458 | Oui (L8) | Page W/L — **a `plot_matches_at_top_by_week()`** |
| `src/ui/pages/match_view.py` | 400+ | Oui (L16) | Vue détaillée match |
| `src/visualization/timeseries.py` | 728 | Oui (L3) | **a `plot_spree_headshots_accuracy()` (L508-626)** |
| `src/visualization/match_bars.py` | 292 | Oui (L11) | **a `plot_metric_bars_by_match()`** |
| `src/analysis/win_streaks.py` | — | — | **N'EXISTE PAS — à créer** |

### 3.2 Fonctions existantes réutilisables

| Tâche S7 | Fonction | Fichier | Action |
|----------|----------|---------|--------|
| 7.1 Score perso barres | `plot_metric_bars_by_match()` | match_bars.py | Appeler avec `personal_score` |
| 7.4 Dégâts histogramme | `plot_metric_bars_by_match()` | match_bars.py | Appeler 2x (dealt + taken) |
| 7.5 Tirs + précision | Pattern de `plot_spree_headshots_accuracy()` | timeseries.py | Adapter |
| 7.6 Retirer précision spree | `plot_spree_headshots_accuracy()` | timeseries.py | Supprimer axe Y2 accuracy |
| 7.7 Matchs Top < semaine | `plot_matches_at_top_by_week()` | win_loss.py | Paramétrer période |

### 3.3 Fonctions à créer

| Tâche | Nouveau fichier/fonction | Effort |
|-------|-------------------------|--------|
| **7.2** Win streaks | `src/analysis/win_streaks.py` (~300 lignes) | Haut |
| **7.3** Rang + score viz | Nouvelle fonction dans visualization | Haut |
| Tests | `tests/test_win_streaks.py` (~150 lignes) | Moyen |

### 3.4 Colonnes nécessaires (toutes disponibles)

`personal_score`, `damage_dealt`, `damage_taken`, `shots_fired`, `shots_hit`,
`accuracy`, `max_killing_spree`, `rank`, `team_mmr`, `enemy_mmr`, `outcome`, `start_time`

### 3.5 Migrations Pandas (7.M1, 7.M2)

| Fichier | Patterns Pandas critiques | Effort |
|---------|--------------------------|--------|
| `match_view.py` (7.M1) | ~80 lignes à modifier | Moyen |
| `timeseries.py` viz (7.M2) | `.rolling()`, `.dt.strftime()`, `.fillna()` — ~150 lignes | Haut |
| `match_bars.py` (implicite) | Pandas wrapper — utilisé par 7.1, 7.4, 7.5 | Moyen |

### 3.6 Ordonnancement recommandé

```
Jour 0 : 7.M1 + 7.M2 (migrations Polars) + début 7.2 (win_streaks.py)
Jour 1 : Fin 7.2 + 7.1, 7.3, 7.4 en parallèle
Jour 2 : 7.5, 7.6, 7.7 + tests + validation
```

### 3.7 Blockers

- **7.M1/7.M2** : Les migrations Pandas doivent précéder les tâches features (7.3-7.6)
- **7.2** : `win_streaks.py` doit être créé from scratch (pattern : `cumulative.py`)
- **match_bars.py** : Encore Pandas — créer wrapper ou migrer

---

## 4. Sprint 8 — Coéquipiers comparaisons

### 4.1 Architecture actuelle teammates (1 741 lignes, 3 fichiers)

| Fichier | Lignes | Rôle |
|---------|--------|------|
| `src/ui/pages/teammates.py` | 1 106 | Logique principale + 3 modes de vue |
| `src/ui/pages/teammates_charts.py` | 306 | Couche visualisation |
| `src/ui/pages/teammates_helpers.py` | 329 | Composants UI |

### 4.2 Modes de vue existants

1. **Single Teammate** (L537-687) : Graphes côte à côte, radar, médailles
2. **Multi Teammate** (L689-838) : Breakdown par carte, historique, barres métriques
3. **Trio View** (L841-1105) : Stats 3 joueurs + radar synergie

### 4.3 Graphes de comparaison existants (7 types)

1. Timeseries (kills/deaths)
2. Stats par minute (K/min, D/min, A/min)
3. Durée de vie moyenne
4. Performance timeseries
5. Barres métriques (folie, HS, perfect kills)
6. Distribution outcomes (W/L/T)
7. **Radar synergie** (6 axes : Objectifs, Combat, Support, Score, Impact, Survie)

### 4.4 Pattern de chargement multi-DB

```python
# src/ui/pages/teammates.py L50-96
_load_teammate_stats_from_own_db(gamertag, match_ids, reference_db_path)
# → Charge depuis data/players/{gamertag}/stats.duckdb
# → Retourne pd.DataFrame (à migrer vers Polars en S9)
```

### 4.5 Tâches S8 (9 sous-tâches comparaisons)

Les 9 sous-tâches ajoutent des comparaisons côte à côte utilisant les **mêmes** fonctions de visualisation des Sprints 6-7. Pas de nouvelles fonctions d'analyse à créer si S6-S7 sont livrés.

### 4.6 Blockers

**Aucun bloquant** si S6-S7 sont livrés. Les vues et le pattern multi-DB sont prêts.

---

## 5. Sprint 9 — Legacy removal + Pandas complet

### 5.1 Phase 9A — Suppression `src/db/`

#### Carte des dépendants de `src/db/`

| Import source | Fichiers dépendants | Criticité |
|---------------|---------------------|-----------|
| `from src.db.parsers` | 9 fichiers (`parse_xuid_input`, `parse_iso_utc`, etc.) | Moyenne — relocalisable |
| `from src.db.loaders` | 6 fichiers (DEPRECATED) | **Haute — cassera à la suppression** |
| `from src.db.loaders_cached` | 4 fichiers (DEPRECATED) | **Haute — cassera à la suppression** |
| `from src.db.connection` | 3 fichiers (`get_connection`) | Moyenne |
| `from src.db.profiles` | 2 fichiers (`list_local_dbs`) | Faible |
| `from src.db` (agrégé) | 2 fichiers (via `__init__.py`) | Haute |

#### Fichier critique : `src/ui/cache.py` (1 332 lignes)

- Mélange logique legacy/DuckDB
- `load_df_optimized()` (L723-852) **retourne déjà Polars** pour DuckDB v4
- MAIS : `cached_compute_sessions_db()` (L84-197) **convertit Polars→Pandas** via `.to_pandas()`
- Stratégie : refactorer fonction par fonction, tests entre chaque migration

#### Actions sur `src/db/`

| Fichier | Action |
|---------|--------|
| `src/db/loaders.py` (1 100+ lignes) | **SUPPRIMER** |
| `src/db/loaders_cached.py` (500+ lignes) | **SUPPRIMER** |
| `src/db/__init__.py` | **SUPPRIMER** (retirer 18 exports dépréciés) |
| `src/db/parsers.py` | **GARDER** → relocaliser vers `src/utils/parsers.py` |
| `src/db/connection.py` | **GARDER** → relocaliser vers `src/utils/` ou `src/data/` |
| `src/db/profiles.py` | **GARDER** → relocaliser vers `src/utils/` |

#### Cascade de corrections (6 fichiers critiques)

1. `src/ui/cache.py` — Retirer imports `load_matches`, `load_matches_cached`
2. `src/analysis/killer_victim.py` — Retirer import `MatchPlayerStats`
3. `src/ui/pages/match_view_players.py` — Retirer import `load_match_players_stats()`
4. `src/ui/sync.py` — Refactorer accès metadata sync
5. `src/ui/pages/session_compare.py` — Retirer connexion SQLite inline
6. `src/ui/sections/source.py` — Mettre à jour fonctions d'inspection

#### `RepositoryMode` (factory.py L42-55)

```python
class RepositoryMode(Enum):
    LEGACY = "legacy"           # → SUPPRIMER
    HYBRID = "hybrid"           # → SUPPRIMER
    SHADOW = "shadow"           # → SUPPRIMER
    SHADOW_COMPARE = "compare"  # → SUPPRIMER
    DUCKDB = "duckdb"           # ✅ GARDER (seul mode)
```

`get_repository()` lève déjà `ValueError` pour LEGACY/HYBRID/SHADOW. Nettoyage safe.

### 5.2 Phase 9B — Éradication SQLite

| Fichier | Ligne(s) | Action |
|---------|----------|--------|
| `src/db/loaders.py:34` | `import sqlite3` | SUPPRIMÉ avec le fichier |
| `src/db/loaders_cached.py:42` | `import sqlite3` | SUPPRIMÉ avec le fichier |
| `src/db/parsers.py:6` | `import sqlite3` | Refactorer (connexion générique) |
| `src/data/infrastructure/database/sqlite_metadata.py:17` | `import sqlite3` | GARDER (script migration) |
| `src/ui/aliases.py:61-80` | Fonction `_load_aliases_from_db_cached()` | **SUPPRIMER** (garder version DuckDB L83-104) |

### 5.3 Phase 9C — Migration Pandas (35 fichiers)

Voir section [8. Audit Pandas complet](#8-audit-pandas) pour la liste exhaustive.

**Stratégie de migration par tiers** :

| Tier | Fichiers | Jours |
|------|----------|-------|
| **CRITIQUE** | `cache.py`, `teammates.py` | J1-J2 |
| **HAUT** | `match_view.py`, `session_compare.py`, `filters.py` | J2-J3 |
| **MOYEN** | `visualization/*` (8), `app/kpis*.py` (4) | J3-J4 |
| **BAS** | `analysis/*`, `components/*` | J4 |

**Pattern de migration** :
```python
# AVANT : Retourne Pandas
def my_function() -> pd.DataFrame:
    df = create_polars_df()
    return df.to_pandas()  # ← Mauvais

# APRÈS : Retourne Polars, convertit à la frontière
def my_function() -> pl.DataFrame:
    return create_polars_df()

# À la frontière Streamlit/Plotly uniquement :
st.dataframe(my_function().to_pandas())
```

---

## 6. Sprint 10 — Données + backfill refactoring

### 6.1 Fichiers SQLite legacy à supprimer

| Fichier | Taille | Statut |
|---------|--------|--------|
| `data/halo_unified.db` | 149 Mo | SUPPRIMER |
| `data/spnkr_gt_Chocoboflor.db` | 15 Mo | SUPPRIMER |
| `data/spnkr_gt_JGtm.db` | 60 Mo | SUPPRIMER |
| `data/spnkr_gt_Madina97294.db` | 116 Mo | SUPPRIMER |
| `data/spnkr_gt_XxDaemonGamerxX.db` | 16 Mo | SUPPRIMER |
| `data/test_sync.db` | 1.3 Mo | SUPPRIMER |
| `data/warehouse/metadata.db` + cache | — | SUPPRIMER |
| **Total** | **~360 Mo** | |

### 6.2 Répertoire `thumbs/`

- **130+ images** (8.8 Mo) dans `thumbs/`
- **3 fichiers Python** référencent `thumbs/` :
  1. `src/data/media_indexer.py`
  2. `src/ui/pages/media_library.py`
  3. `src/ui/pages/match_view_helpers.py`
- Action : Déplacer vers `static/maps/`, mettre à jour les 3 refs

### 6.3 `data/investigation/`

Existe (~2.5 Mo de JSON d'exploration) — à évaluer si encore utile, sinon archiver.

### 6.4 `backfill_data.py` — État actuel

| Métrique | Valeur |
|----------|--------|
| Lignes | **2 563** |
| Taille | 104 Ko |
| Structure | Monolithique (1 fichier, 23 fonctions) |
| Plus grosse fonction | `_find_matches_missing_data()` — 723 lignes |
| Violations Pandas | `pd.Series` L119, L698, L709 |
| Blocs except silencieux | 9 |

**Structure de refactoring proposée** :

```
scripts/backfill/
├── __init__.py
├── detection.py       (~250 lignes) - détection matchs, logique OR/AND
├── computation.py     (~300 lignes) - perf_score, sessions, KV pairs
├── insertion.py       (~400 lignes) - INSERT/UPDATE
├── migrations.py      (~150 lignes) - migrations schéma
└── cli.py             (~100 lignes) - argparse + boucle principale
```

### 6.5 `scripts/backup_player.py`

Existe et fonctionne — prérequis pour backup avant suppression des `.db`.

---

## 7. Sprint 11 — Finalisation

### 7.1 Suite de tests

- **75 fichiers de tests** dans `tests/`
- Limitation connue : tests importants `duckdb` échouent sur MSYS2 (pas de package)
- Fichiers de tests clés : `test_performance_score_v4.py` (19 tests), `test_sync_engine.py`, `test_duckdb_repository.py`

### 7.2 Configuration Ruff (dans `pyproject.toml` L100-138)

```toml
[tool.ruff]
line-length = 100
target-version = "py310"
exclude = ["scripts/_archive", "scripts/migration"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM"]
ignore = ["E501", "E402", "B008", "C901", "ARG001"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]
"tests/*" = ["ARG001", "ARG002"]
"src/db/loaders.py" = ["UP038", "SIM102", "SIM105", "B007"]       # → Supprimer après S9
"src/db/loaders_cached.py" = ["UP038", "SIM102", "SIM105", "B007"] # → Supprimer après S9
```

**Action S11** : Ajouter règle custom pour bloquer `import pandas` dans `src/`.

### 7.3 CI/CD

Fichier `.github/workflows/ci.yml` existe avec black, isort, ruff, pyright.

### 7.4 Documentation `.ai/`

| Fichier | Taille | Mis à jour | Statut |
|---------|--------|------------|--------|
| `project_map.md` | 9.8 Ko | 2026-02-11 | OK |
| `thought_log.md` | 72.6 Ko | 2026-02-11 | OK — Sprints 0-5 documentés |
| `data_lineage.md` | 10 Ko | 2026-02-07 | OK |
| `PLAN_UNIFIE.md` | 43 Ko | 2026-02-11 | OK |
| `features/` | 88 Ko (10 fichiers) | 2026-01-31 | Référence — marquer Implémenté |

### 7.5 CLAUDE.md

Section "Code Déprécié" à mettre à jour après S9 (retirer refs `src/db/`, `src/models.py`).
Section `per-file-ignores` ruff à nettoyer (retirer `src/db/loaders*.py`).

---

## 8. Audit Pandas complet (35 fichiers)

### Par couche

| Couche | Nb | Fichiers |
|--------|----|----------|
| `src/ui/` | 17 | `cache.py`, pages/* (8), components/* (2), `commendations.py`, `formatting.py`, `perf.py` |
| `src/visualization/` | 8 | `timeseries.py`, `maps.py`, `trio.py`, `distributions.py`, `match_bars.py`, etc. |
| `src/app/` | 8 | `filters.py`, `filters_render.py`, `helpers.py`, `kpis.py`, `kpis_render.py`, `page_router.py`, `data_loader.py` |
| `src/analysis/` | 2 | `maps.py`, `stats.py` |
| `src/data/` | 1 | `integration/streamlit_bridge.py` |

### Détail exact (ligne d'import)

```
src/analysis/maps.py:3
src/analysis/stats.py:5
src/app/filters.py:15
src/app/filters_render.py:15
src/app/helpers.py:10
src/app/kpis.py:13
src/app/kpis_render.py:13
src/app/page_router.py:13
src/data/integration/streamlit_bridge.py:21
src/ui/cache.py:28
src/ui/commendations.py:20
src/ui/components/chart_annotations.py:10
src/ui/components/duckdb_analytics.py:133,213  (inline)
src/ui/components/performance.py:11
src/ui/formatting.py:15
src/ui/pages/citations.py:7
src/ui/pages/last_match.py:13
src/ui/pages/match_history.py:15
src/ui/pages/match_view.py:16
src/ui/pages/match_view_charts.py:5
src/ui/pages/match_view_helpers.py:12
src/ui/pages/match_view_participation.py:14
src/ui/pages/session_compare.py:11
src/ui/pages/teammates.py:8
src/ui/pages/teammates_charts.py:8
src/ui/pages/teammates_helpers.py:11
src/ui/pages/timeseries.py:8
src/ui/pages/win_loss.py:8
src/visualization/distributions.py:6
src/visualization/maps.py:3
src/visualization/match_bars.py:11
src/visualization/timeseries.py:3
src/visualization/trio.py:3
```

### Fichiers critiques (usage lourd, >100 opérations Pandas)

1. **`src/ui/cache.py`** (1 332 lignes) — Hybrid legacy/DuckDB
2. **`src/ui/pages/teammates.py`** (1 106 lignes) — Multi-DB + vues complexes
3. **`src/app/filters.py`** — Filtrage sessions
4. **`src/ui/pages/match_view.py`** — Vue détaillée match
5. **`src/ui/pages/session_compare.py`** — Comparaison sessions

---

## 9. Audit SQLite (5 fichiers)

| Fichier | Ligne | Usage | Action |
|---------|-------|-------|--------|
| `src/db/loaders.py:34` | `import sqlite3` | Loader legacy | SUPPRIMER (S9) |
| `src/db/loaders_cached.py:42` | `import sqlite3` | Cache legacy | SUPPRIMER (S9) |
| `src/db/parsers.py:6` | `import sqlite3` | Connexion générique | REFACTORER |
| `src/data/infrastructure/database/sqlite_metadata.py:17` | `import sqlite3` | Migration | GARDER (exception doc.) |
| `src/ui/aliases.py:61-80` | Fonction fallback SQLite | Alias reader | SUPPRIMER fonction (garder DuckDB L83-104) |

---

## 10. Audit `src/db/` dépendants (33 fichiers)

### Imports par module source

| Source | Nb dépendants | Fonctions importées |
|--------|---------------|---------------------|
| `src.db.parsers` | 9 | `parse_xuid_input`, `parse_iso_utc`, etc. |
| `src.db.loaders` | 6 | `load_matches`, `load_match_players_stats`, etc. (DEPRECATED) |
| `src.db.loaders_cached` | 4 | `load_matches_cached`, etc. (DEPRECATED) |
| `src.db.connection` | 3 | `get_connection` |
| `src.db.profiles` | 2 | `list_local_dbs` |
| `src.db` (agrégé) | 2 | Via `__init__.py` |

### Fichiers qui casseront à la suppression

1. `src/ui/cache.py` — imports multiples de `loaders` et `loaders_cached`
2. `src/analysis/killer_victim.py` — import `MatchPlayerStats`
3. `src/ui/pages/match_view_players.py` — import `load_match_players_stats()`
4. `src/ui/sync.py` — accès metadata sync
5. `src/ui/sections/source.py` — fonctions d'inspection
6. `src/ui/pages/session_compare.py` — connexion SQLite inline

### Fonctions à relocaliser (garder)

| Fonction | Source actuelle | Destination proposée |
|----------|----------------|---------------------|
| `parse_xuid_input()` | `src/db/parsers.py` | `src/utils/parsers.py` |
| `parse_iso_utc()` | `src/db/parsers.py` | `src/utils/parsers.py` |
| `_sanitize_gamertag()` | `src/db/loaders.py` | `src/utils/gamertag.py` |
| `get_connection()` | `src/db/connection.py` | `src/data/connection.py` |
| `list_local_dbs()` | `src/db/profiles.py` | `src/utils/profiles.py` |

---

## 8. Sprint 12 — Heatmap d'Impact & Cercle d'Amis

### 8.1 Contexte et objectifs

Ajouter une visualisation interactive dans l'onglet **Coéquipiers** montrant les **moments clés par coéquipier** sur une heatmap (Joueurs × Matchs) avec trois événements mutuellement exclusifs :
- **First Blood** (🟢 +1 point) : Premier kill du match
- **Finisseur** (🟡 +2 points) : Dernier kill du match en victoire (`outcome=2`)
- **Boulet** (🔴 -1 point) : Dernière mort du match en défaite (`outcome=3`)

+ Tableau de ranking Amis/Boulets avec badges MVP/Boulet.

### 8.2 Données et sources

#### Disponibilité requise

| Donnée | Source | Statut | Disponibilité |
|--------|--------|--------|---------------|
| `highlight_events` | DuckDB `match_events` | Existant | ✅ `(xuid, gamertag, match_id, event_type, time_ms)` |
| `match_stats.outcome` | DuckDB `match_stats` | Existant | ✅ `(match_id, outcome: 2=WIN, 3=LOSS)` |
| Friends list | Via `teammates.py` filtrage | Existant | ✅ Coéquipiers sélectionnés |
| Match IDs filtrés | Via filtres actifs | Existant | ✅ (date, playlist, mode, map) |

#### Colonnes impliquées

| Colonne | Table | Type | Utilisation |
|---------|-------|------|-------------|
| `match_id` | `highlight_events`, `match_stats` | TEXT | Join et grouping |
| `xuid` | `highlight_events` | INT64 | Filter friends |
| `gamertag` | `highlight_events` | TEXT | Heatmap labels |
| `event_type` | `highlight_events` | INT | Kill=1, Death=2 (si présent) |
| `time_ms` | `highlight_events` | INT | Déterminer min/max |
| `outcome` | `match_stats` | INT | Valider conditions (outcome=2 pour Finisseur, outcome=3 pour Boulet) |

### 8.3 Incompatibilités logiques et conditions

#### Matrice de compatibilité

| Combinaison | Logique | Possible ? | Note |
|-------------|---------|-----------|------|
| First Blood + Finisseur | `outcome=2`: Min kill + Max kill mêmes = rare mais POSSIBLE | ✅ OUI | Match court, 1v1 victoire |
| First Blood + Boulet | `outcome=3`: Min kill + Max death mêmes = POSSIBLE | ✅ OUI | Match court, mort défaite après unique kill |
| Finisseur + Boulet | `outcome=2 AND outcome=3` = **IMPOSSIBLE** | ❌ NON | **Match ne peut avoir 2 outcomes** |
| 2+ First Bloods | `DISTINCT matches`: Un seul min(time_ms) | ❌ NON | Un seul First Blood par match |
| 2+ Finisseurs | `outcome=2`: Un seul max(time_ms) | ❌ NON | Un seul dernier kill par match/outcome |
| 2+ Boulets | `outcome=3`: Un seul max(time_ms) | ❌ NON | Une seule dernière mort par match/outcome |

#### Conditions strictes dans l'analyse

```python
# Finisseur — OBLIGATOIRE outcome=2
@match.outcome == 2
def identify_clutch_finisher(match_events: dict) -> dict:
    # Retourne: {match_id: (xuid, time_ms)} pour le Max kill_timestamp

# Boulet — OBLIGATOIRE outcome=3
@match.outcome == 3
def identify_last_casualty(match_events: dict) -> dict:
    # Retourne: {match_id: (xuid, time_ms)} pour le Max death_timestamp

# First Blood — INDÉPENDANT du outcome
def identify_first_blood(match_events: dict) -> dict:
    # Retourne: {match_id: (xuid, time_ms)} pour le Min kill_timestamp
```

#### Validation garantie en tests

- ✅ `test_finisseur_and_boulet_never_together` — Assertion : Pas de match avec BOTH Finisseur et Boulet
- ✅ `test_first_blood_always_earliest` — Assertion : First Blood toujours min(time_ms)
- ✅ `test_multiple_events_per_friend` — Assertion : Un ami peut être FB + Finisseur (POSSIBLE)
- ✅ `test_outcome_filtering` — Assertion : Finisseur/Boulet rejetés si outcome ne correspond

### 8.4 Fichiers concernés

| Fichier | Type | Lignes | Action |
|---------|------|--------|--------|
| `src/analysis/friends_impact.py` | **Nouveau** | ~350 | Analyse : `identify_first_blood()`, `identify_clutch_finisher()`, `identify_last_casualty()`, `compute_impact_scores()` |
| `src/visualization/friends_impact_heatmap.py` | **Nouveau** | ~300 | Viz : `plot_friends_impact_heatmap()`, `build_impact_ranking_df()` |
| `src/ui/pages/teammates.py` | Modifié | +70 | Intégration : expander "⚡ Impact & Taquinerie", appel fonctions, filtrage |
| `src/data/repositories/duckdb_repository.py` | Modifié | +40 | Getter : `load_friends_impact_data()` (query highlight_events + match_stats) |
| `src/ui/translations.py` | Modifié | +15 | i18n : S12-IMPACT-* keys (FR/EN) |
| `tests/test_friends_impact.py` | **Nouveau** | ~250 | Tests unitaires : identification events, scoring, incompatibilités |
| `tests/test_friends_impact_viz.py` | **Nouveau** | ~150 | Tests : heatmap rendering, ranking_df construction |

### 8.5 Dépendances et prérequis

#### Modules existants réutilisés

| Module | Fonction | Raison |
|--------|----------|--------|
| `DuckDBRepository` | `load_highlight_events()`, `load_match_stats()` | Source données |
| `Plotly (go.Figure, go.Heatmap)` | Heatmap scaffolding | Visualisation matricielle |
| `Polars` | DataFrame construction, groupby, filter | Calculs + ranking |
| `streamlit` | `st.expander()`, `st.dataframe()`, `st.columns()` | Layout UI |
| `src/ui/translations.py` | Clés i18n existantes | Traduction cohérente |

#### Pas de nouvelles dépendances externes

✅ Utilisés : Plotly, Polars, Streamlit, DuckDB (déjà présents) — **Zéro dépendance neuve**.

### 8.6 Estimation effort

| Tâche | Durée | Détail |
|-------|-------|--------|
| **12.1** Analyse `friends_impact.py` | 4-5h | 3 fonctions ID + 1 fonction scoring + tests unitaires |
| **12.2** Visualisation heatmap | 3-4h | Plotly Figure, ranking DF, integration Streamlit |
| **12.3** UI `teammates.py` + Repository | 2-3h | Expander, filtrage, appels fonctions, caching |
| **12.4** Traductions + Docs | 1h | 12+ clés i18n, doc dans PLAN_UNIFIE.md |
| **Total impact** | **10-13h (1.25-1.6j)** | Peut déborder sur 2j si tests exhaustifs |

### 8.7 Ordonnancement recommandé

**Jour 0** (4-5h)
1. Créer `friends_impact.py` (3 ID funcs + 1 scoring func)
2. Écrire `test_friends_impact.py` (TDD pour conditions outcome)
3. Valider incompatibilités logiques

**Jour 1** (5-6h)
1. Créer `friends_impact_heatmap.py` (Plotly + Polars DF)
2. Modifier `duckdb_repository.py` (getter)
3. Intégrer `teammates.py` (expander + appels)

**Jour 2** (2-3h)
1. Tester UI (filtres, multi-sélection friends)
2. Ajouter traductions
3. Validation finale + perf check (1000+ events)

### 8.8 Checklist de livraison S12

- [ ] `friends_impact.py` créé + tests passent (`pytest tests/test_friends_impact.py`)
- [ ] `friends_impact_heatmap.py` créé + tests passent (`pytest tests/test_friends_impact_viz.py`)
- [ ] `teammates.py` intégré avec expander "⚡ Impact & Taquinerie"
- [ ] `duckdb_repository.py` : méthode `load_friends_impact_data()` accessible
- [ ] Heatmap s'affiche correctement et colorée (FB 🟢, Finisseur 🟡, Boulet 🔴)
- [ ] Filtres (date, playlist, mode, map) appliqués (≥2 amis pour afficher)
- [ ] Ranking table s'affiche (MVP + Boulet badges)
- [ ] Traductions FR/EN complètes (`translations.py` mis à jour)
- [ ] Tests unitaires valident **absence** de Finisseur+Boulet (impossible ensemble)
- [ ] Tests unitaires valident **présence possible** de First Blood + Finisseur (même match court)
- [ ] Perf acceptable (<2s load pour 1000 matches)
- [ ] Docs (docstrings + PLAN_UNIFIE.md S12 section) à jour
- [ ] Commit message : `feat(coéquipiers): ajouter heatmap d'impact & taquinerie (S12)`

### 8.9 Points d'attention

- **Multi-bases DuckDB** : Charger données depuis base du joueur actif via `DuckDBRepository` (pas d'accès multi-files sinon)
- **Missing data** : Si `highlight_events` vide pour un match → aucun event affichable (OK logiquement)
- **Gamertag NULL** : Traiter avec `.coalesce("Unknown")` ou fallback
- **Perf heatmap cellules** : Limiter à top 10 amis pour lisibilité
- **Color cohérence** : Aligner avec palette existante `plot_win_ratio_heatmap()` si possible (GREEN #2ecc71, ORANGE #f39c12, RED #e74c3c)
- **Case-sensitivity xuid** : Coéquipiers peuvent être stockés en INT64 ou STRING — normaliser en INT64 avant join

### 8.10 Blockers / Risques

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| **highlight_events incomplète** | FB/Finisseur/Boulet non trouvables | Vérifier présence avec query testée en Dev |
| **outcome=NULL** | Boulet/Finisseur classification échoue | Filtrer `outcome IS NOT NULL` en analysis |
| **Performance 1000+ events** | UI freeze sur load | Implémenter lazy-loading si dépassement |
| **Multi-friends sélection** | UI trop chargée si >20 amis | Limiter heatmap à top 10 (configurable) |
| **Pandas residual** | Code referencing old DF patterns | Polars-only, pas de .to_pandas() hormis frontière Streamlit |

---

## Résumé — Effort par sprint

| Sprint | Effort estimé | Risque | Prêt ? |
|--------|--------------|--------|--------|
| **S6** | 7-9h | Minimal | **OUI** — fonctions réutilisables, données dispo |
| **S7** | 2.5-3j | Moyen | **CONDITIONNEL** — 2 migrations Pandas + 1 module à créer |
| **S8** | 3j | Faible | **OUI si S6-S7 livrés** — architecture teammates prête |
| **S9** | 4-5j | **ÉLEVÉ** | **CONDITIONNEL** — 35 fichiers Pandas, cache.py critique |
| **S10** | 2-3j | Moyen | **OUI** — backup, suppression, refactoring |
| **S11** | 3j | Faible | **OUI** — infrastructure CI/ruff/docs en place |
| **S12** | 10-13h (1.25-1.6j) | Faible | **OUI** — données disponibles, incompatibilités clarifiées |
