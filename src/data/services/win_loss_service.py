"""Service Victoires/Défaites — agrégats pour la page win_loss.

Encapsule les calculs lourds : bucketing temporel, breakdown par carte,
ratio global, et tableau de période.

Contrat : les pages UI appellent ces fonctions, jamais de calcul inline.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore[assignment]


# ─── Dataclasses retour ────────────────────────────────────────────────


@dataclass(frozen=True)
class PeriodTable:
    """Tableau de victoires/défaites par période."""

    table: pd.DataFrame
    """DataFrame avec colonnes Victoires, Défaites, Égalités, etc."""
    bucket_label: str
    """Label du type de bucket (heure, jour, semaine, mois)."""
    is_empty: bool
    """True si aucune donnée."""


@dataclass(frozen=True)
class MapBreakdownResult:
    """Résultat de l'analyse par carte."""

    breakdown: pd.DataFrame
    """DataFrame avec stats par carte (win_rate, loss_rate, ratio, etc.)."""
    is_empty: bool
    """True si pas assez de matchs."""


@dataclass(frozen=True)
class FriendMatchIds:
    """Résultat de recherche de matchs avec un ami."""

    match_ids: set[str]
    """Set des match_id partagés."""
    scope_df: pd.DataFrame
    """DataFrame filtré sur ces matchs."""


# ─── Service ───────────────────────────────────────────────────────────


class WinLossService:
    """Service d'agrégation pour la page Victoires/Défaites.

    Encapsule les calculs de bucketing, de breakdown par carte,
    et d'accès DB (matchs partagés avec amis).
    """

    @staticmethod
    def compute_period_table(
        dff: pd.DataFrame,
        bucket_label: str,
        is_session_scope: bool = False,
    ) -> PeriodTable:
        """Construit le tableau de victoires/défaites par période.

        Args:
            dff: DataFrame filtré des matchs.
            bucket_label: Label du bucket temporel (pour l'en-tête).
            is_session_scope: True si mode session actif.

        Returns:
            PeriodTable avec le tableau formaté.
        """
        from src.config import SESSION_CONFIG

        if dff.empty or "outcome" not in dff.columns:
            return PeriodTable(table=pd.DataFrame(), bucket_label=bucket_label, is_empty=True)

        d = dff.dropna(subset=["outcome"]).copy()
        if d.empty:
            return PeriodTable(table=pd.DataFrame(), bucket_label=bucket_label, is_empty=True)

        if is_session_scope:
            d = d.sort_values("start_time").reset_index(drop=True)
            if len(d.index) <= 20:
                d["bucket"] = d.index + 1
            else:
                t = pd.to_datetime(d["start_time"], errors="coerce")
                d["bucket"] = t.dt.floor("h")
        else:
            tmin = pd.to_datetime(d["start_time"], errors="coerce").min()
            tmax = pd.to_datetime(d["start_time"], errors="coerce").max()
            dt_range = (tmax - tmin) if (tmin == tmin and tmax == tmax) else pd.Timedelta(days=999)
            days = float(dt_range.total_seconds() / 86400.0) if dt_range is not None else 999.0
            cfg = SESSION_CONFIG
            if days < cfg.bucket_threshold_hourly:
                d = d.sort_values("start_time").reset_index(drop=True)
                d["bucket"] = d.index + 1
            elif days <= cfg.bucket_threshold_daily:
                d["bucket"] = d["start_time"].dt.floor("h")
            elif days <= cfg.bucket_threshold_weekly:
                d["bucket"] = d["start_time"].dt.to_period("D").astype(str)
            elif days <= cfg.bucket_threshold_monthly:
                d["bucket"] = d["start_time"].dt.to_period("W-MON").astype(str)
            else:
                d["bucket"] = d["start_time"].dt.to_period("M").astype(str)

        pivot = (
            d.pivot_table(index="bucket", columns="outcome", values="match_id", aggfunc="count")
            .fillna(0)
            .astype(int)
            .sort_index()
        )
        out_tbl = pd.DataFrame(index=pivot.index)
        out_tbl["Victoires"] = pivot[2] if 2 in pivot.columns else 0
        out_tbl["Défaites"] = pivot[3] if 3 in pivot.columns else 0
        out_tbl["Égalités"] = pivot[1] if 1 in pivot.columns else 0
        out_tbl["Non terminés"] = pivot[4] if 4 in pivot.columns else 0
        out_tbl["Total"] = out_tbl[["Victoires", "Défaites", "Égalités", "Non terminés"]].sum(
            axis=1
        )
        out_tbl["Taux de victoires"] = (
            100.0 * (out_tbl["Victoires"] / out_tbl["Total"].where(out_tbl["Total"] > 0))
        ).fillna(0.0)

        out_tbl = out_tbl.reset_index().rename(columns={"bucket": bucket_label.capitalize()})

        return PeriodTable(table=out_tbl, bucket_label=bucket_label, is_empty=False)

    @staticmethod
    def compute_map_breakdown(
        base_scope: pd.DataFrame,
        min_matches: int = 1,
    ) -> MapBreakdownResult:
        """Calcule le breakdown statistique par carte.

        Args:
            base_scope: DataFrame à analyser.
            min_matches: Nombre minimum de matchs par carte.

        Returns:
            MapBreakdownResult avec le breakdown filtré.
        """
        from src.analysis import compute_map_breakdown

        breakdown = compute_map_breakdown(base_scope)
        breakdown = breakdown.filter(pl.col("matches") >= int(min_matches))

        return MapBreakdownResult(
            breakdown=breakdown.to_pandas() if not breakdown.is_empty() else pd.DataFrame(),
            is_empty=breakdown.is_empty(),
        )

    @staticmethod
    def get_friend_scope_df(
        scope: str,
        dff: pd.DataFrame,
        base: pd.DataFrame,
        db_path: str,
        xuid: str,
        db_key: tuple[int, int] | None,
    ) -> pd.DataFrame:
        """Retourne le DataFrame filtré selon le scope (moi, ami, tous).

        Args:
            scope: Label du scope sélectionné.
            dff: DataFrame filtré courant.
            base: DataFrame de base complet.
            db_path: Chemin DB.
            xuid: XUID du joueur.
            db_key: Clé de cache DB.

        Returns:
            DataFrame filtré sur le scope demandé.
        """
        from src.ui.cache import cached_same_team_match_ids_with_friend

        if scope == "Moi (toutes les parties)":
            return base
        elif scope == "Avec Madina972":
            match_ids = set(
                cached_same_team_match_ids_with_friend(
                    db_path,
                    xuid.strip(),
                    "2533274858283686",
                    db_key=db_key,
                )
            )
            return base.loc[base["match_id"].astype(str).isin(match_ids)].copy()
        elif scope == "Avec Chocoboflor":
            match_ids = set(
                cached_same_team_match_ids_with_friend(
                    db_path,
                    xuid.strip(),
                    "2535469190789936",
                    db_key=db_key,
                )
            )
            return base.loc[base["match_id"].astype(str).isin(match_ids)].copy()
        else:
            return dff
