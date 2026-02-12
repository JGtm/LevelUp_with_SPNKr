"""
Modèles de données pour les matchs Halo Infinite.
(Data models for Halo Infinite matches)

HOW IT WORKS:
- MatchFactInput : Validation des données brutes JSON de l'API
- MatchFact : Entité métier immuable utilisée dans le domaine
- MatchOutcome : Enum des résultats possibles

Ces modèles utilisent Pydantic v2 pour la validation stricte des données
avant leur transformation en fichiers Parquet.
"""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MatchOutcome(IntEnum):
    """
    Résultats possibles d'un match.
    (Possible match outcomes)
    """

    TIE = 1  # Égalité
    WIN = 2  # Victoire
    LOSS = 3  # Défaite
    DID_NOT_FINISH = 4  # Match non terminé


class MatchFactInput(BaseModel):
    """
    Modèle de validation pour les données brutes de l'API.
    (Validation model for raw API data)

    Valide et transforme les données JSON avant stockage.
    Gère les différents formats de l'API SPNKr (nombres, durées, XUIDs).
    """

    model_config = ConfigDict(extra="ignore")  # Ignore les champs inconnus

    match_id: str = Field(..., min_length=1, description="ID unique du match")
    xuid: str = Field(..., description="XUID du joueur")
    start_time: datetime = Field(..., description="Début du match (UTC)")

    # Références (FKs vers tables de dimension)
    playlist_id: str | None = Field(default=None)
    map_id: str | None = Field(default=None)
    game_variant_id: str | None = Field(default=None)

    # Résultat du match
    outcome: MatchOutcome = Field(default=MatchOutcome.DID_NOT_FINISH)
    team_id: Annotated[int, Field(ge=0, le=10)] = 0

    # Statistiques de combat
    kills: Annotated[int, Field(ge=0)] = 0
    deaths: Annotated[int, Field(ge=0)] = 0
    assists: Annotated[int, Field(ge=0)] = 0
    kda: float = 0.0
    accuracy: Annotated[float, Field(ge=0, le=100)] | None = None

    # Statistiques avancées
    headshot_kills: Annotated[int, Field(ge=0)] = 0
    max_killing_spree: Annotated[int, Field(ge=0)] = 0
    time_played_seconds: Annotated[int, Field(ge=0)] = 0
    avg_life_seconds: Annotated[float, Field(ge=0)] | None = None

    # Scores d'équipe
    my_team_score: int = 0
    enemy_team_score: int = 0

    # MMR (Matchmaking Rating)
    team_mmr: float | None = None
    enemy_mmr: float | None = None

    # Noms pour affichage (dénormalisés)
    playlist_name: str | None = None
    map_name: str | None = None
    game_variant_name: str | None = None

    @field_validator("xuid", mode="before")
    @classmethod
    def parse_xuid(cls, v: Any) -> str:
        """
        Parse les différents formats de XUID.
        (Parse different XUID formats)

        Formats supportés:
        - "2533274823110022" (string direct)
        - "xuid(2533274823110022)" (format wrapper)
        - {"Xuid": "2533274823110022"} (format objet)
        """
        if v is None:
            return ""
        if isinstance(v, dict):
            xuid_val = v.get("Xuid") or v.get("xuid") or ""
            return str(xuid_val)
        v_str = str(v)
        if v_str.startswith("xuid(") and v_str.endswith(")"):
            return v_str[5:-1]
        return v_str

    @field_validator("start_time", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime:
        """
        Parse les dates ISO 8601.
        (Parse ISO 8601 dates)
        """
        if isinstance(v, datetime):
            return v
        if not isinstance(v, str):
            raise ValueError(f"Invalid datetime format: {v}")
        # Gère les formats avec/sans timezone
        v_str = v
        if v_str.endswith("Z"):
            v_str = v_str[:-1] + "+00:00"
        return datetime.fromisoformat(v_str)

    @field_validator("outcome", mode="before")
    @classmethod
    def parse_outcome(cls, v: Any) -> MatchOutcome:
        """Parse l'outcome en enum."""
        if isinstance(v, MatchOutcome):
            return v
        if v is None:
            return MatchOutcome.DID_NOT_FINISH
        try:
            return MatchOutcome(int(v))
        except (ValueError, TypeError):
            return MatchOutcome.DID_NOT_FINISH


class MatchFact(BaseModel):
    """
    Entité métier immuable pour un fait de match.
    (Immutable business entity for a match fact)

    Représente une ligne dans la table de faits Parquet.
    Inclut les colonnes de partitionnement (year, month).
    """

    model_config = ConfigDict(frozen=True)  # Immuable

    # Identifiants
    match_id: str
    xuid: str
    start_time: datetime

    # Colonnes de partitionnement
    year: int
    month: int

    # Références vers dimensions (FKs)
    playlist_id: str | None
    map_id: str | None
    game_variant_id: str | None

    # Noms dénormalisés pour éviter les jointures fréquentes
    playlist_name: str | None
    map_name: str | None
    game_variant_name: str | None

    # Faits de résultat
    outcome: MatchOutcome
    team_id: int

    # Faits de combat
    kills: int
    deaths: int
    assists: int
    kda: float
    accuracy: float | None
    headshot_kills: int
    max_killing_spree: int
    time_played_seconds: int
    avg_life_seconds: float | None

    # Faits d'équipe
    my_team_score: int
    enemy_team_score: int
    team_mmr: float | None
    enemy_mmr: float | None

    # Enrichissement (calculé après)
    session_id: str | None = None
    performance_score: float | None = None

    @classmethod
    def from_input(cls, input_data: MatchFactInput) -> MatchFact:
        """
        Crée un MatchFact depuis un MatchFactInput validé.
        (Create MatchFact from validated MatchFactInput)

        Ajoute automatiquement les colonnes de partitionnement (year, month).
        """
        return cls(
            match_id=input_data.match_id,
            xuid=input_data.xuid,
            start_time=input_data.start_time,
            year=input_data.start_time.year,
            month=input_data.start_time.month,
            playlist_id=input_data.playlist_id,
            map_id=input_data.map_id,
            game_variant_id=input_data.game_variant_id,
            playlist_name=input_data.playlist_name,
            map_name=input_data.map_name,
            game_variant_name=input_data.game_variant_name,
            outcome=input_data.outcome,
            team_id=input_data.team_id,
            kills=input_data.kills,
            deaths=input_data.deaths,
            assists=input_data.assists,
            kda=input_data.kda,
            accuracy=input_data.accuracy,
            headshot_kills=input_data.headshot_kills,
            max_killing_spree=input_data.max_killing_spree,
            time_played_seconds=input_data.time_played_seconds,
            avg_life_seconds=input_data.avg_life_seconds,
            my_team_score=input_data.my_team_score,
            enemy_team_score=input_data.enemy_team_score,
            team_mmr=input_data.team_mmr,
            enemy_mmr=input_data.enemy_mmr,
        )

    def to_match_row_dict(self) -> dict:
        """
        Convertit en dict compatible avec MatchRow (dataclass existante).
        (Convert to dict compatible with MatchRow dataclass)

        Permet l'interopérabilité avec le code existant.
        """
        return {
            "match_id": self.match_id,
            "start_time": self.start_time,
            "map_id": self.map_id,
            "map_name": self.map_name,
            "playlist_id": self.playlist_id,
            "playlist_name": self.playlist_name,
            "map_mode_pair_id": None,  # Non stocké dans Parquet
            "map_mode_pair_name": None,
            "game_variant_id": self.game_variant_id,
            "game_variant_name": self.game_variant_name,
            "outcome": self.outcome.value,
            "last_team_id": self.team_id,
            "kda": self.kda,
            "max_killing_spree": self.max_killing_spree,
            "headshot_kills": self.headshot_kills,
            "average_life_seconds": self.avg_life_seconds,
            "time_played_seconds": self.time_played_seconds,
            "kills": self.kills,
            "deaths": self.deaths,
            "assists": self.assists,
            "accuracy": self.accuracy,
            "my_team_score": self.my_team_score,
            "enemy_team_score": self.enemy_team_score,
            "team_mmr": self.team_mmr,
            "enemy_mmr": self.enemy_mmr,
        }
