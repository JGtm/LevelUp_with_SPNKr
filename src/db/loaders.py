"""Chargement des données depuis la base SQLite."""

import json
import re
import sqlite3
from typing import Any, Dict, List, Optional

from src.db.connection import get_connection
from src.db.parsers import (
    coerce_duration_seconds,
    coerce_number,
    parse_iso_utc,
)
from src.db import queries
from src.models import MatchRow, FriendMatch


def load_asset_name_map(con: sqlite3.Connection, table: str) -> Dict[str, str]:
    """Charge la table de correspondance AssetId -> Nom.
    
    Args:
        con: Connexion SQLite ouverte.
        table: Nom de la table (Maps, Playlists, PlaylistMapModePairs).
        
    Returns:
        Dictionnaire {asset_id: nom}.
    """
    cur = con.cursor()
    cur.execute(f"SELECT ResponseBody FROM {table}")
    out: Dict[str, str] = {}
    for (body,) in cur.fetchall():
        try:
            obj = json.loads(body)
        except Exception:
            continue
        asset_id = obj.get("AssetId")
        name = obj.get("PublicName") or obj.get("Title")
        if isinstance(asset_id, str) and isinstance(name, str) and name.strip():
            out[asset_id] = name.strip()
    return out


def _find_player(players: List[Dict[str, Any]], xuid: str) -> Optional[Dict[str, Any]]:
    """Trouve un joueur dans la liste par son XUID."""
    for pl in players:
        pid = pl.get("PlayerId")
        if pid is None:
            continue
        if xuid in json.dumps(pid):
            return pl
    return None


def _find_player_core_stats_dict(player_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Trouve le dictionnaire contenant les stats Kills/Deaths/Assists."""
    targets = {"Kills", "Deaths", "Assists", "ShotsFired", "ShotsHit", "Accuracy"}

    def find_stats_dict(x: Any) -> Optional[Dict[str, Any]]:
        if isinstance(x, dict):
            if "Kills" in x and "Deaths" in x and any(k in x for k in targets):
                if coerce_number(x.get("Kills")) is not None or coerce_number(x.get("Deaths")) is not None:
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


def _extract_player_stats(player_obj: Dict[str, Any]) -> tuple[int, int, int, Optional[float]]:
    """Extrait kills, deaths, assists, accuracy d'un joueur."""
    stats_dict = _find_player_core_stats_dict(player_obj)
    if stats_dict is None:
        return 0, 0, 0, None

    kills = int(coerce_number(stats_dict.get("Kills")) or 0)
    deaths = int(coerce_number(stats_dict.get("Deaths")) or 0)
    assists = int(coerce_number(stats_dict.get("Assists")) or 0)
    accuracy = coerce_number(stats_dict.get("Accuracy"))
    return kills, deaths, assists, accuracy


def _extract_player_outcome_team(player_obj: Dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    """Extrait outcome et team_id d'un joueur."""
    outcome = player_obj.get("Outcome")
    last_team_id = player_obj.get("LastTeamId")
    outcome_i = int(outcome) if isinstance(outcome, int) else None
    team_i = int(last_team_id) if isinstance(last_team_id, int) else None
    return outcome_i, team_i


def _extract_player_kda(player_obj: Dict[str, Any]) -> Optional[float]:
    """Extrait le KDA d'un joueur."""
    stats_dict = _find_player_core_stats_dict(player_obj)
    if stats_dict is not None:
        v = coerce_number(stats_dict.get("KDA"))
        if v is not None:
            return v

    def find_kda(x: Any) -> Optional[float]:
        if isinstance(x, dict):
            if "KDA" in x:
                v = coerce_number(x.get("KDA"))
                if v is not None:
                    return v
            for v in x.values():
                r = find_kda(v)
                if r is not None:
                    return r
        elif isinstance(x, list):
            for v in x:
                r = find_kda(v)
                if r is not None:
                    return r
        return None

    return find_kda(player_obj.get("PlayerTeamStats"))


def _extract_player_spree_headshots(player_obj: Dict[str, Any]) -> tuple[Optional[int], Optional[int]]:
    """Extrait max_killing_spree et headshot_kills."""
    stats_dict = _find_player_core_stats_dict(player_obj)
    if stats_dict is None:
        return None, None
    spree = coerce_number(stats_dict.get("MaxKillingSpree"))
    headshots = coerce_number(stats_dict.get("HeadshotKills"))
    return (
        int(spree) if spree is not None else None,
        int(headshots) if headshots is not None else None,
    )


def _extract_player_average_life_seconds(player_obj: Dict[str, Any]) -> Optional[float]:
    """Extrait la durée de vie moyenne."""
    stats_dict = _find_player_core_stats_dict(player_obj)
    if stats_dict is not None:
        v = coerce_duration_seconds(stats_dict.get("AverageLifeDuration"))
        if v is not None:
            return v

    def find_avg_life(x: Any) -> Optional[float]:
        if isinstance(x, dict):
            if "AverageLifeDuration" in x:
                v = coerce_duration_seconds(x.get("AverageLifeDuration"))
                if v is not None:
                    return v
            for v in x.values():
                r = find_avg_life(v)
                if r is not None:
                    return r
        elif isinstance(x, list):
            for v in x:
                r = find_avg_life(v)
                if r is not None:
                    return r
        return None

    return find_avg_life(player_obj.get("PlayerTeamStats"))


def _extract_player_time_played_seconds(player_obj: Dict[str, Any]) -> Optional[float]:
    """Extrait le temps de jeu."""
    pi = player_obj.get("ParticipationInfo")
    if not isinstance(pi, dict):
        return None
    return coerce_duration_seconds(pi.get("TimePlayed"))


def load_matches(
    db_path: str,
    xuid: str,
    *,
    playlist_filter: Optional[str] = None,
    map_mode_pair_filter: Optional[str] = None,
    map_filter: Optional[str] = None,
) -> List[MatchRow]:
    """Charge tous les matchs d'un joueur depuis la DB.
    
    Args:
        db_path: Chemin vers le fichier .db.
        xuid: XUID du joueur.
        playlist_filter: Filtre optionnel sur playlist_id.
        map_mode_pair_filter: Filtre optionnel sur map_mode_pair_id.
        map_filter: Filtre optionnel sur map_id.
        
    Returns:
        Liste de MatchRow triée par date croissante.
    """
    with get_connection(db_path) as con:
        map_names = load_asset_name_map(con, "Maps")
        playlist_names = load_asset_name_map(con, "Playlists")
        map_mode_pair_names = load_asset_name_map(con, "PlaylistMapModePairs")

        cur = con.cursor()
        cur.execute(queries.LOAD_MATCH_STATS)

        rows: List[MatchRow] = []
        for (body,) in cur.fetchall():
            try:
                obj = json.loads(body)
            except Exception:
                continue

            match_id = obj.get("MatchId")
            if not isinstance(match_id, str):
                continue

            match_info = obj.get("MatchInfo")
            if not isinstance(match_info, dict):
                continue
            start_time_raw = match_info.get("StartTime")
            if not isinstance(start_time_raw, str):
                continue
            start_time = parse_iso_utc(start_time_raw)

            playlist_id = None
            playlist_obj = match_info.get("Playlist")
            if isinstance(playlist_obj, dict):
                playlist_id = playlist_obj.get("AssetId")
            if not isinstance(playlist_id, str):
                playlist_id = None

            map_id = None
            map_variant = match_info.get("MapVariant")
            if isinstance(map_variant, dict):
                map_id = map_variant.get("AssetId")
            if not isinstance(map_id, str):
                map_id = None

            map_mode_pair_id = None
            pair_obj = match_info.get("PlaylistMapModePair")
            if isinstance(pair_obj, dict):
                map_mode_pair_id = pair_obj.get("AssetId")
            if not isinstance(map_mode_pair_id, str):
                map_mode_pair_id = None

            # Applique les filtres
            if playlist_filter is not None and (playlist_id or "") != playlist_filter:
                continue
            if map_mode_pair_filter is not None and (map_mode_pair_id or "") != map_mode_pair_filter:
                continue
            if map_filter is not None and (map_id or "") != map_filter:
                continue

            players = obj.get("Players")
            if not isinstance(players, list):
                continue

            me = _find_player(players, xuid)
            if me is None:
                continue

            kills, deaths, assists, accuracy = _extract_player_stats(me)
            outcome, last_team_id = _extract_player_outcome_team(me)
            kda = _extract_player_kda(me)
            max_spree, headshots = _extract_player_spree_headshots(me)
            avg_life = _extract_player_average_life_seconds(me)
            time_played = _extract_player_time_played_seconds(me)

            playlist_name = playlist_names.get(playlist_id) if playlist_id else None
            pair_name = map_mode_pair_names.get(map_mode_pair_id) if map_mode_pair_id else None
            map_name = map_names.get(map_id) if map_id else None

            rows.append(
                MatchRow(
                    match_id=match_id,
                    start_time=start_time,
                    map_id=map_id,
                    map_name=map_name,
                    playlist_id=playlist_id,
                    playlist_name=playlist_name,
                    map_mode_pair_id=map_mode_pair_id,
                    map_mode_pair_name=pair_name,
                    outcome=outcome,
                    last_team_id=last_team_id,
                    kda=kda,
                    max_killing_spree=max_spree,
                    headshot_kills=headshots,
                    average_life_seconds=avg_life,
                    time_played_seconds=time_played,
                    kills=kills,
                    deaths=deaths,
                    assists=assists,
                    accuracy=accuracy,
                )
            )

        rows.sort(key=lambda r: r.start_time)
        return rows


def query_matches_with_friend(
    db_path: str,
    self_xuid: str,
    friend_xuid: str,
) -> List[FriendMatch]:
    """Retourne les matchs partagés avec un autre joueur.
    
    Args:
        db_path: Chemin vers le fichier .db.
        self_xuid: XUID du joueur principal.
        friend_xuid: XUID de l'ami.
        
    Returns:
        Liste de FriendMatch triée par date décroissante.
    """
    with get_connection(db_path) as con:
        playlist_names = load_asset_name_map(con, "Playlists")
        map_mode_pair_names = load_asset_name_map(con, "PlaylistMapModePairs")

        cur = con.cursor()
        me_id = f"xuid({self_xuid})"
        fr_id = f"xuid({friend_xuid})"
        cur.execute(queries.QUERY_MATCHES_WITH_FRIEND, (me_id, fr_id))
        
        out: List[FriendMatch] = []
        for row in cur.fetchall():
            match_id, start_time_raw, playlist_id, pair_id, my_team, my_out, fr_team, fr_out, same_team = row
            if not isinstance(match_id, str) or not isinstance(start_time_raw, str):
                continue
            start_time = parse_iso_utc(start_time_raw)
            out.append(
                FriendMatch(
                    match_id=match_id,
                    start_time=start_time,
                    playlist_id=playlist_id,
                    playlist_name=playlist_names.get(playlist_id),
                    pair_id=pair_id,
                    pair_name=map_mode_pair_names.get(pair_id),
                    my_team_id=my_team,
                    my_outcome=my_out,
                    friend_team_id=fr_team,
                    friend_outcome=fr_out,
                    same_team=bool(same_team),
                )
            )
        return out


def list_other_player_xuids(db_path: str, self_xuid: str, limit: int = 500) -> List[str]:
    """Liste les XUID des autres joueurs rencontrés.
    
    Args:
        db_path: Chemin vers le fichier .db.
        self_xuid: XUID du joueur principal (à exclure).
        limit: Nombre maximum de résultats.
        
    Returns:
        Liste de XUID (chaînes numériques).
    """
    with get_connection(db_path) as con:
        cur = con.cursor()
        cur.execute(queries.LIST_OTHER_PLAYER_XUIDS, (limit,))
        xuids: set[str] = set()
        for (pid,) in cur.fetchall():
            if not isinstance(pid, str):
                continue
            if pid == f"xuid({self_xuid})":
                continue
            m = re.fullmatch(r"xuid\((\d+)\)", pid)
            if m:
                xuids.add(m.group(1))
        return sorted(xuids)


def list_top_teammates(db_path: str, self_xuid: str, limit: int = 20) -> List[tuple[str, int]]:
    """Liste les coéquipiers les plus fréquents.
    
    Args:
        db_path: Chemin vers le fichier .db.
        self_xuid: XUID du joueur principal.
        limit: Nombre maximum de résultats.
        
    Returns:
        Liste de tuples (xuid, nombre_de_matchs) triée par fréquence.
    """
    me_id = f"xuid({self_xuid})"
    with get_connection(db_path) as con:
        cur = con.cursor()
        cur.execute(queries.LIST_TOP_TEAMMATES, (me_id, me_id, int(limit)))
        out: List[tuple[str, int]] = []
        for pid, matches in cur.fetchall():
            if not isinstance(pid, str):
                continue
            m = re.fullmatch(r"xuid\((\d+)\)", pid)
            if not m:
                continue
            out.append((m.group(1), int(matches)))
        return out
