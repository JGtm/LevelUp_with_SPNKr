# Rapport d'Analyse des Régressions — 3 février 2026

> **URGENT** : Ce document identifie les régressions critiques et propose un plan de correction en sprints.

---

## Table des matières

1. [Résumé exécutif](#résumé-exécutif)
2. [Régressions identifiées](#régressions-identifiées)
3. [Analyse technique détaillée](#analyse-technique-détaillée)
4. [Plan de correction en sprints](#plan-de-correction-en-sprints)
5. [Dépendances et risques](#dépendances-et-risques)

---

## Résumé exécutif

### Problèmes signalés par l'utilisateur (LISTE EXACTE)

| # | Message exact signalé | Sévérité | Section UI |
|---|----------------------|----------|------------|
| 1 | JGtm dernier match listé : Sam. 17 janvier 2026 | 🔴 CRITIQUE | Dernier match |
| 2 | Précision moyenne : nan% | 🔴 CRITIQUE | KPI / Résumé |
| 3 | Temps du premier kill / première mort ne fonctionne pas | 🟠 MAJEUR | Séries temporelles |
| 4a | Aucune donnée de précision disponible pour ce filtre | 🔴 CRITIQUE | Distribution précision |
| 4b | Score de performance non disponible | 🔴 CRITIQUE | Distribution performance |
| 4c | Pas assez de données de précision/FDA disponibles | 🔴 CRITIQUE | Corrélations Précision vs FDA |
| 5 | Roster indisponible pour ce match (payload MatchStats manquant ou équipe introuvable) | 🔴 CRITIQUE | Match View |
| 6 | Médailles indisponibles pour ce match (ou aucune médaille) | 🔴 CRITIQUE | Match View |
| 7a | Aucun média n'a pu être associé à un match | 🟠 MAJEUR | Bibliothèque médias |
| 7b | ⚠️ Aucune fenêtre temporelle de match disponible pour l'association | 🟠 MAJEUR | Bibliothèque médias |
| 7c | Messages d'informations en double | 🟡 MINEUR | Bibliothèque médias |
| 8 | Médailles sur sélection/filtres : Aucune médaille trouvée (ou payload médailles absent) | 🔴 CRITIQUE | Section médailles filtrées |
| 9 | Page "mes coequipiers" vides de graphique | 🔴 CRITIQUE | Mes coéquipiers |

### Cause racine principale

**L'architecture DuckDB v4 a des fonctions qui retournent des valeurs vides au lieu de charger les données.**

---

## Régressions identifiées

### R1 — Dernier match daté du 17 janvier 2026

**Fichier** : `src/ui/cache.py` → `load_df_optimized()`

**Symptôme** : Les matchs récents ne s'affichent pas.

**Cause probable** :
1. Les données DuckDB ne sont pas à jour (sync incomplet)
2. Le tri par `start_time` ne fonctionne pas correctement
3. Les données sont corrompues ou mal importées

**Code impliqué** :
```python
# src/ui/pages/last_match.py:71-72
last_row = dff.sort_values("start_time").iloc[-1]
```

---

### R2 — Précision moyenne : nan%

**Fichier** : `src/ui/cache.py` → `load_df_optimized()` ligne 654

**Symptôme** : La colonne `accuracy` contient uniquement des valeurs NULL.

**Cause** :
1. La colonne `accuracy` n'est pas remplie lors de la sync
2. Les données de précision ne sont pas extraites du JSON brut
3. DuckDBRepository retourne `None` pour accuracy

**Code impliqué** :
```python
# src/ui/cache.py:654
"accuracy": [m.accuracy for m in matches],
```

---

### R3 — Temps du premier kill / première mort

**Fichier** : `src/data/repositories/duckdb_repo.py` → `get_first_kill_death_times()`

**Symptôme** : "Données d'événements non disponibles"

**Cause** :
1. La table `highlight_events` est vide ou inexistante
2. Le XUID utilisé dans la requête ne correspond pas aux données
3. La synchronisation n'a pas importé les highlight events

**Code impliqué** :
```python
# src/data/repositories/duckdb_repo.py:584-625
def load_first_event_times(self, match_ids, event_type="Kill"):
    # Vérifie sqlite_master au lieu de information_schema pour DuckDB
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='highlight_events'"
    ).fetchall()  # ❌ ERREUR : DuckDB utilise information_schema, pas sqlite_master
```

---

### R4 — Distribution précision : "Aucune donnée de précision disponible"

**Fichier** : `src/ui/pages/timeseries.py` lignes 71-88

**Symptôme** : Message "Aucune donnée de précision disponible pour ce filtre."

**Cause** : Dérivée de R2 — pas de données accuracy dans le DataFrame.

**Code impliqué** :
```python
# src/ui/pages/timeseries.py:83-84
elif len(acc_data) == 0:
    st.info("Aucune donnée de précision disponible pour ce filtre.")
```

---

### R5 — Corrélations : "Pas assez de données de précision/FDA disponibles"

**Fichier** : `src/ui/pages/timeseries.py` lignes 183-199

**Symptôme** : Message "Pas assez de données de précision/FDA disponibles."

**Cause** : Moins de 6 matchs ont à la fois `accuracy` ET `kda` non-NULL.

**Code impliqué** :
```python
# src/ui/pages/timeseries.py:185-199
if "accuracy" in dff.columns and "kda" in dff.columns:
    valid_data = dff.dropna(subset=["accuracy", "kda"])
    if len(valid_data) > 5:
        # ... afficher le graphique
    else:
        st.info("Pas assez de données de précision/FDA disponibles.")
```

**Condition d'échec** : `len(valid_data) <= 5` (moins de 6 matchs valides)

---

### R6 — Score de performance non disponible 🔴 IMPORTANT

**Fichier** : `src/ui/pages/timeseries.py` lignes 137-152

**Symptôme** : "Score de performance non disponible."

**Cause** : **OUBLI D'IMPLÉMENTATION** - La colonne `performance_score` n'est JAMAIS calculée dans `timeseries.py`.

**Comparaison avec d'autres fichiers** :
- `match_history.py:161` → Appelle `compute_performance_series()` ✅
- `session_compare.py:422` → Appelle `compute_performance_series()` ✅
- `timeseries.py` → **Vérifie si la colonne existe mais ne la calcule jamais** ❌

**Code problématique** :
```python
# src/ui/pages/timeseries.py:137-152
if "performance_score" in dff.columns:  # ← La colonne n'existe jamais !
    perf_data = dff["performance_score"].dropna()
    # ...
else:
    st.info("Score de performance non disponible.")  # ← Toujours affiché
```

**Correction requise** :
```python
# AVANT la vérification, il faut calculer le score :
from src.analysis.performance_score import compute_performance_series

# Calculer le score de performance
history_df = df_full if df_full is not None else dff
dff["performance_score"] = compute_performance_series(dff, history_df)

# Ensuite vérifier
if "performance_score" in dff.columns:
    # ...
```

---

### R7 — Roster indisponible

**Fichier** : `src/ui/cache.py` → `cached_load_match_rosters()` lignes 198-215

**Symptôme** : "Roster indisponible pour ce match (payload MatchStats manquant)"

**Cause DIRECTE** :
```python
# src/ui/cache.py:211-212
if _is_duckdb_v4_path(db_path):
    return None  # ❌ RETOURNE TOUJOURS None POUR DUCKDB v4
```

**Impact** : La fonction retourne `None` au lieu de charger les données depuis DuckDB.

---

### R8 & R11 — Médailles indisponibles

**Fichier** : `src/data/repositories/duckdb_repo.py` → `load_match_medals()` et `load_top_medals()`

**Symptôme** : "Médailles indisponibles pour ce match" + "Aucune médaille trouvée"

**Cause probable** :
1. La table `medals_earned` est vide
2. Les médailles n'ont pas été importées lors de la sync
3. Le `match_id` ne correspond pas

**Code impliqué** :
```python
# src/data/repositories/duckdb_repo.py:494-499
try:
    count = conn.execute("SELECT COUNT(*) FROM medals_earned").fetchone()[0]
    if count == 0:
        return []  # ← Table vide
```

---

### R9-R10 — Association médias/matchs

**Fichier** : `src/ui/pages/media_library.py`

**Symptôme** : 
- "Aucun média n'a pu être associé à un match"
- "Aucune fenêtre temporelle de match disponible"
- Messages en double

**Cause** :
1. `_compute_match_windows()` retourne un DataFrame vide car `start_time` est NULL
2. La tolérance temporelle ne correspond pas aux métadonnées des fichiers
3. Double affichage des messages d'erreur

**Code impliqué** :
```python
# src/ui/pages/media_library.py:97-142
def _compute_match_windows(df_full, settings):
    if df_full is None or df_full.empty:
        return pd.DataFrame(...)  # ← Retourne vide
    
    if "match_id" not in cols or "start_time" not in cols:
        return pd.DataFrame(...)  # ← Retourne vide si colonnes manquantes
```

---

### R12 — Page coéquipiers vide

**Fichier** : `src/ui/cache.py` → Fonctions `cached_query_matches_with_friend()` et `cached_same_team_match_ids_with_friend()`

**Symptôme** : Aucun graphique affiché sur la page "Mes coéquipiers"

**Cause DIRECTE** :
```python
# src/ui/cache.py:111-112
if _is_duckdb_v4_path(db_path):
    return ()  # ❌ RETOURNE TOUJOURS UN TUPLE VIDE

# src/ui/cache.py:130-131
if _is_duckdb_v4_path(db_path):
    return []  # ❌ RETOURNE TOUJOURS UNE LISTE VIDE
```

**Impact** : Ces fonctions retournent des valeurs vides au lieu de requêter DuckDB.

---

## Analyse technique détaillée

### Architecture actuelle

```
┌─────────────────────────────────────────────────────────────────┐
│                         APPLICATION UI                          │
│  (src/ui/pages/*.py)                                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      COUCHE CACHE                               │
│  (src/ui/cache.py)                                             │
│                                                                 │
│  ┌─────────────────┐    ┌──────────────────────────────┐       │
│  │ _is_duckdb_v4_  │───►│ SI DuckDB v4 → RETURN VIDE   │ ❌    │
│  │ path()          │    │ (au lieu de charger)          │       │
│  └─────────────────┘    └──────────────────────────────┘       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DUCKDB REPOSITORY                            │
│  (src/data/repositories/duckdb_repo.py)                        │
│                                                                 │
│  ✓ load_matches()        - Fonctionne                          │
│  ✓ load_match_medals()   - Fonctionne (si données présentes)   │
│  ? highlight_events      - Requête mal formée (sqlite_master)  │
│  ✗ Rosters              - Non implémenté pour DuckDB v4        │
│  ✗ Coéquipiers          - Non implémenté pour DuckDB v4        │
└─────────────────────────────────────────────────────────────────┘
```

### Fonctions retournant des valeurs vides pour DuckDB v4

| Fonction | Fichier | Ligne | Retour |
|----------|---------|-------|--------|
| `cached_same_team_match_ids_with_friend()` | cache.py | 111-112 | `()` |
| `cached_query_matches_with_friend()` | cache.py | 130-131 | `[]` |
| `cached_load_match_rosters()` | cache.py | 211-212 | `None` |
| `cached_load_friends()` | cache.py | 689-691 | `[]` |
| `cached_get_match_session_info()` | cache.py | 734-736 | `None` |

### Tables DuckDB requises mais potentiellement vides/manquantes

| Table | Usage | État probable |
|-------|-------|---------------|
| `match_stats` | Statistiques des matchs | ✓ Présente mais accuracy=NULL |
| `medals_earned` | Médailles par match | ? Vide ou mal remplie |
| `highlight_events` | Kill feed, événements | ? Vide ou mal requêtée |
| `teammates_aggregate` | Stats coéquipiers | ? Non utilisée par cache.py |
| `antagonists` | Nemesis/victimes | ✓ Fonctionne |

---

## Plan de correction en sprints

### Sprint 1 — Correction critique : Fonctions cache.py (PRIORITÉ HAUTE)

**Durée estimée** : 4-6 heures

**Objectif** : Faire fonctionner les fonctions qui retournent des valeurs vides pour DuckDB v4.

#### Tâches

| # | Tâche | Fichier | Complexité |
|---|-------|---------|------------|
| 1.1 | Implémenter `cached_load_match_rosters()` pour DuckDB v4 | cache.py | 🟠 Moyenne |
| 1.2 | Implémenter `cached_query_matches_with_friend()` pour DuckDB v4 | cache.py | 🟠 Moyenne |
| 1.3 | Implémenter `cached_same_team_match_ids_with_friend()` pour DuckDB v4 | cache.py | 🟠 Moyenne |
| 1.4 | Corriger la détection de table `highlight_events` (sqlite_master → information_schema) | duckdb_repo.py | 🟢 Facile |

#### Détails techniques

**1.1 — Rosters pour DuckDB v4**

Le problème est que DuckDB v4 n'a pas le JSON brut des rosters. Options :
- **Option A** : Stocker les rosters dans une nouvelle table `match_rosters`
- **Option B** : Extraire depuis `highlight_events` (gamertags des joueurs du match)
- **Option C** : Utiliser l'API Halo pour récupérer les rosters à la volée

Recommandation : **Option B** (utiliser highlight_events existants)

**1.2-1.3 — Requêtes coéquipiers pour DuckDB v4**

Utiliser la table `teammates_aggregate` existante :
```sql
SELECT teammate_xuid, matches_together
FROM teammates_aggregate
WHERE teammate_xuid = ?
```

---

### Sprint 2 — Correction données : Accuracy et Médailles (PRIORITÉ HAUTE)

**Durée estimée** : 3-4 heures

**Objectif** : S'assurer que les données accuracy et médailles sont correctement importées.

#### Tâches

| # | Tâche | Fichier | Complexité |
|---|-------|---------|------------|
| 2.1 | Vérifier le script de sync pour l'import d'accuracy | scripts/sync.py | 🟠 Moyenne |
| 2.2 | Vérifier l'import des médailles | scripts/sync.py | 🟠 Moyenne |
| 2.3 | Ajouter un diagnostic de données dans l'UI | src/ui/*.py | 🟢 Facile |
| 2.4 | Créer un script de validation des données | scripts/validate_db.py | 🟠 Moyenne |

#### Script de diagnostic à créer

```python
# scripts/diagnose_player_db.py
import duckdb
from pathlib import Path

def diagnose(db_path: str):
    conn = duckdb.connect(db_path, read_only=True)
    
    # Vérifier les tables
    tables = conn.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'main'
    """).fetchall()
    
    print(f"Tables présentes: {[t[0] for t in tables]}")
    
    # Vérifier match_stats
    stats = conn.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(accuracy) as with_accuracy,
            MAX(start_time) as last_match,
            AVG(accuracy) as avg_accuracy
        FROM match_stats
    """).fetchone()
    
    print(f"Matchs: {stats[0]}")
    print(f"Avec accuracy: {stats[1]}")
    print(f"Dernier match: {stats[2]}")
    print(f"Accuracy moyenne: {stats[3]}")
    
    # Vérifier medals_earned
    medals = conn.execute("SELECT COUNT(*) FROM medals_earned").fetchone()
    print(f"Médailles: {medals[0]}")
    
    # Vérifier highlight_events
    try:
        events = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()
        print(f"Highlight events: {events[0]}")
    except:
        print("Highlight events: TABLE MANQUANTE")
    
    conn.close()
```

---

### Sprint 3 — Correction médias et messages (PRIORITÉ MOYENNE)

**Durée estimée** : 2-3 heures

**Objectif** : Corriger l'association médias/matchs et les messages en double.

#### Tâches

| # | Tâche | Fichier | Complexité |
|---|-------|---------|------------|
| 3.1 | Corriger `_compute_match_windows()` pour gérer les start_time NULL | media_library.py | 🟢 Facile |
| 3.2 | Supprimer les messages d'info en double | media_library.py | 🟢 Facile |
| 3.3 | Améliorer les messages d'erreur pour le diagnostic | media_library.py | 🟢 Facile |

---

### Sprint 4 — Page coéquipiers (PRIORITÉ HAUTE)

**Durée estimée** : 4-5 heures

**Objectif** : Faire fonctionner la page "Mes coéquipiers" avec DuckDB v4.

#### Tâches

| # | Tâche | Fichier | Complexité |
|---|-------|---------|------------|
| 4.1 | Créer `load_matches_with_teammate_duckdb()` | duckdb_repo.py | 🟠 Moyenne |
| 4.2 | Modifier `cached_query_matches_with_friend()` pour utiliser la nouvelle fonction | cache.py | 🟢 Facile |
| 4.3 | Ajouter des vérifications de DataFrame vide dans les graphiques | teammates_charts.py | 🟢 Facile |
| 4.4 | Tester avec plusieurs coéquipiers | - | 🟢 Facile |

#### Implémentation proposée

```python
# duckdb_repo.py - Nouvelle méthode
def load_matches_with_teammate(self, teammate_xuid: str) -> list[str]:
    """Retourne les match_id joués avec un coéquipier.
    
    Utilise highlight_events pour détecter la présence dans le même match.
    """
    conn = self._get_connection()
    
    # Méthode 1: Via highlight_events (si disponible)
    try:
        result = conn.execute("""
            SELECT DISTINCT me.match_id
            FROM highlight_events me
            JOIN highlight_events tm ON me.match_id = tm.match_id
            WHERE me.xuid = ? AND tm.xuid = ?
        """, [self._xuid, teammate_xuid])
        return [row[0] for row in result.fetchall()]
    except:
        pass
    
    # Méthode 2: Via teammates_aggregate (liste des matchs partagés)
    # TODO: nécessite une nouvelle table match_teammates
    return []
```

---

### Sprint 5 — Tests et validation (PRIORITÉ MOYENNE)

**Durée estimée** : 2-3 heures

**Objectif** : Valider toutes les corrections et prévenir les régressions futures.

#### Tâches

| # | Tâche | Fichier | Complexité |
|---|-------|---------|------------|
| 5.1 | Créer des tests unitaires pour les fonctions cache.py | tests/test_cache.py | 🟠 Moyenne |
| 5.2 | Créer des tests pour DuckDBRepository | tests/test_duckdb_repo.py | 🟠 Moyenne |
| 5.3 | Ajouter des tests d'intégration UI | tests/test_ui_pages.py | 🔴 Complexe |
| 5.4 | Documenter les changements | docs/*.md | 🟢 Facile |

---

## Dépendances et risques

### Dépendances

```
Sprint 1 ──► Sprint 4 (les fonctions cache.py sont nécessaires pour coéquipiers)
Sprint 2 ──► Sprint 3 (les données doivent être présentes pour l'association médias)
```

### Risques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Données DuckDB corrompues | 🔴 Élevé | Vérifier avec script diagnostic avant de commencer |
| Schéma DuckDB incompatible | 🟠 Moyen | Vérifier la version et migrer si nécessaire |
| Performance dégradée avec nouvelles requêtes | 🟡 Faible | Ajouter des index si nécessaire |

### Ordre de priorité recommandé

1. **Sprint 2** — Diagnostiquer l'état des données (AVANT tout code)
2. **Sprint 1** — Corriger cache.py
3. **Sprint 4** — Page coéquipiers
4. **Sprint 3** — Médias
5. **Sprint 5** — Tests

---

## Actions immédiates requises

### Avant de coder

1. **Exécuter le diagnostic** sur la base JGtm :
   ```bash
   python scripts/diagnose_player_db.py data/players/JGtm/stats.duckdb
   ```

2. **Vérifier que les bases existent** :
   ```bash
   ls -la data/players/JGtm/
   ls -la data/warehouse/
   ```

3. **Vérifier le dernier sync** :
   ```bash
   python scripts/sync.py --status --gamertag JGtm
   ```

---

## Checklist de validation finale (correspondant à chaque point signalé)

| # | Point à valider | Statut |
|---|-----------------|--------|
| 1 | Dernier match JGtm affiché est récent (pas 17 janvier) | ⬜ |
| 2 | Précision moyenne affiche un % valide (pas nan%) | ⬜ |
| 3 | Temps premier kill/mort affiche le graphique | ⬜ |
| 4a | Distribution précision affiche l'histogramme | ⬜ |
| 4b | Score de performance affiche l'histogramme | ⬜ |
| 4c | Corrélations Précision vs FDA affiche le scatter | ⬜ |
| 5 | Roster du match s'affiche | ⬜ |
| 6 | Médailles du match s'affichent | ⬜ |
| 7a | Médias sont associés aux matchs | ⬜ |
| 7b | Fenêtres temporelles fonctionnent | ⬜ |
| 7c | Pas de messages en double | ⬜ |
| 8 | Médailles sur sélection/filtres s'affichent | ⬜ |
| 9 | Page coéquipiers affiche des graphiques | ⬜ |

---

*Document créé le 3 février 2026*
*Auteur : Agent IA*
