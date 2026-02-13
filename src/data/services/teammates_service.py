"""Service Coéquipiers — agrégats pour la page teammates.

Encapsule les calculs lourds : chargement stats coéquipiers, enrichissement
perfect kills, profils radar de complémentarité, et impact/taquinerie.

Contrat : les pages UI appellent ces fonctions, jamais de calcul inline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore[assignment]


# ─── Dataclasses retour ────────────────────────────────────────────────


@dataclass(frozen=True)
class TeammateStats:
    """Stats agrégées d'un coéquipier pour un ensemble de matchs."""

    gamertag: str
    """Gamertag du coéquipier."""
    df: pd.DataFrame
    """DataFrame des stats sur les matchs communs."""
    is_empty: bool
    """True si aucune donnée trouvée."""


@dataclass(frozen=True)
class EnrichedSeries:
    """Série (nom, DataFrame) enrichie avec perfect_kills."""

    series: list[tuple[str, pd.DataFrame]]
    """Liste de (gamertag, df) avec colonne perfect_kills ajoutée."""


@dataclass(frozen=True)
class ParticipationProfile:
    """Profil de participation radar (6 axes) pour un joueur."""

    name: str
    color: str
    values: dict[str, float]
    """Mapping axe → valeur normalisée."""


@dataclass(frozen=True)
class ImpactData:
    """Données d'impact et taquinerie pour un groupe de joueurs."""

    first_bloods: dict[str, list[str]]
    clutch_finishers: dict[str, list[str]]
    last_casualties: dict[str, list[str]]
    scores: dict[str, float]
    gamertags: list[str]
    match_ids: list[str]
    available: bool
    """True si des événements d'impact ont été trouvés."""


# ─── Service ───────────────────────────────────────────────────────────


class TeammatesService:
    """Service d'agrégation pour la page Coéquipiers.

    Encapsule le chargement multi-DB, l'enrichissement des données,
    et les calculs de profils de participation.
    """

    @staticmethod
    def load_teammate_stats(
        teammate_gamertag: str,
        match_ids: set[str],
        reference_db_path: str,
    ) -> TeammateStats:
        """Charge les stats d'un coéquipier depuis sa propre DB.

        Dans l'architecture DuckDB v4, chaque joueur a sa propre DB :
        data/players/{gamertag}/stats.duckdb

        Args:
            teammate_gamertag: Gamertag du coéquipier.
            match_ids: Set des match_id à filtrer.
            reference_db_path: Chemin vers la DB de référence (joueur principal).

        Returns:
            TeammateStats avec le DataFrame filtré ou vide.
        """
        base_dir = Path(reference_db_path).parent.parent
        teammate_db_path = base_dir / teammate_gamertag / "stats.duckdb"

        if not teammate_db_path.exists():
            return TeammateStats(gamertag=teammate_gamertag, df=pd.DataFrame(), is_empty=True)

        try:
            from src.ui.cache import load_df_optimized

            df_pl = load_df_optimized(str(teammate_db_path), "", db_key=None)
            if df_pl.is_empty():
                return TeammateStats(gamertag=teammate_gamertag, df=pd.DataFrame(), is_empty=True)

            df_filtered = df_pl.filter(
                pl.col("match_id").cast(pl.Utf8).is_in([str(mid) for mid in match_ids])
            )
            result_df = df_filtered.to_pandas()
            return TeammateStats(
                gamertag=teammate_gamertag,
                df=result_df,
                is_empty=result_df.empty,
            )
        except Exception:
            return TeammateStats(gamertag=teammate_gamertag, df=pd.DataFrame(), is_empty=True)

    @staticmethod
    def enrich_series_with_perfect_kills(
        series: list[tuple[str, pd.DataFrame]],
        db_path: str,
    ) -> EnrichedSeries:
        """Ajoute la colonne perfect_kills à chaque DataFrame de la série.

        Le 1er élément (idx=0) = joueur principal (utilise db_path).
        Les suivants = coéquipiers (utilise base_dir / gamertag / stats.duckdb).

        Args:
            series: Liste de (gamertag, DataFrame).
            db_path: Chemin vers la DB du joueur principal.

        Returns:
            EnrichedSeries avec la colonne perfect_kills ajoutée.
        """
        from src.data.repositories.duckdb_repo import DuckDBRepository

        if not db_path or not str(db_path).endswith(".duckdb"):
            return EnrichedSeries(series=series)

        base_dir = Path(db_path).parent.parent
        enriched: list[tuple[str, pd.DataFrame]] = []

        for idx, (name, df) in enumerate(series):
            df = df.copy()
            if "match_id" in df.columns and not df.empty:
                match_ids = df["match_id"].astype(str).tolist()
                try:
                    if idx == 0:
                        use_path = db_path
                    else:
                        player_db = base_dir / name / "stats.duckdb"
                        use_path = str(player_db) if player_db.exists() else db_path
                    repo = DuckDBRepository(use_path, "")
                    counts = repo.count_perfect_kills_by_match(match_ids)
                    df["perfect_kills"] = (
                        df["match_id"].astype(str).map(counts).fillna(0).astype(int)
                    )
                except Exception:
                    df["perfect_kills"] = 0
            else:
                df["perfect_kills"] = 0
            enriched.append((name, df))

        return EnrichedSeries(series=enriched)

    @staticmethod
    def compute_participation_profiles(
        players_data: list[dict[str, Any]],
        db_path: str,
        shared_match_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Calcule les profils de participation radar pour N joueurs.

        Args:
            players_data: Liste de dicts avec clés: name, df, color, xuid (opt).
                          df est le DataFrame des matchs du joueur.
            db_path: Chemin vers la DB de référence.
            shared_match_ids: Match IDs communs à analyser.

        Returns:
            Liste de profils (dicts) compatibles avec create_participation_profile_radar.
        """
        from src.data.repositories import DuckDBRepository
        from src.visualization.participation_radar import (
            compute_participation_profile,
            get_radar_thresholds,
        )

        thresholds = get_radar_thresholds(db_path) if db_path else None
        base_dir = Path(db_path).parent.parent
        profiles: list[dict[str, Any]] = []

        for player in players_data:
            name = player["name"]
            df_player = player["df"]
            color = player["color"]
            is_main = player.get("is_main", False)

            if df_player.empty:
                continue

            player_db = db_path if is_main else str(base_dir / name / "stats.duckdb")
            if not Path(player_db).exists():
                continue

            try:
                repo = DuckDBRepository(player_db, player.get("xuid", ""))
                if repo.has_personal_score_awards():
                    ps = repo.load_personal_score_awards_as_polars(match_ids=shared_match_ids)
                    if not ps.is_empty():
                        match_row = {
                            "deaths": int(df_player["deaths"].sum())
                            if "deaths" in df_player.columns
                            else 0,
                            "time_played_seconds": float(df_player["time_played_seconds"].sum())
                            if "time_played_seconds" in df_player.columns
                            else 600.0 * len(df_player),
                            "pair_name": df_player["pair_name"].iloc[0]
                            if "pair_name" in df_player.columns and len(df_player) > 0
                            else None,
                        }
                        profile = compute_participation_profile(
                            ps,
                            match_row=match_row,
                            name=name,
                            color=color,
                            pair_name=match_row.get("pair_name"),
                            thresholds=thresholds,
                        )
                        profiles.append(profile)
            except Exception:
                pass

        return profiles

    @staticmethod
    def load_impact_data(
        db_path: str,
        xuid: str,
        match_ids: list[str],
        friend_xuids: list[str],
    ) -> ImpactData:
        """Charge les données d'impact et taquinerie depuis la DB.

        Args:
            db_path: Chemin vers la DB.
            xuid: XUID du joueur principal.
            match_ids: Liste des match_id.
            friend_xuids: Liste des XUIDs des coéquipiers.

        Returns:
            ImpactData avec événements ou available=False.
        """
        from src.data.repositories import DuckDBRepository

        if len(friend_xuids) < 2 or not match_ids:
            return ImpactData(
                first_bloods={},
                clutch_finishers={},
                last_casualties={},
                scores={},
                gamertags=[],
                match_ids=[],
                available=False,
            )

        try:
            repo = DuckDBRepository(db_path, xuid.strip())
            conn = repo._get_connection()

            # Vérifier présence table highlight_events
            has_events_table = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_name = 'highlight_events'"
            ).fetchone()

            if not has_events_table:
                return ImpactData(
                    first_bloods={},
                    clutch_finishers={},
                    last_casualties={},
                    scores={},
                    gamertags=[],
                    match_ids=[],
                    available=False,
                )

            # Charger les événements
            events_query = """
                SELECT match_id, xuid::TEXT as xuid, gamertag, event_type, time_ms
                FROM highlight_events
                WHERE match_id IN ({})
            """.format(", ".join(["?" for _ in match_ids]))

            events_result = conn.execute(events_query, match_ids).fetchall()

            if not events_result:
                return ImpactData(
                    first_bloods={},
                    clutch_finishers={},
                    last_casualties={},
                    scores={},
                    gamertags=[],
                    match_ids=[],
                    available=False,
                )

            events_df = pl.DataFrame(
                {
                    "match_id": [str(r[0]) for r in events_result],
                    "xuid": [str(r[1]) for r in events_result],
                    "gamertag": [r[2] or "Unknown" for r in events_result],
                    "event_type": [r[3] for r in events_result],
                    "time_ms": [int(r[4] or 0) for r in events_result],
                }
            )

            # Charger les outcomes
            matches_query = """
                SELECT match_id, outcome
                FROM match_stats
                WHERE match_id IN ({})
            """.format(", ".join(["?" for _ in match_ids]))

            matches_result = conn.execute(matches_query, match_ids).fetchall()

            matches_df = pl.DataFrame(
                {
                    "match_id": [str(r[0]) for r in matches_result],
                    "outcome": [int(r[1] or 0) for r in matches_result],
                }
            )

            all_friend_xuids = {str(x) for x in friend_xuids}
            all_friend_xuids.add(str(xuid).strip())

            from src.analysis.friends_impact import get_all_impact_events

            first_bloods, clutch_finishers, last_casualties, scores = get_all_impact_events(
                events_df, matches_df, friend_xuids=all_friend_xuids
            )

            if not scores:
                return ImpactData(
                    first_bloods={},
                    clutch_finishers={},
                    last_casualties={},
                    scores={},
                    gamertags=[],
                    match_ids=[],
                    available=False,
                )

            gamertags = list(scores.keys())
            sorted_match_ids = sorted(
                {
                    m
                    for m in match_ids
                    if m
                    in set(
                        list(first_bloods.keys())
                        + list(clutch_finishers.keys())
                        + list(last_casualties.keys())
                    )
                }
            )

            return ImpactData(
                first_bloods=first_bloods,
                clutch_finishers=clutch_finishers,
                last_casualties=last_casualties,
                scores=scores,
                gamertags=gamertags,
                match_ids=sorted_match_ids,
                available=True,
            )

        except Exception:
            return ImpactData(
                first_bloods={},
                clutch_finishers={},
                last_casualties={},
                scores={},
                gamertags=[],
                match_ids=[],
                available=False,
            )
