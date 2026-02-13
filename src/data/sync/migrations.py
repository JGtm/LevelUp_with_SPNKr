"""Migrations de schéma DuckDB centralisées.

Ce module regroupe toutes les fonctions de migration de colonnes
utilisées à la fois par engine.py (sync) et backfill_data.py.
Cela évite la duplication de code et garantit la cohérence du schéma.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

logger = logging.getLogger(__name__)


def get_table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    """Retourne l'ensemble des noms de colonnes d'une table.

    Args:
        conn: Connexion DuckDB.
        table_name: Nom de la table.

    Returns:
        Ensemble des noms de colonnes (vide si la table n'existe pas).
    """
    try:
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ?",
            [table_name],
        ).fetchall()
        return {r[0] for r in cols} if cols else set()
    except Exception as e:
        logger.debug(f"Impossible de lire les colonnes de {table_name}: {e}")
        return set()


def table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    """Vérifie si une table existe dans le schéma main.

    Args:
        conn: Connexion DuckDB.
        table_name: Nom de la table.

    Returns:
        True si la table existe.
    """
    try:
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_name = ?",
            [table_name],
        ).fetchone()
        return bool(result and result[0] > 0)
    except Exception:
        return False


def column_exists(conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> bool:
    """Vérifie si une colonne existe dans une table.

    Args:
        conn: Connexion DuckDB.
        table_name: Nom de la table.
        column_name: Nom de la colonne.

    Returns:
        True si la colonne existe.
    """
    try:
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ? AND column_name = ?",
            [table_name, column_name],
        ).fetchone()
        return bool(result and result[0] > 0)
    except Exception:
        return False


def _add_column_if_missing(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    column_name: str,
    column_type: str,
    existing_cols: set[str] | None = None,
) -> bool:
    """Ajoute une colonne à une table si elle n'existe pas.

    Args:
        conn: Connexion DuckDB.
        table_name: Nom de la table.
        column_name: Nom de la colonne à ajouter.
        column_type: Type SQL de la colonne.
        existing_cols: Colonnes existantes (optionnel, évite un query).

    Returns:
        True si la colonne a été ajoutée, False sinon.
    """
    if existing_cols is not None:
        is_missing = column_name not in existing_cols
    else:
        is_missing = not column_exists(conn, table_name, column_name)

    if is_missing:
        try:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            logger.info(f"Ajout de la colonne {column_name} à {table_name}")
            return True
        except Exception as e:
            logger.warning(f"Impossible d'ajouter {column_name} à {table_name}: {e}")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Migrations match_stats
# ─────────────────────────────────────────────────────────────────────────────


def ensure_match_stats_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """S'assure que match_stats a toutes les colonnes optionnelles.

    Colonnes ajoutées si manquantes :
    - accuracy (FLOAT)
    - end_time (TIMESTAMP)
    - session_id (INTEGER)
    - session_label (VARCHAR)
    - rank (SMALLINT)
    - damage_dealt (FLOAT)
    - personal_score (INTEGER)
    - performance_score (FLOAT)
    """
    if not table_exists(conn, "match_stats"):
        return

    col_names = get_table_columns(conn, "match_stats")

    migrations: list[tuple[str, str]] = [
        ("accuracy", "FLOAT"),
        ("end_time", "TIMESTAMP"),
        ("session_id", "INTEGER"),
        ("session_label", "VARCHAR"),
        ("rank", "SMALLINT"),
        ("damage_dealt", "FLOAT"),
        ("personal_score", "INTEGER"),
        ("performance_score", "FLOAT"),
    ]

    for col_name, col_type in migrations:
        _add_column_if_missing(conn, "match_stats", col_name, col_type, col_names)


def ensure_performance_score_column(conn: duckdb.DuckDBPyConnection) -> None:
    """S'assure que la colonne performance_score existe dans match_stats."""
    _add_column_if_missing(conn, "match_stats", "performance_score", "FLOAT")


def ensure_end_time_column(conn: duckdb.DuckDBPyConnection) -> None:
    """S'assure que la colonne end_time existe dans match_stats."""
    _add_column_if_missing(conn, "match_stats", "end_time", "TIMESTAMP")


# ─────────────────────────────────────────────────────────────────────────────
# Migrations match_participants
# ─────────────────────────────────────────────────────────────────────────────


def ensure_match_participants_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Ajoute rank, score, kills, deaths, assists, shots, damage à match_participants si absents.

    Colonnes ajoutées si manquantes :
    - rank (SMALLINT)
    - score (INTEGER)
    - kills (SMALLINT)
    - deaths (SMALLINT)
    - assists (SMALLINT)
    - shots_fired (INTEGER)
    - shots_hit (INTEGER)
    - damage_dealt (FLOAT)
    - damage_taken (FLOAT)
    """
    if not table_exists(conn, "match_participants"):
        return

    col_names = get_table_columns(conn, "match_participants")

    migrations: list[tuple[str, str]] = [
        ("rank", "SMALLINT"),
        ("score", "INTEGER"),
        ("kills", "SMALLINT"),
        ("deaths", "SMALLINT"),
        ("assists", "SMALLINT"),
        ("shots_fired", "INTEGER"),
        ("shots_hit", "INTEGER"),
        ("damage_dealt", "FLOAT"),
        ("damage_taken", "FLOAT"),
    ]

    for col_name, col_type in migrations:
        _add_column_if_missing(conn, "match_participants", col_name, col_type, col_names)


# ─────────────────────────────────────────────────────────────────────────────
# Migration medals_earned (INT32 → BIGINT)
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# Backfill bitmask : colonne match_stats.backfill_completed
# ─────────────────────────────────────────────────────────────────────────────

BACKFILL_FLAGS: dict[str, int] = {
    "medals": 1 << 0,  # 1
    "events": 1 << 1,  # 2
    "skill": 1 << 2,  # 4
    "personal_scores": 1 << 3,  # 8
    "performance_scores": 1 << 4,  # 16
    "accuracy": 1 << 5,  # 32
    "shots": 1 << 6,  # 64
    "enemy_mmr": 1 << 7,  # 128
    "assets": 1 << 8,  # 256
    "participants": 1 << 9,  # 512
    "participants_scores": 1 << 10,  # 1024
    "participants_kda": 1 << 11,  # 2048
    "participants_shots": 1 << 12,  # 4096
    "participants_damage": 1 << 13,  # 8192
    "aliases": 1 << 14,  # 16384
}


def compute_backfill_mask(*types: str) -> int:
    """Calcule le masque de bits pour les types demandés.

    >>> compute_backfill_mask("medals", "events")
    3
    """
    mask = 0
    for t in types:
        mask |= BACKFILL_FLAGS.get(t, 0)
    return mask


def ensure_backfill_completed_column(conn: duckdb.DuckDBPyConnection) -> None:
    """Ajoute la colonne backfill_completed (bitmask) à match_stats si absente."""
    _add_column_if_missing(conn, "match_stats", "backfill_completed", "INTEGER DEFAULT 0")


# ─────────────────────────────────────────────────────────────────────────────
# Migration medals_earned (INT32 → BIGINT)
# ─────────────────────────────────────────────────────────────────────────────


def ensure_medals_earned_bigint(conn: duckdb.DuckDBPyConnection) -> bool:
    """Migre medal_name_id de INTEGER vers BIGINT si nécessaire.

    Certaines medal_name_id dépassent INT32, il faut utiliser BIGINT.
    DuckDB ne supporte pas ALTER COLUMN TYPE, il faut recréer la table.

    Returns:
        True si la migration a été effectuée.
    """
    if not table_exists(conn, "medals_earned"):
        return False

    try:
        col_info = conn.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'medals_earned' AND column_name = 'medal_name_id'"
        ).fetchone()

        if col_info and col_info[0] in ("INTEGER", "INT32"):
            logger.info("Migration du schéma medals_earned: INTEGER -> BIGINT...")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS medals_earned_new (
                    match_id VARCHAR,
                    medal_name_id BIGINT,
                    count SMALLINT,
                    PRIMARY KEY (match_id, medal_name_id)
                )
            """)
            conn.execute("""
                INSERT INTO medals_earned_new
                SELECT match_id, CAST(medal_name_id AS BIGINT), count
                FROM medals_earned
            """)
            conn.execute("DROP TABLE medals_earned")
            conn.execute("ALTER TABLE medals_earned_new RENAME TO medals_earned")
            logger.info("✅ Schéma medals_earned migré vers BIGINT")
            return True
    except Exception as e:
        logger.warning(f"Migration medals_earned échouée (continuation): {e}")

    return False
