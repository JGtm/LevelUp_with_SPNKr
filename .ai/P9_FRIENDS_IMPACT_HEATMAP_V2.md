# P9 — Heatmap d'Impact & Cercle d'Amis (V2 — Logique métier retifiée)

> **Sprint** : 12 (après S11)  
> **Date** : 2026-02-12  
> **Clarification** : Logique métier des incompatibilités (2026-02-12 13h)  
> **Prérequis** : Sprints 0-11 livrés  
> **Durée estimée** : 2.5 jours  

---

## 🎯 Objectif utilisateur

Dans l'onglet **Coéquipiers**, ajouter un nouvel onglet **"Impact & Taquinerie"** permettant de visualiser un **breakdown complet de TOUS les matchs** sur la période filtrée :

1. **Heatmap interactive** : Joueurs (Y-axis) × Matchs (X-axis)
2. **Événements clés** mutellement exclusifs par match :
   - 🟢 **Premier Sang** (+1) : Premier kill du match par ce joueur (peu importe outcome)
   - 🟡 **Finisseur** (+2) : Dernier kill du match + **victoire SEULEMENT** (outcome=2)
   - 🔴 **Boulet** (-1) : Dernière mort du match + **défaite SEULEMENT** (outcome=3)
3. **Tableau de ranking** avec scores de "taquinerie" :
   - 🏆 MVP de la soirée (score max)
   - 🍌 Maillon faible (score min)

---

## ⚠️ Incompatibilités métier (RÈGLES CRITIQUES)

### Cas impossibles (à NE JAMAIS afficher ensemble)

| Combinaison | Possible ? | Explication |
|-------------|-----------|-------------|
| **Finisseur + Boulet** (même match) | ❌ **IMPOSSIBLE** | Un match = 1 outcome. Finisseur=outcome 2 (WIN), Boulet=outcome 3 (LOSS). Impossible d'avoir les deux |
| **"Dernier frag" + "Dernière victime"** (même match) | ❌ **IMPOSSIBLE** | Parité match absolue : Si l'équipe GAGNE, le joueur peut faire le dernier kill. Si l'équipe PERD, l'ADVERSAIRE fait le dernier kill → le joueur ne peut être que la VICTIME |
| **First Blood + Finisseur** (même match) | ✅ **POSSIBLE** | Ex: Player1 = premier kill à t=1000ms, dernier kill à t=8000ms, match gagné |
| **First Blood + Boulet** (même match) | ✅ **POSSIBLE** | Ex: Player1 = premier kill à t=100ms, match perdu, lui subit dernière mort à t=9000ms |
| **Finisseur uniquement** | ✅ **POSSIBLE** | Dernier kill + victoire, no first blood |
| **Boulet uniquement** | ✅ **POSSIBLE** | Dernière mort + défaite, no first blood |

### Conservation des données (logique application)

Pour **chaque match** et **chaque joueur**, on peut avoir :
- **0-1 First Blood** (indépendant de outcome)
- **XOR 1 Finisseur** (si outcome=2 WIN)
- **XOR 1 Boulet** (si outcome=3 LOSS)

**Jamais simultanément** Finisseur ET Boulet (car outcome ne peut pas être 2 ET 3).

### Visualisation dans la heatmap

**1 couleur max par cellule** (priorité) :
1. 🟡 **Finisseur** (valorisé, +2) → couleur OR
2. 🔴 **Boulet** (négatif, -1) → couleur ROUGE
3. 🟢 **Premier Sang** (+1) → couleur VERT
4. ⚪ Aucun événement → gris clair

Si techniquement un joueur aurait 2 événements (ex: First Blood + Finisseur), afficher la priorité 1 et mentionner l'autre en tooltip.

---

## 📊 Pipeline de données

```
match_stats (outcome: 2=WIN, 3=LOSS)
    +
highlight_events (event_type: Kill, Death)
    ↓
DuckDBRepository.load_friends_impact_data(
  match_ids=[...],           # TOUS les matchs période filtrée
  friend_xuids=[...],        # Amis sélectionnés dans teammates.py
)
    ↓
Retourne: (match_events, match_outcomes)
- match_events: {match_id: [event1, event2, ...]}
- match_outcomes: {match_id: outcome}
    ↓
friends_impact.py
├─ identify_first_blood(match_events, friend_xuids)
│  └─ min(time_ms) Kill par joueur (outcome=any) ✓
├─ identify_clutch_finisher(match_events, match_outcomes, friend_xuids)
│  └─ max(time_ms) Kill par joueur + outcome=2 STRICTEMENT ⚠️
├─ identify_last_casualty(match_events, match_outcomes, friend_xuids)
│  └─ max(time_ms) Death par joueur + outcome=3 STRICTEMENT ⚠️
└─ compute_impact_scores(first_bloods, clutches, casualties)
   └─ Score = +2*count(clutch) + 1*count(first_blood) - 1*count(casualty)
    ↓
friends_impact_heatmap.py
├─ plot_friends_impact_heatmap()
│  └─ Heatmap 1 couleur/cellule (appliquer priorité)
└─ build_impact_ranking_df()
   └─ Tableau ranking avec badges MVP/Boulet
    ↓
teammates.py (nouvel onglet)
├─ Heatmap breakdown TOTAL période
├─ Tableau ranking (scoring)
└─ Filtrage graceful
```

---

## 🔧 Implémentation

### Pseudo-code `identify_clutch_finisher()` (STRICT)

```python
def identify_clutch_finisher(match_events, match_outcomes, friend_xuids):
    """
    RÈGLE STRICTE: outcome DOIT être 2 (victoire)
    """
    result = {}
    for match_id, events in match_events.items():
        # ⚠️ CONDITION REQUISE: outcome == 2
        if match_outcomes.get(match_id) != 2:
            continue  # Sauter TOUS les matchs qui ne sont pas des victoires
        
        kills = [e for e in events 
                 if e.get("event_type").lower() == "kill"
                 and e.get("xuid") in friend_xuids]
        if kills:
            last_kill = max(kills, key=lambda e: e.get("time_ms", 0))
            result[match_id] = (last_kill["xuid"], last_kill["time_ms"])
    return result
```

### Pseudo-code `identify_last_casualty()` (STRICT)

```python
def identify_last_casualty(match_events, match_outcomes, friend_xuids):
    """
    RÈGLE STRICTE: outcome DOIT être 3 (défaite)
    """
    result = {}
    for match_id, events in match_events.items():
        # ⚠️ CONDITION REQUISE: outcome == 3
        if match_outcomes.get(match_id) != 3:
            continue  # Sauter TOUS les matchs qui ne sont pas des défaites
        
        deaths = [e for e in events 
                  if e.get("event_type").lower() == "death"
                  and e.get("xuid") in friend_xuids]
        if deaths:
            last_death = max(deaths, key=lambda e: e.get("time_ms", 0))
            result[match_id] = (last_death["xuid"], last_death["time_ms"])
    return result
```

### Logique priorité heatmap

```python
def get_event_priority(match_id, first_bloods, clutches, casualties):
    """
    Priorité pour affichage heatmap (1 couleur/cellule)
    """
    if match_id in clutches:
        return ("clutch", COLOR_CLUTCH, "🟡 Finisseur")
    elif match_id in casualties:
        return ("casualty", COLOR_CASUALTY, "🔴 Boulet")
    elif match_id in first_bloods:
        return ("first_blood", COLOR_FIRST_BLOOD, "🟢 Premier Sang")
    else:
        return (None, "#ecf0f1", "")  # Aucun événement
```

---

## Tests de validation (incompatibilités)

```python
def test_finisseur_and_boulet_never_together():
    """
    Garantir qu'aucun match n'a SIMULTANÉMENT Finisseur et Boulet
    """
    for match_id in all_matches:
        in_finisseur = match_id in clutches
        in_boulet = match_id in casualties
        assert not (in_finisseur and in_boulet), \
            f"Match {match_id}: impossible Finisseur+Boulet"

def test_clutch_requires_outcome_2():
    """Finisseur seulement si outcome=2 (victoire)"""
    for match_id, (xuid, time_ms) in clutches.items():
        assert match_outcomes[match_id] == 2, \
            f"Match {match_id}: Finisseur sans victoire!"

def test_casualty_requires_outcome_3():
    """Boulet seulement si outcome=3 (défaite)"""
    for match_id, (xuid, time_ms) in casualties.items():
        assert match_outcomes[match_id] == 3, \
            f"Match {match_id}: Boulet sans défaite!"
```

---

## 📋 Checklist de livraison (MISE À JOUR)

- [ ] **CRITIQUE** : Vérifier que `identify_clutch_finisher()` skip matches où outcome ≠ 2
- [ ] **CRITIQUE** : Vérifier que `identify_last_casualty()` skip matches où outcome ≠ 3
- [ ] Logique priorité heatmap implémentée (Finisseur > Boulet > First Blood)
- [ ] Tests unitaires valident ABSENCE combinaisons incompatibles
- [ ] Heatmap affiche 1 seule couleur par cellule (ou tooltip enrichi si multi)
- [ ] Tableau ranking scores corrects (+2/+1/-1)
- [ ] Message clair en UI si aucun événement (période vide, matchs sans stats)

---

## 🎯 Résumé correction métier

**AVANT** (potentiellement dangereux) :
- ❌ Risk: Finisseur ET Boulet sur même match
- ❌ Risk: Dernier kill ET dernière mort affichés ensemble

**APRÈS** (logique sûre) :
- ✅ Condition `if outcome == 2` pour Finisseur
- ✅ Condition `if outcome == 3` pour Boulet
- ✅ Cas incompatibles impossible par construction
- ✅ Tests validant l'absence de contradictions

---

> **Version V2 rédigée avec clarifications métier de Guillaume**  
> **Intégré au document principal : PLAN_UNIFIE.md Sprint 12**  
> **Date** : 2026-02-12 13h
