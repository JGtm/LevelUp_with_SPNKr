#!/usr/bin/env python3
"""Script de vérification de la logique de backfill.

Vérifie l'état des données et teste les requêtes de détection.
"""

import sys
from pathlib import Path

# Fix encoding pour Windows
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import duckdb


def verify_backfill_logic(db_path: str, gamertag: str, xuid: str) -> dict:
    """Vérifie la logique de backfill pour une base de données."""
    results = {
        "gamertag": gamertag,
        "db_path": db_path,
        "total_matches": 0,
        "matches_with_highlight_events": 0,
        "matches_with_medals": 0,
        "matches_with_skill": 0,
        "matches_with_personal_scores": 0,
        "matches_with_participants": 0,
        "matches_detected_for_events": 0,
        "matches_detected_for_medals": 0,
        "matches_detected_for_skill": 0,
        "matches_detected_for_personal_scores": 0,
        "matches_detected_for_participants": 0,
        "recent_matches_sample": [],
        "issues": [],
    }

    try:
        conn = duckdb.connect(str(db_path), read_only=True)

        # Compter les matchs totaux
        total = conn.execute("SELECT COUNT(*) FROM match_stats").fetchone()
        results["total_matches"] = total[0] if total else 0

        # Vérifier highlight_events
        try:
            he_count = conn.execute(
                "SELECT COUNT(DISTINCT match_id) FROM highlight_events"
            ).fetchone()
            results["matches_with_highlight_events"] = he_count[0] if he_count else 0
        except Exception as e:
            results["issues"].append(f"Erreur vérification highlight_events: {e}")

        # Vérifier medals
        try:
            medals_count = conn.execute(
                "SELECT COUNT(DISTINCT match_id) FROM medals_earned"
            ).fetchone()
            results["matches_with_medals"] = medals_count[0] if medals_count else 0
        except Exception as e:
            results["issues"].append(f"Erreur vérification medals: {e}")

        # Vérifier skill
        try:
            skill_count = conn.execute(
                "SELECT COUNT(DISTINCT match_id) FROM player_match_stats WHERE xuid = ?",
                [xuid],
            ).fetchone()
            results["matches_with_skill"] = skill_count[0] if skill_count else 0
        except Exception as e:
            results["issues"].append(f"Erreur vérification skill: {e}")

        # Vérifier personal_scores
        try:
            ps_count = conn.execute(
                "SELECT COUNT(DISTINCT match_id) FROM personal_score_awards WHERE xuid = ?",
                [xuid],
            ).fetchone()
            results["matches_with_personal_scores"] = ps_count[0] if ps_count else 0
        except Exception as e:
            results["issues"].append(f"Erreur vérification personal_scores: {e}")

        # Vérifier participants
        try:
            participants_count = conn.execute(
                "SELECT COUNT(DISTINCT match_id) FROM match_participants"
            ).fetchone()
            results["matches_with_participants"] = (
                participants_count[0] if participants_count else 0
            )
        except Exception as e:
            results["issues"].append(f"Erreur vérification participants: {e}")

        # Tester les requêtes de détection (comme dans _find_matches_missing_data)

        # Events
        try:
            events_query = """
                SELECT DISTINCT ms.match_id
                FROM match_stats ms
                WHERE ms.match_id NOT IN (
                    SELECT DISTINCT match_id FROM highlight_events
                )
                ORDER BY ms.start_time DESC
                LIMIT 100
            """
            events_matches = conn.execute(events_query).fetchall()
            results["matches_detected_for_events"] = len(events_matches)
        except Exception as e:
            results["issues"].append(f"Erreur requête détection events: {e}")

        # Medals
        try:
            medals_query = """
                SELECT DISTINCT ms.match_id
                FROM match_stats ms
                WHERE ms.match_id NOT IN (
                    SELECT DISTINCT match_id FROM medals_earned
                )
                ORDER BY ms.start_time DESC
                LIMIT 100
            """
            medals_matches = conn.execute(medals_query).fetchall()
            results["matches_detected_for_medals"] = len(medals_matches)
        except Exception as e:
            results["issues"].append(f"Erreur requête détection medals: {e}")

        # Skill
        try:
            skill_query = """
                SELECT DISTINCT ms.match_id
                FROM match_stats ms
                WHERE ms.match_id NOT IN (
                    SELECT DISTINCT match_id FROM player_match_stats WHERE xuid = ?
                )
                ORDER BY ms.start_time DESC
                LIMIT 100
            """
            skill_matches = conn.execute(skill_query, [xuid]).fetchall()
            results["matches_detected_for_skill"] = len(skill_matches)
        except Exception as e:
            results["issues"].append(f"Erreur requête détection skill: {e}")

        # Personal scores
        try:
            ps_query = """
                SELECT DISTINCT ms.match_id
                FROM match_stats ms
                WHERE ms.match_id NOT IN (
                    SELECT DISTINCT match_id FROM personal_score_awards WHERE xuid = ?
                )
                ORDER BY ms.start_time DESC
                LIMIT 100
            """
            ps_matches = conn.execute(ps_query, [xuid]).fetchall()
            results["matches_detected_for_personal_scores"] = len(ps_matches)
        except Exception as e:
            results["issues"].append(f"Erreur requête détection personal_scores: {e}")

        # Participants
        try:
            participants_query = """
                SELECT DISTINCT ms.match_id
                FROM match_stats ms
                WHERE ms.match_id NOT IN (
                    SELECT DISTINCT match_id FROM match_participants
                )
                ORDER BY ms.start_time DESC
                LIMIT 100
            """
            participants_matches = conn.execute(participants_query).fetchall()
            results["matches_detected_for_participants"] = len(participants_matches)
        except Exception as e:
            results["issues"].append(f"Erreur requête détection participants: {e}")

        # Échantillon des matchs récents avec/sans events
        try:
            sample_query = """
                SELECT
                    ms.match_id,
                    ms.start_time,
                    COUNT(DISTINCT he.match_id) as event_count,
                    COUNT(DISTINCT me.match_id) as medal_count,
                    COUNT(DISTINCT pms.match_id) as skill_count,
                    COUNT(DISTINCT psa.match_id) as personal_score_count,
                    COUNT(DISTINCT mp.match_id) as participant_count
                FROM match_stats ms
                LEFT JOIN highlight_events he ON ms.match_id = he.match_id
                LEFT JOIN medals_earned me ON ms.match_id = me.match_id
                LEFT JOIN player_match_stats pms ON ms.match_id = pms.match_id AND pms.xuid = ?
                LEFT JOIN personal_score_awards psa ON ms.match_id = psa.match_id AND psa.xuid = ?
                LEFT JOIN match_participants mp ON ms.match_id = mp.match_id
                GROUP BY ms.match_id, ms.start_time
                ORDER BY ms.start_time DESC
                LIMIT 10
            """
            sample = conn.execute(sample_query, [xuid, xuid]).fetchall()
            results["recent_matches_sample"] = [
                {
                    "match_id": row[0],
                    "start_time": str(row[1]),
                    "event_count": row[2],
                    "medal_count": row[3],
                    "skill_count": row[4],
                    "personal_score_count": row[5],
                    "participant_count": row[6],
                }
                for row in sample
            ]
        except Exception as e:
            results["issues"].append(f"Erreur échantillon matchs récents: {e}")

        conn.close()

    except Exception as e:
        results["issues"].append(f"Erreur générale: {e}")
        import traceback

        results["traceback"] = traceback.format_exc()

    return results


def main() -> int:
    """Point d'entrée principal."""
    import argparse

    parser = argparse.ArgumentParser(description="Vérifie la logique de backfill")
    parser.add_argument("--db-path", required=True, help="Chemin vers la DB DuckDB v4")
    parser.add_argument("--gamertag", required=True, help="Gamertag du joueur")
    parser.add_argument("--xuid", required=True, help="XUID du joueur")

    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"❌ Erreur: La DB {db_path} n'existe pas", file=sys.stderr)
        return 1

    results = verify_backfill_logic(str(db_path), args.gamertag, args.xuid)

    # Affichage formaté
    print("\n" + "=" * 70)
    print(f"🔍 Vérification logique de backfill pour {results['gamertag']}")
    print("=" * 70 + "\n")

    print("📊 Statistiques générales:")
    print(f"   Total matchs: {results['total_matches']}")
    print(f"   Matchs avec highlight_events: {results['matches_with_highlight_events']}")
    print(f"   Matchs avec medals: {results['matches_with_medals']}")
    print(f"   Matchs avec skill: {results['matches_with_skill']}")
    print(f"   Matchs avec personal_scores: {results['matches_with_personal_scores']}")
    print(f"   Matchs avec participants: {results['matches_with_participants']}")
    print()

    print("🎯 Matchs détectés pour backfill (limite 100):")
    print(f"   --events: {results['matches_detected_for_events']} matchs")
    print(f"   --medals: {results['matches_detected_for_medals']} matchs")
    print(f"   --skill: {results['matches_detected_for_skill']} matchs")
    print(f"   --personal-scores: {results['matches_detected_for_personal_scores']} matchs")
    print(f"   --participants: {results['matches_detected_for_participants']} matchs")
    print()

    # Analyse des problèmes
    issues_found = []

    if (
        results["matches_with_highlight_events"] == 0
        and results["matches_detected_for_events"] == results["total_matches"]
    ):
        issues_found.append(
            "⚠️  highlight_events: Table vide → tous les matchs seront sélectionnés (comportement attendu)"
        )
    elif (
        results["matches_with_highlight_events"] > 0
        and results["matches_detected_for_events"] == results["total_matches"]
    ):
        issues_found.append(
            "❌ highlight_events: Des events existent mais tous les matchs sont sélectionnés (BUG)"
        )
    elif results["matches_detected_for_events"] > 100:
        issues_found.append(
            f"⚠️  highlight_events: {results['matches_detected_for_events']} matchs détectés (beaucoup)"
        )

    if (
        results["matches_with_medals"] == 0
        and results["matches_detected_for_medals"] == results["total_matches"]
    ):
        issues_found.append(
            "⚠️  medals: Table vide → tous les matchs seront sélectionnés (comportement attendu)"
        )
    elif (
        results["matches_with_medals"] > 0
        and results["matches_detected_for_medals"] == results["total_matches"]
    ):
        issues_found.append(
            "❌ medals: Des medals existent mais tous les matchs sont sélectionnés (BUG)"
        )
    elif results["matches_detected_for_medals"] > 100:
        issues_found.append(
            f"⚠️  medals: {results['matches_detected_for_medals']} matchs détectés (beaucoup)"
        )

    if (
        results["matches_with_skill"] == 0
        and results["matches_detected_for_skill"] == results["total_matches"]
    ):
        issues_found.append(
            "⚠️  skill: Table vide → tous les matchs seront sélectionnés (comportement attendu)"
        )
    elif (
        results["matches_with_skill"] > 0
        and results["matches_detected_for_skill"] == results["total_matches"]
    ):
        issues_found.append(
            "❌ skill: Des skill stats existent mais tous les matchs sont sélectionnés (BUG)"
        )
    elif results["matches_detected_for_skill"] > 100:
        issues_found.append(
            f"⚠️  skill: {results['matches_detected_for_skill']} matchs détectés (beaucoup)"
        )

    if (
        results["matches_with_personal_scores"] == 0
        and results["matches_detected_for_personal_scores"] == results["total_matches"]
    ):
        issues_found.append(
            "⚠️  personal_scores: Table vide → tous les matchs seront sélectionnés (comportement attendu)"
        )
    elif (
        results["matches_with_personal_scores"] > 0
        and results["matches_detected_for_personal_scores"] == results["total_matches"]
    ):
        issues_found.append(
            "❌ personal_scores: Des personal scores existent mais tous les matchs sont sélectionnés (BUG)"
        )
    elif results["matches_detected_for_personal_scores"] > 100:
        issues_found.append(
            f"⚠️  personal_scores: {results['matches_detected_for_personal_scores']} matchs détectés (beaucoup)"
        )

    if (
        results["matches_with_participants"] == 0
        and results["matches_detected_for_participants"] == results["total_matches"]
    ):
        issues_found.append(
            "⚠️  participants: Table vide → tous les matchs seront sélectionnés (comportement attendu)"
        )
    elif (
        results["matches_with_participants"] > 0
        and results["matches_detected_for_participants"] == results["total_matches"]
    ):
        issues_found.append(
            "❌ participants: Des participants existent mais tous les matchs sont sélectionnés (BUG)"
        )
    elif results["matches_detected_for_participants"] > 100:
        issues_found.append(
            f"⚠️  participants: {results['matches_detected_for_participants']} matchs détectés (beaucoup)"
        )

    if issues_found:
        print("🚨 Problèmes détectés:")
        for issue in issues_found:
            print(f"   {issue}")
        print()
    else:
        print("✅ Aucun problème détecté")
        print()

    # Échantillon des matchs récents
    if results["recent_matches_sample"]:
        print("📋 Échantillon des 10 derniers matchs:")
        for i, match in enumerate(results["recent_matches_sample"][:5], 1):
            print(f"   {i}. {match['match_id'][:20]}... ({match['start_time']})")
            print(
                f"      Events: {match['event_count']}, Medals: {match['medal_count']}, "
                f"Skill: {match['skill_count']}, PersonalScores: {match['personal_score_count']}, "
                f"Participants: {match['participant_count']}"
            )
        print()

    if results["issues"]:
        print("❌ Erreurs rencontrées:")
        for issue in results["issues"]:
            print(f"   - {issue}")
        print()

    print("=" * 70 + "\n")

    return 0 if not issues_found else 1


if __name__ == "__main__":
    sys.exit(main())
