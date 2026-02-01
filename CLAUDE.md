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

## Commandes Utiles

```bash
# Lancer l'app Streamlit
streamlit run streamlit_app.py

# Synchronisation
python scripts/sync.py --delta --gamertag MonGamertag

# Backup/Restore
python scripts/backup_player.py --gamertag MonGamertag
python scripts/restore_player.py --gamertag MonGamertag --backup ./backups/

# Tests
pytest tests/ -v
```

## Règles

1. Répondre en français
2. Utiliser Pydantic v2 pour valider les données
3. Préférer Polars à Pandas pour les gros volumes
4. Utiliser DuckDBRepository pour l'accès aux données
5. Documenter les décisions dans `.ai/thought_log.md`

## Stack Technique

| Composant | Usage |
|-----------|-------|
| **DuckDB** | Moteur de requêtes OLAP |
| **Polars** | DataFrames haute performance |
| **Pydantic v2** | Validation des données |
| **Streamlit** | Interface utilisateur |
| **SPNKr** | API Halo Infinite |

## Code Déprécié

Les modules suivants sont DÉPRÉCIÉS :
- `src/db/loaders.py` → Utiliser `DuckDBRepository`
- `src/db/loaders_cached.py` → Utiliser `DuckDBRepository`
- `src/data/repositories/legacy.py` → Supprimé
- `src/data/repositories/shadow.py` → Supprimé
- `src/data/repositories/hybrid.py` → Supprimé

## Serveurs MCP Disponibles

Si les MCPs sont configurés, les utiliser :

**duckdb** :
- Exécuter SQL directement sur les données Halo
- `ATTACH 'data/warehouse/metadata.duckdb' AS meta`

**browser** (cursor-ide-browser) :
- Tester l'app Streamlit visuellement
