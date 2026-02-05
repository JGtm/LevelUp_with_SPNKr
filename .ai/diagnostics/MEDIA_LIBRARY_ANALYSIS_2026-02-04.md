# Analyse Complète : Bibliothèque Médias - Problèmes UI et Association

**Date** : 2026-02-04  
**Auteur** : Analyse automatique  
**Contexte** : Problèmes d'affichage UI et d'association médias/matchs après modifications récentes  
**Méthode** : Analyse statique du code + observations utilisateur

---

## 📋 Résumé Exécutif

### État Actuel
- ✅ **Associations fonctionnelles** : Les médias sont correctement associés aux matchs dans la base de données
- ❌ **UI cassée** : Problèmes d'affichage et de clés Streamlit dupliquées
- ⚠️ **Architecture complexe** : Double logique d'association (BDD + fallback scan disque)
- ❌ **Régressions après corrections** : Thumbnails, largeur images, navigation

### Problèmes Critiques Identifiés

#### Problèmes Initiaux (Avant Corrections)
1. **Duplication de médias dans l'affichage** (CRITIQUE) - **CONFIRMÉ PAR UI**
2. **Clés Streamlit dupliquées** (CRITIQUE)
3. **Logique d'affichage conditionnelle complexe** (MAJEUR)
4. **Incohérence entre données BDD et affichage** (MAJEUR)
5. **Code mort et duplication** (MOYEN)

#### Nouvelles Régressions (Après Corrections)
6. **Plus de thumbnails affichés** (CRITIQUE)
7. **Images prennent toute la largeur** (MAJEUR)
8. **Bouton "Ouvrir le match" ne fonctionne pas** (MAJEUR)

### Observation UI Réelle

**Problème observé initialement** :
```
Match 3b1de706-4875-4ba3-b710-81de195bfe45 — Mer. 28 janvier 2026 17:46
├─ [Ouvrir le match]
├─ 🎬 Halo Infinite 2026-01-28 18-48-41.mp4  ← DUPLIQUÉ
│  └─ Cliquer pour afficher la miniature
├─ Halo Infinite 2026-01-28 18-48-41.mp4
├─ [Ouvrir le match]  ← DUPLIQUÉ
└─ 🎬 Halo Infinite 2026-01-28 18-48-41.mp4  ← DUPLIQUÉ
   └─ Cliquer pour afficher la miniature
```

**Cause identifiée** :
- Le même média apparaît **deux fois** dans le même groupe de match
- Le bouton "Ouvrir le match" est rendu **deux fois** (une fois par média dupliqué)
- Cela indique que le DataFrame `g` contient **plusieurs lignes pour le même média** avec le même `match_id`
- Probablement dû à plusieurs associations (`media_match_associations`) pour le même média/match mais avec différents `xuid`

---

## 🔍 Analyse Détaillée - Problèmes Initiaux

### 1. Problème : Clés Streamlit Dupliquées

**Localisation** : `src/ui/pages/media_library.py`, fonction `_render_media_grid()`

**Problème Initial** :
```python
# Ligne 286-288 (avant correction)
path_hash = hashlib.md5(path.encode()).hexdigest()
match_id_part = str(mid).strip() if isinstance(mid, str) and mid.strip() else "no_match"
thumb_key = f"thumb_show::{path_hash}::{match_id_part}"
```

**Cause** :
- Un même média peut apparaître dans **plusieurs groupes de matchs** (si associé à plusieurs joueurs)
- Le même média peut apparaître dans la section "non associés" ET dans un groupe de match
- La clé basée sur `path_hash + match_id` peut créer des collisions si :
  - Le même média apparaît plusieurs fois avec le même `match_id` (impossible normalement)
  - Mais surtout : **quand `match_id` est None**, tous les médias non associés ont la même clé `"no_match"`

**Impact** :
- `StreamlitDuplicateElementKey` : crash de l'application
- Impossible d'afficher plusieurs médias non associés dans la même page

**Correction Appliquée** :
```python
# Ligne 286-290 (après correction)
path_hash = hashlib.md5(path.encode()).hexdigest()
match_id_part = str(mid).strip() if isinstance(mid, str) and mid.strip() else "no_match"
unique_suffix = f"{render_context}::{i}::{col_idx}"
thumb_key = f"thumb_show::{path_hash}::{match_id_part}::{unique_suffix}"
```

**⚠️ NOUVEAU PROBLÈME** : La clé inclut maintenant `i` et `col_idx` qui changent à chaque rendu, causant la perte du `session_state` (voir section Régressions).

---

### 2. Problème : Logique d'Affichage Conditionnelle Complexe

**Localisation** : `src/ui/pages/media_library.py`, fonction `render_media_library_page()`

**Problèmes identifiés** :

#### 2.1 Double Logique d'Association

```python
# Lignes 685-704
if media_df.empty:
    # Fallback : scan disque
    media_df = _index_all_media(settings)
    windows_df = _compute_match_windows(df_full, settings)
    assoc_df = _associate_media_to_matches(media_df, windows_df)
else:
    # Chargement depuis BDD
    assoc_df = media_df.copy()
    windows_df = _load_match_windows_from_db(db_path)
```

**Problème** :
- Deux chemins différents pour charger les médias
- Deux fonctions différentes pour calculer les fenêtres temporelles (`_compute_match_windows` vs `_load_match_windows_from_db`)
- Risque d'incohérence entre les deux approches

#### 2.2 Messages de Diagnostic Confus

```python
# Lignes 733-753
if not using_db:
    st.info("Les médias sont chargés depuis le scan disque...")
elif windows_df.empty and assigned.empty:
    st.warning("Aucune fenêtre temporelle...")
elif assigned.empty and not unassigned.empty and using_db:
    st.warning("Aucun média n'a pu être associé...")
```

**Problème** :
- Conditions imbriquées difficiles à suivre
- Messages qui peuvent être contradictoires
- `windows_df` calculé pour le diagnostic mais pas toujours utilisé

#### 2.3 Code Mort

```python
# Lignes 764-769 (AVANT correction)
if not group_by_match:
    _render_media_grid(assoc_df, cols_per_row=int(cols_per_row))
    return
    st.subheader(f"Médias non associés ({len(unassigned)})")  # ← JAMAIS EXÉCUTÉ
    _render_media_grid(unassigned, cols_per_row=int(cols_per_row))  # ← JAMAIS EXÉCUTÉ
    return
```

**Correction Appliquée** : Code mort supprimé (lignes 767-769).

---

### 3. Problème : Incohérence Données BDD vs Affichage

**Localisation** : `src/ui/pages/media_library.py`, fonction `_load_media_from_db()`

**Problème** :

```python
# Lignes 487-508
if xuid or gamertag:
    uid_filter = "(mma.xuid = ? OR mma.xuid = ?)"
    result = conn.execute(
        f"""
        SELECT DISTINCT
            mf.file_path AS path,
            ...
            mma.match_id,
            mma.xuid
        FROM media_files mf
        LEFT JOIN media_match_associations mma
            ON mf.file_path = mma.media_path
            AND ({uid_filter})
        ...
        """,
        params,
    ).fetchall()
```

**Problème** :
- `LEFT JOIN` avec filtre sur `mma.xuid` peut créer des lignes avec `match_id = NULL` même si le média a des associations pour d'autres joueurs
- Un média peut avoir plusieurs associations (un par joueur), mais `SELECT DISTINCT` peut masquer cela
- Si un média est associé à plusieurs matchs pour le même joueur, seule une association est retournée

**Impact** :
- Médias non affichés alors qu'ils ont des associations
- Associations manquantes dans l'UI

---

### 4. Problème : Association Multi-Joueurs Non Gérée dans l'UI (CONFIRMÉ)

**Localisation** : `src/data/media_indexer.py`, fonction `associate_with_matches()` + `src/ui/pages/media_library.py`, ligne 789

**Comportement Backend** :
```python
# Ligne 624
for match_id, start_time, _distance in best_matches:
    conn_write.execute(
        """
        INSERT INTO media_match_associations (
            media_path, match_id, xuid, match_start_time, association_confidence
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (media_path, match_id, xuid) DO NOTHING
        """,
        [media_path, match_id, player_xuid, start_time, 1.0],
    )
```

**Problème Identifié** :
- Un média peut être associé à **plusieurs matchs** (si plusieurs matchs sont dans la fenêtre temporelle)
- Un média peut être associé au **même match pour plusieurs joueurs** (si plusieurs joueurs ont le même match)
- **CONFIRMÉ** : La requête SQL `_load_media_from_db()` retourne **plusieurs lignes** pour le même média si plusieurs `xuid` ont des associations
- **CONFIRMÉ** : Le code ligne 789 ne déduplique pas avant l'affichage (AVANT correction)

**Correction Appliquée** :
```python
# Ligne 730-737
assigned = assoc_df.loc[assoc_df["match_id"].notna()].copy()
unassigned = assoc_df.loc[assoc_df["match_id"].isna()].copy()

# DÉDUPLIQUER : Un média peut avoir plusieurs associations (multi-joueurs)
if not assigned.empty:
    assigned = assigned.drop_duplicates(subset=["path", "match_id"], keep="first")
if not unassigned.empty:
    unassigned = unassigned.drop_duplicates(subset=["path"], keep="first")
```

**Impact Observé** :
- ✅ **CONFIRMÉ** : Un média apparaît plusieurs fois dans le même groupe de match (AVANT correction)
- ✅ **CONFIRMÉ** : Le bouton "Ouvrir le match" est dupliqué (AVANT correction)
- ✅ **CONFIRMÉ** : Clés Streamlit dupliquées → crash (AVANT correction)

---

## 🚨 Analyse Détaillée - Nouvelles Régressions

### Problème 5 : Plus de Thumbnails Affichés (CRITIQUE)

**Localisation** : `src/ui/pages/media_library.py`, lignes 280-311

**Code Actuel (Après Corrections)** :
```python
thumb_path = str(rec.get("thumbnail_path") or "").strip()
path_hash = hashlib.md5(path.encode()).hexdigest()
match_id_part = str(mid).strip() if isinstance(mid, str) and mid.strip() else "no_match"
unique_suffix = f"{render_context}::{i}::{col_idx}"
thumb_key = f"thumb_show::{path_hash}::{match_id_part}::{unique_suffix}"
show_thumb = st.session_state.get(thumb_key, False)  # ← PAR DÉFAUT FALSE

if show_thumb and thumb_path and os.path.exists(thumb_path):
    # Afficher thumbnail
else:
    # Afficher placeholder
    if thumb_path and os.path.exists(thumb_path):
        if st.button("Afficher miniature", key=thumb_key + "::btn"):
            st.session_state[thumb_key] = True
            st.rerun()
```

**Problèmes Identifiés** :

1. **Clé de session_state change à chaque rendu** :
   - La clé inclut `i` (index de ligne) et `col_idx` (index de colonne)
   - Ces valeurs changent si l'ordre des médias change ou si le nombre de colonnes change
   - **Impact** : Le `session_state` est perdu à chaque changement, l'utilisateur doit re-cliquer

2. **Par défaut, aucun thumbnail n'est affiché** :
   - `show_thumb = False` par défaut
   - L'utilisateur doit cliquer sur "Afficher miniature" pour chaque média
   - **Impact** : Expérience utilisateur dégradée, pas de preview automatique

3. **Vérification `os.path.exists(thumb_path)` peut échouer** :
   - Si le chemin est relatif au lieu d'absolu
   - Si le fichier n'existe pas mais est référencé en BDD
   - **Impact** : Bouton "Afficher miniature" peut ne pas apparaître même si thumbnail_path existe

**Cause Racine Probable** :
- Les modifications récentes ont changé la logique pour charger les thumbnails "au clic" au lieu de "au survol"
- Mais la clé de session_state n'est pas stable, donc l'état est perdu
- **La correction des clés dupliquées a introduit une instabilité des clés**

---

### Problème 6 : Images Prennent Toute la Largeur (MAJEUR)

**Localisation** : `src/ui/pages/media_library.py`, lignes 253-327

**Code Actuel** :
```python
def _render_media_grid(items: pd.DataFrame, *, cols_per_row: int, render_context: str = "default") -> None:
    cols_per_row = int(cols_per_row)
    if cols_per_row < 2:
        cols_per_row = 2
    if cols_per_row > 8:
        cols_per_row = 8

    rows = items.to_dict(orient="records")
    for i in range(0, len(rows), cols_per_row):
        chunk = rows[i : i + cols_per_row]
        cols = st.columns(len(chunk))  # ← Crée len(chunk) colonnes
        for col_idx, (c, rec) in enumerate(zip(cols, chunk, strict=False)):
            with c:
                if kind == "image" and path:
                    st.image(path, width="stretch")  # ← Dans une colonne
```

**Analyse** :

1. **Le code semble correct** :
   - `st.columns(len(chunk))` crée le bon nombre de colonnes
   - `st.image(..., width="stretch")` dans une colonne devrait prendre la largeur de la colonne

2. **Problèmes Potentiels** :

   a) **Si `chunk` n'a qu'un seul élément** :
      - Si `len(rows) == 1`, alors `chunk = [row]` et `len(chunk) == 1`
      - `st.columns(1)` crée une seule colonne qui prend toute la largeur
      - **Impact** : Si un seul média par groupe, il prend toute la largeur

   b) **Si `cols_per_row` n'est pas utilisé correctement** :
      - Le slider définit `cols_per_row` (ligne 595)
      - Mais si `assigned` ou `unassigned` est vide après filtrage, `_render_media_grid` peut être appelé avec un DataFrame vide ou très petit
      - **Impact** : Moins de médias que `cols_per_row`, donc moins de colonnes créées

   c) **Si les images sont dans un expander** :
      - Ligne 787 : `with st.expander(label, expanded=False):`
      - Les colonnes dans un expander peuvent avoir un comportement différent
      - **Impact** : Les colonnes peuvent ne pas se répartir correctement

**Cause Racine Probable** :
- Les médias sont probablement groupés par match dans des expanders
- Chaque expander peut contenir peu de médias (1-2)
- Donc `len(chunk)` est petit, créant peu de colonnes
- L'utilisateur voit des images pleine largeur car il n'y a qu'une colonne par expander

**Vérification Nécessaire** :
- Combien de médias par groupe de match ?
- Le slider "Colonnes" est-il à 4 comme attendu ?
- Les médias sont-ils bien répartis dans les colonnes ?

---

### Problème 7 : Bouton "Ouvrir le match" Ne Fonctionne Pas (MAJEUR)

**Localisation** : `src/ui/pages/media_library.py`, lignes 44-69

**Code Actuel** :
```python
def _build_app_url(page: str, **params: str) -> str:
    qp: dict[str, str] = {"page": str(page)}
    for k, v in params.items():
        s = str(v or "").strip()
        if s:
            qp[str(k)] = s
    return "?" + urllib.parse.urlencode(qp)

def _open_match_button(match_id: str) -> None:
    mid = str(match_id or "").strip()
    if not mid:
        st.caption("Match inconnu")
        return

    url = _build_app_url("Match", match_id=mid)
    safe_url = html.escape(url, quote=True)
    st.markdown(
        f"""
        <a href="{safe_url}" target="_blank" rel="noopener noreferrer"
           style="display:block;text-align:center;padding:6px 10px;border-radius:10px;
                  border:1px solid rgba(255,255,255,0.18);text-decoration:none;"
        >Ouvrir le match</a>
        """,
        unsafe_allow_html=True,
    )
```

**Analyse du Routing** :

D'après `src/app/routing.py` et `src/app/page_router.py` :

1. **Le routing utilise `consume_query_params()`** :
   - Ligne 158-194 de `routing.py` : `consume_query_params()` lit les query params et les stocke en `session_state`
   - Les query params sont ensuite consommés et nettoyés de l'URL

2. **Le routing attend `page` et `match_id`** :
   - `consume_query_params()` retourne `(page, match_id)`
   - `page` doit être "Match" (ligne 139 de `page_router.py`)
   - `match_id` est stocké dans `st.session_state["_pending_match_id"]`

3. **Problème Potentiel** :
   - `_build_app_url("Match", match_id=mid)` génère `?page=Match&match_id=...`
   - Mais le lien utilise `target="_blank"` qui ouvre dans un nouvel onglet
   - **Dans un nouvel onglet, le `session_state` est différent !**
   - **Impact** : Les query params sont dans l'URL mais le `session_state` n'est pas partagé entre onglets

4. **Autre Problème** :
   - Le lien utilise `target="_blank"` mais Streamlit ne gère pas bien la navigation entre onglets
   - Le routing peut ne pas consommer les query params dans le nouvel onglet
   - **Impact** : La page ne change pas ou le match_id n'est pas utilisé

**Cause Racine Probable** :
- `target="_blank"` ouvre un nouvel onglet avec une nouvelle session Streamlit
- Le routing ne consomme pas les query params dans le nouvel onglet
- Ou le routing consomme les query params mais ne navigue pas vers la bonne page

**Solution Attendue** :
- Utiliser `st.query_params` au lieu de `target="_blank"`
- Ou utiliser le routing interne de Streamlit (`st.switch_page()` ou navigation via `session_state`)
- Ou utiliser `st.link_button()` si disponible dans la version de Streamlit

---

## 📊 Résumé des Causes Probables

| Problème | Cause Probable | Impact | Statut |
|----------|----------------|--------|--------|
| **Duplication médias** | Plusieurs associations (multi-xuid) pour même média/match | Doublons dans l'affichage | ✅ CORRIGÉ (déduplication) |
| **Clés Streamlit dupliquées** | Clé basée sur `path_hash + match_id` uniquement | Crash application | ⚠️ PARTIELLEMENT CORRIGÉ (mais instable) |
| **Plus de thumbnails** | Clé `session_state` instable (inclut `i` et `col_idx` qui changent) | Utilisateur doit re-cliquer à chaque rendu | ❌ RÉGRESSION |
| **Images pleine largeur** | Peu de médias par groupe → `len(chunk)` petit → peu de colonnes | Expérience utilisateur dégradée | ❌ NON RÉSOLU |
| **Bouton ne fonctionne pas** | `target="_blank"` + routing Streamlit ne gère pas bien les query params entre onglets | Navigation cassée | ❌ NON RÉSOLU |

---

## 🔧 Corrections Appliquées (2026-02-04)

### Correction 1 : Déduplication des Médias ✅

**Fichier** : `src/ui/pages/media_library.py`

**Ligne 730-737** :
```python
assigned = assoc_df.loc[assoc_df["match_id"].notna()].copy()
unassigned = assoc_df.loc[assoc_df["match_id"].isna()].copy()

# DÉDUPLIQUER : Un média peut avoir plusieurs associations (multi-joueurs)
if not assigned.empty:
    assigned = assigned.drop_duplicates(subset=["path", "match_id"], keep="first")
if not unassigned.empty:
    unassigned = unassigned.drop_duplicates(subset=["path"], keep="first")
```

**Impact** : Évite les doublons avant le groupby.

### Correction 2 : Clés Uniques avec Contexte ✅ (Mais Instable)

**Fichier** : `src/ui/pages/media_library.py`

**Ligne 253** :
```python
def _render_media_grid(items: pd.DataFrame, *, cols_per_row: int, render_context: str = "default") -> None:
```

**Ligne 286-290** :
```python
# Clé unique : hash complet du path + match_id + contexte de rendu + position
path_hash = hashlib.md5(path.encode()).hexdigest()
match_id_part = str(mid).strip() if isinstance(mid, str) and mid.strip() else "no_match"
unique_suffix = f"{render_context}::{i}::{col_idx}"
thumb_key = f"thumb_show::{path_hash}::{match_id_part}::{unique_suffix}"
```

**Impact** : Clés garanties uniques même si le même média apparaît plusieurs fois.

**⚠️ PROBLÈME** : La clé inclut `i` et `col_idx` qui changent, causant la perte du `session_state`.

### Correction 3 : Déduplication dans les Groupes ✅

**Fichier** : `src/ui/pages/media_library.py`

**Ligne 789-791** :
```python
g2 = g.sort_values("mtime", ascending=True).copy()
# Dédupliquer une dernière fois par sécurité (au cas où plusieurs xuid pour même média/match)
g2 = g2.drop_duplicates(subset=["path"], keep="first")
_render_media_grid(g2, cols_per_row=int(cols_per_row), render_context=f"match_{match_id}")
```

**Impact** : Évite les doublons dans chaque groupe de match.

### Correction 4 : Suppression Code Mort ✅

**Fichier** : `src/ui/pages/media_library.py`

**Ligne 764-766** :
```python
if not group_by_match:
    _render_media_grid(assoc_df, cols_per_row=int(cols_per_row), render_context="all")
    return
```

**Impact** : Code mort supprimé (lignes 767-769).

### Correction 5 : Contexte pour Tous les Appels ✅

**Fichier** : `src/ui/pages/media_library.py`

- Ligne 765 : `render_context="all"`
- Ligne 791 : `render_context=f"match_{match_id}"`
- Ligne 795 : `render_context="unassigned"`

**Impact** : Tous les appels utilisent un contexte unique.

---

## 🎯 Recommandations pour Résoudre les Régressions

### Priorité 1 : Corriger les Clés session_state Instables (CRITIQUE)

**Problème** : Les clés incluent `i` et `col_idx` qui changent à chaque rendu.

**Solution Recommandée** :
```python
# Utiliser un identifiant stable basé uniquement sur le path et le match_id
# Ne pas inclure la position dans la grille

def _render_media_grid(items: pd.DataFrame, *, cols_per_row: int, render_context: str = "default") -> None:
    # Ajouter un index stable au DataFrame AVANT le rendu
    items = items.copy()
    items["_stable_id"] = items.reset_index().index
    
    rows = items.to_dict(orient="records")
    for i in range(0, len(rows), cols_per_row):
        chunk = rows[i : i + cols_per_row]
        cols = st.columns(len(chunk))
        for col_idx, (c, rec) in enumerate(zip(cols, chunk, strict=False)):
            with c:
                path = str(rec.get("path") or "").strip()
                path_hash = hashlib.md5(path.encode()).hexdigest()
                match_id_part = str(rec.get("match_id") or "no_match").strip()
                # Utiliser l'ID stable au lieu de i et col_idx
                stable_id = rec.get("_stable_id", 0)
                thumb_key = f"thumb_show::{path_hash}::{match_id_part}::{render_context}::{stable_id}"
                # ...
```

### Priorité 2 : Corriger l'Affichage des Images (MAJEUR)

**Problème** : Images pleine largeur quand peu de médias par groupe.

**Solution Recommandée** :
```python
# Toujours créer cols_per_row colonnes, même si moins de médias
def _render_media_grid(items: pd.DataFrame, *, cols_per_row: int, render_context: str = "default") -> None:
    cols_per_row = int(cols_per_row)
    if cols_per_row < 2:
        cols_per_row = 2
    if cols_per_row > 8:
        cols_per_row = 8

    rows = items.to_dict(orient="records")
    for i in range(0, len(rows), cols_per_row):
        chunk = rows[i : i + cols_per_row]
        # TOUJOURS créer cols_per_row colonnes, même si len(chunk) < cols_per_row
        cols = st.columns(cols_per_row)
        for col_idx in range(cols_per_row):
            with cols[col_idx]:
                if col_idx < len(chunk):
                    rec = chunk[col_idx]
                    # Rendre le média
                else:
                    # Colonne vide (pour garder la grille alignée)
                    st.empty()
```

### Priorité 3 : Corriger la Navigation (MAJEUR)

**Problème** : `target="_blank"` casse le routing Streamlit.

**Solution Recommandée** :
```python
def _open_match_button(match_id: str) -> None:
    mid = str(match_id or "").strip()
    if not mid:
        st.caption("Match inconnu")
        return

    # Utiliser st.query_params au lieu de target="_blank"
    if st.button("Ouvrir le match", key=f"open_match_{mid}"):
        st.query_params["page"] = "Match"
        st.query_params["match_id"] = mid
        st.rerun()
```

**OU** utiliser le routing interne :
```python
from src.app.routing import navigate_to

def _open_match_button(match_id: str) -> None:
    mid = str(match_id or "").strip()
    if not mid:
        st.caption("Match inconnu")
        return

    if st.button("Ouvrir le match", key=f"open_match_{mid}"):
        navigate_to("Match", match_id=mid)
        st.rerun()
```

---

## 📝 Notes Finales

**Points Positifs** :
- ✅ L'association backend fonctionne correctement
- ✅ La logique temporelle est correcte (UTC epoch)
- ✅ Le support multi-joueurs est implémenté côté backend
- ✅ La déduplication des médias fonctionne

**Points à Améliorer** :
- ❌ Clés `session_state` instables → thumbnails perdus
- ❌ Peu de médias par groupe → images pleine largeur
- ❌ `target="_blank"` + routing → navigation cassée
- ❌ UI trop complexe avec trop de chemins conditionnels

**Recommandation Globale** :
- **Ne pas modifier le code sans tests**
- **Créer un script de diagnostic** pour vérifier chaque problème
- **Tester avec des données réelles** avant toute modification
- **Utiliser des identifiants stables** pour les clés `session_state`
- **Simplifier la logique d'affichage** pour éviter les chemins conditionnels complexes

**Prochaines Étapes** :
1. Créer un script de diagnostic pour vérifier les thumbnails en BDD
2. Tester le rendu avec différents nombres de médias
3. Tester la navigation sans `target="_blank"`
4. Refactoriser les clés `session_state` pour utiliser des identifiants stables
