# Sprint 0 — Baseline State (pré-v5 Migration)

> **Date** : 2026-02-14  
> **Branche** : `sprint14/isolation-backend-frontend`  
> **Tests** : 1372 passed, 1 failed (pré-existant), 38 skipped  

---

## Résumé de l'Audit

### Joueurs Trackés

| Joueur | Matchs DB | Archives | Total | Taille DB | Période |
|--------|-----------|----------|-------|-----------|---------|
| Chocoboflor | 241 | 0 | 241 | 64.76 MB | 2023-12 → 2026-02 |
| JGtm | 518 | 17 | 535 | 73.76 MB | 2021-11 → 2026-02 |
| Madina97294 | 971 | 545 | 1516 | 115.76 MB | 2021-11 → 2026-02 |
| XxDaemonGamerxX | 18 | 0 | 18 | 8.01 MB | 2025-10 → 2026-01 |
| **Total** | **1748** | **562** | **2310** | **262.29 MB** | - |

### Taux de Partage de Matchs

- **Matchs uniques** : 1289
- **Matchs dupliqués** : 459 (26.3% de duplication)
- **XxDaemonGamerxX** : 100% de ses matchs partagés avec d'autres
- **Chocoboflor ↔ JGtm** : 161 matchs communs (66.8% de Chocoboflor)
- **JGtm ↔ Madina97294** : 275 matchs communs (53.1% de JGtm)

### Distribution

| Présent dans N DBs | Matchs | % |
|--------------------|--------|---|
| 1 (unique) | 1004 | 77.9% |
| 2 joueurs | 129 | 10.0% |
| 3 joueurs | 138 | 10.7% |
| 4 joueurs | 18 | 1.4% |

### Gains Estimés (shared_matches.duckdb)

- **Stockage match_stats** : -26.3% (1748 → 1289 lignes)
- **Appels API** : -26.3% (1 fetch par match unique au lieu de N)
- **highlight_events** : 716 352 lignes totales → réduction ~26%
- **match_participants** : 26 011 lignes totales → réduction ~26%

### Tables par DB Joueur (schéma actuel)

Chaque `stats.duckdb` contient ~21 tables :
- `match_stats` (table centrale, 1 ligne par match)
- `medals_earned` (médailles du joueur uniquement)
- `highlight_events` (tous les events du match, fortement dupliqué)
- `match_participants` (roster complet du match, fortement dupliqué)
- `killer_victim_pairs` (paires killer/victim)
- `antagonists` (agrégat rivalités)
- `teammates_aggregate` (agrégat coéquipiers)
- `sessions` (sessions de jeu)
- `xuid_aliases` (mapping xuid→gamertag)
- `media_files`, `media_match_associations`
- `mv_*` (vues matérialisées)
- Autres : `personal_score_awards`, `player_match_stats`, `sync_meta`, etc.

### Test echec pré-existant

- `test_cache_loaders_under_800_lines` : `cache_loaders.py` fait 838 lignes (cible < 800)
- Ce test existait avant Sprint 0, ce n'est pas une régression.

---

## Livrables Sprint 0

- [x] `scripts/export_schemas.py` — Export schémas SQL complets
- [x] `scripts/audit_current_data.py` — Audit des données & stats
- [x] `scripts/analyze_match_overlap.py` — Analyse partage de matchs  
- [x] `scripts/validate_migration.py` — Validation post-migration (prêt)
- [x] `.ai/v5-schemas-export.md` — Schémas exportés
- [x] `.ai/v5-baseline-audit.md` — Audit baseline complet
- [x] `.ai/v5-baseline-audit.json` — Données JSON pour comparaison future
- [x] `.ai/v5-match-overlap-analysis.md` — Analyse du partage
- [x] `.ai/v5-baseline-state.md` — Ce fichier

---

## Actions Git à Effectuer (par l'utilisateur)

```bash
# 1. Créer la branche v5
git checkout sprint14/isolation-backend-frontend
git checkout -b v5/shared-matches-migration

# 2. Committer les livrables Sprint 0
git add scripts/export_schemas.py scripts/audit_current_data.py \
        scripts/analyze_match_overlap.py scripts/validate_migration.py \
        .ai/v5-baseline-state.md .ai/v5-baseline-audit.md \
        .ai/v5-baseline-audit.json .ai/v5-match-overlap-analysis.md \
        .ai/v5-schemas-export.md
git commit -m "chore(v5): sprint 0 — audit baseline et scripts de validation"

# 3. Tagger le commit de référence
git tag pre-v5-migration

# 4. Backup des DBs (recommandé)
python scripts/backup_player.py --all --output backups/pre-v5-migration
```

---

## Prochaine Étape : Sprint 1

Créer `data/warehouse/shared_matches.duckdb` avec le schéma cible :
- `match_registry` — Registre central
- `match_participants` — Roster global
- `highlight_events` — Events globaux
- `medals_earned` — Médailles tous joueurs
- `xuid_aliases` — Mapping global
