"""Fonctions de cache Streamlit pour le dashboard.

Ce module regroupe toutes les fonctions @st.cache_data utilisées
pour éviter de recharger les données à chaque interaction.

Stratégie de cache à trois niveaux :
1. Cache Parquet/DuckDB (nouveau) : Données en format colonnaire haute performance
2. Cache DB (MatchCache, etc.) : Données pré-parsées, sessions pré-calculées
3. Cache Streamlit (@st.cache_data) : Évite les requêtes DB répétées

Les fonctions suffixées par _cached utilisent prioritairement le cache DB
avec fallback sur les loaders originaux si le cache n'existe pas.

Architecture hybride (Phase 2+) :
- Mode "legacy" : Utilise src/db/loaders.py (comportement original)
- Mode "hybrid" : Utilise Parquet + DuckDB (haute performance)
- Mode "shadow" : Lit legacy, écrit en shadow vers hybrid (migration)

Le mode est configurable via AppSettings.repository_mode.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import pandas as pd
import polars as pl
import streamlit as st

logger = logging.getLogger(__name__)

from src.analysis import compute_sessions, compute_sessions_with_context_polars, mark_firefight
from src.config import SESSION_CONFIG
from src.db import (
    get_cache_stats,
    get_match_session_info,
    has_cache_tables,
    list_other_player_xuids,
    list_top_teammates,
    load_friends,
    load_highlight_events_for_match,
    load_match_medals_for_player,
    load_match_player_gamertags,
    load_match_rosters,
    load_matches,
    # Nouveaux loaders optimisés
    load_matches_cached,
    load_player_match_result,
    load_top_medals,
    load_top_teammates_cached,
    query_matches_with_friend,
)
from src.db.profiles import list_local_dbs
from src.ui import translate_pair_name, translate_playlist_name

if TYPE_CHECKING:
    pass

# Timezone Paris pour les conversions
PARIS_TZ_NAME = "Europe/Paris"


def db_cache_key(db_path: str) -> tuple[int, int] | None:
    """Retourne une signature stable de la DB pour invalider les caches.

    On utilise (mtime_ns, size) : rapide et suffisamment fiable pour détecter
    les mises à jour de la DB OpenSpartan.
    """
    try:
        st_ = os.stat(db_path)
    except OSError:
        return None
    return int(getattr(st_, "st_mtime_ns", int(st_.st_mtime * 1e9))), int(st_.st_size)


@st.cache_data(show_spinner=False, ttl=30)
def cached_list_local_dbs(_refresh_token: int = 0) -> list[str]:
    """Liste des DB locales (TTL court pour éviter un scan disque trop fréquent)."""
    return list_local_dbs()


@st.cache_data(show_spinner=False)
def cached_compute_sessions_db(
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
    include_firefight: bool,
    gap_minutes: int,
    friends_xuids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Compute sessions sur la base (cache) avec logique avancée (gap + coéquipiers).

    Si friends_xuids est fourni, mode legacy V3 : seuls les amis déclenchent une
    nouvelle session (randoms matchmaking ignorés).
    """
    friends_set = frozenset(friends_xuids) if friends_xuids else None

    # DuckDB v4 : lecture hybride (stocké si stable, sinon calcul à la volée)
    if _is_duckdb_v4_path(db_path):
        try:
            from datetime import datetime, timezone

            import duckdb

            conn = duckdb.connect(db_path, read_only=True)
            firefight_filter = "" if include_firefight else "AND is_firefight = FALSE"

            query = f"""
                SELECT
                    match_id,
                    start_time,
                    teammates_signature,
                    session_id,
                    session_label
                FROM match_stats
                WHERE start_time IS NOT NULL
                {firefight_filter}
                ORDER BY start_time ASC
            """
            df_pl = conn.execute(query).pl()
            conn.close()

            if df_pl.is_empty():
                return pd.DataFrame(
                    columns=["match_id", "start_time", "session_id", "session_label"]
                )

            # Cas A : tous ont session_id et sont >= 4h → utiliser stocké
            # Cas B : au moins un NULL ou récent → calcul complet à la volée
            stability_hours = SESSION_CONFIG.session_stability_hours
            threshold = datetime.now(timezone.utc).timestamp() - (stability_hours * 3600)
            has_null_session = df_pl.filter(pl.col("session_id").is_null()).height > 0
            df_pl = df_pl.with_columns(pl.col("start_time").dt.epoch(time_unit="s").alias("_ts"))
            has_recent = df_pl.filter(pl.col("_ts") > threshold).height > 0
            df_pl = df_pl.drop("_ts")

            if not has_null_session and not has_recent:
                # Cas A : tout stable, retourner tel quel
                return df_pl.select(
                    ["match_id", "start_time", "session_id", "session_label"]
                ).to_pandas()

            # Cas B : calcul complet à la volée
            df_pl = compute_sessions_with_context_polars(
                df_pl.select(["match_id", "start_time", "teammates_signature"]),
                gap_minutes=gap_minutes,
                teammates_column="teammates_signature",
                friends_xuids=friends_set,
            )
            return df_pl.select(
                ["match_id", "start_time", "session_id", "session_label"]
            ).to_pandas()

        except Exception as e:
            logger.warning(f"Erreur calcul sessions Polars, fallback Pandas: {e}")
            # Fallback sur l'ancienne méthode
            pass

    # Legacy SQLite ou fallback : utiliser Polars (load_df_optimized retourne maintenant Polars)
    df0_pl = load_df_optimized(db_path, xuid, db_key=db_key, include_firefight=include_firefight)
    if df0_pl.is_empty():
        return pd.DataFrame(columns=["match_id", "start_time", "session_id", "session_label"])

    df0_pl = mark_firefight(df0_pl)
    if (not include_firefight) and ("is_firefight" in df0_pl.columns):
        df0_pl = df0_pl.filter(~pl.col("is_firefight"))

    # Essayer d'utiliser la logique avancée si teammates_signature est disponible
    if "teammates_signature" in df0_pl.columns:
        try:
            df_sessions_pl = df0_pl.select(["match_id", "start_time", "teammates_signature"])
            df_sessions_pl = compute_sessions_with_context_polars(
                df_sessions_pl,
                gap_minutes=gap_minutes,
                teammates_column="teammates_signature",
                friends_xuids=friends_set,
            )
            # Fusionner les résultats avec le DataFrame original
            df_result_pl = df0_pl.join(
                df_sessions_pl.select(["match_id", "session_id", "session_label"]),
                on="match_id",
                how="left",
            )
            # Convertir en Pandas pour compatibilité UI (sera migré dans les tâches suivantes)
            return df_result_pl.to_pandas()
        except Exception:
            # Fallback sur logique simple (utilise directement Polars)
            df_result_pl = compute_sessions(df0_pl, gap_minutes=int(gap_minutes))
            # Convertir en Pandas pour compatibilité UI (sera migré dans les tâches suivantes)
            return df_result_pl.to_pandas()

    # Fallback sur logique simple (utilise directement Polars)
    df_result_pl = compute_sessions(df0_pl, gap_minutes=int(gap_minutes))
    # Convertir en Pandas pour compatibilité UI (sera migré dans les tâches suivantes)
    return df_result_pl.to_pandas()


@st.cache_data(show_spinner=False)
def cached_same_team_match_ids_with_friend(
    db_path: str,
    self_xuid: str,
    friend_xuid: str,
    db_key: tuple[int, int] | None,
) -> tuple[str, ...]:
    """Retourne les match_id (str) joués dans la même équipe avec un ami (cache).

    Utilise DuckDBRepository pour DuckDB v4, sinon fallback legacy.
    """
    _ = db_key
    # DuckDB v4 : utiliser le repository
    if _is_duckdb_v4_path(db_path):
        try:
            from src.data.repositories.duckdb_repo import DuckDBRepository

            repo = DuckDBRepository(db_path, str(self_xuid).strip())
            match_ids = repo.load_same_team_match_ids(str(friend_xuid).strip())
            return tuple(sorted(match_ids))
        except Exception:
            return ()
    rows = query_matches_with_friend(db_path, self_xuid, friend_xuid)
    ids = {str(r.match_id) for r in rows if getattr(r, "same_team", False)}
    return tuple(sorted(ids))


@st.cache_data(show_spinner=False)
def cached_query_matches_with_friend(
    db_path: str,
    self_xuid: str,
    friend_xuid: str,
    db_key: tuple[int, int] | None,
):
    """Requête les matchs joués avec un ami (cache).

    Utilise DuckDBRepository pour DuckDB v4, sinon fallback legacy.
    """
    _ = db_key
    # DuckDB v4 : utiliser le repository
    if _is_duckdb_v4_path(db_path):
        try:
            from src.data.repositories.duckdb_repo import DuckDBRepository

            repo = DuckDBRepository(db_path, str(self_xuid).strip())
            match_ids = repo.load_matches_with_teammate(str(friend_xuid).strip())
            # Convertir en format compatible avec l'ancien code
            # L'ancien code retourne une liste de MatchRow, mais ici on retourne juste les IDs
            # Les pages qui utilisent cette fonction devront adapter leur code
            return match_ids
        except Exception:
            return []
    return query_matches_with_friend(db_path, self_xuid, friend_xuid)


@st.cache_data(show_spinner=False)
def cached_load_player_match_result(
    db_path: str,
    match_id: str,
    xuid: str,
    db_key: tuple[int, int] | None,
):
    """Charge le résultat d'un match pour un joueur (cache).

    Utilise DuckDBRepository pour .duckdb, sinon fallback legacy.
    Note: DuckDB ne stocke pas les StatPerformances (expected/stddev).
    """
    # DuckDB v4 : utiliser le repository
    if _is_duckdb_v4_path(db_path):
        try:
            from src.data.repositories.duckdb_repo import DuckDBRepository

            repo = DuckDBRepository(db_path, str(xuid).strip())
            mmr_data = repo.load_match_mmr_batch([match_id])
            team_mmr = None
            enemy_mmr = None
            if match_id in mmr_data:
                team_mmr, enemy_mmr = mmr_data[match_id]
            # Toujours retourner un dict même si les MMR sont None
            # Les valeurs kills/deaths/assists seront enrichies depuis row dans match_view.py
            return {
                "team_id": None,  # Non disponible dans DuckDB v4
                "team_mmr": team_mmr,
                "enemy_mmr": enemy_mmr,
                "team_mmrs": None,  # Non disponible dans DuckDB v4
                "kills": {"count": None, "expected": None, "stddev": None},
                "deaths": {"count": None, "expected": None, "stddev": None},
                "assists": {"count": None, "expected": None, "stddev": None},
            }
        except Exception:
            return None

    # Legacy SQLite
    return load_player_match_result(db_path, match_id, xuid)


@st.cache_data(show_spinner=False)
def cached_load_match_medals_for_player(
    db_path: str,
    match_id: str,
    xuid: str,
    db_key: tuple[int, int] | None,
):
    """Charge les médailles d'un match pour un joueur (cache).

    Utilise DuckDBRepository pour .duckdb, sinon fallback legacy.
    """
    # DuckDB v4 : utiliser le repository
    if _is_duckdb_v4_path(db_path):
        try:
            from src.data.repositories.duckdb_repo import DuckDBRepository

            repo = DuckDBRepository(db_path, str(xuid).strip())
            return repo.load_match_medals(match_id)
        except Exception:
            return []

    # Legacy SQLite
    return load_match_medals_for_player(db_path, match_id, xuid)


@st.cache_data(show_spinner=False)
def cached_load_match_rosters(
    db_path: str,
    match_id: str,
    xuid: str,
    db_key: tuple[int, int] | None,
):
    """Charge les rosters d'un match (cache).

    Utilise DuckDBRepository pour DuckDB v4, sinon fallback legacy.
    """
    _ = db_key
    # DuckDB v4 : utiliser le repository
    if _is_duckdb_v4_path(db_path):
        try:
            from src.data.repositories.duckdb_repo import DuckDBRepository

            repo = DuckDBRepository(db_path, str(xuid).strip())
            return repo.load_match_rosters(match_id)
        except Exception:
            return None

    # Legacy SQLite
    return load_match_rosters(db_path, match_id, xuid)


@st.cache_data(show_spinner=False)
def cached_load_highlight_events_for_match(
    db_path: str,
    match_id: str,
    *,
    db_key: tuple[int, int] | None = None,
):
    """Charge les événements highlight d'un match (cache).

    Utilise DuckDBRepository pour .duckdb, sinon fallback legacy.
    """
    _ = db_key
    # DuckDB v4 : charger depuis la table highlight_events
    if _is_duckdb_v4_path(db_path):
        try:
            import duckdb

            conn = duckdb.connect(db_path, read_only=True)
            # Vérifier si la table existe (DuckDB utilise information_schema, pas sqlite_master)
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_name = 'highlight_events'"
            ).fetchall()
            if not tables:
                conn.close()
                return []

            result = conn.execute(
                """
                SELECT event_type, time_ms, xuid, gamertag, type_hint, raw_json
                FROM highlight_events
                WHERE match_id = ?
                ORDER BY time_ms ASC
                """,
                [match_id],
            ).fetchall()
            conn.close()

            import json

            events = []
            for row in result:
                event = {
                    "event_type": row[0],
                    "time_ms": row[1],
                    "xuid": row[2],
                    "gamertag": row[3],
                    "type_hint": row[4],
                }
                # Parser raw_json si présent
                if row[5]:
                    try:
                        extra = json.loads(row[5]) if isinstance(row[5], str) else {}
                        event.update(extra)
                    except Exception:
                        pass
                events.append(event)
            return events
        except Exception:
            return []

    # Legacy SQLite
    return load_highlight_events_for_match(db_path, match_id)


@st.cache_data(show_spinner=False)
def cached_load_match_player_gamertags(
    db_path: str,
    match_id: str,
    *,
    db_key: tuple[int, int] | None = None,
):
    """Charge les gamertags des joueurs d'un match (cache).

    Sprint Gamertag Roster Fix : Utilise DuckDBRepository.resolve_gamertags_batch
    pour obtenir des gamertags propres depuis match_participants/xuid_aliases.
    """
    _ = db_key
    # DuckDB v4 : utiliser le repository pour résolution centralisée
    if _is_duckdb_v4_path(db_path):
        try:
            import duckdb

            from src.data.repositories.duckdb_repo import DuckDBRepository

            conn = duckdb.connect(db_path, read_only=True)

            # Récupérer tous les XUIDs du match depuis highlight_events
            try:
                result = conn.execute(
                    """
                    SELECT DISTINCT xuid
                    FROM highlight_events
                    WHERE match_id = ?
                      AND xuid IS NOT NULL
                      AND xuid != ''
                    """,
                    [match_id],
                ).fetchall()
                xuids = [str(row[0]) for row in result if row[0]]
                conn.close()

                if not xuids:
                    return {}

                # Utiliser le repository pour la résolution centralisée
                # Note: on a besoin du xuid du joueur principal pour le repo,
                # mais on peut utiliser un XUID factice car resolve_gamertags_batch
                # ne dépend pas du xuid du repo
                repo = DuckDBRepository(db_path, xuids[0] if xuids else "")
                return {
                    xuid: gt
                    for xuid, gt in repo.resolve_gamertags_batch(xuids, match_id=match_id).items()
                    if gt
                }
            except Exception:
                conn.close()
                return {}
        except Exception:
            return {}

    # Legacy SQLite
    return load_match_player_gamertags(db_path, match_id)


@st.cache_data(show_spinner=False)
def cached_load_top_medals(
    db_path: str,
    xuid: str,
    match_ids: tuple[str, ...],
    top_n: int | None,
    db_key: tuple[int, int] | None,
):
    """Charge les top médailles (cache).

    Utilise DuckDBRepository pour les bases .duckdb, sinon fallback legacy.
    """
    # DuckDB v4 : utiliser le repository
    if _is_duckdb_v4_path(db_path):
        try:
            from src.data.repositories.duckdb_repo import DuckDBRepository

            repo = DuckDBRepository(db_path, str(xuid).strip())
            return repo.load_top_medals(
                list(match_ids),
                top_n=(int(top_n) if top_n is not None else None),
            )
        except Exception:
            return []

    # Legacy SQLite
    return load_top_medals(
        db_path,
        xuid,
        list(match_ids),
        top_n=(int(top_n) if top_n is not None else None),
    )


def top_medals_smart(
    db_path: str,
    xuid: str,
    match_ids: list[str],
    *,
    top_n: int | None,
    db_key: tuple[int, int] | None,
):
    """Charge les top médailles avec gestion intelligente du cache.

    Évite de stocker d'immenses tuples en cache pour les grandes listes.
    Utilise DuckDBRepository pour les bases .duckdb.
    """
    # DuckDB v4 : utiliser le repository directement (pas de cache pour les grandes listes)
    if _is_duckdb_v4_path(db_path):
        if len(match_ids) > 1500:
            try:
                from src.data.repositories.duckdb_repo import DuckDBRepository

                repo = DuckDBRepository(db_path, str(xuid).strip())
                return repo.load_top_medals(match_ids, top_n=top_n)
            except Exception:
                return []
        return cached_load_top_medals(db_path, xuid, tuple(match_ids), top_n, db_key=db_key)

    # Legacy SQLite
    if len(match_ids) > 1500:
        return load_top_medals(db_path, xuid, match_ids, top_n=top_n)
    return cached_load_top_medals(db_path, xuid, tuple(match_ids), top_n, db_key=db_key)


@st.cache_data(show_spinner=False)
def cached_friend_matches_df(
    db_path: str,
    self_xuid: str,
    friend_xuid: str,
    same_team_only: bool,
    db_key: tuple[int, int] | None,
) -> pd.DataFrame:
    """Retourne un DataFrame des matchs joués avec un ami (cache)."""
    rows = cached_query_matches_with_friend(db_path, self_xuid, friend_xuid, db_key=db_key)
    if same_team_only:
        rows = [r for r in rows if r.same_team]
    if not rows:
        return pd.DataFrame(
            columns=[
                "match_id",
                "start_time",
                "playlist_name",
                "pair_name",
                "same_team",
                "my_team_id",
                "my_outcome",
                "friend_team_id",
                "friend_outcome",
            ]
        )

    dfr = pd.DataFrame(
        [
            {
                "match_id": r.match_id,
                "start_time": r.start_time,
                "playlist_name": translate_playlist_name(r.playlist_name),
                "pair_name": translate_pair_name(r.pair_name),
                "same_team": r.same_team,
                "my_team_id": r.my_team_id,
                "my_outcome": r.my_outcome,
                "friend_team_id": r.friend_team_id,
                "friend_outcome": r.friend_outcome,
            }
            for r in rows
        ]
    )
    dfr["start_time"] = (
        pd.to_datetime(dfr["start_time"], utc=True)
        .dt.tz_convert(PARIS_TZ_NAME)
        .dt.tz_localize(None)
    )
    return dfr.sort_values("start_time", ascending=False)


def clear_app_caches() -> None:
    """Vide les caches Streamlit (utile si DB/alias/csv changent en dehors de l'app)."""
    import contextlib

    with contextlib.suppress(Exception):
        st.cache_data.clear()


@st.cache_data(show_spinner=False)
def cached_list_other_xuids(
    db_path: str, self_xuid: str, db_key: tuple[int, int] | None = None, limit: int = 500
) -> list[str]:
    """Version cachée de list_other_player_xuids.

    DuckDB v4 utilise xuid_aliases ou teammates_aggregate.
    """
    # DuckDB v4 : utiliser la table xuid_aliases ou teammates
    if _is_duckdb_v4_path(db_path):
        try:
            import duckdb

            conn = duckdb.connect(db_path, read_only=True)
            # Essayer depuis xuid_aliases (tous les joueurs rencontrés)
            try:
                result = conn.execute(
                    f"SELECT DISTINCT xuid FROM xuid_aliases WHERE xuid != ? LIMIT {limit}",
                    [self_xuid],
                ).fetchall()
                if result:
                    conn.close()
                    return [str(row[0]) for row in result if row[0]]
            except Exception:
                pass
            conn.close()
            return []
        except Exception:
            return []
    return list_other_player_xuids(db_path, self_xuid, limit)


@st.cache_data(show_spinner=False)
def cached_list_top_teammates(
    db_path: str, self_xuid: str, db_key: tuple[int, int] | None = None, limit: int = 20
) -> list[tuple[str, int]]:
    """Version cachée de list_top_teammates.

    Utilise DuckDBRepository pour .duckdb, sinon TeammatesAggregate (cache DB),
    sinon fallback sur la requête JSON lente (list_top_teammates).
    """
    # DuckDB v4 : utiliser le repository
    if _is_duckdb_v4_path(db_path):
        try:
            from src.data.repositories.duckdb_repo import DuckDBRepository

            repo = DuckDBRepository(db_path, str(self_xuid).strip())
            return repo.list_top_teammates(limit=limit)
        except Exception:
            return []

    # Legacy SQLite : essayer d'abord le cache optimisé (TeammatesAggregate)
    cached_results = load_top_teammates_cached(db_path, self_xuid, limit)
    if cached_results:
        # Convertir le format (xuid, gamertag, matches, wins, losses) -> (xuid, matches)
        return [(row[0], row[2]) for row in cached_results]

    # Fallback sur la requête JSON (lente mais complète)
    return list_top_teammates(db_path, self_xuid, limit)


# =============================================================================
# Nouvelles fonctions utilisant les tables de cache optimisées
# =============================================================================


@st.cache_data(show_spinner=False)
def cached_has_cache_tables(db_path: str, db_key: tuple[int, int] | None = None) -> bool:
    """Vérifie si les tables de cache existent.

    DuckDB v4 considéré comme ayant toujours les tables de cache.
    """
    _ = db_key
    # DuckDB v4 : toujours considéré comme ayant le cache
    if _is_duckdb_v4_path(db_path):
        return True
    return has_cache_tables(db_path)


@st.cache_data(show_spinner=False)
def cached_get_cache_stats(db_path: str, xuid: str, db_key: tuple[int, int] | None = None) -> dict:
    """Retourne les stats du cache DB pour un joueur.

    DuckDB v4 retourne des stats depuis le repository.
    """
    _ = db_key
    # DuckDB v4 : utiliser le repository
    if _is_duckdb_v4_path(db_path):
        try:
            from src.data.repositories.duckdb_repo import DuckDBRepository

            repo = DuckDBRepository(db_path, str(xuid).strip())
            storage = repo.get_storage_info()
            return {
                "has_cache": True,
                "match_count": storage.get("total_matches", 0),
                "sessions_count": storage.get("sessions_count", 0),
            }
        except Exception:
            return {"has_cache": True}
    return get_cache_stats(db_path, xuid)


def _is_duckdb_v4_path(db_path: str) -> bool:
    """Détecte si le chemin est une DB joueur DuckDB v4."""
    if not db_path:
        return False
    return db_path.endswith(".duckdb") or db_path.endswith("stats.duckdb")


def _load_matches_duckdb_v4(db_path: str, include_firefight: bool = True) -> list:
    """Charge les matchs depuis une DB DuckDB v4."""
    try:
        from src.data.repositories.duckdb_repo import DuckDBRepository

        # Le XUID n'est pas nécessaire pour DuckDB v4 (un joueur par DB)
        # On utilise un placeholder
        repo = DuckDBRepository(db_path, xuid="", read_only=True)
        try:
            matches = repo.load_matches(include_firefight=include_firefight)
            return matches
        finally:
            repo.close()
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def load_df_optimized(
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None = None,
    include_firefight: bool = True,
    cache_buster: int = 0,
) -> pl.DataFrame:
    """Charge les matchs avec fallback intelligent.

    Supporte:
    - DuckDB v4: data/players/{gamertag}/stats.duckdb
    - Legacy SQLite: MatchCache puis MatchStats

    Args:
        db_path: Chemin vers la DB.
        xuid: XUID du joueur (ignoré pour DuckDB v4).
        db_key: Clé de cache (mtime, size).
        include_firefight: Inclure les matchs PvE.
        cache_buster: Token pour forcer l'invalidation du cache.

    Returns:
        DataFrame Polars enrichi avec toutes les colonnes calculées.
    """
    _ = db_key  # Utilisé pour invalidation du cache Streamlit
    _ = cache_buster  # Utilisé pour forcer le rechargement après sync

    matches = []

    # Détecter le type de DB
    if _is_duckdb_v4_path(db_path):
        # DuckDB v4: utiliser le repository dédié
        matches = _load_matches_duckdb_v4(db_path, include_firefight=include_firefight)
    else:
        # Legacy SQLite: tenter le cache optimisé d'abord
        matches = load_matches_cached(db_path, xuid, include_firefight=include_firefight)

        if not matches:
            # Fallback sur loader original
            matches = load_matches(db_path, xuid)

    if not matches:
        return pl.DataFrame()

    # Construire le DataFrame Polars directement
    df = pl.DataFrame(
        {
            "match_id": [m.match_id for m in matches],
            "start_time": [m.start_time for m in matches],
            "map_id": [m.map_id for m in matches],
            "map_name": [m.map_name for m in matches],
            "playlist_id": [m.playlist_id for m in matches],
            "playlist_name": [m.playlist_name for m in matches],
            "pair_id": [m.map_mode_pair_id for m in matches],
            "pair_name": [m.map_mode_pair_name for m in matches],
            "game_variant_id": [m.game_variant_id for m in matches],
            "game_variant_name": [m.game_variant_name for m in matches],
            "outcome": [m.outcome for m in matches],
            "kda": [m.kda for m in matches],
            "my_team_score": [m.my_team_score for m in matches],
            "enemy_team_score": [m.enemy_team_score for m in matches],
            "max_killing_spree": [m.max_killing_spree for m in matches],
            "headshot_kills": [m.headshot_kills for m in matches],
            "average_life_seconds": [m.average_life_seconds for m in matches],
            "time_played_seconds": [m.time_played_seconds for m in matches],
            "kills": [m.kills for m in matches],
            "deaths": [m.deaths for m in matches],
            "assists": [m.assists for m in matches],
            "accuracy": [m.accuracy for m in matches],
            "ratio": [m.ratio for m in matches],
            "team_mmr": [m.team_mmr for m in matches],
            "enemy_mmr": [m.enemy_mmr for m in matches],
        }
    )

    # Conversions standard avec Polars
    # Convertir start_time en datetime UTC puis en timezone Paris
    # Gérer les deux cas : start_time peut être déjà datetime (DuckDB) ou string (legacy)
    start_time_dtype = df.schema.get("start_time")
    if start_time_dtype in (pl.Datetime, pl.Datetime("us"), pl.Datetime("ns"), pl.Datetime("ms")):
        # Déjà un datetime : gérer timezone-aware et naïf
        # Polars convert_time_zone peut échouer sur datetime naïf selon la version
        try:
            # Essayer de convertir directement (fonctionne si timezone-aware)
            df = df.with_columns(
                pl.col("start_time")
                .dt.convert_time_zone(PARIS_TZ_NAME)
                .dt.replace_time_zone(None)
                .alias("start_time")
            )
        except Exception:
            # Si échec, c'est probablement un datetime naïf : ajouter UTC puis convertir
            df = df.with_columns(
                pl.col("start_time")
                .dt.replace_time_zone("UTC")
                .dt.convert_time_zone(PARIS_TZ_NAME)
                .dt.replace_time_zone(None)
                .alias("start_time")
            )
    else:
        # String : parser puis convertir la timezone
        df = df.with_columns(
            pl.col("start_time")
            .str.to_datetime(time_zone="UTC")
            .dt.convert_time_zone(PARIS_TZ_NAME)
            .dt.replace_time_zone(None)
            .alias("start_time")
        )

    # Extraire la date
    df = df.with_columns(pl.col("start_time").dt.date().alias("date"))

    # Stats par minute
    df = df.with_columns(
        (pl.col("time_played_seconds").cast(pl.Float64) / 60.0)
        .clip(lower_bound=0.0)
        .alias("minutes")
    )

    df = df.with_columns(
        [
            (pl.col("kills").cast(pl.Float64) / pl.col("minutes")).alias("kills_per_min"),
            (pl.col("deaths").cast(pl.Float64) / pl.col("minutes")).alias("deaths_per_min"),
            (pl.col("assists").cast(pl.Float64) / pl.col("minutes")).alias("assists_per_min"),
        ]
    )

    # Supprimer la colonne temporaire minutes
    df = df.drop("minutes")

    return df


@st.cache_data(show_spinner=False)
def cached_load_friends(
    db_path: str,
    owner_xuid: str,
    db_key: tuple[int, int] | None = None,
) -> list[dict]:
    """Charge la liste des amis depuis la table Friends.

    DuckDB v4 n'a pas de table Friends, retourne liste vide.
    """
    _ = db_key
    # DuckDB v4 : pas de table Friends
    if _is_duckdb_v4_path(db_path):
        return []
    return load_friends(db_path, owner_xuid)


@st.cache_data(show_spinner=False)
def cached_load_top_teammates_optimized(
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None = None,
    limit: int = 20,
) -> list[tuple[str, str | None, int, int, int]]:
    """Charge les top coéquipiers depuis TeammatesAggregate (optimisé).

    Fallback sur l'ancienne méthode si le cache n'existe pas.

    Returns:
        Liste de tuples (xuid, gamertag, matches, wins, losses)
    """
    _ = db_key

    # Tenter le cache d'abord
    result = load_top_teammates_cached(db_path, xuid, limit)

    if result:
        return result

    # Fallback sur l'ancienne méthode (format différent)
    old_result = list_top_teammates(db_path, xuid, limit)
    # Convertir (xuid, count) → (xuid, None, count, 0, 0)
    return [(x, None, c, 0, 0) for x, c in old_result]


@st.cache_data(show_spinner=False)
def cached_get_match_session_info(
    db_path: str,
    match_id: str,
    db_key: tuple[int, int] | None = None,
) -> dict | None:
    """Récupère les infos de session pour un match spécifique.

    DuckDB v4 ne stocke pas les sessions de la même manière.
    """
    _ = db_key
    # DuckDB v4 : pas d'info session disponible de cette façon
    if _is_duckdb_v4_path(db_path):
        return None
    return get_match_session_info(db_path, match_id)


# =============================================================================
# Fonctions utilisant l'architecture hybride (Phase 2+)
# =============================================================================


def _get_repository_mode() -> str:
    """Récupère le mode de repository depuis les settings."""
    try:
        settings = st.session_state.get("app_settings")
        if settings and hasattr(settings, "repository_mode"):
            return str(settings.repository_mode).lower()
    except Exception:
        pass
    return "legacy"


def _is_duckdb_analytics_enabled() -> bool:
    """Vérifie si les analytics DuckDB sont activées."""
    try:
        settings = st.session_state.get("app_settings")
        if settings and hasattr(settings, "enable_duckdb_analytics"):
            return bool(settings.enable_duckdb_analytics)
    except Exception:
        pass
    return False


@st.cache_data(show_spinner=False)
def load_df_hybrid(
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None = None,
    include_firefight: bool = True,
) -> pl.DataFrame:
    """Charge les matchs via le système hybride (Parquet + DuckDB).

    Utilise le DataRepository configuré selon le mode dans les settings.
    Fallback automatique sur legacy si le mode hybride échoue.

    Args:
        db_path: Chemin vers la DB.
        xuid: XUID du joueur.
        db_key: Clé de cache (mtime, size).
        include_firefight: Inclure les matchs PvE.

    Returns:
        DataFrame Polars enrichi avec toutes les colonnes calculées.
    """
    _ = db_key  # Utilisé pour invalidation du cache Streamlit

    try:
        from src.data.integration import get_repository_mode_from_settings, load_matches_df

        mode = get_repository_mode_from_settings()

        # Utiliser le nouveau système (retourne encore Pandas pour l'instant)
        df_pd = load_matches_df(
            db_path,
            xuid,
            include_firefight=include_firefight,
            mode=mode,
        )

        if not df_pd.empty:
            # Convertir en Polars pour cohérence
            return pl.from_pandas(df_pd)

        # Fallback sur legacy si vide (pas de données Parquet)
        return load_df_optimized(db_path, xuid, db_key=db_key, include_firefight=include_firefight)

    except ImportError:
        # Module d'intégration non disponible, utiliser legacy
        return load_df_optimized(db_path, xuid, db_key=db_key, include_firefight=include_firefight)
    except Exception:
        # Erreur inattendue, fallback sur legacy
        return load_df_optimized(db_path, xuid, db_key=db_key, include_firefight=include_firefight)


@st.cache_data(show_spinner=False, ttl=300)
def cached_get_global_stats_duckdb(
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None = None,
) -> dict | None:
    """Récupère les stats globales via DuckDB (haute performance).

    Utilise le QueryEngine pour des agrégations ultra-rapides sur Parquet.
    Retourne None si DuckDB n'est pas disponible ou pas de données.
    """
    if not _is_duckdb_analytics_enabled():
        return None

    try:
        from src.data.integration import check_hybrid_available, get_analytics_for_ui

        if not check_hybrid_available(db_path, xuid):
            return None

        engine, analytics = get_analytics_for_ui(db_path, xuid)
        try:
            stats = analytics.get_global_stats()
            return {
                "total_matches": stats.total_matches,
                "total_kills": stats.total_kills,
                "total_deaths": stats.total_deaths,
                "total_assists": stats.total_assists,
                "total_time_hours": stats.total_time_hours,
                "avg_kda": stats.avg_kda,
                "avg_accuracy": stats.avg_accuracy,
                "win_rate": stats.win_rate,
                "loss_rate": stats.loss_rate,
                "wins": stats.wins,
                "losses": stats.losses,
            }
        finally:
            engine.close()
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=300)
def cached_get_kda_trend_duckdb(
    db_path: str,
    xuid: str,
    window_size: int = 20,
    last_n: int = 500,
    db_key: tuple[int, int] | None = None,
) -> list[dict] | None:
    """Récupère l'évolution du KDA via DuckDB (haute performance).

    Utilise le TrendAnalyzer pour calculer des moyennes mobiles
    ultra-rapidement sur les fichiers Parquet.
    """
    if not _is_duckdb_analytics_enabled():
        return None

    try:
        from src.data.integration import check_hybrid_available, get_trends_for_ui

        if not check_hybrid_available(db_path, xuid):
            return None

        engine, trends = get_trends_for_ui(db_path, xuid)
        try:
            return trends.get_rolling_kda(window_size=window_size, last_n=last_n)
        finally:
            engine.close()
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=300)
def cached_get_performance_by_map_duckdb(
    db_path: str,
    xuid: str,
    min_matches: int = 3,
    db_key: tuple[int, int] | None = None,
) -> list[dict] | None:
    """Récupère les performances par carte via DuckDB."""
    if not _is_duckdb_analytics_enabled():
        return None

    try:
        from src.data.integration import check_hybrid_available, get_analytics_for_ui

        if not check_hybrid_available(db_path, xuid):
            return None

        engine, analytics = get_analytics_for_ui(db_path, xuid)
        try:
            return analytics.get_performance_by_map(min_matches=min_matches)
        finally:
            engine.close()
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=60)
def cached_get_migration_status(
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None = None,
) -> dict:
    """Récupère l'état de la migration vers le système hybride."""
    try:
        from src.data.integration import get_migration_status

        return get_migration_status(db_path, xuid)
    except Exception as e:
        return {
            "error": str(e),
            "legacy_count": 0,
            "hybrid_count": 0,
            "progress_percent": 0,
            "is_complete": False,
        }


# =============================================================================
# Lazy Loading et Pagination (Sprint 4.3)
# =============================================================================


@st.cache_data(show_spinner=False, ttl=300)
def cached_load_recent_matches(
    player_db_path: str,
    xuid: str,
    limit: int = 50,
    db_key: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """Charge les N matchs les plus récents via DuckDB (lazy loading).

    Optimisé pour le chargement initial rapide de l'UI.
    Utilise le DuckDBRepository si disponible, sinon fallback.

    Args:
        player_db_path: Chemin vers stats.duckdb du joueur.
        xuid: XUID du joueur.
        limit: Nombre de matchs à charger.
        db_key: Clé de cache pour invalidation.

    Returns:
        DataFrame des matchs récents.
    """
    _ = db_key  # Pour invalidation du cache Streamlit

    try:
        from pathlib import Path

        from src.data.repositories.duckdb_repo import DuckDBRepository

        db_path = Path(player_db_path)
        if not db_path.exists():
            return pd.DataFrame()

        repo = DuckDBRepository(db_path, xuid)
        try:
            matches = repo.load_recent_matches(limit=limit)
        finally:
            repo.close()

        if not matches:
            return pd.DataFrame()

        df = pd.DataFrame(
            {
                "match_id": [m.match_id for m in matches],
                "start_time": [m.start_time for m in matches],
                "map_id": [m.map_id for m in matches],
                "map_name": [m.map_name for m in matches],
                "playlist_id": [m.playlist_id for m in matches],
                "playlist_name": [m.playlist_name for m in matches],
                "pair_id": [m.map_mode_pair_id for m in matches],
                "pair_name": [m.map_mode_pair_name for m in matches],
                "game_variant_id": [m.game_variant_id for m in matches],
                "game_variant_name": [m.game_variant_name for m in matches],
                "outcome": [m.outcome for m in matches],
                "kda": [m.kda for m in matches],
                "my_team_score": [m.my_team_score for m in matches],
                "enemy_team_score": [m.enemy_team_score for m in matches],
                "max_killing_spree": [m.max_killing_spree for m in matches],
                "headshot_kills": [m.headshot_kills for m in matches],
                "average_life_seconds": [m.average_life_seconds for m in matches],
                "time_played_seconds": [m.time_played_seconds for m in matches],
                "kills": [m.kills for m in matches],
                "deaths": [m.deaths for m in matches],
                "assists": [m.assists for m in matches],
                "accuracy": [m.accuracy for m in matches],
                "ratio": [m.ratio for m in matches],
                "team_mmr": [m.team_mmr for m in matches],
                "enemy_mmr": [m.enemy_mmr for m in matches],
            }
        )

        # Conversions standard
        df["start_time"] = (
            pd.to_datetime(df["start_time"], utc=True)
            .dt.tz_convert(PARIS_TZ_NAME)
            .dt.tz_localize(None)
        )
        df["date"] = df["start_time"].dt.date

        return df

    except ImportError:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=300)
def cached_load_matches_paginated(
    player_db_path: str,
    xuid: str,
    page: int = 1,
    page_size: int = 50,
    db_key: tuple[int, int] | None = None,
) -> tuple[pd.DataFrame, int]:
    """Charge les matchs avec pagination via DuckDB.

    Args:
        player_db_path: Chemin vers stats.duckdb du joueur.
        xuid: XUID du joueur.
        page: Numéro de page (1-indexed).
        page_size: Nombre de matchs par page.
        db_key: Clé de cache pour invalidation.

    Returns:
        Tuple (DataFrame des matchs, nombre total de pages).
    """
    _ = db_key

    try:
        from pathlib import Path

        from src.data.repositories.duckdb_repo import DuckDBRepository

        db_path = Path(player_db_path)
        if not db_path.exists():
            return pd.DataFrame(), 1

        repo = DuckDBRepository(db_path, xuid)
        try:
            matches, total_pages = repo.load_matches_paginated(
                page=page,
                page_size=page_size,
                order_desc=True,
            )
        finally:
            repo.close()

        if not matches:
            return pd.DataFrame(), total_pages

        df = pd.DataFrame(
            {
                "match_id": [m.match_id for m in matches],
                "start_time": [m.start_time for m in matches],
                "map_id": [m.map_id for m in matches],
                "map_name": [m.map_name for m in matches],
                "playlist_id": [m.playlist_id for m in matches],
                "playlist_name": [m.playlist_name for m in matches],
                "pair_id": [m.map_mode_pair_id for m in matches],
                "pair_name": [m.map_mode_pair_name for m in matches],
                "game_variant_id": [m.game_variant_id for m in matches],
                "game_variant_name": [m.game_variant_name for m in matches],
                "outcome": [m.outcome for m in matches],
                "kda": [m.kda for m in matches],
                "my_team_score": [m.my_team_score for m in matches],
                "enemy_team_score": [m.enemy_team_score for m in matches],
                "max_killing_spree": [m.max_killing_spree for m in matches],
                "headshot_kills": [m.headshot_kills for m in matches],
                "average_life_seconds": [m.average_life_seconds for m in matches],
                "time_played_seconds": [m.time_played_seconds for m in matches],
                "kills": [m.kills for m in matches],
                "deaths": [m.deaths for m in matches],
                "assists": [m.assists for m in matches],
                "accuracy": [m.accuracy for m in matches],
                "ratio": [m.ratio for m in matches],
                "team_mmr": [m.team_mmr for m in matches],
                "enemy_mmr": [m.enemy_mmr for m in matches],
            }
        )

        # Conversions standard
        df["start_time"] = (
            pd.to_datetime(df["start_time"], utc=True)
            .dt.tz_convert(PARIS_TZ_NAME)
            .dt.tz_localize(None)
        )
        df["date"] = df["start_time"].dt.date

        return df, total_pages

    except ImportError:
        return pd.DataFrame(), 1
    except Exception:
        return pd.DataFrame(), 1


@st.cache_data(show_spinner=False, ttl=600)
def cached_get_match_count_duckdb(
    player_db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None = None,
) -> int:
    """Récupère le nombre total de matchs via DuckDB.

    Args:
        player_db_path: Chemin vers stats.duckdb du joueur.
        xuid: XUID du joueur.
        db_key: Clé de cache pour invalidation.

    Returns:
        Nombre total de matchs.
    """
    _ = db_key

    try:
        from pathlib import Path

        from src.data.repositories.duckdb_repo import DuckDBRepository

        db_path = Path(player_db_path)
        if not db_path.exists():
            return 0

        repo = DuckDBRepository(db_path, xuid)
        try:
            count = repo.get_match_count()
            return count
        finally:
            repo.close()

    except Exception:
        return 0
