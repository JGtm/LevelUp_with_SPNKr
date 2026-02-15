# Matrice quasi exhaustive — Tests manquants (focus E2E)

> Date : 2026-02-12  
> Périmètre : app Streamlit data-driven (BDD DuckDB → repo → filtres → pages → graphes)  
> Base d'analyse : état courant de `tests/`, `tests/integration/`, `tests/e2e/`, pages `src/ui/pages/*`

---

## 1) État actuel (résumé)

### Déjà bien couvert

- Contrats data critiques (S9.4 T1) :
  - `tests/test_data_contract_medals.py`
  - `tests/test_data_contract_performance_metrics.py`
  - `tests/test_data_contract_shots_accuracy.py`
  - `tests/test_data_contract_participants.py`
  - `tests/test_data_contract_assets_aliases.py`
- Contrats graphes / viz clés :
  - `tests/test_visualizations.py`
  - `tests/test_new_timeseries_sections.py`
  - `tests/test_teammates_impact_tab.py`
  - `tests/test_teammates_new_comparisons.py`
  - `tests/test_filters_and_visualization_contracts.py`
- Intégration app :
  - `tests/integration/test_app_data_to_chart_flow.py`
- E2E navigateur (smoke) :
  - `tests/e2e/test_streamlit_browser_e2e.py`

### Couverture encore limitée

- E2E orienté parcours métier : principalement smoke/navigation, peu d’assertions de changement de données visibles.
- Deep-links (`?page=...`, `match_id`) : non verrouillés E2E.
- Parcours multi-pages sensibles : `Historique` → `Match`, `Médias` → `Match`, `Comparaison de sessions`.
- Tests robustes des états vides/partiels sur plusieurs pages en vrai navigateur.

---

## 2) Priorisation backlog (P0/P1/P2)

## P0 — À implémenter en premier (blocage qualité produit)

### E2E-001 — Filtre playlist impacte les résultats visibles
- **Type** : E2E navigateur
- **Fichier cible** : `tests/e2e/test_streamlit_browser_e2e.py`
- **Scénario** :
  1. Ouvrir `Séries temporelles`
  2. Capturer un indicateur visible (ex: nombre de points/labels en table ou texte de synthèse)
  3. Changer filtre playlist (`Ranked` ↔ `Quick Play`)
  4. Vérifier variation visible
- **Assertion minimale** : la vue affichée change réellement après filtre
- **Risque couvert** : filtre UI inopérant (régression silencieuse)

### E2E-002 — Filtre mode + map combinés
- **Type** : E2E navigateur
- **Fichier cible** : `tests/e2e/test_streamlit_browser_e2e.py`
- **Scénario** : sur `Victoires/Défaites`, appliquer mode puis map
- **Assertion minimale** : aucune erreur front + variation d’au moins un élément visible
- **Risque couvert** : filtres combinés non propagés au dataset page

### E2E-003 — Coéquipiers Impact : état vide puis état rempli
- **Type** : E2E navigateur
- **Fichier cible** : `tests/e2e/test_streamlit_browser_e2e.py`
- **Scénario** :
  1. Aller sur `Mes coéquipiers`
  2. Avec <2 amis sélectionnés : message guidé attendu
  3. Sélectionner ≥2 amis
  4. Vérifier présence heatmap/ranking sans erreur
- **Assertion minimale** : transition vide→rempli fonctionnelle
- **Risque couvert** : UX cassée sur condition d’entrée principale de la feature S12

### E2E-004 — Deep-link page + match_id
- **Type** : E2E navigateur
- **Fichier cible** : `tests/e2e/test_streamlit_browser_e2e.py`
- **Scénario** : ouvrir URL `?page=Match&match_id=<id_fixture>`
- **Assertion minimale** : la page `Match` s’affiche et utilise le `match_id`
- **Risque couvert** : régression routeur/query-params

### INT-002 — Intégration multi-domaines avec datasets partiels
- **Type** : intégration
- **Nouveau fichier** : `tests/integration/test_app_partial_data_to_chart_flow.py`
- **Scénario** : DB minimale avec colonnes partiellement nulles/absentes (dans tolérance)
- **Assertion minimale** : pages/graphes clés tombent en fallback UX, pas en exception
- **Risque couvert** : crash prod quand certaines sources sont incomplètes

## P1 — Important, après P0

### E2E-005 — Historique des parties → ouverture page Match
- **Type** : E2E navigateur
- **Fichier cible** : `tests/e2e/test_streamlit_browser_e2e.py`
- **Scénario** : depuis `Historique`, action “ouvrir match”
- **Assertion minimale** : navigation effective vers page `Match`

### E2E-006 — Médias → ouverture page Match (query param)
- **Type** : E2E navigateur
- **Fichier cible** : `tests/e2e/test_streamlit_browser_e2e.py`
- **Scénario** : cliquer action qui pousse `page=Match`
- **Assertion minimale** : bascule page + absence d’erreur

### E2E-007 — Comparaison de sessions A/B stable
- **Type** : E2E navigateur
- **Fichier cible** : `tests/e2e/test_streamlit_browser_e2e.py`
- **Scénario** : sélectionner Session A puis B, changer période, revenir
- **Assertion minimale** : état session cohérent, pas de reset inattendu

### NR-001 — Régression navigation avec `_pending_page`
- **Type** : non-régression unitaire/intégration légère
- **Nouveau fichier** : `tests/test_pending_page_navigation_regressions.py`
- **Scénario** : simuler `_pending_page`/`consume_pending_page`
- **Assertion minimale** : page finale attendue, sans effet de bord

### NR-002 — Régression query params cleanup
- **Type** : non-régression
- **Nouveau fichier** : `tests/test_query_params_routing_regressions.py`
- **Scénario** : injection query params + clear
- **Assertion minimale** : comportement stable de `_set_query_params`/lecture page

### DATA-006 — Contrat data `session_id/session_label`
- **Type** : contrat data
- **Nouveau fichier** : `tests/test_data_contract_sessions.py`
- **Assertion minimale** : cohérence `session_id`, ordering `start_time`, labels non vides

## P2 — Compléments utiles (nightly / durcissement)

### E2E-008 — Objectifs : 3 onglets rendables
- **Type** : E2E navigateur
- **Fichier cible** : `tests/e2e/test_streamlit_browser_e2e.py`
- **Scénario** : ouvrir `Analyse objectifs`, visiter scatter/breakdown/trend
- **Assertion minimale** : pas d’erreur front, onglets accessibles

### E2E-009 — Carrière : gauge + historique présents
- **Type** : E2E navigateur
- **Fichier cible** : `tests/e2e/test_streamlit_browser_e2e.py`
- **Assertion minimale** : sections clés visibles, pas d’exception

### INT-003 — Parcours `match_participants` incomplet
- **Type** : intégration
- **Nouveau fichier** : `tests/integration/test_participants_partial_columns_flow.py`
- **Assertion minimale** : pages coéquipiers gèrent dégradation gracieuse

### NR-003 — Filtres cross-page persistants
- **Type** : non-régression
- **Nouveau fichier** : `tests/test_cross_page_filter_persistence.py`
- **Assertion minimale** : filtres conservés entre `Séries temporelles` / `Victoires-Défaites` / `Coéquipiers`

---

## 3) Matrice pages × niveaux de test

| Page métier | Unit/Contract | Intégration | E2E actuel | Gap principal |
|---|---:|---:|---:|---|
| Séries temporelles | ✅ | ✅ | ⚠️ smoke | E2E changement réel de données |
| Victoires/Défaites | ✅ | ⚠️ indirect | ⚠️ smoke | E2E filtres combinés |
| Mes coéquipiers | ✅ | ✅ | ⚠️ partiel | état vide/rempli + sélection amis |
| Comparaison sessions | ✅ partiel | ⚠️ | ❌ | parcours A/B complet |
| Historique des parties | ✅ partiel | ⚠️ | ❌ | navigation vers Match |
| Match / Dernier match | ✅ partiel | ⚠️ | ❌ | deep-link query param |
| Médias | ✅ | ⚠️ | ❌ | navigation interne vers Match |
| Carrière | ✅ | ⚠️ | ❌ | smoke dédié page carrière |
| Objectifs | ✅ partiel | ⚠️ | ❌ | smoke onglets objectifs |
| Paramètres | ✅ | ⚠️ | ✅ | assertions métier faibles |

---

## 4) Proposition d’ordonnancement d’implémentation

### Vague 1 (2-3 PR)
1. Ajouter E2E-001 à E2E-004 (P0)
2. Ajouter INT-002
3. Ajouter DATA-006

### Vague 2 (2 PR)
1. Ajouter E2E-005 à E2E-007 (P1)
2. Ajouter NR-001 et NR-002

### Vague 3 (nightly / non bloquant)
1. Ajouter E2E-008 et E2E-009
2. Ajouter INT-003 et NR-003

---

## 5) Politique CI recommandée (mise à jour)

- **PR rapide** : contrats data + non-régression stable (`--ignore=tests/integration`)
- **PR étendue (optionnelle)** : intégrer E2E-001..004 avec skip défensif si contrôles absents
- **Nightly** : E2E complet + intégrations partielles (INT-002, INT-003)
- **Manuel (`workflow_dispatch`)** : E2E full navigateur avec dataset représentatif

---

## 6) Définition de “quasi exhaustive” pour ce repo

La couverture est considérée quasi exhaustive quand :

- chaque page de `src/ui/pages/` a au moins un test E2E dédié (pas seulement smoke global),
- chaque domaine data critique a un contrat table/colonnes/invariants,
- chaque parcours de navigation interne inter-page (historique→match, médias→match, deep-link) est testé,
- chaque feature à condition d’entrée (ex: coéquipiers ≥2) est testée en état vide + état rempli.

---

## 7) Backlog concret de fichiers à ajouter (proposé)

- `tests/integration/test_app_partial_data_to_chart_flow.py`
- `tests/test_data_contract_sessions.py`
- `tests/test_pending_page_navigation_regressions.py`
- `tests/test_query_params_routing_regressions.py`
- `tests/test_cross_page_filter_persistence.py`

> Les scénarios E2E-001..009 sont proposés en extension de `tests/e2e/test_streamlit_browser_e2e.py` pour limiter la dispersion.
