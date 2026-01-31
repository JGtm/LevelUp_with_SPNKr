# Commande /debug

Investigation systématique d'un bug ou comportement inattendu.

## Usage
`/debug [description du problème]`
`/debug --error "message d'erreur"`
`/debug --test test_xxx` (test qui échoue)

## Méthodologie

### Phase 1: Reproduction
```
□ Comprendre le comportement attendu
□ Comprendre le comportement observé
□ Identifier les étapes pour reproduire
□ Isoler le cas minimal de reproduction
```

### Phase 2: Collecte d'indices
```
□ Message d'erreur exact (traceback complet)
□ Contexte d'exécution (CLI, Streamlit, test)
□ Données d'entrée qui causent le problème
□ Logs pertinents
```

### Phase 3: Hypothèses
Lister les causes possibles par ordre de probabilité :
1. Hypothèse A (la plus probable)
2. Hypothèse B
3. Hypothèse C

### Phase 4: Investigation
Pour chaque hypothèse :
```python
# Ajouter des logs temporaires
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug(f"Variable: {var}")

# Ou utiliser breakpoint()
breakpoint()  # Démarre pdb
```

### Phase 5: Correction
```
□ Identifier la cause racine
□ Implémenter le fix minimal
□ Vérifier que le bug est corrigé
□ Vérifier qu'aucune régression n'est introduite
```

## Outils de Debug

### Python Debug
```python
# Breakpoint interactif
breakpoint()

# Inspection de stack
import traceback
traceback.print_stack()

# Type checking runtime
print(type(var), repr(var))
```

### Tests de régression
```bash
# Exécuter le test qui échoue en mode verbose
pytest tests/test_xxx.py::test_function -v --tb=long

# Avec debugger
pytest tests/test_xxx.py::test_function --pdb
```

### Base de données
```python
# Inspecter la DB
import duckdb
conn = duckdb.connect(':memory:')
conn.execute("ATTACH 'data/warehouse/metadata.db' AS meta")
print(conn.execute("SELECT * FROM meta.sqlite_master").fetchall())
```

### Parquet
```python
# Inspecter les fichiers Parquet
import polars as pl
df = pl.scan_parquet("data/warehouse/match_facts/**/*.parquet")
print(df.schema)
print(df.head(5).collect())
```

## Template de Rapport de Bug

```markdown
## Bug Report - [date]

### Description
[Ce qui ne fonctionne pas]

### Reproduction
1. Étape 1
2. Étape 2
3. → Erreur

### Comportement attendu
[Ce qui devrait se passer]

### Comportement observé
[Ce qui se passe réellement]

### Traceback
```
[Coller le traceback complet]
```

### Cause racine
[Explication technique]

### Correction
[Fichier:ligne] - [Description du fix]

### Tests de régression
- [ ] Test ajouté: test_xxx
- [ ] Tests existants passent
```

## Checklist de sortie

- [ ] Bug reproduit et compris
- [ ] Cause racine identifiée
- [ ] Correction implémentée
- [ ] Tests de régression passent
- [ ] Documentation mise à jour si API changée
