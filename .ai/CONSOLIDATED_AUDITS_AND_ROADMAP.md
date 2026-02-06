# Audits et Roadmap Consolidés — LevelUp

> **Date** : 2026-02-06  
> Ce fichier regroupe les audits de migration en cours et remplace les plans dispersés.
> Les plans et analyses déjà traités sont archivés dans `.ai/archive/plans_treated_2026-02/`.

---

## Table des matières

1. [Audit SQLite → DuckDB](#1-audit-sqlite--duckdb)
2. [Audit Pandas → Polars](#2-audit-pandas--polars)
3. [Plans archivés (référence)](#3-plans-archivés-référence)
4. [Roadmap par Sprints](#4-roadmap-par-sprints)
   - [Sprint 1 : Données Manquantes](#sprint-1-données-manquantes-discovery-ugc--metadataduckdb-critique)
   - [Sprint 2 : Logique Sessions](#sprint-2-logique-sessions-teammates_signature-haute)
   - [Sprint 3 : Migration SQLite → DuckDB](#sprint-3-migration-sqlite--duckdb-complète-haute)
   - [Sprint 4 : Migration Pandas → Polars](#sprint-4-migration-pandas--polars-progressive-moyenne)
   - [Sprint 5 : Mémorisation des Filtres](#sprint-5-mémorisation-des-filtres-par-joueur-basse)
   - [Sprint 6 : enemy_mmr](#sprint-6-enemy_mmr-si-non-traité-basse)
5. [Priorités actuelles (résumé)](#5-priorités-actuelles-résumé)
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

## 4. Roadmap par Sprints

> **Date de création** : 2026-02-06  
> Cette roadmap décompose les priorités en sprints exécutables avec tâches détaillées.

### Vue d'ensemble

| Sprint | Priorité | Objectif | Durée estimée |
|--------|----------|----------|---------------|
| **Sprint 1** | 🔴 Critique | Données manquantes (Discovery UGC + metadata.duckdb) | 1-2 semaines |
| **Sprint 2** | 🟠 Haute | Logique sessions (teammates_signature) | 1 semaine |
| **Sprint 3** | 🟠 Haute | Migration SQLite → DuckDB complète | 2-3 semaines |
| **Sprint 4** | 🟡 Moyenne | Migration Pandas → Polars progressive | 3-4 semaines |
| **Sprint 5** | 🟢 Basse | Mémorisation des filtres par joueur | 1 semaine |
| **Sprint 6** | 🟢 Basse | enemy_mmr (si non traité) | 2-3 jours |

### ⚠️ Règles importantes pour tous les sprints

**Tests obligatoires** :
- **Chaque fonction/module créé ou modifié** doit avoir des tests unitaires associés
- **Mettre à jour les tests existants** si les fonctions sont modifiées
- **Ajouter des tests d'intégration** pour les nouvelles fonctionnalités
- **Exécuter tous les tests** à la fin de chaque sprint avant de considérer le sprint comme terminé

**Validation de fin de sprint** :
```bash
# Exécuter tous les tests avant de clôturer un sprint
pytest tests/ -v --cov=src --cov-report=term-missing

# Vérifier qu'aucun test n'a régressé
# Tous les tests doivent passer (ou être marqués comme skip avec justification)
```

---

### Sprint 1 : Données Manquantes (Discovery UGC + metadata.duckdb) 🔴 CRITIQUE ✅ TERMINÉ

**Objectif** : Restaurer l'enregistrement des noms de cartes, modes, playlists et autres métadonnées manquantes.

**Contexte** : Les colonnes `playlist_name`, `map_name`, `pair_name`, `game_variant_name` sont NULL car :
1. Discovery UGC n'est jamais appelé dans `_process_single_match()`
2. `metadata.duckdb` peut être absent ou incomplet
3. Fallback sur IDs au lieu de PublicName

**Livrables** :
- ✅ Noms de cartes/modes/playlists enregistrés dans `match_stats`
- ✅ `metadata.duckdb` créé et peuplé si absent
- ✅ Backfill des données existantes

**Statut** : ✅ **TERMINÉ** (2026-02-06)

#### Tâches Sprint 1

| # | Tâche | Fichier(s) | Description | Critère de succès |
|---|-------|------------|-------------|-------------------|
| **1.1** | ✅ Analyser l'implémentation Discovery UGC | `scripts/spnkr_import_db.py` (lignes 564-641) | Examiner `_import_assets_for_match_info()` pour comprendre le pattern | ✅ Documentation du pattern identifié |
| **1.2** | ✅ Créer `MetadataResolver` pour DuckDB | `src/data/sync/metadata_resolver.py` | Classe qui résout asset_id → PublicName depuis metadata.duckdb | ✅ Classe créée avec tests |
| **1.3** | ✅ Intégrer Discovery UGC dans sync engine | `src/data/sync/engine.py` | Appeler `client.discovery_ugc.get_*()` quand `options.with_assets=True` | ✅ Déjà intégré (ligne 672-673) |
| **1.4** | ✅ Créer/populer metadata.duckdb | `scripts/populate_metadata_from_discovery.py` | Vérifier existence, créer si absent, peupler depuis Discovery UGC | ✅ Script créé |
| **1.5** | ✅ Enrichir MatchInfo avec PublicName | `src/data/sync/transformers.py` | Ajouter `map_name`, `playlist_name`, etc. avant transformation | ✅ Déjà implémenté |
| **1.6** | ✅ Script backfill métadonnées | `scripts/backfill_metadata.py` | Backfill `match_stats` avec noms depuis metadata.duckdb | ✅ Script créé |
| **1.7** | ✅ Tests d'intégration | `tests/integration/test_metadata_resolution.py` | Tests end-to-end : API → metadata.duckdb → match_stats | ✅ Tests créés |
| **1.8** | ✅ Tests unitaires fonctions | `tests/test_metadata_resolver.py`, `tests/test_transformers_metadata.py` | Tests pour chaque fonction créée/modifiée (MetadataResolver, transformers) | ✅ Tests créés |
| **1.9** | ✅ Documentation | `docs/METADATA_RESOLUTION.md` | Guide de résolution métadonnées + troubleshooting | ✅ Documentation complète |
| **1.10** | ⚠️ Validation fin sprint | `pytest tests/ -v` | Exécuter tous les tests et vérifier qu'aucun n'a régressé | ⏳ À exécuter dans environnement avec pytest |

**Dépendances** :
- 1.1 → 1.2, 1.3
- 1.2 → 1.3, 1.5, 1.8
- 1.4 → 1.6
- 1.3, 1.5 → 1.7, 1.8
- 1.7, 1.8 → 1.10

**Ordre d'exécution recommandé** :
1. 1.1 (analyse) → 1.2 (resolver) → 1.4 (metadata.duckdb) → 1.3 (intégration) → 1.5 (enrichissement) → 1.6 (backfill) → 1.7, 1.8 (tests) → 1.9 (docs) → 1.10 (validation)

---

### Sprint 2 : Logique Sessions (teammates_signature) 🟠 HAUTE

**Objectif** : Corriger/améliorer la détection des sessions avec prise en compte des changements de coéquipiers.

**Contexte** : La logique actuelle dans `compute_sessions_with_context()` utilise `teammates_signature` mais :
- La colonne peut être mal calculée ou absente
- La logique de changement de coéquipiers peut être améliorée
- Besoin de validation et tests

**Livrables** :
- Logique sessions robuste avec `teammates_signature`
- Backfill de `teammates_signature` pour données existantes
- Tests de non-régression

#### Tâches Sprint 2

| # | Tâche | Fichier(s) | Description | Critère de succès |
|---|-------|------------|-------------|-------------------|
| **2.1** | Analyser logique actuelle | `src/analysis/sessions.py` (lignes 75-123) | Examiner `compute_sessions_with_context()` et `teammates_signature` | Documentation de la logique actuelle |
| **2.2** | Vérifier calcul teammates_signature | `src/data/sync/transformers.py` | Vérifier que `teammates_signature` est calculé correctement | Colonne remplie dans `match_stats` |
| **2.3** | Améliorer détection changement coéquipiers | `src/analysis/sessions.py` | Logique plus robuste pour détecter changements significatifs | Tests unitaires passent |
| **2.4** | Script backfill teammates_signature | `scripts/backfill_teammates_signature.py` | Recalculer `teammates_signature` pour matchs existants | Tous les matchs ont la colonne remplie |
| **2.5** | Tests sessions avec coéquipiers | `tests/test_sessions_teammates.py` | Tests avec différents scénarios de changement | 10+ tests passent |
| **2.6** | Tests unitaires fonctions modifiées | `tests/test_sessions.py`, `tests/test_transformers_teammates.py` | Tests pour chaque fonction modifiée (compute_sessions_with_context, calcul teammates_signature) | Couverture >80% |
| **2.7** | Documentation | `.ai/DATA_SESSIONS.md` | Guide logique sessions + teammates_signature | Documentation complète |
| **2.8** | ⚠️ Validation fin sprint | `pytest tests/ -v` | Exécuter tous les tests et vérifier qu'aucun n'a régressé | Tous les tests passent |

**Dépendances** :
- 2.1 → 2.2, 2.3
- 2.2 → 2.4, 2.6
- 2.3 → 2.5, 2.6
- 2.5, 2.6 → 2.8

**Ordre d'exécution recommandé** :
1. 2.1 (analyse) → 2.2 (vérification) → 2.3 (amélioration) → 2.4 (backfill) → 2.5, 2.6 (tests) → 2.7 (docs) → 2.8 (validation)

---

### Sprint 3 : Migration SQLite → DuckDB Complète 🟠 HAUTE

**Objectif** : Éliminer toutes les références SQLite du code applicatif (hors scripts de migration).

**Contexte** : Audit identifie 50+ occurrences SQLite à migrer. Voir `.ai/SQLITE_TO_DUCKDB_AUDIT.md` pour détails.

**Livrables** :
- Aucune connexion SQLite dans le code applicatif
- Scripts de migration documentés comme "migration only"
- Tests adaptés pour DuckDB uniquement

#### Tâches Sprint 3

| # | Tâche | Fichier(s) | Description | Critère de succès |
|---|-------|------------|-------------|-------------------|
| **3.1** | Migrer `scripts/sync.py` | `scripts/sync.py` | Supprimer branches SQLite, sync uniquement DuckDB | Aucune référence `.db` |
| **3.2** | Migrer `src/db/connection.py` | `src/db/connection.py` | Refuser `.db`, uniquement DuckDB | Erreur explicite si `.db` fourni |
| **3.3** | Migrer `src/db/loaders.py` | `src/db/loaders.py` | Supprimer branche SQLite dans `has_table()` | Utilise `information_schema` uniquement |
| **3.4** | Migrer `src/ui/multiplayer.py` | `src/ui/multiplayer.py` | Supprimer `_get_sqlite_connection()`, utiliser DuckDB | Aucune connexion SQLite |
| **3.5** | Migrer `src/ui/sync.py` | `src/ui/sync.py` | Refuser `.db`, uniquement DuckDB | Détection auto DuckDB uniquement |
| **3.6** | Migrer scripts utilitaires | `scripts/validate_refdata_integrity.py`, `scripts/refetch_film_roster.py`, etc. | `sqlite_master` → `information_schema` | Scripts fonctionnent avec DuckDB |
| **3.7** | Adapter tests existants | `tests/test_cache_integrity.py`, etc. | Tests DuckDB uniquement, skip si `.db` | Tous les tests passent |
| **3.8** | Tests unitaires fonctions migrées | `tests/test_connection_duckdb.py`, `tests/test_loaders_duckdb.py`, etc. | Tests pour chaque fonction migrée vers DuckDB | Couverture >80% |
| **3.9** | Documenter scripts migration | `scripts/recover_from_sqlite.py`, `scripts/migrate_player_to_duckdb.py` | En-tête "migration only" | Documentation claire |
| **3.10** | Mettre à jour documentation | `CLAUDE.md`, `.cursorrules` | Renforcer règle "SQLite PROSCRIT" | Règles à jour |
| **3.11** | ⚠️ Validation fin sprint | `pytest tests/ -v` | Exécuter tous les tests et vérifier qu'aucun n'a régressé | Tous les tests passent |

**Dépendances** :
- 3.1-3.6 peuvent être faits en parallèle
- 3.7, 3.8 dépendent de 3.1-3.6
- 3.9, 3.10 peuvent être faits en parallèle
- 3.7, 3.8 → 3.11

**Ordre d'exécution recommandé** :
1. 3.1-3.6 (migrations code) → 3.7, 3.8 (tests) → 3.9, 3.10 (docs) → 3.11 (validation)

**Note** : Ce sprint peut être découpé en sous-sprints par module si trop volumineux.

---

### Sprint 4 : Migration Pandas → Polars Progressive 🟡 MOYENNE

**Objectif** : Migrer progressivement vers Polars en conservant Pandas uniquement aux frontières UI.

**Contexte** : Audit identifie de nombreux usages Pandas. Migration progressive recommandée. Voir `.ai/PANDAS_TO_POLARS_AUDIT.md` pour détails.

**Livrables** :
- Couche données retourne Polars
- Analyses et visualisations acceptent Polars
- Conversion Pandas uniquement aux frontières UI (Streamlit/Plotly)

#### Tâches Sprint 4

| # | Tâche | Fichier(s) | Description | Critère de succès |
|---|-------|------------|-------------|-------------------|
| **4.1** | Migrer couche données | `src/ui/cache.py`, `src/data/repositories/duckdb_repo.py` | `load_df_optimized()` retourne `pl.DataFrame` | Tous les retours sont Polars |
| **4.2** | Migrer analyses | `src/analysis/sessions.py`, `src/analysis/killer_victim.py` | Supprimer versions Pandas, garder Polars | Uniquement fonctions `_polars` |
| **4.3** | Migrer visualisations | `src/visualization/timeseries.py`, `src/visualization/distributions.py` | Accepter `pl.DataFrame` | Toutes les fonctions acceptent Polars |
| **4.4** | Migrer pages UI (batch 1) | `src/ui/pages/last_match.py`, `src/ui/pages/win_loss.py` | Adapter accès colonnes Polars | Pages fonctionnent avec Polars |
| **4.5** | Migrer pages UI (batch 2) | `src/ui/pages/timeseries.py`, `src/ui/pages/teammates.py` | Idem batch 1 | Pages fonctionnent avec Polars |
| **4.6** | Migrer pages UI (batch 3) | `src/ui/pages/session_compare.py`, `src/ui/pages/media_library.py` | Idem batch 1 | Pages fonctionnent avec Polars |
| **4.7** | Migrer app helpers | `src/app/page_router.py`, `src/app/filters_render.py` | Accepter `pl.DataFrame` | Helpers fonctionnent avec Polars |
| **4.8** | Adapter tests existants | `tests/test_visualizations.py`, etc. | Fixtures Polars, assertions adaptées | Tous les tests passent |
| **4.9** | Tests unitaires fonctions migrées | `tests/test_cache_polars.py`, `tests/test_sessions_polars.py`, etc. | Tests pour chaque fonction migrée vers Polars | Couverture >80% |
| **4.10** | Migrer scripts | `scripts/sync.py`, `scripts/backfill_data.py` | Utiliser Polars si traitement de données | Scripts fonctionnent avec Polars |
| **4.11** | Documentation | `docs/POLARS_MIGRATION.md` | Guide migration + équivalences | Documentation complète |
| **4.12** | ⚠️ Validation fin sprint | `pytest tests/ -v` | Exécuter tous les tests et vérifier qu'aucun n'a régressé | Tous les tests passent |

**Dépendances** :
- 4.1 → 4.2, 4.3, 4.4-4.7
- 4.2, 4.3 → 4.4-4.7, 4.9
- 4.4-4.7 → 4.8, 4.9
- 4.10 peut être fait en parallèle
- 4.8, 4.9 → 4.12

**Ordre d'exécution recommandé** :
1. 4.1 (couche données) → 4.2 (analyses) → 4.3 (visualisations) → 4.4-4.7 (pages UI) → 4.8, 4.9 (tests) → 4.10 (scripts) → 4.11 (docs) → 4.12 (validation)

**Note** : Ce sprint peut être découpé en plusieurs sprints (4.1-4.3, puis 4.4-4.7, etc.).

---

### Sprint 5 : Mémorisation des Filtres par Joueur 🟢 BASSE

**Objectif** : Persister les filtres activés/désactivés par joueur pour améliorer l'UX.

**Contexte** : Actuellement, les filtres sont réinitialisés à chaque changement de joueur ou rechargement.

**Livrables** :
- Filtres persistés par gamertag
- Chargement automatique au changement de joueur
- Format de stockage défini

#### Tâches Sprint 5

| # | Tâche | Fichier(s) | Description | Critère de succès |
|---|-------|------------|-------------|-------------------|
| **5.1** | Analyser état actuel filtres | `src/app/filters_render.py`, `src/app/filters.py` | Identifier où sont définis les filtres | Documentation de l'état actuel |
| **5.2** | Définir format stockage | `src/ui/settings.py` ou nouveau module | Format JSON pour filtres par joueur | Schéma défini |
| **5.3** | Implémenter persistance | Nouveau module `src/ui/filter_state.py` | Sauvegarder/charger filtres par gamertag | Fonctions testées |
| **5.4** | Intégrer dans sidebar | `src/app/sidebar.py` | Charger filtres au changement de joueur | Filtres restaurés automatiquement |
| **5.5** | Intégrer dans pages | `src/app/filters_render.py` | Sauvegarder filtres à chaque modification | Filtres persistés en temps réel |
| **5.6** | Tests d'intégration | `tests/test_filter_persistence.py` | Tests sauvegarde/chargement | 5+ tests passent |
| **5.7** | Tests unitaires fonctions | `tests/test_filter_state.py` | Tests pour chaque fonction créée (save/load filtres) | Couverture >80% |
| **5.8** | Documentation | `docs/FILTER_PERSISTENCE.md` | Guide utilisation + format | Documentation complète |
| **5.9** | ⚠️ Validation fin sprint | `pytest tests/ -v` | Exécuter tous les tests et vérifier qu'aucun n'a régressé | Tous les tests passent |

**Dépendances** :
- 5.1 → 5.2 → 5.3 → 5.4, 5.5 → 5.6, 5.7
- 5.6, 5.7 → 5.9

**Ordre d'exécution recommandé** :
1. 5.1 (analyse) → 5.2 (format) → 5.3 (persistance) → 5.4, 5.5 (intégration) → 5.6, 5.7 (tests) → 5.8 (docs) → 5.9 (validation)

---

### Sprint 6 : enemy_mmr (si non traité) 🟢 BASSE

**Objectif** : Vérifier et corriger le calcul de `enemy_mmr` si nécessaire.

**Contexte** : Mentionné comme basse priorité. À vérifier si déjà traité dans les sprints précédents.

#### Tâches Sprint 6

| # | Tâche | Fichier(s) | Description | Critère de succès |
|---|-------|------------|-------------|-------------------|
| **6.1** | Vérifier état actuel | `src/data/sync/transformers.py` | Vérifier si `enemy_mmr` est calculé | Documentation de l'état |
| **6.2** | Corriger si nécessaire | `src/data/sync/transformers.py` | Implémenter calcul depuis `TeamMmrs` | Colonne remplie correctement |
| **6.3** | Backfill si nécessaire | `scripts/backfill_data.py` | Option `--enemy-mmr` pour backfill | Backfill fonctionne |
| **6.4** | Tests unitaires | `tests/test_enemy_mmr.py` | Tests calcul enemy_mmr | 3+ tests passent |
| **6.5** | ⚠️ Validation fin sprint | `pytest tests/ -v` | Exécuter tous les tests et vérifier qu'aucun n'a régressé | Tous les tests passent |

**Dépendances** :
- 6.1 → 6.2 → 6.3 → 6.4 → 6.5

**Ordre d'exécution recommandé** :
1. 6.1 (vérification) → 6.2 (correction) → 6.3 (backfill) → 6.4 (tests) → 6.5 (validation)

**Note** : Ce sprint peut être annulé si `enemy_mmr` est déjà correctement implémenté.

---

## 5. Priorités actuelles (résumé)

| Priorité | Sprint | Statut |
|----------|--------|--------|
| **Critique** | Sprint 1 | ✅ **TERMINÉ** (2026-02-06) |
| **Haute** | Sprint 2 | 🟠 À démarrer |
| **Haute** | Sprint 3 | 🟠 À démarrer |
| **Moyenne** | Sprint 4 | 🟡 À planifier |
| **Basse** | Sprint 5 | 🟢 À planifier |
| **Basse** | Sprint 6 | 🟢 À vérifier |

---

## 6. Colonne end_time (match_stats)

**Objectif** : Ajouter une colonne `end_time` (heure de fin du match) dans `match_stats`, dérivée de `start_time + time_played_seconds`, pour simplifier requêtes et affichages (médias, fenêtres temporelles, etc.).

### Planification

| Élément | Détail |
|--------|--------|
| **Colonne** | `end_time TIMESTAMP` (nullable si `time_played_seconds` manquant). |
| **Calcul** | `end_time = start_time + (time_played_seconds || ' seconds')::INTERVAL` (DuckDB) ou en Python `start_time + timedelta(seconds=time_played_seconds or 0)`. |
| **Sync / refresh** | Lors de l'insertion ou du remplacement d'une ligne dans `match_stats`, calculer et persister `end_time` en plus de `start_time` et `time_played_seconds`. |
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

*Dernière mise à jour : 2026-02-06 (Roadmap structurée en sprints avec tâches détaillées + règles tests obligatoires)*
