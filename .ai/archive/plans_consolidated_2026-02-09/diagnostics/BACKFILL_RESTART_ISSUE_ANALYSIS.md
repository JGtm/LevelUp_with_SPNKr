# Analyse : Problème de reprise après interruption du backfill

**Date** : 2026-02-09  
**Problème** : Le script `backfill_data.py --all-data` recommence à 0 après interruption alors qu'il avait déjà traité plus de la moitié des matchs.

---

## Problème identifié

### Logique actuelle (ligne 966)

```python
where_clause = " OR ".join(conditions)
```

**Comportement** : Les conditions sont combinées avec `OR`, ce qui signifie qu'un match est sélectionné s'il manque **AU MOINS UNE** des données demandées.

### Exemple concret avec `--all-data`

Avec `--all-data`, les conditions suivantes sont activées :
- `medals` : matchs sans médailles
- `events` : matchs sans highlight_events
- `skill` : matchs sans skill stats
- `personal_scores` : matchs sans personal scores
- `participants` : matchs sans participants
- `participants_scores` : matchs où participants ont rank/score NULL
- `participants_kda` : matchs où participants ont k/d/a NULL
- `participants_shots` : matchs où participants ont shots NULL
- `accuracy` : matchs avec accuracy NULL
- `shots` : matchs avec shots_fired/shots_hit NULL
- `enemy_mmr` : matchs avec enemy_mmr NULL
- `assets` : matchs avec noms manquants
- etc.

**Résultat** : Un match est sélectionné s'il manque **AU MOINS UNE** de ces données.

### Pourquoi le script recommence à 0

**Scénario** :
1. Premier lancement : 704 matchs détectés (tous manquent au moins une donnée)
2. Traitement de 440 matchs : Chaque match reçoit certaines données (medals, events, skill, etc.)
3. Interruption du script
4. Relancement : Le script détecte à nouveau **704 matchs** car :
   - Les matchs traités ont maintenant des medals, events, skill...
   - MAIS ils manquent peut-être encore `participants_scores`, `participants_kda`, `participants_shots`, `accuracy`, `shots`, `enemy_mmr`, `assets`, etc.
   - Avec `OR`, ces matchs sont **encore sélectionnés** car ils manquent au moins une donnée

**Exemple** :
- Match traité : a maintenant medals, events, skill, personal_scores, participants
- Mais il manque encore : `participants_scores` (rank/score NULL), `accuracy` NULL, `shots` NULL
- Avec `OR`, ce match est **encore sélectionné** car il manque `participants_scores` OU `accuracy` OU `shots`

---

## Impact

### Problème principal

Le script retraite les mêmes matchs plusieurs fois, ce qui :
- ❌ Est inefficace (appels API inutiles)
- ❌ Est frustrant (pas de progression visible)
- ❌ Peut être très long pour un joueur avec beaucoup de matchs

### Pourquoi c'est particulièrement visible avec `--all-data`

Avec `--all-data`, **17 options** sont activées. La probabilité qu'un match manque encore au moins une donnée après traitement partiel est très élevée.

---

## Solutions possibles

### Solution 1 : Utiliser `AND` au lieu de `OR` (non recommandé)

**Problème** : Ne sélectionnerait que les matchs qui manquent **TOUTES** les données, ce qui est trop restrictif.

### Solution 2 : Tracker les matchs déjà traités (recommandé)

Ajouter une table de tracking pour mémoriser quels matchs ont été traités avec quelles options :

```sql
CREATE TABLE IF NOT EXISTS backfill_progress (
    match_id VARCHAR NOT NULL,
    options_hash VARCHAR NOT NULL,  -- Hash des options activées
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (match_id, options_hash)
);
```

**Avantage** : Permet de reprendre exactement là où on s'est arrêté  
**Inconvénient** : Nécessite une modification importante du code

### Solution 3 : Vérifier si un match a TOUTES les données avant de le traiter (recommandé)

Avant de traiter un match, vérifier s'il a déjà toutes les données demandées :

```python
def _match_has_all_requested_data(match_id, conn, options):
    """Vérifie si un match a déjà toutes les données demandées."""
    checks = []
    
    if options.medals:
        checks.append(has_medals(match_id, conn))
    if options.events:
        checks.append(has_events(match_id, conn))
    if options.skill:
        checks.append(has_skill(match_id, conn))
    # etc.
    
    return all(checks)
```

**Avantage** : Simple à implémenter  
**Inconvénient** : Peut être lent si beaucoup de matchs à vérifier

### Solution 4 : Améliorer la requête SQL pour exclure les matchs déjà complets (recommandé)

Modifier `_find_matches_missing_data` pour exclure les matchs qui ont déjà toutes les données demandées :

```python
# Au lieu de OR, construire une condition qui vérifie si TOUTES les données sont présentes
# et exclure ces matchs
```

**Avantage** : Efficace, tout se fait en SQL  
**Inconvénient** : Requête SQL plus complexe

---

## Recommandation

**Solution 4** : Améliorer la requête SQL pour exclure les matchs qui ont déjà toutes les données demandées.

La logique devrait être :
- Si `--all-data` est activé, ne sélectionner que les matchs qui manquent **AU MOINS UNE** des données
- Mais exclure les matchs qui ont **DÉJÀ TOUTES** les données principales (medals, events, skill, personal_scores, participants)

Cela permettrait de :
- ✅ Ne pas retraiter les matchs déjà complets
- ✅ Continuer à traiter les matchs partiellement remplis
- ✅ Reprendre là où on s'est arrêté sans perdre de progression

---

## Conclusion

Le comportement actuel avec `OR` est **techniquement correct** mais **inefficace** pour `--all-data` car :
- Un match peut être traité plusieurs fois si différentes données sont insérées à chaque fois
- Il n'y a pas de mécanisme pour tracker qu'un match a déjà été traité avec `--all-data`

**Action recommandée** : Implémenter la Solution 4 pour améliorer l'efficacité du backfill.

---

## Correction implémentée (2026-02-09)

**Modification** : Ajout d'une clause d'exclusion dans `_find_matches_missing_data` pour exclure les matchs qui ont déjà toutes les données principales (medals, events, skill, personal_scores, participants) lors de l'utilisation de `--all-data`.

**Code ajouté** :
```python
# Détecter si on utilise --all-data (beaucoup d'options activées)
exclude_complete_matches = (
    all_data
    and medals
    and events
    and skill
    and personal_scores
    and participants
    and not force_medals
    and not force_participants
)

# Dans la requête SQL :
if exclude_complete_matches:
    exclude_clause = """
        AND ms.match_id NOT IN (
            SELECT DISTINCT ms2.match_id
            FROM match_stats ms2
            WHERE ms2.match_id IN (SELECT DISTINCT match_id FROM medals_earned)
              AND ms2.match_id IN (SELECT DISTINCT match_id FROM highlight_events)
              AND ms2.match_id IN (SELECT DISTINCT match_id FROM player_match_stats WHERE xuid = ?)
              AND ms2.match_id IN (SELECT DISTINCT match_id FROM personal_score_awards WHERE xuid = ?)
              AND ms2.match_id IN (SELECT DISTINCT match_id FROM match_participants)
        )
    """
```

**Résultat attendu** :
- ✅ Les matchs qui ont déjà toutes les données principales ne seront plus retraités lors d'un relancement
- ✅ Les matchs partiellement traités seront encore sélectionnés (normal, ils manquent encore des données)
- ✅ Le script peut reprendre là où il s'est arrêté sans retraiter les matchs déjà complets
