"""Module de synchronisation API → DuckDB.

Ce module gère le pipeline de synchronisation unifié :
API SPNKr → Transformation Pydantic → DuckDB (direct)

Architecture:
- api_client.py : Wrapper SPNKr async avec rate limiting
- transformers.py : Transformation JSON API → rows DuckDB
- engine.py : Orchestrateur DuckDBSyncEngine
- delta.py : Logique de synchronisation incrémentale
- models.py : Modèles de données (SyncOptions, SyncResult)

Usage:
    from src.data.sync import DuckDBSyncEngine, SyncOptions

    engine = DuckDBSyncEngine(
        player_db_path="data/players/Chocoboflor/stats.duckdb",
        xuid="123456789",
        gamertag="Chocoboflor",
    )

    result = await engine.sync_delta()
    print(result.to_message())
"""

from src.data.sync.api_client import SPNKrAPIClient, Tokens, get_tokens_from_env
from src.data.sync.engine import DuckDBSyncEngine
from src.data.sync.models import (
    HighlightEventRow,
    MatchData,
    MatchHistoryItem,
    MatchStatsRow,
    PlayerMatchStatsRow,
    SyncOptions,
    SyncResult,
    XuidAliasRow,
)
from src.data.sync.transformers import (
    extract_aliases,
    extract_xuids_from_match,
    transform_highlight_events,
    transform_match_stats,
    transform_skill_stats,
)

__all__ = [
    # Models
    "SyncOptions",
    "SyncResult",
    "MatchData",
    "MatchHistoryItem",
    "MatchStatsRow",
    "PlayerMatchStatsRow",
    "HighlightEventRow",
    "XuidAliasRow",
    # Engine
    "DuckDBSyncEngine",
    # API Client
    "SPNKrAPIClient",
    "Tokens",
    "get_tokens_from_env",
    # Transformers
    "transform_match_stats",
    "transform_skill_stats",
    "transform_highlight_events",
    "extract_aliases",
    "extract_xuids_from_match",
]
