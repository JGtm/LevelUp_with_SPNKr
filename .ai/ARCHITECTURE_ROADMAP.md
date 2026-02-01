# Roadmap Architecture - Migration DuckDB Unifiée

> Ce document trace l'évolution planifiée de l'architecture de données.
> Mis à jour : 2026-02-01

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

### Phase 2 : Migration DuckDB Unifiée 🚧 (En cours)

**Objectif** : Migrer vers DuckDB persisté comme moteur unique

| # | Tâche | Statut | Notes |
|---|-------|--------|-------|
| 2.1 | Créer structure `data/players/{gamertag}/` | ✅ | Dossiers créés |
| 2.2 | Mettre à jour `db_profiles.json` | ✅ | Version 2.0 avec nouveaux chemins |
| 2.3 | Créer script de migration métadonnées | ⏳ | `metadata.db` → `metadata.duckdb` |
| 2.4 | Créer script de migration joueur | ⏳ | SQLite → DuckDB |
| 2.5 | Adapter `HybridRepository` pour DuckDB natif | ⏳ | Plus de SQLite |
| 2.6 | Migrer les 4 joueurs existants | ⏳ | ~250 MB total |

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

### Sprint 2.2 : Adapter le Code

| # | Tâche | Fichier(s) | Notes |
|---|-------|------------|-------|
| S2.2.1 | Refactorer `HybridRepository` | `src/data/repositories/hybrid.py` | DuckDB natif |
| S2.2.2 | Mettre à jour `DuckDBEngine` | `src/data/infrastructure/database/` | Attacher player DB |
| S2.2.3 | Adapter le bridge Streamlit | `src/data/integration/streamlit_bridge.py` | Nouveaux chemins |
| S2.2.4 | Tests de non-régression | `tests/` | Valider l'UI |

### Sprint 2.3 : Nettoyage

| # | Tâche | Notes |
|---|-------|-------|
| S2.3.1 | Archiver les DBs legacy | Déplacer vers `data/archive/legacy/` |
| S2.3.2 | Supprimer `halo_unified.db` | Obsolète après migration |
| S2.3.3 | Nettoyer le code legacy | Supprimer `LegacyRepository` si plus utilisé |

---

### Phase 3 : Enrichissement des Données 📋 (Planifié)

**Objectif** : Ajouter des tables pour améliorer l'UX

| Nouvelle Table | Description | Utilisation | Source |
|---------------|-------------|-------------|--------|
| `antagonists` | Top 20 killers/victimes | Rivalités, matchups | API kill_death_graph |
| `weapon_stats` | Stats par arme | Analyse des armes | API weapon_core |
| `skill_history` | Historique CSR | Graphique progression | API playlist_csr |
| `career_ranks` | Traductions rangs | Localisation | JSON statique |
| `match_events` | Timeline événements | Replays (optionnel) | API match_events |

**Schéma SQL** : Voir `docs/SQL_SCHEMA.md`

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

---

## Prochaine Action

**Créer `scripts/migrate_metadata_to_duckdb.py`** pour migrer les référentiels.

```bash
# Prêt à exécuter :
python scripts/migrate_metadata_to_duckdb.py
```

---

*Dernière mise à jour : 2026-02-01*
