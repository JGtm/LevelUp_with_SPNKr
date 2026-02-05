# Audits et Roadmap Consolidés — LevelUp

> **Date** : 2026-02-05  
> Ce fichier regroupe les audits de migration en cours et remplace les plans dispersés.
> Les plans et analyses déjà traités sont archivés dans `.ai/archive/plans_treated_2026-02/`.

---

## Table des matières

1. [Audit SQLite → DuckDB](#1-audit-sqlite--duckdb)
2. [Audit Pandas → Polars](#2-audit-pandas--polars)
3. [Plans archivés (référence)](#3-plans-archivés-référence)
4. [Priorités actuelles](#4-priorités-actuelles)
5. [À analyser / planifier](#5-à-analyser--planifier)
6. [Colonne end_time (match_stats)](#6-colonne-end_time-match_stats)

---

## 1. Audit SQLite → DuckDB

> **Règle projet** : SQLite est **PROSCRIT**. Tout le code applicatif doit utiliser DuckDB v4.
> **Source détaillée** : `.ai/SQLITE_TO_DUCKDB_AUDIT.md`

### Résumé

| Catégorie | Fichiers | Action |
|-----------|----------|--------|
| **À migrer vers DuckDB** | scripts, src/db, src/ui | Remplacer SQLite par DuckDB / `DuckDBRepository` |
| **Scripts migration** | `recover_from_sqlite.py`, `migrate_player_to_duckdb.py` | Garder SQLite en lecture seule (migration only) |
| **Déprécié** | `src/db/loaders.py`, `src/db/connection.py` | Remplacer par DuckDB, puis supprimer |
| **Tests** | `test_cache_integrity.py` | Adapter pour DuckDB |

### Fichiers clés

| Fichier | Action |
|---------|--------|
| `scripts/sync.py` | Sync uniquement sur `stats.duckdb`, supprimer branches SQLite |
| `src/db/connection.py` | Support DuckDB uniquement, refuser `.db` |
| `src/db/loaders.py` | Supprimer branche SQLite dans `has_table()` |
| `src/ui/multiplayer.py` | Supprimer `_get_sqlite_connection()` |
| `src/ui/sync.py` | Refuser `.db`, uniquement DuckDB |
| Scripts : `validate_refdata_integrity`, `refetch_film_roster`, `migrate_*` | `sqlite_master` → `information_schema.tables` |

---

## 2. Audit Pandas → Polars

> **Règle projet** : **Pandas est PROSCRIT.** Utiliser **Polars** uniquement pour DataFrames et séries (CLAUDE.md).
> **Source détaillée** : `.ai/PANDAS_TO_POLARS_AUDIT.md`

### Résumé

| Catégorie | Fichiers | Action |
|-----------|----------|--------|
| **À migrer vers Polars** | src/visualization, src/analysis, src/ui, src/app | Remplacer `pd.DataFrame` par `pl.DataFrame` |
| **Couche données** | cache.py, data_loader.py | Retourner Polars au lieu de convertir en Pandas |
| **Points de conversion** | Streamlit, Plotly | `to_pandas()` uniquement aux frontières UI |
| **Tests** | test_*.py | Fixtures Polars, adapter assertions |
| **Scripts** | scripts/*.py | Migrer si traitement de données |

### Ordre de migration recommandé

1. **Couche données** : `load_df_optimized`, `cached_load_*` → `pl.DataFrame`
2. **Analyses** : `sessions.py`, `killer_victim.py` → supprimer versions Pandas
3. **Visualisations** : `timeseries.py`, `distributions.py` → accepter Polars
4. **Pages UI** : migrer page par page
5. **Tests** : fixtures et assertions Polars
6. **Scripts** : migrer les scripts de traitement

### Équivalences principales

| Pandas | Polars |
|--------|--------|
| `pd.to_datetime(col)` | `pl.col("col").str.to_datetime()` |
| `pd.to_numeric(col, errors="coerce")` | `pl.col("col").cast(pl.Float64)` |
| `df.rolling(window).mean()` | `pl.col("col").rolling_mean(window_size=window)` |
| `pd.merge_asof(a, b)` | `a.join_asof(b)` |
| `df.groupby().agg()` | `df.group_by().agg()` |

---

## 3. Plans archivés (référence)

Les plans et analyses suivants ont été traités ou sont obsolètes. Ils sont archivés dans `.ai/archive/plans_treated_2026-02/`.

### Sprints

| Fichier | Statut | Notes |
|---------|--------|------|
| `SPRINT_DATA_RECOVERY_PLAN.md` | Traité | Récupération xuid_aliases, match_participants, killer_victim_pairs |
| `SPRINT_GAMERTAG_ROSTER_FIX.md` | Traité | Table match_participants, resolve_gamertag, backfill |
| `SPRINT_REGRESSIONS_FIX.md` | Partiellement traité | Cache.py, données, régressions |
| `PLAN_FIX_SESSIONS_ADVANCED.md` | En attente | Logique sessions (gap + teammates_signature) |
| `LOGIC_LEGACY_SESSIONS.md` | Référence | Documentation logique legacy |
| `FIX_ENEMY_MMR.md` | Traité | enemy_mmr depuis TeamMmrs |
| `REGRESSIONS_FIX_FINAL.md` | Traité | Corrections régressions |
| `REGRESSIONS_FIX_SUMMARY.md` | Traité | Résumé |
| `DELTA_MODE_EXPLANATION.md` | Documentation | Mode delta sync |

### Diagnostics

| Fichier | Statut |
|---------|--------|
| `CORRECTIONS_APPLIQUEES_2026-02-05.md` | Appliqué |
| `CORRECTIONS_NULL_METADATA_2026-02-05.md` | Appliqué |
| `CRITICAL_DATA_MISSING_2026-02-05.md` | Appliqué |
| `DERNIER_MATCH_*.md` | Appliqué |
| `FIRST_KILL_DEATH_*.md` | Appliqué (LOWER event_type) |
| `FIX_*.md`, `NULL_METADATA_*.md` | Appliqué |
| `REGRESSIONS_ANALYSIS_2026-02-03.md` | Traité |
| `ROOT_CAUSE_FIXED.md` | Traité |
| `MEDIA_LIBRARY_*.md` | Appliqué |

### Exploration / Features

| Fichier | Statut |
|---------|--------|
| `CRITICAL_DATA_MISSING_EXPLORATION.md` | Diagnostic terminé, correction Discovery UGC en attente |
| `correction_plan_2026-02-02.md` | Appliqué |
| `cleanup_report.md` | Appliqué |
| `test_visualizations_plan.md` | Appliqué (74 tests) |

---

## 4. Priorités actuelles

D’après la synthèse des plans :

| Priorité | Tâche | Fichier(s) |
|----------|-------|------------|
| **Critique** | Données manquantes (noms cartes, modes) | Discovery UGC, metadata.duckdb |
| **Haute** | Logique sessions (teammates_signature) | PLAN_FIX_SESSIONS_ADVANCED |
| **Haute** | Audit SQLite → DuckDB | Voir §1 |
| **Moyenne** | Audit Pandas → Polars | Voir §2 |
| **Basse** | enemy_mmr (si non traité) | transform_skill_stats |

---

## 5. À analyser / planifier

Éléments à étudier et à planifier avant mise en œuvre.

### Mémorisation des filtres par joueur

| Élément | Description |
|--------|--------------|
| **Objectif** | Se souvenir des filtres activés/désactivés pour le joueur sélectionné (persistance par gamertag). |
| **À analyser** | Où sont définis les filtres (sidebar, pages), quel état est pertinent (modes, cartes, plage de dates, etc.), et où persister (session, `app_settings.json`, ou stockage par joueur dans `data/players/{gamertag}/` ou profil utilisateur). |
| **À planifier** | Spécification du format de stockage, chargement au changement de joueur, mise à jour à chaque modification des filtres, impact sur l’URL/query params si pertinent. |
| **Fichiers probables** | UI Streamlit (sidebar, pages avec filtres), éventuel module settings ou state par joueur. |

---

## 6. Colonne end_time (match_stats)

**Objectif** : Ajouter une colonne `end_time` (heure de fin du match) dans `match_stats`, dérivée de `start_time + time_played_seconds`, pour simplifier requêtes et affichages (médias, fenêtres temporelles, etc.).

### Planification

| Élément | Détail |
|--------|--------|
| **Colonne** | `end_time TIMESTAMP` (nullable si `time_played_seconds` manquant). |
| **Calcul** | `end_time = start_time + (time_played_seconds || ' seconds')::INTERVAL` (DuckDB) ou en Python `start_time + timedelta(seconds=time_played_seconds or 0)`. |
| **Sync / refresh** | Lors de l’insertion ou du remplacement d’une ligne dans `match_stats`, calculer et persister `end_time` en plus de `start_time` et `time_played_seconds`. |
| **Fichiers à modifier** | `src/data/sync/models.py` (ajouter `end_time` à `MatchStatsRow`), `src/data/sync/transformers.py` (calculer `end_time` dans `transform_match_stats`), `src/data/sync/engine.py` (création/migration de la colonne, inclusion dans `_insert_match_row`). |
| **Backfill** | Option `--end-time` dans `scripts/backfill_data.py` : mettre à jour `end_time` pour les lignes où `end_time IS NULL` (ou pour toutes les lignes avec `--force-end-time`). Requête type : `UPDATE match_stats SET end_time = start_time + (time_played_seconds || ' seconds')::INTERVAL WHERE end_time IS NULL AND start_time IS NOT NULL AND time_played_seconds IS NOT NULL`. |
| **Documentation** | Mettre à jour `docs/SQL_SCHEMA.md` et `.ai/data_lineage.md` pour documenter `end_time`. |

### Statut

- [x] Modèle et transformers (calcul end_time)
- [x] Engine : CREATE TABLE + migration ADD COLUMN + _insert_match_row
- [x] backfill_data.py : --end-time, --force-end-time, logique de backfill
- [x] Docs : SQL_SCHEMA.md (data_lineage optionnel)
- [x] **Backfill exécuté** : end_time rempli sur les données existantes

**Tâche terminée.**

---

## Fichiers source des audits

- **SQLite → DuckDB** : `.ai/SQLITE_TO_DUCKDB_AUDIT.md`
- **Pandas → Polars** : `.ai/PANDAS_TO_POLARS_AUDIT.md`
- **Roadmap architecture** : `.ai/ARCHITECTURE_ROADMAP.md`
- **Journal des décisions** : `.ai/thought_log.md`

---

*Dernière mise à jour : 2026-02-05 (§6 end_time : tâche terminée, backfill exécuté)*
