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
import math
import re
from datetime import datetime, timezone
from typing import Any

from src.data.sync.models import (
    HighlightEventRow,
    MatchStatsRow,
    PlayerMatchStatsRow,
    XuidAliasRow,
)

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
) -> tuple[float | None, int | None]:
    """Extrait avg_life_seconds et time_played_seconds."""
    stats_dict = _find_core_stats_dict(player_obj)
    if stats_dict is None:
        return None, None

    avg_life = _safe_float(stats_dict.get("AverageLifeSeconds"))

    # Time played peut être dans différents formats
    time_played = None
    if "TimePlayed" in stats_dict:
        tp = stats_dict.get("TimePlayed")
        if isinstance(tp, str):
            # Format ISO 8601 duration (PT1H30M)
            time_played = _parse_duration_to_seconds(tp)
        elif isinstance(tp, int | float):
            time_played = _safe_int(tp)
    elif "TimePlayedSeconds" in stats_dict:
        time_played = _safe_int(stats_dict.get("TimePlayedSeconds"))

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


def _determine_mode_category(match_info: dict[str, Any]) -> str | None:
    """Détermine la catégorie de mode de jeu."""
    game_variant = match_info.get("UgcGameVariant", {})
    if not isinstance(game_variant, dict):
        return None

    name = (game_variant.get("PublicName") or "").lower()

    # Mapping basique des catégories
    if "slayer" in name:
        return "Slayer"
    elif "ctf" in name or "flag" in name:
        return "CTF"
    elif "oddball" in name:
        return "Oddball"
    elif "stronghold" in name or "zone" in name:
        return "Strongholds"
    elif "stockpile" in name:
        return "Stockpile"
    elif "extraction" in name:
        return "Extraction"
    elif "firefight" in name:
        return "Firefight"
    elif "attrition" in name:
        return "Attrition"

    return None


# =============================================================================
# Fonctions de transformation principales
# =============================================================================


def transform_match_stats(
    match_json: dict[str, Any],
    xuid: str,
    *,
    skill_json: dict[str, Any] | None = None,
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
    avg_life, time_played = _extract_life_time_stats(me)
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
    mode_category = _determine_mode_category(match_info)

    # Déterminer si le joueur a quitté prématurément
    left_early = outcome == 4  # DidNotFinish

    return MatchStatsRow(
        match_id=match_id,
        start_time=start_time,
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
        is_ranked=is_ranked,
        is_firefight=is_firefight,
        left_early=left_early,
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

    my_mmr = None
    team_mmrs = []
    enemy_mmrs = []

    for player in value:
        if not isinstance(player, dict):
            continue

        result = player.get("Result")
        if not isinstance(result, dict):
            continue

        mmr = _safe_float(result.get("Mmr"))
        if mmr is None:
            continue

        # Identifier si c'est notre joueur
        player_id = player.get("Id")
        player_xuid = None
        if isinstance(player_id, str):
            m = XUID_RE.search(player_id)
            if m:
                player_xuid = m.group(1)

        if player_xuid == xuid:
            my_mmr = mmr
            continue

        # Déterminer l'équipe du joueur
        player_team = result.get("TeamId")
        if player_team is None:
            # Essayer de trouver dans les données
            player_team = player.get("TeamId")

        if team_id is not None and player_team == team_id:
            team_mmrs.append(mmr)
        else:
            enemy_mmrs.append(mmr)

    # Calculer les moyennes
    team_mmr = None
    enemy_mmr = None

    if team_mmrs:
        # Inclure notre MMR si on l'a trouvé
        all_team = team_mmrs + ([my_mmr] if my_mmr else [])
        team_mmr = sum(all_team) / len(all_team) if all_team else None
    elif my_mmr:
        team_mmr = my_mmr

    if enemy_mmrs:
        enemy_mmr = sum(enemy_mmrs) / len(enemy_mmrs)

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

        # Calculer enemy_mmr (moyenne des autres équipes)
        enemy_mmrs = []
        for other in value:
            if not isinstance(other, dict):
                continue
            other_result = other.get("Result", {})
            other_team = other_result.get("TeamId")
            other_mmr = _safe_float(other_result.get("Mmr"))
            if other_team != team_id and other_mmr is not None:
                enemy_mmrs.append(other_mmr)

        enemy_mmr = sum(enemy_mmrs) / len(enemy_mmrs) if enemy_mmrs else None

        # Extraire expected/stddev
        stat_performances = result.get("StatPerformances")
        kills_expected = None
        kills_stddev = None
        deaths_expected = None
        deaths_stddev = None
        assists_expected = None
        assists_stddev = None

        if isinstance(stat_performances, dict):
            for stat_name, perf in stat_performances.items():
                if not isinstance(perf, dict):
                    continue
                expected = _safe_float(perf.get("Expected"))
                stddev = _safe_float(perf.get("StdDev"))

                if stat_name.lower() == "kills":
                    kills_expected = expected
                    kills_stddev = stddev
                elif stat_name.lower() == "deaths":
                    deaths_expected = expected
                    deaths_stddev = stddev
                elif stat_name.lower() == "assists":
                    assists_expected = expected
                    assists_stddev = stddev

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


def extract_aliases(
    match_json: dict[str, Any],
    *,
    source: str = "match_roster",
) -> list[XuidAliasRow]:
    """Extrait les paires XUID → Gamertag d'un match.

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
        gamertag = player.get("PlayerGamertag") or player.get("Gamertag")

        # Extraire le XUID
        xuid = None
        if isinstance(pid, str):
            m = XUID_RE.search(pid)
            if m:
                xuid = m.group(1)
        elif isinstance(pid, dict):
            # Format {"Xuid": 123456789}
            xuid_val = pid.get("Xuid") or pid.get("xuid")
            if xuid_val:
                xuid = str(xuid_val)

        if not xuid or xuid in seen_xuids:
            continue

        # Nettoyer le gamertag
        if not gamertag or not isinstance(gamertag, str):
            continue

        gt = gamertag.strip()
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
