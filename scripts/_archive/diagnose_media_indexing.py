#!/usr/bin/env python3
"""Script de diagnostic complet pour l'indexation des médias.

Ce script vérifie :
1. Si les médias sont indexés dans la DB
2. Si les associations sont créées
3. Si les matchs ont des start_time valides
4. Si les thumbnails sont générés
5. Pourquoi l'association échoue
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ajouter le répertoire racine au path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

import duckdb

from src.utils.paths import PLAYER_DB_FILENAME, PLAYERS_DIR


def check_media_tables(db_path: Path) -> dict:
    """Vérifie l'état des tables médias."""
    result = {
        "db_exists": db_path.exists(),
        "media_files_exists": False,
        "associations_exists": False,
        "media_count": 0,
        "associations_count": 0,
        "videos_without_thumb": 0,
        "errors": [],
    }

    if not result["db_exists"]:
        result["errors"].append(f"DB introuvable: {db_path}")
        return result

    try:
        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            # Vérifier si les tables existent
            tables = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                AND table_name IN ('media_files', 'media_match_associations')
                """
            ).fetchall()
            table_names = {row[0] for row in tables}

            result["media_files_exists"] = "media_files" in table_names
            result["associations_exists"] = "media_match_associations" in table_names

            if result["media_files_exists"]:
                # Compter les médias
                result["media_count"] = conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[
                    0
                ]

                # Compter les vidéos sans thumbnail
                result["videos_without_thumb"] = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM media_files
                    WHERE kind = 'video'
                    AND (thumbnail_path IS NULL OR thumbnail_path = '')
                    """
                ).fetchone()[0]

                # Vérifier les colonnes
                cols = conn.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'main'
                    AND table_name = 'media_files'
                    """
                ).fetchall()
                column_names = {row[0] for row in cols}
                if "owner_xuid" in column_names:
                    result["errors"].append(
                        "⚠️  La colonne owner_xuid existe encore - migration nécessaire"
                    )

            if result["associations_exists"]:
                result["associations_count"] = conn.execute(
                    "SELECT COUNT(*) FROM media_match_associations"
                ).fetchone()[0]

        finally:
            conn.close()

    except Exception as e:
        result["errors"].append(f"Erreur lecture DB: {e}")

    return result


def check_match_stats(db_path: Path) -> dict:
    """Vérifie l'état des matchs dans la DB."""
    result = {
        "match_stats_exists": False,
        "total_matches": 0,
        "matches_with_start_time": 0,
        "matches_with_null_start_time": 0,
        "sample_start_times": [],
        "errors": [],
    }

    if not db_path.exists():
        result["errors"].append(f"DB introuvable: {db_path}")
        return result

    try:
        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            # Vérifier si la table existe
            tables = conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                AND table_name = 'match_stats'
                """
            ).fetchall()

            if not tables:
                result["errors"].append("Table match_stats introuvable")
                return result

            result["match_stats_exists"] = True

            # Compter les matchs
            result["total_matches"] = conn.execute("SELECT COUNT(*) FROM match_stats").fetchone()[0]

            # Compter les matchs avec start_time
            result["matches_with_start_time"] = conn.execute(
                "SELECT COUNT(*) FROM match_stats WHERE start_time IS NOT NULL"
            ).fetchone()[0]

            result["matches_with_null_start_time"] = (
                result["total_matches"] - result["matches_with_start_time"]
            )

            # Échantillon de start_time
            sample = conn.execute(
                """
                SELECT start_time, match_id
                FROM match_stats
                WHERE start_time IS NOT NULL
                ORDER BY start_time DESC
                LIMIT 5
                """
            ).fetchall()
            result["sample_start_times"] = [
                {"match_id": row[1], "start_time": str(row[0])} for row in sample
            ]

        finally:
            conn.close()

    except Exception as e:
        result["errors"].append(f"Erreur lecture match_stats: {e}")

    return result


def check_all_player_dbs() -> list[dict]:
    """Vérifie toutes les DBs joueurs."""
    results = []
    if not PLAYERS_DIR.exists():
        return results

    for player_dir in PLAYERS_DIR.iterdir():
        if not player_dir.is_dir():
            continue

        db_path = player_dir / PLAYER_DB_FILENAME
        if not db_path.exists():
            continue

        gamertag = player_dir.name
        match_stats = check_match_stats(db_path)
        media_tables = check_media_tables(db_path)

        results.append(
            {
                "gamertag": gamertag,
                "db_path": str(db_path),
                "match_stats": match_stats,
                "media_tables": media_tables,
            }
        )

    return results


def main() -> int:
    """Point d'entrée principal."""
    print("=" * 80)
    print("DIAGNOSTIC COMPLET - INDEXATION MÉDIAS")
    print("=" * 80)
    print()

    # Vérifier toutes les DBs joueurs
    all_dbs = check_all_player_dbs()

    if not all_dbs:
        print("❌ Aucune DB joueur trouvée dans data/players/")
        return 1

    print(f"📁 {len(all_dbs)} DB(s) joueur(s) trouvée(s)\n")

    for db_info in all_dbs:
        gamertag = db_info["gamertag"]
        print(f"{'=' * 80}")
        print(f"Joueur: {gamertag}")
        print(f"DB: {db_info['db_path']}")
        print(f"{'=' * 80}\n")

        # Match stats
        match_stats = db_info["match_stats"]
        print("📊 Match Stats:")
        if match_stats["errors"]:
            for err in match_stats["errors"]:
                print(f"  ❌ {err}")
        else:
            print(f"  ✅ Table existe: {match_stats['match_stats_exists']}")
            print(f"  📈 Total matchs: {match_stats['total_matches']}")
            print(f"  ✅ Avec start_time: {match_stats['matches_with_start_time']}")
            print(f"  ⚠️  Sans start_time: {match_stats['matches_with_null_start_time']}")
            if match_stats["sample_start_times"]:
                print("  📅 Exemples de start_time:")
                for sample in match_stats["sample_start_times"][:3]:
                    print(f"     - {sample['match_id']}: {sample['start_time']}")
        print()

        # Media tables
        media_tables = db_info["media_tables"]
        print("🎬 Tables Médias:")
        if media_tables["errors"]:
            for err in media_tables["errors"]:
                print(f"  ❌ {err}")
        else:
            print(f"  ✅ media_files existe: {media_tables['media_files_exists']}")
            print(f"  ✅ associations existe: {media_tables['associations_exists']}")
            print(f"  📁 Médias indexés: {media_tables['media_count']}")
            print(f"  🔗 Associations créées: {media_tables['associations_count']}")
            print(f"  🎥 Vidéos sans thumbnail: {media_tables['videos_without_thumb']}")
        print()

        # Diagnostic associations
        if media_tables["media_count"] > 0 and media_tables["associations_count"] == 0:
            print("⚠️  PROBLÈME: Des médias sont indexés mais aucune association créée")
            print("   Causes possibles:")
            if match_stats["matches_with_start_time"] == 0:
                print("   - Aucun match avec start_time valide")
            else:
                print("   - Les dates des médias ne correspondent pas aux matchs")
                print("   - La tolérance temporelle est trop faible")
                print("   - Problème de conversion de dates/timezone")
        print()

    print("=" * 80)
    print("RÉSUMÉ")
    print("=" * 80)

    total_media = sum(db["media_tables"]["media_count"] for db in all_dbs)
    total_associations = sum(db["media_tables"]["associations_count"] for db in all_dbs)
    total_matches = sum(db["match_stats"]["matches_with_start_time"] for db in all_dbs)

    print(f"📁 Médias indexés: {total_media}")
    print(f"🔗 Associations créées: {total_associations}")
    print(f"🎮 Matchs avec start_time: {total_matches}")

    if total_media > 0 and total_associations == 0:
        print("\n❌ PROBLÈME CRITIQUE: Aucune association créée")
        if total_matches == 0:
            print("   → Aucun match avec start_time valide dans les DBs")
        else:
            print("   → Vérifier la correspondance temporelle entre médias et matchs")

    return 0


if __name__ == "__main__":
    sys.exit(main())
