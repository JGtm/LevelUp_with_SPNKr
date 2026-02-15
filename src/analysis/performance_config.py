"""Configuration centralisée du score de performance.

Ce module définit toutes les constantes et descriptions du score de performance
pour assurer la cohérence dans toute l'application.
"""

from __future__ import annotations

from dataclasses import dataclass

# =============================================================================
# Version du score
# =============================================================================

PERFORMANCE_SCORE_VERSION = "v4-relative"
# Version actuelle de l'algorithme de score.
#
# Historique:
# - v1: Score absolu basé sur K/D, victoires, précision
# - v2: Score modulaire avec composantes et poids dynamiques
# - v3-relative: Score relatif à l'historique personnel du joueur
# - v4-relative: v3 + PSPM, DPM damage, Rank Performance (8 métriques)


# =============================================================================
# Paramètres du calcul
# =============================================================================

MIN_MATCHES_FOR_RELATIVE = 10  # Nombre minimum de matchs pour activer le score relatif

# Poids des métriques pour le score relatif v4
RELATIVE_WEIGHTS = {
    "kpm": 0.22,  # Kills per minute
    "dpm_deaths": 0.18,  # Deaths per minute (inversé)
    "apm": 0.10,  # Assists per minute
    "kda": 0.15,  # FDA
    "accuracy": 0.08,  # Précision
    "pspm": 0.12,  # Personal Score Per Minute (NOUVEAU v4)
    "dpm_damage": 0.10,  # Damage Per Minute (NOUVEAU v4)
    "rank_perf": 0.05,  # Rank vs Expected (NOUVEAU v4, optionnel)
}

# Anciens poids v3 (conservés pour référence)
RELATIVE_WEIGHTS_V3 = {
    "kpm": 0.30,
    "dpm": 0.25,
    "apm": 0.15,
    "kda": 0.20,
    "accuracy": 0.10,
}

# Seuils de couleur pour l'affichage
SCORE_THRESHOLDS = {
    "excellent": 75,  # Vert
    "good": 60,  # Cyan
    "average": 45,  # Ambre
    "below_average": 30,  # Orange
    # < 30 = Rouge
}

# Labels associés aux seuils
SCORE_LABELS = {
    "excellent": "Excellent",
    "good": "Bon",
    "average": "Moyen",
    "below_average": "Faible",
    "bad": "Difficile",
}


# =============================================================================
# Description centralisée (pour l'UI)
# =============================================================================

PERFORMANCE_SCORE_TITLE = "Score de performance"

PERFORMANCE_SCORE_SHORT_DESC = "Relatif à ton historique"

PERFORMANCE_SCORE_FULL_DESC = f"""
Le **score de performance** (0-100) est un indicateur **relatif** qui compare
ta performance sur un match à ton **historique personnel**.

### Métriques utilisées
| Métrique | Poids | Description |
|----------|-------|-------------|
| KPM (Kills/min) | 22% | Frags par minute |
| DPM Deaths (Deaths/min) | 18% | Morts par minute (inversé) |
| FDA (KDA) | 15% | Ratio (Frags + Assists) / Morts |
| PSPM (Score/min) | 12% | Score personnel par minute |
| APM (Assists/min) | 10% | Assistances par minute |
| DPM Damage (Damage/min) | 10% | Dégâts infligés par minute |
| Précision | 8% | Pourcentage de tirs touchés |
| Rang vs Attendu | 5% | Performance du rang ajustée par le MMR |

### Interprétation
| Score | Signification |
|-------|---------------|
| **75-100** | Match exceptionnel pour toi |
| **60-75** | Au-dessus de ta moyenne |
| **45-60** | Performance typique |
| **30-45** | En-dessous de ta moyenne |
| **0-30** | Mauvaise partie pour toi |

### Calcul
1. Pour chaque métrique, on calcule le **percentile** de ta perf dans ce match
   par rapport à tout ton historique
2. Les percentiles sont combinés avec les poids ci-dessus
3. **50 = ta performance médiane**
4. Les métriques non disponibles sont ignorées (poids renormalisés)

### Notes
- Nécessite au moins **{MIN_MATCHES_FOR_RELATIVE} matchs** dans l'historique
- Le score est **stocké en DB** au moment de l'import
- Un joueur qui s'améliore verra ses nouveaux scores monter au-dessus de 50
"""


PERFORMANCE_SCORE_COMPACT_DESC = f"""
**Score relatif (0-100)** comparant ce match à ton historique.
- >=75: Exceptionnel | >=60: Bon | >=45: Normal | >=30: Sous ta moyenne | <30: Difficile
- 8 métriques: KPM ({RELATIVE_WEIGHTS['kpm']:.0%}), DPM inversé ({RELATIVE_WEIGHTS['dpm_deaths']:.0%}), FDA ({RELATIVE_WEIGHTS['kda']:.0%}), PSPM ({RELATIVE_WEIGHTS['pspm']:.0%}), APM ({RELATIVE_WEIGHTS['apm']:.0%}), DPM Damage ({RELATIVE_WEIGHTS['dpm_damage']:.0%}), Précision ({RELATIVE_WEIGHTS['accuracy']:.0%}), Rang ({RELATIVE_WEIGHTS['rank_perf']:.0%})
- Minimum {MIN_MATCHES_FOR_RELATIVE} matchs requis
"""


# =============================================================================
# Dataclass pour les résultats
# =============================================================================


@dataclass(frozen=True)
class PerformanceScoreResult:
    """Résultat d'un calcul de score de performance."""

    score: float | None
    """Score final 0-100 ou None si non calculable."""

    version: str = PERFORMANCE_SCORE_VERSION
    """Version de l'algorithme utilisé."""

    percentiles: dict[str, float] | None = None
    """Percentiles par métrique (optionnel, pour debug)."""

    match_count_ref: int | None = None
    """Nombre de matchs de référence utilisés."""

    @property
    def label(self) -> str:
        """Label textuel du score."""
        if self.score is None:
            return "N/A"
        if self.score >= SCORE_THRESHOLDS["excellent"]:
            return "Exceptionnel"
        if self.score >= SCORE_THRESHOLDS["good"]:
            return "Bon"
        if self.score >= SCORE_THRESHOLDS["average"]:
            return "Normal"
        if self.score >= SCORE_THRESHOLDS["below_average"]:
            return "Sous la moyenne"
        return "Difficile"

    @property
    def color_class(self) -> str:
        """Classe CSS pour la couleur."""
        if self.score is None:
            return "text-muted"
        if self.score >= SCORE_THRESHOLDS["excellent"]:
            return "perf-excellent"
        if self.score >= SCORE_THRESHOLDS["good"]:
            return "perf-good"
        if self.score >= SCORE_THRESHOLDS["average"]:
            return "perf-average"
        if self.score >= SCORE_THRESHOLDS["below_average"]:
            return "perf-below"
        return "perf-bad"


def get_score_interpretation(score: float | None) -> str:
    """Retourne l'interprétation textuelle d'un score."""
    if score is None:
        return "Historique insuffisant"
    if score >= SCORE_THRESHOLDS["excellent"]:
        return "Match exceptionnel pour toi"
    if score >= SCORE_THRESHOLDS["good"]:
        return "Au-dessus de ta moyenne"
    if score >= SCORE_THRESHOLDS["average"]:
        return "Performance typique"
    if score >= SCORE_THRESHOLDS["below_average"]:
        return "En-dessous de ta moyenne"
    return "Match difficile"
