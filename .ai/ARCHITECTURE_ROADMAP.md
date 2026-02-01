# Roadmap Architecture - Migration DuckDB Unifiée

> Ce document trace l'évolution planifiée de l'architecture de données.
> Mis à jour : 2026-02-01 (Phase 3 planifiée)

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

### Phase 3 : Enrichissement des Données 🚧 (En cours)

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

### Sprint 3.1 : Stabilisation Algorithme Antagonistes 🚧

**Problème identifié** : Le calcul des frags peut être instable avec des événements simultanés.

**Solution** : Validation par totaux officiels + tie-breaker par rang.

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S3.1.1 | Créer `load_match_players_stats()` | `src/db/loaders.py` | ⏳ |
| S3.1.2 | Créer `validate_and_adjust_pairs()` | `src/analysis/killer_victim.py` | ⏳ |
| S3.1.3 | Modifier `compute_personal_antagonists()` | `src/analysis/killer_victim.py` | ⏳ |
| S3.1.4 | Mettre à jour les tests | `tests/test_killer_victim_antagonists.py` | ⏳ |

**Algorithme amélioré** :
```
1. Reconstituer les paires killer→victim (existant)
2. Pour chaque joueur du match :
   - Calculer kills_reconstitués, deaths_reconstitués
   - Comparer avec kills_officiels, deaths_officiels
   - Si écart : marquer comme "incertain"
3. Pour les cas ambigus (égalité de frags par plusieurs adversaires) :
   - Tie-breaker = rang dans le match (meilleur classement = priorité)
4. Retourner résultat avec flag de confiance
```

### Sprint 3.2 : Agrégation et Persistance 📋

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S3.2.1 | Créer `aggregate_antagonists()` | `src/analysis/antagonists.py` | ⏳ |
| S3.2.2 | Créer script `populate_antagonists.py` | `scripts/populate_antagonists.py` | ⏳ |
| S3.2.3 | Ajouter méthode `save_antagonists()` | `src/data/repositories/duckdb_repo.py` | ⏳ |
| S3.2.4 | Tests d'intégration | `tests/test_antagonists_persistence.py` | ⏳ |

### Sprint 3.3 : UI Rivalités 📋

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S3.3.1 | Créer page "Mes Rivalités" | `src/ui/pages/rivalries.py` | ⏳ |
| S3.3.2 | Améliorer mode debug | `src/ui/pages/match_view_players.py` | ⏳ |
| S3.3.3 | Documentation | `.ai/thought_log.md` | ⏳ |

---

### Phase 4 : Optimisations Avancées 📋 (Futur)

| Fonctionnalité | Description | Impact |
|----------------|-------------|--------|
| Vues matérialisées | Pré-calculer agrégations fréquentes | -50% temps requête |
| Compression Zstd | Natif DuckDB | -30% espace disque |
| Lazy loading | Charger données à la demande | -80% RAM initiale |
| Partitionnement temporel | Tables par année | Requêtes historiques rapides |

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

---

## Prochaine Action

**Sprint 3.1 : Stabilisation Algorithme Antagonistes**

Priorité immédiate : corriger l'instabilité du calcul des frags lors d'événements simultanés.

**Tâches** :
1. Créer `load_match_players_stats()` pour obtenir kills/deaths officiels
2. Implémenter `validate_and_adjust_pairs()` pour valider la cohérence
3. Ajouter tie-breaker par rang dans `compute_personal_antagonists()`
4. Tests unitaires pour cas d'événements simultanés

```python
# Utilisation du nouveau système :
# Mode recommandé (auto-détection depuis db_profiles.json v2.1)
from src.data.repositories.factory import get_repository_from_profile
repo = get_repository_from_profile("JGtm")

# Ou depuis Streamlit
from src.data.integration.streamlit_bridge import get_repository_for_player
repo = get_repository_for_player("JGtm")
```

---

*Dernière mise à jour : 2026-02-01 (Phase 3 planifiée - Sprint 3.1 en cours)*
