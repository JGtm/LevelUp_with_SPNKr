# Plan d'intégration SPNKr refdata.py

> Date : 2026-02-03
> Statut : Analyse et planification
> Référence : https://github.com/acurtis166/SPNKr/blob/master/spnkr/models/refdata.py

## Contexte

Le fichier `refdata.py` de SPNKr contient des enums officiels pour :
1. **GameVariantCategory** : Catégories de modes de jeu (Slayer, CTF, Oddball, etc.)
2. **PersonalScoreNameId** : Décomposition du score personnel (kills, assists, objectifs, etc.)

Ces enums permettraient de :
- ✅ Catégoriser les modes de manière **fiable et naturelle** (basé sur l'API officielle)
- ✅ **Décomposer le score personnel** pour analyser la participation aux objectifs
- ✅ **Valoriser les assistances et le marquage** pour les joueurs moins frag-oriented

---

## État actuel du code

### 1. Catégories de modes

**Fichiers concernés** :
- `src/analysis/mode_categories.py` : Mapping manuel préfixe → catégorie
- `Playlist_modes_translations.json` : Traductions + catégories manuelles
- `src/data/sync/transformers.py` : `_determine_mode_category()` utilise le mapping manuel

**Problèmes** :
- ❌ Mapping manuel fragile (nécessite maintenance)
- ❌ Catégories arbitraires ("Assassin", "Fiesta", "BTB", etc.)
- ❌ Pas aligné avec les catégories officielles de l'API

**Code actuel** :
```python
# src/analysis/mode_categories.py
PREFIX_TO_CATEGORY: Final[dict[str, str]] = {
    "Arena": "Assassin",
    "Arène": "Assassin",
    "Tactical": "Assassin",
    # ... mapping manuel
}
```

### 2. Score personnel

**Fichiers concernés** :
- `src/data/sync/transformers.py` : `personal_score` extrait mais **non décomposé**
- `src/data/sync/models.py` : `MatchStatsRow.personal_score: int | None`
- `docs/SQL_SCHEMA.md` : Colonne `personal_score INTEGER` dans `match_stats`

**État** :
- ✅ `PersonalScore` est récupéré depuis l'API (`CoreStats.PersonalScore`)
- ❌ **Pas de décomposition** : on ne sait pas d'où vient le score
- ❌ **Pas de table** pour stocker les composants (kills, assists, objectifs, etc.)

**Code actuel** :
```python
# src/data/sync/transformers.py:405
personal_score = _safe_int(stats_dict.get("PersonalScore")) if stats_dict else None
```

### 3. Assistances et marquage

**État** :
- ✅ `Assists` est récupéré et stocké (`match_stats.assists`)
- ❌ **Pas de décomposition** : Kill Assist, Mark Assist, Sensor Assist, EMP Assist, etc.
- ❌ **Pas de valorisation** différenciée dans les analyses

---

## Analyse de l'API

### GameVariantCategory

**Enum SPNKr** :
```python
class GameVariantCategory(IntEnum):
    MULTIPLAYER_SLAYER = 6
    MULTIPLAYER_CTF = 15
    MULTIPLAYER_ODDBALL = 18
    MULTIPLAYER_STOCKPILE = 19
    MULTIPLAYER_STRONGHOLDS = 11
    MULTIPLAYER_TOTAL_CONTROL = 14
    MULTIPLAYER_KING_OF_THE_HILL = 13
    # ... 42 catégories au total
```

**Disponibilité dans l'API** :
- ❓ `MatchInfo.GameVariantCategory` : **À vérifier** si présent dans les réponses API
- ✅ `MatchInfo.UgcGameVariant` : Asset ID du variant (peut contenir la catégorie)

**Hypothèse** :
- Si `GameVariantCategory` n'est pas directement dans `MatchInfo`, il faut le récupérer depuis l'asset `UgcGameVariant` via Discovery UGC.

### PersonalScoreNameId

**Enum SPNKr** :
```python
class PersonalScoreNameId(IntEnum):
    KILLED_PLAYER = 1024030246, "Killed Player"  # 100 pts
    KILL_ASSIST = 638246808, "Kill Assist"  # 50 pts
    MARK_ASSIST = 152718958, "Mark Assist"  # 10 pts
    SENSOR_ASSIST = 1267013266, "Sensor Assist"  # 10 pts
    EMP_ASSIST = 221060588, "EMP Assist"  # 50 pts
    FLAG_CAPTURED = 601966503, "Flag Captured"  # 300 pts
    FLAG_STOLEN = 3002710045, "Flag Stolen"  # 25 pts
    FLAG_RETURNED = 22113181, "Flag Returned"  # 25 pts
    HILL_SCORED = 1032565232, "Hill Scored"  # 100 pts
    ZONE_CAPTURED_100 = 757037588, "Zone Captured"  # 100 pts
    POWER_SEED_SECURED = 2188620691, "Power Seed Secured"  # 100 pts
    # ... 60+ types de scores
```

**Disponibilité dans l'API** :
- ❓ `CoreStats.PersonalScoreAwards[]` : **À vérifier** si présent
- ❓ `CoreStats.Breakdowns.PersonalScore[]` : **À vérifier** si présent
- ✅ `CoreStats.PersonalScore` : Score total (déjà récupéré)

**Hypothèse** :
- Le détail des `PersonalScoreAwards` pourrait être dans `CoreStats` mais non documenté.
- Alternative : Calculer depuis les médailles et événements connus.

---

## Plan d'action

### Phase 1 : Vérification API

**Objectif** : Confirmer ce qui est disponible dans les réponses API.

**Actions** :
1. **Examiner un payload réel** de `MatchStats` pour vérifier :
   - Présence de `MatchInfo.GameVariantCategory`
   - Présence de `CoreStats.PersonalScoreAwards[]`
   - Présence de `CoreStats.Breakdowns.PersonalScore[]`

2. **Script d'investigation** :
   ```python
   # scripts/investigate_refdata_fields.py
   - Charger un match réel depuis l'API
   - Examiner toutes les clés de MatchInfo
   - Examiner toutes les clés de CoreStats
   - Chercher GameVariantCategory
   - Chercher PersonalScoreAwards / Breakdowns
   ```

**Livrables** :
- Document `.ai/research/API_REFDATA_FIELDS.md` avec les résultats
- Script `scripts/investigate_refdata_fields.py`

### Phase 2 : Intégration GameVariantCategory

**Objectif** : Utiliser les catégories officielles au lieu du mapping manuel.

**Actions** :

#### 2.1 Créer le module refdata

```python
# src/data/domain/refdata.py
"""Enums de référence basés sur SPNKr refdata.py"""

from enum import IntEnum

class GameVariantCategory(IntEnum):
    """Catégories officielles de modes de jeu."""
    UNKNOWN = -1
    NONE = 0
    CAMPAIGN = 1
    FORGE = 2
    ACADEMY = 3
    # ... copier depuis SPNKr
    MULTIPLAYER_SLAYER = 6
    MULTIPLAYER_CTF = 15
    # ...

# Mapping catégorie → nom français
CATEGORY_TO_FR: dict[int, str] = {
    GameVariantCategory.MULTIPLAYER_SLAYER: "Assassin",
    GameVariantCategory.MULTIPLAYER_CTF: "Capture de drapeau",
    GameVariantCategory.MULTIPLAYER_ODDBALL: "Balle",
    # ...
}
```

#### 2.2 Modifier le transformer

**Si `GameVariantCategory` est dans l'API** :
```python
# src/data/sync/transformers.py
from src.data.domain.refdata import GameVariantCategory, CATEGORY_TO_FR

def _extract_game_variant_category(match_info: dict[str, Any]) -> int | None:
    """Extrait GameVariantCategory depuis MatchInfo."""
    category_raw = match_info.get("GameVariantCategory")
    if category_raw is None:
        return None
    try:
        return int(category_raw)
    except (ValueError, TypeError):
        return None

def _determine_mode_category_v2(
    pair_name: str | None,
    game_variant_category: int | None,
) -> str:
    """Détermine la catégorie en utilisant GameVariantCategory si disponible."""
    if game_variant_category is not None:
        return CATEGORY_TO_FR.get(game_variant_category, "Other")
    # Fallback sur l'ancienne méthode
    return infer_custom_category_from_pair_name(pair_name)
```

**Si `GameVariantCategory` n'est pas dans l'API** :
- Récupérer depuis l'asset `UgcGameVariant` via Discovery UGC
- Stocker dans la table `game_modes` (metadata.duckdb)
- Utiliser lors de la transformation

#### 2.3 Migration BDD

**Ajouter colonne** :
```sql
ALTER TABLE match_stats ADD COLUMN game_variant_category INTEGER;
```

**Mettre à jour** :
- Les matchs existants gardent `mode_category` (ancien système)
- Les nouveaux matchs utilisent `game_variant_category` (nouveau système)
- Migration script pour backfill si nécessaire

**Livrables** :
- Module `src/data/domain/refdata.py`
- Transformer modifié
- Migration BDD
- Tests unitaires

### Phase 3 : Décomposition PersonalScore

**Objectif** : Stocker et analyser les composants du score personnel.

**Actions** :

#### 3.1 Vérifier disponibilité API

**Si `PersonalScoreAwards` est disponible** :
```python
# src/data/sync/transformers.py
def _extract_personal_score_awards(
    stats_dict: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extrait les PersonalScoreAwards depuis CoreStats."""
    awards = stats_dict.get("PersonalScoreAwards", [])
    if not isinstance(awards, list):
        return []
    
    result = []
    for award in awards:
        if not isinstance(award, dict):
            continue
        name_id = award.get("NameId")
        count = award.get("Count", 0)
        if name_id is not None:
            result.append({
                "name_id": int(name_id),
                "count": int(count),
            })
    return result
```

**Si non disponible** :
- Calculer depuis les médailles et événements connus
- Utiliser les valeurs de `PersonalScoreNameId` pour mapper

#### 3.2 Créer table BDD

```sql
-- Table pour stocker les composants du score personnel
CREATE TABLE personal_score_awards (
    match_id VARCHAR NOT NULL,
    award_name_id INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, award_name_id),
    FOREIGN KEY (match_id) REFERENCES match_stats(match_id)
);

-- Index pour requêtes rapides
CREATE INDEX idx_personal_score_awards_match ON personal_score_awards(match_id);
CREATE INDEX idx_personal_score_awards_name_id ON personal_score_awards(award_name_id);
```

#### 3.3 Modifier le transformer

```python
# src/data/sync/models.py
@dataclass
class PersonalScoreAwardRow:
    """Ligne pour la table personal_score_awards."""
    match_id: str
    award_name_id: int
    count: int

# src/data/sync/transformers.py
def transform_personal_score_awards(
    match_id: str,
    stats_dict: dict[str, Any],
) -> list[PersonalScoreAwardRow]:
    """Transforme les PersonalScoreAwards en lignes BDD."""
    awards = _extract_personal_score_awards(stats_dict)
    return [
        PersonalScoreAwardRow(
            match_id=match_id,
            award_name_id=award["name_id"],
            count=award["count"],
        )
        for award in awards
    ]
```

#### 3.4 Créer module refdata pour PersonalScoreNameId

```python
# src/data/domain/refdata.py
class PersonalScoreNameId(IntEnum):
    """Types de scores personnels."""
    KILLED_PLAYER = 1024030245, "Killed Player"
    KILL_ASSIST = 638246808, "Kill Assist"
    MARK_ASSIST = 152718958, "Mark Assist"
    # ... copier depuis SPNKr

# Mapping pour analyses
OBJECTIVE_SCORES = {
    PersonalScoreNameId.FLAG_CAPTURED,
    PersonalScoreNameId.FLAG_STOLEN,
    PersonalScoreNameId.FLAG_RETURNED,
    PersonalScoreNameId.HILL_SCORED,
    PersonalScoreNameId.ZONE_CAPTURED_100,
    PersonalScoreNameId.POWER_SEED_SECURED,
    # ...
}

ASSIST_SCORES = {
    PersonalScoreNameId.KILL_ASSIST,
    PersonalScoreNameId.MARK_ASSIST,
    PersonalScoreNameId.SENSOR_ASSIST,
    PersonalScoreNameId.EMP_ASSIST,
    # ...
}
```

**Livrables** :
- Table `personal_score_awards`
- Transformer pour extraire et stocker
- Module refdata avec enums
- Requêtes SQL pour analyses

### Phase 4 : Analyses et visualisations

**Objectif** : Utiliser les données décomposées pour valoriser les joueurs.

**Actions** :

#### 4.1 Requêtes SQL d'analyse

```sql
-- Score par type d'objectif
SELECT 
    psa.award_name_id,
    SUM(psa.count) as total_count,
    SUM(psa.count * award_points.value) as total_points
FROM personal_score_awards psa
JOIN award_points ON psa.award_name_id = award_points.name_id
WHERE psa.award_name_id IN (
    SELECT name_id FROM objective_scores
)
GROUP BY psa.award_name_id
ORDER BY total_points DESC;

-- Top joueurs sur objectifs (par match)
SELECT 
    ms.match_id,
    ms.start_time,
    SUM(CASE 
        WHEN psa.award_name_id IN (objective_scores) 
        THEN psa.count * award_points.value 
        ELSE 0 
    END) as objective_score
FROM match_stats ms
LEFT JOIN personal_score_awards psa ON ms.match_id = psa.match_id
WHERE ms.mode_category IN ('CTF', 'Oddball', 'Strongholds', 'Total Control')
GROUP BY ms.match_id, ms.start_time
ORDER BY objective_score DESC;

-- Valorisation assistances
SELECT 
    ms.match_id,
    ms.kills,
    ms.assists,
    SUM(CASE 
        WHEN psa.award_name_id = 638246808 THEN psa.count * 50  -- Kill Assist
        WHEN psa.award_name_id = 152718958 THEN psa.count * 10  -- Mark Assist
        WHEN psa.award_name_id = 1267013266 THEN psa.count * 10 -- Sensor Assist
        ELSE 0 
    END) as assist_score
FROM match_stats ms
LEFT JOIN personal_score_awards psa ON ms.match_id = psa.match_id
GROUP BY ms.match_id, ms.kills, ms.assists;
```

#### 4.2 Nouveaux KPIs

**Créer module** :
```python
# src/analysis/objective_participation.py
"""Analyse de la participation aux objectifs."""

def compute_objective_participation_score(
    match_id: str,
    repo: DuckDBRepository,
) -> dict[str, Any]:
    """Calcule un score de participation aux objectifs."""
    # Requête SQL pour sommer les scores d'objectifs
    # Retourne : objective_score, assist_score, total_score
    pass

def rank_players_by_objective_contribution(
    match_ids: list[str],
    repo: DuckDBRepository,
) -> list[dict[str, Any]]:
    """Classe les joueurs par contribution aux objectifs."""
    # Utilise personal_score_awards pour calculer
    # Retourne : xuid, gamertag, objective_score, assist_score, kills
    pass
```

#### 4.3 Visualisations Streamlit

**Nouvelle page** : `src/ui/pages/objective_analysis.py`
- Graphique : Score objectifs vs Kills par match
- Tableau : Top joueurs sur objectifs
- Métriques : Ratio objectifs/kills, assistances valorisées

**Livrables** :
- Module d'analyse
- Requêtes SQL optimisées
- Visualisations Streamlit
- Documentation utilisateur

---

## Bénéfices attendus

### 1. Catégories de modes

| Avant | Après |
|------|-------|
| Mapping manuel fragile | Catégories officielles API |
| Maintenance continue | Auto-mise à jour |
| Catégories arbitraires | Catégories standardisées |

### 2. Score personnel décomposé

| Avant | Après |
|------|-------|
| Score total seulement | Décomposition complète |
| Pas de visibilité objectifs | Contribution objectifs visible |
| Assistances non valorisées | Assistances différenciées |

### 3. Analyses enrichies

- ✅ Identifier les joueurs "support" (beaucoup d'assistances, peu de kills)
- ✅ Identifier les joueurs "objectifs" (beaucoup de captures/zones, peu de kills)
- ✅ Valoriser les joueurs qui font le "travail invisible"
- ✅ Comparer la contribution réelle vs K/D ratio

---

## Risques et limitations

### Risques

1. **GameVariantCategory non disponible** :
   - Solution : Récupérer depuis Discovery UGC (plus lent)
   - Impact : Nécessite requête API supplémentaire par match

2. **PersonalScoreAwards non disponible** :
   - Solution : Calculer depuis médailles/événements (approximatif)
   - Impact : Données moins précises

3. **Migration données existantes** :
   - Solution : Backfill progressif ou laisser vide
   - Impact : Données historiques incomplètes

### Limitations

- Les données décomposées ne seront disponibles que pour les **nouveaux matchs**
- Les matchs historiques garderont seulement `personal_score` total
- Nécessite migration si on veut backfill

---

## Prochaines étapes

1. ✅ **Créer ce document** (fait)
2. ✅ **Créer script d'investigation** (fait : `scripts/investigate_refdata_fields.py`)
3. ⏳ **Phase 1** : Exécuter le script pour vérifier disponibilité API
4. ⏳ **Phase 2** : Intégrer GameVariantCategory
5. ⏳ **Phase 3** : Décomposer PersonalScore
6. ⏳ **Phase 4** : Créer analyses et visualisations

## Scripts créés

### `scripts/investigate_refdata_fields.py`

Script d'investigation pour vérifier la disponibilité des champs refdata dans l'API.

**Usage** :
```bash
# Analyser un match spécifique
python scripts/investigate_refdata_fields.py <match_id>

# Analyser le match le plus récent d'un joueur
python scripts/investigate_refdata_fields.py "" JGtm
```

**Sortie** :
- Analyse complète de `MatchInfo` et `CoreStats`
- Recherche de `GameVariantCategory`
- Recherche de `PersonalScoreAwards` et `Breakdowns.PersonalScore`
- Sauvegarde du JSON complet dans `data/investigation/refdata_investigation_<match_id>.json`

---

## Références

- [SPNKr refdata.py](https://github.com/acurtis166/SPNKr/blob/master/spnkr/models/refdata.py)
- [SPNKr Documentation](https://github.com/OpenSpartan/grunt)
- `.ai/API_LIMITATIONS.md` : Limitations connues de l'API
- `docs/SQL_SCHEMA.md` : Schéma actuel de la BDD
