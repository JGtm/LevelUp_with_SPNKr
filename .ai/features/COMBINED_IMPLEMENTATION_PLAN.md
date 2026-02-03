# Plan d'Implémentation Combiné : Refdata + Antagonistes + Performance Cumulée

> Date : 2026-02-03  
> Statut : Plan d'implémentation par sprints  
> Technologies : **Polars** (remplace Pandas), DuckDB, Streamlit  
> Références : 
> - `.ai/research/SPNKR_REFDATA_INTEGRATION_PLAN.md`
> - `.ai/features/ANTAGONIST_CHARTS_CUMULATIVE_PERF_PLAN.md`

---

## Vue d'ensemble

Ce plan combine deux initiatives majeures :
1. **Intégration SPNKr refdata** : Catégories officielles + décomposition score personnel
2. **Antagonistes + Performance cumulée** : Persistance killer-victim + graphiques

**Architecture de données** : DuckDB (source de vérité) + Polars (analyses)

---

## Sprint 0 : Préparation et Investigation (1 semaine)

### Objectifs
- Finaliser l'investigation API refdata (déjà démarrée)
- Créer module refdata avec enums SPNKr
- Valider l'architecture Polars
- Préparer les schémas BDD

### Tâches

| ID | Tâche | Fichiers | Statut | Estimation |
|----|-------|----------|--------|------------|
| 0.1 | ✅ Script investigation refdata créé | `scripts/investigate_refdata_fields.py` | **FAIT** | - |
| 0.2 | Exécuter script investigation et documenter résultats | `.ai/research/API_REFDATA_FIELDS.md` | À faire | 3h |
| 0.3 | Créer module refdata avec enums SPNKr complets | `src/data/domain/refdata.py` | À faire | 4h |
| 0.4 | Tests unitaires module refdata | `tests/test_refdata.py` | À faire | 2h |
| 0.5 | Valider architecture Polars (exemples de requêtes) | `scripts/test_polars_integration.py` | À faire | 3h |

### Livrables
- ✅ Script d'investigation créé (`scripts/investigate_refdata_fields.py`)
- ✅ Plan d'intégration documenté (`.ai/research/SPNKR_REFDATA_INTEGRATION_PLAN.md`)
- ⏳ Résultats investigation API (à exécuter)
- ⏳ Module `refdata.py` avec enums complets
- ⏳ Tests de validation Polars
- ⏳ Documentation schémas BDD étendus

### Note
Le script d'investigation et le plan d'intégration ont déjà été créés. Il reste à :
1. Exécuter le script pour obtenir les résultats réels de l'API
2. Créer le module refdata avec les enums complets
3. Valider l'architecture Polars

---

## Sprint 1 : Persistance Killer-Victim + Schémas Refdata (1 semaine)

### Objectifs
- Créer table `killer_victim_pairs` en DuckDB
- Créer table `personal_score_awards` en DuckDB
- Ajouter colonne `game_variant_category` à `match_stats`

### Tâches

| ID | Tâche | Fichiers | Estimation |
|----|-------|----------|------------|
| 1.1 | Ajouter table `killer_victim_pairs` au schéma | `src/data/sync/engine.py`, `docs/SQL_SCHEMA.md` | 2h |
| 1.2 | Ajouter table `personal_score_awards` au schéma | `src/data/sync/engine.py`, `docs/SQL_SCHEMA.md` | 2h |
| 1.3 | Ajouter colonne `game_variant_category` à `match_stats` | Migration script | 1h |
| 1.4 | Implémenter `_insert_killer_victim_pairs()` | `src/data/sync/engine.py` | 3h |
| 1.5 | Implémenter `_insert_personal_score_awards()` | `src/data/sync/engine.py` | 3h |
| 1.6 | Intégrer dans `_process_single_match()` | `src/data/sync/engine.py` | 2h |
| 1.7 | Ajouter `load_killer_victim_pairs()` à DuckDBRepository | `src/data/repositories/duckdb_repo.py` | 2h |
| 1.8 | Ajouter `load_personal_score_awards()` à DuckDBRepository | `src/data/repositories/duckdb_repo.py` | 2h |

### Livrables
- ✅ Tables créées en DuckDB
- ✅ Pipeline de sync mis à jour
- ✅ Repository avec méthodes de lecture

---

## Sprint 2 : Extraction et Transformation Refdata (1 semaine)

### Objectifs
- Extraire `GameVariantCategory` depuis API
- Extraire `PersonalScoreAwards` depuis API
- Transformer et stocker dans DuckDB

### Tâches

| ID | Tâche | Fichiers | Estimation |
|----|-------|----------|------------|
| 2.1 | Implémenter `_extract_game_variant_category()` | `src/data/sync/transformers.py` | 2h |
| 2.2 | Implémenter `_extract_personal_score_awards()` | `src/data/sync/transformers.py` | 3h |
| 2.3 | Créer `PersonalScoreAwardRow` model | `src/data/sync/models.py` | 1h |
| 2.4 | Modifier `transform_match_stats()` pour inclure `game_variant_category` | `src/data/sync/transformers.py` | 2h |
| 2.5 | Créer `transform_personal_score_awards()` | `src/data/sync/transformers.py` | 2h |
| 2.6 | Gérer fallback si données non disponibles (Discovery UGC) | `src/data/sync/transformers.py` | 4h |
| 2.7 | Tests unitaires transformations | `tests/test_transformers_refdata.py` | 3h |

### Livrables
- ✅ Extraction complète depuis API
- ✅ Transformations validées
- ✅ Gestion des cas limites

---

## Sprint 3 : Calculs Antagonistes avec Polars (1 semaine)

### Objectifs
- Calculer antagonistes depuis `killer_victim_pairs` avec Polars
- Créer fonctions d'analyse avec DataFrames Polars

### Tâches

| ID | Tâche | Fichiers | Estimation |
|----|-------|----------|------------|
| 3.1 | Créer `compute_personal_antagonists_from_pairs_polars()` | `src/analysis/killer_victim.py` | 4h |
| 3.2 | Créer `killer_victim_counts_long_polars()` | `src/analysis/killer_victim.py` | 3h |
| 3.3 | Créer `compute_kd_timeseries_by_minute_polars()` | `src/analysis/killer_victim.py` | 4h |
| 3.4 | Migrer fonctions existantes vers Polars | `src/analysis/killer_victim.py` | 3h |
| 3.5 | Tests unitaires avec Polars | `tests/test_killer_victim_polars.py` | 3h |

### Code exemple Polars

```python
import polars as pl

def compute_personal_antagonists_from_pairs_polars(
    pairs_df: pl.DataFrame,
    me_xuid: str,
) -> dict[str, Any]:
    """Calcule antagonistes avec Polars."""
    # Némésis : qui m'a tué le plus
    nemesis = (
        pairs_df
        .filter(pl.col("victim_xuid") == me_xuid)
        .group_by("killer_xuid", "killer_gamertag")
        .agg(pl.count().alias("times_killed_by"))
        .sort("times_killed_by", descending=True)
        .head(1)
    )
    
    # Souffre-douleur : qui j'ai tué le plus
    victim = (
        pairs_df
        .filter(pl.col("killer_xuid") == me_xuid)
        .group_by("victim_xuid", "victim_gamertag")
        .agg(pl.count().alias("times_killed"))
        .sort("times_killed", descending=True)
        .head(1)
    )
    
    return {
        "nemesis": nemesis.to_dicts()[0] if len(nemesis) > 0 else None,
        "victim": victim.to_dicts()[0] if len(victim) > 0 else None,
    }
```

### Livrables
- ✅ Fonctions d'analyse avec Polars
- ✅ Performance optimisée
- ✅ Tests validés

---

## Sprint 4 : Analyses Score Personnel avec Polars (1 semaine) ✅ TERMINÉ

### Objectifs
- ✅ Analyser `personal_score_awards` avec Polars
- ✅ Créer KPIs de participation aux objectifs
- ✅ Valoriser assistances différenciées

### Tâches

| ID | Tâche | Fichiers | Statut |
|----|-------|----------|--------|
| 4.1 | ✅ Créer `compute_objective_participation_score_polars()` | `src/analysis/objective_participation.py` | **FAIT** |
| 4.2 | ✅ Créer `rank_players_by_objective_contribution_polars()` | `src/analysis/objective_participation.py` | **FAIT** |
| 4.3 | ✅ Créer `compute_assist_breakdown_polars()` | `src/analysis/objective_participation.py` | **FAIT** |
| 4.4 | ✅ Fonctions additionnelles (summary, frequency) | `src/analysis/objective_participation.py` | **FAIT** |
| 4.5 | ✅ Tests unitaires analyses (26 tests) | `tests/test_objective_participation.py` | **FAIT** |

### Fonctions implémentées

```python
import polars as pl

# Sprint 4: Analyse de la participation aux objectifs
from src.analysis import (
    compute_objective_participation_score_polars,
    rank_players_by_objective_contribution_polars,
    compute_assist_breakdown_polars,
    compute_objective_summary_by_match_polars,
    compute_award_frequency_polars,
)

# 1. Score de participation aux objectifs
awards_df = repo.load_personal_score_awards_as_polars()
result = compute_objective_participation_score_polars(awards_df, match_id, xuid)
# result.objective_score, result.assist_score, result.kill_score, result.objective_ratio

# 2. Classement des joueurs par contribution
rankings = rank_players_by_objective_contribution_polars(awards_df, top_n=20)
# [PlayerObjectiveRanking(xuid, objective_score, avg_objective_per_match, ...)]

# 3. Décomposition des assistances
assists = compute_assist_breakdown_polars(awards_df, match_id, xuid)
# assists.kill_assists, assists.mark_assists, assists.emp_assists, assists.high_value_ratio

# 4. Résumé par match
summary_df = compute_objective_summary_by_match_polars(awards_df, xuid)
# DataFrame avec objective_score, assist_score, total_score, objective_ratio par match

# 5. Fréquence des awards
frequency_df = compute_award_frequency_polars(awards_df, category="objective", top_n=20)
```

### Livrables
- ✅ Module `src/analysis/objective_participation.py` avec 6 fonctions Polars
- ✅ Dataclasses : `ObjectiveParticipationResult`, `AssistBreakdownResult`, `PlayerObjectiveRanking`
- ✅ 26 tests unitaires passés (`tests/test_objective_participation.py`)

### Fichiers créés/modifiés
- `src/analysis/objective_participation.py` : Module complet d'analyse
- `src/analysis/__init__.py` : Exports mis à jour
- `tests/test_objective_participation.py` : Tests unitaires

---

## Sprint 5 : Visualisations Antagonistes (1 semaine) ✅ TERMINÉ

### Objectifs
- ✅ Créer graphiques antagonistes avec Plotly
- ✅ Utiliser Polars pour préparer données
- Intégrer dans pages UI (à faire lors de l'intégration)

### Tâches

| ID | Tâche | Fichiers | Statut |
|----|-------|----------|--------|
| 5.1 | ✅ Créer `plot_killer_victim_stacked_bars()` | `src/visualization/antagonist_charts.py` | **FAIT** |
| 5.2 | ✅ Créer `plot_kd_timeseries()` | `src/visualization/antagonist_charts.py` | **FAIT** |
| 5.3 | ✅ Créer `plot_duel_history()` | `src/visualization/antagonist_charts.py` | **FAIT** |
| 5.4 | ✅ Créer `plot_nemesis_victim_summary()` | `src/visualization/antagonist_charts.py` | **FAIT** |
| 5.5 | ✅ Créer `plot_killer_victim_heatmap()` | `src/visualization/antagonist_charts.py` | **FAIT** |
| 5.6 | ✅ Créer `plot_top_antagonists_bars()` | `src/visualization/antagonist_charts.py` | **FAIT** |
| 5.7 | ✅ Créer `create_kd_indicator()` | `src/visualization/antagonist_charts.py` | **FAIT** |

### Fonctions de visualisation implémentées

```python
from src.visualization import (
    plot_killer_victim_stacked_bars,  # Barres empilées kills/deaths par joueur
    plot_kd_timeseries,               # K/D par minute avec cumul
    plot_duel_history,                # Historique des duels entre 2 joueurs
    plot_nemesis_victim_summary,      # Indicateurs némésis/souffre-douleur
    plot_killer_victim_heatmap,       # Heatmap matrice killer→victim
    plot_top_antagonists_bars,        # Top némésis et victimes
    create_kd_indicator,              # Indicateur K/D simple
    get_antagonist_chart_colors,      # Palette de couleurs
)

# Exemple d'utilisation
pairs_df = repo.load_killer_victim_pairs_as_polars(match_id="abc123")
fig = plot_killer_victim_stacked_bars(pairs_df, match_id="abc123", me_xuid="xuid123")
```

### Livrables
- ✅ Module `src/visualization/antagonist_charts.py` avec 8 fonctions
- ✅ Palette de couleurs Halo configurée
- ✅ Intégration avec theme.py (apply_halo_plot_style)

### Fichiers créés/modifiés
- `src/visualization/antagonist_charts.py` : Module complet de visualisation
- `src/visualization/__init__.py` : Exports mis à jour

---

## Sprint 6 : Performance Cumulée avec Polars (1 semaine)

### Objectifs
- Calculer performance cumulée avec Polars
- Créer graphiques de tendance
- Intégrer dans comparaison de sessions

### Tâches

| ID | Tâche | Fichiers | Estimation |
|----|-------|----------|------------|
| 6.1 | Créer `compute_cumulative_net_score_series_polars()` | `src/analysis/performance.py` | 4h |
| 6.2 | Créer `plot_cumulative_net_score()` | `src/visualization/performance.py` | 4h |
| 6.3 | Intégrer dans page comparaison sessions | `src/ui/pages/session_compare.py` | 3h |
| 6.4 | Ajouter métriques cumulées (K/D, score objectifs) | `src/analysis/performance.py` | 3h |
| 6.5 | Tests et validation | `tests/test_performance_cumulative.py` | 2h |

### Code exemple Polars

```python
import polars as pl

def compute_cumulative_net_score_series_polars(
    match_stats_df: pl.DataFrame,
) -> pl.DataFrame:
    """Calcule série cumulative net score avec Polars."""
    return (
        match_stats_df
        .sort("start_time")
        .with_columns([
            # Net score = kills - deaths
            (pl.col("kills") - pl.col("deaths")).alias("net_score"),
        ])
        .with_columns([
            # Cumulatif
            pl.col("net_score").cumsum().alias("cumulative_net_score"),
        ])
        .select(["start_time", "cumulative_net_score"])
    )
```

### Livrables
- ✅ Analyses performance cumulée
- ✅ Graphiques de tendance
- ✅ Intégration UI

---

## Sprint 7 : Analyses Score Personnel Avancées (1 semaine)

### Objectifs
- Créer page d'analyse objectifs
- Visualiser contribution aux objectifs
- Valoriser joueurs support

### Tâches

| ID | Tâche | Fichiers | Estimation |
|----|-------|----------|------------|
| 7.1 | Créer page `objective_analysis.py` | `src/ui/pages/objective_analysis.py` | 5h |
| 7.2 | Graphique score objectifs vs kills | `src/visualization/objective_charts.py` | 4h |
| 7.3 | Tableau top joueurs sur objectifs | `src/ui/pages/objective_analysis.py` | 3h |
| 7.4 | Métriques ratio objectifs/kills | `src/analysis/objective_participation.py` | 2h |
| 7.5 | Tests et validation | Tests manuels | 2h |

### Livrables
- ✅ Page d'analyse objectifs complète
- ✅ Visualisations enrichies
- ✅ Métriques valorisées

---

## Sprint 8 : Backfill et Migration (1 semaine)

### Objectifs
- Créer scripts de backfill pour données existantes
- Migrer données historiques
- Valider intégrité

### Tâches

| ID | Tâche | Fichiers | Estimation |
|----|-------|----------|------------|
| 8.1 | Script backfill `killer_victim_pairs` | `scripts/backfill_killer_victim_pairs.py` | 4h |
| 8.2 | Script backfill `personal_score_awards` | `scripts/backfill_personal_score_awards.py` | 4h |
| 8.3 | Script migration `game_variant_category` | `scripts/migrate_game_variant_category.py` | 3h |
| 8.4 | Validation intégrité données | `scripts/validate_refdata_integrity.py` | 3h |
| 8.5 | Documentation migration | `docs/MIGRATION_REFDATA.md` | 2h |

### Livrables
- ✅ Scripts de backfill fonctionnels
- ✅ Données historiques migrées
- ✅ Documentation complète

---

## Sprint 9 : Optimisation et Tests Finaux (1 semaine)

### Objectifs
- Optimiser requêtes Polars
- Tests d'intégration complets
- Documentation finale

### Tâches

| ID | Tâche | Fichiers | Estimation |
|----|-------|----------|------------|
| 9.1 | Optimiser requêtes DuckDB pour Polars | `src/data/repositories/duckdb_repo.py` | 4h |
| 9.2 | Tests d'intégration end-to-end | `tests/integration/test_refdata_antagonists.py` | 4h |
| 9.3 | Benchmark performance Polars vs Pandas | `scripts/benchmark_polars.py` | 3h |
| 9.4 | Documentation utilisateur complète | `docs/USER_GUIDE_REFDATA.md` | 3h |
| 9.5 | Mise à jour roadmap | `.ai/ARCHITECTURE_ROADMAP.md` | 2h |

### Livrables
- ✅ Performance optimisée
- ✅ Tests complets
- ✅ Documentation finale

---

## Architecture Polars

### Principes

1. **DuckDB → Polars** : Requêtes DuckDB retournent DataFrames Polars
2. **Pas de Pandas** : Toutes les analyses utilisent Polars
3. **Lazy evaluation** : Utiliser `pl.scan_parquet()` quand possible
4. **Type safety** : Validation avec Pydantic après transformations

### Pattern d'utilisation

```python
import polars as pl
from src.data.repositories.duckdb_repo import DuckDBRepository

# 1. Charger depuis DuckDB en Polars
repo = DuckDBRepository(db_path)
pairs_df = repo.load_killer_victim_pairs_as_polars(match_id)

# 2. Analyser avec Polars
result = (
    pairs_df
    .filter(pl.col("killer_xuid") == me_xuid)
    .group_by("victim_xuid")
    .agg(pl.count().alias("kills"))
    .sort("kills", descending=True)
)

# 3. Convertir pour Plotly si nécessaire
data_for_plot = result.to_dicts()
```

---

## Métriques de Succès

### Performance

| Métrique | Cible | Mesure |
|----------|-------|--------|
| Temps chargement antagonistes | < 100ms | Benchmark |
| Temps calcul score objectifs | < 50ms | Benchmark |
| Temps génération graphiques | < 200ms | Benchmark |

### Qualité

| Métrique | Cible | Mesure |
|----------|-------|--------|
| Couverture tests | > 80% | pytest-cov |
| Intégrité données | 100% | Validation scripts |
| Documentation | Complète | Review |

---

## Risques et Mitigation

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| API refdata non disponible | Élevé | Moyenne | Fallback Discovery UGC, calcul depuis médailles |
| Performance Polars insuffisante | Moyen | Faible | Benchmark précoce, optimisation requêtes |
| Migration données complexe | Moyen | Moyenne | Scripts de backfill progressifs, validation |
| Incompatibilité Streamlit | Faible | Faible | Tests d'intégration précoces |

---

## Dépendances entre Sprints

```
Sprint 0 (Investigation)
    ↓
Sprint 1 (Schémas BDD)
    ↓
Sprint 2 (Extraction Refdata) ──┐
    ↓                            │
Sprint 3 (Antagonistes Polars)   │
    ↓                            │
Sprint 4 (Score Personnel)      │
    ↓                            │
Sprint 5 (Viz Antagonistes)     │
    ↓                            │
Sprint 6 (Performance Cumulée)  │
    ↓                            │
Sprint 7 (Analyses Avancées)    │
    ↓                            │
Sprint 8 (Backfill) ←───────────┘
    ↓
Sprint 9 (Optimisation)
```

---

## Checklist de Démarrage

- [x] Script d'investigation refdata créé (`scripts/investigate_refdata_fields.py`)
- [x] Plan d'intégration documenté (`.ai/research/SPNKR_REFDATA_INTEGRATION_PLAN.md`)
- [x] Environnement Python configuré (Polars 1.37.1 installé)
- [x] Tokens API SPNKr configurés et fonctionnels
- [x] Base DuckDB de test disponible
- [x] Scripts d'investigation **exécutés** (résultats API obtenus)
- [x] Module refdata créé avec enums complets (`src/data/domain/refdata.py`)
- [x] Architecture Polars validée (6/6 tests)

### Sprints terminés

- [x] **SPRINT 0 TERMINÉ** ✅ (Investigation + Préparation)
- [x] **SPRINT 1 TERMINÉ** ✅ (Persistance Killer-Victim + Schémas)
- [x] **SPRINT 2 TERMINÉ** ✅ (Extraction Refdata + game_variant_category)
- [x] **SPRINT 3 TERMINÉ** ✅ (Fonctions Polars Antagonistes)
- [x] **SPRINT 4 TERMINÉ** ✅ (Analyses Score Personnel avec Polars - 26 tests)
- [x] **SPRINT 5 TERMINÉ** ✅ (Visualisations Antagonistes - 8 graphiques)

### Prochains sprints

- [ ] Sprint 6 : Performance Cumulée avec Polars
- [ ] Sprint 7 : Analyses Score Personnel Avancées
- [ ] Sprint 8 : Backfill et Migration
- [ ] Sprint 9 : Optimisation et Tests Finaux

---

## Références

- [Polars Documentation](https://pola-rs.github.io/polars/)
- [DuckDB Polars Integration](https://duckdb.org/docs/guides/python/polars)
- `.ai/research/SPNKR_REFDATA_INTEGRATION_PLAN.md`
- `.ai/features/ANTAGONIST_CHARTS_CUMULATIVE_PERF_PLAN.md`
- `docs/SQL_SCHEMA.md`

---

*Dernière mise à jour : 2026-02-03 (Sprints 4 & 5 terminés)*
