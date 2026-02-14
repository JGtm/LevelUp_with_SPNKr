# .ai/features/ - Base de Connaissances Technique

> **⚠️ Note v4.5** (2026-02-14) : Ces fiches ont été générées lors de la v3/v4.0 et contiennent des références à l'architecture SQLite/Parquet supprimée. L'architecture actuelle (v4.5) utilise **DuckDB unifié** + **Polars** comme moteur principal. Les modules `src/db/`, `src/data/infrastructure/` n'existent plus. Se référer à `docs/ARCHITECTURE.md` et `docs/DATA_ARCHITECTURE.md` pour la documentation à jour.

## Statut par fiche (v4.5)

| Fichier | Statut v4.5 | Note |
|---------|:-----------:|------|
| `data_storage.md` | ⚠️ Obsolète | Références SQLite/Parquet à ignorer. Voir `docs/DATA_ARCHITECTURE.md` |
| `ingestion_scripts.md` | ⚠️ Obsolète | Scripts refactorisés dans `src/data/sync/`. Voir `docs/SYNC_GUIDE.md` |
| `query_engine.md` | ⚠️ Obsolète | Remplacé par `DuckDBRepository`. Voir `docs/SQL_SCHEMA.md` |
| `stats_engine.md` | ✅ Partiellement ok | Algorithmes corrects. Manque : performance score, objective participation |
| `ui_streamlit.md` | ✅ Partiellement ok | Structure correcte. Manque : nouvelles pages v4.5 |
| `spnkr_integration.md` | ✅ Partiellement ok | API correcte. Sync engine refactorisé dans `src/data/sync/` |
| `test_agent.md` | ✅ Partiellement ok | Mapping `src/db/` obsolète. 1328 tests, 0 failures |
| `cleanup_agent.md` | ✅ Correct | `src/db/` entièrement supprimé |
| `API_COMPARISON_SPNKR_GRUNT.md` | ✅ Correct | Document de référence API |

Ce dossier contient les spécifications techniques extraites automatiquement du projet par la commande `/investigate`.

## Structure

Chaque fichier `.md` représente un module majeur du projet :

| Fichier | Module |
|---------|--------|
| `spnkr_integration.md` | Intégration API SPNKr |
| `data_storage.md` | Architecture de stockage (SQLite/Parquet) |
| `stats_engine.md` | Moteur de calculs statistiques |
| `ui_components.md` | Composants Streamlit |
| ... | ... |

## Format Standard

Chaque fiche doit suivre ce template :

```markdown
# Nom du Module

## Résumé
[Description en 2-3 phrases]

## Inputs
- [Type et source des données entrantes]

## Outputs  
- [Type et destination des données sortantes]

## Dépendances
- [Modules internes et packages externes]

## Logique Métier
[Algorithmes et règles importantes]

## Points d'Attention
[Bugs connus, limitations, TODOs]
```

## Statut des Priorités (SUPER_PLAN P1-P8)

> Mis à jour le 2026-02-12. Sprints S0-S5 livrés.

| # | Priorité | Description | Sprint | Statut |
|---|----------|-------------|--------|--------|
| **P1** | Bug "Dernière session" | Correction tri bouton dernière session + logique filtres | S0 | **Implémenté** |
| **P2** | Refactoring backfill + Migration Polars core | Migration Pandas→Polars (performance_score, backfill) + logging | S2 | **Implémenté** |
| **P3** | Damage participants | `damage_dealt`, `damage_taken` dans match_participants + backfill | S3A | **Implémenté** |
| **P4** | Médianes, Frags, Modes, Médias, Coéquipiers | Médianes distributions, renommage Frags, normalisation modes, lightbox médias, radar participation | S4 | **Implémenté** |
| **P5** | Score de Performance v4 | 8 métriques (PSPM, DPM, rank_perf…), version `v4-relative` | S5 | **Implémenté** |
| **P6** | Nouvelles visualisations statistiques | Corrélations, distributions, win streaks, comparaisons coéquipiers | S6-S8 | En cours |
| **P7** | Section Carrière | Gauge progression héros, métriques XP, historique rangs | S3B | **Implémenté** |
| **P8** | Persistance filtres multi-joueurs | Nettoyage session_state, FilterState centralisé | S0 | **Implémenté** |

## Usage

Ces fichiers sont lus par la commande `/plan` pour générer un plan d'implémentation structuré.

---
*Dernière mise à jour : 2026-02-12*
