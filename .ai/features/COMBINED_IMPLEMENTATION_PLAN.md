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
- Vérifier disponibilité API pour refdata
- Valider l'architecture Polars
- Préparer les schémas BDD

### Tâches

| ID | Tâche | Fichiers | Estimation |
|----|-------|----------|------------|
| 0.1 | Exécuter script investigation refdata | `scripts/investigate_refdata_fields.py` | 2h |
| 0.2 | Documenter résultats API (GameVariantCategory, PersonalScoreAwards) | `.ai/research/API_REFDATA_FIELDS.md` | 2h |
| 0.3 | Créer module refdata avec enums SPNKr | `src/data/domain/refdata.py` | 4h |
| 0.4 | Tests unitaires module refdata | `tests/test_refdata.py` | 2h |
| 0.5 | Valider architecture Polars (exemples de requêtes) | `scripts/test_polars_integration.py` | 3h |

### Livrables
- ✅ Résultats investigation API
- ✅ Module `refdata.py` avec enums complets
- ✅ Tests de validation Polars
- ✅ Documentation schémas BDD étendus

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

## Sprint 4 : Analyses Score Personnel avec Polars (1 semaine)

### Objectifs
- Analyser `personal_score_awards` avec Polars
- Créer KPIs de participation aux objectifs
- Valoriser assistances différenciées

### Tâches

| ID | Tâche | Fichiers | Estimation |
|----|-------|----------|------------|
| 4.1 | Créer `compute_objective_participation_score_polars()` | `src/analysis/objective_participation.py` | 4h |
| 4.2 | Créer `rank_players_by_objective_contribution_polars()` | `src/analysis/objective_participation.py` | 4h |
| 4.3 | Créer `compute_assist_breakdown_polars()` | `src/analysis/objective_participation.py` | 3h |
| 4.4 | Créer requêtes DuckDB optimisées pour Polars | `src/data/repositories/duckdb_repo.py` | 3h |
| 4.5 | Tests unitaires analyses | `tests/test_objective_participation.py` | 3h |

### Code exemple Polars

```python
import polars as pl
from src.data.domain.refdata import PersonalScoreNameId, OBJECTIVE_SCORES, ASSIST_SCORES

def compute_objective_participation_score_polars(
    awards_df: pl.DataFrame,
    match_id: str,
) -> dict[str, Any]:
    """Calcule score de participation aux objectifs avec Polars."""
    match_awards = awards_df.filter(pl.col("match_id") == match_id)
    
    # Score objectifs
    objective_score = (
        match_awards
        .filter(pl.col("award_name_id").is_in(list(OBJECTIVE_SCORES)))
        .with_columns(
            (pl.col("count") * pl.lit(100)).alias("points")  # Exemple : 100 pts par action
        )
        .select(pl.sum("points"))
        .item()
    )
    
    # Score assistances
    assist_score = (
        match_awards
        .filter(pl.col("award_name_id").is_in(list(ASSIST_SCORES)))
        .with_columns(
            pl.when(pl.col("award_name_id") == PersonalScoreNameId.KILL_ASSIST)
            .then(pl.col("count") * 50)
            .when(pl.col("award_name_id") == PersonalScoreNameId.MARK_ASSIST)
            .then(pl.col("count") * 10)
            .otherwise(pl.col("count") * 10)
            .alias("points")
        )
        .select(pl.sum("points"))
        .item()
    )
    
    return {
        "objective_score": objective_score or 0,
        "assist_score": assist_score or 0,
        "total_score": objective_score + assist_score,
    }
```

### Livrables
- ✅ Module d'analyse objectifs avec Polars
- ✅ KPIs calculés
- ✅ Requêtes optimisées

---

## Sprint 5 : Visualisations Antagonistes (1 semaine)

### Objectifs
- Créer graphiques antagonistes avec Plotly
- Intégrer dans pages UI
- Utiliser Polars pour préparer données

### Tâches

| ID | Tâche | Fichiers | Estimation |
|----|-------|----------|------------|
| 5.1 | Créer `plot_killer_victim_stacked_bars()` | `src/visualization/antagonist_charts.py` | 4h |
| 5.2 | Créer `plot_kd_timeseries()` | `src/visualization/antagonist_charts.py` | 4h |
| 5.3 | Adapter chargement UI pour utiliser DuckDB | `src/ui/pages/match_view_players.py` | 3h |
| 5.4 | Intégrer graphiques dans page match | `src/ui/pages/match_view_players.py` | 3h |
| 5.5 | Tests visuels et validation | Tests manuels | 2h |

### Code exemple

```python
import polars as pl
import plotly.graph_objects as go

def plot_killer_victim_stacked_bars(
    pairs_df: pl.DataFrame,
    match_id: str,
) -> go.Figure:
    """Graphique barres empilées killer-victim avec Polars."""
    match_pairs = pairs_df.filter(pl.col("match_id") == match_id)
    
    # Préparer données avec Polars
    counts = (
        match_pairs
        .group_by("killer_xuid", "killer_gamertag", "victim_xuid", "victim_gamertag")
        .agg(pl.count().alias("count"))
        .sort("count", descending=True)
    )
    
    # Convertir en format Plotly
    killers = counts["killer_gamertag"].unique().to_list()
    victims = counts["victim_gamertag"].unique().to_list()
    
    # Créer graphique empilé
    fig = go.Figure()
    # ... logique de création graphique
    
    return fig
```

### Livrables
- ✅ Graphiques antagonistes fonctionnels
- ✅ Intégration UI complète
- ✅ Documentation utilisateur

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

- [ ] Environnement Python configuré (Polars >= 0.20.0)
- [ ] Tokens API SPNKr configurés
- [ ] Base DuckDB de test disponible
- [ ] Scripts d'investigation exécutés
- [ ] Équipe alignée sur architecture Polars

---

## Références

- [Polars Documentation](https://pola-rs.github.io/polars/)
- [DuckDB Polars Integration](https://duckdb.org/docs/guides/python/polars)
- `.ai/research/SPNKR_REFDATA_INTEGRATION_PLAN.md`
- `.ai/features/ANTAGONIST_CHARTS_CUMULATIVE_PERF_PLAN.md`
- `docs/SQL_SCHEMA.md`

---

*Dernière mise à jour : 2026-02-03*
