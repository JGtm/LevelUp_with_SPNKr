# Architecture OpenSpartan Graph

> Documentation technique de l'architecture du projet.

## Vue d'ensemble

```
openspartan-graph/
├── streamlit_app.py          # Point d'entrée principal (orchestration)
├── openspartan_launcher.py   # Launcher avec gestion mémoire
│
├── src/
│   ├── app/                  # 🆕 Orchestration (Phase 1 & 2)
│   │   ├── state.py          # Gestion session_state centralisée
│   │   ├── routing.py        # Navigation entre pages
│   │   ├── sidebar.py        # Logique sidebar
│   │   ├── helpers.py        # 🆕 Fonctions utilitaires
│   │   ├── filters.py        # 🆕 Logique filtres sidebar
│   │   ├── profile.py        # 🆕 Gestion profil joueur
│   │   ├── kpis.py           # 🆕 Calcul et affichage KPIs
│   │   ├── data_loader.py    # 🆕 Chargement données
│   │   └── navigation.py     # 🆕 Navigation et rendu pages
│   │
│   ├── config.py             # Configuration & constantes
│   ├── models.py             # Dataclasses (entités)
│   │
│   ├── analysis/             # Logique métier (calculs)
│   │   ├── filters.py        # Filtres playlists/modes
│   │   ├── killer_victim.py  # Analyse confrontations
│   │   ├── maps.py           # Stats par carte
│   │   ├── sessions.py       # Détection sessions
│   │   ├── stats.py          # Calculs statistiques
│   │   ├── performance_score.py
│   │   └── performance_config.py
│   │
│   ├── db/                   # Accès données
│   │   ├── connection.py     # Gestion connexions SQLite
│   │   ├── loaders.py        # Chargement données
│   │   ├── loaders_cached.py # Loaders avec cache DB
│   │   ├── parsers.py        # Parsing JSON des matchs
│   │   ├── profiles.py       # Gestion profils joueurs
│   │   ├── queries.py        # Requêtes SQL
│   │   └── schema.py         # 🔧 Schéma + index optimisés
│   │
│   ├── ui/                   # Interface utilisateur
│   │   ├── aliases.py        # Gestion alias XUID
│   │   ├── cache.py          # Cache Streamlit
│   │   ├── medals.py         # Affichage médailles
│   │   ├── settings.py       # Paramètres (AppSettings)
│   │   ├── sync.py           # Synchronisation SPNKr
│   │   ├── translations.py   # Traductions FR
│   │   ├── components/       # Composants réutilisables
│   │   └── pages/            # Pages du dashboard
│   │
│   └── visualization/        # Graphiques Plotly
│       ├── theme.py          # Thème Halo
│       ├── timeseries.py     # Graphiques temporels
│       └── ...
│
├── scripts/
│   ├── sync.py               # 🆕 Script sync unifié
│   ├── spnkr_import_db.py    # Import matchs SPNKr
│   └── ...
│
└── tests/
    ├── test_app_module.py    # 🆕 Tests module app Phase 1
    ├── test_app_phase2.py    # 🆕 Tests module app Phase 2
    └── ...
```

## Module `src/app/` (Phase 1 & 2)

### `state.py` - Gestion de l'état

```python
from src.app.state import (
    PlayerIdentity,      # Dataclass identité joueur
    AppState,            # État global de l'app
    get_default_identity,
    init_source_state,
    get_db_cache_key,
    get_aliases_cache_key,
)

# Exemple d'utilisation
identity = get_default_identity()
print(identity.display_name)  # "Spartan117"
print(identity.xuid)          # "1234567890"
```

### `routing.py` - Navigation

```python
from src.app.routing import (
    Page,                # Enum des pages
    consume_query_params,
    build_app_url,
    navigate_to,
)

# Pages disponibles
Page.ACCUEIL
Page.DERNIER_MATCH
Page.HISTORIQUE
Page.SESSIONS
Page.CARTES
Page.COEQUIPIERS
Page.VICTOIRES
Page.SERIES
Page.CITATIONS
Page.RECHERCHE
Page.PARAMETRES

# Construire une URL
url = build_app_url(Page.MATCH_VIEW, match_id="abc123")
# -> "?page=match_view&match_id=abc123"
```

### `sidebar.py` - Sidebar

```python
from src.app.sidebar import (
    render_sidebar,
    render_sync_button,
    render_player_selector_sidebar,
)
```

### `helpers.py` - Fonctions utilitaires (Phase 2)

```python
from src.app.helpers import (
    clean_asset_label,      # Nettoie les labels d'assets
    normalize_mode_label,   # Normalise les noms de modes
    normalize_map_label,    # Normalise les noms de cartes
    assign_player_colors,   # Assigne des couleurs aux joueurs
    date_range,             # Plage de dates d'un DataFrame
    styler_map,             # Compat pandas Styler
)

# Exemples
clean_asset_label("Quick Play - 12345678")  # -> "Quick Play"
normalize_mode_label("Arena:Slayer on Aquarius")  # -> "Arène : Assassin"
normalize_map_label("a446725e-b281-414c")  # -> "Carte inconnue"
```

### `filters.py` - Logique des filtres (Phase 2)

```python
from src.app.filters import (
    build_friends_opts_map,     # Options de sélection d'amis
    add_ui_columns,             # Ajoute colonnes UI au DataFrame
    apply_date_filter,          # Filtre par dates
    apply_checkbox_filters,     # Filtre par checkboxes
    render_date_filters,        # Rend les filtres de date
    render_session_filters,     # Rend les filtres de session
    render_cascade_filters,     # Rend Playlist → Mode → Carte
)
```

### `profile.py` - Gestion du profil (Phase 2)

```python
from src.app.profile import (
    PlayerIdentity,             # NamedTuple identité joueur
    ProfileAssets,              # NamedTuple assets profil
    get_identity_from_secrets,  # Charge identité depuis secrets
    resolve_xuid,               # Résout un XUID
    load_profile_assets,        # Charge les assets profil
    render_profile_header,      # Rend le header/hero
)

# Exemple
identity = get_identity_from_secrets()
assets, err = load_profile_assets(identity.xuid, settings)
render_profile_header(identity.xuid, settings, assets)
```

### `kpis.py` - Calcul et affichage KPIs (Phase 2)

```python
from src.app.kpis import (
    KPIStats,               # NamedTuple avec toutes les stats
    compute_kpi_stats,      # Calcule les KPIs
    render_matches_summary, # Rend le résumé des parties
    render_career_kpis,     # Rend les KPIs de carrière
    render_all_kpis,        # Rend tout (pratique)
)

# Exemple
kpis = compute_kpi_stats(df_filtered)
print(f"Win rate: {kpis.win_rate:.1%}")
print(f"K/D ratio: {kpis.global_ratio:.2f}")
```

### `data_loader.py` - Chargement des données (Phase 2)

```python
from src.app.data_loader import (
    default_identity_from_secrets,  # Charge l'identité depuis secrets/env
    propagate_identity_env,         # Propage l'identité vers os.environ
    init_source_state,              # Initialise db_path/xuid_input/waypoint_player
    resolve_xuid_input,             # Résout le XUID depuis entrée UI
    validate_db_path,               # Valide et corrige le chemin DB
    load_match_data,                # Charge les données de matchs
    ensure_h5g_commendations_repo,  # Génère le référentiel Citations si absent
)

# Exemple d'initialisation
init_source_state(DEFAULT_DB, settings)
db_path = validate_db_path(st.session_state["db_path"], settings)
xuid = resolve_xuid_input(st.session_state["xuid_input"], db_path)
df = load_match_data(db_path, xuid)
```

### `navigation.py` - Navigation et rendu des pages (Phase 2)

```python
from src.app.navigation import (
    PAGES,                      # Liste des pages disponibles
    get_match_view_params,      # Paramètres communs pour match_view
    consume_pending_navigation, # Consomme les query params
    render_page_navigation,     # Rend le segmented control
    render_active_page,         # Rend la page active
)

# Liste des pages
PAGES = [
    "Séries temporelles",
    "Comparaison de sessions",
    "Dernier match",
    "Match",
    "Citations",
    "Victoires/Défaites",
    "Mes coéquipiers",
    "Historique des parties",
    "Paramètres",
]

# Rendu simplifié
consume_pending_navigation()
page = render_page_navigation()
render_active_page(page, db_path, xuid, df, dff, settings, ...)
```

## Index de base de données (Phase 1)

Les index suivants ont été ajoutés dans `src/db/schema.py` :

### Index composites pour filtres fréquents

```sql
-- Filtres combinés (xuid + playlist + map + date)
CREATE INDEX idx_MatchCache_filters 
ON MatchCache(xuid, playlist_id, map_id, start_time DESC);

-- Filtres par résultat
CREATE INDEX idx_MatchCache_outcome 
ON MatchCache(xuid, outcome, start_time DESC);

-- Performance score
CREATE INDEX idx_MatchCache_perf 
ON MatchCache(xuid, performance_score DESC) 
WHERE performance_score IS NOT NULL;
```

### Index tables sources

```sql
-- MatchStats
CREATE INDEX idx_MatchStats_MatchId ON MatchStats(MatchId);
CREATE INDEX idx_MatchStats_StartTime 
ON MatchStats(json_extract(ResponseBody, '$.MatchInfo.StartTime'));
CREATE INDEX idx_MatchStats_PlayerDate 
ON MatchStats(json_extract(ResponseBody, '$.MatchInfo.StartTime') DESC);

-- PlayerMatchStats
CREATE INDEX idx_PlayerMatchStats_MatchId ON PlayerMatchStats(MatchId);

-- HighlightEvents
CREATE INDEX idx_HighlightEvents_MatchId ON HighlightEvents(MatchId);
CREATE INDEX idx_HighlightEvents_Xuid ON HighlightEvents(Xuid);
```

## Script `sync.py` unifié (Phase 1)

Point d'entrée unique pour la synchronisation :

```bash
# Aide
python scripts/sync.py --help

# Sync incrémentale (nouveaux matchs)
python scripts/sync.py --delta

# Sync complète
python scripts/sync.py --full --max-matches 500

# Reconstruire le cache MatchCache
python scripts/sync.py --rebuild-cache

# Appliquer les index optimisés
python scripts/sync.py --apply-indexes

# Combiner plusieurs opérations
python scripts/sync.py --delta --with-assets --apply-indexes

# Afficher les statistiques
python scripts/sync.py --stats
```

## Stratégie de cache

### Niveau 1 : Streamlit `@st.cache_data`
- TTL: durée de la session
- Usage: DataFrames filtrés, résultats de calculs
- Fichier: `src/ui/cache.py`

### Niveau 2 : SQLite (MatchCache)
- TTL: permanent (invalidé par sync)
- Usage: Données dénormalisées, sessions pré-calculées
- Fichier: `src/db/schema.py`

### Niveau 3 : Disque (JSON/fichiers)
- TTL: configurable
- Usage: Assets (médailles, maps), métadonnées API
- Dossier: `data/cache/`

## Prochaines étapes (Phase 3)

1. **Architecture hexagonale** : Séparer `domain/`, `infrastructure/`, `application/`
2. **Cache multi-niveaux intelligent** : Invalidation automatique
3. **Chargement asynchrone** : Pagination et lazy loading
4. **Documentation API** : Docstrings complètes + schémas
