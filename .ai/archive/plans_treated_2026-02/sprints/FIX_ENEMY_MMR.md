# Plan : Correction enemy_mmr NULL

## Contexte

Les colonnes `enemy_mmr` sont toutes NULL dans les bases de données DuckDB, ce qui empêche l'affichage de :
- **MMR adverse** dans le tableau "Historique — matchs avec mes coéquipiers"
- **Écart MMR** (calculé comme `team_mmr - enemy_mmr`)

## Diagnostic

### Cause racine
Le problème est dans `src/data/sync/transformers.py` dans la fonction `transform_skill_stats()` (lignes 745-756).

Le code actuel cherche `Mmr` individuel des joueurs adverses :
```python
other_mmr = _safe_float(other_result.get("Mmr"))  # MMR individuel, pas TeamMmr
```

Mais il devrait utiliser `TeamMmr` d'un joueur de l'équipe adverse, ou mieux, extraire depuis `TeamMmrs` de l'API.

### Structure de l'API SPNKr (PlayerMatchStats)
```json
{
  "Value": [
    {
      "Id": "xuid(1234567890)",
      "Result": {
        "TeamId": 0,
        "TeamMmr": 1200.5,        // MMR de l'équipe du joueur
        "TeamMmrs": {             // MMR de toutes les équipes
          "0": 1200.5,
          "1": 1150.3
        },
        "Mmr": 1180.0,            // MMR individuel du joueur
        "StatPerformances": {...}
      }
    }
  ]
}
```

## Solution

### Option A : Utiliser TeamMmrs (Recommandé)
Modifier `transform_skill_stats()` pour extraire `enemy_mmr` depuis `TeamMmrs` :

```python
# Dans transform_skill_stats(), après avoir identifié le joueur
team_mmrs_raw = result.get("TeamMmrs")
if isinstance(team_mmrs_raw, dict) and team_id is not None:
    my_key = str(team_id)
    for k, v in team_mmrs_raw.items():
        if k != my_key:
            enemy_mmr = _safe_float(v)
            break
```

### Option B : Utiliser TeamMmr d'un adversaire
Modifier la boucle existante pour utiliser `TeamMmr` au lieu de `Mmr` :

```python
# Ligne 752 actuelle
other_mmr = _safe_float(other_result.get("Mmr"))

# Devrait être
other_team_mmr = _safe_float(other_result.get("TeamMmr"))
```

## Étapes d'implémentation

### 1. Corriger le transformer (5 min)
**Fichier** : `src/data/sync/transformers.py`

Modifier `transform_skill_stats()` (ligne ~745) :
```python
# AVANT
enemy_mmrs = []
for other in value:
    if not isinstance(other, dict):
        continue
    other_result = other.get("Result", {})
    other_team = other_result.get("TeamId")
    other_mmr = _safe_float(other_result.get("Mmr"))
    if other_team != team_id and other_mmr is not None:
        enemy_mmrs.append(other_mmr)

enemy_mmr = sum(enemy_mmrs) / len(enemy_mmrs) if enemy_mmrs else None

# APRÈS (Option A - recommandé)
enemy_mmr = None
team_mmrs_raw = result.get("TeamMmrs")
if isinstance(team_mmrs_raw, dict) and team_id is not None:
    my_key = str(team_id)
    for k, v in team_mmrs_raw.items():
        if k != my_key:
            enemy_mmr = _safe_float(v)
            break
```

### 2. Corriger aussi `_extract_mmr_from_skill()` (5 min)
**Fichier** : `src/data/sync/transformers.py`

Même logique à appliquer dans `_extract_mmr_from_skill()` (ligne ~629) qui est utilisée pour `transform_match_stats()`.

### 3. Script de backfill (15 min)
Créer `scripts/backfill_enemy_mmr.py` pour mettre à jour les matchs existants :

```python
"""Backfill enemy_mmr depuis l'API pour les matchs existants."""

async def backfill_enemy_mmr(gamertag: str, force: bool = False):
    """
    Pour chaque match avec enemy_mmr NULL :
    1. Récupérer le skill JSON depuis l'API
    2. Extraire enemy_mmr avec la logique corrigée
    3. UPDATE player_match_stats SET enemy_mmr = ? WHERE match_id = ?
    """
    pass
```

### 4. Tests (10 min)
Ajouter un test dans `tests/test_sync_engine.py` :
- Vérifier que `enemy_mmr` est correctement extrait
- Vérifier le cas où `TeamMmrs` est absent

## Fichiers impactés

| Fichier | Modification |
|---------|--------------|
| `src/data/sync/transformers.py` | Corriger extraction `enemy_mmr` |
| `scripts/backfill_enemy_mmr.py` | Nouveau script de backfill |
| `tests/test_sync_engine.py` | Ajouter tests |

## Validation

Après implémentation :
```bash
# 1. Vérifier le transformer
pytest tests/test_sync_engine.py -k "enemy_mmr" -v

# 2. Backfill un joueur
python scripts/backfill_enemy_mmr.py --gamertag JGtm

# 3. Vérifier les données
python -c "
import duckdb
con = duckdb.connect('data/players/JGtm/stats.duckdb', read_only=True)
print(con.execute('SELECT COUNT(enemy_mmr) FROM player_match_stats').fetchone())
"
```

## Notes

- Le fallback `COALESCE(match_stats.enemy_mmr, pms.enemy_mmr)` est déjà en place dans `duckdb_repo.py`
- Une fois `player_match_stats.enemy_mmr` rempli, le tableau affichera automatiquement les valeurs
- La correction du sync s'appliquera aux nouveaux matchs synchronisés
