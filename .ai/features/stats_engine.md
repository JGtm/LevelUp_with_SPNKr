# Stats Engine - Moteur de Calculs Statistiques

> **Features implémentées (S0-S5)** : P2 (migration Polars core), P3 (damage participants), P5 (score performance v4 — 8 métriques).

## Résumé
Ensemble de modules pour le calcul des statistiques de performance Halo Infinite. Inclut les agrégations (kills, deaths, assists), les taux de victoire, le score de performance relatif v4 (comparaison à l'historique personnel sur 8 métriques), et les analyses par session/catégorie de mode.

## Inputs
- **DataFrame de matchs** (Polars) avec colonnes :
  - `kills`, `deaths`, `assists` : Stats brutes
  - `outcome` : Résultat (2=Win, 3=Loss, 1=Tie, 4=NoFinish)
  - `kda`, `accuracy` : Ratios calculés
  - `time_played_seconds` : Durée du match
  - `pair_name` : Nom du couple mode/carte
  - `max_killing_spree`, `headshot_kills` : Stats avancées
  - `team_mmr`, `enemy_mmr` : MMR des équipes

## Outputs
- **AggregatedStats** : Totaux (kills, deaths, assists, matches, temps)
- **OutcomeRates** : Comptages wins/losses/ties/no_finish
- **Performance Score** (0-100) : Comparaison relative à l'historique
- **Session Performance** : Métriques agrégées par session

## Dépendances
- **Packages externes** :
  - `polars` : DataFrames (Pandas proscrit — migré en S2)
  - `math` : Calculs mathématiques
- **Modules internes** :
  - `src.models` : AggregatedStats, OutcomeRates
  - `src.analysis.performance_config` : Configuration des poids (v4 depuis S5)
  - `src.analysis.mode_categories` : Inférence de catégories

## Logique Métier

### Score de Performance RELATIF v4 (0-100) — Implémenté S5

Compare chaque match à l'historique personnel du joueur :
- **50** = Match dans la moyenne
- **100** = Meilleur match de l'historique
- **0** = Pire match de l'historique

```python
# Métriques utilisées (8 métriques v4, normalisées par minute)
KPM = kills / (duration / 60)    # Kills Per Minute
DPM = deaths / (duration / 60)   # Deaths Per Minute (inversé)
APM = assists / (duration / 60)  # Assists Per Minute
KDA = (kills + assists) / max(1, deaths)
Accuracy = % de tirs touchés
PSPM = personal_score / (duration / 60)  # Personal Score Per Minute
DmgPM = damage_dealt / (duration / 60)   # Damage Per Minute
rank_perf = performance relative au rang  # Rank Performance

# Pondérations v4 (depuis performance_config.py)
RELATIVE_WEIGHTS = {
    "kpm": 0.20,       # Impact principal
    "dpm": 0.15,       # Survie
    "apm": 0.10,       # Support
    "kda": 0.15,       # Ratio global
    "accuracy": 0.10,  # Précision
    "pspm": 0.10,      # Score personnel/min
    "dmgpm": 0.10,     # Dégâts/min
    "rank_perf": 0.10, # Performance au rang
}

# Calcul du percentile pour chaque métrique
# Puis moyenne pondérée des percentiles
```

### Calcul du Percentile
```python
def _percentile_rank(value, series):
    """Retourne 0-100 où 50 = médiane."""
    below_or_equal = (series <= value).sum()
    return (below_or_equal / len(series)) * 100

def _percentile_rank_inverse(value, series):
    """Pour les morts: moins = mieux."""
    above_or_equal = (series >= value).sum()
    return (above_or_equal / len(series)) * 100
```

### Score de Session (v2)
Composantes pondérées avec renormalisation dynamique :

| Composante | Poids | Calcul |
|------------|-------|--------|
| K/D | 25% | Ratio × 50, cap à 100 |
| Victoires | 20% | win_rate × 100 |
| Précision | 15% | accuracy directe |
| Kills/min | 15% | Saturation exponentielle (scale=0.8) |
| Survie | 10% | avg_life × saturation (scale=50) |
| Objectif | 15% | Points pondérés par type |

### Ajustement MMR
```python
# Si équipe plus forte (delta > 0) → Réduit légèrement le score
# Si équipe plus faible (delta < 0) → Augmente légèrement
adjustment = clamp((-delta_mmr / 300) * 5, -5%, +5%)
final_score *= (1 + adjustment)
```

### Catégories de Mode
```python
# Inférence depuis pair_name
extract_mode_category("Arena:Slayer on Aquarius") → "Ranked"
extract_mode_category("BTB:Big Team Battle on Highpower") → "BTB"
extract_mode_category("PVE:Firefight on Oasis") → "Firefight"

# Catégories: Assassin, Fiesta, BTB, Ranked, Firefight, Other
```

## Points d'Attention
- **MIN_MATCHES_FOR_RELATIVE** : Minimum 10 matchs pour score relatif fiable
- **Durée par défaut** : 600s (10 min) si `time_played_seconds` manquant
- **Confidence** : Indicateur basé sur le nombre de matchs (faible < 4, moyenne < 10, élevée ≥ 10)
- **Colonnes objectif** : Pondérations différentes (flag_captures × 3, zones_captured × 2, etc.)

## Fichiers Clés
| Fichier | Rôle |
|---------|------|
| `src/analysis/stats.py` | Agrégations de base |
| `src/analysis/performance_score.py` | Score relatif et session |
| `src/analysis/performance_config.py` | Configuration centralisée |
| `src/analysis/mode_categories.py` | Inférence de catégories |
| `src/analysis/sessions.py` | Détection de sessions |
| `src/analysis/killer_victim.py` | Analyse killer/victim |
