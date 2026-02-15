# Optimisations Sync — Sprint 6

> **Date** : 2026-02-14  
> **Objectif** : Réduire significativement le temps de synchronisation et les appels API

---

## Résumé des optimisations

| # | Optimisation | Gain estimé |
|---|-------------|-------------|
| 6.1 | Parallélisation appels API skill + events | -50% latence réseau par match |
| 6.2 | Performance score différé en batch post-sync | -80% temps CPU pendant sync |
| 6.3 | Calcul batch vectorisé post-sync | 1 chargement historique au lieu de N |
| 6.4 | Commits DB groupés (tous les 10 matchs) | -90% I/O disque |
| 6.5 | Rate limit augmenté (10 req/s, 5 matchs parallèles) | +100% débit API |

---

## 6.1 — Parallélisation des appels API

### Avant (séquentiel)

```python
skill_json = await client.get_skill_stats(match_id, xuids)    # ~200ms
highlight_events = await client.get_highlight_events(match_id)  # ~200ms
# Total : ~400ms
```

### Après (asyncio.gather)

```python
api_tasks = []
if options.with_skill and xuids:
    api_tasks.append(client.get_skill_stats(match_id, xuids))
if options.with_highlight_events:
    api_tasks.append(client.get_highlight_events(match_id))

api_results = await asyncio.gather(*api_tasks, return_exceptions=True)
# Total : ~200ms (max des deux)
```

**Gestion des erreurs** : chaque résultat est vérifié individuellement. Une erreur sur `skill` n'empêche pas d'obtenir les `events`.

---

## 6.2 — Performance score différé

### Problème

Pendant la sync, chaque match déclenchait :
1. Une requête SQL chargeant **tout l'historique** (potentiellement 1000+ matchs)
2. Un calcul CPU intensif (8 métriques, percentiles, moyenne pondérée)
3. Un `conn.commit()` individuel

Pour 100 nouveaux matchs, cela signifiait 100 chargements de l'historique complet.

### Solution

Nouveau champ `SyncOptions.defer_performance_score` (par défaut `True`) :
- **Pendant la sync** : les matchs sont insérés avec `performance_score = NULL`
- **Après la sync** : un seul appel à `batch_compute_performance_scores()` calcule tous les scores manquants

```python
# Dans SyncOptions
defer_performance_score: bool = True  # Calcul batch post-sync
```

### Migration

Pour forcer l'ancien comportement (calcul inline pendant sync) :
```python
opts = SyncOptions(defer_performance_score=False)
```

---

## 6.3 — Calcul batch des performance scores

### Méthode `DuckDBSyncEngine.batch_compute_performance_scores()`

```python
def batch_compute_performance_scores(self) -> int:
    """Calcule les performance_score pour tous les matchs où il est NULL.

    Returns:
        Nombre de matchs mis à jour.
    """
```

**Algorithme** :
1. Charge **tous** les matchs triés par date (1 seule requête SQL)
2. Identifie les matchs avec `performance_score IS NULL`
3. Pour chaque match NULL avec assez d'historique, calcule le score
4. Batch UPDATE en une seule transaction

**Avantages** :
- 1 seule requête SQL au lieu de N
- L'historique est un slice du DataFrame chargé (pas de re-requête)
- 1 seul commit pour tous les updates

---

## 6.4 — Batching des commits DB

### Avant

```python
# Commit final unique après TOUS les matchs
# → Risque de perte totale en cas de crash
conn.commit()
```

### Après

```python
# Commit intermédiaire tous les N matchs (configurable)
batch_commit_size: int = 10  # dans SyncOptions

# Lors du traitement :
if result.matches_inserted % options.batch_commit_size == 0:
    conn.commit()  # Sauvegarde intermédiaire
```

**Avantage** : en cas de crash, on perd au maximum 10 matchs au lieu de tout.

Le `conn.commit()` individuel dans `_compute_and_update_performance_score()` a également été supprimé.

---

## 6.5 — Rate limit augmenté

| Paramètre | Avant | Après |
|-----------|-------|-------|
| `requests_per_second` | 5 | **10** |
| `parallel_matches` | 3 | **5** |

Basé sur des tests empiriques montrant que l'API Halo Infinite supporte confortablement 10 req/s.

---

## Gains combinés estimés

| Métrique | Avant Sprint 6 | Après Sprint 6 | Gain |
|----------|----------------|----------------|------|
| Temps/match (nouveau) | ~3s | ~1.5s | **-50%** |
| Calcul perf scores (100 matchs) | 100 requêtes SQL | 1 requête SQL | **-99%** |
| Commits DB (100 matchs) | 100+ | 10 + 1 final | **-89%** |
| Débit API | 5 req/s × 3 parallel | 10 req/s × 5 parallel | **×3.3** |

---

## Configuration

### Options par défaut (déjà optimisées)

```python
opts = SyncOptions()
# requests_per_second=10
# parallel_matches=5
# defer_performance_score=True
# batch_commit_size=10
```

### Mode conservateur

```python
opts = SyncOptions(
    requests_per_second=5,
    parallel_matches=3,
    defer_performance_score=False,
    batch_commit_size=0,
)
```

---

## Tests

```bash
# Tests Sprint 6
python -m pytest tests/test_sync_sprint6_optimizations.py -v

# Tests sync complets
python -m pytest tests/test_sync_engine.py tests/test_sync_performance_score.py -v
```
