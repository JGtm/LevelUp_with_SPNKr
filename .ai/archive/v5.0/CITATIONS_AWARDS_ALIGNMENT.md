# Analyse Citations H5G - Alignement avec Awards

**Date** : 2026-02-14  
**Objectif** : Identifier les citations non mappées qui peuvent utiliser `personal_score_awards`

---

## 📊 État actuel

| Métrique | Valeur |
|----------|--------|
| **Total citations H5G** | 159 |
| **Citations avec CUSTOM_RULES** | 8 |
| **Citations avec tracking JSON** | 0 (fichiers absents) |
| **Citations NON mappées** | **151** |

---

## ✅ Citations DÉJÀ mappées (CUSTOM_CITATION_RULES)

1. **Pilote** → Médaille 3169118333
2. **Écrasement** → Médaille 221693153  
3. **Assistant** → Stat `assists`
4. **Bulldozer** → Matches Assassin avec KD > 8
5. **Victoire au drapeau** → Victoires CTF
6. **Seul contre tous** → Victoires Firefight
7. **Victoire en Assassin** → Victoires Slayer
8. **Victoire en Bases** → Victoires Strongholds

---

## 🎯 ANALYSE : Citations alignables avec awards

### Catégorie 1 : Combat général ✅ HAUTE PRIORITÉ

Ces citations peuvent directement utiliser des awards de `personal_score_awards` :

| Citation | Description | Award suggéré | Catégorie award |
|----------|-------------|---------------|-----------------|
| **Assassin** | Assassinez des Spartans | `Assassination` | kill |
| **Tir à la tête** | Tuez d'un headshot | `Headshot Kill` | kill |
| **Pugilat** | Tuez au corps-à-corps | `Melee Kill` | kill |
| **Tueur de Spartans** | Éliminez des Spartans | `Kill` | kill |

**Implémentation** : Nouveau type `"award"` dans CUSTOM_CITATION_RULES

```python
"assassin": {
    "type": "award",
    "award_name": "Assassination",
}
```

---

### Catégorie 2 : Objectifs ✅ HAUTE PRIORITÉ

| Citation | Description | Award suggéré | Catégorie award |
|----------|-------------|---------------|-----------------|
| **Défenseur du drapeau** | Protégez le drapeau | `Flag Defense` | objective |
| **Je te tiens !** | Rapportez le drapeau | `Flag Return` | objective |
| **Sus au porteur du drapeau** | Tuez un porte-drapeau | `Flag Carrier Kill` | objective |
| **Maîtrise du drapeau** | Prenez une base | `Zone Capture` | objective |
| **Partie prenante** | Défendez une base | `Zone Defense` | objective |

**Implémentation** : Même type `"award"` avec noms explicites

---

### Catégorie 3 : Véhicules ✅ PRIORITÉ MOYENNE

| Citation | Description | Award suggéré | Catégorie award |
|----------|-------------|---------------|-----------------|
| **Destructeur de banshees** | Détruisez des banshees | `Vehicle Destruction` | vehicle |
| **Destructeur de ghosts** | Détruisez des ghosts | `Vehicle Destruction` | vehicle |
| **Destructeur de mantis** | Détruisez des mantis | `Vehicle Destruction` | vehicle |
| **Destructeur de scorpions** | Détruisez des scorpions | `Vehicle Destruction` | vehicle |
| **Destructeur de warthogs** | Détruisez des warthogs | `Vehicle Destruction` | vehicle |
| **Destructeur de wasps** | Détruisez des wasps | `Vehicle Destruction` | vehicle |

**Problème** : L'award `Vehicle Destruction` ne distingue pas le type de véhicule.  
**Solution** : Peut regrouper toutes ces citations sous une seule "Destructeur de véhicules"

---

### Catégorie 4 : Assists ✅ HAUTE PRIORITÉ

| Citation | Description | Award suggéré | Catégorie award |
|----------|-------------|---------------|-----------------|
| **Assistant** | Médailles d'assistance | `Assist` | assist |
| **Protecteur** | Protégez un équipier | `Assist` (approx.) | assist |

**Note** : "Assistant" est déjà dans CUSTOM_RULES, mais pourrait migrer vers le système award.

---

## ❌ Citations NON alignables avec awards

Ces citations sont **trop spécifiques** et nécessitent d'autres sources de données :

### Armes spécifiques (52 citations)

- Artilleur de banshee, Artilleur de ghost, etc. → Nécessite `damage_data` par arme/véhicule
- Carabine, DMR, Fusil d'assaut, etc. → Nécessite `damage_data` par arme
- Grenade à fragmentation, Grenade à plasma, etc. → Nécessite `damage_data` par grenade

**Raison** : `personal_score_awards` ne décompose pas les kills par arme.

### Ennemis PvE (10 citations)

- Tueur d'Élites, Tueur de Grognards, etc. → Seulement en Firefight
- Chasseur, Chasse au gros gibier → Boss Warzone (non applicable Halo Infinite)

**Raison** : Données PvE non disponibles en multijoueur Arena.

### Citations complexes (15 citations)

- Bulldozer → Déjà dans CUSTOM_RULES (KD > 8)
- Annexion forcée → 3 captures sans mourir (nécessite séquençage)
- Imparable → Survivre en Élimination (nécessite logique match)
- Carnage de Spartans → Multikills séquentiels (nécessite medals)

**Raison** : Logique complexe, déjà gérée par CUSTOM_RULES ou médailles.

---

## 📈 Résumé par priorité

### 🔴 Haute priorité (17 citations)

**Implémentables immédiatement avec awards** :

1. Assassin (Assassination)
2. Tir à la tête (Headshot Kill)
3. Pugilat (Melee Kill)
4. Tueur de Spartans (Kill)
5. Défenseur du drapeau (Flag Defense)
6. Je te tiens ! (Flag Return)
7. Sus au porteur du drapeau (Flag Carrier Kill)
8. Maîtrise du drapeau (Zone Capture)
9. Partie prenante (Zone Defense)
10. Protecteur (Assist)

**Impact** : +10 citations avec effort minimal (nouveau type `"award"`)

### 🟡 Priorité moyenne (6 citations)

**Regroupables sous awards génériques** :

1. Destructeur de banshees → Vehicle Destruction
2. Destructeur de ghosts → Vehicle Destruction
3. Destructeur de mantis → Vehicle Destruction
4. Destructeur de scorpions → Vehicle Destruction
5. Destructeur de warthogs → Vehicle Destruction
6. Destructeur de wasps → Vehicle Destruction

**Option** : Créer une seule citation "Destructeur de véhicules" au lieu de 6.

### ⚪ Basse priorité (128 citations)

**Non alignables** :

- 52 citations armes spécifiques → Nécessite damage_data
- 10 citations PvE → Non applicable mode Arena
- 15 citations complexes → Déjà en CUSTOM_RULES ou médailles
- 51 autres → Nécessitent médailles spécifiques ou stats indisponibles

---

## 💡 Recommandations

### 1. Implémenter le type `"award"` 

Ajouter support dans `_compute_custom_citation_value()` :

```python
def _compute_custom_citation_value(
    rule: dict[str, Any],
    df: pl.DataFrame | None,
    counts_by_medal: dict[int, int] | None,
    stats_totals: dict[str, int] | None,
    awards_by_name: dict[str, int] | None = None,  # ← NOUVEAU
) -> int:
    rule_type = rule.get("type")
    
    # ... code existant ...
    
    # NOUVEAU TYPE
    if rule_type == "award":
        award_name = rule.get("award_name")
        if award_name and awards_by_name:
            return awards_by_name.get(award_name, 0)
        return 0
```

### 2. Ajouter 10 citations haute priorité

```python
CUSTOM_CITATION_RULES.update({
    "assassin": {
        "type": "award",
        "award_name": "Assassination",
    },
    "tir a la tete": {
        "type": "award",
        "award_name": "Headshot Kill",
    },
    "pugilat": {
        "type": "award",
        "award_name": "Melee Kill",
    },
    "tueur de spartans": {
        "type": "award",
        "award_name": "Kill",
    },
    "defenseur du drapeau": {
        "type": "award",
        "award_name": "Flag Defense",
    },
    "je te tiens": {
        "type": "award",
        "award_name": "Flag Return",
    },
    "sus au porteur du drapeau": {
        "type": "award",
        "award_name": "Flag Carrier Kill",
    },
    "maitrise du drapeau": {
        "type": "award",
        "award_name": "Zone Capture",
    },
    "partie prenante": {
        "type": "award",
        "award_name": "Zone Defense",
    },
    "protecteur": {
        "type": "award",
        "award_name": "Assist",
    },
})
```

### 3. Charger les awards dans render_h5g_commendations_section()

Ajouter dans `src/ui/pages/citations.py` :

```python
# Agréger awards depuis personal_score_awards
awards_by_name = {}
if df_filtered is not None and "award_name" in df_filtered.columns:
    awards_agg = (
        df_filtered.group_by("award_name")
        .agg(pl.col("award_count").sum().alias("total"))
    )
    awards_by_name = dict(zip(awards_agg["award_name"], awards_agg["total"]))
```

### 4. Documenter les award_name disponibles

Créer `docs/AWARDS_CATALOG.md` listant tous les `award_name` présents dans la DB.

---

## 🎯 Prochaines étapes

1. ✅ **Analyser** quelles citations sont alignables → FAIT
2. ⏳ **Implémenter** le type `"award"` dans commendations.py
3. ⏳ **Ajouter** les 10 citations haute priorité
4. ⏳ **Tester** avec données réelles d'un joueur
5. ⏳ **Documenter** le catalogue des awards disponibles

---

## 📝 Notes techniques

### personal_score_awards : Colonnes disponibles

- `match_id` : ID du match
- `xuid` : XUID du joueur
- `award_name` : Nom de l'award (ex: "Kill", "Headshot Kill")
- `award_category` : Catégorie (kill, assist, objective, vehicle, penalty)
- `award_count` : Nombre d'occurrences
- `award_score` : Points de score

### Limitation actuelle

`personal_score_awards` **ne détaille PAS** :
- L'arme utilisée pour un kill
- Le véhicule utilisé pour un kill
- Le type de véhicule détruit

**Conclusion** : Les 52 citations par arme/véhicule spécifique ne peuvent pas être calculées avec awards seuls.

---

**Gain attendu** : +10 à +16 citations mappées (de 8 à 18-24) avec implémentation type `"award"`
