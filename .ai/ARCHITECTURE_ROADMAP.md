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

### Phase 4 : Optimisations Avancées 📋 (Futur)

**Objectif** : Améliorer la performance et l'efficacité de l'architecture DuckDB.

| Fonctionnalité | Description | Impact | Priorité |
|----------------|-------------|--------|----------|
| Vues matérialisées | Pré-calculer agrégations fréquentes | -50% temps requête | Haute |
| Compression Zstd | Natif DuckDB pour export/backup | -30% espace disque | Moyenne |
| Lazy loading | Charger données à la demande | -80% RAM initiale | Haute |
| Partitionnement temporel | Tables par année/saison | Requêtes historiques rapides | Basse |

#### 4.1 Vues Matérialisées

DuckDB ne supporte pas nativement les materialized views. Solution : tables de cache rafraîchies.

```sql
-- Exemple : stats agrégées par mode de jeu
CREATE OR REPLACE TABLE mv_stats_by_mode AS
SELECT game_mode_id, 
       COUNT(*) as matches_played,
       AVG(kills) as avg_kills,
       AVG(deaths) as avg_deaths,
       SUM(medals_total) as total_medals
FROM match_stats
GROUP BY game_mode_id;

-- Rafraîchissement après sync
INSERT OR REPLACE INTO mv_stats_by_mode SELECT ...;
```

**Tables candidates** :
- `mv_stats_by_mode` : Stats par mode de jeu
- `mv_stats_by_map` : Stats par carte
- `mv_weekly_summary` : Résumé hebdomadaire

#### 4.2 Compression Zstd

```sql
-- Export avec compression optimale
COPY match_stats TO 'backup.parquet' (COMPRESSION 'zstd', COMPRESSION_LEVEL 9);

-- Import depuis Parquet compressé
COPY match_stats FROM 'backup.parquet';
```

#### 4.3 Lazy Loading

Stratégie pour réduire la consommation RAM :

1. **Au démarrage** : Charger uniquement les métadonnées légères
2. **Navigation** : Charger les matchs à la demande (pagination)
3. **Cache Streamlit** : Utiliser `@st.cache_data` avec TTL adapté

```python
@st.cache_data(ttl=300)  # 5 min
def load_recent_matches(gamertag: str, limit: int = 50):
    """Charge les N derniers matchs (lazy)."""
    repo = get_repository_for_player(gamertag)
    return repo.get_recent_matches(limit=limit)
```

#### 4.4 Partitionnement Temporel

Structure cible pour gros volumes (> 5000 matchs) :

```
data/players/{gamertag}/
├── stats.duckdb          # Données récentes (saison courante)
└── archive/
    ├── season_1.parquet  # Saison 1 (cold storage)
    ├── season_2.parquet  # Saison 2
    └── season_3.parquet  # Saison 3
```

**Seuil recommandé** : Archiver les matchs > 1 an ou > 2000 matchs.

---

### Phase 5 : Enrichissement Visuel & Grunt API 📋 (Futur)

**Objectif** : Nouvelles sources de données (Grunt API) + visualisations avancées + correctifs.

#### Sprint 5.1 : Intégration Grunt API & Stats Armes

| # | Tâche | Fichier(s) | Statut |
|---|-------|------------|--------|
| S5.1.1 | Étudier les possibilités de Grunt API | `docs/API_GRUNT_RESEARCH.md` | ⏳ |
| S5.1.2 | Récupérer Spartan ID + rang carrière | `src/api/grunt_client.py` | ⏳ |
| S5.1.3 | Ajouter récupération de l'adornment | `src/api/grunt_client.py` | ⏳ |
| S5.1.4 | Explorer récupération stats armes | `src/api/grunt_client.py` | ⏳ |
| S5.1.5 | Persister stats armes en BDD | `src/data/repositories/duckdb_repo.py` | ⏳ |

**Table cible** : `weapon_stats` (déjà dans le schéma v4)

```sql
-- Schéma weapon_stats
CREATE TABLE weapon_stats (
    gamertag VARCHAR,
    weapon_id VARCHAR,
    weapon_name VARCHAR,
    kills INTEGER,
    deaths INTEGER,
    headshots INTEGER,
    shots_fired INTEGER,
    shots_hit INTEGER,
    damage_dealt DOUBLE,
    time_held_seconds DOUBLE,
    updated_at TIMESTAMP
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

---

## Prochaine Action

**Phase 4 : Optimisations Avancées** ou **Phase 5 : Enrichissement Visuel & Grunt API**

La Phase 3 (Enrichissement des Données) est maintenant complète. Deux options :

**Option A - Phase 4** : Optimisations performance (vues matérialisées, lazy loading)
**Option B - Phase 5** : Nouvelles fonctionnalités (Grunt API, stats armes, graphes radar)

```python
# Utilisation du système actuel :
from src.data.repositories.factory import get_repository_from_profile
repo = get_repository_from_profile("JGtm")

# Charger les rivalités (Sprint 3.2)
nemeses = repo.get_top_nemeses(limit=20)  # Qui m'a le plus tué
victims = repo.get_top_victims(limit=20)   # Qui j'ai le plus tué

# Mode debug antagonistes (Sprint 3.3)
# Ajouter ?debug=1 à l'URL ou OPENSPARTAN_DEBUG=1
# Affiche ✓/⚠ + validation_notes sur la page Match View
```

---

*Dernière mise à jour : 2026-02-01 (Sprint 3.3 COMPLETE - Mode debug antagonistes enrichi)*
