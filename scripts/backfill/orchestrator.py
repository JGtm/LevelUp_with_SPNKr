"""Orchestration du backfill pour un ou plusieurs joueurs.

Ce module contient la logique principale de backfill :
- backfill_player_data  : traitement d'un joueur
- backfill_all_players  : itération sur tous les joueurs DuckDB v4
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

from scripts.backfill.core import (
    insert_alias_rows,
    insert_event_rows,
    insert_medal_rows,
    insert_participant_rows,
    insert_personal_score_rows,
    insert_skill_row,
)
from scripts.backfill.detection import find_matches_missing_data
from scripts.backfill.strategies import (
    backfill_end_time,
    backfill_killer_victim_pairs,
    compute_performance_score_for_match,
)

logger = logging.getLogger(__name__)


def _empty_result() -> dict[str, int]:
    """Retourne un dict de résultat vide."""
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
        "participants_damage_updated": 0,
        "killer_victim_pairs_inserted": 0,
        "end_time_updated": 0,
        "sessions_updated": 0,
    }


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
    participants_damage: bool = False,
    killer_victim: bool = False,
    end_time: bool = False,
    sessions: bool = False,
    all_data: bool = False,
    force_medals: bool = False,
    force_accuracy: bool = False,
    shots: bool = False,
    force_shots: bool = False,
    force_participants_shots: bool = False,
    force_participants_damage: bool = False,
    force_enemy_mmr: bool = False,
    force_aliases: bool = False,
    force_assets: bool = False,
    force_participants: bool = False,
    force_end_time: bool = False,
    force_sessions: bool = False,
    detection_mode: str = "or",
) -> dict[str, int]:
    """Remplit les données manquantes pour un joueur.

    Args:
        gamertag: Gamertag du joueur.
        dry_run: Si True, ne fait que lister les matchs sans données.
        max_matches: Nombre maximum de matchs à traiter (None = tous).
        requests_per_second: Rate limiting API.
        detection_mode: "or" (défaut) ou "and" (strict, évite re-téléchargement).
        [autres flags]: Options de backfill activées.

    Returns:
        Dict avec les statistiques.
    """
    # Si all_data, activer toutes les options
    if all_data:
        medals = events = skill = personal_scores = performance_scores = True
        aliases = accuracy = enemy_mmr = assets = participants = True
        shots = participants_scores = participants_kda = True
        participants_shots = participants_damage = True
        killer_victim = end_time = sessions = True

    # Activer les dépendances force → option
    if force_accuracy and not accuracy:
        accuracy = True
    if force_shots and not shots:
        shots = True
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
    if force_participants_damage and not participants_damage:
        participants_damage = True

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
            participants_damage,
            killer_victim,
            end_time,
            sessions,
            force_aliases,
        ]
    ):
        logger.warning(
            "Aucune option de backfill activée. Utilisez --all ou spécifiez des options."
        )
        return _empty_result()

    # Imports lourds
    from src.ui.sync import get_player_duckdb_path, is_duckdb_player
    from src.utils import resolve_xuid_from_db

    # Vérifier que c'est un joueur DuckDB v4
    if not is_duckdb_player(gamertag):
        logger.error(
            f"{gamertag} n'a pas de DB DuckDB v4. Ce script ne fonctionne que pour DuckDB v4."
        )
        return _empty_result()

    db_path = get_player_duckdb_path(gamertag)
    if not db_path or not db_path.exists():
        logger.error(f"DB DuckDB introuvable pour {gamertag}")
        return _empty_result()

    # Résoudre le XUID
    xuid = resolve_xuid_from_db(str(db_path), gamertag)
    if not xuid:
        xuid = _resolve_xuid_fallback(db_path, gamertag)
        if not xuid:
            return _empty_result()
    else:
        logger.info(f"✅ XUID résolu depuis xuid_aliases: {xuid}")

    import duckdb

    conn = duckdb.connect(str(db_path), read_only=False)

    try:
        # Migrations de schéma
        _apply_schema_migrations(
            conn,
            accuracy,
            participants_scores,
            participants_kda,
            participants_shots,
            participants_damage,
        )

        # Détection des matchs manquants
        match_ids = find_matches_missing_data(
            conn,
            xuid,
            detection_mode=detection_mode,
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
            participants_damage=participants_damage,
            force_participants_shots=force_participants_shots,
            force_participants_damage=force_participants_damage,
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
            result = _empty_result()
            result["matches_checked"] = len(match_ids)
            result["matches_missing_data"] = len(match_ids)
            return result

        # Cas : pas de matchs API mais backfill local à faire
        needs_local_only = killer_victim or end_time or sessions
        needs_api = bool(match_ids)

        if not needs_api and not needs_local_only:
            logger.info("Tous les matchs ont déjà toutes les données demandées")
            return _empty_result()

        if not needs_api and needs_local_only:
            return _backfill_local_only(
                conn,
                db_path,
                xuid,
                killer_victim=killer_victim,
                end_time=end_time,
                sessions=sessions,
                force_end_time=force_end_time,
                force_sessions=force_sessions,
                dry_run=dry_run,
            )

        # Traitement API
        return await _backfill_with_api(
            conn,
            db_path,
            xuid,
            match_ids,
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
            participants_damage=participants_damage,
            killer_victim=killer_victim,
            end_time=end_time,
            sessions=sessions,
            force_medals=force_medals,
            force_accuracy=force_accuracy,
            force_shots=force_shots,
            force_enemy_mmr=force_enemy_mmr,
            force_end_time=force_end_time,
            force_sessions=force_sessions,
            force_participants_shots=force_participants_shots,
            force_participants_damage=force_participants_damage,
            shots=shots,
            gamertag=gamertag,
            dry_run=dry_run,
        )

    finally:
        with contextlib.suppress(Exception):
            conn.commit()
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
    participants_damage: bool = False,
    killer_victim: bool = False,
    end_time: bool = False,
    all_data: bool = False,
    force_medals: bool = False,
    force_accuracy: bool = False,
    shots: bool = False,
    force_shots: bool = False,
    force_participants_shots: bool = False,
    force_participants_damage: bool = False,
    force_enemy_mmr: bool = False,
    force_aliases: bool = False,
    force_assets: bool = False,
    force_participants: bool = False,
    force_end_time: bool = False,
    sessions: bool = False,
    force_sessions: bool = False,
    detection_mode: str = "or",
) -> dict[str, Any]:
    """Backfill pour tous les joueurs DuckDB v4."""
    from src.ui.multiplayer import list_duckdb_v4_players

    players = list_duckdb_v4_players()

    if not players:
        logger.warning("Aucun joueur DuckDB v4 trouvé")
        return {"players_processed": 0, "total_results": {}}

    logger.info(f"Trouvé {len(players)} joueur(s) DuckDB v4")

    total_results = _empty_result()

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
            participants_damage=participants_damage,
            killer_victim=killer_victim,
            end_time=end_time,
            sessions=sessions,
            all_data=all_data,
            force_medals=force_medals,
            force_accuracy=force_accuracy,
            shots=shots,
            force_shots=force_shots,
            force_participants_shots=force_participants_shots,
            force_participants_damage=force_participants_damage,
            force_enemy_mmr=force_enemy_mmr,
            force_aliases=force_aliases,
            force_assets=force_assets,
            force_participants=force_participants,
            force_end_time=force_end_time,
            force_sessions=force_sessions,
            detection_mode=detection_mode,
        )

        for key in total_results:
            total_results[key] += result.get(key, 0)

    return {
        "players_processed": len(players),
        "total_results": total_results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_xuid_fallback(db_path: Path, gamertag: str) -> str | None:
    """Tente de résoudre le XUID depuis highlight_events (fallback)."""
    import duckdb

    logger.warning(f"XUID introuvable dans xuid_aliases pour {gamertag}")
    logger.info("Tentative d'extraction depuis les matchs existants...")

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        result = conn.execute(
            """
            SELECT DISTINCT xuid
            FROM highlight_events
            WHERE LOWER(gamertag) = LOWER(?)
              AND xuid IS NOT NULL AND xuid != ''
            LIMIT 1
            """,
            [gamertag],
        ).fetchone()

        if result and result[0]:
            xuid = str(result[0])
            logger.info(f"✅ XUID trouvé depuis highlight_events: {xuid}")
            return xuid

        logger.error(f"❌ Impossible de résoudre le XUID pour {gamertag}")
        logger.error("💡 Solution: python scripts/sync.py --gamertag {gamertag} --delta")
        return None
    finally:
        conn.close()


def _apply_schema_migrations(
    conn: Any,
    accuracy: bool,
    participants_scores: bool,
    participants_kda: bool,
    participants_shots: bool,
    participants_damage: bool,
) -> None:
    """Applique les migrations de schéma nécessaires avant le backfill."""
    from src.db.migrations import (
        ensure_match_participants_columns,
        ensure_medals_earned_bigint,
    )

    # Migration medals_earned INT32 → BIGINT
    ensure_medals_earned_bigint(conn)

    # Colonne accuracy
    if accuracy:
        from src.db.migrations import _add_column_if_missing

        _add_column_if_missing(conn, "match_stats", "accuracy", "FLOAT")

    # Colonnes participants
    if participants_scores or participants_kda or participants_shots or participants_damage:
        with contextlib.suppress(Exception):
            ensure_match_participants_columns(conn)


def _backfill_local_only(
    conn: Any,
    db_path: Path,
    xuid: str,
    *,
    killer_victim: bool,
    end_time: bool,
    sessions: bool,
    force_end_time: bool,
    force_sessions: bool,
    dry_run: bool,
) -> dict[str, int]:
    """Backfill local uniquement (pas d'API nécessaire)."""
    logger.info("Pas de données de match à backfill via API...")
    result = _empty_result()

    if killer_victim:
        logger.info("Backfill des paires killer/victim depuis highlight_events...")
        n = backfill_killer_victim_pairs(conn, xuid)
        result["killer_victim_pairs_inserted"] = n
        if n > 0:
            logger.info(f"✅ {n} paires killer/victim insérées")
        else:
            logger.info("Aucune nouvelle paire killer/victim à insérer")

    if end_time:
        logger.info("Backfill de l'heure de fin des matchs (end_time)...")
        n = backfill_end_time(conn, force=force_end_time)
        result["end_time_updated"] = n
        if n > 0:
            logger.info(f"✅ {n} match(s) avec end_time mis à jour")
        else:
            logger.info("Aucun match à mettre à jour pour end_time")

    if sessions:
        n = _backfill_sessions(conn, db_path, xuid, force=force_sessions, dry_run=dry_run)
        result["sessions_updated"] = n

    return result


def _backfill_sessions(
    conn: Any,
    db_path: Path,
    xuid: str,
    *,
    force: bool,
    dry_run: bool,
) -> int:
    """Backfill des sessions (session_id, session_label)."""
    from src.config import SESSION_CONFIG
    from src.data.sessions_backfill import backfill_sessions_for_player

    logger.info("Backfill des sessions (session_id, session_label)...")
    r = backfill_sessions_for_player(
        db_path,
        xuid,
        conn=conn,
        gap_minutes=SESSION_CONFIG.advanced_gap_minutes,
        include_recent=True,
        force=force,
        dry_run=dry_run,
    )
    n = r.get("updated", 0)
    if r.get("errors"):
        for e in r["errors"]:
            logger.warning(f"  Erreur session: {e}")
    if n > 0:
        logger.info(f"✅ {n} match(s) avec sessions mis à jour")
    else:
        logger.info("Aucun match à mettre à jour pour sessions")
    return n


async def _backfill_with_api(
    conn: Any,
    db_path: Path,
    xuid: str,
    match_ids: list[str],
    *,
    requests_per_second: int,
    medals: bool,
    events: bool,
    skill: bool,
    personal_scores: bool,
    performance_scores: bool,
    aliases: bool,
    accuracy: bool,
    enemy_mmr: bool,
    assets: bool,
    participants: bool,
    participants_scores: bool,
    participants_kda: bool,
    participants_shots: bool,
    participants_damage: bool,
    killer_victim: bool,
    end_time: bool,
    sessions: bool,
    force_medals: bool,
    force_accuracy: bool,
    force_shots: bool,
    force_enemy_mmr: bool,
    force_end_time: bool,
    force_sessions: bool,
    force_participants_shots: bool,
    force_participants_damage: bool,
    shots: bool,
    gamertag: str,
    dry_run: bool,
) -> dict[str, int]:
    """Traitement des matchs via l'API SPNKr."""
    from src.data.sync.api_client import SPNKrAPIClient, get_tokens_from_env
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
    from src.db.migrations import ensure_match_participants_columns

    tokens = await get_tokens_from_env()
    if not tokens:
        logger.error("Tokens SPNKr non disponibles")
        return _empty_result()

    # Compteurs
    totals = _empty_result()
    totals["matches_checked"] = len(match_ids)
    totals["matches_missing_data"] = len(match_ids)

    async with SPNKrAPIClient(
        tokens=tokens,
        requests_per_second=requests_per_second,
    ) as client:
        for i, match_id in enumerate(match_ids, 1):
            try:
                logger.info(f"[{i}/{len(match_ids)}] Traitement {match_id}...")

                stats_json = await client.get_match_stats(match_id)
                if not stats_json:
                    logger.warning(f"Impossible de récupérer {match_id}")
                    continue

                inserted = {}

                # ── Participants scores/kda/shots/damage (UPDATE) ──
                if (
                    participants_scores
                    or participants_kda
                    or participants_shots
                    or participants_damage
                ):
                    ensure_match_participants_columns(conn)
                    ps, pk, psh, pd = _update_participants_details(
                        conn,
                        stats_json,
                        participants_scores=participants_scores,
                        participants_kda=participants_kda,
                        participants_shots=participants_shots,
                        participants_damage=participants_damage,
                    )
                    inserted["participants_scores"] = ps
                    inserted["participants_kda"] = pk
                    inserted["participants_shots"] = psh
                    inserted["participants_damage"] = pd
                    totals["participants_scores_updated"] += ps
                    totals["participants_kda_updated"] += pk
                    totals["participants_shots_updated"] += psh
                    totals["participants_damage_updated"] += pd

                # ── Assets ──
                if assets:
                    await _backfill_assets(client, conn, stats_json, xuid, match_id)
                    totals["assets_updated"] += 1

                xuids = extract_xuids_from_match(stats_json)

                skill_json = None
                highlight_events: list = []

                if (skill or enemy_mmr) and xuids:
                    skill_json = await client.get_skill_stats(match_id, xuids)
                if events:
                    highlight_events = await client.get_highlight_events(match_id)

                # ── Accuracy / Shots ──
                if accuracy or shots:
                    match_row = transform_match_stats(stats_json, xuid)
                    if match_row:
                        a, s = _update_accuracy_shots(
                            conn,
                            match_row,
                            match_id,
                            accuracy=accuracy,
                            shots=shots,
                            force_accuracy=force_accuracy,
                            force_shots=force_shots,
                        )
                        totals["accuracy_updated"] += a
                        totals["shots_updated"] += s

                # ── Médailles ──
                if medals:
                    medal_rows = extract_medals(stats_json, xuid)
                    if medal_rows:
                        n = insert_medal_rows(conn, medal_rows)
                        totals["medals_inserted"] += n

                # ── Events ──
                if events and highlight_events:
                    event_rows = transform_highlight_events(highlight_events, match_id)
                    if event_rows:
                        n = insert_event_rows(conn, event_rows)
                        totals["events_inserted"] += n

                # ── Skill ──
                if skill and skill_json:
                    skill_row = transform_skill_stats(skill_json, match_id, xuid)
                    if skill_row:
                        n = insert_skill_row(conn, skill_row, xuid)
                        totals["skill_inserted"] += n

                # ── Enemy MMR ──
                if enemy_mmr and skill_json:
                    _update_enemy_mmr(conn, skill_json, match_id, xuid, force_enemy_mmr)
                    totals["enemy_mmr_updated"] += 1

                # ── Personal scores ──
                if personal_scores:
                    ps_data = extract_personal_score_awards(stats_json, xuid)
                    if ps_data:
                        ps_rows = transform_personal_score_awards(match_id, xuid, ps_data)
                        if ps_rows:
                            n = insert_personal_score_rows(conn, ps_rows)
                            totals["personal_scores_inserted"] += n

                # ── Aliases ──
                if aliases:
                    alias_rows = extract_aliases(stats_json)
                    if alias_rows:
                        n = insert_alias_rows(conn, alias_rows)
                        totals["aliases_inserted"] += n

                # ── Participants (full insert) ──
                if participants:
                    participant_rows = extract_participants(stats_json)
                    if participant_rows:
                        n = insert_participant_rows(conn, participant_rows)
                        totals["participants_inserted"] += n

                # ── Performance scores ──
                if performance_scores and compute_performance_score_for_match(conn, match_id):
                    totals["performance_scores_inserted"] += 1

                # Commit après chaque match
                conn.commit()

                logger.info(f"  ✅ Match {match_id[:20]}... traité")

            except Exception as e:
                logger.error(f"Erreur traitement {match_id}: {e}")
                import traceback

                traceback.print_exc()
                continue

    # ── Backfill local post-API ──
    if killer_victim:
        logger.info("Backfill des paires killer/victim depuis highlight_events...")
        n = backfill_killer_victim_pairs(conn, xuid)
        totals["killer_victim_pairs_inserted"] = n
        if n > 0:
            logger.info(f"✅ {n} paires killer/victim insérées")

    if end_time:
        logger.info("Backfill de l'heure de fin des matchs (end_time)...")
        n = backfill_end_time(conn, force=force_end_time)
        totals["end_time_updated"] = n
        if n > 0:
            logger.info(f"✅ {n} match(s) avec end_time mis à jour")

    if sessions:
        n = _backfill_sessions(conn, db_path, xuid, force=force_sessions, dry_run=dry_run)
        totals["sessions_updated"] = n

    logger.info(f"Backfill terminé pour {gamertag}")
    return totals


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de traitement par match
# ─────────────────────────────────────────────────────────────────────────────


def _update_participants_details(
    conn: Any,
    stats_json: Any,
    *,
    participants_scores: bool,
    participants_kda: bool,
    participants_shots: bool,
    participants_damage: bool,
) -> tuple[int, int, int, int]:
    """Met à jour les détails des participants (scores, kda, shots, damage).

    Returns:
        Tuple (scores, kda, shots, damage) nombre de mises à jour.
    """
    from src.data.sync.transformers import extract_participants

    participant_rows = extract_participants(stats_json)
    ps = pk = psh = pd = 0

    for row in participant_rows:
        try:
            if participants_scores:
                conn.execute(
                    "UPDATE match_participants SET rank = ?, score = ? "
                    "WHERE match_id = ? AND xuid = ?",
                    (row.rank, row.score, row.match_id, row.xuid),
                )
            if participants_kda:
                conn.execute(
                    "UPDATE match_participants SET kills = ?, deaths = ?, assists = ? "
                    "WHERE match_id = ? AND xuid = ?",
                    (row.kills, row.deaths, row.assists, row.match_id, row.xuid),
                )
            if participants_shots and (row.shots_fired is not None or row.shots_hit is not None):
                conn.execute(
                    "UPDATE match_participants SET shots_fired = ?, shots_hit = ? "
                    "WHERE match_id = ? AND xuid = ?",
                    (row.shots_fired, row.shots_hit, row.match_id, row.xuid),
                )
                psh += 1
            if participants_damage and (
                row.damage_dealt is not None or row.damage_taken is not None
            ):
                conn.execute(
                    "UPDATE match_participants SET damage_dealt = ?, damage_taken = ? "
                    "WHERE match_id = ? AND xuid = ?",
                    (row.damage_dealt, row.damage_taken, row.match_id, row.xuid),
                )
                pd += 1
        except Exception as e:
            logger.debug(f"Update participant {row.xuid}: {e}")

    if participant_rows:
        if participants_scores:
            ps = len(participant_rows)
        if participants_kda:
            pk = len(participant_rows)

    return ps, pk, psh, pd


def _update_accuracy_shots(
    conn: Any,
    match_row: Any,
    match_id: str,
    *,
    accuracy: bool,
    shots: bool,
    force_accuracy: bool,
    force_shots: bool,
) -> tuple[int, int]:
    """Met à jour accuracy et/ou shots pour un match.

    Returns:
        Tuple (accuracy_updated, shots_updated).
    """
    a_updated = 0
    s_updated = 0

    if accuracy and match_row.accuracy is not None:
        if force_accuracy:
            conn.execute(
                "UPDATE match_stats SET accuracy = ? WHERE match_id = ?",
                (match_row.accuracy, match_id),
            )
            a_updated = 1
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
                a_updated = 1

    if shots and (match_row.shots_fired is not None or match_row.shots_hit is not None):
        if force_shots:
            conn.execute(
                "UPDATE match_stats SET shots_fired = ?, shots_hit = ? WHERE match_id = ?",
                (match_row.shots_fired, match_row.shots_hit, match_id),
            )
            s_updated = 1
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
                s_updated = 1

    return a_updated, s_updated


async def _backfill_assets(
    client: Any,
    conn: Any,
    stats_json: Any,
    xuid: str,
    match_id: str,
) -> None:
    """Met à jour les noms d'assets (playlist, map, pair, game_variant) pour un match."""
    from src.data.sync.api_client import enrich_match_info_with_assets
    from src.data.sync.transformers import create_metadata_resolver, transform_match_stats

    await enrich_match_info_with_assets(client, stats_json)

    metadata_resolver = create_metadata_resolver(None)
    match_row = transform_match_stats(stats_json, xuid, metadata_resolver=metadata_resolver)
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


def _update_enemy_mmr(
    conn: Any,
    skill_json: Any,
    match_id: str,
    xuid: str,
    force: bool,
) -> None:
    """Met à jour enemy_mmr pour un match."""
    from src.data.sync.transformers import transform_skill_stats

    skill_row = transform_skill_stats(skill_json, match_id, xuid)
    if not skill_row or skill_row.enemy_mmr is None:
        return

    if force:
        insert_skill_row(conn, skill_row, xuid)
    else:
        existing = conn.execute(
            "SELECT enemy_mmr FROM player_match_stats WHERE match_id = ? AND xuid = ?",
            (match_id, xuid),
        ).fetchone()
        if existing is None:
            insert_skill_row(conn, skill_row, xuid)
        elif existing[0] is None:
            conn.execute(
                "UPDATE player_match_stats SET enemy_mmr = ? WHERE match_id = ? AND xuid = ?",
                (skill_row.enemy_mmr, match_id, xuid),
            )
