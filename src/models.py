"""Modèles de données (dataclasses) du projet."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MatchRow:
    """Représente une ligne de match avec les statistiques du joueur.

    Attributes:
        match_id: Identifiant unique du match.
        start_time: Date/heure de début du match (UTC).
        map_id: Identifiant de la carte (AssetId).
        map_name: Nom lisible de la carte.
        playlist_id: Identifiant de la playlist.
        playlist_name: Nom lisible de la playlist.
        map_mode_pair_id: Identifiant du couple carte/mode.
        map_mode_pair_name: Nom lisible du couple carte/mode.
        outcome: Code de résultat (1=Tie, 2=Win, 3=Loss, 4=NoFinish).
        last_team_id: ID de l'équipe du joueur.
        kda: Ratio KDA officiel du jeu.
        max_killing_spree: Plus longue série de kills.
        headshot_kills: Nombre de headshots.
        average_life_seconds: Durée de vie moyenne en secondes.
        time_played_seconds: Temps de jeu total en secondes.
        kills: Nombre de frags.
        deaths: Nombre de morts.
        assists: Nombre d'assistances.
        accuracy: Précision de tir en pourcentage.
    """

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

    # Champs optionnels ajoutés (avec defaults) — placés en fin pour compat dataclass
    game_variant_id: str | None = None
    game_variant_name: str | None = None

    # Scores d'équipe (si applicable). Pour FFA / modes sans score, reste à None.
    my_team_score: int | None = None
    enemy_team_score: int | None = None

    # MMR (Matchmaking Rating) - utilisé pour les analyses de matchmaking
    team_mmr: float | None = None
    enemy_mmr: float | None = None

    # Score personnel (Sprint 6)
    personal_score: int | None = None

    # Coéquipiers connus (amis)
    known_teammates_count: int = 0
    is_with_friends: bool = False
    friends_xuids: str = ""  # XUIDs séparés par des virgules

    @property
    def ratio(self) -> float:
        """Calcule le ratio (Frags + assists/2) / morts.

        Returns:
            Le ratio calculé, ou NaN si deaths == 0.
        """
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
    """Statistiques agrégées sur un ensemble de matchs.

    Attributes:
        total_kills: Nombre total de frags.
        total_deaths: Nombre total de morts.
        total_assists: Nombre total d'assistances.
        total_matches: Nombre de matchs.
        total_time_seconds: Temps de jeu total en secondes.
    """

    total_kills: int = 0
    total_deaths: int = 0
    total_assists: int = 0
    total_matches: int = 0
    total_time_seconds: float = 0.0

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
    """Taux de victoire/défaite sur un ensemble de matchs.

    Attributes:
        wins: Nombre de victoires.
        losses: Nombre de défaites.
        ties: Nombre d'égalités.
        no_finish: Nombre de matchs non terminés.
        total: Nombre total de matchs avec outcome.
    """

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
    """Représente un match joué avec un ami.

    Attributes:
        match_id: Identifiant du match.
        start_time: Date/heure de début.
        playlist_id: ID de la playlist.
        playlist_name: Nom de la playlist.
        pair_id: ID du couple carte/mode.
        pair_name: Nom du couple carte/mode.
        my_team_id: Mon ID d'équipe.
        my_outcome: Mon résultat.
        friend_team_id: ID d'équipe de l'ami.
        friend_outcome: Résultat de l'ami.
        same_team: True si on était dans la même équipe.
    """

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
    """Statistiques agrégées pour une carte spécifique.

    Attributes:
        map_name: Nom de la carte.
        matches: Nombre de matchs.
        accuracy_avg: Précision moyenne.
        win_rate: Taux de victoire.
        loss_rate: Taux de défaite.
        ratio_global: Ratio global.
    """

    map_name: str
    matches: int
    accuracy_avg: float | None
    win_rate: float | None
    loss_rate: float | None
    ratio_global: float | None
