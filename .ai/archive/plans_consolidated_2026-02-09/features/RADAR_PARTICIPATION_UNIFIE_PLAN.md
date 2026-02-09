# Planification : Radar de participation unifié (6 axes)

> Concept réutilisable pour Dernier match et Mes coéquipiers.
> **Implémenté** 2026-02-06.

---

## 1. Objectif

Remplacer les graphiques actuels "Participation au match" par un **seul radar à 6 axes** représentant le profil de participation du joueur. Le concept doit être **souple et réutilisable** :
- **Dernier match** : un seul radar pour le match courant
- **Mes coéquipiers** : comparaison moi vs coéquipier(s) sur le même radar

---

## 2. Les 6 axes

| # | Axe | Description | Source | Normalisation |
|---|-----|-------------|--------|---------------|
| 1 | **Objectifs** | Contribution à la victoire | PersonalScores | `min(1, score / 800)` |
| 2 | **Combat** | Éliminations directes | PersonalScores | `min(1, kill_score / 1500)` |
| 3 | **Support** | Aide aux coéquipiers | PersonalScores | `min(1, assist_score / 400)` |
| 4 | **Score** | Points totaux du match | PersonalScores | `min(1, score_total / 2000)` |
| 5 | **Impact** | Intensité de participation | PersonalScores + match_stats | `min(1, pts_min / 150)` |
| 6 | **Survie** | Moins de morts + durée vie moy | match_stats | Mélange 50/50 (voir § Survie) |

### Détail des calculs

- **Objectifs** : En mode objectif (CTF, Oddball, etc.) = `objective_score`. En mode Slayer = `kill_score` (les frags sont l'objectif).
- **Score** : `kill_score + assist_score + objective_score + vehicle_score + penalty_score` (les pénalités sont négatives).
- **Impact** : `(kill + assist + objective + vehicle) / durée_min`.
- **Survie** : Mélange 50/50 de :
  - **Composant morts** : `max(0, 1 - deaths_per_min / 2)` (2 morts/min = 0%)
  - **Composant durée de vie** : `min(1, avg_life_seconds / 90)` (90 sec = 100%)
  - Si `avg_life_seconds` absent → fallback sur le seul composant morts.

### Seuils de référence (configurables)

```python
RADAR_THRESHOLDS = {
    "objectifs": 1600,
    "combat": 3000,
    "support": 800,
    "score": 4000,
    "impact_pts_per_min": 250,
    "survie_deaths_per_min_ref": 2.0,
    "survie_avg_life_ref_seconds": 90.0,
}
```

### Seuils globaux (meilleur match)

`compute_global_radar_thresholds()` scanne toutes les DBs `data/players/*/stats.duckdb`, exclut Firefight et BTB (scores disproportionnés), et calcule les max par catégorie. Seuils = max × 0.85 pour éviter un radar vide tout en gardant de la marge.

---

## 3. Architecture de réutilisation

### 3.1 Module partagé : agrégation des données

**Fichier** : `src/visualization/participation_radar.py` (nouveau)

```python
# Contrat d'entrée
def compute_participation_profile(
    awards_df: pl.DataFrame,
    match_stats_row: dict | pl.Series | None = None,
    *,
    mode_is_objective: bool | None = None,
    thresholds: dict | None = None,
) -> dict:
    """Calcule le profil de participation (6 axes) pour un ou plusieurs matchs.
    
    Returns:
        {
            "objectifs_raw": int,
            "combat_raw": int,
            "support_raw": int,
            "score_raw": int,
            "impact_raw": float,  # pts/min
            "survie_raw": float,  # 0-1 (1 = 0 mort/min)
            "objectifs_norm": float,  # 0-1
            ...
        }
    """
```

**Contrat de sortie** : dict compatible avec `create_participation_profile_radar()`.

### 3.2 Composant radar unique

**Fichier** : `src/ui/components/radar_chart.py`

```python
def create_participation_profile_radar(
    profiles: list[dict],
    *,
    title: str = "Profil de participation",
    height: int = 400,
    thresholds: dict | None = None,
) -> go.Figure:
    """Radar à 6 axes : Objectifs, Combat, Support, Score, Impact, Survie.
    
    Args:
        profiles: Liste de dicts avec format:
            [
                {
                    "name": "Moi" | "Coéquipier" | "Ce match",
                    "objectifs_raw": 300,
                    "combat_raw": 800,
                    ...
                    "color": "#636EFA",
                },
                ...
            ]
        thresholds: Seuils de normalisation (optionnel, défauts dans constante).
    """
```

- **Un seul profil** : affichage d'un polygone.
- **Plusieurs profils** : superposition avec légende (cas coéquipiers).

### 3.3 Détection du mode objectif

- **Dernier match** : `row["pair_name"]` → `extract_mode_category()` ou `game_variant_category` si disponible.
- **Référence** : `src/data/domain/refdata.py` → `is_objective_mode(category)` ou logique sur `pair_name` (CTF, Oddball, Strongholds, etc.).

---

## 4. Plan d'implémentation

### Phase 1 : Module de calcul

| Tâche | Fichier | Description |
|-------|---------|-------------|
| 1.1 | `src/visualization/participation_radar.py` | Créer le module avec `RADAR_THRESHOLDS`, `compute_participation_profile()` |
| 1.2 | — | `compute_participation_profile()` : agrège PersonalScores + optionnel match_stats (deaths, duration) |
| 1.3 | — | Gérer le cas multi-matchs (agrégation par somme, durée = somme des durées) |
| 1.4 | `src/visualization/__init__.py` | Exporter `compute_participation_profile` |

### Phase 2 : Composant radar

| Tâche | Fichier | Description |
|-------|---------|-------------|
| 2.1 | `src/ui/components/radar_chart.py` | Créer `create_participation_profile_radar()` |
| 2.2 | — | 6 axes : Objectifs, Combat, Support, Score, Impact, Survie |
| 2.3 | — | Normalisation via seuils, hover avec valeurs brutes |
| 2.4 | — | Support multi-profils (couleurs, légende) |

### Phase 3 : Intégration Dernier match

| Tâche | Fichier | Description |
|-------|---------|-------------|
| 3.1 | `src/ui/pages/match_view_participation.py` | Remplacer radar + pie + indicateur par un seul radar |
| 3.2 | — | Charger `personal_score_awards` + `match_stats` (row) pour le match courant |
| 3.3 | — | Détecter mode objectif via `pair_name` ou `mode_category` |
| 3.4 | — | Appeler `compute_participation_profile()` puis `create_participation_profile_radar()` |

### Phase 4 : Intégration Mes coéquipiers

| Tâche | Fichier | Description |
|-------|---------|-------------|
| 4.1 | `src/ui/pages/teammates.py` | Remplacer `create_teammate_synergy_radar` par `create_participation_profile_radar` |
| 4.2 | — | Charger PersonalScores pour moi + coéquipier(s) sur matchs partagés |
| 4.3 | — | Charger match_stats (deaths, duration) pour chaque joueur depuis leurs DBs |
| 4.4 | — | Construire liste de profils (Moi, Coéquipier 1, …) et afficher le radar comparatif |

### Phase 5 : Nettoyage (optionnel)

| Tâche | Fichier | Description |
|-------|---------|-------------|
| 5.1 | `src/visualization/participation_charts.py` | Marquer `aggregate_participation_for_radar`, `create_participation_indicator`, `plot_participation_pie` comme dépréciés si plus utilisés |
| 5.2 | `src/ui/components/radar_chart.py` | Garder `create_participation_radar` (ancien) pour compatibilité ou le remplacer par un alias vers le nouveau |

---

## 5. Données requises

### PersonalScores (personal_score_awards)

| Colonne | Usage |
|---------|-------|
| `award_category` | kill, assist, objective, vehicle, penalty |
| `award_score` ou `total_points` | Somme par catégorie |
| `match_id` | Filtrage |

### match_stats (pour Impact et Survie)

| Colonne | Usage |
|---------|-------|
| `deaths` | Survie (composant morts) |
| `time_played_seconds` | Impact (durée en min) |
| `avg_life_seconds` / `average_life_seconds` | Survie (composant durée de vie moyenne) |

### Mode objectif

- `pair_name` ou `mode_category` : pour adapter l'axe Objectifs (obj vs kills).

---

## 6. Cas particuliers

| Cas | Comportement |
|-----|--------------|
| PersonalScores vide | Ne pas afficher la section (comportement actuel) |
| Pas de match_stats (deaths, duration) | Impact = 0 ou dérivé des awards uniquement ; Survie = 1 (neutre) |
| Mode inconnu | Considérer mode objectif (objective_score), ou fallback kill_score |
| Plusieurs matchs (coéquipiers) | Agréger : sommes des scores, somme des durées, moyenne des deaths/min |

---

## 7. Tests

- `tests/test_participation_radar.py` : `compute_participation_profile()` avec jeux de données (mode obj, mode slayer, vide).
- Tests du composant radar : 1 profil, 2 profils, valeurs aux limites (0, au-dessus des seuils).

---

## 8. Implémentation (2026-02-06)

| Fichier | Rôle |
|---------|------|
| `src/visualization/participation_radar.py` | `RADAR_THRESHOLDS`, `RADAR_AXIS_LINES`, `compute_participation_profile()`, `compute_global_radar_thresholds()`, `get_radar_thresholds()` |
| `src/ui/components/radar_chart.py` | `create_participation_profile_radar()` (thème Halo appliqué) |
| `src/ui/pages/match_view_participation.py` | Section Dernier match (radar + légende axes sur même rangée) |
| `src/ui/pages/teammates.py` | Section Complémentarité (Moi vs Coéquipier) |
| `src/ui/pages/session_compare.py` | Comparaison Session A vs B |
| `tests/test_participation_radar.py` | Tests `compute_participation_profile` |

### Raffinements post-implémentation

- **Thème** : Fond sombre aligné avec les autres graphiques (`apply_halo_plot_style`, `THEME_COLORS`).
- **Normalisation** : Seuils dérivés du meilleur match global (hors Firefight/BTB), facteur 0.85.
- **Survie** : Mélange morts/min + durée de vie moyenne (50/50).
- **Légende** : `RADAR_AXIS_LINES` affichée à droite du radar, une ligne par axe.

---

## 9. Références

- `.ai/thought_log.md` : journal des décisions
- `src/visualization/participation_charts.py` : ancien code (aggregate_participation_for_radar conservé pour compatibilité)
- `src/analysis/objective_participation.py` : `is_objective_mode_match`, `OBJECTIVE_SCORES`
