"""
Modèles de domaine avec validation Pydantic v2.
(Domain models with Pydantic v2 validation)
"""

from src.data.domain.models.match import (
    MatchFactInput,
    MatchFact,
    MatchOutcome,
)
from src.data.domain.models.player import PlayerProfile
from src.data.domain.models.medal import MedalAward

__all__ = [
    "MatchFactInput",
    "MatchFact", 
    "MatchOutcome",
    "PlayerProfile",
    "MedalAward",
]
