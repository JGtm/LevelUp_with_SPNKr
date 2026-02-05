# Analyse : Graphe "Temps du premier kill / première mort" vide

**Date** : 2026-02-05  
**Auteur** : Analyse automatique  
**Contexte** : Diagnostic du graphe vide dans la page Timeseries

---

## 📋 Résumé Exécutif

Le graphe "Temps du premier kill / première mort" peut être vide pour plusieurs raisons :

1. **Table `highlight_events` inexistante ou vide** (CRITIQUE)
2. **Différence de casse dans `event_type`** (PROBABLE) ⚠️
3. **XUID ne correspond pas aux données** (MOYEN)
4. **Match IDs filtrés n'ont pas d'événements** (MOYEN)
5. **Exception silencieuse dans le code** (MOYEN)

---

## 🔍 Analyse du Code

### Flux de Données

```
timeseries.py (ligne 229)
  ↓
DuckDBRepository.get_first_kill_death_times(match_ids)
  ↓
DuckDBRepository.load_first_event_times(match_ids, event_type="Kill" ou "Death")
  ↓
Requête SQL sur highlight_events
  ↓
plot_first_event_distribution(first_kills, first_deaths)
```

### Code Source Pertinent

#### 1. Récupération des données (`src/ui/pages/timeseries.py`)

```python
# Lignes 222-231
if db_path and xuid and "match_id" in dff.columns:
    try:
        from src.data.repositories.duckdb_repo import DuckDBRepository
        
        if db_path.endswith(".duckdb"):
            repo = DuckDBRepository(db_path, str(xuid).strip())
            match_ids = dff["match_id"].astype(str).tolist()
            first_kills, first_deaths = repo.get_first_kill_death_times(match_ids)
    except Exception:
        pass  # ⚠️ Exception silencieuse !
```

**Problème identifié** : L'exception est silencieusement ignorée (`except Exception: pass`), ce qui masque les erreurs.

#### 2. Requête SQL (`src/data/repositories/duckdb_repo.py`)

```python
# Lignes 611-622
placeholders = ", ".join(["?" for _ in match_ids])
result = conn.execute(
    f"""
    SELECT match_id, MIN(time_ms) as first_time
    FROM highlight_events
    WHERE match_id IN ({placeholders})
      AND event_type = ?      # ⚠️ Recherche exacte "Kill" ou "Death"
      AND xuid = ?
    GROUP BY match_id
    """,
    [*match_ids, event_type, self._xuid],  # event_type = "Kill" ou "Death"
)
```

**Problème identifié** : La requête cherche `event_type = "Kill"` ou `event_type = "Death"` (avec majuscule), mais selon la documentation SPNKr (`.ai/research/HIGHLIGHT_WEAPON_RESEARCH.md`), les événements sont stockés avec `event_type` en **minuscules** : `"kill"`, `"death"`, `"medal"`.

#### 3. Transformation des données (`src/data/sync/transformers.py`)

```python
# Lignes 692-694
event_type = event_dict.get("event_type")
if not isinstance(event_type, str):
    continue
# ⚠️ Pas de normalisation de la casse !
```

**Problème identifié** : La transformation ne normalise pas la casse de `event_type`. Si SPNKr retourne `"kill"` (minuscule), c'est ce qui est stocké en base.

---

## 🎯 Causes Probables

### Cause #1 : Différence de casse (TRÈS PROBABLE) ⚠️

**Symptôme** :
- La table `highlight_events` contient des données
- Mais la requête ne trouve rien car elle cherche `"Kill"` alors que les données contiennent `"kill"`

**Vérification** :
```sql
SELECT DISTINCT event_type FROM highlight_events;
```

**Solution** :
- Modifier `load_first_event_times()` pour utiliser `LOWER(event_type) = LOWER(?)`
- OU normaliser les données lors de l'insertion

### Cause #2 : Table vide ou inexistante

**Symptôme** :
- La table n'existe pas ou est vide
- Le message "Données d'événements non disponibles" s'affiche

**Vérification** :
```sql
SELECT COUNT(*) FROM highlight_events;
```

**Solution** :
- Synchroniser les matchs avec `with_highlight_events=True`

### Cause #3 : XUID incorrect

**Symptôme** :
- La table contient des événements mais pas pour ce XUID

**Vérification** :
```sql
SELECT DISTINCT xuid FROM highlight_events LIMIT 10;
```

**Solution** :
- Vérifier que le XUID utilisé correspond aux données

### Cause #4 : Match IDs filtrés sans événements

**Symptôme** :
- Les matchs affichés dans le filtre n'ont pas d'événements synchronisés

**Vérification** :
```sql
SELECT COUNT(DISTINCT match_id) 
FROM highlight_events 
WHERE match_id IN ('match_id_1', 'match_id_2', ...);
```

**Solution** :
- Resynchroniser ces matchs avec `with_highlight_events=True`

### Cause #5 : Exception silencieuse

**Symptôme** :
- Une erreur se produit mais est masquée par `except Exception: pass`

**Solution** :
- Ajouter un logging pour capturer les erreurs

---

## 🔧 Script de Diagnostic

Un script de diagnostic a été créé : `scripts/diagnose_first_kill_death.py`

**Utilisation** :
```bash
python scripts/diagnose_first_kill_death.py <db_path> <xuid> [--match-ids match1 match2 ...]
```

**Ce que le script vérifie** :
1. ✅ Existence de la table `highlight_events`
2. ✅ Nombre total d'événements
3. ✅ Types d'événements présents (avec analyse de casse)
4. ✅ Événements pour le XUID spécifié
5. ✅ Événements pour les match_ids spécifiés
6. ✅ Test de la requête exacte avec différentes variantes de casse

---

## 📊 Recommandations

### Immédiat

1. **Exécuter le script de diagnostic** pour identifier la cause exacte
2. **Vérifier la casse des `event_type`** dans la base de données
3. **Ajouter du logging** pour capturer les exceptions silencieuses

### Correctif Proposé

**Option 1 : Requête case-insensitive** (RECOMMANDÉ)

Modifier `load_first_event_times()` dans `src/data/repositories/duckdb_repo.py` :

```python
# Avant (ligne 617)
AND event_type = ?

# Après
AND LOWER(event_type) = LOWER(?)
```

**Option 2 : Normalisation lors de l'insertion**

Modifier `transform_highlight_events()` dans `src/data/sync/transformers.py` :

```python
# Après ligne 692
event_type = event_dict.get("event_type")
if not isinstance(event_type, str):
    continue

# Normaliser la casse
event_type = event_type.lower().capitalize()  # "kill" → "Kill", "death" → "Death"
```

**Option 3 : Améliorer la gestion d'erreurs**

Modifier `timeseries.py` pour logger les erreurs :

```python
# Avant
except Exception:
    pass

# Après
except Exception as e:
    import logging
    logging.warning(f"Erreur lors de la récupération des premiers kill/death: {e}", exc_info=True)
```

---

## 📝 Notes Techniques

### Structure de la table `highlight_events`

```sql
CREATE TABLE highlight_events (
    id INTEGER PRIMARY KEY,
    match_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,  -- "kill", "death", "medal", etc.
    time_ms INTEGER NOT NULL,
    xuid VARCHAR,
    gamertag VARCHAR,
    type_hint INTEGER,
    raw_json VARCHAR
);
```

### Valeurs possibles de `event_type`

D'après la documentation SPNKr :
- `"kill"` (minuscule) - Frag d'un joueur
- `"death"` (minuscule) - Mort d'un joueur
- `"medal"` - Médaille obtenue
- `"mode"` - Événement de mode de jeu

**⚠️ IMPORTANT** : Le code cherche `"Kill"` et `"Death"` (majuscules) mais les données contiennent probablement `"kill"` et `"death"` (minuscules).

---

## 🔗 Fichiers Concernés

- `src/ui/pages/timeseries.py` (lignes 211-244)
- `src/data/repositories/duckdb_repo.py` (lignes 584-641)
- `src/visualization/distributions.py` (lignes 1119-1184)
- `src/data/sync/transformers.py` (lignes 663-713)
- `src/data/sync/engine.py` (lignes 642-657, 907-929)

---

## ✅ Checklist de Diagnostic

- [ ] Exécuter `scripts/diagnose_first_kill_death.py`
- [ ] Vérifier l'existence de la table `highlight_events`
- [ ] Vérifier le nombre d'événements dans la table
- [ ] Vérifier les valeurs de `event_type` (casse)
- [ ] Vérifier les événements pour le XUID
- [ ] Vérifier les événements pour les match_ids filtrés
- [ ] Tester la requête avec différentes variantes de casse
- [ ] Vérifier les logs d'erreur dans Streamlit

---

**Prochaine étape** : Exécuter le script de diagnostic pour identifier la cause exacte.
