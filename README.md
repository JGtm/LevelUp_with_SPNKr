# LevelUp - Dashboard Halo Infinite

> **Analysez vos performances Halo Infinite avec des visualisations avancées et une architecture DuckDB ultra-rapide.**

[![Version](https://img.shields.io/badge/Version-3.0.0-green.svg)](https://github.com/JGtm/LevelUp_with_SPNKr/releases/tag/v3.0.0)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B.svg)](https://streamlit.io/)
[![DuckDB](https://img.shields.io/badge/DuckDB-0.10%2B-FEE14E.svg)](https://duckdb.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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

### Architecture v4 - DuckDB Unifié
- **Performance** - Requêtes 10-20x plus rapides
- **Vues matérialisées** - Agrégations instantanées
- **Lazy loading** - Chargement à la demande
- **Backup Parquet** - Export/restore avec compression Zstd

---

## Installation Rapide

Note Windows: pour une installation stable de DuckDB/Polars/Numpy, utilisez de préférence Python 3.11 ou 3.12 (évitez Python 3.14 si vous constatez des crashes natifs pendant `pytest`).

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
# Démarrer avec Docker Compose
docker compose up --build

# Accéder au dashboard
open http://localhost:8501
```

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
| **Python 3.10+** | Langage principal |
| **Streamlit** | Interface utilisateur |
| **DuckDB** | Moteur de requêtes OLAP |
| **Polars** | DataFrames haute performance |
| **Pydantic v2** | Validation des données |
| **Plotly** | Visualisations interactives |
| **SPNKr** | API Halo Infinite |

---

## Licence

Ce projet est sous licence MIT. Voir [LICENSE](LICENSE) pour plus de détails.

---

**Fait avec passion pour la communauté Halo**
