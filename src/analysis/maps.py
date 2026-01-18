"""Analyse par carte (map)."""

from typing import List

import pandas as pd

from src.analysis.stats import compute_outcome_rates, compute_global_ratio
from src.models import MapBreakdown


def compute_map_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule les statistiques agrégées par carte.
    
    Args:
        df: DataFrame de matchs.
        
    Returns:
        DataFrame avec colonnes:
        - map_name
        - matches
        - accuracy_avg
        - win_rate
        - loss_rate
        - ratio_global
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "map_name",
                "matches",
                "accuracy_avg",
                "win_rate",
                "loss_rate",
                "ratio_global",
            ]
        )

    d = df.copy()
    d["map_name"] = d["map_name"].fillna("")
    d = d.loc[d["map_name"].astype(str).str.strip() != ""]
    
    if d.empty:
        return pd.DataFrame(
            columns=[
                "map_name",
                "matches",
                "accuracy_avg",
                "win_rate",
                "loss_rate",
                "ratio_global",
            ]
        )

    rows: List[dict] = []
    for map_name, g in d.groupby("map_name", dropna=True):
        rates = compute_outcome_rates(g)
        total_out = max(1, rates.total)
        acc = g["accuracy"].dropna().mean()
        
        rows.append(
            {
                "map_name": map_name,
                "matches": int(len(g)),
                "accuracy_avg": float(acc) if acc == acc else None,
                "win_rate": rates.wins / total_out if rates.total else None,
                "loss_rate": rates.losses / total_out if rates.total else None,
                "ratio_global": compute_global_ratio(g),
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values(["matches", "ratio_global"], ascending=[False, False])
    return out


def map_breakdown_to_models(df: pd.DataFrame) -> List[MapBreakdown]:
    """Convertit un DataFrame de breakdown en liste de MapBreakdown.
    
    Args:
        df: DataFrame issu de compute_map_breakdown.
        
    Returns:
        Liste de MapBreakdown.
    """
    return [
        MapBreakdown(
            map_name=row["map_name"],
            matches=int(row["matches"]),
            accuracy_avg=row["accuracy_avg"],
            win_rate=row["win_rate"],
            loss_rate=row["loss_rate"],
            ratio_global=row["ratio_global"],
        )
        for _, row in df.iterrows()
    ]
