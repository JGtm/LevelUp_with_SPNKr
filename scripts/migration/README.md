# Scripts de Migration

Scripts de migration SQLite → DuckDB. À utiliser **uniquement** pour migrer des données existantes.

Ces scripts ne font pas partie du workflow normal. Ils ont été utilisés lors de la migration
de l'architecture v3 (SQLite) vers v4 (DuckDB).

## Usage

```bash
# Migration d'un joueur
python scripts/migration/migrate_player_to_duckdb.py --gamertag MonGT

# Migration complète
python scripts/migration/migrate_all_to_duckdb.py

# Récupération depuis SQLite
python scripts/migration/recover_from_sqlite.py --gamertag MonGT
```
