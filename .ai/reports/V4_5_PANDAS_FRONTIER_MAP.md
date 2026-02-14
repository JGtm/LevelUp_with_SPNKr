# Cartographie des frontières Pandas — v4.5 Release

> **Date** : 2026-02-13  
> **Périmètre** : `src/` complet  
> **Objectif** : Documenter chaque usage Pandas résiduel avec sa justification

---

## Synthèse

| Catégorie | Fichiers | Occurrences | Statut |
|-----------|:---:|:---:|:---:|
| **BRIDGE** — couche de conversion officielle | 2 | 6 | ✅ Justifié |
| **FRONTIER** — Plotly/Streamlit exige Pandas | 5 | 13 | ✅ Justifié |
| **LEGACY** — candidats migration future | 5 | 11 | ⚠️ Dette |
| **RAG/AI** — API LanceDB | 1 | 2 | ✅ Exception |
| **Total** | **10 fichiers** | **32 occurrences** | |

**Progression** :  
- S13 baseline : **36 fichiers**, **37** `.to_pandas()`  
- S18 mesure : **10 fichiers**, **19** `.to_pandas()`  
- **Réduction** : **-72% fichiers**, **-49% conversions**

---

## 1. BRIDGE — Couche de conversion officielle ✅

| Fichier | Lignes | Usage |
|---------|--------|-------|
| `src/visualization/_compat.py` | L21 | `import pandas as pd` (TYPE_CHECKING) |
| `src/visualization/_compat.py` | L41, L52 | `to_pandas_for_plotly()`, `to_pandas_for_st()` |
| `src/data/integration/streamlit_bridge.py` | L25 | `import pandas as pd` |
| `src/data/integration/streamlit_bridge.py` | L152-204 | `pd.DataFrame()`, `pd.to_datetime()`, `pd.to_numeric()` |

**Justification** : Points de conversion canoniques Polars↔Pandas pour l'UI. Seront les derniers à disparaître (quand Streamlit supportera nativement Polars).

---

## 2. FRONTIER — Frontières Plotly/Streamlit ✅

| Fichier | Lignes | Usage | Consommateur |
|---------|--------|-------|-------------|
| `src/visualization/participation_charts.py` | L79, L184, L294, L458 | `.to_pandas()` ×4 | `go.Pie()`, `go.Bar()`, `go.Sunburst()` |
| `src/visualization/distributions.py` | L28 | `import pandas` (TYPE_CHECKING) | Type hint `pd.Series` |
| `src/ui/components/duckdb_analytics.py` | L161 | `.to_pandas().set_index()` | `st.line_chart()` |
| `src/ui/pages/objective_analysis.py` | L325, L350, L360 | `.to_pandas()` ×3 | `st.dataframe()` |
| `src/ui/pages/teammates_impact.py` | L118 | `.to_pandas()` | `st.dataframe()` |
| `src/ui/pages/win_loss.py` | L8, L467 | `import pandas`, `.to_pandas()` | `.style.apply()` |

**Justification** : Plotly `go.*()` et Streamlit `st.dataframe()` / `.style.apply()` exigent des Pandas DataFrames. Pas d'alternative sans patch upstream.

---

## 3. LEGACY — Candidats migration future ⚠️

| Fichier | Lignes | Usage | Effort |
|---------|--------|-------|--------|
| `src/data/services/win_loss_service.py` | L16, L68-135 | `compute_period_table()` entier en Pandas | **P1** — ≈2h |
| `src/analysis/performance_score.py` | L410, L423, L464, L475 | `.to_pandas()` ×4 rétro-compat | **P2** — ≈1h |
| `src/data/repositories/_arrow_bridge.py` | L59 | `pl.from_pandas()` tolérance | **P3** — trivial |
| `src/ui/cache_filters.py` | L281-283 | Détection type Pandas | **P3** — trivial |
| `src/ui/pages/match_view_helpers.py` | L34 | `hasattr(..., "to_pydatetime")` | **P3** — trivial |

**Action recommandée** : Backlog post-v4.5. Pas bloquant pour la release.

---

## 4. RAG/AI — Exception documentée ✅

| Fichier | Lignes | Usage |
|---------|--------|-------|
| `src/ai/rag.py` | L565, L693 | `self.table.to_pandas()` — API LanceDB |

**Justification** : LanceDB retourne des DataFrames Pandas. Le module RAG est optionnel et isolé.

---

## Décision v4.5

Les 10 fichiers restants avec Pandas sont **tous justifiés** ou classés en dette future (backlog). La release v4.5 peut procéder avec cet état.

**Aucun `import pandas` n'est gratuit** — chaque occurrence est documentée et classifiée.
