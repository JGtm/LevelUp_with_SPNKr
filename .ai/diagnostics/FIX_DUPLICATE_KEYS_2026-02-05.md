# Correction : Clés Streamlit Dupliquées - Bouton "Ouvrir le match"

**Date** : 2026-02-05  
**Problème** : `StreamlitDuplicateElementKey` pour le bouton "Ouvrir le match"  
**Fichier** : `src/ui/pages/media_library.py`

---

## 🐛 Problème Identifié

**Erreur** :
```
streamlit.errors.StreamlitDuplicateElementKey: There are multiple elements with the same `key='open_match_3b1de706-4875-4ba3-b710-81de195bfe45'`.
```

**Cause** :
- Le bouton "Ouvrir le match" était rendu **deux fois** :
  1. Une fois dans l'expander avant la grille (ligne 797)
  2. Une fois pour **chaque média** dans la grille (ligne 327)
- Quand plusieurs médias avaient le même `match_id`, plusieurs boutons avec la même clé étaient créés

---

## ✅ Corrections Appliquées

### 1. Ajout d'un paramètre `unique_suffix` à `_open_match_button()`

**Avant** :
```python
def _open_match_button(match_id: str) -> None:
    ...
    if st.button("Ouvrir le match", key=f"open_match_{mid}", use_container_width=True):
```

**Après** :
```python
def _open_match_button(match_id: str, *, unique_suffix: str | None = None) -> None:
    ...
    if unique_suffix:
        button_key = f"open_match_{mid}_{unique_suffix}"
    else:
        button_key = f"open_match_{mid}"
    if st.button("Ouvrir le match", key=button_key, use_container_width=True):
```

**Impact** : Les clés peuvent être rendues uniques même si plusieurs médias ont le même `match_id`.

---

### 2. Ne pas rendre le bouton dans la grille quand on est dans un groupe

**Avant** :
```python
st.caption(base)
if isinstance(mid, str) and mid.strip():
    _open_match_button(mid)
```

**Après** :
```python
st.caption(base)
# Ne pas afficher le bouton "Ouvrir le match" si on est dans un contexte de groupe
# (le bouton est déjà affiché avant la grille dans l'expander)
if isinstance(mid, str) and mid.strip() and not render_context.startswith("match_"):
    # Utiliser le stable_id pour rendre la clé unique même si plusieurs médias ont le même match_id
    stable_id = rec.get("_stable_id", 0)
    _open_match_button(mid, unique_suffix=str(stable_id))
elif isinstance(mid, str) and mid.strip():
    # Dans un groupe de match, le bouton est déjà affiché avant la grille
    pass
```

**Impact** : 
- Dans un contexte de groupe (`render_context.startswith("match_")`), le bouton n'est **pas** rendu dans la grille
- Le bouton est rendu **une seule fois** avant la grille dans l'expander
- En dehors d'un groupe, le bouton est rendu avec une clé unique basée sur `stable_id`

---

## 🧪 Tests Créés

### Fichier : `tests/test_media_library_keys.py`
### Fichier : `scripts/test_media_library_keys.py`

**Tests inclus** :
1. ✅ Unicité des clés de boutons avec `unique_suffix`
2. ✅ Détection des contextes de groupe
3. ✅ Plusieurs médias avec le même `match_id`
4. ✅ Génération des `stable_id`
5. ✅ Unicité des clés de thumbnails

---

## 📋 Scénarios de Test

### Scénario 1 : Groupe de match (group_by_match=True)
- **Comportement attendu** : Le bouton "Ouvrir le match" apparaît **une seule fois** avant la grille dans l'expander
- **Vérification** : Aucune erreur `StreamlitDuplicateElementKey`

### Scénario 2 : Pas de groupe (group_by_match=False)
- **Comportement attendu** : Le bouton "Ouvrir le match" apparaît pour chaque média avec une clé unique
- **Vérification** : Les clés incluent le `stable_id` pour être uniques même si plusieurs médias ont le même `match_id`

### Scénario 3 : Plusieurs médias avec le même match_id
- **Comportement attendu** : Chaque média a un bouton avec une clé unique
- **Vérification** : Les clés sont de la forme `open_match_{match_id}_{stable_id}`

---

## 🔍 Points de Vérification

- [x] Le bouton n'est pas rendu dans la grille quand `render_context.startswith("match_")`
- [x] Le bouton utilise `unique_suffix` quand rendu dans la grille
- [x] Les clés sont uniques même si plusieurs médias ont le même `match_id`
- [x] Les tests vérifient l'unicité des clés
- [x] Aucune erreur de linter

---

## 📝 Notes

**Leçon apprise** : 
- Toujours rendre les clés Streamlit uniques, même si plusieurs éléments ont les mêmes données
- Utiliser des identifiants stables (comme `stable_id`) pour garantir l'unicité
- Éviter de rendre le même élément plusieurs fois dans différents contextes

**Améliorations futures** :
- Créer une fonction utilitaire pour générer des clés uniques
- Ajouter des tests d'intégration pour vérifier le rendu réel dans Streamlit

---

**Statut** : ✅ Corrigé et testé
