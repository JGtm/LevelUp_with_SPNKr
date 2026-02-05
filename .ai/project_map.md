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
| `killer_victim_pairs` | Paires killer→victim avec timestamps |
| `match_participants` | Participants par match (xuid, team) ⚠️ À CRÉER |
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

### Documentation IA (.ai/)

| Document | Contenu |
|----------|---------|
| `.ai/DATA_KILLER_VICTIM.md` | Guide killer/victim et antagonistes |
| `.ai/sprints/SPRINT_GAMERTAG_ROSTER_FIX.md` | Sprint correction gamertags et roster |
| `.ai/API_LIMITATIONS.md` | Limitations connues de l'API |

## Problèmes Connus

### 🔴 CRITIQUE - Données Manquantes en BDD (2026-02-05)

**Priorité** : HAUTE  
**Status** : 🔍 EN EXPLORATION

**Problèmes identifiés** :
1. Noms des cartes, modes et playlists non enregistrés (`playlist_name`, `map_name`, `pair_name`, `game_variant_name` sont NULL)
2. Noms des joueurs par match non récupérés correctement
3. Joueurs non affectés à l'équipe adverse
4. Nom de l'équipe adverse non récupéré
5. Valeurs "attendues" pour frags et morts non récupérées (`kills_expected`, `deaths_expected`, `assists_expected` sont NULL)

**Commit de référence** : `1a6115007272619985485be0f94cc69e6be5c2d2` (fonctionnait correctement)

**Documentation** :
- Diagnostic : `.ai/diagnostics/CRITICAL_DATA_MISSING_2026-02-05.md`
- Exploration : `.ai/explore/CRITICAL_DATA_MISSING_EXPLORATION.md`

**Fichiers concernés** :
- `src/data/sync/transformers.py` : Extraction des données depuis JSON
- `src/data/sync/engine.py` : Synchronisation et insertion en BDD
- `src/data/repositories/duckdb_repo.py` : Récupération depuis BDD

## Sprint en Cours

**Sprint Gamertag & Roster Fix** (2026-02-05)  
📄 `.ai/sprints/SPRINT_GAMERTAG_ROSTER_FIX.md`

Objectifs :
- Créer `match_participants` pour restaurer la logique coéquipiers
- Backfill `killer_victim_pairs` depuis `highlight_events`
- Corriger les gamertags corrompus (NUL chars)
- Intégrer les graphiques antagonistes dans l'UI

Tables concernées :
- `killer_victim_pairs` : ❌ Vide → À peupler
- `xuid_aliases` : ❌ Vide → À peupler
- `match_participants` : ❌ N'existe pas → À créer
- `antagonists` : ❌ Vide → À peupler

## Dernière Mise à Jour

**2026-02-05** : Sprint Gamertag & Roster Fix initié + Documentation killer_victim  
**2026-02-05** : 🔴 Problème critique identifié - Données manquantes en BDD (en exploration)  
**2026-02-01** : Phase 6 terminée - Documentation & Branding "LevelUp"
