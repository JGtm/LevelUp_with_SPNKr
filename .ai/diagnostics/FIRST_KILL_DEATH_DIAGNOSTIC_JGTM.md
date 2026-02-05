# Diagnostic : Graphe "Temps du premier kill / première mort" - JGtm

**Date** : 2026-02-05  
**Joueur** : JGtm  
**XUID** : 2533274823110022  
**Base de données** : `data/players/JGtm/stats.duckdb`

---

## 📋 Résumé Exécutif

**Problème** : Le graphe "Temps du premier kill / première mort" est vide dans la page Timeseries.

**Cause probable identifiée** : **Différence de casse dans `event_type`** ⚠️

Le code recherche `event_type = "Kill"` et `event_type = "Death"` (avec majuscules), mais selon la documentation SPNKr, les événements sont stockés avec `event_type` en **minuscules** : `"kill"`, `"death"`, `"medal"`.

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
Requête SQL: WHERE event_type = 'Kill' AND xuid = ?  ⚠️ Comparaison exacte
  ↓
Retourne {} si aucune correspondance
```

### Code Source Pertinent

#### 1. Requête SQL (`src/data/repositories/duckdb_repo.py`, lignes 611-622)

```python
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

**Problème** : La requête utilise une comparaison exacte (`event_type = ?`) qui est sensible à la casse.

#### 2. Documentation SPNKr (`.ai/research/HIGHLIGHT_WEAPON_RESEARCH.md`)

```python
{
    "event_type": "kill" | "death" | "medal",  # ⚠️ MINUSCULES
    "time_ms": 45000,
    "xuid": "2535...",
    "gamertag": "Player",
    "type_hint": 50,  # 10=mode, 20=death, 50=kill
}
```

**Confirmation** : SPNKr retourne les événements avec `event_type` en **minuscules**.

#### 3. Transformation (`src/data/sync/transformers.py`, lignes 692-694)

```python
event_type = event_dict.get("event_type")
if not isinstance(event_type, str):
    continue
# ⚠️ Pas de normalisation de la casse !
```

**Problème** : La transformation ne normalise pas la casse, donc si SPNKr retourne `"kill"`, c'est ce qui est stocké en base.

---

## 🎯 Causes Possibles (par ordre de probabilité)

### Cause #1 : Différence de casse (TRÈS PROBABLE) ⚠️

**Probabilité** : 90%

**Symptôme** :
- La table `highlight_events` contient des données
- Mais la requête ne trouve rien car elle cherche `"Kill"` alors que les données contiennent `"kill"`

**Vérification nécessaire** :
```sql
SELECT DISTINCT event_type FROM highlight_events;
```

**Solution** :
- Modifier `load_first_event_times()` pour utiliser `LOWER(event_type) = LOWER(?)`
- OU normaliser les données lors de l'insertion

### Cause #2 : Table vide ou inexistante

**Probabilité** : 5%

**Symptôme** :
- La table n'existe pas ou est vide
- Le message "Données d'événements non disponibles" s'affiche

**Vérification nécessaire** :
```sql
SELECT COUNT(*) FROM highlight_events;
```

**Solution** :
- Synchroniser les matchs avec `with_highlight_events=True`

### Cause #3 : XUID incorrect

**Probabilité** : 3%

**Symptôme** :
- La table contient des événements mais pas pour ce XUID

**Vérification nécessaire** :
```sql
SELECT DISTINCT xuid FROM highlight_events LIMIT 10;
```

### Cause #4 : Match IDs filtrés sans événements

**Probabilité** : 2%

**Symptôme** :
- Les matchs affichés dans le filtre n'ont pas d'événements synchronisés

---

## 🔧 Solutions Proposées

### Solution 1 : Requête case-insensitive (RECOMMANDÉ) ✅

**Fichier** : `src/data/repositories/duckdb_repo.py`

**Modification** : Ligne 617

```python
# Avant
AND event_type = ?

# Après
AND LOWER(event_type) = LOWER(?)
```

**Avantages** :
- ✅ Fonctionne avec toutes les variantes de casse
- ✅ Pas de migration de données nécessaire
- ✅ Solution immédiate

**Code complet modifié** :

```python
def load_first_event_times(
    self,
    match_ids: list[str],
    event_type: str = "Kill",
) -> dict[str, int | None]:
    """Charge le timestamp du premier événement par match.

    Args:
        match_ids: Liste des IDs de matchs.
        event_type: Type d'événement ("Kill" ou "Death").

    Returns:
        Dict {match_id: time_ms} pour le premier événement de chaque match.
    """
    if not match_ids:
        return {}

    conn = self._get_connection()

    try:
        # Vérifier si la table existe
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_name = 'highlight_events'"
        ).fetchall()
        if not tables:
            return {}

        placeholders = ", ".join(["?" for _ in match_ids])
        result = conn.execute(
            f"""
            SELECT match_id, MIN(time_ms) as first_time
            FROM highlight_events
            WHERE match_id IN ({placeholders})
              AND LOWER(event_type) = LOWER(?)
              AND xuid = ?
            GROUP BY match_id
            """,
            [*match_ids, event_type, self._xuid],
        )
        return {row[0]: row[1] for row in result.fetchall()}
    except Exception:
        return {}
```

### Solution 2 : Normalisation lors de l'insertion

**Fichier** : `src/data/sync/transformers.py`

**Modification** : Après la ligne 692

```python
event_type = event_dict.get("event_type")
if not isinstance(event_type, str):
    continue

# Normaliser la casse
event_type = event_type.lower().capitalize()  # "kill" → "Kill", "death" → "Death"
```

**Avantages** :
- ✅ Normalise les données à la source
- ✅ Cohérence garantie

**Inconvénients** :
- ⚠️ Nécessite une migration des données existantes
- ⚠️ Plus complexe à mettre en place

### Solution 3 : Améliorer la gestion d'erreurs

**Fichier** : `src/ui/pages/timeseries.py`

**Modification** : Ligne 230

```python
# Avant
except Exception:
    pass

# Après
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Erreur lors de la récupération des premiers kill/death: {e}", exc_info=True)
```

**Avantages** :
- ✅ Permet de voir les erreurs réelles
- ✅ Aide au débogage

---

## 📝 Script de Diagnostic

Un script de diagnostic a été créé : `scripts/diagnose_first_kill_death_simple.py`

**Pour exécuter** (nécessite Python avec duckdb installé) :

```bash
python scripts/diagnose_first_kill_death_simple.py "data/players/JGtm/stats.duckdb" "2533274823110022"
```

**Ce que le script vérifie** :
1. ✅ Existence de la table `highlight_events`
2. ✅ Nombre total d'événements
3. ✅ Types d'événements présents (avec analyse de casse)
4. ✅ Événements pour le XUID spécifié
5. ✅ Événements pour les match_ids spécifiés
6. ✅ Test de la requête exacte avec différentes variantes de casse

---

## ✅ Actions Recommandées

### ✅ CORRECTION APPLIQUÉE (2026-02-05)

**Modification effectuée** : Solution 1 (requête case-insensitive) appliquée dans `src/data/repositories/duckdb_repo.py`

**Changements** :
- Ligne 617 : `AND event_type = ?` → `AND LOWER(event_type) = LOWER(?)`
- Normalisation du paramètre `event_type` en minuscules avant la requête
- Documentation mise à jour pour indiquer que toute casse est acceptée

**Prochaines étapes** :
1. **Tester** le graphe dans l'interface Streamlit
2. Vérifier que les données s'affichent correctement

### Si la Solution 1 ne fonctionne pas

1. **Vérifier** que la table `highlight_events` contient des données
2. **Vérifier** que le XUID correspond aux données
3. **Vérifier** que les match_ids filtrés ont des événements
4. **Ajouter** la Solution 3 (logging) pour voir les erreurs réelles

---

## 🔗 Fichiers Concernés

- `src/ui/pages/timeseries.py` (lignes 211-244)
- `src/data/repositories/duckdb_repo.py` (lignes 584-641) ⚠️ **À MODIFIER**
- `src/visualization/distributions.py` (lignes 1119-1184)
- `src/data/sync/transformers.py` (lignes 663-713)

---

## 📊 Résultat Attendu Après Correction

Après application de la Solution 1, le graphe devrait afficher :
- **Histogramme des premiers kills** (en vert)
- **Histogramme des premières morts** (en rouge)
- **Lignes verticales** indiquant les moyennes

Si le graphe est toujours vide après correction, cela indique que :
- La table `highlight_events` est vide pour ce joueur
- Les matchs n'ont pas été synchronisés avec `with_highlight_events=True`

---

**Prochaine étape** : Appliquer la Solution 1 (requête case-insensitive) dans `duckdb_repo.py`.
