"""Insertions batch DuckDB — Sprint 15.

Remplace les boucles `for row in rows: INSERT ...` par des insertions
groupées via `executemany` ou insertion depuis DataFrame Polars/Arrow.

Avantages :
- 10-50x plus rapide sur gros volumes (batches de N rows)
- Typage centralisé via CAST_PLAN
- Zéro dépendance Parquet (DuckDB-first)

Usage :
    from src.data.sync.batch_insert import batch_insert_rows

    batch_insert_rows(conn, "medals_earned", medal_rows, MEDALS_COLUMNS)
"""

from __future__ import annotations

import logging
from dataclasses import fields
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Plan de cast massif — Sprint 15.3
# =============================================================================

# Mapping colonne → type DuckDB attendu, appliqué à l'ingestion
# pour garantir la cohérence des types dans toutes les tables.
CAST_PLAN: dict[str, dict[str, str]] = {
    "match_stats": {
        "match_id": "VARCHAR",
        "start_time": "TIMESTAMP",
        "end_time": "TIMESTAMP",
        "playlist_id": "VARCHAR",
        "playlist_name": "VARCHAR",
        "map_id": "VARCHAR",
        "map_name": "VARCHAR",
        "pair_id": "VARCHAR",
        "pair_name": "VARCHAR",
        "game_variant_id": "VARCHAR",
        "game_variant_name": "VARCHAR",
        "outcome": "TINYINT",
        "team_id": "TINYINT",
        "rank": "SMALLINT",
        "kills": "SMALLINT",
        "deaths": "SMALLINT",
        "assists": "SMALLINT",
        "kda": "FLOAT",
        "accuracy": "FLOAT",
        "headshot_kills": "SMALLINT",
        "max_killing_spree": "SMALLINT",
        "time_played_seconds": "INTEGER",
        "avg_life_seconds": "FLOAT",
        "my_team_score": "SMALLINT",
        "enemy_team_score": "SMALLINT",
        "team_mmr": "FLOAT",
        "enemy_mmr": "FLOAT",
        "damage_dealt": "FLOAT",
        "damage_taken": "FLOAT",
        "shots_fired": "INTEGER",
        "shots_hit": "INTEGER",
        "grenade_kills": "SMALLINT",
        "melee_kills": "SMALLINT",
        "power_weapon_kills": "SMALLINT",
        "score": "INTEGER",
        "personal_score": "INTEGER",
        "mode_category": "VARCHAR",
        "is_ranked": "BOOLEAN",
        "is_firefight": "BOOLEAN",
        "left_early": "BOOLEAN",
        "session_id": "VARCHAR",
        "session_label": "VARCHAR",
        "performance_score": "FLOAT",
        "teammates_signature": "VARCHAR",
        "known_teammates_count": "SMALLINT",
        "is_with_friends": "BOOLEAN",
        "friends_xuids": "VARCHAR",
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
    },
    "medals_earned": {
        "match_id": "VARCHAR",
        "medal_name_id": "BIGINT",
        "count": "INTEGER",
    },
    "highlight_events": {
        "id": "INTEGER",
        "match_id": "VARCHAR",
        "event_type": "VARCHAR",
        "time_ms": "INTEGER",
        "xuid": "VARCHAR",
        "gamertag": "VARCHAR",
        "type_hint": "INTEGER",
        "raw_json": "VARCHAR",
    },
    "player_match_stats": {
        "match_id": "VARCHAR",
        "xuid": "VARCHAR",
        "team_id": "TINYINT",
        "team_mmr": "FLOAT",
        "enemy_mmr": "FLOAT",
        "kills_expected": "FLOAT",
        "kills_stddev": "FLOAT",
        "deaths_expected": "FLOAT",
        "deaths_stddev": "FLOAT",
        "assists_expected": "FLOAT",
        "assists_stddev": "FLOAT",
        "created_at": "TIMESTAMP",
    },
    "personal_score_awards": {
        "match_id": "VARCHAR",
        "xuid": "VARCHAR",
        "award_name": "VARCHAR",
        "award_category": "VARCHAR",
        "award_count": "INTEGER",
        "award_score": "INTEGER",
        "created_at": "TIMESTAMP",
    },
    "match_participants": {
        "match_id": "VARCHAR",
        "xuid": "VARCHAR",
        "team_id": "INTEGER",
        "outcome": "INTEGER",
        "gamertag": "VARCHAR",
        "rank": "SMALLINT",
        "score": "INTEGER",
        "kills": "SMALLINT",
        "deaths": "SMALLINT",
        "assists": "SMALLINT",
        "shots_fired": "INTEGER",
        "shots_hit": "INTEGER",
        "damage_dealt": "FLOAT",
        "damage_taken": "FLOAT",
    },
    "xuid_aliases": {
        "xuid": "VARCHAR",
        "gamertag": "VARCHAR",
        "last_seen": "TIMESTAMP",
        "source": "VARCHAR",
        "updated_at": "TIMESTAMP",
    },
    "killer_victim_pairs": {
        "id": "INTEGER",
        "match_id": "VARCHAR",
        "killer_xuid": "VARCHAR",
        "killer_gamertag": "VARCHAR",
        "victim_xuid": "VARCHAR",
        "victim_gamertag": "VARCHAR",
        "kill_count": "INTEGER",
        "time_ms": "INTEGER",
        "is_validated": "BOOLEAN",
        "created_at": "TIMESTAMP",
    },
    # v5 Shared Matches — match_registry
    "match_registry": {
        "match_id": "VARCHAR",
        "start_time": "TIMESTAMP",
        "end_time": "TIMESTAMP",
        "playlist_id": "VARCHAR",
        "playlist_name": "VARCHAR",
        "map_id": "VARCHAR",
        "map_name": "VARCHAR",
        "pair_id": "VARCHAR",
        "pair_name": "VARCHAR",
        "game_variant_id": "VARCHAR",
        "game_variant_name": "VARCHAR",
        "mode_category": "VARCHAR",
        "is_ranked": "BOOLEAN",
        "is_firefight": "BOOLEAN",
        "duration_seconds": "INTEGER",
        "team_0_score": "SMALLINT",
        "team_1_score": "SMALLINT",
        "backfill_completed": "INTEGER",
        "participants_loaded": "BOOLEAN",
        "events_loaded": "BOOLEAN",
        "medals_loaded": "BOOLEAN",
        "first_sync_by": "VARCHAR",
        "first_sync_at": "TIMESTAMP",
        "last_updated_at": "TIMESTAMP",
        "player_count": "SMALLINT",
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
    },
}

# Tables critiques pour l'audit de typage (Sprint 15.4)
CRITICAL_TABLES = ["match_stats", "match_participants", "highlight_events"]


# =============================================================================
# Fonctions de conversion de type Python
# =============================================================================


def _coerce_value(value: Any, duckdb_type: str) -> Any:
    """Convertit une valeur Python pour correspondre au type DuckDB attendu.

    Args:
        value: Valeur à convertir.
        duckdb_type: Type DuckDB cible (VARCHAR, FLOAT, INTEGER, etc.).

    Returns:
        Valeur convertie, ou None si conversion impossible.
    """
    if value is None:
        return None

    duckdb_type = duckdb_type.upper()

    try:
        if duckdb_type in ("VARCHAR", "TEXT"):
            s = str(value)
            return None if s in ("nan", "None", "") else s

        if duckdb_type in ("FLOAT", "DOUBLE", "REAL"):
            import math

            f = float(value)
            return None if (math.isnan(f) or math.isinf(f)) else f

        if duckdb_type in ("INTEGER", "INT", "BIGINT", "SMALLINT", "TINYINT"):
            import math

            f = float(value)
            if math.isnan(f) or math.isinf(f):
                return None
            return int(f)

        if duckdb_type == "BOOLEAN":
            if isinstance(value, bool):
                return value
            if isinstance(value, int | float):
                return bool(value)
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)

        if duckdb_type == "TIMESTAMP":
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                s = value.replace("Z", "+00:00")
                return datetime.fromisoformat(s)
            return value

    except (TypeError, ValueError, OverflowError):
        return None

    return value


def coerce_row_types(
    row_dict: dict[str, Any],
    table_name: str,
) -> dict[str, Any]:
    """Applique le plan de cast à un dictionnaire de row.

    Args:
        row_dict: Dictionnaire colonne→valeur.
        table_name: Nom de la table cible.

    Returns:
        Dictionnaire avec les types corrigés.
    """
    plan = CAST_PLAN.get(table_name, {})
    if not plan:
        return row_dict

    result = {}
    for col, val in row_dict.items():
        if col in plan:
            result[col] = _coerce_value(val, plan[col])
        else:
            result[col] = val

    return result


# =============================================================================
# Insertion batch — Sprint 15.1 + 15.2
# =============================================================================


def batch_insert_rows(
    conn: Any,
    table_name: str,
    rows: list[Any],
    columns: list[str],
    *,
    on_conflict: str = "",
    apply_cast: bool = True,
) -> int:
    """Insère des rows en batch via executemany.

    Remplace les boucles `for row in rows: conn.execute(INSERT ...)`.
    Applique le plan de cast si activé.

    Args:
        conn: Connexion DuckDB.
        table_name: Nom de la table.
        rows: Liste de dataclass ou dicts.
        columns: Liste des colonnes à insérer.
        on_conflict: Clause ON CONFLICT optionnelle (ex: "DO NOTHING").
        apply_cast: Si True, applique le CAST_PLAN aux valeurs.

    Returns:
        Nombre de rows insérées.
    """
    if not rows:
        return 0

    # Convertir les rows en tuples de valeurs
    values_list: list[tuple] = []
    for row in rows:
        if hasattr(row, "__dataclass_fields__"):
            row_dict = {f.name: getattr(row, f.name, None) for f in fields(row)}
        elif isinstance(row, dict):
            row_dict = row
        else:
            # Namedtuple ou objet avec attributs
            row_dict = {col: getattr(row, col, None) for col in columns}

        if apply_cast:
            row_dict = coerce_row_types(row_dict, table_name)

        values_list.append(tuple(row_dict.get(col) for col in columns))

    # Construire la requête
    placeholders = ", ".join(["?"] * len(columns))
    col_list = ", ".join(columns)
    sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"

    if on_conflict:
        sql += f" {on_conflict}"

    # Insertion batch
    inserted = 0
    try:
        conn.executemany(sql, values_list)
        inserted = len(values_list)
    except Exception as e:
        # Fallback : insertion row-by-row si le batch échoue
        # (ex: contrainte d'unicité sur certaines rows)
        logger.debug(f"Batch insert échoué pour {table_name}, fallback row-by-row: {e}")
        for values in values_list:
            try:
                conn.execute(sql, values)
                inserted += 1
            except Exception as row_err:
                logger.warning(f"Insert échoué {table_name}: {row_err}")

    return inserted


def batch_upsert_rows(
    conn: Any,
    table_name: str,
    rows: list[Any],
    columns: list[str],
    *,
    apply_cast: bool = True,
) -> int:
    """Upsert (INSERT OR REPLACE) des rows en batch.

    Args:
        conn: Connexion DuckDB.
        table_name: Nom de la table.
        rows: Liste de dataclass ou dicts.
        columns: Liste des colonnes à insérer.
        apply_cast: Si True, applique le CAST_PLAN aux valeurs.

    Returns:
        Nombre de rows upsertées.
    """
    if not rows:
        return 0

    # Convertir les rows en tuples de valeurs
    values_list: list[tuple] = []
    for row in rows:
        if hasattr(row, "__dataclass_fields__"):
            row_dict = {f.name: getattr(row, f.name, None) for f in fields(row)}
        elif isinstance(row, dict):
            row_dict = row
        else:
            row_dict = {col: getattr(row, col, None) for col in columns}

        if apply_cast:
            row_dict = coerce_row_types(row_dict, table_name)

        values_list.append(tuple(row_dict.get(col) for col in columns))

    # Construire la requête INSERT OR REPLACE
    placeholders = ", ".join(["?"] * len(columns))
    col_list = ", ".join(columns)
    sql = f"INSERT OR REPLACE INTO {table_name} ({col_list}) VALUES ({placeholders})"

    # Insertion batch
    inserted = 0
    try:
        conn.executemany(sql, values_list)
        inserted = len(values_list)
    except Exception as e:
        logger.debug(f"Batch upsert échoué pour {table_name}, fallback row-by-row: {e}")
        for values in values_list:
            try:
                conn.execute(sql, values)
                inserted += 1
            except Exception as row_err:
                logger.warning(f"Upsert échoué {table_name}: {row_err}")

    return inserted


# =============================================================================
# Colonnes par table (utilisées pour les insertions batch)
# =============================================================================

MEDAL_COLUMNS = ["match_id", "medal_name_id", "count"]

HIGHLIGHT_EVENT_COLUMNS = [
    "match_id",
    "event_type",
    "time_ms",
    "xuid",
    "gamertag",
    "type_hint",
    "raw_json",
]

SKILL_COLUMNS = [
    "match_id",
    "xuid",
    "team_id",
    "team_mmr",
    "enemy_mmr",
    "kills_expected",
    "kills_stddev",
    "deaths_expected",
    "deaths_stddev",
    "assists_expected",
    "assists_stddev",
    "created_at",
]

PERSONAL_SCORE_COLUMNS = [
    "match_id",
    "xuid",
    "award_name",
    "award_category",
    "award_count",
    "award_score",
    "created_at",
]

PARTICIPANT_COLUMNS = [
    "match_id",
    "xuid",
    "team_id",
    "outcome",
    "gamertag",
    "rank",
    "score",
    "kills",
    "deaths",
    "assists",
    "shots_fired",
    "shots_hit",
    "damage_dealt",
    "damage_taken",
]

ALIAS_COLUMNS = ["xuid", "gamertag", "last_seen", "source", "updated_at"]

# v5 Shared Matches — colonnes spécifiques
SHARED_MEDAL_COLUMNS = ["match_id", "xuid", "medal_name_id", "count"]

MATCH_STATS_COLUMNS = [
    "match_id",
    "start_time",
    "end_time",
    "playlist_id",
    "playlist_name",
    "map_id",
    "map_name",
    "pair_id",
    "pair_name",
    "game_variant_id",
    "game_variant_name",
    "outcome",
    "team_id",
    "kills",
    "deaths",
    "assists",
    "kda",
    "accuracy",
    "headshot_kills",
    "max_killing_spree",
    "time_played_seconds",
    "avg_life_seconds",
    "my_team_score",
    "enemy_team_score",
    "team_mmr",
    "enemy_mmr",
    "shots_fired",
    "shots_hit",
    "is_firefight",
    "teammates_signature",
    "updated_at",
]


# =============================================================================
# Audit de types — Sprint 15.4
# =============================================================================


def audit_column_types(
    conn: Any,
    table_name: str,
) -> list[dict[str, str]]:
    """Audite les incohérences de types entre le schéma réel et le CAST_PLAN.

    Args:
        conn: Connexion DuckDB.
        table_name: Nom de la table.

    Returns:
        Liste de dicts {column, expected_type, actual_type, status}.
    """
    expected_types = CAST_PLAN.get(table_name, {})
    if not expected_types:
        return []

    # Récupérer le schéma réel
    try:
        actual_cols = conn.execute(
            """SELECT column_name, data_type
               FROM information_schema.columns
               WHERE table_name = ?
               ORDER BY ordinal_position""",
            (table_name,),
        ).fetchall()
    except Exception:
        return []

    actual_map = {row[0]: row[1] for row in actual_cols}
    issues: list[dict[str, str]] = []

    # Normalisation des types pour comparaison
    type_aliases = {
        "TINYINT": {"TINYINT", "INT1"},
        "SMALLINT": {"SMALLINT", "INT2", "SHORT"},
        "INTEGER": {"INTEGER", "INT4", "INT", "SIGNED"},
        "BIGINT": {"BIGINT", "INT8", "LONG"},
        "FLOAT": {"FLOAT", "FLOAT4", "REAL"},
        "DOUBLE": {"DOUBLE", "FLOAT8"},
        "VARCHAR": {"VARCHAR", "TEXT", "STRING"},
        "BOOLEAN": {"BOOLEAN", "BOOL", "LOGICAL"},
        "TIMESTAMP": {"TIMESTAMP", "DATETIME", "TIMESTAMP WITH TIME ZONE"},
    }

    def _types_compatible(expected: str, actual: str) -> bool:
        """Vérifie si deux types sont compatibles."""
        expected_upper = expected.upper()
        actual_upper = actual.upper()
        if expected_upper == actual_upper:
            return True
        for _group_name, group in type_aliases.items():
            if expected_upper in group and actual_upper in group:
                return True
        # Les entiers plus larges sont acceptables
        int_order = ["TINYINT", "SMALLINT", "INTEGER", "BIGINT"]
        if expected_upper in int_order and actual_upper in int_order:
            return int_order.index(actual_upper) >= int_order.index(expected_upper)
        float_order = ["FLOAT", "DOUBLE"]
        if expected_upper in float_order and actual_upper in float_order:
            return float_order.index(actual_upper) >= float_order.index(expected_upper)
        return False

    for col, expected_type in expected_types.items():
        actual_type = actual_map.get(col)
        if actual_type is None:
            issues.append(
                {
                    "column": col,
                    "expected_type": expected_type,
                    "actual_type": "MISSING",
                    "status": "MISSING_COLUMN",
                }
            )
        elif not _types_compatible(expected_type, actual_type):
            issues.append(
                {
                    "column": col,
                    "expected_type": expected_type,
                    "actual_type": actual_type,
                    "status": "TYPE_MISMATCH",
                }
            )

    # Colonnes inattendues (dans la DB mais pas dans le CAST_PLAN)
    for col, actual_type in actual_map.items():
        if col not in expected_types:
            issues.append(
                {
                    "column": col,
                    "expected_type": "N/A",
                    "actual_type": actual_type,
                    "status": "EXTRA_COLUMN",
                }
            )

    return issues


def audit_all_tables(conn: Any) -> dict[str, list[dict[str, str]]]:
    """Audite toutes les tables connues dans le CAST_PLAN.

    Args:
        conn: Connexion DuckDB.

    Returns:
        Dict table_name → liste d'issues.
    """
    results: dict[str, list[dict[str, str]]] = {}
    for table_name in CAST_PLAN:
        issues = audit_column_types(conn, table_name)
        if issues:
            results[table_name] = issues
    return results
