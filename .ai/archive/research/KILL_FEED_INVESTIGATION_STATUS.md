# Statut de l'Investigation Kill Feed et Weapon IDs

> **Date**: 2026-02-03
> **Statut**: 🟡 En cours
> **Lien**: KILL_FEED_WEAPON_INVESTIGATION.md

---

## Résumé Exécutif

Investigation lancée pour explorer toutes les pistes permettant d'identifier les weapon IDs et leurs icônes depuis le kill feed de Halo Infinite.

**Contexte** : Le kill feed affiche visuellement les icônes d'armes, donc les données doivent être disponibles quelque part.

**État actuel** : 2 weapon IDs identifiés (Sidekick, MA40 AR) depuis les chunks type 3. Recherche en cours pour identifier plus d'armes et leurs icônes.

---

## Outils Créés

### Scripts d'Investigation

| Script | Description | Statut |
|--------|-------------|--------|
| `scripts/explore_killfeed_weapons.py` | Script initial amélioré | ✅ Amélioré |
| `scripts/investigate_killfeed_weapons.py` | Script complet multi-phases | ✅ Créé |

### Fonctionnalités

- ✅ Phase 1 : Exploration Assets Discovery UGC
- ✅ Phase 2 : Analyse Kill Feed visuel (structure des events)
- ✅ Phase 3 : Extraction Film Chunks (extra bytes)
- ✅ Phase 4 : Exploration API non documentée
- ✅ Phase 5 : Theatre Mode extraction

---

## Résultats par Phase

### Phase 1 : Assets Discovery UGC

**Statut** : 🟡 Partiellement exploré

**Découvertes** :
- Types connus : Maps, Playlists, PlaylistMapModePairs, GameVariants
- Types hypothétiques identifiés : Weapons, WeaponIcons, WeaponDefinitions, Equipment, Vehicles, Medals
- Méthodes SPNKr disponibles : `get_map()`, `get_playlist()`, `get_map_mode_pair()`, `get_ugc_game_variant()`

**Actions nécessaires** :
- Tester les types hypothétiques avec des asset IDs valides
- Trouver des weapon IDs depuis les matchs pour les utiliser comme asset_id

**Blocages** :
- Pas d'endpoint de listing pour Discovery UGC
- Besoin d'asset IDs valides pour tester

---

### Phase 2 : Analyse Kill Feed Visuel

**Statut** : 🟡 Structure analysée, corrélation manuelle nécessaire

**Découvertes** :
- Structure des highlight events documentée
- Aucun champ `weapon` ou `icon` dans les events JSON parsés
- Raw JSON disponible mais structure non documentée

**Actions nécessaires** :
1. Capturer des screenshots du kill feed pendant un match
2. Identifier les icônes d'armes visibles
3. Corréler avec les kills extraits des highlight events
4. Créer un mapping icône → arme

**Blocages** :
- Nécessite capture manuelle de screenshots
- Corrélation visuelle requise

---

### Phase 3 : Extraction Film Chunks

**Statut** : ✅ Weapon IDs trouvés dans chunks type 3

**Découvertes** :
- Weapon IDs dans bytes 74-75 (offset 72+2/72+3)
- Format : uint16 little-endian
- 2 weapon IDs confirmés :
  - `0xE02E` (57390) = Sidekick
  - `0x7017` (28695) = MA40 AR

**Scripts existants** :
- `scripts/extract_events_v3.py` : Extraction events depuis chunks type 3
- `scripts/analyze_chunks_bitshifted.py` : Analyse bit-shifted
- `src/data/weapon_ids.py` : Mapping weapon IDs

**Actions nécessaires** :
- Analyser plus de matchs pour identifier d'autres weapon IDs
- Chercher des patterns dans les extra bytes qui pourraient être des icon IDs
- Comparer avec les icônes visibles dans le kill feed

---

### Phase 4 : Exploration API Non Documentée

**Statut** : 🟡 Structure inspectée, endpoints hypothétiques identifiés

**Découvertes** :
- Structure complète des stats JSON inspectée
- Aucun champ `weapon` ou `icon` trouvé dans les stats
- Endpoints hypothétiques identifiés :
  - `/hi/matches/{matchId}/killfeed`
  - `/hi/matches/{matchId}/events`
  - `/hi/matches/{matchId}/weapons`

**Actions nécessaires** :
- Tester les endpoints hypothétiques (nécessite accès HTTP direct)
- Inspecter les réponses complètes pour champs cachés

**Blocages** :
- Endpoints hypothétiques peuvent ne pas exister
- Nécessite accès direct au client HTTP SPNKr

---

### Phase 5 : Theatre Mode

**Statut** : 🟡 Exploration initiale

**Découvertes** :
- Méthodes SPNKr film disponibles identifiées
- Endpoint manifest : `/hi/films/matches/{matchId}/spectate`
- Chunks type 1 (bootstrap) à analyser

**Actions nécessaires** :
1. Analyser les chunks type 1 (bootstrap) pour données kill feed
2. Explorer comment le Theatre Mode génère le kill feed
3. Chercher des endpoints API spécifiques au Theatre Mode

**Scripts existants** :
- `scripts/refetch_film_roster.py` : Téléchargement chunks
- `scripts/extract_events_v3.py` : Extraction events

---

## Prochaines Étapes Prioritaires

### Court Terme (1-2 jours)

1. **Analyser plus de matchs** pour identifier d'autres weapon IDs
   - Utiliser `scripts/extract_events_v3.py` sur plusieurs matchs
   - Compiler une liste complète des weapon IDs

2. **Tester les types Discovery UGC hypothétiques**
   - Trouver des weapon IDs depuis les matchs
   - Essayer de les utiliser comme asset_id dans `get_asset()`

3. **Analyser les extra bytes** pour patterns icon IDs
   - Comparer les bytes 72+ avec les weapon IDs connus
   - Chercher des corrélations

### Moyen Terme (1 semaine)

4. **Capture et corrélation visuelle**
   - Capturer des screenshots du kill feed
   - Identifier les icônes d'armes visibles
   - Corréler avec les kills extraits

5. **Exploration Theatre Mode**
   - Analyser les chunks type 1 (bootstrap)
   - Chercher des données kill feed dans le bootstrap

### Long Terme (si nécessaire)

6. **Reverse engineering du kill feed**
   - Analyser comment le jeu génère le kill feed
   - Identifier les sources de données

---

## Limitations Connues

| Limitation | Impact | Workaround |
|-----------|--------|------------|
| Pas d'endpoint Discovery UGC listing | Impossible de lister les assets | Utiliser des IDs connus |
| Pas de champ weapon dans events JSON | Impossible d'extraire directement | Analyser les bytes bruts |
| Kill feed visuel nécessite capture manuelle | Corrélation difficile | Screenshots + analyse manuelle |
| Endpoints hypothétiques non testés | Incertitude sur leur existence | Tests directs nécessaires |

---

## Références

- [Den Delimarsky - Film Files](https://den.dev/blog/extracting-stats-film-files-halo-infinite/)
- [SPNKr Documentation](https://github.com/OpenSpartan/grunt)
- [Halo Infinite API Discovery](https://github.com/OpenSpartan/grunt/blob/main/docs/discovery.md)
- `.ai/research/BINARY_CHUNK_ANALYSIS_V2_PLAN.md` : Investigation précédente
- `.ai/research/KILL_FEED_WEAPON_INVESTIGATION.md` : Plan d'investigation

---

## Commandes Utiles

```bash
# Investigation complète
python scripts/investigate_killfeed_weapons.py --match-id <ID> --phase all --output results.json

# Phase spécifique
python scripts/investigate_killfeed_weapons.py --match-id <ID> --phase 3

# Exploration assets
python scripts/investigate_killfeed_weapons.py --explore-assets

# Extraction events depuis chunks
python scripts/extract_events_v3.py --match-id <ID> --output events.json

# Obtenir un match ID
python scripts/get_match_id.py --gamertag <GAMERTAG> --limit 5
```

**Note** : Voir `.ai/research/KILL_FEED_EXECUTION_GUIDE.md` pour un guide complet d'exécution.

---

**Dernière mise à jour** : 2026-02-03
