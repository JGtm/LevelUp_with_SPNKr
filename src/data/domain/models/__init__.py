"""
Modèles de domaine avec validation Pydantic v2.
(Domain models with Pydantic v2 validation)
"""

from src.data.domain.models.match import (
    MatchFact,
    MatchFactInput,
    MatchOutcome,
)
from src.data.domain.models.medal import MedalAward
from src.data.domain.models.player import PlayerProfile
from src.data.domain.models.stats import (
    AggregatedStats,
    FriendMatch,
    MapBreakdown,
    MatchRow,
    OutcomeRates,
)

__all__ = [
    "MatchFactInput",
    "MatchFact",
    "MatchOutcome",
    "MatchRow",
    "AggregatedStats",
    "OutcomeRates",
    "FriendMatch",
    "MapBreakdown",
    "PlayerProfile",
    "MedalAward",
]
