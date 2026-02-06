# Mémorisation des Filtres par Joueur

> **Sprint 5** - Fonctionnalité de persistance des filtres pour améliorer l'UX.

## Vue d'ensemble

Le système de mémorisation des filtres permet de sauvegarder automatiquement les préférences de filtres pour chaque joueur, afin qu'elles soient restaurées lors des prochaines sessions ou changements de joueur.

## Fonctionnalités

- ✅ Sauvegarde automatique des filtres après chaque modification
- ✅ Chargement automatique au changement de joueur
- ✅ Chargement automatique au premier rendu de la page
- ✅ Support DuckDB v4 (gamertag) et Legacy (XUID)
- ✅ Format JSON lisible et modifiable manuellement

## Format de stockage

Les filtres sont stockés dans `.streamlit/filter_preferences/` sous la forme de fichiers JSON, un par joueur.

### Structure des fichiers

Chaque fichier JSON contient les préférences de filtres pour un joueur :

```json
{
  "filter_mode": "Période",
  "start_date": "2024-01-15",
  "end_date": "2024-01-20",
  "gap_minutes": 120,
  "picked_session_label": "Session 1",
  "playlists_selected": ["Partie rapide", "Arène classée"],
  "modes_selected": ["Assassin", "Fiesta"],
  "maps_selected": ["Carte 1", "Carte 2"]
}
```

### Champs disponibles

| Champ | Type | Description |
|-------|------|-------------|
| `filter_mode` | `string` | Mode de filtre : `"Période"` ou `"Sessions"` |
| `start_date` | `string` | Date de début (format ISO: `"YYYY-MM-DD"`) - Mode Période |
| `end_date` | `string` | Date de fin (format ISO: `"YYYY-MM-DD"`) - Mode Période |
| `gap_minutes` | `integer` | Écart max entre parties en minutes - Mode Sessions |
| `picked_session_label` | `string` | Label de la session sélectionnée - Mode Sessions |
| `playlists_selected` | `array<string>` | Liste des playlists sélectionnées (triée) |
| `modes_selected` | `array<string>` | Liste des modes sélectionnés (triée) |
| `maps_selected` | `array<string>` | Liste des cartes sélectionnées (triée) |

**Note** : Tous les champs sont optionnels. Seuls les champs définis sont sauvegardés.

### Nommage des fichiers

- **DuckDB v4** : `player_{gamertag}.json`
  - Exemple : `player_MyGamertag.json`
- **Legacy (XUID)** : `xuid_{xuid}.json`
  - Exemple : `xuid_123456789.json`

## Utilisation

### Pour les utilisateurs

Les filtres sont sauvegardés automatiquement. Aucune action n'est requise.

1. **Modification des filtres** : Les filtres sont sauvegardés automatiquement après chaque modification (changement de mode, sélection de dates, checkboxes, etc.)

2. **Changement de joueur** : Lors du changement de joueur, les filtres sauvegardés pour ce joueur sont automatiquement chargés et appliqués.

3. **Premier chargement** : Lors du premier chargement de la page pour un joueur, les filtres sauvegardés sont chargés s'ils existent.

### Pour les développeurs

#### Module `src/ui/filter_state.py`

Le module expose les fonctions suivantes :

##### `save_filter_preferences(xuid, db_path=None, preferences=None)`

Sauvegarde les préférences de filtres pour un joueur.

```python
from src.ui.filter_state import save_filter_preferences

# Sauvegarder depuis session_state (automatique)
save_filter_preferences("MyGamertag", db_path="data/players/MyGamertag/stats.duckdb")

# Sauvegarder des préférences spécifiques
from src.ui.filter_state import FilterPreferences
prefs = FilterPreferences(
    filter_mode="Période",
    start_date="2024-01-15",
    playlists_selected=["Partie rapide"]
)
save_filter_preferences("MyGamertag", db_path="...", preferences=prefs)
```

##### `load_filter_preferences(xuid, db_path=None)`

Charge les préférences de filtres pour un joueur.

```python
from src.ui.filter_state import load_filter_preferences

prefs = load_filter_preferences("MyGamertag", db_path="data/players/MyGamertag/stats.duckdb")
if prefs:
    print(f"Mode: {prefs.filter_mode}")
    print(f"Playlists: {prefs.playlists_selected}")
```

##### `apply_filter_preferences(xuid, db_path=None, preferences=None)`

Applique les préférences dans `st.session_state`.

```python
from src.ui.filter_state import apply_filter_preferences

# Charger et appliquer automatiquement
apply_filter_preferences("MyGamertag", db_path="...")

# Appliquer des préférences spécifiques
apply_filter_preferences("MyGamertag", preferences=prefs)
```

##### `clear_filter_preferences(xuid, db_path=None)`

Supprime les préférences sauvegardées pour un joueur.

```python
from src.ui.filter_state import clear_filter_preferences

clear_filter_preferences("MyGamertag", db_path="...")
```

#### Intégration dans le code

##### Chargement au changement de joueur

Dans `streamlit_app.py` :

```python
from src.ui.filter_state import apply_filter_preferences

# Au changement de joueur
if new_db_path or new_xuid:
    # ... mise à jour du joueur ...
    # Charger les filtres sauvegardés
    apply_filter_preferences(xuid, db_path)
    st.rerun()
```

##### Sauvegarde après modification

Dans `src/app/filters_render.py` :

```python
from src.ui.filter_state import save_filter_preferences

def render_filters_sidebar(...):
    # ... rendu des filtres ...
    
    # Sauvegarder après chaque rendu
    try:
        save_filter_preferences(xuid, db_path)
    except Exception:
        pass  # Ne pas bloquer si la sauvegarde échoue
    
    return FilterState(...)
```

##### Chargement au premier rendu

Dans `src/app/filters_render.py` :

```python
from src.ui.filter_state import apply_filter_preferences

def render_filters_sidebar(...):
    # Charger les filtres sauvegardés au premier rendu
    if "_filters_loaded" not in st.session_state:
        try:
            apply_filter_preferences(xuid, db_path)
            st.session_state["_filters_loaded"] = True
        except Exception:
            st.session_state["_filters_loaded"] = True
    
    # ... reste du rendu ...
```

## Gestion des erreurs

Le système est conçu pour ne jamais bloquer l'application :

- **Sauvegarde** : Si la sauvegarde échoue, un warning silencieux est émis mais l'application continue.
- **Chargement** : Si le chargement échoue (fichier corrompu, inexistant, etc.), les filtres par défaut sont utilisés.
- **Application** : Si l'application des préférences échoue (dates invalides, etc.), les valeurs invalides sont ignorées.

## Tests

Les tests sont disponibles dans `tests/test_filter_state.py` :

```bash
# Exécuter les tests
pytest tests/test_filter_state.py -v

# Avec couverture
pytest tests/test_filter_state.py --cov=src/ui/filter_state --cov-report=term-missing
```

### Couverture des tests

- ✅ Conversion FilterPreferences ↔ dict
- ✅ Sauvegarde et chargement
- ✅ Support DuckDB v4 et Legacy
- ✅ Gestion des erreurs (fichiers corrompus, inexistants)
- ✅ Application dans session_state
- ✅ Génération de clés de joueur

## Troubleshooting

### Les filtres ne sont pas sauvegardés

1. Vérifier que le répertoire `.streamlit/filter_preferences/` existe et est accessible en écriture.
2. Vérifier les logs de l'application pour des erreurs de sauvegarde.
3. Vérifier que `xuid` et `db_path` sont correctement passés à `save_filter_preferences()`.

### Les filtres ne sont pas chargés au changement de joueur

1. Vérifier que le fichier JSON existe dans `.streamlit/filter_preferences/`.
2. Vérifier que la clé de joueur est correcte (gamertag pour DuckDB v4, XUID pour Legacy).
3. Vérifier que le fichier JSON est valide (format correct).

### Les filtres chargés sont incorrects

1. Vérifier le contenu du fichier JSON dans `.streamlit/filter_preferences/`.
2. Supprimer le fichier pour réinitialiser les préférences.
3. Vérifier que les valeurs dans le JSON sont compatibles avec les options disponibles.

## Limitations

- Les filtres sont sauvegardés localement (pas de synchronisation entre machines).
- Les filtres ne sont pas validés contre les données disponibles (ex: une playlist supprimée reste dans les préférences).
- Les filtres sont sauvegardés après chaque rendu (peut être optimisé avec un système de détection de changement).

## Améliorations futures

- [ ] Validation des filtres contre les données disponibles
- [ ] Synchronisation entre machines (cloud storage)
- [ ] Interface de gestion des préférences (réinitialiser, exporter, importer)
- [ ] Optimisation de la sauvegarde (détection de changement)
- [ ] Support de préférences globales (non liées à un joueur)
