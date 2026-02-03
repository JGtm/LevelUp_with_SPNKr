# Résultats Investigation API Refdata

> Date : 2026-02-03  
> Statut : ✅ Investigation complète  
> Match analysé : `253e4aab-56c2-4f0a-8233-cdfedd903012`

---

## Résumé

| Champ | Disponible | Chemin | Type |
|-------|------------|--------|------|
| `GameVariantCategory` | ✅ **OUI** | `MatchInfo.GameVariantCategory` | `int` |
| `PersonalScores` | ✅ **OUI** | `Players[].PlayerTeamStats[].Stats.CoreStats.PersonalScores[]` | `list[dict]` |
| `Outcome` | ✅ **OUI** | `Players[].Outcome` et `Teams[].Outcome` | `int` |

---

## 1. GameVariantCategory

### Disponibilité

**✅ DISPONIBLE** directement dans `MatchInfo.GameVariantCategory`.

### Exemple

```json
{
  "MatchInfo": {
    "GameVariantCategory": 6,
    "LifecycleMode": 3,
    "PlaylistExperience": 2,
    ...
  }
}
```

### Valeurs observées

- `6` = `MULTIPLAYER_SLAYER` (Assassin)

### Impact sur l'implémentation

- **Pas besoin** de récupérer via Discovery UGC
- Extraction directe depuis `MatchInfo` lors du parsing
- Valeur entière à mapper vers `GameVariantCategory` enum

---

## 2. PersonalScores (Décomposition du score personnel)

### Disponibilité

**✅ DISPONIBLE** dans `CoreStats.PersonalScores[]`.

### Chemin complet

```
Players[].PlayerTeamStats[].Stats.CoreStats.PersonalScores[]
Teams[].Stats.CoreStats.PersonalScores[]
```

### Structure

```json
{
  "PersonalScores": [
    {
      "NameId": 1024030246,
      "Count": 7,
      "TotalPersonalScoreAwarded": 700
    },
    {
      "NameId": 638246808,
      "Count": 12,
      "TotalPersonalScoreAwarded": 600
    }
  ]
}
```

### Champs

| Champ | Type | Description |
|-------|------|-------------|
| `NameId` | `int` | ID du type de score (voir `PersonalScoreNameId`) |
| `Count` | `int` | Nombre d'occurrences |
| `TotalPersonalScoreAwarded` | `int` | Points totaux attribués |

### Valeurs observées

| NameId | Enum | Description | Points/unité |
|--------|------|-------------|--------------|
| `1024030246` | `KILLED_PLAYER` | Joueur tué | 100 |
| `638246808` | `KILL_ASSIST` | Assistance kill | 50 |

### Exemple match Slayer

```json
// Joueur avec 7 kills et 12 assists
"PersonalScores": [
  {
    "NameId": 1024030246,  // KILLED_PLAYER
    "Count": 7,
    "TotalPersonalScoreAwarded": 700  // 7 × 100
  },
  {
    "NameId": 638246808,   // KILL_ASSIST
    "Count": 12,
    "TotalPersonalScoreAwarded": 600  // 12 × 50
  }
]
// Total PersonalScore = 1300
```

### Note importante

Le champ s'appelle `PersonalScores` (pas `PersonalScoreAwards` comme dans SPNKr).
La structure est identique mais le nom diffère.

---

## 3. Outcome (Résultat du match)

### Disponibilité

**✅ DISPONIBLE** dans `Players[].Outcome` et `Teams[].Outcome`.

### Valeurs

| Valeur | Enum | Description |
|--------|------|-------------|
| `2` | `WIN` | Victoire |
| `3` | `LOSS` | Défaite |
| `1` | `TIE` | Égalité |

---

## 4. Structure complète CoreStats

```json
{
  "CoreStats": {
    "Score": 7,
    "PersonalScore": 1300,
    "RoundsWon": 1,
    "RoundsLost": 0,
    "RoundsTied": 0,
    "Kills": 7,
    "Deaths": 10,
    "Assists": 12,
    "KDA": 1.0,
    "Suicides": 0,
    "Betrayals": 0,
    "AverageLifeDuration": "PT35.1S",
    "GrenadeKills": 0,
    "HeadshotKills": 2,
    "MeleeKills": 1,
    "PowerWeaponKills": 0,
    "ShotsFired": 507,
    "ShotsHit": 217,
    "Accuracy": 42.8,
    "DamageDealt": 3160,
    "DamageTaken": 3669,
    "CalloutAssists": 0,
    "VehicleDestroys": 0,
    "DriverAssists": 0,
    "Hijacks": 0,
    "EmpAssists": 0,
    "MaxKillingSpree": 2,
    "Medals": [...],
    "PersonalScores": [...],
    "Spawns": 11,
    "ObjectivesCompleted": 0
  }
}
```

---

## 5. Chemin d'accès aux données joueur

```
Players[]
├── PlayerId: "xuid(2535461927511067)"
├── PlayerType: 1 (HUMAN)
├── LastTeamId: 1
├── Outcome: 2 (WIN)
├── Rank: 4
├── ParticipationInfo
│   ├── FirstJoinedTime
│   ├── TimePlayed
│   └── ...
└── PlayerTeamStats[]
    └── Stats
        ├── CoreStats
        │   ├── PersonalScore: 1300
        │   ├── PersonalScores: [...]  ← DÉCOMPOSITION
        │   └── ...
        └── PvpStats
            └── ...
```

---

## Impact sur l'implémentation

### Sprint 1 : Schémas BDD

**Table `personal_score_awards`** :

```sql
CREATE TABLE personal_score_awards (
    match_id VARCHAR NOT NULL,
    player_xuid VARCHAR NOT NULL,
    award_name_id INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    total_score_awarded INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, player_xuid, award_name_id)
);
```

### Sprint 2 : Extraction

```python
def _extract_personal_scores(
    player_stats: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extrait PersonalScores depuis PlayerTeamStats.Stats.CoreStats."""
    core_stats = (
        player_stats
        .get("PlayerTeamStats", [{}])[0]
        .get("Stats", {})
        .get("CoreStats", {})
    )
    
    personal_scores = core_stats.get("PersonalScores", [])
    return [
        {
            "name_id": score.get("NameId"),
            "count": score.get("Count", 0),
            "total_score": score.get("TotalPersonalScoreAwarded", 0),
        }
        for score in personal_scores
        if score.get("NameId") is not None
    ]
```

### Modification transformer

```python
def _extract_game_variant_category(match_info: dict[str, Any]) -> int | None:
    """Extrait GameVariantCategory depuis MatchInfo."""
    category = match_info.get("GameVariantCategory")
    return int(category) if category is not None else None
```

---

## Conclusion

Les deux champs clés sont **disponibles directement** dans l'API :

1. ✅ `GameVariantCategory` : Extraction triviale depuis `MatchInfo`
2. ✅ `PersonalScores` : Extraction depuis `CoreStats.PersonalScores[]`

**Aucun appel API supplémentaire** (Discovery UGC) n'est nécessaire.

Le Sprint 1 peut commencer immédiatement avec ces spécifications.

---

## Fichiers associés

- Script d'investigation : `scripts/investigate_refdata_fields.py`
- JSON complet : `data/investigation/refdata_investigation_253e4aab-56c2-4f0a-8233-cdfedd903012.json`
- Module refdata : `src/data/domain/refdata.py`
