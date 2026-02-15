"""
Modèles de données pour les joueurs.
(Data models for players)

HOW IT WORKS:
- PlayerProfile : Profil complet d'un joueur avec métadonnées
- Ces données sont stockées dans SQLite (données chaudes/relationnelles)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict, field_validator


class PlayerProfile(BaseModel):
    """
    Profil d'un joueur Halo Infinite.
    (Halo Infinite player profile)
    
    Stocké dans SQLite car :
    - Données relationnelles (FK depuis match_facts)
    - Mises à jour fréquentes (gamertag, rank, etc.)
    - Volume faible (quelques milliers max)
    """
    model_config = ConfigDict(extra="ignore")
    
    xuid: str = Field(..., description="Xbox User ID unique")
    gamertag: str = Field(..., description="Nom d'affichage Xbox")
    
    # Personnalisation
    service_tag: str | None = Field(default=None, description="Tag de service (4 chars)")
    emblem_path: str | None = Field(default=None, description="Chemin vers l'emblème")
    backdrop_path: str | None = Field(default=None, description="Chemin vers le backdrop")
    
    # Progression
    career_rank: int = Field(default=0, ge=0, le=272, description="Rang de carrière (0-272)")
    
    # Métadonnées
    last_seen_at: datetime | None = Field(default=None, description="Dernier match joué")
    created_at: datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)
    
    # Stats de synchronisation
    total_matches: int = Field(default=0, ge=0)
    last_sync_at: datetime | None = Field(default=None)
    
    @field_validator("xuid", mode="before")
    @classmethod
    def parse_xuid(cls, v: Any) -> str:
        """Parse et valide le XUID."""
        if v is None:
            raise ValueError("XUID cannot be None")
        v_str = str(v)
        if v_str.startswith("xuid(") and v_str.endswith(")"):
            return v_str[5:-1]
        return v_str
    
    @field_validator("gamertag", mode="before")
    @classmethod
    def sanitize_gamertag(cls, v: Any) -> str:
        """Nettoie le gamertag."""
        if v is None:
            return ""
        return str(v).strip()
