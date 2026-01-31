"""
Bridge entre le nouveau système de données et l'UI Streamlit.
(Bridge between new data system and Streamlit UI)

HOW IT WORKS:
Ce module fournit des fonctions qui :
1. Créent les repositories/engines avec le bon mode
2. Convertissent les résultats en DataFrames Pandas
3. Gèrent le cache et l'état Streamlit

Les fonctions retournent des types compatibles avec l'UI existante
(pd.DataFrame, list, dict) plutôt que les nouveaux types (MatchRow, etc.)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd

from src.data import get_repository, RepositoryMode
from src.data.repositories.protocol import DataRepository
from src.models import MatchRow


# Timezone Paris (identique à cache.py)
PARIS_TZ_NAME = "Europe/Paris"


def get_repository_mode_from_settings() -> RepositoryMode:
    """
    Récupère le mode de repository depuis les settings ou l'environnement.
    (Get repository mode from settings or environment)
    
    Priorité:
    1. Variable d'environnement OPENSPARTAN_REPOSITORY_MODE
    2. Paramètre dans st.session_state.app_settings.repository_mode
    3. Défaut: LEGACY
    """
    # 1. Variable d'environnement
    env_mode = os.environ.get("OPENSPARTAN_REPOSITORY_MODE", "").lower()
    if env_mode in ("legacy", "hybrid", "shadow"):
        return RepositoryMode(env_mode)
    
    # 2. Settings Streamlit (si disponible)
    try:
        import streamlit as st
        settings = st.session_state.get("app_settings")
        if settings and hasattr(settings, "repository_mode"):
            mode_str = str(settings.repository_mode).lower()
            if mode_str in ("legacy", "hybrid", "shadow"):
                return RepositoryMode(mode_str)
    except Exception:
        pass
    
    # 3. Défaut
    return RepositoryMode.LEGACY


def get_warehouse_path(db_path: str) -> Path:
    """
    Détermine le chemin du warehouse à partir du chemin de la DB.
    (Determine warehouse path from DB path)
    
    Convention: warehouse est dans le même dossier que la DB.
    """
    return Path(db_path).parent / "warehouse"


def get_repository_for_ui(
    db_path: str,
    xuid: str,
    *,
    mode: RepositoryMode | None = None,
) -> DataRepository:
    """
    Crée un repository configuré pour l'UI.
    (Create a repository configured for UI)
    
    Args:
        db_path: Chemin vers la base de données
        xuid: XUID du joueur
        mode: Mode explicite (sinon récupéré depuis settings)
        
    Returns:
        Instance de DataRepository
    """
    if mode is None:
        mode = get_repository_mode_from_settings()
    
    warehouse_path = get_warehouse_path(db_path)
    
    return get_repository(
        db_path,
        xuid,
        mode=mode,
        warehouse_path=warehouse_path,
    )


def matches_to_dataframe(matches: list[MatchRow]) -> pd.DataFrame:
    """
    Convertit une liste de MatchRow en DataFrame Pandas.
    (Convert list of MatchRow to Pandas DataFrame)
    
    Format identique à load_df_optimized() pour compatibilité.
    """
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
    
    # Conversions standard (identiques à cache.py)
    df["start_time"] = (
        pd.to_datetime(df["start_time"], utc=True)
        .dt.tz_convert(PARIS_TZ_NAME)
        .dt.tz_localize(None)
    )
    df["date"] = df["start_time"].dt.date
    
    # Stats par minute
    minutes = (pd.to_numeric(df["time_played_seconds"], errors="coerce") / 60.0).astype(float)
    minutes = minutes.where(minutes > 0)
    df["kills_per_min"] = pd.to_numeric(df["kills"], errors="coerce") / minutes
    df["deaths_per_min"] = pd.to_numeric(df["deaths"], errors="coerce") / minutes
    df["assists_per_min"] = pd.to_numeric(df["assists"], errors="coerce") / minutes
    
    return df


def load_matches_df(
    db_path: str,
    xuid: str,
    *,
    include_firefight: bool = True,
    playlist_filter: str | None = None,
    map_filter: str | None = None,
    mode: RepositoryMode | None = None,
) -> pd.DataFrame:
    """
    Charge les matchs en DataFrame via le DataRepository.
    (Load matches as DataFrame via DataRepository)
    
    Fonction principale d'intégration, remplaçant load_df_optimized()
    pour les cas où on veut utiliser le nouveau système.
    
    Args:
        db_path: Chemin vers la base de données
        xuid: XUID du joueur
        include_firefight: Inclure les matchs PvE
        playlist_filter: Filtre sur playlist_id
        map_filter: Filtre sur map_id
        mode: Mode de repository (défaut: depuis settings)
        
    Returns:
        DataFrame Pandas compatible avec l'UI existante
    """
    repo = get_repository_for_ui(db_path, xuid, mode=mode)
    
    try:
        matches = repo.load_matches(
            playlist_filter=playlist_filter,
            map_filter=map_filter,
            include_firefight=include_firefight,
        )
        return matches_to_dataframe(matches)
    finally:
        # Fermer si c'est un HybridRepository ou ShadowRepository
        if hasattr(repo, "close"):
            repo.close()


def get_analytics_for_ui(
    db_path: str,
    xuid: str,
):
    """
    Crée une instance d'AnalyticsQueries pour l'UI.
    (Create AnalyticsQueries instance for UI)
    
    Returns:
        Tuple (engine, analytics) à fermer après utilisation
    """
    from src.data.query import QueryEngine, AnalyticsQueries
    
    warehouse_path = get_warehouse_path(db_path)
    engine = QueryEngine(warehouse_path)
    analytics = AnalyticsQueries(engine, xuid)
    
    return engine, analytics


def get_trends_for_ui(
    db_path: str,
    xuid: str,
):
    """
    Crée une instance de TrendAnalyzer pour l'UI.
    (Create TrendAnalyzer instance for UI)
    
    Returns:
        Tuple (engine, trends) à fermer après utilisation
    """
    from src.data.query import QueryEngine, TrendAnalyzer
    
    warehouse_path = get_warehouse_path(db_path)
    engine = QueryEngine(warehouse_path)
    trends = TrendAnalyzer(engine, xuid)
    
    return engine, trends


def check_hybrid_available(db_path: str, xuid: str) -> bool:
    """
    Vérifie si les données hybrides (Parquet) sont disponibles.
    (Check if hybrid data (Parquet) is available)
    """
    warehouse_path = get_warehouse_path(db_path)
    parquet_path = warehouse_path / "match_facts" / f"player={xuid}"
    
    if not parquet_path.exists():
        return False
    
    return bool(list(parquet_path.glob("**/*.parquet")))


def get_migration_status(db_path: str, xuid: str) -> dict[str, Any]:
    """
    Retourne l'état de la migration pour un joueur.
    (Return migration status for a player)
    """
    from src.data.repositories.shadow import ShadowRepository, ShadowMode
    
    warehouse_path = get_warehouse_path(db_path)
    
    try:
        shadow = ShadowRepository(
            db_path,
            xuid,
            warehouse_path=warehouse_path,
            mode=ShadowMode.SHADOW_READ,
        )
        progress = shadow.get_migration_progress()
        shadow.close()
        return progress
    except Exception as e:
        return {
            "error": str(e),
            "legacy_count": 0,
            "hybrid_count": 0,
            "progress_percent": 0,
            "is_complete": False,
        }
