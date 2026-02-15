# Règle : Pas de SQLite

## Contexte

Le projet LevelUp utilise **DuckDB v4** comme unique moteur de données applicatif. SQLite est proscrit.

## Interdictions

- Ne pas ajouter `import sqlite3` ni `sqlite3.connect()` dans le code applicatif (src/, streamlit_app.py, scripts de sync/UI).
- Ne pas implémenter de fallback vers une base `.db` (SQLite). Si une base est requise, elle doit être `.duckdb`.
- Ne pas utiliser `sqlite_master` ; utiliser `information_schema.tables` pour DuckDB.
- Ne pas étendre le support des bases SQLite dans l’UI, la sync ou les repositories.

## Exceptions (uniquement)

- **Scripts de migration** qui lisent l’ancien SQLite pour alimenter DuckDB :
  - `scripts/recover_from_sqlite.py`
  - `scripts/migrate_player_to_duckdb.py`
- Ces scripts sont les seuls autorisés à ouvrir un fichier `.db`.

## Référence

- Audit complet des points à migrer : `.ai/SQLITE_TO_DUCKDB_AUDIT.md`
- Instructions agents : `CLAUDE.md` (section "SQLite interdit")

## En cas de modification

Lors de tout changement touchant la persistance ou la synchronisation :
1. Utiliser `duckdb` et `DuckDBRepository`.
2. Ne pas introduire de chemin ou branche SQLite.
3. Si du code existant utilise encore SQLite, le marquer ou le migrer selon l’audit.
