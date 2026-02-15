# Correction : Navigation vers la Page Match

**Date** : 2026-02-05  
**Problème** : `StreamlitAPIException: st.session_state.page cannot be modified after the widget with key page is instantiated`  
**Fichier** : `src/ui/pages/media_library.py`

---

## 🐛 Problème Identifié

**Erreur** :
```
streamlit.errors.StreamlitAPIException: `st.session_state.page` cannot be modified after the widget with key `page` is instantiated.
```

**Cause** :
- Le widget `st.segmented_control` avec la clé `"page"` est créé dans `render_page_selector()` (ligne 536 de `streamlit_app.py`)
- Après l'instanciation du widget, on ne peut plus modifier directement `st.session_state["page"]`
- Le code tentait de modifier `st.session_state["page"]` directement dans `_open_match_button()`

---

## ✅ Correction Appliquée

### Utilisation de `_pending_page` au lieu de modifier directement `page`

**Avant** :
```python
if st.button("Ouvrir le match", key=button_key, use_container_width=True):
    st.session_state["page"] = "Match"
    st.session_state["match_id_input"] = mid
    st.rerun()
```

**Après** :
```python
# Utiliser _pending_page au lieu de modifier directement "page"
# car le widget segmented_control avec key="page" est déjà instancié
# consume_pending_page() s'occupera de mettre à jour "page" au prochain rendu
if st.button("Ouvrir le match", key=button_key, use_container_width=True):
    st.session_state["_pending_page"] = "Match"
    st.session_state["_pending_match_id"] = mid
    st.rerun()
```

**Explication** :
- Le pattern utilisé dans le codebase est de mettre la page dans `_pending_page`
- Au prochain rendu, `consume_pending_page()` (ligne 534 de `streamlit_app.py`) lit `_pending_page` et met à jour `st.session_state["page"]` **AVANT** que `render_page_selector()` ne soit appelé
- De même, `consume_pending_match_id()` (ligne 535) lit `_pending_match_id` et met à jour `st.session_state["match_id_input"]`

---

## 🔍 Flux de Navigation

1. **Clic sur le bouton** → `_open_match_button()` est appelé
2. **Mise à jour du session_state** :
   - `st.session_state["_pending_page"] = "Match"`
   - `st.session_state["_pending_match_id"] = mid`
3. **Rerun** → `st.rerun()` déclenche un nouveau rendu
4. **Consommation des valeurs en attente** (dans `streamlit_app.py`, lignes 534-535) :
   - `consume_pending_page()` lit `_pending_page` et met à jour `st.session_state["page"]`
   - `consume_pending_match_id()` lit `_pending_match_id` et met à jour `st.session_state["match_id_input"]`
5. **Rendu du sélecteur de page** → `render_page_selector()` lit `st.session_state["page"]` et affiche "Match"
6. **Dispatch vers la page** → `dispatch_page()` route vers la page "Match" avec le `match_id_input` pré-rempli

---

## 📋 Points de Vérification

- [x] Utilisation de `_pending_page` au lieu de `page`
- [x] Utilisation de `_pending_match_id` au lieu de `match_id_input`
- [x] Le flux correspond au pattern utilisé ailleurs dans le codebase
- [x] Aucune erreur de linter

---

## 🧪 Test à Effectuer

1. Ouvrir la page "Bibliothèque médias"
2. Cliquer sur "Ouvrir le match" pour un média associé
3. **Vérifier** :
   - La page change vers "Match"
   - Le champ de recherche contient le `match_id`
   - Aucune erreur `StreamlitAPIException`

---

**Statut** : ✅ Corrigé
