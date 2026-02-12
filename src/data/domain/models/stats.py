"""Modèles dataclass pour l'analytique de matchs.

Ce module regroupe les structures de données historisées (MatchRow,
AggregatedStats, OutcomeRates, FriendMatch, MapBreakdown) utilisées par les
repositories et la couche d'analyse.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MatchRow:
    """Représente une ligne de match avec les statistiques du joueur."""

    match_id: str
    start_time: datetime
    map_id: str | None
    map_name: str | None
    playlist_id: str | None
    playlist_name: str | None
    map_mode_pair_id: str | None
    map_mode_pair_name: str | None
    outcome: int | None
    last_team_id: int | None
    kda: float | None
    max_killing_spree: int | None
    headshot_kills: int | None
    average_life_seconds: float | None
    time_played_seconds: float | None
    kills: int
    deaths: int
    assists: int
    accuracy: float | None

    game_variant_id: str | None = None
    game_variant_name: str | None = None
    my_team_score: int | None = None
    enemy_team_score: int | None = None
    team_mmr: float | None = None
    enemy_mmr: float | None = None
    personal_score: int | None = None
    known_teammates_count: int = 0
    is_with_friends: bool = False
    friends_xuids: str = ""

    @property
    def ratio(self) -> float:
        """Calcule le ratio (Frags + assists/2) / morts."""
        if self.deaths <= 0:
            return float("nan")
        return (self.kills + (self.assists / 2.0)) / self.deaths

    @property
    def is_win(self) -> bool:
        """Retourne True si le match est une victoire."""
        return self.outcome == 2

    @property
    def is_loss(self) -> bool:
        """Retourne True si le match est une défaite."""
        return self.outcome == 3


@dataclass
class AggregatedStats:
    """Statistiques agrégées sur un ensemble de matchs."""

    total_kills: int = 0
    total_deaths: int = 0
    total_assists: int = 0
    total_matches: int = 0
    total_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, int | float]:
        """Expose une représentation dict pour compatibilité."""
        return {
            "total_kills": self.total_kills,
            "total_deaths": self.total_deaths,
            "total_assists": self.total_assists,
            "total_matches": self.total_matches,
            "total_time_seconds": self.total_time_seconds,
        }

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return key in self.to_dict()

    def __getitem__(self, key: str) -> int | float:
        return self.to_dict()[key]

    def __iter__(self):
        return iter(self.to_dict())

    @property
    def global_ratio(self) -> float | None:
        """Calcule le ratio global (K + A/2) / D."""
        if self.total_deaths <= 0:
            return None
        return (self.total_kills + self.total_assists / 2.0) / self.total_deaths

    @property
    def kills_per_match(self) -> float | None:
        """Moyenne de frags par match."""
        if self.total_matches <= 0:
            return None
        return self.total_kills / self.total_matches

    @property
    def deaths_per_match(self) -> float | None:
        """Moyenne de morts par match."""
        if self.total_matches <= 0:
            return None
        return self.total_deaths / self.total_matches

    @property
    def assists_per_match(self) -> float | None:
        """Moyenne d'assistances par match."""
        if self.total_matches <= 0:
            return None
        return self.total_assists / self.total_matches

    @property
    def kills_per_minute(self) -> float | None:
        """Frags par minute."""
        minutes = self.total_time_seconds / 60.0
        if minutes <= 0:
            return None
        return self.total_kills / minutes

    @property
    def deaths_per_minute(self) -> float | None:
        """Morts par minute."""
        minutes = self.total_time_seconds / 60.0
        if minutes <= 0:
            return None
        return self.total_deaths / minutes

    @property
    def assists_per_minute(self) -> float | None:
        """Assistances par minute."""
        minutes = self.total_time_seconds / 60.0
        if minutes <= 0:
            return None
        return self.total_assists / minutes


@dataclass
class OutcomeRates:
    """Taux de victoire/défaite sur un ensemble de matchs."""

    wins: int = 0
    losses: int = 0
    ties: int = 0
    no_finish: int = 0
    total: int = 0

    @property
    def win_rate(self) -> float | None:
        """Taux de victoire (0-1)."""
        if self.total <= 0:
            return None
        return self.wins / self.total

    @property
    def loss_rate(self) -> float | None:
        """Taux de défaite (0-1)."""
        if self.total <= 0:
            return None
        return self.losses / self.total


@dataclass
class FriendMatch:
    """Représente un match joué avec un ami."""

    match_id: str
    start_time: datetime
    playlist_id: str | None
    playlist_name: str | None
    pair_id: str | None
    pair_name: str | None
    my_team_id: int | None
    my_outcome: int | None
    friend_team_id: int | None
    friend_outcome: int | None
    same_team: bool


@dataclass
class MapBreakdown:
    """Statistiques agrégées pour une carte spécifique."""

    map_name: str
    matches: int
    accuracy_avg: float | None
    win_rate: float | None
    loss_rate: float | None
    ratio_global: float | None
