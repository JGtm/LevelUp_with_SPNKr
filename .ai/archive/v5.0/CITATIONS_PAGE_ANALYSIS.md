# Analyse de la page Citations - Fonctionnement complet

**Date** : 2026-02-14

---

## 🎯 Flux complet de la page Citations

### 1. Chargement des données

```
render_citations_page()
  ↓
  Agrège médailles pour matchs filtrés → counts_by_medal
  Agrège médailles pour TOUS matchs → counts_by_medal_full
  Agrège stats (kills, assists, etc.) → stats_totals / stats_totals_full
  ↓
render_h5g_commendations_section()
```

### 2. Chargement des citations et règles

```python
# Citations H5G (159 au total)
data = load_h5g_commendations_json("data/wiki/halo5_commendations_fr.json")
items = data.get("items")

# Règles de tracking (JSON auto-générés)
tracking = load_h5g_commendations_tracking_rules(
    "out/commendations_mapping_assumed_old.json",
    "out/commendations_mapping_unmatched_old.json"
)

# Règles hardcodées
CUSTOM_CITATION_RULES = {
    "pilote": {...},
    "ecrasement": {...},
    # ... 8 règles
}
```

### 3. Filtrage des citations affichées

**IMPORTANT** : Seules les citations avec une règle de calcul sont affichées !

```python
def _has_tracking_rule(it: dict[str, Any]) -> bool:
    norm_name = _normalize_name(str(it.get("name") or "").strip())
    return norm_name in tracking or norm_name in CUSTOM_CITATION_RULES

items = [it for it in items if _has_tracking_rule(it)]
```

**Conclusion** : Le nombre de citations affichées = `len(tracking) + len(CUSTOM_CITATION_RULES)`

---

## 📊 Calcul de la valeur d'une citation

### Ordre de priorité

Pour chaque citation affichée, on calcule sa valeur dans cet ordre :

#### 1️⃣ CUSTOM_CITATION_RULES (priorité absolue)

```python
if norm_name in CUSTOM_CITATION_RULES:
    custom_rule = CUSTOM_CITATION_RULES[norm_name]
    current = _compute_custom_citation_value(
        custom_rule, df, counts_by_medal, stats_totals
    )
```

**Types supportés** :
- `"medal"` : compte une médaille spécifique
- `"stat"` : somme une stat (kills, assists, etc.)
- `"wins_mode"` : compte les victoires dans un mode
- `"matches_mode_kd"` : partie avec KD > seuil

#### 2️⃣ Tracking JSON - Liste de médailles

```python
elif isinstance(rule.get("medal_ids"), list):
    total = sum(counts_by_medal.get(mid, 0) for mid in rule["medal_ids"])
    current = total
```

**Usage** : Citations qui nécessitent plusieurs médailles (ex: "Obtenir BXR, Combo noob, ou Grenade headshot")

#### 3️⃣ Tracking JSON - Médaille unique

```python
elif rule.get("medal_id") is not None:
    current = counts_by_medal.get(rule["medal_id"], 0)
```

**Usage** : Citation = 1 médaille (cas le plus fréquent)

#### 4️⃣ Tracking JSON - Stat simple

```python
elif isinstance(rule.get("stat"), str):
    stat_key = rule["stat"]
    current = stats_totals.get(stat_key, 0)
```

**Usage** : Citations basées sur les stats totales (kills, assists, headshot_kills)

---

## 🗂️ Format des fichiers de tracking JSON

### Structure attendue

```json
{
  "items": [
    {
      "name": "Nom de la citation",
      "notes": "COMPTER MÉDAILLES: 12345, 67890",  // ← Can override
      "chosen": {
        "type": "medal",
        "name_id": 12345
      },
      "candidates": [
        {"type": "medal", "name_id": 12345},
        {"type": "stat", "stat": "kills", "expression": "kills = sum(kills)"}
      ]
    }
  ]
}
```

### Parsing des notes

Le système parse les `notes` pour extraire des règles spéciales :

```python
def _medal_ids_from_notes(notes: str) -> list[int]:
    """Parse 'COMPTER MÉDAILLES: 123, 456, 789'"""
    # Extrait les IDs de médailles depuis les notes
    
def _is_dropped_by_notes(notes: str) -> bool:
    """Vérifie si 'IGNORE' ou 'SKIP' dans les notes"""
```

### Logique de chargement

1. **Charger** `assumed_old.json` + `unmatched_old.json`
2. **Parser notes** : Si "COMPTER MÉDAILLES: X, Y" → créer `medal_ids: [X, Y]`
3. **Sinon, prendre chosen/candidates** :
   - `chosen.type = "medal"` → `medal_id: chosen.name_id`
   - `chosen.type = "stat"` → `stat: chosen.stat`
4. **Merger** toutes les règles dans un dict `{norm_name: rule}`

---

## 🎨 Affichage d'une citation

### Calcul de la progression

```python
level_label, counter_label, is_master, progress_ratio = _compute_mastery_display(
    current, tiers
)
```

**Tiers** : Chaque citation a 5 niveaux (tiers) avec des seuils :
- Tier 1 : 5 kills
- Tier 2 : 10 kills
- Tier 3 : 25 kills
- Tier 4 : 50 kills
- Tier 5 (Master) : 100 kills

**Progress ratio** : Pourcentage de progression dans le tier actuel (pour l'anneau)

### Rendu HTML

```html
<div class="os-citation-ring" style="--p: 0.75; --img: url(...)">
  <!-- Anneau de progression avec image -->
</div>
<div class="os-citation-name">Nom de la citation</div>
<div class="os-citation-level">Niveau III</div>
<div class="os-citation-counter">
  25/50
  <span style="color: #4CAF50">+10</span>  <!-- Delta si filtré -->
</div>
```

---

## 🔍 Découvertes clés

### 1. Pourquoi plus de 8 citations sont affichées

Tu vois plus de 8 citations parce que :
- Les fichiers `out/commendations_mapping_*.json` existent
- Ils contiennent des règles pour de nombreuses citations
- Ces règles sont chargées automatiquement au démarrage

### 2. Format du tracking JSON

Les fichiers JSON contiennent probablement des correspondances :
- Citation → medal_id (pour médailles simples)
- Citation → medal_ids (pour médailles multiples)
- Citation → stat (pour stats agrégées)

### 3. Système modulaire bien conçu

- **Niveau 1** : CUSTOM_RULES (complexe, hardcodé)
- **Niveau 2** : Tracking JSON (auto-généré, simple)
- **Séparation claire** : Logique custom vs mapping auto

---

## 📋 Pour vérifier l'état réel

### Commandes à exécuter

```bash
# 1. Vérifier existence des fichiers
ls -la out/commendations_mapping*.json

# 2. Compter les règles dans chaque fichier
jq '.items | length' out/commendations_mapping_assumed_old.json
jq '.items | length' out/commendations_mapping_unmatched_old.json

# 3. Voir quelques exemples
jq '.items[:5]' out/commendations_mapping_assumed_old.json

# 4. Compter combien de citations ont un medal_id
jq '.items | map(select(.chosen.type == "medal")) | length' out/commendations_mapping_assumed_old.json
```

### Dans l'app

Compter dans l'interface :
1. Ouvrir l'onglet **Citations**
2. Sélectionner catégorie **(toutes)**
3. Regarder le nombre total de citations affichées

---

## 🎯 Prochaines étapes recommandées

### Court terme
1. **Vérifier** : Lister le contenu de `out/` pour confirmer les fichiers
2. **Analyser** : Extraire 10-20 exemples de mappings du JSON
3. **Documenter** : Créer un inventaire des citations déjà mappées

### Moyen terme
1. **Audit** : Comparer `tracking` vs `CUSTOM_RULES` (doublons ?)
2. **Compléter** : Ajouter les 15-20 citations prioritaires manquantes
3. **Centraliser** : Migrer vers une architecture unifiée

---

## 💡 Observations importantes

### Points forts du système actuel
- ✅ Séparation CUSTOM vs auto-mapping
- ✅ Support médailles multiples (medal_ids)
- ✅ Affichage de deltas (filtre vs tous matchs)
- ✅ Progression par tiers
- ✅ Cache Streamlit pour performance

### Points à améliorer
- ⚠️ Fichiers JSON dans `out/` (pas versionné ?)
- ⚠️ Pas de documentation sur le format
- ⚠️ Logique de parsing dans plusieurs fonctions
- ⚠️ Difficile de savoir quelles citations sont mappées sans lire le code

### Proposition d'amélioration
- 📝 Créer `docs/CITATIONS_MAPPING.md` avec format détaillé
- 🗂️ Déplacer les JSONs vers `data/citations/` (versionné)
- 🔧 Script pour lister/vérifier les mappings existants
- 📊 Interface admin pour gérer les mappings (futur)
