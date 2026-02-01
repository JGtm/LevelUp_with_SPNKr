# Scripts Obsolètes

Ce dossier contient les scripts de migration qui ne sont plus utilisés depuis l'adoption de l'architecture DuckDB unifiée (v4.7+).

## Scripts archivés

### `migrate_to_cache.py`
- **Obsolète depuis** : Sprint 4.7.4
- **Raison** : Le cache SQLite (`MatchCache`, `TeammatesAggregate`) est remplacé par les vues matérialisées DuckDB
- **Remplacement** : Le script `scripts/migrate_all_to_duckdb.py` gère désormais toutes les migrations

### `migrate_to_parquet.py`
- **Obsolète depuis** : Sprint 4.7.4
- **Raison** : Parquet n'est plus utilisé comme format intermédiaire. DuckDB offre les mêmes performances analytiques avec support transactionnel
- **Remplacement** : Utiliser `DuckDBRepository` directement. Pour l'export Parquet (backup/archivage), utiliser `COPY ... TO 'file.parquet'` via DuckDB

## Nouvelle architecture (v4.7+)

```
data/players/{gamertag}/stats.duckdb    # Données par joueur
data/warehouse/metadata.duckdb           # Référentiels partagés
```

## Scripts de migration actuels

- `scripts/migrate_all_to_duckdb.py` - Migration complète vers DuckDB
- `scripts/migrate_highlight_events.py` - Migration des highlight events
- `scripts/migrate_player_match_stats.py` - Migration des stats MMR/skill

## Ne pas supprimer

Ces scripts sont conservés pour :
1. Référence historique
2. Dépannage de migrations partielles anciennes
3. Documentation des anciennes structures de données
