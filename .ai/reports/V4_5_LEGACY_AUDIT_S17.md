# Audit legacy S17 — Entrée (vague B + perf)

> Date: 2026-02-12
> Périmètre: global `src/`
> Objectif: confirmer le reliquat legacy et préparer la clôture v4.5.

## 1) Reliquat Pandas global

### Commandes

- `grep -r "import pandas|to_pandas" src/ --include="*.py"`

### Résultats

- Fichiers `import pandas`: TODO
- Occurrences `to_pandas`: TODO
- Exceptions frontière documentées: TODO

## 2) Reliquat `src.db` / compat legacy

### Commandes

- `grep -r "from src\.db|import src\.db" src/ --include="*.py"`
- `grep -r "RepositoryMode|LEGACY|HYBRID|SHADOW" src/ --include="*.py"`

### Résultats

- Références runtime `src.db`: TODO
- Wrappers/compat à supprimer: TODO

## 3) Hotspots complexité / taille

### Commandes

- `ruff check src/ --select C901`
- Audit taille fonctions/fichiers: TODO script/commande

### Résultats

- Fichiers >800 lignes: TODO
- Fonctions >80 lignes: TODO
- Plan de découpage hotspots: TODO

## 4) Préparation optimisation Arrow/Polars

### Cibles

- Helper officiel DuckDB -> Arrow -> Polars
- Réduction conversions intermédiaires
- Mesure CPU/RAM sur 3 parcours: timeseries, teammates, carrière

### Baseline perf avant S17

- Mesures initiales: TODO
- Seuils cibles: TODO

## 5) Gate d’entrée S17

- [ ] Reliquat Pandas global confirmé
- [ ] Reliquat `src.db` confirmé
- [ ] Hotspots priorisés avec plan de découpage
- [ ] Baseline perf avant optimisation
