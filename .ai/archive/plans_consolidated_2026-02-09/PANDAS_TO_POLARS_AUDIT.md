# Audit Pandas → Polars

> **Règle projet** : Préférer Polars à Pandas pour les gros volumes (CLAUDE.md).
> **Objectif** : Migrer progressivement l’ensemble du code applicatif vers Polars, en conservant Pandas uniquement là où une dépendance externe l’exige (Streamlit, Plotly dans certains cas).

## Résumé

| Catégorie | Fichiers | Action |
|-----------|----------|--------|
| **À migrer vers Polars** | src/visualization, src/analysis, src/ui, src/app | Remplacer `pd.DataFrame` par `pl.DataFrame`, API Pandas par API Polars |
| **Couche données** | cache.py, data_loader.py, DuckDBRepository | Retourner Polars au lieu de convertir en Pandas |
| **Points de conversion** | Streamlit st.dataframe, Plotly customdata | Convertir `pl.DataFrame.to_pandas()` uniquement à l’interface |
| **Tests** | test_*.py | Utiliser Polars pour les fixtures, adapter les assertions |
| **Scripts** | scripts/*.py | Migrer vers Polars si traitement de données |

---

## 1. Points à migrer vers Polars

### 1.1 `src/visualization/timeseries.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 3 | `import pandas as pd` | Remplacer par `import polars as pl` |
| 13 | `_rolling_mean(series: pd.Series)` | Remplacer par `pl.Series` + `pl.col().rolling_mean()` |
| 18+ | `plot_timeseries(df: pd.DataFrame)` | Accepter `pl.DataFrame`, utiliser `df["col"]` Polars |
| 57, 170 | `pd.to_numeric(..., errors="coerce")` | `pl.col().cast(pl.Float64)` ou `str.to_float()` |
| 197, 408 | `_rolling_mean(pd.to_numeric(...))` | `pl.col().cast(pl.Float64).rolling_mean()` |
| 482-484 | `pd.Series`, `pd.isna()` | Équivalents Polars |
| 607, 623 | `pd.to_numeric`, `pd.isna` | Polars `cast`, `is_nan` |
| 136-210 | `plot_assists_timeseries`, `plot_per_minute_timeseries` | Idem : df Polars, rolling Polars |
| 356-429 | `plot_accuracy_last_n`, `plot_average_life` | Idem |
| 430-499 | `plot_spree_headshots_accuracy` | Idem |
| 578-669 | `plot_performance_timeseries` | Idem |

**Objectif** : Toutes les fonctions de timeseries acceptent et manipulent `pl.DataFrame`.

---

### 1.2 `src/visualization/distributions.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 6 | `import pandas as pd` | Remplacer par Polars |
| 16+ | `plot_kda_distribution(df: pd.DataFrame)` | Accepter `pl.DataFrame` |
| 27 | `pd.to_numeric(d["kda"])` | `pl.col("kda").cast(pl.Float64)` |
| 88-156 | `plot_outcomes_over_time` | Pivot, datetime → Polars |
| 118-125 | `pd.to_datetime`, `pd.Timedelta` | `pl.col().str.to_datetime()`, `pl.duration` |
| 219-366 | `plot_stacked_outcomes_by_category`, etc. | Migrer pivot et agrégations |
| 531, 557 | `pd.Series`, `isinstance(values, pd.Series)` | `pl.Series`, `isinstance(values, pl.Series)` |
| 757-964 | `plot_correlation_scatter`, `plot_first_event_distribution` | Migrer |

**Objectif** : Visualisations distributions en Polars natif.

---

### 1.3 `src/analysis/sessions.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 15 | `import pandas as pd` | Garder pour fonctions legacy, migrer progressivement |
| 31 | `compute_sessions(df: pd.DataFrame)` | Déjà une version Polars : `compute_sessions_with_context_polars` (ligne 173+) |
| 53-54, 99-100 | `pd.Series(dtype=int/str)` | Remplacer par `pl.Series` ou `pl.lit(None).cast()` |
| 114 | `pd.Series(0, index=d.index)` | `pl.lit(0)` ou équivalent |
| 163 | `pd.Timedelta(days=1)` | `pl.duration(days=1)` |

**Note** : Le module a déjà `compute_sessions_with_context_polars`. Unifier sur Polars et déprécier les versions Pandas.

---

### 1.4 `src/ui/cache.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 28 | `import pandas as pd` | Réduire, convertir retours en Polars |
| 89+ | `cached_load_match_data()` retourne `pd.DataFrame` | Retourner `pl.DataFrame` |
| 118, 130 | `df_pl.to_pandas()` | **Supprimer** : garder Polars jusqu’à l’UI |
| 138-160 | `load_df_optimized` → `df0` Pandas | Charger en Polars, passer `pl.DataFrame` aux callers |
| 513-540 | `cached_load_match_data_paginated` | Retourner `pl.DataFrame`, pagination Polars |
| 699-777 | `load_df_optimized` construit `pd.DataFrame` | Construire `pl.DataFrame` directement |
| 768-777 | `pd.to_datetime`, `pd.to_numeric` | Polars `str.to_datetime`, `cast` |
| 877+ | Toutes les fonctions retournant `pd.DataFrame` | Migrer vers `pl.DataFrame` |

**Objectif** : La couche cache retourne Polars. Les conversions Pandas se font uniquement dans les composants UI qui en ont besoin (Streamlit, export CSV).

---

### 1.5 `src/ui/pages/*.py`

| Fichier | Usage | Action |
|---------|--------|--------|
| `last_match.py` | `pd.DataFrame`, `pd.to_datetime` | Accepter `pl.DataFrame`, adapter les accès |
| `win_loss.py` | `pd.Series`, `pd.DataFrame`, `pd.to_datetime`, `pd.Timedelta` | Migrer vers Polars |
| `timeseries.py` | `pd.DataFrame` | Déjà alimenté par cache ; migrer quand cache retourne Polars |
| `teammates_helpers.py` | `pd.Timestamp`, `pd.isna`, `pd.notna` | `pl.Timestamp` ou `datetime`, `is_nan` |
| `teammates.py` | `pd.DataFrame` partout | Migrer |
| `session_compare.py` | `pd.DataFrame`, `pd.isna`, `pd.notna` | Migrer |
| `media_library.py` | `pd.DataFrame`, `pd.concat`, `pd.merge_asof`, `pd.to_datetime` | Migrer (merge_asof → `pl.DataFrame.join_asof`) |
| `match_view_helpers.py` | `pd.Series`, `pd.to_datetime`, `pd.isna` | Migrer |
| `match_view_charts.py` | `pd.Series`, `pd.DataFrame`, `pd.to_numeric` | Migrer |
| `match_view.py` | `pd.Series`, `pd.DataFrame` | Migrer |
| `match_history.py` | `pd.DataFrame`, `pd.Timestamp`, `pd.isna`, `pd.to_numeric` | Migrer |
| `citations.py` | `pd.DataFrame`, `pd.to_numeric` | Migrer |
| `objective_analysis.py` | Déjà Polars pour analyses, `.to_pandas()` pour tables UI | Réduire les to_pandas |

---

### 1.6 `src/app/*.py`

| Fichier | Usage | Action |
|---------|--------|--------|
| `page_router.py` | `pd.DataFrame` (df_full, dff, base) | Accepter `pl.DataFrame` |
| `main_helpers.py` | `load_df_optimized` → `pd.DataFrame` | Adapter quand cache retourne Polars |
| `filters_render.py` | `pd.DataFrame`, `pd.to_datetime`, `pd.Timestamp` | Migrer |
| `data_loader.py` | `load_match_data()` retourne `pd.DataFrame` | Retourner `pl.DataFrame` |

---

### 1.7 `src/analysis/killer_victim.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 26 | `import pandas as pd` | Garder pour `killer_victim_counts_long`, `killer_victim_matrix` (legacy) |
| 641-666 | `killer_victim_counts_long()` retourne `pd.DataFrame` | Déjà `killer_victim_counts_long_polars` : déprécier la version Pandas |
| 666+ | `killer_victim_matrix()` | Déjà `killer_victim_matrix_polars` : déprécier Pandas |

**Objectif** : Supprimer les fonctions Pandas, garder uniquement les versions `_polars`.

---

### 1.8 `src/data/sync/engine.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 63 | `import pandas as pd` | Utilisé pour `pd.Series` dans une conversion |
| 844 | `match_series = pd.Series(...)` | Remplacer par `pl.Series` ou structure native |

---

### 1.9 `src/ui/components/duckdb_analytics.py`

| Ligne(s) | Usage | Action |
|----------|--------|--------|
| 133, 213 | `import pandas as pd` | Construire `pl.DataFrame` depuis les données, puis `.to_pandas()` si affichage Streamlit requis |

---

### 1.10 Scripts

| Fichier | Usage | Action |
|---------|--------|--------|
| `scripts/sync.py` | `pd.DataFrame` pour agrégations | Migrer vers Polars si volume significatif |
| `scripts/backfill_data.py` | `pd.Series` pour match_series | Remplacer par Polars |
| `scripts/compute_historical_performance.py` | `pd.Series`, `pd.DataFrame`, `pd.read_sql_query` | Migrer : `pd.read_sql` → DuckDB + Polars |
| `scripts/benchmark_polars.py` | Référence Pandas pour comparaison | Garder pour benchmark |
| `scripts/test_media_library_*.py` | `pd.DataFrame` fixtures | Migrer en `pl.DataFrame` |

---

## 2. Tests

| Fichier | Usage | Action |
|---------|--------|--------|
| `tests/test_visualizations.py` | `pd.DataFrame`, `pd.Series`, `pd.date_range` | Créer fixtures Polars, adapter les tests |
| `tests/test_timeseries_performance_score.py` | `pd.DataFrame`, `pd.isna` | Migrer |
| `tests/test_phase6_refactoring.py` | `pd.Timestamp`, `pd.Series` | Migrer |
| `tests/test_media_library_keys.py` | `pd.DataFrame` | Migrer |
| `tests/test_performance_score.py` | `pd.DataFrame`, `pd.concat` | Migrer |
| `tests/test_session_compare_hist_avg_category.py` | `pd.DataFrame` | Migrer |
| `tests/test_app_phase2.py` | `pd.DataFrame` | Migrer |
| `tests/test_analysis.py` | `pd.DataFrame`, `pd.Series` | Migrer |

---

## 3. Points de conversion Pandas (à conserver si nécessaire)

Certains composants exigent Pandas en entrée :

| Composant | Raison | Action |
|-----------|--------|--------|
| `st.dataframe()` | Streamlit accepte Pandas et Polars | Vérifier : Polars supporté nativement en Streamlit récent |
| `st.line_chart`, `st.bar_chart` | Format attendu Pandas | Utiliser `st.plotly_chart` avec figures Plotly (déjà le cas) |
| `go.Figure` Plotly | `customdata` peut être liste/numpy | Polars `.to_numpy()` ou `.to_list()` suffit |
| Export CSV | `df.to_csv()` | Polars : `pl.DataFrame.write_csv()` |

**Recommandation** : Garder `.to_pandas()` uniquement aux frontières UI quand un composant Streamlit/Plotly ne supporte pas Polars. Documenter ces points.

---

## 4. Équivalences Pandas → Polars

| Pandas | Polars |
|--------|--------|
| `pd.DataFrame()` | `pl.DataFrame()` |
| `pd.Series()` | `pl.Series()` |
| `df["col"]` | `df["col"]` ou `df.select(pl.col("col"))` |
| `df.sort_values("col")` | `df.sort("col")` |
| `pd.to_datetime(col)` | `pl.col("col").str.to_datetime()` |
| `pd.to_numeric(col, errors="coerce")` | `pl.col("col").cast(pl.Float64)` ou `str.to_float()` |
| `pd.isna(x)` | `x is None` ou `pl.lit(x).is_nan()` selon contexte |
| `df.dropna(subset=[...])` | `df.drop_nulls(subset=[...])` |
| `df.fillna(val)` | `df.fill_null(val)` |
| `df.rolling(window).mean()` | `pl.col("col").rolling_mean(window_size=window)` |
| `pd.merge_asof(a, b, ...)` | `a.join_asof(b, ...)` |
| `pd.concat([df1, df2])` | `pl.concat([df1, df2])` |
| `df.groupby().agg()` | `df.group_by().agg()` |
| `df.pivot_table()` | `df.pivot()` ou `df.group_by().agg()` |

---

## 5. Ordre de migration recommandé

1. **Couche données** : `load_df_optimized`, `cached_load_*` → retourner `pl.DataFrame`
2. **Analyses** : `sessions.py`, `killer_victim.py` → supprimer versions Pandas
3. **Visualisations** : `timeseries.py`, `distributions.py` → accepter Polars
4. **Pages UI** : migrer page par page (filters → page_router → pages)
5. **Tests** : adapter les fixtures et assertions
6. **Scripts** : migrer les scripts de traitement

---

## 6. Dépendance pandas (pyproject.toml)

- `pandas>=2.0.0` : À conserver jusqu’à migration complète.
- Après migration : passer en dépendance optionnelle ou de dev si des librairies tierces (Streamlit, Plotly) l’exigent encore.

---

*Dernière mise à jour : 2026-02-05*
