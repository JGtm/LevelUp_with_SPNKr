# Binary Film Chunk Analysis - Final Report

> **Date**: 2026-02-02
> **Status**: 🛑 **ARCHIVED** - Investigation concluded, chunks not usable for weapon identification
> **Objective**: Identify weapon patterns in undocumented binary film chunk bytes

---

## Executive Summary

After extensive analysis of Halo Infinite film chunks (types 1, 2, and 3), we conclude that:

1. **Type 3 chunks contain only a random sample** (~10-20%) of match events
2. **The WID (Weapon ID) field does NOT represent the weapon used** for kills
3. **The killer/victim pattern is unreliable** (false positives on respawns)
4. **Type 2 chunks contain only the focal player's data** (who created the Theatre film)

**Conclusion**: Film chunks are **not suitable** for weapon identification or comprehensive frag analysis without official documentation.

---

## 🆕 IMPORTANT DISCOVERY: Bit-Shifted Data

After reviewing [Den Delimarsky's blog post](https://den.dev/blog/extracting-stats-film-files-halo-infinite/), we discovered that chunk data is **NOT byte-aligned**. Data can be shifted by 1-7 bits, making it invisible to standard byte-level searches.

### Proof of Concept

| Search Type | JGtm XUID found | JGtm Gamertag found |
|-------------|-----------------|---------------------|
| Byte-aligned | 0 | 1 |
| **Bit-shifted** | **17** | **17** |

This explains why we found so few events - we were searching at the wrong alignment!

### Next Steps (if investigation resumes)

1. Implement full bit-shifted event extraction
2. Re-analyze chunks with proper bit alignment
3. Follow Den Delimarsky's structure: `[Header 12B][Gamertag 32B][Padding 15B][Type 1B][Timestamp 4B][Padding 3B][Medal 1B][Padding 3B][Metadata 1B]`

**Reference**: https://den.dev/blog/extracting-stats-film-files-halo-infinite/

---

## What Works

| Feature | Status | Notes |
|---------|--------|-------|
| Timestamp extraction | ✅ Works | `(B1 + B2 * 256) / 100 = seconds` |
| Gamertag detection | ✅ Works | UTF-16 LE encoding |
| Type 2 temporal mapping | ✅ Works | ~20 seconds per chunk |

## What Does NOT Work

| Feature | Status | Reason |
|---------|--------|--------|
| Kill detection | ❌ Unreliable | Pattern produces false positives (respawns = kills) |
| Weapon identification | ❌ Invalid | Same WID for different weapons (BR75, MA40, melee) |
| Complete frag list | ❌ Impossible | Chunks contain only a sample of events |

---

## Technical Findings

### Timestamp Format (VALIDATED)

```
Pattern: 00 XX 00 [B0] [B1] [B2] [B3]
Timestamp = (B1 + B2 * 256) / 100 = seconds
```

### Event Structure (PARTIALLY VALIDATED)

```
Section       | Offset | Size   | Content
--------------|--------|--------|------------------
Gamertag      | 0      | 6-32   | UTF-16 LE
Padding       | ~24    | ~24    | 0x00
Event Pattern | ~24    | 3      | [00] [Code] [00]
Timestamp Raw | +3     | 4      | [B0] [B1] [B2] [B3]
B9 (flag)     | +9     | 1      | Unreliable
B13 (role)    | +13    | 1      | Unreliable
Marker        | +16    | 2      | [2e] [e0] (fixed)
Category      | +18    | 2      | Not meaningful
Weapon ID     | +20    | 2      | NOT the actual weapon
```

### Chunk Types

| Type | Content | Usability |
|------|---------|-----------|
| **Type 1** | Component schema/metadata | ❌ No gameplay data |
| **Type 2** | Replay data (positions, states) | ⚠️ Focal player only |
| **Type 3** | Highlight events | ❌ Random sample only |

---

## Invalidated Hypotheses

### Hypothesis 1: WID = Killer's Weapon
**INVALIDATED** on Solution match `55df2a12`:

| Event | Killer | Kill Weapon | Killer's Gun | Victim's Gun | WID |
|-------|--------|-------------|--------------|--------------|-----|
| 1:08 | Thdragonadvs | BR75 | BR75 | BR75 | `2f03` |
| 7:00 | Beef Shala | **Melee** | MA40 | MA40 | `2f03` |
| 9:24 | xoKIKAox | BR75 | BR75 | MA40 | `2f03` |

→ Same WID (`2f03`) for BR75 kills AND melee kill!

### Hypothesis 2: WID = Victim's Weapon
**INVALIDATED**: Victims had different weapons (BR75, MA40) but same WID.

### Hypothesis 3: WID varies by weapon on Fiesta
**INVALIDATED** on Fiesta match `189d1c23`:

| Event | User-confirmed weapon | WID |
|-------|----------------------|-----|
| 2:37 | Disruptor | `0c03` |
| 3:46 | **Commando** | `0c03` |

→ Same WID for different weapons!

### Hypothesis 4: Cat=36c0 + B13=1 = Kill
**INVALIDATED**: Event at 8:45 showed JGtm as "KILLER" but user confirmed he was in respawn (dead).

---

## Test Matches Analyzed

### Match 1: Solution `55df2a12` (Quick Play)
- **Focal player**: Beef Shala
- **Type 3 events**: 18 total
- **JGtm appearances**: 1 (should be 6+)

### Match 2: Fiesta `189d1c23` (Bazaar)
- **Focal player**: JGtm
- **Type 3 events**: ~20 total
- **JGtm kills in Theatre**: 15+
- **JGtm kills in chunk**: ~5

### Match 3: Quick Play `7f1bbf06`
- **Focal player**: breizhbengp (Type 2 only)
- **Type 3 events**: 18 total
- **JGtm confirmed frags**: 6
- **JGtm events in chunk**: 1

---

## Alternatives for Weapon Identification

Since chunks are not usable, consider these alternatives:

### 1. Medal API (Partiel)
Some medals indicate weapon type:
- **Ninja**: Sword kill from behind
- **Sharpshooter**: Precision weapon headshot
- **Splatter**: Vehicle kill
- **Beatdown**: Melee kill

### 2. ~~Match Stats API~~ ❌ NE FONCTIONNE PAS
~~`CoreStats.Breakdowns.Weapons[]` provides damage by weapon type.~~

**VÉRIFIÉ LE 2026-02-02** : Cette fonctionnalité n'existe PAS dans l'API réelle.
Voir section "Limites de l'API Halo Infinite" ci-dessous.

### 3. Manual Theatre Correlation
Watch replay and manually note weapons (current method).

---

## ⚠️ Limites de l'API Halo Infinite (Weapon Stats)

> **Date de vérification**: 2026-02-02
> **Conclusion**: Les statistiques détaillées par arme ne sont PAS disponibles dans l'API.

### Ce que l'API NE retourne PAS

| Donnée souhaitée | Disponible ? | Commentaire |
|------------------|--------------|-------------|
| Kills par type d'arme | ❌ NON | `Breakdowns.Weapons[]` n'existe pas |
| Headshots par arme | ❌ NON | Non exposé |
| Précision par arme | ❌ NON | Non exposé |
| Kill individuel avec arme | ❌ NON | Impossible via API |
| Dégâts par arme | ❌ NON | Non exposé |

### Ce que l'API retourne (Service Record + Match Stats)

```json
{
  "GrenadeKills": 224,
  "HeadshotKills": 1532,
  "MeleeKills": 643,
  "PowerWeaponKills": 533,
  "Accuracy": 43.92  // Globale, pas par arme
}
```

### Vérifications effectuées

| Source | Endpoint | Breakdowns.Weapons ? |
|--------|----------|----------------------|
| Match Stats (Quick Play) | `/hi/matches/{id}/stats` | ❌ Absent |
| Match Stats (Team Slayer) | `/hi/matches/{id}/stats` | ❌ Absent |
| Match Stats (Fiesta) | `/hi/matches/{id}/stats` | ❌ Absent |
| Service Record | `/hi/players/{xuid}/matchmade/servicerecord` | ❌ Absent |

### Scripts de test

Les scripts suivants ont été créés pour vérifier ces limites :
- `scripts/find_match_with_weapons.py` - Recherche de matchs avec breakdowns (aucun trouvé)
- `scripts/check_service_record_v2.py` - Vérification du Service Record
- `scripts/debug_match_raw.py` - Dump JSON brut des matchs

### Documentation externe

Le blog de Den Delimarsky ([den.dev/blog/halo-api-match-stats](https://den.dev/blog/halo-api-match-stats)) documente les endpoints mais ne mentionne pas de `Breakdowns.Weapons[]` dans les réponses réelles.

### Conclusion

**Il est IMPOSSIBLE d'obtenir les statistiques par arme** (kills, précision, dégâts) via l'API Halo Infinite officielle. Cette fonctionnalité n'est tout simplement pas exposée par 343 Industries.

Les seules données armes disponibles sont des compteurs agrégés :
- `PowerWeaponKills` (total kills avec armes lourdes)
- `MeleeKills` (total kills mêlée)
- `GrenadeKills` (total kills grenades)
- `HeadshotKills` (total headshots, toutes armes confondues)

---

## Files Structure

```
data/investigation/mapping/
├── 55df2a12/chunks/    # Solution (Quick Play)
├── 189d1c23/chunks/    # Fiesta (Bazaar)
├── 7f1bbf06/chunks/    # Quick Play
```

---

## Conclusion

Film chunks are **not a viable source** for:
- Weapon identification
- Comprehensive kill tracking
- Accurate killer/victim detection

The binary format is too opaque without official documentation, and the data is incomplete by design (highlight sampling).

**Recommendation**: Use Medal API and Match Stats API instead.

---

*Investigation archived on 2026-02-02*
*LevelUp Project - Experimental Research*
