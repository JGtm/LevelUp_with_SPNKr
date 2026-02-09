# Analyse approfondie : Persistance des filtres par DB joueur

> **Contexte** : L’utilisateur signale des conflits et une mauvaise persistance des filtres par joueur : au changement de joueur les préférences ne sont pas correctement restaurées, et au retour sur le joueur initial encore plus de filtres apparaissent désélectionnés. Demande : analyse détaillée + plan de correction ultra détaillé, **sans toucher au code** pour l’instant.

---

## 1. Synthèse du problème

- **Symptômes** :  
  - En passant à un autre utilisateur, l’état des filtres ne correspond pas à ce qui était sauvegardé pour ce joueur.  
  - En revenant au joueur initial, davantage de filtres sont désélectionnés qu’avant.  
  - Comportement perçu comme des « conflits » et de la « concurrence » entre joueurs.

- **Cause principale identifiée** :  
  Une partie de l’état des filtres est **globale** (clés `session_state` partagées entre tous les joueurs) alors que la persistance (fichiers JSON par joueur) et les flags de chargement sont déjà scopés par joueur. Les **clés des widgets Streamlit** (checkboxes playlists/modes/cartes) ne sont pas nettoyées au changement de joueur, ce qui provoque affichage incohérent, clics « de correction » et **écrasement des préférences** à la sauvegarde automatique.

---

## 2. Architecture actuelle (rappel)

### 2.1 Stockage persistant

- **Emplacement** : `.streamlit/filter_preferences/`
- **Fichiers** : un JSON par joueur, nommé `player_{gamertag}.json` (DuckDB v4) ou `xuid_{xuid}.json` (legacy).
- **Contenu** : `FilterPreferences` (mode, dates, gap_minutes, session, playlists/modes/cartes sélectionnés).

### 2.2 Flux au changement de joueur (`streamlit_app.py`)

1. Sauvegarde des filtres de l’**ancien** joueur : `save_filter_preferences(old_xuid, old_db_path)` (lit `session_state`).
2. Nettoyage d’une **liste partielle** de clés dans `session_state`.
3. Suppression des flags scopés de l’ancien joueur : `_filters_loaded_{player_key}`, `_last_saved_player_{player_key}`.
4. Mise à jour `db_path` et `xuid` pour le **nouveau** joueur.
5. Application des préférences du nouveau joueur : `apply_filter_preferences(xuid, db_path)` (charge le JSON et écrit dans `session_state`).
6. `st.rerun()`.

### 2.3 Chargement au premier rendu (`filters_render.py`)

- Pour le joueur courant, clé scopée `_filters_loaded_{player_key}`.
- Si la clé est absente : chargement du JSON (ou défaut « dernière session »), `apply_filter_preferences`, puis marquage `_filters_loaded_{player_key} = True`.
- En fin de rendu : sauvegarde automatique pour le joueur courant si `_last_saved_player_{player_key}` cohérent.

---

## 3. Causes racines détaillées

### 3.1 (Critique) Clés des widgets checkboxes non scopées et non nettoyées

**Fichiers** : `src/ui/components/checkbox_filter.py`, `src/app/filters_render.py`.

- Les filtres cascade (playlists, modes, cartes) utilisent des **clés globales** :
  - Données : `filter_playlists`, `filter_modes`, `filter_maps`.
  - Widgets : `filter_playlists_cb_{opt}_v{version}`, `filter_playlists_cat_*`, `filter_playlists_mode_*`, et équivalents pour modes/cartes, plus `*_version`, `*_all`, `*_none`.
- Au changement de joueur, **seules** les clés listées dans `filter_keys_to_clear` sont supprimées (`filter_playlists`, `filter_modes`, `filter_maps`). Les clés des **widgets** (`*_cb_*`, `*_cat_*`, `*_mode_*`, `*_version`, etc.) **restent** dans `session_state`.

**Conséquence** :  
Après `apply_filter_preferences(new_player)`, les **données** (`filter_playlists` etc.) sont correctes pour le nouveau joueur, mais Streamlit réutilise l’**état des widgets** associé aux anciennes clés. Pour un `st.checkbox(..., value=opt in current_selection, key="filter_playlists_cb_Arène_v2")`, si la clé existe déjà, Streamlit affiche la valeur stockée (ancien joueur), pas `value`. L’utilisateur voit donc des cases à cocher incohérentes avec la sélection réelle. En « corrigeant » en cliquant, il modifie la sélection ; la sauvegarde automatique en fin de rendu enregistre alors cette sélection **dégradée** et écrase le JSON du joueur. À chaque aller-retour entre joueurs, les fichiers sont réécrits avec de plus en plus de désélections → « encore plus de filtres désélectionnés » au retour.

### 3.2 Liste de nettoyage incomplète au changement de joueur

**Fichier** : `streamlit_app.py`, `filter_keys_to_clear`.

**Clés actuellement supprimées** :  
`filter_mode`, `start_date_cal`, `end_date_cal`, `picked_session_label`, `picked_sessions`, `filter_playlists`, `filter_modes`, `filter_maps`.

**Clés utilisées par les filtres mais non supprimées** (liste à compléter) :

- `gap_minutes` (mode Sessions).
- `_latest_session_label`, `_trio_latest_session_label` (sessions).
- `min_matches_maps`, `_min_matches_maps_auto`, `min_matches_maps_friends`, `_min_matches_maps_friends_auto`.
- Toutes les clés dérivées des checkboxes :  
  `filter_playlists_version`, `filter_modes_version`, `filter_maps_version`, et toute clé dont le nom commence par `filter_playlists_`, `filter_modes_`, `filter_maps_` (sous-clés widgets).

**Risque** :  
Mélange d’état entre joueurs (ex. `gap_minutes` ou labels de session de l’ancien joueur) et persistance de l’état d’affichage des checkboxes (voir 3.1).

### 3.3 Sauvegarde automatique en fin de rendu et « concurrence »

**Fichier** : `src/app/filters_render.py` (fin de `render_filters_sidebar`).

- À chaque run, après le rendu des filtres pour le joueur courant, on appelle `save_filter_preferences(xuid, db_path)` si `_last_saved_player_{player_key}` est cohérent.
- La sauvegarde lit **tout** depuis `session_state` (filter_mode, dates, gap_minutes, playlists/modes/cartes).
- Si `session_state` a été faussé par des widgets globaux (3.1) ou par des clés résiduelles (3.2), on **persiste cet état erroné** dans le JSON du joueur courant. D’où l’impression de « concurrence » : un même run peut afficher un joueur mais enregistrer un état déjà corrompu par l’affichage ou par des résidus d’un autre joueur.

### 3.4 Ordre d’exécution et double application

- Dans `streamlit_app.py`, après mise à jour `db_path`/`xuid`, on appelle `apply_filter_preferences(xuid, db_path)` puis `st.rerun()`.
- Au run suivant, `render_filters_sidebar` est appelé avec le nouveau joueur ; `_filters_loaded_{new_player_key}` n’est pas défini, donc on recharge le JSON et on réapplique une deuxième fois.
- Ce double apply n’est pas en soi la cause des régressions, mais il montre que le chargement repose à la fois sur le bloc « changement de joueur » et sur le bloc « premier rendu ». Toute incohérence (clés non nettoyées) est alors amplifiée.

### 3.5 Pas de scopage des clés de données par joueur

- Aujourd’hui, les données de filtres en `session_state` sont en clair : `filter_playlists`, `filter_mode`, etc. Un seul jeu de clés pour toute l’app.
- Quand on change de joueur, on efface puis on réécrit ces clés. Si le nettoyage est incomplet (3.1, 3.2), l’état du nouveau joueur peut être pollué par l’ancien, et la sauvegarde automatique enregistre cet état mixte.

---

## 4. Scénario type « encore plus de filtres désélectionnés »

1. Joueur A : playlists [P1, P2, P3] sélectionnées, sauvegardées dans `player_A.json`.
2. Utilisateur passe au joueur B : on sauve A (OK), on nettoie les clés listées (mais pas les clés widgets), on applique B.
3. Au rendu pour B, les checkboxes réutilisent des clés créées pour A ; l’affichage peut montrer P2 décochée alors que `filter_playlists` pour B contient P2.
4. L’utilisateur décoche/recoche pour « aligner » l’affichage ; la sélection réelle change ; en fin de rendu on sauvegarde B (éventuellement avec une sélection déjà dégradée).
5. Retour au joueur A : on sauve B, on nettoie (toujours sans les clés widgets), on applique A depuis `player_A.json` (donc [P1, P2, P3]).
6. Les widgets ont encore des clés en mémoire (éventuellement de B) ; l’affichage pour A peut montrer P1 ou P3 décochées.
7. L’utilisateur clique pour « remettre » les cases ; en réalité il **décoche** des options (Streamlit inverse par rapport à ce qu’il croit).
8. Sauvegarde automatique : on écrit dans `player_A.json` une sélection avec moins d’éléments (ex. [P2] seulement).
9. Prochain passage sur A : chargement de [P2] → encore plus de filtres « désélectionnés » par rapport à l’intention initiale.

C’est une combinaison de **widgets globaux** (3.1) et de **sauvegarde automatique** (3.3) qui fait dégrader progressivement les JSON.

---

## 5. Plan de correction ultra détaillé (sans coder)

### 5.0 Principes directeurs

- **Un seul propriétaire par run** : à un instant donné, `session_state` pour les filtres doit refléter un seul joueur (celui dont on affiche les données).
- **Nettoyage exhaustif** au changement de joueur : toute clé qui peut contenir un état de filtre (données ou widget) doit être supprimée ou réinitialisée pour éviter toute réutilisation entre joueurs.
- **Cohérence affichage / données** : après application des préférences d’un joueur, les widgets ne doivent pas réutiliser d’état lié à un autre joueur (soit clés nettoyées, soit clés scopées par joueur).
- **Ne pas bloquer l’app** : sauvegarde et chargement doivent rester dans des try/except ou équivalents ; les erreurs ne doivent pas empêcher le changement de joueur.

---

### 5.1 Nettoyage complet des clés au changement de joueur

**Objectif** : À l’instant où on décide de passer au nouveau joueur, supprimer **toutes** les clés `session_state` qui portent un état de filtre (données ou widgets), pour ce run et pour le prochain après `rerun`.

**Fichier** : `streamlit_app.py`, bloc « Changement de joueur ».

**Étapes** :

1. **Garder la sauvegarde de l’ancien joueur** avant toute suppression (déjà en place).
2. **Construire une liste exhaustive de clés à supprimer** :
   - Clés « données » déjà présentes :  
     `filter_mode`, `start_date_cal`, `end_date_cal`, `picked_session_label`, `picked_sessions`, `filter_playlists`, `filter_modes`, `filter_maps`.
   - Clés « données » à ajouter :  
     `gap_minutes`, `_latest_session_label`, `_trio_latest_session_label`, `min_matches_maps`, `_min_matches_maps_auto`, `min_matches_maps_friends`, `_min_matches_maps_friends_auto`.  
     (À adapter si d’autres clés liées aux filtres existent ailleurs dans l’app.)
   - Clés « widgets » : supprimer **toute** clé dont le nom **commence par** l’un des préfixes suivants :  
     `filter_playlists_`, `filter_modes_`, `filter_maps_`.  
     Cela couvre `filter_playlists_version`, `filter_playlists_cb_*`, `filter_playlists_cat_*`, `filter_playlists_mode_*`, `filter_playlists_all`, `filter_playlists_none`, et les équivalents pour modes et cartes.
3. **Implémentation recommandée** :  
   - Boucle sur les clés explicites à supprimer (comme aujourd’hui).  
   - Puis : `keys_to_delete = [k for k in st.session_state.keys() if any(k.startswith(prefix) for prefix in ("filter_playlists_", "filter_modes_", "filter_maps_"))]` (ou équivalent), puis `del st.session_state[k]` pour chaque.
4. **Ordre** : faire ce nettoyage **après** `save_filter_preferences(old_xuid, old_db_path)` et **avant** de mettre à jour `db_path`/`xuid` et d’appeler `apply_filter_preferences(xuid, db_path)`.

**Critère de succès** : Après un changement de joueur, aucune clé `session_state` ne doit commencer par `filter_playlists_`, `filter_modes_` ou `filter_maps_`, et les clés listées ci‑dessus (gap_minutes, _latest_session_label, etc.) ne doivent plus exister.

---

### 5.2 Centraliser la liste des préfixes/clés de filtres

**Objectif** : Éviter que de futures clés (ex. nouveaux widgets ou options) soient oubliées au nettoyage.

**Fichier** : à définir (ex. `src/ui/filter_state.py` ou petit module dédié `src/app/filter_keys.py`).

**Contenu proposé** (à adapter au style du projet) :

- **Constante** : liste des clés « données » de filtres à réinitialiser au changement de joueur (ex. `FILTER_DATA_KEYS`).
- **Constante** : liste des préfixes de clés « widgets » (ex. `FILTER_WIDGET_KEY_PREFIXES = ("filter_playlists_", "filter_modes_", "filter_maps_")`).
- **Fonction** : `get_all_filter_keys_to_clear(session_state) -> list[str]` qui retourne :
  - les clés dans `FILTER_DATA_KEYS` qui sont présentes dans `session_state` ;
  - toutes les clés de `session_state` dont le nom commence par l’un des préfixes.
- **Utilisation** : dans `streamlit_app.py`, au changement de joueur, appeler cette fonction et supprimer les clés retournées au lieu de maintenir une liste en dur.

**Critère de succès** : Toute nouvelle clé de filtre (donnée ou widget) est soit dans `FILTER_DATA_KEYS`, soit sous un préfixe dans `FILTER_WIDGET_KEY_PREFIXES`, et le nettoyage au changement de joueur reste exhaustif sans modifier `streamlit_app.py` à chaque ajout.

---

### 5.3 (Optionnel mais recommandé) Scoper les clés des widgets par joueur

**Objectif** : À long terme, éviter toute collision entre joueurs même si un nettoyage était incomplet.

**Fichiers** : `src/ui/components/checkbox_filter.py`, `src/app/filters_render.py` (appels aux checkboxes).

**Idée** :  
- Introduire un paramètre optionnel `player_key` (ou `scope`) dans les composants qui rendent les checkboxes (ou dans la fonction qui construit les `session_key`).
- Construire les clés de persistance des widgets à partir de `session_key` + `player_key`, par ex. :  
  `effective_session_key = f"{session_key}_{player_key}"` pour les données, et dériver les clés des widgets à partir de `effective_session_key` (ex. `filter_playlists_player_A_cb_...`).
- Dans `render_filters_sidebar`, récupérer `player_key = _get_player_key(xuid, db_path)` et le passer aux composants (ou à une couche qui génère les `session_key`).

**Points d’attention** :  
- `save_filter_preferences` / `apply_filter_preferences` lisent/écrivent aujourd’hui `filter_playlists`, `filter_modes`, `filter_maps` sans suffixe. Il faudrait soit :
  - continuer à utiliser des clés « logiques » sans joueur pour ces trois clés et ne scoper que les clés des widgets ; soit
  - faire en sorte que apply/save utilisent les mêmes clés scopées (ex. `filter_playlists_{player_key}`). Alors il faut s’assurer que partout où on lit ces clés (filtrage des données, etc.) on utilise la même convention.
- Cohérence avec le nettoyage : si on scope par joueur, au changement de joueur on peut soit ne plus supprimer les clés de l’ancien joueur (elles ne seront plus lues), soit les supprimer pour éviter l’accumulation de clés en mémoire.

**Critère de succès** : En changeant de joueur, les checkboxes affichent immédiatement la sélection du joueur courant sans réutiliser l’état des widgets d’un autre joueur, même sans nettoyage agressif.

---

### 5.4 Renforcer la robustesse de la sauvegarde automatique

**Objectif** : Ne pas enregistrer un état manifestement incohérent (ex. sélection vide alors que le joueur avait des préférences).

**Fichier** : `src/app/filters_render.py`, bloc de sauvegarde en fin de `render_filters_sidebar`.

**Pistes** (à trancher en implémentation) :

- **Option A** : Avant d’appeler `save_filter_preferences`, comparer l’état courant en `session_state` avec les préférences chargées pour ce joueur (ex. une copie stockée dans `_loaded_prefs_{player_key}`). Si la seule différence est une réduction « suspecte » des ensembles (ex. playlists passées de 5 à 0 sans action utilisateur explicite), ne pas sauvegarder ou sauvegarder l’ancienne version.
- **Option B** : Ne pas sauvegarder automatiquement à chaque run, mais seulement après un délai / debounce ou sur événements explicites (ex. changement de page, bouton « Sauvegarder les filtres »). Réduit le risque d’écraser avec un état corrompu par des widgets, au prix d’un peu plus de complexité et d’UX.
- **Option C** : Conserver la sauvegarde en fin de rendu telle quelle, mais s’assurer que le nettoyage (5.1) et éventuellement le scopage (5.3) rendent l’état fiable avant cette sauvegarde.

**Recommandation** : Prioriser 5.1 (et 5.2) ; si les tests montrent encore des régressions, ajouter une garde type Option A ou B.

---

### 5.5 Éviter le double chargement (optionnel)

**Objectif** : Clarifier le flux et éviter d’appliquer deux fois les préférences du nouveau joueur.

**Fichier** : `streamlit_app.py` et éventuellement `filters_render.py`.

**Option** :  
- Après mise à jour `db_path`/`xuid` et nettoyage, appeler `apply_filter_preferences(xuid, db_path)` comme aujourd’hui.
- Avant `st.rerun()`, définir **déjà** `st.session_state["_filters_loaded_{new_player_key}"] = True` pour le nouveau joueur, de sorte qu’au run suivant `render_filters_sidebar` ne recharge plus le JSON ni n’applique à nouveau. Le premier rendu du nouveau joueur utilisera alors uniquement l’état appliqué dans le bloc « changement de joueur ».

**Risque** : Si `apply_filter_preferences` échoue silencieusement, on marquerait tout de même les filtres comme chargés. Il faudrait ne set le flag qu’en cas de succès, ou garder le comportement actuel (double apply) qui est plus tolérant aux erreurs.

**Recommandation** : Traiter en dernier ; le double apply n’est pas la cause des bugs actuels.

---

### 5.6 Tests de non-régression et scénarios de validation

**Objectif** : Valider la persistance et l’isolation entre joueurs après les correctifs.

**Scénarios à couvrir** (manuellement ou via scripts/UI) :

1. **Isolation A → B → A**  
   - Joueur A : définir des filtres (mode, dates, playlists, modes, cartes).  
   - Changer vers B, définir d’autres filtres.  
   - Revenir à A.  
   - **Attendu** : Les filtres de A sont exactement ceux laissés à l’étape 1 (aucune désélection supplémentaire).

2. **Sauvegarde au changement**  
   - Joueur A : modifier les filtres sans quitter la page.  
   - Changer vers B.  
   - Revenir à A.  
   - **Attendu** : Les dernières modifications sur A sont bien présentes.

3. **Premier chargement d’un joueur**  
   - Changer vers un joueur qui n’a jamais eu de préférences sauvegardées.  
   - **Attendu** : Comportement par défaut (ex. dernière session) sans erreur, et pas d’état résiduel d’un autre joueur.

4. **Checkboxes cohérentes**  
   - Après chaque changement de joueur, vérifier que les cases à cocher (playlists, modes, cartes) correspondent bien à la sélection chargée (ex. en comparant avec le contenu du JSON ou avec un indicateur de compte « X/Y sélectionnés »).

**Scripts existants** :  
- `scripts/test_filter_persistence_by_player.py`, `scripts/validate_filter_state.py`, `tests/test_filter_state.py` : les étendre ou ajouter des cas qui simulent un changement de joueur et vérifient l’absence de clés résiduelles et la cohérence des fichiers JSON.

---

### 5.7 Documentation et thought_log

**À faire après implémentation** :

- Mettre à jour `docs/FILTER_PERSISTENCE.md` : décrire la liste (ou le module) des clés/préfixes à nettoyer au changement de joueur, et le fait que les clés widgets sont soit nettoyées, soit scopées par joueur.
- Mettre à jour `.ai/thought_log.md` : résumer la cause racine (widgets globaux + liste de nettoyage incomplète) et les changements effectués (fichiers modifiés, nouvelles constantes/fonctions).
- Si un plan existant (ex. `.ai/FILTER_PERSISTENCE_FIX_PLAN.md`) est rendu obsolète, le marquer comme intégré dans la présente analyse ou l’archiver.

---

## 6. Ordre d’implémentation recommandé

| Phase | Action | Priorité |
|-------|--------|----------|
| 1 | **5.1** – Nettoyage exhaustif au changement de joueur (données + préfixes widgets) | Haute |
| 2 | **5.2** – Centraliser clés/préfixes dans un module dédié et utiliser cette liste dans 5.1 | Haute |
| 3 | **5.6** – Ajouter/étendre tests et valider scénarios A→B→A et cohérence checkboxes | Haute |
| 4 | **5.4** – (Si besoin) Renforcer la sauvegarde automatique (garde ou debounce) | Moyenne |
| 5 | **5.3** – Scoper les clés des widgets par joueur | Moyenne (long terme) |
| 6 | **5.5** – Éviter le double chargement (optionnel) | Basse |
| 7 | **5.7** – Documentation et thought_log | Après chaque phase |

---

## 7. Résumé des causes et des corrections

| Cause | Correction principale |
|-------|------------------------|
| Clés widgets checkboxes globales et non nettoyées | 5.1 : supprimer toutes les clés dont le nom commence par `filter_playlists_`, `filter_modes_`, `filter_maps_` au changement de joueur. Option 5.3 : scopage par joueur. |
| Liste `filter_keys_to_clear` incomplète | 5.1 : ajouter `gap_minutes`, `_latest_session_label`, `_trio_latest_session_label`, `min_matches_maps`, etc. 5.2 : centraliser la liste. |
| Sauvegarde automatique enregistre un état faussé | 5.1 + 5.2 (état propre après changement) ; option 5.4 (garde ou debounce). |
| Risque de régression sur de nouvelles clés | 5.2 : module avec préfixes et liste de clés, utilisé partout pour le nettoyage. |

---

## 8. Fichiers concernés (référence)

- **streamlit_app.py** : bloc changement de joueur (sauvegarde, nettoyage, apply, rerun).
- **src/app/filters_render.py** : chargement initial scopé, sauvegarde automatique en fin de rendu.
- **src/ui/filter_state.py** : `save_filter_preferences`, `apply_filter_preferences`, `_get_player_key`, (optionnel) constantes/clés à nettoyer.
- **src/ui/components/checkbox_filter.py** : clés des widgets (optionnel : paramètre scope/player_key).
- **docs/FILTER_PERSISTENCE.md** : documentation utilisateur/développeur.
- **.ai/FILTER_PERSISTENCE_FIX_PLAN.md** : plan précédent (à aligner ou archiver).
- **.ai/thought_log.md** : journal des décisions.

Aucune modification de code n’a été effectuée dans le cadre de ce document ; le plan ci‑dessus est prêt à être implémenté étape par étape.
