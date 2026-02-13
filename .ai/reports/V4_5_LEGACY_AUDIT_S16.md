# Audit legacy S16 — Entrée (vague A UI/Viz)

> **Date** : 2026-02-13  
> **Périmètre** : `src/ui/pages/`, `src/visualization/`  
> **Objectif** : Figer l'état legacy avant migration Pandas vague A.

---

## 1) Inventaire Pandas (périmètre S16)

### Fichiers avec `import pandas` — périmètre S16

#### `src/visualization/` — 6 fichiers

| Fichier | Ligne | Notes |
|---------|-------|-------|
| `distributions.py` | L17 | Utilise pd pour transformations + Plotly |
| `maps.py` | L11 | Conversion .to_pandas() L22 |
| `match_bars.py` | L18 | Conversion .to_pandas() L32 |
| `timeseries.py` | L14 | Conversions .to_pandas() L29, L45 |
| `trio.py` | L11 | Conversion .to_pandas() L22 |
| `participation_charts.py` | — | Pas d'import top-level mais 4× .to_pandas() |

#### `src/ui/pages/` — 13 fichiers

| Fichier | Ligne | Notes |
|---------|-------|-------|
| `citations.py` | L11 | |
| `last_match.py` | L18 | |
| `match_history.py` | L19 | |
| `match_view.py` | L20 | .to_pandas() L111 |
| `match_view_charts.py` | L12 | .to_pandas() L56, L279 |
| `match_view_helpers.py` | L17 | |
| `match_view_participation.py` | L14 | |
| `media_library.py` | L34 | |
| `session_compare.py` | L16 | |
| `teammates.py` | L12 | .to_pandas() L115, L585 |
| `teammates_charts.py` | L12 | |
| `timeseries.py` | L12 | |
| `win_loss.py` | L12 | |

**Total périmètre S16** : **19 fichiers** avec `import pandas` + `.to_pandas()`

### Occurrences `.to_pandas()` — périmètre S16

| Fichier | Occurrences | Lignes |
|---------|-------------|--------|
| `src/visualization/participation_charts.py` | 4 | L79, L184, L294, L458 |
| `src/visualization/timeseries.py` | 2 | L29, L45 |
| `src/visualization/distributions.py` | 1 | L32 |
| `src/visualization/maps.py` | 1 | L22 |
| `src/visualization/match_bars.py` | 1 | L32 |
| `src/visualization/trio.py` | 1 | L22 |
| `src/ui/pages/match_view.py` | 1 | L111 |
| `src/ui/pages/match_view_charts.py` | 2 | L56, L279 |
| `src/ui/pages/teammates.py` | 2 | L115, L585 |
| `src/ui/pages/objective_analysis.py` | 3 | L325, L350, L360 |
| **Total** | **18** | |

### Frontières explicitement autorisées

- Conversion `.to_pandas()` en entrée de Plotly Express (`px.bar`, `px.scatter`, etc.) — Plotly ne supporte pas nativement Polars
- Conversion `.to_pandas()` en entrée de `st.dataframe()` / `st.data_editor()` — Streamlit a un support Polars partiel

---

## 2) Vérification SQLite / sqlite_master

| Indicateur | Total | Statut |
|------------|-------|--------|
| `import sqlite3` dans `src/` | **0** | ✅ Propre |
| `sqlite_master` dans `src/` | **0** | ✅ Propre |

---

## 3) Hotspots clean code S16

### Fichiers > 600 lignes (périmètre S16)

| Fichier | Lignes | Priorité |
|---------|--------|----------|
| `src/ui/pages/teammates.py` | **1 334** | 🔴 Bloquant (> 1200) |
| `src/ui/pages/session_compare.py` | **1 182** | 🟡 Alerte (> 800) |
| `src/visualization/distributions.py` | **1 104** | 🟡 Alerte (> 800) |
| `src/visualization/timeseries.py` | **1 080** | 🟡 Alerte (> 800) |
| `src/ui/pages/media_library.py` | **874** | 🟡 Alerte (> 800) |
| `src/ui/pages/teammates_charts.py` | ~300 | ✅ OK |
| `src/ui/pages/win_loss.py` | ~510 | ✅ OK |
| `src/ui/pages/timeseries.py` | ~535 | ✅ OK |

### Fonctions > 80 lignes (périmètre S16)

#### `src/ui/pages/teammates.py` — 7 fonctions géantes

| Fonction | Lignes | Taille |
|----------|--------|--------|
| `_render_trio_view()` | L1070–L1334 | **265 lignes** |
| `_render_impact_taquinerie()` | L424–L614 | 191 lignes |
| `_render_multi_teammate_view()` | L906–L1069 | 164 lignes |
| `_render_single_teammate_view()` | L754–L905 | 152 lignes |
| `_render_synergy_radar()` | L169–L308 | 140 lignes |
| `render_teammates_page()` | L615–L753 | 139 lignes |
| `_render_trio_synergy_radar()` | L309–L423 | 115 lignes |

#### `src/ui/pages/win_loss.py` — 3 fonctions

| Fonction | Lignes | Taille |
|----------|--------|--------|
| `render_win_loss_page()` | L94–L416 | **323 lignes** |
| `_style_pct()` | L307–L416 | 110 lignes |
| `_render_map_table()` | L417–L507 | 91 lignes |

#### `src/ui/pages/timeseries.py` — 1 fonction monolithique

| Fonction | Lignes | Taille |
|----------|--------|--------|
| `render_timeseries_page()` | L48–L532 | **485 lignes** |

#### `src/visualization/distributions.py` — 9 fonctions

| Fonction | Lignes | Taille |
|----------|--------|--------|
| `plot_stacked_outcomes_by_category()` | L261–L410 | 150 lignes |
| `plot_matches_at_top_by_week()` | L862–L997 | 136 lignes |
| `plot_outcomes_over_time()` | L127–L260 | 134 lignes |
| `plot_correlation_scatter()` | L744–L861 | 118 lignes |
| `plot_histogram()` | L574–L682 | 109 lignes |
| `plot_first_event_distribution()` | L998–L1104 | 107 lignes |
| `plot_win_ratio_heatmap()` | L411–L508 | 98 lignes |
| `plot_kda_distribution()` | L36–L126 | 91 lignes |

---

## 4) Risques de migration vague A

1. **Régression visuelle** sur pages timeseries / win-loss / teammates
2. **Rupture contrats DataFrame** entre page et visualisation (types colonnes)
3. **Dégradation perf** si conversions multiples Polars ↔ Pandas en cascade
4. **Fonctions monolithiques** : refactor obligatoire avant migration (risque d'erreur si 485 lignes d'un bloc)
5. **Frontière Plotly** : nécessite `.to_pandas()` — centraliser le point de conversion

---

## 5) Plan d'exécution recommandé S16

1. **Migrer les visualisations** (`distributions`, `timeseries`, `maps`, `match_bars`, `trio`) — opérations Polars-natives, conversion `.to_pandas()` centralisée en sortie
2. **Migrer les pages UI** (`timeseries`, `win_loss`, `teammates`, `teammates_charts`) — consommer `pl.DataFrame`, convertir uniquement à la frontière Streamlit
3. **Centraliser** un helper `to_pandas_for_plotly()` dans un utilitaire viz
4. **Découper** les fonctions > 120 lignes avant migration (teammates + timeseries + win_loss)
5. **Valider** via tests wave A + non-régression visuelle

---

## 6) Gate d'entrée S16

- [x] Inventaire Pandas validé
- [x] Vérification SQLite/sqlite_master validée
- [x] Hotspots priorisés
- [x] Stratégie de refactor validée
