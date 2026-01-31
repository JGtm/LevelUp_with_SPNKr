# Workflows d'Orchestration

> Ce fichier définit les patterns de workflow pour les requêtes courantes.
> L'orchestrateur (`/orchestrate`) s'en inspire pour générer les plans.

## Workflow : Migration de Données

**Déclencheurs** : "migration", "migrer vers", "convertir en"

```yaml
phases:
  1_preparation:
    - Lire les schémas actuels
    - Créer les nouveaux schémas
    - Écrire les scripts de migration
    parallel: true
    
  2_migration:
    - Exécuter la migration (dry-run d'abord)
    - Valider les données migrées
    - Comparer ancien vs nouveau
    parallel: false
    
  3_verification:
    - Tests unitaires
    - Tests d'intégration
    - Test manuel (si UI concernée)
    parallel: true
    
  4_cleanup:
    - Supprimer les anciennes structures (optionnel)
    - Mettre à jour la documentation
    parallel: true
```

## Workflow : Nouvelle Fonctionnalité

**Déclencheurs** : "ajoute", "implémente", "crée"

```yaml
phases:
  1_design:
    - Analyser les requirements
    - Définir l'interface (I/O)
    - Créer les modèles Pydantic
    parallel: false
    
  2_implementation:
    - Écrire le code métier
    - Écrire les tests
    parallel: true
    
  3_integration:
    - Intégrer dans l'app existante
    - Tester l'intégration
    parallel: false
    
  4_validation:
    - Revue de code (/review)
    - Tests complets
    - Documentation
    parallel: true
```

## Workflow : Fix/Debug

**Déclencheurs** : "corrige", "fix", "bug", "erreur"

```yaml
phases:
  1_diagnostic:
    - Reproduire le bug
    - Identifier la cause racine
    - Localiser le code concerné
    parallel: false
    
  2_fix:
    - Écrire le test qui échoue
    - Corriger le code
    - Vérifier que le test passe
    parallel: false
    
  3_regression:
    - Lancer tous les tests
    - Vérifier pas de régression
    parallel: false
```

## Workflow : Refactoring

**Déclencheurs** : "refactor", "réorganise", "nettoie", "simplifie"

```yaml
phases:
  1_snapshot:
    - Lancer tous les tests (baseline)
    - Sauvegarder la couverture
    parallel: false
    
  2_refactor:
    - Appliquer les changements
    - Linter + formatter
    parallel: false
    
  3_validate:
    - Relancer tous les tests
    - Comparer la couverture
    - Vérifier pas de régression
    parallel: false
```

## Workflow : Vérification Complète

**Déclencheurs** : "vérifie", "teste", "valide", "assure-toi"

```yaml
phases:
  1_static:
    - Linter (ruff)
    - Type checking (mypy/pyright)
    - Sécurité (detect-secrets)
    parallel: true
    
  2_tests:
    - Tests unitaires
    - Tests d'intégration
    - Couverture
    parallel: false
    
  3_runtime:
    - Test app Streamlit
    - Test scripts CLI
    parallel: true
```

---

## Exemple : Requête Complexe

**Requête** : "Finalise la migration vers DuckDB/Parquet et vérifie que le refresh full et delta fonctionnent bien"

**Plan généré** :

```yaml
objective: "Migration DuckDB/Parquet + Validation refresh"

parallel_tasks:
  - id: P1
    name: "Vérifier schéma Parquet existant"
    files: ["src/data/infrastructure/parquet/writer.py"]
    test: "python -c 'from src.data.infrastructure.parquet import *'"
    
  - id: P2
    name: "Vérifier QueryEngine DuckDB"
    files: ["src/data/query/engine.py"]
    test: "pytest tests/test_query_module.py -v"

sequential_tasks:
  - id: S1
    name: "Implémenter refresh full"
    depends: [P1, P2]
    files: ["scripts/sync.py"]
    test: "python scripts/sync.py --mode full --dry-run"
    
  - id: S2
    name: "Implémenter refresh delta"
    depends: [S1]
    files: ["scripts/sync.py"]
    test: "python scripts/sync.py --mode delta --dry-run"
    
  - id: S3
    name: "Tester via app Streamlit"
    depends: [S2]
    test: "streamlit run streamlit_app.py (manuel)"
    
  - id: S4
    name: "Tester via CLI"
    depends: [S2]
    test: "python scripts/ingest_halo_data.py --action verify"

validation:
  - "pytest tests/ -v"
  - "python scripts/cleanup_codebase.py --fix"
  - "pre-commit run --all-files"
```

---

*Ce fichier est lu par `/orchestrate` pour générer des plans structurés.*
