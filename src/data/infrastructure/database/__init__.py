"""
Connecteurs de base de données.
(Database connectors)

Ce module fournit :
- DuckDBEngine : Moteur DuckDB pour requêtes analytiques
- DuckDBConfig : Configuration centralisée DuckDB
"""

from src.data.infrastructure.database.duckdb_config import (
    ANALYTICS_CONFIG,
    DEFAULT_CONFIG,
    WRITE_CONFIG,
    DuckDBConfig,
    configure_connection,
    get_attach_sql,
)
from src.data.infrastructure.database.duckdb_engine import DuckDBEngine

__all__ = [
    # Config DuckDB
    "DuckDBConfig",
    "DEFAULT_CONFIG",
    "ANALYTICS_CONFIG",
    "WRITE_CONFIG",
    "configure_connection",
    "get_attach_sql",
    # Engines
    "DuckDBEngine",
]
