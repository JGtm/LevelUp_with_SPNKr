# Correction de l'option `--all-data`

**Date** : 2026-02-09  
**Action** : Ajout des options manquantes à `--all-data`

---

## Modifications apportées

### 1. Ajout des 4 options manquantes (ligne 1046-1049)

```python
if all_data:
    # ... options existantes ...
    shots = True  # shots_fired/shots_hit pour le joueur principal
    participants_scores = True  # rank et score des participants
    participants_kda = True  # kills, deaths, assists des participants
    participants_shots = True  # shots_fired/shots_hit des participants
    # ... autres options ...
```

### 2. Mise à jour de l'aide (ligne 2108)

**Avant** :
```
help="Backfill toutes les données (équivalent à --medals --events --skill --personal-scores --performance-scores --aliases --participants --killer-victim --end-time --sessions)"
```

**Après** :
```
help="Backfill toutes les données (équivalent à --medals --events --skill --personal-scores --performance-scores --aliases --accuracy --enemy-mmr --assets --participants --shots --participants-scores --participants-kda --participants-shots --killer-victim --end-time --sessions)"
```

### 3. Mise à jour de la docstring (ligne 1029)

**Avant** :
```python
all_data: Backfill toutes les données.
```

**Après** :
```python
all_data: Backfill toutes les données (inclut shots et participants-*).
```

---

## Options maintenant incluses dans `--all-data` (17 au total)

1. ✅ `medals` - Médailles
2. ✅ `events` - Highlight events
3. ✅ `skill` - Stats skill/MMR
4. ✅ `personal_scores` - Personal score awards
5. ✅ `performance_scores` - Scores de performance
6. ✅ `aliases` - Aliases XUID → Gamertag
7. ✅ `accuracy` - Précision
8. ✅ `enemy_mmr` - MMR ennemi
9. ✅ `assets` - Noms playlist/map/pair
10. ✅ `participants` - Participants (roster complet)
11. ✅ `shots` - **NOUVEAU** - shots_fired/shots_hit pour le joueur principal
12. ✅ `participants_scores` - **NOUVEAU** - rank et score des participants
13. ✅ `participants_kda` - **NOUVEAU** - kills, deaths, assists des participants
14. ✅ `participants_shots` - **NOUVEAU** - shots_fired/shots_hit des participants
15. ✅ `killer_victim` - Paires killer/victim
16. ✅ `end_time` - Heure de fin des matchs
17. ✅ `sessions` - Session ID et label

---

## Résultat

L'option `--all-data` récupère maintenant **vraiment toutes les données** disponibles pour le backfill.

**Note** : Pour un joueur avec beaucoup de matchs, cela peut prendre du temps car toutes les données seront récupérées depuis l'API SPNKr.
