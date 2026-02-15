# Documentation : Données Killer-Victim et Antagonistes

> Guide pour les IA sur l'exploitation des données de frags dans LevelUp.

## Vue d'ensemble

Les données de "qui a tué qui" permettent d'analyser les performances PvP d'un joueur :
- **Némésis** : L'adversaire qui vous tue le plus
- **Souffre-douleur** : L'adversaire que vous tuez le plus
- **Timeseries K/D** : Évolution du K/D au cours d'un match
- **Historique de duels** : Performance contre un adversaire spécifique

## Architecture des tables

```
highlight_events         → Source brute (events kill/death)
       ↓
killer_victim_pairs      → Paires killer→victim avec timestamps
       ↓
antagonists              → Stats agrégées par adversaire
```

### Table `highlight_events`

| Colonne | Type | Description |
|---------|------|-------------|
| match_id | VARCHAR | UUID du match |
| event_type | VARCHAR | `kill`, `death`, `medal`, `mode` |
| time_ms | INTEGER | Timestamp (ms depuis début match) |
| xuid | VARCHAR | XUID Xbox du joueur concerné |
| gamertag | VARCHAR | Nom du joueur (**peut être corrompu**) |
| raw_json | VARCHAR | JSON brut de l'event |

**Note** : Les gamertags peuvent contenir des caractères NUL (`\x00`). Utiliser `resolve_gamertag()` ou `match_participants` pour obtenir des noms propres.

### Table `killer_victim_pairs`

| Colonne | Type | Description |
|---------|------|-------------|
| match_id | VARCHAR | UUID du match |
| killer_xuid | VARCHAR | XUID du tueur |
| killer_gamertag | VARCHAR | Nom du tueur |
| victim_xuid | VARCHAR | XUID de la victime |
| victim_gamertag | VARCHAR | Nom de la victime |
| kill_count | INTEGER | Nombre de frags (1 par row) |
| time_ms | INTEGER | Timestamp du frag |
| is_validated | BOOLEAN | Vérifié contre stats officielles |

### Table `antagonists`

| Colonne | Type | Description |
|---------|------|-------------|
| opponent_xuid | VARCHAR PK | XUID de l'adversaire |
| opponent_gamertag | VARCHAR | Dernier gamertag connu |
| times_killed | INTEGER | Nombre de fois tué par moi |
| times_killed_by | INTEGER | Nombre de fois il m'a tué |
| matches_against | INTEGER | Nombre de matchs en opposition |
| last_encounter | TIMESTAMP | Date du dernier match |

## Modules Python

### `src/analysis/killer_victim.py`

Fonctions principales :

```python
# Calculer les paires killer/victim depuis les events bruts
from src.analysis.killer_victim import compute_killer_victim_pairs
pairs = compute_killer_victim_pairs(events_list, tolerance_ms=5)

# Calculer némésis/souffre-douleur pour un match
from src.analysis.killer_victim import compute_personal_antagonists
result = compute_personal_antagonists(events, me_xuid="2533274823110022")
print(result.nemesis.gamertag, result.bully.gamertag)

# Version Polars pour les graphiques
from src.analysis.killer_victim import (
    compute_kd_timeseries_by_minute_polars,
    compute_duel_history_polars,
    killer_victim_matrix_polars,
)
```

### `src/data/repositories/duckdb_repo.py`

```python
repo = get_repository_from_profile("JGtm")

# Charger les paires comme DataFrame Polars
pairs_df = repo.load_killer_victim_pairs_as_polars(match_id="abc-123")

# Vérifier si les données existent
if repo.has_killer_victim_pairs():
    # ...

# Résumé des antagonistes
summary = repo.compute_antagonists_summary_polars(top_n=5)
```

### `src/visualization/antagonist_charts.py`

```python
from src.visualization.antagonist_charts import (
    plot_killer_victim_stacked_bars,  # Barres empilées K/D
    plot_kd_timeseries,               # K/D par minute
    plot_duel_history,                # Historique vs adversaire
    plot_killer_victim_heatmap,       # Matrice killer/victim
    plot_top_antagonists_bars,        # Top némésis/victimes
    plot_nemesis_victim_summary,      # Indicateurs Plotly
)
```

## Exemples de requêtes SQL

### Top adversaires tués

```sql
SELECT victim_gamertag, SUM(kill_count) as total_kills
FROM killer_victim_pairs
WHERE killer_xuid = '2533274823110022'
GROUP BY victim_gamertag
ORDER BY total_kills DESC
LIMIT 10;
```

### K/D par playlist

```sql
SELECT 
    ms.playlist_name,
    SUM(CASE WHEN kv.killer_xuid = '2533274823110022' THEN kv.kill_count ELSE 0 END) as kills,
    SUM(CASE WHEN kv.victim_xuid = '2533274823110022' THEN kv.kill_count ELSE 0 END) as deaths
FROM killer_victim_pairs kv
JOIN match_stats ms ON kv.match_id = ms.match_id
GROUP BY ms.playlist_name
ORDER BY kills DESC;
```

### Frags par minute d'un match

```sql
SELECT 
    time_ms / 60000 as minute,
    SUM(CASE WHEN killer_xuid = '2533274823110022' THEN 1 ELSE 0 END) as kills,
    SUM(CASE WHEN victim_xuid = '2533274823110022' THEN 1 ELSE 0 END) as deaths
FROM killer_victim_pairs
WHERE match_id = 'abc-123-def'
GROUP BY minute
ORDER BY minute;
```

## Backfill des données

Si `killer_victim_pairs` est vide, lancer :

```bash
# Backfill depuis highlight_events
python scripts/backfill_data.py --player JGtm --killer-victim

# Recalculer les antagonistes agrégés
python scripts/populate_antagonists.py --gamertag JGtm --force
```

## Palette de couleurs Halo

```python
COLORS = {
    "kills": "#00ff00",       # Vert néon
    "deaths": "#ff4444",      # Rouge
    "nemesis": "#ff6600",     # Orange
    "victim": "#00aaff",      # Bleu
    "positive_kd": "#00ff00", # Vert
    "negative_kd": "#ff4444", # Rouge
    "highlight": "#ffd700",   # Or
}
```

## Intégration Streamlit

```python
import streamlit as st
from src.data.repositories.factory import get_repository_from_profile
from src.visualization.antagonist_charts import plot_killer_victim_stacked_bars

def render_antagonists(gamertag: str, match_id: str | None = None):
    repo = get_repository_from_profile(gamertag)
    
    if not repo.has_killer_victim_pairs():
        st.warning("Données non disponibles. Lancez --killer-victim backfill.")
        return
    
    pairs_df = repo.load_killer_victim_pairs_as_polars(match_id=match_id)
    
    fig = plot_killer_victim_stacked_bars(pairs_df, match_id=match_id)
    st.plotly_chart(fig, use_container_width=True)
```

## Liens vers les fichiers

- **Analyse** : `src/analysis/killer_victim.py`, `src/analysis/antagonists.py`
- **Repository** : `src/data/repositories/duckdb_repo.py` (méthodes `load_killer_victim_*`)
- **Visualisation** : `src/visualization/antagonist_charts.py`
- **Scripts** : `scripts/populate_antagonists.py`, `scripts/backfill_data.py`
- **Tests** : `tests/test_killer_victim_antagonists.py`
