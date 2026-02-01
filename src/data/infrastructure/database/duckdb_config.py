"""Configuration centralisée pour DuckDB.

Ce module centralise tous les paramètres de configuration DuckDB
utilisés dans le projet OpenSpartan Graph (architecture v4).

Usage:
    from src.data.infrastructure.database.duckdb_config import DuckDBConfig, configure_connection

    # Utiliser les valeurs par défaut
    with duckdb.connect(path) as conn:
        configure_connection(conn)

    # Ou avec des valeurs personnalisées
    config = DuckDBConfig(memory_limit="1GB", threads=4)
    with duckdb.connect(path) as conn:
        config.apply(conn)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb


# =============================================================================
# Configuration par défaut
# =============================================================================

# Limite mémoire DuckDB par défaut pour les opérations de lecture
DEFAULT_MEMORY_LIMIT = "512MB"

# Limite mémoire DuckDB pour les opérations analytiques lourdes
DEFAULT_MEMORY_LIMIT_ANALYTICS = "1GB"

# Limite mémoire DuckDB pour les opérations d'écriture (plus légères)
DEFAULT_MEMORY_LIMIT_WRITE = "256MB"

# Nombre de threads (None = auto-détection par DuckDB)
DEFAULT_THREADS = None

# Active le cache d'objets DuckDB pour les lectures répétées
DEFAULT_ENABLE_OBJECT_CACHE = True

# Désactive la barre de progression (meilleur pour les apps)
DEFAULT_ENABLE_PROGRESS_BAR = False


# =============================================================================
# Configuration via environnement
# =============================================================================


def _get_env_memory_limit() -> str | None:
    """Lit la limite mémoire depuis l'environnement."""
    return os.environ.get("OPENSPARTAN_DUCKDB_MEMORY_LIMIT")


def _get_env_threads() -> int | None:
    """Lit le nombre de threads depuis l'environnement."""
    val = os.environ.get("OPENSPARTAN_DUCKDB_THREADS")
    if val:
        try:
            return int(val)
        except ValueError:
            pass
    return None


# =============================================================================
# Classe de configuration
# =============================================================================


@dataclass
class DuckDBConfig:
    """Configuration DuckDB avec paramètres par défaut.

    Attributes:
        memory_limit: Limite mémoire (ex: "512MB", "1GB")
        threads: Nombre de threads (None = auto)
        enable_object_cache: Active le cache d'objets
        enable_progress_bar: Active la barre de progression
    """

    memory_limit: str = DEFAULT_MEMORY_LIMIT
    threads: int | None = DEFAULT_THREADS
    enable_object_cache: bool = DEFAULT_ENABLE_OBJECT_CACHE
    enable_progress_bar: bool = DEFAULT_ENABLE_PROGRESS_BAR

    def __post_init__(self) -> None:
        """Applique les overrides depuis l'environnement."""
        if env_memory := _get_env_memory_limit():
            self.memory_limit = env_memory
        if env_threads := _get_env_threads():
            self.threads = env_threads

    def apply(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Applique la configuration à une connexion DuckDB.

        Args:
            conn: Connexion DuckDB ouverte.
        """
        conn.execute(f"SET memory_limit = '{self.memory_limit}'")

        if self.threads is not None:
            conn.execute(f"SET threads = {self.threads}")

        if self.enable_object_cache:
            conn.execute("SET enable_object_cache = true")
        else:
            conn.execute("SET enable_object_cache = false")

        if self.enable_progress_bar:
            conn.execute("SET enable_progress_bar = true")
        else:
            conn.execute("SET enable_progress_bar = false")


# =============================================================================
# Configurations pré-définies
# =============================================================================

# Configuration standard pour lectures
DEFAULT_CONFIG = DuckDBConfig()

# Configuration pour analytics lourds
ANALYTICS_CONFIG = DuckDBConfig(
    memory_limit=DEFAULT_MEMORY_LIMIT_ANALYTICS,
    enable_object_cache=True,
)

# Configuration pour écritures
WRITE_CONFIG = DuckDBConfig(
    memory_limit=DEFAULT_MEMORY_LIMIT_WRITE,
    enable_object_cache=False,
)


# =============================================================================
# Fonctions utilitaires
# =============================================================================


def configure_connection(
    conn: duckdb.DuckDBPyConnection,
    *,
    memory_limit: str | None = None,
    threads: int | None = None,
) -> None:
    """Configure une connexion DuckDB avec les paramètres par défaut.

    Args:
        conn: Connexion DuckDB ouverte.
        memory_limit: Override de la limite mémoire (optionnel).
        threads: Override du nombre de threads (optionnel).
    """
    config = DuckDBConfig(
        memory_limit=memory_limit or DEFAULT_MEMORY_LIMIT,
        threads=threads,
    )
    config.apply(conn)


def get_attach_sql(
    db_path: str,
    alias: str,
    *,
    read_only: bool = True,
    db_type: str | None = None,
) -> str:
    """Génère la commande SQL ATTACH pour une DB.

    Args:
        db_path: Chemin vers la DB.
        alias: Alias pour la DB attachée.
        read_only: Si True, attacher en lecture seule.
        db_type: Type de DB ("SQLITE", "DUCKDB", ou None pour auto).

    Returns:
        Commande SQL ATTACH.
    """
    parts = [f"ATTACH '{db_path}' AS {alias}"]

    options = []
    if read_only:
        options.append("READ_ONLY")
    if db_type:
        options.append(f"TYPE {db_type}")

    if options:
        parts.append(f"({', '.join(options)})")

    return " ".join(parts)
