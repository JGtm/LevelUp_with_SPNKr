#!/usr/bin/env python3
"""Script de backfill pour remplir les données manquantes.

Ce script identifie les matchs existants qui ont des données manquantes
(medals, highlight_events, skill stats, personal_scores, performance_scores)
et les remplit en re-téléchargeant les données nécessaires depuis l'API SPNKr.

Usage:
    # Backfill toutes les données pour un joueur (inclut shots et participants-*)
    python scripts/backfill_data.py --player JGtm --all-data

    # Backfill uniquement les médailles
    python scripts/backfill_data.py --player JGtm --medals

    # Calculer les scores de performance manquants
    python scripts/backfill_data.py --player JGtm --performance-scores

    # Backfill la précision (accuracy) pour les matchs avec accuracy NULL
    python scripts/backfill_data.py --player JGtm --accuracy

    # Forcer la récupération de accuracy pour TOUS les matchs
    python scripts/backfill_data.py --player JGtm --accuracy --force-accuracy

    # Backfill shots_fired/shots_hit pour les matchs où ils sont NULL
    python scripts/backfill_data.py --player JGtm --shots

    # Forcer la mise à jour de shots_fired/shots_hit pour TOUS les matchs
    python scripts/backfill_data.py --player JGtm --shots --force-shots

    # Backfill enemy_mmr pour les matchs avec enemy_mmr NULL
    python scripts/backfill_data.py --player JGtm --enemy-mmr

    # Forcer la récupération de enemy_mmr pour TOUS les matchs
    python scripts/backfill_data.py --player JGtm --enemy-mmr --force-enemy-mmr

    # Récupérer les noms (playlist, map, pair) via Discovery UGC
    python scripts/backfill_data.py --player JGtm --assets

    # Forcer la ré-extraction des aliases (gamertags)
    python scripts/backfill_data.py --player JGtm --force-aliases

    # Backfill score et rang des participants (matchs où rank/score sont manquants)
    python scripts/backfill_data.py --player JGtm --participants-scores

    # Backfill kills, deaths, assists des participants (matchs où k/d/a sont manquants)
    python scripts/backfill_data.py --player JGtm --participants-kda

    # Backfill shots_fired/shots_hit des participants (matchs où shots manquants)
    python scripts/backfill_data.py --player JGtm --participants-shots

    # Forcer shots pour tous les participants de tous les matchs
    python scripts/backfill_data.py --player JGtm --participants-shots --force-participants-shots

    # Backfill paires killer/victim pour antagonistes
    python scripts/backfill_data.py --player JGtm --killer-victim

    # Remplir l'heure de fin des matchs (end_time = start_time + time_played_seconds)
    python scripts/backfill_data.py --player JGtm --end-time

    # Forcer le recalcul de end_time pour tous les matchs
    python scripts/backfill_data.py --player JGtm --end-time --force-end-time

    # Backfill session_id et session_label (matchs stables ≥ 4h)
    python scripts/backfill_data.py --player JGtm --sessions

    # Forcer le recalcul des sessions même si déjà remplies
    python scripts/backfill_data.py --player JGtm --sessions --force-sessions

    # Backfill pour tous les joueurs
    python scripts/backfill_data.py --all --all-data

    # Mode dry-run (liste seulement)
    python scripts/backfill_data.py --player JGtm --dry-run

    # Limiter le nombre de matchs
    python scripts/backfill_data.py --player JGtm --max-matches 100

Note: Pour combiner sync + backfill en une seule commande, utilisez :
    python scripts/sync.py --delta --player JGtm --with-backfill

Workaround OR — Exécution par étapes:
    La détection des matchs manquants combine les conditions avec OR.
    Avec --all-data, un match qui ne manque QUE les médailles sera sélectionné
    et retraité pour TOUS les types de données (shots, participants, etc.).
    Pour un backfill ciblé et plus rapide, exécuter par étapes :
        python scripts/backfill_data.py --player JGtm --medals
        python scripts/backfill_data.py --player JGtm --sessions
        python scripts/backfill_data.py --player JGtm --participants-kda
    Réserver --all-data pour le backfill initial ou un rattrapage complet.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys
from pathlib import Path
from typing import Any

# Ajouter le répertoire parent au path pour les imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.analysis.killer_victim import KVPair, compute_killer_victim_pairs
from src.data.sync.api_client import (
    SPNKrAPIClient,
    enrich_match_info_with_assets,
    get_tokens_from_env,
)
from src.data.sync.transformers import (
    extract_aliases,
    extract_medals,
    extract_participants,
    extract_personal_score_awards,
    extract_xuids_from_match,
    transform_highlight_events,
    transform_match_stats,
    transform_personal_score_awards,
    transform_skill_stats,
)
from src.db.parsers import resolve_xuid_from_db
from src.ui.multiplayer import list_duckdb_v4_players
from src.ui.sync import get_player_duckdb_path, is_duckdb_player

# Import pour le calcul des scores de performance
try:
    import polars as pl

    from src.analysis.performance_config import MIN_MATCHES_FOR_RELATIVE
    from src.analysis.performance_score import compute_relative_performance_score

    PERFORMANCE_SCORE_AVAILABLE = True
except ImportError:
    PERFORMANCE_SCORE_AVAILABLE = False
    pl = None
    compute_relative_performance_score = None
    MIN_MATCHES_FOR_RELATIVE = 10

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _insert_medal_rows(conn, rows: list) -> int:
    """Insère les médailles dans la table medals_earned."""
    if not rows:
        return 0

    inserted = 0
    for row in rows:
        try:
            # Utiliser une requête avec CAST dans une sous-requête pour forcer BIGINT
            # Cela évite les erreurs de conversion INT64 -> INT32
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


def _insert_event_rows(conn, rows: list) -> int:
    """Insère les highlight events."""
    if not rows:
        return 0

    # Récupérer le max id actuel pour auto-increment manuel
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


def _insert_skill_row(conn, row: Any, xuid: str) -> int:
    """Insère les stats skill/MMR."""
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


def _insert_personal_score_rows(conn, rows: list) -> int:
    """Insère les personal score awards."""
    if not rows:
        return 0

    inserted = 0
    for row in rows:
        try:
            # PersonalScoreAwardRow n'a pas d'attribut created_at, utiliser CURRENT_TIMESTAMP
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


def _insert_alias_rows(conn, rows: list) -> int:
    """Insère les aliases XUID (XuidAliasRow n'a pas updated_at, utiliser last_seen)."""
    if not rows:
        return 0

    from datetime import datetime, timezone

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


def _ensure_match_participants_columns(conn) -> None:
    """Ajoute rank, score, kills, deaths, assists à match_participants si absents (migration)."""
    try:
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = 'match_participants'"
        ).fetchall()
        col_names = {r[0] for r in cols} if cols else set()
        if "rank" not in col_names:
            conn.execute("ALTER TABLE match_participants ADD COLUMN rank SMALLINT")
        if "score" not in col_names:
            conn.execute("ALTER TABLE match_participants ADD COLUMN score INTEGER")
        if "kills" not in col_names:
            conn.execute("ALTER TABLE match_participants ADD COLUMN kills SMALLINT")
        if "deaths" not in col_names:
            conn.execute("ALTER TABLE match_participants ADD COLUMN deaths SMALLINT")
        if "assists" not in col_names:
            conn.execute("ALTER TABLE match_participants ADD COLUMN assists SMALLINT")
        if "shots_fired" not in col_names:
            conn.execute("ALTER TABLE match_participants ADD COLUMN shots_fired INTEGER")
        if "shots_hit" not in col_names:
            conn.execute("ALTER TABLE match_participants ADD COLUMN shots_hit INTEGER")
    except Exception as e:
        logger.debug(f"match_participants columns: {e}")


def _insert_participant_rows(conn, rows: list) -> int:
    """Insère les participants dans match_participants (roster + rank, score, k/d/a depuis API)."""
    if not rows:
        return 0

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
    _ensure_match_participants_columns(conn)
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_participants_xuid ON match_participants(xuid)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_participants_team ON match_participants(match_id, team_id)"
        )
    except Exception:
        pass

    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO match_participants
                   (match_id, xuid, team_id, outcome, gamertag, rank, score, kills, deaths, assists, shots_fired, shots_hit)
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


def _backfill_killer_victim_pairs(conn, me_xuid: str) -> int:
    """Extrait les paires killer/victim depuis highlight_events.

    Sprint Gamertag Roster Fix Phase 6 : Utilise l'algorithme de pairing
    de src/analysis/killer_victim.py pour apparier les events kill/death par timestamp.

    Args:
        conn: Connexion DuckDB.
        me_xuid: XUID du joueur principal (pour référence).

    Returns:
        Nombre de paires insérées.
    """
    # S'assurer que la table existe (sans id auto-increment pour DuckDB)
    # Drop et recreate pour être sûr de la structure
    conn.execute("DROP TABLE IF EXISTS killer_victim_pairs")
    conn.execute("""
        CREATE TABLE killer_victim_pairs (
            match_id VARCHAR NOT NULL,
            killer_xuid VARCHAR NOT NULL,
            killer_gamertag VARCHAR,
            victim_xuid VARCHAR NOT NULL,
            victim_gamertag VARCHAR,
            kill_count INTEGER DEFAULT 1,
            time_ms INTEGER,
            is_validated BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.info("Table killer_victim_pairs (re)créée")
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kv_match ON killer_victim_pairs(match_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kv_killer ON killer_victim_pairs(killer_xuid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kv_victim ON killer_victim_pairs(victim_xuid)")
    except Exception:
        pass

    # Charger tous les matchs avec highlight events de type kill/death
    # Note: LOWER() pour comparaison insensible à la casse
    try:
        matches = conn.execute("""
            SELECT DISTINCT match_id
            FROM highlight_events
            WHERE LOWER(event_type) IN ('kill', 'death')
        """).fetchall()
    except Exception as e:
        logger.warning(f"Erreur lecture highlight_events: {e}")
        return 0

    if not matches:
        logger.info("Aucun match avec highlight events kill/death trouvé")
        return 0

    logger.info(f"Trouvé {len(matches)} matchs avec highlight events kill/death")
    total_pairs = 0
    skipped_no_pairs = 0
    logged_debug = False

    for (match_id,) in matches:
        # Charger les events du match
        try:
            events = conn.execute(
                """
                SELECT event_type, time_ms, xuid, gamertag
                FROM highlight_events
                WHERE match_id = ?
                  AND LOWER(event_type) IN ('kill', 'death')
                ORDER BY time_ms
            """,
                [match_id],
            ).fetchall()
        except Exception:
            continue

        if not events:
            continue

        # Convertir en dicts pour l'algorithme
        event_dicts = [
            {
                "event_type": row[0],
                "time_ms": row[1],
                "xuid": row[2],
                "gamertag": row[3],
            }
            for row in events
        ]

        # Debug: compter les types d'events
        kills_count = sum(
            1 for e in event_dicts if str(e.get("event_type") or "").lower() == "kill"
        )
        deaths_count = sum(
            1 for e in event_dicts if str(e.get("event_type") or "").lower() == "death"
        )
        time_ms_null = sum(1 for e in event_dicts if e.get("time_ms") is None)

        # Log premier match nouveau traité pour debug
        is_first_match = not logged_debug
        if is_first_match:
            logged_debug = True
            sample_types = {str(e.get("event_type")) for e in event_dicts[:10]}
            logger.info(f"  [DEBUG] Sample event_types: {sample_types}")
            logger.info(
                f"  [DEBUG] Match {match_id[:20]}...: {len(events)} events, {kills_count} kills, {deaths_count} deaths, {time_ms_null} sans time_ms"
            )

        if kills_count == 0 or deaths_count == 0:
            skipped_no_pairs += 1
            continue

        # Calculer les paires avec l'algorithme validé
        pairs: list[KVPair] = compute_killer_victim_pairs(event_dicts, tolerance_ms=5)

        # Debug: log le nombre de paires calculées pour le premier match
        if is_first_match:
            logger.info(f"  [DEBUG] Paires calculées: {len(pairs)}")
            if pairs:
                logger.info(
                    f"  [DEBUG] Première paire: killer={pairs[0].killer_xuid}, victim={pairs[0].victim_xuid}, time={pairs[0].time_ms}"
                )

        if not pairs:
            skipped_no_pairs += 1
            continue

        # Insérer les paires
        insert_errors = 0
        for p in pairs:
            try:
                conn.execute(
                    """
                    INSERT INTO killer_victim_pairs
                    (match_id, killer_xuid, killer_gamertag, victim_xuid, victim_gamertag, kill_count, time_ms)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                    [
                        match_id,
                        p.killer_xuid,
                        p.killer_gamertag,
                        p.victim_xuid,
                        p.victim_gamertag,
                        p.time_ms,
                    ],
                )
                total_pairs += 1
            except Exception as e:
                insert_errors += 1
                if insert_errors == 1:
                    logger.warning(f"  Erreur INSERT: {e}")

        if insert_errors > 0 and not logged_debug:
            logger.info(f"  [DEBUG] {insert_errors} erreurs d'insertion sur {len(pairs)} paires")

    if skipped_no_pairs > 0:
        logger.info(
            f"  Matchs skippés (pas de kills/deaths ou algorithme vide): {skipped_no_pairs}"
        )

    return total_pairs


def _ensure_end_time_column(conn) -> None:
    """S'assure que la colonne end_time existe dans match_stats."""
    try:
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'match_stats'
              AND column_name = 'end_time'
            """
        ).fetchone()
        if result and result[0] == 0:
            logger.info("Ajout de la colonne end_time à match_stats")
            conn.execute("ALTER TABLE match_stats ADD COLUMN end_time TIMESTAMP")
            conn.commit()
    except Exception as e:
        logger.warning(f"Note lors de la vérification de end_time: {e}")


def _backfill_end_time(conn, force: bool = False) -> int:
    """Met à jour end_time (start_time + time_played_seconds) pour les matchs concernés.

    Returns:
        Nombre de lignes mises à jour.
    """
    _ensure_end_time_column(conn)
    try:
        # DuckDB: start_time + (time_played_seconds * INTERVAL '1 SECOND')
        where_clause = (
            "WHERE start_time IS NOT NULL AND time_played_seconds IS NOT NULL"
            if force
            else """WHERE end_time IS NULL
                  AND start_time IS NOT NULL
                  AND time_played_seconds IS NOT NULL"""
        )
        cursor = conn.execute(
            f"""
            UPDATE match_stats
            SET end_time = start_time + (time_played_seconds * INTERVAL '1 SECOND')
            {where_clause}
            RETURNING match_id
            """
        )
        updated = cursor.fetchall()
        conn.commit()
        return len(updated)
    except Exception as e:
        logger.warning(f"Erreur backfill end_time: {e}")
        return 0


def _ensure_performance_score_column(conn) -> None:
    """S'assure que la colonne performance_score existe dans match_stats."""
    try:
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'match_stats'
              AND column_name = 'performance_score'
            """
        ).fetchone()

        if result and result[0] == 0:
            # Colonne n'existe pas, l'ajouter
            logger.info("Ajout de la colonne performance_score à match_stats")
            conn.execute("ALTER TABLE match_stats ADD COLUMN performance_score FLOAT")
            conn.commit()
    except Exception as e:
        logger.warning(f"Note lors de la vérification de performance_score: {e}")


def _compute_performance_score_for_match(conn, match_id: str) -> bool:
    """Calcule et met à jour le score de performance pour un match.

    Returns:
        True si le score a été calculé, False sinon.
    """
    if not PERFORMANCE_SCORE_AVAILABLE:
        return False

    try:
        # S'assurer que la colonne existe
        _ensure_performance_score_column(conn)

        # Vérifier si le score existe déjà
        existing = conn.execute(
            "SELECT performance_score FROM match_stats WHERE match_id = ?",
            (match_id,),
        ).fetchone()

        if existing and existing[0] is not None:
            # Score déjà calculé
            return False

        # Récupérer les données du match actuel
        match_data = conn.execute(
            """
            SELECT match_id, start_time, kills, deaths, assists, kda, accuracy,
                   time_played_seconds, avg_life_seconds
            FROM match_stats
            WHERE match_id = ?
            """,
            (match_id,),
        ).fetchone()

        if not match_data:
            return False

        match_start_time = match_data[1]  # start_time
        if match_start_time is None:
            return False

        # Charger l'historique (tous les matchs AVANT celui-ci)
        # Utiliser .pl() pour obtenir directement un DataFrame Polars
        try:
            history_df = conn.execute(
                """
                SELECT
                    match_id, start_time, kills, deaths, assists, kda, accuracy,
                    time_played_seconds, avg_life_seconds
                FROM match_stats
                WHERE match_id != ?
                  AND start_time IS NOT NULL
                  AND start_time < ?
                ORDER BY start_time ASC
                """,
                (match_id, match_start_time),
            ).pl()
        except Exception as e:
            logger.warning(f"Erreur chargement historique pour {match_id}: {e}")
            return False

        # Vérifier si assez de données
        if history_df.is_empty() or len(history_df) < MIN_MATCHES_FOR_RELATIVE:
            return False

        # Convertir match_data en dict pour compute_relative_performance_score
        match_dict = {
            "kills": match_data[2] or 0,
            "deaths": match_data[3] or 0,
            "assists": match_data[4] or 0,
            "kda": match_data[5],
            "accuracy": match_data[6],
            "time_played_seconds": match_data[7] or 600.0,
        }

        # Calculer le score (accepte dict + Polars DataFrame)
        score = compute_relative_performance_score(match_dict, history_df)

        if score is not None:
            conn.execute(
                "UPDATE match_stats SET performance_score = ? WHERE match_id = ?",
                (score, match_id),
            )
            conn.commit()
            return True

        return False

    except Exception as e:
        logger.warning(f"Erreur calcul score performance pour {match_id}: {e}")
        return False


def _find_matches_missing_data(
    conn,
    xuid: str,
    *,
    medals: bool = False,
    events: bool = False,
    skill: bool = False,
    personal_scores: bool = False,
    performance_scores: bool = False,
    accuracy: bool = False,
    enemy_mmr: bool = False,
    assets: bool = False,
    participants: bool = False,
    participants_scores: bool = False,
    participants_kda: bool = False,
    participants_shots: bool = False,
    force_participants_shots: bool = False,
    force_medals: bool = False,
    force_accuracy: bool = False,
    shots: bool = False,
    force_shots: bool = False,
    force_enemy_mmr: bool = False,
    force_aliases: bool = False,
    force_assets: bool = False,
    force_participants: bool = False,
    max_matches: int | None = None,
    all_data: bool = False,
) -> list[str]:
    """Trouve les matchs avec des données manquantes."""
    conditions = []
    params = []

    # Détecter si on utilise --all-data (beaucoup d'options activées)
    # Pour éviter de retraiter les matchs déjà complets, on exclut ceux qui ont
    # déjà toutes les données principales ET qui sont parmi les plus récents
    # (car les matchs récents sont plus susceptibles d'avoir été traités récemment)
    exclude_complete_matches = (
        all_data
        and medals
        and events
        and skill
        and personal_scores
        and participants
        and not force_medals
        and not force_participants
    )

    if medals:
        if force_medals:
            # Mode force: inclure TOUS les matchs pour réinsérer les médailles
            conditions.append("1=1")  # Condition toujours vraie = tous les matchs
        else:
            # Détecter les matchs sans médailles
            # Note: INSERT OR REPLACE remplacera les médailles existantes si elles sont déjà présentes
            # donc même si certaines médailles ont échoué précédemment, elles seront réinsérées
            conditions.append("""
                ms.match_id NOT IN (
                    SELECT DISTINCT match_id FROM medals_earned
                )
            """)

    if events:
        conditions.append("""
            ms.match_id NOT IN (
                SELECT DISTINCT match_id FROM highlight_events
            )
        """)

    if skill:
        conditions.append("""
            ms.match_id NOT IN (
                SELECT DISTINCT match_id FROM player_match_stats WHERE xuid = ?
            )
        """)
        params.append(xuid)

    if personal_scores:
        conditions.append("""
            ms.match_id NOT IN (
                SELECT DISTINCT match_id FROM personal_score_awards WHERE xuid = ?
            )
        """)
        params.append(xuid)

    if performance_scores:
        # Vérifier si la colonne performance_score existe
        try:
            col_check = conn.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = 'match_stats'
                  AND column_name = 'performance_score'
                """
            ).fetchone()

            if col_check and col_check[0] > 0:
                # Colonne existe, trouver les matchs sans score
                conditions.append("""
                    ms.match_id IN (
                        SELECT match_id FROM match_stats
                        WHERE performance_score IS NULL
                    )
                """)
            # Colonne n'existe pas encore, tous les matchs sont concernés
            else:
                conditions.append("1=1")
        except Exception:
            # En cas d'erreur, considérer que tous les matchs sont concernés
            conditions.append("1=1")

    if accuracy:
        if force_accuracy:
            # Mode force: inclure TOUS les matchs pour forcer la mise à jour de accuracy
            # Mais seulement si accuracy est activé
            conditions.append("1=1")  # Condition toujours vraie = tous les matchs
        else:
            # Détecter les matchs avec accuracy NULL
            conditions.append("ms.accuracy IS NULL")

    if shots:
        if force_shots:
            conditions.append("1=1")  # Tous les matchs pour forcer shots_fired/shots_hit
        else:
            conditions.append("(ms.shots_fired IS NULL OR ms.shots_hit IS NULL)")

    if enemy_mmr:
        if force_enemy_mmr:
            # Mode force: inclure TOUS les matchs pour forcer la mise à jour de enemy_mmr
            conditions.append("1=1")  # Condition toujours vraie = tous les matchs
        else:
            # Détecter les matchs avec enemy_mmr NULL dans player_match_stats
            conditions.append("""
                ms.match_id IN (
                    SELECT match_id FROM player_match_stats
                    WHERE xuid = ? AND enemy_mmr IS NULL
                )
            """)
            params.append(xuid)

    if assets:
        if force_assets:
            conditions.append("1=1")
        else:
            # Matchs où les "noms" sont en fait des UUID (fallback du sync)
            # Quand le nom manque, transform_match_stats stocke l'ID dans la colonne name
            conditions.append("""
                ms.playlist_name IS NULL OR ms.playlist_name = ms.playlist_id
                OR ms.map_name IS NULL OR ms.map_name = ms.map_id
                OR ms.pair_name IS NULL OR ms.pair_name = ms.pair_id
                OR ms.game_variant_name IS NULL OR ms.game_variant_name = ms.game_variant_id
            """)

    if force_aliases:
        # Inclure tous les matchs pour ré-extraire les aliases (encodage corrigé)
        conditions.append("1=1")

    if participants:
        if force_participants:
            # Mode force: inclure TOUS les matchs pour réinsérer les participants
            conditions.append("1=1")
        else:
            # Vérifier si la table match_participants existe
            try:
                table_exists = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'main' AND table_name = 'match_participants'
                    """
                ).fetchone()
                if table_exists and table_exists[0] > 0:
                    # Table existe, trouver les matchs sans participants
                    conditions.append("""
                        ms.match_id NOT IN (
                            SELECT DISTINCT match_id FROM match_participants
                        )
                    """)
                else:
                    # Table n'existe pas, tous les matchs sont concernés
                    conditions.append("1=1")
            except Exception:
                # En cas d'erreur, considérer que tous les matchs sont concernés
                conditions.append("1=1")

    if participants_scores:
        # Matchs où des participants existent mais rank ou score manquant
        try:
            table_ok = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_name = 'match_participants'"
            ).fetchone()
            rank_ok = conn.execute(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = 'main' AND table_name = 'match_participants' AND column_name = 'rank'"
            ).fetchone()
            if table_ok and table_ok[0] and rank_ok and rank_ok[0]:
                conditions.append("""
                    ms.match_id IN (
                        SELECT match_id FROM match_participants
                        WHERE rank IS NULL OR score IS NULL
                    )
                """)
        except Exception:
            pass

    if participants_kda:
        # Matchs où des participants existent mais kills/deaths/assists manquants
        try:
            table_ok = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_name = 'match_participants'"
            ).fetchone()
            k_ok = conn.execute(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = 'main' AND table_name = 'match_participants' AND column_name = 'kills'"
            ).fetchone()
            if table_ok and table_ok[0] and k_ok and k_ok[0]:
                conditions.append("""
                    ms.match_id IN (
                        SELECT match_id FROM match_participants
                        WHERE kills IS NULL OR deaths IS NULL OR assists IS NULL
                    )
                """)
        except Exception:
            pass

    if participants_shots:
        if force_participants_shots:
            conditions.append("1=1")  # Tous les matchs pour forcer shots des participants
        else:
            try:
                table_ok = conn.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = 'main' AND table_name = 'match_participants'"
                ).fetchone()
                shots_ok = conn.execute(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = 'main' AND table_name = 'match_participants' AND column_name = 'shots_fired'"
                ).fetchone()
                if table_ok and table_ok[0] and shots_ok and shots_ok[0]:
                    conditions.append("""
                        ms.match_id IN (
                            SELECT match_id FROM match_participants
                            WHERE shots_fired IS NULL OR shots_hit IS NULL
                        )
                    """)
                else:
                    conditions.append("1=1")
            except Exception:
                conditions.append("1=1")

    if not conditions:
        return []

    where_clause = " OR ".join(conditions)

    # Si on utilise --all-data, exclure les matchs qui ont déjà toutes les données principales
    # ET qui sont parmi les plus récents (car ils sont plus susceptibles d'avoir été traités récemment)
    # Cela évite de retraiter les matchs déjà complets lors d'un relancement
    exclude_clause = ""
    if exclude_complete_matches:
        # Exclure les matchs qui ont toutes les données principales ET qui sont parmi les 500 plus récents
        # (les matchs récents sont plus susceptibles d'avoir été traités récemment avec --all-data)
        exclude_clause = """
            AND ms.match_id NOT IN (
                SELECT DISTINCT ms2.match_id
                FROM match_stats ms2
                WHERE ms2.match_id IN (SELECT DISTINCT match_id FROM medals_earned)
                  AND ms2.match_id IN (SELECT DISTINCT match_id FROM highlight_events)
                  AND ms2.match_id IN (SELECT DISTINCT match_id FROM player_match_stats WHERE xuid = ?)
                  AND ms2.match_id IN (SELECT DISTINCT match_id FROM personal_score_awards WHERE xuid = ?)
                  AND ms2.match_id IN (SELECT DISTINCT match_id FROM match_participants)
                  AND ms2.match_id IN (
                      SELECT match_id FROM match_stats
                      ORDER BY start_time DESC
                      LIMIT 500
                  )
            )
        """
        params.append(xuid)
        params.append(xuid)

    query = f"""
        SELECT DISTINCT ms.match_id
        FROM match_stats ms
        WHERE ({where_clause}){exclude_clause}
        ORDER BY ms.start_time DESC
    """

    if max_matches:
        query += f" LIMIT {max_matches}"

    result = conn.execute(query, params).fetchall() if params else conn.execute(query).fetchall()

    return [row[0] for row in result]


async def backfill_player_data(
    gamertag: str,
    *,
    dry_run: bool = False,
    max_matches: int | None = None,
    requests_per_second: int = 5,
    medals: bool = False,
    events: bool = False,
    skill: bool = False,
    personal_scores: bool = False,
    performance_scores: bool = False,
    aliases: bool = False,
    accuracy: bool = False,
    enemy_mmr: bool = False,
    assets: bool = False,
    participants: bool = False,
    participants_scores: bool = False,
    participants_kda: bool = False,
    participants_shots: bool = False,
    killer_victim: bool = False,
    end_time: bool = False,
    sessions: bool = False,
    all_data: bool = False,
    force_medals: bool = False,
    force_accuracy: bool = False,
    shots: bool = False,
    force_shots: bool = False,
    force_participants_shots: bool = False,
    force_enemy_mmr: bool = False,
    force_aliases: bool = False,
    force_assets: bool = False,
    force_participants: bool = False,
    force_end_time: bool = False,
    force_sessions: bool = False,
) -> dict[str, int]:
    """Remplit les données manquantes pour un joueur.

    Args:
        gamertag: Gamertag du joueur.
        dry_run: Si True, ne fait que lister les matchs sans données.
        max_matches: Nombre maximum de matchs à traiter (None = tous).
        requests_per_second: Rate limiting API.
        medals: Backfill les médailles.
        events: Backfill les highlight events.
        skill: Backfill les stats skill/MMR.
        personal_scores: Backfill les personal score awards.
        aliases: Mettre à jour les aliases.
        all_data: Backfill toutes les données (inclut shots et participants-*).

    Returns:
        Dict avec les statistiques.
    """
    # Si all_data, activer toutes les options
    if all_data:
        medals = True
        events = True
        skill = True
        personal_scores = True
        performance_scores = True
        aliases = True
        accuracy = True
        enemy_mmr = True
        assets = True
        participants = True
        shots = True  # shots_fired/shots_hit pour le joueur principal
        participants_scores = True  # rank et score des participants
        participants_kda = True  # kills, deaths, assists des participants
        participants_shots = True  # shots_fired/shots_hit des participants
        killer_victim = True
        end_time = True
        sessions = True

    # Si force_accuracy est activé sans accuracy, l'activer automatiquement
    if force_accuracy and not accuracy:
        accuracy = True

    # Si force_shots est activé sans shots, l'activer automatiquement
    if force_shots and not shots:
        shots = True

    # Si force_enemy_mmr est activé sans enemy_mmr, l'activer automatiquement
    if force_enemy_mmr and not enemy_mmr:
        enemy_mmr = True

    if force_aliases and not aliases:
        aliases = True

    if force_assets and not assets:
        assets = True

    if force_participants and not participants:
        participants = True

    if force_end_time and not end_time:
        end_time = True

    if force_sessions and not sessions:
        sessions = True

    if force_participants_shots and not participants_shots:
        participants_shots = True

    # Vérifier qu'au moins une option est activée
    if not any(
        [
            medals,
            events,
            skill,
            personal_scores,
            performance_scores,
            aliases,
            accuracy,
            shots,
            enemy_mmr,
            assets,
            participants,
            participants_scores,
            participants_kda,
            participants_shots,
            killer_victim,
            end_time,
            sessions,
            force_aliases,
        ]
    ):
        logger.warning(
            "Aucune option de backfill activée. Utilisez --all ou spécifiez des options."
        )
        return {
            "matches_checked": 0,
            "matches_missing_data": 0,
            "medals_inserted": 0,
            "events_inserted": 0,
            "skill_inserted": 0,
            "personal_scores_inserted": 0,
            "performance_scores_inserted": 0,
            "aliases_inserted": 0,
            "accuracy_updated": 0,
            "shots_updated": 0,
            "enemy_mmr_updated": 0,
            "assets_updated": 0,
            "participants_inserted": 0,
            "participants_scores_updated": 0,
            "participants_kda_updated": 0,
            "participants_shots_updated": 0,
            "killer_victim_pairs_inserted": 0,
            "end_time_updated": 0,
            "sessions_updated": 0,
        }

    # Vérifier que c'est un joueur DuckDB v4
    if not is_duckdb_player(gamertag):
        logger.error(
            f"{gamertag} n'a pas de DB DuckDB v4. Ce script ne fonctionne que pour DuckDB v4."
        )
        return {
            "matches_checked": 0,
            "matches_missing_data": 0,
            "medals_inserted": 0,
            "events_inserted": 0,
            "skill_inserted": 0,
            "personal_scores_inserted": 0,
            "performance_scores_inserted": 0,
            "aliases_inserted": 0,
            "accuracy_updated": 0,
            "shots_updated": 0,
            "enemy_mmr_updated": 0,
            "assets_updated": 0,
            "participants_inserted": 0,
            "participants_scores_updated": 0,
            "participants_kda_updated": 0,
            "killer_victim_pairs_inserted": 0,
            "end_time_updated": 0,
            "sessions_updated": 0,
        }

    # Obtenir le chemin de la DB
    db_path = get_player_duckdb_path(gamertag)
    if not db_path or not db_path.exists():
        logger.error(f"DB DuckDB introuvable pour {gamertag}")
        return {
            "matches_checked": 0,
            "matches_missing_data": 0,
            "medals_inserted": 0,
            "events_inserted": 0,
            "skill_inserted": 0,
            "personal_scores_inserted": 0,
            "performance_scores_inserted": 0,
            "aliases_inserted": 0,
            "accuracy_updated": 0,
            "shots_updated": 0,
            "enemy_mmr_updated": 0,
            "assets_updated": 0,
            "participants_inserted": 0,
            "participants_scores_updated": 0,
            "participants_kda_updated": 0,
            "killer_victim_pairs_inserted": 0,
        }

    # Obtenir le XUID depuis la DB
    import duckdb

    # Résoudre le XUID depuis le gamertag
    xuid = resolve_xuid_from_db(str(db_path), gamertag)

    if not xuid:
        logger.warning(f"XUID introuvable dans xuid_aliases pour {gamertag}")
        logger.info("Tentative d'extraction depuis les matchs existants...")

        # Fallback : essayer d'extraire depuis highlight_events
        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            # Essayer depuis highlight_events (contient gamertag + xuid)
            result = conn.execute(
                """
                SELECT DISTINCT xuid
                FROM highlight_events
                WHERE LOWER(gamertag) = LOWER(?)
                  AND xuid IS NOT NULL
                  AND xuid != ''
                LIMIT 1
                """,
                [gamertag],
            ).fetchone()

            if result and result[0]:
                xuid = str(result[0])
                logger.info(f"✅ XUID trouvé depuis highlight_events: {xuid}")
            else:
                logger.error(f"❌ Impossible de résoudre le XUID pour {gamertag}")
                logger.error("")
                logger.error(
                    "La table xuid_aliases est vide et aucun match avec highlight_events trouvé."
                )
                logger.error("")
                logger.error(
                    "💡 Solution: Faites une synchronisation complète pour remplir xuid_aliases:"
                )
                logger.error(f"   python scripts/sync.py --gamertag {gamertag} --delta")
                logger.error("")
                return {
                    "matches_checked": 0,
                    "matches_missing_data": 0,
                    "medals_inserted": 0,
                    "events_inserted": 0,
                    "skill_inserted": 0,
                    "personal_scores_inserted": 0,
                    "aliases_inserted": 0,
                    "accuracy_updated": 0,
                    "shots_updated": 0,
                    "enemy_mmr_updated": 0,
                    "assets_updated": 0,
                    "participants_inserted": 0,
                    "participants_scores_updated": 0,
                    "participants_kda_updated": 0,
                    "killer_victim_pairs_inserted": 0,
                    "end_time_updated": 0,
                    "sessions_updated": 0,
                }
        finally:
            conn.close()
    else:
        logger.info(f"✅ XUID résolu depuis xuid_aliases: {xuid}")

    # Ouvrir la connexion en écriture pour les insertions
    conn = duckdb.connect(str(db_path), read_only=False)

    try:
        # Modifier le schéma de medals_earned si nécessaire
        # Certaines medal_name_id dépassent INT32, il faut utiliser BIGINT
        # DuckDB ne supporte pas ALTER COLUMN TYPE, il faut recréer la table
        try:
            # Vérifier si la table existe
            table_exists = (
                conn.execute(
                    """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_name = 'medals_earned'
                """
                ).fetchone()[0]
                > 0
            )

            if table_exists:
                # Vérifier le type actuel de la colonne
                col_info = conn.execute(
                    """
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_name = 'medals_earned'
                      AND column_name = 'medal_name_id'
                    """
                ).fetchone()

                if col_info and col_info[0] in ("INTEGER", "INT32"):
                    logger.info("Migration du schéma medals_earned: INTEGER -> BIGINT...")
                    # Recréer la table avec BIGINT
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS medals_earned_new (
                            match_id VARCHAR,
                            medal_name_id BIGINT,
                            count SMALLINT,
                            PRIMARY KEY (match_id, medal_name_id)
                        )
                    """)
                    # Copier les données existantes
                    conn.execute("""
                        INSERT INTO medals_earned_new
                        SELECT match_id, CAST(medal_name_id AS BIGINT), count
                        FROM medals_earned
                    """)
                    # Remplacer l'ancienne table
                    conn.execute("DROP TABLE medals_earned")
                    conn.execute("ALTER TABLE medals_earned_new RENAME TO medals_earned")
                    logger.info("✅ Schéma medals_earned migré vers BIGINT")
                else:
                    logger.debug(
                        f"Type de colonne déjà correct: {col_info[0] if col_info else 'N/A'}"
                    )
            else:
                # Table n'existe pas encore, créer avec le bon type directement
                logger.debug("Table medals_earned n'existe pas encore, sera créée avec BIGINT")
        except Exception as e:
            # Si la migration échoue, continuer quand même
            logger.warning(f"Note: Migration du schéma échouée (continuation): {e}")

        # S'assurer que la colonne accuracy existe si nécessaire
        if accuracy:
            try:
                col_check = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.columns
                    WHERE table_name = 'match_stats'
                      AND column_name = 'accuracy'
                    """
                ).fetchone()

                if not col_check or col_check[0] == 0:
                    logger.info("Ajout de la colonne accuracy à match_stats")
                    conn.execute("ALTER TABLE match_stats ADD COLUMN accuracy FLOAT")
                    conn.commit()
            except Exception as e:
                logger.warning(f"Note lors de la vérification de accuracy: {e}")

        # Pour participants_scores / participants_kda / participants_shots, s'assurer que les colonnes existent
        # avant de chercher les matchs (sinon la requête ne trouve rien)
        if participants_scores or participants_kda or participants_shots:
            with contextlib.suppress(Exception):
                _ensure_match_participants_columns(conn)

        # Trouver les matchs avec données manquantes
        match_ids = _find_matches_missing_data(
            conn,
            xuid,
            medals=medals,
            events=events,
            skill=skill,
            personal_scores=personal_scores,
            performance_scores=performance_scores,
            accuracy=accuracy,
            enemy_mmr=enemy_mmr,
            assets=assets,
            participants=participants,
            participants_scores=participants_scores,
            participants_kda=participants_kda,
            participants_shots=participants_shots,
            force_participants_shots=force_participants_shots,
            force_medals=force_medals,
            force_accuracy=force_accuracy,
            shots=shots,
            force_shots=force_shots,
            force_enemy_mmr=force_enemy_mmr,
            force_aliases=force_aliases,
            force_assets=force_assets,
            force_participants=force_participants,
            max_matches=max_matches,
            all_data=all_data,
        )

        logger.info(f"Matchs trouvés avec données manquantes: {len(match_ids)}")

        if dry_run:
            logger.info("Mode dry-run: aucun traitement effectué")
            return {
                "matches_checked": len(match_ids),
                "matches_missing_data": len(match_ids),
                "medals_inserted": 0,
                "events_inserted": 0,
                "skill_inserted": 0,
                "personal_scores_inserted": 0,
                "performance_scores_inserted": 0,
                "aliases_inserted": 0,
                "accuracy_updated": 0,
                "shots_updated": 0,
                "enemy_mmr_updated": 0,
                "assets_updated": 0,
                "participants_inserted": 0,
                "participants_scores_updated": 0,
                "participants_kda_updated": 0,
                "participants_shots_updated": 0,
                "killer_victim_pairs_inserted": 0,
                "end_time_updated": 0,
                "sessions_updated": 0,
            }

        if (
            not match_ids
            and not killer_victim
            and not end_time
            and not sessions
            and not participants_scores
            and not participants_kda
            and not participants_shots
        ):
            # Pas de matchs à traiter ET pas de killer_victim ni end_time à backfill
            logger.info("Tous les matchs ont déjà toutes les données demandées")
            return {
                "matches_checked": 0,
                "matches_missing_data": 0,
                "medals_inserted": 0,
                "events_inserted": 0,
                "skill_inserted": 0,
                "personal_scores_inserted": 0,
                "performance_scores_inserted": 0,
                "aliases_inserted": 0,
                "accuracy_updated": 0,
                "shots_updated": 0,
                "enemy_mmr_updated": 0,
                "assets_updated": 0,
                "participants_inserted": 0,
                "participants_scores_updated": 0,
                "participants_kda_updated": 0,
                "participants_shots_updated": 0,
                "killer_victim_pairs_inserted": 0,
                "end_time_updated": 0,
                "sessions_updated": 0,
            }
        elif not match_ids and (killer_victim or end_time or sessions):
            # Pas de matchs à traiter via API mais killer_victim et/ou end_time à backfill
            logger.info("Pas de données de match à backfill via API...")
            total_killer_victim_pairs = 0
            total_end_time_updated = 0
            if killer_victim:
                logger.info("Backfill des paires killer/victim depuis highlight_events...")
                total_killer_victim_pairs = _backfill_killer_victim_pairs(conn, xuid)
                if total_killer_victim_pairs > 0:
                    logger.info(f"✅ {total_killer_victim_pairs} paires killer/victim insérées")
                else:
                    logger.info("Aucune nouvelle paire killer/victim à insérer")
            if end_time:
                logger.info("Backfill de l'heure de fin des matchs (end_time)...")
                total_end_time_updated = _backfill_end_time(conn, force=force_end_time)
                if total_end_time_updated > 0:
                    logger.info(f"✅ {total_end_time_updated} match(s) avec end_time mis à jour")
                else:
                    logger.info("Aucun match à mettre à jour pour end_time")

            total_sessions_updated = 0
            if sessions:
                from src.config import SESSION_CONFIG
                from src.data.sessions_backfill import backfill_sessions_for_player

                logger.info("Backfill des sessions (session_id, session_label)...")
                r = backfill_sessions_for_player(
                    db_path,
                    xuid,
                    conn=conn,
                    gap_minutes=SESSION_CONFIG.advanced_gap_minutes,
                    include_recent=True,
                    force=force_sessions,
                    dry_run=dry_run,
                )
                total_sessions_updated = r.get("updated", 0)
                if r.get("errors"):
                    for e in r["errors"]:
                        logger.warning(f"  Erreur session: {e}")
                if total_sessions_updated > 0:
                    logger.info(f"✅ {total_sessions_updated} match(s) avec sessions mis à jour")
                else:
                    logger.info("Aucun match à mettre à jour pour sessions")

            logger.info(f"Backfill terminé pour {gamertag}")
            return {
                "matches_checked": 0,
                "matches_missing_data": 0,
                "medals_inserted": 0,
                "events_inserted": 0,
                "skill_inserted": 0,
                "personal_scores_inserted": 0,
                "performance_scores_inserted": 0,
                "aliases_inserted": 0,
                "accuracy_updated": 0,
                "shots_updated": 0,
                "enemy_mmr_updated": 0,
                "assets_updated": 0,
                "participants_inserted": 0,
                "participants_scores_updated": 0,
                "participants_kda_updated": 0,
                "participants_shots_updated": 0,
                "killer_victim_pairs_inserted": total_killer_victim_pairs,
                "end_time_updated": total_end_time_updated,
                "sessions_updated": total_sessions_updated,
            }

        # Récupérer les tokens
        tokens = await get_tokens_from_env()
        if not tokens:
            logger.error("Tokens SPNKr non disponibles")
            return {
                "matches_checked": 0,
                "matches_missing_data": 0,
                "medals_inserted": 0,
                "events_inserted": 0,
                "skill_inserted": 0,
                "personal_scores_inserted": 0,
                "performance_scores_inserted": 0,
                "aliases_inserted": 0,
                "accuracy_updated": 0,
                "shots_updated": 0,
                "enemy_mmr_updated": 0,
                "assets_updated": 0,
                "participants_inserted": 0,
                "participants_scores_updated": 0,
                "participants_kda_updated": 0,
                "participants_shots_updated": 0,
                "killer_victim_pairs_inserted": 0,
                "end_time_updated": 0,
                "sessions_updated": 0,
            }

        # Traiter les matchs
        total_medals = 0
        total_events = 0
        total_skill = 0
        total_personal_scores = 0
        total_performance_scores = 0
        total_aliases = 0
        total_accuracy_updated = 0
        total_shots_updated = 0
        total_enemy_mmr_updated = 0
        total_assets_updated = 0
        total_participants_inserted = 0
        total_participants_scores_updated = 0
        total_participants_kda_updated = 0
        total_participants_shots_updated = 0
        total_end_time_updated = 0

        async with SPNKrAPIClient(
            tokens=tokens,
            requests_per_second=requests_per_second,
        ) as client:
            for i, match_id in enumerate(match_ids, 1):
                try:
                    logger.info(f"[{i}/{len(match_ids)}] Traitement {match_id}...")

                    # Récupérer les stats du match
                    stats_json = await client.get_match_stats(match_id)
                    if not stats_json:
                        logger.warning(f"Impossible de récupérer {match_id}")
                        continue

                    # Compteurs pour le log "données insérées" ce match (score/rang, k/d/a, shots)
                    participants_scores_this_match = 0
                    participants_kda_this_match = 0
                    participants_shots_this_match = 0

                    # Mise à jour score/rang, k/d/a ou shots des participants (options distinctes)
                    if participants_scores or participants_kda or participants_shots:
                        _ensure_match_participants_columns(conn)
                        participant_rows = extract_participants(stats_json)
                        for row in participant_rows:
                            try:
                                if participants_scores:
                                    conn.execute(
                                        """UPDATE match_participants
                                           SET rank = ?, score = ?
                                           WHERE match_id = ? AND xuid = ?""",
                                        (row.rank, row.score, row.match_id, row.xuid),
                                    )
                                if participants_kda:
                                    conn.execute(
                                        """UPDATE match_participants
                                           SET kills = ?, deaths = ?, assists = ?
                                           WHERE match_id = ? AND xuid = ?""",
                                        (
                                            row.kills,
                                            row.deaths,
                                            row.assists,
                                            row.match_id,
                                            row.xuid,
                                        ),
                                    )
                                if participants_shots and (
                                    row.shots_fired is not None or row.shots_hit is not None
                                ):
                                    conn.execute(
                                        """UPDATE match_participants
                                           SET shots_fired = ?, shots_hit = ?
                                           WHERE match_id = ? AND xuid = ?""",
                                        (row.shots_fired, row.shots_hit, row.match_id, row.xuid),
                                    )
                                    participants_shots_this_match += 1
                            except Exception as e:
                                logger.debug(f"Update participant {row.xuid}: {e}")
                        if participant_rows:
                            if participants_scores:
                                participants_scores_this_match = len(participant_rows)
                                total_participants_scores_updated += participants_scores_this_match
                            if participants_kda:
                                participants_kda_this_match = len(participant_rows)
                                total_participants_kda_updated += participants_kda_this_match
                            if participants_shots:
                                total_participants_shots_updated += participants_shots_this_match

                    # Enrichir avec les noms depuis Discovery UGC (playlist, map, pair, game_variant)
                    if assets:
                        await enrich_match_info_with_assets(client, stats_json)

                    # Extraire les XUIDs pour skill
                    xuids = extract_xuids_from_match(stats_json)

                    # Récupérer skill et events si nécessaire
                    skill_json = None
                    highlight_events = []

                    if (skill or enemy_mmr) and xuids:
                        skill_json = await client.get_skill_stats(match_id, xuids)

                    if events:
                        highlight_events = await client.get_highlight_events(match_id)

                    # Transformer les données
                    inserted_this_match = {
                        "medals": 0,
                        "events": 0,
                        "skill": 0,
                        "personal_scores": 0,
                        "performance_scores": 0,
                        "aliases": 0,
                        "accuracy": 0,
                        "shots": 0,
                        "enemy_mmr": 0,
                        "assets": 0,
                        "participants": 0,
                        "participants_scores": participants_scores_this_match,
                        "participants_kda": participants_kda_this_match,
                        "participants_shots": participants_shots_this_match,
                    }

                    # Assets (noms playlist/map/pair) — mise à jour match_stats
                    if assets:
                        from src.data.sync.transformers import create_metadata_resolver

                        metadata_resolver = create_metadata_resolver(None)
                        match_row = transform_match_stats(
                            stats_json, xuid, metadata_resolver=metadata_resolver
                        )
                        if match_row and (
                            match_row.playlist_name
                            or match_row.map_name
                            or match_row.pair_name
                            or match_row.game_variant_name
                        ):
                            conn.execute(
                                """UPDATE match_stats SET
                                    playlist_name = COALESCE(?, playlist_name),
                                    map_name = COALESCE(?, map_name),
                                    pair_name = COALESCE(?, pair_name),
                                    game_variant_name = COALESCE(?, game_variant_name)
                                    WHERE match_id = ?""",
                                (
                                    match_row.playlist_name,
                                    match_row.map_name,
                                    match_row.pair_name,
                                    match_row.game_variant_name,
                                    match_id,
                                ),
                            )
                            inserted_this_match["assets"] = 1
                            total_assets_updated += 1

                    # Accuracy et shots (utilisent transform_match_stats)
                    if accuracy or shots:
                        match_row = transform_match_stats(stats_json, xuid)
                        if match_row:
                            if accuracy and match_row.accuracy is not None:
                                if force_accuracy:
                                    conn.execute(
                                        "UPDATE match_stats SET accuracy = ? WHERE match_id = ?",
                                        (match_row.accuracy, match_id),
                                    )
                                    inserted_this_match["accuracy"] = 1
                                    total_accuracy_updated += 1
                                else:
                                    existing = conn.execute(
                                        "SELECT accuracy FROM match_stats WHERE match_id = ?",
                                        (match_id,),
                                    ).fetchone()
                                    if existing and existing[0] is None:
                                        conn.execute(
                                            "UPDATE match_stats SET accuracy = ? WHERE match_id = ?",
                                            (match_row.accuracy, match_id),
                                        )
                                        inserted_this_match["accuracy"] = 1
                                        total_accuracy_updated += 1
                            if shots and (
                                match_row.shots_fired is not None or match_row.shots_hit is not None
                            ):
                                if force_shots:
                                    conn.execute(
                                        "UPDATE match_stats SET shots_fired = ?, shots_hit = ? WHERE match_id = ?",
                                        (match_row.shots_fired, match_row.shots_hit, match_id),
                                    )
                                    inserted_this_match["shots"] = 1
                                    total_shots_updated += 1
                                else:
                                    existing = conn.execute(
                                        "SELECT shots_fired, shots_hit FROM match_stats WHERE match_id = ?",
                                        (match_id,),
                                    ).fetchone()
                                    if existing and (existing[0] is None or existing[1] is None):
                                        conn.execute(
                                            "UPDATE match_stats SET shots_fired = ?, shots_hit = ? WHERE match_id = ?",
                                            (match_row.shots_fired, match_row.shots_hit, match_id),
                                        )
                                        inserted_this_match["shots"] = 1
                                        total_shots_updated += 1

                    # Médailles
                    if medals:
                        medal_rows = extract_medals(stats_json, xuid)
                        if medal_rows:
                            inserted_this_match["medals"] = _insert_medal_rows(conn, medal_rows)
                            total_medals += inserted_this_match["medals"]

                    # Events
                    if events and highlight_events:
                        event_rows = transform_highlight_events(highlight_events, match_id)
                        if event_rows:
                            inserted_this_match["events"] = _insert_event_rows(conn, event_rows)
                            total_events += inserted_this_match["events"]

                    # Skill
                    if skill and skill_json:
                        skill_row = transform_skill_stats(skill_json, match_id, xuid)
                        if skill_row:
                            inserted_this_match["skill"] = _insert_skill_row(conn, skill_row, xuid)
                            total_skill += inserted_this_match["skill"]

                    # Enemy MMR (peut être fait indépendamment de skill si seulement enemy_mmr est demandé)
                    if enemy_mmr and skill_json:
                        skill_row = transform_skill_stats(skill_json, match_id, xuid)
                        if skill_row and skill_row.enemy_mmr is not None:
                            if force_enemy_mmr:
                                # Forcer la mise à jour même si enemy_mmr existe déjà
                                # Utiliser INSERT OR REPLACE pour créer la ligne si elle n'existe pas
                                _insert_skill_row(conn, skill_row, xuid)
                                inserted_this_match["enemy_mmr"] = 1
                                total_enemy_mmr_updated += 1
                            else:
                                # Ne mettre à jour que si enemy_mmr est NULL
                                existing = conn.execute(
                                    "SELECT enemy_mmr FROM player_match_stats WHERE match_id = ? AND xuid = ?",
                                    (match_id, xuid),
                                ).fetchone()
                                if existing is None:
                                    # La ligne n'existe pas, l'insérer complètement
                                    _insert_skill_row(conn, skill_row, xuid)
                                    inserted_this_match["enemy_mmr"] = 1
                                    total_enemy_mmr_updated += 1
                                elif existing[0] is None:
                                    # La ligne existe mais enemy_mmr est NULL, mettre à jour seulement enemy_mmr
                                    conn.execute(
                                        "UPDATE player_match_stats SET enemy_mmr = ? WHERE match_id = ? AND xuid = ?",
                                        (skill_row.enemy_mmr, match_id, xuid),
                                    )
                                    inserted_this_match["enemy_mmr"] = 1
                                    total_enemy_mmr_updated += 1

                    # Personal scores
                    if personal_scores:
                        personal_scores_data = extract_personal_score_awards(stats_json, xuid)
                        if personal_scores_data:
                            personal_score_rows = transform_personal_score_awards(
                                match_id, xuid, personal_scores_data
                            )
                            if personal_score_rows:
                                inserted_this_match["personal_scores"] = (
                                    _insert_personal_score_rows(conn, personal_score_rows)
                                )
                                total_personal_scores += inserted_this_match["personal_scores"]

                    # Aliases
                    if aliases:
                        alias_rows = extract_aliases(stats_json)
                        if alias_rows:
                            inserted_this_match["aliases"] = _insert_alias_rows(conn, alias_rows)
                            total_aliases += inserted_this_match["aliases"]

                    # Participants (Sprint Gamertag Roster Fix)
                    if participants:
                        participant_rows = extract_participants(stats_json)
                        if participant_rows:
                            inserted_this_match["participants"] = _insert_participant_rows(
                                conn, participant_rows
                            )
                            total_participants_inserted += inserted_this_match["participants"]

                    # Performance scores (calculé après récupération des données)
                    if performance_scores and _compute_performance_score_for_match(conn, match_id):
                        inserted_this_match["performance_scores"] = 1
                        total_performance_scores += 1

                    # Commit après chaque match
                    conn.commit()

                    # Log des insertions
                    parts = []
                    if inserted_this_match["medals"] > 0:
                        parts.append(f"{inserted_this_match['medals']} médaille(s)")
                    if inserted_this_match["events"] > 0:
                        parts.append(f"{inserted_this_match['events']} event(s)")
                    if inserted_this_match["skill"] > 0:
                        parts.append("skill")
                    if inserted_this_match["personal_scores"] > 0:
                        parts.append(f"{inserted_this_match['personal_scores']} personal_score(s)")
                    if inserted_this_match.get("performance_scores", 0) > 0:
                        parts.append("performance_score")
                    if inserted_this_match["aliases"] > 0:
                        parts.append(f"{inserted_this_match['aliases']} alias(es)")
                    if inserted_this_match.get("accuracy", 0) > 0:
                        parts.append("accuracy")
                    if inserted_this_match.get("shots", 0) > 0:
                        parts.append("shots")
                    if inserted_this_match.get("enemy_mmr", 0) > 0:
                        parts.append("enemy_mmr")
                    if inserted_this_match.get("assets", 0) > 0:
                        parts.append("noms assets")
                    if inserted_this_match.get("participants", 0) > 0:
                        parts.append(f"{inserted_this_match['participants']} participant(s)")
                    if inserted_this_match.get("participants_scores", 0) > 0:
                        parts.append(f"{inserted_this_match['participants_scores']} score(s)/rang")
                    if inserted_this_match.get("participants_kda", 0) > 0:
                        parts.append(f"{inserted_this_match['participants_kda']} k/d/a")
                    if inserted_this_match.get("participants_shots", 0) > 0:
                        parts.append(
                            f"{inserted_this_match['participants_shots']} shots participant(s)"
                        )

                    if parts:
                        logger.info(f"  ✅ {', '.join(parts)} inséré(s)")
                    else:
                        logger.info("  ⚠️  Aucune donnée insérée")

                except Exception as e:
                    logger.error(f"Erreur traitement {match_id}: {e}")
                    import traceback

                    traceback.print_exc()
                    continue

        # Phase 6 : Backfill killer_victim_pairs (ne nécessite pas d'API)
        total_killer_victim_pairs = 0
        if killer_victim:
            logger.info("Backfill des paires killer/victim depuis highlight_events...")
            total_killer_victim_pairs = _backfill_killer_victim_pairs(conn, xuid)
            if total_killer_victim_pairs > 0:
                logger.info(f"✅ {total_killer_victim_pairs} paires killer/victim insérées")
            else:
                logger.info("Aucune nouvelle paire killer/victim à insérer")

        # Backfill end_time (start_time + time_played_seconds)
        total_end_time_updated = 0
        if end_time:
            logger.info("Backfill de l'heure de fin des matchs (end_time)...")
            total_end_time_updated = _backfill_end_time(conn, force=force_end_time)
            if total_end_time_updated > 0:
                logger.info(f"✅ {total_end_time_updated} match(s) avec end_time mis à jour")
            else:
                logger.info("Aucun match à mettre à jour pour end_time")

        # Backfill sessions (session_id, session_label) — matchs stables ≥ 4h
        total_sessions_updated = 0
        if sessions:
            from src.config import SESSION_CONFIG
            from src.data.sessions_backfill import backfill_sessions_for_player

            logger.info("Backfill des sessions (session_id, session_label)...")
            r = backfill_sessions_for_player(
                db_path,
                xuid,
                conn=conn,
                gap_minutes=SESSION_CONFIG.advanced_gap_minutes,
                include_recent=True,
                force=force_sessions,
                dry_run=dry_run,
            )
            total_sessions_updated = r.get("updated", 0)
            if r.get("errors"):
                for e in r["errors"]:
                    logger.warning(f"  Erreur session: {e}")
            if total_sessions_updated > 0:
                logger.info(f"✅ {total_sessions_updated} match(s) avec sessions mis à jour")
            else:
                logger.info("Aucun match à mettre à jour pour sessions")

        logger.info(f"Backfill terminé pour {gamertag}")

        return {
            "matches_checked": len(match_ids),
            "matches_missing_data": len(match_ids),
            "medals_inserted": total_medals,
            "events_inserted": total_events,
            "skill_inserted": total_skill,
            "personal_scores_inserted": total_personal_scores,
            "performance_scores_inserted": total_performance_scores,
            "aliases_inserted": total_aliases,
            "accuracy_updated": total_accuracy_updated,
            "shots_updated": total_shots_updated,
            "enemy_mmr_updated": total_enemy_mmr_updated,
            "assets_updated": total_assets_updated,
            "participants_inserted": total_participants_inserted,
            "participants_scores_updated": total_participants_scores_updated,
            "participants_kda_updated": total_participants_kda_updated,
            "participants_shots_updated": total_participants_shots_updated,
            "killer_victim_pairs_inserted": total_killer_victim_pairs,
            "end_time_updated": total_end_time_updated,
            "sessions_updated": total_sessions_updated,
        }

    finally:
        try:
            # Commit final pour assurer que toutes les données sont persistées
            conn.commit()
        except Exception as e:
            logger.debug(f"Note lors du commit final: {e}")
        finally:
            conn.close()


async def backfill_all_players(
    *,
    dry_run: bool = False,
    max_matches: int | None = None,
    requests_per_second: int = 5,
    medals: bool = False,
    events: bool = False,
    skill: bool = False,
    personal_scores: bool = False,
    performance_scores: bool = False,
    aliases: bool = False,
    accuracy: bool = False,
    enemy_mmr: bool = False,
    assets: bool = False,
    participants: bool = False,
    participants_scores: bool = False,
    participants_kda: bool = False,
    participants_shots: bool = False,
    killer_victim: bool = False,
    end_time: bool = False,
    all_data: bool = False,
    force_medals: bool = False,
    force_accuracy: bool = False,
    shots: bool = False,
    force_shots: bool = False,
    force_participants_shots: bool = False,
    force_enemy_mmr: bool = False,
    force_aliases: bool = False,
    force_assets: bool = False,
    force_participants: bool = False,
    force_end_time: bool = False,
    sessions: bool = False,
    force_sessions: bool = False,
) -> dict[str, Any]:
    """Backfill pour tous les joueurs DuckDB v4."""
    players = list_duckdb_v4_players()

    if not players:
        logger.warning("Aucun joueur DuckDB v4 trouvé")
        return {"players_processed": 0, "total_results": {}}

    logger.info(f"Trouvé {len(players)} joueur(s) DuckDB v4")

    total_results = {
        "matches_checked": 0,
        "matches_missing_data": 0,
        "medals_inserted": 0,
        "events_inserted": 0,
        "skill_inserted": 0,
        "personal_scores_inserted": 0,
        "performance_scores_inserted": 0,
        "aliases_inserted": 0,
        "accuracy_updated": 0,
        "shots_updated": 0,
        "enemy_mmr_updated": 0,
        "assets_updated": 0,
        "participants_inserted": 0,
        "participants_scores_updated": 0,
        "participants_kda_updated": 0,
        "participants_shots_updated": 0,
        "killer_victim_pairs_inserted": 0,
        "end_time_updated": 0,
        "sessions_updated": 0,
    }

    for i, player_info in enumerate(players, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"[{i}/{len(players)}] Traitement de {player_info.gamertag}")
        logger.info(f"{'='*60}")

        result = await backfill_player_data(
            player_info.gamertag,
            dry_run=dry_run,
            max_matches=max_matches,
            requests_per_second=requests_per_second,
            medals=medals,
            events=events,
            skill=skill,
            personal_scores=personal_scores,
            performance_scores=performance_scores,
            aliases=aliases,
            accuracy=accuracy,
            enemy_mmr=enemy_mmr,
            assets=assets,
            participants=participants,
            participants_scores=participants_scores,
            participants_kda=participants_kda,
            participants_shots=participants_shots,
            killer_victim=killer_victim,
            end_time=end_time,
            sessions=sessions,
            all_data=all_data,
            force_medals=force_medals,
            force_accuracy=force_accuracy,
            shots=shots,
            force_shots=force_shots,
            force_participants_shots=force_participants_shots,
            force_enemy_mmr=force_enemy_mmr,
            force_aliases=force_aliases,
            force_assets=force_assets,
            force_participants=force_participants,
            force_end_time=force_end_time,
            force_sessions=force_sessions,
        )

        # Agréger les résultats
        for key in total_results:
            total_results[key] += result.get(key, 0)

    return {
        "players_processed": len(players),
        "total_results": total_results,
    }


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Backfill des données manquantes pour DuckDB v4",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--player",
        type=str,
        default=None,
        help="Gamertag du joueur (ignoré si --all)",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Traiter tous les joueurs DuckDB v4",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode dry-run (ne fait que lister les matchs sans données)",
    )

    parser.add_argument(
        "--max-matches",
        type=int,
        default=None,
        help="Nombre maximum de matchs à traiter par joueur (défaut: tous)",
    )

    parser.add_argument(
        "--requests-per-second",
        type=int,
        default=5,
        help="Rate limiting API (défaut: 5 req/s)",
    )

    # Options de données à backfill
    parser.add_argument(
        "--medals",
        action="store_true",
        help="Backfill les médailles",
    )

    parser.add_argument(
        "--events",
        action="store_true",
        help="Backfill les highlight events",
    )

    parser.add_argument(
        "--skill",
        action="store_true",
        help="Backfill les stats skill/MMR",
    )

    parser.add_argument(
        "--personal-scores",
        action="store_true",
        help="Backfill les personal score awards",
    )

    parser.add_argument(
        "--performance-scores",
        action="store_true",
        help="Calculer les scores de performance manquants",
    )

    parser.add_argument(
        "--aliases",
        action="store_true",
        help="Mettre à jour les aliases XUID",
    )

    parser.add_argument(
        "--all-data",
        action="store_true",
        help="Backfill toutes les données (équivalent à --medals --events --skill --personal-scores --performance-scores --aliases --accuracy --enemy-mmr --assets --participants --shots --participants-scores --participants-kda --participants-shots --killer-victim --end-time --sessions)",
    )

    parser.add_argument(
        "--force-medals",
        action="store_true",
        help="Force le rescan de TOUS les matchs pour les médailles, même s'ils en ont déjà",
    )

    parser.add_argument(
        "--accuracy",
        action="store_true",
        help="Backfill la précision (accuracy) pour les matchs avec accuracy NULL",
    )

    parser.add_argument(
        "--force-accuracy",
        action="store_true",
        help="Force la récupération de accuracy pour TOUS les matchs, même si elle existe déjà",
    )

    parser.add_argument(
        "--shots",
        action="store_true",
        help="Backfill shots_fired/shots_hit pour les matchs où ils sont NULL",
    )

    parser.add_argument(
        "--force-shots",
        action="store_true",
        help="Force la mise à jour de shots_fired/shots_hit pour TOUS les matchs",
    )

    parser.add_argument(
        "--enemy-mmr",
        action="store_true",
        help="Backfill enemy_mmr pour les matchs avec enemy_mmr NULL dans player_match_stats",
    )

    parser.add_argument(
        "--force-enemy-mmr",
        action="store_true",
        help="Force la récupération de enemy_mmr pour TOUS les matchs, même s'il existe déjà",
    )

    parser.add_argument(
        "--assets",
        action="store_true",
        help="Récupérer les noms (playlist, map, pair, game_variant) via Discovery UGC",
    )

    parser.add_argument(
        "--force-assets",
        action="store_true",
        help="Force la récupération des noms pour TOUS les matchs",
    )

    parser.add_argument(
        "--force-aliases",
        action="store_true",
        help="Force la ré-extraction des aliases pour tous les matchs (encodage corrigé)",
    )

    parser.add_argument(
        "--participants",
        action="store_true",
        help="Backfill les participants de match (table match_participants pour rosters/coéquipiers)",
    )

    parser.add_argument(
        "--force-participants",
        action="store_true",
        help="Force la ré-extraction des participants pour tous les matchs",
    )

    parser.add_argument(
        "--participants-scores",
        action="store_true",
        help="Backfill score et rang des participants (matchs où rank/score sont manquants)",
    )

    parser.add_argument(
        "--participants-kda",
        action="store_true",
        help="Backfill kills, deaths, assists des participants (matchs où k/d/a sont manquants)",
    )

    parser.add_argument(
        "--participants-shots",
        action="store_true",
        help="Backfill shots_fired/shots_hit des participants (matchs où shots manquants)",
    )

    parser.add_argument(
        "--force-participants-shots",
        action="store_true",
        help="Force la mise à jour de shots_fired/shots_hit pour tous les participants de tous les matchs",
    )

    parser.add_argument(
        "--killer-victim",
        action="store_true",
        help="Backfill les paires killer/victim depuis highlight_events pour antagonistes",
    )

    parser.add_argument(
        "--end-time",
        action="store_true",
        help="Remplir l'heure de fin des matchs (end_time = start_time + time_played_seconds)",
    )

    parser.add_argument(
        "--force-end-time",
        action="store_true",
        help="Recalculer end_time pour tous les matchs, même déjà remplis",
    )

    parser.add_argument(
        "--sessions",
        action="store_true",
        help="Backfill session_id et session_label (matchs stables ≥ 4h)",
    )

    parser.add_argument(
        "--force-sessions",
        action="store_true",
        help="Recalculer les sessions même si session_id déjà rempli",
    )

    args = parser.parse_args()

    # Validation
    if not args.all and not args.player:
        parser.error("--player ou --all est requis")

    # Exécuter le backfill
    try:
        if args.all:
            result = asyncio.run(
                backfill_all_players(
                    dry_run=args.dry_run,
                    max_matches=args.max_matches,
                    requests_per_second=args.requests_per_second,
                    medals=args.medals,
                    events=args.events,
                    skill=args.skill,
                    personal_scores=args.personal_scores,
                    performance_scores=args.performance_scores,
                    aliases=args.aliases,
                    accuracy=args.accuracy,
                    enemy_mmr=args.enemy_mmr,
                    assets=args.assets,
                    participants=args.participants,
                    participants_scores=args.participants_scores,
                    participants_kda=args.participants_kda,
                    participants_shots=args.participants_shots,
                    killer_victim=args.killer_victim,
                    end_time=args.end_time,
                    all_data=args.all_data,
                    force_medals=args.force_medals,
                    force_accuracy=args.force_accuracy,
                    shots=args.shots,
                    force_shots=args.force_shots,
                    force_participants_shots=args.force_participants_shots,
                    force_enemy_mmr=args.force_enemy_mmr,
                    force_aliases=args.force_aliases,
                    force_assets=args.force_assets,
                    force_participants=args.force_participants,
                    force_end_time=args.force_end_time,
                    sessions=args.sessions,
                    force_sessions=args.force_sessions,
                )
            )

            logger.info("\n" + "=" * 60)
            logger.info("=== RÉSUMÉ GLOBAL ===")
            logger.info("=" * 60)
            logger.info(f"Joueurs traités: {result['players_processed']}")
            totals = result["total_results"]
            logger.info(f"Matchs vérifiés: {totals['matches_checked']}")
            logger.info(f"Matchs avec données manquantes: {totals['matches_missing_data']}")
            logger.info(f"Médailles insérées: {totals['medals_inserted']}")
            logger.info(f"Events insérés: {totals['events_inserted']}")
            logger.info(f"Skill inséré: {totals['skill_inserted']}")
            logger.info(f"Personal scores insérés: {totals['personal_scores_inserted']}")
            logger.info(f"Scores de performance calculés: {totals['performance_scores_inserted']}")
            logger.info(f"Aliases insérés: {totals['aliases_inserted']}")
            if args.accuracy:
                logger.info(f"Accuracy mis à jour: {totals['accuracy_updated']}")
            if args.shots:
                logger.info(f"Shots mis à jour: {totals['shots_updated']}")
            if args.enemy_mmr:
                logger.info(f"Enemy MMR mis à jour: {totals['enemy_mmr_updated']}")
            if args.assets:
                logger.info(f"Noms assets mis à jour: {totals['assets_updated']}")
            if args.participants:
                logger.info(f"Participants insérés: {totals['participants_inserted']}")
            if args.participants_scores:
                logger.info(
                    f"Scores/rang participants mis à jour: {totals['participants_scores_updated']}"
                )
            if args.participants_kda:
                logger.info(f"K/D/A participants mis à jour: {totals['participants_kda_updated']}")
            if args.participants_shots:
                logger.info(
                    f"Shots participants mis à jour: {totals['participants_shots_updated']}"
                )
            if args.killer_victim:
                logger.info(
                    f"Paires killer/victim insérées: {totals['killer_victim_pairs_inserted']}"
                )
            if args.end_time:
                logger.info(f"End time mis à jour: {totals['end_time_updated']}")
            if args.sessions:
                logger.info(f"Sessions mises à jour: {totals['sessions_updated']}")
        else:
            result = asyncio.run(
                backfill_player_data(
                    args.player,
                    dry_run=args.dry_run,
                    max_matches=args.max_matches,
                    requests_per_second=args.requests_per_second,
                    medals=args.medals,
                    events=args.events,
                    skill=args.skill,
                    personal_scores=args.personal_scores,
                    performance_scores=args.performance_scores,
                    aliases=args.aliases,
                    accuracy=args.accuracy,
                    enemy_mmr=args.enemy_mmr,
                    assets=args.assets,
                    participants=args.participants,
                    participants_scores=args.participants_scores,
                    participants_kda=args.participants_kda,
                    participants_shots=args.participants_shots,
                    killer_victim=args.killer_victim,
                    end_time=args.end_time,
                    all_data=args.all_data,
                    force_medals=args.force_medals,
                    force_accuracy=args.force_accuracy,
                    shots=args.shots,
                    force_shots=args.force_shots,
                    force_participants_shots=args.force_participants_shots,
                    force_enemy_mmr=args.force_enemy_mmr,
                    force_aliases=args.force_aliases,
                    force_assets=args.force_assets,
                    force_participants=args.force_participants,
                    force_end_time=args.force_end_time,
                    sessions=args.sessions,
                    force_sessions=args.force_sessions,
                )
            )

            logger.info("\n=== Résumé ===")
            logger.info(f"Matchs vérifiés: {result['matches_checked']}")
            logger.info(f"Matchs avec données manquantes: {result['matches_missing_data']}")
            logger.info(f"Médailles insérées: {result['medals_inserted']}")
            logger.info(f"Events insérés: {result['events_inserted']}")
            logger.info(f"Skill inséré: {result['skill_inserted']}")
            logger.info(f"Personal scores insérés: {result['personal_scores_inserted']}")
            logger.info(f"Scores de performance calculés: {result['performance_scores_inserted']}")
            logger.info(f"Aliases insérés: {result['aliases_inserted']}")
            if args.accuracy:
                logger.info(f"Accuracy mis à jour: {result['accuracy_updated']}")
            if args.shots:
                logger.info(f"Shots mis à jour: {result['shots_updated']}")
            if args.enemy_mmr:
                logger.info(f"Enemy MMR mis à jour: {result['enemy_mmr_updated']}")
            if args.assets:
                logger.info(f"Noms assets mis à jour: {result['assets_updated']}")
            if args.participants:
                logger.info(f"Participants insérés: {result['participants_inserted']}")
            if args.participants_scores:
                logger.info(
                    f"Scores/rang participants mis à jour: {result['participants_scores_updated']}"
                )
            if args.participants_kda:
                logger.info(f"K/D/A participants mis à jour: {result['participants_kda_updated']}")
            if args.participants_shots:
                logger.info(
                    f"Shots participants mis à jour: {result['participants_shots_updated']}"
                )
            if args.killer_victim:
                logger.info(
                    f"Paires killer/victim insérées: {result['killer_victim_pairs_inserted']}"
                )
            if args.end_time:
                logger.info(f"End time mis à jour: {result['end_time_updated']}")
            if args.sessions:
                logger.info(f"Sessions mises à jour: {result['sessions_updated']}")

        return 0

    except KeyboardInterrupt:
        logger.info("\nInterrompu par l'utilisateur")
        return 1
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
