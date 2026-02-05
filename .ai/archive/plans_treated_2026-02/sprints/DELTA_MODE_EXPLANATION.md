# Explication du Mode Delta

> **Date** : 4 février 2026

---

## Comportement du Mode `--delta`

### Ce que fait le mode delta

Le mode `--delta` recherche **uniquement les nouveaux matchs** :

1. **Charge les match_ids existants** depuis `match_stats`
2. **Parcourt l'historique** depuis l'API (du plus récent au plus ancien)
3. **S'arrête dès qu'un match déjà présent est trouvé** (ligne 465-468)
4. **Pour chaque nouveau match** : Extrait **TOUTES** les données :
   - ✅ `match_stats` (obligatoire)
   - ✅ `highlight_events` (si `with_highlight_events=True`)
   - ✅ `skill/MMR` (si `with_skill=True`)
   - ✅ `aliases` (si `with_aliases=True`)
   - ✅ `personal_scores`
   - ✅ **`medals_earned`** (toujours extraites maintenant)

### Ce que le mode delta NE fait PAS

❌ **Ne remplit PAS les données manquantes** pour les matchs existants :
- Si un match existe déjà mais qu'il manque des médailles → **elles ne seront pas ajoutées**
- Si un match existe déjà mais qu'il manque des highlight_events → **ils ne seront pas ajoutés**
- Si un match existe déjà mais qu'il manque des données skill → **elles ne seront pas ajoutées**

---

## Comparaison Delta vs Full

| Aspect | `--delta` | `--full` |
|--------|-----------|----------|
| **Nouveaux matchs** | ✅ Ajoute | ✅ Ajoute |
| **Matchs existants** | ❌ Ignore (s'arrête) | ⚠️ Skip mais continue |
| **Backfill données** | ❌ Non | ⚠️ Partiel (skip les matchs existants) |
| **Vitesse** | ⚡ Rapide (< 10s) | 🐌 Plus lent |
| **Usage** | Sync régulière | Backfill initial |

---

## Code Source

### Mode Delta (ligne 465-468)
```python
if match_id in existing_ids:
    if delta_mode:
        logger.info(f"[DELTA] Match {match_id} déjà connu — arrêt")
        return result  # ← S'ARRÊTE ICI
```

### Mode Full (ligne 469-473)
```python
else:  # full mode
    result.matches_skipped += 1
    remaining -= 1
    start += 1
    continue  # ← Continue à chercher
```

---

## Pour remplir les médailles des matchs existants

### Option 1 : Mode `--full` (partiel)
```bash
python scripts/sync.py --full --player JGtm
```
⚠️ **Limitation** : Skip les matchs existants, donc ne remplit pas les données manquantes

### Option 2 : Script de backfill dédié (recommandé)
Créer un script qui :
1. Liste tous les match_ids existants
2. Vérifie quelles données manquent (médailles, events, etc.)
3. Re-télécharge uniquement les données manquantes

### Option 3 : Supprimer et re-sync (extrême)
```bash
# Supprimer les matchs existants
# Puis re-sync avec --delta
```

---

## Recommandation

Pour remplir les médailles des matchs existants après avoir ajouté `extract_medals()` :

1. **Court terme** : Utiliser `--full` avec `--max-matches` élevé
   ```bash
   python scripts/sync.py --full --player JGtm --max-matches 1000
   ```
   ⚠️ Note : Cela skip les matchs existants, donc ne remplit pas les médailles manquantes

2. **Long terme** : Créer un script de backfill spécifique pour les médailles
   - Parcourt tous les matchs existants
   - Vérifie si `medals_earned` est vide pour chaque match
   - Re-télécharge uniquement les données nécessaires pour extraire les médailles

---

## Conclusion

**Le mode `--delta`** :
- ✅ Recherche uniquement les **nouveaux matchs**
- ✅ Pour chaque nouveau match, extrait **toutes les données** (y compris médailles)
- ❌ **Ne remplit PAS** les données manquantes pour les matchs existants

**Pour remplir les médailles des matchs existants**, il faut soit :
- Utiliser un script de backfill dédié
- Ou re-synchroniser avec `--full` (mais cela skip les matchs existants)
