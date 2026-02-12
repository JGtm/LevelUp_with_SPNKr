# CLAUDE.md - Instructions pour agents IA

> Ce fichier est lu par Claude Code et autres agents IA au début de chaque session.

## Contexte Projet

**LevelUp** - Dashboard de statistiques Halo Infinite avec architecture DuckDB unifiée (v4).

## Workflow Agentique

**AVANT TOUTE ACTION** : Consulter les fichiers `.ai/` :
- `.ai/project_map.md` : Cartographie du projet
- `.ai/thought_log.md` : Journal des décisions
- `.ai/data_lineage.md` : Flux de données
- `.ai/ARCHITECTURE_ROADMAP.md` : Roadmap des phases
- `.ai/PLAN_UNIFIE.md` : Plan unifié des sprints (S0-S11)
- `.ai/SPRINT_EXPLORATION.md` : **Exploration codebase pour Sprints 6-11** — catalogue de données, fonctions réutilisables, audit Pandas/SQLite/src/db, blockers par sprint. **Consulter impérativement avant de travailler sur un sprint >= 6.**

**APRÈS CHAQUE MODIFICATION SIGNIFICATIVE** : Mettre à jour ces fichiers.

## Architecture des Données (v4)

| Type | Stockage | Chemin |
|------|----------|--------|
| Référentiels | DuckDB | `data/warehouse/metadata.duckdb` |
| Matchs joueur | DuckDB | `data/players/{gamertag}/stats.duckdb` |
| Archives | Parquet | `data/players/{gamertag}/archive/` |
| Config | JSON | `db_profiles.json`, `app_settings.json` |

## Tables DuckDB Principales

| Table | Description |
|-------|-------------|
| `match_stats` | Faits des matchs |
| `medals_earned` | Médailles par match |
| `teammates_aggregate` | Stats coéquipiers |
| `antagonists` | Top killers/victimes |
| `highlight_events` | Événements film |
| `career_progression` | Historique rangs |
| `mv_*` | Vues matérialisées |

## Environnement Python

**IMPORTANT : Utiliser le `.venv` à la racine du repo (Python 3.12.10 Windows natif)**

### Configuration officielle

- **Interpreter** : `.venv` à la racine du repo
- **Python** : 3.12.10
- **Commande canonique** : toujours préférer `python -m ...` (ex: `python -m pytest`)

### Packages vérifiés

- `pytest==9.0.2`
- `duckdb==1.4.4`
- `polars==1.38.1`
- `pyarrow==23.0.0`
- `pandas==2.3.3` (uniquement pour compatibilité Streamlit/Plotly, interdit dans le code métier)
- `numpy==2.4.2`

### Activation selon shell

- **PowerShell** : `./.venv/Scripts/Activate.ps1`
- **cmd.exe** : `.venv\\Scripts\\activate.bat`
- **Git Bash** : `source .venv/Scripts/activate`

### Commandes tests

```bash
# Suite stable hors intégration
python -m pytest -q --ignore=tests/integration

# Suite complète
python -m pytest

# Healthcheck environnement
python scripts/check_env.py
```

### Règles strictes

1. **Ne pas installer/mettre à jour** des packages sans motivation documentée
2. **Ne pas utiliser le Python MSYS2/MinGW** — source de conflits DLL
3. **Ne pas modifier le `PATH`** — utiliser `.venv` + `python -m pytest`

## Commandes Utiles

```bash
# Synchronisation
python scripts/sync.py --delta --gamertag MonGamertag

# Backup/Restore
python scripts/backup_player.py --gamertag MonGamertag
python scripts/restore_player.py --gamertag MonGamertag --backup ./backups/

# Backfill sessions (session_id, session_label dans match_stats)
python scripts/backfill_data.py --player MonGT --sessions
python scripts/backfill_data.py --all --sessions

# Backfill shots_fired/shots_hit (match_stats et match_participants)
python scripts/backfill_data.py --player MonGT --shots
python scripts/backfill_data.py --player MonGT --shots --force-shots
python scripts/backfill_data.py --player MonGT --participants-shots
python scripts/backfill_data.py --player MonGT --participants-shots --force-participants-shots

# Tests
.venv/bin/python.exe -m pytest tests/ -v
```

## Règles

1. Répondre en français
2. Utiliser Pydantic v2 pour valider les données
3. **Backfill** : Pour tout backfill ou création de nouvelles fonctions de backfill, utiliser `scripts/backfill_data.py`. Ne pas créer de scripts backfill séparés ; ajouter une option dédiée (ex. `--sessions`, `--killer-victim`) dans `backfill_data.py`.
4. **Pandas est PROSCRIT** - Utiliser **Polars** uniquement pour les DataFrames et séries (voir § Pandas interdit ci-dessous)
5. Utiliser DuckDBRepository pour l'accès aux données
6. Documenter les décisions dans `.ai/thought_log.md`
7. **SQLite est PROSCRIT** - Aucun fallback SQLite, tout le code doit utiliser DuckDB v4 uniquement
8. **Streamlit** : Ne jamais utiliser `use_container_width=True` (déprécié). Utiliser `width="stretch"` à la place (`width="content"` si besoin). Pour `st.button`, `st.image`, `st.plotly_chart`, etc.

## ⛔ Pandas interdit (règle critique)

- **Aucun** `import pandas` ni `import pandas as pd` dans le code applicatif (analyse, UI, sync, repositories, scripts).
- **Polars uniquement** : `import polars as pl` ; utiliser `pl.DataFrame`, `pl.Series`, `pl.LazyFrame`.
- À la frontière avec des librairies qui exigent du NumPy/Pandas (ex. certains composants Streamlit/Plotly), convertir au dernier moment avec `.to_pandas()` ou `.to_numpy()` et ne pas faire remonter du Pandas dans les modules métier.
- **Audit des points à migrer** : voir `.ai/PANDAS_TO_POLARS_AUDIT.md` et `.ai/CONSOLIDATED_AUDITS_AND_ROADMAP.md`.

## ⛔ SQLite interdit (règle critique)

- **Aucun** `import sqlite3` ni `sqlite3.connect()` dans le code applicatif (UI, sync, repositories, loaders).
- **Aucun** fallback sur une base `.db` (SQLite) : si une base est attendue, elle doit être `.duckdb`.
- **Aucun** usage de `sqlite_master` : utiliser `information_schema.tables` (DuckDB).
- **Seules exceptions** : les scripts de **migration** qui lisent l’ancien SQLite pour alimenter DuckDB (`recover_from_sqlite.py`, `migrate_player_to_duckdb.py`). Ils restent les seuls autorisés à ouvrir un fichier `.db`.
- **Audit des points à migrer** : voir `.ai/SQLITE_TO_DUCKDB_AUDIT.md`.
- **Audit Pandas → Polars** : voir `.ai/PANDAS_TO_POLARS_AUDIT.md`.
- **Synthèse consolidée** : `.ai/CONSOLIDATED_AUDITS_AND_ROADMAP.md`.

## Architecture Multi-Joueurs (DuckDB v4)

Chaque joueur a sa propre DB : `data/players/{gamertag}/stats.duckdb`

**Pour afficher les stats d'un coéquipier** sur des matchs communs :
1. Identifier les `match_id` communs via `teammates_aggregate` ou filtres
2. Charger les stats du coéquipier depuis **SA propre DB** (pas celle du joueur principal)
3. Utiliser `_load_teammate_stats_from_own_db(gamertag, match_ids, reference_db_path)`

**Important** : Ne jamais passer le xuid d'un coéquipier à `load_df_optimized(db_path, xuid)` car le xuid est ignoré pour DuckDB v4. Il faut construire le chemin vers la DB du coéquipier.

## Stack Technique

| Composant | Usage |
|-----------|-------|
| **DuckDB** | Moteur de requêtes OLAP |
| **Polars** | DataFrames et séries (Pandas interdit) |
| **Pydantic v2** | Validation des données |
| **Streamlit** | Interface utilisateur |
| **SPNKr** | API Halo Infinite |

## Modules Supprimés (v4.1)

Les anciens modules legacy ont été supprimés lors de la migration v4.1 :
- `src/db/loaders.py` — supprimé, remplacé par `DuckDBRepository`
- `src/db/loaders_cached.py` — supprimé
- `src/data/repositories/legacy.py` — supprimé
- `src/data/repositories/shadow.py` — supprimé
- `src/data/repositories/hybrid.py` — supprimé

**Tout le code doit utiliser `DuckDBRepository`** (`src/data/repositories/duckdb_repo.py`).

## Serveurs MCP Disponibles

Si les MCPs sont configurés, les utiliser :

**duckdb** :
- Exécuter SQL directement sur les données Halo
- `ATTACH 'data/warehouse/metadata.duckdb' AS meta`

**browser** (cursor-ide-browser) :
- Tester l'app Streamlit visuellement
