# Release Notes — LevelUp v4.1

> **Date** : 2026-02-12
> **Version** : 4.1.0 (`v4.1-clean`)

---

## 🎉 Vue d'ensemble

Cette version majeure finalise la migration de l'architecture LevelUp vers DuckDB v4 unifiée avec Polars comme moteur DataFrame. Elle apporte de nouvelles fonctionnalités statistiques, une refonte complète du code legacy, et améliore significativement la qualité du code.

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
- **1065+ tests passants** (hors intégration)
- **15 nouveaux tests d'intégration** pour les statistiques
- Tests de charge validés (1000-2000 matchs < 1s)
- Suppression complète du code legacy (`src/db/loaders.py`, repositories hybrides)

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

---

## 📊 Métriques

| Métrique | Avant | Après |
|----------|-------|-------|
| Tests passants | ~800 | 1065+ |
| Scripts actifs | 113 | 16 |
| Fichiers Pandas | 35 | 0 |
| Code legacy (loaders) | Actif | Supprimé |
| Tests d'intégration | 0 | 15 |

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

1. **Pandas interdit** dans le code métier (Polars uniquement)
2. **SQLite interdit** (DuckDB v4 uniquement)
3. **DuckDBRepository obligatoire** pour l'accès aux données
4. **Environnement `.venv`** officiel (Python 3.12.10)

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
- Optimisation des requêtes DuckDB pour gros volumes
- Nouvelles visualisations (tendances long terme)

---

## 🙏 Remerciements

Cette release représente plusieurs semaines de travail intensif sur la qualité du code, l'architecture et les nouvelles fonctionnalités. Merci à tous les contributeurs et testeurs.

---

**LevelUp v4.1** — *Analyse de statistiques Halo Infinite*
