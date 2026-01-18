"""Gestion des connexions SQLite."""

import sqlite3
from contextlib import contextmanager
from typing import Generator


class DatabaseConnection:
    """Gestionnaire de connexion SQLite avec context manager.
    
    Exemple d'utilisation:
        with DatabaseConnection("path/to/db.db") as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM table")
    """

    def __init__(self, db_path: str):
        """Initialise la connexion.
        
        Args:
            db_path: Chemin vers le fichier SQLite.
        """
        self.db_path = db_path
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        """Ouvre la connexion."""
        self._connection = sqlite3.connect(self.db_path)
        return self._connection

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ferme la connexion."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None


@contextmanager
def get_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Context manager pour obtenir une connexion SQLite.
    
    Args:
        db_path: Chemin vers le fichier SQLite.
        
    Yields:
        La connexion SQLite ouverte.
        
    Exemple:
        with get_connection("path/to/db.db") as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM table")
    """
    con = sqlite3.connect(db_path)
    try:
        yield con
    finally:
        con.close()
