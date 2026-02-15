# Baseline v4.5 — LevelUp

> **Date** : 2026-02-13  
> **Branche** : `sprint13/v4.5-roadmap-hardening`  
> **Objectif** : Établir la baseline factuelle avant exécution S14-S18.

---

## 1) Environnement

| Paramètre | Valeur |
|-----------|--------|
| OS | Windows 11 |
| Python | 3.12.10 (`.venv` à la racine) |
| Commande canonique | `python -m ...` |
| Healthcheck | `python scripts/check_env.py` ✅ |

---

## 2) Baseline tests

### Commandes

```bash
python -m pytest -q --ignore=tests/integration
python -m pytest tests/integration -q           # (si environnement OK)
```

### Résultats (2026-02-13)

| Suite | Passed | Skipped | Failed | Durée |
|-------|--------|---------|--------|-------|
| Unitaires/stables (hors integration) | **1065** | 48 | **0** | 35.78s |
| Intégration | — | — | — | Non exécuté (optionnel) |
| E2E navigateur | — | — | — | Non exécuté (requiert `--run-e2e-browser`) |

**Détail skipped (48)** :
- 13 : tests E2E browser (`test_streamlit_browser_e2e.py`)
- 11 : tests `test_cache_integrity.py` (nécessitent données réelles)
- 24 : conditions spécifiques (RAG, archives, polars compat, etc.)

---

## 3) Baseline conformité architecture

| Indicateur | Total | Statut |
|------------|-------|--------|
| `import pandas` dans `src/` | **36** (34 fichiers) | ⚠️ Migration Polars incomplète |
| `import sqlite3` dans `src/` | **0** | ✅ Propre |
| `sqlite_master` dans `src/` | **0** | ✅ Propre |
| `.to_pandas()` dans `src/` | **37** (16 fichiers) | ⚠️ Ponts de conversion actifs |
| `from src.db` / `import src.db` | **3** (1 fichier : `engine.py`) | ⚠️ Legacy résiduel |

### Répartition `import pandas` par zone

| Zone | Fichiers |
|------|----------|
| `src/ui/pages/` | 13 fichiers |
| `src/visualization/` | 6 fichiers |
| `src/app/` | 5 fichiers |
| `src/ui/` (hors pages) | 5 fichiers |
| `src/ui/components/` | 3 fichiers |
| `src/analysis/` | 2 fichiers |
| `src/data/` | 1 fichier |

### Points chauds `.to_pandas()`

| Fichier | Occurrences |
|---------|-------------|
| `src/ui/cache.py` | 5 |
| `src/analysis/performance_score.py` | 4 |
| `src/visualization/participation_charts.py` | 4 |
| `src/app/filters_render.py` | 3 |
| `src/ui/pages/objective_analysis.py` | 3 |

### Références `src.db` (legacy)

| Fichier | Ligne | Import |
|---------|-------|--------|
| `src/data/sync/engine.py` | L378 | `from src.db.migrations import ensure_match_stats_columns` |
| `src/data/sync/engine.py` | L387 | `from src.db.migrations import ensure_match_participants_columns` |
| `src/data/sync/engine.py` | L781 | `from src.db.migrations import ensure_performance_score_column` |

---

## 4) Baseline qualité code

### Lint ruff (2026-02-13)

| Indicateur | Total |
|------------|-------|
| Erreurs lint globales (`ruff check src/`) | **198** (96 auto-fixables) |
| Fonctions complexes C901 (> 10) | **100** |

### Top 10 complexité cyclomatique

| Fonction | Fichier | Score C901 |
|----------|---------|------------|
| `compute_personal_antagonists` | `src/analysis/killer_victim.py` | **51** |
| `load_match_rosters` | `src/data/repositories/duckdb_repo.py` | **50** |
| `apply_filters` | `src/app/filters_render.py` | **33** |
| `render_h5g_commendations_section` | `src/ui/commendations.py` | **32** |
| `_compute_custom_citation_value` | `src/ui/commendations.py` | **26** |
| `compute_relative_performance_score` | `src/analysis/performance_score.py` | **25** |
| `render_hierarchical_checkbox_filter` | `src/ui/components/checkbox_filter.py` | **24** |
| `render_h5g_commendations_tracking_rules` | `src/ui/commendations.py` | **22** |
| `scan_and_index` | `src/data/media_indexer.py` | **21** |
| `transform_skill_stats` / `_extract_mmr_from_skill` | `src/data/sync/transformers.py` | **19** |

### Taille code

| Indicateur | Total |
|------------|-------|
| Fichiers `.py` dans `src/` | **140** |
| Fichiers > 600 lignes | **25** |
| Fichiers > 1200 lignes (seuil bloquant) | **6** |
| Fonctions > 80 lignes (fichiers critiques) | **30** |
| Fonctions > 120 lignes (seuil bloquant) | **20+** |

### Top 5 fichiers par taille

| Fichier | Lignes |
|---------|--------|
| `src/data/repositories/duckdb_repo.py` | **3 158** |
| `src/data/sync/transformers.py` | 1 468 |
| `src/ui/pages/teammates.py` | 1 334 |
| `src/ui/cache.py` | 1 321 |
| `src/data/sync/engine.py` | 1 298 |

---

## 5) Baseline couverture

```bash
python -m pytest --ignore=tests/integration --tb=no -q --cov=src --cov-report=term-missing
```

### Résultats (2026-02-13)

| Indicateur | Valeur |
|------------|--------|
| **Couverture globale** | **39%** (19 053 stmts, 10 914 miss) |

### Couverture modules critiques

| Module | Stmts | Miss | Branches | BrMiss | Couverture |
|--------|-------|------|----------|--------|------------|
| `src/data/repositories/duckdb_repo.py` | 1490 | 282 | 538 | 115 | **79%** |
| `src/data/sync/engine.py` | 394 | 269 | 126 | 10 | **28%** |
| `src/ui/pages/timeseries.py` | 229 | 217 | 80 | 0 | **4%** |
| `src/ui/pages/teammates.py` | 446 | 365 | 126 | 5 | **16%** |
| `src/ui/pages/win_loss.py` | 230 | 214 | 74 | 0 | **5%** |

> **Constat** : Le code data/repositories est bien couvert (79%). Les pages UI sont quasi-non couvertes (4-16%) car elles dépendent de Streamlit runtime. Le moteur de sync est faiblement couvert (28%).

### Paliers cibles

| Sprint | Cible |
|--------|-------|
| **S13 (baseline)** | **39%** (mesuré) |
| S15 | >= 55% |
| S16 | >= 65% |
| S17 | >= 72% |
| S18 (release) | >= 75% global, >= 85% modules critiques |

---

## 6) Baseline performance

- **Source** : `.ai/reports/benchmark_v1.json` (2026-02-01)
- Benchmark v1 porte sur les comparaisons legacy vs hybrid (DuckDB), mesuré sur 407 matchs
- **Parcours cibles v4.5** : timeseries, teammates, carrière
- Mesures initiales UI non disponibles (nécessite instrumentation Streamlit)
- **Référence sync** : DuckDB ~15ms/requête pour `load_matches_all` (vs ~4.5ms legacy SQLite — surcoût initial DuckDB compensé par scalabilité et agrégats)

---

## 7) Décisions verrouillées v4.5

- ✅ **DuckDB-first** — architecture cible sans dépendance SQLite
- ✅ **Parquet optionnel** (non bloquant) — archivage uniquement
- ✅ **Tolérance Pandas transitoire** : autorisé jusqu'à S17 (levée progressive), frontière Plotly/Streamlit tolérée en S18
- ✅ **Cible couverture release** : >= 75% global et >= 85% modules critiques
- ✅ **Standards clean code** : fonctions <= 50 lignes (alerte > 80, bloquant > 120), fichiers <= 600 lignes (alerte > 800, bloquant > 1200)

---

## 8) Go/No-Go S14

- [x] Baseline tests complète
- [x] Baseline conformité complète
- [x] Baseline couverture complète
- [x] Baseline performance initiale (benchmark_v1 + référence)
- [x] **Feu vert exécution S14** ✅
