# Limites de l'API Halo Infinite

> **Dernière vérification** : 2026-02-02
> **Statut** : Documenté et confirmé

Ce fichier documente les limitations connues de l'API Halo Infinite pour éviter de perdre du temps sur des fonctionnalités impossibles.

---

## ❌ Fonctionnalités NON DISPONIBLES

### 1. Statistiques par arme (Weapon Breakdowns)

| Donnée | Disponible | Notes |
|--------|------------|-------|
| Kills par type d'arme | ❌ | `Breakdowns.Weapons[]` n'existe pas |
| Précision par arme | ❌ | Non exposé |
| Headshots par arme | ❌ | Non exposé |
| Dégâts par arme | ❌ | Non exposé |
| Kill individuel → arme | ❌ | Impossible |

**Note** : Certains scripts du projet référencent `CoreStats.Breakdowns.Weapons[]` mais cette structure **n'existe pas** dans les réponses API réelles. Ces scripts ont été créés en anticipation d'une fonctionnalité qui n'a jamais été exposée.

### 2. Film Chunks (Theatre)

| Donnée | Disponible | Notes |
|--------|------------|-------|
| Identification d'armes | ❌ | WID ne correspond pas à l'arme réelle |
| Liste complète des kills | ❌ | Échantillon ~10-20% seulement |
| Détection killer/victime | ❌ | Faux positifs fréquents |

**Référence** : `.ai/archive/BINARY_CHUNK_ANALYSIS_FINAL.md`

---

## ✅ Fonctionnalités DISPONIBLES

### Match Stats API

```
Endpoint: /hi/matches/{matchId}/stats
```

| Donnée | Disponible | Champ |
|--------|------------|-------|
| Kills total | ✅ | `CoreStats.Kills` |
| Deaths total | ✅ | `CoreStats.Deaths` |
| Assists | ✅ | `CoreStats.Assists` |
| Headshots (total) | ✅ | `CoreStats.HeadshotKills` |
| Melee kills (total) | ✅ | `CoreStats.MeleeKills` |
| Grenade kills (total) | ✅ | `CoreStats.GrenadeKills` |
| Power weapon kills (total) | ✅ | `CoreStats.PowerWeaponKills` |
| Précision globale | ✅ | `CoreStats.Accuracy` |
| Dégâts totaux | ✅ | `CoreStats.DamageDealt` |
| Médailles | ✅ | `CoreStats.Medals[]` |

### Service Record API

```
Endpoint: /hi/players/{xuid}/matchmade/servicerecord
```

Mêmes champs que Match Stats, agrégés sur tous les matchs.

### Medals API

Certaines médailles indiquent indirectement le type d'arme :
- **Ninja** → Épée (kill par derrière)
- **Splatter** → Véhicule
- **Beatdown** → Mêlée
- **Sharpshooter** → Arme de précision (headshot)

---

## Scripts de vérification

Ces scripts ont été créés pour tester les limites :

| Script | Usage |
|--------|-------|
| `scripts/find_match_with_weapons.py` | Cherche des matchs avec Breakdowns.Weapons (aucun trouvé) |
| `scripts/check_service_record_v2.py` | Vérifie la structure du Service Record |
| `scripts/debug_match_raw.py` | Dump JSON brut d'un match |

---

## Références

- Blog Den Delimarsky : https://den.dev/blog/halo-api-match-stats/
- Investigation chunks : `.ai/archive/BINARY_CHUNK_ANALYSIS_FINAL.md`

---

*Dernière mise à jour : 2026-02-02*
