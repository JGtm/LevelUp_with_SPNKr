# Commande /test

Génère et exécute des tests pour valider une implémentation.

## Usage
`/test [module ou feature à tester]`

## Modes

### Mode 1: Tests existants
```bash
# Tous les tests
pytest tests/ -v

# Tests d'un module spécifique
pytest tests/test_[module].py -v

# Tests rapides (sans slow/integration)
pytest tests/ -x -q -m "not slow and not integration"
```

### Mode 2: Génération de nouveaux tests
Si les tests n'existent pas, les créer dans `tests/test_[module].py`

## Étapes

### 1. Analyse du code à tester
```
□ Identifier les fonctions/classes publiques
□ Identifier les cas limites (edge cases)
□ Identifier les dépendances à mocker
```

### 2. Structure du fichier de test
```python
"""Tests pour [module]."""
import pytest
from unittest.mock import Mock, patch

# Fixtures
@pytest.fixture
def sample_data():
    """Données de test."""
    return {...}

# Tests unitaires
class TestClassName:
    def test_nominal_case(self):
        """Test du cas nominal."""
        ...
    
    def test_edge_case(self):
        """Test des cas limites."""
        ...
    
    def test_error_handling(self):
        """Test de la gestion d'erreurs."""
        ...

# Tests d'intégration (marqués slow)
@pytest.mark.slow
def test_integration():
    ...
```

### 3. Exécution et validation
```bash
# Exécuter les nouveaux tests
pytest tests/test_[module].py -v --tb=short

# Vérifier la couverture
pytest tests/test_[module].py --cov=src/[module] --cov-report=term-missing
```

### 4. Critères de succès
```
□ Tous les tests passent
□ Couverture > 80% sur les fonctions critiques
□ Cas nominaux couverts
□ Cas d'erreur couverts
```

## Patterns de test courants

### Mock API externe
```python
@patch('src.api.client.fetch')
def test_with_mocked_api(mock_fetch):
    mock_fetch.return_value = {"data": "test"}
    result = my_function()
    assert result == expected
```

### Test avec base de données
```python
@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    # Setup
    yield db_path
    # Teardown automatique
```

### Test Pydantic
```python
def test_model_validation():
    with pytest.raises(ValidationError):
        MyModel(invalid_field="bad")
```

## Sortie attendue

- [ ] Tests créés/exécutés
- [ ] Résultats documentés
- [ ] Bugs identifiés listés pour /debug si nécessaire
