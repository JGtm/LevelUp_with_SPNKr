#!/usr/bin/env python3
"""Diagnostic pour comprendre quels matchs sont encore sélectionnés par le backfill.

Ce script analyse quels types de données manquent dans les matchs détectés
par le backfill avec --all-data.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ajouter le répertoire racine au path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Fix encoding Windows
import io

import duckdb

from src.ui.sync import get_player_duckdb_path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def analyze_missing_data(db_path: Path, xuid: str) -> None:
    """Analyse quels types de données manquent dans les matchs."""
    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        # Trouver tous les matchs
        all_matches = conn.execute(
            "SELECT DISTINCT match_id FROM match_stats ORDER BY start_time DESC"
        ).fetchall()
        all_match_ids = [r[0] for r in all_matches]
        print(f"📊 Total de matchs dans la DB: {len(all_match_ids)}")

        # Matchs avec toutes les données principales
        complete_matches = conn.execute(
            """
            SELECT DISTINCT ms.match_id
            FROM match_stats ms
            WHERE ms.match_id IN (SELECT DISTINCT match_id FROM medals_earned)
              AND ms.match_id IN (SELECT DISTINCT match_id FROM highlight_events)
              AND ms.match_id IN (SELECT DISTINCT match_id FROM player_match_stats WHERE xuid = ?)
              AND ms.match_id IN (SELECT DISTINCT match_id FROM personal_score_awards WHERE xuid = ?)
              AND ms.match_id IN (SELECT DISTINCT match_id FROM match_participants)
            """,
            [xuid, xuid],
        ).fetchall()
        complete_match_ids = {r[0] for r in complete_matches}
        print(f"✅ Matchs avec toutes les données principales: {len(complete_match_ids)}")

        # Analyser ce qui manque dans les autres matchs
        incomplete_match_ids = [m for m in all_match_ids if m not in complete_match_ids]
        print(f"\n🔍 Analyse des {len(incomplete_match_ids)} matchs incomplets:\n")

        if not incomplete_match_ids:
            print("Tous les matchs sont complets !")
            return

        # Compter les matchs manquants par type de donnée
        stats = {
            "medals": 0,
            "events": 0,
            "skill": 0,
            "personal_scores": 0,
            "participants": 0,
            "participants_scores": 0,
            "participants_kda": 0,
            "participants_shots": 0,
            "accuracy": 0,
            "shots": 0,
            "enemy_mmr": 0,
            "assets": 0,
        }

        # Vérifier chaque type de donnée
        for match_id in incomplete_match_ids:
            # Medals
            has_medals = conn.execute(
                "SELECT COUNT(*) FROM medals_earned WHERE match_id = ?", [match_id]
            ).fetchone()[0]
            if not has_medals:
                stats["medals"] += 1

            # Events
            has_events = conn.execute(
                "SELECT COUNT(*) FROM highlight_events WHERE match_id = ?", [match_id]
            ).fetchone()[0]
            if not has_events:
                stats["events"] += 1

            # Skill
            has_skill = conn.execute(
                "SELECT COUNT(*) FROM player_match_stats WHERE match_id = ? AND xuid = ?",
                [match_id, xuid],
            ).fetchone()[0]
            if not has_skill:
                stats["skill"] += 1

            # Personal scores
            has_personal_scores = conn.execute(
                "SELECT COUNT(*) FROM personal_score_awards WHERE match_id = ? AND xuid = ?",
                [match_id, xuid],
            ).fetchone()[0]
            if not has_personal_scores:
                stats["personal_scores"] += 1

            # Participants
            has_participants = conn.execute(
                "SELECT COUNT(*) FROM match_participants WHERE match_id = ?", [match_id]
            ).fetchone()[0]
            if not has_participants:
                stats["participants"] += 1

            # Participants scores
            if has_participants:
                missing_scores = conn.execute(
                    """
                    SELECT COUNT(*) FROM match_participants
                    WHERE match_id = ? AND (rank IS NULL OR score IS NULL)
                    """,
                    [match_id],
                ).fetchone()[0]
                if missing_scores > 0:
                    stats["participants_scores"] += 1

            # Participants KDA
            if has_participants:
                missing_kda = conn.execute(
                    """
                    SELECT COUNT(*) FROM match_participants
                    WHERE match_id = ? AND (kills IS NULL OR deaths IS NULL OR assists IS NULL)
                    """,
                    [match_id],
                ).fetchone()[0]
                if missing_kda > 0:
                    stats["participants_kda"] += 1

            # Participants shots
            if has_participants:
                missing_shots = conn.execute(
                    """
                    SELECT COUNT(*) FROM match_participants
                    WHERE match_id = ? AND (shots_fired IS NULL OR shots_hit IS NULL)
                    """,
                    [match_id],
                ).fetchone()[0]
                if missing_shots > 0:
                    stats["participants_shots"] += 1

            # Accuracy
            missing_accuracy = conn.execute(
                "SELECT COUNT(*) FROM match_stats WHERE match_id = ? AND accuracy IS NULL",
                [match_id],
            ).fetchone()[0]
            if missing_accuracy > 0:
                stats["accuracy"] += 1

            # Shots
            missing_shots = conn.execute(
                """
                SELECT COUNT(*) FROM match_stats
                WHERE match_id = ? AND (shots_fired IS NULL OR shots_hit IS NULL)
                """,
                [match_id],
            ).fetchone()[0]
            if missing_shots > 0:
                stats["shots"] += 1

            # Enemy MMR
            missing_enemy_mmr = conn.execute(
                """
                SELECT COUNT(*) FROM player_match_stats
                WHERE match_id = ? AND xuid = ? AND enemy_mmr IS NULL
                """,
                [match_id, xuid],
            ).fetchone()[0]
            if missing_enemy_mmr > 0:
                stats["enemy_mmr"] += 1

            # Assets
            missing_assets = conn.execute(
                """
                SELECT COUNT(*) FROM match_stats
                WHERE match_id = ?
                  AND (
                    playlist_name IS NULL OR playlist_name = playlist_id
                    OR map_name IS NULL OR map_name = map_id
                    OR pair_name IS NULL OR pair_name = pair_id
                    OR game_variant_name IS NULL OR game_variant_name = game_variant_id
                  )
                """,
                [match_id],
            ).fetchone()[0]
            if missing_assets > 0:
                stats["assets"] += 1

        # Afficher les résultats
        print("Types de données manquantes (par nombre de matchs):")
        for data_type, count in sorted(stats.items(), key=lambda x: -x[1]):
            if count > 0:
                percentage = (count / len(incomplete_match_ids)) * 100
                print(f"  - {data_type:20s}: {count:4d} matchs ({percentage:5.1f}%)")

        # Analyser les matchs qui ont toutes les données principales mais manquent des données secondaires
        print("\n📈 Matchs avec données principales complètes mais données secondaires manquantes:")
        secondary_only = []
        for match_id in incomplete_match_ids:
            if match_id in complete_match_ids:
                secondary_only.append(match_id)

        if secondary_only:
            print(f"  {len(secondary_only)} matchs ont toutes les données principales")
            print("  Mais ils manquent encore des données secondaires:")
            secondary_stats = {
                "participants_scores": 0,
                "participants_kda": 0,
                "participants_shots": 0,
                "accuracy": 0,
                "shots": 0,
                "enemy_mmr": 0,
                "assets": 0,
            }
            for match_id in secondary_only:
                # Participants scores
                if (
                    conn.execute(
                        """
                    SELECT COUNT(*) FROM match_participants
                    WHERE match_id = ? AND (rank IS NULL OR score IS NULL)
                    """,
                        [match_id],
                    ).fetchone()[0]
                    > 0
                ):
                    secondary_stats["participants_scores"] += 1

                # Participants KDA
                if (
                    conn.execute(
                        """
                    SELECT COUNT(*) FROM match_participants
                    WHERE match_id = ? AND (kills IS NULL OR deaths IS NULL OR assists IS NULL)
                    """,
                        [match_id],
                    ).fetchone()[0]
                    > 0
                ):
                    secondary_stats["participants_kda"] += 1

                # Participants shots
                if (
                    conn.execute(
                        """
                    SELECT COUNT(*) FROM match_participants
                    WHERE match_id = ? AND (shots_fired IS NULL OR shots_hit IS NULL)
                    """,
                        [match_id],
                    ).fetchone()[0]
                    > 0
                ):
                    secondary_stats["participants_shots"] += 1

                # Accuracy
                if (
                    conn.execute(
                        "SELECT COUNT(*) FROM match_stats WHERE match_id = ? AND accuracy IS NULL",
                        [match_id],
                    ).fetchone()[0]
                    > 0
                ):
                    secondary_stats["accuracy"] += 1

                # Shots
                if (
                    conn.execute(
                        """
                    SELECT COUNT(*) FROM match_stats
                    WHERE match_id = ? AND (shots_fired IS NULL OR shots_hit IS NULL)
                    """,
                        [match_id],
                    ).fetchone()[0]
                    > 0
                ):
                    secondary_stats["shots"] += 1

                # Enemy MMR
                if (
                    conn.execute(
                        """
                    SELECT COUNT(*) FROM player_match_stats
                    WHERE match_id = ? AND xuid = ? AND enemy_mmr IS NULL
                    """,
                        [match_id, xuid],
                    ).fetchone()[0]
                    > 0
                ):
                    secondary_stats["enemy_mmr"] += 1

                # Assets
                if (
                    conn.execute(
                        """
                    SELECT COUNT(*) FROM match_stats
                    WHERE match_id = ?
                      AND (
                        playlist_name IS NULL OR playlist_name = playlist_id
                        OR map_name IS NULL OR map_name = map_id
                        OR pair_name IS NULL OR pair_name = pair_id
                        OR game_variant_name IS NULL OR game_variant_name = game_variant_id
                      )
                    """,
                        [match_id],
                    ).fetchone()[0]
                    > 0
                ):
                    secondary_stats["assets"] += 1

            for data_type, count in sorted(secondary_stats.items(), key=lambda x: -x[1]):
                if count > 0:
                    percentage = (count / len(secondary_only)) * 100
                    print(f"    - {data_type:20s}: {count:4d} matchs ({percentage:5.1f}%)")
        else:
            print("  Aucun match dans cette catégorie")

    finally:
        conn.close()


def main() -> int:
    """Point d'entrée principal."""
    import argparse

    parser = argparse.ArgumentParser(description="Diagnostic du statut du backfill")
    parser.add_argument("--gamertag", required=True, help="Gamertag du joueur")
    args = parser.parse_args()

    # Trouver la DB du joueur
    db_path = get_player_duckdb_path(args.gamertag)
    if not db_path or not db_path.exists():
        print(f"❌ Base de données non trouvée pour {args.gamertag}")
        return 1

    # Résoudre le XUID
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        xuid_result = conn.execute(
            "SELECT xuid FROM xuid_aliases WHERE gamertag = ? LIMIT 1", [args.gamertag]
        ).fetchone()
        if not xuid_result:
            print(f"❌ XUID non trouvé pour {args.gamertag}")
            return 1
        xuid = xuid_result[0]
    finally:
        conn.close()

    print(f"🔍 Analyse du backfill pour {args.gamertag} (XUID: {xuid})\n")
    analyze_missing_data(db_path, xuid)

    return 0


if __name__ == "__main__":
    sys.exit(main())
