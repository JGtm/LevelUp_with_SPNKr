# Planification détaillée : Nouvelles données statistiques (To do.txt lignes 15-44)

> Planification ultra détaillée et précise pour chaque élément. **Aucune modification de code dans ce document.**

**Date** : 2026-02-07  
**Source** : `To do.txt` lignes 15-44  
**Référence Hero Stats** : https://github.com/OpenSpartan/notebooks/blob/main/src/hero/Hero%20Stats.ipynb

---

## Table des matières

1. [Éléments à ajouter à "Mes coéquipiers" et "Victoires/défaites"](#1-éléments-à-ajouter-à-mes-coéquipiers-et-victoiresdéfaites)
2. [Éléments à ajouter sur "timeseries" et "Mes coéquipiers"](#2-éléments-à-ajouter-sur-timeseries-et-mes-coéquipiers)
3. [Éléments à ajouter sur "Dernier match" et "Mes coéquipiers"](#3-éléments-à-ajouter-sur-dernier-match-et-mes-coéquipiers)
4. [Éléments à ajouter sur "Timeseries" et "Dernier match"](#4-éléments-à-ajouter-sur-timeseries-et-dernier-match)
5. [Visualisations différences joueurs (Mes coéquipiers)](#5-visualisations-différences-joueurs-mes-coéquipiers)
6. [Ajouts et mise à jour de graphes existants](#6-ajouts-et-mise-à-jour-de-graphes-existants)

---

## 1. Éléments à ajouter à "Mes coéquipiers" et "Victoires/défaites"

### 1.1 Per-Match Personal Score

**Description** : Afficher le score personnel (`personal_score`) pour chaque match, sous forme de graphique et/ou tableau.

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonne** : `personal_score` (INTEGER, nullable)
- **Disponibilité** : ✅ Colonne existe déjà dans le schéma (`src/data/sync/engine.py` L.356, `src/data/sync/models.py` L.203)
- **Source API** : `MatchStats.Players[].PlayerTeamStats[].Stats.CoreStats.PersonalScore`

**Où ajouter** :

#### A. Page "Victoires/Défaites" (`src/ui/pages/win_loss.py`)

**Emplacement** : Après la section "Par période" (ligne ~197) ou dans une nouvelle sous-section "Score personnel par match".

**Visualisation proposée** :
- **Graphique** : Barres horizontales ou verticales par match (trié chronologiquement)
  - Axe X : Matchs (index ou date)
  - Axe Y : Score personnel
  - Couleur : Selon `outcome` (vert=victoire, rouge=défaite, amber=égalité)
- **Tableau** : Colonnes `start_time`, `personal_score`, `outcome`, `map_name`, `pair_name` (optionnel : triable)

**Fichier à modifier** :
- `src/ui/pages/win_loss.py` : Ajouter section après `render_win_loss_page()` ligne ~197
- `src/visualization/distributions.py` ou nouveau fichier : Fonction `plot_personal_score_by_match()`

**Logique** :
```python
# Requête/calcul
df_personal = dff[["start_time", "personal_score", "outcome", "match_id", "map_name", "pair_name"]].copy()
df_personal = df_personal.dropna(subset=["personal_score"]).sort_values("start_time")
# Graphique : barres avec couleur selon outcome
```

**Dépendances** :
- Vérifier que `personal_score` est bien rempli dans `match_stats` (peut être NULL si non sync)
- Gérer les cas où `personal_score` est NULL (afficher message d'info)

---

#### B. Page "Mes coéquipiers" (`src/ui/pages/teammates.py`)

**Emplacement** : Dans la vue single-teammate (`_render_single_teammate_view`) ou multi-teammate (`_render_multi_teammate_view`), après le tableau "Stats par minute" (ligne ~776).

**Visualisation proposée** :
- **Graphique comparatif** : Barres groupées comparant le score personnel du joueur principal vs coéquipier(s) sur les matchs communs
  - Axe X : Matchs (ou périodes)
  - Axe Y : Score personnel
  - Série 1 : Moi
  - Série 2 : Coéquipier(s)
- **Tableau** : Colonnes `match_id`, `start_time`, `my_personal_score`, `teammate_personal_score`, `diff` (différence)

**Fichier à modifier** :
- `src/ui/pages/teammates.py` : Ajouter section dans `_render_single_teammate_view()` ou `_render_multi_teammate_view()`
- `src/ui/pages/teammates_charts.py` : Nouvelle fonction `render_personal_score_comparison()`

**Logique** :
```python
# Pour chaque coéquipier sélectionné
# Charger match_ids communs
# Charger personal_score depuis match_stats pour moi et le coéquipier
# Comparer sur les matchs communs
```

**Dépendances** :
- Utiliser `_load_teammate_stats_from_own_db()` pour charger les stats du coéquipier depuis sa DB
- Vérifier que `personal_score` existe dans les deux DBs

---

### 1.2 Weekly Longest Winning Streak, Distribution of Win Streaks

**Description** :
- **Weekly Longest Winning Streak** : La plus longue série de victoires par semaine
- **Distribution of Win Streaks** : Histogramme montrant la répartition des longueurs de séries de victoires

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonnes** : `start_time`, `outcome` (2=Win, 3=Loss)
- **Fonction existante** : `src/data/query/analytics.py` → `get_win_streak_stats()` (ligne ~328)
  - Retourne `max_win_streak`, `max_loss_streak`, `current_streak`
  - **À étendre** : Calculer par semaine et distribution complète

**Où ajouter** :

#### A. Page "Victoires/Défaites" (`src/ui/pages/win_loss.py`)

**Emplacement** : Nouvelle sous-section après "Matches Top vs Total par semaine" (ligne ~197).

**Visualisation proposée** :

**1. Weekly Longest Winning Streak** :
- **Graphique** : Barres par semaine (axe X = semaine, axe Y = longueur de la plus longue série)
  - Couleur : Dégradé vert selon la longueur
  - Annotation : Afficher la valeur sur chaque barre

**2. Distribution of Win Streaks** :
- **Graphique** : Histogramme (barres verticales)
  - Axe X : Longueur de série (1, 2, 3, 4, ...)
  - Axe Y : Nombre de séries de cette longueur
  - KDE optionnel : Courbe de densité superposée

**Fichier à modifier** :
- `src/ui/pages/win_loss.py` : Ajouter section après ligne ~197
- `src/visualization/distributions.py` : Nouvelle fonction `plot_win_streak_distribution()`
- `src/data/query/analytics.py` : Étendre `get_win_streak_stats()` pour calculer par semaine et distribution complète

**Logique de calcul** :

```python
# 1. Calculer toutes les séries de victoires
# Grouper par semaine
# Pour chaque semaine, calculer la plus longue série de victoires consécutives

# 2. Distribution complète
# Parcourir tous les matchs triés par start_time
# Identifier chaque série de victoires (suite de outcome=2)
# Compter la longueur de chaque série
# Créer histogramme des longueurs
```

**Fichiers à créer/modifier** :
- `src/analysis/win_streaks.py` (nouveau) : Fonctions `compute_weekly_longest_streak()`, `compute_win_streak_distribution()`
- `src/visualization/distributions.py` : `plot_weekly_longest_streak()`, `plot_win_streak_distribution()`

**Dépendances** :
- Utiliser `get_win_streak_stats()` comme base mais étendre pour les besoins spécifiques

---

#### B. Page "Mes coéquipiers" (`src/ui/pages/teammates.py`)

**Emplacement** : Dans la vue single-teammate, après les métriques comparatives (ligne ~470).

**Visualisation proposée** :
- **Graphique comparatif** : Comparer les séries de victoires entre moi et le coéquipier
  - Barres groupées : Ma plus longue série vs celle du coéquipier (par semaine ou globale)
  - Distribution côte à côte : Deux histogrammes superposés (moi vs coéquipier)

**Fichier à modifier** :
- `src/ui/pages/teammates.py` : Ajouter section dans `_render_single_teammate_view()`
- `src/ui/pages/teammates_charts.py` : Nouvelle fonction `render_win_streak_comparison()`

**Logique** :
```python
# Charger matchs communs
# Calculer séries pour moi et le coéquipier séparément
# Comparer
```

---

### 1.3 Rang/position dans le match et score personnel

**Description** : Afficher le rang du joueur dans le match (`rank`, 1 = meilleur) et le score personnel (`personal_score`) ensemble.

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonnes** : `rank` (SMALLINT, nullable), `personal_score` (INTEGER, nullable)
- **Disponibilité** : ✅ Colonnes existent (`src/data/sync/engine.py` L.334, L.356)
- **Alternative** : `match_participants` contient aussi `rank` et `score` pour tous les joueurs

**Où ajouter** :

#### A. Page "Victoires/Défaites" (`src/ui/pages/win_loss.py`)

**Emplacement** : Nouvelle sous-section "Rang et score personnel" après "Par période".

**Visualisation proposée** :
- **Graphique** : Scatter plot ou barres groupées
  - Axe X : Matchs (chronologique)
  - Axe Y gauche : Rang (1 = meilleur, inverser pour affichage)
  - Axe Y droit : Score personnel
  - Couleur : Selon `outcome`
- **Tableau** : Colonnes `start_time`, `rank`, `personal_score`, `outcome`, `map_name`

**Fichier à modifier** :
- `src/ui/pages/win_loss.py` : Ajouter section
- `src/visualization/distributions.py` : Nouvelle fonction `plot_rank_and_personal_score()`

---

#### B. Page "Mes coéquipiers" (`src/ui/pages/teammates.py`)

**Emplacement** : Dans la vue single-teammate, après les métriques comparatives.

**Visualisation proposée** :
- **Graphique comparatif** : Comparer rang et score personnel entre moi et le coéquipier sur les matchs communs
  - Barres groupées : Mon rang vs rang du coéquipier (par match)
  - Scatter : Rang vs Score personnel (moi vs coéquipier)

**Fichier à modifier** :
- `src/ui/pages/teammates.py` : Ajouter section
- `src/ui/pages/teammates_charts.py` : Nouvelle fonction `render_rank_score_comparison()`

**Logique** :
```python
# Charger matchs communs
# Charger rank et personal_score depuis match_stats (moi) et match_participants ou DB coéquipier (lui)
# Comparer
```

---

## 2. Éléments à ajouter sur "timeseries" et "Mes coéquipiers"

### 2.1 Correlation between average life duration, deaths, and outcomes

**Description** : Analyser la corrélation entre la durée de vie moyenne (`avg_life_seconds`), les morts (`deaths`), et les résultats (`outcome`).

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonnes** : `avg_life_seconds` (FLOAT), `deaths` (SMALLINT), `outcome` (TINYINT)
- **Disponibilité** : ✅ Colonnes existent

**Où ajouter** :

#### A. Page "Séries temporelles" (`src/ui/pages/timeseries.py`)

**Emplacement** : Dans la section "Corrélations" existante (ligne ~195), ajouter ce nouveau scatter.

**Visualisation proposée** :
- **Graphique** : Scatter plot avec couleur selon `outcome`
  - Axe X : Durée de vie moyenne (`avg_life_seconds`)
  - Axe Y : Nombre de morts (`deaths`)
  - Couleur : `outcome` (vert=victoire, rouge=défaite, amber=égalité)
  - Ligne de tendance : Régression linéaire avec R²
- **Métrique** : Afficher le coefficient de corrélation de Pearson

**Fichier à modifier** :
- `src/ui/pages/timeseries.py` : Ajouter dans la section corrélations (ligne ~195)
- `src/visualization/distributions.py` : Utiliser `plot_correlation_scatter()` existant (ligne ~773) avec `x_col="avg_life_seconds"`, `y_col="deaths"`, `color_col="outcome"`

**Logique** :
```python
# Filtrer les données valides (non-NaN pour avg_life_seconds et deaths)
# Créer scatter avec plot_correlation_scatter()
# Calculer corrélation Pearson
```

---

#### B. Page "Mes coéquipiers" (`src/ui/pages/teammates.py`)

**Emplacement** : Dans la vue single-teammate, nouvelle section "Corrélations" après les métriques comparatives.

**Visualisation proposée** :
- **Graphique comparatif** : Deux scatter plots côte à côte (moi vs coéquipier)
  - Même axes (avg_life_seconds vs deaths)
  - Comparer les patterns de corrélation

**Fichier à modifier** :
- `src/ui/pages/teammates.py` : Ajouter section
- `src/ui/pages/teammates_charts.py` : Nouvelle fonction `render_life_deaths_correlation_comparison()`

---

### 2.2 Correlation between kills, deaths, and outcomes

**Description** : Analyser la corrélation entre kills, deaths, et outcomes.

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonnes** : `kills`, `deaths`, `outcome`
- **Disponibilité** : ✅ Colonnes existent

**Où ajouter** :

#### A. Page "Séries temporelles" (`src/ui/pages/timeseries.py`)

**Emplacement** : Dans la section "Corrélations" existante, ajouter ce scatter.

**Visualisation proposée** :
- **Graphique** : Scatter plot
  - Axe X : Kills
  - Axe Y : Deaths
  - Couleur : `outcome`
  - Ligne de tendance avec R²

**Fichier à modifier** :
- `src/ui/pages/timeseries.py` : Ajouter dans corrélations
- `src/visualization/distributions.py` : Utiliser `plot_correlation_scatter()` avec `x_col="kills"`, `y_col="deaths"`, `color_col="outcome"`

---

#### B. Page "Mes coéquipiers" (`src/ui/pages/teammates.py`)

**Emplacement** : Même section corrélations que 2.1.

**Visualisation proposée** :
- **Graphique comparatif** : Deux scatter plots côte à côte (moi vs coéquipier)

---

### 2.3 Correlation between enemy and friendly team MMR

**Description** : Analyser la corrélation entre le MMR de l'équipe ennemie (`enemy_mmr`) et le MMR de l'équipe alliée (`team_mmr`).

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonnes** : `team_mmr` (FLOAT), `enemy_mmr` (FLOAT)
- **Disponibilité** : ✅ Colonnes existent (`src/data/sync/engine.py` L.346-347)

**Où ajouter** :

#### A. Page "Séries temporelles" (`src/ui/pages/timeseries.py`)

**Emplacement** : Dans la section "Corrélations".

**Visualisation proposée** :
- **Graphique** : Scatter plot
  - Axe X : MMR équipe alliée (`team_mmr`)
  - Axe Y : MMR équipe ennemie (`enemy_mmr`)
  - Couleur : `outcome` (optionnel)
  - Ligne de tendance avec R²
  - Ligne de référence : `y=x` (équilibre théorique)

**Fichier à modifier** :
- `src/ui/pages/timeseries.py` : Ajouter dans corrélations
- `src/visualization/distributions.py` : Utiliser `plot_correlation_scatter()` avec `x_col="team_mmr"`, `y_col="enemy_mmr"`, `color_col="outcome"` (optionnel)

**Logique** :
```python
# Filtrer les données où team_mmr et enemy_mmr sont non-NaN
# Créer scatter
# Ajouter ligne y=x pour référence équilibre
```

---

#### B. Page "Mes coéquipiers" (`src/ui/pages/teammates.py`)

**Emplacement** : Section corrélations.

**Visualisation proposée** :
- **Graphique comparatif** : Deux scatter plots côte à côte (moi vs coéquipier)
  - Comparer les patterns de matchmaking (équipes équilibrées vs déséquilibrées)

---

### 2.4 Distribution of Personal Score Earned Per Minute

**Description** : Histogramme de la distribution du score personnel par minute (`personal_score / time_played_seconds * 60`).

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonnes** : `personal_score` (INTEGER), `time_played_seconds` (INTEGER)
- **Disponibilité** : ✅ Colonnes existent

**Où ajouter** :

#### A. Page "Séries temporelles" (`src/ui/pages/timeseries.py`)

**Emplacement** : Dans la section "Distributions" existante (ligne ~70), ajouter ce nouvel histogramme.

**Visualisation proposée** :
- **Graphique** : Histogramme avec KDE optionnel
  - Axe X : Score personnel par minute (calculé)
  - Axe Y : Fréquence (nombre de matchs)
  - KDE : Courbe de densité superposée

**Fichier à modifier** :
- `src/ui/pages/timeseries.py` : Ajouter dans distributions (ligne ~70)
- `src/visualization/distributions.py` : Utiliser `plot_histogram()` existant (ligne ~547) avec la série calculée

**Logique de calcul** :
```python
# Calculer personal_score_per_minute = (personal_score / time_played_seconds) * 60
# Filtrer les valeurs valides (non-NaN, time_played_seconds > 0)
# Créer histogramme avec plot_histogram()
```

---

#### B. Page "Mes coéquipiers" (`src/ui/pages/teammates.py`)

**Emplacement** : Nouvelle section "Distributions" dans la vue single-teammate.

**Visualisation proposée** :
- **Graphique comparatif** : Deux histogrammes superposés (moi vs coéquipier)
  - Comparer les distributions de score par minute

**Fichier à modifier** :
- `src/ui/pages/teammates.py` : Ajouter section
- `src/ui/pages/teammates_charts.py` : Nouvelle fonction `render_personal_score_per_min_distribution_comparison()`

---

### 2.5 Distribution of win ratio

**Description** : Histogramme de la distribution du taux de victoire (win ratio) calculé sur des fenêtres glissantes ou par période.

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonnes** : `outcome` (TINYINT)
- **Disponibilité** : ✅ Colonne existe

**Où ajouter** :

#### A. Page "Séries temporelles" (`src/ui/pages/timeseries.py`)

**Emplacement** : Dans la section "Distributions".

**Visualisation proposée** :
- **Graphique** : Histogramme avec KDE
  - Axe X : Taux de victoire (0.0 à 1.0 ou 0% à 100%)
  - Axe Y : Fréquence
  - **Calcul** : Win ratio sur fenêtres glissantes (ex. 10 matchs) ou par période (jour/semaine)

**Fichier à modifier** :
- `src/ui/pages/timeseries.py` : Ajouter dans distributions
- `src/visualization/distributions.py` : Nouvelle fonction `plot_win_ratio_distribution()`

**Logique de calcul** :
```python
# Option 1 : Fenêtre glissante de N matchs
# Parcourir les matchs triés par start_time
# Pour chaque fenêtre de 10 matchs, calculer win_rate = wins / total
# Créer histogramme des win_rate

# Option 2 : Par période (jour/semaine)
# Grouper par jour ou semaine
# Calculer win_rate par période
# Créer histogramme
```

---

#### B. Page "Mes coéquipiers" (`src/ui/pages/teammates.py`)

**Emplacement** : Section distributions.

**Visualisation proposée** :
- **Graphique comparatif** : Deux histogrammes superposés (moi vs coéquipier)

---

### 2.6 Performance Cumulée avec lignes verticales tous les 8 min

**Description** : Graphique de performance cumulée (net score = Kills - Deaths) avec lignes verticales pointillées tous les 8 minutes pour marquer la fin d'un match.

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonnes** : `start_time`, `kills`, `deaths`, `time_played_seconds`
- **Disponibilité** : ✅ Colonnes existent
- **Fonction existante** : `src/visualization/performance.py` → `plot_cumulative_net_score()` (ligne ~53)
  - **À modifier** : Ajouter les lignes verticales tous les 8 min

**Où ajouter** :

#### A. Page "Séries temporelles" (`src/ui/pages/timeseries.py`)

**Emplacement** : Dans la section "Performance cumulée & tendance" déjà ajoutée (après "Stats par minute").

**Visualisation proposée** :
- **Graphique** : Courbe de net score cumulé (déjà implémentée) + **lignes verticales pointillées**
  - Lignes verticales : Tous les 8 minutes depuis le début de la session
  - Couleur des lignes : Gris clair, style pointillé
  - Annotation optionnelle : "Match N" sur chaque ligne

**Fichier à modifier** :
- `src/visualization/performance.py` : Modifier `plot_cumulative_net_score()` pour accepter un paramètre `show_match_markers: bool = True` et calculer les positions des lignes
- `src/ui/pages/timeseries.py` : Passer `show_match_markers=True` lors de l'appel

**Logique de calcul** :
```python
# Dans plot_cumulative_net_score() :
# 1. Calculer le temps cumulé depuis le début de la session
#    cumulative_time_minutes = cumsum(time_played_seconds) / 60
# 2. Identifier les positions où cumulative_time_minutes est un multiple de 8
#    match_boundaries = [8, 16, 24, 32, ...]
# 3. Ajouter des lignes verticales avec fig.add_vline() à ces positions
```

**Note** : Si les données sont par match (pas minute par minute), les lignes seront aux positions correspondant à la fin de chaque match (approximativement tous les 8 min).

---

#### B. Page "Mes coéquipiers" (`src/ui/pages/teammates.py`)

**Emplacement** : Section "Tendance de session" déjà ajoutée.

**Visualisation proposée** :
- **Graphique** : Même graphique avec lignes verticales (si applicable sur la période filtrée)

---

## 3. Éléments à ajouter sur "Dernier match" et "Mes coéquipiers"

### 3.1 Distribution of Damage Dealt Values, Distribution of Damage Taken Values

**Description** : Histogrammes de la distribution des dégâts infligés (`damage_dealt`) et subis (`damage_taken`), idéalement sur le même graphe.

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonnes** : `damage_dealt` (FLOAT, nullable), `damage_taken` (FLOAT, nullable)
- **Disponibilité** : ✅ Colonnes existent (`src/data/sync/engine.py` L.348-349, `src/data/sync/models.py` L.195-196)

**Où ajouter** :

#### A. Page "Dernier match" (`src/ui/pages/last_match.py`)

**Emplacement** : Dans `render_match_view()` (`src/ui/pages/match_view.py`), nouvelle section "Dégâts" après les métriques principales.

**Visualisation proposée** :
- **Graphique** : Histogramme superposé (deux séries)
  - Série 1 : Distribution de `damage_dealt` (barres vertes/cyan, opacité 0.7)
  - Série 2 : Distribution de `damage_taken` (barres rouges, opacité 0.7)
  - Axe X : Valeur de dégâts (bins)
  - Axe Y : Fréquence
  - Légende : "Dégâts infligés" vs "Dégâts subis"

**Fichier à modifier** :
- `src/ui/pages/match_view.py` : Ajouter section dans `render_match_view()`
- `src/visualization/distributions.py` : Nouvelle fonction `plot_damage_distribution_combined()`

**Logique** :
```python
# Charger historique des matchs (dff ou df_full)
# Extraire damage_dealt et damage_taken (non-NaN)
# Créer histogramme avec deux séries superposées
# Utiliser même échelle de bins pour comparaison
```

**Note** : Pour le "Dernier match", on peut afficher :
- La distribution historique (tous les matchs) avec le dernier match mis en évidence
- Ou seulement le dernier match si on veut une vue plus large

---

#### B. Page "Mes coéquipiers" (`src/ui/pages/teammates.py`)

**Emplacement** : Dans la vue single-teammate, nouvelle section "Dégâts" après les métriques comparatives.

**Visualisation proposée** :
- **Graphique comparatif** : Deux histogrammes superposés (moi vs coéquipier)
  - Pour chaque joueur : distribution de damage_dealt et damage_taken
  - Quatre séries au total (moi dealt, moi taken, coéquipier dealt, coéquipier taken)
  - Ou deux graphiques côte à côte (dealt vs taken)

**Fichier à modifier** :
- `src/ui/pages/teammates.py` : Ajouter section
- `src/ui/pages/teammates_charts.py` : Nouvelle fonction `render_damage_distribution_comparison()`

**Logique** :
```python
# Charger matchs communs
# Charger damage_dealt et damage_taken pour moi et le coéquipier
# Créer histogrammes comparatifs
```

---

## 4. Éléments à ajouter sur "Timeseries" et "Dernier match"

### 4.1 Shots Fired / Shots Hit en barres + Précision en courbe

**Description** : Graphique combiné avec :
- Barres : Nombre de tirs effectués (`shots_fired`) et tirs réussis (`shots_hit`)
- Courbe : Précision (`accuracy`) sur axe Y secondaire

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonnes** : `shots_fired` (INTEGER, nullable), `shots_hit` (INTEGER, nullable), `accuracy` (FLOAT, nullable)
- **Disponibilité** : ✅ Colonnes existent (`src/data/sync/engine.py` L.350-351, `src/data/sync/models.py` L.197-198)
- **Note** : `match_participants` contient aussi `shots_fired` et `shots_hit` pour tous les joueurs

**Où ajouter** :

#### A. Page "Séries temporelles" (`src/ui/pages/timeseries.py`)

**Emplacement** : Nouvelle sous-section "Tirs et précision" après "Folie meurtrière / Tirs à la tête / Précision / Frags parfaits" (ligne ~290).

**Visualisation proposée** :
- **Graphique** : Barres groupées + courbe (axe Y secondaire)
  - Barres groupées :
    - Série 1 : `shots_fired` (barres cyan, opacité 0.7)
    - Série 2 : `shots_hit` (barres vertes, opacité 0.7)
  - Courbe : `accuracy` (ligne violette, axe Y secondaire)
  - Axe X : Matchs (chronologique)
  - Axe Y gauche : Nombre de tirs
  - Axe Y droit : Précision (%)

**Fichier à modifier** :
- `src/ui/pages/timeseries.py` : Ajouter section après ligne ~290
- `src/visualization/timeseries.py` : Nouvelle fonction `plot_shots_fired_hit_accuracy()`

**Logique** :
```python
# Utiliser make_subplots avec secondary_y=True
# Barres : shots_fired et shots_hit
# Courbe : accuracy sur secondary_y
```

---

#### B. Page "Dernier match" (`src/ui/pages/match_view.py`)

**Emplacement** : Dans `render_match_view()`, section "Combat" ou nouvelle section "Tirs".

**Visualisation proposée** :
- **Graphique** : Même type que Timeseries mais pour le dernier match uniquement
  - Barres : shots_fired et shots_hit du dernier match
  - Courbe : accuracy du dernier match (peut être un point unique)
  - Contexte historique : Afficher la moyenne historique en ligne pointillée

**Fichier à modifier** :
- `src/ui/pages/match_view.py` : Ajouter section
- `src/visualization/timeseries.py` : Réutiliser `plot_shots_fired_hit_accuracy()` ou créer variante pour un seul match

---

### 4.2 Damage taken/dealt avec moyenne lissée

**Description** : Graphique de dégâts infligés et subis avec courbe de moyenne lissée (rolling average).

**Données nécessaires** :
- **Table** : `match_stats`
- **Colonnes** : `damage_dealt`, `damage_taken`, `start_time`
- **Disponibilité** : ✅ Colonnes existent

**Où ajouter** :

#### A. Page "Séries temporelles" (`src/ui/pages/timeseries.py`)

**Emplacement** : Nouvelle sous-section "Dégâts" après "Tirs et précision".

**Visualisation proposée** :
- **Graphique** : Barres + courbes lissées
  - Barres :
    - Série 1 : `damage_dealt` (barres vertes/cyan, opacité 0.6)
    - Série 2 : `damage_taken` (barres rouges, opacité 0.6)
  - Courbes lissées :
    - Série 3 : Moyenne mobile de `damage_dealt` (fenêtre 10 matchs, ligne verte)
    - Série 4 : Moyenne mobile de `damage_taken` (fenêtre 10 matchs, ligne rouge pointillée)
  - Axe X : Matchs (chronologique)
  - Axe Y : Dégâts

**Fichier à modifier** :
- `src/ui/pages/timeseries.py` : Ajouter section
- `src/visualization/timeseries.py` : Nouvelle fonction `plot_damage_timeseries_with_smooth()`

**Logique** :
```python
# Calculer moyenne mobile avec rolling(window=10)
# Créer graphique avec barres + courbes superposées
```

---

#### B. Page "Dernier match" (`src/ui/pages/match_view.py`)

**Emplacement** : Section "Dégâts" (voir 3.1).

**Visualisation proposée** :
- **Graphique** : Même type mais pour le dernier match avec contexte historique
  - Barres : damage_dealt et damage_taken du dernier match
  - Lignes de référence : Moyennes historiques (pointillées)

---

## 5. Visualisations différences joueurs (Mes coéquipiers)

**Rôle** : Data analyst pour proposer des représentations visuelles des différences entre joueurs.

### 5.1 Nombre de tirs total et nombre de tirs réussis

**Données** :
- **Table** : `match_stats` ou `match_participants`
- **Colonnes** : `shots_fired`, `shots_hit`
- **Disponibilité** : ✅ Colonnes existent

**Propositions de visualisations** :

#### A. Graphique en barres groupées comparatif
- **Type** : Barres groupées horizontales
- **Axe Y** : Joueurs (moi, coéquipier 1, coéquipier 2, ...)
- **Axe X** : Nombre de tirs
- **Séries** :
  - Série 1 : Shots Fired (barres cyan)
  - Série 2 : Shots Hit (barres vertes)
- **Emplacement** : Vue multi-coéquipiers (`_render_multi_teammate_view`)

#### B. Scatter plot comparatif
- **Type** : Scatter plot
- **Axe X** : Shots Fired
- **Axe Y** : Shots Hit
- **Points** : Un point par joueur (moi vs coéquipiers)
- **Ligne de référence** : Ligne de précision 100% (y=x)
- **Emplacement** : Vue single ou multi-coéquipiers

#### C. Graphique radar (si plusieurs coéquipiers)
- **Type** : Radar chart
- **Axes** : Shots Fired, Shots Hit, Accuracy (shots_hit/shots_fired), Headshot Rate (si disponible)
- **Séries** : Une série par joueur
- **Emplacement** : Vue multi-coéquipiers

#### D. Heatmap de précision par match
- **Type** : Heatmap
- **Axe X** : Matchs (chronologique)
- **Axe Y** : Joueurs
- **Couleur** : Précision (shots_hit/shots_fired) avec échelle de couleurs
- **Emplacement** : Vue multi-coéquipiers sur matchs communs

**Fichiers à créer/modifier** :
- `src/ui/pages/teammates_charts.py` : Nouvelles fonctions
  - `render_shots_comparison_bars()`
  - `render_shots_scatter_comparison()`
  - `render_shots_radar_comparison()`
  - `render_shots_heatmap_comparison()`

---

### 5.2 Dégâts subis et dégâts infligés (damage taken/dealt)

**Données** :
- **Table** : `match_stats` ou `match_participants`
- **Colonnes** : `damage_dealt`, `damage_taken`
- **Disponibilité** : ✅ Colonnes existent

**Propositions de visualisations** :

#### A. Graphique en barres groupées comparatif
- **Type** : Barres groupées horizontales
- **Axe Y** : Joueurs
- **Axe X** : Dégâts
- **Séries** :
  - Série 1 : Damage Dealt (barres vertes/cyan)
  - Série 2 : Damage Taken (barres rouges)
- **Ratio** : Afficher le ratio dealt/taken comme annotation

#### B. Scatter plot "Efficacité défensive vs offensive"
- **Type** : Scatter plot
- **Axe X** : Damage Dealt (offensif)
- **Axe Y** : Damage Taken (défensif, inversé pour meilleure interprétation)
- **Points** : Un point par joueur
- **Quadrants** :
  - Haut-gauche : Offensif mais vulnérable
  - Haut-droite : Offensif et résistant (idéal)
  - Bas-gauche : Défensif mais peu offensif
  - Bas-droite : Défensif et peu offensif

#### C. Graphique en aires empilées par match
- **Type** : Area chart empilé
- **Axe X** : Matchs (chronologique)
- **Axe Y** : Dégâts cumulés
- **Séries** : Une série par joueur (damage_dealt)
- **Emplacement** : Vue multi-coéquipiers sur matchs communs

#### D. Ratio Damage Dealt/Taken par joueur
- **Type** : Barres horizontales
- **Axe Y** : Joueurs
- **Axe X** : Ratio (damage_dealt / damage_taken)
- **Ligne de référence** : Ratio = 1.0 (équilibre)
- **Couleur** : Vert si ratio > 1, rouge si ratio < 1

**Fichiers à créer/modifier** :
- `src/ui/pages/teammates_charts.py` : Nouvelles fonctions
  - `render_damage_comparison_bars()`
  - `render_damage_efficiency_scatter()`
  - `render_damage_stacked_area()`
  - `render_damage_ratio_bars()`

---

## 6. Ajouts et mise à jour de graphes existants

### 6.1 Matchs Top vs Total par semaine → adapter pour périodes < semaine + ajouter à Mes coéquipiers

**Description** : Adapter `plot_matches_at_top_by_week()` pour gérer les périodes plus petites qu'une semaine et l'ajouter à "Mes coéquipiers".

**Fonction existante** :
- **Fichier** : `src/visualization/distributions.py`
- **Fonction** : `plot_matches_at_top_by_week()` (ligne ~956)
- **Problème actuel** : Force le groupement par semaine (`dt.to_period("W-MON")`)

**Modifications à apporter** :

#### A. Adapter la fonction pour périodes flexibles

**Fichier à modifier** : `src/visualization/distributions.py`

**Changements** :
1. Ajouter paramètre `period: str = "week"` avec options : `"day"`, `"week"`, `"month"`
2. Logique de groupement dynamique :
   ```python
   if period == "day":
       d["period"] = d["start_time"].dt.to_period("D").astype(str)
   elif period == "week":
       d["period"] = d["start_time"].dt.to_period("W-MON").astype(str)
   elif period == "month":
       d["period"] = d["start_time"].dt.to_period("M").astype(str)
   ```
3. Détection automatique : Si la période filtrée est < 7 jours, utiliser `period="day"` par défaut
4. Mettre à jour les labels d'axe X selon la période

**Signature proposée** :
```python
def plot_matches_at_top_by_period(
    df: pd.DataFrame,
    *,
    title: str | None = None,
    rank_col: str = "rank",
    top_n_ranks: int = 1,
    period: str | None = None,  # "day", "week", "month", ou None pour auto
) -> go.Figure:
```

**Fichiers à modifier** :
- `src/visualization/distributions.py` : Modifier `plot_matches_at_top_by_week()` ou créer `plot_matches_at_top_by_period()`
- `src/ui/pages/win_loss.py` : Mettre à jour l'appel (ligne ~197) pour utiliser la nouvelle fonction

---

#### B. Ajouter à "Mes coéquipiers"

**Emplacement** : Dans la vue single-teammate (`_render_single_teammate_view`), nouvelle section "Matchs Top" après les métriques comparatives.

**Visualisation proposée** :
- **Graphique comparatif** : Deux graphiques côte à côte (moi vs coéquipier)
  - Chaque graphique : Matchs Top vs Total par période
  - Comparer les taux "Top" entre les deux joueurs

**Fichier à modifier** :
- `src/ui/pages/teammates.py` : Ajouter section dans `_render_single_teammate_view()`
- `src/ui/pages/teammates_charts.py` : Nouvelle fonction `render_top_matches_comparison()`

**Logique** :
```python
# Charger matchs communs
# Calculer "Top" pour moi et le coéquipier séparément
# Afficher deux graphiques côte à côte avec plot_matches_at_top_by_period()
```

---

### 6.2 Heatmap à mettre sur mes coéquipiers aussi

**Description** : Ajouter la heatmap Win Ratio par jour et heure (`plot_win_ratio_heatmap`) à la page "Mes coéquipiers".

**Fonction existante** :
- **Fichier** : `src/visualization/distributions.py`
- **Fonction** : `plot_win_ratio_heatmap()` (ligne ~384)
- **Utilisation actuelle** : `src/ui/pages/win_loss.py` (ligne ~162)

**Où ajouter** :

**Emplacement** : Dans la vue single-teammate (`_render_single_teammate_view`), nouvelle section "Win Rate par jour et heure" après les métriques comparatives.

**Visualisation proposée** :
- **Graphique comparatif** : Deux heatmaps côte à côte (moi vs coéquipier)
  - Chaque heatmap : Win Rate par jour de semaine (lignes) et heure (colonnes)
  - Comparer les créneaux où chaque joueur performe le mieux

**Fichier à modifier** :
- `src/ui/pages/teammates.py` : Ajouter section dans `_render_single_teammate_view()`
- `src/ui/pages/teammates_charts.py` : Nouvelle fonction `render_win_ratio_heatmap_comparison()`

**Logique** :
```python
# Charger matchs communs
# Calculer win_ratio_heatmap pour moi et le coéquipier séparément
# Afficher deux heatmaps côte à côte avec plot_win_ratio_heatmap()
```

---

### 6.3 Retirer la précision du graphe "Folie meurtrière / Tirs à la tête / Précision / Frags parfaits"

**Description** : Retirer la série "Précision (%)" du graphique `plot_spree_headshots_accuracy()`.

**Fonction existante** :
- **Fichier** : `src/visualization/timeseries.py`
- **Fonction** : `plot_spree_headshots_accuracy()` (ligne ~508)
- **Série à retirer** : Ligne ~590-600 (trace Scatter avec `accuracy` sur secondary_y)

**Modifications à apporter** :

**Fichier à modifier** : `src/visualization/timeseries.py`

**Changements** :
1. Supprimer la trace Scatter de la précision (lignes ~590-600)
2. Supprimer l'axe Y secondaire (`secondary_y=True` dans `make_subplots`)
3. Mettre à jour le titre de la fonction/docstring : "Folie meurtrière / Tirs à la tête / Frags parfaits"
4. Mettre à jour les appels dans `src/ui/pages/timeseries.py` (ligne ~290) : Le titre affiché peut rester le même ou être mis à jour

**Code à retirer** :
```python
# Lignes ~590-600 à supprimer :
fig.add_trace(
    go.Scatter(
        x=x_idx,
        y=d["accuracy"],
        mode="lines",
        name="Précision (%)",
        line={"width": PLOT_CONFIG.line_width, "color": colors["violet"]},
        hovertemplate="précision=%{y:.2f}%<extra></extra>",
    ),
    secondary_y=True,
)

# Et mettre à jour :
fig.update_yaxes(
    title_text="Précision (%)", ticksuffix="%", rangemode="tozero", secondary_y=True
)
# → Supprimer cette ligne car plus d'axe secondaire
```

**Impact** :
- `src/ui/pages/timeseries.py` : Aucun changement nécessaire (la fonction sera appelée de la même manière)
- Le graphique affichera uniquement : Folie meurtrière, Tirs à la tête, Frags parfaits (tous sur le même axe Y)

---

## Résumé des fichiers à créer/modifier

### Fichiers à créer

1. `src/analysis/win_streaks.py` : Calculs de séries de victoires
2. `src/visualization/damage_charts.py` : Graphiques de dégâts (optionnel, peut être dans distributions.py)

### Fichiers à modifier

#### Pages UI
- `src/ui/pages/timeseries.py` : Ajouts sections corrélations, distributions, performance cumulée (lignes modifiées)
- `src/ui/pages/win_loss.py` : Ajouts Per-Match Personal Score, Win Streaks, Rang/Score (lignes modifiées)
- `src/ui/pages/teammates.py` : Ajouts multiples sections comparatives (lignes modifiées)
- `src/ui/pages/last_match.py` : Pas de modification directe (utilise match_view.py)
- `src/ui/pages/match_view.py` : Ajouts sections Dégâts, Tirs (lignes modifiées)

#### Visualisations
- `src/visualization/timeseries.py` : Nouvelle fonction `plot_shots_fired_hit_accuracy()`, `plot_damage_timeseries_with_smooth()`, modification `plot_spree_headshots_accuracy()`
- `src/visualization/distributions.py` : Nouvelles fonctions `plot_personal_score_by_match()`, `plot_win_streak_distribution()`, `plot_weekly_longest_streak()`, `plot_rank_and_personal_score()`, `plot_win_ratio_distribution()`, `plot_damage_distribution_combined()`, modification `plot_matches_at_top_by_week()` → `plot_matches_at_top_by_period()`
- `src/visualization/performance.py` : Modification `plot_cumulative_net_score()` pour ajouter lignes verticales

#### Composants coéquipiers
- `src/ui/pages/teammates_charts.py` : Nouvelles fonctions comparatives (voir détails section 5)

#### Analyse
- `src/data/query/analytics.py` : Extension `get_win_streak_stats()` pour calculs par semaine et distribution

---

## Ordre de priorité suggéré

1. **Phase 1** : Modifications simples (retirer précision, adapter période)
2. **Phase 2** : Ajouts sur Timeseries (corrélations, distributions, performance cumulée)
3. **Phase 3** : Ajouts sur Victoires/Défaites (Personal Score, Win Streaks, Rang/Score)
4. **Phase 4** : Ajouts sur Dernier match (Dégâts, Tirs)
5. **Phase 5** : Ajouts sur Mes coéquipiers (toutes les comparaisons)

---

**Document généré le** : 2026-02-07  
**Dernière mise à jour** : 2026-02-07
