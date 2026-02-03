"""Analyse de la participation aux objectifs avec Polars.

Sprint 4 - Fonctions d'analyse des personal_score_awards pour :
- Calculer les scores de participation aux objectifs
- Classer les joueurs par contribution aux objectifs
- Décomposer les types d'assistances

Références :
- src/data/domain/refdata.py : Enums et catégorisation des scores
- src/data/repositories/duckdb_repo.py : Chargement des données
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

# Import conditionnel de Polars pour gérer l'absence
try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None  # type: ignore

from src.data.domain.refdata import (
    ASSIST_SCORES,
    KILL_SCORES,
    NEGATIVE_SCORES,
    OBJECTIVE_SCORES,
    PERSONAL_SCORE_DISPLAY_NAMES,
    PERSONAL_SCORE_POINTS,
    PersonalScoreNameId,
    get_personal_score_display_name,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Dataclasses de résultats
# =============================================================================


@dataclass(frozen=True)
class ObjectiveParticipationResult:
    """Résultat du calcul de participation aux objectifs.

    Attributes:
        match_id: ID du match analysé.
        xuid: XUID du joueur (si filtré).
        objective_score: Score total des actions d'objectif.
        assist_score: Score total des assistances.
        kill_score: Score total des kills.
        negative_score: Score total des pénalités (trahisons, suicides).
        total_score: Score total combiné.
        objective_ratio: Ratio objectifs / total (0-1).
        assist_ratio: Ratio assistances / total (0-1).
        objective_count: Nombre d'actions d'objectif.
        assist_count: Nombre d'assistances.
        kill_count: Nombre de kills.
    """

    match_id: str | None
    xuid: str | None
    objective_score: int
    assist_score: int
    kill_score: int
    negative_score: int
    total_score: int
    objective_ratio: float
    assist_ratio: float
    objective_count: int
    assist_count: int
    kill_count: int


@dataclass(frozen=True)
class AssistBreakdownResult:
    """Décomposition détaillée des assistances.

    Attributes:
        kill_assists: Nombre d'assistances kill classiques (50 pts).
        mark_assists: Nombre d'assistances marquage (10 pts).
        emp_assists: Nombre d'assistances EMP (50 pts).
        driver_assists: Nombre d'assistances conducteur (50 pts).
        sensor_assists: Nombre d'assistances capteur (10 pts).
        flag_assists: Nombre d'assistances capture drapeau (100 pts).
        total_assists: Total des assistances.
        total_assist_points: Points totaux d'assistance.
        high_value_ratio: Ratio des assistances à haute valeur (50+ pts).
    """

    kill_assists: int
    mark_assists: int
    emp_assists: int
    driver_assists: int
    sensor_assists: int
    flag_assists: int
    total_assists: int
    total_assist_points: int
    high_value_ratio: float


@dataclass(frozen=True)
class PlayerObjectiveRanking:
    """Classement d'un joueur par contribution aux objectifs.

    Attributes:
        xuid: XUID du joueur.
        gamertag: Gamertag du joueur (si disponible).
        objective_score: Score objectifs.
        assist_score: Score assistances.
        total_score: Score total.
        matches_played: Nombre de matchs joués.
        avg_objective_per_match: Moyenne de score objectifs par match.
        objective_focus_ratio: Ratio objectifs / total.
    """

    xuid: str
    gamertag: str | None
    objective_score: int
    assist_score: int
    total_score: int
    matches_played: int
    avg_objective_per_match: float
    objective_focus_ratio: float


# =============================================================================
# Fonctions d'analyse Polars
# =============================================================================


def _ensure_polars() -> None:
    """Vérifie que Polars est disponible."""
    if not POLARS_AVAILABLE:
        raise ImportError("Polars n'est pas installé. Installez-le avec: pip install polars")


def compute_objective_participation_score_polars(
    awards_df: pl.DataFrame,
    match_id: str | None = None,
    xuid: str | None = None,
) -> ObjectiveParticipationResult:
    """Calcule le score de participation aux objectifs avec Polars.

    Cette fonction analyse les personal_score_awards pour catégoriser
    les contributions du joueur en objectifs, assistances et kills.

    Args:
        awards_df: DataFrame Polars avec colonnes match_id, xuid,
                   award_name_id, count, total_points.
        match_id: Filtrer pour un match spécifique (optionnel).
        xuid: Filtrer pour un joueur spécifique (optionnel).

    Returns:
        ObjectiveParticipationResult avec scores détaillés.
    """
    _ensure_polars()

    # Vérifier si le DataFrame est vide
    if awards_df.is_empty():
        return ObjectiveParticipationResult(
            match_id=match_id,
            xuid=xuid,
            objective_score=0,
            assist_score=0,
            kill_score=0,
            negative_score=0,
            total_score=0,
            objective_ratio=0.0,
            assist_ratio=0.0,
            objective_count=0,
            assist_count=0,
            kill_count=0,
        )

    # Appliquer les filtres
    filtered_df = awards_df
    if match_id:
        filtered_df = filtered_df.filter(pl.col("match_id") == match_id)
    if xuid:
        filtered_df = filtered_df.filter(pl.col("xuid") == xuid)

    if filtered_df.is_empty():
        return ObjectiveParticipationResult(
            match_id=match_id,
            xuid=xuid,
            objective_score=0,
            assist_score=0,
            kill_score=0,
            negative_score=0,
            total_score=0,
            objective_ratio=0.0,
            assist_ratio=0.0,
            objective_count=0,
            assist_count=0,
            kill_count=0,
        )

    # Convertir les sets en listes pour Polars
    objective_ids = list(OBJECTIVE_SCORES)
    assist_ids = list(ASSIST_SCORES)
    kill_ids = list(KILL_SCORES)
    negative_ids = list(NEGATIVE_SCORES)

    # Calculer les scores par catégorie
    objective_df = filtered_df.filter(pl.col("award_name_id").is_in(objective_ids))
    assist_df = filtered_df.filter(pl.col("award_name_id").is_in(assist_ids))
    kill_df = filtered_df.filter(pl.col("award_name_id").is_in(kill_ids))
    negative_df = filtered_df.filter(pl.col("award_name_id").is_in(negative_ids))

    # Agréger les totaux
    objective_score = objective_df.select(pl.col("total_points").sum()).item() or 0
    assist_score = assist_df.select(pl.col("total_points").sum()).item() or 0
    kill_score = kill_df.select(pl.col("total_points").sum()).item() or 0
    negative_score = negative_df.select(pl.col("total_points").sum()).item() or 0

    # Compter les actions
    objective_count = objective_df.select(pl.col("count").sum()).item() or 0
    assist_count = assist_df.select(pl.col("count").sum()).item() or 0
    kill_count = kill_df.select(pl.col("count").sum()).item() or 0

    # Calculer le total et les ratios
    total_score = objective_score + assist_score + kill_score + negative_score

    objective_ratio = objective_score / total_score if total_score > 0 else 0.0
    assist_ratio = assist_score / total_score if total_score > 0 else 0.0

    return ObjectiveParticipationResult(
        match_id=match_id,
        xuid=xuid,
        objective_score=int(objective_score),
        assist_score=int(assist_score),
        kill_score=int(kill_score),
        negative_score=int(negative_score),
        total_score=int(total_score),
        objective_ratio=float(objective_ratio),
        assist_ratio=float(assist_ratio),
        objective_count=int(objective_count),
        assist_count=int(assist_count),
        kill_count=int(kill_count),
    )


def rank_players_by_objective_contribution_polars(
    awards_df: pl.DataFrame,
    *,
    match_ids: list[str] | None = None,
    top_n: int = 20,
    min_matches: int = 1,
) -> list[PlayerObjectiveRanking]:
    """Classe les joueurs par leur contribution aux objectifs.

    Cette fonction agrège les personal_score_awards sur plusieurs matchs
    et classe les joueurs par leur score objectif moyen.

    Args:
        awards_df: DataFrame Polars avec colonnes match_id, xuid,
                   award_name_id, count, total_points.
        match_ids: Liste de matchs à analyser (tous si None).
        top_n: Nombre de joueurs à retourner.
        min_matches: Nombre minimum de matchs pour être inclus.

    Returns:
        Liste de PlayerObjectiveRanking triée par contribution.
    """
    _ensure_polars()

    if awards_df.is_empty():
        return []

    # Appliquer le filtre de matchs si fourni
    filtered_df = awards_df
    if match_ids:
        filtered_df = filtered_df.filter(pl.col("match_id").is_in(match_ids))

    if filtered_df.is_empty():
        return []

    # Convertir les sets en listes
    objective_ids = list(OBJECTIVE_SCORES)
    assist_ids = list(ASSIST_SCORES)

    # Calculer les scores par joueur
    # 1. Score objectifs par joueur
    objective_by_player = (
        filtered_df.filter(pl.col("award_name_id").is_in(objective_ids))
        .group_by("xuid")
        .agg(
            [
                pl.col("total_points").sum().alias("objective_score"),
                pl.col("match_id").n_unique().alias("objective_matches"),
            ]
        )
    )

    # 2. Score assistances par joueur
    assist_by_player = (
        filtered_df.filter(pl.col("award_name_id").is_in(assist_ids))
        .group_by("xuid")
        .agg(pl.col("total_points").sum().alias("assist_score"))
    )

    # 3. Score total par joueur
    total_by_player = filtered_df.group_by("xuid").agg(
        [
            pl.col("total_points").sum().alias("total_score"),
            pl.col("match_id").n_unique().alias("matches_played"),
        ]
    )

    # Joindre les DataFrames
    result_df = (
        total_by_player.join(objective_by_player, on="xuid", how="left")
        .join(assist_by_player, on="xuid", how="left")
        .with_columns(
            [
                pl.col("objective_score").fill_null(0),
                pl.col("assist_score").fill_null(0),
            ]
        )
        .filter(pl.col("matches_played") >= min_matches)
        .with_columns(
            [
                (pl.col("objective_score") / pl.col("matches_played")).alias(
                    "avg_objective_per_match"
                ),
                (pl.col("objective_score") / pl.col("total_score"))
                .fill_nan(0)
                .fill_null(0)
                .alias("objective_focus_ratio"),
            ]
        )
        .sort("avg_objective_per_match", descending=True)
        .head(top_n)
    )

    # Convertir en liste de dataclasses
    results = []
    for row in result_df.iter_rows(named=True):
        results.append(
            PlayerObjectiveRanking(
                xuid=row["xuid"],
                gamertag=None,  # À remplir via xuid_aliases si nécessaire
                objective_score=int(row["objective_score"]),
                assist_score=int(row["assist_score"]),
                total_score=int(row["total_score"]),
                matches_played=int(row["matches_played"]),
                avg_objective_per_match=float(row["avg_objective_per_match"]),
                objective_focus_ratio=float(row["objective_focus_ratio"]),
            )
        )

    return results


def compute_assist_breakdown_polars(
    awards_df: pl.DataFrame,
    *,
    match_id: str | None = None,
    xuid: str | None = None,
) -> AssistBreakdownResult:
    """Décompose les types d'assistances avec Polars.

    Cette fonction analyse les personal_score_awards pour catégoriser
    les différents types d'assistances et leur valeur.

    Args:
        awards_df: DataFrame Polars avec colonnes match_id, xuid,
                   award_name_id, count, total_points.
        match_id: Filtrer pour un match spécifique (optionnel).
        xuid: Filtrer pour un joueur spécifique (optionnel).

    Returns:
        AssistBreakdownResult avec détail des assistances.
    """
    _ensure_polars()

    if awards_df.is_empty():
        return AssistBreakdownResult(
            kill_assists=0,
            mark_assists=0,
            emp_assists=0,
            driver_assists=0,
            sensor_assists=0,
            flag_assists=0,
            total_assists=0,
            total_assist_points=0,
            high_value_ratio=0.0,
        )

    # Appliquer les filtres
    filtered_df = awards_df
    if match_id:
        filtered_df = filtered_df.filter(pl.col("match_id") == match_id)
    if xuid:
        filtered_df = filtered_df.filter(pl.col("xuid") == xuid)

    # Filtrer uniquement les assistances
    assist_ids = list(ASSIST_SCORES)
    assist_df = filtered_df.filter(pl.col("award_name_id").is_in(assist_ids))

    if assist_df.is_empty():
        return AssistBreakdownResult(
            kill_assists=0,
            mark_assists=0,
            emp_assists=0,
            driver_assists=0,
            sensor_assists=0,
            flag_assists=0,
            total_assists=0,
            total_assist_points=0,
            high_value_ratio=0.0,
        )

    # Mapper les IDs aux noms des colonnes
    assist_mapping = {
        PersonalScoreNameId.KILL_ASSIST: "kill_assists",
        PersonalScoreNameId.MARK_ASSIST: "mark_assists",
        PersonalScoreNameId.EMP_ASSIST: "emp_assists",
        PersonalScoreNameId.DRIVER_ASSIST: "driver_assists",
        PersonalScoreNameId.SENSOR_ASSIST: "sensor_assists",
        PersonalScoreNameId.FLAG_CAPTURE_ASSIST: "flag_assists",
    }

    # Compter chaque type d'assistance
    counts = {name: 0 for name in assist_mapping.values()}
    total_points = 0

    for row in assist_df.iter_rows(named=True):
        award_id = row["award_name_id"]
        count = row["count"]
        points = row["total_points"]

        for score_id, col_name in assist_mapping.items():
            if award_id == int(score_id):
                counts[col_name] += count
                break

        total_points += points

    total_assists = sum(counts.values())

    # Calculer le ratio des assistances à haute valeur (50+ pts)
    # KILL_ASSIST, EMP_ASSIST, DRIVER_ASSIST, FLAG_CAPTURE_ASSIST = 50+ pts
    high_value_count = (
        counts["kill_assists"]
        + counts["emp_assists"]
        + counts["driver_assists"]
        + counts["flag_assists"]
    )
    high_value_ratio = high_value_count / total_assists if total_assists > 0 else 0.0

    return AssistBreakdownResult(
        kill_assists=counts["kill_assists"],
        mark_assists=counts["mark_assists"],
        emp_assists=counts["emp_assists"],
        driver_assists=counts["driver_assists"],
        sensor_assists=counts["sensor_assists"],
        flag_assists=counts["flag_assists"],
        total_assists=total_assists,
        total_assist_points=total_points,
        high_value_ratio=high_value_ratio,
    )


def compute_objective_summary_by_match_polars(
    awards_df: pl.DataFrame,
    *,
    xuid: str | None = None,
) -> pl.DataFrame:
    """Calcule un résumé des objectifs par match avec Polars.

    Retourne un DataFrame avec les scores objectifs agrégés par match,
    utile pour les graphiques de tendance.

    Args:
        awards_df: DataFrame Polars avec les awards.
        xuid: Filtrer pour un joueur spécifique (optionnel).

    Returns:
        DataFrame Polars avec match_id, objective_score, assist_score,
        total_score, objective_ratio.
    """
    _ensure_polars()

    if awards_df.is_empty():
        return pl.DataFrame(
            {
                "match_id": [],
                "objective_score": [],
                "assist_score": [],
                "kill_score": [],
                "total_score": [],
                "objective_ratio": [],
            }
        )

    filtered_df = awards_df
    if xuid:
        filtered_df = filtered_df.filter(pl.col("xuid") == xuid)

    if filtered_df.is_empty():
        return pl.DataFrame(
            {
                "match_id": [],
                "objective_score": [],
                "assist_score": [],
                "kill_score": [],
                "total_score": [],
                "objective_ratio": [],
            }
        )

    # Convertir les sets en listes
    objective_ids = list(OBJECTIVE_SCORES)
    assist_ids = list(ASSIST_SCORES)
    kill_ids = list(KILL_SCORES)

    # Créer une colonne catégorie
    categorized = filtered_df.with_columns(
        [
            pl.when(pl.col("award_name_id").is_in(objective_ids))
            .then(pl.lit("objective"))
            .when(pl.col("award_name_id").is_in(assist_ids))
            .then(pl.lit("assist"))
            .when(pl.col("award_name_id").is_in(kill_ids))
            .then(pl.lit("kill"))
            .otherwise(pl.lit("other"))
            .alias("category")
        ]
    )

    # Pivoter pour avoir une colonne par catégorie
    summary = (
        categorized.group_by(["match_id", "category"])
        .agg(pl.col("total_points").sum().alias("points"))
        .pivot(
            values="points",
            index="match_id",
            on="category",
            aggregate_function="sum",
        )
        .fill_null(0)
    )

    # S'assurer que toutes les colonnes existent
    for col in ["objective", "assist", "kill", "other"]:
        if col not in summary.columns:
            summary = summary.with_columns(pl.lit(0).alias(col))

    # Renommer et calculer les totaux
    result = (
        summary.rename(
            {
                "objective": "objective_score",
                "assist": "assist_score",
                "kill": "kill_score",
            }
        )
        .with_columns(
            [
                (pl.col("objective_score") + pl.col("assist_score") + pl.col("kill_score")).alias(
                    "total_score"
                )
            ]
        )
        .with_columns(
            [
                (pl.col("objective_score") / pl.col("total_score"))
                .fill_nan(0)
                .fill_null(0)
                .alias("objective_ratio")
            ]
        )
        .select(
            [
                "match_id",
                "objective_score",
                "assist_score",
                "kill_score",
                "total_score",
                "objective_ratio",
            ]
        )
    )

    return result


def compute_award_frequency_polars(
    awards_df: pl.DataFrame,
    *,
    category: str | None = None,
    top_n: int = 20,
) -> pl.DataFrame:
    """Calcule la fréquence des awards par type.

    Args:
        awards_df: DataFrame Polars avec les awards.
        category: Filtrer par catégorie ("objective", "assist", "kill", ou None pour tous).
        top_n: Nombre de types à retourner.

    Returns:
        DataFrame Polars avec award_name_id, display_name, count, total_points.
    """
    _ensure_polars()

    if awards_df.is_empty():
        return pl.DataFrame(
            {
                "award_name_id": [],
                "display_name": [],
                "count": [],
                "total_points": [],
            }
        )

    filtered_df = awards_df

    # Filtrer par catégorie si spécifié
    if category == "objective":
        filtered_df = filtered_df.filter(pl.col("award_name_id").is_in(list(OBJECTIVE_SCORES)))
    elif category == "assist":
        filtered_df = filtered_df.filter(pl.col("award_name_id").is_in(list(ASSIST_SCORES)))
    elif category == "kill":
        filtered_df = filtered_df.filter(pl.col("award_name_id").is_in(list(KILL_SCORES)))

    if filtered_df.is_empty():
        return pl.DataFrame(
            {
                "award_name_id": [],
                "display_name": [],
                "count": [],
                "total_points": [],
            }
        )

    # Agréger par award_name_id
    aggregated = (
        filtered_df.group_by("award_name_id")
        .agg(
            [
                pl.col("count").sum().alias("count"),
                pl.col("total_points").sum().alias("total_points"),
            ]
        )
        .sort("total_points", descending=True)
        .head(top_n)
    )

    # Ajouter les noms d'affichage
    award_ids = aggregated["award_name_id"].to_list()
    display_names = [get_personal_score_display_name(aid) for aid in award_ids]

    result = aggregated.with_columns(pl.Series("display_name", display_names)).select(
        [
            "award_name_id",
            "display_name",
            "count",
            "total_points",
        ]
    )

    return result


# =============================================================================
# Fonctions utilitaires
# =============================================================================


def get_objective_mode_awards() -> dict[int, str]:
    """Retourne les awards liés aux modes à objectifs avec leurs noms.

    Returns:
        Dict {award_name_id: display_name} pour les awards objectifs.
    """
    return {
        int(score_id): PERSONAL_SCORE_DISPLAY_NAMES.get(int(score_id), "Inconnu")
        for score_id in OBJECTIVE_SCORES
    }


def get_assist_awards_with_points() -> dict[int, tuple[str, int]]:
    """Retourne les awards d'assistance avec leurs noms et points.

    Returns:
        Dict {award_name_id: (display_name, points)} pour les awards d'assistance.
    """
    return {
        int(score_id): (
            PERSONAL_SCORE_DISPLAY_NAMES.get(int(score_id), "Inconnu"),
            PERSONAL_SCORE_POINTS.get(int(score_id), 0),
        )
        for score_id in ASSIST_SCORES
    }


def is_objective_mode_match(game_variant_category: int) -> bool:
    """Vérifie si un match est un mode à objectifs basé sur la catégorie.

    Args:
        game_variant_category: Valeur de GameVariantCategory.

    Returns:
        True si c'est un mode à objectifs.
    """
    from src.data.domain.refdata import OBJECTIVE_MODE_CATEGORIES

    return game_variant_category in OBJECTIVE_MODE_CATEGORIES


# =============================================================================
# Sprint 7.4 - Métriques ratio objectifs/kills
# =============================================================================


@dataclass(frozen=True)
class PlayerProfileResult:
    """Profil du joueur basé sur ses contributions.

    Attributes:
        profile_type: Type de profil ("slayer", "support", "versatile").
        profile_label: Label humain du profil.
        objective_ratio: Ratio objectifs/total (0-1).
        kill_ratio: Ratio kills/total (0-1).
        assist_ratio: Ratio assistances/total (0-1).
        confidence: Niveau de confiance (basé sur le nombre de matchs).
        description: Description du profil.
    """

    profile_type: str
    profile_label: str
    objective_ratio: float
    kill_ratio: float
    assist_ratio: float
    confidence: str
    description: str


def compute_objective_kill_ratio_polars(
    awards_df: pl.DataFrame,
    match_stats_df: pl.DataFrame,
    *,
    xuid: str | None = None,
) -> pl.DataFrame:
    """Calcule le ratio objectifs/kills par match.

    Cette fonction compare le score objectifs au nombre de kills pour
    identifier les matchs où le joueur a plus contribué aux objectifs.

    Args:
        awards_df: DataFrame des personal_score_awards.
        match_stats_df: DataFrame des match_stats avec kills.
        xuid: Filtrer pour un joueur spécifique (optionnel).

    Returns:
        DataFrame Polars avec match_id, objective_score, kills,
        objective_per_kill, is_objective_focused.
    """
    _ensure_polars()

    if awards_df.is_empty() or match_stats_df.is_empty():
        return pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "objective_score": pl.Int64,
                "kills": pl.Int64,
                "objective_per_kill": pl.Float64,
                "is_objective_focused": pl.Boolean,
            }
        )

    # Filtrer par joueur si spécifié
    filtered_awards = awards_df
    if xuid and "xuid" in filtered_awards.columns:
        filtered_awards = filtered_awards.filter(pl.col("xuid") == xuid)

    # Calculer score objectifs par match
    objective_ids = list(OBJECTIVE_SCORES)
    obj_by_match = (
        filtered_awards.filter(pl.col("award_name_id").is_in(objective_ids))
        .group_by("match_id")
        .agg(pl.col("total_points").sum().alias("objective_score"))
    )

    # Joindre avec match_stats pour avoir les kills
    result = (
        match_stats_df.select(["match_id", "kills"])
        .join(obj_by_match, on="match_id", how="left")
        .with_columns([pl.col("objective_score").fill_null(0)])
        .with_columns(
            [
                # Ratio objectifs par kill (éviter division par zéro)
                (
                    pl.col("objective_score")
                    / pl.when(pl.col("kills") == 0).then(1).otherwise(pl.col("kills"))
                ).alias("objective_per_kill"),
            ]
        )
        .with_columns(
            [
                # Match orienté objectif si ratio > 50 points par kill
                (pl.col("objective_per_kill") > 50).alias("is_objective_focused"),
            ]
        )
    )

    return result


def compute_player_profile_polars(
    awards_df: pl.DataFrame,
    *,
    xuid: str | None = None,
    min_matches: int = 5,
) -> PlayerProfileResult:
    """Détermine le profil du joueur basé sur ses contributions.

    Analyse les personal_score_awards pour classifier le joueur en :
    - "slayer" : Orienté kills (ratio kills > 60%)
    - "support" : Orienté objectifs/assists (ratio objectifs+assists > 40%)
    - "versatile" : Équilibré

    Args:
        awards_df: DataFrame des personal_score_awards.
        xuid: XUID du joueur (optionnel, prend tous si non spécifié).
        min_matches: Nombre minimum de matchs pour une analyse fiable.

    Returns:
        PlayerProfileResult avec le profil déterminé.
    """
    _ensure_polars()

    # Valeurs par défaut
    default_result = PlayerProfileResult(
        profile_type="unknown",
        profile_label="Inconnu",
        objective_ratio=0.0,
        kill_ratio=0.0,
        assist_ratio=0.0,
        confidence="faible",
        description="Pas assez de données pour déterminer le profil.",
    )

    if awards_df.is_empty():
        return default_result

    # Filtrer par joueur
    filtered_df = awards_df
    if xuid and "xuid" in filtered_df.columns:
        filtered_df = filtered_df.filter(pl.col("xuid") == xuid)

    if filtered_df.is_empty():
        return default_result

    # Compter les matchs uniques
    matches_count = filtered_df.select(pl.col("match_id").n_unique()).item()
    if matches_count < min_matches:
        return PlayerProfileResult(
            profile_type="unknown",
            profile_label="Données insuffisantes",
            objective_ratio=0.0,
            kill_ratio=0.0,
            assist_ratio=0.0,
            confidence="faible",
            description=f"Seulement {matches_count} matchs analysés (min: {min_matches}).",
        )

    # Calculer les scores par catégorie
    objective_ids = list(OBJECTIVE_SCORES)
    assist_ids = list(ASSIST_SCORES)
    kill_ids = list(KILL_SCORES)

    objective_score = (
        filtered_df.filter(pl.col("award_name_id").is_in(objective_ids))
        .select(pl.col("total_points").sum())
        .item()
    ) or 0

    assist_score = (
        filtered_df.filter(pl.col("award_name_id").is_in(assist_ids))
        .select(pl.col("total_points").sum())
        .item()
    ) or 0

    kill_score = (
        filtered_df.filter(pl.col("award_name_id").is_in(kill_ids))
        .select(pl.col("total_points").sum())
        .item()
    ) or 0

    total_score = objective_score + assist_score + kill_score

    if total_score == 0:
        return default_result

    # Calculer les ratios
    objective_ratio = objective_score / total_score
    assist_ratio = assist_score / total_score
    kill_ratio = kill_score / total_score
    support_ratio = objective_ratio + assist_ratio

    # Déterminer le niveau de confiance
    if matches_count >= 50:
        confidence = "élevée"
    elif matches_count >= 20:
        confidence = "moyenne"
    else:
        confidence = "faible"

    # Classifier le profil
    if kill_ratio >= 0.60:
        profile_type = "slayer"
        profile_label = "🎯 Joueur Slayer"
        description = (
            f"Vous excellez dans les éliminations avec {kill_ratio*100:.0f}% "
            "de votre score provenant des kills."
        )
    elif support_ratio >= 0.40:
        profile_type = "support"
        profile_label = "🛡️ Joueur Support"
        description = (
            f"Vous contribuez fortement aux objectifs ({objective_ratio*100:.0f}%) "
            f"et aux assistances ({assist_ratio*100:.0f}%)."
        )
    else:
        profile_type = "versatile"
        profile_label = "⚔️ Joueur Polyvalent"
        description = (
            f"Bon équilibre entre kills ({kill_ratio*100:.0f}%), "
            f"objectifs ({objective_ratio*100:.0f}%) et assists ({assist_ratio*100:.0f}%)."
        )

    return PlayerProfileResult(
        profile_type=profile_type,
        profile_label=profile_label,
        objective_ratio=round(objective_ratio, 3),
        kill_ratio=round(kill_ratio, 3),
        assist_ratio=round(assist_ratio, 3),
        confidence=confidence,
        description=description,
    )


def compute_objective_efficiency_polars(
    awards_df: pl.DataFrame,
    match_stats_df: pl.DataFrame,
    *,
    xuid: str | None = None,
) -> dict[str, float | None]:
    """Calcule l'efficacité objective du joueur.

    Mesure le ratio entre les points d'objectifs et les ressources investies
    (temps de jeu, morts, etc.).

    Args:
        awards_df: DataFrame des personal_score_awards.
        match_stats_df: DataFrame des match_stats.
        xuid: XUID du joueur (optionnel).

    Returns:
        Dict avec les métriques d'efficacité :
        - objective_per_minute: Points objectifs par minute de jeu.
        - objective_per_death: Points objectifs par mort.
        - objective_contribution_pct: % de la contribution aux objectifs de l'équipe.
    """
    _ensure_polars()

    default_result = {
        "objective_per_minute": None,
        "objective_per_death": None,
        "objective_contribution_pct": None,
    }

    if awards_df.is_empty() or match_stats_df.is_empty():
        return default_result

    # Filtrer par joueur
    filtered_awards = awards_df
    if xuid and "xuid" in filtered_awards.columns:
        filtered_awards = filtered_awards.filter(pl.col("xuid") == xuid)

    # Calculer score objectifs total
    objective_ids = list(OBJECTIVE_SCORES)
    total_objective = (
        filtered_awards.filter(pl.col("award_name_id").is_in(objective_ids))
        .select(pl.col("total_points").sum())
        .item()
    ) or 0

    if total_objective == 0:
        return default_result

    # Calculer temps de jeu et morts
    total_time_seconds = (match_stats_df.select(pl.col("time_played_seconds").sum()).item()) or 0
    total_deaths = (match_stats_df.select(pl.col("deaths").sum()).item()) or 0

    # Métriques
    objective_per_minute = (
        total_objective / (total_time_seconds / 60) if total_time_seconds > 0 else None
    )
    objective_per_death = (
        total_objective / total_deaths if total_deaths > 0 else float(total_objective)
    )

    return {
        "objective_per_minute": round(objective_per_minute, 1) if objective_per_minute else None,
        "objective_per_death": round(objective_per_death, 1) if objective_per_death else None,
        "objective_contribution_pct": None,  # Nécessite données équipe (à implémenter)
    }
