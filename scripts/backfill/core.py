"""Fonctions d'insertion de base pour le backfill DuckDB.

Responsabilités :
- Insertion de médailles, events, skill, personal scores, aliases, participants
- Aucun commit : le commit est géré par l'orchestrateur
"""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Insertion helpers
# ─────────────────────────────────────────────────────────────────────────────


def insert_medal_rows(conn: Any, rows: list) -> int:
    """Insère les médailles dans la table medals_earned.

    Args:
        conn: Connexion DuckDB.
        rows: Liste de MedalRow.

    Returns:
        Nombre de médailles insérées.
    """
    if not rows:
        return 0

    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO medals_earned
                   (match_id, medal_name_id, count)
                   SELECT ?, CAST(? AS BIGINT), ?""",
                (row.match_id, row.medal_name_id, row.count),
            )
            inserted += 1
        except Exception as e:
            logger.warning(
                f"Erreur insertion médaille {row.medal_name_id} pour {row.match_id}: {e}"
            )

    return inserted


def insert_event_rows(conn: Any, rows: list) -> int:
    """Insère les highlight events.

    Args:
        conn: Connexion DuckDB.
        rows: Liste de HighlightEventRow.

    Returns:
        Nombre d'events insérés.
    """
    if not rows:
        return 0

    max_id_result = conn.execute("SELECT COALESCE(MAX(id), 0) FROM highlight_events").fetchone()
    next_id = (max_id_result[0] or 0) + 1

    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT INTO highlight_events
                   (id, match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    next_id,
                    row.match_id,
                    row.event_type,
                    row.time_ms,
                    row.xuid,
                    row.gamertag,
                    row.type_hint,
                    row.raw_json,
                ),
            )
            next_id += 1
            inserted += 1
        except Exception as e:
            logger.warning(f"Erreur insertion event pour {row.match_id}: {e}")

    return inserted


def insert_skill_row(conn: Any, row: Any, xuid: str) -> int:
    """Insère les stats skill/MMR.

    Args:
        conn: Connexion DuckDB.
        row: SkillStatsRow.
        xuid: XUID du joueur.

    Returns:
        1 si inséré, 0 sinon.
    """
    if not row:
        return 0

    try:
        conn.execute(
            """INSERT OR REPLACE INTO player_match_stats
               (match_id, xuid, team_id, team_mmr, enemy_mmr,
                kills_expected, kills_stddev,
                deaths_expected, deaths_stddev,
                assists_expected, assists_stddev)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row.match_id,
                xuid,
                row.team_id,
                row.team_mmr,
                row.enemy_mmr,
                row.kills_expected,
                row.kills_stddev,
                row.deaths_expected,
                row.deaths_stddev,
                row.assists_expected,
                row.assists_stddev,
            ),
        )
        return 1
    except Exception as e:
        logger.warning(f"Erreur insertion skill pour {row.match_id}: {e}")
        return 0


def insert_personal_score_rows(conn: Any, rows: list) -> int:
    """Insère les personal score awards.

    Args:
        conn: Connexion DuckDB.
        rows: Liste de PersonalScoreAwardRow.

    Returns:
        Nombre de scores insérés.
    """
    if not rows:
        return 0

    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT INTO personal_score_awards
                   (match_id, xuid, award_name, award_category,
                    award_count, award_score, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    row.match_id,
                    row.xuid,
                    row.award_name,
                    row.award_category,
                    row.award_count,
                    row.award_score,
                ),
            )
            inserted += 1
        except Exception as e:
            logger.warning(f"Erreur insertion personal_score pour {row.match_id}: {e}")

    return inserted


def insert_alias_rows(conn: Any, rows: list) -> int:
    """Insère les aliases XUID.

    Args:
        conn: Connexion DuckDB.
        rows: Liste de XuidAliasRow.

    Returns:
        Nombre d'aliases insérés.
    """
    if not rows:
        return 0

    now = datetime.now(timezone.utc)
    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO xuid_aliases
                   (xuid, gamertag, last_seen, source, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    row.xuid,
                    row.gamertag,
                    row.last_seen.isoformat() if row.last_seen else None,
                    row.source,
                    now.isoformat(),
                ),
            )
            inserted += 1
        except Exception as e:
            logger.warning(f"Erreur insertion alias {row.xuid}: {e}")

    return inserted


def insert_participant_rows(conn: Any, rows: list) -> int:
    """Insère les participants dans match_participants.

    Crée la table si elle n'existe pas et s'assure que les colonnes
    sont à jour via migrations.

    Args:
        conn: Connexion DuckDB.
        rows: Liste de ParticipantRow.

    Returns:
        Nombre de participants insérés.
    """
    if not rows:
        return 0

    from src.db.migrations import ensure_match_participants_columns

    conn.execute("""
        CREATE TABLE IF NOT EXISTS match_participants (
            match_id VARCHAR NOT NULL,
            xuid VARCHAR NOT NULL,
            team_id INTEGER,
            outcome INTEGER,
            gamertag VARCHAR,
            rank SMALLINT,
            score INTEGER,
            kills SMALLINT,
            deaths SMALLINT,
            assists SMALLINT,
            PRIMARY KEY (match_id, xuid)
        )
    """)
    ensure_match_participants_columns(conn)

    with contextlib.suppress(Exception):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_participants_xuid ON match_participants(xuid)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_participants_team ON match_participants(match_id, team_id)"
        )

    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO match_participants
                   (match_id, xuid, team_id, outcome, gamertag, rank, score,
                    kills, deaths, assists, shots_fired, shots_hit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row.match_id,
                    row.xuid,
                    row.team_id,
                    row.outcome,
                    row.gamertag,
                    row.rank,
                    row.score,
                    row.kills,
                    row.deaths,
                    row.assists,
                    getattr(row, "shots_fired", None),
                    getattr(row, "shots_hit", None),
                ),
            )
            inserted += 1
        except Exception as e:
            logger.warning(f"Erreur insertion participant {row.xuid} pour {row.match_id}: {e}")

    return inserted
