# Cleanup Agent - Agent de Nettoyage Automatique

## Résumé
Système de nettoyage automatique du codebase. Supprime les fichiers temporaires, corrige les imports inutilisés, détecte les fichiers orphelins et le code mort. Peut être exécuté manuellement, via pre-commit hooks, ou programmé via cron/Task Scheduler.

## Inputs
- **Codebase** : Dossiers `src/`, `scripts/`, `tests/`
- **Configuration** : `pyproject.toml` (règles ruff)
- **Mode** : `--fix` (applique), `--deep` (analyse code mort)

## Outputs
- **Fichiers supprimés** : `__pycache__`, `.pyc`, `.coverage`, etc.
- **Code corrigé** : Imports inutilisés supprimés
- **Rapport** : `.ai/cleanup_report.md`

## Dépendances
- **Packages** :
  - `ruff` : Linting et correction imports (obligatoire)
  - `vulture` : Détection code mort (optionnel)
  - `pre-commit` : Hooks automatiques (optionnel)

## Méthodes d'Exécution

### 1. Manuel (CLI)
```bash
# Dry-run (affiche ce qui serait fait)
python scripts/cleanup_codebase.py

# Applique les corrections
python scripts/cleanup_codebase.py --fix

# Analyse approfondie avec détection code mort
python scripts/cleanup_codebase.py --fix --deep
```

### 2. Pre-commit Hooks (automatique à chaque commit)
```bash
# Installation (une seule fois)
pip install pre-commit
pre-commit install

# Exécution manuelle sur tous les fichiers
pre-commit run --all-files
```

### 3. Programmation (cron/Task Scheduler)
```bash
# Linux/Mac - crontab -e
0 3 * * * cd /path/to/project && python scripts/cleanup_codebase.py --fix

# Windows - PowerShell
schtasks /create /tn "CleanupCodebase" /tr "python scripts/cleanup_codebase.py --fix" /sc daily /st 03:00
```

### 4. Commande Agentique (/cleanup)
```
/cleanup mon projet. Supprime les fichiers temporaires et corrige les imports.
```

## Logique Métier

### Étapes de Nettoyage
```
1. Fichiers temporaires
   ├── __pycache__/
   ├── *.pyc, *.pyo, *.pyd
   ├── .pytest_cache/
   ├── .coverage
   ├── .mypy_cache/
   ├── .ruff_cache/
   ├── *.egg-info/
   └── tmp_*.sqlite, tmp_*.db

2. Imports inutilisés (ruff)
   └── Règle F401: unused-import

3. Fichiers orphelins
   ├── Scan tous les .py
   ├── Extrait les imports
   ├── Compare avec les fichiers existants
   └── Exclut: __init__.py, conftest.py, scripts CLI

4. Code mort (vulture, --deep)
   └── Fonctions/classes jamais appelées
```

### Fichiers Ignorés
```python
IGNORE_FILES = {
    "__init__.py",      # Exports de package
    "conftest.py",      # Fixtures pytest
    "streamlit_app.py", # Point d'entrée
}

IGNORE_DIRS = {
    ".git", ".venv", "venv",
    "node_modules", ".ai", ".cursor",
}
```

## Configuration Pre-commit

### Hooks Activés
| Hook | Rôle |
|------|------|
| `ruff` | Lint + fix imports |
| `ruff-format` | Formatage (remplace black) |
| `trailing-whitespace` | Espaces en fin de ligne |
| `end-of-file-fixer` | Newline en fin de fichier |
| `check-yaml/json` | Validation syntaxe |
| `debug-statements` | Détecte `print()`, `pdb` |
| `check-merge-conflict` | Conflits non résolus |

### Workflow CI
```yaml
# .pre-commit-config.yaml
ci:
  autofix_commit_msg: "style: auto-fix by pre-commit hooks"
  autofix_prs: true
  autoupdate_schedule: monthly
```

## Points d'Attention
- **Sécurité** : Ne supprime JAMAIS de fichier `.py` automatiquement
- **Dry-run par défaut** : Toujours afficher avant d'appliquer
- **Rapport** : Généré dans `.ai/cleanup_report.md` pour traçabilité
- **Exclusions** : Respecter les patterns de `.gitignore`

## Fichiers Clés
| Fichier | Rôle |
|---------|------|
| `scripts/cleanup_codebase.py` | Script principal |
| `.pre-commit-config.yaml` | Configuration hooks |
| `pyproject.toml` | Règles ruff et config |
| `.ai/cleanup_report.md` | Rapport généré |
