# Guide de Tests v5 — LevelUp

Ce document décrit l'architecture de tests pour la migration v5 (shared_matches).

---

## Organisation des fichiers de tests

```
tests/
├── conftest.py                        # Fixtures globales (Polars, monkey-patch DuckDB)
├── __init__.py
│
├── test_batch_insert.py               # Tests batch_insert (coerce, upsert, cast_plan)
├── test_duckdb_repository.py          # Tests core DuckDBRepository (v4)
├── test_duckdb_repository_v5.py       # Tests DuckDBRepository avec shared (v5)
├── test_repository_shared_v5.py       # Tests complémentaires shared v5
├── test_sync_shared_v5.py             # Tests sync engine (backfill mask, extract, etc.)
├── test_metadata_resolver.py          # Tests résolution métadonnées
├── test_analysis.py                   # Tests modules d'analyse
│
├── migration/
│   ├── __init__.py
│   ├── test_migration_integrity.py    # Tests intégrité migration (25 tests)
│   └── test_migration_v5.py           # Tests idempotence et edge cases migration
│
├── ui/
│   ├── __init__.py
│   └── test_all_pages_v5.py           # Smoke tests import + helpers UI (71 tests)
│
├── performance/
│   ├── __init__.py
│   └── test_load_v5.py                # Tests de charge (1000+ matchs, @slow)
│
└── integration/                       # Tests d'intégration (exclus par défaut)
```

---

## Commandes

### Suite rapide (recommandé)

```bash
python -m pytest -q --ignore=tests/integration
```

### Tests v5 uniquement

```bash
python -m pytest tests/test_batch_insert.py tests/test_repository_shared_v5.py \
  tests/test_sync_shared_v5.py tests/migration/test_migration_v5.py \
  tests/ui/test_all_pages_v5.py -v
```

### Tests de charge (marqués `@slow`)

```bash
python -m pytest tests/performance/ -v -m slow
```

### Couverture

```bash
# Rapport JSON + HTML
python -m pytest --cov=src --cov-report=json --cov-report=html \
  --ignore=tests/integration --ignore=tests/performance -q

# Vérifier le seuil
python scripts/check_coverage_threshold.py --min 65
```

---

## Fixtures principales

### `conftest.py` (racine)

| Fixture | Description |
|---------|-------------|
| `sample_match_df_polars` | DataFrame Polars avec 5 matchs exemple |
| `empty_df_polars` | DataFrame Polars vide avec le bon schéma |
| `df_with_nans_polars` | DataFrame Polars avec valeurs nulles |

### Fixtures locales (dans les fichiers de test)

| Fixture | Fichier | Description |
|---------|---------|-------------|
| `repo_with_shared` | `test_repository_shared_v5.py` | Repository v5 avec shared_matches.duckdb |
| `repo_v4_only` | `test_repository_shared_v5.py` | Repository v4 sans shared |
| `large_shared_db` | `test_load_v5.py` | DB partagée avec 1000 matchs |
| `tmp_path` | pytest built-in | Répertoire temporaire auto-nettoyé |

---

## Helpers réutilisables

### `_create_player_db(db_path)`
Crée une base joueur minimale avec le schéma complet :
`match_stats`, `medals_earned`, `teammates_aggregate`, `antagonists`,
`highlight_events`, `match_participants`, `xuid_aliases`

### `_create_shared_db(db_path)`
Crée une `shared_matches.duckdb` avec le schéma v5 :
`match_registry`, `match_participants`, `highlight_events`,
`medals_earned`, `xuid_aliases`, `schema_version`

### `_create_large_player_db(db_path, n_matches)`
Crée une DB joueur avec `n_matches` matchs pour les tests de charge.

---

## Patterns de test

### Import smoke test (UI)

```python
@pytest.mark.parametrize("module_name", PAGE_MODULES)
def test_import(self, module_name: str) -> None:
    mod = importlib.import_module(module_name)
    assert mod is not None
```

### Test DuckDB en mémoire

```python
def test_example(self):
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val VARCHAR)")
    # ... test logic
    conn.close()
```

### Test avec shared_matches

```python
def test_with_shared(self, tmp_path):
    player_db = tmp_path / "player" / "stats.duckdb"
    shared_db = tmp_path / "shared.duckdb"
    _create_player_db(player_db)
    _create_shared_db(shared_db)
    repo = DuckDBRepository(player_db, "xuid", shared_db_path=shared_db)
    # ... assertions
    repo.close()
```

---

## Bonnes pratiques Windows

1. **Toujours utiliser `tmp_path`** (pas `tempfile.TemporaryDirectory`) pour éviter les
   `PermissionError: [WinError 32]` causés par le file-locking DuckDB.

2. **Monkey-patch DuckDB threads=1** dans `conftest.py` pour éviter les
   `RuntimeError: Query interrupted` sur Windows.

3. **Fermer les connexions explicitement** avec `repo.close()` ou `conn.close()`
   avant la fin du test (ou utiliser `yield` dans les fixtures avec cleanup).

4. **Exécuter via `.venv`** :
   ```bash
   .venv/Scripts/python.exe -m pytest
   ```

---

## Seuils de couverture

| Module | Objectif |
|--------|----------|
| Global | ≥ 65 % |
| `src/data/sync/` | ≥ 70 % |
| `src/data/repositories/` | ≥ 75 % |
| `src/analysis/` | ≥ 60 % |
| `src/ui/pages/` | ≥ 30 % (smoke tests) |

---

## Script de vérification

```bash
# Vérifier couverture globale ≥ 65%
python scripts/check_coverage_threshold.py --min 65

# Avec module spécifique
python scripts/check_coverage_threshold.py --min 70 --module src/data/sync

# Afficher les fichiers à faible couverture
python scripts/check_coverage_threshold.py --min 65 --show-low 50
```

---

## Fichiers créés lors du Sprint 7

| Fichier | Tests | Description |
|---------|-------|-------------|
| `tests/test_batch_insert.py` | 48 | Coercion types, batch insert/upsert, cast plan |
| `tests/test_repository_shared_v5.py` | 29 | Repository v5 shared complet |
| `tests/migration/test_migration_v5.py` | 10 | Idempotence, edge cases migration |
| `tests/test_sync_shared_v5.py` | 22 | Sync engine v5 (backfill, extract, options) |
| `tests/ui/test_all_pages_v5.py` | 71 | Smoke imports + helpers UI |
| `tests/performance/test_load_v5.py` | 8 | Charge 1000+ matchs |
| `scripts/check_coverage_threshold.py` | — | Outil CLI vérification couverture |

**Total nouveaux tests Sprint 7 : ~188**
