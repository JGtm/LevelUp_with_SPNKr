# Test Agent - Agent de Test Intelligent

## Résumé
Agent de test automatisé qui détecte les fichiers modifiés, mappe les sources vers leurs tests, et exécute une suite de tests ciblée. Supporte le mode watch, la couverture, et l'intégration avec les hooks pre-commit.

## Inputs
- **Fichiers modifiés** : Détectés via `git diff`
- **Mapping source→test** : Configuration explicite + fallback par nom
- **Options** : `--quick`, `--full`, `--file`, `--watch`

## Outputs
- **Résultats** : Passés, échoués, ignorés, durée
- **Couverture** : Rapport HTML dans `htmlcov/`
- **Logs** : Sortie colorée avec résumé

## Dépendances
- **Packages** :
  - `pytest` : Framework de test
  - `pytest-cov` : Couverture de code
  - `watchdog` : Mode watch (optionnel)

## Méthodes d'Exécution

### 1. Script CLI
```bash
# Mode intelligent (fichiers modifiés → tests ciblés)
python scripts/smart_test.py

# Tests rapides (< 30s)
python scripts/smart_test.py --quick

# Suite complète avec couverture
python scripts/smart_test.py --full

# Tests pour un fichier spécifique
python scripts/smart_test.py --file src/analysis/stats.py

# Mode watch (relance sur changements)
python scripts/smart_test.py --watch
```

### 2. Commande Agentique (/test)
```
/test quick
/test full
/test src/data/query/engine.py
```

### 3. Pre-commit Hook (avant push)
```bash
# Installation
pre-commit install --hook-type pre-push

# À chaque push: tests rapides automatiques
```

### 4. CI/CD (GitHub Actions)
Voir `.github/workflows/tests.yml`

## Logique Métier

### Mapping Source → Test
```python
SOURCE_TO_TEST_MAP = {
    "src/analysis/": "tests/test_analysis.py",
    "src/data/query/": "tests/test_query_module.py",
    "src/data/domain/models/": "tests/test_models.py",
    "src/db/parsers": "tests/test_parsers.py",
    "src/app/": "tests/test_app_module.py",
    "src/ui/": "tests/test_app_module.py",
}

# Fallback: src/analysis/stats.py → tests/test_stats.py
```

### Flux de Décision
```
1. Détection des fichiers modifiés (git diff HEAD)
   ↓
2. Mapping vers tests correspondants
   ↓
3. Si tests trouvés → Exécution ciblée
   Sinon → Tests rapides (-m "not slow")
   ↓
4. Si succès → "Prêt pour commit/push"
   Si échec → Affichage détaillé des erreurs
```

### Marqueurs Pytest
```python
# tests/conftest.py ou dans les tests
@pytest.mark.slow         # Test lent (> 5s)
@pytest.mark.integration  # Test d'intégration (réseau, DB)

# Exécution sélective
pytest -m "not slow"           # Exclure les lents
pytest -m "not integration"    # Exclure les intégrations
```

## Points d'Attention
- **Debounce** : En mode watch, attend 2s entre les exécutions
- **Coverage** : Rapport HTML généré dans `htmlcov/`
- **Exit code** : 0 = succès, 1 = échec (pour CI/CD)
- **Mapping incomplet** : Ajouter les nouveaux modules dans `SOURCE_TO_TEST_MAP`

## Fichiers Clés
| Fichier | Rôle |
|---------|------|
| `scripts/smart_test.py` | Script principal |
| `tests/conftest.py` | Fixtures pytest |
| `pyproject.toml` | Configuration pytest |
| `.pre-commit-config.yaml` | Hook pre-push |
