"""
Module d'intégration pour l'UI Streamlit.
(Integration module for Streamlit UI)

Ce module fournit des fonctions de bridge entre le nouveau système
de données (DataRepository + QueryEngine) et l'UI Streamlit existante.

HOW IT WORKS:
1. Fournit des fonctions qui retournent des DataFrames Pandas (compatibles avec l'UI)
2. Gère automatiquement le choix entre Legacy et Hybrid
3. Convertit les résultats du nouveau système vers les formats attendus par l'UI

Usage:
    from src.data.integration import (
        load_matches_df,
        get_analytics,
        get_repository_for_ui,
    )
    
    # Charger les matchs en DataFrame (compatible avec l'UI existante)
    df = load_matches_df(db_path, xuid)
    
    # Obtenir les analytics (nouveau système)
    analytics = get_analytics(db_path, xuid)
    stats = analytics.get_global_stats()
"""

from src.data.integration.streamlit_bridge import (
    load_matches_df,
    get_repository_for_ui,
    get_analytics_for_ui,
    get_trends_for_ui,
    matches_to_dataframe,
    get_repository_mode_from_settings,
)

__all__ = [
    "load_matches_df",
    "get_repository_for_ui",
    "get_analytics_for_ui",
    "get_trends_for_ui",
    "matches_to_dataframe",
    "get_repository_mode_from_settings",
]
