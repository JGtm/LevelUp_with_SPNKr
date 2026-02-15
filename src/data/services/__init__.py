"""Couche services — agrégats métier pour l'UI.

Contrat d'architecture v4.5 :
- Les services encapsulent les calculs lourds (cumuls, distributions, corrélations).
- Les services accèdent aux repositories et à la couche analysis.
- Les pages UI consomment les services — aucun calcul métier inline.
- Les retours sont typés (dataclasses, pl.DataFrame, dict) avec docstrings FR.
"""

from src.data.services.teammates_service import TeammatesService
from src.data.services.timeseries_service import TimeseriesService
from src.data.services.win_loss_service import WinLossService

__all__ = [
    "TimeseriesService",
    "WinLossService",
    "TeammatesService",
]
