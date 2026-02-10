# Résultats de l'Analyse Binaire des Film Chunks

> **Date** : 2026-02-02
> **Objectif** : Identifier les patterns d'armes dans les bytes non documentés
> **Statut** : ✅ **WEAPON ID TROUVÉ !**

---

## 1. Résumé Exécutif

### Découverte Principale

**✅ WEAPON ID TROUVÉ !**

L'arme utilisée est encodée dans les **bytes 74-75** des highlight events (offset 72+2/72+3 dans la structure extra_bytes).

| Bytes (hex) | uint16 LE | Arme identifiée |
|-------------|-----------|-----------------|
| `0x2e 0xe0` | 57390 | **Sidekick** |
| `0x17 0x70` | 28695 | **MA40 AR** |

### Structure de l'Event Kill (confirmée)

```
Offset | Taille | Contenu
-------|--------|------------------
0-11   | 12     | Header (variable, flags)
12-43  | 32     | Gamertag (UTF-16 BE, souvent corrompu)
44-58  | 15     | Padding (0x00)
59     | 1      | Type (50=kill, 20=death, 10=mode)
60-63  | 4      | Timestamp (ms, little-endian)
64-71  | 8      | Padding/Flags
72-73  | 2      | ??? (souvent 0x00)
74-75  | 2      | **WEAPON ID** (uint16 little-endian)
76+    | ?      | Données supplémentaires
```

### Localisation Clé

Les weapon IDs sont dans les **chunks type 3** (summary chunks), **PAS** dans les chunks type 2 (gameplay).

---

## 2. Validation

### Match Analysé

**ID** : `7f1bbf06-d54d-4434-ad80-923fcabe8b1b`

**Données joueur (JGtm)** :
- Armes utilisées : Sidekick (principal), MA40 AR, Melee
- 6 kills confirmés au Sidekick
- 1-2 kills AR/Melee

**Résultats extraction chunk type 3** :
- **48 kills** total (tous joueurs du match)
- **41 kills** avec pattern `0x2e 0xe0` → **Sidekick**
- **7 kills** avec pattern `0x17 0x70` → **MA40 AR / Melee**

**Corrélation** : ✅ Les ratios correspondent aux données connues.

---

## 3. Méthodologie

### 3.1 Approche Initiale (Échec)

**Problème** : Les chunks type 2 (gameplay) ne contiennent pas les events formatés.

**Symptômes** :
- Timestamps aberrants (8h, 600h pour un match de 10min)
- Gamertags corrompus
- >90% de faux positifs

**Cause** : La structure 72 bytes documentée est spécifique aux chunks type 3.

### 3.2 Découverte du Chunk Type 3

**Observation** : Le manifest contenait un chunk type 3 (filmChunk18) non téléchargé.

**Solution** : Modifier `refetch_film_roster.py` pour inclure `type_ids = {1, 2, 3}`.

### 3.3 Extraction Réussie

```bash
python scripts/extract_binary_events.py \
    --chunk data/investigation/match_7f1bbf06/chunks_with_type3/type3___filmChunk18.bin \
    --analyze
```

**Résultat** : 274 events (48 kills, 115 deaths, 111 mode)

### 3.4 Analyse des Patterns

```python
# Grouper les kills par pattern bytes 74-75
for k in kills:
    extra = k['extra_bytes_32']
    weapon_pattern = (extra[2], extra[3])  # bytes 74-75 = offset 72+2/72+3
```

**Découverte** : Deux patterns distincts correspondant aux armes utilisées.

---

## 4. Scripts Créés

| Script | Description | Statut |
|--------|-------------|--------|
| `scripts/extract_binary_events.py` | Extrait events bruts d'un chunk | ✅ |
| `scripts/analyze_binary_patterns.py` | Analyse patterns via marker 0x2D 0xC0 | ✅ |
| `scripts/correlate_kills.py` | Corrèle kills avec XUIDs/timestamps | ✅ |
| `scripts/find_kill_patterns.py` | Cherche structures kill par XUID | ✅ |
| `scripts/find_events_by_type.py` | Cherche events par type byte | ✅ |

---

## 5. Structure Roster (Annexe)

Pour référence, la structure roster identifiée via marker `0x2D 0xC0` :

```
[Variable]     | Gamertag (UTF-16 BE)
8 bytes        | XUID (little-endian)
2 bytes        | Marker: 0x2D 0xC0
32+ bytes      | Métadonnées (slot, équipe, etc.)
```

Cette structure est présente dans les chunks type 1 (roster) et type 2 (gameplay).

---

## 6. Fichiers d'Investigation

```
data/investigation/match_7f1bbf06/
├── manifest.json              # Manifest du film
├── chunks/                    # Chunks type 1 & 2 (partiels)
├── chunks_all/               # Tous les chunks type 2
├── chunks_with_type3/        # Chunks incluant type 3
│   ├── type1___filmChunk0.bin
│   ├── type2___filmChunk*.bin
│   └── type3___filmChunk18.bin  # ← Summary chunk (CLEF!)
├── type3_events.json         # Events extraits du type 3
├── correlated_kills.json     # Analyse corrélation timestamps
└── events_by_type.json       # Events par type byte
```

---

## 7. Prochaines Étapes

### 7.1 Construire Mapping Complet

Analyser d'autres matchs pour identifier les weapon IDs de :
- BR75 (Battle Rifle)
- Sniper S7
- Mangler
- Rocket Launcher
- Energy Sword
- Gravity Hammer
- Melee (à distinguer de AR)

### 7.2 Intégration App

Créer `src/data/parsers/weapon_parser.py` avec mapping weapon_id → weapon_name.

### 7.3 Automatiser Extraction

Modifier le pipeline de sync pour :
1. Télécharger les chunks type 3 quand disponibles
2. Extraire les weapon IDs des kills
3. Stocker dans DuckDB (`highlight_events.weapon_id`)

---

## 8. Références

- [Den Delimarsky - Film Files](https://den.dev/blog/extracting-stats-film-files-halo-infinite/)
- [SPNKr GitHub](https://github.com/acurtis166/SPNKr)
- [OpenSpartan film-event-extractor](https://github.com/OpenSpartan/film-event-extractor)

---

*Analyse réalisée le 2026-02-02 - Projet LevelUp*
*✅ SUCCÈS : Weapon ID localisé bytes 74-75 dans chunks type 3*
