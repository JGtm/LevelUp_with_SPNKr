# Plan de Correction : Persistance des Filtres par Joueur/DB

## 🔍 Analyse du Problème

### Problème Identifié
La persistance des filtres est **partagée entre tous les joueurs/DB** au lieu d'être spécifique à chaque joueur/DB.

### Causes Racines

#### 1. **Flag `_filters_loaded` global et non-scopé par joueur**
**Fichier** : `src/app/filters_render.py` (lignes 77-83)

```python
# Charger les filtres sauvegardés au premier rendu (si pas déjà chargés)
if "_filters_loaded" not in st.session_state:
    try:
        apply_filter_preferences(xuid, db_path)
        st.session_state["_filters_loaded"] = True
    except Exception:
        st.session_state["_filters_loaded"] = True
```

**Problème** :
- Le flag `_filters_loaded` est un booléen global dans `session_state`
- Une fois mis à `True` pour un joueur, il reste `True` pour tous les autres joueurs
- Les filtres ne sont donc chargés qu'une seule fois au premier rendu, jamais lors des changements de joueur

**Impact** :
- Quand on change de joueur, les filtres de l'ancien joueur restent actifs
- Les filtres sauvegardés du nouveau joueur ne sont jamais chargés

#### 2. **Absence de sauvegarde automatique lors des modifications**
**Fichier** : Aucun appel à `save_filter_preferences()` dans le code applicatif

**Problème** :
- Les filtres sont chargés via `apply_filter_preferences()` mais jamais sauvegardés automatiquement
- Les modifications de filtres par l'utilisateur ne sont pas persistées
- Seul le chargement initial fonctionne (et encore, seulement une fois)

**Impact** :
- Les préférences de filtres ne sont jamais sauvegardées
- Chaque session repart avec des filtres par défaut

#### 3. **Changement de joueur : chargement mais pas de réinitialisation du flag**
**Fichier** : `streamlit_app.py` (lignes 403-420)

```python
if new_db_path or new_xuid:
    # Changement de joueur
    if new_db_path:
        st.session_state["db_path"] = new_db_path
        db_path = new_db_path
        # ...
    if new_xuid:
        st.session_state["xuid_input"] = new_xuid
        xuid = new_xuid
    # Charger les filtres sauvegardés pour le nouveau joueur
    apply_filter_preferences(xuid, db_path)
    st.rerun()
```

**Problème** :
- `apply_filter_preferences()` est appelé lors du changement de joueur
- MAIS le flag `_filters_loaded` n'est pas réinitialisé
- Donc dans `render_filters_sidebar()`, le bloc `if "_filters_loaded" not in st.session_state:` ne s'exécute jamais après le premier rendu

**Impact** :
- Les filtres du nouveau joueur ne sont pas appliqués car le flag bloque le chargement

## 📋 Plan de Correction Détaillé

### Phase 1 : Scoper le flag `_filters_loaded` par joueur/DB

#### 1.1 Modifier `render_filters_sidebar()` dans `src/app/filters_render.py`

**Objectif** : Remplacer le flag global `_filters_loaded` par un flag scopé par joueur/DB.

**Changements** :
```python
# AVANT (lignes 76-83)
if "_filters_loaded" not in st.session_state:
    try:
        apply_filter_preferences(xuid, db_path)
        st.session_state["_filters_loaded"] = True
    except Exception:
        st.session_state["_filters_loaded"] = True

# APRÈS
# Générer une clé unique pour ce joueur/DB
from src.ui.filter_state import _get_player_key
player_key = _get_player_key(xuid, db_path)
filters_loaded_key = f"_filters_loaded_{player_key}"

if filters_loaded_key not in st.session_state:
    try:
        apply_filter_preferences(xuid, db_path)
        st.session_state[filters_loaded_key] = True
    except Exception:
        st.session_state[filters_loaded_key] = True
```

**Alternative (plus propre)** : Utiliser une fonction helper pour générer la clé :
```python
def _get_filters_loaded_key(xuid: str, db_path: str) -> str:
    """Génère une clé unique pour le flag de chargement des filtres."""
    from src.ui.filter_state import _get_player_key
    player_key = _get_player_key(xuid, db_path)
    return f"_filters_loaded_{player_key}"
```

#### 1.2 Réinitialiser le flag lors du changement de joueur dans `streamlit_app.py`

**Objectif** : S'assurer que le flag est réinitialisé quand on change de joueur.

**Changements** (lignes 403-420) :
```python
if new_db_path or new_xuid:
    # Changement de joueur
    # Sauvegarder les filtres de l'ancien joueur avant de changer
    from src.ui.filter_state import save_filter_preferences
    save_filter_preferences(xuid, db_path)
    
    if new_db_path:
        st.session_state["db_path"] = new_db_path
        db_path = new_db_path
        gamertag = get_gamertag_from_duckdb_v4_path(new_db_path)
        if gamertag:
            st.session_state["xuid_input"] = gamertag
            st.session_state["waypoint_player"] = gamertag
            xuid = gamertag
    if new_xuid:
        st.session_state["xuid_input"] = new_xuid
        xuid = new_xuid
    
    # Réinitialiser le flag de chargement pour le nouveau joueur
    from src.ui.filter_state import _get_player_key
    from src.app.filters_render import _get_filters_loaded_key
    old_player_key = _get_player_key(xuid, db_path)  # Ancien xuid/db_path
    new_player_key = _get_player_key(xuid, db_path)  # Nouveau xuid/db_path
    old_filters_key = f"_filters_loaded_{old_player_key}"
    new_filters_key = f"_filters_loaded_{new_player_key}"
    
    # Supprimer le flag de l'ancien joueur si différent
    if old_filters_key != new_filters_key and old_filters_key in st.session_state:
        del st.session_state[old_filters_key]
    
    # Charger les filtres sauvegardés pour le nouveau joueur
    apply_filter_preferences(xuid, db_path)
    st.rerun()
```

**Note** : Cette approche est complexe car on doit gérer l'ancien et le nouveau joueur. Une approche plus simple serait de toujours vérifier si le joueur a changé.

### Phase 2 : Ajouter la sauvegarde automatique des filtres

#### 2.1 Créer un système de détection de changement de filtres

**Objectif** : Détecter quand les filtres changent pour les sauvegarder automatiquement.

**Approche 1 : Sauvegarde à chaque modification dans les composants de filtres**

**Fichiers à modifier** :
- `src/ui/components/checkbox_filter.py` : Ajouter un callback de sauvegarde
- `src/app/filters_render.py` : Ajouter la sauvegarde après chaque modification

**Problème** : Les composants Streamlit ne permettent pas facilement de détecter les changements.

**Approche 2 : Sauvegarde périodique basée sur un flag de "dirty state"**

**Fichier** : `src/app/filters_render.py`

**Changements** :
```python
def render_filters_sidebar(...):
    # ... code existant ...
    
    # À la fin de la fonction, après tous les rendus de filtres
    # Vérifier si les filtres ont changé depuis le dernier chargement
    current_prefs = FilterPreferences()
    # Remplir current_prefs depuis session_state (comme dans save_filter_preferences)
    
    # Comparer avec les préférences chargées (stocker dans session_state)
    loaded_prefs_key = f"_loaded_prefs_{player_key}"
    if loaded_prefs_key in st.session_state:
        loaded_prefs = st.session_state[loaded_prefs_key]
        if current_prefs.to_dict() != loaded_prefs.to_dict():
            # Les filtres ont changé, sauvegarder
            save_filter_preferences(xuid, db_path)
            st.session_state[loaded_prefs_key] = current_prefs.to_dict()
    else:
        # Première fois, stocker les préférences chargées
        st.session_state[loaded_prefs_key] = current_prefs.to_dict()
```

**Problème** : Complexe à maintenir, nécessite de comparer les états.

**Approche 3 : Sauvegarde sur événements spécifiques (RECOMMANDÉE)**

**Stratégie** : Sauvegarder les filtres :
1. Lors du changement de joueur (avant de changer)
2. Lors de la fermeture/navigation (via un callback)
3. Après un délai d'inactivité (debounce)

**Fichier** : `src/app/filters_render.py`

**Changements** :
```python
def render_filters_sidebar(...):
    # ... code existant ...
    
    # À la fin de la fonction
    # Sauvegarder les filtres si le joueur n'a pas changé depuis le dernier rendu
    from src.ui.filter_state import save_filter_preferences, _get_player_key
    player_key = _get_player_key(xuid, db_path)
    last_saved_key = f"_last_saved_player_{player_key}"
    
    # Vérifier si c'est le même joueur que lors de la dernière sauvegarde
    if last_saved_key not in st.session_state or st.session_state[last_saved_key] == player_key:
        # Sauvegarder les filtres actuels
        try:
            save_filter_preferences(xuid, db_path)
            st.session_state[last_saved_key] = player_key
        except Exception:
            pass  # Ne pas bloquer si la sauvegarde échoue
```

**Fichier** : `streamlit_app.py`

**Changements** (lignes 403-420) :
```python
if new_db_path or new_xuid:
    # Sauvegarder les filtres de l'ancien joueur AVANT de changer
    from src.ui.filter_state import save_filter_preferences
    try:
        save_filter_preferences(xuid, db_path)
    except Exception:
        pass  # Ne pas bloquer le changement de joueur
    
    # ... reste du code de changement de joueur ...
```

#### 2.2 Ajouter une sauvegarde explicite via un bouton (optionnel)

**Objectif** : Permettre à l'utilisateur de sauvegarder manuellement ses filtres.

**Fichier** : `src/app/filters_render.py` ou `src/ui/pages/settings.py`

**Ajout** : Un bouton "Sauvegarder les filtres" dans la sidebar ou dans les paramètres.

### Phase 3 : Améliorer la gestion du changement de joueur

#### 3.1 Nettoyer les filtres de session_state lors du changement de joueur

**Objectif** : S'assurer que les filtres de l'ancien joueur ne polluent pas le nouveau joueur.

**Fichier** : `streamlit_app.py`

**Changements** :
```python
if new_db_path or new_xuid:
    # Sauvegarder les filtres de l'ancien joueur
    from src.ui.filter_state import save_filter_preferences
    try:
        save_filter_preferences(xuid, db_path)
    except Exception:
        pass
    
    # Nettoyer les filtres de session_state pour forcer le rechargement
    filter_keys_to_clear = [
        "filter_mode",
        "start_date_cal",
        "end_date_cal",
        "gap_minutes",
        "picked_session_label",
        "picked_sessions",
        "filter_playlists",
        "filter_modes",
        "filter_maps",
    ]
    for key in filter_keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    # Réinitialiser le flag de chargement pour forcer le rechargement
    from src.ui.filter_state import _get_player_key
    old_player_key = _get_player_key(xuid, db_path)
    old_filters_loaded_key = f"_filters_loaded_{old_player_key}"
    if old_filters_loaded_key in st.session_state:
        del st.session_state[old_filters_loaded_key]
    
    # ... reste du code ...
```

#### 3.2 S'assurer que le nouveau joueur charge ses filtres

**Fichier** : `streamlit_app.py`

**Changements** :
```python
if new_db_path or new_xuid:
    # ... sauvegarde et nettoyage ...
    
    # Mettre à jour db_path et xuid
    if new_db_path:
        st.session_state["db_path"] = new_db_path
        db_path = new_db_path
        gamertag = get_gamertag_from_duckdb_v4_path(new_db_path)
        if gamertag:
            st.session_state["xuid_input"] = gamertag
            st.session_state["waypoint_player"] = gamertag
            xuid = gamertag
    if new_xuid:
        st.session_state["xuid_input"] = new_xuid
        xuid = new_xuid
    
    # Charger les filtres du nouveau joueur
    # Le flag _filters_loaded sera vérifié dans render_filters_sidebar()
    # et comme on l'a supprimé, les filtres seront rechargés
    apply_filter_preferences(xuid, db_path)
    st.rerun()
```

### Phase 4 : Tests et Validation

#### 4.1 Scénarios de test

1. **Test 1 : Changement de joueur avec filtres différents**
   - Joueur A : Sélectionner des filtres spécifiques
   - Changer vers Joueur B
   - Vérifier que les filtres de Joueur B sont chargés (pas ceux de A)
   - Modifier les filtres de Joueur B
   - Revenir à Joueur A
   - Vérifier que les filtres de Joueur A sont restaurés

2. **Test 2 : Persistance entre sessions**
   - Joueur A : Configurer des filtres
   - Redémarrer l'application
   - Vérifier que les filtres de Joueur A sont toujours là

3. **Test 3 : Plusieurs joueurs avec filtres différents**
   - Joueur A : Filtres X
   - Joueur B : Filtres Y
   - Joueur C : Filtres Z
   - Alterner entre les joueurs
   - Vérifier que chaque joueur garde ses propres filtres

4. **Test 4 : Sauvegarde automatique**
   - Modifier des filtres
   - Changer de joueur
   - Revenir au joueur précédent
   - Vérifier que les modifications sont sauvegardées

#### 4.2 Script de validation

**Fichier** : `scripts/validate_filter_persistence.py`

**Contenu** : Script pour tester manuellement la persistance des filtres.

## 📝 Résumé des Modifications

### Fichiers à Modifier

1. **`src/app/filters_render.py`**
   - Scoper le flag `_filters_loaded` par joueur/DB
   - Ajouter la sauvegarde automatique des filtres

2. **`streamlit_app.py`**
   - Sauvegarder les filtres avant changement de joueur
   - Nettoyer les filtres de session_state lors du changement
   - Réinitialiser le flag de chargement

3. **`src/ui/filter_state.py`** (optionnel)
   - Exposer `_get_player_key()` si nécessaire pour les autres modules

### Ordre d'Implémentation Recommandé

1. **Phase 1** : Scoper le flag `_filters_loaded` (corrige le problème principal)
2. **Phase 3** : Améliorer la gestion du changement de joueur (nettoyage)
3. **Phase 2** : Ajouter la sauvegarde automatique (améliore l'UX)
4. **Phase 4** : Tests et validation

## ⚠️ Points d'Attention

1. **Performance** : La sauvegarde automatique ne doit pas ralentir l'application
   - Utiliser un debounce si nécessaire
   - Sauvegarder de manière asynchrone si possible

2. **Compatibilité** : S'assurer que les anciens fichiers de filtres (sans scope) sont toujours compatibles
   - Migration automatique si nécessaire

3. **Gestion d'erreurs** : Les erreurs de sauvegarde ne doivent pas bloquer l'application
   - Utiliser des try/except appropriés

4. **Race conditions** : S'assurer qu'il n'y a pas de conditions de course lors du changement de joueur
   - Sauvegarder avant de changer
   - Nettoyer après avoir changé

## 🔗 Références

- Module de persistance : `src/ui/filter_state.py`
- Rendu des filtres : `src/app/filters_render.py`
- Gestion du changement de joueur : `streamlit_app.py` (lignes 398-420)
- Documentation : `docs/FILTER_PERSISTENCE.md`
