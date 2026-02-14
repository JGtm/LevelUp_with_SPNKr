# Plan d'Optimisation : Synchronisation DuckDB v4

**Contexte** : Performances actuelles ~16s/match lors d'un sync delta.  
**Objectif** : Atteindre ≤2-3s/match (gain 5-8x).

---

## 🔍 Diagnostic : Goulots d'Étranglement Identifiés

### 1. **Appels API Séquentiels par Match** ⚠️ CRITIQUE

**Localisation** : [src/data/sync/engine.py](src/data/sync/engine.py#L683-L691)

```python
# PROBLÈME : Appels séquentiels (pas de parallélisation)
if options.with_skill and xuids:
    skill_json = await client.get_skill_stats(match_id, xuids)

if options.with_highlight_events:
    highlight_events = await client.get_highlight_events(match_id)
```

**Impact** :
- Pour chaque match : 1 appel stats + 1 appel skill + 1 appel events = **3 appels séquentiels**
- Avec rate limit 5 req/s et latence réseau (~500ms-1s par appel), cela donne **~5-7s par match minimum**

**Solution Existante Non Utilisée** :
La méthode `SPNKrAPIClient.get_match_data()` existe déjà et parallélise skill + events avec `asyncio.gather` ([api_client.py](src/data/sync/api_client.py#L492-L497)), mais elle n'est **PAS utilisée** dans le code de sync.

---

### 2. **Calcul de Performance Score en Temps Réel** ⚠️ IMPORTANT

**Localisation** : [src/data/sync/engine.py](src/data/sync/engine.py#L768-L772)

```python
# PROBLÈME : Calcul lourd pour chaque match
self._compute_and_update_performance_score(match_id, match_row)
```

**Impact** :
- Pour chaque match inséré, requête SELECT de tout l'historique avec `WHERE start_time < current_match`
- Calcul Polars sur cet historique
- UPDATE pour persister le score
- Complexité croissante avec le nombre de matchs (O(n²) sur la session de sync)

**Estimation** : **~3-5s par match** pour 500+ matchs historiques

---

### 3. **Lock DB Global Bloquant la Parallélisation** 🔒

**Localisation** : [src/data/sync/engine.py](src/data/sync/engine.py#L739)

```python
# PROBLÈME : Lock global empêche les écritures concurrentes
async with self._db_lock:
    self._insert_match_row(match_row)
    # ... toutes les autres insertions
    self._compute_and_update_performance_score(match_id, match_row)
```

**Impact** :
- Même avec `parallel_matches=3`, les insertions DB sont **strictement séquentielles**
- Le calcul de score (lourd) se fait dans la section critique
- Aucun bénéfice du semaphore pour les écritures

---

### 4. **Pas de Commit Batchés**

**Constat** :
- Chaque match est committé individuellement via les insertions
- Pas de batching des INSERTs pour réduire les I/O
- Autocommit implicite sur chaque opération

**Impact** : **~1-2s** de latence I/O cumulée

---

### 5. **Rate Limiting Conservateur**

**Configuration actuelle** :
```python
requests_per_second: int = 5  # SyncOptions par défaut
parallel_matches: int = 3     # Seulement 3 matchs en parallèle
```

**Impact** :
- Avec 3 appels/match et 3 matchs en parallèle : 9 requêtes/s théoriques
- Mais rate limit de 5 req/s bride à ~1.67 match/s
- La parallélisation est sous-exploitée

---

## 🎯 Plan d'Optimisation (par priorité)

### **Phase 1 : Quick Wins (impact immédiat)** 🚀

#### 1.1 Paralléliser les Appels API par Match
**Objectif** : Réduire de 5-7s à 2-3s par match

**Modifications** :
- Remplacer les appels séquentiels par `asyncio.gather` dans `_process_single_match`
- Fusionner `get_skill_stats` + `get_highlight_events` en un seul groupe parallèle

**Fichiers** : [src/data/sync/engine.py](src/data/sync/engine.py#L683-L691)

```python
# AVANT (séquentiel)
skill_json = await client.get_skill_stats(match_id, xuids)
highlight_events = await client.get_highlight_events(match_id)

# APRÈS (parallèle)
skill_json, highlight_events = await asyncio.gather(
    client.get_skill_stats(match_id, xuids) if xuids else asyncio.sleep(0),
    client.get_highlight_events(match_id),
    return_exceptions=True,
)
```

**Gain estimé** : **-60%** du temps par match (5-7s → 2-3s)

---

#### 1.2 Optimiser le Calcul des Scores de Performance
**Objectif** : Retirer le calcul du chemin critique tout en respectant la dépendance séquentielle

**⚠️ CONTRAINTE CRITIQUE** : Le score de chaque match dépend de l'historique **avant** lui.  
→ On ne peut PAS recalculer en parallèle ou dans le désordre.

**Stratégies** :

**Option A : Calcul Post-Sync en Batch Ordonné** ⭐ RECOMMANDÉ
- Désactiver pendant la sync (`compute_performance_scores=False`)
- Après insertion de tous les matchs, faire **UNE passe unique** ordonnée par `start_time`
- Charger l'historique une seule fois, puis ajouter chaque match au fur et à mesure
```python
# Pseudo-code
history_df = load_all_matches(order_by="start_time ASC")
for match in new_matches_ordered:
    score = compute_score(match, history_df)
    update_score(match.id, score)
    history_df.append(match)  # Ajouter au contexte pour le suivant
```

**Option B : Cache In-Memory de l'Historique**
- Charger l'historique **une fois** au début du sync
- Pour chaque nouveau match, calculer avec le cache + matchs déjà insérés
- Évite les N requêtes SELECT sur la DB

**Option C : Sortir du Lock DB**
- Calculer le score **avant** l'acquisition du lock
- L'historique est stable à ce moment (matchs déjà en DB)
- Réduire la durée de la section critique

**Implémentation** :
```python
# SyncOptions
compute_performance_scores: bool = False  # Désactivé par défaut

# Après sync
engine._batch_compute_performance_scores()  # Passe unique ordonnée
```

**Gain estimé** : **-3-5s** par match si > 200 matchs historiques  
**Complexité** : Moyenne (refactoring de `_compute_and_update_performance_score`)

---

### **Phase 2 : Optimisations Structurelles** 🏗️

#### 2.1 Batching des Insertions DB
**Objectif** : Réduire les I/O et permettre commits groupés

**Modifications** :
- Accumuler les rows dans des buffers (par type : match, medals, events, etc.)
- Commit toutes les 10-20 matchs au lieu de chaque match
- Utiliser les fonctions `batch_insert_rows` existantes dans [src/data/sync/batch_insert.py](src/data/sync/batch_insert.py)

**Fichiers** : [src/data/sync/engine.py](src/data/sync/engine.py#L739-L780)

**Gain estimé** : **-30%** des I/O (1-2s → 0.5-1s par match)

---

#### 2.2 Lock Granulaire ou Queue d'Écriture
**Objectif** : Permettre la parallélisation réelle des matchs

**Options** :
- **Option A** : Remplacer `self._db_lock` par une queue d'écriture (1 writer thread/task)
- **Option B** : DuckDB multi-connexion (1 writer + N readers)
- **Option C** : Batching + lock uniquement sur le commit final

**Complexité** : Moyenne (refactoring async)

**Gain estimé** : **+50%** de throughput avec `parallel_matches=5-10`

---

#### 2.3 Augmenter le Rate Limit
**Objectif** : Exploiter pleinement la bande passante API

**Tests recommandés** :
```python
# Tester progressivement
requests_per_second: int = 10  # Au lieu de 5
parallel_matches: int = 5      # Au lieu de 3
```

**Validation** : Surveiller les erreurs 429 (Too Many Requests)

**Gain estimé** : **+50-100%** de throughput global

---

### **Phase 3 : Optimisations Avancées** ⚡

#### 3.1 Cache Metadata In-Memory
**Constat** : Le `metadata_resolver` est recréé pour chaque match
**Solution** : Cache LRU des résolutions (maps, modes, médailles)

#### 3.2 Prefetch Match History
**Idée** : Démarrer le fetch du batch suivant pendant le traitement du batch courant

#### 3.3 Worker Pool pour Transformations
**Stratégie** : Paralléliser les transformations CPU-bound (Polars, extractions JSON)

---

## 📊 Estimation des Gains Cumulés

| Phase | Temps/match actuel | Après optimisation | Gain |
|-------|-------------------|-------------------|------|
| **Baseline (actuel)** | 16s | - | - |
| **+ Phase 1.1 (API parallèle)** | 16s | **6-8s** | 50-60% |
| **+ Phase 1.2 (scores différés)** | 6-8s | **2-4s** | 60-70% |
| **+ Phase 2.1 (batching DB)** | 2-4s | **1.5-3s** | 25-30% |
| **+ Phase 2.3 (rate limit)** | 1.5-3s | **1-2s** | 30-50% |

**Objectif final** : **≤2s par match** (8x plus rapide)

---

## 🛠️ Implémentation Recommandée

### Étape 1 : Parallélisation API (Impact Immédiat)
1. Modifier `_process_single_match` pour utiliser `asyncio.gather`
2. Tester sur un petit dataset (10 matchs)
3. Valider avec `python scripts/sync.py --delta --player JGtm`

### Étape 2 : Scores de Performance (Optionnel)
1. Ajouter option `compute_performance_scores` à `SyncOptions`
2. Désactiver par défaut
3. Créer commande dédiée `--compute-scores`

### Étape 3 : Batching DB (Optimisation suivante)
1. Introduire buffers d'accumulation
2. Commit toutes les 10 matchs
3. Benchmarker avant/après

---

## 🔬 Métriques à Surveiller

### Avant chaque modification
```bash
# Benchmark baseline
python scripts/sync.py --delta --player JGtm
# Noter : temps total, temps/match, logs SQL
```

### Après chaque modification
```bash
# Re-benchmark
python scripts/sync.py --delta --player TestPlayer --max-matches 20
# Comparer : temps/match, taux d'erreur, cohérence données
```

### Outils
- `scripts/benchmark_pages.py` (s'il existe)
- Logs de temps dans le terminal
- DuckDB query profiling : `PRAGMA enable_profiling;`

---

## ⚠️ Points de Vigilance

1. **Ordre des opérations** : S'assurer que le calcul du score de performance a bien accès à l'historique complet
2. **Transactions DB** : Vérifier que les rollbacks sont possibles en cas d'erreur
3. **Rate limiting API** : Tester prudemment les augmentations (risque de ban)
4. **Compatibilité** : Tester avec les 4 DB joueurs (JGtm, Madina97294, Chocoboflor, XxDaemonGamerxX)
5. **Tests de régression** : Lancer `pytest tests/test_data_architecture.py` après chaque modif

---

## 📝 Checklist de Validation

- [ ] Temps/match réduit à ≤3s en delta
- [ ] Aucune régression sur les données (medals, events, skill)
- [ ] Tests passent (`pytest --ignore=tests/integration`)
- [ ] Logs clairs et exploitables
- [ ] Documentation mise à jour (SYNC_GUIDE.md)

---

**Prochaine étape suggérée** : Implémenter Phase 1.1 (parallélisation API) en priorité.

---

## 🚨 NOTES IMPORTANTES

### Dépendance Séquentielle des Scores
Le calcul du score de performance **n'est PAS parallélisable** car chaque match dépend de l'historique précédent :
- Match N+1 nécessite les scores/stats des matchs 1..N
- Le calcul doit respecter l'ordre chronologique strict

**Implications** :
1. ❌ **INTERDIT** : Recalculer tous les scores en parallèle
2. ✅ **AUTORISÉ** : Batch post-sync en ordre chronologique
3. ✅ **OPTIMAL** : Cache in-memory de l'historique pendant la sync
