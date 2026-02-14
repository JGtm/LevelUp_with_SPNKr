# LevelUp - Dashboard Halo Infinite

> **Analysez vos performances Halo Infinite avec des visualisations avancées et une architecture DuckDB ultra-rapide.**

[![Version](https://img.shields.io/badge/Version-4.5.0-green.svg)](https://github.com/JGtm/LevelUp_with_SPNKr/releases/tag/v4.5)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B.svg)](https://streamlit.io/)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.4%2B-FEE14E.svg)](https://duckdb.org/)
[![Polars](https://img.shields.io/badge/Polars-1.38%2B-blue.svg)](https://pola.rs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Nouveautés v4.5

- **Migration Polars complète** — Remplacement de Pandas par Polars dans le runtime principal (gains de 5-28% selon les parcours)
- **Architecture DuckDB unifiée** — Zéro dépendance SQLite, zéro module legacy `src.db`
- **Score de Performance** — Algorithme composite multi-métriques pour évaluer chaque match
- **Analyse d'impact coéquipiers** — Heatmap et classement des synergies
- **Sessions de jeu avancées** — Détection automatique, comparaison inter-sessions
- **Participation objective** — Analyse des objectifs de mode (CTF, Oddball, Strongholds)
- **Backfill incrémental avec bitmask** — Reprise sélective des données manquantes
- **1328 tests unitaires** — Suite verte, 0 failure

---

## Fonctionnalités

### Statistiques Avancées
- **Dashboard interactif** - Visualisez vos stats en temps réel
- **Graphiques détaillés** - Évolution K/D, précision, durée de vie, séries de frags
- **Analyse par carte** - Performance détaillée sur chaque map avec heatmaps
- **Coéquipiers** - Statistiques avec vos amis (même équipe ou adversaires)
- **Sessions de jeu** - Détection automatique avec métriques de performance

### Visualisations
- **Graphes radar** - Stats par minute et performance globale
- **Heatmaps** - Win rate par jour/heure de la semaine
- **Distributions** - Histogrammes précision, kills, scores
- **Corrélations** - Scatter plots durée de vie vs kills
- **Top armes** - Statistiques par arme avec headshot rate

### Architecture v4.5 - DuckDB + Polars
- **Performance** — Requêtes DuckDB < 30ms (warm), DataFrame Polars natifs
- **Vues matérialisées** — Agrégations instantanées (carte, mode, global)
- **Lazy loading** — Chargement à la demande par page
- **Zéro legacy** — Plus de SQLite, plus de `src.db`, Pandas uniquement aux frontières Plotly/Streamlit
- **Backup Parquet** — Export/restore avec compression Zstd

---

## Installation Rapide

**Prérequis** : Python 3.12+ recommandé (3.10 minimum). Note Windows : évitez Python 3.14 si vous constatez des crashes natifs pendant `pytest`.

```bash
# Cloner le projet
git clone https://github.com/JGtm/LevelUp_with_SPNKr.git
cd LevelUp_with_SPNKr

# Créer l'environnement virtuel
python -m venv .venv

# Activer (Windows)
.venv\Scripts\activate

# Activer (Linux/macOS)
source .venv/bin/activate

# Installer les dépendances
pip install -e .
```

**Documentation détaillée** : [docs/INSTALL.md](docs/INSTALL.md)

---

## Configuration

### 1. Copier le fichier d'environnement

```bash
cp .env.example .env.local
```

### 2. Configurer les tokens Azure

```env
SPNKR_AZURE_CLIENT_ID=votre_client_id
SPNKR_AZURE_CLIENT_SECRET=votre_secret
SPNKR_AZURE_REDIRECT_URI=https://localhost
SPNKR_OAUTH_REFRESH_TOKEN=votre_refresh_token
```

### 3. Récupérer le refresh token

```bash
python scripts/spnkr_get_refresh_token.py
```

**Documentation détaillée** : [docs/CONFIGURATION.md](docs/CONFIGURATION.md)

---

## Utilisation

### Lancer le Dashboard

```bash
# Mode interactif
python openspartan_launcher.py

# Lancer directement
python openspartan_launcher.py run

# Avec synchronisation
python openspartan_launcher.py run+refresh --player MonGamertag --delta
```

### Synchronisation des Données

```bash
# Sync incrémentale (nouveaux matchs uniquement)
python scripts/sync.py --delta --gamertag MonGamertag

# Sync complète
python scripts/sync.py --full --gamertag MonGamertag --max-matches 500
```

### Backup et Restore

```bash
# Backup d'un joueur
python scripts/backup_player.py --gamertag MonGamertag

# Restauration
python scripts/restore_player.py --gamertag MonGamertag --backup ./backups/MonGamertag
```

---

## Architecture

### Structure des Données (v4)

```
data/
├── players/                    # Données par joueur
│   └── {gamertag}/
│       ├── stats.duckdb       # Base DuckDB persistée
│       └── archive/           # Archives Parquet temporelles
├── warehouse/
│   └── metadata.duckdb        # Référentiels partagés
└── backups/                   # Backups Parquet
```

### Tables DuckDB

| Table | Description |
|-------|-------------|
| `match_stats` | Statistiques des matchs |
| `medals_earned` | Médailles par match |
| `teammates_aggregate` | Stats coéquipiers agrégées |
| `antagonists` | Top killers/victimes (rivalités) |
| `highlight_events` | Événements marquants |
| `career_progression` | Progression de rang |
| `mv_map_stats` | Vue matérialisée par carte |
| `mv_mode_category_stats` | Vue matérialisée par mode |
| `mv_global_stats` | Statistiques globales |

**Documentation technique** : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Documentation

| Document | Contenu |
|----------|---------|
| [INSTALL.md](docs/INSTALL.md) | Guide d'installation détaillé |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | Configuration des tokens et profils |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture technique |
| [DATA_ARCHITECTURE.md](docs/DATA_ARCHITECTURE.md) | Architecture des données |
| [SQL_SCHEMA.md](docs/SQL_SCHEMA.md) | Schémas DuckDB complets |
| [SYNC_GUIDE.md](docs/SYNC_GUIDE.md) | Guide de synchronisation |
| [BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md) | Backup et restauration |
| [FAQ.md](docs/FAQ.md) | Questions fréquentes |

---

## Tests

```bash
# Suite complète (inclut les tests smoke pages/filtres/visualisations)
python -m pytest

# Suite stable hors intégration (recommandé au quotidien)
python -m pytest -q --ignore=tests/integration

# Avec couverture
python -m pytest --cov=src --cov-report=html

# Tests spécifiques
python -m pytest tests/test_duckdb_repository.py -v

# E2E navigateur réel (optionnel, Playwright)
# Désactivé par défaut ; activation explicite avec --run-e2e-browser
python -m pytest tests/e2e/test_streamlit_browser_e2e.py -v --run-e2e-browser
```

---

## Docker

```bash
# Construire et démarrer
docker compose up --build

# En arrière-plan
docker compose up -d

# Arrêter
docker compose down
```

Le dashboard est accessible sur `http://localhost:8501`.

L'image installe toutes les dépendances via `pyproject.toml` (y compris SPNKr pour la synchronisation API). Au runtime, `docker-compose.yml` monte :
- `./data` → `/app/data` — données DuckDB v4 (lecture/écriture)
- `./db_profiles.json` → `/app/db_profiles.json` — profils joueurs
- `./app_settings.json` → `/app/app_settings.json` — paramètres

Pour forcer une base précise, décommentez dans `docker-compose.yml` :

```yaml
environment:
  - OPENSPARTAN_DB=/app/data/players/MonGamertag/stats.duckdb
```

**Documentation Docker détaillée** : [docs/INSTALL.md](docs/INSTALL.md#installation-docker)

---

## Remerciements

- **Andy Curtis** ([acurtis166](https://github.com/acurtis166)) pour [SPNKr](https://github.com/acurtis166/SPNKr)
- **Den Delimarsky** ([dend](https://github.com/dend)) pour [Grunt](https://github.com/dend/grunt) et [OpenSpartan](https://github.com/OpenSpartan)

Voir aussi [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md).

---

## Contribution

Les contributions sont les bienvenues ! Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour les guidelines.

```bash
# Format du code
ruff check --fix .
black .
isort .

# Avant de commiter
pytest
```

---

## Stack Technique

| Technologie | Usage |
|-------------|-------|
| **Python 3.12+** | Langage principal |
| **Streamlit** | Interface utilisateur |
| **DuckDB 1.4** | Moteur de requêtes OLAP |
| **Polars 1.38** | DataFrames haute performance |
| **PyArrow 23** | Passerelle données |
| **Pydantic v2** | Validation des données |
| **Plotly** | Visualisations interactives |
| **SPNKr** | API Halo Infinite |

---

## Limitations connues

- **Pandas résiduel** : 10 fichiers conservent Pandas aux frontières Plotly/Streamlit (conversion obligatoire) et dans le module RAG (API LanceDB). Voir `.ai/reports/V4_5_PANDAS_FRONTIER_MAP.md`.
- **Couverture tests** : ~40% global. Les modules UI (pages, renderers) ont peu de tests unitaires (logique de rendu Streamlit).
- **API Halo** : Dépend de l'API Grunt/SPNKr — certains endpoints peuvent être instables ou limités en débit.

---

## Licence

Ce projet est sous licence MIT. Voir [LICENSE](LICENSE) pour plus de détails.

---

**Fait avec passion pour la communauté Halo**
