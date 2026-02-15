# Rétrospective v5.0 — LevelUp Shared Matches

> **Date** : 2026-02-15
> **Branche** : `v5/shared-matches-migration`
> **Sprints** : S0 → S8 (9 sprints, ~14 jours effectifs)

---

## Objectif initial

Migrer vers une architecture avec base de données partagée (`shared_matches.duckdb`)
pour éliminer la duplication massive de données entre joueurs partageant des matchs.

## Résultats

### Gains mesurés

| Métrique | v4 | v5 | Gain |
|----------|----|----|------|
| Appels API (sync 4 joueurs) | 12 000 | 3 300 | **-72%** |
| Temps/match (partagé) | 16s | 0.5s | **-97%** |
| Temps/match (nouveau) | 16s | 2-3s | **-81%** |
| Stockage shared DB | N/A | 78 MB | Base partagée unique |

### Suite de tests

| Métrique | Avant v5 | Après v5 |
|----------|----------|----------|
| Tests | ~1 800 | **2 768** |
| Failures | 0 | **0** |
| Modules métier (couverture) | ~40% | **70-99%** |

### Sprints réalisés

| Sprint | Durée réelle | Contenu |
|--------|-------------|---------|
| S0 | 0.5j | Audit baseline + backups |
| S1 | 1j | Schéma shared_matches.duckdb |
| S2 | 1j | Migration 4 joueurs |
| S3 | 1j | Refactoring Sync Engine |
| S4 | 1j | Refactoring Repository |
| S5 | 1j | Refactoring UI (Big Bang) |
| S6 | 0.5j | Optimisation API |
| S7 | 2j | Tests & Couverture |
| S7bis | 1.5j | Tests UI (MockStreamlit) |
| S7ter | 1.5j | Couverture modules volumineux |
| S8 | 1j | Finalisation & Release |
| **Total** | **~12j** | |

---

## Leçons apprises

### Ce qui a bien fonctionné

1. **La stratégie de sous-requête `_get_match_source()`** a permis d'adapter toutes
   les pages UI en une seule passe (Sprint 5 réduit de 3j à 8h).

2. **Le framework MockStreamlit** a débloqué les tests UI sans serveur Streamlit.

3. **L'audit baseline (S0)** a posé des fondations solides — aucune surprise pendant
   la migration.

4. **Le plan détaillé par sprint** a guidé efficacement le développement. Les estimations
   étaient conservatrices et les sprints ont souvent été terminés plus vite que prévu.

### Ce qui pourrait être amélioré

1. **Couverture globale** : 43% (vs 65% visé). Les pages UI Streamlit (70+ fichiers)
   tirent la moyenne vers le bas. Un framework de test UI plus sophistiqué serait nécessaire.

2. **Player DBs encore volumineuses** : Les player DBs contiennent encore des données
   historiques (match_stats legacy, etc.) qui pourraient être nettoyées pour atteindre
   les -85% de stockage par joueur annoncés.

3. **Tests d'intégration** : Peu de tests end-to-end avec l'API Halo réelle. Les mocks
   sont exhaustifs mais ne garantissent pas la compatibilité avec les évolutions API.

### Décisions clés documentées

- **ATTACH READ_ONLY** au lieu de MERGE/COPY : Performances et simplicité.
- **Sous-requête vs migration UI** : Évite de toucher chaque page individuellement.
- **DuckDB `:memory:`** pour tous les tests : Isolation, vitesse, pas de file locking.
- **Polars strict** : Aucun nouveau code Pandas dans les modules métier.
- **Citations DuckDB-first** : Post-v5, intégré naturellement dans l'architecture shared.

---

## Fichiers clés créés/modifiés

### Créés
- `data/warehouse/shared_matches.duckdb` (base partagée)
- `scripts/migration/schema_v5.sql` (DDL)
- `scripts/migration/create_shared_matches_db.py`
- `scripts/migration/migrate_player_to_shared.py`
- `src/data/repositories/_match_queries.py`
- `src/data/repositories/_roster_loader.py`
- `src/analysis/citations/engine.py`
- `docs/SHARED_MATCHES_SCHEMA.md`
- `docs/ARCHITECTURE_V5.md`
- `docs/MIGRATION_V4_TO_V5.md`
- `docs/SYNC_OPTIMIZATIONS_V5.md`
- `docs/TESTING_V5.md`

### Modifiés significativement
- `src/data/sync/engine.py` (sync vers shared)
- `src/data/sync/transformers.py` (extracteurs collectifs)
- `src/data/repositories/duckdb_repo.py` (ATTACH multi-DB)
- `src/data/repositories/factory.py` (propagation shared_db_path)
- `CHANGELOG.md`, `README.md`, `pyproject.toml`

---

## Prochaines étapes (hors scope v5)

1. **Nettoyage player DBs** : Supprimer les tables legacy dupliquées pour atteindre -85%
2. **Tests Playwright** : Framework E2E navigateur pour les pages UI
3. **Couverture 65%** : Investir dans les tests UI avec des mocks plus avancés
4. **API Halo** : Adapter aux changements d'endpoints si nécessaire
