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
python openspartan_launcher.py run

# Ou directement avec Streamlit
streamlit run streamlit_app.py
```

---

## Installation Docker

### Prérequis
- Docker Desktop installé
- Docker Compose disponible

### Lancer avec Docker Compose

```bash
# Construire et démarrer
docker compose up --build

# En arrière-plan
docker compose up -d

# Arrêter
docker compose down
```

### Configuration Docker

Le fichier `docker-compose.yml` monte les volumes suivants :
- `./data:/data:ro` : Données en lecture seule
- `./appdata:/appdata` : Configuration persistante

### Variables d'Environnement Docker

```yaml
environment:
  - OPENSPARTAN_DB=/data/players/MonGamertag/stats.duckdb
  - OPENSPARTAN_DB_READONLY=1
```

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
