"""Stratégies de backfill spécifiques.

Chaque stratégie est une fonction autonome qui opère sur une connexion DuckDB.
Aucun commit : le commit est géré par l'orchestrateur.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Killer / Victim pairs
# ─────────────────────────────────────────────────────────────────────────────


def backfill_killer_victim_pairs(conn: Any, me_xuid: str, *, force: bool = False) -> int:
    """Extrait les paires killer/victim depuis highlight_events.

    Mode incrémental par défaut : ne traite que les matchs qui n'ont pas
    encore de paires dans killer_victim_pairs.
    Mode force : DROP + recréation complète de la table.

    Utilise l'algorithme de pairing de src/analysis/killer_victim.py
    pour apparier les events kill/death par timestamp.

    Args:
        conn: Connexion DuckDB.
        me_xuid: XUID du joueur principal (pour référence).
        force: Si True, reconstruit toute la table.

    Returns:
        Nombre de paires insérées.
    """
    from src.analysis.killer_victim import KVPair, compute_killer_victim_pairs

    if force:
        # Mode destructif : tout reconstruire
        conn.execute("DROP TABLE IF EXISTS killer_victim_pairs")
        logger.info("Table killer_victim_pairs supprimée (mode --force)")

    # Créer la table si elle n'existe pas
    conn.execute("""
        CREATE TABLE IF NOT EXISTS killer_victim_pairs (
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
    with contextlib.suppress(Exception):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kv_match ON killer_victim_pairs(match_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kv_killer ON killer_victim_pairs(killer_xuid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kv_victim ON killer_victim_pairs(victim_xuid)")

    # Charger les matchs avec highlight events kill/death
    # qui n'ont PAS encore de paires (mode incrémental)
    try:
        matches = conn.execute("""
            SELECT DISTINCT he.match_id
            FROM highlight_events he
            WHERE LOWER(he.event_type) IN ('kill', 'death')
              AND NOT EXISTS (
                  SELECT 1 FROM killer_victim_pairs kvp
                  WHERE kvp.match_id = he.match_id
              )
        """).fetchall()
    except Exception as e:
        logger.warning(f"Erreur lecture highlight_events: {e}")
        return 0

    if not matches:
        logger.info(
            "Aucun nouveau match à traiter pour killer/victim (incrémental, tous déjà traités)"
        )
        return 0

    logger.info(f"Trouvé {len(matches)} matchs à traiter pour paires killer/victim")
    total_pairs = 0
    skipped_no_pairs = 0
    logged_debug = False

    for (match_id,) in matches:
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
        except Exception as e:
            logger.warning(f"Impossible de charger les events pour match {match_id}: {e}")
            continue

        if not events:
            continue

        event_dicts = [
            {
                "event_type": row[0],
                "time_ms": row[1],
                "xuid": row[2],
                "gamertag": row[3],
            }
            for row in events
        ]

        kills_count = sum(
            1 for e in event_dicts if str(e.get("event_type") or "").lower() == "kill"
        )
        deaths_count = sum(
            1 for e in event_dicts if str(e.get("event_type") or "").lower() == "death"
        )

        is_first_match = not logged_debug
        if is_first_match:
            logged_debug = True
            sample_types = {str(e.get("event_type")) for e in event_dicts[:10]}
            logger.info(f"  [DEBUG] Sample event_types: {sample_types}")
            logger.info(
                f"  [DEBUG] Match {match_id[:20]}...: {len(events)} events, "
                f"{kills_count} kills, {deaths_count} deaths"
            )

        if kills_count == 0 or deaths_count == 0:
            skipped_no_pairs += 1
            continue

        pairs: list[KVPair] = compute_killer_victim_pairs(event_dicts, tolerance_ms=5)

        if is_first_match and pairs:
            logger.info(f"  [DEBUG] Paires calculées: {len(pairs)}")
            logger.info(
                f"  [DEBUG] Première paire: killer={pairs[0].killer_xuid}, "
                f"victim={pairs[0].victim_xuid}, time={pairs[0].time_ms}"
            )

        if not pairs:
            skipped_no_pairs += 1
            continue

        insert_errors = 0
        for p in pairs:
            try:
                conn.execute(
                    """
                    INSERT INTO killer_victim_pairs
                    (match_id, killer_xuid, killer_gamertag, victim_xuid,
                     victim_gamertag, kill_count, time_ms)
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

    if skipped_no_pairs > 0:
        logger.info(
            f"  Matchs skippés (pas de kills/deaths ou algorithme vide): {skipped_no_pairs}"
        )

    return total_pairs


# ─────────────────────────────────────────────────────────────────────────────
# End time
# ─────────────────────────────────────────────────────────────────────────────


def backfill_end_time(conn: Any, force: bool = False) -> int:
    """Met à jour end_time (start_time + time_played_seconds).

    Args:
        conn: Connexion DuckDB.
        force: Si True, recalcule pour tous les matchs.

    Returns:
        Nombre de lignes mises à jour.
    """
    from src.data.sync.migrations import ensure_end_time_column

    ensure_end_time_column(conn)

    try:
        where_clause = (
            "WHERE start_time IS NOT NULL AND time_played_seconds IS NOT NULL"
            if force
            else "WHERE end_time IS NULL "
            "AND start_time IS NOT NULL "
            "AND time_played_seconds IS NOT NULL"
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
        return len(updated)
    except Exception as e:
        logger.warning(f"Erreur backfill end_time: {e}")
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# Performance score
# ─────────────────────────────────────────────────────────────────────────────

# Import conditionnel pour le calcul des scores de performance
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


def compute_performance_score_for_match(conn: Any, match_id: str) -> bool:
    """Calcule et met à jour le score de performance pour un match.

    Args:
        conn: Connexion DuckDB.
        match_id: ID du match.

    Returns:
        True si le score a été calculé, False sinon.
    """
    if not PERFORMANCE_SCORE_AVAILABLE:
        return False

    from src.data.sync.migrations import ensure_performance_score_column, get_table_columns

    try:
        existing_cols = get_table_columns(conn, "match_stats")

        optional_cols = ["personal_score", "damage_dealt", "rank", "team_mmr", "enemy_mmr"]

        def _col_or_null(col: str) -> str:
            return col if col in existing_cols else f"NULL AS {col}"

        optional_select = ",\n                   ".join(_col_or_null(c) for c in optional_cols)

        ensure_performance_score_column(conn)

        # Vérifier si le score existe déjà
        existing = conn.execute(
            "SELECT performance_score FROM match_stats WHERE match_id = ?",
            (match_id,),
        ).fetchone()

        if existing and existing[0] is not None:
            return False

        # Récupérer les données du match actuel
        match_data = conn.execute(
            f"""
            SELECT match_id, start_time, kills, deaths, assists, kda, accuracy,
                   time_played_seconds, avg_life_seconds,
                   {optional_select}
            FROM match_stats
            WHERE match_id = ?
            """,
            (match_id,),
        ).fetchone()

        if not match_data:
            return False

        match_start_time = match_data[1]
        if match_start_time is None:
            return False

        # Charger l'historique directement en Polars
        try:
            history_df = conn.execute(
                f"""
                SELECT
                    match_id, start_time, kills, deaths, assists, kda, accuracy,
                    time_played_seconds, avg_life_seconds,
                    {optional_select}
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

        if history_df.is_empty() or len(history_df) < MIN_MATCHES_FOR_RELATIVE:
            return False

        # Dict au lieu de pd.Series
        match_dict = {
            "kills": match_data[2] or 0,
            "deaths": match_data[3] or 0,
            "assists": match_data[4] or 0,
            "kda": match_data[5],
            "accuracy": match_data[6],
            "time_played_seconds": match_data[7] or 600.0,
            "personal_score": match_data[9],
            "damage_dealt": match_data[10],
            "rank": match_data[11],
            "team_mmr": match_data[12],
            "enemy_mmr": match_data[13],
        }

        score = compute_relative_performance_score(match_dict, history_df)

        if score is not None:
            conn.execute(
                "UPDATE match_stats SET performance_score = ? WHERE match_id = ?",
                (score, match_id),
            )
            return True

        return False

    except Exception as e:
        logger.warning(f"Erreur calcul score performance pour {match_id}: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Citations
# ─────────────────────────────────────────────────────────────────────────────


def backfill_citations(
    conn: Any,
    db_path: str | Any,
    xuid: str,
    *,
    force: bool = False,
) -> int:
    """Calcule et insère les citations pour les matchs existants.

    Mode incrémental par défaut : ne traite que les matchs sans citations.
    Mode force : recalcule pour tous les matchs.

    Args:
        conn: Connexion DuckDB (non utilisée directement, on ouvre via engine).
        db_path: Chemin vers la DB joueur.
        xuid: XUID du joueur.
        force: Si True, recalcule pour tous les matchs.

    Returns:
        Nombre de matchs traités.
    """
    from pathlib import Path

    from src.analysis.citations.engine import CitationEngine

    db_path = Path(db_path) if not isinstance(db_path, Path) else db_path
    engine = CitationEngine(str(db_path), xuid, conn=conn)

    # Vérifier que les mappings existent
    mappings = engine.load_mappings()
    if not mappings:
        logger.warning("Aucun mapping de citations trouvé")
        return 0

    # Récupérer les match_ids à traiter via la connexion existante
    if force:
        match_ids = [
            r[0]
            for r in conn.execute("SELECT match_id FROM match_stats ORDER BY start_time").fetchall()
        ]
    else:
        # Matchs sans aucune citation dans match_citations
        match_ids = [
            r[0]
            for r in conn.execute(
                "SELECT ms.match_id FROM match_stats ms "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM match_citations mc WHERE mc.match_id = ms.match_id"
                ") ORDER BY ms.start_time"
            ).fetchall()
        ]

    if not match_ids:
        logger.info("Aucun match à traiter pour les citations")
        return 0

    logger.info(f"Traitement de {len(match_ids)} match(s) pour les citations...")

    count = 0
    for i, match_id in enumerate(match_ids, 1):
        try:
            n = engine.compute_and_store_for_match(match_id, conn=conn)
            if n > 0:
                count += 1
            if i % 100 == 0:
                logger.info(f"  [{i}/{len(match_ids)}] {count} matchs avec citations")
        except Exception as e:
            logger.warning(f"Erreur citation pour {match_id}: {e}")
            continue

    logger.info(f"✅ {count} match(s) traités pour les citations")
    return count
