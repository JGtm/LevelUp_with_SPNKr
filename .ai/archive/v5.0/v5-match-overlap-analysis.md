# Analyse du Partage de Matchs — pré-v5 Migration

> Généré le 2026-02-14 17:34:01

---

## Objectif

Quantifier le taux de partage de matchs entre joueurs pour valider
l'architecture `shared_matches.duckdb` et estimer les gains.

---

## Matchs par Joueur

| Joueur | Matchs DB | Match IDs |
|--------|-----------|-----------|
| Chocoboflor | 241 | 241 uniques |
| JGtm | 518 | 518 uniques |
| Madina97294 | 971 | 971 uniques |
| XxDaemonGamerxX | 18 | 18 uniques |

## Statistiques Globales

- **Total matchs (somme brute)** : 1748
- **Matchs uniques (dédupliqués)** : 1289
- **Matchs dupliqués** : 459 (26.3%)
- **Joueurs trackés** : 4

## Matrice de Partage (Paires)

| Joueur A | Joueur B | Matchs Communs | % de A | % de B | Uniques A | Uniques B |
|----------|----------|----------------|--------|--------|-----------|-----------|
| Chocoboflor | JGtm | **161** | 66.8% | 31.1% | 80 | 357 |
| Chocoboflor | Madina97294 | **161** | 66.8% | 16.6% | 80 | 810 |
| Chocoboflor | XxDaemonGamerxX | **18** | 7.5% | 100.0% | 223 | 0 |
| JGtm | Madina97294 | **275** | 53.1% | 28.3% | 243 | 696 |
| JGtm | XxDaemonGamerxX | **18** | 3.5% | 100.0% | 500 | 0 |
| Madina97294 | XxDaemonGamerxX | **18** | 1.9% | 100.0% | 953 | 0 |

## Estimation des Gains avec shared_matches.duckdb

### Stockage

- Avant : 1748 lignes match_stats réparties sur 4 DBs
- Après : 1289 lignes dans match_registry (shared)
- **Réduction match_stats** : -26.3%

### Tables Associées (estimation)

| Table | Lignes Totales (somme DBs) | Est. Réduction |
|-------|---------------------------|----------------|
| highlight_events | 716352 | ~26% |
| medals_earned | 7162 | ~26% |
| match_participants | 26011 | ~26% |
| killer_victim_pairs | 259689 | ~26% |

### Appels API

- Matchs actuellement sync 1x chacun par joueur : 1748 appels
- Avec partage : 1289 appels (1 seul fetch par match)
- **Réduction appels API** : -26.3%

## Distribution de la Duplication

| Nombre de DBs contenant le match | Nombre de matchs | % |
|----------------------------------|------------------|---|
| 1 (unique) | 1004 | 77.9% |
| 2 (partagé entre 2 joueurs) | 129 | 10.0% |
| 3 (partagé entre 3 joueurs) | 138 | 10.7% |
| 4 (partagé entre 4 joueurs) | 18 | 1.4% |
