# Audit legacy S17 — Entrée (vague B + perf)

> **Date** : 2026-02-13  
> **Périmètre** : global `src/`  
> **Objectif** : Confirmer le reliquat legacy et préparer la clôture v4.5.

---

## 1) Reliquat Pandas global

### Fichiers `import pandas` hors périmètre S16

| # | Fichier | Ligne | Zone |
|---|---------|-------|------|
| 1 | `src/analysis/maps.py` | L11 | analysis |
| 2 | `src/analysis/stats.py` | L13 | analysis |
| 3 | `src/app/filters.py` | L20 | app |
| 4 | `src/app/filters_render.py` | L20 | app |
| 5 | `src/app/helpers.py` | L15 | app |
| 6 | `src/app/kpis.py` | L23 | app |
| 7 | `src/app/kpis_render.py` | L38 | app |
| 8 | `src/app/page_router.py` | L20 | app |
| 9 | `src/data/integration/streamlit_bridge.py` | L25 | data |
| 10 | `src/ui/cache.py` | L24 | ui |
| 11 | `src/ui/commendations.py` | L26 | ui |
| 12 | `src/ui/components/chart_annotations.py` | L15 | ui/components |
| 13 | `src/ui/components/duckdb_analytics.py` | L133, L213 | ui/components (local) |
| 14 | `src/ui/components/performance.py` | L16 | ui/components |
| 15 | `src/ui/formatting.py` | L19 | ui |
| 16 | `src/ui/perf.py` | L19 | ui |

**Total S17** : **16 fichiers** restants après S16

### Occurrences `.to_pandas()` hors périmètre S16

| Fichier | Occurrences | Lignes |
|---------|-------------|--------|
| `src/ui/cache.py` | 5 | L133, L144, L177, L182, L187 |
| `src/analysis/performance_score.py` | 4 | L410, L423, L464, L475 |
| `src/app/filters_render.py` | 3 | L102, L604, L622 |
| `src/app/filters.py` | 1 | L50 |
| `src/ui/components/performance.py` | 1 | L33 |
| `src/ui/perf.py` | 1 | L98 |
| `src/ai/rag.py` | 2 | L565, L693 |
| **Total** | **17** | |

### Exceptions frontière documentées

- `src/ai/rag.py` : RAG module — Pandas nécessaire pour embeddings/vectorisation (exception validée)
- `src/data/integration/streamlit_bridge.py` : pont officiel Polars ↔ Pandas pour Streamlit (sera le seul survivant)

---

## 2) Reliquat `src.db` / compat legacy

### Références runtime `src.db`

| Fichier | Ligne | Import |
|---------|-------|--------|
| `src/data/sync/engine.py` | L378 | `from src.db.migrations import ensure_match_stats_columns` |
| `src/data/sync/engine.py` | L387 | `from src.db.migrations import ensure_match_participants_columns` |
| `src/data/sync/engine.py` | L781 | `from src.db.migrations import ensure_performance_score_column` |

**Action S17** : Déplacer les 3 fonctions de migration de `src/db/migrations.py` vers `src/data/sync/` ou `src/data/repositories/`, puis supprimer la dépendance `src.db`.

### Wrappers/compat à supprimer

| Module | Contenu | Action |
|--------|---------|--------|
| `src/db/__init__.py` | Vide (0 lignes de code) | Supprimer si aucun import externe |
| `src/db/migrations.py` | 69 stmts, 3 fonctions (`ensure_*_columns`) | Migrer vers `src/data/` puis supprimer |

---

## 3) Hotspots complexité / taille

### Fichiers > 800 lignes (global `src/`, hors périmètre S16 traité)

| Fichier | Lignes | Zone |
|---------|--------|------|
| `src/data/repositories/duckdb_repo.py` | **3 158** | data |
| `src/data/sync/transformers.py` | **1 468** | data/sync |
| `src/ui/cache.py` | **1 321** | ui |
| `src/data/sync/engine.py` | **1 298** | data/sync |
| `src/data/media_indexer.py` | **1 058** | data |
| `src/analysis/objective_participation.py` | **1 016** | analysis |
| `src/analysis/killer_victim.py` | **976** | analysis |
| `src/ui/commendations.py` | **962** | ui |
| `src/analysis/performance_score.py` | **948** | analysis |
| `src/data/sync/api_client.py` | **907** | data/sync |
| `src/ui/sync.py` | **869** | ui |

### Fonctions > 80 lignes (hors périmètre S16)

#### `src/data/repositories/duckdb_repo.py` — 10 fonctions

| Fonction | Taille |
|----------|--------|
| `load_match_rosters()` | **336 lignes** |
| `_clean_gamertag()` | 279 lignes |
| `load_matches()` | 185 lignes |
| `refresh_materialized_views()` | 178 lignes |
| `load_matches_paginated()` | 129 lignes |
| `load_recent_matches()` | 113 lignes |
| `load_matches_from_archives()` | 108 lignes |
| `save_antagonists()` | 104 lignes |
| `load_matches_in_range()` | 94 lignes |
| `load_match_players_stats()` | 82 lignes |

### Plan de découpage hotspots

| Cible | Action |
|-------|--------|
| `duckdb_repo.py` (3158 lignes) | Extraire modules : `roster_loader.py`, `match_queries.py`, `materialized_views.py`, `antagonists_repo.py` |
| `cache.py` (1321 lignes) | Extraire : `cache_loaders.py`, `cache_filters.py` |
| `session_compare.py` (1182 lignes) | Extraire sous-rendus en helpers |
| `engine.py` (1298 lignes) | Extraire `match_processor.py`, `migration_compat.py` |

---

## 4) Préparation optimisation Arrow/Polars

### Cibles

- Helper officiel DuckDB → Arrow → Polars (zéro copie quand possible) dans `duckdb_repo.py`
- Réduction conversions intermédiaires (supprimer les `.to_pandas()` non-frontière)
- Mesure CPU/RAM sur 3 parcours : timeseries, teammates, carrière

### Baseline perf avant S17

| Mesure | Valeur |
|--------|--------|
| DuckDB `load_matches_all` (407 matchs) | ~15ms (mode hybrid) |
| Couverture globale post-S16 | Cible >= 65% |
| Conversions `.to_pandas()` post-S16 | Cible <= 17 (périmètre S17) |

---

## 5) Gate d'entrée S17

- [x] Reliquat Pandas global confirmé (16 fichiers, 17 `.to_pandas()`)
- [x] Reliquat `src.db` confirmé (3 imports dans `engine.py`)
- [x] Hotspots priorisés avec plan de découpage
- [x] Baseline perf avant optimisation (benchmark_v1 existant)
