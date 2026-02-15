# Guide d'Installation - LevelUp

> Guide complet pour installer et configurer LevelUp sur votre machine.

## Prérequis

### Système
- **Windows 10/11**, Linux ou macOS
- **Python 3.10+** (recommandé: 3.11 ou 3.12)
- **Git** pour cloner le repository

### Compte Azure
- Compte Azure AD pour l'authentification API Halo
- Application enregistrée dans Azure Portal

---

## Installation Standard

### 1. Cloner le Repository

```bash
git clone https://github.com/username/levelup-halo.git
cd levelup-halo
```

### 2. Créer l'Environnement Virtuel

**Windows (PowerShell)** :
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (CMD)** :
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Linux/macOS** :
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Installer les Dépendances

**Installation standard** :
```bash
pip install -e .
```

**Installation développeur** (avec outils de test/linting) :
```bash
pip install -e ".[dev]"
```

**Avec support SPNKr** (API Halo) :
```bash
pip install -e ".[spnkr]"
```

**Installation complète** :
```bash
pip install -e ".[dev,spnkr]"
```

### 4. Vérifier l'Installation

```bash
# Vérifier Python
python --version

# Vérifier Streamlit
streamlit --version

# Vérifier DuckDB
python -c "import duckdb; print(duckdb.__version__)"

# Vérifier Pytest (évite les soucis de PATH)
python -m pytest --version

# Healthcheck environnement (recommandé)
python scripts/check_env.py
```

---

## Tests

Pour lancer la suite de tests, privilégiez `python -m pytest` (ça utilise toujours le pytest installé dans *cet* environnement virtuel).

```bash
# Tous les tests
python -m pytest

# Un fichier spécifique
python -m pytest tests/test_duckdb_repository.py -v
```

---

## Configuration Initiale

### 1. Fichier d'Environnement

```bash
# Copier le template
cp .env.example .env.local
```

### 2. Configurer les Tokens

Voir [CONFIGURATION.md](CONFIGURATION.md) pour la configuration des tokens Azure.

### 3. Ajouter un Joueur

Éditer `db_profiles.json` :

```json
{
  "version": "2.1",
  "profiles": {
    "MonGamertag": {
      "xuid": "2533274XXXXXXXXX",
      "gamertag": "MonGamertag",
      "db_path": "data/players/MonGamertag/stats.duckdb"
    }
  }
}
```

### 4. Premier Lancement

```bash
# Lancer le dashboard
python launcher.py run

# Ou directement avec Streamlit
streamlit run streamlit_app.py
```

---

## Installation Docker

### Prérequis
- Docker Desktop installé
- Docker Compose v2 disponible (`docker compose version`)
- Fichier `db_profiles.json` à la racine du projet (créé automatiquement si absent)

### Prérequis : fichiers de configuration

Avant le premier `docker compose up`, assurez-vous que ces fichiers existent. Sinon, créez-les :

```bash
# Si db_profiles.json n'existe pas encore
echo '{"profiles": {}}' > db_profiles.json

# Si app_settings.json n'existe pas encore
echo '{}' > app_settings.json
```

> **Pourquoi ?** Docker bind-mount crée un *dossier* (pas un fichier) si la source n'existe pas, ce qui crasherait l'app.

### Lancer avec Docker Compose

```bash
# Construire et démarrer
docker compose up --build

# En arrière-plan
docker compose up -d

# Voir les logs
docker compose logs -f

# Arrêter
docker compose down
```

### Architecture de l'image

L'image Docker :
- Installe les dépendances via `pip install -e ".[spnkr]"` (pyproject.toml), incluant SPNKr + aiohttp pour la synchronisation API
- Embarque les données de référence minimales (traductions playlists, wiki commendations)
- Tourne en utilisateur non-root (`appuser`, UID 10001)
- Expose le healthcheck Streamlit sur `/_stcore/health`

### Configuration Docker

`docker-compose.yml` monte les volumes suivants :

| Volume hôte | Chemin conteneur | Description |
|-------------|-----------------|-------------|
| `./data` | `/app/data` | Données DuckDB v4 (lecture/écriture) |
| `./db_profiles.json` | `/app/db_profiles.json` | Profils joueurs |
| `./app_settings.json` | `/app/app_settings.json` | Paramètres applicatifs |

### Variables d'Environnement Docker

| Variable | Défaut | Description |
|----------|--------|-------------|
| `OPENSPARTAN_ROOT` | `/app` | Racine du projet (détection pyproject.toml) |
| `OPENSPARTAN_DB` | *(vide)* | Forcer un chemin DB (optionnel) |
| `OPENSPARTAN_DEFAULT_GAMERTAG` | *(vide)* | Gamertag par défaut pour mode headless |

Exemple pour forcer une base :

```yaml
environment:
  - OPENSPARTAN_DB=/app/data/players/MonGamertag/stats.duckdb
```

`OPENSPARTAN_DB` est optionnelle : si non définie, l'application utilise la sélection via profils/UI.

---

## Mise à Jour

### Mettre à Jour le Code

```bash
# Pull les dernières modifications
git pull origin main

# Réinstaller les dépendances
pip install -e .
```

### Migration de Base de Données

Si vous migrez depuis une ancienne version (SQLite → DuckDB) :

```bash
# Migrer les métadonnées
python scripts/migrate_metadata_to_duckdb.py

# Migrer un joueur
python scripts/migrate_player_to_duckdb.py --gamertag MonGamertag

# Migrer tous les joueurs
python scripts/migrate_player_to_duckdb.py --all
```

---

## Dépannage

### Erreur "Module not found"

```bash
# Réinstaller les dépendances
pip install -e .
```

### Erreur DuckDB

```bash
# Vérifier la version
python -c "import duckdb; print(duckdb.__version__)"

# Doit être >= 0.10.0
pip install --upgrade duckdb
```

### Erreur Streamlit

```bash
# Vider le cache Streamlit
streamlit cache clear

# Relancer
streamlit run streamlit_app.py
```

### Permission Denied (Windows)

Exécuter PowerShell en tant qu'administrateur ou utiliser CMD :

```cmd
python -m streamlit run streamlit_app.py
```

---

## Structure des Dossiers Après Installation

```
levelup-halo/
├── .venv/                  # Environnement virtuel
├── data/
│   ├── players/            # Données par joueur
│   │   └── MonGamertag/
│   │       └── stats.duckdb
│   └── warehouse/
│       └── metadata.duckdb
├── .env.local              # Configuration locale
├── db_profiles.json        # Profils joueurs
└── ...
```

---

## Prochaines Étapes

1. [Configurer les tokens Azure](CONFIGURATION.md)
2. [Synchroniser vos matchs](SYNC_GUIDE.md)
3. [Explorer le dashboard](../README.md#utilisation)
