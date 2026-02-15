# LevelUp - Dashboard Halo Infinite

> **Analysez vos performances Halo Infinite avec des visualisations avancées et une architecture DuckDB v5 ultra-rapide.**

[![Version](https://img.shields.io/badge/Version-5.0.0-green.svg)](https://github.com/JGtm/LevelUp_with_SPNKr/releases/tag/v5.0.0)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B.svg)](https://streamlit.io/)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.4%2B-FEE14E.svg)](https://duckdb.org/)
[![Polars](https://img.shields.io/badge/Polars-1.38%2B-blue.svg)](https://pola.rs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Nouveautés v5.0

- **Architecture Shared Matches** — Base partagée `shared_matches.duckdb` centralisant les matchs de tous les joueurs (-69% stockage, -72% appels API, -73% temps de sync)
- **Sync Engine v5** — Détection des matchs partagés, sync allégée pour les matchs connus, parallélisation API
- **ATTACH multi-DB** — Lecture transparente depuis la base partagée via DuckDB ATTACH
- **Citations DuckDB-first** — Moteur SQL de calcul et agrégation des citations (14 règles, +6 objectives réintégrées)
- **Optimisations Sync** — Parallélisation `asyncio.gather`, batching DB, performance scores en batch post-sync
- **2768 tests unitaires** — Suite verte, 0 failure, modules métier couverts à 70%+

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

### Architecture v5.0 - DuckDB Shared Matches
- **Shared Matches** — Base partagée `shared_matches.duckdb` centralisant tous les matchs
- **ATTACH multi-DB** — DuckDB ATTACH pour lecture transparente cross-DB
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
python launcher.py

# Lancer directement
python launcher.py run

# Avec synchronisation
python launcher.py run+refresh --player MonGamertag --delta
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

### Structure des Données (v5)

```
data/
├── warehouse/
│   ├── metadata.duckdb            # Référentiels partagés
│   └── shared_matches.duckdb      # Base partagée (tous les matchs)
│       ├── match_registry         # Registre central (1 ligne/match)
│       ├── match_participants     # Tous les joueurs de tous les matchs
│       ├── highlight_events       # Tous les événements filmés
│       ├── medals_earned          # Médailles de tous les joueurs
│       └── xuid_aliases           # Mapping xuid→gamertag
├── players/                       # Données par joueur
│   └── {gamertag}/
│       ├── stats.duckdb           # Enrichissements personnels
│       │   ├── player_match_enrichment  # performance_score, session_id
│       │   ├── teammates_aggregate      # Stats coéquipiers (POV joueur)
│       │   ├── antagonists              # Rivalités (POV joueur)
│       │   └── match_citations          # Citations par match
│       └── archive/               # Archives Parquet temporelles
└── backups/                       # Backups Parquet
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
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture technique (v4 legacy) |
| [ARCHITECTURE_V5.md](docs/ARCHITECTURE_V5.md) | Architecture v5 (shared matches) |
| [DATA_ARCHITECTURE.md](docs/DATA_ARCHITECTURE.md) | Architecture des données |
| [SHARED_MATCHES_SCHEMA.md](docs/SHARED_MATCHES_SCHEMA.md) | Schéma shared_matches.duckdb |
| [SQL_SCHEMA.md](docs/SQL_SCHEMA.md) | Schémas DuckDB complets |
| [SYNC_GUIDE.md](docs/SYNC_GUIDE.md) | Guide de synchronisation |
| [SYNC_OPTIMIZATIONS_V5.md](docs/SYNC_OPTIMIZATIONS_V5.md) | Optimisations sync v5 |
| [MIGRATION_V4_TO_V5.md](docs/MIGRATION_V4_TO_V5.md) | Guide de migration v4→v5 |
| [CLEANUP_V5.md](docs/CLEANUP_V5.md) | Nettoyage post-migration v5 |
| [BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md) | Backup et restauration |
| [TESTING_V5.md](docs/TESTING_V5.md) | Stratégie de tests v5 |
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

- **Pandas résiduel** : ~10 fichiers conservent Pandas aux frontières Plotly/Streamlit (conversion obligatoire). Polars est le standard pour tout le code métier.
- **Couverture tests** : ~43% global — les modules UI Streamlit (pages, renderers) tirent la moyenne vers le bas. Les modules métier (sync, repositories, analysis) dépassent individuellement 70%.
- **API Halo** : Dépend de l'API Grunt/SPNKr — certains endpoints peuvent être instables ou limités en débit.

---

## Licence

Ce projet est sous licence MIT. Voir [LICENSE](LICENSE) pour plus de détails.

---

## Remerciements

- **Andy Curtis** ([acurtis166](https://github.com/acurtis166)) pour [SPNKr](https://github.com/acurtis166/SPNKr)
- **Den Delimarsky** ([dend](https://github.com/dend)) pour [Grunt](https://github.com/dend/grunt) et [OpenSpartan](https://github.com/OpenSpartan)

Voir aussi [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md).

---

**Fait avec passion pour la communauté Halo**
