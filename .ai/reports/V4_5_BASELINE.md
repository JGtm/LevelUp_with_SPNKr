# Baseline v4.5 — LevelUp

> Date: 2026-02-12
> Branche: sprint13/v4.5-roadmap-hardening
> Objectif: établir la baseline factuelle avant exécution S14-S18.

## 1) Environnement

- OS: Windows
- Interpréteur: `.venv`
- Commande canonique: `python -m ...`
- Healthcheck: `python scripts/check_env.py` → TODO

## 2) Baseline tests

### Commandes

- `python -m pytest -q --ignore=tests/integration`
- `python -m pytest tests/integration -q` (si environnement OK)

### Résultats

- Unitaires/stables: TODO
- Intégration: TODO
- E2E navigateur: TODO

## 3) Baseline conformité architecture

### Commandes

- `grep -r "import pandas" src/ --include="*.py"`
- `grep -r "import sqlite3" src/ --include="*.py"`
- `grep -r "sqlite_master" src/ --include="*.py"`
- `grep -r "from src\.db|import src\.db" src/ --include="*.py"`

### Résultats

- Pandas: TODO
- SQLite (`import sqlite3`): TODO
- `sqlite_master`: TODO
- Références `src.db`: TODO

## 4) Baseline qualité code

### Commandes

- `ruff check src/ tests/`
- `ruff check src/ --select C901`

### Résultats

- Lint global: TODO
- Complexité hotspots: TODO

## 5) Baseline couverture

### Commande

- `python -m pytest tests/ -v --cov=src --cov-report=term-missing`

### Résultats

- Couverture globale: TODO
- Couverture modules critiques: TODO
  - `src/data/repositories/duckdb_repo.py`: TODO
  - `src/data/sync/engine.py`: TODO
  - `src/ui/pages/timeseries.py`: TODO
  - `src/ui/pages/teammates.py`: TODO
  - `src/ui/pages/win_loss.py`: TODO

## 6) Baseline performance

- Source actuelle: `.ai/reports/benchmark_v1.json`
- Parcours cibles v4.5: timeseries, teammates, carrière
- Mesures initiales (CPU/RAM/latence): TODO

## 7) Décisions verrouillées v4.5

- DuckDB-first validé
- Parquet optionnel (non bloquant)
- Tolérance Pandas transitoire: jusqu’à S17, levée cible en S18
- Cible couverture release: >= 75% global et >= 85% modules critiques

## 8) Go/No-Go S14

- [ ] Baseline tests complète
- [ ] Baseline conformité complète
- [ ] Baseline couverture complète
- [ ] Baseline performance initiale
- [ ] Feu vert exécution S14
