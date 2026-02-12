# Audit legacy S16 — Entrée (vague A UI/Viz)

> Date: 2026-02-12
> Périmètre: `src/ui/pages/`, `src/visualization/`
> Objectif: figer l’état legacy avant migration Pandas vague A.

## 1) Inventaire Pandas (périmètre S16)

### Commande

- `grep -r "import pandas|to_pandas" src/ui/pages src/visualization --include="*.py"`

### Résultats

- Fichiers avec `import pandas`: TODO
- Occurrences `to_pandas`: TODO
- Frontières explicitement autorisées: TODO

## 2) Vérification SQLite / sqlite_master

### Commande

- `grep -r "import sqlite3|sqlite_master" src/ --include="*.py"`

### Résultats

- `import sqlite3`: TODO
- `sqlite_master`: TODO

## 3) Hotspots clean code S16

### Commandes

- `python -m pytest --collect-only -q` (sanity tests)
- Audit statique (fonctions >80 lignes / fichiers >600 lignes): TODO script/commande

### Résultats

- Fonctions >80 lignes (top 20): TODO
- Fichiers >600 lignes (top 20): TODO
- Priorités de refactor S16: TODO

## 4) Risques de migration vague A

- Régression visuelle sur pages timeseries/win-loss/teammates
- Rupture contrats DataFrame entre page et visualisation
- Dégradation perf si conversions multiples

## 5) Plan d’exécution recommandé S16

1. Migrer visualisations (distributions/timeseries/maps/match_bars/trio)
2. Migrer pages UI (timeseries/win_loss/teammates/teammates_charts)
3. Centraliser frontière `to_pandas()`
4. Découper fonctions >120 lignes touchées
5. Valider via tests wave A

## 6) Gate d’entrée S16

- [ ] Inventaire Pandas validé
- [ ] Vérification SQLite/sqlite_master validée
- [ ] Hotspots priorisés
- [ ] Stratégie de refactor validée
