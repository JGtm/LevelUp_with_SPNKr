# Plan Détaillé de Correction des Tests

**Date**: 2026-02-06  
**Objectif**: Corriger tous les problèmes de tests identifiés (segfaults DuckDB, tests Polars échoués, autres erreurs)

---

## 📋 Vue d'ensemble

### Problèmes identifiés
1. **Segfaults DuckDB** : Fixtures DuckDB causant des crashes lors d'exécutions groupées
2. **Tests Polars échoués** : Plusieurs tests Polars retournent FAILED
3. **Autres erreurs** : Tests échouant pour diverses raisons (build_option_map, etc.)

### Statistiques
- **Total de tests** : ~854 tests collectés
- **Tests passants actuellement** : ~70+ tests (modèles, parsers, filter_state, etc.)
- **Tests problématiques** : Fixtures DuckDB + tests Polars + autres erreurs

---

## 🎯 Phase 1 : Correction des Fixtures DuckDB Restantes

### Objectif
Éliminer tous les segfaults causés par les fixtures DuckDB mal gérées.

### Fichiers à corriger

#### 1.1 `tests/test_cache_duckdb_regressions.py`
**Problème** : Fixture `temp_duckdb` utilise un nom de fichier fixe, peut causer des conflits.

**Actions** :
```python
# AVANT (ligne 21-23)
@pytest.fixture
def temp_duckdb(tmp_path):
    db_path = tmp_path / "test_stats.duckdb"
    conn = duckdb.connect(str(db_path))
    # ... pas de try/finally

# APRÈS
@pytest.fixture
def temp_duckdb(tmp_path):
    import uuid
    db_path = tmp_path / f"test_stats_{uuid.uuid4().hex[:8]}.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        # ... création tables et données
    finally:
        conn.close()
        del conn
        gc.collect()
    return db_path
```

**Fichier** : `tests/test_cache_duckdb_regressions.py`  
**Lignes** : 20-100 (approximatif, vérifier le fichier complet)

---

#### 1.2 `tests/test_sync_ui.py`
**Problème** : Plusieurs fixtures DuckDB (`mock_duckdb_env`, `mock_duckdb_db`) sans gestion propre.

**Actions** :
- **Fixture `mock_duckdb_env`** (ligne ~109) :
  ```python
  @pytest.fixture
  def mock_duckdb_env(self, tmp_path):
      import uuid
      players_dir = tmp_path / "data" / "players" / f"TestPlayer_{uuid.uuid4().hex[:8]}"
      players_dir.mkdir(parents=True)
      db_path = players_dir / "stats.duckdb"
      
      conn = duckdb.connect(str(db_path))
      try:
          # ... création tables
      finally:
          conn.close()
      return str(db_path)
  ```

- **Fixture `mock_duckdb_db`** (ligne ~198) : Même correction

**Fichier** : `tests/test_sync_ui.py`  
**Lignes** : 108-138, 198-230 (approximatif)

---

#### 1.3 `tests/test_lazy_loading.py`
**Problème** : Fixture `temp_duckdb` dans classe `TestLazyLoadingIntegration` (ligne ~325).

**Actions** :
```python
@pytest.fixture
def temp_duckdb(self, tmp_path):
    import uuid
    db_path = tmp_path / f"test_stats_{uuid.uuid4().hex[:8]}.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        # ... création tables
    finally:
        conn.close()
    return db_path
```

**Fichier** : `tests/test_lazy_loading.py`  
**Lignes** : 324-400 (approximatif)

---

#### 1.4 `tests/test_sync_performance_score.py`
**Problème** : Fixture `temp_duckdb` retourne juste un chemin sans créer la DB.

**Actions** :
```python
@pytest.fixture
def temp_duckdb(tmp_path: Path) -> Path:
    import uuid
    db_path = tmp_path / f"test_player_{uuid.uuid4().hex[:8]}" / "stats.duckdb"
    db_path.parent.mkdir(parents=True)
    
    # Créer la DB avec tables de base si nécessaire
    conn = duckdb.connect(str(db_path))
    try:
        # Créer tables si nécessaire pour les tests
        pass  # Ou créer les tables requises
    finally:
        conn.close()
    return db_path
```

**Fichier** : `tests/test_sync_performance_score.py`  
**Lignes** : 22-26

---

#### 1.5 `tests/test_backfill_performance_score.py`
**Problème** : Fixture `temp_duckdb_with_matches` crée la DB mais peut avoir des problèmes.

**Actions** :
```python
@pytest.fixture
def temp_duckdb_with_matches(tmp_path: Path) -> tuple[Path, str]:
    import uuid
    db_path = tmp_path / f"test_player_{uuid.uuid4().hex[:8]}" / "stats.duckdb"
    db_path.parent.mkdir(parents=True)
    
    conn = duckdb.connect(str(db_path))
    try:
        # ... création tables et insertion données
    finally:
        conn.close()
    return db_path, xuid
```

**Fichier** : `tests/test_backfill_performance_score.py`  
**Lignes** : 25-60 (approximatif)

---

#### 1.6 `tests/test_data_architecture.py`
**Problème** : Tests créent des DB DuckDB inline sans fixtures propres.

**Actions** :
- Extraire la création de DB dans des fixtures
- Utiliser des noms de fichiers uniques
- Ajouter try/finally pour fermeture

**Fichier** : `tests/test_data_architecture.py`  
**Lignes** : 146-180 (approximatif)

---

#### 1.7 Autres fichiers avec fixtures DuckDB
**Fichiers à vérifier** :
- `tests/test_materialized_views.py`
- `tests/test_duckdb_repository.py`
- `tests/test_season_archive.py`
- `tests/test_sprint1_antagonists.py`

**Actions** :
- Rechercher toutes les occurrences de `duckdb.connect` dans les fixtures
- Appliquer le pattern : nom unique + try/finally + fermeture propre

---

### Checklist Phase 1
- [ ] Corriger `test_cache_duckdb_regressions.py`
- [ ] Corriger `test_sync_ui.py` (2 fixtures)
- [ ] Corriger `test_lazy_loading.py`
- [ ] Corriger `test_sync_performance_score.py`
- [ ] Corriger `test_backfill_performance_score.py`
- [ ] Corriger `test_data_architecture.py`
- [ ] Vérifier et corriger autres fichiers avec fixtures DuckDB
- [ ] Exécuter tests par petits groupes pour valider les corrections

---

## 🎯 Phase 2 : Correction des Tests Polars Échoués

### Objectif
Corriger les tests Polars qui retournent FAILED.

### Tests identifiés comme échoués

#### 2.1 `tests/test_analysis.py` - Tests Polars
**Tests échoués** :
- `test_normal_values_polars` (ligne 46)
- `test_empty_dataframe_polars` (ligne 66)
- `test_zero_deaths_polars` (ligne 83)
- `test_normal_values_polars` (OutcomeRates, ligne 113)
- `test_empty_dataframe_polars` (OutcomeRates, ligne 134)

**Diagnostic** :
1. Examiner la fonction `compute_global_ratio` dans `src/analysis/stats.py`
2. Vérifier que `_normalize_df` fonctionne correctement avec Polars
3. Tester manuellement les fonctions avec des DataFrames Polars

**Actions** :
```python
# Vérifier que _normalize_df convertit bien Polars -> Pandas
def _normalize_df(df: pd.DataFrame | pl.DataFrame) -> pd.DataFrame:
    if isinstance(df, pl.DataFrame):
        return df.to_pandas()
    return df

# Tester que compute_global_ratio fonctionne avec Polars
# Si problème : vérifier les types de retour, les conversions, etc.
```

**Fichier** : `tests/test_analysis.py`  
**Fichiers source** : `src/analysis/stats.py`

**Plan de correction** :
1. Exécuter un test Polars isolé pour voir l'erreur exacte
2. Vérifier que Polars est bien installé dans l'environnement
3. Vérifier que `df.to_pandas()` fonctionne correctement
4. Corriger la fonction si nécessaire
5. Réexécuter les tests

---

#### 2.2 `tests/test_analysis.py` - `build_option_map`
**Tests échoués** :
- `test_normal_values` (ligne ~150)
- `test_with_uuid_suffix` (ligne ~160)
- `test_empty_values` (ligne ~170)

**Diagnostic** :
- La fonction `build_option_map` attend des `pl.Series` en entrée
- Vérifier que les tests passent les bons types

**Actions** :
1. Lire `src/analysis/filters.py` ligne 80+
2. Vérifier la signature de `build_option_map`
3. Corriger les tests pour passer des `pl.Series` au lieu de listes/autres types
4. Ou adapter la fonction pour accepter d'autres types

**Fichier** : `tests/test_analysis.py`  
**Fichier source** : `src/analysis/filters.py`

---

### Checklist Phase 2
- [ ] Exécuter tests Polars isolés pour voir erreurs exactes
- [ ] Vérifier installation Polars dans environnement
- [ ] Corriger `compute_global_ratio` si nécessaire
- [ ] Corriger `compute_outcome_rates` si nécessaire
- [ ] Corriger tests `build_option_map`
- [ ] Réexécuter tous les tests Polars
- [ ] Documenter les corrections

---

## 🎯 Phase 3 : Correction des Autres Erreurs

### Objectif
Corriger les tests qui échouent pour d'autres raisons que les segfaults ou Polars.

### Tests à investiguer

#### 3.1 Tests avec erreurs non identifiées
**Actions** :
1. Exécuter tous les tests avec `--tb=short` pour voir les erreurs
2. Catégoriser les erreurs :
   - Import errors
   - Assertion errors
   - Type errors
   - Logic errors
3. Corriger chaque catégorie systématiquement

---

### Checklist Phase 3
- [ ] Exécuter tous les tests et collecter les erreurs
- [ ] Catégoriser les erreurs
- [ ] Corriger les erreurs une par une
- [ ] Valider les corrections

---

## 🎯 Phase 4 : Validation Finale

### Objectif
S'assurer que tous les tests passent.

### Actions
1. **Exécution complète** :
   ```bash
   pytest tests/ -v --tb=short
   ```

2. **Exécution par groupes** :
   ```bash
   # Tests sans DuckDB
   pytest tests/ --ignore=tests/integration -v
   
   # Tests avec DuckDB
   pytest tests/integration/ -v
   
   # Tests Polars
   pytest tests/ -k "polars" -v
   ```

3. **Rapport final** :
   - Nombre de tests passants
   - Nombre de tests échoués (devrait être 0)
   - Nombre de warnings (documenter si nécessaire)

---

## 📝 Notes Techniques

### Pattern de Correction des Fixtures DuckDB

```python
import uuid
import gc
import duckdb

@pytest.fixture
def temp_duckdb(tmp_path):
    """Crée une base DuckDB temporaire avec nom unique."""
    # Nom unique pour éviter conflits
    db_path = tmp_path / f"test_db_{uuid.uuid4().hex[:8]}.duckdb"
    
    conn = duckdb.connect(str(db_path))
    try:
        # Création des tables
        conn.execute("CREATE TABLE ...")
        # Insertion de données si nécessaire
        conn.execute("INSERT INTO ...")
    finally:
        # Fermeture propre
        conn.close()
        del conn
        gc.collect()  # Aide sur Windows pour libérer lockfiles
    
    return db_path
```

### Vérification Polars

```python
# Vérifier que Polars est disponible
try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None

# Dans les tests
@pytest.mark.skipif(not POLARS_AVAILABLE, reason="Polars not available")
def test_polars_function():
    df = pl.DataFrame({"col": [1, 2, 3]})
    # ... test
```

---

## 🚀 Ordre d'Exécution Recommandé

1. **Phase 1** : Corriger toutes les fixtures DuckDB (priorité haute - élimine les segfaults)
2. **Phase 2** : Corriger les tests Polars (priorité moyenne)
3. **Phase 3** : Corriger les autres erreurs (priorité basse)
4. **Phase 4** : Validation finale

---

## 📊 Métriques de Succès

- ✅ **0 segfaults** lors de l'exécution des tests
- ✅ **Tous les tests Polars passent** (ou skip si Polars non disponible)
- ✅ **Taux de réussite > 95%** (certains tests peuvent être skip pour raisons légitimes)
- ✅ **Pas de régressions** : les tests qui passaient avant continuent de passer

---

## 🔍 Commandes Utiles

```bash
# Exécuter un fichier de test spécifique
pytest tests/test_analysis.py -v

# Exécuter un test spécifique
pytest tests/test_analysis.py::TestComputeGlobalRatio::test_normal_values_polars -v

# Exécuter avec affichage des erreurs détaillées
pytest tests/ -v --tb=short

# Exécuter seulement les tests qui échouent
pytest tests/ --lf -v

# Compter les tests
pytest tests/ --co -q

# Exécuter avec coverage
pytest tests/ --cov=src --cov-report=html
```

---

**Dernière mise à jour** : 2026-02-06  
**Statut** : Plan créé, prêt pour exécution
