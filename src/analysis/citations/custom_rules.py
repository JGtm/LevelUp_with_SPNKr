"""
Règles de calcul custom pour citations H5G complexes.

Ce module contient les fonctions de calcul pour les citations qui nécessitent
une logique métier complexe (filtres multiples, conditions, séquences, etc.).
"""

from typing import Any

import polars as pl


def compute_bulldozer(df: pl.DataFrame) -> int:
    """Compte les parties Assassin avec KD > 8 (hors Firefight/BTB).

    Args:
        df: DataFrame des matchs avec colonnes playlist_name, kills, deaths, outcome

    Returns:
        Nombre de parties validant la condition
    """
    if df.is_empty():
        return 0

    filtered = df.filter(
        pl.col("playlist_name").str.contains("(?i)slayer|assassin")
        & ~pl.col("playlist_name").str.contains(
            "(?i)firefight|btb|baptême|bapteme|big team|grande bataille"
        )
    )

    if filtered.is_empty():
        return 0

    # KD > 8 (gérer division par zéro)
    count = filtered.filter((pl.col("kills") / pl.col("deaths").clip(1, None)) > 8.0).height

    return count


def compute_wins_mode(df: pl.DataFrame, mode_pattern: str) -> int:
    """Compte les victoires dans un mode donné.

    Args:
        df: DataFrame des matchs
        mode_pattern: Pattern regex pour le mode (ex: "ctf|drapeau")

    Returns:
        Nombre de victoires
    """
    if df.is_empty():
        return 0

    return df.filter(
        pl.col("playlist_name").str.contains(f"(?i){mode_pattern}") & pl.col("outcome").eq("win")
    ).height


def compute_wins_ctf(df: pl.DataFrame) -> int:
    """Victoires en Capture du drapeau."""
    return compute_wins_mode(df, "ctf|capture.*drapeau|drapeau.*neutre|neutral.*flag")


def compute_wins_firefight(df: pl.DataFrame) -> int:
    """Victoires en Firefight/Baptême du feu."""
    return compute_wins_mode(df, "firefight|baptême|bapteme")


def compute_wins_slayer(df: pl.DataFrame) -> int:
    """Victoires en Slayer/Assassin."""
    return compute_wins_mode(df, "slayer|assassin")


def compute_wins_strongholds(df: pl.DataFrame) -> int:
    """Victoires en Strongholds/Bases."""
    return compute_wins_mode(df, "stronghold|bases")


def compute_annexion_forcee(
    df: pl.DataFrame | None = None, awards: dict[str, int] | None = None, **kwargs: Any
) -> int:
    """Compte les séquences de 3+ Zone Capture consécutives sans mourir.

    Condition : Capturer 3 zones d'affilée dans un match Strongholds sans mourir entre.

    Note: Cette fonction nécessite des données au niveau match-par-match pour analyser
    les séquences. Pour l'instant, on retourne le nombre total de Zone Capture divisé par 3
    comme approximation. L'implémentation précise nécessiterait highlight_events avec
    timestamps des captures et deaths.

    Args:
        df: DataFrame des matchs (non utilisé pour l'instant)
        awards: Dict des compteurs d'awards
        **kwargs: Arguments supplémentaires (pour compatibilité)

    Returns:
        Approximation du nombre de séquences de 3+ captures
    """
    if awards is None:
        return 0

    # Version simplifiée : Total Zone Capture / 3
    # TODO: Implémenter la vraie logique avec highlight_events quand disponible
    zone_captures = awards.get("Zone Capture", 0)

    # Au minimum 3 captures nécessaires
    if zone_captures < 3:
        return 0

    # Approximation conservatrice : chaque groupe de 3 captures = 1 point
    return zone_captures // 3


# Registry des fonctions custom pour utilisation dynamique
CUSTOM_FUNCTIONS = {
    "compute_bulldozer": compute_bulldozer,
    "compute_wins_ctf": compute_wins_ctf,
    "compute_wins_firefight": compute_wins_firefight,
    "compute_wins_slayer": compute_wins_slayer,
    "compute_wins_strongholds": compute_wins_strongholds,
    "compute_annexion_forcee": compute_annexion_forcee,
}


def get_custom_function(function_name: str):
    """Récupère une fonction custom par son nom.

    Args:
        function_name: Nom de la fonction

    Returns:
        La fonction ou None si non trouvée
    """
    return CUSTOM_FUNCTIONS.get(function_name)
