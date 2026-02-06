"""Gestion des connexions base de données.

RÈGLE CRITIQUE : SQLite est PROSCRIT dans le code applicatif.
Uniquement DuckDB v4 (.duckdb) est supporté.
Pour migrer depuis SQLite, utiliser scripts/migrate_player_to_duckdb.py ou scripts/recover_from_sqlite.py.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb


class SQLiteForbiddenError(ValueError):
    """Levée lorsque un chemin .db (SQLite) est fourni.

    Le projet utilise exclusivement DuckDB. Migrez avec scripts/migrate_player_to_duckdb.py.
    """

    def __init__(self, db_path: str):
        super().__init__(
            f"SQLite (.db) interdit. Le chemin '{db_path}' pointe vers une base SQLite. "
            "Migrez vers DuckDB avec: python scripts/migrate_player_to_duckdb.py --gamertag <GAMERTAG>"
        )


def _ensure_duckdb_path(db_path: str) -> None:
    """Vérifie que le chemin est une base DuckDB, pas SQLite."""
    if not db_path or not isinstance(db_path, str):
        raise ValueError("db_path doit être un chemin non vide")
    if db_path.strip().lower().endswith(".db"):
        raise SQLiteForbiddenError(db_path)


@contextmanager
def get_connection(db_path: str) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Context manager pour obtenir une connexion DuckDB.

    Refuse explicitement les chemins .db (SQLite).
    Uniquement les fichiers .duckdb sont acceptés.

    Args:
        db_path: Chemin vers le fichier .duckdb (ex: data/players/JGtm/stats.duckdb).

    Yields:
        Connexion DuckDB ouverte.

    Raises:
        SQLiteForbiddenError: Si db_path se termine par .db.

    Exemple:
        with get_connection("data/players/JGtm/stats.duckdb") as con:
            con.execute("SELECT COUNT(*) FROM match_stats")
    """
    _ensure_duckdb_path(db_path)  # Refuse .db AVANT d'importer duckdb
    import duckdb

    con = duckdb.connect(db_path)
    try:
        yield con
    finally:
        con.close()


class DatabaseConnection:
    """Gestionnaire de connexion DuckDB avec context manager.

    RÈGLE : Uniquement les fichiers .duckdb sont acceptés.

    Exemple:
        with DatabaseConnection("data/players/JGtm/stats.duckdb") as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM match_stats LIMIT 1")
    """

    def __init__(self, db_path: str):
        """Initialise la connexion.

        Args:
            db_path: Chemin vers le fichier .duckdb (refuse .db).

        Raises:
            SQLiteForbiddenError: Si db_path se termine par .db.
        """
        _ensure_duckdb_path(db_path)
        self.db_path = db_path
        self._connection: duckdb.DuckDBPyConnection | None = None

    def __enter__(self) -> duckdb.DuckDBPyConnection:
        """Ouvre la connexion DuckDB."""
        import duckdb

        self._connection = duckdb.connect(self.db_path)
        return self._connection

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ferme la connexion."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
