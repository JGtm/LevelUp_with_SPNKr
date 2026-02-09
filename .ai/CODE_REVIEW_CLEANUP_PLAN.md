# Plan de Revue de Code & Nettoyage Complet — LevelUp

> **Date** : 2026-02-09
> **Branche** : `feature/hybrid-data-architecture`
> **Auteur** : Audit automatisé (Claude Code)
> **Objectif** : Éliminer le code legacy, consolider les scripts, assainir l'architecture.

---

## Table des matières

1. [Diagnostic Global](#1-diagnostic-global)
2. [Axe 1 — Nettoyage des Scripts (112 fichiers)](#axe-1--nettoyage-des-scripts-112-fichiers)
3. [Axe 2 — Suppression du Code Legacy (`src/db/`)](#axe-2--suppression-du-code-legacy-srcdb)
4. [Axe 3 — Migration Pandas → Polars (38+ fichiers)](#axe-3--migration-pandas--polars-38-fichiers)
5. [Axe 4 — Éradication SQLite dans le code applicatif](#axe-4--éradication-sqlite-dans-le-code-applicatif)
6. [Axe 5 — Réorganisation de l'Architecture `src/`](#axe-5--réorganisation-de-larchitecture-src)
7. [Axe 6 — Nettoyage des Données et Fichiers Racine](#axe-6--nettoyage-des-données-et-fichiers-racine)
8. [Axe 7 — Nettoyage des Tests](#axe-7--nettoyage-des-tests)
9. [Axe 8 — Nettoyage de la Documentation `.ai/`](#axe-8--nettoyage-de-la-documentation-ai)
10. [Ordre d'Exécution Recommandé](#ordre-dexécution-recommandé)
11. [Checklist Finale](#checklist-finale)

---

## 1. Diagnostic Global

### Chiffres Clés

| Métrique | Valeur | Commentaire |
|----------|--------|-------------|
| Fichiers Python (src/) | ~140 | Dont ~20 dépréciés ou à nettoyer |
| Scripts (scripts/) | 112 | **~70 obsolètes ou redondants** |
| Violations Pandas | 38+ fichiers | Règle CLAUDE.md non respectée |
| Violations SQLite | 3 fichiers actifs | `aliases.py`, `queries.py`, `loaders_cached.py` |
| Modules dépréciés encore importés | 8 fichiers | `loaders.py`, `loaders_cached.py` |
| Implémentations dupliquées (load_matches) | 6 versions | Legacy + DuckDB + Cache + Bridge + Query |
| Taille données legacy (.db) | ~370 Mo | SQLite inutilisé en production |
| Fichiers JSON volumineux (racine) | ~224 Mo | `xuid_aliases.json` + `Playlist_modes_translations.json` |
| Documents .ai/ | 173+ fichiers | Beaucoup obsolètes |

### Problèmes Architecturaux Majeurs

1. **Double couche d'accès aux données** : `src/db/` (legacy SQLite) coexiste avec `src/data/repositories/` (DuckDB v4)
2. **Aucune application de la règle Pandas** : 38+ fichiers importent pandas malgré l'interdiction
3. **Scripts anarchiques** : 112 scripts sans organisation, dont ~70 sont des one-shots ou des doublons
4. **Enum zombie** : `RepositoryMode` conserve LEGACY/HYBRID/SHADOW qui lèvent des erreurs
5. **Modèle dupliqué** : `MatchRow` défini dans `src/models.py` ET `src/data/domain/models/match.py`

---

## Axe 1 — Nettoyage des Scripts (112 fichiers)

### 1.1 Structure Cible

```
scripts/
├── sync.py                          # Synchronisation (GARDER)
├── backfill_data.py                 # Backfill unifié (GARDER)
├── backup_player.py                 # Backup (GARDER)
├── restore_player.py                # Restore (GARDER)
├── archive_season.py                # Archivage saisons (GARDER)
├── generate_thumbnails.py           # Génération thumbnails (GARDER)
├── compute_sessions.py              # Calcul sessions (GARDER)
├── populate_antagonists.py          # Population antagonistes (GARDER)
├── populate_metadata_from_discovery.py  # Metadata Discovery (GARDER)
├── install_dependencies.py          # Installation dépendances (GARDER)
├── setup_env.ps1                    # Setup Windows (GARDER)
├── setup_env.sh                     # Setup Linux (GARDER)
├── migration/                       # Scripts de migration SQLite → DuckDB
│   ├── migrate_player_to_duckdb.py
│   ├── migrate_all_to_duckdb.py
│   ├── recover_from_sqlite.py
│   └── README.md                    # "À utiliser uniquement pour migration"
└── _archive/                        # Scripts historiques conservés pour référence
    └── README.md                    # "NE PAS UTILISER - archive uniquement"
```

### 1.2 Scripts à SUPPRIMER (redondants avec `backfill_data.py`)

> Règle CLAUDE.md #3 : toute fonctionnalité de backfill doit être dans `backfill_data.py`.

| Script | Raison de suppression | Déjà couvert par |
|--------|----------------------|-------------------|
| `backfill_medals.py` | Doublon | `backfill_data.py --medals` |
| `backfill_match_data.py` | Doublon | `backfill_data.py --all-data` |
| `backfill_metadata.py` | Doublon | `backfill_data.py --assets` |
| `backfill_null_metadata.py` | Doublon | `backfill_data.py --assets` |
| `backfill_killer_victim_pairs.py` | Doublon | `backfill_data.py --killer-victim` |
| `backfill_personal_score_awards.py` | Doublon partiel | Vérifier puis consolider |
| `backfill_teammates_signature.py` | Doublon partiel | Vérifier puis consolider |

### 1.3 Scripts à SUPPRIMER (corrections one-shot déjà appliquées)

| Script | Raison |
|--------|--------|
| `fix_null_metadata.py` | Fix appliqué, résolu dans `transformers.py` |
| `fix_null_metadata_all_players.py` | Variante du précédent |
| `fix_null_metadata_direct.py` | Variante du précédent |
| `fix_null_metadata_now.py` | Variante du précédent |
| `fix_null_metadata_streamlit.py` | Variante du précédent (hardcoded) |
| `fix_accuracy_column.py` | Fix appliqué |

### 1.4 Scripts à ARCHIVER dans `_archive/` (recherche terminée)

**Analyse binaire / film chunks** (recherche terminée, aucun résultat exploitable — cf. `.ai/API_LIMITATIONS.md`) :

| Script | Catégorie |
|--------|-----------|
| `analyze_all_type3_chunks.py` | Recherche binaire |
| `analyze_all_weapon_ids.py` | Recherche binaire |
| `analyze_binary_patterns.py` | Recherche binaire |
| `analyze_byte_shifting.py` | Recherche binaire |
| `analyze_chunk_with_hexdump.py` | Recherche binaire |
| `analyze_chunks_bitshifted.py` | Recherche binaire |
| `analyze_highlight_binary.py` | Recherche binaire |
| `analyze_player_kills_deaths.py` | Recherche binaire |
| `analyze_weapon_ids_by_player.py` | Recherche binaire |
| `analyze_with_offset_variations.py` | Recherche binaire |
| `batch_weapon_analysis.py` | Recherche binaire |
| `aggregate_weapon_ids.py` | Recherche binaire |
| `find_sixxt_kills_around_512.py` | Recherche binaire |
| `extract_binary_events.py` | Recherche binaire |
| `extract_events_v3.py` | Recherche binaire |
| `explore_killfeed_weapons.py` | Recherche killfeed |
| `investigate_killfeed_weapons.py` | Recherche killfeed |
| `investigate_killfeed_simple.py` | Recherche killfeed |
| `find_killer_victim_pairs.py` | Recherche kill pairs |
| `find_kill_patterns.py` | Recherche kill patterns |
| `correlate_kills.py` | Recherche corrélation |
| `find_events_by_type.py` | Recherche événements |
| `find_match_with_weapons.py` | Recherche armes |
| `find_specific_kill.py` | Recherche kills |
| `fetch_fiesta_weapons.py` | Recherche armes |

**Diagnostics one-shot** (problèmes résolus) :

| Script | Raison |
|--------|--------|
| `diagnose_null_metadata.py` | Résolu dans transformers.py |
| `diagnose_migration_gaps.py` | Migration terminée |
| `diagnose_first_kill_death.py` | Investigation terminée |
| `diagnose_first_kill_death_simple.py` | Investigation terminée |
| `diagnostic_critical_data.py` | One-shot |
| `diagnose_media_associations.py` | One-shot |
| `diagnose_media_indexing.py` | One-shot |

**Scripts de migration one-shot** (déplacer dans `migration/`) :

| Script | Raison |
|--------|--------|
| `migrate_highlight_events.py` | Migration terminée |
| `migrate_highlight_events_schema.py` | Migration terminée |
| `migrate_game_variant_category.py` | Migration terminée |
| `migrate_player_match_stats.py` | Migration terminée |
| `migrate_aliases_to_db.py` | Migration terminée |
| `migrate_add_columns.py` | Migration terminée |
| `migrate_metadata_to_duckdb.py` | Migration terminée |

**Tests/validations périmés** :

| Script | Raison |
|--------|--------|
| `validate_sprint1_metadata.py` | Sprint 1 terminé |
| `test_polars_integration.py` | Devrait être dans tests/ |
| `test_highlight_events_sync.py` | Devrait être dans tests/ |
| `test_media_library_fixes.py` | Devrait être dans tests/ |
| `test_media_library_keys.py` | Devrait être dans tests/ |
| `test_metadata_query.py` | Devrait être dans tests/ |
| `test_filter_persistence_by_player.py` | Devrait être dans tests/ |
| `validate_filter_state.py` | Devrait être dans tests/ |

**Outils legacy / one-shot** :

| Script | Raison |
|--------|--------|
| `spnkr_import_db.py` (1465 lignes) | Remplacé par `sync.py` + `DuckDBSyncEngine` |
| `ingest_halo_data.py` | Legacy SQLite, remplacé par sync |
| `merge_assets_to_unified.py` | Legacy : réf. `halo_unified.db` |
| `merge_databases.py` | One-shot |
| `generate_medals_fr.py` | One-shot (génération faite) |
| `generate_commendations_mapping.py` | One-shot (génération faite) |
| `extract_h5g_commendations_fr.py` | One-shot (Halo 5) |
| `download_career_rank_icons.py` | One-shot (icônes téléchargées) |
| `add_friend.py` | Legacy SQLite |
| `cleanup_codebase.py` | Ironiquement obsolète lui-même |
| `smart_test.py` | Utiliser pytest directement |
| `benchmark_polars.py` | One-shot de benchmark |
| `compute_historical_performance.py` | Legacy SQLite |

### 1.5 Scripts `_obsolete/` existants à SUPPRIMER

| Script | Raison |
|--------|--------|
| `_obsolete/migrate_to_cache.py` | Totalement obsolète (SQLite MatchCache) |
| `_obsolete/migrate_to_parquet.py` | Totalement obsolète (ShadowRepository) |

### 1.6 Résumé de l'impact

| Action | Nombre de scripts | Avant | Après |
|--------|-------------------|-------|-------|
| Garder (production) | ~12 | — | 12 |
| Déplacer dans `migration/` | ~10 | — | 10 |
| Archiver dans `_archive/` | ~50 | — | 50 |
| Supprimer | ~40 | — | 0 |
| **Total** | **112** | **112 dans scripts/** | **~22 actifs** |

---

## Axe 2 — Suppression du Code Legacy (`src/db/`)

### 2.1 État Actuel

Le dossier `src/db/` est **entièrement déprécié** selon CLAUDE.md, mais encore activement importé :

| Fichier | Lignes | Importé par | Action |
|---------|--------|-------------|--------|
| `loaders.py` | 1664 | 8 fichiers | **SUPPRIMER** après migration des importeurs |
| `loaders_cached.py` | 535 | 5 fichiers | **SUPPRIMER** après migration |
| `connection.py` | ~200 | loaders, loaders_cached | **SUPPRIMER** avec les loaders |
| `queries.py` | ~150 | loaders, loaders_cached | **SUPPRIMER** (contient `sqlite_master`) |
| `schema.py` | ~200 | loaders, sync | **SUPPRIMER** ou migrer dans `data/` |
| `parsers.py` | ~150 | loaders, sync, UI | **Évaluer** : fonctions utiles à migrer ? |
| `profiles.py` | ~200 | loaders, app | **Évaluer** : peut-être garder si pas de doublon |
| `__init__.py` | ~30 | Re-exporte tout | **SUPPRIMER** |

### 2.2 Plan de Migration des Importeurs

Chaque fichier qui importe depuis `src/db/` doit être mis à jour :

| Fichier importeur | Importe depuis `src/db/` | Remplacer par |
|-------------------|--------------------------|---------------|
| `src/ui/cache.py` | 15+ fonctions de loaders | `DuckDBRepository` + requêtes directes |
| `src/ui/pages/match_view_players.py` | `load_match_players_stats` | `DuckDBRepository.load_match_rosters()` |
| `src/analysis/killer_victim.py` | `MatchPlayerStats` (TYPE_CHECKING) | Modèle Pydantic de `src/data/domain/` |
| `src/app/data_loader.py` | Utilitaires path/XUID | `src/config.py` ou `src/utils/paths.py` |
| `src/app/state.py` | XUID/path parsing | `src/config.py` |
| `scripts/sync.py` | Fonctions loaders | `DuckDBSyncEngine` |
| `scripts/populate_antagonists.py` | Fonctions loaders | `DuckDBRepository` |
| `src/db/__init__.py` | Re-export | Supprimer le dossier |

### 2.3 Fonctions Utilitaires à Sauvegarder

Avant de supprimer `src/db/`, vérifier si ces fonctions ont un équivalent dans `src/data/` :

- `_sanitize_gamertag()` → déplacer dans `src/utils/` si pas d'équivalent
- `get_db_path()` → probablement dans `src/config.py`
- `load_match_player_gamertags()` → vérifier `DuckDBRepository`
- Fonctions de parsing de `parsers.py` → évaluer une par une

### 2.4 Étapes d'Exécution

1. **Lister toutes les fonctions** de `src/db/loaders.py` utilisées ailleurs (grep exhaustif)
2. **Mapper chaque fonction** vers son équivalent DuckDB dans `duckdb_repo.py`
3. **Migrer les importeurs** un par un, en testant après chaque migration
4. **Extraire les utilitaires orphelins** vers `src/utils/`
5. **Supprimer `src/db/`** entièrement
6. **Nettoyer `src/db/__init__.py`** et tous les re-exports

---

## Axe 3 — Migration Pandas → Polars (38+ fichiers)

### 3.1 Fichiers Concernés par Couche

#### Couche Visualisation (priorité BASSE — frontière Plotly)

> Note : Plotly accepte nativement les DataFrames Polars depuis Plotly 5.16.
> Convertir `.to_pandas()` uniquement si strictement nécessaire.

| Fichier | Import pandas | Action |
|---------|---------------|--------|
| `src/visualization/trio.py` | L3 | Remplacer par Polars |
| `src/visualization/timeseries.py` | L3 | Remplacer par Polars |
| `src/visualization/distributions.py` | L6 | Remplacer par Polars |
| `src/visualization/match_bars.py` | L11 | Remplacer par Polars |
| `src/visualization/maps.py` | L3 | Remplacer par Polars |
| `src/visualization/performance.py` | - | Vérifier |
| `src/visualization/antagonist_charts.py` | - | Vérifier |

#### Couche UI/App (priorité HAUTE — code applicatif)

| Fichier | Import pandas | Action |
|---------|---------------|--------|
| `src/app/kpis.py` | L13 | Migrer vers Polars |
| `src/app/helpers.py` | L10 | Migrer vers Polars |
| `src/app/filters_render.py` | L15 | Migrer vers Polars |
| `src/app/filters.py` | L15 | Migrer vers Polars |
| `src/app/page_router.py` | L13 | Migrer vers Polars |
| `src/app/kpis_render.py` | L13 | Migrer vers Polars |
| `src/ui/cache.py` | L28 | Migrer vers Polars |
| `src/ui/formatting.py` | L15 | Migrer vers Polars |
| `src/ui/commendations.py` | L20 | Migrer vers Polars |
| `src/ui/perf.py` | L14 | Migrer vers Polars |
| `src/data/integration/streamlit_bridge.py` | L21 | Migrer vers Polars |

#### Couche UI Pages (priorité HAUTE)

| Fichier | Import pandas |
|---------|---------------|
| `src/ui/pages/win_loss.py` | L8 |
| `src/ui/pages/timeseries.py` | L8 |
| `src/ui/pages/teammates_helpers.py` | L11 |
| `src/ui/pages/teammates_charts.py` | L8 |
| `src/ui/pages/last_match.py` | L13 |
| `src/ui/pages/teammates.py` | L8 |
| `src/ui/pages/citations.py` | L7 |
| `src/ui/pages/session_compare.py` | L11 |
| `src/ui/pages/media_library.py` | L30 |
| `src/ui/pages/match_view.py` | L16 |
| `src/ui/pages/match_view_helpers.py` | L12 |
| `src/ui/pages/match_view_charts.py` | L5 |
| `src/ui/pages/match_view_participation.py` | L14 |
| `src/ui/pages/match_history.py` | L15 |
| `src/ui/components/performance.py` | L11 |
| `src/ui/components/chart_annotations.py` | L10 |

#### Couche Analysis (priorité MOYENNE — fonctions dupliquées pandas/polars)

| Fichier | Import pandas | Doublons |
|---------|---------------|----------|
| `src/analysis/killer_victim.py` | L26 | `killer_victim_counts_long()` (pd) vs `_polars()` |
| `src/analysis/stats.py` | L5 | Rolling means pandas |
| `src/analysis/sessions.py` | L15 | `compute_sessions()` (pd) vs `_polars()` |
| `src/analysis/maps.py` | L3 | À migrer |
| `src/analysis/performance_score.py` | L8 | À migrer |

### 3.2 Stratégie de Migration

1. **Supprimer les doublons** : Pour les fonctions `_polars()`, renommer en version principale et supprimer la version pandas
2. **Migrer couche par couche** : Analysis → App → UI Pages → Visualization
3. **Règle de frontière** : `.to_pandas()` autorisé UNIQUEMENT pour `st.dataframe()` et certains composants Streamlit qui l'exigent
4. **Tests** : Chaque migration doit passer les tests existants

### 3.3 Points de Vigilance

- `st.dataframe()` accepte Polars nativement depuis Streamlit 1.28+
- `st.bar_chart()`, `st.line_chart()` acceptent Polars nativement
- Plotly `px.bar()`, `px.line()` etc. acceptent Polars depuis Plotly 5.16+
- Seuls certains widgets obscurs nécessitent `.to_pandas()`

---

## Axe 4 — Éradication SQLite dans le Code Applicatif

### 4.1 Violations Actives (code applicatif — CRITIQUE)

| Fichier | Lignes | Problème | Action |
|---------|--------|----------|--------|
| `src/ui/aliases.py` | L61, L64, L67 | `sqlite3.connect()` + `sqlite_master` | Réécrire avec DuckDB |
| `src/db/queries.py` | L93 | `HAS_TABLE` utilise `sqlite_master` | Supprimer (Axe 2) |
| `src/db/loaders_cached.py` | L42, L54 | `sqlite3` + `sqlite_master` | Supprimer (Axe 2) |
| `src/data/infrastructure/database/sqlite_metadata.py` | L17 | Module SQLite metadata | Supprimer ou migrer |

### 4.2 `sqlite_master` → `information_schema.tables`

Tous les usages de `sqlite_master` doivent être remplacés par :

```sql
-- AVANT (SQLite)
SELECT name FROM sqlite_master WHERE type='table' AND name=?

-- APRÈS (DuckDB)
SELECT table_name FROM information_schema.tables
WHERE table_name = ? AND table_schema = 'main'
```

### 4.3 Fichiers Legacy SQLite à Nettoyer

| Fichier | Lignes | Action |
|---------|--------|--------|
| `src/config.py` | L62 | Supprime la recherche de fichiers `.db` |
| `src/db/profiles.py` | L108, L121 | `list_local_dbs()` cherche des `.db` — migrer vers `.duckdb` |

---

## Axe 5 — Réorganisation de l'Architecture `src/`

### 5.1 Problèmes Identifiés

1. **`src/db/`** : Dossier entier déprécié, toujours présent et importé
2. **`src/models.py`** : Modèle `MatchRow` dupliqué dans `src/data/domain/models/match.py`
3. **`RepositoryMode` enum** : Conserve 4 modes zombies (LEGACY, HYBRID, SHADOW, SHADOW_COMPARE)
4. **`src/data/infrastructure/database/sqlite_metadata.py`** : Module SQLite dans l'infrastructure
5. **Manque de clarté** : `src/ui/cache.py` (1332 lignes) fait trop de choses

### 5.2 Actions

| Action | Fichier | Détail |
|--------|---------|--------|
| Supprimer dossier | `src/db/` | Après migration des importeurs (Axe 2) |
| Supprimer modèle dupliqué | `src/models.py` | Garder uniquement `src/data/domain/models/match.py` |
| Nettoyer enum | `src/data/repositories/factory.py` | Supprimer LEGACY, HYBRID, SHADOW, SHADOW_COMPARE |
| Supprimer module | `src/data/infrastructure/database/sqlite_metadata.py` | Plus utilisé en v4 |
| Nettoyer docstrings | `src/data/repositories/protocol.py` | Supprimer références aux repos supprimés |
| Nettoyer bridge | `src/data/integration/streamlit_bridge.py` | Supprimer fonctions @deprecated |
| Évaluer | `src/ui/cache.py` | Refactoriser si possible (1332 lignes) |

### 5.3 Architecture Cible `src/`

```
src/
├── __init__.py
├── config.py                          # Configuration globale
├── utils/
│   └── paths.py                       # + fonctions extraites de db/
├── analysis/                          # Logique métier (Polars uniquement)
│   ├── antagonists.py
│   ├── killer_victim.py               # Version Polars uniquement
│   ├── sessions.py                    # Version Polars uniquement
│   ├── performance_score.py
│   ├── mode_categories.py
│   ├── maps.py
│   ├── cumulative.py
│   └── stats.py                       # Version Polars uniquement
├── app/                               # Orchestration Streamlit
│   ├── data_loader.py
│   ├── filters.py / filters_render.py
│   ├── helpers.py
│   ├── kpis.py / kpis_render.py
│   ├── sidebar.py
│   ├── state.py
│   └── routing.py
├── data/                              # Couche données
│   ├── domain/                        # Modèles Pydantic
│   ├── infrastructure/                # DuckDB engine (SANS sqlite_metadata.py)
│   ├── repositories/                  # DuckDB repo (SANS modes zombies)
│   ├── sync/                          # Moteur de synchronisation
│   ├── query/                         # Requêtes analytiques
│   └── integration/                   # Streamlit bridge (SANS @deprecated)
├── ui/                                # Interface utilisateur
│   ├── pages/                         # Pages Streamlit
│   ├── components/                    # Composants réutilisables
│   └── [modules UI]
├── visualization/                     # Graphiques Plotly
└── ai/                                # MCP + RAG
```

**Supprimé** : `src/db/` entièrement, `src/models.py`

---

## Axe 6 — Nettoyage des Données et Fichiers Racine

### 6.1 Fichiers de Données Legacy

| Fichier | Taille | Action |
|---------|--------|--------|
| `data/halo_unified.db` | 149 Mo | **SUPPRIMER** — DB SQLite unifiée legacy |
| `data/spnkr_gt_Chocoboflor.db` | 15 Mo | **SUPPRIMER** — Migration DuckDB terminée |
| `data/spnkr_gt_JGtm.db` | 62 Mo | **SUPPRIMER** — Migration DuckDB terminée |
| `data/spnkr_gt_Madina97294.db` | 121 Mo | **SUPPRIMER** — Migration DuckDB terminée |
| `data/spnkr_gt_XxDaemonGamerxX.db` | 17 Mo | **SUPPRIMER** — Migration DuckDB terminée |
| `data/investigation/` | 216 Mo | **SUPPRIMER** — Recherche binaire terminée, non exploitable |

> **Libération estimée : ~580 Mo**

> **ATTENTION** : Faire un **backup complet** avant toute suppression de fichiers `.db`. Vérifier que les données sont bien présentes dans les DuckDB respectifs.

### 6.2 Fichiers JSON Volumineux (Racine)

| Fichier | Taille | Action |
|---------|--------|--------|
| `xuid_aliases.json` | 180 Mo | **Déplacer** dans `data/` ou `data/warehouse/` |
| `Playlist_modes_translations.json` | 44 Mo | **Déplacer** dans `data/` ou `data/warehouse/` |

### 6.3 Fichiers Racine à Évaluer

| Fichier | Action |
|---------|--------|
| `openspartan_launcher.py` | Garder (CLI launcher principal) |
| `.cursorrules` | Évaluer si encore nécessaire (doublon avec CLAUDE.md ?) |
| `activate_env.sh` | Garder |
| `run.sh` | Garder |

---

## Axe 7 — Nettoyage des Tests

### 7.1 Tests Liés au Code Legacy

| Fichier test | Teste | Action |
|-------------|-------|--------|
| `test_cache_optimization.py` | SQLite MatchCache | **SUPPRIMER** — MatchCache SQLite n'existe plus |
| `test_cache_integrity.py` | SQLite MatchCache | **SUPPRIMER** — Idem |
| `test_match_player_gamertags.py` | `loaders.load_match_player_gamertags` | **SUPPRIMER** ou migrer vers DuckDB |
| `test_gamertag_sanitize.py` | `loaders._sanitize_gamertag` | **Migrer** — tester la fonction dans son nouveau module |
| `test_parsers.py` | `src/db/parsers.py` | **Évaluer** — les parsers sont-ils encore utilisés ? |
| `test_query_module.py` | Crée un fichier `.db` pour test | **SUPPRIMER** ou réécrire pour DuckDB |

### 7.2 Tests avec Imports Pandas

| Fichier test | Action |
|-------------|--------|
| `test_analysis.py` | Migrer pandas → polars |
| `test_app_phase2.py` | Migrer pandas → polars |
| `test_performance_score.py` | Migrer pandas → polars |
| `test_polars_migration.py` | Nettoyer les try-except pandas |
| `test_session_compare_hist_avg_category.py` | Migrer pandas → polars |
| `test_timeseries_performance_score.py` | Migrer pandas → polars |
| `test_visualizations.py` | Migrer pandas → polars |

### 7.3 Scripts de Test dans `scripts/` à Déplacer

| Script actuel | Destination |
|--------------|-------------|
| `scripts/test_polars_integration.py` | `tests/test_polars_integration.py` |
| `scripts/test_highlight_events_sync.py` | `tests/test_highlight_events_sync.py` |
| `scripts/test_media_library_fixes.py` | `tests/test_media_library_fixes.py` |
| `scripts/test_media_library_keys.py` | `tests/test_media_library_keys.py` |
| `scripts/test_metadata_query.py` | `tests/test_metadata_query.py` |
| `scripts/test_filter_persistence_by_player.py` | `tests/test_filter_persistence.py` |
| `scripts/validate_filter_state.py` | `tests/test_filter_state_validation.py` |
| `scripts/validate_refdata_integrity.py` | `tests/test_refdata_integrity.py` |
| `scripts/verify_accuracy_extraction.py` | `tests/test_accuracy_extraction.py` |
| `scripts/verify_backfill_logic.py` | `tests/test_backfill_logic.py` |

---

## Axe 8 — Nettoyage de la Documentation `.ai/`

### 8.1 Constats

Le dossier `.ai/` contient **173+ fichiers** accumulés sur plusieurs mois. Beaucoup sont obsolètes :
- Plans de sprints terminés
- Diagnostics de bugs corrigés
- Recherches binaires abandonnées
- Multiples versions de plans et audits

### 8.2 Actions

1. **Garder à la racine de `.ai/`** (documents vivants) :
   - `project_map.md` — Cartographie du projet (à mettre à jour après nettoyage)
   - `thought_log.md` — Journal des décisions
   - `data_lineage.md` — Flux de données
   - `ARCHITECTURE_ROADMAP.md` — Roadmap architecture
   - `CONSOLIDATED_AUDITS_AND_ROADMAP.md` — Audits consolidés
   - `API_LIMITATIONS.md` — Limitations API connues
   - Ce fichier (`CODE_REVIEW_CLEANUP_PLAN.md`)

2. **Archiver le reste** dans `.ai/archive/` avec un sous-dossier daté :
   - `.ai/archive/2026-02/` — Tout ce qui est obsolète
   - Garder un `README.md` dans l'archive expliquant le contenu

3. **Supprimer les audits individuels** devenus redondants avec le fichier consolidé :
   - `PANDAS_TO_POLARS_AUDIT.md` → Fusionné dans CONSOLIDATED
   - `SQLITE_TO_DUCKDB_AUDIT.md` → Fusionné dans CONSOLIDATED

4. **Mettre à jour** les documents survivants après le nettoyage

---

## Ordre d'Exécution Recommandé

### Phase A — Préparation (0 risque)

| # | Action | Risque | Effort |
|---|--------|--------|--------|
| A1 | Backup complet des données (`backup_player.py` pour chaque joueur) | Nul | Faible |
| A2 | Commit/tag de l'état actuel avant nettoyage | Nul | Faible |
| A3 | Archiver les docs `.ai/` obsolètes | Nul | Faible |

### Phase B — Nettoyage des Scripts (impact faible)

| # | Action | Risque | Effort |
|---|--------|--------|--------|
| B1 | Créer `scripts/migration/` et `scripts/_archive/` | Nul | Faible |
| B2 | Déplacer les scripts de migration dans `scripts/migration/` | Nul | Faible |
| B3 | Déplacer les scripts de recherche/one-shot dans `scripts/_archive/` | Nul | Faible |
| B4 | Supprimer les backfill redondants et les fix one-shot | Faible | Faible |
| B5 | Supprimer `scripts/_obsolete/` | Nul | Faible |
| B6 | Vérifier que les tests de `scripts/test_*` ont des équivalents dans `tests/` avant de déplacer | Faible | Moyen |

### Phase C — Suppression de `src/db/` (impact moyen)

| # | Action | Risque | Effort |
|---|--------|--------|--------|
| C1 | Lister toutes les fonctions de `src/db/loaders.py` réellement utilisées | Nul | Moyen |
| C2 | Mapper chaque fonction vers son équivalent DuckDB | Nul | Moyen |
| C3 | Migrer `src/ui/cache.py` (le plus gros importeur) | Moyen | Élevé |
| C4 | Migrer `src/ui/pages/match_view_players.py` | Moyen | Moyen |
| C5 | Migrer `scripts/sync.py` | Moyen | Moyen |
| C6 | Migrer les autres importeurs (5 fichiers) | Faible | Moyen |
| C7 | Extraire les utilitaires orphelins vers `src/utils/` | Faible | Faible |
| C8 | Supprimer `src/db/` | Faible | Faible |
| C9 | Supprimer `src/models.py` (doublon) | Faible | Faible |
| C10 | Nettoyer `RepositoryMode` enum | Faible | Faible |
| C11 | Lancer `pytest tests/ -v` — corriger les régressions | Moyen | Variable |

### Phase D — Migration Pandas → Polars (impact élevé)

| # | Action | Risque | Effort |
|---|--------|--------|--------|
| D1 | Supprimer les fonctions `_polars()` dupliquées dans `src/analysis/` | Moyen | Moyen |
| D2 | Migrer `src/app/` (6 fichiers) | Moyen | Élevé |
| D3 | Migrer `src/ui/pages/` (14 fichiers) | Élevé | Très élevé |
| D4 | Migrer `src/ui/` modules (4 fichiers) | Moyen | Élevé |
| D5 | Migrer `src/visualization/` (5 fichiers) | Moyen | Élevé |
| D6 | Migrer `src/data/integration/streamlit_bridge.py` | Moyen | Moyen |
| D7 | Migrer les tests | Moyen | Moyen |
| D8 | Lancer `pytest tests/ -v` — corriger les régressions | Moyen | Variable |
| D9 | Ajouter un lint CI (ruff rule) pour bloquer `import pandas` | Nul | Faible |

### Phase E — Éradication SQLite (impact faible après Phase C)

| # | Action | Risque | Effort |
|---|--------|--------|--------|
| E1 | Réécrire `src/ui/aliases.py` sans SQLite | Faible | Moyen |
| E2 | Supprimer `src/data/infrastructure/database/sqlite_metadata.py` | Faible | Faible |
| E3 | Nettoyer `src/config.py` (recherche `.db`) | Faible | Faible |
| E4 | Nettoyer `src/db/profiles.py` ou le déplacer | Faible | Faible |

### Phase F — Nettoyage Données (libérer 580+ Mo)

| # | Action | Risque | Effort |
|---|--------|--------|--------|
| F1 | Vérifier que toutes les données sont dans DuckDB (contrôle croisé) | Nul | Moyen |
| F2 | Supprimer les `.db` legacy dans `data/` | Moyen | Faible |
| F3 | Supprimer `data/investigation/` | Faible | Faible |
| F4 | Déplacer les gros JSON dans `data/` | Faible | Faible |

### Phase G — Nettoyage Tests & Finalisation

| # | Action | Risque | Effort |
|---|--------|--------|--------|
| G1 | Supprimer les tests legacy SQLite | Faible | Faible |
| G2 | Migrer tests pandas → polars | Moyen | Moyen |
| G3 | Mettre à jour `project_map.md` | Nul | Faible |
| G4 | Mettre à jour `CLAUDE.md` (supprimer refs aux modules supprimés) | Nul | Faible |
| G5 | Mettre à jour `CONSOLIDATED_AUDITS_AND_ROADMAP.md` | Nul | Faible |
| G6 | Lancer `pytest tests/ -v` — validation finale | Nul | Faible |
| G7 | Tag git `v4.0-clean` | Nul | Nul |

---

## Checklist Finale

Après exécution de toutes les phases, vérifier :

- [ ] `scripts/` contient uniquement ~22 scripts actifs + `migration/` + `_archive/`
- [ ] `src/db/` n'existe plus
- [ ] `src/models.py` n'existe plus (utiliser `src/data/domain/models/`)
- [ ] `RepositoryMode` ne contient que `DUCKDB`
- [ ] Aucun `import pandas` dans le code applicatif (hors `TYPE_CHECKING` et `.to_pandas()` à la frontière)
- [ ] Aucun `import sqlite3` dans le code applicatif (hors `scripts/migration/`)
- [ ] Aucun `sqlite_master` dans le code applicatif
- [ ] Aucun fichier `.db` dans `data/` (hors `scripts/migration/` qui les lit)
- [ ] `data/investigation/` supprimé
- [ ] Gros JSON déplacés dans `data/`
- [ ] `.ai/` nettoyé : ~10 fichiers vivants + archive datée
- [ ] `pytest tests/ -v` passe à 100%
- [ ] `CLAUDE.md` à jour (sections "Code Déprécié" vidées)
- [ ] Tag git `v4.0-clean` créé

---

> **Estimation d'effort total** : Ce plan représente un chantier significatif.
> **Recommandation** : Exécuter phase par phase, avec un commit entre chaque phase.
> Les phases A-B sont sans risque et libèrent immédiatement de la clarté.
> La phase D (Pandas → Polars) est la plus lourde et peut être étalée.
