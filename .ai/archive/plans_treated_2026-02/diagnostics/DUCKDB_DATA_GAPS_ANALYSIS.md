# Analyse des Données Manquantes - DuckDB v4

## Diagnostic Complet

### Date: 2026-02-03

---

## 1. ÉTAT ACTUEL DE LA BASE JGtm

### 1.1 Tables et Remplissage

| Table | Lignes | Statut |
|-------|--------|--------|
| `match_stats` | 448 | ✅ Peuplée |
| `medals_earned` | 0 | ❌ VIDE |
| `highlight_events` | 0 | ❌ VIDE |
| `antagonists` | 0 | ❌ VIDE |
| `xuid_aliases` | 0 | ❌ VIDE |
| `skill_history` | 0 | ❌ VIDE |
| `killer_victim_pairs` | 0 | ❌ VIDE |
| `career_progression` | 0 | ❌ VIDE |
| `teammates_aggregate` | 853 | ✅ Peuplée |
| `personal_score_awards` | 1321 | ✅ Peuplée |

### 1.2 Colonnes Critiques dans `match_stats`

| Colonne | % Rempli | Impact UI |
|---------|----------|-----------|
| `time_played_seconds` | **0%** | ❌ Durée match, stats/min |
| `avg_life_seconds` | **0%** | ❌ Durée de vie moyenne |
| `damage_dealt` | **0%** | ❌ Stats de dégâts |
| `damage_taken` | **0%** | ❌ Stats de dégâts |
| `shots_fired` | **0%** | ❌ Précision détaillée |
| `shots_hit` | **0%** | ❌ Précision détaillée |
| `team_mmr` | **0%** | ❌ MMR équipe |
| `enemy_mmr` | **0%** | ❌ MMR ennemis |
| `map_name` | 78.3% | ⚠️ Partiel |
| `playlist_name` | ~0% | ❌ Noms playlists |
| `pair_name` | ~0% | ❌ Noms modes |

### 1.3 Timeline des Imports

| Date | Matchs | Source probable |
|------|--------|-----------------|
| 2026-01-26 | 351 | Migration initiale (partielle) |
| 2026-02-01 | 92 | Sync incrémentale |
| 2026-02-03 | 5 | Sync incrémentale |

---

## 2. CAUSES RACINES

### 2.1 Problème #1: Import Initial Incomplet

Les 351 matchs du 26 janvier ont été importés avec des données partielles.
Le script/processus d'import n'a pas récupéré toutes les colonnes.

**Hypothèse**: Migration depuis une ancienne base SQLite qui n'avait pas ces colonnes.

### 2.2 Problème #2: sync_delta() ne met pas à jour les matchs existants

```
Mode delta : s'arrête dès qu'un match connu est rencontré
→ Ne peut jamais compléter les données manquantes
```

Le code dans `DuckDBSyncEngine._process_matches`:
```python
if match_id in existing_ids:
    if delta_mode:
        return result  # STOP - ne met pas à jour
```

### 2.3 Problème #3: Tables auxiliaires jamais peuplées

Les tables `medals_earned`, `highlight_events`, `antagonists` sont créées mais jamais remplies car :
1. L'import initial ne les a pas créées
2. `sync_delta()` ne traite pas les matchs existants

### 2.4 Problème #4: Données API potentiellement absentes

L'API `get_match_stats()` pourrait ne pas retourner toutes les données dans tous les cas.
À vérifier : est-ce que le JSON brut contient `TimePlayed`, `AverageLifeSeconds`, etc. ?

---

## 3. IMPACTS UI

### 3.1 Graphiques Vides
- ❌ Stats par minute (kills/min, deaths/min) - division par 0
- ❌ Durée de vie moyenne - NULL
- ❌ Durée totale de jeu - NULL  
- ❌ Durée moyenne de match - NULL

### 3.2 Fonctionnalités Cassées
- ❌ Antagonistes (0 highlight_events)
- ❌ Médailles par match (0 medals_earned)
- ❌ Association médias ↔ matchs (start_time OK mais autres données manquantes)
- ❌ Adornment profil (cache supprimé, pas re-fetché correctement)

### 3.3 Onglets Affectés
- **Séries temporelles**: Graphiques vides ou partiels
- **Dernier match**: Pas de médailles, pas d'antagonistes
- **Match**: Idem
- **Bibliothèque médias**: Association impossible

---

## 4. PLAN DE CORRECTION

### Phase 1: Diagnostic Approfondi (30 min)

1. **Vérifier le JSON brut de l'API**
   - Tester `client.get_match_stats(match_id)` sur un match récent
   - Vérifier si `TimePlayed`, `AverageLifeSeconds`, `DamageDealt` sont présents
   - Documenter la structure exacte du JSON

2. **Vérifier le transformer**
   - `transform_match_stats()` extrait-il correctement ces champs ?
   - `_extract_life_time_stats()` fonctionne-t-il ?

### Phase 2: Backfill des Données Manquantes

**Option A: sync_full() avec UPDATE**
- Modifier `_process_single_match` pour UPDATE au lieu de SKIP
- Risque: Écrase les données existantes

**Option B: Script de backfill dédié** ✅ RECOMMANDÉ
```python
async def backfill_missing_data(
    match_ids: list[str],
    columns_to_fill: list[str]
) -> SyncResult:
    """Récupère uniquement les données manquantes pour les matchs existants."""
```

**Option C: Réimport complet**
- Supprimer les données et réimporter
- Plus simple mais perte de l'historique de sync

### Phase 3: Peupler les Tables Auxiliaires

1. **medals_earned**: 
   - Extraire depuis `stats_json.Players[].PlayerTeamStats[].Stats.CoreStats.Medals[]`
   - Ou depuis un endpoint dédié de l'API

2. **highlight_events**:
   - Déjà supporté dans `_process_single_match`
   - Juste besoin de re-traiter les matchs

3. **antagonists**:
   - Calculé depuis `highlight_events` après peuplement
   - Utiliser `_refresh_aggregates_async()`

### Phase 4: Corrections UI

1. **Message médias redondant**
   - Supprimer le message "Aucune fenêtre temporelle..."
   - Garder uniquement "Aucun média n'a pu être associé..."

2. **Gestion des NULL**
   - Afficher "N/A" ou masquer les graphiques si données manquantes
   - Ne pas afficher de graphiques vides

---

## 5. ACTIONS IMMÉDIATES

### Action 1: Vérifier l'API (5 min)
```python
# Script de test
async def test_api_data():
    client = SPNKrAPIClient(tokens)
    stats = await client.get_match_stats("84c6dd42-c7c7-4119-83ab-9266ca2ba273")
    print(json.dumps(stats, indent=2, default=str))
```

### Action 2: Créer script backfill (2h)
```bash
python scripts/backfill_match_data.py --gamertag JGtm --columns time_played,avg_life,damage,medals,events
```

### Action 3: Corriger UI médias (15 min)
- Supprimer message redondant

### Action 4: Tests automatisés (1h)
- Ajouter tests qui vérifient que les colonnes critiques sont non-NULL après sync

---

## 6. QUESTIONS OUVERTES

1. **L'API SPNKr retourne-t-elle toutes ces données ?**
   - `TimePlayed` format ISO 8601 ?
   - `AverageLifeSeconds` disponible ?
   - `DamageDealt/DamageTaken` disponibles ?

2. **Comment ont été importés les 351 matchs initiaux ?**
   - Quel script ?
   - Quelle version du code ?

3. **Faut-il garder la compatibilité avec l'ancienne base SQLite ?**
   - Ou migration complète vers DuckDB v4 ?

---

## 7. MÉTRIQUES DE SUCCÈS

Après correction, vérifier :
- [x] `time_played_seconds` rempli à 100% ✅ (CORRIGÉ 2026-02-03)
- [x] `avg_life_seconds` rempli à 97.1% ✅ (CORRIGÉ 2026-02-03)
- [ ] `medals_earned` > 0 lignes (TODO: ajouter extraction medals)
- [x] `highlight_events` > 0 lignes ✅ (100,268 lignes après backfill)
- [ ] `antagonists` calculés (TODO: relancer refresh_aggregates)
- [ ] UI affiche les stats/min correctement
- [ ] Association médias ↔ matchs fonctionne

---

## 8. CORRECTIONS EFFECTUÉES (2026-02-03)

### 8.1 Correction du Transformer
- **Fichier**: `src/data/sync/transformers.py`
- **Problème**: `_extract_life_time_stats()` cherchait `AverageLifeSeconds` au lieu de `AverageLifeDuration`
- **Solution**: Ajout de fallback pour parser `AverageLifeDuration` (format ISO 8601: "PT49.3S")
- **Solution**: Ajout de fallback pour extraire `Duration` depuis `MatchInfo`

### 8.2 Script de Backfill
- **Fichier**: `scripts/backfill_match_data.py`
- **Fonctionnalité**: Récupère les données manquantes pour les matchs existants
- **Résultat**: 448 matchs mis à jour avec time_played, avg_life, damage, etc.
- **Résultat**: 100,268 highlight_events ajoutés
