"""Transformateurs API JSON → lignes DuckDB.

Ce module contient les fonctions de transformation pour convertir
les réponses JSON de l'API SPNKr en rows prêtes pour DuckDB.

Architecture:
- transform_match_stats() : JSON match → MatchStatsRow
- transform_skill_stats() : JSON skill → PlayerMatchStatsRow
- transform_highlight_events() : Events → [HighlightEventRow]
- extract_aliases() : JSON match → {xuid: gamertag}
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.analysis.mode_categories import infer_custom_category_from_pair_name
from src.data.domain.refdata import PERSONAL_SCORE_POINTS
from src.data.sync.metadata_resolver import create_metadata_resolver_function
from src.data.sync.models import (
    HighlightEventRow,
    KillerVictimPairRow,
    MatchParticipantRow,
    MatchStatsRow,
    MedalEarnedRow,
    PlayerMatchStatsRow,
    XuidAliasRow,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Regex et constantes
# =============================================================================

XUID_RE = re.compile(r"(\d{12,20})")


# =============================================================================
# Helpers de parsing (inspirés de src/db/loaders.py)
# =============================================================================


def _safe_float(v: Any) -> float | None:
    """Convertit une valeur en float, gérant NaN et None."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    """Convertit une valeur en int, gérant NaN et None."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(f)
    except (TypeError, ValueError):
        return None


def _safe_str(v: Any) -> str | None:
    """Convertit une valeur en str, gérant None."""
    if v is None:
        return None
    try:
        s = str(v)
        if s == "nan" or s == "None":
            return None
        return s
    except Exception:
        return None


def _parse_iso_utc(s: str | None) -> datetime | None:
    """Parse un timestamp ISO 8601 en datetime UTC."""
    if not s or not isinstance(s, str):
        return None
    try:
        # Gérer les formats avec ou sans 'Z'
        s = s.replace("Z", "+00:00")
        if "+" not in s and "-" not in s[10:]:
            s += "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _find_player(players: list[dict[str, Any]], xuid: str) -> dict[str, Any] | None:
    """Trouve un joueur dans la liste par son XUID."""
    for pl in players:
        pid = pl.get("PlayerId")
        if pid is None:
            continue
        if xuid in json.dumps(pid):
            return pl
    return None


def _find_core_stats_dict(player_obj: dict[str, Any]) -> dict[str, Any] | None:
    """Trouve le dictionnaire contenant les stats Kills/Deaths/Assists.

    Parcourt récursivement PlayerTeamStats pour trouver le dict avec les stats.
    """
    targets = {"Kills", "Deaths", "Assists", "ShotsFired", "ShotsHit", "Accuracy"}

    def find_stats_dict(x: Any) -> dict[str, Any] | None:
        if isinstance(x, dict):
            if (
                "Kills" in x
                and "Deaths" in x
                and any(k in x for k in targets)
                and (
                    _safe_int(x.get("Kills")) is not None or _safe_int(x.get("Deaths")) is not None
                )
            ):
                return x
            for v in x.values():
                r = find_stats_dict(v)
                if r is not None:
                    return r
        elif isinstance(x, list):
            for v in x:
                r = find_stats_dict(v)
                if r is not None:
                    return r
        return None

    return find_stats_dict(player_obj.get("PlayerTeamStats"))


def _extract_player_stats(player_obj: dict[str, Any]) -> tuple[int, int, int, float | None]:
    """Extrait kills, deaths, assists, accuracy d'un joueur."""
    stats_dict = _find_core_stats_dict(player_obj)
    if stats_dict is None:
        return 0, 0, 0, None

    kills = _safe_int(stats_dict.get("Kills")) or 0
    deaths = _safe_int(stats_dict.get("Deaths")) or 0
    assists = _safe_int(stats_dict.get("Assists")) or 0
    accuracy = _safe_float(stats_dict.get("Accuracy"))
    return kills, deaths, assists, accuracy


def _extract_player_outcome_team(player_obj: dict[str, Any]) -> tuple[int | None, int | None]:
    """Extrait outcome et team_id d'un joueur."""
    outcome = player_obj.get("Outcome")
    last_team_id = player_obj.get("LastTeamId")
    outcome_i = int(outcome) if isinstance(outcome, int) else None
    team_i = int(last_team_id) if isinstance(last_team_id, int) else None
    return outcome_i, team_i


def _extract_player_rank(player_obj: dict[str, Any]) -> int | None:
    """Extrait le rang du joueur dans le match."""
    rank = player_obj.get("Rank")
    return int(rank) if isinstance(rank, int) else None


def _extract_kda(player_obj: dict[str, Any]) -> float | None:
    """Extrait le KDA d'un joueur."""
    stats_dict = _find_core_stats_dict(player_obj)
    if stats_dict is not None:
        v = _safe_float(stats_dict.get("KDA"))
        if v is not None:
            return v
    return None


def _extract_spree_headshots(player_obj: dict[str, Any]) -> tuple[int | None, int | None]:
    """Extrait max_killing_spree et headshot_kills."""
    stats_dict = _find_core_stats_dict(player_obj)
    if stats_dict is None:
        return None, None

    max_spree = _safe_int(stats_dict.get("MaxKillingSpree"))
    headshots = _safe_int(stats_dict.get("HeadshotKills"))
    return max_spree, headshots


def _extract_life_time_stats(
    player_obj: dict[str, Any],
    match_obj: dict[str, Any] | None = None,
) -> tuple[float | None, int | None]:
    """Extrait avg_life_seconds et time_played_seconds.

    Args:
        player_obj: Objet joueur avec PlayerTeamStats.
        match_obj: Objet match complet (pour extraire Duration depuis MatchInfo).

    Returns:
        (avg_life_seconds, time_played_seconds)
    """
    stats_dict = _find_core_stats_dict(player_obj)

    # Extraire avg_life_seconds
    avg_life = None
    if stats_dict:
        # Essayer d'abord AverageLifeSeconds (format numérique)
        avg_life = _safe_float(stats_dict.get("AverageLifeSeconds"))

        # Si non trouvé, essayer AverageLifeDuration (format ISO: "PT49.3S")
        if avg_life is None:
            avg_life_duration = stats_dict.get("AverageLifeDuration")
            if isinstance(avg_life_duration, str):
                avg_life_secs = _parse_duration_to_seconds(avg_life_duration)
                avg_life = float(avg_life_secs) if avg_life_secs else None

    # Extraire time_played_seconds
    time_played = None

    # 1. Essayer depuis CoreStats
    if stats_dict:
        if "TimePlayed" in stats_dict:
            tp = stats_dict.get("TimePlayed")
            if isinstance(tp, str):
                time_played = _parse_duration_to_seconds(tp)
            elif isinstance(tp, int | float):
                time_played = _safe_int(tp)
        elif "TimePlayedSeconds" in stats_dict:
            time_played = _safe_int(stats_dict.get("TimePlayedSeconds"))

    # 2. Fallback: extraire depuis MatchInfo.Duration
    if time_played is None and match_obj:
        match_info = match_obj.get("MatchInfo")
        if isinstance(match_info, dict):
            duration = match_info.get("Duration")
            if isinstance(duration, str):
                time_played = _parse_duration_to_seconds(duration)

    return avg_life, time_played


def _parse_duration_to_seconds(duration_str: str) -> int | None:
    """Parse une durée ISO 8601 (PT1H30M45S) en secondes."""
    if not duration_str or not isinstance(duration_str, str):
        return None

    # Format: PT{hours}H{minutes}M{seconds}S ou variations
    pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?"
    match = re.match(pattern, duration_str, re.IGNORECASE)
    if not match:
        return None

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = float(match.group(3) or 0)

    return int(hours * 3600 + minutes * 60 + seconds)


def _extract_team_scores(
    match_obj: dict[str, Any], team_id: int | None
) -> tuple[int | None, int | None]:
    """Extrait my_team_score et enemy_team_score."""
    teams = match_obj.get("Teams")
    if not isinstance(teams, list) or team_id is None:
        return None, None

    my_score = None
    enemy_scores = []

    for team in teams:
        if not isinstance(team, dict):
            continue
        tid = team.get("TeamId")
        score = _safe_int(team.get("TotalPoints")) or _safe_int(team.get("Score"))

        if tid == team_id:
            my_score = score
        elif score is not None:
            enemy_scores.append(score)

    # Pour les modes FFA ou multi-équipes, prendre le max des ennemis
    enemy_score = max(enemy_scores) if enemy_scores else None

    return my_score, enemy_score


def _extract_asset_id(match_info: dict[str, Any], key: str) -> str | None:
    """Extrait l'AssetId d'un objet (Playlist, MapVariant, etc.)."""
    obj = match_info.get(key)
    if isinstance(obj, dict):
        asset_id = obj.get("AssetId")
        if isinstance(asset_id, str):
            return asset_id
    return None


def _extract_public_name(match_info: dict[str, Any], key: str) -> str | None:
    """Extrait le PublicName d'un objet si disponible."""
    obj = match_info.get(key)
    if isinstance(obj, dict):
        name = obj.get("PublicName")
        if isinstance(name, str):
            return name
    return None


def _is_uuid(value: str | None) -> bool:
    """Vérifie si une chaîne est un UUID (format standard)."""
    if not value or not isinstance(value, str):
        return False
    # Format UUID standard: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (36 caractères)
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    return bool(uuid_pattern.match(value.strip()))


def _is_ranked_playlist(match_info: dict[str, Any]) -> bool:
    """Détermine si le match est ranked."""
    playlist = match_info.get("Playlist")
    if isinstance(playlist, dict):
        # Vérifier les tags ou le nom
        tags = playlist.get("Tags")
        if isinstance(tags, list) and "ranked" in [t.lower() for t in tags if isinstance(t, str)]:
            return True
        name = playlist.get("PublicName", "")
        if isinstance(name, str) and "ranked" in name.lower():
            return True
    return False


def _is_firefight_match(match_info: dict[str, Any]) -> bool:
    """Détermine si le match est un Firefight."""
    # Vérifier le game mode ou le nom
    game_variant = match_info.get("UgcGameVariant", {})
    if isinstance(game_variant, dict):
        name = game_variant.get("PublicName", "")
        if isinstance(name, str) and "firefight" in name.lower():
            return True

    # Vérifier la playlist
    playlist = match_info.get("Playlist", {})
    if isinstance(playlist, dict):
        name = playlist.get("PublicName", "")
        if isinstance(name, str) and "firefight" in name.lower():
            return True

    return False


def _determine_mode_category(pair_name: str | None) -> str:
    """Détermine la catégorie custom de mode de jeu.

    Utilise la logique de mode_categories.py pour aligner avec les filtres UI.
    Retourne une des catégories : Assassin, Fiesta, BTB, Ranked, Firefight, Other.

    Args:
        pair_name: Nom du PlaylistMapModePair (ex: "Arena:Slayer on Aquarius").

    Returns:
        Catégorie custom (jamais None, "Other" par défaut).
    """
    return infer_custom_category_from_pair_name(pair_name)


# =============================================================================
# Résolution depuis les référentiels
# =============================================================================


def create_metadata_resolver(
    metadata_db_path: Path | str | None = None,
) -> Callable[[str, str], str | None] | None:
    """Crée une fonction de résolution des noms depuis metadata.duckdb.

    Cette fonction est un wrapper autour de MetadataResolver pour maintenir
    la compatibilité avec le code existant.

    Args:
        metadata_db_path: Chemin vers metadata.duckdb (auto-détecté si None).

    Returns:
        Fonction resolver(asset_type, asset_id) -> name | None, ou None si metadata.duckdb n'existe pas.
    """
    return create_metadata_resolver_function(metadata_db_path)


# =============================================================================
# Fonctions de transformation principales
# =============================================================================


def transform_match_stats(
    match_json: dict[str, Any],
    xuid: str,
    *,
    skill_json: dict[str, Any] | None = None,
    metadata_resolver: Callable[[str, str | None], str | None] | None = None,
) -> MatchStatsRow | None:
    """Transforme le JSON API en MatchStatsRow pour DuckDB.

    Args:
        match_json: JSON brut de l'API SPNKr (MatchStats).
        xuid: XUID du joueur principal.
        skill_json: JSON skill optionnel (PlayerMatchStats) pour MMR.

    Returns:
        MatchStatsRow ou None si le parsing échoue.
    """
    match_id = match_json.get("MatchId")
    if not isinstance(match_id, str):
        return None

    match_info = match_json.get("MatchInfo")
    if not isinstance(match_info, dict):
        return None

    # Parse start_time
    start_time_raw = match_info.get("StartTime")
    start_time = _parse_iso_utc(start_time_raw)
    if start_time is None:
        return None

    # Trouver le joueur
    players = match_json.get("Players")
    if not isinstance(players, list):
        return None

    me = _find_player(players, xuid)
    if me is None:
        return None

    # Extraire les stats de base
    kills, deaths, assists, accuracy = _extract_player_stats(me)
    outcome, team_id = _extract_player_outcome_team(me)
    rank = _extract_player_rank(me)
    kda = _extract_kda(me)
    max_spree, headshots = _extract_spree_headshots(me)
    avg_life, time_played = _extract_life_time_stats(me, match_json)
    my_team_score, enemy_team_score = _extract_team_scores(match_json, team_id)

    # Extraire les identifiants d'assets
    playlist_id = _extract_asset_id(match_info, "Playlist")
    playlist_name = _extract_public_name(match_info, "Playlist")
    map_id = _extract_asset_id(match_info, "MapVariant")
    map_name = _extract_public_name(match_info, "MapVariant")
    pair_id = _extract_asset_id(match_info, "PlaylistMapModePair")
    pair_name = _extract_public_name(match_info, "PlaylistMapModePair")
    game_variant_id = _extract_asset_id(match_info, "UgcGameVariant")
    game_variant_name = _extract_public_name(match_info, "UgcGameVariant")

    # Résolution depuis les référentiels si les noms sont NULL mais les IDs sont présents
    # OU si les noms sont des UUIDs (fallback précédent qui a stocké l'ID)
    if metadata_resolver:
        # Vérifier si playlist_name est un UUID (format UUID standard)
        if playlist_id and (not playlist_name or _is_uuid(playlist_name)):
            resolved = metadata_resolver("playlist", playlist_id)
            if resolved:
                playlist_name = resolved
        # Vérifier si map_name est un UUID
        if map_id and (not map_name or _is_uuid(map_name)):
            resolved = metadata_resolver("map", map_id)
            if resolved:
                map_name = resolved
        # Vérifier si pair_name est un UUID
        if pair_id and (not pair_name or _is_uuid(pair_name)):
            resolved = metadata_resolver("pair", pair_id)
            if resolved:
                pair_name = resolved
        # Vérifier si game_variant_name est un UUID
        if game_variant_id and (not game_variant_name or _is_uuid(game_variant_name)):
            resolved = metadata_resolver("game_variant", game_variant_id)
            if resolved:
                game_variant_name = resolved

    # Fallback sur les IDs si les noms sont toujours NULL
    playlist_name = playlist_name or playlist_id
    map_name = map_name or map_id
    pair_name = pair_name or pair_id
    game_variant_name = game_variant_name or game_variant_id

    # Extraire MMR depuis skill_json si disponible
    team_mmr, enemy_mmr = None, None
    if skill_json:
        mmr_data = _extract_mmr_from_skill(skill_json, xuid, team_id)
        if mmr_data:
            team_mmr, enemy_mmr = mmr_data

    # Stats additionnelles depuis le dict de stats
    stats_dict = _find_core_stats_dict(me)
    damage_dealt = _safe_float(stats_dict.get("DamageDealt")) if stats_dict else None
    damage_taken = _safe_float(stats_dict.get("DamageTaken")) if stats_dict else None
    shots_fired = _safe_int(stats_dict.get("ShotsFired")) if stats_dict else None
    shots_hit = _safe_int(stats_dict.get("ShotsHit")) if stats_dict else None
    grenade_kills = _safe_int(stats_dict.get("GrenadeKills")) if stats_dict else None
    melee_kills = _safe_int(stats_dict.get("MeleeKills")) if stats_dict else None
    power_weapon_kills = _safe_int(stats_dict.get("PowerWeaponKills")) if stats_dict else None
    score = _safe_int(stats_dict.get("Score")) if stats_dict else None
    personal_score = _safe_int(stats_dict.get("PersonalScore")) if stats_dict else None

    # Déterminer les flags
    is_ranked = _is_ranked_playlist(match_info)
    is_firefight = _is_firefight_match(match_info)
    mode_category = _determine_mode_category(pair_name)

    # Sprint 2: Extraire GameVariantCategory (6=Slayer, 15=CTF, etc.)
    game_variant_category = extract_game_variant_category(match_json)

    # Déterminer si le joueur a quitté prématurément
    left_early = outcome == 4  # DidNotFinish

    # Calculer la signature des coéquipiers
    teammates_signature = compute_teammates_signature(match_json, xuid, team_id)

    # Heure de fin du match : start_time + time_played_seconds
    end_time = None
    if start_time is not None and time_played is not None and time_played >= 0:
        end_time = start_time + timedelta(seconds=time_played)

    return MatchStatsRow(
        match_id=match_id,
        start_time=start_time,
        end_time=end_time,
        playlist_id=playlist_id,
        playlist_name=playlist_name,
        map_id=map_id,
        map_name=map_name,
        pair_id=pair_id,
        pair_name=pair_name,
        game_variant_id=game_variant_id,
        game_variant_name=game_variant_name,
        outcome=outcome,
        team_id=team_id,
        rank=rank,
        kills=kills,
        deaths=deaths,
        assists=assists,
        kda=kda,
        accuracy=accuracy,
        headshot_kills=headshots,
        max_killing_spree=max_spree,
        time_played_seconds=time_played,
        avg_life_seconds=avg_life,
        my_team_score=my_team_score,
        enemy_team_score=enemy_team_score,
        team_mmr=team_mmr,
        enemy_mmr=enemy_mmr,
        damage_dealt=damage_dealt,
        damage_taken=damage_taken,
        shots_fired=shots_fired,
        shots_hit=shots_hit,
        grenade_kills=grenade_kills,
        melee_kills=melee_kills,
        power_weapon_kills=power_weapon_kills,
        score=score,
        personal_score=personal_score,
        mode_category=mode_category,
        game_variant_category=game_variant_category,
        is_ranked=is_ranked,
        is_firefight=is_firefight,
        left_early=left_early,
        teammates_signature=teammates_signature,
    )


def _extract_mmr_from_skill(
    skill_json: dict[str, Any],
    xuid: str,
    team_id: int | None,
) -> tuple[float, float] | None:
    """Extrait team_mmr et enemy_mmr depuis le JSON skill.

    Args:
        skill_json: JSON de l'API skill (PlayerMatchStats).
        xuid: XUID du joueur.
        team_id: ID de l'équipe du joueur.

    Returns:
        Tuple (team_mmr, enemy_mmr) ou None.
    """
    value = skill_json.get("Value")
    if not isinstance(value, list):
        return None

    # Trouver notre joueur et extraire TeamMmrs
    my_result = None
    my_team_id = None

    for player in value:
        if not isinstance(player, dict):
            continue

        player_id = player.get("Id")
        player_xuid = None
        if isinstance(player_id, str):
            m = XUID_RE.search(player_id)
            if m:
                player_xuid = m.group(1)

        if player_xuid == xuid:
            my_result = player.get("Result")
            if isinstance(my_result, dict):
                my_team_id = _safe_int(my_result.get("TeamId"))
                break

    if not my_result or my_team_id is None:
        return None

    # Extraire team_mmr depuis TeamMmr du joueur
    team_mmr = _safe_float(my_result.get("TeamMmr"))

    # Extraire enemy_mmr depuis TeamMmrs (recommandé)
    # TeamMmrs contient les MMR de toutes les équipes : {"0": 1200.5, "1": 1150.3}
    enemy_mmr = None
    team_mmrs_raw = my_result.get("TeamMmrs")
    if isinstance(team_mmrs_raw, dict):
        my_key = str(my_team_id)
        for k, v in team_mmrs_raw.items():
            if k != my_key:
                enemy_mmr = _safe_float(v)
                break

    # Fallback : utiliser TeamMmr d'un adversaire si TeamMmrs n'est pas disponible
    if enemy_mmr is None:
        enemy_team_mmrs = []
        for player in value:
            if not isinstance(player, dict):
                continue
            result = player.get("Result")
            if not isinstance(result, dict):
                continue
            player_team = result.get("TeamId")
            player_team_mmr = _safe_float(result.get("TeamMmr"))
            if (
                player_team is not None
                and player_team != my_team_id
                and player_team_mmr is not None
            ):
                enemy_team_mmrs.append(player_team_mmr)

        if enemy_team_mmrs:
            enemy_mmr = sum(enemy_team_mmrs) / len(enemy_team_mmrs)

    if team_mmr is not None and enemy_mmr is not None:
        return (team_mmr, enemy_mmr)

    return None


def transform_skill_stats(
    skill_json: dict[str, Any],
    match_id: str,
    xuid: str,
) -> PlayerMatchStatsRow | None:
    """Transforme le JSON skill en PlayerMatchStatsRow.

    Args:
        skill_json: JSON de l'API skill.
        match_id: ID du match.
        xuid: XUID du joueur.

    Returns:
        PlayerMatchStatsRow ou None.
    """
    value = skill_json.get("Value")
    if not isinstance(value, list):
        return None

    # Trouver notre joueur
    for player in value:
        if not isinstance(player, dict):
            continue

        player_id = player.get("Id")
        if not isinstance(player_id, str):
            continue

        if xuid not in player_id:
            continue

        result = player.get("Result")
        if not isinstance(result, dict):
            continue

        team_id = _safe_int(result.get("TeamId"))
        team_mmr = _safe_float(result.get("TeamMmr"))

        # Extraire enemy_mmr depuis TeamMmrs (recommandé)
        # TeamMmrs contient les MMR de toutes les équipes : {"0": 1200.5, "1": 1150.3}
        enemy_mmr = None
        team_mmrs_raw = result.get("TeamMmrs")
        if isinstance(team_mmrs_raw, dict) and team_id is not None:
            my_key = str(team_id)
            for k, v in team_mmrs_raw.items():
                if k != my_key:
                    enemy_mmr = _safe_float(v)
                    break

        # Fallback : utiliser TeamMmr d'un adversaire si TeamMmrs n'est pas disponible
        if enemy_mmr is None:
            enemy_mmrs = []
            for other in value:
                if not isinstance(other, dict):
                    continue
                other_result = other.get("Result", {})
                other_team = other_result.get("TeamId")
                other_team_mmr = _safe_float(other_result.get("TeamMmr"))
                if other_team is not None and other_team != team_id and other_team_mmr is not None:
                    enemy_mmrs.append(other_team_mmr)

            if enemy_mmrs:
                enemy_mmr = sum(enemy_mmrs) / len(enemy_mmrs)

        # Extraire expected/stddev (aligné legacy loaders.py et API : Kills, Deaths, Assists)
        stat_performances = result.get("StatPerformances")
        kills_expected = None
        kills_stddev = None
        deaths_expected = None
        deaths_stddev = None
        assists_expected = None
        assists_stddev = None

        def _perf_value(sp: dict | None, key: str, subkey: str) -> float | None:
            """Récupère StatPerformances[key][subkey] avec variantes de casse."""
            if not isinstance(sp, dict):
                return None
            for k, v in sp.items():
                if k and k.lower() == key.lower() and isinstance(v, dict):
                    return _safe_float(v.get(subkey))
            return None

        if isinstance(stat_performances, dict):
            # Accès direct (API retourne Kills, Deaths, Assists)
            kills_expected = _perf_value(stat_performances, "Kills", "Expected")
            kills_stddev = _perf_value(stat_performances, "Kills", "StdDev")
            deaths_expected = _perf_value(stat_performances, "Deaths", "Expected")
            deaths_stddev = _perf_value(stat_performances, "Deaths", "StdDev")
            assists_expected = _perf_value(stat_performances, "Assists", "Expected")
            assists_stddev = _perf_value(stat_performances, "Assists", "StdDev")

            # Fallback: itération si structure différente
            if kills_expected is None and deaths_expected is None and assists_expected is None:
                for stat_name, perf in stat_performances.items():
                    if not isinstance(perf, dict):
                        continue
                    expected = _safe_float(perf.get("Expected"))
                    stddev = _safe_float(perf.get("StdDev"))
                    if stat_name and stat_name.lower() == "kills":
                        kills_expected, kills_stddev = expected, stddev
                    elif stat_name and stat_name.lower() == "deaths":
                        deaths_expected, deaths_stddev = expected, stddev
                    elif stat_name and stat_name.lower() == "assists":
                        assists_expected, assists_stddev = expected, stddev

        return PlayerMatchStatsRow(
            match_id=match_id,
            xuid=xuid,
            team_id=team_id,
            team_mmr=team_mmr,
            enemy_mmr=enemy_mmr,
            kills_expected=kills_expected,
            kills_stddev=kills_stddev,
            deaths_expected=deaths_expected,
            deaths_stddev=deaths_stddev,
            assists_expected=assists_expected,
            assists_stddev=assists_stddev,
        )

    return None


def transform_highlight_events(
    events: list[Any],
    match_id: str,
) -> list[HighlightEventRow]:
    """Transforme les highlight events en HighlightEventRows.

    Args:
        events: Liste des events (objets Pydantic ou dicts).
        match_id: ID du match.

    Returns:
        Liste de HighlightEventRow.
    """
    rows = []

    for event in events:
        # Convertir l'event en dict si nécessaire
        event_dict: dict[str, Any]
        if isinstance(event, dict):
            event_dict = event
        elif hasattr(event, "model_dump"):
            event_dict = event.model_dump()
        elif hasattr(event, "dict"):
            event_dict = event.dict()
        elif hasattr(event, "_asdict"):
            event_dict = event._asdict()
        else:
            continue

        event_type = event_dict.get("event_type")
        if not isinstance(event_type, str):
            continue

        time_ms = _safe_int(event_dict.get("time_ms")) or 0
        xuid = _safe_str(event_dict.get("xuid"))
        gamertag = _safe_str(event_dict.get("gamertag"))
        type_hint = _safe_int(event_dict.get("type_hint"))

        rows.append(
            HighlightEventRow(
                match_id=match_id,
                event_type=event_type,
                time_ms=time_ms,
                xuid=xuid,
                gamertag=gamertag,
                type_hint=type_hint,
                raw_json=json.dumps(event_dict, ensure_ascii=False),
            )
        )

    return rows


def _normalize_gamertag(raw: str | bytes | Any) -> str | None:
    """Normalise un gamertag pour éviter troncature et problèmes d'encodage.

    Aligné avec le script legacy spnkr_import_db (_extract_gamertags_from_match_stats).
    Utilise str().strip() comme le legacy et gère les bytes mal encodés.
    """
    if raw is None:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="replace")
        except Exception:
            return None
    s = str(raw).strip() if raw else ""
    return s if s else None


def extract_aliases(
    match_json: dict[str, Any],
    *,
    source: str = "match_roster",
) -> list[XuidAliasRow]:
    """Extrait les paires XUID → Gamertag d'un match.

    Aligné avec le script legacy spnkr_import_db (_extract_gamertags_from_match_stats).
    Gère correctement l'encodage des gamertags (évite troncature/mojibake).

    Args:
        match_json: JSON brut du match.
        source: Source de l'alias (pour traçabilité).

    Returns:
        Liste de XuidAliasRow.
    """
    players = match_json.get("Players")
    if not isinstance(players, list):
        return []

    now = datetime.now(timezone.utc)
    aliases = []
    seen_xuids = set()

    for player in players:
        if not isinstance(player, dict):
            continue

        pid = player.get("PlayerId")
        gamertag_raw = player.get("PlayerGamertag") or player.get("Gamertag")

        # Extraire le XUID (aligné legacy: str ou json.dumps pour dict)
        xuid = None
        if isinstance(pid, str):
            m = XUID_RE.search(pid)
            if m:
                xuid = m.group(1)
        elif isinstance(pid, dict):
            xuid_val = pid.get("Xuid") or pid.get("xuid")
            if xuid_val is not None:
                xuid = str(xuid_val)
            else:
                try:
                    s = json.dumps(pid)
                    m = XUID_RE.search(s)
                    if m:
                        xuid = m.group(1)
                except (TypeError, ValueError):
                    pass

        if not xuid or xuid in seen_xuids:
            continue

        # Nettoyer et normaliser le gamertag (évite troncature/encodage)
        gt = _normalize_gamertag(gamertag_raw)
        if not gt:
            continue

        seen_xuids.add(xuid)
        aliases.append(
            XuidAliasRow(
                xuid=xuid,
                gamertag=gt,
                last_seen=now,
                source=source,
            )
        )

    return aliases


def build_players_lookup(match_json: dict[str, Any]) -> dict[str, str]:
    """Construit un dictionnaire XUID → Gamertag depuis le JSON du match.

    Args:
        match_json: JSON brut du match (clé Players).

    Returns:
        Dict mapping xuid (str) → gamertag (str).
    """
    aliases = extract_aliases(match_json)
    return {a.xuid: a.gamertag for a in aliases}


def extract_killer_victim_pairs_from_highlight_events(
    events: list[dict[str, Any]],
    match_id: str,
    *,
    players_lookup: dict[str, str] | None = None,
) -> list[KillerVictimPairRow]:
    """Extrait les paires killer→victim depuis les highlight events de type Kill.

    Args:
        events: Liste d'events (dicts avec event_type, xuid, victim_xuid, etc.).
        match_id: ID du match.
        players_lookup: Optionnel, mapping xuid → gamertag pour enrichir les rows.

    Returns:
        Liste de KillerVictimPairRow.
    """
    rows = []
    lookup = players_lookup or {}

    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("event_type") != "Kill":
            continue

        killer_xuid = _safe_str(event.get("xuid"))
        victim_xuid = _safe_str(event.get("victim_xuid"))
        if not killer_xuid or not victim_xuid:
            continue

        killer_gamertag = _safe_str(event.get("gamertag")) or lookup.get(killer_xuid)
        victim_gamertag = _safe_str(event.get("victim_gamertag")) or lookup.get(victim_xuid)
        time_ms = _safe_int(event.get("time_ms"))

        rows.append(
            KillerVictimPairRow(
                match_id=match_id,
                killer_xuid=killer_xuid,
                victim_xuid=victim_xuid,
                killer_gamertag=killer_gamertag,
                victim_gamertag=victim_gamertag,
                kill_count=1,
                time_ms=time_ms,
            )
        )

    return rows


def _extract_xuid(player: dict[str, Any] | str) -> str | None:
    """Extrait le XUID d'un joueur depuis son PlayerId.

    Args:
        player: Dict joueur ou PlayerId (str).

    Returns:
        XUID (str) ou None.
    """
    pid = player if isinstance(player, str) else player.get("PlayerId")

    if not pid:
        return None

    if isinstance(pid, str):
        m = XUID_RE.search(pid)
        if m:
            return m.group(1)
    elif isinstance(pid, dict):
        xuid_val = pid.get("Xuid") or pid.get("xuid")
        if xuid_val is not None:
            return str(xuid_val)
        else:
            try:
                s = json.dumps(pid)
                m = XUID_RE.search(s)
                if m:
                    return m.group(1)
            except (TypeError, ValueError):
                pass

    return None


def compute_teammates_signature(
    match_json: dict[str, Any],
    my_xuid: str,
    my_team_id: int | None,
) -> str | None:
    """Calcule la signature des coéquipiers pour un match.

    Args:
        match_json: JSON du match depuis l'API.
        my_xuid: XUID du joueur principal.
        my_team_id: ID de l'équipe du joueur.

    Returns:
        Signature (XUIDs triés séparés par virgule) ou None.
    """
    players = match_json.get("Players")
    if not players or my_team_id is None:
        return None

    # Extraire les XUIDs des coéquipiers (même équipe, excluant moi)
    teammate_xuids = []
    for player in players:
        if not isinstance(player, dict):
            continue

        xuid = _extract_xuid(player)
        team_id = _safe_int(player.get("LastTeamId"))

        if xuid and team_id == my_team_id and xuid != my_xuid:
            teammate_xuids.append(xuid)

    if not teammate_xuids:
        return None

    # Trier et joindre pour créer une signature stable
    teammate_xuids.sort()
    return ",".join(teammate_xuids)


def extract_xuids_from_match(match_json: dict[str, Any]) -> list[int]:
    """Extrait tous les XUIDs d'un match.

    Args:
        match_json: JSON brut du match.

    Returns:
        Liste d'entiers XUID.
    """
    players = match_json.get("Players")
    if not isinstance(players, list):
        return []

    xuids = []
    seen = set()

    for player in players:
        if not isinstance(player, dict):
            continue

        pid = player.get("PlayerId")
        s = pid if isinstance(pid, str) else json.dumps(pid) if pid else None
        if not s:
            continue

        m = XUID_RE.search(s)
        if not m:
            continue

        try:
            xuid = int(m.group(1))
            if xuid not in seen:
                seen.add(xuid)
                xuids.append(xuid)
        except ValueError:
            continue

    return xuids


def extract_participants(match_json: dict[str, Any]) -> list[MatchParticipantRow]:
    """Extrait tous les participants d'un match (xuid, team_id, outcome, gamertag).

    Source : MatchStats.Players[] (JSON API propre, pas les films corrompus).

    Cette fonction permet de reconstruire le roster complet d'un match,
    incluant les équipes et les outcomes, ce qui est nécessaire pour :
    - Identifier les coéquipiers vs adversaires
    - Corriger les requêtes de "Mes coéquipiers"
    - Avoir des gamertags propres pour le roster

    Args:
        match_json: JSON brut de l'API SPNKr (MatchStats).

    Returns:
        Liste de MatchParticipantRow avec tous les joueurs du match.
    """
    match_id = match_json.get("MatchId")
    if not isinstance(match_id, str):
        return []

    players = match_json.get("Players")
    if not isinstance(players, list):
        return []

    rows = []
    seen_xuids = set()

    for player in players:
        if not isinstance(player, dict):
            continue

        # Extraire le XUID
        pid = player.get("PlayerId")
        xuid = None
        if isinstance(pid, str):
            m = XUID_RE.search(pid)
            if m:
                xuid = m.group(1)
        elif isinstance(pid, dict):
            xuid_val = pid.get("Xuid") or pid.get("xuid")
            if xuid_val is not None:
                xuid = str(xuid_val)
            else:
                try:
                    s = json.dumps(pid)
                    m = XUID_RE.search(s)
                    if m:
                        xuid = m.group(1)
                except (TypeError, ValueError):
                    pass

        if not xuid or xuid in seen_xuids:
            continue

        seen_xuids.add(xuid)

        # Extraire team_id et outcome
        team_id = _safe_int(player.get("LastTeamId"))
        outcome = _safe_int(player.get("Outcome"))

        # Extraire et normaliser le gamertag
        gamertag_raw = player.get("PlayerGamertag") or player.get("Gamertag")
        gamertag = _normalize_gamertag(gamertag_raw)

        rows.append(
            MatchParticipantRow(
                match_id=match_id,
                xuid=xuid,
                team_id=team_id,
                outcome=outcome,
                gamertag=gamertag,
            )
        )

    return rows


# =============================================================================
# Sprint 2 : Extracteur GameVariantCategory
# =============================================================================


def extract_game_variant_category(match_json: dict[str, Any]) -> int | None:
    """Extrait le GameVariantCategory depuis le JSON du match.

    Le GameVariantCategory est un entier qui identifie le type de mode
    (Slayer=6, CTF=15, Oddball=18, etc.).

    Args:
        match_json: JSON brut du match (MatchStats).

    Returns:
        GameVariantCategory (int) ou None si non disponible.
    """
    match_info = match_json.get("MatchInfo")
    if not isinstance(match_info, dict):
        return None

    # Chemin direct : MatchInfo.GameVariantCategory
    category = match_info.get("GameVariantCategory")
    if isinstance(category, int):
        return category

    # Fallback : UgcGameVariant.Category
    ugc = match_info.get("UgcGameVariant")
    if isinstance(ugc, dict):
        cat = ugc.get("Category") or ugc.get("GameVariantCategory")
        if isinstance(cat, int):
            return cat

    return None


# =============================================================================
# Extracteur de médailles
# =============================================================================


def extract_medals(
    match_json: dict[str, Any],
    xuid: str,
) -> list[MedalEarnedRow]:
    """Extrait les médailles d'un joueur depuis le JSON du match.

    Args:
        match_json: JSON brut du match depuis l'API SPNKr.
        xuid: XUID du joueur.

    Returns:
        Liste de MedalEarnedRow avec les médailles obtenues.
    """
    match_id = match_json.get("MatchId")
    if not isinstance(match_id, str):
        return []

    players = match_json.get("Players")
    if not isinstance(players, list):
        return []

    # Trouver le joueur
    me = _find_player(players, xuid)
    if me is None:
        return []

    # Extraire les médailles depuis PlayerTeamStats[].Stats.CoreStats.Medals[]
    pts = me.get("PlayerTeamStats")
    if not isinstance(pts, list):
        return []

    medals_dict: dict[int, int] = {}  # medal_name_id -> total_count

    for team_stats in pts:
        if not isinstance(team_stats, dict):
            continue

        stats = team_stats.get("Stats")
        if not isinstance(stats, dict):
            continue

        core_stats = stats.get("CoreStats")
        if not isinstance(core_stats, dict):
            continue

        medals = core_stats.get("Medals")
        if not isinstance(medals, list):
            continue

        for medal in medals:
            if not isinstance(medal, dict):
                continue

            name_id = _safe_int(medal.get("NameId"))
            count = _safe_int(medal.get("Count"))

            if name_id is not None and count is not None and count > 0:
                medals_dict[name_id] = medals_dict.get(name_id, 0) + count

    # Convertir en MedalEarnedRow
    return [
        MedalEarnedRow(match_id=match_id, medal_name_id=name_id, count=count)
        for name_id, count in medals_dict.items()
    ]


# =============================================================================
# Sprint 8.2 : Extracteur PersonalScores (décomposition du score personnel)
# =============================================================================


def extract_personal_score_awards(
    match_json: dict[str, Any],
    xuid: str,
) -> list[dict[str, Any]]:
    """Extrait les PersonalScores depuis le JSON du match.

    Les PersonalScores sont la décomposition du score personnel en
    différents types d'actions (kills, assists, objectifs, etc.).

    Chemin API: Players[].PlayerTeamStats[].Stats.CoreStats.PersonalScores[]

    Args:
        match_json: JSON brut du match (MatchStats).
        xuid: XUID du joueur.

    Returns:
        Liste de dicts avec name_id, count, total_score.
        Ex: [{"name_id": 1024030246, "count": 7, "total_score": 700}, ...]
    """
    players = match_json.get("Players")
    if not isinstance(players, list):
        return []

    # Trouver le joueur
    me = _find_player(players, xuid)
    if me is None:
        return []

    # Parcourir les structures pour trouver PersonalScores
    personal_scores = _find_personal_scores(me)
    if not personal_scores:
        return []

    result = []
    for ps in personal_scores:
        if not isinstance(ps, dict):
            continue

        name_id = _safe_int(ps.get("NameId"))
        if name_id is None:
            continue

        count = _safe_int(ps.get("Count")) or 0
        total_score = _safe_int(ps.get("TotalPersonalScoreAwarded"))
        if total_score is None:
            total_score = count * PERSONAL_SCORE_POINTS.get(name_id, 0)

        result.append(
            {
                "name_id": name_id,
                "count": count,
                "total_score": total_score,
            }
        )

    return result


def _find_personal_scores(player_obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Trouve la liste PersonalScores dans l'objet joueur.

    Parcourt récursivement PlayerTeamStats pour trouver PersonalScores[].
    """

    def find_ps(x: Any) -> list[dict[str, Any]] | None:
        if isinstance(x, dict):
            # Vérifier si ce dict contient PersonalScores
            ps = x.get("PersonalScores")
            if isinstance(ps, list) and len(ps) > 0:
                return ps

            # Parcourir récursivement
            for v in x.values():
                r = find_ps(v)
                if r is not None:
                    return r
        elif isinstance(x, list):
            for v in x:
                r = find_ps(v)
                if r is not None:
                    return r
        return None

    return find_ps(player_obj.get("PlayerTeamStats")) or []


def categorize_personal_score(name_id: int) -> str:
    """Détermine la catégorie d'un PersonalScore.

    Args:
        name_id: ID du score (PersonalScoreNameId).

    Returns:
        Catégorie: "kill", "assist", "objective", "vehicle", "penalty", "other".
    """
    from src.data.domain.refdata import (
        ASSIST_SCORES,
        KILL_SCORES,
        OBJECTIVE_SCORES,
        PENALTY_SCORES,
        VEHICLE_DESTRUCTION_SCORES,
    )

    if name_id in KILL_SCORES:
        return "kill"
    if name_id in ASSIST_SCORES:
        return "assist"
    if name_id in OBJECTIVE_SCORES:
        return "objective"
    if name_id in VEHICLE_DESTRUCTION_SCORES:
        return "vehicle"
    if name_id in PENALTY_SCORES:
        return "penalty"
    return "other"


def transform_personal_score_awards(
    match_id: str,
    xuid: str,
    personal_scores: list[dict[str, Any]],
) -> list:
    """Transforme les PersonalScores en PersonalScoreAwardRows.

    Args:
        match_id: ID du match.
        xuid: XUID du joueur.
        personal_scores: Liste de dicts depuis extract_personal_score_awards().

    Returns:
        Liste de PersonalScoreAwardRow.
    """
    from src.data.domain.refdata import get_personal_score_display_name
    from src.data.sync.models import PersonalScoreAwardRow

    rows = []
    for ps in personal_scores:
        name_id = ps.get("name_id")
        if name_id is None:
            continue

        category = categorize_personal_score(name_id)
        display_name = get_personal_score_display_name(name_id)

        rows.append(
            PersonalScoreAwardRow(
                match_id=match_id,
                xuid=xuid,
                award_name=display_name,
                award_category=category,
                award_count=ps.get("count", 1),
                award_score=ps.get("total_score", 0),
            )
        )

    return rows
