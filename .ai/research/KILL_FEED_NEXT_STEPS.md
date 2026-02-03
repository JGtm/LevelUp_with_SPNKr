# Prochaines Étapes Concrètes - Investigation Kill Feed

> **Date**: 2026-02-03
> **Statut**: 🟢 Prêt à exécuter
> **Prérequis**: Environnement Python avec dépendances installées

---

## 🎯 Objectif

Identifier plus de weapon IDs et leurs icônes depuis le kill feed de Halo Infinite.

**État actuel** : 2 weapon IDs identifiés (Sidekick, MA40 AR) depuis les chunks type 3.

---

## ✅ Ce qui a été fait

1. ✅ Scripts d'investigation créés (`investigate_killfeed_weapons.py`, `investigate_killfeed_simple.py`)
2. ✅ Script utilitaire pour obtenir des match IDs (`get_match_id.py`)
3. ✅ Documentation complète créée
4. ✅ Weapon IDs confirmés : `0xE02E` (Sidekick), `0x7017` (MA40 AR)

---

## 🚀 Actions Immédiates à Exécuter

### Étape 1 : Préparer l'environnement

```bash
# Installer les dépendances
pip install duckdb polars pydantic streamlit spnkr aiohttp pandas

# Vérifier les tokens API
cat .env.local | grep SPNKR
```

### Étape 2 : Obtenir des match IDs

```bash
# Lister les matchs disponibles
python scripts/get_match_id.py --gamertag JGtm --limit 10

# Ou utiliser un match ID connu
MATCH_ID="7f1bbf06-d54d-4434-ad80-923fcabe8b1b"
```

### Étape 3 : Exécuter l'investigation Phase 1 (Assets)

```bash
python scripts/investigate_killfeed_weapons.py \
    --phase 1 \
    --output .ai/research/results_phase1.json
```

**Résultats attendus** :
- Liste des méthodes Discovery UGC disponibles
- Types d'assets hypothétiques identifiés
- Plan pour tester les types "Weapons", "WeaponIcons", etc.

---

### Étape 4 : Exécuter l'investigation Phase 2 (Events)

```bash
python scripts/investigate_killfeed_weapons.py \
    --match-id $MATCH_ID \
    --phase 2 \
    --output .ai/research/results_phase2.json
```

**Résultats attendus** :
- Structure complète des highlight events
- Champs suspects dans raw_json
- Corrélation avec weapon IDs connus

---

### Étape 5 : Extraire plus de weapon IDs (Phase 3)

```bash
# Extraire les events depuis les chunks type 3
python scripts/extract_events_v3.py \
    --match-id $MATCH_ID \
    --output .ai/research/events_$MATCH_ID.json

# Analyser les weapon IDs trouvés
python scripts/aggregate_weapon_ids.py \
    --input .ai/research/events_*.json \
    --output .ai/research/weapon_ids_found.json
```

**Résultats attendus** :
- Nouveaux weapon IDs identifiés
- Patterns dans les extra bytes
- Mapping weapon_id → nom d'arme

---

### Étape 6 : Analyser plusieurs matchs

```bash
# Créer un script batch pour analyser plusieurs matchs
for match_id in $(python scripts/get_match_id.py --gamertag JGtm --limit 20 | grep -o '[a-f0-9-]\{36\}'); do
    echo "Analyse match $match_id..."
    python scripts/extract_events_v3.py --match-id $match_id --output "events_${match_id}.json"
done

# Agrégation de tous les weapon IDs
python scripts/aggregate_weapon_ids.py \
    --input events_*.json \
    --output all_weapon_ids.json
```

**Résultats attendus** :
- Liste complète des weapon IDs utilisés
- Fréquence d'utilisation par arme
- Armes rares identifiées

---

## 🔍 Tests Spécifiques à Effectuer

### Test 1 : Discovery UGC - Types hypothétiques

```python
# Tester si les types "Weapons", "WeaponIcons" existent
async with SPNKrAPIClient() as client:
    # Essayer avec un weapon ID connu
    weapon_id = 0xE02E  # Sidekick
    
    # Tester différents formats d'asset_id
    for asset_type in ["Weapons", "WeaponIcons", "WeaponDefinitions"]:
        result = await client.get_asset(asset_type, str(weapon_id), "1")
        if result:
            print(f"✅ {asset_type} existe pour weapon_id {weapon_id}")
            print(json.dumps(result, indent=2))
```

### Test 2 : Corrélation visuelle kill feed

1. **Capturer des screenshots** du kill feed pendant un match
2. **Identifier les icônes** visibles pour chaque kill
3. **Extraire les weapon IDs** depuis les chunks pour les mêmes kills
4. **Créer un mapping** icône → weapon_id

**Script à créer** :
```python
# scripts/correlate_killfeed_visual.py
# - Prend en entrée : screenshots + events extraits
# - Sortie : mapping icon_id → weapon_id
```

### Test 3 : Analyse des extra bytes

```python
# Analyser les bytes 72+ pour trouver des patterns icon IDs
# Comparer avec les weapon IDs connus
# Chercher des corrélations avec les icônes visibles
```

---

## 📊 Résultats Attendus

### Weapon IDs à identifier

| Arme | Weapon ID estimé | Source |
|------|------------------|--------|
| BR75 | ? | Matchs Ranked |
| Sniper | ? | Matchs avec médaille "Snipe" |
| Rocket Launcher | ? | Power weapon kills |
| Energy Sword | ? | Melee kills spécifiques |
| Gravity Hammer | ? | Matchs avec marteau |
| Cindershot | ? | Matchs avec armes spéciales |

### Mapping Icon ID → Weapon ID

Si les icon IDs sont différents des weapon IDs :
- Identifier le pattern de conversion
- Créer une table de mapping
- Documenter dans `src/data/weapon_ids.py`

---

## 📝 Documentation à Mettre à Jour

Après chaque découverte :

1. **Mettre à jour `src/data/weapon_ids.py`** :
   ```python
   WEAPON_IDS: dict[int, str] = {
       0xE02E: "Sidekick",
       0x7017: "MA40 AR",
       # Ajouter les nouveaux IDs trouvés
   }
   ```

2. **Documenter dans `.ai/research/KILL_FEED_INVESTIGATION_STATUS.md`**

3. **Créer un rapport de découvertes** dans `.ai/research/`

---

## 🐛 Dépannage

### Erreur : "No module named 'pandas'"

```bash
pip install pandas
```

### Erreur : "Tokens manquants"

Vérifier `.env.local` :
```bash
SPNKR_SPARTAN_TOKEN=...
SPNKR_CLEARANCE_TOKEN=...
```

### Erreur : "Base de données non trouvée"

Synchroniser d'abord :
```bash
python scripts/sync.py --gamertag JGtm
```

---

## ✅ Checklist de Completion

- [ ] Environnement Python configuré avec dépendances
- [ ] Tokens API configurés
- [ ] Phase 1 exécutée (Assets Discovery UGC)
- [ ] Phase 2 exécutée (Analyse events)
- [ ] Phase 3 exécutée (Extraction weapon IDs)
- [ ] Plusieurs matchs analysés
- [ ] Nouveaux weapon IDs identifiés
- [ ] Mapping icon_id → weapon_id créé (si applicable)
- [ ] Documentation mise à jour
- [ ] `src/data/weapon_ids.py` enrichi

---

**Dernière mise à jour** : 2026-02-03
