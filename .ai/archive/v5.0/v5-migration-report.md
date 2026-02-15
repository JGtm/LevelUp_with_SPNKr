# Rapport de Migration v5 — Sprint 2

> **Date** : 2026-02-14
> **Durée** : ~2h effectives (incluant débogage FK DuckDB)
> **Statut** : ✅ TERMINÉ

---

## Résumé Exécutif

Migration réussie des 4 joueurs vers `data/warehouse/shared_matches.duckdb`.
VIEWs de compatibilité créées dans chaque DB joueur.
25/25 tests passent.

---

## Données Migrées

| Table              |    Lignes |
|--------------------|----------:|
| match_registry     |     1 289 |
| match_participants |    21 976 |
| highlight_events   |   521 991 |
| medals_earned      |     7 162 |
| xuid_aliases       |    13 955 |

### Par Joueur

| Joueur           | Matchs nouveaux | Matchs existants | Participants | Events  | Médailles |
|------------------|----------------:|-----------------:|-------------:|--------:|----------:|
| Chocoboflor      |             241 |                0 |        2 049 | 167 858 |       502 |
| Madina97294      |             810 |              161 |       17 636 | 276 180 |     5 056 |
| JGtm             |             238 |              280 |        2 291 |  77 953 |     1 584 |
| XxDaemonGamerxX  |               0 |               18 |            0 |       0 |        20 |
| **Total**        |       **1 289** |        **459**   |   **21 976** |**521 991**| **7 162**|

### Distribution player_count

| player_count | Matchs | % du total |
|-------------:|-------:|-----------:|
|            1 |  1 004 |      77.9% |
|            2 |    129 |      10.0% |
|            3 |    138 |      10.7% |
|            4 |     18 |       1.4% |

**Taux de partage** : 285 matchs partagés sur 1 289 = **22.1%**

---

## Intégrité

- ✅ 0 participants orphelins (sans match_registry correspondant)
- ✅ 0 médailles orphelines
- ✅ 0 événements orphelins
- ✅ VIEWs de compatibilité fonctionnelles (20/20)

---

## VIEWs de Compatibilité

Créées dans chaque DB joueur :
- `v_match_stats` : Reconstruit match_stats depuis shared + player_match_enrichment
- `v_medals_earned` : Médailles filtrées par xuid du joueur
- `v_highlight_events` : Événements avec xuid/gamertag reconstruits
- `v_match_participants` : Tous les participants depuis shared

Table `player_match_enrichment` créée et peuplée pour chaque joueur
(performance_score, session_id, is_with_friends restent locaux).

---

## Décisions Techniques

### 1. Suppression des FK Constraints DuckDB

**Problème** : DuckDB 1.4.4 traite `UPDATE` comme `DELETE+INSERT` en interne.
Quand la table parent (`match_registry`) est référencée par des FK depuis
`match_participants`, `medals_earned` et `highlight_events`, l'UPDATE de
`player_count` échoue avec `ConstraintException`.

De plus, `ALTER TABLE DROP CONSTRAINT` n'est pas implémenté dans DuckDB 1.4.4.

**Décision** : Supprimer les FK contraintes du schéma v5. DuckDB étant un moteur
OLAP, les FK n'apportent pas d'optimisation de requêtes et l'intégrité
référentielle est assurée par la logique de migration.

**Impact** : Aucun — les FK logiques sont documentées en commentaires SQL.

### 2. Filtrage DataFrame vs reconstruction dict

**Problème** : La conversion `iter_rows(named=True)` → `pl.DataFrame(list_of_dicts)`
provoquait une erreur de type (`i64` au lieu de `i16` pour les scores) car
Polars infère Int64 par défaut pour les entiers Python.

**Décision** : Filtrer le DataFrame original avec `pl.col("match_id").is_in()`
au lieu de reconstruire depuis des dicts. Préserve les types DuckDB d'origine.

### 3. Recalcul post-migration des player_counts

Fonction `recalculate_player_counts()` ajoutée pour recalculer les player_count
à la fin de la migration, en lisant les match_stats de chaque joueur et en
comptant les occurrences de chaque match_id.

---

## Fichiers Créés/Modifiés

### Créés
- `scripts/migration/migrate_player_to_shared.py` (~1030 lignes)
- `scripts/migration/create_compat_views.py` (~346 lignes)
- `tests/migration/test_migration_integrity.py` (~1070 lignes, 25 tests)
- `.ai/v5-migration-report.md` (ce fichier)

### Modifiés
- `scripts/migration/schema_v5.sql` — FK constraints retirées (commentaires logiques)
- `src/data/sync/models.py` — Ajout `SharedMedalEarnedRow`
- `src/data/sync/transformers.py` — Ajout `extract_all_medals()`

---

## Prochaines Étapes (Sprint 3)

- [ ] Adapter `DuckDBRepository` pour lire depuis shared via ATTACH
- [ ] Adapter les sync pour écrire dans shared au lieu des DBs joueur
- [ ] Tests de non-régression sur l'UI Streamlit
