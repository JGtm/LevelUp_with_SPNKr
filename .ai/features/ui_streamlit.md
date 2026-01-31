# UI Streamlit - Interface Utilisateur

## Résumé
Application Streamlit multi-pages pour la visualisation des statistiques Halo Infinite. Architecture modulaire avec séparation claire entre rendu (pages), logique métier (helpers), et état (session_state). Supporte le multi-joueurs, la synchronisation SPNKr, et les filtres avancés.

## Inputs
- **Base de données** : Chemin vers la DB SPNKr (`db_path`)
- **XUID** : Identifiant du joueur sélectionné
- **Paramètres utilisateur** : `AppSettings` (persistés en JSON)
- **Query params** : Navigation via URL (`?page=...&match_id=...`)

## Outputs
- **Dashboard interactif** : KPIs, graphiques, tableaux
- **Pages spécialisées** : Historique, Sessions, Coéquipiers, Médailles, etc.
- **Exports** : Données filtrées, graphiques

## Dépendances
- **Packages externes** :
  - `streamlit` : Framework UI
  - `plotly` : Visualisations interactives
  - `pandas` : DataFrames
- **Modules internes** :
  - `src.ui.pages.*` : Rendus de pages
  - `src.ui.components.*` : Composants réutilisables
  - `src.app.*` : Helpers et routing
  - `src.analysis.*` : Calculs statistiques
  - `src.visualization.*` : Graphiques

## Logique Métier

### Architecture des Pages
```
streamlit_app.py (main)
├── Sidebar
│   ├── Logo + Brand
│   ├── Sync indicator
│   ├── Player selector (multi-joueurs)
│   ├── Sync button
│   └── Filters (dates, playlists, modes, maps, amis)
├── Hero Profile (API SPNKr)
├── KPIs Section
├── Analytics DuckDB (optionnel)
└── Page Router
    ├── Dernier match
    ├── Recherche match
    ├── Historique
    ├── Sessions
    ├── Séries temporelles
    ├── Win/Loss
    ├── Coéquipiers
    ├── Médiathèque
    ├── Citations (H5)
    └── Paramètres
```

### Gestion de l'État (session_state)
```python
# Source de données
st.session_state["db_path"]           # Chemin DB
st.session_state["xuid_input"]        # XUID sélectionné
st.session_state["waypoint_player"]   # Gamertag pour Waypoint

# Filtres
st.session_state["filter_playlists"]  # Playlists sélectionnées
st.session_state["filter_modes"]      # Modes sélectionnés
st.session_state["filter_maps"]       # Cartes sélectionnées
st.session_state["filter_dates"]      # Plage de dates
st.session_state["filter_friends"]    # Amis sélectionnés

# Navigation
st.session_state["page"]              # Page courante
st.session_state["_pending_page"]     # Redirection en attente
st.session_state["_pending_match_id"] # Match à afficher

# Settings
st.session_state["app_settings"]      # AppSettings
```

### Flux de Données
```
1. main()
   ├── load_settings() → AppSettings
   ├── propagate_identity_to_env() → Tokens SPNKr
   ├── init_source_state() → db_path, xuid
   └── validate_and_fix_db_path()

2. Sidebar
   ├── render_sync_indicator()
   ├── render_player_selector()
   ├── sync_all_players() (bouton)
   └── render_filters_sidebar() → FilterState

3. Data Loading
   ├── load_match_dataframe() → df, db_key
   └── apply_filters() → dff (filtered)

4. Rendering
   ├── render_kpis_section(dff)
   ├── render_analytics_section() (DuckDB)
   └── dispatch_page(page, dff, ...)
```

### Système de Cache
```python
# Cache Streamlit
@st.cache_data
cached_list_local_dbs()
cached_compute_sessions_db()
cached_load_player_match_result()
cached_load_match_medals_for_player()
cached_load_match_rosters()

# Invalidation via db_cache_key()
db_key = hash(db_path + modification_time)
```

### Composants Réutilisables
| Composant | Usage |
|-----------|-------|
| `render_kpi_cards()` | Cartes KPI (kills, deaths, ratio) |
| `render_checkbox_filter()` | Filtre multi-sélection |
| `render_hierarchical_checkbox_filter()` | Filtre hiérarchique |
| `render_top_summary()` | Résumé en haut de page |
| `render_analytics_section()` | Analytics DuckDB |

### Filtres Avancés
```python
FilterState:
  - date_start, date_end
  - playlists: set[str]
  - modes: set[str]
  - maps: set[str]
  - friends: set[str]
  - gap_minutes: int (sessions)
  - picked_session_labels: list[str]
  - include_firefight: bool
```

## Points d'Attention
- **Rerun** : Utiliser `st.rerun()` après modification d'état
- **Query params** : Consommés une seule fois puis effacés
- **Multi-joueurs** : Reset des filtres au changement de joueur
- **Sync orphans** : Nettoyage des fichiers temporaires au démarrage
- **CSS custom** : `static/styles.css` chargé via `load_css()`

## Fichiers Clés
| Fichier | Rôle |
|---------|------|
| `streamlit_app.py` | Point d'entrée |
| `src/app/page_router.py` | Dispatch des pages |
| `src/app/filters_render.py` | Rendu des filtres |
| `src/app/kpis_render.py` | Rendu des KPIs |
| `src/ui/pages/*.py` | Pages individuelles |
| `src/ui/components/*.py` | Composants réutilisables |
| `src/ui/cache.py` | Gestion du cache |
| `src/ui/sync.py` | Synchronisation SPNKr |
