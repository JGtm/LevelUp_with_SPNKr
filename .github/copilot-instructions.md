# Instructions pour GitHub Copilot & Assistants IA

Ce fichier définit les conventions et règles à suivre lors de modifications sur le projet LevelUp.

---

## Contexte du Projet

**LevelUp** est un dashboard Streamlit pour analyser les statistiques Halo Infinite.

- **Stack** : Python 3.10+, Streamlit, DuckDB, SPNKr (API Halo)
- **Langue UI** : Français (traductions dans `src/ui/translations.py`)
- **Architecture** : DuckDB unifié (v4)

---

## Environnement de référence (Windows)

Objectif : éviter les confusions d'interpréteur (PowerShell vs Git Bash/MSYS2) et les erreurs "module introuvable".

- **Python officiel** : `.venv` à la racine du repo (Python 3.12.10)
- **Interdit** : utiliser le Python MSYS2/MinGW (`pacman ... python/pip`) pour exécuter le projet
- **Règle d'or** : toujours lancer les outils via `python -m ...` (ne pas dépendre du `PATH`)

Packages critiques vérifiés dans `.venv` :
- `pytest==9.0.2`
- `duckdb==1.4.4`
- `polars==1.38.1`
- `pyarrow==23.0.0`
- `pandas==2.3.3`
- `numpy==2.4.2`

Healthcheck (à lancer avant de diagnostiquer un souci d'environnement) :
- `python scripts/check_env.py`

---

## Architecture des Données (v4)

| Données | Stockage | Chemin |
|---------|----------|--------|
| Référentiels | DuckDB | `data/warehouse/metadata.duckdb` |
| Matchs joueur | DuckDB | `data/players/{gamertag}/stats.duckdb` |
| Archives | Parquet | `data/players/{gamertag}/archive/` |
| Config | JSON | `db_profiles.json` |

### Tables Principales

| Table | Description |
|-------|-------------|
| `match_stats` | Statistiques des matchs |
| `medals_earned` | Médailles par match |
| `teammates_aggregate` | Stats coéquipiers |
| `antagonists` | Rivalités (killers/victimes) |
| `highlight_events` | Événements marquants |
| `mv_*` | Vues matérialisées |

---

## Workflow d'Interaction IA

### Avant toute modification

1. **Analyser la demande** : Reformuler pour confirmer la compréhension
2. **Explorer le contexte** : Lire les fichiers concernés
3. **Proposer un plan** : Lister les étapes avant d'implémenter
4. **Valider** : Attendre le "go" avant les modifications majeures

### Structure d'une réponse idéale

```markdown
## Compréhension de la demande
[Reformulation en 1-2 phrases]

## Analyse de l'existant
- Fichiers impactés : ...
- Dépendances : ...

## Plan d'implémentation
1. [ ] Étape 1
2. [ ] Étape 2

## Points de vigilance
- ...

Tu veux que je procède ?
```

---

## Conventions de Code

### Python

- **Type hints** obligatoires sur fonctions publiques
- **Docstrings** en français
- **Formatage** : Black + isort + ruff

```python
# Bon
def compute_kd_ratio(kills: int, deaths: int) -> float:
    """Calcule le ratio kills/deaths."""
    if deaths == 0:
        return float(kills)
    return kills / deaths
```

### Accès aux Données

**TOUJOURS** utiliser `DuckDBRepository` :

```python
from src.data.repositories import DuckDBRepository

repo = DuckDBRepository(db_path, xuid)
matches = repo.load_matches(limit=100)
```

**INTERDIT** : Utiliser `src/db/loaders.py` (déprécié)

### SQL / DuckDB

```python
# Bon - Paramètres
cursor.execute("SELECT * FROM match_stats WHERE match_id = ?", (match_id,))

# Mauvais - Injection SQL
cursor.execute(f"SELECT * FROM match_stats WHERE match_id = '{match_id}'")
```

---

## Synchronisation

### Mode Delta (incrémental)

```bash
python scripts/sync.py --delta --gamertag MonGamertag
```

### Mode Full (complet)

```bash
python scripts/sync.py --full --gamertag MonGamertag --max-matches 500
```

---

## Tests

```bash
# Tous les tests (recommandé)
python -m pytest

# Avec couverture
python -m pytest --cov=src

# Tests spécifiques
python -m pytest tests/test_duckdb_repository.py -v

# Suite stable hors intégration (Windows)
python -m pytest --ignore=tests/integration
```

---

## Commits

### Format Conventional Commits

```
<type>(<scope>): <description>
```

### Types autorisés

| Type | Description |
|------|-------------|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Correction de bug |
| `docs` | Documentation |
| `refactor` | Refactoring |
| `test` | Tests |
| `chore` | Maintenance |

### Exemples

```
feat(ui): ajouter graphe radar des stats par minute
fix(sync): corriger détection des modes Firefight
docs: mettre à jour README avec branding LevelUp
```

---

## À Éviter

1. **Ne pas** utiliser les loaders legacy (`src/db/loaders.py`)
2. **Ne pas** modifier les tables DB sans migration
3. **Ne pas** hardcoder des chemins Windows
4. **Ne pas** créer de dépendances sans les ajouter à `pyproject.toml`
5. **Ne pas** committer des tokens ou secrets

---

## Checklist avant PR

- [ ] Tests passent (`pytest`)
- [ ] Pas d'erreurs de type
- [ ] Traductions FR à jour si nouvelle UI
- [ ] Documentation mise à jour si nouvelle feature
- [ ] Commit message au format Conventional Commits

---

## Ressources

- [DuckDB Documentation](https://duckdb.org/docs/)
- [Streamlit Docs](https://docs.streamlit.io/)
- [SPNKr Documentation](https://github.com/acurtis166/SPNKr)
