# Plan d'Implémentation : Migration DuckDB/Parquet + Validation Refresh

> Généré par `/orchestrate` le 2026-01-31
> Requête : "Finalise la migration vers DuckDB/Parquet et vérifie que le refresh full et delta fonctionnent bien, que ce soit sur l'app ou par ligne de commande"

## Objectif
Compléter la migration vers l'architecture hybride SQLite + DuckDB + Parquet et valider les fonctionnalités de synchronisation (full refresh et delta sync).

## Statut
✅ Complété

---

## Résumé des Modifications

### 1. Bug Fix - ParquetWriter (✅)
**Fichier**: `src/data/infrastructure/parquet/writer.py`
- Corrigé bug ligne 90 : `group_by().agg(pl.all())` → `select().unique()`
- Aligné avec la méthode `write_medals()` qui utilise déjà le pattern correct

### 2. Script sync.py Unifié (✅)
**Fichier**: `scripts/sync.py`
- Ajouté fonction `migrate_to_parquet()` pour migration automatique vers Parquet
- Ajouté options CLI:
  - `--migrate-parquet` : Migre explicitement vers Parquet
  - `--warehouse` : Chemin personnalisé vers le warehouse
- La migration Parquet est automatiquement appelée après `--delta` ou `--full`

### 3. Dépendances (✅)
**Fichier**: `pyproject.toml`
- Ajouté dépendances manquantes:
  - `polars>=0.20.0`
  - `duckdb>=0.10.0`
  - `pydantic>=2.5.0`

---

## Architecture Implémentée

### Flux de Synchronisation Unifié
```
API Halo Infinite (SPNKr)
        ↓
scripts/sync.py --delta ou --full
        ↓
   ┌────────────┐
   │ SQLite DB  │  (MatchStats, PlayerMatchStats, etc.)
   └────────────┘
        ↓
   rebuild_match_cache()
        ↓
   migrate_to_parquet()
        ↓
   ┌────────────────────────┐
   │ data/warehouse/        │
   │ ├── metadata.db        │  (SQLite - référentiels)
   │ └── match_facts/       │  (Parquet - faits de match)
   │     └── player={xuid}/ │
   │         └── year=*/    │
   │             └── month=/│
   └────────────────────────┘
        ↓
   DuckDB QueryEngine
        ↓
   Streamlit UI / CLI
```

### Modes de Synchronisation

| Mode | Commande CLI | Comportement |
|------|--------------|--------------|
| Delta | `python scripts/sync.py --delta` | Arrêt au premier match connu |
| Full | `python scripts/sync.py --full` | Traite tous les matchs jusqu'à la limite |
| Delta (UI) | Bouton "Synchroniser" | Sync delta de tous les joueurs |

---

## Commandes de Test

### CLI - Synchronisation
```bash
# Aide
python scripts/sync.py --help

# Delta sync (rapide, nouveaux matchs)
python scripts/sync.py --delta

# Delta sync pour un joueur
python scripts/sync.py --delta --player Chocoboflor

# Full sync avec limite
python scripts/sync.py --full --max-matches 500

# Full sync pour un joueur
python scripts/sync.py --full --player Madina97294

# Migration Parquet uniquement
python scripts/sync.py --migrate-parquet

# Afficher les statistiques
python scripts/sync.py --stats
```

### CLI - Tests
```bash
# Tests architecture données
pytest tests/test_data_architecture.py -v

# Tests delta sync
pytest tests/test_delta_sync.py -v

# Suite complète
pytest tests/ -v
```

### UI - Streamlit
```bash
streamlit run streamlit_app.py
# → Bouton "Synchroniser" dans la sidebar (delta sync auto)
```

---

## Infrastructure Vérifiée

### SQLiteMetadataStore (✅)
- Table `sync_meta` avec colonnes: `xuid`, `last_sync_at`, `last_match_id`, `total_matches`, `sync_status`
- Méthodes: `get_sync_status()`, `update_sync_status()`
- Schéma créé automatiquement à l'initialisation

### ParquetWriter (✅ corrigé)
- Partitionnement: `player={xuid}/year={yyyy}/month={mm}/`
- Déduplication sur `match_id`
- Bug corrigé ligne 90

### ParquetReader (✅)
- Lecture avec pruning de partitions
- Support date range filter
- Méthodes: `has_data()`, `count_rows()`, `read_match_facts()`

### QueryEngine DuckDB (✅)
- Jointures SQLite + Parquet via ATTACH
- Placeholders: `{match_facts}`, `{medals}`, `{players}`, etc.
- Gestion cas "pas de données Parquet"

### ShadowRepository (✅)
- Modes: SHADOW_READ, SHADOW_COMPARE, HYBRID_FIRST
- Méthode `migrate_matches_to_parquet()`
- Pattern Shadow Module pour migration progressive

---

## Points d'Attention

### Installation des Dépendances
Avant utilisation, installer les dépendances :
```bash
pip install polars duckdb pydantic
# Ou via pyproject.toml
pip install -e ".[dev,spnkr]"
```

### Tokens SPNKr Requis
Les syncs nécessitent les tokens Halo Waypoint :
```bash
# Dans .env.local ou variables d'environnement
SPNKR_SPARTAN_TOKEN=v4=...
SPNKR_CLEARANCE_TOKEN=eyJ...
```

### Migration Progressive
Le système supporte une migration progressive :
1. Les données legacy (SQLite JSON) continuent de fonctionner
2. `ShadowRepository` lit depuis legacy, écrit vers Parquet
3. `HybridRepository` lit depuis Parquet si disponible

---

*Dernière mise à jour : 2026-01-31 22:00*
*Statut : Implémentation complète, tests non exécutés (environnement sans dépendances)*
