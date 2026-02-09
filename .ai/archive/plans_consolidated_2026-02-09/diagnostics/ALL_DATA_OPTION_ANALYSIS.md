# Analyse de l'option `--all-data` dans backfill_data.py

**Date** : 2026-02-09  
**Question** : L'option `--all-data` récupère-t-elle bien toutes les données ?

---

## Ce que `--all-data` active (ligne 1035-1048)

Quand `--all-data` est activé, les options suivantes sont automatiquement activées :

```python
if all_data:
    medals = True                    # ✅ Médailles
    events = True                    # ✅ Highlight events
    skill = True                     # ✅ Stats skill/MMR
    personal_scores = True           # ✅ Personal score awards
    performance_scores = True        # ✅ Scores de performance
    aliases = True                   # ✅ Aliases XUID → Gamertag
    accuracy = True                  # ✅ Précision (accuracy)
    enemy_mmr = True                # ✅ MMR ennemi
    assets = True                    # ✅ Noms playlist/map/pair via Discovery UGC
    participants = True              # ✅ Participants (roster complet)
    killer_victim = True             # ✅ Paires killer/victim
    end_time = True                 # ✅ Heure de fin des matchs
    sessions = True                 # ✅ Session ID et label
```

---

## Ce qui manque dans `--all-data`

### Options non activées par `--all-data` :

1. **`shots`** (ligne 1007)
   - Backfill `shots_fired` et `shots_hit` pour le joueur principal dans `match_stats`
   - **Impact** : Les données de tirs ne seront pas backfillées automatiquement

2. **`participants_scores`** (ligne 998)
   - Backfill `rank` et `score` des participants dans `match_participants`
   - **Impact** : Les rangs et scores des participants ne seront pas backfillés automatiquement

3. **`participants_kda`** (ligne 999)
   - Backfill `kills`, `deaths`, `assists` des participants dans `match_participants`
   - **Impact** : Les K/D/A des participants ne seront pas backfillés automatiquement

4. **`participants_shots`** (ligne 1000)
   - Backfill `shots_fired` et `shots_hit` des participants dans `match_participants`
   - **Impact** : Les tirs des participants ne seront pas backfillés automatiquement

---

## Incohérence dans l'aide

**Ligne 2108** - Aide de `--all-data` :
```
help="Backfill toutes les données (équivalent à --medals --events --skill --personal-scores --performance-scores --aliases --participants --killer-victim --end-time --sessions)"
```

**Problèmes** :
1. ❌ L'aide ne mentionne pas `--accuracy`, `--enemy-mmr`, `--assets` alors qu'ils sont activés
2. ❌ L'aide ne mentionne pas que `--shots` et `--participants-*` ne sont **PAS** inclus

---

## Recommandations

### Option 1 : Ajouter les options manquantes à `--all-data`

Modifier le code pour inclure :
```python
if all_data:
    # ... options existantes ...
    shots = True                     # Ajouter
    participants_scores = True       # Ajouter
    participants_kda = True         # Ajouter
    participants_shots = True       # Ajouter
```

**Avantage** : `--all-data` récupère vraiment **TOUTES** les données  
**Inconvénient** : Peut être très long pour un joueur avec beaucoup de matchs

---

### Option 2 : Corriger l'aide pour refléter la réalité

Mettre à jour l'aide pour être précise :
```
help="Backfill toutes les données principales (équivalent à --medals --events --skill --personal-scores --performance-scores --aliases --accuracy --enemy-mmr --assets --participants --killer-victim --end-time --sessions). Note: --shots et --participants-* ne sont pas inclus."
```

**Avantage** : Documente clairement ce qui est inclus  
**Inconvénient** : `--all-data` ne récupère pas vraiment "toutes" les données

---

### Option 3 : Créer deux niveaux

- `--all-data` : Données principales (comportement actuel)
- `--all-data-complete` : Vraiment toutes les données (inclut shots et participants-*)

---

## Conclusion

**Réponse à la question** : ❌ Non, `--all-data` ne récupère **PAS** toutes les données.

**Données manquantes** :
- `shots` (shots_fired/shots_hit pour le joueur principal)
- `participants_scores` (rank/score des participants)
- `participants_kda` (kills/deaths/assists des participants)
- `participants_shots` (shots_fired/shots_hit des participants)

**Recommandation** : Ajouter ces 4 options à `--all-data` pour que l'option récupère vraiment toutes les données, ou renommer l'option en `--all-main-data` et créer une nouvelle option `--all-data-complete`.
