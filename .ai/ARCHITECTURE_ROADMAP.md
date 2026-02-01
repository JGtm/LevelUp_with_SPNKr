# Roadmap Architecture - Migration DuckDB Unifiée

> Ce document trace l'évolution planifiée de l'architecture de données.
> Mis à jour : 2026-02-01 (Sprint 4.7 - Refonte Sync en cours)

---

## TL;DR - Architecture Cible

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     ARCHITECTURE v4 (DuckDB Unifié)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   data/players/{gamertag}/stats.duckdb                                      │
│   ════════════════════════════════════                                      │
│   ├── match_stats ─────────► Faits des matchs (remplace MatchCache)        │
│   ├── medals_earned ───────► Médailles par match                           │
│   ├── teammates_aggregate ─► Stats coéquipiers                             │
│   ├── antagonists ─────────► [NEW] Top killers/victimes                    │
│   ├── weapon_stats ────────► [NEW] Stats par arme                          │
│   ├── skill_history ───────► [NEW] Historique CSR par playlist             │
│   └── sessions ────────────► Sessions de jeu détectées                     │
│                                                                             │
│   data/warehouse/metadata.duckdb                                            │
│   ══════════════════════════════                                            │
│   ├── playlists ───────────► Définitions des playlists                     │
│   ├── maps ────────────────► Définitions des cartes                        │
│   ├── game_modes ──────────► Modes de jeu                                  │
│   ├── medal_definitions ───► Référentiel médailles                         │
│   └── career_ranks ────────► [NEW] Traductions des rangs (0-272)           │
│                                                                             │
│   data/archive/parquet/                                                     │
│   ════════════════════                                                      │
│   └── player={xuid}/ ──────► Cold storage (backup optionnel)               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Gains vs v1 :
• -70% complexité code (1 techno vs 3)
• Requêtes 10-20x plus rapides (DuckDB natif)
• Plus de redondance MatchCache/Parquet
• Transactions ACID partout
```

---

## Découvertes (2026-02-01)

### Données Existantes

| Fichier | Taille | Contenu |
|---------|--------|---------|
| `halo_unified.db` | 156 MB | DB unifiée existante (tentative précédente) |
| `spnkr_gt_Chocoboflor.db` | 15 MB | Legacy SQLite |
| `spnkr_gt_JGtm.db` | 62 MB | Legacy SQLite |
| `spnkr_gt_Madina97294.db` | 121 MB | Legacy SQLite |
| `spnkr_gt_XxDaemonGamerxX.db` | 17 MB | Legacy SQLite |
| `warehouse/metadata.db` | ~1 MB | Référentiels (496 lignes) |
| `warehouse/match_facts/` | ~7 fichiers | Parquet partitionné |

**Observation** : `halo_unified.db` est une DB SQLite unifiée existante. Avec DuckDB, cette approche devient optimale car DuckDB est OLAP-natif (vs SQLite qui est OLTP).

### Structure Créée

```
data/
├── players/              ✅ Créé
│   ├── Chocoboflor/      ✅
│   ├── JGtm/             ✅
│   ├── Madina97294/      ✅
│   └── XxDaemonGamerxX/  ✅
├── archive/              ✅ Créé
│   └── parquet/          ✅
└── warehouse/
    └── metadata.db       → À migrer vers .duckdb
```

---

## Phases de Migration

### Phase 1 : Stabilisation ✅ (Complète)

**Objectif** : Valider l'architecture hybride SQLite+Parquet+DuckDB

| Tâche | Statut | Livrable |
|-------|--------|----------|
| Tables de cache SQLite fonctionnelles | ✅ | `metadata.db` |
| Migration Parquet automatique après sync | ✅ | `match_facts/` |
| Fallback si Parquet indisponible | ✅ | `LegacyRepository` |
| Tests de non-régression UI | ✅ | `tests/test_hybrid_benchmark.py` |
| Benchmarks de performance documentés | ✅ | `scripts/benchmark_hybrid.py` |

---

### Phase 2 : Migration DuckDB Unifiée ✅ (Complète)

**Objectif** : Migrer vers DuckDB persisté comme moteur unique

| # | Tâche | Statut | Notes |
|---|-------|--------|-------|
| 2.1 | Créer structure `data/players/{gamertag}/` | ✅ | Dossiers créés |
| 2.2 | Mettre à jour `db_profiles.json` | ✅ | Version 2.1 avec nouveaux chemins |
| 2.3 | Créer script de migration métadonnées | ✅ | `metadata.db` → `metadata.duckdb` |
| 2.4 | Créer script de migration joueur | ✅ | SQLite → DuckDB |
| 2.5 | Adapter `DuckDBRepository` pour DuckDB natif | ✅ | Nouveau repository |
| 2.6 | Migrer les 4 joueurs existants | ✅ | ~250 MB total, 1372 matchs |

---

## Sprint Actuel : Migration DuckDB

### Sprint 2.1 : Scripts de Migration ✅ COMPLETE

| # | Tâche | Statut | Livrable |
|---|-------|--------|----------|
| S2.1.1 | Script migration métadonnées | ✅ | `scripts/migrate_metadata_to_duckdb.py` |
| S2.1.2 | Script migration joueur | ✅ | `scripts/migrate_player_to_duckdb.py` |
| S2.1.3 | Validation post-migration | ✅ | 12 tables, 1372 matchs migrés |

**Script migration métadonnées** :
```python
# scripts/migrate_metadata_to_duckdb.py
# 1. Lire metadata.db (SQLite)
# 2. Créer metadata.duckdb
# 3. Copier toutes les tables
# 4. Ajouter table career_ranks
# 5. Valider les données
```

**Script migration joueur** :
```python
# scripts/migrate_player_to_duckdb.py
# 1. Lire spnkr_gt_{gamertag}.db (SQLite)
# 2. Créer data/players/{gamertag}/stats.duckdb
# 3. Convertir MatchStats JSON → match_stats
# 4. Migrer TeammatesAggregate
# 5. Supprimer MatchCache (redondant)
# 6. Créer tables vides: antagonists, weapon_stats, skill_history
```

### Sprint 2.2 : Adapter le Code ✅ COMPLETE

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S2.2.1 | Créer `DuckDBRepository` | `src/data/repositories/duckdb_repo.py` | ✅ |
| S2.2.2 | Ajouter mode DUCKDB au factory | `src/data/repositories/factory.py` | ✅ |
| S2.2.3 | Adapter le bridge Streamlit | `src/data/integration/streamlit_bridge.py` | ✅ |
| S2.2.4 | Tests de non-régression | `tests/test_duckdb_repository.py` | ✅ |

**Nouvelles fonctions** :
- `DuckDBRepository` : Repository natif lisant depuis `stats.duckdb`
- `RepositoryMode.DUCKDB` : Nouveau mode pour l'architecture v4
- `get_repository_from_profile(gamertag)` : Création auto depuis `db_profiles.json`
- `get_repository_for_player(gamertag)` : Bridge Streamlit simplifié

### Sprint 2.3 : Nettoyage ✅ COMPLETE

| # | Tâche | Statut | Notes |
|---|-------|--------|-------|
| S2.3.1 | Nettoyer `db_profiles.json` | ✅ | Version 2.1, legacy_db_path supprimés |
| S2.3.2 | Créer dossiers joueurs manquants | ✅ | JGtm, Madina97294, Chocoboflor |
| S2.3.3 | Documenter code legacy | ✅ | Conservé pour rétrocompatibilité |

**Résumé des changements** :
- `db_profiles.json` passé en version 2.1 sans références legacy
- Dossiers `data/players/{gamertag}/` créés pour tous les joueurs
- `LegacyRepository` et factory documentés comme optionnels/dépréciés
- Les DBs legacy (`halo_unified.db`, `spnkr_gt_*.db`) étaient déjà absentes du repo

---

### Phase 3 : Enrichissement des Données ✅ (Complète)

**Objectif** : Ajouter des tables pour améliorer l'UX + stabiliser les calculs existants

| Nouvelle Table | Description | Utilisation | Source |
|---------------|-------------|-------------|--------|
| `antagonists` | Top 20 killers/victimes | Rivalités, matchups | HighlightEvents + validation |
| `weapon_stats` | Stats par arme | Analyse des armes | API weapon_core |
| `skill_history` | Historique CSR | Graphique progression | API playlist_csr |
| `career_ranks` | Traductions rangs | Localisation | ✅ Migré (JSON statique) |
| `match_events` | Timeline événements | Replays (optionnel) | API match_events |

**Schéma SQL** : Voir `docs/SQL_SCHEMA.md`

---

## Sprint Actuel : Phase 3 - Enrichissement

### Sprint 3.1 : Stabilisation Algorithme Antagonistes ✅ COMPLETE

**Problème identifié** : Le calcul des frags peut être instable avec des événements simultanés.

**Solution** : Validation par totaux officiels + tie-breaker par rang.

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S3.1.1 | Créer `load_match_players_stats()` | `src/db/loaders.py` | ✅ |
| S3.1.2 | Créer `validate_and_adjust_pairs()` | `src/analysis/killer_victim.py` | ✅ |
| S3.1.3 | Modifier `compute_personal_antagonists()` | `src/analysis/killer_victim.py` | ✅ |
| S3.1.4 | Mettre à jour les tests | `tests/test_killer_victim_antagonists.py` | ✅ |

**Algorithme amélioré** :
```
1. Reconstituer les paires killer→victim (existant)
2. Pour chaque joueur du match :
   - Calculer kills_reconstitués, deaths_reconstitués
   - Comparer avec kills_officiels, deaths_officiels
   - Si écart : marquer comme "incertain"
3. Pour les cas ambigus (égalité de frags par plusieurs adversaires) :
   - Tie-breaker = rang dans le match (meilleur classement = priorité)
4. Retourner résultat avec flag de confiance (is_validated, validation_notes)
```

**Nouvelles fonctions** :
- `load_match_players_stats(db_path, match_id)` : Charge kills/deaths/rank de tous les joueurs
- `validate_and_adjust_pairs(pairs, official_stats)` : Valide cohérence reconstitué vs officiel
- `AntagonistsResult.is_validated` : Flag de confiance
- `AntagonistsResult.validation_notes` : Notes explicatives sur la validation

### Sprint 3.2 : Agrégation et Persistance ✅ COMPLETE

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S3.2.1 | Créer `aggregate_antagonists()` | `src/analysis/antagonists.py` | ✅ |
| S3.2.2 | Créer script `populate_antagonists.py` | `scripts/populate_antagonists.py` | ✅ |
| S3.2.3 | Ajouter méthode `save_antagonists()` | `src/data/repositories/duckdb_repo.py` | ✅ |
| S3.2.4 | Tests d'intégration | `tests/test_antagonists_persistence.py` | ✅ |

**Implémentations réalisées** :
- `AntagonistEntry` : Dataclass pour une entrée agrégée (opponent_xuid, times_killed, times_killed_by, etc.)
- `AggregationResult` : Résultat avec méthodes `get_top_nemeses()`, `get_top_victims()`, `get_top_rivals()`
- `aggregate_antagonists()` : Agrège les résultats de `compute_personal_antagonists()` sur plusieurs matchs
- `DuckDBRepository.save_antagonists()` : Upsert dans la table antagonists avec gestion du replace
- `DuckDBRepository.load_antagonists()` : Chargement avec tri configurable
- `DuckDBRepository.get_top_nemeses()` / `get_top_victims()` : Helpers pour les requêtes fréquentes

### Sprint 3.3 : Enrichissement Mode Debug ✅ COMPLETE

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S3.3.1 | Afficher validation antagonistes en mode debug | `src/ui/pages/match_view_players.py` | ✅ |
| S3.3.2 | Afficher is_validated + validation_notes | `src/ui/pages/match_view_players.py` | ✅ |
| S3.3.3 | Indicateur visuel de confiance (✓/⚠) | `src/ui/pages/match_view_players.py` | ✅ |

**Implémentation réalisée** :
- Chargement des stats officielles via `load_match_players_stats()` avant `compute_personal_antagonists()`
- Passage du paramètre `official_stats` pour activer la validation
- Affichage de l'indicateur visuel (✓ Validé / ⚠ Non validé) en mode debug
- Affichage de `validation_notes` pour expliquer les écarts éventuels

> **Note** : La page "Mes Rivalités" initialement prévue est reportée (faible priorité).

---

### Phase 4 : Optimisations Avancées 🚧 (En cours)

**Objectif** : Améliorer la performance et l'efficacité de l'architecture DuckDB.

| Fonctionnalité | Description | Impact | Priorité |
|----------------|-------------|--------|----------|
| Vues matérialisées | Pré-calculer agrégations fréquentes | -50% temps requête | Haute |
| Optimisation N+1 | Corriger boucles de requêtes | -90% temps page | Haute |
| Lazy loading | Charger données à la demande | -80% RAM initiale | Haute |
| Compression Zstd | Natif DuckDB pour export/backup | -30% espace disque | Moyenne |
| Partitionnement temporel | Tables par année/saison | Requêtes historiques rapides | Basse |

---

## Sprint Actuel : Phase 4 - Optimisations

### Sprint 4.1 : Vues Matérialisées ✅ COMPLETE

**Problème identifié** : Les agrégations (stats par carte, par mode, par session) sont recalculées à chaque affichage.

**Solution** : Créer des tables de cache rafraîchies après chaque sync.

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S4.1.1 | Créer table `mv_map_stats` | `src/data/repositories/duckdb_repo.py` | ✅ |
| S4.1.2 | Créer table `mv_mode_category_stats` | `src/data/repositories/duckdb_repo.py` | ✅ |
| S4.1.3 | Créer table `mv_session_stats` | `src/data/repositories/duckdb_repo.py` | ✅ |
| S4.1.4 | Créer table `mv_global_stats` | `src/data/repositories/duckdb_repo.py` | ✅ |
| S4.1.5 | Méthode `refresh_materialized_views()` | `src/data/repositories/duckdb_repo.py` | ✅ |
| S4.1.6 | Appeler refresh après sync | `scripts/sync.py` | ✅ |
| S4.1.7 | Tests de performance | `tests/test_materialized_views.py` | ✅ |

**Implémentations réalisées** :
- Tables `mv_map_stats`, `mv_mode_category_stats`, `mv_session_stats`, `mv_global_stats`
- Méthode `refresh_materialized_views()` pour rafraîchir toutes les vues en une seule opération
- Méthodes de lecture : `get_map_stats()`, `get_mode_category_stats()`, `get_global_stats()`, `get_session_stats()`
- Méthode `has_materialized_views()` pour vérifier si les vues sont disponibles
- 13 tests unitaires couvrant la création, le refresh, et les performances

**Schémas SQL** :

```sql
-- mv_map_stats : Stats par carte
CREATE TABLE IF NOT EXISTS mv_map_stats (
    map_id VARCHAR PRIMARY KEY,
    map_name VARCHAR,
    matches_played INTEGER,
    wins INTEGER,
    losses INTEGER,
    ties INTEGER,
    avg_kills DOUBLE,
    avg_deaths DOUBLE,
    avg_assists DOUBLE,
    avg_accuracy DOUBLE,
    avg_kda DOUBLE,
    win_rate DOUBLE,
    updated_at TIMESTAMP
);

-- mv_mode_category_stats : Stats par catégorie de mode
CREATE TABLE IF NOT EXISTS mv_mode_category_stats (
    mode_category VARCHAR PRIMARY KEY,
    matches_played INTEGER,
    avg_kills DOUBLE,
    avg_deaths DOUBLE,
    avg_assists DOUBLE,
    avg_ratio DOUBLE,
    updated_at TIMESTAMP
);

-- mv_session_stats : Stats par session (pré-calculées)
CREATE TABLE IF NOT EXISTS mv_session_stats (
    session_id INTEGER PRIMARY KEY,
    match_count INTEGER,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    kd_ratio DOUBLE,
    win_rate DOUBLE,
    avg_accuracy DOUBLE,
    avg_life_seconds DOUBLE,
    is_with_friends BOOLEAN,
    updated_at TIMESTAMP
);

-- mv_global_stats : Stats globales du joueur
CREATE TABLE IF NOT EXISTS mv_global_stats (
    stat_key VARCHAR PRIMARY KEY,
    stat_value DOUBLE,
    updated_at TIMESTAMP
);
```

**Implémentation** :

```python
def refresh_materialized_views(self) -> None:
    """Rafraîchit toutes les vues matérialisées après sync."""
    with self._get_connection() as conn:
        # mv_map_stats
        conn.execute("""
            INSERT OR REPLACE INTO mv_map_stats
            SELECT 
                map_id, map_name, COUNT(*) as matches_played,
                SUM(CASE WHEN outcome = 2 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 3 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 1 THEN 1 ELSE 0 END) as ties,
                AVG(kills), AVG(deaths), AVG(assists), AVG(accuracy),
                AVG(kda), 
                SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0.0 END) / COUNT(*),
                CURRENT_TIMESTAMP
            FROM match_stats
            GROUP BY map_id, map_name
        """)
        # ... autres tables
```

### Sprint 4.2 : Optimisation Requêtes N+1 ✅ COMPLETE

**Problème identifié** : `match_history.py` faisait une requête DB par match pour charger le MMR (boucle N+1).

**Impact** : Pour 500 matchs = 500 requêtes → très lent.

**Solution découverte** : Les colonnes `team_mmr` et `enemy_mmr` étaient DÉJÀ chargées par `load_matches()` dans le DataFrame ! La boucle N+1 était donc complètement redondante.

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S4.2.1 | Créer `load_match_mmr_batch()` | `src/data/repositories/duckdb_repo.py` | ✅ |
| S4.2.2 | Supprimer la boucle N+1 | `src/ui/pages/match_history.py` | ✅ |
| S4.2.3 | Optimiser chargement coéquipiers | `src/ui/pages/teammates.py` | ⏳ (Futur sprint) |
| S4.2.4 | Tests de performance | `tests/test_materialized_views.py` | ✅ |

**Changements réalisés** :

```python
# AVANT (N+1) - match_history.py (SUPPRIMÉ)
with st.spinner("Chargement des MMR (équipe/adverse)…"):
    def _mmr_tuple(match_id: str):
        pm = cached_load_player_match_result(db_path, str(match_id), xuid.strip(), db_key=db_key)
        # ... 1 requête par match = 500+ requêtes

# APRÈS (Optimisé) - Utilisation directe des colonnes existantes
if "team_mmr" not in dff_table.columns:
    dff_table["team_mmr"] = None
dff_table["delta_mmr"] = pd.to_numeric(
    dff_table["team_mmr"], errors="coerce"
) - pd.to_numeric(dff_table["enemy_mmr"], errors="coerce")
```

**Impact** :
- Suppression du spinner "Chargement des MMR" (plus de latence)
- De 500+ requêtes à 0 requête supplémentaire
- Gain estimé : ~90% de temps sur la page Historique

### Sprint 4.3 : Lazy Loading et Pagination ✅ COMPLETE

**Problème identifié** : `load_matches()` charge tous les matchs en mémoire (~2000 matchs × 50 colonnes).

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S4.3.1 | Ajouter `limit`/`offset` à `load_matches()` | `src/data/repositories/duckdb_repo.py` | ✅ |
| S4.3.2 | Créer `load_recent_matches(limit)` | `src/data/repositories/duckdb_repo.py` | ✅ |
| S4.3.3 | Fonctions de cache pour pagination | `src/ui/cache.py` | ✅ |
| S4.3.4 | Chargement par chunks temporels | `src/ui/cache.py` | ✅ |
| S4.3.5 | Tests de lazy loading | `tests/test_lazy_loading.py` | ✅ |

**Implémentations réalisées** :
- `load_matches(limit=N, offset=M)` : Pagination SQL native
- `load_recent_matches(limit=50)` : Chargement des matchs récents (tri DESC)
- `load_matches_paginated(page, page_size)` : Pagination avec total de pages
- `cached_load_recent_matches()` : Cache Streamlit pour lazy loading
- `cached_load_matches_paginated()` : Cache Streamlit pour pagination
- `cached_get_match_count_duckdb()` : Compte total des matchs

**Stratégie** :

1. **Au démarrage** : Charger uniquement les métadonnées légères + 50 derniers matchs
2. **Navigation** : Charger les matchs à la demande (pagination par 50)
3. **Cache Streamlit** : Utiliser `@st.cache_data` avec TTL adapté (5 min)

```python
@st.cache_data(ttl=300)
def cached_load_recent_matches(player_db_path, xuid, limit=50, db_key=None):
    """Charge les N matchs avec pagination lazy."""
    repo = DuckDBRepository(player_db_path, xuid)
    return repo.load_recent_matches(limit=limit)
```

### Sprint 4.4 : Compression Zstd et Export ✅ COMPLETE

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S4.4.1 | Script backup Zstd | `scripts/backup_player.py` | ✅ |
| S4.4.2 | Script restore depuis Parquet | `scripts/restore_player.py` | ✅ |
| S4.4.3 | Documentation export/import | `docs/BACKUP_RESTORE.md` | ✅ |

**Implémentations réalisées** :
- `backup_player.py` : Export vers Parquet avec compression Zstd (niveaux 1-22)
- `restore_player.py` : Import depuis Parquet avec options --replace, --dry-run
- Documentation complète avec exemples, cas d'usage, et dépannage

**Export avec compression optimale** :

```bash
# Backup d'un joueur
python scripts/backup_player.py --gamertag Chocoboflor

# Backup de tous les joueurs
python scripts/backup_player.py --all --compression-level 15

# Restauration
python scripts/restore_player.py --gamertag Chocoboflor --backup ./backups/Chocoboflor
```

```sql
-- Export compressé (compression 9 = défaut recommandé)
COPY match_stats TO 'backup/match_stats.parquet' 
    (FORMAT PARQUET, COMPRESSION 'zstd', COMPRESSION_LEVEL 9);

-- Import depuis Parquet compressé
COPY match_stats FROM 'backup/match_stats.parquet';
```

### Sprint 4.5 : Partitionnement Temporel ✅ COMPLETE

**Seuil** : Implémenter si > 5000 matchs ou > 1 an d'historique.

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S4.5.1 | Script archivage saison | `scripts/archive_season.py` | ✅ |
| S4.5.2 | Vue unifiée stats + archives | `src/data/repositories/duckdb_repo.py` | ✅ |
| S4.5.3 | Tests partitionnement temporel | `tests/test_season_archive.py` | ✅ |

**Implémentations réalisées** :

1. **Script `archive_season.py`** :
   - Archivage par année ou par date de cutoff vers Parquet compressé Zstd
   - Options : `--cutoff`, `--older-than-days`, `--dry-run`, `--delete`
   - Archivage automatique par année si plusieurs années de données
   - Index des archives (`archive_index.json`) pour traçabilité
   - Statistiques et recommandations intégrées

2. **Méthodes `DuckDBRepository`** :
   - `get_archive_info()` : Informations sur les archives existantes
   - `load_matches_from_archives()` : Charge les matchs depuis Parquet
   - `load_all_matches_unified()` : Vue unifiée DB + archives (avec déduplication)
   - `get_total_match_count_with_archives()` : Compte total (DB + archives)

3. **Tests** :
   - Tests d'archivage (dry-run, création fichiers, par année)
   - Tests de chargement depuis archives
   - Tests de vue unifiée avec déduplication
   - Tests de filtrage par dates

**Structure créée** :

```
data/players/{gamertag}/
├── stats.duckdb          # Données récentes (saison courante)
└── archive/
    ├── matches_2023.parquet    # Matchs 2023 archivés
    ├── matches_2024.parquet    # Matchs 2024 archivés
    └── archive_index.json      # Index avec métadonnées
```

**Usage** :

```bash
# Lister les statistiques et archives existantes
python scripts/archive_season.py --gamertag Chocoboflor --list-archives

# Archiver les matchs avant 2024 (dry-run)
python scripts/archive_season.py --gamertag Chocoboflor --cutoff 2024-01-01 --dry-run

# Archiver les matchs de plus d'un an
python scripts/archive_season.py --gamertag Chocoboflor --older-than-days 365

# Vue unifiée dans le code
repo = DuckDBRepository(db_path, xuid)
all_matches = repo.load_all_matches_unified()  # DB + archives
```

---

### Sprint 4.6 : Audit et Nettoyage Pre-Phase 5 ✅ COMPLETE

**Objectif** : Identifier et nettoyer les reliquats, redondances et code obsolète avant de passer à la Phase 5.

#### Audit Réalisé (2026-02-01)

Exploration exhaustive du codebase pour vérifier l'adoption de l'architecture DuckDB/Parquet.

##### 1. Reliquats SQLite à Migrer (50+ occurrences)

| Module | Problème | Priorité | Action |
|--------|----------|----------|--------|
| `src/ui/multiplayer.py` | 4 connexions SQLite directes | Haute | Migrer vers `DuckDBRepository` |
| `src/ui/aliases.py` | Lit `XuidAliases` via SQLite | Haute | Migrer vers DuckDB |
| `src/data/query/engine.py` | Référence `metadata.db` | Haute | Changer en `metadata.duckdb` |
| `src/data/repositories/hybrid.py` | Utilise `SQLiteMetadataStore` | Moyenne | Créer `DuckDBMetadataStore` |
| `scripts/ingest_halo_data.py` | Ingestion vers SQLite | Moyenne | Migrer vers DuckDB |
| `scripts/compute_historical_performance.py` | Accès SQLite direct | Moyenne | Migrer vers repository |
| `scripts/refetch_film_roster.py` | Accès SQLite direct | Basse | Migrer vers repository |
| `scripts/generate_medals_fr.py` | Accès SQLite direct | Basse | Migrer vers DuckDB |

**Fichiers legacy à conserver** (rétrocompatibilité) :
- `src/db/loaders.py`, `loaders_cached.py` — Legacy repository
- `scripts/sync.py`, `merge_databases.py`, `spnkr_import_db.py` — Scripts legacy
- `openspartan_launcher.py` — Support des anciennes DBs

##### 2. Redondances de Code Identifiées

| Pattern | Occurrences | Solution |
|---------|-------------|----------|
| `load_matches()` | 5 implémentations | Extraire construction filtres SQL → `filters.py` |
| `get_player_db_path()` | 4 scripts | Créer `src/utils/paths.py` |
| Config DuckDB (`memory_limit`, `attach`) | 4 endroits | Créer `duckdb_config.py` |
| Constantes de session | 2 définitions | Importer depuis `sessions.py` |
| Chemins hardcodés | 10+ occurrences | Centraliser dans `src/config/paths.py` |

**Nouveaux modules à créer** :
```
src/utils/paths.py                                  # Chemins centralisés
src/data/infrastructure/database/duckdb_config.py  # Config DuckDB partagée
src/data/query/filters.py                          # Construction filtres WHERE
src/config/defaults.py                             # Constantes par défaut
```

##### 3. État d'Adoption Architecture DuckDB/Parquet

| Catégorie | Conformité | Problèmes |
|-----------|------------|-----------|
| Repositories | ✅ 100% | Aucun |
| UI Pages | ⚠️ 85% | 2 pages avec accès directs |
| UI Cache | ✅ 95% | Bon |
| Analysis | ✅ 100% | Fonctions pures, aucun accès direct |
| Scripts | ⚠️ 60% | Beaucoup d'accès directs (certains légitimes) |

**Pages UI non-conformes** :
- `src/ui/pages/match_view_players.py` → Import direct `load_match_players_stats`
- `src/ui/pages/session_compare.py` → Import direct `get_connection`

##### 4. Code Mort à Supprimer

| Fichier | Lignes | Raison |
|---------|--------|--------|
| `src/app/navigation.py` | 292 | Remplacé par `page_router.py` |
| `src/data/query/examples.py` | 443 | Classe `QueryExamples` jamais importée |

##### 5. Commentaires Obsolètes (11 occurrences)

Fichiers avec docstrings/commentaires mentionnant "SQLite" ou "metadata.db" à mettre à jour :
- `src/db/loaders.py` (ligne 1)
- `src/data/__init__.py` (ligne 2)
- `src/data/repositories/hybrid.py` (lignes 2, 7)
- `src/data/infrastructure/database/sqlite_metadata.py` (lignes 2, 6)
- `scripts/ingest_halo_data.py` (lignes 3, 133, 139, 159)
- `scripts/sync.py` (ligne 1003)

#### Plan de Nettoyage

| # | Tâche | Fichier(s) | Priorité | Statut |
|---|-------|------------|----------|--------|
| S4.6.1 | Supprimer `navigation.py` (code mort) | `src/app/navigation.py`, `src/app/__init__.py` | Haute | ✅ |
| S4.6.2 | Supprimer `examples.py` (code mort) | `src/data/query/examples.py` | Haute | ✅ |
| S4.6.3 | Migrer `multiplayer.py` vers DuckDB | `src/ui/multiplayer.py` | Haute | ✅ |
| S4.6.4 | Migrer `aliases.py` vers DuckDB | `src/ui/aliases.py` | Haute | ✅ |
| S4.6.5 | Corriger `match_view_players.py` | `src/ui/pages/match_view_players.py` | Haute | ✅ |
| S4.6.6 | Corriger `session_compare.py` | `src/ui/pages/session_compare.py` | Haute | ✅ |
| S4.6.7 | Créer `src/utils/paths.py` | `src/utils/paths.py` | Moyenne | ✅ |
| S4.6.8 | Créer `duckdb_config.py` | `src/data/infrastructure/database/duckdb_config.py` | Moyenne | ✅ |
| S4.6.9 | Migrer `metadata.db` → `metadata.duckdb` | Multiples fichiers | Moyenne | ✅ |
| S4.6.10 | Mettre à jour commentaires obsolètes | 11 fichiers | Basse | ✅ |

**Implémentations réalisées** :

1. **Code mort supprimé** (~30 KB) :
   - `src/app/navigation.py` : Remplacé par `page_router.py`
   - `src/data/query/examples.py` : Classe `QueryExamples` jamais utilisée

2. **Modules migrés vers DuckDB** :
   - `src/ui/multiplayer.py` : Détection auto SQLite/DuckDB, fallback gracieux
   - `src/ui/aliases.py` : Support DuckDB pour table `xuid_aliases`

3. **Imports directs corrigés** :
   - `match_view_players.py` : `load_match_players_stats` retourne [] pour DuckDB
   - `session_compare.py` : `get_connection` remplacé par détection auto

4. **Nouveaux modules créés** :
   - `src/utils/paths.py` : Chemins centralisés (REPO_ROOT, PLAYERS_DIR, etc.)
   - `src/data/infrastructure/database/duckdb_config.py` : Config DuckDB partagée

5. **Références metadata.db migrées** :
   - `src/data/query/engine.py` : Priorité metadata.duckdb avec fallback
   - `src/data/repositories/hybrid.py` : Idem
   - `src/data/repositories/shadow.py` : Idem

6. **Commentaires mis à jour** :
   - `src/db/loaders.py` : Docstring indiquant le support DuckDB limité
   - `src/data/repositories/hybrid.py` : Docstring mis à jour

---

### Sprint 4.7 : Refonte Système de Synchronisation 📋 (Avant Phase 5)

**Objectif** : Simplifier le pipeline de synchronisation en passant directement de l'API SPNKr à DuckDB, sans intermédiaires.

**Spécification détaillée** : `.ai/features/SYNC_REFACTORING_SPEC.md`

#### Problème Actuel

Le pipeline actuel est trop complexe (4 étapes, 8+ fichiers) :

```
API SPNKr → SQLite (JSON) → SQLite (Cache) → Parquet → DuckDB
```

| Fichier | Verdict |
|---------|---------|
| `scripts/spnkr_import_db.py` | À refactorer |
| `scripts/sync.py` | À refactorer |
| `scripts/migrate_to_cache.py` | **OBSOLÈTE** |
| `scripts/migrate_to_parquet.py` | **OBSOLÈTE** |
| `src/db/loaders.py` | **À DÉPRÉCIER** |
| `src/data/repositories/shadow.py` | **OBSOLÈTE** |

#### Architecture Cible

```
API SPNKr
    │
    ▼
DuckDBSyncEngine (src/data/sync/)
├── api_client.py      # SPNKr wrapper async
├── transformers.py    # API JSON → DuckDB rows  
├── engine.py          # Orchestrateur
└── delta.py           # Logique incrémentale
    │
    ▼
data/players/{gamertag}/stats.duckdb
├── match_stats
├── player_match_stats  # MMR/skill (nouveau)
├── highlight_events    # (nouveau)
├── xuid_aliases        # (nouveau)
└── sync_meta
```

#### Sprint 4.7.1 : Core Sync Engine ✅ COMPLETE

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S4.7.1.1 | Créer structure `src/data/sync/` | `__init__.py`, `models.py` | ✅ |
| S4.7.1.2 | Implémenter `SPNKrAPIClient` | `api_client.py` | ✅ |
| S4.7.1.3 | Implémenter transformers | `transformers.py` | ✅ |
| S4.7.1.4 | Implémenter `DuckDBSyncEngine` | `engine.py` | ✅ |
| S4.7.1.5 | Tests unitaires | `tests/test_sync_engine.py` | ✅ |

**Implémentations réalisées** :

1. **`src/data/sync/models.py`** :
   - `SyncOptions` : Options de synchronisation (match_type, max_matches, with_skill, etc.)
   - `SyncResult` : Résultat avec compteurs, erreurs, et méthode `to_message()`
   - `MatchStatsRow`, `PlayerMatchStatsRow`, `HighlightEventRow`, `XuidAliasRow` : Dataclasses pour DuckDB

2. **`src/data/sync/api_client.py`** :
   - `SPNKrAPIClient` : Wrapper async avec rate limiting, retry, et gestion des tokens
   - `get_tokens_from_env()` : Récupération des tokens depuis env (manuel ou OAuth Azure)
   - Support des highlight events via `spnkr.film`

3. **`src/data/sync/transformers.py`** :
   - `transform_match_stats()` : JSON API → MatchStatsRow
   - `transform_skill_stats()` : JSON skill → PlayerMatchStatsRow
   - `transform_highlight_events()` : Events → [HighlightEventRow]
   - `extract_aliases()` : JSON match → [XuidAliasRow]
   - Helpers de parsing : `_safe_float`, `_safe_int`, `_parse_iso_utc`

4. **`src/data/sync/engine.py`** :
   - `DuckDBSyncEngine` : Orchestrateur complet API → DuckDB
   - `sync_delta()` : Synchronisation incrémentale (arrêt au premier match connu)
   - `sync_full()` : Synchronisation complète avec backfill
   - Insertion directe dans DuckDB (match_stats, player_match_stats, highlight_events, xuid_aliases)
   - Refresh automatique des vues matérialisées après sync

5. **`tests/test_sync_engine.py`** :
   - Tests pour SyncOptions, SyncResult
   - Tests pour tous les transformers
   - Tests des helpers de parsing
   - Pipeline complet de transformation

#### Sprint 4.7.2 : Intégration ✅ COMPLETE

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S4.7.2.1 | Adapter `scripts/sync.py` CLI | `scripts/sync.py` | ✅ |
| S4.7.2.2 | Adapter `src/ui/sync.py` | `src/ui/sync.py` | ✅ |
| S4.7.2.3 | Adapter `openspartan_launcher.py` | `openspartan_launcher.py` | ⏳ (Optionnel) |
| S4.7.2.4 | Tests d'intégration | `tests/test_sync_integration.py` | ⏳ (Optionnel) |

**Implémentations réalisées** :

1. **`scripts/sync.py`** :
   - `sync_delta()` et `sync_full()` détectent automatiquement si le joueur a une DB DuckDB v4
   - Nouvelle fonction `_try_sync_duckdb()` pour basculer vers le nouveau pipeline
   - Fallback transparent vers le pipeline legacy si DuckDB non disponible

2. **`src/ui/sync.py`** :
   - `is_duckdb_player()` : Détecte si un joueur utilise l'architecture v4
   - `get_player_duckdb_path()` : Retourne le chemin vers stats.duckdb
   - `sync_player_duckdb()` : Synchronisation via DuckDBSyncEngine (sync wrapper)
   - `sync_player_duckdb_async()` : Version async native
   - `sync_player_auto()` : Détection automatique DuckDB vs legacy

#### Sprint 4.7.3 : Migration Historique ✅ COMPLETE

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S4.7.3.1 | Migrer HighlightEvents → DuckDB | `scripts/migrate_highlight_events.py` | ✅ |
| S4.7.3.2 | Migrer PlayerMatchStats → DuckDB | `scripts/migrate_player_match_stats.py` | ✅ |
| S4.7.3.3 | Migrer XuidAliases → DuckDB | Inclus dans `migrate_all_to_duckdb.py` | ✅ |
| S4.7.3.4 | Script unifié | `scripts/migrate_all_to_duckdb.py` | ✅ |

**Implémentations réalisées** :

1. **`scripts/migrate_highlight_events.py`** :
   - Lit la table `HighlightEvents` (MatchId + ResponseBody JSON) depuis SQLite
   - Parse chaque event JSON et extrait : event_type, time_ms, xuid, gamertag, type_hint
   - Insère dans la table DuckDB `highlight_events` avec raw_json pour les données complètes
   - Options : `--gamertag`, `--all`, `--dry-run`, `--verbose`

2. **`scripts/migrate_player_match_stats.py`** :
   - Lit la table `PlayerMatchStats` depuis SQLite
   - Extrait les données MMR/skill pour le joueur : team_mmr, enemy_mmr, kills/deaths/assists expected/stddev
   - Insère dans la table DuckDB `player_match_stats`
   - Options : `--gamertag`, `--all`, `--dry-run`, `--verbose`

3. **`scripts/migrate_all_to_duckdb.py`** :
   - Script unifié qui exécute toutes les migrations en une seule commande
   - Migre : HighlightEvents, PlayerMatchStats, XuidAliases
   - Extrait les XuidAliases depuis plusieurs sources : table XuidAliases, table Players, MatchStats
   - Met à jour `sync_meta` avec les métadonnées de migration
   - Options : `--gamertag`, `--all`, `--dry-run`, `--skip-matchcache`, `--verbose`

**Usage** :

```bash
# Migrer toutes les données d'un joueur
python scripts/migrate_all_to_duckdb.py --gamertag Chocoboflor

# Migrer tous les joueurs
python scripts/migrate_all_to_duckdb.py --all

# Dry-run pour vérifier avant migration
python scripts/migrate_all_to_duckdb.py --all --dry-run

# Migrations individuelles
python scripts/migrate_highlight_events.py --gamertag JGtm
python scripts/migrate_player_match_stats.py --gamertag JGtm
```

#### Sprint 4.7.4 : Nettoyage ✅

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S4.7.4.1 | Marquer obsolète | `src/db/loaders.py`, `loaders_cached.py` | ✅ |
| S4.7.4.2 | Archiver scripts obsolètes | `scripts/_obsolete/migrate_to_*.py` | ✅ |
| S4.7.4.3 | MAJ documentation | `ARCHITECTURE_ROADMAP.md`, `thought_log.md` | ✅ |
| S4.7.4.4 | Déprécier ShadowRepository | `src/data/repositories/shadow.py` | ⚠️ (encore utilisé) |

**Notes S4.7.4.4** : `ShadowRepository` est encore utilisé par 10+ fichiers (factory, sync, tests...).
Plan de dépréciation : marquer obsolète dans Sprint 4.8, supprimer après migration complète des usages vers `DuckDBRepository`.

#### Sprint 4.8 : Suppression ShadowRepository ✅

**Objectif** : Éliminer `ShadowRepository` et finaliser la migration vers `DuckDBRepository`.

**Prérequis** : Sprint 4.7.4 (Nettoyage) terminé.

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S4.8.1 | Migrer factory.py vers DuckDBRepository | `src/data/repositories/factory.py` | ✅ |
| S4.8.2 | Migrer sync.py vers DuckDBRepository | `scripts/sync.py` | ✅ |
| S4.8.3 | Migrer streamlit_bridge.py | `src/data/integration/streamlit_bridge.py` | ✅ |
| S4.8.4 | Migrer settings.py | `src/ui/pages/settings.py` | ✅ |
| S4.8.5 | Supprimer HybridRepository | `src/data/repositories/hybrid.py` | ✅ |
| S4.8.6 | Supprimer ShadowRepository | `src/data/repositories/shadow.py` | ✅ |
| S4.8.7 | Supprimer LegacyRepository | `src/data/repositories/legacy.py` | ✅ |
| S4.8.8 | Nettoyer __init__.py exports | `src/data/repositories/__init__.py` | ✅ |
| S4.8.9 | MAJ tests (supprimer tests obsolètes) | `tests/test_hybrid_benchmark.py`, etc. | ✅ |
| S4.8.10 | Supprimer ParquetWriter | `src/data/infrastructure/parquet/` | ⚠️ Gardé (QueryEngine) |

**Fichiers supprimés** :

```
src/data/repositories/shadow.py      # ✅ Supprimé
src/data/repositories/hybrid.py      # ✅ Supprimé
src/data/repositories/legacy.py      # ✅ Supprimé
tests/test_hybrid_benchmark.py       # ✅ Supprimé
scripts/benchmark_hybrid.py          # ✅ Supprimé
```

**Fichiers conservés (utilisés par QueryEngine)** :

```
src/data/infrastructure/parquet/     # Gardé pour archivage/export
src/db/loaders.py                    # Gardé pour scripts utilitaires
src/db/loaders_cached.py             # Gardé pour scripts utilitaires
```

**Validation** :
- [x] Tous les tests passent avec DuckDBRepository uniquement
- [x] L'app Streamlit fonctionne sans imports legacy
- [x] Modes legacy/shadow/hybrid lèvent ValueError

---

#### Décisions Architecturales (Sprint 4.7)

| Question | Décision | Justification |
|----------|----------|---------------|
| Données historiques | Migrer TOUT | HighlightEvents, PlayerMatchStats, Aliases |
| Parquet | Optionnel (archivage) | DuckDB suffit pour l'analytique |
| Grunt API | Phase 5 | Comparaison SPNKr vs Grunt à faire |
| DB unifiée vs multi | Multi-joueurs | Réactivité + isolation par joueur |

#### Parquet : Verdict Final

**Parquet n'est plus nécessaire comme format intermédiaire** car :
1. DuckDB lit nativement les fichiers Parquet si besoin
2. On n'a plus de flux SQLite → Parquet → DuckDB
3. DuckDB offre les mêmes perfs analytiques avec transactions ACID

**Conserver Parquet uniquement pour** :
- **Export/Backup** : Archivage annuel (`scripts/archive_season.py`)
- **Interopérabilité** : Partage de données avec outils externes

**Action** : Supprimer `migrate_to_parquet.py` du workflow automatique.

---

### Phase 5 : Enrichissement Visuel & API Complémentaires 📋 (Futur)

**Objectif** : Visualisations avancées + données complémentaires (Career Rank, Weapon Stats).

**Prérequis** : Sprint 4.7 (Refonte Sync) terminé.

#### Analyse Comparative SPNKr vs Grunt

> Analyse détaillée : `.ai/features/API_COMPARISON_SPNKR_GRUNT.md`

| Critère | SPNKr | Grunt | Verdict |
|---------|-------|-------|---------|
| **Langage** | Python (natif) | C# (bridge requis) | **SPNKr** |
| **Intégration** | ✅ Déjà fait | ❌ À implémenter | **SPNKr** |
| **Endpoints core** | ✅ Complet | ✅ Complet | Égal |
| **Highlight Events** | ✅ `film` module | ❓ Non documenté | **SPNKr** |
| **Career Rank** | ⚠️ Partiel | ✅ Endpoint dédié | **Grunt** |
| **Service Record** | ❓ Non trouvé | ✅ Disponible | **Grunt** |
| **Effort intégration** | 0 (existant) | 2-3 semaines | **SPNKr** |

**Recommandation** : **Continuer avec SPNKr** (score 4.15/5 vs 3.45/5)

**Stratégie hybride** (optionnelle) : Bridge .NET minimal pour Career Rank si demandé.

#### Sprint 5.0 : Validation Post-Refactoring ⏳

| # | Tâche | Objectif | Statut |
|---|-------|----------|--------|
| S5.0.1 | Benchmark sync 1000 matchs | Stabilité SPNKr | ⏳ |
| S5.0.2 | Test rate limiting 10 req/s | Limites API | ⏳ |
| S5.0.3 | Test token refresh 24h | Durabilité auth | ⏳ |
| S5.0.4 | Comparaison données vs HaloWaypoint | Complétude | ⏳ |

**Métriques cibles** :
- Taux d'erreurs < 1%
- Latence moyenne < 300ms
- Token refresh 100% OK
- Données manquantes < 5%

#### Sprint 5.1 : Career Rank & Stats Armes ✅ COMPLETE

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S5.1.1 | Endpoint Career Rank via SPNKr | `src/data/sync/api_client.py` | ✅ |
| S5.1.2 | Récupérer Spartan ID + adornment | `src/data/sync/api_client.py` | ✅ |
| S5.1.3 | Explorer weapon_core dans match stats | `src/data/sync/transformers.py` | ✅ |
| S5.1.4 | Persister career_progression en BDD | `src/data/sync/engine.py` | ✅ |
| S5.1.5 | (Optionnel) Bridge Grunt pour Service Record | `scripts/grunt_bridge.py` | ⏳ (Reporté) |

**Implémentations réalisées** :

1. **Endpoint Career Rank** (`api_client.py`) :
   - `get_career_rank_progression(xuid)` : Récupère les données depuis l'API economy
   - `get_match_count(xuid)` : Récupère le nombre total de matchs
   - `get_player_customization(xuid)` : Récupère les données Spartan (armure, couleurs)
   - Parsing automatique des rangs (Bronze → Hero Legend, rangs 1-272)

2. **Modèles CareerRank** (`models.py`) :
   - `CareerRankData` : Données complètes avec progression calculée
   - `CareerRankRow` : Ligne pour la table DuckDB
   - `WeaponStatsRow` : Stats d'armes par match
   - `WeaponAggregateRow` : Stats agrégées par arme

3. **Engine Sync Career Rank** (`engine.py`) :
   - Table `career_progression` créée dans le schéma
   - `sync_career_rank()` : Récupère et sauvegarde la progression
   - `get_career_rank_history()` : Historique de progression
   - `get_latest_career_rank()` : Dernier rang enregistré

4. **Extraction Stats Armes** (`transformers.py`) :
   - `extract_weapon_stats()` : Extrait les stats d'armes d'un match
   - `has_weapon_stats()` : Vérifie la disponibilité des données
   - Support des formats WeaponStats, weapon_core, Weapons

**Tables cibles** :

```sql
-- career_progression (historique des rangs)
CREATE TABLE career_progression (
    id INTEGER PRIMARY KEY,
    xuid VARCHAR NOT NULL,
    rank INTEGER NOT NULL,
    rank_name VARCHAR,
    rank_tier VARCHAR,
    current_xp INTEGER,
    xp_for_next_rank INTEGER,
    xp_total INTEGER,
    is_max_rank BOOLEAN,
    adornment_path VARCHAR,
    recorded_at TIMESTAMP
);

-- weapon_match_stats (stats par match)
CREATE TABLE weapon_match_stats (
    match_id VARCHAR,
    xuid VARCHAR,
    weapon_id VARCHAR,
    weapon_name VARCHAR,
    kills INTEGER,
    deaths INTEGER,
    headshot_kills INTEGER,
    shots_fired INTEGER,
    shots_hit INTEGER,
    damage_dealt DOUBLE,
    time_held_seconds DOUBLE,
    PRIMARY KEY (match_id, xuid, weapon_id)
);
```

**Objectif citations** : Permettre des citations contextuelles comme "Tu as fait X kills avec le BR cette session".

#### Sprint 5.2 : Correctifs Prioritaires

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S5.2.1 | Corriger modes/playlists (Madina97294) | `src/data/parsers/` | ⏳ |
| S5.2.2 | Réparer synchro via app | `src/api/sync.py` | ⏳ |
| S5.2.3 | Association matchs ↔ vidéos capturées | `src/ui/pages/match_view.py` | ⏳ |
| S5.2.4 | Script thumbnails animés pour vidéos | `scripts/generate_thumbnails.py` | ⏳ |

#### Sprint 5.3 : Graphes Radar & Étiquettes

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S5.3.1 | Graphe radar "Stats par minute" | `src/ui/pages/teammates.py` | ⏳ |
| S5.3.2 | Graphe radar Objectif/Frags/Morts/Assists | `src/ui/components/radar_chart.py` | ⏳ |
| S5.3.3 | Étiquettes valeurs extrêmes sur graphes | `src/ui/components/charts.py` | ⏳ |
| S5.3.4 | Intégrer note de performance (TrueSkill) | `src/analysis/performance.py` | ⏳ |

**Source** : [Reddit - Halo Query MMR](https://www.reddit.com/r/CompetitiveHalo/comments/19f97ir/halo_query_a_new_stats_site_to_see_your_mmr/)

#### Sprint 5.4 : Nouvelles Représentations Statistiques

| # | Tâche | Description | Statut |
|---|-------|-------------|--------|
| S5.4.1 | Frags parfaits sur graphe Précision | Compter médailles "Perfect" | ⏳ |
| S5.4.2 | Stacked columns matchs par carte/mode | Win/Loss/Tie/Left | ⏳ |
| S5.4.3 | Distributions : Win ratio, dégâts, scores | Histogrammes | ⏳ |
| S5.4.4 | Distribution timestamps 1er kill/death | Par map ou match | ⏳ |
| S5.4.5 | Corrélations durée vie / kills / outcomes | Scatter plots | ⏳ |
| S5.4.6 | Win Ratio par jour/heure de la semaine | Heatmap | ⏳ |
| S5.4.7 | Matches at Top vs Total par semaine | Comparaison | ⏳ |
| S5.4.8 | Top 3 armes par session avec kills | Cards ou bar chart | ⏳ |
| S5.4.9 | Médailles gagnées (distribution) | Treemap ou bar | ⏳ |
| S5.4.10 | Shots Fired/Hit + Callout Assists | Sur graphes précision | ⏳ |

**Source notebooks** : [OpenSpartan Hero Stats](https://github.com/OpenSpartan/notebooks/blob/main/src/hero/Hero%20Stats.ipynb)

---

### Phase 6 : Documentation & Branding "LevelUp" 📋 (Après Phase 5)

**Objectif** : Mise à jour complète de la documentation et finalisation du branding "LevelUp".

**Nom officiel de l'application** : **LevelUp** (anciennement OpenSpartan Graph)

#### Sprint 6.1 : README & Documentation Utilisateur ⏳

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S6.1.1 | Réécriture complète du README.md | `README.md` | ⏳ |
| S6.1.2 | Screenshots UI mise à jour | `docs/images/` | ⏳ |
| S6.1.3 | Guide d'installation simplifié | `docs/INSTALL.md` | ⏳ |
| S6.1.4 | Guide de configuration (db_profiles, tokens) | `docs/CONFIGURATION.md` | ⏳ |
| S6.1.5 | FAQ utilisateurs | `docs/FAQ.md` | ⏳ |

**Contenu README cible** :
- Présentation "LevelUp" avec logo
- Features clés avec captures
- Installation one-liner
- Configuration minimale
- Liens vers documentation détaillée

#### Sprint 6.2 : Documentation Technique ⏳

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S6.2.1 | MAJ ARCHITECTURE.md avec DuckDB | `docs/ARCHITECTURE.md` | ⏳ |
| S6.2.2 | MAJ DATA_ARCHITECTURE.md | `docs/DATA_ARCHITECTURE.md` | ⏳ |
| S6.2.3 | MAJ SQL_SCHEMA.md | `docs/SQL_SCHEMA.md` | ⏳ |
| S6.2.4 | MAJ API_GRUNT_RESEARCH.md | `docs/API_GRUNT_RESEARCH.md` | ⏳ |
| S6.2.5 | Nouveau SYNC_GUIDE.md | `docs/SYNC_GUIDE.md` | ⏳ |
| S6.2.6 | MAJ BACKUP_RESTORE.md | `docs/BACKUP_RESTORE.md` | ⏳ |

#### Sprint 6.3 : Branding & Renommage ⏳

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S6.3.1 | Renommer références "OpenSpartan Graph" → "LevelUp" | Global | ⏳ |
| S6.3.2 | Renommer streamlit_app.py si nécessaire | `streamlit_app.py` | ⏳ |
| S6.3.3 | MAJ sidebar brand "LevelUp" | `src/app/sidebar.py` | ✅ Déjà fait |
| S6.3.4 | MAJ launcher "LevelUp" | `openspartan_launcher.py` | ✅ Déjà fait |
| S6.3.5 | MAJ pyproject.toml (name, description) | `pyproject.toml` | ⏳ |
| S6.3.6 | Création logo LevelUp | `static/logo.png` | ⏳ |

#### Sprint 6.4 : Documentation Agent/IA ⏳

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S6.4.1 | MAJ CLAUDE.md avec nouvelles commandes | `CLAUDE.md` | ⏳ |
| S6.4.2 | MAJ .cursorrules | `.cursorrules` | ⏳ |
| S6.4.3 | MAJ project_map.md | `.ai/project_map.md` | ⏳ |
| S6.4.4 | MAJ data_lineage.md | `.ai/data_lineage.md` | ⏳ |
| S6.4.5 | Archivage thought_log.md ancien | `.ai/archive/` | ⏳ |
| S6.4.6 | Nouveau thought_log.md frais | `.ai/thought_log.md` | ⏳ |

#### Sprint 6.5 : GitHub & CI/CD ⏳

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S6.5.1 | MAJ copilot-instructions.md | `.github/copilot-instructions.md` | ⏳ |
| S6.5.2 | MAJ ci.yml avec DuckDB | `.github/workflows/ci.yml` | ⏳ |
| S6.5.3 | Création CONTRIBUTING.md | `CONTRIBUTING.md` | ⏳ |
| S6.5.4 | MAJ LICENSE si nécessaire | `LICENSE` | ⏳ |
| S6.5.5 | Templates issues/PR | `.github/ISSUE_TEMPLATE/` | ⏳ |

#### Checklist Documentation

| Document | Existe | À Jour | Priorité |
|----------|--------|--------|----------|
| README.md | ✅ | ❌ | **Critique** |
| CLAUDE.md | ✅ | ⚠️ | Haute |
| .cursorrules | ✅ | ⚠️ | Haute |
| docs/ARCHITECTURE.md | ✅ | ❌ | Haute |
| docs/DATA_ARCHITECTURE.md | ✅ | ❌ | Haute |
| docs/SQL_SCHEMA.md | ✅ | ⚠️ | Moyenne |
| docs/BACKUP_RESTORE.md | ✅ | ✅ | Basse |
| docs/INSTALL.md | ❌ | N/A | Haute |
| docs/CONFIGURATION.md | ❌ | N/A | Haute |
| docs/FAQ.md | ❌ | N/A | Moyenne |
| CONTRIBUTING.md | ❌ | N/A | Basse |

---

## Décisions Architecturales

### Pourquoi migrer vers DuckDB unifié ?

| Critère | SQLite + Parquet | DuckDB Unifié |
|---------|------------------|---------------|
| Jointures cross-store | `ATTACH` + bridge | Natif, ultra-rapide |
| Requêtes OLAP | Parquet via DuckDB | Direct DuckDB |
| Transactions | SQLite seulement | Partout (ACID) |
| Compression | Snappy (Parquet) | Zstd (2x mieux) |
| Complexité code | 2 technos | 1 techno |
| Import/Export Parquet | Script manuel | `COPY ... TO/FROM` |

### Pourquoi `data/players/{gamertag}/` ?

1. **Isolation** : Chaque joueur a sa propre DB, pas de contention
2. **Portabilité** : Copier un dossier = migrer un joueur
3. **Lisibilité** : Plus clair que `spnkr_gt_*.db`
4. **Scalabilité** : Facile d'ajouter des joueurs

### Pourquoi garder Parquet ?

- **Cold storage** : Archive des vieux matchs (> 1 an)
- **Export/Sharing** : Format standard pour partage
- **Backup** : `COPY ... TO 'file.parquet'`

---

## Schéma de Migration

```
Données existantes                    Cible v4
═════════════════                    ═════════

spnkr_gt_Chocoboflor.db (15 MB)      data/players/Chocoboflor/stats.duckdb
├── MatchStats ──────────────────────► match_stats (JSON → colonnes)
├── MatchCache ──────────────────────► (supprimé, redondant)
├── TeammatesAggregate ──────────────► teammates_aggregate
├── MedalsAggregate ─────────────────► (calculé via medals_earned)
├── Players ─────────────────────────► (dans metadata.duckdb)
└── Friends ─────────────────────────► (dans metadata.duckdb)

halo_unified.db (156 MB)             → Archivé puis supprimé
                                       (remplacé par architecture distribuée)

data/warehouse/metadata.db           data/warehouse/metadata.duckdb
├── playlists ───────────────────────► playlists
├── game_modes ──────────────────────► game_modes
├── categories ──────────────────────► categories
├── medal_definitions ───────────────► medal_definitions
└── (nouveau) ───────────────────────► career_ranks

data/warehouse/match_facts/          data/archive/parquet/
└── player={xuid}/... ───────────────► player={xuid}/... (cold storage)
```

---

## Commandes Utiles

```bash
# Migrer les métadonnées (à créer)
python scripts/migrate_metadata_to_duckdb.py

# Migrer un joueur (à créer)
python scripts/migrate_player_to_duckdb.py --gamertag Chocoboflor

# Migrer tous les joueurs (à créer)
python scripts/migrate_player_to_duckdb.py --all

# Vérifier l'intégrité post-migration
pytest tests/test_duckdb_migration.py -v

# Benchmark nouveau vs ancien
python scripts/benchmark_hybrid.py --db data/players/Chocoboflor/stats.duckdb
```

---

## Références

| Document | Contenu |
|----------|---------|
| `docs/DATA_ARCHITECTURE.md` | Architecture technique détaillée |
| `docs/SQL_SCHEMA.md` | Schémas DuckDB complets |
| `.ai/data_lineage.md` | Traçabilité des flux |
| `src/data/repositories/` | Implémentation des repositories |
| `db_profiles.json` | Configuration des joueurs (v2.0) |

---

## Comportements IA

> Instructions à suivre par les agents IA lors du travail sur ce projet.

### Fin de Sprint

Quand un sprint est marqué comme **COMPLETE** :

1. **Mettre à jour cette roadmap** :
   - Changer le statut du sprint de `🚧` à `✅ COMPLETE`
   - Mettre à jour les statuts des tâches (`⏳` → `✅`)
   - Ajouter une entrée dans "Historique des Décisions" si pertinent
   - Mettre à jour la date "Dernière mise à jour" en fin de fichier

2. **Mettre à jour les fichiers `.ai/`** :
   - `.ai/thought_log.md` : Documenter les décisions prises
   - `.ai/project_map.md` : Si nouveaux fichiers créés
   - `.ai/data_lineage.md` : Si flux de données modifiés

3. **Proposer un commit** :
   - Proposer à l'utilisateur de créer un commit avec les changements
   - Inclure dans le commit : roadmap + fichiers `.ai/` modifiés + code du sprint
   - Format suggéré : `feat(sprint-X.Y): [Description courte du sprint]`

---

## Historique des Décisions

| Date | Décision | Raison |
|------|----------|--------|
| 2026-01-31 | Ingestion JSON → SQLite | Référentiels fonctionnels |
| 2026-01-31 | Infrastructure Parquet | Préparation volumétrie |
| 2026-02-01 | Fusion `current_plan.md` + roadmap | Éviter redondance |
| 2026-02-01 | Migration DuckDB unifié | Simplification + performance |
| 2026-02-01 | Structure `data/players/` | Isolation par joueur |
| 2026-02-01 | Découverte `halo_unified.db` | À archiver, remplacé par v4 |
| 2026-02-01 | Phase 2 COMPLETE | Sprints 2.1-2.3 terminés |
| 2026-02-01 | Stabilisation antagonistes (Phase 3) | Événements simultanés instables |
| 2026-02-01 | Tie-breaker par rang | Si égalité frags, le mieux classé gagne |
| 2026-02-01 | Sprint 3.1 COMPLETE | Validation + tie-breaker implémentés |
| 2026-02-01 | Sprint 3.2 COMPLETE | Agrégation + persistance antagonistes |
| 2026-02-01 | Sprint 3.3 recentré sur debug | Page Rivalités reportée (faible priorité) |
| 2026-02-01 | Phase 4 détaillée | Documentation des 4 axes d'optimisation |
| 2026-02-01 | Phase 5 créée | Grunt API + Stats armes + Visualisations avancées |
| 2026-02-01 | Sprint 3.3 COMPLETE | Mode debug enrichi avec validation antagonistes |
| 2026-02-01 | Phase 4 démarrée | Optimisations avancées (vues matérialisées, N+1, lazy loading) |
| 2026-02-01 | Analyse bottlenecks | Identifié : boucle N+1 MMR, agrégations répétitives, chargement complet |
| 2026-02-01 | Sprint 4.1 COMPLETE | Vues matérialisées (mv_map_stats, mv_mode_category_stats, mv_global_stats, mv_session_stats) |
| 2026-02-01 | Sprint 4.2 COMPLETE | Optimisation N+1 - colonnes MMR déjà dans le DataFrame, boucle supprimée |
| 2026-02-01 | Découverte N+1 | Les colonnes team_mmr/enemy_mmr étaient déjà chargées par load_matches() |
| 2026-02-01 | Sprint 4.1.6 COMPLETE | Appel refresh_materialized_views() après sync (delta/full) |
| 2026-02-01 | Sprint 4.3 COMPLETE | Lazy loading + pagination (load_recent_matches, load_matches_paginated) |
| 2026-02-01 | Sprint 4.4 COMPLETE | Scripts backup/restore Parquet + compression Zstd + documentation |
| 2026-02-01 | Sprint 4.5 COMPLETE | Partitionnement temporel : archive_season.py + vue unifiée DB+archives |
| 2026-02-01 | Phase 4 COMPLETE | Tous les sprints d'optimisation terminés (4.1-4.5) |
| 2026-02-01 | Audit Pre-Phase 5 | 50+ reliquats SQLite, 2 fichiers code mort, 10 tâches de nettoyage |
| 2026-02-01 | Sprint 4.6 COMPLETE | Nettoyage pre-Phase 5, code mort supprimé, modules DuckDB-compatibles |
| 2026-02-01 | Sprint 4.7.1 COMPLETE | Core Sync Engine : DuckDBSyncEngine, SPNKrAPIClient, transformers |
| 2026-02-01 | Sprint 4.7.2 COMPLETE | Intégration : scripts/sync.py et src/ui/sync.py adaptés |
| 2026-02-01 | Sprint 4.7.3 COMPLETE | Migration historique : HighlightEvents, PlayerMatchStats, XuidAliases |
| 2026-02-01 | Sprint 5.1 COMPLETE | Career Rank, Weapon Stats, Spartan ID endpoints + tables DuckDB |

---

## Prochaine Action

**Sprint 5.1 COMPLETE** : Career Rank & Stats Armes (✅)

Prochaine priorité :
- **Phase 5** (suite) : Enrichissement Visuel
  - Sprint 5.0 : Validation Post-Refactoring (benchmarks optionnels)
  - Sprint 5.2 : Correctifs Prioritaires (modes/playlists, synchro app)
  - Sprint 5.3 : Graphes Radar & Étiquettes

```python
# Utilisation des vues matérialisées dans le code UI :
repo = DuckDBRepository(player_db_path, xuid)

# Stats par carte (instantané via mv_map_stats)
map_stats = repo.get_map_stats(min_matches=3)

# Stats par mode (instantané via mv_mode_category_stats)
mode_stats = repo.get_mode_category_stats()

# Stats globales (instantané via mv_global_stats)
global_stats = repo.get_global_stats()

# Lazy loading : les 50 derniers matchs
recent = repo.load_recent_matches(limit=50)

# Pagination : page 2 avec 50 matchs par page
matches, total_pages = repo.load_matches_paginated(page=2, page_size=50)

# Après sync : rafraîchir les vues (appelé automatiquement par sync.py)
repo.refresh_materialized_views()
```

```bash
# Backup et restore (Sprint 4.4)
python scripts/backup_player.py --gamertag Chocoboflor
python scripts/restore_player.py --gamertag Chocoboflor --backup ./data/backups/Chocoboflor
```

---

*Dernière mise à jour : 2026-02-01 (Sprint 5.1 COMPLETE - Career Rank & Stats Armes)*
