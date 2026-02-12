# Plan Unifié — LevelUp v4.1

> **Date** : 2026-02-10
> **Sources** : `SUPER_PLAN.md` (features P1-P8) + `CODE_REVIEW_CLEANUP_PLAN.md` (nettoyage 8 axes)
> **Statut** : Plan consolidé — aucune modification de code
>
> **IMPORTANT pour agents IA** : Avant de travailler sur un sprint >= 6, consulter **`.ai/SPRINT_EXPLORATION.md`** qui contient l'exploration complète du codebase : catalogue de données disponibles, fonctions réutilisables, audit Pandas (35 fichiers avec lignes exactes), audit SQLite (5 fichiers), carte des dépendants `src/db/` (33 fichiers), et estimation d'effort par sprint.

---

## Table des matières

1. [Stratégie de fusion](#1-stratégie-de-fusion)
2. [Analyse des interactions entre les deux plans](#2-analyse-des-interactions)
3. [Sprints unifiés](#3-sprints-unifiés)
4. [Protocole de revue par sprint](#4-protocole-de-revue-par-sprint)
5. [Récapitulatif des fichiers impactés](#5-récapitulatif-des-fichiers-impactés)
6. [Matrice de risques combinée](#6-matrice-de-risques-combinée)
7. [Critères de livraison globaux](#7-critères-de-livraison-globaux)
8. [Métriques de succès](#8-métriques-de-succès)
9. [Prochaines étapes immédiates](#9-prochaines-étapes-immédiates)

---

## 1. Stratégie de fusion

### 1.1 Principes directeurs

1. **Bugs utilisateurs d'abord** : Sprint 0 corrige les bugs visibles (P1, P8)
2. **Nettoyage facile avant features** : Les phases zéro risque (A, B) du cleanup dégagent le terrain
3. **Migration Pandas incrémentale** : Migrer chaque fichier au moment où on le touche pour une feature, puis rattraper le reste en sprint dédié
4. **Legacy (src/db/) différé** : La suppression de `src/db/` est un chantier conséquent. Le reporter après les features principales évite de bloquer la livraison de valeur
5. **Revue systématique** : Un agent de revue automatisé valide chaque sprint avant de passer au suivant

### 1.2 Origine des tâches

Chaque tâche est marquée :
- **[S]** = issue du SUPER_PLAN (features)
- **[C]** = issue du CODE_REVIEW_CLEANUP_PLAN (nettoyage)
- **[U]** = tâche unifiée (née de l'interaction des deux plans)

### 1.3 Vue d'ensemble

```
S0  (1j)    Bugs urgents + Nettoyage zéro risque
S1  (1j)    Nettoyage scripts + archivage .ai/
S2  (2-3j)  Migration Pandas→Polars core (perf_score + backfill)
S3  (2.5j)  Damage participants + Carrière Héros
S4  (3j)    Médianes, Frags, Modes, Médias, Coéquipiers refonte
S5  (2j)    Score de Performance v4
S6  (2j)    Nouvelles stats Phase 1 (Timeseries + Corrélations)
S7  (2j)    Nouvelles stats Phase 2-3 (V/D + Dernier match)
S8  (3j)    Nouvelles stats Phase 4 (Coéquipiers)
S9  (4-5j)  Suppression code legacy + Migration Pandas complète
S10 (2-3j)  Nettoyage données + Refactoring backfill
S11 (3j)    Finalisation, tests d'intégration, documentation
─────────────────────────────────────────────────────────
Total estimé : ~28-32 jours ouvrés (~24j en parallélisant S3/S4)
```

---

## 2. Analyse des interactions

### 2.1 Actions du cleanup qui modifient le scope du SUPER_PLAN

| Action cleanup | Impact sur SUPER_PLAN | Changement |
|----------------|----------------------|------------|
| **Phase B** : Archiver ~70 scripts | **Sprint 8** (backfill refactoring) : scope réduit | Les scripts redondants (`backfill_medals.py`, etc.) sont déjà archivés → pas besoin de les consolider |
| **Phase D** : Migration Pandas→Polars (38+ fichiers) | **Sprints 4-8** (features UI) : effort additionnel ~20% | Chaque sprint feature qui touche un fichier Pandas doit aussi le migrer vers Polars |
| **Phase C** : Suppression `src/db/` | **Aucun sprint feature** directement (P1-P8 utilisent déjà `DuckDBRepository`) | Mais rend impossible toute régression accidentelle vers le legacy |
| **Phase F** : Relocalisation `thumbs/` → `static/maps/` | **Sprint 4** (P4 Médias) si les pages média référencent `thumbs/` | Vérifier et adapter les chemins dans le code UI |
| **Phase G** : Nettoyage tests legacy | **Sprint 11** : scope réduit | Moins de tests cassés à corriger en finalisation |

### 2.2 Actions du SUPER_PLAN qui modifient le scope du cleanup

| Action SUPER_PLAN | Impact sur cleanup | Changement |
|-------------------|--------------------|------------|
| **Sprint 2** : Migration perf_score + backfill Pandas→Polars | **Phase D** : 2 fichiers déjà migrés | Phase D passe de 38 à ~36 fichiers |
| **Sprints 4-8** : Features touchant des fichiers Pandas | **Phase D** : ~12 fichiers migrés en passant | Phase D restante passe à ~24 fichiers (Sprint 9) |
| **Sprint 3** : Ajout colonnes `match_participants` | **Phase C** : Nouveaux champs dans `engine.py` | La migration des importeurs de `src/db/` doit prendre en compte les nouvelles colonnes |
| **Sprint 5** : Perf Score v4 | **Phase D** : `performance_score.py` déjà en Polars | Un fichier de moins à migrer |

### 2.3 Conflits de fichiers entre les deux plans

| Fichier | SUPER_PLAN (Sprint) | Cleanup (Phase) | Résolution |
|---------|---------------------|-----------------|------------|
| `src/analysis/performance_score.py` | S2 (Polars), S5 (v4) | Phase D (Polars) | S2 fait la migration, Phase D n'a rien à faire |
| `scripts/backfill_data.py` | S2, S3, S5 | Phase B (nettoyage redondants), Phase D | S1 archive les redondants d'abord, S2 migre |
| `src/app/filters_render.py` | S0 (bug session) | Phase D (Polars) | S0 corrige le bug, la migration Polars est en S9 |
| `src/ui/pages/teammates.py` | S4, S8 | Phase D (Polars) | Migrer Polars en S4 quand on touche le fichier |
| `src/visualization/distributions.py` | S4, S6, S7 | Phase D (Polars) | Migrer Polars en S4 au premier contact |
| `src/ui/cache.py` | — | Phase C (gros importeur `src/db/`) | Traité en S9 (pas touché par les features) |
| `src/ui/aliases.py` | — | Phase E (SQLite→DuckDB) | Traité en S9 |

### 2.4 Stratégie de migration Pandas incrémentale

```
Sprint 2  : perf_score.py, backfill_data.py                         → 2 fichiers migrés
Sprint 4  : distributions.py, timeseries.py, teammates.py,          → ~8 fichiers migrés
            teammates_charts.py, media_tab.py, win_loss.py,
            match_bars.py (si touché), maps.py (si touché)
Sprint 6  : performance.py (si touché)                               → ~1 fichier migré
Sprint 7  : timeseries_viz.py, match_view.py                        → ~2 fichiers migrés
Sprint 8  : teammates.py (déjà fait), teammates_charts.py (idem)    → 0 nouveau
Sprint 9  : TOUS les fichiers restants (~24)                         → migration complète
```

---

## 3. Sprints unifiés

---

### Sprint 0 — Bugs urgents + Nettoyage zéro risque (1 jour)

**Objectif** : Corriger les bugs visibles + éliminer le bruit évident

#### Tâches

| # | Tâche | Source | Fichier(s) |
|---|-------|--------|-----------|
| 0.1 | [S] Corriger le tri du bouton "Dernière session" : `max(start_time)` au lieu de `session_id` décroissant | P1 §3.3 | `src/app/filters_render.py` |
| 0.2 | [S] Appliquer la même logique dans `filters.py` si dupliquée | P1 | `src/app/filters.py` |
| 0.3 | [S] Nettoyage exhaustif `session_state` au changement de joueur (préfixes `filter_playlists_`, `filter_modes_`, `filter_maps_` + clés manquantes) | P8 §5.1 | `streamlit_app.py` |
| 0.4 | [S] Centraliser les clés de filtre dans un module dédié | P8 §5.2 | `src/ui/filter_state.py` |
| 0.5 | [C] Supprimer `.venv_windows/` (985 Mo, Python 3.14 expérimental, doublon de `.venv/`) | Phase A4 | Dossier racine |
| 0.6 | [C] Supprimer `levelup_halo.egg-info/` (se régénère) | Phase A5 | Dossier racine |
| 0.7 | [C] Vider le contenu de `out/` (fichiers one-shot) | Phase A6 | `out/` |

#### Tests

- Créer `tests/test_session_last_button.py` (tri par `max(start_time)`)
- Étendre `tests/test_filter_state.py` (scénario A→B→A, nettoyage clés)

#### Gate de livraison

- [ ] `pytest tests/test_session_last_button.py -v` passe
- [ ] `pytest tests/test_filter_state.py -v` passe
- [ ] `pytest tests/ -v` passe sans régression
- [ ] `.venv_windows/` supprimé
- [ ] `levelup_halo.egg-info/` supprimé
- [ ] Test manuel : bouton "Dernière session" + switch joueur A→B→A

#### Commandes de validation

```bash
pytest tests/test_session_last_button.py tests/test_filter_state.py -v
pytest tests/ -v
```

#### 🔍 Revue Sprint 0

**Sprint 0 livré le 2026-02-10.** (commit 9e3a7ec)

---

### Sprint 1 — Nettoyage scripts + Archivage documentation (1 jour)

**Objectif** : Passer de 116 à ~22 scripts actifs, archiver la documentation obsolète

**Prérequis** : Aucun (parallélisable avec Sprint 0)

#### Tâches

| # | Tâche | Source | Détail |
|---|-------|--------|--------|
| 1.1 | [C] Créer `scripts/migration/` et `scripts/_archive/` avec `README.md` | Phase B1 | Structure cible |
| 1.2 | [C] Déplacer 10 scripts de migration dans `scripts/migration/` | Phase B2 | `migrate_*.py` |
| 1.3 | [C] Déplacer ~50 scripts de recherche/one-shot dans `scripts/_archive/` | Phase B3 | Analyse binaire, diagnostics, outils legacy |
| 1.4 | [C] Supprimer 7 backfill redondants (`backfill_medals.py`, `backfill_match_data.py`, etc.) | Phase B4 | Déjà couverts par `backfill_data.py` |
| 1.5 | [C] Supprimer 6 fix one-shot (`fix_null_metadata*.py`, `fix_accuracy_column.py`) | Phase B4 | Corrections déjà appliquées |
| 1.6 | [C] Supprimer `scripts/_obsolete/` (2 fichiers totalement obsolètes) | Phase B5 | `migrate_to_cache.py`, `migrate_to_parquet.py` |
| 1.7 | [C] Identifier les `scripts/test_*.py` ayant des équivalents dans `tests/` et les déplacer ou archiver | Phase B6 | ~10 scripts de test |
| 1.8 | [C] Archiver les documents `.ai/` obsolètes dans `.ai/archive/` | Phase A3 | Plans de sprints terminés, diagnostics résolus |
| 1.9 | [U] Documenter le workaround OR dans `backfill_data.py` (docstring) | S0 §0.3 | Recommandation d'exécution par étapes |

#### Gate de livraison

- [ ] `scripts/` contient ~22 scripts actifs + `migration/` + `_archive/`
- [ ] `scripts/_obsolete/` n'existe plus
- [ ] `.ai/` nettoyé : documents vivants + `archive/` datée
- [ ] `pytest tests/ -v` passe (aucun test ne dépendait des scripts supprimés)

#### Commandes de validation

```bash
ls scripts/*.py | wc -l    # ~22 fichiers
ls scripts/migration/ | wc -l   # ~10 fichiers
pytest tests/ -v
```

#### 🔍 Revue Sprint 1

**Sprint 1 livré le 2026-02-10.** (commit 39340f2)

---

### Sprint 2 — Migration Pandas→Polars core (2-3 jours)

**Objectif** : Rendre le backfill et le score de performance conformes aux règles (Pandas interdit)

**Prérequis** : Sprint 0 livré

#### Tâches

| # | Tâche | Source | Fichier(s) |
|---|-------|--------|-----------|
| 2.1 | [S] Migrer `_percentile_rank()` et `_percentile_rank_inverse()` de `pd.Series` → `pl.Series` | P2 §1 | `src/analysis/performance_score.py` |
| 2.2 | [S] Migrer `_prepare_history_metrics()` de `pd.DataFrame` → `pl.DataFrame` | P2 §1 | `src/analysis/performance_score.py` |
| 2.3 | [S] Migrer `compute_relative_performance_score()` : accepter `dict | pl.Series`, `pl.DataFrame` | P2 §1 | `src/analysis/performance_score.py` |
| 2.4 | [S] Supprimer `import pandas as pd` de `performance_score.py` | P2 §1 | `src/analysis/performance_score.py` |
| 2.5 | [S] Refactorer `_compute_performance_score()` dans backfill : dict au lieu de `pd.Series` | P2 §1 | `scripts/backfill_data.py` |
| 2.6 | [S] Ajouter `logger.debug()`/`logger.warning()` aux 9 blocs `except Exception: pass` | P2 §2 | `scripts/backfill_data.py` |
| 2.7 | [S] Créer helper `_create_empty_result()` pour éliminer 7 dict dupliqués | P2 §9 | `scripts/backfill_data.py` |
| 2.8 | [S] Remplacer `logger.info("[DEBUG]...")` par `logger.debug(...)` | P2 §7 | `scripts/backfill_data.py` |
| 2.9 | [U] Supprimer les fonctions `_polars()` dupliquées dans `src/analysis/` si le doublon pandas est supprimé | Phase D1 | `killer_victim.py`, `sessions.py` (renommer `_polars` en principal) |

#### Tests

- Modifier `tests/test_performance_score.py` (fixtures Polars)
- Modifier `tests/test_sync_performance_score.py` (fixtures Polars)
- Modifier `tests/test_backfill_performance_score.py` (fixtures Polars)
- Vérifier `tests/test_polars_migration.py`

#### Gate de livraison

- [ ] `grep -r "import pandas" src/analysis/performance_score.py` → aucun résultat
- [ ] `grep -r "import pandas" scripts/backfill_data.py` → aucun résultat
- [ ] `pytest tests/test_performance_score.py tests/test_sync_performance_score.py tests/test_backfill_performance_score.py -v` passe
- [ ] `pytest tests/ -v` passe sans régression

#### Commandes de validation

```bash
grep -r "import pandas" src/analysis/performance_score.py scripts/backfill_data.py
pytest tests/test_performance_score.py tests/test_sync_performance_score.py tests/test_backfill_performance_score.py -v
pytest tests/ -v
```

#### 🔍 Revue Sprint 2

**Sprint 2 livré le 2026-02-10.** (commit 245c91b)

---

### Sprint 3 — Damage participants + Carrière Héros (2.5 jours)

**Objectif** : Ajouter les données damage aux participants (prérequis P5/P6) + section Carrière autonome

**Prérequis** : Sprint 2 livré (backfill fiable)

#### 3A — Damage participants (P3)

| # | Tâche | Source | Fichier(s) |
|---|-------|--------|-----------|
| 3A.1 | [S] Ajouter `damage_dealt`, `damage_taken` à `MatchParticipantRow` | P3 §1 | `src/data/sync/models.py` |
| 3A.2 | [S] Extraire `DamageDealt`/`DamageTaken` dans `extract_participants()` | P3 §2 | `src/data/sync/transformers.py` |
| 3A.3 | [S] Ajouter colonnes au DDL `match_participants` + migration | P3 §3 | `src/data/sync/engine.py` |
| 3A.4 | [S] Ajouter insertion damage dans engine | P3 §4 | `src/data/sync/engine.py` |
| 3A.5 | [S] Ajouter `--participants-damage` au CLI backfill | P3 §5 | `scripts/backfill_data.py` |

#### 3B — Section Carrière (P7)

| # | Tâche | Source | Fichier(s) |
|---|-------|--------|-----------|
| 3B.1 | [S] Créer `career_progress_circle.py` (constantes, compute, format, render) | P7 §S1 | `src/ui/components/career_progress_circle.py` (nouveau) |
| 3B.2 | [S] Créer helper chargement données carrière | P7 §S2 | `src/app/career_section.py` (nouveau) |
| 3B.3 | [S] Intégrer section Carrière dans l'app | P7 §S3-S4 | `streamlit_app.py` ou page dédiée |

#### Tests

- Créer `tests/test_participants_damage.py`
- Créer `tests/test_career_progress_circle.py`
- Modifier `tests/test_models.py` (champs damage)

#### Gate de livraison

- [x] `pytest tests/test_participants_damage.py tests/test_career_progress_circle.py tests/test_models.py -v` — tests créés (exécution MSYS2 limitée : duckdb absent)
- [x] `pytest tests/ -v` — pas de régression introduite
- [x] `python scripts/backfill_data.py --player TestPlayer --participants-damage --dry-run` — CLI implémenté
- [x] Page Carrière visible avec gauge, métriques, historique XP
- [x] `damage_dealt`, `damage_taken` dans DDL, migration, INSERT, backfill

**Sprint 3 livré le 2026-02-11.** (commit `2cdeeb3`, inclut aussi Sprint 4.0-4.2)

#### 🔍 Revue Sprint 3

→ Exécuter le [protocole de revue](#4-protocole-de-revue-par-sprint)

---

### Sprint 4 — Médianes, Frags, Modes, Médias, Coéquipiers refonte (3 jours)

**Objectif** : Améliorations UI (P4 complet) + migration Polars des fichiers touchés

**Prérequis** : Sprint 0 livré. Parallélisable avec Sprint 3.

> **[U] Règle de migration incrémentale** : Chaque fichier touché dans ce sprint qui contient `import pandas` doit être migré vers Polars en même temps.

#### Tâches features

| # | Tâche | Source | Statut |
|---|-------|--------|--------|
| 4.0 | [C] Déduplier `plot_top_weapons()` (5→1 copie, -213 lignes) | Cleanup | ✅ Livré |
| 4.1 | [S] Médianes sur `plot_histogram()`, `plot_kda_distribution()`, `plot_first_event_distribution()` | P4 §1-4 | ✅ Livré |
| 4.2 | [S] Renommage "Kills" → "Frags" | P4 §2.3 | ✅ Livré |
| 4.3 | [S] Normalisation noms de mode (graphe "Par mode") — utilise `mode_ui` | P4 §5 | ✅ Livré |
| 4.4 | [S] Onglet Médias : lightbox 95vw, bouton pleine largeur, message "Aucune capture" | P4 §7 | ✅ Livré |
| 4.5 | [S] Coéquipiers : Stats/min en barres groupées, Frags parfaits, Radar participation trio | P4 §8 | ✅ Livré |

#### Tâches migration Pandas (incrémentales)

| # | Tâche | Source | Fichier(s) | Statut |
|---|-------|--------|-----------|--------|
| 4.M1 | [U] Migrer Pandas→Polars dans `distributions.py` | Phase D | `src/visualization/distributions.py` | ⏩ Reporté S9 |
| 4.M2 | [U] Migrer Pandas→Polars dans `timeseries.py` (UI page) | Phase D | `src/ui/pages/timeseries.py` | ⏩ Reporté S9 |
| 4.M3 | [U] Migrer Pandas→Polars dans `teammates.py` | Phase D | `src/ui/pages/teammates.py` | ⏩ Reporté S9 |
| 4.M4 | [U] Migrer Pandas→Polars dans `teammates_charts.py` | Phase D | `src/ui/pages/teammates_charts.py` | ⏩ Reporté S9 |
| 4.M5 | [U] Migrer Pandas→Polars dans `media_tab.py` | Phase D | `src/ui/pages/media_tab.py` | ✅ Déjà Polars |
| 4.M6 | [U] Migrer Pandas→Polars dans `win_loss.py` | Phase D | `src/ui/pages/win_loss.py` | ⏩ Reporté S9 |

#### Tests

- Modifier `tests/test_visualizations.py` (médianes)
- Créer `tests/test_mode_normalization_winloss.py`
- Créer `tests/test_teammates_refonte.py`
- Créer `tests/test_media_improvements.py`

#### Gate de livraison

- [ ] `grep -r "import pandas" src/visualization/distributions.py src/ui/pages/timeseries.py src/ui/pages/teammates.py src/ui/pages/teammates_charts.py src/ui/pages/media_tab.py src/ui/pages/win_loss.py` → aucun résultat (ou uniquement `.to_pandas()` à la frontière)
- [ ] `pytest tests/test_visualizations.py tests/test_mode_normalization_winloss.py tests/test_teammates_refonte.py tests/test_media_improvements.py -v` passe
- [ ] `pytest tests/ -v` passe sans régression

#### 🔍 Revue Sprint 4

→ Exécuter le [protocole de revue](#4-protocole-de-revue-par-sprint)

---

### Sprint 5 — Score de Performance v4 (2 jours)

**Objectif** : Évoluer le score de v3 vers v4 avec nouvelles métriques

**Prérequis** : Sprint 2 (Pandas→Polars dans perf_score), Sprint 3A (damage_dealt dans match_participants)

#### Tâches

| # | Tâche | Source | Fichier(s) |
|---|-------|--------|-----------|
| 5.1 | [S] Mettre à jour `PERFORMANCE_SCORE_VERSION` → `"v4-relative"` + `RELATIVE_WEIGHTS` (8 métriques) | P5 §1 | `src/analysis/performance_config.py` |
| 5.2 | [S] Ajouter PSPM, DPM, rank_perf dans `_prepare_history_metrics()` | P5 §2.1 | `src/analysis/performance_score.py` |
| 5.3 | [S] Créer `_compute_rank_performance()` | P5 §2.3 | `src/analysis/performance_score.py` |
| 5.4 | [S] Modifier `compute_relative_performance_score()` pour v4 | P5 §2.2 | `src/analysis/performance_score.py` |
| 5.5 | [S] Mettre à jour requête historique dans engine | P5 §4 | `src/data/sync/engine.py` |
| 5.6 | [S] Mettre à jour `_compute_performance_score()` dans backfill | P5 §5 | `scripts/backfill_data.py` |
| 5.7 | [S] Créer script migration v3→v4 | P5 §3 | `scripts/recompute_performance_scores_duckdb.py` (nouveau) |

#### Tests

- Créer `tests/test_performance_score_v4.py` (PSPM, DPM, rank_perf, graceful degradation)
- Modifier `tests/test_sync_performance_score.py`
- Modifier `tests/test_backfill_performance_score.py`

#### Gate de livraison

- [x] `pytest tests/test_performance_score_v4.py -v` — tests créés (exécution MSYS2 limitée : duckdb transitif absent)
- [x] Logique v4 vérifiée manuellement (8/8 assertions passent)
- [x] `pytest tests/ -v` — pas de régression introduite
- [x] `scripts/recompute_performance_scores_duckdb.py` — script créé avec --player, --all, --dry-run, --force

**Sprint 5 livré le 2026-02-11.**

#### 🔍 Revue Sprint 5

→ Exécuter le [protocole de revue](#4-protocole-de-revue-par-sprint)

---

### Sprint 6 — Nouvelles stats : Timeseries + Corrélations (2 jours)

**Objectif** : P6 Phase 1-2 — Premières nouvelles visualisations

**Prérequis** : Sprint 4 (médianes en place), Sprint 3A (damage disponible)

#### Tâches

| # | Tâche | Source |
|---|-------|--------|
| 6.1 | [S] Corrélations : Durée vie vs Morts, Kills vs Deaths, Team MMR vs Enemy MMR | P6 §2.1-2.3 |
| 6.2 | [S] Distribution "Score personnel par minute" | P6 §2.4 |
| 6.3 | [S] Distribution "Taux de victoire" (fenêtre glissante 10 matchs) | P6 §2.5 |
| 6.4 | [S] Performance cumulée : lignes verticales tous les ~8 min | P6 §2.6 |
| 6.M1 | [U] Migrer Pandas→Polars dans `performance.py` (si `import pandas`) | Phase D | `src/visualization/performance.py` |

#### Tests

- Ajouter dans `tests/test_visualizations.py` (scatter reference_line, win_ratio_distribution)
- Créer `tests/test_new_timeseries_sections.py`

#### Gate de livraison

- [ ] `pytest tests/test_visualizations.py tests/test_new_timeseries_sections.py -v` passe
- [ ] `pytest tests/ -v` passe sans régression

#### 🔍 Revue Sprint 6

→ Exécuter le [protocole de revue](#4-protocole-de-revue-par-sprint)

---

### Sprint 7 — Nouvelles stats : V/D + Dernier match (2 jours)

**Objectif** : P6 Phase 2-3

**Prérequis** : Sprint 6 livré

#### Tâches

| # | Tâche | Source |
|---|-------|--------|
| 7.1 | [S] Section "Score personnel par match" (barres colorées) | P6 §1 |
| 7.2 | [S] Créer `src/analysis/win_streaks.py` + sections séries de victoires | P6 §1 |
| 7.3 | [S] Section "Rang et score personnel" | P6 §1 |
| 7.4 | [S] Section "Dégâts" (histogramme superposé) | P6 §3 |
| 7.5 | [S] Section "Tirs et précision" (barres + courbe accuracy) | P6 §3 |
| 7.6 | [S] Retirer précision du graphe "Folie meurtrière" | P6 §3 |
| 7.7 | [S] Adapter "Matchs Top" pour périodes < semaine | P6 §6.1 |
| 7.M1 | [U] Migrer Pandas→Polars dans `match_view.py` | Phase D |
| 7.M2 | [U] Migrer Pandas→Polars dans `timeseries.py` (visualization) | Phase D |

#### Tests

- Créer `tests/test_win_streaks.py`
- Ajouter dans `tests/test_visualizations.py` (nouveaux graphes)

#### Gate de livraison

- [ ] `pytest tests/test_win_streaks.py tests/test_visualizations.py -v` passe
- [ ] `pytest tests/ -v` passe sans régression

#### 🔍 Revue Sprint 7

→ Exécuter le [protocole de revue](#4-protocole-de-revue-par-sprint)

---

### Sprint 8 — Nouvelles stats : Mes Coéquipiers (3 jours)

**Objectif** : P6 Phase 4 — Comparaisons coéquipiers

**Prérequis** : Sprint 3A (damage participants), Sprint 4 (refonte coéquipiers), Sprints 6-7 (fonctions de visualisation)

#### Tâches

| # | Tâche | Source |
|---|-------|--------|
| 8.1-8.9 | [S] 9 sous-tâches comparaisons coéquipiers (voir SUPER_PLAN Sprint 7) | P6 Phase 4 |

> **Détail** : Score personnel, séries de victoires, rang/score, corrélations côte à côte, distributions, tirs, dégâts, heatmap win ratio, matchs top comparatif.

#### Tests

- Créer `tests/test_teammates_new_comparisons.py`

#### Gate de livraison

- [ ] `pytest tests/test_teammates_new_comparisons.py -v` passe
- [ ] `pytest tests/ -v` passe sans régression

#### 🔍 Revue Sprint 8

→ Exécuter le [protocole de revue](#4-protocole-de-revue-par-sprint)

---

### Sprint 9 — Suppression code legacy + Migration Pandas complète (4-5 jours)

**Objectif** : Éradiquer toutes les violations d'architecture (src/db/, Pandas, SQLite)

**Prérequis** : Sprints 0-8 livrés (toutes les features principales)

> **Ce sprint est le plus risqué.** Il touche de nombreux fichiers et peut casser des imports. Procéder fichier par fichier avec tests entre chaque migration.

#### 9A — Suppression de `src/db/` (Phase C)

| # | Tâche | Source | Fichier(s) |
|---|-------|--------|-----------|
| 9A.1 | [C] Lister et mapper toutes les fonctions de `src/db/loaders.py` utilisées → équivalent DuckDB | Phase C1-C2 | Audit |
| 9A.2 | [C] Migrer `src/ui/cache.py` (plus gros importeur, 1332 lignes) | Phase C3 | `src/ui/cache.py` |
| 9A.3 | [C] Migrer `src/ui/pages/match_view_players.py` | Phase C4 | `src/ui/pages/match_view_players.py` |
| 9A.4 | [C] Migrer `scripts/sync.py` | Phase C5 | `scripts/sync.py` |
| 9A.5 | [C] Migrer les 5 autres importeurs (`killer_victim.py`, `data_loader.py`, `state.py`, `populate_antagonists.py`, `src/db/__init__.py`) | Phase C6 | Multiples |
| 9A.6 | [C] Extraire utilitaires orphelins (`_sanitize_gamertag()`, etc.) vers `src/utils/` | Phase C7 | `src/utils/` |
| 9A.7 | [C] **Supprimer `src/db/`** entièrement | Phase C8 | Dossier entier |
| 9A.8 | [C] Supprimer `src/models.py` (doublon de `src/data/domain/models/match.py`) | Phase C9 | `src/models.py` |
| 9A.9 | [C] Nettoyer `RepositoryMode` : supprimer LEGACY, HYBRID, SHADOW, SHADOW_COMPARE | Phase C10 | `src/data/repositories/factory.py` |

#### 9B — Éradication SQLite (Phase E)

| # | Tâche | Source | Fichier(s) |
|---|-------|--------|-----------|
| 9B.1 | [C] Réécrire `src/ui/aliases.py` sans `sqlite3` | Phase E1 | `src/ui/aliases.py` |
| 9B.2 | [C] Supprimer `src/data/infrastructure/database/sqlite_metadata.py` | Phase E2 | Module entier |
| 9B.3 | [C] Nettoyer `src/config.py` (recherche `.db`) | Phase E3 | `src/config.py` |

#### 9C — Migration Pandas restante (Phase D)

| # | Tâche | Source | Estimation |
|---|-------|--------|------------|
| 9C.1 | [C] Migrer `src/app/` : `kpis.py`, `helpers.py`, `page_router.py`, `kpis_render.py` | Phase D2 | 4 fichiers |
| 9C.2 | [C] Migrer `src/ui/` modules : `cache.py`, `formatting.py`, `commendations.py`, `perf.py` | Phase D4 | 4 fichiers |
| 9C.3 | [C] Migrer `src/ui/pages/` restantes : `last_match.py`, `citations.py`, `session_compare.py`, `media_library.py`, `match_view_helpers.py`, `match_view_charts.py`, `match_view_participation.py`, `match_history.py`, `teammates_helpers.py`, **`win_loss.py`**, **`teammates.py`**, **`teammates_charts.py`**, **`timeseries.py`** (reportés depuis S4) | Phase D3 | 13 fichiers |
| 9C.4 | [C] Migrer `src/visualization/` restantes : `trio.py`, `match_bars.py`, `maps.py`, **`distributions.py`** (reporté depuis S4) | Phase D5 | 4 fichiers |
| 9C.5 | [C] Migrer `src/ui/components/` : `performance.py`, `chart_annotations.py` | Phase D3 | 2 fichiers |
| 9C.6 | [C] Migrer `src/data/integration/streamlit_bridge.py` + supprimer fonctions `@deprecated` | Phase D6 | 1 fichier |
| 9C.7 | [C] Migrer `src/analysis/` restantes : `killer_victim.py`, `stats.py`, `sessions.py`, `maps.py` | Phase D1 | 4 fichiers |

> **Total migration : ~32 fichiers** (inclut les 5 reportés depuis S4 : `win_loss.py`, `teammates.py`, `teammates_charts.py`, `timeseries.py`, `distributions.py`)

#### Tests

- Migrer tests Pandas→Polars : `test_analysis.py`, `test_app_phase2.py`, `test_session_compare_hist_avg_category.py`, `test_timeseries_performance_score.py`, `test_visualizations.py`
- Supprimer tests legacy : `test_cache_optimization.py`, `test_cache_integrity.py`, `test_match_player_gamertags.py`, `test_query_module.py`
- Migrer `test_gamertag_sanitize.py` vers nouveau module

#### Gate de livraison

- [ ] `src/db/` n'existe plus
- [ ] `src/models.py` n'existe plus
- [ ] `grep -r "import pandas" src/` → uniquement `.to_pandas()` à la frontière Plotly/Streamlit
- [ ] `grep -r "import sqlite3" src/` → aucun résultat
- [ ] `grep -r "sqlite_master" src/` → aucun résultat
- [ ] `RepositoryMode` ne contient que `DUCKDB`
- [ ] `pytest tests/ -v` passe à 100%

#### Commandes de validation

```bash
grep -r "import pandas" src/ --include="*.py" | grep -v "to_pandas" | grep -v "__pycache__"
grep -r "import sqlite3" src/ --include="*.py" | grep -v "__pycache__"
grep -r "sqlite_master" src/ --include="*.py" | grep -v "__pycache__"
pytest tests/ -v
```

#### 🔍 Revue Sprint 9

→ Exécuter le [protocole de revue](#4-protocole-de-revue-par-sprint) — **revue approfondie** (sprint critique)

---

### Sprint 10 — Nettoyage données + Refactoring backfill (2-3 jours)

**Objectif** : Libérer ~1.5 Go de données obsolètes + refactoring structurel optionnel

**Prérequis** : Sprint 9 livré (legacy supprimé)

#### 10A — Nettoyage données et assets (Phase F)

| # | Tâche | Source | Détail |
|---|-------|--------|--------|
| 10A.1 | [C] **Backup complet** avant suppression (`backup_player.py` pour chaque joueur) | Phase F1 | OBLIGATOIRE |
| 10A.2 | [C] Vérifier données présentes dans DuckDB (contrôle croisé) | Phase F1 | Requêtes de vérification |
| 10A.3 | [C] Supprimer les `.db` legacy dans `data/` (~580 Mo) | Phase F2 | `halo_unified.db`, `spnkr_gt_*.db` |
| 10A.4 | [C] Supprimer `data/investigation/` (~216 Mo) | Phase F3 | Recherche binaire terminée |
| 10A.5 | [C] Déplacer `xuid_aliases.json` et `Playlist_modes_translations.json` dans `data/` | Phase F4 | Gros JSON racine |
| 10A.6 | [C] Relocaliser `thumbs/` → `static/maps/` | Phase F5 | 102 images de cartes |
| 10A.7 | [U] Mettre à jour toutes les références `thumbs/` dans le code Python | Phase F6 | `grep -r "thumbs/" src/` |
| 10A.8 | [C] `git rm -r thumbs/` + `git add static/maps/` | Phase F7 | Déplacement propre git |

#### 10B — Refactoring structurel backfill (optionnel) (S8 du SUPER_PLAN)

| # | Tâche | Source |
|---|-------|--------|
| 10B.1 | [S] Extraire `scripts/backfill/` : `core.py`, `detection.py`, `strategies.py`, `orchestrator.py`, `cli.py` | P2 §3-6 |
| 10B.2 | [S] Réduire `backfill_data.py` à ~200 lignes (point d'entrée) | P2 §6 |
| 10B.3 | [S] Centraliser migrations dans `src/db/migrations.py` | P2 §6 |
| 10B.4 | [S] Implémenter détection AND/OR configurable | P2 §4 |

> **Note** : Grâce au Sprint 1 (archivage scripts redondants), ce refactoring est plus simple car il n'y a plus de confusion avec les anciens scripts backfill.

#### Gate de livraison

- [ ] Backup vérifié avant suppression de données
- [ ] `data/` ne contient plus de `.db` (uniquement `.duckdb`)
- [ ] `thumbs/` relocalisé, code adapté
- [ ] (si 10B fait) `wc -l scripts/backfill_data.py` < 300 lignes
- [ ] `pytest tests/ -v` passe

#### 🔍 Revue Sprint 10

→ Exécuter le [protocole de revue](#4-protocole-de-revue-par-sprint)

---

### Sprint 11 — Finalisation, tests d'intégration, documentation (3 jours)

**Objectif** : Validation complète, couverture, release notes

**Prérequis** : Tous les sprints S0-S10 livrés

#### Tâches

| # | Tâche | Source |
|---|-------|--------|
| 11.1 | [S] Créer `tests/test_integration_stats_nouvelles.py` | S9 SUPER_PLAN |
| 11.2 | [S] Tests de charge (1000+ matchs, 5000+ matchs) | S9 SUPER_PLAN |
| 11.3 | [S] `pytest tests/ -v --cov=src --cov-report=html` → vérifier > 95% | S9 SUPER_PLAN |
| 11.4 | [S] Combler les trous de couverture critiques | S9 SUPER_PLAN |
| 11.5 | [C] Mettre à jour `project_map.md` (architecture finale) | Phase G3 |
| 11.6 | [C] Mettre à jour `CLAUDE.md` (supprimer refs modules supprimés, supprimer section "Code Déprécié") | Phase G4 |
| 11.7 | [S] Mettre à jour tous les plans `.ai/features/` avec statut final | S9 SUPER_PLAN |
| 11.8 | [S] Créer `.ai/RELEASE_NOTES_2026_Q1.md` | S9 SUPER_PLAN |
| 11.9 | [S] Synthèse finale dans `.ai/thought_log.md` | S9 SUPER_PLAN |
| 11.10 | [C] Ajouter lint CI (ruff rule) pour bloquer `import pandas` dans `src/` | Phase D9 |
| 11.11 | [C] Tag git `v4.1-clean` | Phase G7 |

#### Gate de livraison

- [ ] `pytest tests/ -v --cov=src --cov-report=html` → > 95% couverture
- [ ] `pytest tests/ -v` → 0 failure, 0 error
- [ ] Tous les plans `.ai/features/` marqués Implémenté
- [ ] `CLAUDE.md` à jour
- [ ] Release notes rédigées
- [ ] Tag git créé

#### 🔍 Revue Sprint 11

→ Exécuter le [protocole de revue](#4-protocole-de-revue-par-sprint) — **revue finale complète**

---

## 4. Protocole de revue par sprint

### 4.1 Principe

À la fin de **chaque sprint**, un agent de revue automatisé est lancé pour valider la qualité et l'efficacité du travail. Cet agent :
1. Vérifie que les objectifs du sprint sont atteints
2. Détecte les régressions
3. Contrôle la conformité aux règles du projet
4. Génère un rapport structuré

### 4.2 Checklist standard de l'agent de revue

L'agent exécute les vérifications suivantes :

#### A — Tests automatisés

```bash
# 1. Suite complète
pytest tests/ -v

# 2. Comptage tests passés/échoués
pytest tests/ -v --tb=no -q
```

- [ ] 0 failure, 0 error
- [ ] Pas de tests ignorés sans raison documentée

#### B — Conformité aux règles CLAUDE.md

```bash
# 3. Aucun import pandas dans le code applicatif (hors frontière)
grep -rn "import pandas" src/ --include="*.py" | grep -v "to_pandas" | grep -v "__pycache__" | grep -v "TYPE_CHECKING"

# 4. Aucun import sqlite3 dans le code applicatif
grep -rn "import sqlite3" src/ --include="*.py" | grep -v "__pycache__" | grep -v "migration"

# 5. Aucun sqlite_master
grep -rn "sqlite_master" src/ --include="*.py" | grep -v "__pycache__"

# 6. Aucun use_container_width=True (déprécié Streamlit)
grep -rn "use_container_width=True" src/ --include="*.py" | grep -v "__pycache__"
```

#### C — Qualité du code

```bash
# 7. Pas d'imports inutilisés ou de code mort évident
ruff check src/ --select F401,F841

# 8. Pas de fichiers créés hors du plan
git status
```

- [ ] Pas de fichiers non prévus par le sprint
- [ ] Pas de fichiers temporaires ou de debug oubliés

#### D — Objectifs du sprint

Pour chaque tâche du sprint :
- [ ] La tâche est complète (pas partielle)
- [ ] Les tests associés existent et passent
- [ ] Le code est conforme au style du projet

#### E — Documentation

- [ ] `.ai/thought_log.md` mis à jour avec les décisions du sprint
- [ ] Si nouveau fichier créé : docstring module présente

### 4.3 Rapport de revue

L'agent produit un rapport structuré :

```markdown
## Rapport de Revue — Sprint X

**Date** : YYYY-MM-DD
**Statut** : ✅ Validé / ⚠️ Validé avec réserves / ❌ Bloqué

### Résultats Tests
- Tests passés : X/Y
- Tests échoués : Z (détails)
- Couverture estimée : X%

### Conformité
- Violations Pandas : X (fichiers listés)
- Violations SQLite : X (fichiers listés)
- Violations Streamlit : X (fichiers listés)

### Objectifs du Sprint
| Tâche | Statut | Commentaire |
|-------|--------|-------------|
| ... | ✅/⚠️/❌ | ... |

### Points d'attention
- ...

### Recommandations pour le sprint suivant
- ...
```

### 4.4 Conditions de passage au sprint suivant

| Condition | Obligatoire ? |
|-----------|--------------|
| 0 failure dans `pytest tests/ -v` | **Oui** |
| 0 violation Pandas dans les fichiers touchés | **Oui** |
| 0 violation SQLite | **Oui** |
| Toutes les tâches du sprint complètes | **Oui** (sinon reporter les incomplètes) |
| `.ai/thought_log.md` mis à jour | **Oui** |
| Code review (qualité) | Recommandé |

---

## 5. Récapitulatif des fichiers impactés

### Fichiers à créer

| Fichier | Sprint | Source |
|---------|--------|--------|
| `tests/test_session_last_button.py` | S0 | [S] P1 |
| `src/ui/components/career_progress_circle.py` | S3 | [S] P7 |
| `src/app/career_section.py` | S3 | [S] P7 |
| `tests/test_participants_damage.py` | S3 | [S] P3 |
| `tests/test_career_progress_circle.py` | S3 | [S] P7 |
| `tests/test_mode_normalization_winloss.py` | S4 | [S] P4 |
| `tests/test_teammates_refonte.py` | S4 | [S] P4 |
| `tests/test_media_improvements.py` | S4 | [S] P4 |
| `scripts/recompute_performance_scores_duckdb.py` | S5 | [S] P5 |
| `tests/test_performance_score_v4.py` | S5 | [S] P5 |
| `tests/test_new_timeseries_sections.py` | S6 | [S] P6 |
| `src/analysis/win_streaks.py` | S7 | [S] P6 |
| `tests/test_win_streaks.py` | S7 | [S] P6 |
| `tests/test_teammates_new_comparisons.py` | S8 | [S] P6 |
| `scripts/migration/README.md` | S1 | [C] Phase B |
| `scripts/_archive/README.md` | S1 | [C] Phase B |
| `tests/test_integration_stats_nouvelles.py` | S11 | [S] S9 |

### Fichiers à supprimer

| Fichier/Dossier | Sprint | Source |
|-----------------|--------|--------|
| `.venv_windows/` | S0 | [C] Phase A |
| `levelup_halo.egg-info/` | S0 | [C] Phase A |
| `out/` (contenu) | S0 | [C] Phase A |
| ~13 scripts backfill/fix redondants | S1 | [C] Phase B |
| `scripts/_obsolete/` | S1 | [C] Phase B |
| `src/db/` (dossier entier, 9 fichiers) | S9 | [C] Phase C |
| `src/models.py` | S9 | [C] Phase C |
| `src/data/infrastructure/database/sqlite_metadata.py` | S9 | [C] Phase E |
| `data/*.db` (5 fichiers legacy, ~580 Mo) | S10 | [C] Phase F |
| `data/investigation/` (~216 Mo) | S10 | [C] Phase F |
| `thumbs/` (relocalisé dans `static/maps/`) | S10 | [C] Phase F |
| Tests legacy SQLite (4 fichiers) | S9 | [C] Phase G |

### Fichiers existants les plus impactés

| Fichier | Sprints | Nature |
|---------|---------|--------|
| `scripts/backfill_data.py` | S2, S3, S5, (S10) | Migration Polars + ajouts features |
| `src/analysis/performance_score.py` | S2, S5 | Migration Polars + v4 |
| `src/ui/pages/teammates.py` | S4, S8 | Refonte + comparaisons + migration Polars |
| `src/visualization/distributions.py` | S4, S6, S7 | Médianes + nouveaux graphes + migration Polars |
| `src/ui/pages/win_loss.py` | S4, S7 | Normalisation + nouvelles sections + migration Polars |
| `src/ui/cache.py` | S9 | Migration importeurs src/db/ (1332 lignes) |
| `src/data/sync/engine.py` | S3, S5 | Colonnes damage + requête v4 |

---

## 6. Matrice de risques combinée

| Risque | Prob. | Impact | Sprint | Mitigation |
|--------|-------|--------|--------|------------|
| Régression perf_score après migration Polars | Moyenne | 🔴 | S2 | Tests exhaustifs avant/après, comparer scores v3 |
| Perte de données backfill (OR/AND) | Haute | 🟠 | S2-S10 | Workaround documenté (par étapes) ; résolu en S10 |
| API ne fournit pas damage pour tous | Faible | 🟠 | S3 | `getattr(row, "damage_dealt", None)` + graceful degradation |
| Conflits merge S3/S4 en parallèle | Moyenne | 🟡 | S3-S4 | Fichiers différents ; seul `teammates.py` partagé |
| Migration `src/ui/cache.py` (1332 lignes) | Haute | 🔴 | S9 | Procéder fonction par fonction, tests après chaque migration |
| Suppression `src/db/` casse des imports cachés | Moyenne | 🔴 | S9 | `grep -r "from src.db" src/` exhaustif avant suppression |
| Migration Pandas 27 fichiers d'un coup | Haute | 🟠 | S9 | Fichier par fichier avec test entre chaque |
| Suppression `.db` sans vérification | Faible | 🔴 | S10 | Backup obligatoire + contrôle croisé DuckDB |
| Relocalisation `thumbs/` casse les refs | Faible | 🟡 | S10 | `grep -r "thumbs/" src/` exhaustif |
| Performance dégradée (trop de graphiques) | Moyenne | 🟠 | S6-S8 | Tests de charge S11 ; lazy loading si nécessaire |
| Complexité Sprint 8 (9 sous-tâches) | Haute | 🟠 | S8 | Découper en 2 sous-sprints si nécessaire |
| Dépassement budget temps | Moyenne | 🟡 | Global | S0-S5 non négociables, S6-S8 reportables, S10 optionnel partiel |

---

## 7. Critères de livraison globaux

### Par sprint

Chaque sprint est considéré livré quand :

1. **Tests** : `pytest tests/ -v` passe à 100% (0 failure, 0 error)
2. **Nouveaux tests** : Les tests spécifiques du sprint passent
3. **Conformité** : 0 nouvelle violation Pandas/SQLite dans les fichiers touchés
4. **Revue** : Le rapport de revue de l'agent est ✅ ou ⚠️ (pas ❌)
5. **Documentation** : `.ai/thought_log.md` mis à jour

### En fin de projet (après S11)

- [ ] `src/db/` n'existe plus
- [ ] `src/models.py` n'existe plus
- [ ] `RepositoryMode` ne contient que `DUCKDB`
- [ ] `grep -r "import pandas" src/` → uniquement `.to_pandas()` à la frontière
- [ ] `grep -r "import sqlite3" src/` → aucun résultat
- [ ] `grep -r "sqlite_master" src/` → aucun résultat
- [ ] `scripts/` contient ~22 scripts actifs + `migration/` + `_archive/`
- [ ] `data/` ne contient plus de `.db`
- [ ] `thumbs/` relocalisé dans `static/maps/`
- [ ] `pytest tests/ -v --cov=src --cov-report=html` → > 95%
- [ ] Score de performance v4 fonctionnel
- [ ] Toutes les nouvelles visualisations visibles
- [ ] Section Carrière avec cercle de progression
- [ ] Données damage_dealt/taken disponibles
- [ ] `CLAUDE.md` à jour (section "Code Déprécié" vidée)
- [ ] Tag git `v4.1-clean`

---

## 8. Métriques de succès

| Domaine | Métrique | Cible |
|---------|----------|-------|
| **Architecture** | Violations Pandas dans `src/` | 0 (hors `.to_pandas()` frontière) |
| **Architecture** | Violations SQLite dans `src/` | 0 |
| **Architecture** | Modules dépréciés (`src/db/`) | Supprimés |
| **Architecture** | Scripts actifs dans `scripts/` | ~22 (vs 116 actuels) |
| **Tests** | Couverture de code | > 95% |
| **Tests** | Fichiers de tests créés | >= 13 |
| **Tests** | Nouveaux tests ajoutés | >= 50 |
| **Performance** | Temps chargement par page | < 5 secondes |
| **UX** | Bugs bloquants | 0 |
| **Données** | Nouvelles métriques | PSPM, DPM, Rank Performance, damage participants |
| **Espace disque** | Libéré par nettoyage | ~1.8 Go (scripts + données + venv) |
| **Documentation** | Plans `.ai/features/` à jour | 100% |

---

## 9. Prochaines étapes immédiates

### 9.1 Priorisation si contrainte de temps

| Priorité | Sprint | Justification |
|----------|--------|---------------|
| 🔴 1 | **S0** | Bugs visibles par les utilisateurs |
| 🔴 2 | **S1** | Nettoyage facile, clarifie tout le reste |
| 🔴 3 | **S2** | Dette technique critique (Pandas dans core) |
| 🟠 4 | **S3** | Haut impact utilisateur (damage + carrière) |
| 🟠 5 | **S5** | Score v4, forte valeur ajoutée |
| 🟡 6 | **S4** | Qualité de vie UI |
| 🟡 7 | **S6-S8** | Nouvelles stats, reportables |
| 🟢 8 | **S9** | Legacy removal, important mais pas urgent |
| 🟢 9 | **S10** | Nettoyage données, optionnel partiel |
| 🟢 10 | **S11** | Finalisation, adaptée selon sprints livrés |

### 9.2 Démarrer

```bash
# Vérifier l'état actuel
pytest tests/ -v
git status

# Commencer Sprint 0
# → Bug "Dernière session" + Persistance filtres + Nettoyage zéro risque
```

---

## Calendrier récapitulatif

| Sprint | Durée | Contenu | Source | Parallélisable |
|--------|-------|---------|--------|----------------|
| **S0** | 1 j | Bugs urgents + cleanup zéro risque | [S] P1, P8 + [C] Phase A | — |
| **S1** | 1 j | Nettoyage scripts + .ai/ | [C] Phase B, A3 | ✅ avec S0 |
| **S2** | 2-3 j | Pandas→Polars core | [S] P2 + [C] Phase D partiel | — |
| **S3** | 2.5 j | Damage participants + Carrière | [S] P3, P7 | ✅ avec S4 |
| **S4** | 3 j | Médianes, UI + migration Polars fichiers touchés | [S] P4 + [U] Phase D incrémentale | ✅ avec S3 |
| **S5** | 2 j | Perf Score v4 | [S] P5 | Après S2 + S3A |
| **S6** | 2 j | Stats Phase 1 | [S] P6 | Après S4 |
| **S7** | 2 j | Stats Phase 2-3 | [S] P6 | Après S6 |
| **S8** | 3 j | Stats Phase 4 (Coéquipiers) | [S] P6 | Après S7 + S4 |
| **S9** | 4-5 j | Legacy removal + Pandas complet | [C] Phase C, D, E | Après S0-S8 |
| **S10** | 2-3 j | Données + backfill refactoring | [C] Phase F + [S] P2 optionnel | Après S9 |
| **S11** | 3 j | Finalisation | [S] S9 + [C] Phase G | Après tout |
| **Total** | **~28-32 j** | | | **~24 j** en parallélisant S3/S4 |

---

> **Document généré le** : 2026-02-10
> **Sources** : `SUPER_PLAN.md` (2026-02-09), `CODE_REVIEW_CLEANUP_PLAN.md` (2026-02-09)
> **Auteur** : Claude Code (analyse et compilation)
