"""Agrégation des données antagonistes (killers/victimes) sur plusieurs matchs.

Sprint 3.2 - Ce module agrège les données issues de compute_personal_antagonists()
sur l'ensemble des matchs d'un joueur pour alimenter la table `antagonists`.

Schéma de la table antagonists:
    - opponent_xuid: XUID de l'adversaire
    - opponent_gamertag: Gamertag (dernier connu)
    - times_killed: Nombre de fois où on l'a tué
    - times_killed_by: Nombre de fois où il nous a tué
    - matches_against: Nombre de matchs en opposition
    - last_encounter: Dernier match contre cet adversaire
    - net_kills: times_killed - times_killed_by (calculé)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.analysis.killer_victim import AntagonistsResult

logger = logging.getLogger(__name__)


@dataclass
class AntagonistEntry:
    """Entrée agrégée pour un adversaire.

    Représente les données à persister dans la table antagonists.
    """

    opponent_xuid: str
    opponent_gamertag: str
    times_killed: int = 0
    times_killed_by: int = 0
    matches_against: int = 0
    last_encounter: datetime | None = None

    @property
    def net_kills(self) -> int:
        """Différence entre kills et deaths contre cet adversaire."""
        return self.times_killed - self.times_killed_by

    def update_from_result(
        self,
        result: AntagonistsResult,
        match_time: datetime,
        gamertag: str | None = None,
    ) -> None:
        """Met à jour l'entrée avec les résultats d'un match.

        Args:
            result: Résultat de compute_personal_antagonists() pour un match.
            match_time: Date du match.
            gamertag: Gamertag à utiliser (optionnel, prend priority sur celui du result).
        """
        # Comptabiliser les kills/deaths
        if result.nemesis and result.nemesis.xuid == self.opponent_xuid:
            self.times_killed_by += result.nemesis.opponent_killed_me.total

        if result.bully and result.bully.xuid == self.opponent_xuid:
            self.times_killed += result.bully.me_killed_opponent.total

        # Mettre à jour le gamertag avec le plus récent
        if gamertag:
            self.opponent_gamertag = gamertag
        elif self.last_encounter is None or match_time > self.last_encounter:
            if (
                result.nemesis
                and result.nemesis.xuid == self.opponent_xuid
                and result.nemesis.gamertag
            ):
                self.opponent_gamertag = result.nemesis.gamertag
            elif result.bully and result.bully.xuid == self.opponent_xuid and result.bully.gamertag:
                self.opponent_gamertag = result.bully.gamertag

        # Mettre à jour la date du dernier encounter
        if self.last_encounter is None or match_time > self.last_encounter:
            self.last_encounter = match_time

        self.matches_against += 1


@dataclass
class AggregationResult:
    """Résultat de l'agrégation des antagonistes.

    Contient les statistiques agrégées et les métadonnées de l'agrégation.
    """

    entries: list[AntagonistEntry] = field(default_factory=list)
    matches_processed: int = 0
    matches_with_events: int = 0
    matches_with_errors: int = 0
    total_duels_found: int = 0

    def add_entry(self, entry: AntagonistEntry) -> None:
        """Ajoute une entrée au résultat."""
        self.entries.append(entry)

    def get_top_nemeses(self, limit: int = 20) -> list[AntagonistEntry]:
        """Retourne les adversaires qui nous ont le plus tué.

        Args:
            limit: Nombre maximum de résultats.

        Returns:
            Liste triée par times_killed_by décroissant.
        """
        sorted_entries = sorted(
            self.entries,
            key=lambda e: (e.times_killed_by, -e.times_killed),
            reverse=True,
        )
        return sorted_entries[:limit]

    def get_top_victims(self, limit: int = 20) -> list[AntagonistEntry]:
        """Retourne les adversaires qu'on a le plus tué.

        Args:
            limit: Nombre maximum de résultats.

        Returns:
            Liste triée par times_killed décroissant.
        """
        sorted_entries = sorted(
            self.entries,
            key=lambda e: (e.times_killed, -e.times_killed_by),
            reverse=True,
        )
        return sorted_entries[:limit]

    def get_top_rivals(self, limit: int = 20) -> list[AntagonistEntry]:
        """Retourne les adversaires avec le plus de duels (kills + deaths).

        Args:
            limit: Nombre maximum de résultats.

        Returns:
            Liste triée par total de duels décroissant.
        """
        sorted_entries = sorted(
            self.entries,
            key=lambda e: (e.times_killed + e.times_killed_by, e.matches_against),
            reverse=True,
        )
        return sorted_entries[:limit]


def aggregate_antagonists(
    match_results: list[tuple[datetime, AntagonistsResult]],
    *,
    min_encounters: int = 1,
) -> AggregationResult:
    """Agrège les résultats d'antagonistes sur plusieurs matchs.

    Cette fonction prend les résultats de compute_personal_antagonists()
    pour chaque match et les agrège par adversaire.

    Args:
        match_results: Liste de tuples (match_time, AntagonistsResult).
            match_time est utilisé pour déterminer le dernier encounter.
        min_encounters: Nombre minimum de matchs pour inclure un adversaire.

    Returns:
        AggregationResult avec les données agrégées.
    """
    result = AggregationResult()
    antagonists_map: dict[str, AntagonistEntry] = {}

    for match_time, ar in match_results:
        result.matches_processed += 1

        # Compter les matchs avec des events (au moins un kill ou death)
        if ar.my_kills_total > 0 or ar.my_deaths_total > 0:
            result.matches_with_events += 1

        # Traiter le nemesis
        if ar.nemesis and ar.nemesis.xuid:
            xuid = ar.nemesis.xuid
            if xuid not in antagonists_map:
                antagonists_map[xuid] = AntagonistEntry(
                    opponent_xuid=xuid,
                    opponent_gamertag=ar.nemesis.gamertag or xuid,
                )

            entry = antagonists_map[xuid]
            # Ajouter les kills que le nemesis a fait contre moi
            entry.times_killed_by += ar.nemesis.opponent_killed_me.total
            # Ajouter les kills que j'ai fait contre le nemesis
            entry.times_killed += ar.nemesis.me_killed_opponent.total

            # Mettre à jour le gamertag et last_encounter
            if entry.last_encounter is None or match_time > entry.last_encounter:
                entry.last_encounter = match_time
                if ar.nemesis.gamertag:
                    entry.opponent_gamertag = ar.nemesis.gamertag

            entry.matches_against += 1
            result.total_duels_found += ar.nemesis.opponent_killed_me.total

        # Traiter le bully (victime préférée)
        if ar.bully and ar.bully.xuid:
            xuid = ar.bully.xuid

            # Si c'est le même que le nemesis, on a déjà comptabilisé
            if ar.nemesis and ar.nemesis.xuid == xuid:
                # Ne rien faire, déjà traité
                pass
            else:
                if xuid not in antagonists_map:
                    antagonists_map[xuid] = AntagonistEntry(
                        opponent_xuid=xuid,
                        opponent_gamertag=ar.bully.gamertag or xuid,
                    )

                entry = antagonists_map[xuid]
                # Ajouter les kills que j'ai fait contre le bully
                entry.times_killed += ar.bully.me_killed_opponent.total
                # Ajouter les kills que le bully a fait contre moi
                entry.times_killed_by += ar.bully.opponent_killed_me.total

                # Mettre à jour le gamertag et last_encounter
                if entry.last_encounter is None or match_time > entry.last_encounter:
                    entry.last_encounter = match_time
                    if ar.bully.gamertag:
                        entry.opponent_gamertag = ar.bully.gamertag

                entry.matches_against += 1
                result.total_duels_found += ar.bully.me_killed_opponent.total

    # Filtrer par nombre minimum d'encounters
    for _xuid, entry in antagonists_map.items():
        if entry.matches_against >= min_encounters:
            result.add_entry(entry)

    return result


def aggregate_antagonists_from_events(
    matches_data: list[dict[str, Any]],
    me_xuid: str,
    *,
    tolerance_ms: int = 5,
    load_official_stats_fn: Any | None = None,
    min_encounters: int = 1,
) -> AggregationResult:
    """Agrège les antagonistes directement depuis les données de matchs.

    Version haut niveau qui prend les données brutes et fait tout le traitement.

    Args:
        matches_data: Liste de dicts avec:
            - match_id: ID du match
            - start_time: datetime du match
            - highlight_events: Liste des events du match
            - official_stats: (optionnel) Stats officielles pour validation
        me_xuid: XUID du joueur principal.
        tolerance_ms: Tolérance pour l'appariement kill/death.
        load_official_stats_fn: Fonction pour charger les stats officielles (optionnel).
        min_encounters: Nombre minimum de matchs pour inclure un adversaire.

    Returns:
        AggregationResult avec les données agrégées.
    """
    from src.analysis.killer_victim import compute_personal_antagonists

    match_results: list[tuple[datetime, AntagonistsResult]] = []
    result = AggregationResult()

    for match_data in matches_data:
        result.matches_processed += 1

        match_id = match_data.get("match_id", "")
        start_time = match_data.get("start_time")
        events = match_data.get("highlight_events", [])
        official_stats = match_data.get("official_stats")

        if not isinstance(start_time, datetime):
            result.matches_with_errors += 1
            logger.warning(f"Match {match_id}: start_time invalide")
            continue

        if not events:
            # Pas d'events, on skip
            continue

        try:
            ar = compute_personal_antagonists(
                events,
                me_xuid=me_xuid,
                tolerance_ms=tolerance_ms,
                official_stats=official_stats,
            )
            match_results.append((start_time, ar))

        except Exception as e:
            result.matches_with_errors += 1
            logger.warning(f"Match {match_id}: erreur lors du calcul: {e}")
            continue

    # Déléguer l'agrégation
    aggregated = aggregate_antagonists(match_results, min_encounters=min_encounters)

    # Copier les métriques
    result.entries = aggregated.entries
    result.matches_with_events = aggregated.matches_with_events
    result.total_duels_found = aggregated.total_duels_found

    return result
