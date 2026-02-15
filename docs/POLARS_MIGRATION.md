# Migration Pandas → Polars — Guide Complet

> **Date** : 2026-02-06  
> **Sprint** : Sprint 4 — Migration Pandas → Polars Progressive  
> **Statut** : ✅ Migration principale terminée

## Vue d'ensemble

Ce document décrit la migration progressive de Pandas vers Polars dans le projet LevelUp. La migration a été effectuée de manière progressive pour maintenir la compatibilité avec l'UI existante.

### Principes de migration

1. **Couche données** : Retourne Polars (`pl.DataFrame`)
2. **Analyses** : Acceptent Polars (et Pandas pour compatibilité)
3. **Visualisations** : Acceptent Polars (conversion interne vers Pandas pour Plotly)
4. **UI** : Reçoit Pandas (conversion depuis Polars aux frontières)

## Architecture de la migration

### Flux de données

```
DuckDB → Polars → Analyses → Visualisations → Pandas → UI (Streamlit/Plotly)
```

### Points de conversion

| Point | Conversion | Raison |
|-------|------------|--------|
| `load_df_optimized()` | → `pl.DataFrame` | Couche données native Polars |
| `compute_*()` | `pl.DataFrame` → `pd.DataFrame` (interne) | Compatibilité avec opérations Pandas complexes |
| `plot_*()` | `pl.DataFrame` → `pd.DataFrame` (interne) | Plotly nécessite Pandas |
| `streamlit_app.py` | `pl.DataFrame` → `pd.DataFrame` | Pages UI utilisent encore Pandas |

## Fonctions migrées

### Couche données

#### `src/ui/cache.py`

- ✅ `load_df_optimized()` → Retourne `pl.DataFrame`
- ✅ `load_df_hybrid()` → Retourne `pl.DataFrame`
- ✅ `cached_compute_sessions_db()` → Utilise Polars en interne

#### `src/app/data_loader.py`

- ✅ `load_match_data()` → Retourne `pl.DataFrame`

#### `src/app/main_helpers.py`

- ✅ `load_match_dataframe()` → Retourne `pl.DataFrame`

### Analyses

#### `src/analysis/stats.py`

- ✅ `compute_aggregated_stats()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `compute_outcome_rates()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `compute_global_ratio()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `compute_mode_category_averages()` → Accepte `pd.DataFrame | pl.DataFrame`

#### `src/analysis/sessions.py`

- ✅ `compute_sessions()` → Détecte automatiquement Pandas/Polars
- ⚠️ `compute_sessions_with_context()` → Dépréciée (utiliser `compute_sessions_with_context_polars()`)

#### `src/analysis/performance_score.py`

- ✅ `compute_performance_series()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `compute_relative_performance_score()` → Accepte Polars pour `df_history`
- ✅ `compute_session_performance_score_v1()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `compute_session_performance_score_v2()` → Accepte `pd.DataFrame | pl.DataFrame`

#### `src/analysis/maps.py`

- ✅ `compute_map_breakdown()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `map_breakdown_to_models()` → Accepte `pd.DataFrame | pl.DataFrame`

#### `src/analysis/killer_victim.py`

- ⚠️ `killer_victim_counts_long()` → Dépréciée (utiliser `killer_victim_counts_long_polars()`)
- ⚠️ `killer_victim_matrix()` → Dépréciée (utiliser `killer_victim_matrix_polars()`)

### Visualisations

#### `src/visualization/timeseries.py`

- ✅ `plot_timeseries()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `plot_assists_timeseries()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `plot_per_minute_timeseries()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `plot_accuracy_last_n()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `plot_average_life()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `plot_spree_headshots_accuracy()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `plot_performance_timeseries()` → Accepte `pd.DataFrame | pl.DataFrame`

#### `src/visualization/distributions.py`

- ✅ `plot_kda_distribution()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `plot_outcomes_over_time()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `plot_stacked_outcomes_by_category()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `plot_histogram()` → Accepte `pd.Series | pl.Series | np.ndarray`
- ✅ `plot_correlation_scatter()` → Accepte `pd.DataFrame | pl.DataFrame`

### Helpers et utilitaires

#### `src/app/filters_render.py`

- ✅ `apply_filters()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `render_filters_sidebar()` → Accepte `pd.DataFrame | pl.DataFrame`

#### `src/app/filters.py`

- ✅ `add_ui_columns()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `apply_date_filter()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `apply_checkbox_filters()` → Accepte `pd.DataFrame | pl.DataFrame`

#### `src/app/kpis.py`

- ✅ `compute_kpi_stats()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `avg_match_duration_seconds()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `compute_total_play_seconds()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `render_matches_summary()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `render_all_kpis()` → Accepte `pd.DataFrame | pl.DataFrame`

#### `src/app/helpers.py`

- ✅ `compute_session_span_seconds()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `compute_total_play_seconds()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `avg_match_duration_seconds()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `date_range()` → Accepte `pd.DataFrame | pl.DataFrame`

#### `src/app/kpis_render.py`

- ✅ `render_kpis_section()` → Accepte `pd.DataFrame | pl.DataFrame`

#### `src/ui/components/performance.py`

- ✅ `compute_session_performance_score()` → Accepte `pd.DataFrame | pl.DataFrame`
- ✅ `compute_session_performance_score_v2_ui()` → Accepte `pd.DataFrame | pl.DataFrame`

### Scripts

#### `scripts/backfill_data.py`

- ✅ Utilise `.pl()` pour charger directement en Polars depuis DuckDB
- ✅ Fallback sur `.df()` si `.pl()` n'est pas disponible

## Équivalences principales Pandas → Polars

| Pandas | Polars |
|--------|--------|
| `pd.DataFrame()` | `pl.DataFrame()` |
| `pd.Series()` | `pl.Series()` |
| `df["col"]` | `df["col"]` ou `df.select(pl.col("col"))` |
| `df.sort_values("col")` | `df.sort("col")` |
| `pd.to_datetime(col)` | `pl.col("col").str.to_datetime()` |
| `pd.to_numeric(col, errors="coerce")` | `pl.col("col").cast(pl.Float64)` |
| `pd.isna(x)` | `x is None` ou `pl.lit(x).is_nan()` |
| `df.dropna(subset=[...])` | `df.drop_nulls(subset=[...])` |
| `df.fillna(val)` | `df.fill_null(val)` |
| `df.rolling(window).mean()` | `pl.col("col").rolling_mean(window_size=window)` |
| `pd.merge_asof(a, b)` | `a.join_asof(b)` |
| `pd.concat([df1, df2])` | `pl.concat([df1, df2])` |
| `df.groupby().agg()` | `df.group_by().agg()` |
| `df.pivot_table()` | `df.pivot()` ou `df.group_by().agg()` |
| `df.empty` | `df.is_empty()` |
| `df.copy()` | `df.clone()` |
| `df.loc[mask]` | `df.filter(pl.col("col") == value)` |

## Pattern de normalisation

Toutes les fonctions qui acceptent les deux types utilisent un pattern de normalisation :

```python
def _normalize_df(df: pd.DataFrame | pl.DataFrame) -> pd.DataFrame:
    """Convertit un DataFrame Polars en Pandas si nécessaire."""
    if isinstance(df, pl.DataFrame):
        return df.to_pandas()
    return df

def ma_fonction(df: pd.DataFrame | pl.DataFrame) -> pd.DataFrame:
    """Ma fonction qui accepte Pandas ou Polars."""
    # Normaliser en Pandas pour compatibilité
    df = _normalize_df(df)
    
    # Utiliser les opérations Pandas normalement
    result = df.groupby("col").agg(...)
    return result
```

## Conversion timezone avec Polars

```python
# Pandas
df["start_time"] = (
    pd.to_datetime(df["start_time"], utc=True)
    .dt.tz_convert(PARIS_TZ_NAME)
    .dt.tz_localize(None)
)

# Polars
df = df.with_columns(
    pl.col("start_time")
    .str.to_datetime(time_zone="UTC")
    .dt.convert_time_zone(PARIS_TZ_NAME)
    .dt.replace_time_zone(None)
    .alias("start_time")
)
```

## Calculs par minute avec Polars

```python
# Pandas
minutes = (pd.to_numeric(df["time_played_seconds"], errors="coerce") / 60.0).astype(float)
minutes = minutes.where(minutes > 0)
df["kills_per_min"] = pd.to_numeric(df["kills"], errors="coerce") / minutes

# Polars
df = df.with_columns(
    (pl.col("time_played_seconds").cast(pl.Float64) / 60.0)
    .clip(lower_bound=0.0)
    .alias("minutes")
)
df = df.with_columns(
    (pl.col("kills").cast(pl.Float64) / pl.col("minutes")).alias("kills_per_min")
)
df = df.drop("minutes")
```

## Points de conversion intentionnels

### Frontières UI

Les conversions Polars → Pandas se font uniquement aux frontières UI :

1. **`streamlit_app.py`** : Conversion avant passage aux pages UI
2. **`apply_filters()`** : Conversion pour compatibilité avec le code de filtres
3. **`render_filters_sidebar()`** : Conversion pour compatibilité
4. **Fonctions de visualisation** : Conversion interne pour Plotly

### Raisons

- **Streamlit** : Certains composants nécessitent encore Pandas
- **Plotly** : Nécessite Pandas pour certaines opérations
- **Code legacy** : Le code de filtres utilise encore des opérations Pandas spécifiques

## Fonctions dépréciées

Les fonctions suivantes sont marquées comme dépréciées et seront supprimées dans une future version :

- `compute_sessions_with_context()` → Utiliser `compute_sessions_with_context_polars()`
- `killer_victim_counts_long()` → Utiliser `killer_victim_counts_long_polars()`
- `killer_victim_matrix()` → Utiliser `killer_victim_matrix_polars()`

## Migration des pages UI (optionnel)

Les pages UI dans `src/ui/pages/` peuvent être migrées progressivement vers Polars. Pour l'instant, elles fonctionnent car elles reçoivent Pandas après conversion au niveau de `streamlit_app.py`.

### Exemple de migration d'une page

```python
# Avant (Pandas)
def render_page(df: pd.DataFrame) -> None:
    df_filtered = df[df["kills"] > 10]
    st.write(df_filtered)

# Après (Polars)
def render_page(df: pd.DataFrame | pl.DataFrame) -> None:
    # Normaliser si nécessaire
    if isinstance(df, pl.DataFrame):
        df = df.to_pandas()  # Ou migrer complètement vers Polars
    
    df_filtered = df[df["kills"] > 10]
    st.write(df_filtered)
```

## Tests

### Fixtures Polars

Les tests doivent utiliser des fixtures Polars :

```python
import polars as pl

@pytest.fixture
def sample_df():
    return pl.DataFrame({
        "match_id": ["m1", "m2", "m3"],
        "kills": [10, 15, 12],
        "deaths": [5, 8, 6],
    })
```

### Assertions

```python
# Vérifier qu'un DataFrame Polars est vide
assert df.is_empty()

# Vérifier la longueur
assert len(df) == 3

# Vérifier les colonnes
assert "kills" in df.columns
```

## Performance

### Avantages de Polars

- **Performance** : Polars est généralement 5-10x plus rapide que Pandas
- **Mémoire** : Utilisation mémoire optimisée
- **Lazy evaluation** : Possibilité d'utiliser `pl.scan_parquet()` pour des requêtes optimisées

### Benchmarks

Voir `scripts/benchmark_polars.py` pour des benchmarks comparatifs.

## Prochaines étapes

1. ✅ Migration couche données → **TERMINÉ**
2. ✅ Migration analyses → **TERMINÉ**
3. ✅ Migration visualisations → **TERMINÉ**
4. ✅ Migration helpers → **TERMINÉ**
5. ⏳ Migration pages UI (optionnel) → En attente
6. ⏳ Tests avec fixtures Polars → En attente
7. ⏳ Documentation complète → **EN COURS**

## Références

- [Documentation Polars](https://pola-rs.github.io/polars/)
- [Guide de migration Pandas → Polars](https://pola-rs.github.io/polars/user-guide/migration/)
- Audit détaillé : `.ai/PANDAS_TO_POLARS_AUDIT.md`
- Roadmap : `.ai/CONSOLIDATED_AUDITS_AND_ROADMAP.md`

---

*Dernière mise à jour : 2026-02-06*
