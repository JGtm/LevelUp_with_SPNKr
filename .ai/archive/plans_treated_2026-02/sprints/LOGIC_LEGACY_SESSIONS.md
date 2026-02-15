# Logique Legacy des Sessions

> **Source** : `scripts/_obsolete/migrate_to_cache.py`  
> **Fonction** : `compute_sessions_with_teammates()`  
> **Date** : Système SQLite/MatchCache (avant migration DuckDB v4)

---

## 📋 Vue d'ensemble

La logique legacy calcule les sessions en combinant **deux critères** :
1. **Gap temporel** entre matchs
2. **Changement de coéquipiers** (avec règles spécifiques)

---

## 🔧 Configuration

```python
SESSION_GAP_MINUTES = 120  # 2 heures
SESSION_CUTOFF_HOUR = 8     # 8h du matin (pour sessions "en cours")
```

---

## 📐 Règles de Calcul des Sessions

### Règle 1 : Gap Temporel

**Nouvelle session si** : `gap > SESSION_GAP_MINUTES` (120 minutes)

```python
gap = (match.start_time - prev_match.start_time).total_seconds() / 60.0
if gap > gap_minutes:
    new_session = True
```

**Exemple** :
- Match 1 : 14:00
- Match 2 : 15:30 → **Même session** (gap = 90 min < 120 min)
- Match 3 : 16:30 → **Nouvelle session** (gap = 120 min = 120 min)

---

### Règle 2 : Changement de Coéquipiers

**Fonction** : `should_start_new_session_on_teammate_change()`

#### Logique avec `FRIENDS_XUIDS` défini (mode "amis proches")

Si une liste d'amis proches est définie (`FRIENDS_XUIDS`), **seuls les amis comptent** pour le changement de session. Les joueurs aléatoires du matchmaking sont **ignorés**.

**Règles** :

1. **Nouvelle session si un AMI rejoint**
   ```python
   new_friends = curr_friends - prev_friends
   if new_friends:
       return True  # Nouvelle session
   ```

2. **Nouvelle session si passage de "avec amis" à "SOLO"**
   ```python
   if not curr_friends and prev_friends:
       return True  # Nouvelle session
   ```

3. **MÊME session si un ami part** (sauf passage à solo)
   ```python
   # Si des amis partent mais aucun nouveau → même session
   return False
   ```

#### Logique sans `FRIENDS_XUIDS` (mode "tous les coéquipiers")

Si `FRIENDS_XUIDS` est vide, **tous les coéquipiers** sont considérés pour le changement de session.

**Règles** :
- **Nouvelle session si** : `prev_teammates != curr_teammates`
- C'est-à-dire : **tout changement** dans la liste des coéquipiers déclenche une nouvelle session

---

## 📝 Format de `teammates_signature`

**Format** : Chaîne de caractères avec XUIDs séparés par virgule, triés par ordre croissant

```
"2533274823110022,2533274858283686,2533274883457349"
```

**Exemple de parsing** :
```python
def _parse_teammates(sig: str) -> set[str]:
    if not sig:
        return set()
    return set(sig.split(","))
```

---

## 🎯 Exemples Concrets

### Exemple 1 : Gap temporel seul

```
Match 1 : 14:00, teammates = [A, B]
Match 2 : 15:30, teammates = [A, B]  → Même session (gap 90 min)
Match 3 : 16:30, teammates = [A, B]  → Nouvelle session (gap 120 min)
```

### Exemple 2 : Changement d'ami (mode "amis proches")

**Configuration** : `FRIENDS_XUIDS = {A, B}`

```
Match 1 : 14:00, teammates = [A, random1, random2]
Match 2 : 14:30, teammates = [A, B, random3]     → Nouvelle session (B rejoint)
Match 3 : 15:00, teammates = [A, random4]         → Même session (B part mais A reste)
Match 4 : 15:30, teammates = [random5, random6]  → Nouvelle session (passage à solo)
```

### Exemple 3 : Changement de coéquipier (mode "tous")

**Configuration** : `FRIENDS_XUIDS = {}` (vide)

```
Match 1 : 14:00, teammates = [A, B, C]
Match 2 : 14:30, teammates = [A, B, D]  → Nouvelle session (C → D)
Match 3 : 15:00, teammates = [A, B, C]  → Nouvelle session (D → C)
```

### Exemple 4 : Combinaison gap + coéquipiers

```
Match 1 : 14:00, teammates = [A, B]
Match 2 : 14:30, teammates = [A, B]     → Même session (gap 30 min, mêmes coéquipiers)
Match 3 : 15:00, teammates = [A, C]     → Nouvelle session (changement coéquipier)
Match 4 : 16:00, teammates = [A, C]     → Même session (gap 60 min, mêmes coéquipiers)
Match 5 : 18:00, teammates = [A, C]     → Nouvelle session (gap 120 min)
```

---

## 🔄 Algorithme Complet

```python
def compute_sessions_with_teammates(
    matches: list[MatchForSession],
    gap_minutes: int = 120,
    cutoff_hour: int = 8,
) -> dict[str, tuple[int, str]]:
    """Calcule les sessions avec la logique améliorée."""
    
    matches = sorted(matches, key=lambda m: m.start_time)
    result: dict[str, tuple[int, str]] = {}
    
    session_id = 0
    session_matches: list[MatchForSession] = []
    
    prev_match: MatchForSession | None = None
    prev_teammates: set[str] = set()
    
    for match in matches:
        new_session = False
        curr_teammates = _parse_teammates(match.teammates_signature)
        
        if prev_match is None:
            # Premier match = première session
            new_session = True
        else:
            # Vérifier le gap temporel
            gap = (match.start_time - prev_match.start_time).total_seconds() / 60.0
            
            # Nouvelle session si gap OU changement de coéquipiers
            if gap > gap_minutes or should_start_new_session_on_teammate_change(
                prev_teammates, curr_teammates
            ):
                new_session = True
        
        if new_session and session_matches:
            # Finaliser la session précédente
            _finalize_session(session_matches, session_id)
            session_id += 1
            session_matches = []
        
        session_matches.append(match)
        prev_match = match
        prev_teammates = curr_teammates
    
    # Finaliser la dernière session
    if session_matches:
        _finalize_session(session_matches, session_id)
    
    return result
```

---

## 📊 Format de Sortie

**Retour** : `dict[str, tuple[int, str]]`

- **Clé** : `match_id` (str)
- **Valeur** : `(session_id, session_label)` (tuple)

**Exemple** :
```python
{
    "match-123": (0, "25/01/26 14:30–16:45 (5)"),
    "match-124": (0, "25/01/26 14:30–16:45 (5)"),
    "match-125": (1, "25/01/26 18:00–19:15 (3)"),
}
```

**Format du label** : `"{start:%d/%m/%y %H:%M}–{end:%H:%M} ({count})"`

---

## ⚙️ Fonction `should_start_new_session_on_teammate_change()`

### Code complet

```python
def should_start_new_session_on_teammate_change(
    prev_teammates: set[str],
    curr_teammates: set[str],
) -> bool:
    """Détermine si un changement de coéquipiers déclenche une nouvelle session."""
    
    # Si FRIENDS_XUIDS est défini, ne considérer que les amis
    if FRIENDS_XUIDS:
        prev_friends = prev_teammates & FRIENDS_XUIDS
        curr_friends = curr_teammates & FRIENDS_XUIDS
    else:
        # Sinon considérer tous les coéquipiers
        prev_friends = prev_teammates
        curr_friends = curr_teammates
    
    # Cas 1: Passage à "sans amis" (curr_friends vide alors que prev_friends non vide)
    if not curr_friends and prev_friends:
        return True
    
    # Cas 2: Un ami rejoint
    new_friends = curr_friends - prev_friends
    if new_friends:
        return True
    
    # Cas 3: Des amis partent mais aucun nouveau → même session
    return False
```

### Matrice de Décision (mode "amis proches")

| État précédent | État actuel | Action |
|----------------|-------------|--------|
| `[A, B]` | `[A, B]` | ✅ Même session |
| `[A, B]` | `[A, B, C]` | 🔴 Nouvelle session (C rejoint) |
| `[A, B]` | `[A]` | ✅ Même session (B part mais A reste) |
| `[A]` | `[]` | 🔴 Nouvelle session (passage à solo) |
| `[A, random]` | `[A, B, random]` | 🔴 Nouvelle session (B rejoint) |
| `[A, B]` | `[random1, random2]` | 🔴 Nouvelle session (passage à solo) |

---

## 🔍 Différences avec la Logique Actuelle

### Logique Legacy (SQLite/MatchCache)

✅ **Prend en compte** :
- Gap temporel (120 min)
- Changement de coéquipiers avec règles spécifiques
- Mode "amis proches" vs "tous les coéquipiers"

### Logique Actuelle (DuckDB v4)

❌ **Ne prend en compte QUE** :
- Gap temporel (configurable, défaut 35 min dans `SESSION_CONFIG`)

❌ **Ignore** :
- Changement de coéquipiers (`teammates_signature`)

---

## 📝 Notes Importantes

1. **`FRIENDS_XUIDS`** : Peut être chargé depuis la table `Friends` dans la DB
2. **Heure de coupure** : `SESSION_CUTOFF_HOUR = 8` est défini mais **pas utilisé** dans `compute_sessions_with_teammates()` (mentionné dans la docstring mais non implémenté)
3. **Tri** : Les matchs doivent être triés par `start_time` croissant avant le calcul
4. **Signature** : `teammates_signature` doit être triée (XUIDs en ordre croissant) pour comparaison stable

---

## 🎯 Objectif de Migration

**Réimplémenter cette logique dans DuckDB v4** avec :
- ✅ Polars au lieu de Pandas
- ✅ Même logique de changement de coéquipiers
- ✅ Support du mode "amis proches" vs "tous les coéquipiers"
- ✅ Gap temporel configurable

---

*Document créé le 2026-02-05*
