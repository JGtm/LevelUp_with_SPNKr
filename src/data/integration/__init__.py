"""
Module d'intégration pour l'UI Streamlit.
(Integration module for Streamlit UI)

Ce module fournit des fonctions de bridge entre le nouveau système
de données (DataRepository + QueryEngine) et l'UI Streamlit existante.

HOW IT WORKS:
1. Fournit des fonctions qui retournent des DataFrames Pandas (compatibles avec l'UI)
2. Gère automatiquement le choix entre Legacy, Hybrid et DuckDB
3. Convertit les résultats du nouveau système vers les formats attendus par l'UI

Usage:
    from src.data.integration import (
        load_matches_df,
        get_repository_for_player,
        get_repository_for_ui,
    )

    # Méthode recommandée : via gamertag (auto-détection du mode)
    repo = get_repository_for_player("JGtm")
    matches = repo.load_matches()

    # Charger les matchs en DataFrame (compatible avec l'UI existante)
    df = load_matches_df(db_path, xuid)
"""

from src.data.integration.streamlit_bridge import (
    get_analytics_for_ui,
    get_repository_for_player,
    get_repository_for_ui,
    get_repository_mode_from_settings,
    get_trends_for_ui,
    load_matches_df,
    matches_to_dataframe,
)

__all__ = [
    "load_matches_df",
    "get_repository_for_ui",
    "get_repository_for_player",
    "get_analytics_for_ui",
    "get_trends_for_ui",
    "matches_to_dataframe",
    "get_repository_mode_from_settings",
]
