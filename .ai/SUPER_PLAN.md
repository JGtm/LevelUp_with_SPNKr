# Super Plan Consolidé — LevelUp v4.1

> **Date** : 2026-02-09
> **Statut** : Plan consolidé — aucune modification de code
> **Sources** : 7 documents de planification compilés après analyse du projet

---

## Table des matières

1. [Synthèse des plans](#1-synthèse-des-plans)
2. [Analyse des dépendances](#2-analyse-des-dépendances)
3. [Graphe de dépendances](#3-graphe-de-dépendances)
4. [État des tests existants](#4-état-des-tests-existants)
5. [Sprints](#5-sprints)
6. [Récapitulatif des fichiers impactés](#6-récapitulatif-des-fichiers-impactés)
7. [Matrice de risques](#7-matrice-de-risques)
8. [Critères de livraison](#8-critères-de-livraison)
9. [Métriques de succès](#9-métriques-de-succès)
10. [Prochaines étapes immédiates](#10-prochaines-étapes-immédiates)

---

## 1. Synthèse des plans

| # | Plan | Source | Priorité | Complexité |
|---|------|--------|----------|------------|
| **P1** | Correction bug "Dernière session" | `DERNIERE_SESSION_BOUTON_BUG_ANALYSIS.md` | 🔴 Urgente (bug visible) | Faible |
| **P2** | Refactoring backfill_data.py | `BACKFILL_SCRIPT_REVIEW.md` | 🔴 Critique (données non persistées) | Haute |
| **P3** | Damage participants (match_participants) | `PARTICIPANTS_DAMAGE_PLAN.md` | 🟠 Haute (prérequis P5, P6) | Moyenne |
| **P4** | Médianes + renommage Frags + normalisation modes + Médias + Coéquipiers | `DISTRIBUTIONS_MEDIAN_PLAN.md` | 🟡 Moyenne | Moyenne |
| **P5** | Score de performance v4 | `PERFORMANCE_SCORE_V4_PLAN.md` | 🟡 Moyenne | Haute |
| **P6** | Nouvelles visualisations statistiques | `PLAN_DETAIL_STATS_NOUVELLES.md` | 🟢 Normale | Très haute |
| **P7** | Section Carrière (progression Héros) | `CAREER_PROGRESS_HERO_PLAN.md` | 🟢 Normale (autonome) | Moyenne |
| **P8** | Persistance filtres par joueur / DB | `ANALYSE_PERSISTANCE_FILTRES_MULTI_JOUEURS.md` | 🔴 Urgente (bug UX) | Faible |

---

## 2. Analyse des dépendances

### 2.1 Dépendances critiques identifiées

```
P2 (Backfill refactoring) ──► P3 (Participants damage)
       │                           │
       │                           ▼
       │                      P5 (Perf Score v4)
       │                           │
       ▼                           ▼
  P3 utilise backfill         P6 (Nouvelles stats)
  pour --participants-damage  utilise damage_dealt, personal_score, rank
```

**Détail des dépendances** :

| Bloc | Dépend de | Raison |
|------|-----------|--------|
| **P1** (Bug session) | Rien | Bug autonome, corrigeable immédiatement |
| **P2** (Backfill) | Rien | Infrastructure de base, prérequis pour tout backfill fiable |
| **P3** (Damage participants) | **P2** (partiel) | Ajoute `--participants-damage` au backfill ; le commit final (P2-A) doit être fiable |
| **P4** (Médianes, Frags, etc.) | Rien | Touches UI indépendantes des données backfill |
| **P5** (Perf Score v4) | **P2** (Pandas→Polars), **P3** (damage_dealt dans history) | La v4 utilise `personal_score`, `damage_dealt`, `rank`, `team_mmr`, `enemy_mmr` — colonnes déjà en `match_stats` mais le calcul dans le backfill utilise Pandas (à migrer P2). Le DPM damage nécessite que le champ soit rempli. |
| **P6** (Nouvelles stats) | **P3** (damage participants pour comparaison coéquipiers), **P5** (score v4 pour distributions) | Les graphes de dégâts comparatifs (coéquipiers) nécessitent damage_dealt/taken dans `match_participants`. Le graphe "Distribution score de performance" utilise le score v4. |
| **P7** (Carrière Héros) | Rien | Section autonome (career_progression existe déjà en BDD) |
| **P8** (Persistance filtres) | Rien | Bug UX autonome : nettoyage session_state au changement de joueur |

### 2.2 Conflits de fichiers identifiés

Plusieurs plans touchent les mêmes fichiers. Ordre d'exécution critique :

| Fichier | Plans concernés | Risque de conflit |
|---------|----------------|-------------------|
| `scripts/backfill_data.py` | P2, P3, P5 | 🔴 Élevé — Refactoring P2 avant ajouts P3/P5 |
| `src/analysis/performance_score.py` | P2 (Pandas→Polars), P5 (v4) | 🔴 Élevé — Migration Pandas d'abord, puis v4 |
| `src/analysis/performance_config.py` | P5 | 🟢 Faible |
| `src/ui/pages/teammates.py` | P4, P6 | 🟠 Moyen — P4 (Stats/min barres, radar participation, frags parfaits) puis P6 (nouvelles sections) |
| `src/ui/pages/timeseries.py` | P4, P6 | 🟠 Moyen — P4 (médianes, renommage) puis P6 (nouvelles sections) |
| `src/ui/pages/win_loss.py` | P4 (normalisation modes), P6 (personal score, streaks) | 🟡 Faible — Sections différentes |
| `src/visualization/distributions.py` | P4 (médiane), P6 (nouveaux graphes) | 🟡 Faible — Ajouts indépendants |
| `src/data/sync/models.py` | P3 | 🟢 Faible |
| `src/data/sync/transformers.py` | P3 | 🟢 Faible |
| `src/data/sync/engine.py` | P3, P5 | 🟡 Faible — Sections différentes |
| `src/ui/pages/media_tab.py` | P4 | 🟢 Faible |
| `src/ui/pages/teammates_charts.py` | P4, P6 | 🟠 Moyen — P4 (frags parfaits) puis P6 (nouvelles comparaisons) |
| `src/app/filters_render.py` | P1, P8 | 🟠 Moyen — P1 (tri session) puis P8 (sauvegarde/nettoyage) |
| `streamlit_app.py` | P8 | 🟢 Faible |
| `src/ui/filter_state.py` | P8 | 🟢 Faible |

### 2.3 Dette technique à résoudre en prérequis

**Constat après analyse du code** :

1. **`performance_score.py`** (L.8-9) : `import pandas as pd` + `import polars as pl` — violation règle CLAUDE.md. Fonctions `_percentile_rank`, `_prepare_history_metrics`, `compute_relative_performance_score` utilisent toutes `pd.Series` / `pd.DataFrame`.
2. **`backfill_data.py`** (L.119) : `import pandas as pd` — violation règle. `_compute_performance_score` (L.698) crée un `pd.Series`.
3. **`test_performance_score.py`** (L.3) : `import pandas as pd` — les tests utilisent Pandas. Il faudra les migrer en parallèle.
4. **`test_visualizations.py`** (L.18, 32) : `import pandas as pd`, fixtures en Pandas — acceptable car frontière Plotly (CLAUDE.md autorise `.to_pandas()` à la frontière).

---

## 3. Graphe de dépendances (ordre d'exécution)

```
Semaine 1 (Sprint 0 + 1)
═══════════════════════════════════════════════════
  P1 (Bug session)          ─── Autonome, immédiat
  P2-A (Commit final)       ─── Déjà fait (✅)
  P2-B (Pandas → Polars     ─── Prérequis P5
        dans perf_score.py
        et backfill_data.py)
  P2-C (Logs exceptions)    ─── Amélioration backfill

Semaine 2 (Sprint 2)
═══════════════════════════════════════════════════
  P3 (Damage participants)  ─── Prérequis P5 DPM, P6 comparaisons
  P7 (Carrière Héros)       ─── Autonome, parallélisable

Semaine 3 (Sprint 3)
═══════════════════════════════════════════════════
  P4 (Médianes, Frags,      ─── Autonome sur UI
      modes, Médias,
      Coéquipiers refonte)

Semaine 4 (Sprint 4)
═══════════════════════════════════════════════════
  P5 (Perf Score v4)        ─── Dépend de P2-B, P3

Semaines 5-7 (Sprints 5-7)
═══════════════════════════════════════════════════
  P6 (Nouvelles stats)      ─── Dépend de P3, P5 (partiellement)
    Phase 1 : Timeseries
    Phase 2 : Victoires/Défaites
    Phase 3 : Dernier match
    Phase 4 : Mes coéquipiers

Semaine 8 (Sprint 8)
═══════════════════════════════════════════════════
  P2-D (Refactoring          ─── Découpage fichier, table backfill_status
        structurel backfill)
```

---

## 4. État des tests existants

### 4.1 Tests actuels (65 fichiers)

| Domaine | Fichiers de test | Couverture |
|---------|-----------------|------------|
| Performance score | `test_performance_score.py` (7 tests v2), `test_sync_performance_score.py` (7 tests), `test_backfill_performance_score.py` (8 tests), `test_timeseries_performance_score.py` | ✅ Bonne pour v3 |
| Visualisations | `test_visualizations.py` (~60 tests : distributions, timeseries, radar, barres, etc.) | ✅ Bonne |
| Sessions | `test_sessions_advanced.py`, `test_sessions_teammates.py`, `test_session_compare_hist_avg_category.py` | ✅ Moyenne |
| Sync/Engine | `test_sync_engine.py`, `test_sync_cli_integration.py`, `test_sync_ui.py` | ✅ Moyenne |
| Modèles | `test_models.py`, `test_parsers.py`, `test_transformers_*.py` | ✅ Bonne |
| DuckDB | `test_duckdb_repository.py`, `test_duckdb_repo_regressions.py`, `test_connection_duckdb.py` | ✅ Bonne |
| Médias | `test_media_*.py` (4 fichiers) | ✅ Moyenne |
| Participation | `test_participation_radar.py`, `test_objective_participation.py` | ✅ Moyenne |
| Polars migration | `test_polars_migration.py` | ✅ Spécifique |
| Killer/Victim | `test_killer_victim_*.py` (2 fichiers) | ✅ Bonne |

### 4.2 Tests à créer ou modifier par plan

| Plan | Tests à créer | Tests à modifier |
|------|---------------|------------------|
| **P1** | `test_session_last_button.py` (tri par max(start_time)) | — |
| **P8** | Étendre `test_filter_state.py` ou `scripts/test_filter_persistence_by_player.py` (nettoyage clés, A→B→A) | — |
| **P2** | `test_perf_score_polars_only.py` (vérifier que Pandas n'est plus requis) | `test_performance_score.py` (migrer fixtures Pandas→Polars), `test_backfill_performance_score.py` (idem) |
| **P3** | `test_participants_damage.py` (extraction, insertion, backfill) | `test_models.py` (MatchParticipantRow avec damage) |
| **P4** | `test_distributions_median.py` (médiane sur 6 graphes), `test_mode_normalization.py` (graphe "Par mode") | `test_visualizations.py` (plot_histogram show_median, plot_kda_distribution médiane, plot_first_event médianes) |
| **P5** | `test_performance_score_v4.py` (PSPM, DPM, rank_perf, graceful degradation) | `test_sync_performance_score.py` (nouvelles colonnes history), `test_backfill_performance_score.py` |
| **P6** | `test_win_streaks.py`, `test_new_visualizations.py` (personal score, correlations, damage distributions, shots accuracy) | `test_visualizations.py` (nouvelles fonctions) |
| **P7** | `test_career_progress_circle.py` (compute_percent, xp_remaining, format_xp, rang 272, fallback) | — |

---

## 5. Sprints

### Sprint 0 — Bug Fix Urgent (½ jour)

**Objectif** : Corriger le bug visible pour les utilisateurs

| # | Tâche | Fichier(s) | Tests |
|---|-------|-----------|-------|
| 0.1 | Corriger le tri du bouton "Dernière session" : remplacer le tri par `session_id` décroissant par `max(start_time)` par session (P1, §3.3) | `src/app/filters_render.py` : `_session_labels_ordered_by_last_match()` | Créer `tests/test_session_last_button.py` |
| 0.2 | Appliquer la même logique dans `filters.py` (si logique dupliquée) | `src/app/filters.py` | Idem |
| 0.3 | Documenter le workaround pour la détection OR/AND dans backfill sans refonte immédiate. Ajouter exemples dans docstring et `.ai/BACKFILL_SCRIPT_REVIEW.md` | `.ai/BACKFILL_SCRIPT_REVIEW.md`, `scripts/backfill_data.py` (docstring) | — |

> **Workaround OR documenté** : Au lieu de `--all-data`, recommander l'exécution par étapes :
> ```bash
> python scripts/backfill_data.py --all --medals --events --skill
> python scripts/backfill_data.py --all --performance-scores --sessions
> ```

**Gate de livraison** :
- [ ] `pytest tests/test_session_last_button.py -v` passe
- [ ] `pytest tests/ -v` (suite complète) passe sans régression
- [ ] Test manuel : cliquer "Dernière session" pour JGtm → session la plus récente sélectionnée

**Commandes de validation** :
```bash
pytest tests/test_session_last_button.py -v
pytest tests/ -v
streamlit run streamlit_app.py  # Vérifier bouton "Dernière session"
```

**Livrables** :
- Code corrigé dans `src/app/filters_render.py` et `src/app/filters.py`
- Nouveau fichier `tests/test_session_last_button.py`
- Mise à jour `.ai/BACKFILL_SCRIPT_REVIEW.md` (workaround OR documenté)
- Mise à jour `.ai/thought_log.md`

---

### Sprint 0bis — Persistance filtres multi-joueurs (P8) (½–1 jour)

**Objectif** : Rétablir la conservation des filtres (sélectionnés/désélectionnés) par joueur malgré les changements de DB. Source : `ANALYSE_PERSISTANCE_FILTRES_MULTI_JOUEURS.md`.

**Prérequis** : Aucun (parallélisable avec Sprint 0)

| # | Tâche | Source | Fichier(s) | Tests |
|---|-------|--------|-----------|-------|
| 0bis.1 | Nettoyage exhaustif au changement de joueur : supprimer toutes les clés dont le nom **commence par** `filter_playlists_`, `filter_modes_`, `filter_maps_` (widgets checkboxes) | P8 §5.1 | `streamlit_app.py` (bloc changement de joueur) | — |
| 0bis.2 | Ajouter au nettoyage les clés manquantes : `gap_minutes`, `_latest_session_label`, `_trio_latest_session_label`, `min_matches_maps`, `_min_matches_maps_auto`, `min_matches_maps_friends`, `_min_matches_maps_friends_auto` | P8 §5.1 | `streamlit_app.py` | — |
| 0bis.3 | Centraliser la liste des clés et préfixes dans un module (ex. `src/ui/filter_state.py` ou `src/app/filter_keys.py`) : `FILTER_DATA_KEYS`, `FILTER_WIDGET_KEY_PREFIXES`, fonction `get_all_filter_keys_to_clear(session_state)` | P8 §5.2 | `src/ui/filter_state.py` ou nouveau `src/app/filter_keys.py`, `streamlit_app.py` | — |
| 0bis.4 | Tests : scénario A→B→A (isolation), cohérence checkboxes après switch, extension de `test_filter_state.py` ou `scripts/test_filter_persistence_by_player.py` | P8 §5.6 | `tests/test_filter_state.py` ou script existant | Créer/étendre tests |

**Gate de livraison** :
- [ ] Après changement de joueur, aucune clé `session_state` ne commence par `filter_playlists_`, `filter_modes_`, `filter_maps_`
- [ ] Test manuel : joueur A (filtres X) → joueur B (filtres Y) → retour A → les filtres de A sont identiques à X
- [ ] `pytest tests/test_filter_state.py -v` passe (et nouveaux tests persistance multi-joueurs si ajoutés)

**Commandes de validation** :
```bash
pytest tests/test_filter_state.py -v
streamlit run streamlit_app.py  # Switch A → B → A, vérifier filtres conservés
```

**Livrables** :
- Code : `streamlit_app.py` (nettoyage exhaustif), `src/ui/filter_state.py` ou `src/app/filter_keys.py` (centralisation)
- Tests : extension tests persistance filtres
- Mise à jour `docs/FILTER_PERSISTANCE.md` et `.ai/thought_log.md`

**Optionnel (phases ultérieures P8)** : Scopage des clés des widgets par joueur (`checkbox_filter.py`) ; garde sur la sauvegarde automatique ; éviter double chargement. Voir `.ai/ANALYSE_PERSISTANCE_FILTRES_MULTI_JOUEURS.md` §5.3–5.5.

---

### Sprint 1 — Assainissement backfill & migration Pandas→Polars (2 jours)

**Objectif** : Rendre le backfill fiable et conforme aux règles du projet (Pandas interdit)

**Prérequis** : Sprint 0 livré

| # | Tâche | Source | Fichier(s) | Tests |
|---|-------|--------|-----------|-------|
| 1.1 | Migrer `_percentile_rank()` et `_percentile_rank_inverse()` de `pd.Series` vers `pl.Series` (ou `np.ndarray`) | P2 §1 | `src/analysis/performance_score.py` L.50-77 | Modifier `tests/test_performance_score.py` (fixtures Polars) |
| 1.2 | Migrer `_prepare_history_metrics()` de `pd.DataFrame` vers `pl.DataFrame` | P2 §1 | `src/analysis/performance_score.py` L.80-135 | Idem |
| 1.3 | Migrer `compute_relative_performance_score()` : accepter `row: dict \| pl.Series`, `df_history: pl.DataFrame` ; supprimer `_normalize_df` | P2 §1 | `src/analysis/performance_score.py` L.138+ | Modifier `tests/test_sync_performance_score.py`, `tests/test_backfill_performance_score.py` |
| 1.4 | Supprimer `import pandas as pd` de `performance_score.py` | P2 §1 | `src/analysis/performance_score.py` L.8 | `test_polars_migration.py` (vérifier aucun import pandas) |
| 1.5 | Refactorer `_compute_performance_score()` dans backfill pour utiliser un dict au lieu de `pd.Series` ; supprimer `import pandas as pd` | P2 §1 | `scripts/backfill_data.py` L.119, 670-720 | `tests/test_backfill_performance_score.py` |
| 1.6 | Ajouter `logger.debug()`/`logger.warning()` aux 9 blocs `except Exception: pass` | P2 §2 | `scripts/backfill_data.py` L.347, 413, 450, 678, 834, 908, 930, 951, 976 | Test manuel (vérifier logs) |
| 1.7 | Créer helper `_create_empty_result()` pour éliminer les 7 dict dupliqués | P2 §9 | `scripts/backfill_data.py` L.1153+ | — |
| 1.8 | Remplacer `logger.info("[DEBUG]...")` par `logger.debug(...)` | P2 §7 | `scripts/backfill_data.py` L.481-531 | — |

**Gate de livraison** :
- [ ] `pytest tests/test_performance_score.py -v` passe (avec fixtures Polars)
- [ ] `pytest tests/test_sync_performance_score.py -v` passe
- [ ] `pytest tests/test_backfill_performance_score.py -v` passe
- [ ] `grep -r "import pandas" src/analysis/performance_score.py` → aucun résultat
- [ ] `grep -r "import pandas" scripts/backfill_data.py` → aucun résultat
- [ ] `pytest tests/ -v` (suite complète) passe sans régression

**Commandes de validation** :
```bash
pytest tests/test_performance_score.py tests/test_sync_performance_score.py tests/test_backfill_performance_score.py -v
grep -r "import pandas" src/analysis/performance_score.py scripts/backfill_data.py
pytest tests/ -v
python scripts/backfill_data.py --player TestPlayer --medals --dry-run
```

**Livrables** :
- Code migré Polars dans `src/analysis/performance_score.py` et `scripts/backfill_data.py`
- Tests migrés dans `tests/test_performance_score.py`, `tests/test_sync_performance_score.py`, `tests/test_backfill_performance_score.py`
- Mise à jour `.ai/thought_log.md`
- Mise à jour `.ai/BACKFILL_SCRIPT_REVIEW.md` (statut des correctifs)

---

### Sprint 2 — Damage participants + Carrière Héros (2.5 jours)

**Objectif** : Ajouter les données damage aux participants (prérequis P5/P6) + section Carrière autonome

**Prérequis** : Sprint 1 livré (backfill fiable)

#### 2A — Damage participants (P3)

| # | Tâche | Source | Fichier(s) |
|---|-------|--------|-----------|
| 2A.1 | Ajouter `damage_dealt: float \| None`, `damage_taken: float \| None` à `MatchParticipantRow` | P3 §1 | `src/data/sync/models.py` L.302+ |
| 2A.2 | Extraire `DamageDealt`/`DamageTaken` dans `extract_participants()` | P3 §2 | `src/data/sync/transformers.py` L.1162+ |
| 2A.3 | Ajouter colonnes `damage_dealt FLOAT, damage_taken FLOAT` au DDL `match_participants` | P3 §3.1 | `src/data/sync/engine.py` L.146+ |
| 2A.4 | Ajouter migration colonnes dans `_ensure_match_participants_rank_score()` | P3 §3.2 | `src/data/sync/engine.py` L.425+ |
| 2A.5 | Ajouter `damage_dealt`, `damage_taken` dans `_insert_participant_rows()` (engine) | P3 §4 | `src/data/sync/engine.py` L.1101+ |
| 2A.6 | Ajouter `_ensure_match_participants_columns()` dans backfill pour damage | P3 §5.1 | `scripts/backfill_data.py` L.295+ |
| 2A.7 | Ajouter `_insert_participant_rows()` dans backfill pour damage | P3 §5.2 | `scripts/backfill_data.py` L.321+ |
| 2A.8 | Ajouter option `--participants-damage` et `--force-participants-damage` au CLI | P3 §5.6 | `scripts/backfill_data.py` (main, arguments) |
| 2A.9 | Ajouter `participants_damage = True` dans le bloc `if all_data:` | P3 §5.4 | `scripts/backfill_data.py` L.1080+ |
| 2A.10 | Ajouter paramètres et logique dans `backfill_player_data()`, `backfill_all_players()`, `_find_matches_missing_data()` | P3 §5.3-5.5 | `scripts/backfill_data.py` |

**Tests Sprint 2A** :
- Créer `tests/test_participants_damage.py` :
  - Test extraction `extract_participants()` retourne damage_dealt/taken
  - Test insertion avec colonnes damage
  - Test migration colonnes (DB existante sans damage → ALTER TABLE)
  - Test backfill `--participants-damage`
- Modifier `tests/test_models.py` : validation MatchParticipantRow avec damage

#### 2B — Section Carrière (P7)

| # | Tâche | Source | Fichier(s) |
|---|-------|--------|-----------|
| 2B.1 | Créer `src/ui/components/career_progress_circle.py` : constantes `XP_HERO_TOTAL = 9_319_350`, `RANK_MAX = 272` | P7 §S1.1 | Nouveau fichier |
| 2B.2 | Implémenter `compute_career_progress_percent()` (approche B : par XP, fallback par rang) | P7 §S1.2 | `career_progress_circle.py` |
| 2B.3 | Implémenter `compute_xp_remaining()`, `format_xp_number()` | P7 §S1.3-S1.4 | `career_progress_circle.py` |
| 2B.4 | Implémenter `render_career_progress_circle()` (Plotly gauge) | P7 §S1.5 | `career_progress_circle.py` |
| 2B.5 | Créer ou compléter le helper de chargement données carrière (BDD puis API) | P7 §S2.1-S2.4 | `src/app/career_section.py` (nouveau) ou helper existant |
| 2B.6 | Implémenter `render_career_section()` : rangée 5 cases (XP gagnée, XP restante, Total requis, Rang/272, Cercle) | P7 §S3 | `career_section.py` |
| 2B.7 | Intégrer dans la partie Carrière de l'app | P7 §S4 | `streamlit_app.py` ou page dédiée |

**Tests Sprint 2B** :
- Créer `tests/test_career_progress_circle.py` :
  - Test rang 1 → ~0 %
  - Test rang 135 → ~50 % (approx)
  - Test rang 272 → 100 %, xp_remaining = 0
  - Test sans données → fallback ou message
  - Test format_xp_number (9319350 → "9 319 350")
  - Test compute_xp_remaining (max(0, ...))

**Gate de livraison** :
- [ ] `pytest tests/test_participants_damage.py -v` passe
- [ ] `pytest tests/test_career_progress_circle.py -v` passe
- [ ] `pytest tests/test_models.py -v` passe (avec champs damage)
- [ ] `pytest tests/ -v` passe sans régression
- [ ] Test d'intégration backfill : `python scripts/backfill_data.py --player JGtm --participants-damage --dry-run`

**Commandes de validation** :
```bash
pytest tests/test_participants_damage.py tests/test_career_progress_circle.py tests/test_models.py -v
python scripts/backfill_data.py --player TestPlayer --participants-damage --dry-run
python scripts/backfill_data.py --player TestPlayer --participants-damage --max-matches 10
python scripts/backfill_data.py --player TestPlayer --all-data --max-matches 5
pytest tests/ -v
streamlit run streamlit_app.py  # Vérifier section Carrière
```

**Livrables** :
- Code participants damage : `src/data/sync/models.py`, `transformers.py`, `engine.py`, `scripts/backfill_data.py`
- Code section Carrière : `src/ui/components/career_progress_circle.py`, `src/app/career_section.py`
- Tests : `tests/test_participants_damage.py`, `tests/test_career_progress_circle.py`
- Mise à jour `.ai/thought_log.md`
- Mise à jour `.ai/features/PARTICIPANTS_DAMAGE_PLAN.md` (statut : Implémenté)
- Mise à jour `.ai/features/CAREER_PROGRESS_HERO_PLAN.md` (statut : Implémenté)

---

### Sprint 3 — Médianes, Frags, Modes, Médias, Coéquipiers refonte (3 jours)

**Objectif** : Améliorations UI (P4 complet)

**Prérequis** : Sprint 0 livré (pour filters). Pas de dépendance sur Sprint 1-2.

**Note** : Ce sprint est parallélisable avec Sprint 2 si 2 développeurs.

#### 3A — Médianes sur distributions (P4 §1-4)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 3A.1 | Ajouter param `show_median: bool = True` à `plot_histogram()` ; si True : `fig.add_vline(x=median)` + annotation | `src/visualization/distributions.py` L.547+ |
| 3A.2 | Ajouter médiane à `plot_kda_distribution()` : `np.median(x)` + vline + annotation | `src/visualization/distributions.py` L.28+ |
| 3A.3 | Ajouter médianes à `plot_first_event_distribution()` : 2 vlines (kill + mort), style différent des moyennes | `src/visualization/distributions.py` L.1135+ |

#### 3B — Renommage "Kills" → "Frags" (P4 §2.3)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 3B.1 | Remplacer titre "Distribution des Kills" → "Distribution des frags" | `src/ui/pages/timeseries.py` |
| 3B.2 | Remplacer `x_label="Kills"` → `x_label="Frags"` | `src/ui/pages/timeseries.py` |
| 3B.3 | Adapter messages `st.info` (données de frags) | `src/ui/pages/timeseries.py` |

#### 3C — Normalisation noms de mode (P4 §5)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 3C.1 | Pour le graphe "Par mode" (Victoires/défaites) : appliquer `normalize_mode_label_fn` aux labels | `src/ui/pages/win_loss.py` L.137-149 |
| 3C.2 | Si nécessaire : passer `normalize_mode_label_fn` via `render_win_loss_page` depuis le routeur | `src/app/page_router.py`, `src/ui/pages/win_loss.py` |

#### 3D — Onglet Médias (P4 §7)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 3D.1 | Lightbox adapté à la fenêtre (CSS max-width/max-height) | `src/ui/pages/media_tab.py` L.121-139 |
| 3D.2 | Bouton "Ouvrir le match" en pleine largeur (display:block; width:100%) | `src/ui/pages/media_tab.py` L.98-105 |
| 3D.3 | Message "Aucune capture détectée" si `mine.is_empty()` | `src/ui/pages/media_tab.py` |
| 3D.4 | Étudier et implémenter clic thumbnail → lightbox (option A, B ou C) | `src/ui/pages/media_tab.py`, `src/ui/components/media_thumbnail.py`, `src/ui/components/media_lightbox.py` |

#### 3E — Coéquipiers : Stats/min en barres + Frags parfaits + Radar participation trio (P4 §8)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 3E.1 | Supprimer le tableau + radar de la section "Stats par minute" (vue trio) ; remplacer par un **graphe en barres groupées** | `src/ui/pages/teammates.py` L.804-857 |
| 3E.2 | Ajouter graphe "Frags parfaits" après "Tirs à la tête" dans `render_metric_bar_charts` | `src/ui/pages/teammates_charts.py`, `src/ui/pages/teammates.py` (enrichissement DataFrames avec `perfect_kills` via `DuckDBRepository.count_perfect_kills_by_match`) |
| 3E.3 | Ajouter section "Profil de participation" (radar 6 axes) en vue trio : participation moyenne des 3 joueurs sur les matchs filtrés | `src/ui/pages/teammates.py` (nouvelle fonction `_render_trio_participation_radar`) ; réutilisation de `create_participation_profile_radar`, `compute_participation_profile` |

**Tests Sprint 3** :
- Modifier `tests/test_visualizations.py` :
  - `test_plot_histogram_with_median` : vérifier que la figure a une shape (vline) quand `show_median=True`
  - `test_plot_histogram_without_median` : `show_median=False` → pas de vline médiane
  - `test_plot_kda_distribution_has_median` : vérifier annotation médiane
  - `test_plot_first_event_distribution_has_median` : vérifier 2 annotations médianes (kill + mort)
- Créer `tests/test_mode_normalization_winloss.py` :
  - Vérifier que les labels du graphe "Par mode" correspondent à `normalize_mode_label`
- Créer `tests/test_media_improvements.py` (ou ajouter dans `test_media_tab_sprint5.py`) :
  - Test message "Aucune capture" quand df vide
- Créer `tests/test_teammates_refonte.py` :
  - Test graphe barres groupées stats/min (3 joueurs × 3 métriques)
  - Test frags parfaits (colonne ajoutée)
  - Test radar participation trio (3 profils)

**Gate de livraison** :
- [ ] `pytest tests/test_visualizations.py -v` passe (avec nouveaux tests médiane)
- [ ] `pytest tests/test_mode_normalization_winloss.py -v` passe
- [ ] `pytest tests/test_teammates_refonte.py -v` passe
- [ ] `pytest tests/ -v` passe sans régression
- [ ] Test manuel UI : vérifier médianes affichées, "Frags" au lieu de "Kills", modes normalisés, médias, coéquipiers

**Commandes de validation** :
```bash
pytest tests/test_visualizations.py tests/test_mode_normalization_winloss.py tests/test_teammates_refonte.py tests/test_media_improvements.py -v
pytest tests/ -v
streamlit run streamlit_app.py  # Vérifier médianes, Frags, modes, médias, coéquipiers
```

**Livrables** :
- Code distributions/médiane : `src/visualization/distributions.py`, `src/ui/pages/timeseries.py`
- Code normalisation modes : `src/ui/pages/win_loss.py`
- Code Médias : `src/ui/pages/media_tab.py`
- Code Coéquipiers : `src/ui/pages/teammates.py`, `src/ui/pages/teammates_charts.py`
- Tests : `tests/test_mode_normalization_winloss.py`, `tests/test_teammates_refonte.py`, `tests/test_media_improvements.py`
- Mise à jour `.ai/thought_log.md`
- Mise à jour `.ai/features/DISTRIBUTIONS_MEDIAN_PLAN.md` (statut : Implémenté)

---

### Sprint 4 — Score de Performance v4 (2 jours)

**Objectif** : Évoluer le score de v3 vers v4 avec nouvelles métriques

**Prérequis** : Sprint 1 (Pandas→Polars dans perf_score), Sprint 2A (damage_dealt dans match_participants)

| # | Tâche | Source | Fichier(s) |
|---|-------|--------|-----------|
| 4.1 | Mettre à jour `PERFORMANCE_SCORE_VERSION` → `"v4-relative"` et `RELATIVE_WEIGHTS` avec 8 métriques | P5 §1 | `src/analysis/performance_config.py` |
| 4.2 | Mettre à jour `PERFORMANCE_SCORE_FULL_DESC` et `COMPACT_DESC` | P5 §1 | `src/analysis/performance_config.py` |
| 4.3 | Ajouter calcul `pspm` (Personal Score Per Minute) dans `_prepare_history_metrics()` | P5 §2.1 | `src/analysis/performance_score.py` |
| 4.4 | Ajouter calcul `dpm_damage` (Damage Per Minute) dans `_prepare_history_metrics()` | P5 §2.1 | `src/analysis/performance_score.py` |
| 4.5 | Ajouter calcul `rank_perf_diff` (rank performance) dans `_prepare_history_metrics()` | P5 §2.1 | `src/analysis/performance_score.py` |
| 4.6 | Créer `_compute_rank_performance()` | P5 §2.3 | `src/analysis/performance_score.py` |
| 4.7 | Modifier `compute_relative_performance_score()` : extraire `personal_score`, `damage_dealt`, `rank`, `team_mmr`, `enemy_mmr` ; calculer percentiles pour PSPM, DPM, rank_perf ; intégrer dans la moyenne pondérée | P5 §2.2 | `src/analysis/performance_score.py` |
| 4.8 | Mettre à jour la requête historique dans `_compute_and_update_performance_score()` (engine.py) pour inclure `personal_score`, `damage_dealt`, `rank`, `team_mmr`, `enemy_mmr` | P5 §4 | `src/data/sync/engine.py` L.914+ |
| 4.9 | Mettre à jour `_compute_performance_score()` dans backfill pour passer les nouvelles colonnes | P5 §5 | `scripts/backfill_data.py` L.640-720 |
| 4.10 | Créer script `scripts/recompute_performance_scores_duckdb.py` (migration v3→v4) avec `--dry-run`, `--force`, `--player`, `--batch-size` | P5 §3 | Nouveau script (exception à la règle "tout dans backfill_data.py" car c'est une migration ponctuelle) |

**Tests Sprint 4** :
- Créer `tests/test_performance_score_v4.py` :
  - Test calcul PSPM avec historique suffisant
  - Test calcul DPM damage avec historique
  - Test calcul Rank Performance avec MMR (delta positif, négatif, nul)
  - Test graceful degradation : personal_score=None → PSPM ignoré, poids renormalisés
  - Test graceful degradation : damage_dealt=None → DPM ignoré
  - Test graceful degradation : rank/mmr=None → rank_perf ignoré
  - Test compatibilité : données v3 (sans personal_score etc.) → score calculé avec métriques disponibles
  - Test total des poids = 1.0
- Modifier `tests/test_sync_performance_score.py` : adapter les colonnes history
- Modifier `tests/test_backfill_performance_score.py` : nouvelles colonnes

**Gate de livraison** :
- [ ] `pytest tests/test_performance_score_v4.py -v` passe
- [ ] `pytest tests/test_sync_performance_score.py -v` passe
- [ ] `pytest tests/test_backfill_performance_score.py -v` passe
- [ ] `pytest tests/ -v` passe sans régression
- [ ] Test dry-run migration : `python scripts/recompute_performance_scores_duckdb.py --player JGtm --dry-run`
- [ ] Vérifier que nouveaux matchs utilisent v4 automatiquement

**Migration des données existantes (v3 → v4)** :

Processus :
1. Déployer le code v4
2. `python scripts/recompute_performance_scores_duckdb.py --all --dry-run` (vérification)
3. Exécuter le script réel pour tous les joueurs
4. Vérifier statistiques (nombre recalculés, erreurs)

Estimation temps de recalcul :
- 10 joueurs x 1000 matchs : ~20-40 secondes
- 50 joueurs x 2000 matchs : ~2-4 minutes

**Commandes de validation** :
```bash
pytest tests/test_performance_score_v4.py tests/test_sync_performance_score.py tests/test_backfill_performance_score.py -v
python scripts/recompute_performance_scores_duckdb.py --player JGtm --dry-run
python scripts/recompute_performance_scores_duckdb.py --player JGtm
pytest tests/ -v
```

**Livrables** :
- Code v4 : `src/analysis/performance_score.py`, `src/analysis/performance_config.py`
- Script migration : `scripts/recompute_performance_scores_duckdb.py`
- Mises à jour sync/backfill : `src/data/sync/engine.py`, `scripts/backfill_data.py`
- Tests : `tests/test_performance_score_v4.py`
- Mise à jour `.ai/thought_log.md`
- Mise à jour `.ai/features/PERFORMANCE_SCORE_V4_PLAN.md` (statut : Implémenté)

---

### Sprint 5 — Nouvelles stats : Timeseries + Corrélations (2 jours)

**Objectif** : Premières nouvelles visualisations (P6 Phase 1-2)

**Prérequis** : Sprint 3 (médianes en place), Sprint 2A (damage disponible)

#### 5A — Corrélations (P6 §2.1-2.3)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 5A.1 | Ajouter scatter "Durée de vie moyenne vs Morts" coloré par outcome | `src/ui/pages/timeseries.py` (section Corrélations) ; réutiliser `plot_correlation_scatter()` |
| 5A.2 | Ajouter scatter "Kills vs Deaths" coloré par outcome | Idem |
| 5A.3 | Ajouter scatter "Team MMR vs Enemy MMR" avec ligne y=x | `src/ui/pages/timeseries.py` ; adapter `plot_correlation_scatter()` ou ajouter param `reference_line` |

#### 5B — Distributions (P6 §2.4-2.5)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 5B.1 | Ajouter histogramme "Score personnel par minute" (personal_score / time_played * 60) | `src/ui/pages/timeseries.py` ; réutiliser `plot_histogram()` |
| 5B.2 | Ajouter histogramme "Distribution du taux de victoire" (fenêtre glissante 10 matchs) | `src/ui/pages/timeseries.py` ; créer `plot_win_ratio_distribution()` dans `distributions.py` |

#### 5C — Performance cumulée améliorée (P6 §2.6)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 5C.1 | Ajouter lignes verticales pointillées tous les ~8 min dans `plot_cumulative_net_score()` | `src/visualization/performance.py` L.53+ (param `show_match_markers`) |

**Tests Sprint 5** :
- Ajouter dans `tests/test_visualizations.py` :
  - `test_plot_correlation_scatter_with_reference_line`
  - `test_plot_win_ratio_distribution_valid` / `_empty`
- Créer `tests/test_new_timeseries_sections.py` :
  - Test que les nouvelles sections gèrent les données vides gracieusement
  - Test que le calcul score_per_minute est correct
  - Test que la fenêtre glissante win_ratio est correcte

**Gate de livraison** :
- [ ] `pytest tests/test_visualizations.py -v` passe
- [ ] `pytest tests/test_new_timeseries_sections.py -v` passe
- [ ] `pytest tests/ -v` passe sans régression

**Commandes de validation** :
```bash
pytest tests/test_visualizations.py tests/test_new_timeseries_sections.py -v
pytest tests/ -v
streamlit run streamlit_app.py  # Vérifier corrélations, distributions, performance cumulée
```

**Livrables** :
- Code corrélations et distributions : `src/ui/pages/timeseries.py`, `src/visualization/distributions.py`, `src/visualization/performance.py`
- Tests : `tests/test_new_timeseries_sections.py`
- Mise à jour `.ai/thought_log.md`

---

### Sprint 6 — Nouvelles stats : Victoires/Défaites + Dernier match (2 jours)

**Objectif** : P6 Phase 2-3

**Prérequis** : Sprint 5 livré

#### 6A — Page Victoires/Défaites (P6 §1)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 6A.1 | Ajouter section "Score personnel par match" (barres colorées par outcome) | `src/ui/pages/win_loss.py` ; créer `plot_personal_score_by_match()` dans `distributions.py` |
| 6A.2 | Créer `src/analysis/win_streaks.py` : `compute_weekly_longest_streak()`, `compute_win_streak_distribution()` | Nouveau fichier |
| 6A.3 | Ajouter section "Série de victoires hebdomadaire" (barres par semaine) | `src/ui/pages/win_loss.py` ; créer `plot_weekly_longest_streak()` dans `distributions.py` |
| 6A.4 | Ajouter section "Distribution des séries de victoires" (histogramme) | `src/ui/pages/win_loss.py` ; créer `plot_win_streak_distribution()` dans `distributions.py` |
| 6A.5 | Ajouter section "Rang et score personnel" (scatter ou barres groupées) | `src/ui/pages/win_loss.py` ; créer `plot_rank_and_personal_score()` dans `distributions.py` |

#### 6B — Page Dernier match (P6 §3-4)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 6B.1 | Ajouter section "Dégâts" (histogramme superposé damage_dealt/taken) | `src/ui/pages/match_view.py` ; créer `plot_damage_distribution_combined()` dans `distributions.py` |
| 6B.2 | Ajouter section "Tirs et précision" (barres shots_fired/hit + courbe accuracy) | `src/ui/pages/match_view.py` (ou `timeseries.py`) ; créer `plot_shots_fired_hit_accuracy()` dans `src/visualization/timeseries.py` |
| 6B.3 | Ajouter section "Dégâts avec moyenne lissée" (barres + rolling average) | `src/ui/pages/timeseries.py` ; créer `plot_damage_timeseries_with_smooth()` dans `src/visualization/timeseries.py` |
| 6B.4 | Retirer la précision du graphe "Folie meurtrière / Tirs à la tête / Précision / Frags parfaits" (supprimer trace + axe Y secondaire) | `src/visualization/timeseries.py` L.508+ (`plot_spree_headshots_accuracy`) |

#### 6C — Adapter Matchs Top pour périodes < semaine (P6 §6.1)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 6C.1 | Créer `plot_matches_at_top_by_period()` (ou modifier `plot_matches_at_top_by_week()`) avec détection auto période (day/week/month) | `src/visualization/distributions.py` L.956+ |
| 6C.2 | Mettre à jour l'appel dans `win_loss.py` | `src/ui/pages/win_loss.py` L.197+ |

**Tests Sprint 6** :
- Créer `tests/test_win_streaks.py` :
  - Test `compute_weekly_longest_streak` avec données connues (séries de 3, 5, 2)
  - Test `compute_win_streak_distribution` (distribution correcte)
  - Test avec données vides
- Ajouter dans `tests/test_visualizations.py` :
  - `test_plot_personal_score_by_match_valid` / `_empty`
  - `test_plot_win_streak_distribution_valid` / `_empty`
  - `test_plot_weekly_longest_streak_valid` / `_empty`
  - `test_plot_rank_and_personal_score_valid` / `_empty`
  - `test_plot_damage_distribution_combined_valid` / `_empty`
  - `test_plot_shots_fired_hit_accuracy_valid` / `_empty`
  - `test_plot_damage_timeseries_with_smooth_valid` / `_empty`
  - `test_plot_spree_headshots_no_accuracy` (vérifier suppression trace)
  - `test_plot_matches_at_top_by_period_day` / `_week` / `_month` / `_auto`

**Gate de livraison** :
- [ ] `pytest tests/test_win_streaks.py -v` passe
- [ ] `pytest tests/test_visualizations.py -v` passe (avec nouveaux tests)
- [ ] `pytest tests/ -v` passe sans régression

**Commandes de validation** :
```bash
pytest tests/test_win_streaks.py tests/test_visualizations.py -v
pytest tests/ -v
streamlit run streamlit_app.py  # Vérifier Victoires/Défaites, Dernier match, tirs, dégâts
```

**Livrables** :
- Code : `src/analysis/win_streaks.py` (nouveau), `src/ui/pages/win_loss.py`, `src/ui/pages/match_view.py`
- Visualisations : `src/visualization/distributions.py`, `src/visualization/timeseries.py`
- Tests : `tests/test_win_streaks.py`
- Mise à jour `.ai/thought_log.md`

---

### Sprint 7 — Nouvelles stats : Mes Coéquipiers (3 jours)

**Objectif** : P6 Phase 4 — Toutes les comparaisons coéquipiers

**Prérequis** : Sprint 2A (damage participants), Sprint 3E (refonte coéquipiers), Sprint 5-6 (fonctions de visualisation)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 7.1 | Ajouter comparaison "Score personnel" (moi vs coéquipier) sur matchs communs | `src/ui/pages/teammates.py`, `teammates_charts.py` |
| 7.2 | Ajouter comparaison "Séries de victoires" (moi vs coéquipier) | `src/ui/pages/teammates.py`, `teammates_charts.py` |
| 7.3 | Ajouter comparaison "Rang et score" (moi vs coéquipier) | `src/ui/pages/teammates.py`, `teammates_charts.py` |
| 7.4 | Ajouter corrélations côte à côte (durée vie vs morts, kills vs deaths, MMR) | `src/ui/pages/teammates.py`, `teammates_charts.py` |
| 7.5 | Ajouter comparaison distributions (score/min, win ratio, dégâts dealt/taken) | `src/ui/pages/teammates.py`, `teammates_charts.py` |
| 7.6 | Ajouter visualisations tirs (barres groupées, scatter, heatmap précision) | `src/ui/pages/teammates_charts.py` : `render_shots_comparison_bars()`, `render_shots_scatter_comparison()`, `render_shots_heatmap_comparison()` |
| 7.7 | Ajouter visualisations dégâts (barres groupées, scatter efficacité, ratio dealt/taken) | `src/ui/pages/teammates_charts.py` : `render_damage_comparison_bars()`, `render_damage_efficiency_scatter()`, `render_damage_ratio_bars()` |
| 7.8 | Ajouter heatmap Win Ratio par jour/heure (moi vs coéquipier) | `src/ui/pages/teammates.py`, `teammates_charts.py` : `render_win_ratio_heatmap_comparison()` |
| 7.9 | Ajouter "Matchs Top vs Total par période" comparatif | `src/ui/pages/teammates.py`, `teammates_charts.py` : `render_top_matches_comparison()` |

**Tests Sprint 7** :
- Créer `tests/test_teammates_new_comparisons.py` :
  - Test chaque nouvelle fonction de comparaison avec données fixtures
  - Test avec données vides (pas de matchs communs)
  - Test avec un seul match commun
  - Test avec données manquantes (damage_dealt NULL)

**Gate de livraison** :
- [ ] `pytest tests/test_teammates_new_comparisons.py -v` passe
- [ ] `pytest tests/ -v` passe sans régression
- [ ] Test manuel UI : vérifier chaque graphe comparatif

**Commandes de validation** :
```bash
pytest tests/test_teammates_new_comparisons.py -v
pytest tests/ -v
streamlit run streamlit_app.py  # Vérifier toutes les comparaisons coéquipiers
```

**Livrables** :
- Code : `src/ui/pages/teammates.py`, `src/ui/pages/teammates_charts.py`
- Tests : `tests/test_teammates_new_comparisons.py`
- Mise à jour `.ai/thought_log.md`
- Mise à jour `.ai/PLAN_DETAIL_STATS_NOUVELLES.md` (statut : Implémenté)

---

### Sprint 8 — Refactoring structurel backfill (optionnel, 3 jours)

**Objectif** : P2 §3-6 — Amélioration à long terme de la maintenabilité

**Prérequis** : Tous les sprints précédents livrés

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 8.1 | Créer `scripts/backfill/__init__.py`, `core.py` (fonctions d'insertion) | Nouveaux fichiers |
| 8.2 | Extraire `detection.py` (`_find_matches_missing_data`) | Nouveau fichier |
| 8.3 | Extraire `strategies.py` (backfill spécifiques : killer_victim, end_time, sessions, etc.) | Nouveau fichier |
| 8.4 | Extraire `orchestrator.py` (`backfill_player_data`, `backfill_all_players`) | Nouveau fichier |
| 8.5 | Extraire `cli.py` (arguments CLI) | Nouveau fichier |
| 8.6 | Refactorer `backfill_data.py` en point d'entrée léger (~200 lignes) | `scripts/backfill_data.py` |
| 8.7 | Implémenter détection AND/OR configurable (`--strict-detection`) | `scripts/backfill/detection.py` |
| 8.8 | Optimiser SQL : remplacer `IN` par `EXISTS` / CTEs | `scripts/backfill/detection.py` |
| 8.9 | Centraliser migrations : créer `src/db/migrations.py` (DRY engine.py + backfill) | Nouveau fichier |
| 8.10 | (Optionnel) Table `backfill_status` pour tracking par type de donnée | `scripts/backfill/detection.py` |

**Tests Sprint 8** :
- Adapter tous les tests backfill existants aux nouveaux imports
- Créer `tests/test_backfill_detection.py` :
  - Test mode OR vs AND
  - Test CTEs vs sous-requêtes (même résultat)
- Créer `tests/test_migrations.py` :
  - Test `ensure_match_participants_columns` sur DB vierge
  - Test sur DB existante (idempotence)
  - Test `run_all_migrations`

**Gate de livraison** :
- [ ] `pytest tests/ -v` passe (tous les tests, y compris refactorisés)
- [ ] `python scripts/backfill_data.py --player JGtm --all-data --dry-run` fonctionne
- [ ] `wc -l scripts/backfill_data.py` < 300 lignes

**Commandes de validation** :
```bash
pytest tests/test_backfill_detection.py tests/test_migrations.py -v
python scripts/backfill_data.py --player JGtm --all-data --dry-run
wc -l scripts/backfill_data.py
pytest tests/ -v
```

**Livrables** :
- Modules : `scripts/backfill/__init__.py`, `core.py`, `detection.py`, `strategies.py`, `orchestrator.py`, `cli.py`
- Migrations : `src/db/migrations.py`
- `scripts/backfill_data.py` réduit à ~200 lignes (point d'entrée léger)
- Tests : `tests/test_backfill_detection.py`, `tests/test_migrations.py`
- Mise à jour `.ai/thought_log.md`

---

### Sprint 9 — Finalisation, tests d'intégration et documentation (3 jours)

**Objectif** : Tests d'intégration complets, tests de charge, couverture, release notes, guide utilisateur

**Prérequis** : Tous les sprints S0-S7 livrés (S8 optionnel)

#### 9A — Tests d'intégration (1 jour)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 9A.1 | Créer `tests/test_integration_stats_nouvelles.py` : toutes les nouvelles visualisations accessibles | Nouveau fichier |
| 9A.2 | Vérifier pas de régression sur pages existantes | Tests existants |
| 9A.3 | Vérifier performance acceptable (temps de chargement < 5s par page) | Test manuel + métrique |
| 9A.4 | Vérifier pas d'erreurs dans les logs Streamlit | Test manuel |

#### 9B — Tests de charge (½ jour)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 9B.1 | Test avec joueur ayant 1000+ matchs | Test manuel |
| 9B.2 | Test avec joueur ayant 5000+ matchs | Test manuel |
| 9B.3 | Vérifier que les temps de chargement restent acceptables, implémenter lazy loading si nécessaire | UI pages |

#### 9C — Couverture de tests (½ jour)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 9C.1 | Exécuter `pytest tests/ -v --cov=src --cov-report=html` et vérifier > 95% | — |
| 9C.2 | Identifier et combler les trous de couverture critiques | Tests existants |

#### 9D — Documentation et release (1 jour)

| # | Tâche | Fichier(s) |
|---|-------|-----------|
| 9D.1 | Mettre à jour tous les plans `.ai/features/` avec statut final | Fichiers `.ai/` |
| 9D.2 | Créer `.ai/RELEASE_NOTES_2026_Q1.md` (changelog de toutes les nouvelles fonctionnalités) | Nouveau fichier |
| 9D.3 | Créer `docs/USER_GUIDE_NEW_FEATURES.md` (guide utilisateur avec screenshots) | Nouveau fichier |
| 9D.4 | Mettre à jour `CLAUDE.md` si nécessaire (nouvelles commandes, tables) | `CLAUDE.md` |
| 9D.5 | Synthèse finale dans `.ai/thought_log.md` | `.ai/thought_log.md` |

**Gate de livraison** :
- [ ] `pytest tests/ -v --cov=src --cov-report=html` → > 95% couverture
- [ ] `pytest tests/ -v` → 0 failure, 0 error
- [ ] Tous les plans `.ai/features/` marqués Implémenté
- [ ] Release notes et guide utilisateur rédigés
- [ ] Performance validée sur plusieurs profils (1000+, 5000+ matchs)

**Commandes de validation** :
```bash
pytest tests/ -v --cov=src --cov-report=html
streamlit run streamlit_app.py  # Navigation complète toutes pages
grep -r "import pandas" src/  # Vérifier conformité
grep -r "import sqlite3" src/  # Vérifier conformité
```

**Livrables** :
- Tests : `tests/test_integration_stats_nouvelles.py`
- Documentation : `.ai/RELEASE_NOTES_2026_Q1.md`, `docs/USER_GUIDE_NEW_FEATURES.md`
- Mise à jour tous les fichiers `.ai/` avec statut final
- App prête pour release

---

## 6. Récapitulatif des fichiers impactés

### Fichiers à créer

| Fichier | Sprint | Plan |
|---------|--------|------|
| `src/ui/components/career_progress_circle.py` | S2 | P7 |
| `src/app/career_section.py` | S2 | P7 |
| `src/analysis/win_streaks.py` | S6 | P6 |
| `scripts/recompute_performance_scores_duckdb.py` | S4 | P5 |
| `scripts/backfill/__init__.py` | S8 | P2 |
| `scripts/backfill/core.py` | S8 | P2 |
| `scripts/backfill/detection.py` | S8 | P2 |
| `scripts/backfill/strategies.py` | S8 | P2 |
| `scripts/backfill/orchestrator.py` | S8 | P2 |
| `scripts/backfill/cli.py` | S8 | P2 |
| `src/db/migrations.py` | S8 | P2 |

### Fichiers de tests à créer

| Fichier | Sprint |
|---------|--------|
| `tests/test_session_last_button.py` | S0 |
| `tests/test_participants_damage.py` | S2 |
| `tests/test_career_progress_circle.py` | S2 |
| `tests/test_mode_normalization_winloss.py` | S3 |
| `tests/test_teammates_refonte.py` | S3 |
| `tests/test_performance_score_v4.py` | S4 |
| `tests/test_new_timeseries_sections.py` | S5 |
| `tests/test_win_streaks.py` | S6 |
| `tests/test_teammates_new_comparisons.py` | S7 |
| `tests/test_backfill_detection.py` | S8 |
| `tests/test_migrations.py` | S8 |
| `tests/test_media_improvements.py` | S3 |
| `tests/test_integration_stats_nouvelles.py` | S9 |

### Fichiers de documentation à créer

| Fichier | Sprint |
|---------|--------|
| `.ai/RELEASE_NOTES_2026_Q1.md` | S9 |
| `docs/USER_GUIDE_NEW_FEATURES.md` | S9 |

### Fichiers existants à modifier

| Fichier | Sprints |
|---------|---------|
| `src/app/filters_render.py` | S0 |
| `src/app/filters.py` | S0 |
| `streamlit_app.py` | S0bis |
| `src/ui/filter_state.py` | S0bis |
| `src/analysis/performance_score.py` | S1, S4 |
| `src/analysis/performance_config.py` | S4 |
| `scripts/backfill_data.py` | S1, S2, S4, (S8) |
| `src/data/sync/models.py` | S2 |
| `src/data/sync/transformers.py` | S2 |
| `src/data/sync/engine.py` | S2, S4 |
| `src/visualization/distributions.py` | S3, S5, S6 |
| `src/visualization/timeseries.py` | S6 |
| `src/visualization/performance.py` | S5 |
| `src/ui/pages/timeseries.py` | S3, S5 |
| `src/ui/pages/win_loss.py` | S3, S6 |
| `src/ui/pages/teammates.py` | S3, S7 |
| `src/ui/pages/teammates_charts.py` | S3, S7 |
| `src/ui/pages/match_view.py` | S6 |
| `src/ui/pages/media_tab.py` | S3 |
| `src/ui/components/media_thumbnail.py` | S3 |
| `src/ui/components/media_lightbox.py` | S3 |
| `src/app/page_router.py` | S3 |
| `tests/test_performance_score.py` | S1 |
| `tests/test_sync_performance_score.py` | S1, S4 |
| `tests/test_backfill_performance_score.py` | S1, S4 |
| `tests/test_visualizations.py` | S3, S5, S6 |
| `tests/test_models.py` | S2 |

---

## 7. Matrice de risques

| Risque | Probabilité | Impact | Mitigation | Sprint |
|--------|-------------|--------|------------|--------|
| Régression performance_score après migration Polars | Moyenne | 🔴 Élevé | Tests exhaustifs avant/après ; comparer scores v3 sur échantillon | S1 |
| Perte de données backfill (problème B non résolu) | Haute | 🟠 Moyen | Workaround documenté (traiter par étapes) ; résolu en S8 | S1-S8 |
| API ne fournit pas DamageDealt/DamageTaken pour tous les joueurs | Faible | 🟠 Moyen | `getattr(row, "damage_dealt", None)` + graceful degradation | S2 |
| Conflits de merge entre sprints parallèles (S2 + S3) | Moyenne | 🟡 Faible | Fichiers différents ; seul `teammates.py` touché par les deux | S2-S3 |
| XP_HERO_TOTAL incorrect (9 319 350) | Faible | 🟡 Faible | Vérifier via métadonnées cache ; ajouter fallback par rang | S2 |
| Recalcul v4 trop long pour joueurs avec 2000+ matchs | Faible | 🟡 Faible | Batching + `--batch-size` ; parallélisation par joueur | S4 |
| Complexité excessive Sprint 7 (9 sous-tâches coéquipiers) | Haute | 🟠 Moyen | Découper S7 en 2 sous-sprints (7a : stats individuelles, 7b : comparaisons) | S7 |
| Performance dégradée (trop de graphiques par page) | Moyenne | 🟠 Moyen | Tests de charge S9 ; lazy loading si nécessaire ; limiter le nombre de graphiques visibles simultanément | S5-S9 |
| Dépassement de budget temps | Moyenne | 🟡 Faible | Priorisation stricte (S0-S4 non négociables) ; possibilité de reporter S6-S7 | S0-S9 |
| Régression affichage filtres (nettoyage trop large) | Faible | 🟡 Faible | Ne supprimer que les clés listées + préfixes widgets ; tests A→B→A | S0bis |

---

## 8. Critères de livraison

### Par sprint

Chaque sprint est considéré livré quand :

1. **Tests automatisés** : `pytest tests/ -v` passe à 100 % (0 failure, 0 error)
2. **Nouveaux tests** : Les tests spécifiques du sprint passent
3. **Pas de régression** : Les tests existants ne sont pas cassés
4. **Conformité règles** :
   - `grep -r "import pandas" src/` → uniquement dans les fichiers autorisés (frontière Plotly/Streamlit)
   - `grep -r "import sqlite3" src/` → aucun résultat
5. **Commit propre** : Un commit par sprint avec message descriptif

### Globale (fin de tous les sprints)

- [ ] Toutes les gates de livraison des sprints S0-S9 validées
- [ ] Au moins **12 nouveaux fichiers de tests** créés
- [ ] Plus de **50 nouveaux tests** ajoutés
- [ ] `scripts/backfill_data.py` : aucun `import pandas`
- [ ] `src/analysis/performance_score.py` : aucun `import pandas`
- [ ] Score de performance v4 fonctionnel avec graceful degradation
- [ ] Toutes les nouvelles visualisations visibles dans l'UI
- [ ] Section Carrière avec cercle de progression
- [ ] Données damage_dealt/taken disponibles dans match_participants
- [ ] Documentation `.ai/thought_log.md` et `.ai/project_map.md` mises à jour
- [ ] Release notes et guide utilisateur rédigés (S9)
- [ ] Couverture de tests > 95% (S9)

---

## Calendrier récapitulatif

| Sprint | Durée | Plans | Parallélisable |
|--------|-------|-------|---------------|
| **S0** | ½ j | P1 | — |
| **S0bis** | ½–1 j | P8 | ✅ avec S0 |
| **S1** | 2 j | P2 (partiel) | — |
| **S2** | 2.5 j | P3 + P7 | ✅ avec S3 |
| **S3** | 3 j | P4 | ✅ avec S2 |
| **S4** | 2 j | P5 | Après S1 + S2A |
| **S5** | 2 j | P6 (Phase 1) | Après S3 |
| **S6** | 2 j | P6 (Phase 2-3) | Après S5 |
| **S7** | 3 j | P6 (Phase 4) | Après S6 + S3E |
| **S8** | 3 j | P2 (structurel) | Optionnel |
| **S9** | 3 j | Finalisation | Après S0-S7 |
| **Total** | **~23 j** | 7 plans + finalisation | |

> En parallélisant S2 et S3, le chemin critique est d'environ **19 jours ouvrés** (S8 optionnel).

---

---

## 9. Métriques de succès

| Domaine | Métrique | Cible |
|---------|----------|-------|
| **Code Quality** | Violations Pandas dans `src/` | 0 (uniquement `.to_pandas()` à la frontière Plotly/Streamlit) |
| **Code Quality** | Violations SQLite dans `src/` | 0 |
| **Code Quality** | Architecture DuckDB v4 | 100% |
| **Tests** | Couverture de code | > 95% |
| **Tests** | Nombre de fichiers de tests créés | >= 12 |
| **Tests** | Nombre de nouveaux tests | >= 50 |
| **Performance** | Temps de chargement par page | < 5 secondes |
| **Performance** | Backfill par match | < 2 secondes |
| **UX** | Bugs bloquants | 0 |
| **UX** | Navigation | Intuitive, labels clairs, graphiques lisibles |
| **Données** | Nouvelles métriques disponibles et correctes | PSPM, DPM damage, Rank Performance, damage participants |
| **Documentation** | Plans `.ai/features/` marqués Implémenté | 100% |
| **Documentation** | Guide utilisateur | Complet avec exemples |

---

## 10. Prochaines étapes immédiates

### 10.1 Vérification de l'environnement

```bash
# Vérifier versions requises
python --version        # 3.11+
streamlit --version     # >= 1.30
pytest --version        # >= 7.0
duckdb --version        # >= 0.10 (v4)

# Vérifier que l'app démarre
streamlit run streamlit_app.py
```

### 10.2 Préparation git

```bash
# Créer branche de développement
git checkout -b feature/consolidated-roadmap-2026-q1

# Ou utiliser la branche existante si applicable
git checkout feature/hybrid-data-architecture
```

### 10.3 Démarrer Sprint 0 / Sprint 0bis

Sprint 0 est le point d'entrée immédiat : correction du bug "Dernière session" (½ jour). Sprint 0bis (persistance filtres multi-joueurs, P8) peut être fait en parallèle ou juste après : conservation des filtres par joueur au switch de DB.

### 10.4 Ordre de priorité si contrainte de temps

Si le budget temps est limité, prioriser strictement :
1. **S0** (bug fix visible "Dernière session") — non négociable
2. **S0bis** (persistance filtres par joueur) — fort impact UX, rapide
3. **S1** (backfill fiable + Pandas) — non négociable (dette technique critique)
3. **S2** (damage participants + carrière) — haut impact utilisateur
4. **S4** (perf score v4) — forte valeur ajoutée
5. **S3** (médianes, UI) — qualité de vie
6. **S5-S7** (nouvelles stats) — améliorations progressives, reportables
7. **S8** (refactoring structurel) — optionnel, maintenabilité long terme
8. **S9** (finalisation) — à adapter selon sprints effectivement livrés

---

**Document généré le** : 2026-02-09
**Dernière mise à jour** : 2026-02-09 (intégration P8 — Persistance filtres multi-joueurs)
**Auteur** : Claude Code (analyse et compilation)
**Mis à jour avec** : Éléments du premier jet (`nouveau 1.txt`)
