"""Détection des matchs avec données manquantes.

Supporte deux modes de détection :
- OR (défaut) : sélectionne les matchs manquant AU MOINS UNE donnée demandée
- AND (strict) : sélectionne les matchs manquant TOUTES les données demandées

Chaque type de données possède un bit dans la colonne match_stats.backfill_completed.
Après un run de backfill, les bits correspondants sont mis à 1 pour chaque
match traité (que l'API ait retourné des données ou non).
Au prochain run, ces matchs ne sont plus détectés comme manquants (sauf --force-*).
"""

from __future__ import annotations

import logging
from typing import Any

from src.data.sync.migrations import BACKFILL_FLAGS, compute_backfill_mask  # noqa: F401

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Re-exports pour rétro-compatibilité (BACKFILL_FLAGS, compute_backfill_mask)
# Définition canonique : src.data.sync.migrations
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée principal
# ─────────────────────────────────────────────────────────────────────────────


def find_matches_missing_data(
    conn: Any,
    xuid: str,
    *,
    shared_conn: Any | None = None,
    detection_mode: str = "or",
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
    participants_damage: bool = False,
    participants_avg_life: bool = False,
    force_participants_shots: bool = False,
    force_participants_damage: bool = False,
    force_participants_avg_life: bool = False,
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
    """Trouve les matchs avec des données manquantes.

    La détection exclut automatiquement les matchs déjà traités lors d'un
    précédent run (via le bitmask match_stats.backfill_completed), sauf si
    un flag --force-* est utilisé pour le type concerné.

    Args:
        conn: Connexion DuckDB (player DB).
        xuid: XUID du joueur.
        shared_conn: Connexion optionnelle à shared_matches.duckdb (v5).
        detection_mode: "or" (défaut) ou "and" (strict).
        max_matches: Limite de résultats.
        all_data: True si --all-data est actif.

    Returns:
        Liste des match_id manquants.
    """
    _ = all_data  # compat signature

    # Détecter le type de flags demandés
    local_data_requested = any(
        [
            medals,
            events,
            skill,
            personal_scores,
            performance_scores,
            accuracy,
            shots,
            enemy_mmr,
            assets,
            participants,
        ]
    )
    participants_data_requested = any(
        [
            participants_scores,
            participants_kda,
            participants_shots,
            participants_damage,
            participants_avg_life,
        ]
    )

    # ── Détection participants via shared DB (toujours si shared_conn disponible) ──
    shared_match_ids: list[str] = []
    if participants_data_requested and shared_conn is not None:
        shared_match_ids = _find_matches_in_shared_db(
            shared_conn=shared_conn,
            xuid=xuid,
            max_matches=max_matches,
            participants_scores=participants_scores,
            participants_kda=participants_kda,
            participants_shots=participants_shots,
            participants_damage=participants_damage,
            participants_avg_life=participants_avg_life,
            force_participants_shots=force_participants_shots,
            force_participants_damage=force_participants_damage,
            force_participants_avg_life=force_participants_avg_life,
        )
        # Si aucun flag local → on retourne directement les résultats shared
        if not local_data_requested:
            return shared_match_ids

    conditions: list[str] = []
    params: list[Any] = []
    has_col = _has_backfill_completed_column(conn)

    # ── Médailles ──
    if medals:
        base = "ms.match_id NOT IN (SELECT DISTINCT match_id FROM medals_earned)"
        if force_medals:
            conditions.append(base)
        else:
            conditions.append(base + _done_guard("medals", has_col))

    # ── Events ──
    if events:
        base = "ms.match_id NOT IN (SELECT DISTINCT match_id FROM highlight_events)"
        conditions.append(base + _done_guard("events", has_col))

    # ── Skill ──
    if skill:
        base = (
            "ms.match_id NOT IN "
            "(SELECT DISTINCT match_id FROM player_match_stats WHERE xuid = ?)"
        )
        conditions.append(base + _done_guard("skill", has_col))
        params.append(xuid)

    # ── Personal scores ──
    if personal_scores:
        base = (
            "ms.match_id NOT IN "
            "(SELECT DISTINCT match_id FROM personal_score_awards WHERE xuid = ?)"
        )
        conditions.append(base + _done_guard("personal_scores", has_col))
        params.append(xuid)

    # ── Performance scores ──
    if performance_scores:
        try:
            col_check = conn.execute(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_name = 'match_stats' AND column_name = 'performance_score'"
            ).fetchone()
            if col_check and col_check[0] > 0:
                conditions.append(
                    "(ms.performance_score IS NULL"
                    + _done_guard("performance_scores", has_col)
                    + ")"
                )
            else:
                conditions.append("1=1")
        except Exception as e:
            logger.debug(f"Vérification performance_score: {e}")
            conditions.append("1=1")

    # ── Accuracy ──
    if accuracy:
        if force_accuracy:
            conditions.append("1=1")
        else:
            conditions.append("(ms.accuracy IS NULL" + _done_guard("accuracy", has_col) + ")")

    # ── Shots ──
    if shots:
        if force_shots:
            conditions.append("1=1")
        else:
            conditions.append(
                "((ms.shots_fired IS NULL OR ms.shots_hit IS NULL)"
                + _done_guard("shots", has_col)
                + ")"
            )

    # ── Enemy MMR ──
    if enemy_mmr:
        base = (
            "ms.match_id IN "
            "(SELECT match_id FROM player_match_stats WHERE xuid = ? AND enemy_mmr IS NULL)"
        )
        if force_enemy_mmr:
            conditions.append(base)
        else:
            conditions.append("(" + base + _done_guard("enemy_mmr", has_col) + ")")
        params.append(xuid)

    # ── Assets ──
    if assets:
        asset_cond = (
            "(ms.playlist_name IS NULL OR ms.playlist_name = ms.playlist_id "
            "OR ms.map_name IS NULL OR ms.map_name = ms.map_id "
            "OR ms.pair_name IS NULL OR ms.pair_name = ms.pair_id "
            "OR ms.game_variant_name IS NULL OR ms.game_variant_name = ms.game_variant_id)"
        )
        if force_assets:
            conditions.append(asset_cond)
        else:
            conditions.append("(" + asset_cond + _done_guard("assets", has_col) + ")")

    # ── Aliases (force uniquement) ──
    if force_aliases:
        conditions.append("1=1")

    # ── Participants ──
    if participants:
        if force_participants:
            conditions.append("1=1")
        else:
            _add_participants_condition(conn, conditions, has_col)

    # ── Participants: si shared_conn gère déjà la détection, skip local ──
    _skip_local_participants = participants_data_requested and shared_conn is not None

    # ── Participants scores ──
    if participants_scores and not _skip_local_participants:
        _add_participants_column_condition(
            conn,
            conditions,
            ["rank", "score"],
            check_col="rank",
            flag_name="participants_scores",
            has_bf_col=has_col,
        )

    # ── Participants KDA ──
    if participants_kda and not _skip_local_participants:
        _add_participants_column_condition(
            conn,
            conditions,
            ["kills", "deaths", "assists"],
            check_col="kills",
            flag_name="participants_kda",
            has_bf_col=has_col,
        )

    # ── Participants shots ──
    if participants_shots and not _skip_local_participants:
        if force_participants_shots:
            conditions.append("1=1")
        else:
            _add_participants_column_condition(
                conn,
                conditions,
                ["shots_fired", "shots_hit"],
                check_col="shots_fired",
                flag_name="participants_shots",
                has_bf_col=has_col,
            )

    # ── Participants damage ──
    if participants_damage and not _skip_local_participants:
        if force_participants_damage:
            conditions.append("1=1")
        else:
            _add_participants_column_condition(
                conn,
                conditions,
                ["damage_dealt", "damage_taken"],
                check_col="damage_dealt",
                flag_name="participants_damage",
                has_bf_col=has_col,
            )

    # ── Participants avg_life_seconds ──
    if participants_avg_life and not _skip_local_participants:
        if force_participants_avg_life:
            conditions.append("1=1")
        else:
            _add_participants_column_condition(
                conn,
                conditions,
                ["avg_life_seconds"],
                check_col="avg_life_seconds",
                flag_name="participants_avg_life",
                has_bf_col=has_col,
            )

    if not conditions:
        # Pas de conditions locales → retourner les résultats shared uniquement
        return shared_match_ids

    joiner = " AND " if detection_mode == "and" else " OR "
    where_clause = joiner.join(conditions)

    query = f"""
        SELECT DISTINCT ms.match_id
        FROM match_stats ms
        WHERE ({where_clause})
        ORDER BY ms.start_time DESC
    """
    if max_matches:
        query += f" LIMIT {max_matches}"

    try:
        result = (
            conn.execute(query, params).fetchall() if params else conn.execute(query).fetchall()
        )
        local_match_ids = [row[0] for row in result]
    except Exception as e:
        logger.error(f"Erreur lors de la recherche des matchs manquants: {e}")
        local_match_ids = []

    # Fusionner résultats locaux + shared (dédoublonner, garder l'ordre)
    if shared_match_ids:
        seen = set(local_match_ids)
        merged = list(local_match_ids)
        for mid in shared_match_ids:
            if mid not in seen:
                merged.append(mid)
                seen.add(mid)
        return merged

    return local_match_ids


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ─────────────────────────────────────────────────────────────────────────────


def _has_backfill_completed_column(conn: Any) -> bool:
    """Vérifie si match_stats possède la colonne backfill_completed."""
    try:
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'match_stats' AND column_name = 'backfill_completed'"
        ).fetchone()
        return bool(result and result[0] > 0)
    except Exception:
        return False


def _has_registry_backfill_column(shared_conn: Any) -> bool:
    """Vérifie si match_registry possède la colonne backfill_completed."""
    try:
        result = shared_conn.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'match_registry' AND column_name = 'backfill_completed'"
        ).fetchone()
        return bool(result and result[0] > 0)
    except Exception:
        return False


def _done_guard(flag_name: str, has_column: bool) -> str:
    """Clause SQL excluant les matchs déjà traités pour ce type.

    Si la colonne backfill_completed existe, retourne :
        AND (COALESCE(ms.backfill_completed, 0) & {bit} = 0)
    Sinon retourne une chaîne vide (aucun filtrage).
    """
    if not has_column:
        return ""
    bit = BACKFILL_FLAGS.get(flag_name, 0)
    if bit == 0:
        return ""
    return f" AND (COALESCE(ms.backfill_completed, 0) & {bit} = 0)"


def _registry_done_guard(flag_name: str, has_column: bool) -> str:
    """Clause SQL excluant les matchs déjà traités dans match_registry (v5).

    Utilise mr.backfill_completed au lieu de ms.backfill_completed.
    """
    if not has_column:
        return ""
    bit = BACKFILL_FLAGS.get(flag_name, 0)
    if bit == 0:
        return ""
    return f" AND (COALESCE(mr.backfill_completed, 0) & {bit} = 0)"


def _find_matches_in_shared_db(
    shared_conn: Any,
    xuid: str,
    *,
    max_matches: int | None,
    participants_scores: bool,
    participants_kda: bool,
    participants_shots: bool,
    participants_damage: bool,
    participants_avg_life: bool,
    force_participants_shots: bool,
    force_participants_damage: bool,
    force_participants_avg_life: bool,
) -> list[str]:
    """Détection des matchs manquants dans shared_matches.duckdb (v5).

    Utilisé pour les backfills participants-only qui travaillent directement
    sur la base partagée sans dépendre de la DB joueur locale.

    La requête filtre d'abord par xuid dans match_participants, puis
    applique les conditions de NULL sur les colonnes demandées.

    Args:
        shared_conn: Connexion à shared_matches.duckdb.
        xuid: XUID du joueur.
        max_matches: Limite de résultats.
        participants_*: Flags de backfill.
        force_participants_*: Flags de forçage.

    Returns:
        Liste des match_id nécessitant un backfill.
    """
    conditions: list[str] = []

    # Vérifier si backfill_completed existe dans match_registry
    has_bf_col = _has_registry_backfill_column(shared_conn)

    # ── Participants scores/rank ──
    if participants_scores:
        conditions.append(
            "(mp.score IS NULL OR mp.rank IS NULL)"
            + _registry_done_guard("participants_scores", has_bf_col)
        )

    # ── Participants K/D/A ──
    if participants_kda:
        conditions.append(
            "(mp.kills IS NULL OR mp.deaths IS NULL OR mp.assists IS NULL)"
            + _registry_done_guard("participants_kda", has_bf_col)
        )

    # ── Participants shots ──
    if participants_shots:
        if force_participants_shots:
            conditions.append("1=1")
        else:
            conditions.append(
                "(mp.shots_fired IS NULL OR mp.shots_hit IS NULL)"
                + _registry_done_guard("participants_shots", has_bf_col)
            )

    # ── Participants damage ──
    if participants_damage:
        if force_participants_damage:
            conditions.append("1=1")
        else:
            conditions.append(
                "(mp.damage_dealt IS NULL OR mp.damage_taken IS NULL)"
                + _registry_done_guard("participants_damage", has_bf_col)
            )

    # ── Participants avg_life_seconds ──
    if participants_avg_life:
        if force_participants_avg_life:
            conditions.append("1=1")
        else:
            conditions.append(
                "mp.avg_life_seconds IS NULL"
                + _registry_done_guard("participants_avg_life", has_bf_col)
            )

    if not conditions:
        return []

    where_clause = " OR ".join(conditions)

    query = f"""
        SELECT DISTINCT mp.match_id
        FROM match_participants mp
        JOIN match_registry mr ON mr.match_id = mp.match_id
        WHERE mp.xuid = ? AND ({where_clause})
        ORDER BY mr.end_time DESC
    """
    if max_matches:
        query += f" LIMIT {max_matches}"

    try:
        result = shared_conn.execute(query, [xuid]).fetchall()
        return [row[0] for row in result]
    except Exception as e:
        logger.error(f"Erreur lors de la détection dans shared DB: {e}")
        return []


def _add_participants_condition(
    conn: Any,
    conditions: list[str],
    has_bf_col: bool,
) -> None:
    """Ajoute la condition pour les matchs sans participants."""
    try:
        table_ok = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_name = 'match_participants'"
        ).fetchone()
        if table_ok and table_ok[0] > 0:
            conditions.append(
                "ms.match_id NOT IN (SELECT DISTINCT match_id FROM match_participants)"
                + _done_guard("participants", has_bf_col)
            )
        else:
            conditions.append("1=1")
    except Exception as e:
        logger.debug(f"Vérification match_participants: {e}")
        conditions.append("1=1")


def _add_participants_column_condition(
    conn: Any,
    conditions: list[str],
    null_columns: list[str],
    check_col: str,
    flag_name: str,
    has_bf_col: bool,
) -> None:
    """Ajoute une condition pour les matchs dont des colonnes participant sont NULL."""
    try:
        table_ok = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_name = 'match_participants'"
        ).fetchone()
        col_ok = conn.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = 'match_participants' "
            f"AND column_name = '{check_col}'"
        ).fetchone()
        if table_ok and table_ok[0] and col_ok and col_ok[0]:
            null_check = " OR ".join(f"{c} IS NULL" for c in null_columns)
            conditions.append(
                f"(ms.match_id IN (SELECT match_id FROM match_participants WHERE {null_check})"
                + _done_guard(flag_name, has_bf_col)
                + ")"
            )
    except Exception as e:
        logger.debug(f"Vérification participants.{check_col}: {e}")
