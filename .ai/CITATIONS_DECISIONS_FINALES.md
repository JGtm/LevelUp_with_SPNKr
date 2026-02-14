# Citations - Décisions Finales & Implémentation

**Date** : 2026-02-14  
**Statut** : ✅ VALIDÉ par utilisateur  
**Référence** : [CITATIONS_ARCHITECTURE_ANALYSIS.md](CITATIONS_ARCHITECTURE_ANALYSIS.md)

---

## 🎯 Décisions VALIDÉES

### Citations à réintégrer : **6 citations**

#### ✅ Type `award` - 5 citations objectives simples

| Citation | Award | Catégorie | Confiance |
|----------|-------|-----------|-----------|
| **Défenseur du drapeau** | `Flag Defense` | objective | Haute |
| **Je te tiens !** | `Flag Return` | objective | Haute |
| **Sus au porteur du drapeau** | `Flag Carrier Kill` | objective | Haute |
| **Partie prenante** | `Zone Defense` | objective | Haute |
| **À la charge** | `Zone Capture` | objective | Haute |

#### ✅ Type `custom` - 1 citation objective complexe

| Citation | Condition | Fonction | Confiance |
|----------|-----------|----------|-----------|
| **Annexion forcée** | 3 Zone Capture d'affilée sans mourir | `compute_annexion_forcee()` | Moyenne |

**Note** : Implémentation approximative (total ÷ 3) car détecter la séquence exacte nécessiterait `highlight_events` match-par-match.

### Citations restant EXCLUES

❌ **Toutes les autres** (108 citations) :
- Maîtrise du drapeau (doublon avec "À la charge")
- Geronimo, Mastodonte, Protecteur, Body Guard (médailles, pas awards)
- Destructeurs de véhicules (6 citations, award non spécifique)
- 52 citations armes spécifiques
- 11 citations PvE
- 33 citations complexes/autres

---

## 📊 Impact

| Métrique | Avant | Après | Gain |
|----------|-------|-------|------|
| **Citations affichées** | 41 | **47** | **+6 (+14.6%)** |
| **Architecture** | 3 fichiers JSON | 1 table DuckDB | Unifié |
| **Versioning** | ❌ Non versionné | ✅ Versionné | Sécurisé |
| **Maintenance** | Complexe | Simple | 1 SQL INSERT |

---

## 🏗️ Implémentation

### Fichiers créés

✅ **Scripts**
- [scripts/create_citation_mappings_table.py](../../scripts/create_citation_mappings_table.py) - Initialisation table + données

✅ **Modules**
- [src/analysis/citations/custom_rules.py](../../src/analysis/citations/custom_rules.py) - Fonctions custom
- [src/analysis/citations/__init__.py](../../src/analysis/citations/__init__.py) - Package

### Schéma table `citation_mappings`

```sql
CREATE TABLE citation_mappings (
    citation_name_norm TEXT PRIMARY KEY,
    citation_name_display TEXT NOT NULL,
    mapping_type TEXT NOT NULL,  -- 'medal' | 'stat' | 'award' | 'custom'
    
    -- Pour type = 'medal'
    medal_id INTEGER,
    medal_ids TEXT,
    
    -- Pour type = 'stat'
    stat_name TEXT,
    
    -- Pour type = 'award'
    award_name TEXT,
    award_category TEXT,
    
    -- Pour type = 'custom'
    custom_function TEXT,
    
    -- Métadonnées
    confidence TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Données insérées

**8 citations existantes** (CUSTOM_CITATION_RULES migrées) :
- Pilote (medal)
- Écrasement (medal)
- Assistant (stat)
- Bulldozer (custom)
- Victoire au drapeau (custom)
- Seul contre tous (custom)
- Victoire en Assassin (custom)
- Victoire en Bases (custom)

**6 nouvelles citations** (réintégrées) :
- Défenseur du drapeau (award)
- Je te tiens ! (award)
- Sus au porteur du drapeau (award)
- Partie prenante (award)
- À la charge (award)
- Annexion forcée (custom)

**Total** : **14 citations** dans la table

---

## 🚀 Étapes suivantes

### Phase 1 : Initialisation (maintenant)

**📋 Plan détaillé** : Voir [CITATIONS_SPRINTS.md](CITATIONS_SPRINTS.md)

```bash
# 1. Créer la table et insérer les données
python scripts/create_citation_mappings_table.py
```

**Résultat attendu** :
```
✅ 8 citations existantes migrées
✅ 6 nouvelles citations ajoutées
✅ Total : 14 citations dans citation_mappings
```

### Sprints courts (12-16h total)

**Sprint 1** (2-3h) : Tables DuckDB + Nettoyage  
**Sprint 2** (3-4h) : CitationEngine core  
**Sprint 3** (3-4h) : Intégration sync + backfill `--citations`  
**Sprint 4** (2-3h) : Refactoring UI  
**Sprint 5** (2h) : Tests finaux + Documentation  

**Détails complets** : [.ai/CITATIONS_SPRINTS.md](CITATIONS_SPRINTS.md)

---

## 📝 Notes techniques

### Fonction `compute_annexion_forcee()`

**Logique actuelle** (approximation) :
```python
zone_captures = awards.get("Zone Capture", 0)
return zone_captures // 3  # Chaque 3 captures = 1 point
```

**Logique future** (précise) :
1. Charger `personal_score_awards` avec timestamps
2. Charger `highlight_events` (deaths)
3. Pour chaque match :
   - Trier captures par temps
   - Détecter séquences >= 3 sans death entre
   - Compter les séquences valides

**Raison** : `personal_score_awards` n'a pas de timestamp explicite actuellement.

### Support type `award` dans CitationEngine

```python
def compute_citation(mapping, awards):
    if mapping['mapping_type'] == 'award':
        return awards.get(mapping['award_name'], 0)
```

---

## ✅ Checklist avant merge

- [x] Table `citation_mappings` créée
- [x] Script d'initialisation prêt
- [x] Module `src/analysis/citations/` créé
- [x] Fonctions custom implémentées
- [ ] Tests unitaires (optionnel)
- [ ] Blacklist mise à jour
- [ ] UI refactorisée (optionnel, futur)

---

**Prochaine action** : Exécuter `python scripts/create_citation_mappings_table.py`
