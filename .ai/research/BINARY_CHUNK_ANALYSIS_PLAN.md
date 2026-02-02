# Plan d'Analyse des Bytes Binaires des Film Chunks

> **Date** : 2026-02-02
> **Objectif** : Identifier les patterns d'armes dans les bytes non documentés des highlight events
> **Statut** : ✅ **SUCCÈS - WEAPON ID TROUVÉ !**

---

## 🎯 DÉCOUVERTE MAJEURE

### Localisation du Weapon ID

**Position confirmée** : Bytes 74-75 dans les highlight events (chunks type 3)

| Bytes (hex) | uint16 LE | Arme |
|-------------|-----------|------|
| `0x2e 0xe0` | 57390 | **Sidekick** |
| `0x17 0x70` | 28695 | **MA40 AR** |

### Structure Complète d'un Kill Event

```
Offset | Taille | Contenu
-------|--------|------------------
0-11   | 12     | Header (variable, contient flags)
12-43  | 32     | Gamertag (UTF-16 BE, souvent corrompu)
44-58  | 15     | Padding (0x00)
59     | 1      | Type (50=kill, 20=death, 10=mode)
60-63  | 4      | Timestamp (ms, little-endian)
64-71  | 8      | Padding/Flags
72-73  | 2      | ??? (souvent 0x00)
74-75  | 2      | **WEAPON ID** (uint16 little-endian)
76+    | ?      | Données supplémentaires (victim index?)
```

### Validation

**Match analysé** : `7f1bbf06-d54d-4434-ad80-923fcabe8b1b`
- **48 kills** total (tous joueurs)
- **41 kills** avec pattern `0x2e 0xe0` → Sidekick
- **7 kills** avec pattern `0x17 0x70` → MA40 AR / Melee

Correspond aux données du joueur : principalement Sidekick + quelques kills AR/Melee.

---

## 1. Contexte

### 1.1 Problème Initial

Les highlight events parsés par SPNKr contenaient uniquement :
- `event_type` : "kill", "death", "medal", "mode"
- `time_ms` : timestamp en millisecondes
- `xuid` : identifiant du joueur
- `gamertag` : nom du joueur
- `type_hint` : 50=kill, 20=death, 10=mode

**L'arme utilisée pour un kill n'était PAS dans ces champs.**

### 1.2 Hypothèse Validée

✅ **L'arme est encodée dans les bytes 74-75** (après offset 72 de la structure documentée).

### 1.3 Découverte Clé

Les events formatés sont dans les **chunks type 3** (summary), pas dans les chunks type 2 (gameplay).

Le script `refetch_film_roster.py` ne téléchargeait que les types 1 et 2. Il a fallu modifier pour inclure le type 3.

---

## 2. Méthodologie Qui a Fonctionné

### Phase 1 : Téléchargement du Chunk Type 3

```bash
# Modification du script pour inclure type 3
type_ids = {1, 2, 3}  # au lieu de {1, 2}

python scripts/refetch_film_roster.py \
    --match-id 7f1bbf06-d54d-4434-ad80-923fcabe8b1b \
    --save-chunks-dir ./data/investigation/match_7f1bbf06/chunks_with_type3 \
    --include-type2
```

### Phase 2 : Extraction des Events Type 3

```bash
python scripts/extract_binary_events.py \
    --chunk data/investigation/match_7f1bbf06/chunks_with_type3/type3___filmChunk18.bin \
    --analyze \
    --output data/investigation/match_7f1bbf06/type3_events.json
```

**Résultat** : 274 events (48 kills, 115 deaths, 111 mode)

### Phase 3 : Analyse des Patterns

```python
# Grouper les kills par pattern bytes 74-75
kills = [e for e in events if e['event_type'] == 50]

for k in kills:
    extra = k['extra_bytes_32']
    weapon_pattern = (extra[2], extra[3])  # bytes 74-75
```

**Résultat** :
- 41 kills avec `(0x2e, 0xe0)` = Sidekick
- 7 kills avec `(0x17, 0x70)` = AR/Melee

---

## 3. Plan pour la Suite

### Phase A : Construire le Mapping Complet

**Objectif** : Identifier les weapon IDs pour toutes les armes de Halo Infinite.

**Méthode** :
1. Analyser des matchs avec différentes armes (via medals ou usage connu)
2. Extraire les patterns bytes 74-75 pour chaque kill
3. Corréler avec l'arme connue

**Armes prioritaires** :
| Arme | Méthode d'identification |
|------|-------------------------|
| BR75 | Matchs Ranked (arme de départ) |
| Sniper S7 | Medal "Sniper Spree" |
| Mangler | Caractéristique (melee combo) |
| Rocket | Medal "Overkill" avec explosif |
| Shotgun | Medal "Scattergunner" |
| Energy Sword | Medal "Ninja" |
| Gravity Hammer | Medal "Hammer Spree" |
| Melee | Premier kill du match test |

### Phase B : Distinguer AR vs Melee

**Problème** : Le pattern `0x17 0x70` pourrait être AR **ou** Melee.

**Test** :
1. Match où le joueur fait **uniquement** des kills melee (aucune arme)
2. Comparer le pattern avec un match AR pur

### Phase C : Intégration dans l'App

**Script à créer** : `src/data/parsers/weapon_parser.py`

```python
WEAPON_ID_MAP = {
    0xe02e: "Sidekick",
    0x7017: "MA40 AR",
    # ... autres armes
}

def extract_weapon_from_event(extra_bytes: bytes) -> str | None:
    """Extrait le nom de l'arme depuis les extra_bytes d'un event."""
    if len(extra_bytes) < 4:
        return None
    weapon_id = int.from_bytes(extra_bytes[2:4], 'little')
    return WEAPON_ID_MAP.get(weapon_id)
```

### Phase D : Parser les Chunks Type 3

**Modifier** : `scripts/refetch_film_roster.py`

Ajouter une fonction pour extraire les highlight events formatés depuis le chunk type 3 et les sauvegarder avec le weapon_id.

---

## 4. Scripts Créés

| Script | Statut | Description |
|--------|--------|-------------|
| `scripts/extract_binary_events.py` | ✅ | Extrait events bruts d'un chunk |
| `scripts/analyze_binary_patterns.py` | ✅ | Analyse patterns binaires |
| `scripts/correlate_kills.py` | ✅ | Corrèle kills avec XUIDs/timestamps |
| `scripts/find_kill_patterns.py` | ✅ | Cherche structures kill par XUID |
| `scripts/find_events_by_type.py` | ✅ | Cherche events par type byte |
| `scripts/fetch_match_weapon_stats.py` | ⚠️ | Fetch API (auth issues) |

---

## 5. Suivi

- [x] Tokens API configurés (Azure OAuth)
- [x] Chunks téléchargés (type 1, 2, **3**)
- [x] Script extract_binary_events.py créé
- [x] Events type 3 extraits (274 events)
- [x] **WEAPON ID TROUVÉ** : bytes 74-75
- [x] Mapping initial : Sidekick (0xe02e), AR (0x7017)
- [ ] Mapping complet (autres armes)
- [ ] Distinction AR vs Melee
- [ ] Intégration dans l'app LevelUp

---

## 6. Fichiers d'Investigation

```
data/investigation/match_7f1bbf06/
├── manifest.json              # Manifest du film
├── chunks/                    # Chunks type 1 & 2
├── chunks_all/               # Tous les chunks type 2
├── chunks_with_type3/        # Chunks incluant type 3
│   └── type3___filmChunk18.bin  # ← Summary chunk avec events
├── type3_events.json         # Events extraits du type 3
├── correlated_kills.json     # Analyse corrélation
└── events_by_type.json       # Events par type byte
```

---

## 7. Ressources

### Documentation

- [Den Delimarsky - Film Files](https://den.dev/blog/extracting-stats-film-files-halo-infinite/)
- [SPNKr GitHub](https://github.com/acurtis166/SPNKr)
- [OpenSpartan film-event-extractor](https://github.com/OpenSpartan/film-event-extractor)

### Weapon IDs Découverts

| Bytes | uint16 | Arme |
|-------|--------|------|
| `0x2e 0xe0` | 57390 (0xe02e) | Sidekick |
| `0x17 0x70` | 28695 (0x7017) | MA40 AR |
| *à découvrir* | ... | BR75 |
| *à découvrir* | ... | Sniper S7 |
| *à découvrir* | ... | Melee |

---

*Plan créé le 2026-02-02 - Recherche expérimentale LevelUp*
*✅ SUCCÈS : Weapon ID trouvé le 2026-02-02*
