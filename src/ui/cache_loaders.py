"""Fonctions de cache Streamlit — Chargement atomique depuis DuckDB.

Ce module regroupe les fonctions @st.cache_data qui effectuent
des lectures unitaires depuis la base DuckDB (matchs, médailles,
rosters, coéquipiers, highlights, etc.).

Extrait de cache.py lors du Sprint 17 (découpage <800L).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import polars as pl
import streamlit as st

from src.utils.profiles import list_local_dbs

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Timezone Paris pour les conversions
PARIS_TZ_NAME = "Europe/Paris"

# ─── Constantes de projection par page (Sprint 19 — tâche 19.3) ────────────
# Colonnes effectivement utilisées par les pages principales.
# Permet de réduire la mémoire en ne chargeant que le nécessaire.
# Note : game_variant_id, game_variant_name, team_id ne sont utilisés par aucune
# page hot-path et sont exclus du set commun.

COLUMNS_COMMON: list[str] = [
    "match_id",
    "start_time",
    "map_id",
    "map_name",
    "playlist_id",
    "playlist_name",
    "pair_id",
    "pair_name",
    "outcome",
    "kda",
    "kills",
    "deaths",
    "assists",
    "accuracy",
    "average_life_seconds",
    "time_played_seconds",
    "max_killing_spree",
    "headshot_kills",
    "personal_score",
    "my_team_score",
    "enemy_team_score",
    "team_mmr",
    "enemy_mmr",
]

# Colonnes calculées ajoutées par _enrich_matches_df
COLUMNS_COMPUTED: list[str] = [
    "ratio",
    "date",
    "kills_per_min",
    "deaths_per_min",
    "assists_per_min",
]


def _to_polars(df: object) -> pl.DataFrame:
    """Convertit un DataFrame Pandas en Polars si nécessaire (pont de sécurité)."""
    if isinstance(df, pl.DataFrame):
        return df
    try:
        return pl.from_pandas(df)  # type: ignore[arg-type]
    except Exception:
        return pl.DataFrame()


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


def _is_duckdb_v4_path(db_path: str) -> bool:
    """Détecte si le chemin est une DB joueur DuckDB v4."""
    if not db_path:
        return False
    return db_path.endswith(".duckdb") or db_path.endswith("stats.duckdb")


def _load_matches_duckdb_v4(db_path: str, include_firefight: bool = True) -> list:
    """Charge les matchs depuis une DB DuckDB v4 (legacy — retourne MatchRow).

    Préférer _load_matches_duckdb_v4_polars() pour le chemin optimisé.
    """
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


def _load_matches_duckdb_v4_polars(
    db_path: str,
    include_firefight: bool = True,
    columns: list[str] | None = None,
) -> pl.DataFrame:
    """Charge les matchs depuis une DB DuckDB v4 en Polars via Arrow zero-copy.

    Chemin optimisé Sprint 19 : DuckDB → Arrow → Polars sans intermédiaire
    MatchRow. ~3× plus rapide que _load_matches_duckdb_v4 + reconstruction.

    Args:
        db_path: Chemin vers la DB DuckDB.
        include_firefight: Inclure les matchs PvE.
        columns: Liste de colonnes à projeter (None = toutes).

    Returns:
        DataFrame Polars. Vide en cas d'erreur.
    """
    try:
        from src.data.repositories.duckdb_repo import DuckDBRepository

        repo = DuckDBRepository(db_path, xuid="", read_only=True)
        try:
            return repo.load_matches_as_polars(
                include_firefight=include_firefight,
                columns=columns,
            )
        finally:
            repo.close()
    except Exception:
        logger.debug("load_matches_as_polars échoué, fallback MatchRow", exc_info=True)
        return pl.DataFrame()


@st.cache_data(show_spinner=False, ttl=30)
def cached_list_local_dbs(_refresh_token: int = 0) -> list[str]:
    """Liste des DB locales (TTL court pour éviter un scan disque trop fréquent)."""
    return list_local_dbs()


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return ()


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return []


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return None


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return []


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return None


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
            # Vérifier si la table existe (DuckDB utilise information_schema)
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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return []


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return {}


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return []


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return []


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return []


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return []


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return False


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
    # Legacy SQLite non supporté depuis v4.8
    logger.warning(f"DB legacy SQLite non supportée: {db_path}")
    return {}


def _enrich_matches_df(df: pl.DataFrame) -> pl.DataFrame:
    """Enrichit un DataFrame Polars de matchs avec timezone et colonnes calculées.

    Applique les transformations standard :
    - Conversion timezone UTC → Paris → naïf
    - Extraction colonne date
    - Calcul kills/deaths/assists par minute

    Args:
        df: DataFrame Polars brut avec au minimum start_time, kills, deaths, assists,
            time_played_seconds.

    Returns:
        DataFrame enrichi.
    """
    if df.is_empty():
        return df

    # Conversion timezone start_time
    if "start_time" in df.columns:
        start_time_dtype = df.schema.get("start_time")
        if start_time_dtype in (
            pl.Datetime,
            pl.Datetime("us"),
            pl.Datetime("ns"),
            pl.Datetime("ms"),
        ):
            try:
                df = df.with_columns(
                    pl.col("start_time")
                    .dt.convert_time_zone(PARIS_TZ_NAME)
                    .dt.replace_time_zone(None)
                    .alias("start_time")
                )
            except Exception:
                df = df.with_columns(
                    pl.col("start_time")
                    .dt.replace_time_zone("UTC")
                    .dt.convert_time_zone(PARIS_TZ_NAME)
                    .dt.replace_time_zone(None)
                    .alias("start_time")
                )
        elif start_time_dtype == pl.Utf8:
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
    if "time_played_seconds" in df.columns:
        df = df.with_columns(
            (pl.col("time_played_seconds").cast(pl.Float64) / 60.0)
            .clip(lower_bound=0.0)
            .alias("minutes")
        )
        per_min_cols = []
        if "kills" in df.columns:
            per_min_cols.append(
                (pl.col("kills").cast(pl.Float64) / pl.col("minutes")).alias("kills_per_min")
            )
        if "deaths" in df.columns:
            per_min_cols.append(
                (pl.col("deaths").cast(pl.Float64) / pl.col("minutes")).alias("deaths_per_min")
            )
        if "assists" in df.columns:
            per_min_cols.append(
                (pl.col("assists").cast(pl.Float64) / pl.col("minutes")).alias("assists_per_min")
            )
        if per_min_cols:
            df = df.with_columns(per_min_cols)
        df = df.drop("minutes")

    return df


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

    Mécanisme d'invalidation du cache (Sprint 19 — tâche 19.4) :
    - db_key (mtime_ns, size) : détecte les modifications du fichier DB
      (sync externe, modification directe). Invalidation automatique.
    - cache_buster (int) : incrémenté dans session_state après un sync réussi.
      Force le rechargement même si db_key n'a pas encore changé (race condition).
    Les deux paramètres sont passés à @st.cache_data comme clés de hash,
    et ne sont pas lus dans le corps de la fonction.

    Args:
        db_path: Chemin vers la DB.
        xuid: XUID du joueur (ignoré pour DuckDB v4).
        db_key: Clé de cache (mtime, size) — None si fichier inexistant.
        include_firefight: Inclure les matchs PvE.
        cache_buster: Token pour forcer l'invalidation du cache après sync.

    Returns:
        DataFrame Polars enrichi avec toutes les colonnes calculées.
    """
    _ = db_key  # Utilisé pour invalidation du cache Streamlit
    _ = cache_buster  # Utilisé pour forcer le rechargement après sync

    # Détecter le type de DB
    if _is_duckdb_v4_path(db_path):
        # Sprint 19 : chemin optimisé DuckDB → Arrow → Polars (zero-copy)
        df = _load_matches_duckdb_v4_polars(db_path, include_firefight=include_firefight)
        if not df.is_empty():
            # Enrichissement standard (timezone, colonnes calculées)
            df = _enrich_matches_df(df)
            return df

        # Fallback legacy : MatchRow → reconstruction DataFrame
        matches = _load_matches_duckdb_v4(db_path, include_firefight=include_firefight)
    else:
        # Legacy SQLite non supporté depuis v4.8
        logger.warning(f"DB legacy SQLite non supportée: {db_path}")
        matches = []

    if not matches:
        return pl.DataFrame()

    # Construire le DataFrame Polars depuis MatchRow (fallback legacy)
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

    return _enrich_matches_df(df)


# ─── Fonctions sociales réexportées depuis cache_social.py ─────────────────
from src.ui.cache_social import (  # noqa: E402
    cached_get_match_session_info,
    cached_load_friends,
    cached_load_top_teammates_optimized,
)

__all__ = [
    "cached_get_match_session_info",
    "cached_load_friends",
    "cached_load_top_teammates_optimized",
]
