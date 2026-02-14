"""Fonctions de cache Streamlit — Transformations, analytics et pagination.

Ce module regroupe les fonctions @st.cache_data qui effectuent
des calculs de sessions, transformations, agrégations DuckDB analytics,
et pagination.

Extrait de cache.py lors du Sprint 17 (découpage <800L).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl
import streamlit as st

from src.analysis import compute_sessions, compute_sessions_with_context_polars, mark_firefight
from src.config import SESSION_CONFIG
from src.ui import translate_pair_name, translate_playlist_name
from src.ui.cache_loaders import (
    PARIS_TZ_NAME,
    _is_duckdb_v4_path,
    cached_query_matches_with_friend,
    load_df_optimized,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@st.cache_data(show_spinner=False)
def cached_compute_sessions_db(
    db_path: str,
    xuid: str,
    db_key: tuple[int, int] | None,
    include_firefight: bool,
    gap_minutes: int,
    friends_xuids: tuple[str, ...] | None = None,
) -> pl.DataFrame:
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
                return pl.DataFrame(
                    schema={
                        "match_id": pl.Utf8,
                        "start_time": pl.Datetime,
                        "session_id": pl.Utf8,
                        "session_label": pl.Utf8,
                    }
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
                return df_pl.select(["match_id", "start_time", "session_id", "session_label"])

            # Cas B : calcul complet à la volée
            df_pl = compute_sessions_with_context_polars(
                df_pl.select(["match_id", "start_time", "teammates_signature"]),
                gap_minutes=gap_minutes,
                teammates_column="teammates_signature",
                friends_xuids=friends_set,
            )
            return df_pl.select(["match_id", "start_time", "session_id", "session_label"])

        except Exception as e:
            logger.warning(f"Erreur calcul sessions Polars, fallback Pandas: {e}")
            # Fallback sur l'ancienne méthode
            pass

    # Legacy SQLite ou fallback : utiliser Polars (load_df_optimized retourne maintenant Polars)
    df0_pl = load_df_optimized(db_path, xuid, db_key=db_key, include_firefight=include_firefight)
    if df0_pl.is_empty():
        return pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "start_time": pl.Datetime,
                "session_id": pl.Utf8,
                "session_label": pl.Utf8,
            }
        )

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
            # Convertir en Polars
            return df_result_pl
        except Exception:
            # Fallback sur logique simple (utilise directement Polars)
            df_result_pl = compute_sessions(df0_pl, gap_minutes=int(gap_minutes))
            return df_result_pl

    # Fallback sur logique simple (utilise directement Polars)
    df_result_pl = compute_sessions(df0_pl, gap_minutes=int(gap_minutes))
    return df_result_pl


@st.cache_data(show_spinner=False)
def cached_friend_matches_df(
    db_path: str,
    self_xuid: str,
    friend_xuid: str,
    same_team_only: bool,
    db_key: tuple[int, int] | None,
) -> pl.DataFrame:
    """Retourne un DataFrame des matchs joués avec un ami (cache)."""
    rows = cached_query_matches_with_friend(db_path, self_xuid, friend_xuid, db_key=db_key)
    if same_team_only:
        rows = [r for r in rows if r.same_team]
    if not rows:
        return pl.DataFrame(
            schema={
                "match_id": pl.Utf8,
                "start_time": pl.Datetime,
                "playlist_name": pl.Utf8,
                "pair_name": pl.Utf8,
                "same_team": pl.Boolean,
                "my_team_id": pl.Int64,
                "my_outcome": pl.Utf8,
                "friend_team_id": pl.Int64,
                "friend_outcome": pl.Utf8,
            }
        )

    dfr = pl.DataFrame(
        {
            "match_id": [r.match_id for r in rows],
            "start_time": [r.start_time for r in rows],
            "playlist_name": [translate_playlist_name(r.playlist_name) for r in rows],
            "pair_name": [translate_pair_name(r.pair_name) for r in rows],
            "same_team": [r.same_team for r in rows],
            "my_team_id": [r.my_team_id for r in rows],
            "my_outcome": [r.my_outcome for r in rows],
            "friend_team_id": [r.friend_team_id for r in rows],
            "friend_outcome": [r.friend_outcome for r in rows],
        }
    )
    # Conversion timezone : UTC → Paris → naïf
    try:
        dfr = dfr.with_columns(
            pl.col("start_time")
            .cast(pl.Datetime("us", "UTC"))
            .dt.convert_time_zone(PARIS_TZ_NAME)
            .dt.replace_time_zone(None)
        )
    except Exception:
        import contextlib

        with contextlib.suppress(Exception):
            dfr = dfr.with_columns(
                pl.col("start_time")
                .dt.replace_time_zone("UTC")
                .dt.convert_time_zone(PARIS_TZ_NAME)
                .dt.replace_time_zone(None)
            )
    return dfr.sort("start_time", descending=True)


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
    return "duckdb"


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

        if isinstance(df_pd, pl.DataFrame):
            if not df_pd.is_empty():
                return df_pd
        elif hasattr(df_pd, "empty") and not df_pd.empty:
            # Pandas DataFrame — convertir en Polars (bridge résiduel, mode intégration legacy)
            logger.debug("load_df_hybrid: conversion Pandas→Polars (mode intégration)")
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
) -> pl.DataFrame:
    """Charge les N matchs les plus récents via DuckDB (lazy loading).

    Optimisé pour le chargement initial rapide de l'UI.
    Utilise le DuckDBRepository si disponible, sinon fallback.

    Args:
        player_db_path: Chemin vers stats.duckdb du joueur.
        xuid: XUID du joueur.
        limit: Nombre de matchs à charger.
        db_key: Clé de cache pour invalidation.

    Returns:
        DataFrame Polars des matchs récents.
    """
    _ = db_key  # Pour invalidation du cache Streamlit

    try:
        from pathlib import Path

        from src.data.repositories.duckdb_repo import DuckDBRepository

        db_path = Path(player_db_path)
        if not db_path.exists():
            return pl.DataFrame()

        repo = DuckDBRepository(db_path, xuid)
        try:
            matches = repo.load_recent_matches(limit=limit)
        finally:
            repo.close()

        if not matches:
            return pl.DataFrame()

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

        # Conversion timezone : UTC → Paris → naïf + colonne date
        try:
            df = df.with_columns(
                pl.col("start_time")
                .cast(pl.Datetime("us", "UTC"))
                .dt.convert_time_zone(PARIS_TZ_NAME)
                .dt.replace_time_zone(None)
            )
        except Exception:
            import contextlib

            with contextlib.suppress(Exception):
                df = df.with_columns(
                    pl.col("start_time")
                    .dt.replace_time_zone("UTC")
                    .dt.convert_time_zone(PARIS_TZ_NAME)
                    .dt.replace_time_zone(None)
                )
        df = df.with_columns(pl.col("start_time").cast(pl.Date).alias("date"))

        return df

    except ImportError:
        return pl.DataFrame()
    except Exception:
        return pl.DataFrame()


@st.cache_data(show_spinner=False, ttl=300)
def cached_load_matches_paginated(
    player_db_path: str,
    xuid: str,
    page: int = 1,
    page_size: int = 50,
    db_key: tuple[int, int] | None = None,
) -> tuple[pl.DataFrame, int]:
    """Charge les matchs avec pagination via DuckDB.

    Args:
        player_db_path: Chemin vers stats.duckdb du joueur.
        xuid: XUID du joueur.
        page: Numéro de page (1-indexed).
        page_size: Nombre de matchs par page.
        db_key: Clé de cache pour invalidation.

    Returns:
        Tuple (DataFrame Polars des matchs, nombre total de pages).
    """
    _ = db_key

    try:
        from pathlib import Path

        from src.data.repositories.duckdb_repo import DuckDBRepository

        db_path = Path(player_db_path)
        if not db_path.exists():
            return pl.DataFrame(), 1

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
            return pl.DataFrame(), total_pages

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

        # Conversion timezone : UTC → Paris → naïf + colonne date
        try:
            df = df.with_columns(
                pl.col("start_time")
                .cast(pl.Datetime("us", "UTC"))
                .dt.convert_time_zone(PARIS_TZ_NAME)
                .dt.replace_time_zone(None)
            )
        except Exception:
            import contextlib

            with contextlib.suppress(Exception):
                df = df.with_columns(
                    pl.col("start_time")
                    .dt.replace_time_zone("UTC")
                    .dt.convert_time_zone(PARIS_TZ_NAME)
                    .dt.replace_time_zone(None)
                )
        df = df.with_columns(pl.col("start_time").cast(pl.Date).alias("date"))

        return df, total_pages

    except ImportError:
        return pl.DataFrame(), 1
    except Exception:
        return pl.DataFrame(), 1


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
