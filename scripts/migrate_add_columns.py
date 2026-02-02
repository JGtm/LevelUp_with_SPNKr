#!/usr/bin/env python3
"""Script de migration: Ajoute les colonnes manquantes à match_stats et supprime weapon_stats.

Ce script met à jour les bases DuckDB existantes pour les aligner avec le schéma v4.1:
1. Ajoute les colonnes manquantes à match_stats (combat, objectives, metadata)
2. Supprime la table weapon_stats (vide et inutile - l'API ne fournit pas ces données)

Usage:
    python scripts/migrate_add_columns.py                    # Migre tous les joueurs
    python scripts/migrate_add_columns.py --gamertag John    # Migre un joueur spécifique
    python scripts/migrate_add_columns.py --dry-run          # Affiche sans modifier
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
PLAYERS_DIR = DATA_DIR / "players"

# Colonnes à ajouter à match_stats (avec types DuckDB)
COLUMNS_TO_ADD = [
    ("rank", "SMALLINT"),
    ("damage_dealt", "FLOAT"),
    ("damage_taken", "FLOAT"),
    ("shots_fired", "INTEGER"),
    ("shots_hit", "INTEGER"),
    ("grenade_kills", "SMALLINT"),
    ("melee_kills", "SMALLINT"),
    ("power_weapon_kills", "SMALLINT"),
    ("score", "INTEGER"),
    ("personal_score", "INTEGER"),
    ("mode_category", "VARCHAR"),
    ("is_ranked", "BOOLEAN DEFAULT FALSE"),
    ("left_early", "BOOLEAN DEFAULT FALSE"),
]

# Colonnes objectives à supprimer (non exploitables - l'API ne fournit pas ces données)
COLUMNS_TO_DROP = [
    "expected_kills",
    "expected_deaths",
    "objectives_completed",
    "zone_captures",
    "zone_defensive_kills",
    "zone_offensive_kills",
    "zone_secures",
    "zone_occupation_time",
    "ctf_flag_captures",
    "ctf_flag_grabs",
    "ctf_flag_returners_killed",
    "ctf_flag_returns",
    "ctf_flag_carriers_killed",
    "ctf_time_as_carrier_seconds",
    "oddball_time_held_seconds",
    "oddball_kills_as_carrier",
    "oddball_kills_as_non_carrier",
    "stockpile_seeds_deposited",
    "stockpile_seeds_collected",
]


def get_existing_columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    """Récupère les colonnes existantes d'une table."""
    try:
        result = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
        return {row[1] for row in result}
    except Exception:
        return set()


def table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    """Vérifie si une table existe."""
    try:
        result = conn.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
        ).fetchone()
        return result is not None
    except Exception:
        return False


def migrate_player_db(db_path: Path, dry_run: bool = False, verbose: bool = False) -> dict:
    """Migre une base de données joueur.

    Returns:
        dict avec columns_added, columns_dropped, weapon_stats_dropped, errors
    """
    result = {
        "columns_added": [],
        "columns_dropped": [],
        "weapon_stats_dropped": False,
        "errors": [],
    }

    if not db_path.exists():
        result["errors"].append(f"Base non trouvée: {db_path}")
        return result

    try:
        conn = duckdb.connect(str(db_path), read_only=dry_run)

        # 1. Vérifier si match_stats existe
        if not table_exists(conn, "match_stats"):
            result["errors"].append("Table match_stats non trouvée")
            conn.close()
            return result

        # 2. Récupérer les colonnes existantes
        existing_cols = get_existing_columns(conn, "match_stats")
        if verbose:
            print(f"  Colonnes existantes: {len(existing_cols)}")

        # 3. Ajouter les colonnes manquantes
        for col_name, col_type in COLUMNS_TO_ADD:
            if col_name not in existing_cols:
                if dry_run:
                    print(f"  [DRY-RUN] ALTER TABLE match_stats ADD COLUMN {col_name} {col_type}")
                    result["columns_added"].append(col_name)
                else:
                    try:
                        conn.execute(f"ALTER TABLE match_stats ADD COLUMN {col_name} {col_type}")
                        result["columns_added"].append(col_name)
                        if verbose:
                            print(f"  + Ajouté: {col_name}")
                    except Exception as e:
                        result["errors"].append(f"Erreur ajout {col_name}: {e}")

        # 4. Supprimer les colonnes objectives obsolètes
        for col_name in COLUMNS_TO_DROP:
            if col_name in existing_cols:
                if dry_run:
                    print(f"  [DRY-RUN] ALTER TABLE match_stats DROP COLUMN {col_name}")
                    result["columns_dropped"].append(col_name)
                else:
                    try:
                        conn.execute(f"ALTER TABLE match_stats DROP COLUMN {col_name}")
                        result["columns_dropped"].append(col_name)
                        if verbose:
                            print(f"  - Supprimé: {col_name}")
                    except Exception as e:
                        result["errors"].append(f"Erreur suppression {col_name}: {e}")

        # 5. Supprimer weapon_stats si elle existe
        if table_exists(conn, "weapon_stats"):
            if dry_run:
                print("  [DRY-RUN] DROP TABLE weapon_stats")
                result["weapon_stats_dropped"] = True
            else:
                try:
                    conn.execute("DROP TABLE weapon_stats")
                    result["weapon_stats_dropped"] = True
                    if verbose:
                        print("  - Supprimé: weapon_stats")
                except Exception as e:
                    result["errors"].append(f"Erreur suppression weapon_stats: {e}")

        conn.close()

    except Exception as e:
        result["errors"].append(f"Erreur connexion: {e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Migration schéma match_stats v4.1")
    parser.add_argument("--gamertag", "-g", help="Gamertag spécifique à migrer")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Simulation sans modification")
    parser.add_argument("--verbose", "-v", action="store_true", help="Affichage détaillé")
    args = parser.parse_args()

    print("=" * 60)
    print("Migration schéma match_stats v4.1")
    print("=" * 60)

    if args.dry_run:
        print("Mode DRY-RUN : aucune modification ne sera effectuée\n")

    # Lister les joueurs à migrer
    if args.gamertag:
        player_dirs = [PLAYERS_DIR / args.gamertag]
    else:
        player_dirs = [d for d in PLAYERS_DIR.iterdir() if d.is_dir()]

    total_columns_added = 0
    total_columns_dropped = 0
    total_weapon_stats_dropped = 0
    total_errors = 0

    for player_dir in player_dirs:
        db_path = player_dir / "stats.duckdb"
        if not db_path.exists():
            continue

        gamertag = player_dir.name
        print(f"\n[{gamertag}]")

        result = migrate_player_db(db_path, dry_run=args.dry_run, verbose=args.verbose)

        if result["columns_added"]:
            total_columns_added += len(result["columns_added"])
            if not args.verbose:
                print(f"  + {len(result['columns_added'])} colonnes ajoutées")

        if result["columns_dropped"]:
            total_columns_dropped += len(result["columns_dropped"])
            if not args.verbose:
                print(f"  - {len(result['columns_dropped'])} colonnes supprimées")

        if result["weapon_stats_dropped"]:
            total_weapon_stats_dropped += 1
            if not args.verbose:
                print("  - Table weapon_stats supprimée")

        if result["errors"]:
            total_errors += len(result["errors"])
            for err in result["errors"]:
                print(f"  ❌ {err}")

        if (
            not result["columns_added"]
            and not result["columns_dropped"]
            and not result["weapon_stats_dropped"]
            and not result["errors"]
        ):
            print("  ✓ Déjà à jour")

    # Résumé
    print("\n" + "=" * 60)
    print("Résumé")
    print("=" * 60)
    print(f"Joueurs traités: {len(player_dirs)}")
    print(f"Colonnes ajoutées: {total_columns_added}")
    print(f"Colonnes supprimées: {total_columns_dropped}")
    print(f"Tables weapon_stats supprimées: {total_weapon_stats_dropped}")
    if total_errors:
        print(f"Erreurs: {total_errors}")
    print()


if __name__ == "__main__":
    main()
