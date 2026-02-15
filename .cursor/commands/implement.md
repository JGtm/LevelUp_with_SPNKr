# Commande /implement

Implémente une fonctionnalité de manière structurée avec validation à chaque étape.

## Usage
`/implement [description de la feature ou référence au plan]`

## Prérequis
- Un plan existe dans `.ai/plans/` ou `.ai/current_plan.md`
- Ou une description claire de ce qu'il faut implémenter

## Étapes

### 1. Vérification du contexte
```
□ Lire .ai/project_map.md (architecture)
□ Lire .ai/current_plan.md ou le plan référencé
□ Identifier les fichiers à modifier
```

### 2. Préparation
```
□ Créer une branche si nécessaire (git checkout -b feature/xxx)
□ Vérifier que les tests existants passent (pytest tests/ -x -q)
□ Identifier les dépendances à ajouter
```

### 3. Implémentation (par ordre de dépendance)
```
□ Modèles de données (src/data/domain/models/)
□ Infrastructure (src/data/infrastructure/)
□ Repositories (src/data/repositories/)
□ Services/Logic (src/analysis/, src/services/)
□ UI si applicable (streamlit_app.py, src/app/)
```

### 4. Validation à chaque fichier modifié
```
□ Linter: ruff check [fichier]
□ Import OK: python -c "from [module] import *"
□ Tests unitaires du module si existants
```

### 5. Finalisation
```
□ Mettre à jour .ai/thought_log.md avec la décision
□ Proposer /test pour valider l'implémentation
```

## Checklist de sortie

- [ ] Code implémenté et fonctionnel
- [ ] Pas d'erreurs de linting
- [ ] Imports validés
- [ ] Documentation .ai/ mise à jour
- [ ] Prêt pour /test
