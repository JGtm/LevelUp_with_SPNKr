# Plan Projet — Remédiation P0/P1 (hors chantier Pandas)

Date: 2026-02-15  
Auteur: Agent IA (revue + plan d’exécution)  
Statut: Prêt à exécuter  
Contre-revue: 2026-02-15 — 5 trouvailles ajoutées (voir § Addendum)

---

## 1) Résumé exécutif

Ce plan structure la remédiation des anomalies **P0/P1** identifiées lors de la revue de code, en excluant explicitement le sujet **Pandas** (accepté comme dette connue).  
Priorité absolue: supprimer les risques de crash et de SQL non sécurisé (P0), puis restaurer la conformité architecture/runtime (P1) sans régression fonctionnelle.

Objectifs mesurables:
- Zéro crash sur la page Objectif lié à l’instanciation repository.
- Zéro interpolation SQL risquée dans les chemins ciblés P0/P1.
- Zéro fallback SQLite en runtime applicatif (hors scripts migration/legacy explicitement classés).
- Conformité Streamlit sur le paramètre `width` pour les vues ciblées.

---

## 2) Périmètre

### Inclus
- Correctifs **P0** (stabilité + sécurité SQL) sur la page Objectif.
- Correctifs **P1** (conformité architecture DuckDB/runtime, SQL dynamique Trends/Analytics, conformité Streamlit largeur).
- Validation par tests ciblés puis suite stable hors intégration.
- Mise à jour documentaire minimale associée aux décisions runtime/legacy.

### Exclus (décision explicite)
- Migration Pandas → Polars (considérée normale et hors périmètre de ce plan).
- Refactors non reliés aux items P0/P1.
- Optimisations UX non demandées.

---

## 3) Gouvernance projet

### 3.1 Livrables attendus
1. Correctifs code P0/P1 appliqués avec diffs minimaux.
2. Tests ciblés verts + suite stable hors intégration verte.
3. Note de conformité (SQLite runtime, SQL paramétré, Streamlit width).
4. Trace décisionnelle dans `.ai/thought_log.md`.

### 3.2 Critères de succès (Definition of Done)
- Tous les critères d’acceptation par lot (cf. section 6) sont validés.
- Aucun nouveau problème bloquant introduit dans `src/`.
- Pas de régression sur les chemins fonctionnels concernés.
- Aucune dérive de scope (pas de chantier Pandas).

### 3.3 Risques majeurs
- Régression silencieuse dans les pages Streamlit (couverture UI partielle).
- Rupture de compatibilité si suppression brute des chemins SQLite legacy.
- SQL dynamique difficilement paramétrable sur certaines clauses structurelles.

### 3.4 Stratégie de mitigation
- Traitement incrémental par lots, avec tests après chaque lot.
- Distinction stricte entre runtime applicatif et scripts migration/legacy.
- Paramétrage SQL partout où possible; validation stricte/cast sinon.

---

## 4) Étape 0 — Analyse de contexte / Explore (obligatoire)

**Objectif:** verrouiller le diagnostic avant modification pour éviter les faux positifs et cadrer l’impact réel.

### 4.1 Inventaire technique ciblé
- Cartographier les points d’entrée concernés:
  - `src/ui/pages/objective_analysis.py`
  - `src/data/query/engine.py`
  - `src/data/infrastructure/database/duckdb_engine.py`
  - `src/data/query/trends.py`
  - `src/data/query/analytics.py`
  - `src/ui/pages/career.py`
  - `scripts/refetch_film_roster.py`
- Vérifier signatures/contrats (constructeurs, API repository, helpers SQL).

### 4.2 Analyse de flux et dépendances
- Tracer les flux d’appel depuis pages UI vers query layer/repository.
- Identifier l’origine des paramètres injectés dans SQL (utilisateur/session/config).
- Qualifier chaque interpolation SQL:
  - **Sûre** (valeur contrôlée/castée),
  - **À risque faible** (source interne mais non castée),
  - **À risque moyen/élevé** (source externe non bornée).

### 4.3 Baseline qualité
- Exécuter un grep ciblé des patterns:
  - `sqlite3.connect(`
  - SQL f-strings/concat dans modules ciblés
  - `use_container_width=True` et appels `st.plotly_chart` sans `width`
- Capturer l’état initial des tests ciblés avant correction.

### 4.4 Livrables de sortie Étape 0
- Mini-matrice “fichier → risque → action”.
- Liste des correctifs strictement nécessaires (sans hors-scope).
- Plan de test de non-régression par lot.

### 4.5 Critères de sortie Étape 0
- Tous les P0/P1 sont localisés avec preuves fichier/symbole.
- Les hypothèses techniques sont levées ou explicitement marquées “à vérifier”.

---

## 5) Backlog opérationnel P0/P1 (WBS)

## Lot A — P0 (bloquant)

### A1. Corriger crash page Objectif (instanciation repository)
- **Priorité:** P0
- **Fichier principal:** `src/ui/pages/objective_analysis.py` (L455)
- **Action technique:** aligner l'appel de `DuckDBRepository` avec la signature réelle (xuid requis).
- **Localisation exacte:** `render_objective_analysis_page_from_session_state()` L455 : `repo = DuckDBRepository(db_path)` → manque `xuid`.
- **Note (contre-revue):** La page Objectifs n'est **pas routée** actuellement (absente de `dispatch_page()`). Le crash est donc **latent**, pas actif en prod. Cela n'invalide pas le correctif mais réduit l'urgence réelle.
- **Actions détaillées:**
  1. Vérifier la source du `xuid` dans le contexte page/session — **confirmé disponible** à L447.
  2. Injecter le `xuid` au point d'instanciation : `DuckDBRepository(db_path, xuid)`.
  3. Ajouter garde-fou explicite si `xuid` absent (message/return contrôlé).
  4. Vérifier la compatibilité avec appels downstream.
- **Risques:**
  - `xuid` non disponible dans certains scénarios.
  - Effets de bord sur chargement conditionnel.
- **Critères d’acceptation:**
  - La page ne lève plus d’exception de constructeur.
  - Comportement défini si contexte incomplet.

### A2. Paramétrer SQL `match_ids` sur page Objectif
- **Priorité:** P0
- **Fichier principal:** `src/ui/pages/objective_analysis.py`
- **Action technique:** remplacer l’interpolation `IN (...)` par placeholders dynamiques + tuple de paramètres.
- **Actions détaillées:**
  1. Construire la chaîne de placeholders selon cardinalité.
  2. Gérer le cas liste vide (retour rapide sans SQL invalide).
  3. Maintenir l’ordre logique des résultats.
  4. Ajouter validation de type sur `match_ids` (cast/bornage si nécessaire).
- **Risques:**
  - Requête invalide quand `match_ids` vide.
  - Dégradation perf si cardinalité très élevée.
- **Critères d’acceptation:**
  - Aucune concaténation brute de `match_ids` en SQL.
  - Résultats fonctionnellement identiques sur jeu de test.

## Lot B — P1 (conformité/robustesse)

### B1. Supprimer fallback SQLite en runtime applicatif
- **Priorité:** P1
- **Fichiers principaux:**
  - `src/data/query/engine.py`
  - `src/data/infrastructure/database/duckdb_engine.py`
- **Action technique:** neutraliser les chemins SQLite runtime et durcir le contrat DuckDB-only.
- **Actions détaillées:**
  1. Identifier branches conditionnelles SQLite.
  2. Remplacer par erreurs explicites/actionnables (message clair).
  3. Vérifier qu’aucun appel runtime ne dépend encore de ces branches.
  4. Harmoniser les messages d’erreur côté query engine.
- **Risques:**
  - Rupture pour environnements legacy non migrés.
- **Critères d’acceptation:**
  - Aucun fallback SQLite actif dans le flux applicatif normal.
  - Échec contrôlé si base non DuckDB.

### B2. Isoler/classer usage SQLite du script legacy
- **Priorité:** P1
- **Fichier principal:** `scripts/refetch_film_roster.py`
- **Action technique:** expliciter son statut legacy/migration OU migrer son backend en DuckDB selon faisabilité.
- **Actions détaillées (option minimale, recommandée court terme):**
  1. Ajouter préambule documentaire indiquant “script legacy/migration”.
  2. Ajouter garde CLI empêchant l’usage en runtime standard.
  3. Lister alternative recommandée si elle existe.
- **Actions détaillées (option cible moyen terme):**
  1. Porter le script en DuckDB natif.
  2. Valider intégrité des résultats sur échantillon.
- **Risques:**
  - Ambiguïté de statut du script pour les opérateurs.
- **Critères d’acceptation:**
  - Conformité de règle claire et traçable (runtime vs migration).

### B3. Conformité Streamlit `width` (page carrière)
- **Priorité:** P1
- **Fichier principal:** `src/ui/pages/career.py`
- **Action technique:** uniformiser `st.plotly_chart(..., width="stretch")` sur appels ciblés.
- **Actions détaillées:**
  1. Corriger les 2 occurrences identifiées.
  2. Vérifier rendu visuel desktop standard.
  3. Vérifier absence d’impact sur layout adjacent.
- **Risques:**
  - Rupture mineure d’alignement selon container parent.
- **Critères d’acceptation:**
  - Zéro occurrence non conforme dans la page.

### B4. Sécuriser SQL interpolé (Trends/Analytics)
- **Priorité:** P1
- **Fichiers principaux:**
  - `src/data/query/trends.py`
  - `src/data/query/analytics.py`
- **Action technique:** paramétrer toutes les valeurs; pour clauses non paramétrables (structure), appliquer validation/cast stricts.
- **Actions détaillées:**
  1. Classer les interpolations par type (valeur vs structure SQL).
  2. Remplacer interpolations valeur par placeholders.
  3. Pour structure: whitelist stricte (colonnes/ordre) + valeurs bornées.
  4. Ajouter helpers utilitaires de sanitation si duplication.
  5. **(Contre-revue — cas critique)** `compare_periods(metric)` dans `trends.py` L339 : le paramètre `metric` est directement interpolé via `f"AVG({metric})"` **sans aucune whitelist**. Ajouter impérativement une validation en début de méthode :
     ```python
     VALID_METRICS = {"kda", "accuracy", "win_rate", "kills", "deaths", "assists"}
     if metric not in VALID_METRICS:
         raise ValueError(f"Métrique invalide : {metric}")
     ```
  6. **(Contre-revue)** `analytics.py` L232 : dates interpolées via `f"'{start_date.isoformat()}'"` — anti-pattern (`datetime.isoformat()` est safe par nature, mais utiliser un paramètre `?` bindé serait plus propre).
- **Risques:**
  - Changement de plan d'exécution SQL.
  - Régression sur tris/filtres avancés.
- **Critères d'acceptation:**
  - Plus d'interpolation non contrôlée sur paramètres dynamiques.
  - `compare_periods()` refuse toute métrique hors whitelist.
  - Résultats analytiques inchangés sur scénarios de référence.

### B5. Conformité architecture — `career.py` contourne `DuckDBRepository` (contre-revue)
- **Priorité:** P1 (dette architecture, faible effort)
- **Fichier principal:** `src/ui/pages/career.py` (L35, L77)
- **Constat:** `_load_career_data()` et `_load_career_history()` utilisent `duckdb.connect()` directement au lieu de `DuckDBRepository`. Les requêtes SQL sont correctement paramétrées (`?`), donc **aucun risque injection**, mais le contrat « tout passe par `DuckDBRepository` » n'est pas respecté.
- **Action technique (option minimale, recommandée court terme):**
  1. Ajouter commentaire `# TODO: migrer vers DuckDBRepository` sur les deux fonctions.
  2. Documenter comme dette connue.
- **Action technique (option cible moyen terme):**
  1. Refactorer pour utiliser `DuckDBRepository.query_df()` ou méthode dédiée.
- **Critères d'acceptation:**
  - Déviation explicitement documentée ou corrigée.

### B6. Documenter les API SQL fragiles de `engine.py` (contre-revue)
- **Priorité:** P1 (prévention, très faible effort)
- **Fichier principal:** `src/data/query/engine.py`
- **Constat:** Deux API internes acceptent du SQL brut sans validation :
  - `query_match_facts(select, where, order_by)` L312-340 — clauses injectées directement.
  - `execute()` L241 — `SET VARIABLE {key} = {repr(value)}` avec `key` non validé.
- **Note:** Actuellement les appelants sont internes et safe (littéraux hardcodés, whitelist sur `metric`). Mais l'absence de garde rend ces API **fragiles pour tout futur développeur**.
- **Action technique:**
  1. Ajouter commentaire `# SECURITY: ne jamais passer d'input utilisateur à select/where/order_by` sur `query_match_facts()`.
  2. Ajouter commentaire `# SECURITY: keys et values doivent être contrôlés en amont` sur le bloc `SET VARIABLE`.
- **Critères d'acceptation:**
  - Commentaires de sécurité en place sur les deux points.

---

## 6) Stratégie de validation & QA

### 6.1 Validation par lot
- **Après Lot A (P0):**
  - Tests ciblés page objectif + requêtes associées.
  - Vérification manuelle du chemin nominal page Objectif.
- **Après Lot B (P1):**
  - Tests ciblés Trends/Analytics/Career.
  - Vérification non-régression query engine.

### 6.2 Commandes de test recommandées
- `python -m pytest tests -k "objective or career or trends or analytics" -q`
- `python -m pytest -q --ignore=tests/integration`

### 6.3 Contrôles statiques ciblés
- Recherche de patterns SQL à risque dans modules traités.
- Recherche `sqlite3.connect(` hors scripts migration/legacy explicitement autorisés.
- Recherche des appels `st.plotly_chart` non conformes sur périmètre.
- **(Contre-revue)** Vérifier que `compare_periods()` et tout autre méthode de `TrendAnalyzer` valident `metric` par whitelist après correction.
- **(Contre-revue)** Vérifier que les commentaires `# SECURITY` sont en place sur `query_match_facts()` et `SET VARIABLE`.

### 6.4 Critères de sortie QA
- Tous tests ciblés verts.
- Suite stable hors intégration verte.
- Aucun nouveau warning bloquant lié aux fichiers modifiés.

---

## 7) Planning détaillé (exécution projet)

### Vague 0 — Explore & cadrage (0.5 j)
- Exécution Étape 0 complète.
- Validation des hypothèses et des priorités.
- Gel du scope P0/P1 (hors Pandas).

### Vague 1 — Correctifs P0 (0.5 à 1 j)
- A1 + A2.
- Revue rapide de diff + tests ciblés.
- Go/No-Go pour passage en P1.

### Vague 2 — Correctifs P1 immédiats (1 à 2 j)
- B3 (width) + B4 (SQL Trends/Analytics, incluant whitelist `metric`).
- B6 (commentaires sécurité engine.py) — très faible effort, inclus dans cette vague.
- Tests ciblés UI/query.

### Vague 3 — Conformité architecture runtime (1 à 2 j)
- B1 (fallback SQLite runtime).
- B2 (isolation script legacy / migration partielle).
- B5 (documentation/TODO career.py bypass DuckDBRepository).
- Validation globale + documentation conformité.

### Jalons
- **J0:** Diagnostic verrouillé (Étape 0)
- **J1:** P0 clôturés
- **J2:** P1 UI/SQL clôturés (B3 + B4 + B6)
- **J3:** P1 architecture clôturés (B1 + B2 + B5) + dossier de validation

---

## 8) Matrice des risques (extrait)

| Risque | Probabilité | Impact | Niveau | Mitigation |
|---|---:|---:|---:|---|
| Régression UI page Objectif | Moyen | Élevé | Haut | Test ciblé + smoke manuel |
| Rupture environnement legacy après retrait SQLite runtime | Moyen | Élevé | Haut | Message erreur explicite + documentation migration |
| Régression logique Trends/Analytics | Moyen | Moyen | Moyen | Golden scenarios + comparaison sorties |
| SQL dynamique partiellement non paramétrable | Élevé | Moyen | Moyen | Whitelist stricte + cast fort |
| **(CR)** Injection via `compare_periods(metric)` sans whitelist | Moyen | Élevé | Haut | Whitelist `VALID_METRICS` obligatoire |
| **(CR)** API `query_match_facts` fragile pour futurs appelants | Bas | Moyen | Bas | Commentaires sécurité + documentation |

---

## 9) Checklist d’exécution opérationnelle

### Avant dev
- [ ] Étape 0 finalisée et validée.
- [ ] Jeux de tests ciblés identifiés.
- [ ] Cas de référence (inputs/outputs) documentés.

### Pendant dev
- [ ] Uniquement correctifs P0/P1 (hors Pandas).
- [ ] Diffs minimaux, sans refactor parasite.
- [ ] Validation après chaque lot.

### Avant clôture
- [ ] Tests ciblés verts.
- [ ] Suite stable hors intégration verte.
- [ ] Vérifications statiques SQL/SQLite/Streamlit effectuées.
- [ ] Thought log mis à jour.

---

## 10) Fichiers prioritaires (ordre d’intervention)

1. `src/ui/pages/objective_analysis.py` (P0 crash L455 + SQL match_ids L87-95)
2. `src/data/query/trends.py` (P1 SQL dynamique + **whitelist `metric` L339** — critique)
3. `src/data/query/analytics.py` (P1 SQL dynamique, dates L232)
4. `src/data/query/engine.py` (P1 fallback SQLite runtime L111-118 + **commentaires sécurité** L241, L329-334)
5. `src/ui/pages/career.py` (P1 Streamlit width L260/L275 + **TODO bypass DuckDBRepository** L35/L77)
6. `src/data/infrastructure/database/duckdb_engine.py` (P1 fallback SQLite runtime, méthode `attach_sqlite`)
7. `scripts/refetch_film_roster.py` (P1 classification legacy/migration)

---

## 11) Notes de conduite

- Respect strict des conventions repo: DuckDBRepository, SQL paramétré, Streamlit `width="stretch"`.
- Aucune modification de schéma DB sans migration explicite.
- Ne pas introduire de dépendances nouvelles pour ce chantier.
- Toute décision non triviale doit être tracée dans `.ai/thought_log.md`.

---

## 12) Décision de lancement

Ce plan est prêt pour exécution immédiate par vagues (0 → 3).  
Mode recommandé: démarrer par **Vague 0 + Vague 1** dans le même cycle pour sécuriser rapidement la prod (P0).

---

## Addendum — Contre-revue (2026-02-15)

Contre-revue effectuée par second agent IA. Audit complet de `src/` avec grep globaux et inspection de tous les fichiers ciblés.

### Résultats de la contre-revue

**Tous les items P0/P1 du plan initial sont confirmés et correctement localisés.**

### Trouvailles supplémentaires (5 items)

| # | Trouvaille | Sévérité | Action | Intégré dans |
|---|-----------|----------|--------|-------------|
| CR-1 | `compare_periods(metric)` — paramètre `metric` interpolé sans whitelist dans `trends.py` L339 (`f"AVG({metric})"`) | **Élevé** | Whitelist `VALID_METRICS` obligatoire | B4 (action 5) |
| CR-2 | `career.py` contourne `DuckDBRepository` — `duckdb.connect()` direct L35/L77 | Moyen | Documentation + TODO ou refactor | B5 (nouveau) |
| CR-3 | `engine.py` API fragiles — `query_match_facts(select, where, order_by)` L329 et `SET VARIABLE` L241 acceptent du SQL brut | Moyen | Commentaires sécurité | B6 (nouveau) |
| CR-4 | A1 crash latent — page Objectifs non routée actuellement (absente de `dispatch_page()`) | Info | Réduit l'urgence réelle mais ne change pas le correctif | Précision A1 |
| CR-5 | `analytics.py` L232 — dates interpolées via f-string au lieu de `?` bindé (safe en pratique via `isoformat()`) | Bas | Binder proprement | B4 (action 6) |

### Éléments vérifiés sans anomalie

- **`import sqlite3`** : zéro occurrence dans `src/` — conforme.
- **`use_container_width=True`** : zéro occurrence dans `src/` — migration terminée.
- **`st.plotly_chart` sans `width`** : uniquement les 2 cas dans `career.py` (déjà en B3).
- **SQL placeholders `IN ({placeholders})`** : tous les usages dans `duckdb_repo.py`, `_roster_loader.py`, `_match_queries.py`, `_antagonists_repo.py`, `citations/engine.py` utilisent correctement des `?` bindés.
- **`batch_insert.py` / `metadata_resolver.py`** : interpolations SQL de noms de tables/colonnes depuis des listes fermées internes — aucun risque.
- **Aucune injection SQL exploitable par un utilisateur final** n'a été trouvée dans le codebase.
