# Contribuer à LevelUp

Merci de votre intérêt pour contribuer à LevelUp ! Ce document explique comment participer au projet.

## Table des Matières

- [Code de Conduite](#code-de-conduite)
- [Comment Contribuer](#comment-contribuer)
- [Configuration de l'Environnement](#configuration-de-lenvironnement)
- [Standards de Code](#standards-de-code)
- [Processus de Pull Request](#processus-de-pull-request)
- [Signaler un Bug](#signaler-un-bug)
- [Proposer une Fonctionnalité](#proposer-une-fonctionnalité)

---

## Code de Conduite

Ce projet suit un code de conduite respectueux et inclusif. Soyez bienveillant envers les autres contributeurs.

---

## Comment Contribuer

### 1. Fork le Projet

```bash
# Fork via GitHub puis cloner
git clone https://github.com/votre-username/levelup-halo.git
cd levelup-halo
```

### 2. Créer une Branche

```bash
git checkout -b feature/ma-fonctionnalite
# ou
git checkout -b fix/mon-bug
```

### 3. Développer

Faites vos modifications en suivant les standards de code.

### 4. Tester

```bash
pytest
```

### 5. Committer

```bash
git add .
git commit -m "feat(scope): description"
```

### 6. Push et Pull Request

```bash
git push origin feature/ma-fonctionnalite
```

Créez une Pull Request sur GitHub.

---

## Configuration de l'Environnement

### Prérequis

- Python 3.10+
- Git

### Installation

```bash
# Créer l'environnement virtuel
python -m venv .venv

# Activer (Windows)
.venv\Scripts\activate

# Activer (Linux/macOS)
source .venv/bin/activate

# Installer les dépendances de développement
pip install -e ".[dev]"
```

### Outils de Développement

Les outils suivants sont inclus dans `[dev]` :

| Outil | Usage |
|-------|-------|
| `pytest` | Tests unitaires |
| `black` | Formatage du code |
| `isort` | Tri des imports |
| `ruff` | Linting |
| `mypy` | Type checking |

---

## Standards de Code

### Formatage

Avant chaque commit :

```bash
# Formatage
black .
isort .

# Linting
ruff check --fix .
```

### Type Hints

Toutes les fonctions publiques doivent avoir des type hints :

```python
def compute_kd_ratio(kills: int, deaths: int) -> float:
    """Calcule le ratio kills/deaths."""
    if deaths == 0:
        return float(kills)
    return kills / deaths
```

### Docstrings

Utilisez des docstrings en français :

```python
def load_matches(self, limit: int = 100) -> pl.DataFrame:
    """
    Charge les matchs depuis la base de données.
    
    Args:
        limit: Nombre maximum de matchs à charger.
        
    Returns:
        DataFrame Polars avec les statistiques des matchs.
    """
```

### Accès aux Données

**TOUJOURS** utiliser `DuckDBRepository` :

```python
from src.data.repositories import DuckDBRepository

repo = DuckDBRepository(db_path, xuid)
matches = repo.load_matches()
```

---

## Processus de Pull Request

### Checklist

Avant de soumettre une PR, vérifiez :

- [ ] Les tests passent (`pytest`)
- [ ] Le code est formaté (`black`, `isort`)
- [ ] Pas d'erreurs de linting (`ruff check`)
- [ ] Les nouveaux tests couvrent les changements
- [ ] La documentation est mise à jour si nécessaire
- [ ] Le message de commit suit le format Conventional Commits

### Format du Commit

```
<type>(<scope>): <description>

[body optionnel]
```

Types :
- `feat` : Nouvelle fonctionnalité
- `fix` : Correction de bug
- `docs` : Documentation
- `refactor` : Refactoring
- `test` : Ajout de tests
- `chore` : Maintenance

Exemples :
```
feat(ui): ajouter graphe radar des performances
fix(sync): corriger parsing des modes Firefight
docs: mettre à jour guide d'installation
```

### Review

Un mainteneur reviendra vers vous pour :
- Questions de clarification
- Suggestions d'amélioration
- Validation et merge

---

## Signaler un Bug

### Avant de Signaler

1. Vérifiez que le bug n'est pas déjà signalé
2. Testez avec la dernière version

### Créer une Issue

Incluez :
- **Description** : Comportement observé vs attendu
- **Reproduction** : Étapes pour reproduire
- **Environnement** : OS, Python version
- **Logs** : Messages d'erreur complets

```markdown
## Bug

### Description
Le dashboard ne charge pas les matchs pour le joueur X.

### Reproduction
1. Ouvrir le dashboard
2. Sélectionner le joueur X
3. Observer l'erreur

### Environnement
- OS: Windows 11
- Python: 3.11.4
- Version: 3.0.0

### Logs
```
Error: DuckDB file not found...
```
```

---

## Proposer une Fonctionnalité

### Avant de Proposer

1. Vérifiez que la feature n'est pas déjà proposée ou en cours
2. Réfléchissez à l'implémentation

### Créer une Issue

Incluez :
- **Description** : Qu'est-ce que la feature fait ?
- **Motivation** : Pourquoi est-ce utile ?
- **Implémentation** : Comment l'implémenter (optionnel)

```markdown
## Feature Request

### Description
Ajouter un export CSV des statistiques.

### Motivation
Permettre aux utilisateurs d'analyser leurs stats dans Excel.

### Implémentation suggérée
- Ajouter un bouton "Exporter CSV" dans la page Historique
- Utiliser Polars pour la conversion
```

---

## Questions ?

Si vous avez des questions, ouvrez une issue avec le tag `question`.

---

**Merci de contribuer à LevelUp !**
