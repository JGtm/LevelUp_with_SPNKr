"""Compatibilité: diagnostic de base joueur.

Ce module existe pour compatibilité avec la suite de tests et les usages historiques.
L’implémentation de référence est conservée dans `scripts/_archive/diagnose_player_db.py`.
"""

from __future__ import annotations

from typing import Any


def diagnose(db_path: str) -> dict[str, Any]:
    """Diagnostique une base joueur et retourne un résumé.

    Args:
        db_path: Chemin vers la base DuckDB du joueur.

    Returns:
        Un dictionnaire contenant des informations de diagnostic.
    """

    from scripts._archive.diagnose_player_db import diagnose as _diagnose

    return _diagnose(db_path)
