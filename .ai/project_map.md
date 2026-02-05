# Project Map - LevelUp

> Ce fichier est la cartographie vivante du projet. L'agent IA doit le consulter et le mettre à jour.

## ⚠️ Limitations Connues

**IMPORTANT** : Consulter `.ai/API_LIMITATIONS.md` avant d'implémenter des fonctionnalités liées aux armes.

- **Weapon Stats par arme** : NON DISPONIBLE dans l'API (vérifié 2026-02-02)
- **Film Chunks** : NON EXPLOITABLES pour l'identification d'armes
- **SQLite** : PROSCRIT - Tout le code doit utiliser DuckDB v4 uniquement

## ⚠️ RÈGLE CRITIQUE : Chargement Multi-Joueurs

**NE JAMAIS** passer le xuid d'un coéquipier à `load_df_optimized(db_path, xuid)` !
Le xuid est IGNORÉ pour DuckDB v4 et ça charge toujours depuis `db_path`.

**TOUJOURS** utiliser `_load_teammate_stats_from_own_db(gamertag, match_ids, db_path)`
pour charger les stats d'un coéquipier depuis **SA propre DB**.

```python
# ❌ FAUX - Charge depuis db_path (joueur principal), pas le coéquipier
teammate_df = load_df_optimized(db_path, teammate_xuid)

# ✅ CORRECT - Charge depuis data/players/{gamertag}/stats.duckdb
teammate_df = _load_teammate_stats_from_own_db(gamertag, match_ids, db_path)
```

Voir `src/ui/pages/teammates.py` pour l'implémentation de référence.

## État Actuel (2026-02-02)

### Phases Complétées

- **Phase 1** : Stabilisation architecture hybride ✅
- **Phase 2** : Migration vers DuckDB Unifiée ✅
- **Phase 3** : Enrichissement des Données (antagonistes) ✅
- **Phase 4** : Optimisations Avancées ✅
  - Vues matérialisées (`mv_map_stats`, `mv_mode_category_stats`, etc.)
  - Lazy loading et pagination
  - Backup/Restore Parquet avec compression Zstd
  - Partitionnement temporel
  - Refonte système de synchronisation (DuckDBSyncEngine)
- **Phase 5** : Enrichissement Visuel & API ✅
  - Career Rank & Stats Armes
  - Correctifs modes/playlists
  - Graphes Radar & Étiquettes
  - Nouvelles représentations statistiques
  - Watcher/Daemon Thumbnails
- **Phase 6** : Documentation & Branding "LevelUp" ✅
  - README.md complet
  - Guides d'installation et configuration
  - Documentation technique mise à jour
  - Branding LevelUp appliqué

### Architecture Cible v4

```
data/
├── players/                    # Données par joueur
│   └── {gamertag}/
│       ├── stats.duckdb       # DB DuckDB persistée
│       └── archive/           # Archives temporelles
│           ├── matches_2023.parquet
│           └── archive_index.json
├── warehouse/
│   └── metadata.duckdb        # Référentiels partagés
└── backups/                   # Backups Parquet
```

## Modules Clés

### Accès aux Données
- `src/data/repositories/duckdb_repo.py` : Repository principal DuckDB
- `src/data/repositories/factory.py` : Factory pattern
- `src/data/sync/engine.py` : Moteur de synchronisation

### Analyse
- `src/analysis/killer_victim.py` : Calcul antagonistes
- `src/analysis/antagonists.py` : Agrégation rivalités
- `src/analysis/sessions.py` : Détection sessions
- `src/analysis/performance_score.py` : Score de performance

### UI
- `src/ui/pages/` : Pages du dashboard
- `src/ui/components/` : Composants réutilisables
- `src/visualization/` : Graphiques Plotly

## Tables DuckDB

### Base Joueur (stats.duckdb)

| Table | Description |
|-------|-------------|
| `match_stats` | Faits des matchs |
| `medals_earned` | Médailles par match |
| `teammates_aggregate` | Stats coéquipiers |
| `antagonists` | Top killers/victimes |
| `player_match_stats` | Données MMR/skill |
| `highlight_events` | Événements film |
| `xuid_aliases` | Mapping XUID→Gamertag |
| `career_progression` | Historique rangs |
| `sync_meta` | Métadonnées sync |
| `mv_*` | Vues matérialisées |

### Base Métadonnées (metadata.duckdb)

| Table | Description |
|-------|-------------|
| `playlists` | Définitions playlists |
| `game_modes` | Modes de jeu (FR/EN) |
| `medal_definitions` | Référentiel médailles |
| `career_ranks` | Rangs de carrière |

## Scripts Utilitaires

| Script | Description |
|--------|-------------|
| `scripts/sync.py` | Synchronisation SPNKr |
| `scripts/backup_player.py` | Export Parquet Zstd |
| `scripts/restore_player.py` | Import depuis backup |
| `scripts/archive_season.py` | Archivage temporel |
| `scripts/migrate_*.py` | Scripts de migration |

## Dépendances Critiques

| Package | Version | Usage |
|---------|---------|-------|
| `duckdb` | >=0.10.0 | Moteur unique |
| `polars` | >=0.20.0 | DataFrames |
| `pydantic` | >=2.5.0 | Validation |
| `streamlit` | >=1.28.0 | Interface |

## Points d'Entrée

- `streamlit_app.py` : Application principale
- `openspartan_launcher.py` : Lanceur CLI

## Documentation

| Document | Contenu |
|----------|---------|
| `docs/INSTALL.md` | Installation |
| `docs/CONFIGURATION.md` | Configuration |
| `docs/ARCHITECTURE.md` | Architecture technique |
| `docs/DATA_ARCHITECTURE.md` | Architecture données |
| `docs/SYNC_GUIDE.md` | Guide synchronisation |
| `docs/BACKUP_RESTORE.md` | Backup/Restore |
| `docs/FAQ.md` | Questions fréquentes |

## Dernière Mise à Jour

**2026-02-01** : Phase 6 terminée - Documentation & Branding "LevelUp"
