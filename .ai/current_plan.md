# Plan Courant : Sprint 1 - Clôturer Phase 1 (Stabilisation)

> Généré par `/pm` le 2026-02-01
> Objectif : Finaliser la Phase 1 avec validation et benchmarks

## Statut Global

| Phase | Statut | Progression |
|-------|--------|-------------|
| Phase 1 - Stabilisation | 🟡 En cours | 80% |
| Phase 2 - Shadow Compare | ⏳ Planifié | 0% |
| Phase 3 - Bascule Hybrid | ⏳ Backlog | 0% |
| Phase 4 - Optimisations | ⏳ Future | 0% |

---

## Sprint 1 : Tâches

### 1.1 Script Benchmark CLI ✅

**Fichier** : `scripts/benchmark_hybrid.py`

Compare les performances Legacy vs Hybrid sur les opérations clés :
- `load_matches()` (tous les matchs)
- `load_matches(playlist_filter=...)` (requête filtrée)
- `get_match_count()`
- `get_storage_info()`

**Usage** :
```bash
# Benchmark avec 5 itérations
python scripts/benchmark_hybrid.py --db data/spnkr_gt_Chocoboflor.db --iterations 5

# Export JSON
python scripts/benchmark_hybrid.py --db data/spnkr_gt_Chocoboflor.db --output .ai/reports/benchmark_v1.json

# Aide
python scripts/benchmark_hybrid.py --help
```

**Output** :
```
======================================================================
BENCHMARK LEGACY vs HYBRID
======================================================================
Benchmark                 Legacy (ms)     Hybrid (ms)     Speedup   Winner
----------------------------------------------------------------------
load_matches_all               45.2 ms        38.1 ms     1.19x    Hybrid ✓
load_matches_ranked            12.3 ms         8.7 ms     1.41x    Hybrid ✓
get_match_count                 2.1 ms         1.8 ms     1.17x    Hybrid ✓
----------------------------------------------------------------------
```

---

### 1.2 Tests E2E Cohérence ✅

**Fichier** : `tests/test_hybrid_benchmark.py`

Tests pytest validant :
- **Cohérence** : Legacy et Hybrid retournent les mêmes données
- **Performance** : Hybrid au moins aussi rapide que Legacy
- **Shadow Compare** : Mode SHADOW_COMPARE détecte les divergences

**Classes de test** :
- `TestHybridConsistency` : Vérifie que les deux modes retournent les mêmes résultats
- `TestHybridPerformance` : Mesure et compare les temps d'exécution
- `TestShadowCompareMode` : Valide le comportement du mode SHADOW_COMPARE

**Usage** :
```bash
# Exécuter tous les tests
pytest tests/test_hybrid_benchmark.py -v

# Avec affichage des prints (timing)
pytest tests/test_hybrid_benchmark.py -v -s

# Un test spécifique
pytest tests/test_hybrid_benchmark.py::TestHybridConsistency::test_match_count_consistency -v
```

---

### 1.3 Exécuter Benchmarks en Prod ⏳

**À faire** :
1. Exécuter le benchmark sur une vraie DB de joueur
2. Sauvegarder le rapport JSON dans `.ai/reports/benchmark_v1.json`
3. Analyser les résultats

**Commande** :
```bash
python scripts/benchmark_hybrid.py \
  --db data/players/Chocoboflor.db \
  --iterations 5 \
  --output .ai/reports/benchmark_v1.json
```

---

### 1.4 Documenter Pain Points ⏳

**À faire** :
1. Noter les problèmes rencontrés dans `.ai/thought_log.md`
2. Identifier les requêtes lentes ou problématiques
3. Lister les améliorations pour Phase 2

---

## Infrastructure Existante

### Repositories

| Mode | Classe | Source | Utilisation |
|------|--------|--------|-------------|
| LEGACY | `LegacyRepository` | SQLite (MatchCache) | Production actuelle |
| HYBRID | `HybridRepository` | Parquet + DuckDB | Cible |
| SHADOW | `ShadowRepository` | Les deux | Migration |

### Modes Shadow

| Mode | Comportement |
|------|--------------|
| `SHADOW_READ` | Lit Legacy, peut écrire Hybrid |
| `SHADOW_COMPARE` | Lit les deux, compare, log divergences |
| `HYBRID_FIRST` | Préfère Hybrid, fallback Legacy |

---

## Prochaines Étapes

Après Sprint 1 :
1. **Sprint 2** : Activer SHADOW_COMPARE en dev pour détecter les divergences
2. **Sprint 3** : Migrer toutes les requêtes UI vers Hybrid
3. **Sprint 4** : Supprimer MatchCache, optimiser avec Delta Lake

---

## Références

- `ARCHITECTURE_ROADMAP.md` : Roadmap complète des phases
- `docs/DATA_ARCHITECTURE.md` : Architecture technique
- `src/data/repositories/shadow.py` : Pattern Shadow
- `src/data/repositories/factory.py` : Factory de repositories

---

*Dernière mise à jour : 2026-02-01*
