# Plan d'Analyse des Bytes Binaires des Film Chunks

> **Date** : 2026-02-02
> **Objectif** : Identifier les patterns d'armes dans les bytes non documentés des highlight events
> **Statut** : ✅ **SUCCÈS - WEAPON ID TROUVÉ !** → Phase 2 : Mapping complet en attente

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

---

## 🚀 PHASE 2 : MAPPING COMPLET DES WEAPON IDs

### Objectif

Analyser les **10 derniers matchs** de JGtm pour :
1. Extraire **TOUS** les weapon IDs uniques (pas seulement ceux de JGtm)
2. Identifier les IDs **inconnus** (non encore mappés)
3. Pour chaque ID inconnu, fournir les infos nécessaires à l'identification manuelle

### Prérequis

**Base de données** : `data/players/JGtm/stats.duckdb`

**Requête pour obtenir les 10 derniers matchs** :
```sql
SELECT match_id, started_at, mode_category, map_name
FROM match_stats
ORDER BY started_at DESC
LIMIT 10;
```

**XUID JGtm** : `2533274823110022`

### Étapes d'Exécution

#### Étape 1 : Récupérer les 10 derniers match IDs

```bash
python -c "
import duckdb
con = duckdb.connect('data/players/JGtm/stats.duckdb', read_only=True)
matches = con.execute('''
    SELECT match_id, started_at, mode_category, map_name
    FROM match_stats
    ORDER BY started_at DESC
    LIMIT 10
''').fetchall()
for m in matches:
    print(f'{m[0]} | {m[1]} | {m[2]} | {m[3]}')
"
```

#### Étape 2 : Télécharger les chunks type 3 pour chaque match

```bash
# Pour chaque match_id :
python scripts/refetch_film_roster.py \
    --match-id <MATCH_ID> \
    --save-chunks-dir ./data/investigation/mapping/<MATCH_ID_SHORT>/chunks \
    --include-type2 \
    --max-type2-chunks 1
```

**Note** : `--max-type2-chunks 1` limite les chunks type 2 pour gagner du temps. Le chunk type 3 sera téléchargé automatiquement.

#### Étape 3 : Extraire les events de chaque chunk type 3

```bash
python scripts/extract_binary_events.py \
    --chunk ./data/investigation/mapping/<MATCH_ID_SHORT>/chunks/type3___filmChunk*.bin \
    --output ./data/investigation/mapping/<MATCH_ID_SHORT>/events.json
```

#### Étape 4 : Agréger tous les weapon IDs uniques

**Script à utiliser** : Créer `scripts/aggregate_weapon_ids.py`

```python
#!/usr/bin/env python3
"""
Agrège tous les weapon IDs uniques des matchs analysés.

Output: JSON avec pour chaque weapon_id inconnu :
- weapon_id (hex et decimal)
- match_id
- timestamp_ms
- gamertag du killer (si lisible)
- nombre d'occurrences total
"""

import json
from pathlib import Path
from collections import defaultdict

# Mapping connu
KNOWN_WEAPONS = {
    0xe02e: "Sidekick",
    0x7017: "MA40 AR",
}

def extract_weapon_id(extra_bytes: list[int]) -> int | None:
    """Extrait le weapon_id des extra_bytes (offset 2-3)."""
    if len(extra_bytes) < 4:
        return None
    return extra_bytes[2] + extra_bytes[3] * 256  # little-endian

def main():
    base_dir = Path("data/investigation/mapping")
    
    all_weapons = defaultdict(list)  # weapon_id -> list of occurrences
    
    for match_dir in base_dir.iterdir():
        if not match_dir.is_dir():
            continue
        
        events_file = match_dir / "events.json"
        if not events_file.exists():
            continue
        
        match_id = match_dir.name
        data = json.loads(events_file.read_text(encoding="utf-8"))
        
        for event in data.get("events", []):
            if event.get("event_type") != 50:  # kills only
                continue
            
            weapon_id = extract_weapon_id(event.get("extra_bytes_32", []))
            if weapon_id is None:
                continue
            
            all_weapons[weapon_id].append({
                "match_id": match_id,
                "timestamp_ms": event.get("timestamp_ms", 0),
                "gamertag": event.get("gamertag", "???")[:16],
            })
    
    # Séparer connus vs inconnus
    known = {}
    unknown = {}
    
    for weapon_id, occurrences in sorted(all_weapons.items()):
        weapon_name = KNOWN_WEAPONS.get(weapon_id)
        entry = {
            "weapon_id_hex": f"0x{weapon_id:04x}",
            "weapon_id_dec": weapon_id,
            "total_kills": len(occurrences),
            "weapon_name": weapon_name,
            "samples": occurrences[:3],  # 3 exemples max
        }
        
        if weapon_name:
            known[weapon_id] = entry
        else:
            unknown[weapon_id] = entry
    
    result = {
        "known_weapons": known,
        "unknown_weapons": unknown,
        "summary": {
            "total_unique_ids": len(all_weapons),
            "known_count": len(known),
            "unknown_count": len(unknown),
        }
    }
    
    output_path = base_dir / "weapon_ids_summary.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Résultats sauvegardés: {output_path}")
    
    # Afficher résumé
    print(f"\n=== RÉSUMÉ ===")
    print(f"Weapon IDs uniques: {len(all_weapons)}")
    print(f"Connus: {len(known)}")
    print(f"Inconnus: {len(unknown)}")
    
    if unknown:
        print(f"\n=== WEAPON IDs INCONNUS ===")
        print(f"{'ID (hex)':<12} {'ID (dec)':<10} {'Kills':<8} {'Exemple (match, timestamp, joueur)'}")
        print("-" * 80)
        for wid, entry in sorted(unknown.items(), key=lambda x: -x[1]["total_kills"]):
            sample = entry["samples"][0] if entry["samples"] else {}
            print(f"{entry['weapon_id_hex']:<12} {entry['weapon_id_dec']:<10} {entry['total_kills']:<8} "
                  f"{sample.get('match_id', '?')[:8]}... @ {sample.get('timestamp_ms', 0)/1000:.1f}s - {sample.get('gamertag', '?')}")

if __name__ == "__main__":
    main()
```

### Format de Sortie Attendu

**Fichier** : `data/investigation/mapping/weapon_ids_summary.json`

```json
{
  "known_weapons": {
    "57390": {
      "weapon_id_hex": "0xe02e",
      "weapon_id_dec": 57390,
      "total_kills": 87,
      "weapon_name": "Sidekick",
      "samples": [...]
    }
  },
  "unknown_weapons": {
    "12345": {
      "weapon_id_hex": "0x3039",
      "weapon_id_dec": 12345,
      "total_kills": 15,
      "weapon_name": null,
      "samples": [
        {
          "match_id": "abc123...",
          "timestamp_ms": 125000,
          "gamertag": "SomePlayer"
        }
      ]
    }
  },
  "summary": {
    "total_unique_ids": 12,
    "known_count": 2,
    "unknown_count": 10
  }
}
```

### Output Console Attendu

```
=== WEAPON IDs INCONNUS ===
ID (hex)     ID (dec)   Kills    Exemple (match, timestamp, joueur)
--------------------------------------------------------------------------------
0x1234       4660       23       abc123de... @ 125.0s - PlayerName
0x5678       22136      15       def456ab... @ 89.3s - AnotherPlayer
...
```

### Informations pour Identification Manuelle

Pour chaque weapon_id inconnu, l'utilisateur peut :

1. **Consulter le replay** du match indiqué au timestamp donné
2. **Identifier visuellement** l'arme utilisée par le joueur
3. **Mettre à jour** le mapping `KNOWN_WEAPONS` dans le script

### Armes Attendues dans Halo Infinite

| Catégorie | Armes |
|-----------|-------|
| **Pistolets** | Sidekick ✅, Mangler, Disruptor |
| **Fusils** | MA40 AR ✅, BR75, Commando, VK78, Stalker Rifle |
| **Précision** | Sniper S7, Shock Rifle, Skewer |
| **Shotguns** | Bulldog, Heatwave |
| **Explosifs** | Rocket Launcher, Cindershot, Ravager |
| **Corps-à-corps** | Energy Sword, Gravity Hammer, Melee |
| **Grenades** | Frag, Plasma, Dynamo, Spike |
| **Véhicules** | Warthog, Ghost, Banshee turrets |

---

## Données de Référence

### Match de Test Initial

**ID** : `7f1bbf06-d54d-4434-ad80-923fcabe8b1b`

**Résultats** :
- 48 kills total
- 41 Sidekick (0xe02e)
- 7 AR/Melee (0x7017)

### Mapping Actuel

```python
KNOWN_WEAPONS = {
    0xe02e: "Sidekick",   # 57390
    0x7017: "MA40 AR",    # 28695
}
```

---

## Structure des Fichiers

```
data/investigation/
├── match_7f1bbf06/           # Match de test initial
│   └── chunks_with_type3/
│       └── type3___filmChunk18.bin
│
└── mapping/                  # Phase 2 : Mapping complet
    ├── <match_id_1>/
    │   ├── chunks/
    │   │   └── type3___filmChunk*.bin
    │   └── events.json
    ├── <match_id_2>/
    │   └── ...
    └── weapon_ids_summary.json   # ← OUTPUT FINAL
```

---

## Suivi

- [x] Tokens API configurés
- [x] WEAPON ID localisé (bytes 74-75)
- [x] Mapping initial : Sidekick, MA40 AR
- [ ] **Télécharger chunks type 3 des 10 derniers matchs**
- [ ] **Extraire events de chaque match**
- [ ] **Agréger weapon IDs uniques**
- [ ] **Identifier manuellement les IDs inconnus**
- [ ] **Compléter le mapping**
- [ ] Intégration dans l'app LevelUp

---

## Ressources

### Scripts Existants

| Script | Usage |
|--------|-------|
| `scripts/refetch_film_roster.py` | Téléchargement chunks (type 1, 2, **3**) |
| `scripts/extract_binary_events.py` | Extraction events d'un chunk type 3 |
| `scripts/aggregate_weapon_ids.py` | **À CRÉER** - Agrégation des weapon IDs |

### Documentation

- [Den Delimarsky - Film Files](https://den.dev/blog/extracting-stats-film-files-halo-infinite/)
- [SPNKr GitHub](https://github.com/acurtis166/SPNKr)

---

*Plan créé le 2026-02-02 - Recherche expérimentale LevelUp*
*✅ Phase 1 : Weapon ID trouvé*
*⏳ Phase 2 : Mapping complet en attente*
