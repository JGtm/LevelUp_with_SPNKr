# Investigation : Kill Feed et Weapon IDs

> Date : 2026-02-02
> Statut : Nouvelle piste exploratoire
> Lien : BINARY_CHUNK_ANALYSIS_V2_PLAN.md

## Contexte

Le **kill feed** dans Halo Infinite affiche visuellement :
- ✅ Icône de l'arme utilisée
- ✅ Nom du killer
- ✅ Nom de la victime
- ✅ Type de kill (headshot, melee, etc.)

**Hypothèse** : Si le kill feed peut afficher l'arme, les données doivent être disponibles quelque part !

## Pistes d'investigation

### 1. Assets d'icônes d'armes

Les icônes d'armes sont probablement des **assets** téléchargés depuis les serveurs 343i.

**Questions** :
- Où sont stockées les icônes d'armes ?
- Y a-t-il un mapping `weapon_id → icon_path` ?
- Les assets sont-ils accessibles via l'API Discovery UGC ?

**Endpoints potentiels** :
```
/discovery/ugc/weapons/{asset_id}/{version_id}
/discovery/ugc/weapon_icons/{asset_id}/{version_id}
```

### 2. Police d'icônes (Icon Font)

Alternative : Les icônes pourraient être dans une **police spéciale** (comme FontAwesome).

**Questions** :
- Y a-t-il une police d'icônes Halo Infinite ?
- Les codes de caractères correspondent-ils aux weapon IDs ?
- Où est stockée cette police ?

### 3. Kill Feed dans les Film Chunks

Le kill feed pourrait être généré depuis les mêmes données que les highlight events.

**Hypothèse** : Les bytes non documentés (position 72+) pourraient contenir un **weapon icon ID** plutôt qu'un weapon ID brut.

**Test** :
- Extraire tous les events kill
- Analyser les patterns dans les extra bytes
- Chercher des corrélations avec les icônes visibles dans le kill feed

### 4. API Match Stats - Kill Feed Data

L'API pourrait exposer les données du kill feed dans un format non documenté.

**Endpoints à explorer** :
```
/hi/matches/{matchId}/stats
/hi/matches/{matchId}/killfeed  (hypothétique)
/hi/matches/{matchId}/events    (hypothétique)
```

### 5. Theatre Mode - Kill Feed Extraction

Le Theatre Mode doit avoir accès aux données du kill feed pour les afficher.

**Questions** :
- Comment le Theatre Mode génère-t-il le kill feed ?
- Y a-t-il un endpoint API pour le Theatre Mode ?
- Peut-on extraire ces données depuis les film chunks type 1 (bootstrap) ?

## Plan d'action

### Phase 1 : Exploration Assets

1. **Lister les assets disponibles** via Discovery UGC
2. **Chercher des assets de type "Weapon" ou "WeaponIcon"**
3. **Télécharger et analyser** les métadonnées

### Phase 2 : Analyse Kill Feed visuel

1. **Capturer des screenshots** du kill feed pendant un match
2. **Identifier les icônes d'armes** visibles
3. **Corréler avec les kills** extraits des highlight events
4. **Créer un mapping** icône → arme

### Phase 3 : Extraction depuis Film Chunks

1. **Analyser les extra bytes** (position 72+) pour tous les kills
2. **Chercher des patterns** qui pourraient être des icon IDs
3. **Comparer avec les icônes** visibles dans le kill feed

### Phase 4 : Exploration API non documentée

1. **Inspecter les réponses API** complètes (pas seulement les champs documentés)
2. **Chercher des champs cachés** contenant weapon/icon IDs
3. **Tester des endpoints hypothétiques**

## Outils créés

### Scripts disponibles

1. **`scripts/explore_killfeed_weapons.py`** (amélioré)
   - Exploration Discovery UGC
   - Analyse des events kill
   - Exploration film chunks

2. **`scripts/investigate_killfeed_weapons.py`** (nouveau - complet)
   - Phase 1 : Exploration Assets Discovery UGC
   - Phase 2 : Analyse Kill Feed visuel
   - Phase 3 : Extraction Film Chunks (extra bytes)
   - Phase 4 : Exploration API non documentée
   - Phase 5 : Theatre Mode extraction
   - Sauvegarde des résultats en JSON

### Usage

```bash
# Exploration complète (toutes les phases)
python scripts/investigate_killfeed_weapons.py --match-id <ID> --phase all --output results.json

# Phase spécifique
python scripts/investigate_killfeed_weapons.py --match-id <ID> --phase 1

# Exploration assets uniquement
python scripts/investigate_killfeed_weapons.py --explore-assets
```

## Outils nécessaires (à créer)

- Script pour capturer/analyser le kill feed visuel (screenshots)
- Script pour corréler icônes avec kills extraits
- Documentation des assets disponibles

## Références

- [Den Delimarsky - Film Files](https://den.dev/blog/extracting-stats-film-files-halo-infinite/)
- [SPNKr Documentation](https://github.com/OpenSpartan/grunt)
- [Halo Infinite API Discovery](https://github.com/OpenSpartan/grunt/blob/main/docs/discovery.md)
