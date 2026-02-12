"""Module d'analyse d'impact des coéquipiers (Sprint 12).

Identifie les événements clés par coéquipier :
- First Blood : Premier kill du match
- Clutch Finisher : Dernier kill d'une victoire
- Last Casualty : Dernière mort d'une défaite

Ces événements sont utilisés pour calculer un score d'impact
et générer une heatmap de "taquinerie" entre amis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    pass

# Constantes de scoring
SCORE_CLUTCH_FINISHER = 2  # Finisseur : +2 points
SCORE_FIRST_BLOOD = 1  # Premier sang : +1 point
SCORE_LAST_CASUALTY = -1  # Boulet : -1 point

# Codes d'outcome
OUTCOME_WIN = 2
OUTCOME_LOSS = 3


@dataclass
class ImpactEvent:
    """Représente un événement d'impact dans un match."""

    match_id: str
    xuid: str
    gamertag: str
    time_ms: int
    event_type: str  # "first_blood", "clutch_finisher", "last_casualty"


def identify_first_blood(
    events_df: pl.DataFrame,
    friend_xuids: set[str] | None = None,
) -> dict[str, ImpactEvent]:
    """Identifie le joueur avec le premier kill par match.

    Le First Blood est le kill avec le timestamp le plus bas (min time_ms)
    dans chaque match, indépendamment de l'outcome.

    Args:
        events_df: DataFrame Polars avec colonnes :
            - match_id, xuid, gamertag, event_type, time_ms
        friend_xuids: Set d'XUIDs à filtrer (optionnel). Si None, tous les joueurs.

    Returns:
        Dict {match_id: ImpactEvent} pour le premier kill de chaque match.
    """
    if events_df.is_empty():
        return {}

    # Filtrer les kills uniquement (event_type peut être "kill" ou "Kill")
    kills = events_df.filter(pl.col("event_type").str.to_lowercase() == "kill")

    if kills.is_empty():
        return {}

    # Filtrer par amis si spécifié
    if friend_xuids:
        # Normaliser en string pour comparaison
        friend_xuids_str = {str(x) for x in friend_xuids}
        kills = kills.filter(pl.col("xuid").cast(pl.Utf8).is_in(friend_xuids_str))

    if kills.is_empty():
        return {}

    # Trouver le premier kill par match (min time_ms)
    first_kills = (
        kills.group_by("match_id")
        .agg(pl.col("time_ms").min().alias("min_time"))
        .join(kills, on="match_id")
        .filter(pl.col("time_ms") == pl.col("min_time"))
        .unique(subset=["match_id"])  # Un seul FB par match
    )

    result = {}
    for row in first_kills.iter_rows(named=True):
        match_id = str(row["match_id"])
        result[match_id] = ImpactEvent(
            match_id=match_id,
            xuid=str(row["xuid"]),
            gamertag=str(row.get("gamertag", "Unknown")),
            time_ms=int(row["time_ms"]),
            event_type="first_blood",
        )

    return result


def identify_clutch_finisher(
    events_df: pl.DataFrame,
    matches_df: pl.DataFrame,
    friend_xuids: set[str] | None = None,
) -> dict[str, ImpactEvent]:
    """Identifie le joueur avec le dernier kill d'une victoire.

    Le Clutch Finisher est le kill avec le timestamp le plus haut (max time_ms)
    dans un match où l'outcome = 2 (victoire).

    Args:
        events_df: DataFrame Polars des événements (match_id, xuid, gamertag, event_type, time_ms).
        matches_df: DataFrame Polars des matchs avec (match_id, outcome).
        friend_xuids: Set d'XUIDs à filtrer (optionnel).

    Returns:
        Dict {match_id: ImpactEvent} pour le dernier kill de chaque victoire.
    """
    if events_df.is_empty() or matches_df.is_empty():
        return {}

    # Filtrer les victoires
    wins = matches_df.filter(pl.col("outcome") == OUTCOME_WIN).select("match_id")
    win_match_ids = {str(m) for m in wins["match_id"].to_list()}

    if not win_match_ids:
        return {}

    # Filtrer les kills dans les matchs gagnés
    kills = events_df.filter(
        (pl.col("event_type").str.to_lowercase() == "kill")
        & (pl.col("match_id").cast(pl.Utf8).is_in(win_match_ids))
    )

    if kills.is_empty():
        return {}

    # Filtrer par amis si spécifié
    if friend_xuids:
        friend_xuids_str = {str(x) for x in friend_xuids}
        kills = kills.filter(pl.col("xuid").cast(pl.Utf8).is_in(friend_xuids_str))

    if kills.is_empty():
        return {}

    # Trouver le dernier kill par match (max time_ms)
    last_kills = (
        kills.group_by("match_id")
        .agg(pl.col("time_ms").max().alias("max_time"))
        .join(kills, on="match_id")
        .filter(pl.col("time_ms") == pl.col("max_time"))
        .unique(subset=["match_id"])
    )

    result = {}
    for row in last_kills.iter_rows(named=True):
        match_id = str(row["match_id"])
        result[match_id] = ImpactEvent(
            match_id=match_id,
            xuid=str(row["xuid"]),
            gamertag=str(row.get("gamertag", "Unknown")),
            time_ms=int(row["time_ms"]),
            event_type="clutch_finisher",
        )

    return result


def identify_last_casualty(
    events_df: pl.DataFrame,
    matches_df: pl.DataFrame,
    friend_xuids: set[str] | None = None,
) -> dict[str, ImpactEvent]:
    """Identifie le joueur avec la dernière mort d'une défaite.

    Le Last Casualty (Boulet) est la mort avec le timestamp le plus haut
    dans un match où l'outcome = 3 (défaite).

    Args:
        events_df: DataFrame Polars des événements.
        matches_df: DataFrame Polars des matchs avec (match_id, outcome).
        friend_xuids: Set d'XUIDs à filtrer (optionnel).

    Returns:
        Dict {match_id: ImpactEvent} pour la dernière mort de chaque défaite.
    """
    if events_df.is_empty() or matches_df.is_empty():
        return {}

    # Filtrer les défaites
    losses = matches_df.filter(pl.col("outcome") == OUTCOME_LOSS).select("match_id")
    loss_match_ids = {str(m) for m in losses["match_id"].to_list()}

    if not loss_match_ids:
        return {}

    # Filtrer les morts dans les matchs perdus
    deaths = events_df.filter(
        (pl.col("event_type").str.to_lowercase() == "death")
        & (pl.col("match_id").cast(pl.Utf8).is_in(loss_match_ids))
    )

    if deaths.is_empty():
        return {}

    # Filtrer par amis si spécifié
    if friend_xuids:
        friend_xuids_str = {str(x) for x in friend_xuids}
        deaths = deaths.filter(pl.col("xuid").cast(pl.Utf8).is_in(friend_xuids_str))

    if deaths.is_empty():
        return {}

    # Trouver la dernière mort par match (max time_ms)
    last_deaths = (
        deaths.group_by("match_id")
        .agg(pl.col("time_ms").max().alias("max_time"))
        .join(deaths, on="match_id")
        .filter(pl.col("time_ms") == pl.col("max_time"))
        .unique(subset=["match_id"])
    )

    result = {}
    for row in last_deaths.iter_rows(named=True):
        match_id = str(row["match_id"])
        result[match_id] = ImpactEvent(
            match_id=match_id,
            xuid=str(row["xuid"]),
            gamertag=str(row.get("gamertag", "Unknown")),
            time_ms=int(row["time_ms"]),
            event_type="last_casualty",
        )

    return result


def compute_impact_scores(
    first_bloods: dict[str, ImpactEvent],
    clutch_finishers: dict[str, ImpactEvent],
    last_casualties: dict[str, ImpactEvent],
) -> dict[str, int]:
    """Calcule les scores d'impact par joueur.

    Scoring :
    - Clutch Finisher : +2 points
    - First Blood : +1 point
    - Last Casualty : -1 point

    Args:
        first_bloods: Dict {match_id: ImpactEvent} des premiers kills.
        clutch_finishers: Dict {match_id: ImpactEvent} des derniers kills victorieux.
        last_casualties: Dict {match_id: ImpactEvent} des dernières morts en défaite.

    Returns:
        Dict {gamertag: score} trié par score décroissant.
    """
    scores: dict[str, int] = {}

    # +1 pour First Blood
    for event in first_bloods.values():
        gamertag = event.gamertag
        scores[gamertag] = scores.get(gamertag, 0) + SCORE_FIRST_BLOOD

    # +2 pour Clutch Finisher
    for event in clutch_finishers.values():
        gamertag = event.gamertag
        scores[gamertag] = scores.get(gamertag, 0) + SCORE_CLUTCH_FINISHER

    # -1 pour Last Casualty
    for event in last_casualties.values():
        gamertag = event.gamertag
        scores[gamertag] = scores.get(gamertag, 0) + SCORE_LAST_CASUALTY

    # Trier par score décroissant
    return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))


def get_all_impact_events(
    events_df: pl.DataFrame,
    matches_df: pl.DataFrame,
    friend_xuids: set[str] | None = None,
) -> tuple[
    dict[str, ImpactEvent],
    dict[str, ImpactEvent],
    dict[str, ImpactEvent],
    dict[str, int],
]:
    """Récupère tous les événements d'impact et calcule les scores.

    Fonction de convenance qui appelle les 3 fonctions d'identification
    puis calcule les scores.

    Args:
        events_df: DataFrame des événements highlight.
        matches_df: DataFrame des matchs avec outcome.
        friend_xuids: Set d'XUIDs des amis à filtrer.

    Returns:
        Tuple (first_bloods, clutch_finishers, last_casualties, scores).
    """
    first_bloods = identify_first_blood(events_df, friend_xuids)
    clutch_finishers = identify_clutch_finisher(events_df, matches_df, friend_xuids)
    last_casualties = identify_last_casualty(events_df, matches_df, friend_xuids)
    scores = compute_impact_scores(first_bloods, clutch_finishers, last_casualties)

    return first_bloods, clutch_finishers, last_casualties, scores


def build_impact_matrix(
    first_bloods: dict[str, ImpactEvent],
    clutch_finishers: dict[str, ImpactEvent],
    last_casualties: dict[str, ImpactEvent],
    match_ids: list[str],
    gamertags: list[str],
) -> pl.DataFrame:
    """Construit une matrice d'impact pour la heatmap.

    Crée un DataFrame avec les colonnes :
    - match_id : ID du match
    - gamertag : Nom du joueur
    - event_type : Type d'événement (ou null)
    - event_value : Valeur numérique pour la heatmap (1=FB, 2=Clutch, -1=Boulet)

    Args:
        first_bloods: Dict des premiers kills.
        clutch_finishers: Dict des finisseurs.
        last_casualties: Dict des boulets.
        match_ids: Liste ordonnée des IDs de matchs.
        gamertags: Liste des gamertags à inclure.

    Returns:
        DataFrame Polars avec la matrice d'impact.
    """
    # Créer un mapping {(match_id, gamertag): [(event_type, value), ...]}
    events_map: dict[tuple[str, str], list[tuple[str, int]]] = {}

    for match_id in match_ids:
        for gamertag in gamertags:
            key = (match_id, gamertag)
            events_map[key] = []

    # Ajouter les First Bloods
    for match_id, event in first_bloods.items():
        key = (match_id, event.gamertag)
        if key in events_map:
            events_map[key].append(("first_blood", 1))

    # Ajouter les Clutch Finishers
    for match_id, event in clutch_finishers.items():
        key = (match_id, event.gamertag)
        if key in events_map:
            events_map[key].append(("clutch_finisher", 2))

    # Ajouter les Last Casualties
    for match_id, event in last_casualties.items():
        key = (match_id, event.gamertag)
        if key in events_map:
            events_map[key].append(("last_casualty", -1))

    # Construire le DataFrame
    rows = []
    for (match_id, gamertag), events in events_map.items():
        if events:
            # Prendre l'événement le plus significatif (priorité: clutch > FB > boulet)
            sorted_events = sorted(events, key=lambda x: abs(x[1]), reverse=True)
            event_type, event_value = sorted_events[0]
            rows.append(
                {
                    "match_id": match_id,
                    "gamertag": gamertag,
                    "event_type": event_type,
                    "event_value": event_value,
                }
            )
        else:
            rows.append(
                {
                    "match_id": match_id,
                    "gamertag": gamertag,
                    "event_type": None,
                    "event_value": 0,
                }
            )

    if not rows:
        # DataFrame vide avec le bon schéma
        return pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "gamertag": pl.Utf8,
                "event_type": pl.Utf8,
                "event_value": pl.Int64,
            }
        )

    return pl.DataFrame(rows)
