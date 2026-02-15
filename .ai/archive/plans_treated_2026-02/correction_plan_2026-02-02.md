# Plan de Correction — Revue Code LevelUp

> Généré le 2026-02-02 suite à la revue de code automatisée (11 fichiers, ~1167 lignes)

## Résumé

| Catégorie | Issues | Statut |
|-----------|--------|--------|
| Signal Fort (bloquant) | 0 | ✅ |
| Signal Moyen (recommandé) | 5 | ✅ Corrigé |
| Signal Faible (optionnel) | 5 | ✅ Corrigé |

---

## Phase 1 : Corrections Prioritaires (Signal Moyen)

### 1.1 Type hints incorrects (M1)

**Fichier** : `src/ui/cache.py`  
**Lignes** : 163, 174  
**Problème** : `db_key: str | None` au lieu de `tuple[int, int] | None`  
**Impact** : Peut causer des bugs de cache Streamlit si comparaison stricte des clés

**Action** :
```python
# Ligne 163 - AVANT
def cached_load_highlight_events_for_match(..., db_key: str | None = None):

# Ligne 163 - APRÈS  
def cached_load_highlight_events_for_match(..., db_key: tuple[int, int] | None = None):

# Ligne 174 - Même correction pour cached_load_match_player_gamertags
```

**Effort** : ~5 min  
**Statut** : ✅ Corrigé

---

### 1.2 Centraliser les chemins (M4, M5)

**Fichiers** : `launcher.py`, `src/ui/multiplayer.py`  
**Problème** : Chemins définis localement au lieu d'utiliser `src/utils/paths`  
**Impact** : Duplication, risque d'incohérence si chemins changent

**Action launcher.py** :
```python
# AVANT (lignes 53-56)
PLAYERS_DIR = REPO_ROOT / "data" / "players"
WAREHOUSE_DIR = REPO_ROOT / "data" / "warehouse"
PLAYER_DB_FILENAME = "stats.duckdb"
METADATA_DB_FILENAME = "metadata.duckdb"

# APRÈS
from src.utils.paths import PLAYERS_DIR, WAREHOUSE_DIR, PLAYER_DB_FILENAME, METADATA_DB_FILENAME
```

**Action src/ui/multiplayer.py** :
```python
# AVANT (ligne 37)
_PLAYERS_DIR = Path(__file__).resolve().parents[2] / "data" / "players"

# APRÈS
from src.utils.paths import PLAYERS_DIR
_PLAYERS_DIR = PLAYERS_DIR
```

**Effort** : ~10 min  
**Statut** : ✅ Corrigé

---

### 1.3 Connexions DuckDB directes (M2, M3)

**Fichiers** : `launcher.py:239,283`, `src/app/data_loader.py:155`  
**Problème** : Utilise `duckdb.connect()` directement au lieu de `DuckDBRepository`  
**Impact** : Incohérence architecturale, connexions potentiellement non fermées

**Options** :

| Option | Description | Recommandation |
|--------|-------------|----------------|
| A | Conserver (justifié pour perf/simplicité) | ⚠️ Acceptable |
| B | Créer `DuckDBRepository.get_match_count_static(db_path)` | ✅ Propre |
| C | Ajouter context manager `try/finally` | ✅ Compromis |

**Action recommandée (Option C)** :
```python
# AVANT
con = duckdb.connect(str(db_path), read_only=True)
result = con.execute("SELECT COUNT(*) FROM match_stats").fetchone()
total_matches = result[0] if result else 0
con.close()

# APRÈS
try:
    con = duckdb.connect(str(db_path), read_only=True)
    result = con.execute("SELECT COUNT(*) FROM match_stats").fetchone()
    total_matches = result[0] if result else 0
finally:
    con.close()
```

**Effort** : ~15 min  
**Statut** : ✅ Corrigé

---

## Phase 2 : Améliorations Optionnelles (Signal Faible)

### 2.1 Garantir fermeture des connexions (m1)

**Fichier** : `src/ui/cache.py`  
**Lignes** : 383, 841, 924, 1010  
**Problème** : `repo.close()` non appelé si exception

**Action** :
```python
# AVANT
repo = DuckDBRepository(db_path, xuid="", read_only=True)
matches = repo.load_matches(...)
repo.close()

# APRÈS
repo = DuckDBRepository(db_path, xuid="", read_only=True)
try:
    matches = repo.load_matches(...)
finally:
    repo.close()
```

**Effort** : ~10 min (4 occurrences)  
**Statut** : ✅ Corrigé

---

### 2.2 Supprimer code mort (m2)

**Fichier** : `src/ui/cache.py`  
**Problème** : 4 fonctions jamais appelées

| Fonction | Ligne | Remplacée par |
|----------|-------|---------------|
| `load_df()` | 276 | `load_df_optimized()` |
| `cached_load_sessions()` | 480 | — |
| `cached_compute_sessions_db_optimized()` | 545 | `cached_compute_sessions_db()` |
| `load_df_smart()` | 663 | `load_df_optimized()` |

**Action** : Supprimer ces 4 fonctions

**Effort** : ~5 min  
**Statut** : ✅ Corrigé

---

### 2.3 Refactoring fonctions longues (m3)

**Fichier** : `launcher.py`  
**Lignes** : 507 (`_cmd_sync`), 627 (`_interactive`)  
**Problème** : ~80 lignes chacune

**Action** : Reporter (fonctionne correctement, faible priorité)

**Effort** : ~30 min  
**Statut** : 📅 Reporté

---

### 2.4 Extraire magic number (m4)

**Fichier** : `launcher.py:464`  
**Problème** : `time.sleep(1.2)` sans constante nommée

**Action** :
```python
# Ajouter en haut du fichier (~ligne 50)
STREAMLIT_STARTUP_DELAY_SECONDS = 1.2

# Ligne 464
time.sleep(STREAMLIT_STARTUP_DELAY_SECONDS)
```

**Effort** : ~2 min  
**Statut** : ✅ Corrigé

---

### 2.5 Renommer variable confuse (m5)

**Fichier** : `streamlit_app.py:264`  
**Problème** : `qp_token` contient (page, match_id), pas un token

**Action** :
```python
# AVANT
qp_token = (str(qp_page or "").strip(), str(qp_mid or "").strip())
if any(qp_token) and st.session_state.get("_consumed_query_params") != qp_token:
    st.session_state["_consumed_query_params"] = qp_token

# APRÈS
qp_params = (str(qp_page or "").strip(), str(qp_mid or "").strip())
if any(qp_params) and st.session_state.get("_consumed_query_params") != qp_params:
    st.session_state["_consumed_query_params"] = qp_params
```

**Effort** : ~2 min  
**Statut** : ✅ Corrigé

---

## Récapitulatif

| Phase | Tâches | Effort | Priorité |
|-------|--------|--------|----------|
| **Phase 1** | M1, M4, M5, M2/M3 | ~30 min | ✅ Corrigé |
| **Phase 2** | m1, m2, m4, m5 | ~20 min | ✅ Corrigé |
| **Reporter** | m3 (refactoring) | ~30 min | ⚪ Reporté |

**Total Phase 1 + 2** : ~50 min ✅ Terminé

---

## Commande pour exécuter

```
Demander à l'agent : "Exécute le plan de correction Phase 1" ou "Phase 1 + Phase 2"
```

---

## Points Positifs (conservés)

- ✅ Sécurité : Aucun token exposé, pas de SQL injection
- ✅ Patterns Streamlit : Cache approprié avec TTL
- ✅ Gestion erreurs : Fallbacks robustes
- ✅ Architecture : Détection auto DuckDB v4 vs Legacy

---

*Généré par l'agent de revue de code LevelUp*
