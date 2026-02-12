"""Détection des matchs avec données manquantes.

Supporte deux modes de détection :
- OR (défaut, compatible) : sélectionne les matchs manquant AU MOINS UNE donnée
- AND (strict) : sélectionne les matchs manquant TOUTES les données demandées

Le mode AND évite les re-téléchargements inutiles lors de relances avec --all-data.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def find_matches_missing_data(
    conn: Any,
    xuid: str,
    *,
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
    force_participants_shots: bool = False,
    force_participants_damage: bool = False,
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

    Args:
        conn: Connexion DuckDB.
        xuid: XUID du joueur.
        detection_mode:
            - "or" : Sélectionne les matchs manquant AU MOINS UNE donnée (défaut, compatible)
            - "and" : Sélectionne les matchs manquant TOUTES les données (strict, pas de re-traitement)
        medals..force_participants: Flags de backfill activés.
        max_matches: Limite de résultats.
        all_data: True si --all-data est actif.

    Returns:
        Liste des match_id manquants.
    """
    conditions: list[str] = []
    params: list[Any] = []

    # ── Médailles ──
    if medals:
        if force_medals:
            conditions.append("1=1")
        else:
            conditions.append("ms.match_id NOT IN (SELECT DISTINCT match_id FROM medals_earned)")

    # ── Highlight events ──
    if events:
        conditions.append("ms.match_id NOT IN (SELECT DISTINCT match_id FROM highlight_events)")

    # ── Skill/MMR ──
    if skill:
        conditions.append(
            "ms.match_id NOT IN ("
            "SELECT DISTINCT match_id FROM player_match_stats WHERE xuid = ?)"
        )
        params.append(xuid)

    # ── Personal scores ──
    if personal_scores:
        conditions.append(
            "ms.match_id NOT IN ("
            "SELECT DISTINCT match_id FROM personal_score_awards WHERE xuid = ?)"
        )
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
                    "ms.match_id IN ("
                    "SELECT match_id FROM match_stats WHERE performance_score IS NULL)"
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
            conditions.append("ms.accuracy IS NULL")

    # ── Shots (joueur principal) ──
    if shots:
        if force_shots:
            conditions.append("1=1")
        else:
            conditions.append("(ms.shots_fired IS NULL OR ms.shots_hit IS NULL)")

    # ── Enemy MMR ──
    if enemy_mmr:
        if force_enemy_mmr:
            conditions.append("1=1")
        else:
            conditions.append(
                "ms.match_id IN ("
                "SELECT match_id FROM player_match_stats "
                "WHERE xuid = ? AND enemy_mmr IS NULL)"
            )
            params.append(xuid)

    # ── Assets (noms playlist/map/pair) ──
    if assets:
        if force_assets:
            conditions.append("1=1")
        else:
            conditions.append(
                "ms.playlist_name IS NULL OR ms.playlist_name = ms.playlist_id "
                "OR ms.map_name IS NULL OR ms.map_name = ms.map_id "
                "OR ms.pair_name IS NULL OR ms.pair_name = ms.pair_id "
                "OR ms.game_variant_name IS NULL OR ms.game_variant_name = ms.game_variant_id"
            )

    # ── Force aliases ──
    if force_aliases:
        conditions.append("1=1")

    # ── Participants ──
    if participants:
        if force_participants:
            conditions.append("1=1")
        else:
            _add_participants_condition(conn, conditions)

    # ── Participants scores (rank/score) ──
    if participants_scores:
        _add_participants_column_condition(conn, conditions, ["rank", "score"], check_col="rank")

    # ── Participants KDA ──
    if participants_kda:
        _add_participants_column_condition(
            conn, conditions, ["kills", "deaths", "assists"], check_col="kills"
        )

    # ── Participants shots ──
    if participants_shots:
        if force_participants_shots:
            conditions.append("1=1")
        else:
            _add_participants_column_condition(
                conn,
                conditions,
                ["shots_fired", "shots_hit"],
                check_col="shots_fired",
            )

    # ── Participants damage ──
    if participants_damage:
        if force_participants_damage:
            conditions.append("1=1")
        else:
            _add_participants_column_condition(
                conn,
                conditions,
                ["damage_dealt", "damage_taken"],
                check_col="damage_dealt",
            )

    if not conditions:
        return []

    # ── Construction de la clause WHERE ──
    where_clause = " AND ".join(conditions) if detection_mode == "and" else " OR ".join(conditions)

    # NOTE: L'ancienne clause exclude_complete_matches (top 500 avec 5 données
    # core) a été supprimée car elle excluait à tort les matchs avec nouvelles
    # colonnes NULL (damage_dealt/taken, shots, etc.). Le mode OR gère déjà
    # correctement la sélection : si un match a tout, aucune condition ne le
    # sélectionne.

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
        return [row[0] for row in result]
    except Exception as e:
        logger.error(f"Erreur lors de la recherche des matchs manquants: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ─────────────────────────────────────────────────────────────────────────────


def _add_participants_condition(conn: Any, conditions: list[str]) -> None:
    """Ajoute la condition pour les matchs sans participants."""
    try:
        table_ok = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_name = 'match_participants'"
        ).fetchone()
        if table_ok and table_ok[0] > 0:
            conditions.append(
                "ms.match_id NOT IN (SELECT DISTINCT match_id FROM match_participants)"
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
) -> None:
    """Ajoute une condition pour les matchs dont des colonnes participant sont NULL.

    Args:
        conn: Connexion DuckDB.
        conditions: Liste de conditions à enrichir.
        null_columns: Colonnes dont la valeur NULL déclenche la sélection.
        check_col: Colonne à vérifier pour l'existence (migration).
    """
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
                f"ms.match_id IN (" f"SELECT match_id FROM match_participants WHERE {null_check})"
            )
    except Exception as e:
        logger.debug(f"Vérification participants.{check_col}: {e}")
