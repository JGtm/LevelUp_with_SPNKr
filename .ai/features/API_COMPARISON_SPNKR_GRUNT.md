# Comparaison SPNKr vs Grunt API

> **Date** : 2026-02-01
> **Contexte** : Analyse préliminaire avant Phase 5 pour évaluer quelle API utiliser
> **Statut** : Draft - À compléter avec tests réels

---

## 1. Vue d'Ensemble

| Critère | SPNKr | Grunt |
|---------|-------|-------|
| **Langage** | Python | C# (.NET) |
| **Package** | PyPI (`spnkr`) | NuGet (`Den.Dev.Grunt`) |
| **Version actuelle** | 0.9.6 (juillet 2025) | Variable |
| **Mainteneur** | acurtis166 | Den Delimarsky (den.dev) |
| **Licence** | MIT | MIT |
| **Documentation** | acurtis166.github.io/SPNKr | docs.gruntapi.com |
| **Repo GitHub** | Public | Public (github.com/dend/grunt) |

---

## 2. Compatibilité Technique

### 2.1 Intégration avec notre stack

| Aspect | SPNKr | Grunt |
|--------|-------|-------|
| **Langage du projet** | ✅ Python (natif) | ⚠️ C# (nécessite bridge) |
| **Async** | ✅ `asyncio` natif | ✅ `async/await` C# |
| **Pydantic models** | ✅ Intégré | ❌ Non (modèles C#) |
| **Intégration actuelle** | ✅ Déjà utilisé | ❌ À implémenter |

**Verdict** : SPNKr a un avantage majeur car notre projet est en Python. Utiliser Grunt nécessiterait soit :
- Un subprocess vers un binaire .NET
- Un service HTTP intermédiaire
- Python.NET (complexité)

### 2.2 Dépendances

**SPNKr** :
```
aiohttp>=3.8
aiolimiter>=1.1
pydantic>=2.0
bitstring>=4.0
```

**Grunt** :
```
.NET 6.0+
Microsoft.Extensions.Http
System.Text.Json
```

---

## 3. Endpoints Disponibles

### 3.1 Comparaison par Catégorie

| Endpoint | SPNKr | Grunt | Notes |
|----------|-------|-------|-------|
| **Match History** | ✅ `stats.get_match_history()` | ✅ | Identique |
| **Match Stats** | ✅ `stats.get_match_stats()` | ✅ | Identique |
| **Match Skill/MMR** | ✅ `skill.get_match_skill()` | ✅ | Identique |
| **Playlist CSR** | ✅ `skill.get_playlist_csr()` | ✅ | Identique |
| **Player Customization** | ✅ `economy.get_player_customization()` | ✅ | Identique |
| **Career Rank Progression** | ⚠️ Non documenté | ✅ Documenté | Grunt a un endpoint dédié |
| **Career Rank Metadata** | ✅ `gamecms_hacs.get_career_reward_track()` | ✅ | Identique |
| **Film/Highlight Events** | ✅ `film.read_highlight_events()` | ❓ Non documenté | SPNKr a du code dédié |
| **UGC Assets (Maps)** | ✅ `discovery_ugc.get_map()` | ✅ | Identique |
| **UGC Assets (Playlists)** | ✅ `discovery_ugc.get_playlist()` | ✅ | Identique |
| **UGC Assets (Variants)** | ✅ `discovery_ugc.get_ugc_game_variant()` | ✅ | Identique |
| **Images** | ✅ `gamecms_hacs.get_image()` | ✅ | Identique |
| **Inventory Items** | ⚠️ Partiel | ✅ `GameCmsGetItem()` | Grunt plus complet |
| **Medals Metadata** | ✅ `gamecms_hacs.get_medal_metadata()` | ✅ | Identique |
| **Weapon Stats** | ❓ Non trouvé | ❓ Non documenté | À investiguer |
| **Service Record** | ❓ Non documenté | ✅ | Grunt semble avoir plus |

### 3.2 Endpoints Critiques pour notre Projet

| Fonctionnalité | Importance | SPNKr | Grunt | Verdict |
|---------------|------------|-------|-------|---------|
| Match History | Critique | ✅ | ✅ | Équivalent |
| Match Stats | Critique | ✅ | ✅ | Équivalent |
| MMR/Skill | Haute | ✅ | ✅ | Équivalent |
| Highlight Events | Haute | ✅ | ❓ | **SPNKr gagne** |
| Career Rank | Moyenne | ⚠️ | ✅ | **Grunt gagne** |
| Weapon Stats | Moyenne | ❓ | ❓ | À tester |
| Service Record | Moyenne | ❓ | ✅ | **Grunt gagne** |

---

## 4. Stabilité et Fiabilité

### 4.1 Historique de Maintenance

| Métrique | SPNKr | Grunt |
|----------|-------|-------|
| **Commits (2025)** | ~20+ | ~30+ (estimé) |
| **Dernière release** | Juillet 2025 | Variable |
| **Issues ouvertes** | < 5 | < 10 |
| **Réactivité mainteneur** | Bonne | Excellente |

### 4.2 Gestion des Erreurs

**SPNKr** :
```python
# Retry automatique configurable
from spnkr import HaloInfiniteClient

# Rate limiting intégré via aiolimiter
client = HaloInfiniteClient(session, tokens, rate_limit=5.0)
```

**Grunt** :
```csharp
// Gestion d'erreurs robuste (source: openspartan-workshop)
var result = await SafeAPICall(async () => await HaloClient.StatsGetMatchStats(matchId));
```

### 4.3 Problèmes Connus

**SPNKr** :
- ⚠️ API non-officielle : peut casser sans préavis
- ⚠️ Tokens expirent (durée ~4h pour Spartan, ~1h pour Clearance)
- ✅ Refresh automatique si Azure App configurée

**Grunt** :
- ⚠️ Même limitation (API non-officielle)
- ⚠️ Même expiration de tokens
- ✅ Refresh automatique intégré

---

## 5. Authentification

### 5.1 Méthodes Supportées

| Méthode | SPNKr | Grunt |
|---------|-------|-------|
| **Tokens manuels** | ✅ | ✅ |
| **Azure App OAuth** | ✅ `refresh_player_tokens()` | ✅ |
| **Refresh automatique** | ✅ | ✅ |
| **Multi-compte** | ❓ Non testé | ✅ |

### 5.2 Implémentation Actuelle (Notre Projet)

```python
# scripts/spnkr_import_db.py - Lignes 412-470
# Supporte :
# 1. Tokens manuels (env vars SPNKR_SPARTAN_TOKEN, SPNKR_CLEARANCE_TOKEN)
# 2. Azure OAuth avec refresh_token

from spnkr import AzureApp, refresh_player_tokens
from spnkr.auth.halo import request_spartan_token, request_clearance_token
```

---

## 6. Performance

### 6.1 Benchmarks Estimés

| Opération | SPNKr | Grunt | Notes |
|-----------|-------|-------|-------|
| Match History (25) | ~200-400ms | ~200-400ms | Réseau-bound |
| Match Stats | ~100-200ms | ~100-200ms | Réseau-bound |
| Skill Stats | ~100-200ms | ~100-200ms | Réseau-bound |
| Film/Events | ~500-2000ms | ❓ | Dépend chunks |

### 6.2 Rate Limiting

| API | Limite Connue | SPNKr | Grunt |
|-----|--------------|-------|-------|
| Stats | ~5-10 req/s | ✅ Configurable | ✅ |
| Skill | ~5-10 req/s | ✅ | ✅ |
| Economy | ~5 req/s | ✅ | ✅ |
| Discovery | ~10 req/s | ✅ | ✅ |

---

## 7. Données Disponibles

### 7.1 Champs Match Stats

Les deux APIs retournent les mêmes données car elles appellent les mêmes endpoints Waypoint.

| Catégorie | Champs |
|-----------|--------|
| **Match Info** | MatchId, StartTime, Duration, Playlist, Map, GameVariant |
| **Player Stats** | Kills, Deaths, Assists, Damage, Accuracy, Headshots |
| **Team Stats** | TeamId, Outcome, TeamScore |
| **Medals** | MedalId, Count, MedalType |
| **Objectives** | FlagCaptures, Strongholds, OddballTime, etc. |

### 7.2 Champs Skill/MMR

| Champ | Disponible |
|-------|------------|
| TeamMMR | ✅ |
| EnemyMMR | ✅ |
| KillsExpected | ✅ |
| KillsStdDev | ✅ |
| DeathsExpected | ✅ |
| DeathsStdDev | ✅ |
| PlaylistCSR | ✅ |
| CSRTier | ✅ |

### 7.3 Données Exclusives (Non Confirmées)

| Donnée | SPNKr | Grunt | Source |
|--------|-------|-------|--------|
| **Weapon Details** | ❓ | ❓ | weapon_core dans match stats |
| **Service Record** | ❓ | ✅ | Grunt endpoint dédié |
| **Progression XP** | ❓ | ✅ | career rank endpoint |
| **Inventory Details** | ⚠️ | ✅ | Grunt plus complet |

---

## 8. Effort d'Intégration

### 8.1 SPNKr (Déjà Intégré)

| Tâche | Effort | Statut |
|-------|--------|--------|
| Installation | 0 | ✅ Fait |
| Auth | 0 | ✅ Fait |
| Match Import | 0 | ✅ Fait (~1400 lignes) |
| Refactoring DuckDB | Moyen | ⏳ Sprint 4.7 |

**Total** : ~0 effort additionnel (refactoring planifié)

### 8.2 Grunt (Nouvelle Intégration)

| Tâche | Effort | Notes |
|-------|--------|-------|
| Bridge Python → .NET | Élevé | subprocess ou Python.NET |
| Réécriture auth | Moyen | Tokens similaires |
| Réécriture import | Élevé | ~1500 lignes à porter |
| Tests | Moyen | Nouveaux tests |
| Documentation | Faible | Adapter docs existantes |

**Total** : ~2-3 semaines de travail

---

## 9. Recommandation

### 9.1 Verdict Global

| Critère | Poids | SPNKr | Grunt | Gagnant |
|---------|-------|-------|-------|---------|
| Compatibilité Stack | 30% | ⭐⭐⭐⭐⭐ | ⭐⭐ | SPNKr |
| Endpoints Disponibles | 25% | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Grunt |
| Stabilité | 15% | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Grunt |
| Effort Intégration | 20% | ⭐⭐⭐⭐⭐ | ⭐⭐ | SPNKr |
| Documentation | 10% | ⭐⭐⭐ | ⭐⭐⭐⭐ | Grunt |

**Score Pondéré** :
- SPNKr : 4.15 / 5
- Grunt : 3.45 / 5

### 9.2 Recommandation Finale

**Continuer avec SPNKr** pour les raisons suivantes :

1. **Déjà intégré** : ~1400 lignes de code fonctionnel
2. **Python natif** : Pas de bridge complexe à maintenir
3. **Highlight Events** : Fonctionnalité critique disponible
4. **Refactoring en cours** : Sprint 4.7 optimise déjà SPNKr → DuckDB

**Considérer Grunt pour** :
- Career Rank progression (endpoint dédié)
- Service Record global
- Inventory details avancés

### 9.3 Stratégie Hybride (Future)

Pour Phase 5, envisager une approche hybride :

```
SPNKr (Python) ─────────────► DuckDB
  ├── Match History
  ├── Match Stats
  ├── Skill/MMR
  └── Highlight Events

Grunt (Bridge) ─────────────► DuckDB
  ├── Career Rank Progression
  ├── Service Record
  └── Weapon Stats (si disponible)
```

**Bridge minimal** : Créer un script .NET standalone appelé via subprocess pour les 2-3 endpoints manquants.

---

## 10. Tests à Réaliser (Phase 5)

### 10.1 Validation SPNKr

| Test | Objectif | Priorité |
|------|----------|----------|
| Fetch 1000 matchs | Stabilité long-run | P0 |
| Rate limit 10 req/s | Limites API | P0 |
| Token refresh 24h | Durabilité | P1 |
| Erreurs réseau | Retry robuste | P1 |

### 10.2 Exploration Grunt

| Test | Objectif | Priorité |
|------|----------|----------|
| Career Rank via bridge | Faisabilité | P1 |
| Service Record content | Données utiles ? | P2 |
| Weapon Stats existence | Endpoint existe ? | P2 |

---

## 11. Métriques de Décision Finale

À collecter pendant les tests Phase 5 :

| Métrique | Cible | Mesure |
|----------|-------|--------|
| Taux d'erreurs API | < 1% | Logs sync |
| Latence moyenne | < 300ms | Benchmarks |
| Tokens refresh OK | 100% | Logs auth |
| Données manquantes | < 5% | Comparaison HaloWaypoint |

---

## 12. Conclusion

**SPNKr reste le choix principal** pour la synchronisation car :
- Intégration native Python
- Fonctionnalités critiques couvertes
- Effort d'intégration Grunt trop élevé pour les gains limités

**Grunt en complément** possible pour :
- Career Rank progression (si demandé par l'utilisateur)
- Données non disponibles via SPNKr

La Phase 5 devrait se concentrer sur l'optimisation de SPNKr via `DuckDBSyncEngine` (Sprint 4.7) plutôt que sur une migration vers Grunt.

---

## 13. Endpoints Grunt à Porter en Python

### 13.1 Endpoints Intéressants Identifiés

Après analyse du code source de Grunt (`HaloInfiniteClient.cs`), voici les endpoints absents ou partiels dans SPNKr :

| Endpoint | Grunt Method | Intérêt | Effort |
|----------|--------------|---------|--------|
| **Career Rank Progression** | `EconomyGetRewardTrack()` | Progression XP joueur | Faible |
| **Service Record** | Non trouvé directement | Stats globales | Moyen |
| **Match Count** | `StatsGetMatchCount()` | Nombre total de matchs | Faible |
| **Player Inventory** | `EconomyGetInventoryItems()` | Items possédés | Faible |
| **Virtual Currencies** | `EconomyGetVirtualCurrencyBalances()` | Crédits, points | Faible |
| **Clearance/Flight** | `SettingsGetPlayerClearance()` | ID clearance joueur | Faible |
| **Film Chunks** | `HIUGCDiscoverySpectateByMatchId()` | **Métadonnées films** | Moyen |

### 13.2 Highlight Events : Analyse Détaillée

**SPNKr a déjà implémenté le parsing des film files** via le module `spnkr.film`.

**Source** : Blog de Den Delimarsky ([Extracting Match Stats From Halo Infinite Film Files](https://den.dev/blog/extracting-stats-film-files-halo-infinite))

**Comment ça fonctionne** :

1. **Récupérer les chunks** :
   ```
   GET https://discovery-infiniteugc.svc.halowaypoint.com/hi/films/matches/{matchId}/spectate
   ```

2. **Télécharger chaque chunk** :
   ```
   GET {BlobStoragePathPrefix}/filmChunk{N}
   ```

3. **Décompresser** (zlib) :
   ```python
   import zlib
   decompressed = zlib.decompress(chunk_data)
   ```

4. **Parser les events** :
   - ChunkType 1 : Bootstrap (gamertags + XUIDs)
   - ChunkType 2 : Events in-game (positions, mouvements)
   - ChunkType 3 : **Summary (kills, deaths, medals)**

**Structure d'un event** (ChunkType 3) :
| Offset | Taille | Contenu |
|--------|--------|---------|
| 0 | 12 bytes | Header |
| 12 | 32 bytes | Gamertag (Unicode) |
| 44 | 15 bytes | Padding |
| 59 | 1 byte | **Type** (10=objectif, 20=death, 50=kill) |
| 60 | 4 bytes | **Timestamp** (ms) |
| 64 | 3 bytes | Padding |
| 67 | 1 byte | Medal marker |
| 68 | 3 bytes | Padding |
| 71 | 1 byte | **Medal ID** |

**SPNKr implémente déjà** :
- `film.read_highlight_events()` : Parse les events
- `medal_codes.json` : Mapping des 150+ medals

**Ce qui manque potentiellement** :
- Heatmaps de positions (données dans chunks type 2)
- Tracking des assists (non encore parsé)
- Weapon switches (nécessite reverse-engineering)

### 13.3 Endpoints Faciles à Porter

**1. Career Rank Progression** (Haute priorité)

```python
# Nouveau endpoint pour SPNKr ou notre code
async def get_career_rank_progression(self, xuid: str) -> dict:
    """Récupère la progression de rang carrière."""
    url = f"https://economy.svc.halowaypoint.com/hi/players/xuid({xuid})/rewardtracks/careerranks/careerrank1"
    return await self._get(url)
```

**2. Match Count** (Faible priorité)

```python
async def get_match_count(self, xuid: str) -> dict:
    """Récupère le nombre total de matchs."""
    url = f"https://halostats.svc.halowaypoint.com/hi/players/xuid({xuid})/matches/count"
    return await self._get(url)
```

**3. Player Inventory** (Moyenne priorité)

```python
async def get_player_inventory(self, xuid: str) -> dict:
    """Récupère l'inventaire du joueur."""
    url = f"https://economy.svc.halowaypoint.com/hi/players/xuid({xuid})/inventory"
    return await self._get(url)
```

### 13.4 Recommandation : Extensions SPNKr

Plutôt que de créer un bridge Grunt, **étendre SPNKr** avec les endpoints manquants :

1. **Créer `src/data/sync/extended_api.py`** avec les endpoints additionnels
2. **Contribuer à SPNKr upstream** si possible (PR GitHub)
3. **Utiliser les mêmes tokens** (déjà gérés par notre code)

**Effort estimé** : 2-3 jours vs 2-3 semaines pour un bridge Grunt

---

## 14. Plan d'Action Révisé

### Option A : Extensions Python (Recommandée)

| Tâche | Fichier | Priorité | Effort |
|-------|---------|----------|--------|
| Career Rank endpoint | `src/data/sync/api_client.py` | P0 | 1 jour |
| Match Count endpoint | `src/data/sync/api_client.py` | P2 | 0.5 jour |
| Player Inventory endpoint | `src/data/sync/api_client.py` | P3 | 0.5 jour |
| Tests unitaires | `tests/test_extended_api.py` | P1 | 1 jour |

### Option B : Bridge Grunt Minimal

| Tâche | Fichier | Priorité | Effort |
|-------|---------|----------|--------|
| CLI .NET standalone | `scripts/grunt_cli/Program.cs` | P2 | 3 jours |
| Wrapper Python | `scripts/grunt_bridge.py` | P2 | 1 jour |
| Documentation | `docs/GRUNT_BRIDGE.md` | P3 | 0.5 jour |

**Verdict** : **Option A** est préférable car :
- Même stack Python
- Mêmes tokens, pas de double auth
- Maintenance simplifiée
- Contribution possible à SPNKr upstream

---

*Document généré le 2026-02-01 - Analyse préliminaire Phase 5*
*Mis à jour avec analyse du code source Grunt et endpoints à porter*
