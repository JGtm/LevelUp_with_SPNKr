# Guide de Configuration - LevelUp

> Configuration complète des tokens Azure, profils joueurs et paramètres de l'application.

## Table des Matières

- [Configuration Azure](#configuration-azure)
- [Profils Joueurs](#profils-joueurs)
- [Variables d'Environnement](#variables-denvironnement)
- [Paramètres Application](#paramètres-application)

---

## Configuration Azure

### Prérequis

Pour utiliser l'API Halo Infinite via SPNKr, vous devez :

1. Avoir un compte Microsoft/Xbox
2. Créer une application dans Azure Portal
3. Obtenir un refresh token OAuth

### 1. Créer une Application Azure

1. Aller sur [Azure Portal](https://portal.azure.com/)
2. Naviguer vers **Azure Active Directory** → **App registrations**
3. Cliquer sur **New registration**
4. Configurer :
   - **Name** : `LevelUp Halo`
   - **Supported account types** : Personal Microsoft accounts only
   - **Redirect URI** : `https://localhost` (Web)
5. Cliquer sur **Register**

### 2. Configurer les Permissions

1. Dans votre application, aller à **API permissions**
2. Cliquer sur **Add a permission**
3. Sélectionner **Microsoft Graph** → **Delegated permissions**
4. Ajouter : `User.Read`, `offline_access`
5. Ajouter aussi les permissions Xbox Live (si disponibles)

### 3. Créer un Secret Client

1. Aller à **Certificates & secrets**
2. Cliquer sur **New client secret**
3. Donner un nom et choisir une expiration
4. **Copier immédiatement la valeur** (elle ne sera plus visible après)

### 4. Configurer le Fichier .env.local

```bash
# Copier le template
cp .env.example .env.local
```

Éditer `.env.local` :

```env
# Azure Application
SPNKR_AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
SPNKR_AZURE_CLIENT_SECRET=votre_secret_client
SPNKR_AZURE_REDIRECT_URI=https://localhost

# Token OAuth (à obtenir via le script)
SPNKR_OAUTH_REFRESH_TOKEN=
```

### 5. Obtenir le Refresh Token

```bash
python scripts/spnkr_get_refresh_token.py
```

Ce script :
1. Ouvre un navigateur pour l'authentification Microsoft
2. Récupère le code d'autorisation
3. Échange contre un refresh token
4. Affiche le token à copier dans `.env.local`

---

## Profils Joueurs

### Structure du Fichier db_profiles.json

```json
{
  "version": "2.1",
  "profiles": {
    "MonGamertag": {
      "xuid": "2533274823110022",
      "gamertag": "MonGamertag",
      "db_path": "data/players/MonGamertag/stats.duckdb",
      "is_default": true
    },
    "AutreJoueur": {
      "xuid": "2533274XXXXXXXXX",
      "gamertag": "AutreJoueur",
      "db_path": "data/players/AutreJoueur/stats.duckdb"
    }
  }
}
```

### Propriétés

| Propriété | Type | Description |
|-----------|------|-------------|
| `xuid` | string | Identifiant Xbox unique (16 chiffres) |
| `gamertag` | string | Nom du joueur |
| `db_path` | string | Chemin vers la base DuckDB |
| `is_default` | boolean | Joueur par défaut au lancement |

### Trouver son XUID

Plusieurs méthodes :

1. **Via le dashboard** : L'XUID s'affiche dans les paramètres
2. **Via l'API** : Lors de la première sync
3. **Via des sites tiers** : xboxgamertag.com, etc.

### Ajouter un Nouveau Joueur

```bash
# Créer le dossier
mkdir -p data/players/NouveauJoueur

# Ajouter au fichier db_profiles.json
# Puis synchroniser
python scripts/sync.py --gamertag NouveauJoueur --full
```

---

## Variables d'Environnement

### Fichiers de Configuration

| Fichier | Usage | Git |
|---------|-------|-----|
| `.env.example` | Template avec valeurs par défaut | Versionné |
| `.env.local` | Configuration locale (tokens) | Ignoré |
| `.env` | Alternative à .env.local | Ignoré |

### Variables Disponibles

#### Azure / SPNKr

| Variable | Description | Requis |
|----------|-------------|--------|
| `SPNKR_AZURE_CLIENT_ID` | ID de l'application Azure | Oui |
| `SPNKR_AZURE_CLIENT_SECRET` | Secret client Azure | Oui |
| `SPNKR_AZURE_REDIRECT_URI` | URI de redirection | Oui |
| `SPNKR_OAUTH_REFRESH_TOKEN` | Token de rafraîchissement | Oui |

#### Application

| Variable | Description | Défaut |
|----------|-------------|--------|
| `OPENSPARTAN_DB` | Chemin vers la DB par défaut | Auto |
| `OPENSPARTAN_DB_PATH` | Alias pour OPENSPARTAN_DB | Auto |
| `OPENSPARTAN_DB_READONLY` | Mode lecture seule | `0` |
| `SPNKR_PLAYER` | Joueur par défaut pour sync | Premier profil |

#### Debug

| Variable | Description | Défaut |
|----------|-------------|--------|
| `OPENSPARTAN_DEBUG` | Mode debug global | `0` |
| `OPENSPARTAN_DEBUG_ANTAGONISTS` | Debug calcul antagonistes | `0` |
| `STREAMLIT_DEBUG` | Debug Streamlit | `0` |

---

## Paramètres Application

### Fichier app_settings.json

```json
{
  "theme": "halo",
  "language": "fr",
  "default_player": "MonGamertag",
  "cache_ttl_seconds": 300,
  "max_matches_display": 100,
  "enable_debug_mode": false
}
```

### Paramètres Streamlit (.streamlit/config.toml)

```toml
[server]
port = 8501
headless = true

[theme]
primaryColor = "#00A2E8"
backgroundColor = "#0D1117"
secondaryBackgroundColor = "#161B22"
textColor = "#C9D1D9"
font = "sans serif"

[browser]
gatherUsageStats = false
```

---

## Sécurité

### Ne Jamais Versionner

Les fichiers suivants ne doivent **jamais** être committés :

- `.env.local`
- `.env`
- Tout fichier contenant des tokens
- `credentials.json`

Ils sont déjà dans `.gitignore`.

### Rotation des Tokens

Les refresh tokens Azure expirent après :
- 90 jours d'inactivité
- Ou selon la politique de l'organisation

Pour renouveler :

```bash
python scripts/spnkr_get_refresh_token.py
```

### Mode Production

En production (Docker, serveur) :

```env
OPENSPARTAN_DB_READONLY=1
```

Cela empêche les modifications accidentelles de la base.

---

## Dépannage

### Token Expiré

```
Error: invalid_grant
```

**Solution** : Régénérer le refresh token :
```bash
python scripts/spnkr_get_refresh_token.py
```

### Client ID Invalide

```
Error: unauthorized_client
```

**Solution** : Vérifier le Client ID dans Azure Portal.

### Permission Refusée

```
Error: access_denied
```

**Solution** : Vérifier les permissions API dans Azure Portal.

### Base de Données Non Trouvée

```
Error: Database file not found
```

**Solution** : Vérifier le chemin dans `db_profiles.json` et créer le dossier :
```bash
mkdir -p data/players/MonGamertag
```
