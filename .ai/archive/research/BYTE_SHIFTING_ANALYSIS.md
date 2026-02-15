# Analyse du Byte Shifting - Match 58d09c44

## Contexte

L'utilisateur a confirmé manuellement dans le mode Theatre :
- **sixxt** tue **ObscureGuide710** à **8:32 (512s)** avec le **Commando**
- À **8:47 (527s)**, **sixxt** respawn (pas un kill)

## Problème Identifié

Les scripts d'extraction actuels supposent une structure fixe :
- Pattern kill: `[00 0x32 00]`
- Timestamp: 2 bytes à `offset + 3` (little-endian, centisecondes)
- Weapon ID: pattern `[00 00 WID_LO WID_HI]` dans une zone fixe après le timestamp
- Gamertag: dans une plage de 20-200 bytes **avant** le pattern kill

## Résultats de l'Analyse

### Timestamp 512s

J'ai trouvé plusieurs events autour de 512s, mais **aucun ne correspond exactement** à la structure attendue :

1. **Kill à 512.01s** (offset `0001D771`)
   - Gamertag proche: **JGtm** (à -46 bytes)
   - Weapon IDs trouvés: `0x2E00`, `0xE02E` (Sidekick)
   - ❌ Pas sixxt ni ObscureGuide710

2. **Kill à 512.08s** (offset `001BD665`)
   - Gamertag proche: **Rim7955** (à -46 bytes)
   - Weapon IDs trouvés: `0x2E00`, `0xE02E`, `0x6E00`
   - ❌ Pas sixxt ni ObscureGuide710

### Positions de sixxt dans le chunk

J'ai identifié **5 occurrences** du gamertag "sixxt" :
- `000F7E3C`
- `00160AC8`
- `00162603`
- `001BBAFC`
- `0022E3CF`

**Aucun kill pattern trouvé dans une zone de ±500 bytes autour de ces positions** avec un timestamp proche de 512s.

### Positions d'ObscureGuide710

J'ai identifié **12 occurrences** du gamertag "ObscureGuide710", mais aucune corrélée avec un kill à 512s.

## Hypothèses sur le Byte Shifting

### Hypothèse 1 : Offset de timestamp variable

Le timestamp pourrait être à un offset différent selon le contexte :
- Actuellement testé: offsets 3-11
- Peut-être nécessaire: offsets plus larges ou dépendants du contexte

### Hypothèse 2 : Structure différente pour certains events

Certains events (peut-être les kills avec power weapons comme le Commando) pourraient avoir une structure différente :
- Padding différent avant/après le pattern
- Weapon ID à un offset différent
- Gamertag à un emplacement différent (après le kill au lieu d'avant ?)

### Hypothèse 3 : Gamertag non directement associé

Le gamertag du killer/victim pourrait ne pas être dans la même structure que le kill event :
- Stocké séparément et référencé par un ID
- Dans un autre chunk ou section
- Encodé différemment

### Hypothèse 4 : Timestamp en millisecondes au lieu de centisecondes

Si le timestamp était en millisecondes :
- 512s = 512000 ms
- Bytes: `00 7D 00` (little-endian) ou `00 00 07 D0` (si 4 bytes)

Mais cela ne correspond pas aux patterns trouvés.

## Recommandations

### 1. Analyse manuelle avec hexdump

Pour le kill spécifique à 512s, il faudrait :
- Identifier manuellement la zone exacte dans le chunk
- Analyser la structure hexadécimale complète
- Identifier tous les patterns possibles

### 2. Comparaison avec d'autres matchs

Analyser d'autres matchs où sixxt fait des kills pour identifier des patterns communs.

### 3. Recherche du weapon ID du Commando

Si on peut identifier le weapon ID du Commando dans d'autres sources (API, autres matchs), on pourrait le chercher directement autour de 512s.

### 4. Analyse des chunks type 1 et type 2

Peut-être que les informations killer/victim sont dans d'autres types de chunks.

## Structure Actuelle Supposée

```
[Gamertag UTF-16 LE] (variable length)
[Padding ~24 bytes de 0x00]
[00 0x32 00] (pattern kill)
[TS_LO TS_HI] (2 bytes LE, centisecondes, offset +3)
[Padding ~8 bytes]
[00 00 WID_LO WID_HI] (weapon ID)
```

## Structure Possible Alternative

```
[Autres données]
[00 0x32 00] (pattern kill)
[TS_LO TS_HI] (offset variable ?)
[Gamertag UTF-16 LE] (après le timestamp ?)
[Weapon ID] (offset variable ?)
[Victim gamertag] (dans la même structure ?)
```

## Prochaines Étapes

1. ✅ Analyser le chunk avec différents offsets
2. ⏳ Identifier manuellement la structure exacte pour le kill à 512s
3. ⏳ Chercher le weapon ID du Commando dans d'autres sources
4. ⏳ Analyser d'autres matchs pour identifier des patterns communs
5. ⏳ Comparer avec les chunks type 1/type 2

## Fichiers Générés

- `scripts/analyze_with_offset_variations.py` - Teste différents offsets
- `scripts/analyze_chunk_with_hexdump.py` - Analyse détaillée avec hexdump
- `scripts/find_specific_kill.py` - Recherche d'un kill spécifique
- `scripts/analyze_byte_shifting.py` - Analyse autour de timestamps cibles
- `scripts/find_sixxt_kills_around_512.py` - Recherche autour des positions de sixxt
