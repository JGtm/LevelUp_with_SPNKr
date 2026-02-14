# Release Notes — LevelUp v4.5

> **Date** : 2026-02-14
> **Version** : 4.5.0 (`v4.5`)

---

## 🎉 Vue d'ensemble

Cette version majeure finalise la migration complète de l'architecture LevelUp vers DuckDB + Polars. Zéro SQLite, zéro module legacy, Polars natif dans le runtime. Benchmark validé avec gains sur tous les parcours.

---

## ✨ Nouvelles Fonctionnalités

### Score de Performance v4
- Nouveau calcul du score de performance intégrant :
  - KDA pondéré
  - Précision et headshots
  - Dommages infligés/reçus
  - Rangs et MMR (équipe/ennemi)
- Performance relative par rapport à la médiane du joueur

### Heatmap d'Impact & Cercle d'Amis (Sprint 12)
- **Heatmap d'impact coéquipiers** : Visualisation des moments clés (First Blood, Clutch, Last Casualty)
- **Tableau "Taquinerie"** : Ranking MVP/Boulet basé sur les événements de match
- Intégré dans l'onglet Coéquipiers

### Nouvelles Statistiques
- **Timeseries enrichies** : Évolution temporelle des métriques clés
- **Corrélations de performance** : Analyse des facteurs de succès
- **Comparaisons coéquipiers avancées** : Stats par minute, frags parfaits, radar trio

### Page Carrière
- Affichage du rang de carrière avec progression
- Icônes de rang et adornment
- Historique de progression

---

## 🔧 Améliorations Techniques

### Architecture
- **DuckDB v4 unifié** : Plus de fallback SQLite
- **Migration Polars complète** : 35+ fichiers migrés de Pandas vers Polars
- **Backfill modulaire** : Refactoring de `scripts/backfill_data.py` en modules (`scripts/backfill/`)

### Qualité du Code
- **1358 tests passants** (dont 30 nouveaux pour migrations)
- Tests de charge validés (1000-2000 matchs < 1s)
- Suppression complète du code legacy (`src/db/`, repositories hybrides)
- Zéro `import sqlite3`, zéro `from src.db` dans le runtime
- Benchmark post-migration : cold <160ms, warm <30ms, Polars→Pandas -28.6%

### Scripts Nettoyés
- Consolidation de 113 scripts vers 16 actifs
- Archivage des scripts obsolètes dans `scripts/_archive/`

---

## 🗂️ Sprints Livrés

| Sprint | Description | Statut |
|--------|-------------|--------|
| S0 | Bugs urgents (tri session, nettoyage filtres) | ✅ |
| S1 | Nettoyage scripts + archivage .ai/ | ✅ |
| S2 | Migration Pandas→Polars core | ✅ |
| S3 | Damage participants + Page Carrière | ✅ |
| S4 | Médianes, Frags, Modes, Médias | ✅ |
| S5 | Score de Performance v4 | ✅ |
| S6 | Nouvelles stats Phase 1 (Timeseries) | ✅ |
| S7 | Nouvelles stats Phase 2-3 (V/D, Dernier match) | ✅ |
| S8 | Nouvelles stats Phase 4 (Coéquipiers) | ✅ |
| S9 | Suppression code legacy | ✅ |
| S10 | Nettoyage données + Refactoring backfill | ✅ |
| S11 | Finalisation, tests, documentation | ✅ |
| S12 | Heatmap d'Impact & Cercle d'Amis | ✅ |
| S13 | Audit baseline v4.5 + gouvernance | ✅ |
| S14 | Backfill bitmask + perf score v4 | ✅ |
| S15 | Analyse participation objective | ✅ |
| S16 | Refactoring UI (découpage + migration Polars vague A) | ✅ |
| S17 | Migration Polars vague B + cache | ✅ |
| S18 | Stabilisation, benchmark, docs, release v4.5 | ✅ |

---

## 📊 Métriques

| Métrique | v4.1 | v4.5 |
|----------|-------|------|
| Tests passants | 1065 | 1358 |
| `import pandas` résiduel | 36 fichiers | 10 fichiers (-72%) |
| `import sqlite3` | 0 | 0 |
| `from src.db` | 3 | 0 |
| Violations N806 | 9 | 0 |
| Cold load (ms) | 161 | 153 (-5%) |
| Warm load (ms) | 21 | 22 (stable) |
| Polars→Pandas (ms) | 5.6 | 4.0 (-29%) |

---

## ⚠️ Breaking Changes

### Imports
Les anciens imports ne fonctionnent plus :
```python
# ❌ Ancien (supprimé)
from src.db.loaders import load_df_optimized

# ✅ Nouveau
from src.data.repositories import DuckDBRepository
repo = DuckDBRepository(db_path, xuid)
matches = repo.load_matches()
```

### Backfill
Les fonctions internes de backfill ont été déplacées :
```python
# ❌ Ancien
from scripts.backfill_data import _find_matches_missing_data

# ✅ Nouveau
from scripts.backfill.detection import find_matches_missing_data
from scripts.backfill.strategies import compute_performance_score_for_match
```

---

## 🔒 Règles Critiques Maintenues

1. **Pandas uniquement aux frontières** Plotly/Streamlit (10 fichiers documentés)
2. **SQLite interdit** (DuckDB v4 uniquement)
3. **DuckDBRepository obligatoire** pour l'accès aux données
4. **Environnement `.venv`** officiel (Python 3.12.10)
5. **Conventions N806** respectées (variables locales en snake_case)

---

## 📁 Structure Finale

```
data/
├── players/{gamertag}/
│   ├── stats.duckdb      # DB joueur
│   └── archive/          # Backups Parquet
├── warehouse/
│   └── metadata.duckdb   # Référentiels
└── cache/                # Cache médias/profils

scripts/
├── sync.py               # Synchronisation SPNKr
├── backfill_data.py      # Point d'entrée backfill
├── backfill/             # Modules backfill
│   ├── detection.py
│   ├── strategies.py
│   └── orchestrator.py
└── backup_player.py      # Export Parquet

src/
├── data/repositories/    # DuckDB + Factory
├── analysis/             # Modules analyse (Polars)
├── ui/pages/             # Pages Streamlit
└── visualization/        # Graphiques Plotly
```

---

## 🚀 Prochaines Étapes

- Amélioration de la couverture de tests (objectif 80%+)
- Migration Polars des reliquats legacy (win_loss_service, performance_score rétro-compat)
- Optimisation long terme si volumes > 5000 matchs
- Support natif Polars dans Streamlit (quand disponible upstream)

---

## 🙏 Remerciements

Cette release représente plusieurs semaines de travail intensif sur la qualité du code, l'architecture et les nouvelles fonctionnalités. Merci à tous les contributeurs et testeurs.

---

**LevelUp v4.5** — *Analyse de statistiques Halo Infinite*
