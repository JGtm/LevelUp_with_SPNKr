#!/usr/bin/env python3
"""Script de diagnostic pour vérifier les données d'un match dans DuckDB v4.

Usage:
    python scripts/diagnose_match_data.py --db-path data/players/MonGamertag/stats.duckdb --match-id <match_id>
    python scripts/diagnose_match_data.py --db-path data/players/MonGamertag/stats.duckdb --last-match
"""

import argparse
import json
import sys
from pathlib import Path

# Fix encoding pour Windows
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import duckdb


def diagnose_match(db_path: str, match_id: str | None = None) -> dict[str, any]:
    """Diagnostique les données d'un match."""
    results = {
        "match_id": match_id,
        "match_exists": False,
        "has_match_stats": False,
        "has_highlight_events": False,
        "highlight_events_count": 0,
        "has_match_participants": False,
        "participants_count": 0,
        "has_killer_victim_pairs": False,
        "killer_victim_pairs_count": 0,
        "has_aliases": False,
        "aliases_count": 0,
        "errors": [],
    }

    try:
        conn = duckdb.connect(str(db_path), read_only=True)

        # Si match_id n'est pas fourni, prendre le dernier match
        if not match_id:
            try:
                match_row = conn.execute(
                    "SELECT match_id FROM match_stats ORDER BY start_time DESC LIMIT 1"
                ).fetchone()
                if match_row:
                    match_id = match_row[0]
                    results["match_id"] = match_id
                    print(f"📋 Match ID détecté automatiquement: {match_id}")
                else:
                    results["errors"].append("Aucun match trouvé dans la base")
                    return results
            except Exception as e:
                results["errors"].append(f"Erreur détection dernier match: {e}")
                return results

        # Vérifier si le match existe
        try:
            match_exists = conn.execute(
                "SELECT COUNT(*) FROM match_stats WHERE match_id = ?", [match_id]
            ).fetchone()[0]
            results["match_exists"] = match_exists > 0
        except Exception as e:
            results["errors"].append(f"Erreur vérification match: {e}")
            return results

        if not results["match_exists"]:
            results["errors"].append(f"Match {match_id} introuvable dans match_stats")
            return results

        results["has_match_stats"] = True

        # Vérifier les highlight_events
        try:
            he_count = conn.execute(
                "SELECT COUNT(*) FROM highlight_events WHERE match_id = ?", [match_id]
            ).fetchone()[0]
            results["has_highlight_events"] = he_count > 0
            results["highlight_events_count"] = he_count
        except Exception as e:
            results["errors"].append(f"Erreur vérification highlight_events: {e}")

        # Vérifier les match_participants
        try:
            participants_count = conn.execute(
                "SELECT COUNT(*) FROM match_participants WHERE match_id = ?", [match_id]
            ).fetchone()[0]
            results["has_match_participants"] = participants_count > 0
            results["participants_count"] = participants_count
        except Exception as e:
            results["errors"].append(f"Erreur vérification match_participants: {e}")

        # Vérifier les killer_victim_pairs
        try:
            kvp_count = conn.execute(
                "SELECT COUNT(*) FROM killer_victim_pairs WHERE match_id = ?", [match_id]
            ).fetchone()[0]
            results["has_killer_victim_pairs"] = kvp_count > 0
            results["killer_victim_pairs_count"] = kvp_count
        except Exception as e:
            results["errors"].append(f"Erreur vérification killer_victim_pairs: {e}")

        # Vérifier les aliases (au moins un alias pour un participant du match)
        try:
            # Récupérer les XUIDs des participants
            participant_xuids = conn.execute(
                "SELECT DISTINCT xuid FROM match_participants WHERE match_id = ?", [match_id]
            ).fetchall()
            if participant_xuids:
                xuids = [str(x[0]) for x in participant_xuids if x[0]]
                if xuids:
                    placeholders = ",".join(["?"] * len(xuids))
                    alias_count = conn.execute(
                        f"SELECT COUNT(*) FROM xuid_aliases WHERE xuid IN ({placeholders})",
                        xuids,
                    ).fetchone()[0]
                    results["has_aliases"] = alias_count > 0
                    results["aliases_count"] = alias_count
        except Exception as e:
            results["errors"].append(f"Erreur vérification aliases: {e}")

        # Détails supplémentaires sur les highlight_events
        if results["has_highlight_events"]:
            try:
                event_types = conn.execute(
                    """
                    SELECT event_type, COUNT(*) as cnt
                    FROM highlight_events
                    WHERE match_id = ?
                    GROUP BY event_type
                    ORDER BY cnt DESC
                    """,
                    [match_id],
                ).fetchall()
                results["highlight_events_by_type"] = dict(event_types)
            except Exception:
                pass

        # Détails sur les participants
        if results["has_match_participants"]:
            try:
                team_distribution = conn.execute(
                    """
                    SELECT team_id, COUNT(*) as cnt
                    FROM match_participants
                    WHERE match_id = ?
                    GROUP BY team_id
                    ORDER BY team_id
                    """,
                    [match_id],
                ).fetchall()
                results["participants_by_team"] = dict(team_distribution)
            except Exception:
                pass

        conn.close()

    except Exception as e:
        results["errors"].append(f"Erreur générale: {e}")

    return results


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Diagnostique les données d'un match dans DuckDB v4"
    )
    parser.add_argument(
        "--db-path",
        required=True,
        help="Chemin vers la DB DuckDB v4 (ex: data/players/MonGamertag/stats.duckdb)",
    )
    parser.add_argument(
        "--match-id",
        help="ID du match à diagnostiquer (si non fourni, prend le dernier match)",
    )
    parser.add_argument(
        "--last-match",
        action="store_true",
        help="Diagnostiquer le dernier match (équivalent à --match-id non fourni)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Afficher les résultats en JSON",
    )

    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"❌ Erreur: La DB {db_path} n'existe pas", file=sys.stderr)
        return 1

    match_id = None if args.last_match or not args.match_id else args.match_id

    results = diagnose_match(str(db_path), match_id)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    # Affichage formaté
    print("\n" + "=" * 60)
    print(f"🔍 Diagnostic du match: {results['match_id']}")
    print("=" * 60 + "\n")

    if results["errors"]:
        print("❌ Erreurs:")
        for error in results["errors"]:
            print(f"   - {error}")
        print()

    if not results["match_exists"]:
        print("❌ Le match n'existe pas dans la base de données")
        return 1

    print("✅ Match trouvé dans match_stats\n")

    # Highlight events
    if results["has_highlight_events"]:
        print(f"✅ Highlight events: {results['highlight_events_count']} événements")
        if "highlight_events_by_type" in results:
            print("   Répartition par type:")
            for et, cnt in results["highlight_events_by_type"].items():
                print(f"     - {et}: {cnt}")
    else:
        print("❌ Highlight events: Aucun événement trouvé")
    print()

    # Match participants
    if results["has_match_participants"]:
        print(f"✅ Match participants: {results['participants_count']} joueurs")
        if "participants_by_team" in results:
            print("   Répartition par équipe:")
            for tid, cnt in results["participants_by_team"].items():
                team_name = f"Équipe {tid}" if tid is not None else "Sans équipe"
                print(f"     - {team_name}: {cnt} joueurs")
    else:
        print("❌ Match participants: Aucun participant trouvé")
    print()

    # Killer-victim pairs
    if results["has_killer_victim_pairs"]:
        print(f"✅ Killer-victim pairs: {results['killer_victim_pairs_count']} paires")
    else:
        print("⚠️  Killer-victim pairs: Aucune paire trouvée")
    print()

    # Aliases
    if results["has_aliases"]:
        print(f"✅ Aliases: {results['aliases_count']} alias(es) pour les participants")
    else:
        print("⚠️  Aliases: Aucun alias trouvé pour les participants")
    print()

    # Résumé
    print("=" * 60)
    issues = []
    if not results["has_highlight_events"]:
        issues.append("highlight_events manquants")
    if not results["has_match_participants"]:
        issues.append("match_participants manquants")

    if issues:
        print(f"⚠️  Problèmes détectés: {', '.join(issues)}")
        print("\n💡 Solutions possibles:")
        if not results["has_highlight_events"]:
            print("   - Les highlight_events peuvent ne pas être disponibles immédiatement")
            print("     après un match (délai API SPNKr). Réessayer plus tard.")
        if not results["has_match_participants"]:
            print("   - Relancer une synchronisation avec --participants activé")
            print("     (normalement activé par défaut dans _sync_duckdb_player)")
    else:
        print("✅ Toutes les données semblent présentes")
    print("=" * 60 + "\n")

    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
