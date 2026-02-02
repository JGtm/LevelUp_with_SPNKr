#!/usr/bin/env python3
"""
Script de migration des donnees joueur SQLite vers DuckDB.

Ce script migre spnkr_gt_{gamertag}.db (SQLite legacy) vers
data/players/{gamertag}/stats.duckdb (DuckDB).

Usage:
    python scripts/migrate_player_to_duckdb.py --gamertag JGtm
    python scripts/migrate_player_to_duckdb.py --all
    python scripts/migrate_player_to_duckdb.py --gamertag JGtm --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ajouter le repertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import duckdb
except ImportError:
    print("ERREUR: DuckDB non installe. Executez: pip install duckdb")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Configuration des chemins
DATA_DIR = Path(__file__).parent.parent / "data"
PLAYERS_DIR = DATA_DIR / "players"
DB_PROFILES_PATH = Path(__file__).parent.parent / "db_profiles.json"


def load_db_profiles() -> dict[str, Any]:
    """Charge la configuration des profils joueurs."""
    if not DB_PROFILES_PATH.exists():
        return {"profiles": {}}
    with open(DB_PROFILES_PATH, encoding="utf-8") as f:
        return json.load(f)


def create_player_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Cree le schema des tables joueur dans DuckDB."""

    # Table match_stats (faits des matchs)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS match_stats (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP,
            playlist_id VARCHAR,
            playlist_name VARCHAR,
            map_id VARCHAR,
            map_name VARCHAR,
            pair_id VARCHAR,
            pair_name VARCHAR,
            game_variant_id VARCHAR,
            game_variant_name VARCHAR,
            outcome TINYINT,
            team_id TINYINT,
            rank SMALLINT,
            kills SMALLINT,
            deaths SMALLINT,
            assists SMALLINT,
            kda FLOAT,
            accuracy FLOAT,
            headshot_kills SMALLINT,
            max_killing_spree SMALLINT,
            time_played_seconds INTEGER,
            avg_life_seconds FLOAT,
            my_team_score SMALLINT,
            enemy_team_score SMALLINT,
            team_mmr FLOAT,
            enemy_mmr FLOAT,
            -- Colonnes de combat détaillées
            damage_dealt FLOAT,
            damage_taken FLOAT,
            shots_fired INTEGER,
            shots_hit INTEGER,
            grenade_kills SMALLINT,
            melee_kills SMALLINT,
            power_weapon_kills SMALLINT,
            expected_kills FLOAT,
            expected_deaths FLOAT,
            score INTEGER,
            personal_score INTEGER,
            -- Colonnes objectives
            objectives_completed SMALLINT,
            zone_captures SMALLINT,
            zone_defensive_kills SMALLINT,
            zone_offensive_kills SMALLINT,
            zone_secures SMALLINT,
            zone_occupation_time FLOAT,
            ctf_flag_captures SMALLINT,
            ctf_flag_grabs SMALLINT,
            ctf_flag_returners_killed SMALLINT,
            ctf_flag_returns SMALLINT,
            ctf_flag_carriers_killed SMALLINT,
            ctf_time_as_carrier_seconds FLOAT,
            oddball_time_held_seconds FLOAT,
            oddball_kills_as_carrier SMALLINT,
            oddball_kills_as_non_carrier SMALLINT,
            stockpile_seeds_deposited SMALLINT,
            stockpile_seeds_collected SMALLINT,
            -- Colonnes metadata
            mode_category VARCHAR,
            is_ranked BOOLEAN DEFAULT FALSE,
            is_firefight BOOLEAN DEFAULT FALSE,
            left_early BOOLEAN DEFAULT FALSE,
            -- Colonnes session/social (existantes)
            session_id VARCHAR,
            session_label VARCHAR,
            performance_score FLOAT,
            teammates_signature VARCHAR,
            known_teammates_count SMALLINT,
            is_with_friends BOOLEAN,
            friends_xuids VARCHAR,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    # Table teammates_aggregate
    conn.execute("""
        CREATE TABLE IF NOT EXISTS teammates_aggregate (
            teammate_xuid VARCHAR PRIMARY KEY,
            teammate_gamertag VARCHAR,
            matches_together INTEGER DEFAULT 0,
            same_team_count INTEGER DEFAULT 0,
            opposite_team_count INTEGER DEFAULT 0,
            wins_together INTEGER DEFAULT 0,
            losses_together INTEGER DEFAULT 0,
            first_played TIMESTAMP,
            last_played TIMESTAMP,
            computed_at TIMESTAMP
        )
    """)

    # Table medals_earned (vide, a remplir plus tard)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS medals_earned (
            match_id VARCHAR,
            medal_name_id INTEGER,
            count SMALLINT,
            PRIMARY KEY (match_id, medal_name_id)
        )
    """)

    # Table antagonists (nouvelle)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS antagonists (
            opponent_xuid VARCHAR PRIMARY KEY,
            opponent_gamertag VARCHAR,
            times_killed INTEGER DEFAULT 0,
            times_killed_by INTEGER DEFAULT 0,
            matches_against INTEGER DEFAULT 0,
            last_encounter TIMESTAMP
        )
    """)

    # Table skill_history (nouvelle)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS skill_history (
            playlist_id VARCHAR,
            recorded_at TIMESTAMP,
            csr INTEGER,
            tier VARCHAR,
            division INTEGER,
            matches_played INTEGER,
            PRIMARY KEY (playlist_id, recorded_at)
        )
    """)

    # Table sessions
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

    # Index
    conn.execute("CREATE INDEX IF NOT EXISTS idx_match_stats_time ON match_stats(start_time)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_match_stats_playlist ON match_stats(playlist_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_match_stats_outcome ON match_stats(outcome)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_match_stats_session ON match_stats(session_id)")


def migrate_player(
    gamertag: str,
    legacy_db_path: Path,
    target_db_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """
    Migre les donnees d'un joueur de SQLite vers DuckDB.

    Returns:
        dict avec les statistiques de migration
    """
    results = {
        "gamertag": gamertag,
        "success": False,
        "match_stats_count": 0,
        "teammates_count": 0,
        "errors": [],
    }

    if not legacy_db_path.exists():
        results["errors"].append(f"Base legacy non trouvee: {legacy_db_path}")
        logger.error(results["errors"][-1])
        return results

    # Creer le dossier du joueur si necessaire
    target_db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Connexion DuckDB
        if dry_run:
            conn = duckdb.connect(":memory:")
            logger.info(f"[DRY-RUN] Migration de {gamertag} en memoire")
        else:
            # Supprimer l'ancien fichier si existant
            if target_db_path.exists():
                backup_path = target_db_path.with_suffix(".duckdb.bak")
                import shutil

                shutil.copy2(target_db_path, backup_path)
                target_db_path.unlink()
                logger.info(f"Backup cree: {backup_path}")

            conn = duckdb.connect(str(target_db_path))
            logger.info(f"Creation de: {target_db_path}")

        # Creer le schema
        create_player_schema(conn)
        logger.info("Schema cree")

        # Attacher la base SQLite legacy
        conn.execute(f"ATTACH '{legacy_db_path}' AS legacy (TYPE SQLITE, READ_ONLY)")
        logger.info(f"Source SQLite attachee: {legacy_db_path}")

        # Migrer MatchCache -> match_stats
        try:
            # Verifier si MatchCache existe
            check = conn.execute("SELECT COUNT(*) FROM legacy.MatchCache").fetchone()
            match_count = check[0] if check else 0

            if match_count > 0:
                conn.execute("""
                    INSERT INTO match_stats
                    SELECT
                        match_id,
                        TRY_CAST(start_time AS TIMESTAMP) as start_time,
                        playlist_id,
                        playlist_name,
                        map_id,
                        map_name,
                        pair_id,
                        pair_name,
                        game_variant_id,
                        game_variant_name,
                        CAST(outcome AS TINYINT) as outcome,
                        CAST(last_team_id AS TINYINT) as team_id,
                        CAST(kills AS SMALLINT) as kills,
                        CAST(deaths AS SMALLINT) as deaths,
                        CAST(assists AS SMALLINT) as assists,
                        CAST(kda AS FLOAT) as kda,
                        CAST(accuracy AS FLOAT) as accuracy,
                        CAST(headshot_kills AS SMALLINT) as headshot_kills,
                        CAST(max_killing_spree AS SMALLINT) as max_killing_spree,
                        CAST(time_played_seconds AS INTEGER) as time_played_seconds,
                        CAST(average_life_seconds AS FLOAT) as avg_life_seconds,
                        CAST(my_team_score AS SMALLINT) as my_team_score,
                        CAST(enemy_team_score AS SMALLINT) as enemy_team_score,
                        CAST(team_mmr AS FLOAT) as team_mmr,
                        CAST(enemy_mmr AS FLOAT) as enemy_mmr,
                        CAST(session_id AS VARCHAR) as session_id,
                        session_label,
                        CAST(performance_score AS FLOAT) as performance_score,
                        CAST(is_firefight AS BOOLEAN) as is_firefight,
                        teammates_signature,
                        CAST(known_teammates_count AS SMALLINT) as known_teammates_count,
                        CAST(is_with_friends AS BOOLEAN) as is_with_friends,
                        friends_xuids,
                        TRY_CAST(created_at AS TIMESTAMP) as created_at,
                        TRY_CAST(updated_at AS TIMESTAMP) as updated_at
                    FROM legacy.MatchCache
                """)
                results["match_stats_count"] = match_count
                logger.info(f"  [OK] match_stats: {match_count} lignes")
            else:
                logger.warning("  [!] MatchCache vide")

        except Exception as e:
            error_msg = f"Erreur migration MatchCache: {e}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # Migrer TeammatesAggregate -> teammates_aggregate
        try:
            check = conn.execute("SELECT COUNT(*) FROM legacy.TeammatesAggregate").fetchone()
            teammates_count = check[0] if check else 0

            if teammates_count > 0:
                conn.execute("""
                    INSERT INTO teammates_aggregate
                    SELECT
                        teammate_xuid,
                        teammate_gamertag,
                        CAST(matches_together AS INTEGER),
                        CAST(same_team_count AS INTEGER),
                        CAST(opposite_team_count AS INTEGER),
                        CAST(wins_together AS INTEGER),
                        CAST(losses_together AS INTEGER),
                        TRY_CAST(first_played AS TIMESTAMP),
                        TRY_CAST(last_played AS TIMESTAMP),
                        TRY_CAST(computed_at AS TIMESTAMP)
                    FROM legacy.TeammatesAggregate
                """)
                results["teammates_count"] = teammates_count
                logger.info(f"  [OK] teammates_aggregate: {teammates_count} lignes")
            else:
                logger.warning("  [!] TeammatesAggregate vide")

        except Exception as e:
            error_msg = f"Erreur migration TeammatesAggregate: {e}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # Detacher la source
        conn.execute("DETACH legacy")

        # Validation finale
        logger.info("Validation finale...")

        match_check = conn.execute("SELECT COUNT(*) FROM match_stats").fetchone()[0]
        teammates_check = conn.execute("SELECT COUNT(*) FROM teammates_aggregate").fetchone()[0]

        if (
            match_check == results["match_stats_count"]
            and teammates_check == results["teammates_count"]
        ):
            logger.info("  [OK] Validation reussie")
            results["success"] = True
        else:
            logger.warning(
                f"  [!] Difference detectee: match_stats {match_check}/{results['match_stats_count']}, teammates {teammates_check}/{results['teammates_count']}"
            )

        conn.close()

    except Exception as e:
        results["errors"].append(f"Erreur fatale: {e}")
        logger.error(f"Erreur fatale: {e}")
        import traceback

        if verbose:
            traceback.print_exc()

    return results


def print_summary(all_results: list[dict[str, Any]]) -> None:
    """Affiche un resume de toutes les migrations."""
    print("\n" + "=" * 60)
    print("RESUME DE LA MIGRATION JOUEURS")
    print("=" * 60)

    success_count = sum(1 for r in all_results if r["success"])
    total_matches = sum(r["match_stats_count"] for r in all_results)
    total_teammates = sum(r["teammates_count"] for r in all_results)

    print(f"\nJoueurs migres: {success_count}/{len(all_results)}")
    print(f"Total matchs: {total_matches}")
    print(f"Total coequipiers: {total_teammates}")

    print("\nDetail par joueur:")
    for result in all_results:
        status = "[OK]" if result["success"] else "[X]"
        print(
            f"  {status} {result['gamertag']}: {result['match_stats_count']} matchs, {result['teammates_count']} coequipiers"
        )
        if result["errors"]:
            for error in result["errors"]:
                print(f"      Erreur: {error}")

    print("\n" + "=" * 60)


def main() -> int:
    """Point d'entree principal."""
    parser = argparse.ArgumentParser(
        description="Migre les donnees joueur de SQLite vers DuckDB",
    )
    parser.add_argument(
        "--gamertag",
        help="Gamertag du joueur a migrer",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrer tous les joueurs de db_profiles.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule la migration sans ecrire",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Affiche plus de details",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.gamertag and not args.all:
        parser.error("Specifie --gamertag ou --all")
        return 1

    # Charger les profils
    profiles = load_db_profiles()

    if not profiles.get("profiles"):
        logger.error("Aucun profil trouve dans db_profiles.json")
        return 1

    # Determiner les joueurs a migrer
    gamertags = list(profiles["profiles"].keys()) if args.all else [args.gamertag]

    logger.info("=" * 60)
    logger.info("Migration SQLite -> DuckDB (donnees joueur)")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("[DRY-RUN] Aucune modification ne sera effectuee")

    all_results = []

    for gamertag in gamertags:
        if gamertag not in profiles["profiles"]:
            logger.warning(f"Joueur {gamertag} non trouve dans db_profiles.json")
            continue

        profile = profiles["profiles"][gamertag]
        legacy_path = Path(profile.get("legacy_db_path", f"data/spnkr_gt_{gamertag}.db"))
        target_path = Path(profile.get("db_path", f"data/players/{gamertag}/stats.duckdb"))

        logger.info(f"\n--- Migration de {gamertag} ---")
        logger.info(f"Source: {legacy_path}")
        logger.info(f"Destination: {target_path}")

        result = migrate_player(
            gamertag=gamertag,
            legacy_db_path=legacy_path,
            target_db_path=target_path,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        all_results.append(result)

    print_summary(all_results)

    # Retourner 0 si au moins une migration a reussi
    return 0 if any(r["success"] for r in all_results) else 1


if __name__ == "__main__":
    sys.exit(main())
