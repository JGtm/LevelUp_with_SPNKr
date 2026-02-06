# Triage To do.txt – Graphiques déjà faits vs à faire

> Exploration du code (fév. 2026). Ce document fait le tri entre ce qui est déjà implémenté et ce qui reste à faire, sans modifier le code.

---

## ✅ Déjà implémenté (graphiques / viz)

### Séries temporelles (`src/ui/pages/timeseries.py` + `src/visualization/timeseries.py`)
| Élément To do | Implémentation |
|---------------|----------------|
| Graphe principal Frags / Morts / Ratio | `plot_timeseries()` – barres K/D/ratio + **étiquettes valeurs extrêmes sur le ratio** (`add_extreme_annotations` dans `timeseries.py` L.163) |
| FDA (KDA) distribution | `plot_kda_distribution()` |
| Distributions (précision, kills, durée de vie, score de perf) | `plot_histogram()` pour les 4 |
| Corrélations (durée de vie vs frags ; précision vs FDA) | `plot_correlation_scatter()` (2 scatter + tendance) |
| Distribution First Kill / First Death | `plot_first_event_distribution()` (repo `get_first_kill_death_times`) |
| Score de performance (série temporelle) | `plot_performance_timeseries()` |
| Assistances | `plot_assists_timeseries()` |
| Stats par minute (barres) | `plot_per_minute_timeseries()` (frags/morts/assist par minute) |
| Durée de vie moyenne | `plot_average_life()` |
| Folie meurtrière / Tirs à la tête / Précision / **Frags parfaits** | `plot_spree_headshots_accuracy(df, perfect_counts=...)` – médailles Perfect comptées via repo |

### Victoires / Défaites (`src/ui/pages/win_loss.py` + `src/visualization/distributions.py`, `maps.py`)
| Élément To do | Implémentation |
|---------------|----------------|
| Évolution victoires/défaites par période | `plot_outcomes_over_time()` |
| **Matches par carte** (stacked win/loss/tie/left) | `plot_stacked_outcomes_by_category(dff, "map_name", ...)` |
| **Matches par mode / game variant** (stacked) | `plot_stacked_outcomes_by_category(dff, mode_col, ...)` |
| **Win Ratio par jour et heure** | `plot_win_ratio_heatmap()` |
| **Matches Top vs Total par semaine** + taux Top (%) | `plot_matches_at_top_by_week()` – barres empilées + ligne "Taux Top (%)" |
| Ratio par cartes (tableau + graphes) | `plot_map_comparison()`, `plot_map_ratio_with_winloss()`, tableau détaillé |

### Mes coéquipiers (`src/ui/pages/teammates.py`)
| Élément To do | Implémentation |
|---------------|----------------|
| **Tableau "Stats par minute" + radar à droite** | Tableau + `create_stats_per_minute_radar()` en colonnes côte à côte (L.776–829) |
| Radar complémentarité (6 axes) | `_render_synergy_radar()` → `create_participation_profile_radar()` |
| Grille médailles | `render_medals_grid()` |

### Match / Participation / Session
| Élément To do | Implémentation |
|---------------|----------------|
| Radar participation 6 axes (match) | `match_view_participation.py` → `create_participation_profile_radar()` |
| Radar participation (comparaison sessions) | `session_compare.py` – radar + barres comparatives |
| Médailles (grille + distribution) | `render_medals_grid()` (match_view, teammates, citations) ; `plot_medals_distribution()` sur **page Citations** |

### Autres (antagonistes, objectifs, maps)
| Élément To do | Implémentation |
|---------------|----------------|
| Graphiques antagonistes (killer/victim, duel, heatmap, etc.) | `antagonist_charts.py` – utilisés dans match_view_players, etc. |
| Objectifs (scatter, barres, gauge, tendance) | `objective_charts.py` ; page `objective_analysis.py` |
| Top armes (barres) | `plot_top_weapons()` – présent dans le module, à confirmer où affiché en UI (données limitées par API) |

---

## ⚠️ Implémenté mais **non branché en UI**

Ces fonctions existent et sont testées, mais **aucune page Streamlit ne les appelle** :

| Fonction | Fichier | Usage actuel |
|----------|---------|---------------|
| `plot_cumulative_net_score()` | `src/visualization/performance.py` | Uniquement dans `tests/test_performance_cumulative.py` |
| `plot_cumulative_kd()` | idem | idem |
| `plot_rolling_kd()` | idem | idem |
| `plot_session_trend()` | idem | idem |
| `plot_cumulative_comparison()` | idem | idem |

**Analyse** : Le To do demande un « graphique performance cumulée » (net score cumulé, pas de reset par match, lignes verticales tous les 8 min). La logique existe dans `src/analysis/cumulative.py` et les figures dans `performance.py`, mais il manque :
- l’intégration dans une page (ex. **Séries temporelles** ou **Comparer sessions**) ;
- l’axe temps **minute par minute** (MM:SS) et les marqueurs de fin de match (tous les 8 min) si on veut coller au cahier.

---

## ❌ Pas fait / À faire

### Étiquettes valeurs extrêmes
- **Fait** : uniquement sur le graphe principal Frags/Morts/Ratio (`plot_timeseries`), pour la métrique *ratio*.
- **À faire** : étendre `add_extreme_annotations` (ou équivalent) aux **autres** graphes (win_loss, session_compare, match_view_charts, etc.), en excluant les graphes de la page « Mes coéquipiers » comme indiqué dans le To do.

### Série temporelle K–D (cahier en bas du To do)
- **À faire** : série **minute par minute** avec axe X = temps (MM:SS), axe Y = différentiel (Kills − Deaths), ligne horizontale à zéro.
- **État actuel** : `plot_timeseries` est par **match** (barres), pas par minute. Il faut soit un nouveau graphique basé sur des données minute par minute (si disponibles), soit clarifier si “minute par minute” désigne “par match” avec un pas de 1 minute à l’intérieur du match.

### Graphique performance cumulée (cahier)
- **À faire** : brancher en UI (ex. Séries temporelles ou Comparer sessions) et, si besoin, ajouter :
  - lignes verticales pointillées tous les 8 min pour marquer les fins de match ;
  - axe temps adapté (session = suite de matchs, pas forcément MM:SS intra-match).

### Nouvelles stats Hero (à traduire / placer)
| Élément | Statut | Où c’est / où le mettre |
|--------|--------|--------------------------|
| Distribution of **win ratio** (histogramme des taux de victoire) | ❌ | Pas de viz dédiée (on a la heatmap jour/heure, pas la distribution du win ratio). À ajouter (ex. `win_loss.py` ou distributions). |
| **Weekly Longest Winning Streak** / **Distribution of Win Streaks** | ❌ | `get_win_streak_stats()` dans `src/data/query/analytics.py` – pas d’UI. À ajouter (ex. win_loss ou une section « Séries »). |
| **Per-Match Personal Score** (tableau ou graphe) | Partiel | `personal_score` dans `match_stats` ; pas de graphe dédié « score personnel par match ». |
| **Distribution Damage Dealt / Damage Taken** | ❌ | Données en BDD (`damage_dealt`, `damage_taken` dans sync). Pas de graphique. À ajouter (ex. timeseries ou page Combat). |
| **Distribution Personal Score per minute** | ❌ | À calculer (score / durée) et afficher. |
| **Corrélation life duration vs outcomes** | Partiel | On a life vs kills ; pas life vs outcome. |
| **Corrélation kills vs deaths vs outcomes** | Partiel | Corrélations 2D existantes ; pas de vue 3D ou multi-métriques explicite. |
| **Ratio of Matches at Top to Total (%)** | ✅ | Déjà dans `plot_matches_at_top_by_week` (ligne « Taux Top (%) »). |
| **Correlation enemy vs friendly team MMR** | ❌ | À faire si données MMR équipes dispo. |
| **Top 3 armes + frags sur période session** | Limité | `plot_top_weapons` existe ; données armes limitées par API (voir `.ai/API_LIMITATIONS.md`). |
| **Rang/position dans le match et score personnel** | À préciser | À placer (match_view, timeseries ou onglet dédié). |
| **Shots Fired / Shots Hit, Callout Assists** | ❌ | À faire si champs disponibles en BDD. |
| **Radar objectif/frags/morts/assist si joueur a joué l’objectif** | Partiel | Radars 6 axes existants ; condition « a joué l’objectif » à définir et brancher. |

---

## Récap par fichier (où ça vit)

| Fichier | Rôle |
|---------|------|
| `src/ui/pages/timeseries.py` | Séries temporelles, distributions, corrélations, first kill/death, perf, stats/min, durée de vie, spree/headshots/accuracy/perfect. |
| `src/ui/pages/win_loss.py` | Outcomes over time, stacked par carte/mode, heatmap win ratio, matches at top par semaine, ratio par cartes. |
| `src/ui/pages/teammates.py` | Tableau + radar « Stats par minute », radars complémentarité, médailles. |
| `src/ui/pages/session_compare.py` | Comparaison sessions, radars, barres, score de performance. |
| `src/ui/pages/match_view.py` / `match_view_participation.py` | Détail match, participation, radar 6 axes, médailles. |
| `src/ui/pages/citations.py` | `plot_medals_distribution` + grille médailles. |
| `src/visualization/performance.py` | `plot_cumulative_net_score`, `plot_cumulative_kd`, `plot_rolling_kd`, `plot_session_trend` – **non utilisés en UI**. |
| `src/visualization/timeseries.py` | Tous les plot_* de séries + `add_extreme_annotations` sur `plot_timeseries`. |
| `src/visualization/distributions.py` | KDA, outcomes, stacked outcomes, heatmap win ratio, histogram, medals, corrélations, matches at top, first event, top weapons. |
| `src/ui/components/chart_annotations.py` | `add_extreme_annotations` – utilisé uniquement dans `plot_timeseries`. |

---

## Actions recommandées (sans toucher au code pour l’instant)

1. **Mettre à jour le To do.txt** : cocher ou déplacer en « Fait » les lignes correspondant aux éléments de la section « Déjà implémenté » et « Ratio of Matches at Top ».
2. **Étiquettes extrêmes** : prévoir d’appliquer les annotations aux autres graphes (win_loss, session_compare, etc.), hors Mes coéquipiers.
3. **Performance cumulée** : décider de la page (timeseries vs session_compare), puis brancher `plot_cumulative_net_score` (et éventuellement `plot_cumulative_kd`) + marqueurs 8 min si requis.
4. **Série K–D minute par minute** : clarifier la source des données (par minute de match vs par match) puis ajouter le graphique dédié.
5. **Hero stats manquantes** : prioriser (win ratio distribution, win streaks, damage dealt/taken, personal score per minute, MMR) et attribuer chaque item à une page (win_loss, timeseries, match_view, etc.).

Document généré par exploration du code – fév. 2026.
