# Analyse : Problème de backfill des highlight_events

**Date** : 2026-02-09  
**Problème** : Le script `backfill_data.py --events` met à jour tous les matchs de JGtm au lieu de seulement ceux sans highlight_events.

---

## Analyse du Code

### 1. Détection des matchs manquants (`_find_matches_missing_data`)

**Ligne 772-777** :
```python
if events:
    conditions.append("""
        ms.match_id NOT IN (
            SELECT DISTINCT match_id FROM highlight_events
        )
    """)
```

**Analyse** : Cette condition semble **correcte**. Elle devrait trouver uniquement les matchs qui ne sont PAS dans la table `highlight_events`.

### 2. Combinaison des conditions

**Ligne 966** :
```python
where_clause = " OR ".join(conditions)
```

**Problème potentiel** : Si plusieurs options sont activées en même temps (ex: `--events --medals`), les conditions sont combinées avec `OR`, ce qui peut retourner plus de matchs que prévu. Mais si seul `--events` est utilisé, cela ne devrait pas être un problème.

### 3. Insertion des events (`_insert_event_rows`)

**Ligne 175-199** :
```python
def _insert_event_rows(conn, rows: list) -> int:
    """Insère les highlight events."""
    if not rows:
        return 0

    # Récupérer le max id actuel pour auto-increment manuel
    max_id_result = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM highlight_events"
    ).fetchone()
    next_id = (max_id_result[0] or 0) + 1

    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT INTO highlight_events
                   (id, match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    next_id,
                    row.match_id,
                    row.event_type,
                    row.time_ms,
                    row.xuid,
                    row.gamertag,
                    row.type_hint,
                    row.raw_json,
                ),
            )
            next_id += 1
            inserted += 1
        except Exception as e:
            logger.warning(f"Erreur insertion event pour {row.match_id}: {e}")

    return inserted
```

**Problème identifié** : 
- La fonction utilise `INSERT` (pas `INSERT OR REPLACE` ou `INSERT OR IGNORE`)
- Les erreurs sont catchées mais seulement loggées
- Si un match a déjà des events, l'insertion devrait échouer avec une erreur de contrainte, mais l'erreur est ignorée silencieusement

### 4. Condition d'insertion dans la boucle principale

**Ligne 1715** :
```python
if events and highlight_events:
    event_rows = transform_highlight_events(highlight_events, match_id)
    if event_rows:
        inserted_this_match["events"] = _insert_event_rows(conn, event_rows)
        total_events += inserted_this_match["events"]
```

**Analyse** : Cette condition vérifie que `highlight_events` n'est pas vide. Si l'API retourne une liste vide pour un match, rien n'est inséré (correct).

---

## Problèmes Potentiels Identifiés

### Problème 1 : La requête de détection peut être incorrecte

**Hypothèse** : La table `highlight_events` pourrait contenir des données pour certains matchs mais pas tous. Si la requête `SELECT DISTINCT match_id FROM highlight_events` retourne des résultats, alors la condition `NOT IN` devrait fonctionner correctement.

**Vérification nécessaire** :
```sql
-- Compter les matchs avec highlight_events
SELECT COUNT(DISTINCT match_id) FROM highlight_events;

-- Compter les matchs total
SELECT COUNT(*) FROM match_stats;

-- Vérifier si certains matchs ont des events
SELECT ms.match_id, COUNT(he.id) as event_count
FROM match_stats ms
LEFT JOIN highlight_events he ON ms.match_id = he.match_id
GROUP BY ms.match_id
ORDER BY ms.start_time DESC
LIMIT 20;
```

### Problème 2 : La table highlight_events pourrait être vide ou presque vide

**Hypothèse** : Si la table `highlight_events` est vide ou ne contient que très peu de matchs, alors la condition `NOT IN (SELECT DISTINCT match_id FROM highlight_events)` retournera TOUS les matchs (car aucun match n'est dans la sous-requête).

**C'est probablement le cas** : D'après le diagnostic précédent, le dernier match de JGtm n'avait pas de highlight_events dans la base. Si la table est globalement vide ou presque vide, alors tous les matchs seront sélectionnés pour le backfill.

### Problème 3 : L'insertion peut échouer silencieusement

**Hypothèse** : Si un match a déjà des events (par exemple, insérés lors d'une sync précédente mais qui ont échoué partiellement), l'insertion de nouveaux events peut échouer avec des erreurs de contrainte qui sont ignorées.

**Impact** : Le script peut traiter tous les matchs, mais seulement certains events sont réellement insérés.

---

## Diagnostic Recommandé

Pour comprendre pourquoi tous les matchs sont sélectionnés, exécuter :

```sql
-- 1. Vérifier combien de matchs ont des highlight_events
SELECT COUNT(DISTINCT match_id) as matches_with_events
FROM highlight_events;

-- 2. Vérifier combien de matchs au total
SELECT COUNT(*) as total_matches
FROM match_stats;

-- 3. Vérifier la requête de détection
SELECT DISTINCT ms.match_id
FROM match_stats ms
WHERE ms.match_id NOT IN (
    SELECT DISTINCT match_id FROM highlight_events
)
ORDER BY ms.start_time DESC
LIMIT 10;

-- 4. Vérifier les matchs récents avec/sans events
SELECT 
    ms.match_id,
    ms.start_time,
    COUNT(he.id) as event_count
FROM match_stats ms
LEFT JOIN highlight_events he ON ms.match_id = he.match_id
GROUP BY ms.match_id, ms.start_time
ORDER BY ms.start_time DESC
LIMIT 20;
```

---

## Conclusion

**Cause probable** : La table `highlight_events` est probablement vide ou presque vide pour JGtm. Dans ce cas, la condition `NOT IN (SELECT DISTINCT match_id FROM highlight_events)` retourne correctement TOUS les matchs car aucun match n'a d'events.

**Ce n'est pas un bug** : C'est le comportement attendu si la table est vide. Le script devrait traiter tous les matchs pour les remplir.

**Vérification** : Il faut vérifier si la table `highlight_events` contient réellement des données pour JGtm. Si elle est vide, alors le comportement est correct.

---

## Recommandations

1. **Vérifier l'état de la table** : Exécuter les requêtes SQL ci-dessus pour comprendre l'état réel de la table
2. **Si la table est vide** : Le comportement est correct, mais il faudrait peut-être ajouter une option `--force-events` pour forcer la récupération même si des events existent déjà
3. **Si la table contient des données** : Il y a un problème avec la requête de détection qui doit être investigué plus en profondeur
