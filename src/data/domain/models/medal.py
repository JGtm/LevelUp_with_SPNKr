"""
Modèles de données pour les médailles.
(Data models for medals)

HOW IT WORKS:
- MedalAward : Une médaille obtenue dans un match
- Stocké dans Parquet (données volumineuses)
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class MedalAward(BaseModel):
    """
    Une médaille obtenue par un joueur dans un match.
    (A medal awarded to a player in a match)
    
    Stockée dans Parquet car :
    - Volume très important (plusieurs médailles par match)
    - Append-only (jamais modifiée après création)
    - Requêtes analytiques (agrégations, top médailles)
    """
    model_config = ConfigDict(frozen=True)
    
    # Identifiants
    match_id: str = Field(..., description="ID du match")
    xuid: str = Field(..., description="XUID du joueur")
    
    # Partitionnement
    start_time: datetime = Field(..., description="Début du match (pour partitionnement)")
    year: int = Field(..., description="Année (partition)")
    month: int = Field(..., description="Mois (partition)")
    
    # Données de la médaille
    medal_name_id: int = Field(..., description="ID de la médaille (FK vers définitions)")
    count: int = Field(default=1, ge=1, description="Nombre de fois obtenue dans ce match")
    
    @classmethod
    def from_raw(
        cls,
        match_id: str,
        xuid: str,
        start_time: datetime,
        name_id: int,
        count: int,
    ) -> MedalAward:
        """
        Crée un MedalAward depuis les données brutes.
        (Create MedalAward from raw data)
        """
        return cls(
            match_id=match_id,
            xuid=xuid,
            start_time=start_time,
            year=start_time.year,
            month=start_time.month,
            medal_name_id=name_id,
            count=count,
        )
