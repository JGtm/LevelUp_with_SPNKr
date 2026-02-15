# Recherche Expérimentale : Identification des Armes dans les Highlight Events

> **Date** : 2026-02-02
> **Auteur** : Agent IA
> **Statut** : Recherche exploratoire

---

## 1. Contexte et Objectif

L'objectif est d'identifier les **patterns récurrents** dans les highlight events qui pourraient correspondre à **l'arme utilisée lors d'un frag** (kill d'un joueur sur un autre).

---

## 2. État de l'Art Actuel

### 2.1 Structure documentée des Highlight Events (ChunkType 3)

Selon le blog de [Den Delimarsky](https://den.dev/blog/extracting-stats-film-files-halo-infinite/) :

| Offset | Taille | Contenu |
|--------|--------|---------|
| 0 | 12 bytes | Header (contenu inconnu) |
| 12 | 32 bytes | Gamertag (Unicode UTF-16) |
| 44 | 15 bytes | Padding (0x00) |
| 59 | 1 byte | **Type** (10=mode, 20=death, 50=kill) |
| 60 | 4 bytes | **Timestamp** (ms, little-endian) |
| 64 | 3 bytes | Padding |
| 67 | 1 byte | Medal marker |
| 68 | 3 bytes | Padding |
| 71 | 1 byte | **Medal ID** |
| **72** | **?** | **BYTES NON DOCUMENTÉS** |

### 2.2 Ce que SPNKr extrait actuellement

```python
{
    "event_type": "kill" | "death" | "medal",
    "time_ms": 45000,      # Timestamp en millisecondes
    "xuid": "2535...",     # XUID du joueur
    "gamertag": "Player",  # Gamertag
    "type_hint": 50,       # 10=mode, 20=death, 50=kill
}
```

### 2.3 Ce qui MANQUE (confirmé par Den Delimarsky)

> "One thing that I haven't yet figured out is how **assists** are tracked within the event batch."

> "Film files *may* contain the data required for us to build **heatmaps** of map movement... understand how binary data changes with **movement**, **weapon switches**, use of grenades..."

**L'arme utilisée lors d'un kill n'est PAS documentée !**

---

## 3. Hypothèses de Recherche

### Hypothèse 1 : Données dans les bytes non documentés (>72 bytes)

La structure documentée fait 72 bytes, mais les events pourraient contenir des bytes supplémentaires avec :
- **Weapon ID** : Identifiant de l'arme utilisée
- **Damage Type** : Type de dégât (balistique, énergie, explosion)
- **Victim XUID** : Pour les kills, le XUID de la victime (corrélation directe)
- **Killer XUID** : Pour les deaths, le XUID du tueur

### Hypothèse 2 : Données encodées dans le Header (0-12 bytes)

Le "header" de 12 bytes pourrait contenir :
- **Weapon ID** encodé
- **Damage flags**
- **Match context**

### Hypothèse 3 : Events corrélés par timestamp

Certains jeux stockent l'arme dans un event séparé corrélé par timestamp :
- Event Kill (t=45000) → joueur A
- Event Weapon (t=45000) → weapon_id=X
- Event Death (t=45000) → joueur B

### Hypothèse 4 : Données dans les ChunkType 2 (in-game events)

Les chunks de type 2 contiennent les "in-game event captures" (positions, mouvements). L'arme active pourrait être trackée là.

---

## 4. Méthodologie d'Expérimentation

### Phase 1 : Analyse du raw_json existant

1. Extraire tous les `raw_json` distincts de la table `highlight_events`
2. Identifier tous les champs JSON présents (pas seulement les 5 mappés)
3. Chercher des patterns comme `weapon_id`, `damage_type`, `killer_xuid`, etc.

### Phase 2 : Analyse binaire des chunks

1. Télécharger les chunks bruts pour plusieurs matchs via `scripts/refetch_film_roster.py`
2. Comparer la taille réelle des events vs la structure documentée (72 bytes)
3. Analyser les bytes au-delà de l'offset 72

### Phase 3 : Corrélation avec weapon_stats

1. Récupérer les `weapon_stats` depuis l'API (endpoint match_stats)
2. Pour chaque arme utilisée (>0 kills), vérifier si des patterns apparaissent

### Phase 4 : Analyse comparative multi-matchs

1. Sélectionner des matchs où le joueur n'a utilisé QU'UNE seule arme
2. Extraire les bytes non documentés de ces kills
3. Chercher des valeurs constantes (= weapon_id potentiel)

---

## 5. Ressources et Outils

### APIs disponibles

| Endpoint | URL | Données |
|----------|-----|---------|
| Film Manifest | `/hi/films/matches/{matchId}/spectate` | Liste des chunks |
| Film Chunk | `{BlobStoragePathPrefix}/filmChunk{N}` | Données binaires compressées |
| Match Stats | `/hi/matches/{matchId}/stats` | Stats incluant `weapon_core` |

### Scripts existants dans le projet

| Script | Usage |
|--------|-------|
| `scripts/refetch_film_roster.py` | Téléchargement et décompression des chunks |
| `scripts/migrate_highlight_events.py` | Parsing des events JSON |
| `src/data/sync/transformers.py` | Transformation events → rows |

### Bibliothèques Python pour l'analyse binaire

```python
# Lecture binaire avec struct
import struct

# Parsing bit-level avec bitstring (utilisé par SPNKr)
from bitstring import BitArray

# Décompression zlib
import zlib
```

---

## 6. Références Externes

### Documentation SPNKr

- GitHub : [acurtis166/SPNKr](https://github.com/acurtis166/SPNKr)
- Documentation : acurtis166.github.io/spnkr/
- Module `spnkr.film` : parsing des highlight events

### Blog Den Delimarsky

- [Extracting Match Stats From Halo Infinite Film Files](https://den.dev/blog/extracting-stats-film-files-halo-infinite/)
- [Parsing Bond Responses From The Halo Infinite API](https://den.dev/blog/parsing-halo-api-bond/)

### Outils communautaires

- [OpenSpartan/film-event-extractor](https://github.com/OpenSpartan/film-event-extractor) - Outil C# d'extraction (archivé)
- [libpyinfinite](https://github.com/Surasia/libpyinfinite) - Parser de fichiers binaires Halo Infinite

---

## 7. Schéma Binaire Potentiel (Hypothèse)

```
Offset  | Taille | Champ             | Notes
--------|--------|-------------------|-------
0       | 4      | Event ID?         | Inconnu
4       | 4      | Unknown flags     | Pourrait contenir weapon_type
8       | 4      | Unknown           | Inconnu
12      | 32     | Gamertag          | UTF-16 BE
44      | 15     | Padding           | 0x00
59      | 1      | Event Type        | 10/20/50
60      | 4      | Timestamp (ms)    | Little-endian
64      | 3      | Padding           | 0x00
67      | 1      | Medal marker      | 0x00 ou 0x01
68      | 3      | Padding           | 0x00
71      | 1      | Medal ID          | Voir mapping
72      | 8?     | Killer/Victim XUID? | Hypothèse
80      | 4?     | Weapon ID?        | Hypothèse
84      | ?      | Damage info?      | Hypothèse
```

---

## 8. Prochaines Étapes

1. **Créer script d'analyse** : `scripts/analyze_highlight_binary.py`
2. **Extraire samples** : 100 matchs avec variété d'armes
3. **Mapper les weapon_ids** : Croiser avec les stats d'armes connues
4. **Documenter les findings** : Mettre à jour ce fichier

---

## 9. Résultats (À compléter)

### Champs supplémentaires identifiés dans raw_json

_À compléter après l'analyse_

### Patterns binaires corrélés aux armes

_À compléter après l'expérimentation_

### Mapping Weapon ID → Nom

_À compléter_

---

*Document de recherche - LevelUp Project*
