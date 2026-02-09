# Plan : médiane sur les graphes de distribution + renommage Frags

**Statut** : Planification (aucune modification de code pour l’instant)  
**Objectif** : Afficher la valeur **médiane** sur 6 graphes de distribution, renommer « Distribution des Kills » en « Distribution des frags », **normaliser les noms de mode** dans le graphe « Par mode » (Victoires/défaites), **améliorer l’onglet Médias** (lightbox, clic thumbnail, largeur bouton, message si aucune capture), et **évoluer l’onglet Mes coéquipiers** (Stats par minute : barres groupées ; graphe Frags parfaits ; **Profil de participation** moyen des 3 joueurs sur les matchs filtrés).

---

## 1. Périmètre

| Graphe | Fichier / fonction | Page UI | Action |
|--------|--------------------|--------|--------|
| **FDA** | `distributions.py` → `plot_kda_distribution` | Séries temporelles | Ajouter ligne verticale médiane + annotation |
| **Distribution de la précision** | `plot_histogram` (appelée depuis `timeseries.py`) | Séries temporelles | Ajouter médiane (via param ou calcul dans l’appelant) |
| **Distribution des kills** | `plot_histogram` + libellés dans `timeseries.py` | Séries temporelles | **Renommer** en « Distribution des frags » + ajouter médiane |
| **Distribution durée de vie** | `plot_histogram` | Séries temporelles | Ajouter médiane |
| **Distribution score de performance** | `plot_histogram` | Séries temporelles | Ajouter médiane |
| **Temps du premier kill / première mort** | `distributions.py` → `plot_first_event_distribution` | Séries temporelles | Ajouter médiane (en plus des moyennes existantes) |
| **Par mode** (Résultats par carte et mode) | `win_loss.py` → `plot_stacked_outcomes_by_category(..., mode_col)` | Victoires/défaites | **Normaliser** les noms de mode comme dans les filtres sidebar (`normalize_mode_label`) |
| **Stats par minute** (Mes coéquipiers, vue trio) | `teammates.py` (tableau + radar côte à côte) | Mes coéquipiers | **Un seul graphe** : supprimer le tableau et le radar ; conserver uniquement un **graphe en barres groupées** (Frags/min, Morts/min, Assists/min par joueur). |
| **Frags parfaits** (après Tirs à la tête) | `teammates_charts.py` → `render_metric_bar_charts` | Mes coéquipiers | **Ajouter** un graphe détaillant les frags parfaits (médailles Perfect), après le graphe « Tirs à la tête ». |
| **Profil de participation** (vue trio) | À ajouter dans `teammates.py` (vue 2 coéquipiers) | Mes coéquipiers | **Ajouter** un graphe « Profil de participation » (radar 6 axes) comme dans « Participation au match » (Dernier match), affichant la **participation moyenne** des 3 joueurs sur la base des filtres sélectionnés. |

---

## 2. Décisions de conception

### 2.1 Affichage de la médiane

- **Ligne verticale** : `fig.add_vline(x=median, ...)` sur l’axe des abscisses.
- **Annotation** : texte du type « Médiane : 1.25 » ou « Méd. : 1.25 » (format adapté à l’unité : FDA sans unité, précision en %, frags entier ou 1 décimale, secondes pour durée de vie / premier kill-mort, score avec 1–2 décimales).
- **Style** : distinguable de la ligne zéro (FDA) et des moyennes (premier kill/mort). Ex. trait plein pour la médiane, tirets pour la moyenne là où les deux coexistent.

### 2.2 Où calculer et dessiner la médiane

- **`plot_kda_distribution`** : calcul de la médiane dans la fonction (sur `x`), ajout d’une `add_vline` + annotation. Pas de paramètre optionnel : la médiane est toujours affichée quand il y a des données.
- **`plot_histogram`** :  
  - Option A : ajouter un paramètre optionnel `show_median: bool = True`. Si True, calculer `np.median(x)` et ajouter la vline + annotation.  
  - Option B : laisser `plot_histogram` sans changement et ajouter les vlines côté appelant (`timeseries.py`) après récupération de la figure.  
  - **Recommandation** : Option A pour garder la logique « distribution → médiane » dans le module de viz et éviter de dupliquer le style d’annotation.
- **`plot_first_event_distribution`** : dans la fonction, calculer la médiane pour `kills_sec` et `deaths_sec` (ex. `np.median(kills_sec)`), ajouter deux nouvelles `add_vline` avec annotation « Méd. kill : Xs » et « Méd. mort : Xs », style différent des lignes « Moy. » (ex. médiane en trait plein, moyenne en tirets).

### 2.3 Renommage « Kills » → « Frags »

- **Titre du graphe** : « Distribution des Kills » → **« Distribution des frags »**.
- **Label axe X** : « Kills » → **« Frags »**.
- **Messages d’info** : remplacer les textes du type « données de kills » / « pas assez de données de kills » par **« frags »** pour cohérence.
- **Colonne données** : rester sur `dff["kills"]` (pas de changement de schéma), seul le libellé utilisateur change.

Fichiers concernés par le libellé : `src/ui/pages/timeseries.py` (titres, labels, messages).

---

## 3. Plan d’implémentation (ordre proposé)

### Phase 1 – Module `plot_histogram` (réutilisable)

- **Fichier** : `src/visualization/distributions.py`, fonction `plot_histogram`.
- Ajouter paramètre optionnel `show_median: bool = True`.
- Si `show_median` et `x.size > 0` : calculer `median = np.median(x)`, puis `fig.add_vline(x=median, ...)` avec annotation (texte selon unité : utiliser `x_label` ou un paramètre optionnel `median_label` si besoin).
- Choisir un format d’annotation cohérent (ex. « Médiane : {valeur} » avec 1–2 décimales pour float, entier pour int).
- Style de ligne : trait plein, couleur lisible (ex. même que les barres ou couleur secondaire du thème).

### Phase 2 – FDA

- **Fichier** : `src/visualization/distributions.py`, fonction `plot_kda_distribution`.
- Après construction du KDE et du rug plot, calculer `median = np.median(x)`.
- Ajouter `fig.add_vline(x=median, ...)` avec annotation « Médiane : {median:.2f} » (ou « Méd. : … »), style distinct de la ligne zéro (ex. dash + couleur cyan/ambre).

### Phase 3 – Page Séries temporelles (histogrammes + renommage)

- **Fichier** : `src/ui/pages/timeseries.py`.
- **Précision** : conserver l’appel à `plot_histogram(..., show_kde=True)` et s’assurer que `show_median=True` (défaut) pour afficher la médiane.
- **Frags** :  
  - Remplacer le titre par « Distribution des frags ».  
  - Remplacer `x_label="Kills"` par `x_label="Frags"`.  
  - Adapter les messages `st.info` (« données de frags », « pas assez de données de frags »).  
  - La médiane s’affichera via le défaut de `plot_histogram`.
- **Durée de vie** : aucun changement de libellé ; la médiane via `plot_histogram(..., show_median=True)` (ou défaut).
- **Score de performance** : idem, médiane via `plot_histogram`.

Aucun autre fichier ne devrait être concerné pour ces libellés (pas de « Distribution des Kills » ailleurs d’après la recherche).

### Phase 4 – Premier kill / première mort

- **Fichier** : `src/visualization/distributions.py`, fonction `plot_first_event_distribution`.
- Pour `kills_sec` : calculer `median_kill = np.median(kills_sec)`, ajouter `fig.add_vline(x=median_kill, ...)` avec annotation « Méd. kill : {median_kill:.0f}s », style différent de la ligne « Moy. kill » (ex. trait plein pour médiane, dash pour moyenne).
- Pour `deaths_sec` : idem avec `median_death` et « Méd. mort : … ».
- Position des annotations : éviter le chevauchement (ex. médiane en `annotation_position="top"` si moyenne en top, ou décaler légèrement).

### Phase 5 – Normalisation des noms de mode (graphe « Par mode »)

- **Contexte** : Dans l’onglet **Victoires/défaites**, section **« Résultats par carte et mode »**, le graphe **« Par mode »** affiche les libellés bruts (`mode_category` ou `pair_name`). Les filtres de la sidebar utilisent eux `normalize_mode_label` (`src/app/helpers.py`) pour afficher des noms normalisés (traduction, retrait de « on MapName », retrait des suffixes Forge/Ranked).
- **Objectif** : Afficher les mêmes noms normalisés sur le graphe « Par mode » que dans les filtres.
- **Fichiers concernés** : `src/ui/pages/win_loss.py` ; éventuellement `src/app/page_router.py` si la page n’a pas encore accès à `normalize_mode_label`.
- **Approche recommandée** :  
  - Faire passer `normalize_mode_label` (ou `normalize_mode_label_fn`) en paramètre de `render_win_loss_page` depuis le routeur (comme pour d’autres pages, ex. `match_history`, `filters_render`).  
  - Pour le bloc « Par mode » uniquement : construire une colonne d’affichage `mode_display = dff[mode_col].apply(normalize_mode_label_fn)` (avec gestion des `None` si la fonction le retourne), utiliser un DataFrame qui contient cette colonne, et appeler `plot_stacked_outcomes_by_category(..., category_col="mode_display", ...)`. Ainsi les barres sont regroupées par libellé normalisé et les étiquettes de l’axe correspondent à ceux de la sidebar.  
- **Alternative** : Ajouter un paramètre optionnel `category_label_fn: Callable[[str], str] | None` à `plot_stacked_outcomes_by_category` et l’appliquer aux libellés de catégorie avant affichage ; alors la page Victoires/défaites passerait `category_label_fn=normalize_mode_label_fn` uniquement pour l’appel « Par mode ». La première approche (colonne dédiée) évite de modifier l’API générique du graphique.

---

## 7. Onglet Médias – lightbox, boutons, empty state

Toutes les évolutions ci‑dessous concernent l’onglet **Médias** (`src/ui/pages/media_tab.py`), sections « Mes captures », « Captures de XXX », « Sans correspondance », et les composants associés (`media_thumbnail.py`, `media_lightbox.py`).

### 7.1 Bouton « Voir en grand » → lightbox adapté à la taille de la fenêtre

- **Contexte** : Au clic sur « Voir en grand », la page ouvre un `@st.dialog("Média", width="large")` (`media_tab.py`, ~121–139) avec `st.image` / `st.video`. La taille du dialog est fixe (« large »).
- **Objectif** : Que le mode lightbox s’adapte à la taille de la fenêtre et affiche le média **le plus grand possible** (sans débordement).
- **Pistes** :
  - Utiliser la largeur maximale disponible pour le dialog Streamlit (si l’API le permet, ex. `width` en pourcentage ou « full » / « stretch »).
  - Renforcer le CSS injecté dans le dialog pour que le contenu (img/video) utilise `max-width: 100%` / `max-height: 100%` par rapport au **conteneur du dialog** et que le dialog lui‑même occupe une largeur/hauteur maximale (ex. 90vw / 90vh ou équivalent selon les contraintes Streamlit).
- **Fichiers** : `src/ui/pages/media_tab.py` (fonction `_lightbox_dialog`, paramètre `width` du decorator, CSS).

### 7.2 Ouvrir le lightbox en cliquant sur la thumbnail

- **Contexte** : Le composant `render_media_thumbnail` (`media_thumbnail.py`) injecte du HTML/JS dans une iframe : au clic sur le conteneur thumbnail, il ouvre un lightbox **HTML** (overlay généré par `build_lightbox_html` dans `media_lightbox.py`) avec `max-width: 95vw; max-height: 95vh`. Le bouton « Voir en grand » dans `media_tab.py` ouvre quant à lui le **dialog Streamlit** (session state + rerun).
- **Objectif** : Étudier la possibilité d’ouvrir le mode lightbox **en cliquant directement sur la thumbnail** (sans obliger à cliquer sur « Voir en grand »).
- **Pistes à étudier** :
  - **Option A** : Faire en sorte que le clic sur la thumbnail déclenche le même flux que « Voir en grand » (écriture de `_lightbox_media_path` / `_lightbox_media_kind` en session state + rerun) pour ouvrir le dialog Streamlit. Cela implique de pouvoir appeler une action Streamlit depuis l’iframe (ex. lien ou widget avec clé dédiée qui déclenche le même état qu’un bouton « Voir en grand »), ou d’exposer un mécanisme (query param, fragment) que la page lit au rerun pour ouvrir le dialog.
  - **Option B** : Conserver le lightbox HTML dans l’iframe et l’agrandir pour qu’il s’adapte à la fenêtre (comme en 7.1), afin que le clic thumbnail ouvre déjà un lightbox « grand ». Risque : le lightbox est contenu dans l’iframe, donc la taille utile peut rester limitée par l’iframe.
  - **Option C** : Hybride – clic thumbnail ouvre le lightbox HTML en grand (améliorer `media_lightbox.py` pour 100vw/100vh ou proche), et garder « Voir en grand » pour le dialog Streamlit si besoin (ou unifier sur un seul mécanisme après tests).
- **À documenter** : avantages/inconvénients (UX, cohérence avec le dialog, contraintes iframe/Streamlit), puis choisir une option.

### 7.3 Largeur du bouton « Ouvrir le match »

- **Contexte** : Dans `_render_media_grid` (`media_tab.py`, ~98–105), le lien « Ouvrir le match » est rendu en `st.markdown` avec des styles inline (`display:inline-block; padding:...`). Le bouton « Voir en grand » est un `st.button(..., width="stretch")` qui s’étire sur le conteneur.
- **Objectif** : Harmoniser la largeur du bouton « Ouvrir le match » avec celle du bouton « Voir en grand » et de la thumbnail : **adapter la largeur** du lien/bouton « Ouvrir le match » au conteneur (pleine largeur comme « Voir en grand »).
- **Pistes** : Rendre le lien en `display:block; width:100%; text-align:center;` (ou équivalent) pour qu’il occupe toute la largeur de la colonne, ou utiliser un `st.button` + `st.link_button` si disponible, ou un conteneur avec largeur 100 % pour que le lien s’étire. Vérifier l’API Streamlit (link_button, etc.) et la cohérence visuelle avec « Voir en grand » et la largeur de la thumbnail.

### 7.4 Message lorsqu’il n’y a aucune capture (section « Mes captures »)

- **Contexte** : Si le joueur n’a aucune capture, `mine` est vide ; `_render_media_grid(mine, ...)` est appelé puis retourne immédiatement (`if df.is_empty(): return`), donc **aucun texte** n’est affiché sous le titre « Mes captures ».
- **Objectif** : Lorsqu’il n’y a **aucune capture** dans la section « Mes captures », afficher un **texte explicite** du type : « Aucune capture détectée » (ou « Aucune capture trouvée pour ce joueur »).
- **Implémentation prévue** : Dans `render_media_tab`, avant ou après l’appel à `_render_media_grid(mine, ...)` : si `mine.is_empty()`, afficher un message (ex. `st.info("Aucune capture détectée.")` ou `st.caption("…")`) dans la section « Mes captures », de façon à ce que l’utilisateur comprenne que la liste est vide et non un chargement en cours.

---

## 8. Onglet Mes coéquipiers – Stats par minute (un seul graphe) et graphe Frags parfaits

### 8.1 Section « Stats par minute » : ne conserver qu’un seul graphe (barres groupées)

- **Contexte** : Dans l’onglet **Mes coéquipiers**, en **vue trio** (2 coéquipiers sélectionnés), la section **« Stats par minute »** affiche actuellement **deux éléments côte à côte** : un **tableau** (`st.dataframe(trio_per_min)`) avec colonnes Joueur, Frags/min, Morts/min, Assists/min, et un **graphe radar** (`create_stats_per_minute_radar`) sur les mêmes trois métriques. Fichier : `src/ui/pages/teammates.py` (lignes ~804–857).
- **Objectif** : Supprimer la redondance et ne garder **qu’une seule visualisation**.
- **Choix retenu** : **Graphe en barres groupées** (supprimer le tableau et le radar).
  - Une barre par joueur par métrique (Frags/min, Morts/min, Assists/min) : lecture directe des valeurs, comparaison côte à côte des trois joueurs sur chaque indicateur, sans duplication avec un tableau.
- **Implémentation prévue** :
  - Dans `teammates.py`, section « Stats par minute » : supprimer le tableau (`col_table`, `st.dataframe(trio_per_min)`) et le radar (`col_radar`, `create_stats_per_minute_radar`).
  - Introduire un **graphe en barres groupées** (Plotly ou via un module de viz existant) : en abscisse les 3 métriques (Frags/min, Morts/min, Assists/min) ou les 3 joueurs selon la disposition choisie ; en ordonnée les valeurs ; une série (couleur) par joueur pour permettre la comparaison. Les données viennent de `trio_per_min` (ou directement de `me_stats`, `f1_stats`, `f2_stats`). Si aucun composant réutilisable n’existe pour ce type de barres groupées, en créer un (ex. dans `src/visualization/` ou `src/ui/components/`) puis l’appeler depuis `teammates.py`.
  - Supprimer ou simplifier la construction de `trio_per_min` si elle ne sert plus qu’à alimenter ce graphe (garder la logique de calcul des stats agrégées pour l’entrée du graphe).

### 8.2 Ajouter un graphe « Frags parfaits » après « Tirs à la tête »

- **Contexte** : Dans la page Mes coéquipiers, les graphes de métriques par match (Folie meurtrière, Tirs à la tête, etc.) sont rendus par `render_metric_bar_charts` dans `src/ui/pages/teammates_charts.py`. Actuellement sont affichés : Folie meurtrière (max), puis **Tirs à la tête** (`headshot_kills`). Il n’y a pas de graphe pour les **frags parfaits** (médailles Perfect).
- **Objectif** : Ajouter **un graphe supplémentaire** qui détaille les **frags parfaits** (Perfect kills), **juste après** le graphe « Tirs à la tête », dans le même style (barres par match, comparaison joueurs).
- **Données** : Les frags parfaits ne sont pas dans `match_stats` ; ils sont dérivés des **médailles** (medals_earned). Le repository expose `count_perfect_kills_by_match(match_ids)` (`src/data/repositories/duckdb_repo.py`) qui retourne un dict `{match_id: count}`. Pour chaque joueur (moi + coéquipiers), il faut récupérer les match_ids des DataFrames de la série, puis appeler le repo (DB du joueur concerné : joueur principal = db_path courant, coéquipiers = DB de chaque coéquipier) pour obtenir les comptes Perfect par match, et ajouter une colonne (ex. `perfect_kills`) aux DataFrames ou construire une série compatible avec `plot_multi_metric_bars_fn`.
- **Implémentation prévue** :
  - Dans `render_metric_bar_charts` (`teammates_charts.py`), après le bloc qui trace « Tirs à la tête » (lignes ~141–154), ajouter un bloc similaire pour « Frags parfaits ».
  - Pour chaque entrée de `series` (nom, DataFrame), récupérer les `match_id`, appeler le repo adapté (celui du joueur principal ou du coéquipier selon la série) avec `count_perfect_kills_by_match(match_ids)`, puis enrichir le DataFrame avec une colonne `perfect_kills` (ou équivalent) mappée par match_id. Ensuite appeler `plot_fn(series, metric_col="perfect_kills", title="Frags parfaits", y_axis_title="Frags parfaits", hover_label="frags parfaits", ...)`.
  - **Contrainte** : `render_metric_bar_charts` ne reçoit peut‑être pas le `db_path` ni les références aux DB des coéquipiers ; il faudra soit les faire passer en paramètre, soit que l’appelant (teammates.py) pré-enrichisse les DataFrames avec une colonne `perfect_kills` avant d’appeler `render_metric_bar_charts`. La seconde option évite de changer la signature de `render_metric_bar_charts` pour y injecter le repo/db_path.
- **Fichiers concernés** : `src/ui/pages/teammates_charts.py` (ajout du bloc Frags parfaits dans `render_metric_bar_charts`) ; `src/ui/pages/teammates.py` (si enrichissement des DataFrames en amont : récupération des perfect counts par joueur et ajout de la colonne aux DataFrames passés à `render_metric_bar_charts`). Donnée : `DuckDBRepository.count_perfect_kills_by_match` (déjà utilisé dans match_view_charts, timeseries).

### 8.3 Profil de participation (vue trio) – participation moyenne des 3 joueurs

- **Contexte** : Dans l’onglet **Dernier match**, la section **« Participation au match »** (`match_view_participation.py` → `render_participation_section`) affiche un **radar « Profil de participation »** (6 axes : Objectifs, Combat, Support, Score, Impact, Survie) basé sur les PersonalScores et `compute_participation_profile` / `create_participation_profile_radar`. En **Mes coéquipiers**, la vue **1 coéquipier** a déjà un radar de complémentarité (`_render_synergy_radar` dans `teammates.py`) qui affiche 2 profils (moi + le coéquipier) sur les matchs partagés. La **vue trio** (2 coéquipiers sélectionnés) n’a aujourd’hui **pas** de graphe de ce type.
- **Objectif** : Ajouter dans l’onglet **Mes coéquipiers** (vue trio) un graphe **« Profil de participation »** identique en forme à celui de la section « Participation au match » du Dernier match, affichant la **participation moyenne des 3 joueurs** (moi + 2 coéquipiers) sur les matchs correspondant aux **filtres sélectionnés** (mêmes match_ids que le reste de la vue trio).
- **Données et logique** :
  - Les **match_ids communs** au trio sont déjà disponibles dans la vue trio (`trio_ids` / `merged`).
  - Pour **chaque joueur** (moi, f1, f2) : charger les **PersonalScores** pour ces match_ids depuis **la DB du joueur concerné** (joueur principal = `db_path` courant ; coéquipiers = `data/players/{gamertag}/stats.duckdb` comme dans `_render_synergy_radar`), puis calculer un **profil agrégé** (participation moyenne sur la période) via `compute_participation_profile` en passant un `match_row` agrégé (somme des deaths, somme du time_played_seconds, etc.) sur les matchs filtrés.
  - Réutiliser **tel quel** : `create_participation_profile_radar(profiles, title="Profil de participation", ...)` avec une liste de 3 profils (un par joueur), comme pour `_render_synergy_radar` avec 2 profils.
- **Implémentation prévue** :
  - Créer une fonction dédiée (ex. `_render_trio_participation_radar`) dans `teammates.py`, ou étendre la logique existante pour la vue trio. Entrées : `me_df`, `f1_df`, `f2_df`, noms et xuids, `db_path`, `xuid`, chemins DB des 2 coéquipiers (déduits depuis `db_path` et gamertag comme dans `_render_synergy_radar` : `base_dir / friend_name / "stats.duckdb"`).
  - Pour chaque joueur : `DuckDBRepository(..., xuid_or_gamertag).load_personal_score_awards_as_polars(match_ids=shared_match_ids)` ; construire `match_row` agrégé à partir du DataFrame matchs du joueur ; `compute_participation_profile(ps_polars, match_row=..., name=..., color=..., thresholds=get_radar_thresholds(db_path))` ; ajouter le profil à la liste.
  - Afficher un sous-titre du type « 🎯 Profil de participation » (ou réutiliser « Participation au match » pour cohérence avec Dernier match), puis `create_participation_profile_radar(profiles, title="Profil de participation", height=380)` avec légende des axes (RADAR_AXIS_LINES) comme dans `_render_synergy_radar` et `match_view_participation.py`.
  - **Emplacement** dans la page : après la section « Stats par minute » (barres groupées) et avant les graphes détaillés (trio kills, deaths, etc.) ou à un autre endroit cohérent du flux vue trio (à définir au moment de l’implémentation).
- **Fichiers concernés** : `src/ui/pages/teammates.py` (nouvelle section ou fonction pour le radar trio ; appel depuis le bloc vue multi-coéquipiers quand 2 coéquipiers sont sélectionnés). Réutilisation de `src/ui/components/radar_chart.create_participation_profile_radar`, `src/visualization/participation_radar.compute_participation_profile` et `get_radar_thresholds`, comme pour Dernier match et vue 1 coéquipier.

---

## 4. Récapitulatif des fichiers à modifier (au moment de l’implémentation)

| Fichier | Modifications prévues |
|---------|------------------------|
| `src/visualization/distributions.py` | `plot_histogram` : param `show_median`, calcul + vline + annotation. `plot_kda_distribution` : calcul médiane + vline + annotation. `plot_first_event_distribution` : calcul médianes + 2 vlines + annotations. |
| `src/ui/pages/timeseries.py` | Titre et `x_label` « Frags » pour l’ex‑« Kills » ; messages d’info « frags » ; aucun changement de logique d’appel si `show_median` est True par défaut. |
| `src/ui/pages/win_loss.py` | Pour le graphe « Par mode » : ajouter colonne `mode_display` via `normalize_mode_label_fn`, appeler `plot_stacked_outcomes_by_category(..., category_col="mode_display")`. Signature de `render_win_loss_page` : ajouter paramètre `normalize_mode_label_fn` si absent. |
| `src/app/page_router.py` | Si nécessaire : passer `normalize_mode_label` (ou fn) à `render_win_loss_page` lors de l’appel. |
| `src/ui/pages/media_tab.py` | Lightbox : dialog adapté à la fenêtre (width/CSS). Clic thumbnail → lightbox (si option retenue). Bouton « Ouvrir le match » : largeur pleine (style block/100 %). Section « Mes captures » : si `mine.is_empty()`, afficher message « Aucune capture détectée ». |
| `src/ui/components/media_thumbnail.py` | Si option clic thumbnail → dialog Streamlit : mécanisme pour déclencher session state + rerun depuis la thumbnail (ou doc de l’option retenue). |
| `src/ui/components/media_lightbox.py` | Si lightbox HTML est agrandi (option B/C 7.2) : adapter `max-width` / `max-height` (ex. 100vw / 100vh ou à la fenêtre). |
| `src/ui/pages/teammates.py` | Section « Stats par minute » (vue trio) : supprimer le tableau et le radar ; afficher un **graphe en barres groupées**. Pour Frags parfaits : si enrichissement en amont, ajouter colonne `perfect_kills` aux DataFrames avant `render_metric_bar_charts`. **Profil de participation (vue trio)** : ajouter une section « Profil de participation » avec radar 6 axes (comme Dernier match / Participation au match), affichant la participation moyenne des 3 joueurs sur les matchs filtrés : fonction dédiée type `_render_trio_participation_radar`, chargement PersonalScores par joueur depuis sa DB, `compute_participation_profile` + `create_participation_profile_radar`. |
| `src/ui/pages/teammates_charts.py` | Dans `render_metric_bar_charts`, après le graphe « Tirs à la tête », ajouter un graphe « Frags parfaits » (même pattern, `metric_col` / données Perfect). Adapter la signature ou les données reçues pour disposer des comptes Perfect par match par joueur (repo ou colonne pré-remplie). |

---

## 5. Tests à prévoir

- **`plot_kda_distribution`** : avec jeu de données fixe, vérifier que la figure contient une annotation ou une trace correspondant à la médiane attendue (ex. test de régression ou assertion sur les `layout.annotations` / shapes).
- **`plot_histogram`** : avec une série de valeurs connues, vérifier que lorsque `show_median=True`, une vline est présente à `np.median(values)` ; avec `show_median=False`, pas de vline médiane.
- **`plot_first_event_distribution`** : avec des `first_kills` / `first_deaths` connus, vérifier la présence de deux annotations (moyenne + médiane) pour chaque série non vide.
- **UI** : vérifier manuellement que le libellé « Distribution des frags » et « Frags » apparaissent bien sur la page Séries temporelles.
- **Par mode** : vérifier que les libellés du graphe « Par mode » (Victoires/défaites) correspondent à ceux des filtres de mode (sidebar), avec traduction et sans « on MapName » / Forge / Ranked.
- **Médias** : lightbox s’adapte à la fenêtre (taille maximale) ; si implémenté, clic sur thumbnail ouvre le lightbox ; bouton « Ouvrir le match » en pleine largeur ; section « Mes captures » vide affiche « Aucune capture détectée ».
- **Mes coéquipiers** : section « Stats par minute » n’affiche plus qu’un graphe en barres groupées ; après « Tirs à la tête », le graphe « Frags parfaits » est affiché ; en vue trio, le graphe « Profil de participation » (radar 6 axes) affiche la participation moyenne des 3 joueurs sur les matchs filtrés.

---

## 6. Références

- FDA : `plot_kda_distribution` (ligne ~28), appel dans `timeseries.py` ligne ~74.
- Histogrammes : `plot_histogram` (ligne ~555), appels dans `timeseries.py` (précision ~89, kills ~113, durée de vie ~142, perf ~164).
- Premier kill/mort : `plot_first_event_distribution` (ligne ~1135), appel dans `timeseries.py` ~256.
- Par mode : `plot_stacked_outcomes_by_category` appelé avec `mode_col` dans `win_loss.py` (lignes ~137–149) ; normalisation des modes : `normalize_mode_label` dans `src/app/helpers.py` (ligne ~66), utilisé côté filters dans `filters.py` / `filters_render.py`.
- Médias : `media_tab.py` (grille, dialog lightbox, boutons), `media_thumbnail.py` (thumbnail + lightbox HTML dans iframe), `media_lightbox.py` (overlay HTML/CSS/JS). Section « Mes captures » : `mine = media_df.filter(pl.col("section") == "mine")`, puis `_render_media_grid(mine, ...)`.
- Mes coéquipiers : « Stats par minute » (vue trio) dans `teammates.py` (l.804–857) : remplacer tableau + radar par un **graphe en barres groupées**. Profil de participation : même radar que « Participation au match » (Dernier match) — `match_view_participation.render_participation_section`, `create_participation_profile_radar`, `compute_participation_profile` dans `participation_radar.py` ; vue 1 coéquipier = `_render_synergy_radar` (teammates.py l.104+) ; vue trio = à ajouter (`_render_trio_participation_radar` ou équivalent). Métriques (Folie meurtrière, Tirs à la tête) dans `teammates_charts.py` → `render_metric_bar_charts` ; frags parfaits : `DuckDBRepository.count_perfect_kills_by_match` dans `duckdb_repo.py`.

Ce document ne demande **aucune modification de code** tant que l’implémentation n’est pas décidée ; il sert de plan de travail pour l’ajout de la médiane, le renommage Frags, la normalisation des noms de mode sur le graphe « Par mode », les évolutions de l’onglet Médias, et les évolutions de l’onglet Mes coéquipiers (Stats par minute en barres groupées, graphe Frags parfaits, Profil de participation moyen des 3 joueurs en vue trio).
