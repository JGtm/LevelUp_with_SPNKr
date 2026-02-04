# Sprints de correction des régressions

> **Date** : 3 février 2026
> **Priorité** : CRITIQUE
> **Statut** : EN ATTENTE DE DIAGNOSTIC

---

## Checklist pré-sprint

- [ ] Exécuter le diagnostic des données DuckDB (Sprint 2.1)
- [ ] Confirmer l'existence de `data/players/JGtm/stats.duckdb`
- [ ] Confirmer l'existence de `data/warehouse/metadata.duckdb`
- [ ] Vérifier le statut de la dernière synchronisation

## Points signalés par l'utilisateur (13 total)

| # | Message exact | Sprint |
|---|---------------|--------|
| 1 | Dernier match : Sam. 17 janvier 2026 | Sprint 2 |
| 2 | Précision moyenne : nan% | Sprint 2 |
| 3 | Temps premier kill/mort ne fonctionne pas | Sprint 2 + 1 |
| 4a | Aucune donnée de précision disponible pour ce filtre | Sprint 2 |
| 4b | Score de performance non disponible | Sprint 3 |
| 4c | Pas assez de données de précision/FDA disponibles | Sprint 2 |
| 5 | Roster indisponible (payload MatchStats manquant) | Sprint 1 |
| 6 | Médailles indisponibles pour ce match | Sprint 2 |
| 7a | Aucun média associé aux matchs | Sprint 3 |
| 7b | Aucune fenêtre temporelle disponible | Sprint 2 + 3 |
| 7c | Messages d'info en double | Sprint 3 |
| 8 | Médailles sur filtres : Aucune médaille trouvée | Sprint 2 |
| 9 | Page coéquipiers vide de graphiques | Sprint 1 + 4 |

---

## Sprint 1 — Cache.py : Fonctions DuckDB v4

**Priorité** : 🔴 CRITIQUE
**Durée estimée** : 4-6 heures
**Statut** : ⏳ EN ATTENTE

### Problème

Les fonctions suivantes dans `src/ui/cache.py` retournent des valeurs vides pour DuckDB v4 au lieu de charger les données :

| Fonction | Ligne | Retour actuel | Impact |
|----------|-------|---------------|--------|
| `cached_same_team_match_ids_with_friend()` | 111-112 | `()` | Page coéquipiers vide |
| `cached_query_matches_with_friend()` | 130-131 | `[]` | Page coéquipiers vide |
| `cached_load_match_rosters()` | 211-212 | `None` | Roster indisponible |
| `cached_load_friends()` | 689-691 | `[]` | Liste amis vide |
| `cached_get_match_session_info()` | 734-736 | `None` | Info session manquante |

### Tâches

- [ ] **1.1** Implémenter `load_match_rosters_duckdb()` dans `duckdb_repo.py`
  - Utiliser `highlight_events` pour extraire les gamertags des joueurs
  - Identifier l'équipe via `team_id` dans `match_stats`
  
- [ ] **1.2** Implémenter `load_matches_with_teammate()` dans `duckdb_repo.py`
  - Requêter les match_id partagés via `highlight_events` ou nouvelle table
  
- [ ] **1.3** Modifier `cached_load_match_rosters()` pour appeler la nouvelle fonction
  
- [ ] **1.4** Modifier `cached_query_matches_with_friend()` pour appeler la nouvelle fonction
  
- [ ] **1.5** Corriger la requête `sqlite_master` → `information_schema.tables` dans `duckdb_repo.py:605`

### Fichiers à modifier

- `src/ui/cache.py`
- `src/data/repositories/duckdb_repo.py`

### Tests de validation

```bash
# Après modification, tester :
python -c "
from src.data.repositories.duckdb_repo import DuckDBRepository
repo = DuckDBRepository('data/players/JGtm/stats.duckdb', '2533274823110022')
print('Match count:', repo.get_match_count())
# Tester les nouvelles fonctions ici
"
```

---

## Sprint 2 — Diagnostic et correction des données

**Priorité** : 🔴 CRITIQUE
**Durée estimée** : 3-4 heures
**Statut** : ⏳ EN ATTENTE

### Problème

Les données suivantes semblent manquantes ou NULL :
- `accuracy` dans `match_stats` → nan%
- `medals_earned` → vide ou mal remplie
- `highlight_events` → vide ou mal requêtée

### Tâches

- [ ] **2.1** Créer `scripts/diagnose_player_db.py`
  - Compter les lignes par table
  - Vérifier les NULL dans accuracy
  - Vérifier la date du dernier match
  - Afficher les statistiques de remplissage
  
- [ ] **2.2** Exécuter le diagnostic sur JGtm
  
- [ ] **2.3** Si accuracy est NULL partout :
  - Vérifier `scripts/sync.py` pour l'extraction d'accuracy
  - Corriger le mapping si nécessaire
  - Re-sync les données
  
- [ ] **2.4** Si medals_earned est vide :
  - Vérifier `scripts/sync.py` pour l'import des médailles
  - Corriger et re-sync

### Script de diagnostic

```python
#!/usr/bin/env python3
"""Diagnostic de la base de données joueur."""

import sys
import duckdb

def diagnose(db_path: str) -> dict:
    conn = duckdb.connect(db_path, read_only=True)
    results = {}
    
    # Tables présentes
    tables = conn.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'main'
    """).fetchall()
    results['tables'] = [t[0] for t in tables]
    
    # Stats match_stats
    results['match_stats'] = conn.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(accuracy) as with_accuracy,
            COUNT(CASE WHEN accuracy IS NULL THEN 1 END) as null_accuracy,
            MAX(start_time) as last_match,
            MIN(start_time) as first_match,
            AVG(accuracy) as avg_accuracy
        FROM match_stats
    """).fetchone()
    
    # Stats medals_earned
    try:
        results['medals'] = conn.execute("""
            SELECT COUNT(*), COUNT(DISTINCT match_id)
            FROM medals_earned
        """).fetchone()
    except:
        results['medals'] = (0, 0)
    
    # Stats highlight_events
    try:
        results['highlight_events'] = conn.execute("""
            SELECT COUNT(*), COUNT(DISTINCT match_id)
            FROM highlight_events
        """).fetchone()
    except:
        results['highlight_events'] = None
    
    conn.close()
    return results

if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "data/players/JGtm/stats.duckdb"
    r = diagnose(db)
    
    print("=" * 60)
    print(f"DIAGNOSTIC: {db}")
    print("=" * 60)
    
    print(f"\nTables présentes: {r['tables']}")
    
    ms = r['match_stats']
    print(f"\nMATCH_STATS:")
    print(f"  Total matchs: {ms[0]}")
    print(f"  Avec accuracy: {ms[1]} ({100*ms[1]/ms[0]:.1f}%)" if ms[0] else "  Avec accuracy: 0")
    print(f"  Sans accuracy: {ms[2]}")
    print(f"  Dernier match: {ms[3]}")
    print(f"  Premier match: {ms[4]}")
    print(f"  Accuracy moyenne: {ms[5]:.2f}%" if ms[5] else "  Accuracy moyenne: NULL")
    
    print(f"\nMEDALS_EARNED:")
    print(f"  Total médailles: {r['medals'][0]}")
    print(f"  Matchs distincts: {r['medals'][1]}")
    
    print(f"\nHIGHLIGHT_EVENTS:")
    if r['highlight_events']:
        print(f"  Total events: {r['highlight_events'][0]}")
        print(f"  Matchs distincts: {r['highlight_events'][1]}")
    else:
        print("  TABLE MANQUANTE OU ERREUR")
```

---

## Sprint 3 — Score de performance + Médias

**Priorité** : 🔴 CRITIQUE (score) + 🟠 MAJEUR (médias)
**Durée estimée** : 3-4 heures
**Statut** : ⏳ EN ATTENTE

### Problème 1 : Score de performance non disponible

**Fichier** : `src/ui/pages/timeseries.py`

Le code vérifie si la colonne `performance_score` existe mais **ne la calcule jamais**.

Comparaison :
- `match_history.py:161` → Appelle `compute_performance_series()` ✅
- `session_compare.py:422` → Appelle `compute_performance_series()` ✅
- `timeseries.py` → **Ne calcule pas le score** ❌

### Tâches Score de Performance

- [ ] **3.0** Corriger `timeseries.py` pour calculer le score de performance
  
```python
# AJOUTER au début de render_timeseries_page() après les vérifications

from src.analysis.performance_score import compute_performance_series

# Calculer le score de performance AVANT d'afficher les distributions
history_df = df_full if df_full is not None else dff
dff["performance_score"] = compute_performance_series(dff, history_df)
```

- [x] ~~**3.0b** Vérifier que `df_full` est bien passé~~ → Confirmé dans `page_router.py:159`

### Problème 2 : Association médias/matchs

- Messages en double ("Aucun média associé" + "Aucune fenêtre temporelle")
- `_compute_match_windows()` retourne vide si `start_time` est NULL

### Tâches Médias

- [ ] **3.1** Supprimer le message redondant dans `media_library.py`
  - Garder uniquement le message le plus informatif
  
- [ ] **3.2** Améliorer `_compute_match_windows()` pour afficher un diagnostic
  - Compter combien de matchs ont `start_time` NULL
  - Afficher un message clair si c'est le cas
  
- [ ] **3.3** Ajouter un fallback si `time_played_seconds` est NULL
  - Utiliser une durée par défaut de 12 minutes

### Fichiers à modifier

- `src/ui/pages/timeseries.py` (CRITIQUE)
- `src/ui/pages/media_library.py`

---

## Sprint 4 — Page coéquipiers

**Priorité** : 🔴 CRITIQUE
**Durée estimée** : 4-5 heures
**Statut** : ⏳ EN ATTENTE
**Dépend de** : Sprint 1

### Problème

La page "Mes coéquipiers" est vide car les fonctions de chargement retournent des listes vides.

### Tâches

- [ ] **4.1** Implémenter `load_shared_match_ids()` dans `duckdb_repo.py`
  - Retourne les match_id où les deux joueurs apparaissent
  
- [ ] **4.2** Créer une table `match_players` lors de la sync
  - Colonnes : match_id, xuid, team_id, gamertag
  - Permet des requêtes rapides sur les coéquipiers
  
- [ ] **4.3** Modifier `cached_friend_matches_df()` pour utiliser DuckDB
  
- [ ] **4.4** Ajouter des vérifications de DataFrame vide dans `teammates_charts.py`
  - Afficher un message clair au lieu d'un graphique vide

### Fichiers à modifier

- `src/data/repositories/duckdb_repo.py`
- `src/ui/cache.py`
- `src/ui/pages/teammates.py`
- `src/ui/pages/teammates_charts.py`
- `scripts/sync.py` (pour créer match_players)

---

## Sprint 5 — Tests et validation

**Priorité** : 🟠 MAJEUR
**Durée estimée** : 2-3 heures
**Statut** : ⏳ EN ATTENTE
**Dépend de** : Sprints 1-4

### Tâches

- [ ] **5.1** Créer `tests/test_cache_duckdb.py`
  - Tester toutes les fonctions avec mock DuckDB
  
- [ ] **5.2** Créer `tests/test_duckdb_repo.py`
  - Tester les nouvelles méthodes
  
- [ ] **5.3** Ajouter des tests de smoke pour l'UI
  - Vérifier que les pages ne crashent pas
  
- [ ] **5.4** Mettre à jour la documentation
  - Documenter les nouvelles tables
  - Documenter les limitations DuckDB v4

---

## Résumé de l'ordre d'exécution

```
┌───────────────────────────────────────────────────────────────┐
│  1. DIAGNOSTIC (Sprint 2.1-2.2)                              │
│     Vérifier l'état réel des données avant de coder          │
└───────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  2. CORRECTION DONNÉES (Sprint 2.3-2.4)                      │
│     Si données manquantes, corriger sync.py et re-sync       │
└───────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  3. FONCTIONS CACHE.PY (Sprint 1)                            │
│     Implémenter les fonctions DuckDB v4                      │
└───────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  4. PAGE COÉQUIPIERS (Sprint 4)                              │
│     Dépend des fonctions cache.py                            │
└───────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  5. MÉDIAS (Sprint 3)                                        │
│     Corrections mineures                                      │
└───────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  6. TESTS (Sprint 5)                                         │
│     Validation finale                                         │
└───────────────────────────────────────────────────────────────┘
```

---

## Métriques de succès (correspondant aux 13 points signalés)

| # | Point | Avant | Objectif |
|---|-------|-------|----------|
| 1 | Dernier match JGtm | 17 jan 2026 | Date récente |
| 2 | Précision moyenne | nan% | XX.X% |
| 3 | Premier kill/mort | "Données non disponibles" | Graphique affiché |
| 4a | Distribution précision | "Aucune donnée" | Histogramme affiché |
| 4b | Distribution performance | "Non disponible" | Histogramme affiché |
| 4c | Corrélation Précision/FDA | "Pas assez de données" | Scatter plot affiché |
| 5 | Roster | "Indisponible" | Tableau affiché |
| 6 | Médailles du match | "Indisponible" | Grille affichée |
| 7a | Médias associés | 0 | > 0 |
| 7b | Fenêtres temporelles | "Aucune fenêtre" | Fonctionnel |
| 7c | Messages doublons | 2 messages | 1 message |
| 8 | Médailles filtrées | "Aucune trouvée" | Grille affichée |
| 9 | Page coéquipiers | Vide | Graphiques affichés |

---

*Dernière mise à jour : 3 février 2026*
