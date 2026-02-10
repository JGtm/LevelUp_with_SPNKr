# Analyse: Film Chunks et Fonctions Antagonistes

> Date: 2026-02-02
> Statut: Investigation complète
> Lien: BINARY_CHUNK_ANALYSIS_V2_PLAN.md

## Contexte

Les fonctions antagonistes (Némésis/Souffre-douleur) utilisent les `highlight_events` extraits des film chunks Halo Infinite via `spnkr.film.read_highlight_events()`.

## Architecture actuelle

```
Film Chunks (binaire)
    ↓
spnkr.film.read_highlight_events()
    ↓
highlight_events (list[dict])
    ↓
compute_killer_victim_pairs() [tolérance ~5ms]
    ↓
compute_personal_antagonists()
    ↓
aggregate_antagonists()
    ↓
Table DuckDB: antagonists
```

## Découvertes validées (Investigation V2)

| Élément | Format validé | Impact |
|---------|---------------|--------|
| **Timestamp** | Big Endian, millisecondes | Critique pour l'appariement kill/death |
| **Event type** | byte 59: 50=kill, 20=death, 10=mode | Correctement utilisé via `type_hint` |
| **Gamertag** | UTF-16 LE, 32 bytes | Extraction roster OK |
| **Header (0-11)** | Identifiant joueur unique | Pas d'impact sur antagonistes |
| **Extra bytes (72+)** | Pas de weapon ID | Pas d'impact sur antagonistes |

## Corrélation validée

Sur le match Fiesta test (189d1c23):
- **14/14 kills** (100%) corrélés avec les observations Theatre
- **Précision temporelle** : 0.1s - 2.3s de delta
- **Bit offsets testés** : 0, 2, 4, 6 (tous productifs)

## Points de vigilance pour la stabilité

### 1. Format de timestamp

```python
# CORRECT (Big Endian)
timestamp_be = struct.unpack('>I', timestamp_bytes)[0]

# INCORRECT (Little Endian) - causerait des timestamps aberrants
timestamp_le = struct.unpack('<I', timestamp_bytes)[0]
```

**Si spnkr utilise Little Endian**, les timestamps seraient faux → mauvais appariement kill/death → antagonistes incohérents.

### 2. Bit offsets multiples

Les events peuvent être à différents bit offsets (0, 2, 4, 6). Si l'extraction ne scanne pas tous les offsets, certains events seront manqués.

### 3. Validation avec stats officielles

Le code actuel valide déjà les résultats :
```python
# Dans compute_personal_antagonists()
if kills_diff == 0 and deaths_diff == 0:
    is_validated = True
```

Si `is_validated=False` fréquemment, c'est un indicateur de problème d'extraction.

## Recommandations

### Court terme

1. **Monitorer `is_validated`** - Ajouter des logs/métriques sur le taux de validation
2. **Vérifier le format timestamp dans spnkr** - Confirmer Big Endian

### Moyen terme

1. **Script de diagnostic** - Comparer les events extraits par spnkr vs notre extraction validée
2. **Tests de régression** - Ajouter des tests avec des données réelles de film chunks

## Structure des fichiers concernés

| Fichier | Rôle |
|---------|------|
| `src/analysis/killer_victim.py` | Appariement kill/death, calcul antagonistes |
| `src/analysis/antagonists.py` | Agrégation multi-matchs |
| `src/data/sync/api_client.py` | Appel spnkr.film |
| `src/data/sync/transformers.py` | Transformation events → rows |

## Conclusion

L'investigation binaire a **validé** que l'extraction d'events fonctionne correctement quand le format est respecté (Big Endian timestamps, scan multi-offset). 

Les instabilités potentielles des antagonistes proviendraient de :
1. Mauvais format de timestamp dans spnkr
2. Events manqués (bit offsets non scannés)
3. Problèmes de roster (XUIDs/gamertags manquants)

**Action prioritaire** : Vérifier le code source de `spnkr.film` pour confirmer le format de timestamp utilisé.
