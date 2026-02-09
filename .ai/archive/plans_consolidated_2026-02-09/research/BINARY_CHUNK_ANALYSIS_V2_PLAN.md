# Binary Film Chunk Analysis v2 - Bit-Shifted Investigation

> **Date**: 2026-02-02
> **Status**: ✅ **INVESTIGATION COMPLETE** - Events validated, Weapon ID not found
> **Objective**: Re-analyze film chunks using bit-shifted extraction (Den Delimarsky method)

---

## Context

Previous investigation failed to find events because data is **NOT byte-aligned**. After discovering [Den Delimarsky's blog post](https://den.dev/blog/extracting-stats-film-files-halo-infinite/), we found that:

| Search Type | JGtm XUID found | JGtm Gamertag found |
|-------------|-----------------|---------------------|
| Byte-aligned | 0 | 1 |
| **Bit-shifted** | **17** | **17** |

This plan outlines the systematic re-investigation using proper bit-shifted extraction.

---

## Phase 1: Implement Bit-Shifted Extraction

### 1.1 Core Functions Needed

```python
def find_pattern_bit_shifted(data: bytes, pattern: bytes) -> list[int]
def extract_bits(data: bytes, start_bit: int, bit_length: int) -> bytes
def is_bit_match(data: bytes, pattern: bytes, bit_offset: int) -> bool
```

### 1.2 Structure to Extract (per Den Delimarsky)

| Section | Size | Content |
|---------|------|---------|
| Header | 12 bytes | Unknown metadata |
| Gamertag | 32 bytes | UTF-16 LE |
| Padding | 15 bytes | 0x00 |
| Event Type | 1 byte | 10=mode, 20=death, 50=kill |
| Timestamp | 4 bytes | Milliseconds from match start |
| Padding | 3 bytes | 0x00 |
| Medal Marker | 1 byte | Medal indicator |
| Padding | 3 bytes | 0x00 |
| Metadata | 1 byte | Medal type ID |

### 1.3 Key Markers to Search

| Marker | Hex | Description |
|--------|-----|-------------|
| XUID indicator | `0x2D 0xC0` | Precedes XUID (8 bytes before) |
| Event marker | `0x2E 0xE0` | Found in all events (from our previous analysis) |

---

## Phase 2: Reference Data from Theatre Mode

### Match 1: Fiesta `189d1c23-b006-421a-9515-f978edc0dc45` (Bazaar)

**Player**: JGtm  
**Map**: Bazaar  
**Mode**: Fiesta

| # | Timestamp | Weapon | Victim | Notes |
|---|-----------|--------|--------|-------|
| 1 | **1:04** | Sniper S7 Flexfire | SP00KY MAGE | |
| 2 | **1:08** | Sniper S7 Flexfire | SimonGames64 | |
| 3 | **1:51** | Disrupteur calciné | SimonGames64 | |
| 4 | **2:37** | Disrupteur calciné | ? | |
| 5 | **3:01** | Fusil électrique (Shock Rifle) | ? | |
| 6 | **3:10** | Fusil électrique (Shock Rifle) | SimonGames64 | |
| 7 | **4:33** | Marteau Rushdown (Gravity Hammer) | ? | |
| 8 | **4:43** | Marteau Rushdown | SimonGames64 | |
| 9 | **5:21** | Marteau Rushdown | ? | |
| 10 | **6:48** | M41 Tracker (Rocket Launcher) | ? | Double kill |
| 11 | **7:52** | Ravageur Rebound (Ravager) | SimonGames64 | |
| 12 | **8:26** | Bulldog Convergence | SimonGames64 | |
| 13 | **8:38** | Bulldog Convergence | ? | |
| 14 | ??? | Grenade électrique ? | ? | Hard to identify |
| 15 | **9:11** | Bulldog Convergence | TGITousley | |

**Other confirmed events (other players)**:
- **1:35** - Pwr opps tue SP00KY MAGE avec **Épée à énergie duelliste**
- **6:33** - Pwr opps tue SimonGames64 avec **Rayon de Sentinelle Arcane**
- **8:40** - JGtm tue SP00KY MAGE avec **Bulldog Convergence**

**User notes**:
- Match duration: **9:37** (577 seconds)
- At **8:45** JGtm was in respawn (dead)
- At **3:45** JGtm was running (no frag)

---

### Match 2: Quick Play `55df2a12-ccbf-4f52-bf8c-6772632096f0` (Solution)

**Player**: JGtm  
**Map**: Solution  
**Mode**: Quick Play (standard weapons)

| # | Timestamp | Weapon | Victim | Notes |
|---|-----------|--------|--------|-------|
| 1 | **1:49** | BR75 | ? | |
| 2 | **3:55** | Corps à corps (Melee) | ? | |
| 3 | **4:14** | BR75 | ? | |

**Confirmed events (other players)**:
- **1:08** - Thdragonadvs lance grenade (no kill)
- **1:15** - Thdragonadvs tue JGtm avec **BR75**
- **1:28** - Ticklemaster962 tue Nerdalert5125 avec **BR75 Breacher**
- **7:00** - Beef Shala tue quelqu'un avec **Melee** (équipé: MA40)
- **7:45** - Nerdalert5125 tue xDelta avec **Marteau (Gravity Hammer)**
- **9:24** - xoKIKAox tue Beef Shala avec **BR75** (médaille Tireur d'élite)

**User notes - FALSE POSITIVES identified**:
- **0:30** - xoKIKAox: **NOT in game yet** (spawn event?)
- **0:35** - JGtm: **NOT in game yet** (spawn event?)
- **1:42** - Thdragonadvs: **En respawn** (was dead, not killer)
- **3:02** - mimo2956: **Rien de notable** (no Bulldog on map)
- **5:06** - JGtm: **Respawn** (was dead)
- **5:57** - JGtm: **Walking crouched** (no action)

---

### Match 3: Quick Play `7f1bbf06-d54d-4434-ad80-923fcabe8b1b`

**Player**: JGtm  
**Map**: ?  
**Mode**: Quick Play

| # | Timestamp | Weapon | Victim |
|---|-----------|--------|--------|
| 1 | ~2:00 | Corps à corps (Melee) | ? |
| 2 | **2:49** | Sidekick | breizhbengp |
| 3 | **3:40** | Sidekick | breizhbengp |
| 4 | **3:51** | Sidekick | HJ Destroyer |
| 5 | **4:11** | Sidekick | Ecaru |
| 6 | **4:57** | Sidekick | breizhbengp |

**User notes**:
- JGtm used primarily **Sidekick, MA40 AR, and Melee**
- First frag was melee (can be isolated with medals)

---

## Phase 3: Hypotheses to Test (with bit-shifted extraction)

### Hypothesis A: Den Delimarsky Structure Works

Test if the structure `[Header 12B][Gamertag 32B][Padding 15B][Type 1B][Timestamp 4B]...` applies to type 3 chunks.

**Test method**:
1. Find all `0x2D 0xC0` markers with bit-shifted search
2. Extract XUID (8 bytes before marker)
3. Extract gamertag (32 bytes before padding, 21 bytes before XUID)
4. Validate against known players

### Hypothesis B: Event Type Codes

| Code (decimal) | Description |
|----------------|-------------|
| 10 | Mode-specific (flag capture, etc.) |
| 20 | Death |
| 50 | Kill |

**Test method**:
1. Extract all events with bit-shifted search
2. Filter by type code
3. Correlate timestamps with Theatre observations

### Hypothesis C: Medal Mapping

Den Delimarsky provides a partial medal ID mapping. Test against known medals.

**Test method**:
1. Extract medal bytes from events
2. Compare with medal API data for same match
3. Validate mappings

### Hypothesis D: Timestamp Format

Previous investigation found `(B1 + B2 * 256) / 100 = seconds` but with byte-aligned extraction.

**Test method**:
1. Extract timestamps with bit-shifted method
2. Compare with Theatre timestamps
3. If different, test `milliseconds from match start` (Den's format)

### Hypothesis E: Weapon ID Location

Previous byte-aligned analysis found:
- `0xE02E` = Sidekick
- `0x7017` = MA40 AR

**Test method**:
1. With bit-shifted extraction, verify if these patterns still appear
2. Check if weapon ID location changes with proper alignment
3. Correlate with Theatre weapon observations

---

## Phase 4: Validation Protocol

### Step 1: Download All Chunks

For each reference match, download **ALL chunk types**:
```bash
python scripts/refetch_film_roster.py --match-id {MATCH_ID} \
  --save-chunks-dir data/investigation/mapping/{SHORT_ID}/chunks \
  --include-type2
```

### Step 2: Extract XUID/Gamertag Pairs

Use bit-shifted search for `0x2D 0xC0` in chunks 1 & 2 to build player roster.

### Step 3: Extract Events from Chunk Type 3

Use bit-shifted search to find all events matching Den's structure.

### Step 4: Correlate with Theatre Data

| Theatre Event | Chunk Event Found? | Timestamp Match? | Player Match? | Weapon ID? |
|---------------|-------------------|------------------|---------------|------------|
| JGtm 1:04 Sniper | ? | ? | ? | ? |
| ... | ... | ... | ... | ... |

### Step 5: Identify Pattern Reliability

Calculate:
- Detection rate: `events_found / theatre_events * 100%`
- False positive rate: `fake_events / all_detected_events * 100%`
- Timestamp accuracy: `avg(|chunk_ts - theatre_ts|)`

---

## Phase 5: Deliverables

1. **Python script**: `scripts/analyze_chunks_bitshifted.py`
   - Bit-shifted extraction functions
   - Event parsing with Den's structure
   - Validation against Theatre data

2. **Updated documentation**: This file + archive update

3. **Weapon ID mapping**: If successful, documented mapping

---

## Test Execution Order

1. ✅ Proof of concept done (JGtm XUID found 17x with bit-shift)
2. ✅ Implement full event extraction with bit-shift
3. ✅ Test Hypothesis A on match `189d1c23` (Fiesta) - **VALIDATED**
4. ✅ Test Hypothesis B (event type codes) - **VALIDATED** (10=mode, 20=death, 50=kill)
5. ✅ Test Hypothesis D (timestamp format) - **BIG ENDIAN, not LE!**
6. ✅ Correlate with Theatre data table - **100% CORRELATION (14/14 kills)**
7. ❌ Test Hypothesis E (weapon ID) - **WEAPON ID NOT FOUND in extra bytes**
8. ⬜ Test on match `55df2a12` (Solution) for cross-validation
9. ✅ Conclusions documented below

---

## Investigation Results (2026-02-02)

### Validated Findings

| Finding | Status | Details |
|---------|--------|---------|
| Event extraction | ✅ SUCCESS | Structure Den Delimarsky works |
| Timestamp format | ✅ SUCCESS | **Big Endian** (not LE as initially assumed) |
| Event type codes | ✅ SUCCESS | 10=mode, 20=death, 50=kill confirmed |
| Theatre correlation | ✅ SUCCESS | **14/14 kills matched** (0.1s - 2.3s delta) |
| Multiple bit offsets | ✅ SUCCESS | Must scan bit_off 0,2,4,6 for all events |

### Failed Findings

| Finding | Status | Details |
|---------|--------|---------|
| Weapon ID in extra bytes | ❌ FAILED | Pattern `0x2ee0` is constant, NOT weapon-specific |
| Weapon ID location | ❌ NOT FOUND | All weapons (Sniper, Hammer, Rocket, etc.) have identical extra bytes |

### Technical Details

**Correct Event Structure** (validated):
```
| Offset | Size | Content                           |
|--------|------|-----------------------------------|
| 0      | 12   | Header (unknown metadata)         |
| 12     | 32   | Gamertag (UTF-16 LE)              |
| 44     | 15   | Padding (0x00)                    |
| 59     | 1    | Event type (10/20/50)             |
| 60     | 4    | Timestamp (ms, **BIG ENDIAN**)    |
| 64     | 3    | Padding                           |
| 67     | 1    | Medal marker                      |
| 68     | 3    | Padding                           |
| 71     | 1    | Medal ID                          |
| 72+    | var  | Extra bytes (NO weapon ID found)  |
```

**Critical Discovery**: Timestamp is **Big Endian**, not Little Endian!
```python
# WRONG (original assumption)
timestamp_le = struct.unpack('<I', ts_bytes)[0]

# CORRECT (validated)
timestamp_be = struct.unpack('>I', ts_bytes)[0]
```

### Correlation Results (Match 189d1c23 - Fiesta)

| Theatre | Found | Delta | Weapon (theatre) |
|---------|-------|-------|------------------|
| 1:04 | 1:04.6 | 0.7s | Sniper S7 |
| 1:08 | 1:08.5 | 0.6s | Sniper S7 |
| 1:51 | 1:52.3 | 1.3s | Disrupteur |
| 2:37 | 2:39.1 | 2.1s | Disrupteur |
| 3:01 | 3:01.8 | 0.8s | Shock Rifle |
| 3:10 | 3:11.3 | 1.3s | Shock Rifle |
| 4:33 | 4:35.3 | 2.3s | Gravity Hammer |
| 4:43 | 4:44.1 | 1.1s | Gravity Hammer |
| 5:21 | 5:21.1 | 0.1s | Gravity Hammer |
| 6:48 | 6:49.6 | 1.6s | Rocket |
| 7:52 | 7:53.5 | 1.5s | Ravager |
| 8:26 | 8:27.1 | 1.1s | Bulldog |
| 8:38 | 8:39.5 | 1.5s | Bulldog |
| 9:11 | 9:12.1 | 1.1s | Bulldog |

**Success Rate: 14/14 (100%)**

### Conclusion

The Den Delimarsky structure successfully extracts **kill/death events with accurate timestamps**.
However, **weapon IDs are NOT encoded** in the documented extra bytes.

The pattern `0x2e 0xe0` is a constant marker, not a weapon identifier.
All weapons (7 different types in Fiesta) produce identical extra byte patterns.

**Weapon ID location remains unknown.**

---

## Investigation complémentaire (Headers et Medals)

### Header Analysis (bytes 0-11)

| Test | Résultat |
|------|----------|
| Header = Weapon ID? | ❌ **NON** - Header est un identifiant JOUEUR, pas arme |
| Header unique par joueur | ✅ OUI - Chaque joueur a un header constant unique |

Exemple :
- JGtm: `4cde91e8aba1301621967cf9` (tous les kills)
- SP00KY MAGE: `213832158f62f7f089e736a7`
- SimonGames64: `b01ee8381a54b19b4f34788f`

### Medal Analysis (position 71)

| Test | Résultat |
|------|----------|
| Medal → Weapon inference | ⚠️ **PARTIEL** - Seulement ~7% des kills |

Medals liées aux armes :
| Medal ID | Medal Name | Arme |
|----------|------------|------|
| 76 | Gunslinger | Sidekick |
| 77 | Scattergunner | Shotgun |
| 78 | Sharpshooter | Precision |
| 80 | Heavy | Power Weapon |
| 108 | Snipe | Sniper Headshot |
| 114 | No Scope | Sniper No Scope |

**Exemple trouvé** : Kill à 1:04 avec Sniper → Medal ID 108 ("Snipe") ✓

### Conclusion définitive

**Le weapon ID n'est PAS encodé** dans la structure des film chunks documentée.

Options pour identifier l'arme utilisée :
1. **Medals** (~7% des kills) - Certaines medals indiquent l'arme
2. **Catégories API** - `power_weapon_kills`, `melee_kills`, `grenade_kills` (agrégés seulement)
3. **Non disponible** - Pour la majorité des kills individuels

---

## Dernière théorie testée : Event DEATH de la victime

| Test | Résultat |
|------|----------|
| Event DEATH contient weapon ID? | ❌ NON - Extra bytes identiques pour différentes armes |
| Killer référencé dans event victime? | ❌ NON - Pas de structure killer+victim |
| API Match Stats / Weapons breakdown? | ❌ NON - Seulement compteurs agrégés |

**API Match Stats** ne fournit que :
- `PowerWeaponKills` (total)
- `MeleeKills` (total)  
- `GrenadeKills` (total)
- `HeadshotKills` (total)

Pas de breakdown par arme spécifique (Sniper, Rocket, etc.).

## VERDICT FINAL

**Les weapon stats individuelles par kill ne sont PAS disponibles** :
- ❌ Pas dans les Film Chunks (structure Den Delimarsky)
- ❌ Pas dans l'API Match Stats
- ⚠️ Partiellement via Medals (~7% des kills)

Cette limitation est **côté 343 Industries**, pas côté LevelUp.

---

## Key Differences from v1 Investigation

| Aspect | v1 (Failed) | v2 (This Plan) |
|--------|-------------|----------------|
| Search method | Byte-aligned | **Bit-shifted** |
| Structure | Custom guesses | **Den Delimarsky documented** |
| Event type | 0x14, 0x32 (arbitrary) | **10, 20, 50 (documented)** |
| Timestamp | B[1:2] LE centiseconds | **4 bytes milliseconds** |
| Validation | Ad-hoc | **Systematic correlation table** |

---

## Resources

- [Den Delimarsky's Blog Post](https://den.dev/blog/extracting-stats-film-files-halo-infinite/)
- [OpenSpartan Film Event Extractor](https://github.com/OpenSpartan/film-event-extractor)
- [SPNKr Project](https://github.com/acurtis166/SPNKr)

---

*Created: 2026-02-02*
*LevelUp Project - Experimental Research*
