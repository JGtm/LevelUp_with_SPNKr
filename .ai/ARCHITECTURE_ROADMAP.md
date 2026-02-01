# Roadmap Architecture - Simplification SQLite/DuckDB/Parquet

> Ce document trace l'évolution planifiée de l'architecture de données.

## État actuel (v1 - Transition)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARCHITECTURE v1 (actuelle)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   player.db (SQLite)                                                        │
│   ══════════════════                                                        │
│   ├── MatchStats ────────────► JSON brut (source de vérité)                │
│   ├── MatchCache ────────────► Dénormalisé (REDONDANT avec Parquet)        │
│   ├── TeammatesAggregate ───► Stats coéquipiers (unique)                   │
│   ├── MedalsAggregate ──────► Totaux médailles (unique)                    │
│   ├── Players ──────────────► Profils joueurs                              │
│   └── Friends ──────────────► Relations amis                               │
│                                                                             │
│   data/warehouse/                                                           │
│   ═══════════════                                                           │
│   ├── metadata.db ──────────► Référentiels (playlists, médailles)          │
│   └── match_facts/ ─────────► Parquet partitionné (REDONDANT avec Cache)   │
│                                                                             │
│   DuckDB (en mémoire)                                                       │
│   ═══════════════════                                                       │
│   └── Requêtes analytiques sur Parquet + SQLite                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Redondance : MatchCache ↔ match_facts/ (~même données, 2 formats)
```

---

## Phase 1 : Stabilisation (actuelle)

**Objectif** : Mise en prod stable avec architecture duale

**Actions** :
- [x] Tables de cache SQLite fonctionnelles
- [x] Migration Parquet automatique après sync
- [x] Fallback si Parquet indisponible
- [x] Tests de non-régression UI → `tests/test_hybrid_benchmark.py`
- [x] Benchmarks de performance documentés → `scripts/benchmark_hybrid.py`

**Outils de validation** :
```bash
# Benchmark CLI (génère rapport comparatif)
python scripts/benchmark_hybrid.py --db data/spnkr_gt_Chocoboflor.db --iterations 5

# Tests pytest (cohérence + performance)
pytest tests/test_hybrid_benchmark.py -v -s
```

**Critères de succès** :
- UI fonctionne en mode LEGACY et HYBRID
- Aucune régression fonctionnelle
- Performance mesurée et documentée

---

## Phase 2 : Validation Hybrid (post-prod)

**Objectif** : Valider que le mode HYBRID est équivalent au LEGACY

**Actions** :
- [ ] Activer mode `SHADOW_COMPARE` en dev
- [ ] Comparer résultats Legacy vs Hybrid sur 100% des requêtes
- [ ] Logger les divergences
- [ ] Corriger les écarts

**Critères de succès** :
- 0 divergence sur les requêtes critiques
- Performance Hybrid >= Legacy

---

## Phase 3 : Bascule Hybrid (v2)

**Objectif** : Utiliser Parquet/DuckDB comme source principale

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARCHITECTURE v2 (cible)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   player.db (SQLite) - ALLÉGÉ                                               │
│   ══════════════════════════                                                │
│   ├── MatchStats ────────────► JSON brut (source, write-only)              │
│   ├── TeammatesAggregate ───► Stats coéquipiers (gardé, rapide)            │
│   ├── Players ──────────────► Profils joueurs                              │
│   └── Friends ──────────────► Relations amis                               │
│                                                                             │
│   ❌ MatchCache ──────────────► SUPPRIMÉ (remplacé par Parquet)            │
│   ❌ MedalsAggregate ─────────► SUPPRIMÉ (calculé via DuckDB)              │
│                                                                             │
│   data/warehouse/                                                           │
│   ═══════════════                                                           │
│   ├── metadata.db ──────────► Référentiels                                 │
│   ├── match_facts/ ─────────► Parquet (SOURCE PRINCIPALE)                  │
│   └── medals/ ──────────────► Parquet (médailles par match)                │
│                                                                             │
│   DuckDB (en mémoire)                                                       │
│   ═══════════════════                                                       │
│   └── TOUTES les requêtes analytiques                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Gains :
• -50% espace disque (plus de duplication)
• Requêtes unifiées via DuckDB
• Maintenance simplifiée
```

**Actions** :
- [ ] Migrer les requêtes UI vers `load_df_hybrid()`
- [ ] Supprimer dépendances à `MatchCache` dans l'UI
- [ ] Supprimer table `MatchCache` du schéma
- [ ] Calculer médailles via DuckDB au lieu de `MedalsAggregate`

**Critères de succès** :
- UI fonctionne sans `MatchCache`
- Performance équivalente ou meilleure

---

## Phase 4 : Optimisations avancées (v3)

**Objectif** : Performance maximale

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARCHITECTURE v3 (optimisée)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   player.db (SQLite) - MINIMAL                                              │
│   ════════════════════════════                                              │
│   ├── MatchStats ────────────► Archive JSON (cold storage)                 │
│   ├── Players ──────────────► Profils                                      │
│   └── Friends ──────────────► Relations                                    │
│                                                                             │
│   data/warehouse/                                                           │
│   ═══════════════                                                           │
│   ├── metadata.db ──────────► Référentiels + TeammatesAggregate            │
│   ├── match_facts/ ─────────► Parquet + Delta Lake (incrémental)           │
│   └── medals/ ──────────────► Parquet                                      │
│                                                                             │
│   DuckDB (persisté optionnel)                                               │
│   ═══════════════════════════                                               │
│   └── Cache de requêtes matérialisées                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Options avancées :
• Delta Lake pour updates incrémentaux sans réécriture
• DuckDB persisté pour cache de vues matérialisées
• Compression Zstd pour Parquet (2x plus compact)
```

**Actions** :
- [ ] Évaluer Delta Lake vs Parquet pur
- [ ] Implémenter vues matérialisées DuckDB
- [ ] Migrer `TeammatesAggregate` vers metadata.db
- [ ] Archiver MatchStats (ne plus lire en runtime)

---

## Comparaison des phases

| Métrique | v1 (actuel) | v2 (cible) | v3 (optimisé) |
|----------|-------------|------------|---------------|
| Tables SQLite | 6 | 4 | 3 |
| Redondance | Oui | Non | Non |
| Espace disque | 100% | ~50% | ~40% |
| Complexité code | Moyenne | Faible | Faible |
| Requêtes unifiées | Non | Partiellement | Oui |

---

## Décisions architecturales

### Garder SQLite pour :
- **MatchStats** : Source de vérité, format JSON original de l'API
- **Players/Friends** : Petites tables relationnelles, mises à jour fréquentes
- **TeammatesAggregate** : Requêtes très fréquentes, index SQLite efficaces

### Utiliser Parquet/DuckDB pour :
- **match_facts** : Volume important, lectures analytiques
- **medals** : Agrégations fréquentes
- **Jointures cross-player** : DuckDB excelle sur ce use case

### Supprimer à terme :
- **MatchCache** : Redondant avec Parquet
- **MedalsAggregate** : Calculable via DuckDB sur `medals/`

---

## Plan d'Orchestration des Sprints

> Mis à jour le 2026-02-01

### Sprint 1 : Clôturer Phase 1 (Stabilisation)

**Statut** : ✅ Outils créés

| # | Tâche | Statut | Livrable |
|---|-------|--------|----------|
| 1.1 | Script benchmark CLI | ✅ | `scripts/benchmark_hybrid.py` |
| 1.2 | Tests E2E cohérence | ✅ | `tests/test_hybrid_benchmark.py` |
| 1.3 | Exécuter benchmarks en prod | ⏳ | `.ai/reports/benchmark_v1.md` |
| 1.4 | Documenter pain points | ⏳ | `thought_log.md` |

**Commandes** :
```bash
# Benchmark complet avec export JSON
python scripts/benchmark_hybrid.py --db data/spnkr_gt_Chocoboflor.db --output .ai/reports/benchmark_v1.json

# Tests unitaires
pytest tests/test_hybrid_benchmark.py -v
```

---

### Sprint 2 : Phase 2 - Validation Shadow Compare

**Statut** : 📋 Planifié

| # | Tâche | Statut | Livrable |
|---|-------|--------|----------|
| 2.1 | Activer SHADOW_COMPARE en dev | ⏳ | Config `app_settings.json` |
| 2.2 | Logger divergences Legacy/Hybrid | ⏳ | Logs structurés |
| 2.3 | Script comparaison automatisée | ⏳ | `scripts/compare_shadow.py` |
| 2.4 | Corriger les écarts détectés | ⏳ | Commits de fix |

**Critère de sortie** : 0 divergence sur requêtes critiques

---

### Sprint 3 : Phase 3 - Bascule Hybrid (v2)

**Statut** : 📋 Backlog

| # | Tâche | Statut |
|---|-------|--------|
| 3.1 | Migrer toutes requêtes UI vers `load_df_hybrid()` | ⏳ |
| 3.2 | Supprimer dépendances à `MatchCache` | ⏳ |
| 3.3 | Supprimer table `MatchCache` du schéma | ⏳ |
| 3.4 | Calculer médailles via DuckDB | ⏳ |

**Critère de sortie** : UI fonctionne sans `MatchCache`, espace -50%

---

### Sprint 4 : Phase 4 - Optimisations (v3)

**Statut** : 📋 Future

- Évaluer Delta Lake vs Parquet pur
- Vues matérialisées DuckDB
- Migrer `TeammatesAggregate` vers `metadata.db`
- Archiver `MatchStats` (cold storage)

---

## Dépendances entre Sprints

```
Sprint 1 ──► Sprint 2 ──► Sprint 3 ──► Sprint 4
   │            │            │
   ▼            ▼            ▼
Tests OK   0 divergence   MatchCache
+ Benchmarks              supprimé
```

---

## Références

- `docs/DATA_ARCHITECTURE.md` : Architecture technique détaillée
- `.ai/data_lineage.md` : Traçabilité des flux de données
- `src/data/repositories/shadow.py` : Pattern Shadow pour migration
- `scripts/benchmark_hybrid.py` : Benchmark Legacy vs Hybrid
- `tests/test_hybrid_benchmark.py` : Tests E2E de cohérence
