# Exploration complète du projet LevelUp

> **Date** : 2026-02-05  
> Document d’exploration « refait » de tout le projet : structure, modules, scripts, tests, docs.

---

## 1. Vue d’ensemble

| Élément | Détail |
|--------|--------|
| **Nom** | LevelUp (OpenSpartan-graph) |
| **Type** | Dashboard Streamlit de statistiques Halo Infinite |
| **Version** | 3.0.0 (pyproject.toml) |
| **Python** | >=3.10 |
| **Stack** | DuckDB, Polars, Pydantic v2, Streamlit, SPNKr API |
| **Point d’entrée** | `streamlit run streamlit_app.py` |
| **Lanceur CLI** | `launcher.py` |

**Règles critiques** (voir CLAUDE.md) :
- SQLite **interdit** en applicatif ; DuckDB v4 uniquement (sauf scripts de migration qui lisent l’ancien SQLite).
- Chargement multi-joueurs : ne jamais utiliser `load_df_optimized(db_path, teammate_xuid)` pour un coéquipier ; utiliser `_load_teammate_stats_from_own_db(gamertag, match_ids, reference_db_path)`.

---

## 2. Arborescence `src/`

### 2.1 Racine

| Fichier | Rôle |
|---------|------|
| `config.py` | Chemins par défaut, config (DB, aliases, etc.) |
| `models.py` | Modèles Pydantic partagés (si présents à la racine) |

### 2.2 `src/ai/`

| Fichier | Rôle |
|---------|------|
| `mcp_server.py` | Serveur MCP (Model Context Protocol) |
| `rag.py` | RAG (Retrieval-Augmented Generation) / base de connaissances |

### 2.3 `src/analysis/`

| Fichier | Rôle |
|---------|------|
| `antagonists.py` | Agrégation rivalités (killer/victim) |
| `cumulative.py` | Stats cumulatives |
| `filters.py` | Filtres analytiques |
| `killer_victim.py` | Calcul paires killer→victim |
| `maps.py` | Analyse par carte |
| `mode_categories.py` | Catégorisation des modes |
| `objective_participation.py` | Participation objectifs |
| `performance_config.py` | Config score de performance |
| `performance_score.py` | Score de performance |
| `sessions.py` | Détection des sessions de jeu |
| `stats.py` | Calculs statistiques généraux |

### 2.4 `src/app/`

| Fichier | Rôle |
|---------|------|
| `data_loader.py` | Chargement des données pour l’app (identité, source, commendations) |
| `filters.py` | Logique des filtres (amis, plage de dates, etc.) |
| `filters_render.py` | Rendu sidebar des filtres |
| `helpers.py` | Helpers (couleurs joueurs, durées, labels, etc.) |
| `kpis.py` | Calcul des KPIs |
| `kpis_render.py` | Rendu section KPIs + infos performance |
| `main_helpers.py` | Helpers main : load_match_dataframe, resolve_xuid, validate_and_fix_db_path, render_profile_hero, etc. |
| `page_router.py` | Liste des pages, dispatch, paramètres communs match view |
| `profile.py` | Profil joueur |
| `routing.py` | Routage (pages, états) |
| `sidebar.py` | Sidebar Streamlit |
| `state.py` | État applicatif (session) |

### 2.5 `src/data/`

#### 2.5.1 Domain

| Chemin | Rôle |
|--------|------|
| `domain/models/` | Modèles domaine (match, medal, player) |
| `domain/refdata.py` | Référentiels (playlists, modes, médailles, etc.) |
| `domain/services/` | Services métier (si présents) |

#### 2.5.2 Infrastructure

| Chemin | Rôle |
|--------|------|
| `infrastructure/database/duckdb_config.py` | Config DuckDB |
| `infrastructure/database/duckdb_engine.py` | Moteur DuckDB |
| `infrastructure/database/sqlite_metadata.py` | Métadonnées (à migrer/limiter à DuckDB) |
| `infrastructure/parquet/reader.py` | Lecture Parquet (archives) |
| `infrastructure/parquet/writer.py` | Écriture Parquet |

#### 2.5.3 Integration

| Chemin | Rôle |
|--------|------|
| `integration/streamlit_bridge.py` | Pont Streamlit ↔ couche données |

#### 2.5.4 Repositories

| Fichier | Rôle |
|---------|------|
| `repositories/duckdb_repo.py` | **Repository principal** : load_matches, load_matches_paginated, load_match_medals, load_match_rosters, load_antagonists, save_antagonists, vues matérialisées, archives, killer_victim_pairs, resolve_gamertag, etc. |
| `repositories/factory.py` | `get_repository()`, `get_repository_from_profile()`, `load_db_profiles()` |
| `repositories/protocol.py` | Protocole `DataRepository` |

#### 2.5.5 Sync

| Fichier | Rôle |
|---------|------|
| `sync/api_client.py` | Client API SPNKr (Halo Infinite) |
| `sync/engine.py` | **DuckDBSyncEngine** : synchronisation vers `stats.duckdb` |
| `sync/models.py` | Modèles Pydantic pour la sync |
| `sync/transformers.py` | Transformation JSON API → schéma DuckDB (match_stats, medals, highlight_events, etc.) |

#### 2.5.6 Query

| Fichier | Rôle |
|---------|------|
| `query/analytics.py` | Requêtes analytiques |
| `query/engine.py` | Moteur de requêtes |
| `query/trends.py` | Tendances |

#### 2.5.7 Autres

| Fichier | Rôle |
|---------|------|
| `media_indexer.py` | Indexation médias (films, captures) |
| `weapon_ids.py` | IDs armes (référentiel / mapping) |
| `migration/` | Code de migration (vide ou minimal) |

### 2.6 `src/db/`

**Déprécié** : à terme tout passer par `DuckDBRepository`. Utiliser uniquement pour transition.

| Fichier | Rôle |
|---------|------|
| `connection.py` | Connexion DB (DuckDB prioritaire) |
| `loaders.py` | Anciens loaders → remplacer par DuckDBRepository |
| `loaders_cached.py` | Ancien cache → remplacer par DuckDBRepository |
| `parsers.py` | Parsers (dates, etc.) |
| `profiles.py` | Profils DB (db_profiles.json) |
| `queries.py` | Requêtes SQL réutilisables |
| `schema.py` | Schémas / DDL |

### 2.7 `src/ui/`

#### 2.7.1 Pages (`ui/pages/`)

| Fichier | Page / Rôle |
|---------|-------------|
| `timeseries.py` | Séries temporelles |
| `session_compare.py` | Comparaison de sessions |
| `last_match.py` | Dernier match |
| `match_view.py` | Vue Match (détail d’un match) |
| `match_view_charts.py` | Graphiques vue match |
| `match_view_helpers.py` | Helpers vue match |
| `match_view_participation.py` | Participation (objectifs, etc.) |
| `match_view_players.py` | Joueurs dans la vue match |
| `media_library.py` | Bibliothèque médias |
| `citations.py` | Citations |
| `win_loss.py` | Victoires / Défaites |
| `teammates.py` | Mes coéquipiers (référence chargement multi-DB) |
| `teammates_charts.py` | Graphiques coéquipiers |
| `teammates_helpers.py` | Helpers coéquipiers |
| `match_history.py` | Historique des parties |
| `objective_analysis.py` | Analyse objectifs |
| `settings.py` | Paramètres (peut être partagé avec app) |

#### 2.7.2 Composants (`ui/components/`)

| Fichier | Rôle |
|---------|------|
| `chart_annotations.py` | Annotations sur graphiques |
| `checkbox_filter.py` | Filtre type checkbox |
| `duckdb_analytics.py` | Composants analytiques DuckDB |
| `kpi.py` | Affichage KPI |
| `performance.py` | Composant performance |
| `radar_chart.py` | Graphique radar |

#### 2.7.3 Sections

| Fichier | Rôle |
|---------|------|
| `sections/openspartan.py` | Section OpenSpartan |
| `sections/source.py` | Section source de données |

#### 2.7.4 Fichiers racine `ui/`

| Fichier | Rôle |
|---------|------|
| `aliases.py` | Gestion des alias (XUID ↔ gamertag) |
| `cache.py` | Cache (chargements, DB key) |
| `career_ranks.py` | Rangs de carrière (affichage/traduction) |
| `commendations.py` | Commendations |
| `formatting.py` | Formatage dates, nombres, etc. |
| `medals.py` | Médailles (affichage) |
| `multiplayer.py` | Logique multi-joueurs (rosters, etc.) |
| `path_picker.py` | Sélecteur de chemin DB |
| `perf.py` | Helpers performance UI |
| `player_assets.py` | Assets joueur (images, etc.) |
| `profile_api*.py` | API profil (cache, tokens, URLs) |
| `settings.py` | Paramètres app (AppSettings) |
| `styles.py` | Styles CSS |
| `sync.py` | UI de synchronisation |
| `translations.py` | Traductions |

### 2.8 `src/visualization/`

| Fichier | Rôle |
|---------|------|
| `antagonist_charts.py` | Graphiques antagonistes |
| `distributions.py` | Distributions (kills, etc.) |
| `maps.py` | Visualisations par carte |
| `match_bars.py` | Barres par match |
| `objective_charts.py` | Graphiques objectifs |
| `participation_charts.py` | Graphiques participation |
| `performance.py` | Visualisations performance |
| `theme.py` | Thème Plotly |
| `timeseries.py` | Séries temporelles (graphiques) |
| `trio.py` | Visualisations type trio |

### 2.9 `src/utils/`

| Fichier | Rôle |
|---------|------|
| `paths.py` | Utilitaires chemins (données, warehouse, players, etc.) |

---

## 3. Scripts (`scripts/`)

Scripts listés par catégorie (environ 100 fichiers .py).

### 3.1 Sync et données principales

| Script | Rôle |
|--------|------|
| `sync.py` | Synchronisation SPNKr → DuckDB (delta, gamertag) |
| `ingest_halo_data.py` | Ingestion données Halo (référentiels → metadata.duckdb) |
| `install_dependencies.py` | Installation des dépendances projet |

### 3.2 Backup / Restore / Archive

| Script | Rôle |
|--------|------|
| `backup_player.py` | Export joueur en Parquet (Zstd) |
| `restore_player.py` | Restauration depuis backup |
| `archive_season.py` | Archivage temporel (saison → Parquet) |

### 3.3 Migration (SQLite → DuckDB, schéma)

| Script | Rôle |
|--------|------|
| `recover_from_sqlite.py` | Récupération depuis ancienne base SQLite (autorisé SQLite en lecture) |
| `migrate_player_to_duckdb.py` | Migration d’un joueur vers DuckDB |
| `migrate_all_to_duckdb.py` | Migration globale |
| `migrate_metadata_to_duckdb.py` | Migration métadonnées |
| `migrate_highlight_events.py` | Migration highlight_events |
| `migrate_player_match_stats.py` | Migration player_match_stats |
| `migrate_aliases_to_db.py` | Migration alias vers BDD |
| `migrate_add_columns.py` | Ajout de colonnes |
| `migrate_game_variant_category.py` | Catégorie game variant |
| `merge_databases.py` | Fusion de bases |

### 3.4 Backfill et peuplement

| Script | Rôle |
|--------|------|
| `backfill_data.py` | Backfill données génériques |
| `backfill_killer_victim_pairs.py` | Backfill killer_victim_pairs |
| `backfill_match_data.py` | Backfill données match |
| `backfill_medals.py` | Backfill médailles |
| `backfill_null_metadata.py` | Backfill métadonnées NULL |
| `backfill_personal_score_awards.py` | Backfill personal_score_awards |
| `backfill_teammates_signature.py` | Backfill signature coéquipiers |
| `populate_antagonists.py` | Peuplement table antagonists |
| `populate_metadata_players.py` | Peuplement joueurs dans metadata |

### 3.5 Diagnostic et correctifs

| Script | Rôle |
|--------|------|
| `diagnose_player_db.py` | Diagnostic BDD joueur |
| `diagnose_accuracy.py` | Diagnostic précision |
| `diagnose_first_kill_death.py` / `_simple.py` | Premier kill/death |
| `diagnose_media_*.py` | Médias, indexation, associations |
| `diagnose_metadata_resolution.py` | Résolution métadonnées |
| `diagnose_migration_gaps.py` | Lacunes migration |
| `diagnose_null_metadata.py` | Métadonnées NULL |
| `diagnostic_critical_data.py` | Données critiques |
| `fix_null_metadata*.py` | Correctifs métadonnées NULL (plusieurs variantes) |
| `fix_accuracy_column.py` | Correction colonne accuracy |
| `resolve_missing_gamertags.py` | Résolution gamertags manquants |
| `refetch_film_roster.py` | Rafraîchir roster film |

### 3.6 Analyse / Recherche (weapons, killfeed, binaire)

| Script | Rôle |
|--------|------|
| `analyze_*weapon*.py`, `analyze_*chunk*.py`, `analyze_*binary*.py` | Analyses armes, chunks, binaire |
| `aggregate_weapon_ids.py` | Agrégation IDs armes |
| `explore_killfeed_weapons.py` | Exploration armes killfeed |
| `find_killer_victim_pairs.py`, `find_kill_patterns.py`, `find_events_by_type.py` | Recherche paires / patterns |
| `correlate_kills.py` | Corrélation kills |
| `extract_events_v3.py`, `extract_binary_events.py` | Extraction événements |
| `fetch_match_weapon_stats.py`, `fetch_fiesta_weapons.py` | Récupération stats armes |
| `investigate_refdata_fields.py`, `investigate_killfeed_*.py` | Investigation refdata / killfeed |

### 3.7 Calculs et batch

| Script | Rôle |
|--------|------|
| `compute_sessions.py` | Calcul des sessions |
| `compute_historical_performance.py` | Performance historique |
| `generate_thumbnails.py` | Génération miniatures |
| `generate_medals_fr.py` / `generate_commendations_mapping.py` | Génération mappings FR |
| `build_commendations_exclude_from_notes.py` | Exclusions commendations |
| `download_career_rank_icons.py` | Téléchargement icônes rangs |
| `prefetch_profile_assets.py` | Préchargement assets profil |
| `merge_assets_to_unified.py` | Fusion assets |

### 3.8 API / SPNKr

| Script | Rôle |
|--------|------|
| `spnkr_get_refresh_token.py` | Refresh token SPNKr |
| `spnkr_import_db.py` | Import depuis SPNKr |
| `add_friend.py` | Ajout ami |
| `check_service_record.py` / `_v2.py` | Vérification service record |

### 3.9 Tests et validation

| Script | Rôle |
|--------|------|
| `validate_refdata_integrity.py` | Validation intégrité refdata |
| `verify_accuracy_extraction.py` | Vérification extraction précision |
| `test_metadata_query.py`, `test_media_library_*.py`, `test_polars_integration.py` | Tests ciblés |
| `smart_test.py` | Tests rapides |

### 3.10 Autres

| Script | Rôle |
|--------|------|
| `get_match_id.py` | Récupération match_id |
| `index_media.py` | Indexation médias |
| `index_knowledge_base.py` | Index base connaissances (RAG) |
| `cleanup_codebase.py` | Nettoyage code |
| `benchmark_polars.py` | Benchmark Polars |
| `thumbnails-watcher.service` | Service systemd watcher thumbnails |
| `_obsolete/` | Anciens scripts (migrate_to_cache, migrate_to_parquet) |

---

## 4. Tests (`tests/`)

- **Integration** : `integration/test_refdata_antagonists.py`
- **Analysis** : `test_analysis.py`, `test_antagonists_persistence.py`, `test_killer_victim_*.py`, `test_performance_*.py`, `test_sessions_advanced.py`, `test_objective_participation.py`, `test_mode_categories_custom.py`
- **App** : `test_app_module.py`, `test_app_phase2.py`, `test_phase6_refactoring.py`
- **Data / Repo** : `test_duckdb_repository.py`, `test_duckdb_repo_regressions.py`, `test_data_architecture.py`, `test_data_validation_regressions.py`, `test_query_module.py`, `test_refdata.py`, `test_transformers_refdata.py`
- **Sync** : `test_sync_engine.py`, `test_delta_sync.py`, `test_sync_cli_integration.py`, `test_sync_ui.py`, `test_spnkr_refactoring.py`
- **Cache / Lazy** : `test_cache_*.py`, `test_lazy_loading.py`, `test_materialized_views.py`
- **UI / Last match** : `test_last_match_fixes.py`, `test_match_player_gamertags.py`, `test_visualizations.py`
- **Media** : `test_media_indexer.py`, `test_media_library_keys.py`
- **Autres** : `test_models.py`, `test_parsers.py`, `test_rag.py`, `test_season_archive.py`, `test_settings_backfill.py`, `test_gamertag_sanitize.py`, `test_sprint1_antagonists.py`, `test_session_compare_hist_avg_category.py`, `test_timeseries_performance_score.py`

---

## 5. Documentation

### 5.1 `docs/` (utilisateur / technique)

| Document | Contenu |
|----------|---------|
| `INSTALL.md` | Installation |
| `CONFIGURATION.md` | Configuration |
| `ARCHITECTURE.md` | Architecture technique |
| `DATA_ARCHITECTURE.md` | Architecture données |
| `SQL_SCHEMA.md` | Schémas SQL |
| `SYNC_GUIDE.md` | Guide synchronisation |
| `BACKUP_RESTORE.md` | Backup / Restore |
| `PERFORMANCE_SCORE.md` | Score de performance |
| `QUERY_EXAMPLES.md` | Exemples de requêtes |
| `MIGRATION_REFDATA.md` | Migration référentiels |
| `THUMBNAILS_WATCHER.md` | Watcher miniatures |
| `FAQ.md` | FAQ |
| `API_GRUNT_RESEARCH.md` | Recherche API Grunt |

### 5.2 `.ai/` (agents IA et décisions)

| Document | Contenu |
|----------|---------|
| `project_map.md` | Cartographie vivante (à consulter en premier) |
| `thought_log.md` | Journal des décisions |
| `data_lineage.md` | Flux de données |
| `ARCHITECTURE_ROADMAP.md` | Roadmap des phases |
| `CONSOLIDATED_AUDITS_AND_ROADMAP.md` | Audits SQLite→DuckDB, Pandas→Polars, priorités |
| `SQLITE_TO_DUCKDB_AUDIT.md` | Détail migration SQLite |
| `PANDAS_TO_POLARS_AUDIT.md` | Détail migration Pandas→Polars |
| `API_LIMITATIONS.md` | Limitations API (armes, etc.) |
| `DATA_KILLER_VICTIM.md` | Guide killer/victim et antagonistes |
| `MCP_CONFIG.md` | Config MCP |
| `explore/` | Explorations (ce document) |
| `features/`, `research/`, `sprints/`, `archive/` | Spécs, recherche, sprints, archives |

---

## 6. Données et configuration

### 6.1 Structure données (v4)

```
data/
├── players/{gamertag}/
│   ├── stats.duckdb      # Base joueur (match_stats, medals_earned, antagonists, etc.)
│   └── archive/          # Parquet (matches_*.parquet, archive_index.json)
├── warehouse/
│   └── metadata.duckdb   # Référentiels (playlists, game_modes, medal_definitions, career_ranks)
└── backups/              # Backups Parquet (optionnel)
```

### 6.2 Fichiers de config (racine)

| Fichier | Rôle |
|---------|------|
| `db_profiles.json` | Profils DB (chemins, gamertags) |
| `app_settings.json` | Paramètres application (si utilisé) |
| `.env` / `.env.example` | Variables d’environnement |
| `.streamlit/secrets.toml` | Secrets Streamlit (SPNKr, etc.) |
| `Playlist_modes_translations.json` | Traductions playlists / modes |

### 6.3 Static / assets

| Dossier | Rôle |
|--------|------|
| `static/` | CSS, commendations, medals (images) |
| `thumbs/` | Miniatures cartes / modes (jpg, png) |

---

## 7. Points d’entrée et flux

1. **Lancement** : `streamlit run streamlit_app.py` → `streamlit_app.py` charge `src.app.*`, `src.ui.*`, applique filtres, route via `page_router.dispatch_page()` vers les pages dans `src.ui.pages.*`.
2. **Données** : `DuckDBRepository` (factory depuis `db_profiles.json` ou chemin par défaut) ; chargement via `load_matches`, `load_match_medals`, etc. ; vues matérialisées rafraîchies après sync.
3. **Sync** : `scripts/sync.py` → `DuckDBSyncEngine` + `transformers` → écriture dans `data/players/{gamertag}/stats.duckdb` et mise à jour metadata.

---

## 8. Dépendances principales (pyproject.toml)

| Package | Version | Usage |
|---------|---------|--------|
| `streamlit` | >=1.28.0 | UI |
| `plotly` | >=5.18.0 | Graphiques |
| `pandas` | >=2.0.0 | DataFrames (à réduire au profit de Polars) |
| `polars` | >=0.20.0 | DataFrames performants |
| `duckdb` | >=0.10.0 | Moteur BDD |
| `pydantic` | >=2.5.0 | Validation |
| `tqdm` | >=4.65.0 | Barres de progression |
| Optionnel `spnkr` | >=0.9.0 | Client API Halo |

---

## 9. État des audits (référence)

- **SQLite → DuckDB** : voir `.ai/SQLITE_TO_DUCKDB_AUDIT.md` et `.ai/CONSOLIDATED_AUDITS_AND_ROADMAP.md`. SQLite interdit en applicatif.
- **Pandas → Polars** : migration en cours, préférer Polars pour gros volumes ; voir `.ai/PANDAS_TO_POLARS_AUDIT.md`.
- **Problème critique données manquantes** (noms cartes/modes/playlists NULL, gamertags, etc.) : voir `.ai/project_map.md` section « Problèmes connus » et diagnostics dans `.ai/archive/plans_treated_2026-02/diagnostics/`.

---

## 10. Dernière mise à jour

**2026-02-05** : Exploration complète refaite (ce document).  
Pour la cartographie vivante et les problèmes en cours : `.ai/project_map.md`.
