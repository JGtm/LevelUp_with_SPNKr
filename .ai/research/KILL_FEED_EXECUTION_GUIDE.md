# Guide d'Exécution - Investigation Kill Feed

> **Date**: 2026-02-03
> **Prérequis**: Environnement Python avec dépendances installées

---

## Prérequis

### 1. Installation des dépendances

```bash
# Depuis la racine du projet
pip install -r requirements.txt
# ou
pip install duckdb polars pydantic streamlit spnkr aiohttp
```

### 2. Configuration des tokens API

Créer un fichier `.env.local` ou `.env` à la racine avec :

```bash
SPNKR_SPARTAN_TOKEN=votre_token_spartan
SPNKR_CLEARENCE_TOKEN=votre_token_clearance
```

Ou utiliser OAuth Azure :

```bash
SPNKR_AZURE_CLIENT_ID=votre_client_id
SPNKR_AZURE_CLIENT_SECRET=votre_client_secret
SPNKR_OAUTH_REFRESH_TOKEN=votre_refresh_token
```

---

## Scripts Disponibles

### 1. Script d'investigation complet

```bash
# Investigation complète (toutes les phases)
python scripts/investigate_killfeed_weapons.py \
    --match-id <MATCH_ID> \
    --phase all \
    --output .ai/research/results.json

# Phase spécifique
python scripts/investigate_killfeed_weapons.py \
    --match-id <MATCH_ID> \
    --phase 1  # Assets Discovery UGC
```

### 2. Script simplifié (si problèmes d'imports)

```bash
python scripts/investigate_killfeed_simple.py \
    --match-id <MATCH_ID> \
    --phase all \
    --output .ai/research/results.json
```

### 3. Script d'exploration initial

```bash
# Exploration assets uniquement
python scripts/explore_killfeed_weapons.py --explore-assets

# Analyse d'un match
python scripts/explore_killfeed_weapons.py --match-id <MATCH_ID>
```

### 4. Obtenir un match ID

```bash
# Lister les derniers matchs d'un joueur
python scripts/get_match_id.py --gamertag <GAMERTAG> --limit 10

# Obtenir seulement le premier match ID
python scripts/get_match_id.py --gamertag <GAMERTAG> --first-only
```

---

## Exemple d'Exécution Complète

### Étape 1 : Obtenir un match ID

```bash
python scripts/get_match_id.py --gamertag JGtm --limit 5
```

Sortie attendue :
```
Match ID                                  Date                 Map                      Playlist                 K/D
--------------------------------------------------------------------------------------------------------------------
7f1bbf06-d54d-4434-ad80-923fcabe8b1b     2026-01-15 10:30:00  Bazaar                   Quick Play               6/3
```

### Étape 2 : Exécuter l'investigation

```bash
python scripts/investigate_killfeed_weapons.py \
    --match-id 7f1bbf06-d54d-4434-ad80-923fcabe8b1b \
    --phase all \
    --output .ai/research/investigation_results.json
```

### Étape 3 : Analyser les résultats

```bash
# Visualiser le JSON
cat .ai/research/investigation_results.json | python -m json.tool
```

---

## Phases d'Investigation

### Phase 1 : Exploration Assets Discovery UGC

**Objectif** : Explorer les types d'assets disponibles dans Discovery UGC pour trouver des assets liés aux armes.

**Commandes** :
```bash
python scripts/investigate_killfeed_weapons.py --phase 1
```

**Résultats attendus** :
- Liste des types d'assets connus
- Méthodes SPNKr disponibles
- Types hypothétiques à tester

---

### Phase 2 : Analyse Kill Feed Visuel

**Objectif** : Analyser la structure des highlight events pour identifier des champs liés aux armes/icônes.

**Commandes** :
```bash
python scripts/investigate_killfeed_weapons.py \
    --match-id <MATCH_ID> \
    --phase 2
```

**Résultats attendus** :
- Structure complète des events kill
- Champs potentiellement liés aux armes/icônes
- Analyse du raw_json

---

### Phase 3 : Extraction Film Chunks

**Objectif** : Extraire et analyser les extra bytes des film chunks pour identifier les weapon IDs.

**Commandes** :
```bash
# Utiliser les scripts existants
python scripts/extract_events_v3.py --match-id <MATCH_ID> --output events.json
python scripts/analyze_chunks_bitshifted.py --match-id <MATCH_ID>
```

**Résultats attendus** :
- Weapon IDs extraits depuis les chunks type 3
- Patterns dans les extra bytes
- Corrélation avec les weapon IDs connus

---

### Phase 4 : Exploration API Non Documentée

**Objectif** : Inspecter les réponses API complètes pour trouver des champs cachés.

**Commandes** :
```bash
python scripts/investigate_killfeed_weapons.py \
    --match-id <MATCH_ID> \
    --phase 4
```

**Résultats attendus** :
- Structure complète des stats JSON
- Champs suspects contenant "weapon", "icon", "killfeed"
- Endpoints hypothétiques identifiés

---

### Phase 5 : Theatre Mode

**Objectif** : Explorer le Theatre Mode pour extraire les données du kill feed.

**Commandes** :
```bash
python scripts/investigate_killfeed_weapons.py \
    --match-id <MATCH_ID> \
    --phase 5

# Télécharger les chunks
python scripts/refetch_film_roster.py --match-id <MATCH_ID>
```

**Résultats attendus** :
- Méthodes SPNKr film disponibles
- Structure des chunks type 1 (bootstrap)
- Données kill feed potentielles

---

## Dépannage

### Erreur : "No module named 'pandas'"

**Solution** :
```bash
pip install pandas
```

### Erreur : "Impossible d'importer SPNKrAPIClient"

**Solution** :
```bash
# Vérifier que tous les modules sont installés
pip install -r requirements.txt

# Vérifier les imports
python -c "from src.data.sync.api_client import SPNKrAPIClient; print('OK')"
```

### Erreur : "Tokens manquants"

**Solution** :
1. Vérifier que `.env.local` ou `.env` existe
2. Vérifier que les tokens sont valides
3. Tester avec :
```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('SPARTAN:', bool(os.getenv('SPNKR_SPARTAN_TOKEN')))"
```

### Erreur : "Base de données non trouvée"

**Solution** :
```bash
# Vérifier que la base existe
ls -la data/players/<GAMERTAG>/stats.duckdb

# Si elle n'existe pas, synchroniser d'abord
python scripts/sync.py --gamertag <GAMERTAG>
```

---

## Résultats Attendus

### Structure des résultats JSON

```json
{
  "phase1": {
    "known_types": ["Maps", "Playlists", ...],
    "hypothetical_types": ["Weapons", "WeaponIcons", ...],
    "methods_found": ["get_map", "get_playlist", ...],
    "errors": []
  },
  "phase2": {
    "match_id": "...",
    "events_found": 150,
    "kills_found": 25,
    "weapon_fields": [],
    "icon_fields": [],
    "sample_kill": {...},
    "errors": []
  },
  ...
}
```

---

## Prochaines Étapes Après Exécution

1. **Analyser les résultats JSON** pour identifier des patterns
2. **Tester les types Discovery UGC hypothétiques** avec des asset IDs valides
3. **Extraire plus de weapon IDs** depuis plusieurs matchs
4. **Corréler visuellement** avec des screenshots du kill feed
5. **Documenter les découvertes** dans `.ai/research/KILL_FEED_INVESTIGATION_STATUS.md`

---

**Dernière mise à jour** : 2026-02-03
