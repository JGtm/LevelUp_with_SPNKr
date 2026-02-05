# Plan de Tests des Visualisations

> **Date**: 2026-02-02  
> **Objectif**: Tester 100% des fonctions de visualisation pour garantir qu'elles produisent des `go.Figure` valides avec des données correctes.

## 1. Inventaire des Fonctions à Tester

### 1.1 `src/visualization/distributions.py` (10 fonctions)

| Fonction | Signature | Retour | Priorité |
|----------|-----------|--------|----------|
| `plot_kda_distribution` | `(df: DataFrame)` | `go.Figure` | P1 |
| `plot_outcomes_over_time` | `(df, session_style=False)` | `tuple[go.Figure, str]` | P1 |
| `plot_stacked_outcomes_by_category` | `(df, category_col, ...)` | `go.Figure` | P1 |
| `plot_win_ratio_heatmap` | `(df, ...)` | `go.Figure` | P2 |
| `plot_top_weapons` | `(weapons_data, ...)` | `go.Figure` | P2 |
| `plot_histogram` | `(values, ...)` | `go.Figure` | P2 |
| `plot_medals_distribution` | `(medals_data, medal_names, ...)` | `go.Figure` | P2 |
| `plot_correlation_scatter` | `(df, x_col, y_col, ...)` | `go.Figure` | P2 |
| `plot_matches_at_top_by_week` | `(df, ...)` | `go.Figure` | P3 |
| `plot_first_event_distribution` | `(first_kills, first_deaths, ...)` | `go.Figure` | P3 |

### 1.2 `src/visualization/timeseries.py` (7 fonctions)

| Fonction | Signature | Retour | Priorité |
|----------|-----------|--------|----------|
| `plot_timeseries` | `(df, title=...)` | `go.Figure` | P1 |
| `plot_assists_timeseries` | `(df, title=...)` | `go.Figure` | P1 |
| `plot_per_minute_timeseries` | `(df, title=...)` | `go.Figure` | P1 |
| `plot_accuracy_last_n` | `(df, n)` | `go.Figure` | P2 |
| `plot_average_life` | `(df, title=...)` | `go.Figure` | P2 |
| `plot_spree_headshots_accuracy` | `(df, perfect_counts=...)` | `go.Figure` | P2 |
| `plot_performance_timeseries` | `(df, df_history=..., ...)` | `go.Figure` | P1 |

### 1.3 `src/visualization/maps.py` (2 fonctions)

| Fonction | Signature | Retour | Priorité |
|----------|-----------|--------|----------|
| `plot_map_comparison` | `(df_breakdown, metric, title)` | `go.Figure` | P2 |
| `plot_map_ratio_with_winloss` | `(df_breakdown, title)` | `go.Figure` | P2 |

### 1.4 `src/visualization/match_bars.py` (2 fonctions)

| Fonction | Signature | Retour | Priorité |
|----------|-----------|--------|----------|
| `plot_metric_bars_by_match` | `(df_, ...)` | `go.Figure \| None` | P2 |
| `plot_multi_metric_bars_by_match` | `(series, ...)` | `go.Figure \| None` | P2 |

### 1.5 `src/visualization/trio.py` (1 fonction)

| Fonction | Signature | Retour | Priorité |
|----------|-----------|--------|----------|
| `plot_trio_metric` | `(d_self, d_f1, d_f2, ...)` | `go.Figure` | P2 |

### 1.6 `src/ui/components/radar_chart.py` (3 fonctions)

| Fonction | Signature | Retour | Priorité |
|----------|-----------|--------|----------|
| `create_radar_chart` | `(data, ...)` | `go.Figure` | P2 |
| `create_stats_per_minute_radar` | `(players, ...)` | `go.Figure` | P2 |
| `create_performance_radar` | `(players, ...)` | `go.Figure` | P2 |

### 1.7 `src/ui/components/chart_annotations.py` (2 fonctions)

| Fonction | Signature | Retour | Priorité |
|----------|-----------|--------|----------|
| `add_extreme_annotations` | `(fig, x_values, y_values, ...)` | `go.Figure` | P3 |
| `annotate_timeseries_extremes` | `(fig, df, ...)` | `go.Figure` | P3 |

---

## 2. Stratégie de Test

### 2.1 Types de Tests

1. **Tests de validité** — Vérifie que chaque fonction retourne un `go.Figure` valide
2. **Tests de données vides** — Vérifie la gestion des DataFrames vides
3. **Tests de NaN/None** — Vérifie la robustesse face aux valeurs manquantes
4. **Tests de colonnes manquantes** — Vérifie la gestion des colonnes absentes
5. **Tests de contenu** — Vérifie que les traces contiennent des données

### 2.2 Fixtures Communes

```python
@pytest.fixture
def sample_match_df() -> pd.DataFrame:
    """DataFrame type avec colonnes de match standard."""
    return pd.DataFrame({
        "match_id": [f"match_{i}" for i in range(20)],
        "start_time": pd.date_range("2025-01-01", periods=20, freq="h"),
        "kills": np.random.randint(5, 25, 20),
        "deaths": np.random.randint(3, 15, 20),
        "assists": np.random.randint(2, 12, 20),
        "accuracy": np.random.uniform(30, 60, 20),
        "ratio": np.random.uniform(0.5, 2.5, 20),
        "kda": np.random.uniform(-5, 10, 20),
        "outcome": np.random.choice([1, 2, 3, 4], 20),
        "map_name": np.random.choice(["Recharge", "Streets", "Live Fire"], 20),
        "playlist_name": np.random.choice(["Ranked", "Quick Play"], 20),
        "time_played_seconds": np.random.randint(300, 900, 20),
        "kills_per_min": np.random.uniform(0.3, 1.5, 20),
        "deaths_per_min": np.random.uniform(0.2, 1.0, 20),
        "assists_per_min": np.random.uniform(0.1, 0.8, 20),
        "headshot_kills": np.random.randint(1, 10, 20),
        "max_killing_spree": np.random.randint(0, 8, 20),
        "average_life_seconds": np.random.uniform(20, 60, 20),
    })

@pytest.fixture
def empty_df() -> pd.DataFrame:
    """DataFrame vide avec les colonnes attendues."""
    return pd.DataFrame(columns=[
        "match_id", "start_time", "kills", "deaths", "assists",
        "accuracy", "ratio", "kda", "outcome", "map_name",
    ])

@pytest.fixture
def df_with_nans(sample_match_df) -> pd.DataFrame:
    """DataFrame avec des valeurs NaN."""
    df = sample_match_df.copy()
    df.loc[0:5, "kills"] = np.nan
    df.loc[10:15, "accuracy"] = np.nan
    return df
```

### 2.3 Pattern de Test Standard

```python
def test_plot_function_returns_valid_figure(sample_match_df):
    """La fonction retourne une go.Figure valide."""
    fig = plot_function(sample_match_df)
    
    # Assertions de base
    assert isinstance(fig, go.Figure)
    assert fig.layout is not None
    
    # Vérifier qu'il y a au moins une trace
    assert len(fig.data) > 0
    
def test_plot_function_handles_empty_df(empty_df):
    """La fonction gère les DataFrames vides sans erreur."""
    fig = plot_function(empty_df)
    assert isinstance(fig, go.Figure)
    
def test_plot_function_handles_nans(df_with_nans):
    """La fonction gère les NaN sans erreur."""
    fig = plot_function(df_with_nans)
    assert isinstance(fig, go.Figure)
```

---

## 3. Structure des Fichiers de Test

```
tests/
├── test_visualizations/
│   ├── __init__.py
│   ├── conftest.py              # Fixtures communes
│   ├── test_distributions.py    # Tests distributions.py
│   ├── test_timeseries.py       # Tests timeseries.py
│   ├── test_maps.py             # Tests maps.py
│   ├── test_match_bars.py       # Tests match_bars.py
│   ├── test_trio.py             # Tests trio.py
│   ├── test_radar_chart.py      # Tests radar_chart.py
│   └── test_annotations.py      # Tests chart_annotations.py
└── test_visualizations.py       # Tests d'intégration (optionnel)
```

**Alternative simplifiée** (fichier unique):
```
tests/
└── test_visualizations.py       # Tous les tests dans un seul fichier
```

---

## 4. Intégration CI/CD

### 4.1 Modification de `.github/workflows/ci.yml`

```yaml
- name: Run visualization tests
  run: |
    pytest tests/test_visualizations.py -v --tb=short
```

### 4.2 Marker pytest pour les tests de visualisation

```python
# Dans conftest.py ou pyproject.toml
[tool.pytest.ini_options]
markers = [
    "visualization: tests des fonctions de visualisation",
]
```

Exécution ciblée:
```bash
pytest -m visualization -v
```

---

## 5. Plan d'Implémentation

### Phase 1 — Fondations (immédiat)
- [ ] Créer `tests/test_visualizations.py`
- [ ] Implémenter les fixtures communes
- [ ] Tester les 5 fonctions P1 (timeseries, distributions principales)

### Phase 2 — Couverture complète
- [ ] Tester les 12 fonctions P2
- [ ] Tester les 5 fonctions P3

### Phase 3 — Intégration
- [ ] Ajouter les tests au workflow CI
- [ ] Créer un rapport de couverture

---

## 6. Checklist des Tests

### `src/visualization/distributions.py`

- [ ] `test_plot_kda_distribution_valid_data`
- [ ] `test_plot_kda_distribution_empty_df`
- [ ] `test_plot_kda_distribution_all_nans`
- [ ] `test_plot_outcomes_over_time_valid_data`
- [ ] `test_plot_outcomes_over_time_session_style`
- [ ] `test_plot_outcomes_over_time_empty_df`
- [ ] `test_plot_stacked_outcomes_by_category_valid`
- [ ] `test_plot_stacked_outcomes_by_category_empty`
- [ ] `test_plot_win_ratio_heatmap_valid`
- [ ] `test_plot_win_ratio_heatmap_empty`
- [ ] `test_plot_top_weapons_valid`
- [ ] `test_plot_top_weapons_empty`
- [ ] `test_plot_histogram_valid`
- [ ] `test_plot_histogram_empty`
- [ ] `test_plot_histogram_with_kde`
- [ ] `test_plot_medals_distribution_valid`
- [ ] `test_plot_medals_distribution_empty`
- [ ] `test_plot_correlation_scatter_valid`
- [ ] `test_plot_correlation_scatter_with_trendline`
- [ ] `test_plot_correlation_scatter_empty`
- [ ] `test_plot_matches_at_top_by_week_valid`
- [ ] `test_plot_matches_at_top_by_week_empty`
- [ ] `test_plot_first_event_distribution_valid`
- [ ] `test_plot_first_event_distribution_empty`

### `src/visualization/timeseries.py`

- [ ] `test_plot_timeseries_valid`
- [ ] `test_plot_timeseries_empty`
- [ ] `test_plot_assists_timeseries_valid`
- [ ] `test_plot_assists_timeseries_empty`
- [ ] `test_plot_per_minute_timeseries_valid`
- [ ] `test_plot_per_minute_timeseries_empty`
- [ ] `test_plot_accuracy_last_n_valid`
- [ ] `test_plot_accuracy_last_n_empty`
- [ ] `test_plot_average_life_valid`
- [ ] `test_plot_average_life_empty`
- [ ] `test_plot_spree_headshots_accuracy_valid`
- [ ] `test_plot_spree_headshots_accuracy_with_perfects`
- [ ] `test_plot_spree_headshots_accuracy_empty`
- [ ] `test_plot_performance_timeseries_valid`
- [ ] `test_plot_performance_timeseries_with_history`
- [ ] `test_plot_performance_timeseries_empty`

### `src/visualization/maps.py`

- [ ] `test_plot_map_comparison_valid`
- [ ] `test_plot_map_comparison_empty`
- [ ] `test_plot_map_ratio_with_winloss_valid`
- [ ] `test_plot_map_ratio_with_winloss_empty`

### `src/visualization/match_bars.py`

- [ ] `test_plot_metric_bars_by_match_valid`
- [ ] `test_plot_metric_bars_by_match_empty`
- [ ] `test_plot_metric_bars_by_match_missing_column`
- [ ] `test_plot_multi_metric_bars_by_match_valid`
- [ ] `test_plot_multi_metric_bars_by_match_empty`

### `src/visualization/trio.py`

- [ ] `test_plot_trio_metric_valid`
- [ ] `test_plot_trio_metric_empty`
- [ ] `test_plot_trio_metric_partial_data`

### `src/ui/components/radar_chart.py`

- [ ] `test_create_radar_chart_valid`
- [ ] `test_create_radar_chart_empty`
- [ ] `test_create_stats_per_minute_radar_valid`
- [ ] `test_create_stats_per_minute_radar_empty`
- [ ] `test_create_performance_radar_valid`
- [ ] `test_create_performance_radar_empty`

### `src/ui/components/chart_annotations.py`

- [ ] `test_add_extreme_annotations_valid`
- [ ] `test_add_extreme_annotations_empty`
- [ ] `test_annotate_timeseries_extremes_valid`
- [ ] `test_annotate_timeseries_extremes_empty`

---

## 7. Métriques de Succès

| Métrique | Objectif |
|----------|----------|
| Couverture fonctions | 100% (27 fonctions) |
| Tests par fonction | ≥ 2 (valid + empty) |
| Total tests | ~60-70 tests |
| Temps d'exécution CI | < 30s |
| Taux de réussite | 100% |

---

## 8. Notes Techniques

### 8.1 Dépendances requises

```python
# Dans pyproject.toml ou requirements-dev.txt
pytest>=7.0
plotly>=5.0
pandas>=2.0
numpy>=1.24
```

### 8.2 Gestion des imports circulaires

Certaines fonctions de visualisation importent des modules de config. S'assurer que les mocks sont en place si nécessaire:

```python
@pytest.fixture(autouse=True)
def mock_config(monkeypatch):
    """Mock les configurations si nécessaire."""
    # Exemple: mock HALO_COLORS si problème d'import
    pass
```

### 8.3 Validation des traces Plotly

```python
def assert_figure_has_data(fig: go.Figure, min_traces: int = 1):
    """Vérifie qu'une figure contient des données."""
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= min_traces
    
    for trace in fig.data:
        # Vérifier que la trace a des données (x ou y)
        has_x = hasattr(trace, 'x') and trace.x is not None and len(trace.x) > 0
        has_y = hasattr(trace, 'y') and trace.y is not None and len(trace.y) > 0
        has_r = hasattr(trace, 'r') and trace.r is not None and len(trace.r) > 0  # Pour radar
        has_z = hasattr(trace, 'z') and trace.z is not None  # Pour heatmap
        
        assert has_x or has_y or has_r or has_z, f"Trace {type(trace).__name__} sans données"
```

---

## 9. Prochaines Étapes

1. **Créer le fichier `tests/test_visualizations.py`** avec toutes les fixtures et tests
2. **Exécuter les tests localement** : `pytest tests/test_visualizations.py -v`
3. **Corriger les éventuels bugs** découverts
4. **Mettre à jour le CI** pour inclure ces tests
5. **Documenter** dans `thought_log.md`
