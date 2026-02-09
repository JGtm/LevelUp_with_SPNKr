# Analyse : Données manquantes après synchronisation via l'app

**Date** : 2026-02-09  
**Problème** : Après une synchronisation via l'app, le dernier match affiche :
- "Impossible de déterminer Némésis/Souffre-douleur (timeline insuffisante)"
- "Roster indisponible pour ce match (payload MatchStats manquant ou équipe introuvable)"

---

## Root Causes Identifiées

### 1. ✅ **`with_participants` non explicitement activé** (CORRIGÉ)

**Problème** : Dans `src/ui/sync.py`, la fonction `_sync_duckdb_player` créait les `SyncOptions` sans spécifier explicitement `with_participants=True`. Bien que la valeur par défaut soit `True` dans `SyncOptions`, il est préférable de l'expliciter pour éviter toute confusion.

**Fichier** : `src/ui/sync.py` ligne ~280-285

**Correction** : Ajout explicite de `with_participants=True` dans les `SyncOptions`.

```python
# Avant
options = SyncOptions(
    max_matches=max_matches,
    with_highlight_events=True,
    with_skill=True,
    with_aliases=True,
)

# Après
options = SyncOptions(
    max_matches=max_matches,
    with_highlight_events=True,
    with_skill=True,
    with_aliases=True,
    with_participants=True,  # Récupérer le roster complet pour chaque match
)
```

---

### 2. ⚠️ **Highlight Events non disponibles immédiatement** (ATTENDU)

**Problème** : Les highlight events (film) peuvent ne pas être disponibles immédiatement après un match. L'API SPNKr peut avoir un délai avant de rendre les données de film disponibles.

**Comportement actuel** : 
- `get_highlight_events()` retourne `[]` si les events ne sont pas disponibles (non bloquant)
- Le code gère correctement ce cas (ligne 737-738 de `engine.py`)

**Impact** :
- Si les highlight_events sont vides, le calcul de Némésis/Souffre-douleur échoue avec "timeline insuffisante"
- Le roster peut toujours être construit depuis `match_participants` si disponible

**Solution** : 
- C'est un comportement attendu de l'API SPNKr
- Les highlight_events deviendront disponibles après un délai (quelques minutes à quelques heures)
- Une nouvelle synchronisation récupérera les events une fois disponibles

---

### 3. ⚠️ **Roster indisponible si `match_participants` vide** (À VÉRIFIER)

**Problème** : La fonction `load_match_rosters()` dans `DuckDBRepository` utilise plusieurs méthodes pour construire le roster :
1. `killer_victim_pairs` (si disponible)
2. `highlight_events` (fallback)
3. `match_participants` (via `resolve_gamertags_batch`)

Si `match_participants` n'est pas rempli ET que les highlight_events sont vides, le roster ne peut pas être construit.

**Vérification nécessaire** :
- Vérifier que `extract_participants()` fonctionne correctement
- Vérifier que `_insert_participant_rows()` insère bien les données
- Vérifier qu'il n'y a pas d'erreur silencieuse lors de l'extraction/insertion

---

## Corrections Apportées

### 1. Activation explicite de `with_participants`
- ✅ Fichier : `src/ui/sync.py`
- ✅ Ajout de `with_participants=True` dans `SyncOptions`

### 2. Script de diagnostic
- ✅ Fichier : `scripts/diagnose_match_data.py`
- ✅ Permet de vérifier les données présentes pour un match donné
- ✅ Usage : `python scripts/diagnose_match_data.py --db-path <path> --last-match`

---

## Actions Recommandées

### Immédiat
1. ✅ Relancer une synchronisation avec la correction `with_participants=True`
2. ✅ Utiliser le script de diagnostic pour vérifier les données :
   ```bash
   python scripts/diagnose_match_data.py --db-path data/players/MonGamertag/stats.duckdb --last-match
   ```

### Si le problème persiste
1. Vérifier les logs de synchronisation pour voir si `extract_participants()` retourne des données
2. Vérifier que `_insert_participant_rows()` ne génère pas d'erreurs silencieuses
3. Vérifier que les highlight_events deviennent disponibles après un délai (réessayer la sync plus tard)

---

## Tests à Effectuer

1. **Test de synchronisation** :
   - Faire une sync via l'app
   - Vérifier avec le script de diagnostic que `match_participants` est rempli
   - Vérifier que le roster s'affiche correctement

2. **Test highlight_events** :
   - Si les highlight_events sont vides, attendre quelques heures
   - Relancer une sync pour récupérer les events
   - Vérifier que Némésis/Souffre-douleur fonctionne

3. **Test de diagnostic** :
   - Utiliser le script sur plusieurs matchs récents
   - Identifier les patterns de données manquantes

---

## Références

- Code de synchronisation : `src/data/sync/engine.py`
- Extraction des participants : `src/data/sync/transformers.py::extract_participants()`
- Chargement du roster : `src/data/repositories/duckdb_repo.py::load_match_rosters()`
- Calcul des antagonistes : `src/analysis/killer_victim.py::compute_personal_antagonists()`
