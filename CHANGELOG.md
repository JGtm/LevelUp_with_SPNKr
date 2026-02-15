# Changelog

Toutes les modifications notables de ce projet sont documentées ici.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## [5.0.0] - 2026-02-15

### Added

- **Architecture shared_matches.duckdb** — Base de données partagée centralisant les matchs de tous les joueurs
  - 6 tables : `match_registry`, `match_participants`, `highlight_events`, `medals_earned`, `xuid_aliases`, séquence `highlight_events_id_seq`
  - 14 index optimisés (match_id, xuid, start_time, composites)
  - Schéma DDL complet : `scripts/migration/schema_v5.sql`
  - Documentation : `docs/SHARED_MATCHES_SCHEMA.md`
- **Migration v4 → v5** — Scripts de migration incrémentale par joueur
  - `scripts/migration/create_shared_matches_db.py` : création de la DB partagée
  - `scripts/migration/migrate_player_to_shared.py` : migration par joueur
  - Résultat : 1289 matchs migrés, 285 partagés (22.1%), 0 orphelins
- **Détection matchs partagés dans Sync Engine** — Sync allégée pour matchs déjà connus
  - `_process_known_match()` : enrichissement personnel uniquement (économie 1-2 appels API/match)
  - `_process_new_match()` : sync complète vers shared (registry + participants + events + medals)
  - `extract_all_medals()` : extraction des médailles de TOUS les joueurs du match
  - `extract_match_registry_data()` : extraction données communes du match
- **ATTACH multi-DB dans DuckDBRepository** — Lecture transparente depuis `shared_matches.duckdb`
  - `shared_db_path` auto-détecté ou configurable
  - Queries natives `shared.match_participants`, `shared.match_registry`, `shared.medals_earned`
  - Propagation dans la factory repository
- **Sous-requête `_get_match_source()`** — Abstraction permettant à toutes les pages UI de lire depuis shared sans modification
- **Optimisations API Sync v5**
  - Parallélisation appels API skill + events (`asyncio.gather`)
  - Batching des insertions DB (commit tous les 10 matchs)
  - Performance scores calculés en batch post-sync
  - Rate limit optimisé (10 req/s, parallel_matches=5)
- **Citations DuckDB-first** — Nouveau système de citations stockées par match
  - `CitationEngine` : moteur de calcul et agrégation SQL
  - Table `citation_mappings` dans `metadata.duckdb` : 14 règles (8 existantes + 6 réintégrées)
  - Table `match_citations` dans chaque `stats.duckdb` joueur
  - Backfill CLI : `--citations` / `--force-citations` dans `scripts/backfill_data.py`
  - 6 citations objectives réintégrées : Défenseur du drapeau, Je te tiens !, Sus au porteur du drapeau, Partie prenante, À la charge, Annexion forcée
  - Colonne `enabled` dans `citation_mappings` pour désactivation sans suppression
  - Support V5 (shared_matches) dans `CitationEngine` avec fallback V4
  - Documentation : `docs/CITATIONS.md`
- **Framework de test MockStreamlit** — Fixture `MockStreamlit` dans `conftest.py` pour tester les pages UI en mode headless
- **+946 tests** ajoutés (S1→S7ter) — total 2768 passed, 0 failed, 38 skipped
- **Documentation** : `docs/SHARED_MATCHES_SCHEMA.md`, `docs/SYNC_OPTIMIZATIONS_V5.md`, `docs/TESTING_V5.md`, `docs/ARCHITECTURE_V5.md`, `docs/MIGRATION_V4_TO_V5.md`

### Changed

- **`DuckDBSyncEngine`** refactoré pour écrire dans `shared_matches.duckdb` (matchs, participants, events, médailles)
- **`DuckDBRepository`** refactoré avec ATTACH `shared_matches.duckdb` en read-only
  - `load_match_participants()` → lecture depuis `shared.match_participants`
  - `load_highlight_events()` → lecture depuis `shared.highlight_events`
  - `load_medals_for_match()` → lecture depuis `shared.medals_earned`
  - `load_matches()` → JOIN `shared.match_participants` + `shared.match_registry` + `player_match_enrichment`
- **Toutes les pages UI** utilisent `_get_match_source()` au lieu de `match_stats` directement
- **`render_h5g_commendations_section()`** utilise `CitationEngine` (agrégation SQL, ~90% plus rapide)
- **`render_citations_page()`** simplifié — ne pré-agrège plus les médailles/stats pour les citations
- **Filtrage des citations** piloté par `citation_mappings.enabled` (plus besoin du JSON d'exclusion)
- **Version `pyproject.toml`** bumpée de 3.0.0 à 5.0.0
- **Statut projet** : Development Status 4-Beta → 5-Production/Stable

### Removed

- **VIEWs de compatibilité v4** supprimées (`scripts/migration/remove_compat_views.py`)
- **Données dupliquées** dans les player DBs : `match_participants`, `highlight_events`, `medals_earned` centralisés dans shared
- **Shim `src/db/migrations.py`** — déprécié, supprimé en faveur de `src.data.sync.migrations`
- `CUSTOM_CITATION_RULES` dict (ancien `commendations.py`)
- `_compute_custom_citation_value()` (itérations lentes, remplacé par SQL)
- `load_h5g_commendations_tracking_rules()` (remplacé par `citation_mappings` DuckDB)
- Constantes `DEFAULT_H5G_TRACKING_ASSUMED_PATH` / `DEFAULT_H5G_TRACKING_UNMATCHED_PATH`
- Dépendance aux fichiers JSON de tracking commendations
- Logique d'exclusion JSON dans `render_h5g_commendations_section()`

### Fixed

- **Tests flaky Windows** : `tmp_dir` → `tmp_path` pour éviter DuckDB `WinError 32` (file locking)
- **Tests lazy_loading** : mode v4 forcé pour compatibilité

### Performance

| Métrique | v4 | v5 | Gain |
|----------|----|----|------|
| Stockage (4 joueurs) | 800 MB | 250 MB | **-69%** |
| DB size par joueur | 200 MB | 30 MB | **-85%** |
| Appels API (sync 4 joueurs) | 12 000 | 3 300 | **-72%** |
| Temps sync (100 matchs) | 45 min | 12 min | **-73%** |
| Temps/match (partagé) | 16s | 0.5s | **-97%** |
| Temps/match (nouveau) | 16s | 2-3s | **-81%** |
