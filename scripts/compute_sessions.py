#!/usr/bin/env python3
"""Script pour calculer et persister les sessions dans match_stats.

Ce script :
1. Calcule les sessions basées sur le gap temporel entre matchs
2. Met à jour session_id et session_label dans match_stats
3. Rafraîchit la vue matérialisée mv_session_stats

Usage:
    # Calculer les sessions pour un joueur
    python scripts/compute_sessions.py --gamertag JGtm

    # Calculer les sessions pour tous les joueurs
    python scripts/compute_sessions.py --all

    # Spécifier un gap différent (défaut: 120 minutes)
    python scripts/compute_sessions.py --gamertag JGtm --gap-minutes 90

    # Mode dry-run (affiche seulement, ne modifie rien)
    python scripts/compute_sessions.py --gamertag JGtm --dry-run

    # Forcer le recalcul même si des sessions existent
    python scripts/compute_sessions.py --gamertag JGtm --force

Note: Les boutons "Dernière session" et "Session en trio" utilisent
      le calcul à la volée (cached_compute_sessions_db), mais persister
      les sessions améliore les performances et permet mv_session_stats.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

# Ajouter le répertoire parent au path pour les imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import duckdb
import polars as pl

from src.analysis.sessions import compute_sessions_with_context_polars
from src.config import SESSION_CONFIG
from src.ui.multiplayer import list_duckdb_v4_players
from src.ui.sync import get_player_duckdb_path, is_duckdb_player

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def compute_sessions_for_db(
    conn: duckdb.DuckDBPyConnection,
    gap_minutes: int = 120,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Calcule et persiste les sessions dans match_stats avec logique avancée (gap + coéquipiers).

    Args:
        conn: Connexion DuckDB.
        gap_minutes: Écart max entre parties d'une même session (en minutes).
        force: Si True, recalcule même si des sessions existent.
        dry_run: Si True, affiche seulement sans modifier.

    Returns:
        Dict avec les résultats du calcul.
    """
    results = {
        "total_matches": 0,
        "sessions_computed": 0,
        "matches_updated": 0,
        "already_has_sessions": False,
        "dry_run": dry_run,
    }

    # Vérifier si des sessions existent déjà
    existing_sessions = conn.execute(
        "SELECT COUNT(*) FROM match_stats WHERE session_id IS NOT NULL"
    ).fetchone()[0]

    if existing_sessions > 0:
        results["already_has_sessions"] = True
        if not force:
            logger.info(
                f"Des sessions existent déjà ({existing_sessions} matchs). "
                "Utilisez --force pour recalculer."
            )
            return results

    # Charger les matchs depuis DuckDB en DataFrame Polars
    df = conn.execute("""
        SELECT
            match_id,
            start_time,
            teammates_signature
        FROM match_stats
        WHERE start_time IS NOT NULL
        ORDER BY start_time ASC
    """).pl()

    results["total_matches"] = len(df)

    if df.is_empty():
        logger.info("Aucun match trouvé.")
        return results

    # Calculer les sessions avec la logique avancée
    df_with_sessions = compute_sessions_with_context_polars(
        df,
        gap_minutes=gap_minutes,
        teammates_column="teammates_signature",
    )

    results["sessions_computed"] = df_with_sessions["session_id"].n_unique()

    logger.info(
        f"Calculé {results['sessions_computed']} sessions pour {len(df)} matchs "
        f"(gap: {gap_minutes} min, logique avancée: gap + coéquipiers)"
    )

    if dry_run:
        # Afficher un aperçu
        preview = (
            df_with_sessions.select(["session_id", "session_label", "match_id"])
            .group_by("session_id", "session_label")
            .agg(pl.count("match_id").alias("count"))
            .head(5)
        )
        for row in preview.iter_rows(named=True):
            logger.info(f"  Session {row['session_id']}: {row['session_label']}")
        if results["sessions_computed"] > 5:
            logger.info(f"  ... et {results['sessions_computed'] - 5} autres sessions")
        return results

    # Persister les sessions dans match_stats
    logger.info("Mise à jour de match_stats...")

    # Réinitialiser les sessions existantes si force
    if force:
        conn.execute("UPDATE match_stats SET session_id = NULL, session_label = NULL")

    # Mettre à jour chaque match avec son session_id et session_label
    updates = 0
    for row in df_with_sessions.select(["match_id", "session_id", "session_label"]).iter_rows(
        named=True
    ):
        conn.execute(
            """
            UPDATE match_stats
            SET session_id = ?, session_label = ?
            WHERE match_id = ?
            """,
            [str(row["session_id"]), row["session_label"], row["match_id"]],
        )
        updates += 1

    results["matches_updated"] = updates

    logger.info(f"Mis à jour {updates} matchs avec leurs sessions.")

    return results


def refresh_session_stats(conn: duckdb.DuckDBPyConnection) -> int:
    """Rafraîchit la vue matérialisée mv_session_stats.

    Args:
        conn: Connexion DuckDB.

    Returns:
        Nombre de sessions dans la vue.
    """
    logger.info("Rafraîchissement de mv_session_stats...")

    try:
        # Vérifier si la table existe
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'mv_session_stats'"
        ).fetchall()

        if not tables:
            # Créer la table si elle n'existe pas
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mv_session_stats (
                    session_id VARCHAR PRIMARY KEY,
                    match_count INTEGER,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    total_kills INTEGER,
                    total_deaths INTEGER,
                    total_assists INTEGER,
                    kd_ratio DOUBLE,
                    win_rate DOUBLE,
                    avg_accuracy DOUBLE,
                    avg_life_seconds DOUBLE,
                    updated_at TIMESTAMP
                )
            """)

        # Vider et recalculer
        conn.execute("DELETE FROM mv_session_stats")
        conn.execute("""
            INSERT INTO mv_session_stats
            SELECT
                session_id,
                COUNT(*) as match_count,
                MIN(start_time) as start_time,
                MAX(start_time) as end_time,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(assists) as total_assists,
                CASE WHEN SUM(deaths) > 0
                     THEN CAST(SUM(kills) AS DOUBLE) / SUM(deaths)
                     ELSE SUM(kills) END as kd_ratio,
                CASE WHEN COUNT(*) > 0
                     THEN SUM(CASE WHEN outcome = 2 THEN 1.0 ELSE 0.0 END) / COUNT(*)
                     ELSE 0 END as win_rate,
                AVG(accuracy) as avg_accuracy,
                AVG(avg_life_seconds) as avg_life_seconds,
                CURRENT_TIMESTAMP as updated_at
            FROM match_stats
            WHERE session_id IS NOT NULL
            GROUP BY session_id
        """)

        count = conn.execute("SELECT COUNT(*) FROM mv_session_stats").fetchone()[0]
        logger.info(f"mv_session_stats rafraîchie: {count} sessions")
        return count

    except Exception as e:
        logger.error(f"Erreur lors du rafraîchissement de mv_session_stats: {e}")
        return 0


def populate_sessions_table(conn: duckdb.DuckDBPyConnection) -> int:
    """Peuple la table sessions depuis match_stats.

    Args:
        conn: Connexion DuckDB.

    Returns:
        Nombre de sessions insérées.
    """
    logger.info("Peuplement de la table sessions...")

    try:
        # Vérifier si la table existe
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'sessions'"
        ).fetchall()

        if not tables:
            # Créer la table si elle n'existe pas
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id VARCHAR PRIMARY KEY,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    match_count INTEGER,
                    total_kills INTEGER,
                    total_deaths INTEGER,
                    total_assists INTEGER,
                    avg_kda FLOAT,
                    avg_accuracy FLOAT,
                    performance_score FLOAT
                )
            """)

        # Vider et recalculer
        conn.execute("DELETE FROM sessions")
        conn.execute("""
            INSERT INTO sessions (
                session_id, start_time, end_time, match_count,
                total_kills, total_deaths, total_assists,
                avg_kda, avg_accuracy, performance_score
            )
            SELECT
                session_id,
                MIN(start_time) as start_time,
                MAX(start_time) as end_time,
                COUNT(*) as match_count,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(assists) as total_assists,
                CASE WHEN SUM(deaths) > 0
                     THEN CAST(SUM(kills) + SUM(assists) AS DOUBLE) / SUM(deaths)
                     ELSE SUM(kills) + SUM(assists) END as avg_kda,
                AVG(accuracy) as avg_accuracy,
                AVG(performance_score) as performance_score
            FROM match_stats
            WHERE session_id IS NOT NULL
            GROUP BY session_id
        """)

        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        logger.info(f"Table sessions peuplée: {count} sessions")
        return count

    except Exception as e:
        logger.error(f"Erreur lors du peuplement de la table sessions: {e}")
        return 0


def process_player(
    gamertag: str,
    gap_minutes: int = 120,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Traite un joueur.

    Args:
        gamertag: Gamertag du joueur.
        gap_minutes: Gap entre sessions en minutes.
        force: Forcer le recalcul.
        dry_run: Mode dry-run.

    Returns:
        Dict avec les résultats.
    """
    logger.info(f"=== Traitement de {gamertag} ===")

    if not is_duckdb_player(gamertag):
        logger.warning(f"{gamertag} n'est pas un joueur DuckDB v4")
        return {"error": "not_duckdb_v4"}

    db_path = get_player_duckdb_path(gamertag)
    if not db_path or not Path(db_path).exists():
        logger.warning(f"Base de données non trouvée pour {gamertag}")
        return {"error": "db_not_found"}

    results = {"gamertag": gamertag}

    try:
        conn = duckdb.connect(str(db_path))

        # Calculer les sessions
        session_results = compute_sessions_for_db(
            conn, gap_minutes=gap_minutes, force=force, dry_run=dry_run
        )
        results.update(session_results)

        if not dry_run and session_results.get("matches_updated", 0) > 0:
            # Rafraîchir les vues matérialisées
            results["mv_session_stats"] = refresh_session_stats(conn)
            results["sessions_table"] = populate_sessions_table(conn)

        conn.close()

    except Exception as e:
        logger.error(f"Erreur pour {gamertag}: {e}")
        results["error"] = str(e)

    return results


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Calcule et persiste les sessions dans match_stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--gamertag", type=str, help="Gamertag du joueur à traiter")
    group.add_argument("--all", action="store_true", help="Traiter tous les joueurs")

    parser.add_argument(
        "--gap-minutes",
        type=int,
        default=SESSION_CONFIG.default_gap_minutes,
        help=f"Écart max entre parties (défaut: {SESSION_CONFIG.default_gap_minutes} min)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forcer le recalcul même si des sessions existent",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode dry-run : affiche seulement, ne modifie rien",
    )

    args = parser.parse_args()

    logger.info(f"Compute sessions - gap: {args.gap_minutes} min")

    if args.all:
        player_infos = list_duckdb_v4_players()
        players = [p.gamertag for p in player_infos]
        logger.info(f"Joueurs trouvés: {players}")
    else:
        players = [args.gamertag]

    all_results = []
    for gamertag in players:
        result = process_player(
            gamertag,
            gap_minutes=args.gap_minutes,
            force=args.force,
            dry_run=args.dry_run,
        )
        all_results.append(result)

    # Résumé
    logger.info("\n=== RÉSUMÉ ===")
    for r in all_results:
        gamertag = r.get("gamertag", "?")
        if "error" in r:
            logger.warning(f"{gamertag}: Erreur - {r['error']}")
        else:
            sessions = r.get("sessions_computed", 0)
            matches = r.get("matches_updated", 0)
            logger.info(f"{gamertag}: {sessions} sessions, {matches} matchs mis à jour")

    return 0


if __name__ == "__main__":
    sys.exit(main())
