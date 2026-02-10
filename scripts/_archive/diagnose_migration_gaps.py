#!/usr/bin/env python3
"""
Diagnostic complet de la migration SQLite → DuckDB.

Ce script analyse l'état actuel des données DuckDB pour identifier
les lacunes potentielles par rapport au système legacy SQLite.

Usage:
    python scripts/diagnose_migration_gaps.py
    python scripts/diagnose_migration_gaps.py --gamertag JGtm
    python scripts/diagnose_migration_gaps.py --all --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import duckdb
except ImportError:
    print("ERREUR: DuckDB non installé. Exécutez: pip install duckdb")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Configuration des chemins
DATA_DIR = Path(__file__).parent.parent / "data"
PLAYERS_DIR = DATA_DIR / "players"
WAREHOUSE_DIR = DATA_DIR / "warehouse"
DB_PROFILES_PATH = Path(__file__).parent.parent / "db_profiles.json"


@dataclass
class TableStats:
    """Statistiques d'une table."""

    name: str
    row_count: int = 0
    exists: bool = False
    expected_min: int = 0
    status: str = "unknown"
    issues: list[str] = field(default_factory=list)


@dataclass
class PlayerDiagnostic:
    """Diagnostic complet pour un joueur."""

    gamertag: str
    xuid: str
    db_path: str
    db_exists: bool = False
    total_matches: int = 0
    tables: dict[str, TableStats] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def load_db_profiles() -> dict[str, Any]:
    """Charge la configuration des profils joueurs."""
    if not DB_PROFILES_PATH.exists():
        return {"profiles": {}}
    with open(DB_PROFILES_PATH, encoding="utf-8") as f:
        return json.load(f)


def diagnose_player(
    gamertag: str, profile: dict[str, Any], verbose: bool = False
) -> PlayerDiagnostic:
    """Effectue un diagnostic complet pour un joueur."""
    db_path = Path(profile.get("db_path", f"data/players/{gamertag}/stats.duckdb"))
    xuid = profile.get("xuid", "")

    diag = PlayerDiagnostic(
        gamertag=gamertag,
        xuid=xuid,
        db_path=str(db_path),
    )

    if not db_path.exists():
        diag.issues.append(f"Base de données non trouvée: {db_path}")
        return diag

    diag.db_exists = True

    try:
        conn = duckdb.connect(str(db_path), read_only=True)

        # Tables attendues avec minimum de lignes
        expected_tables = {
            "match_stats": {"min": 100, "desc": "Stats des matchs (principal)"},
            "medals_earned": {"min": 100, "desc": "Médailles gagnées par match"},
            "teammates_aggregate": {"min": 10, "desc": "Stats agrégées coéquipiers"},
            "antagonists": {"min": 0, "desc": "Némésis/victimes agrégées"},
            "highlight_events": {"min": 10, "desc": "Événements des films"},
            "player_match_stats": {"min": 50, "desc": "Stats MMR par match"},
            "xuid_aliases": {"min": 10, "desc": "Mapping XUID → Gamertag"},
            "killer_victim_pairs": {"min": 0, "desc": "Paires killer/victim"},
            "match_participants": {"min": 0, "desc": "Participants par match"},
            "skill_history": {"min": 0, "desc": "Historique des rangs"},
            "sessions": {"min": 0, "desc": "Sessions de jeu"},
            "career_progression": {"min": 0, "desc": "Progression de carrière"},
            "sync_meta": {"min": 1, "desc": "Métadonnées de sync"},
        }

        # Vérifier chaque table
        for table_name, config in expected_tables.items():
            stats = TableStats(
                name=table_name,
                expected_min=config["min"],
            )

            # Vérifier si la table existe
            check = conn.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = '{table_name}'
            """).fetchone()

            if check and check[0] > 0:
                stats.exists = True
                stats.row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

                if stats.row_count == 0:
                    stats.status = "empty"
                    stats.issues.append(f"Table vide (attendu: ≥{config['min']})")
                elif stats.row_count < config["min"]:
                    stats.status = "low"
                    stats.issues.append(
                        f"Peu de données ({stats.row_count}, attendu: ≥{config['min']})"
                    )
                else:
                    stats.status = "ok"
            else:
                stats.exists = False
                stats.status = "missing"
                if config["min"] > 0:
                    stats.issues.append("Table non créée")

            diag.tables[table_name] = stats

        # Compter les matchs
        diag.total_matches = diag.tables.get("match_stats", TableStats("match_stats")).row_count

        # === Analyses spécifiques ===

        # 1. Vérifier si xuid_aliases est vide (problème connu)
        aliases_stats = diag.tables.get("xuid_aliases")
        if aliases_stats and aliases_stats.row_count == 0:
            diag.issues.append("❌ xuid_aliases VIDE - Gamertags ne peuvent pas être résolus")
            diag.recommendations.append(
                "Exécuter: python scripts/backfill_data.py --player {gamertag} --force-aliases"
            )

        # 2. Vérifier si match_participants existe
        mp_stats = diag.tables.get("match_participants")
        if not mp_stats or not mp_stats.exists or mp_stats.row_count == 0:
            diag.issues.append(
                "⚠️ match_participants manquant - Coéquipiers/équipes non disponibles"
            )
            diag.recommendations.append(
                "Exécuter: python scripts/backfill_data.py --player {gamertag} --participants"
            )

        # 3. Vérifier le ratio highlight_events vs match_stats
        he_stats = diag.tables.get("highlight_events")
        ms_stats = diag.tables.get("match_stats")
        if (
            he_stats
            and ms_stats
            and ms_stats.row_count > 0
            and he_stats.row_count < ms_stats.row_count
        ):
            diag.issues.append(
                f"⚠️ Peu d'events ({he_stats.row_count} vs {ms_stats.row_count} matchs)"
            )

        # 4. Vérifier le ratio player_match_stats vs match_stats
        pms_stats = diag.tables.get("player_match_stats")
        if pms_stats and ms_stats and ms_stats.row_count > 0:
            coverage = (pms_stats.row_count / ms_stats.row_count) * 100
            if coverage < 50:
                diag.issues.append(f"⚠️ Couverture player_match_stats faible ({coverage:.1f}%)")
                diag.recommendations.append("L'API ne retourne pas toujours les stats MMR")

        # 5. Vérifier la qualité des gamertags dans highlight_events
        if he_stats and he_stats.row_count > 0:
            try:
                # Compter les gamertags corrompus (avec caractères non-ASCII)
                corrupt_count = conn.execute("""
                    SELECT COUNT(DISTINCT gamertag)
                    FROM highlight_events
                    WHERE gamertag IS NOT NULL
                    AND gamertag != ''
                    AND NOT regexp_matches(gamertag, '^[\\x20-\\x7E]+$')
                """).fetchone()[0]

                if corrupt_count > 0:
                    diag.issues.append(
                        f"⚠️ {corrupt_count} gamertags corrompus dans highlight_events"
                    )
            except Exception:
                pass  # regexp_matches peut ne pas être disponible

        # 6. Vérifier antagonists
        ant_stats = diag.tables.get("antagonists")
        if not ant_stats or ant_stats.row_count == 0:
            diag.issues.append("⚠️ antagonists vide - Némésis/victimes non calculés")

        # 7. Vérifier killer_victim_pairs
        kvp_stats = diag.tables.get("killer_victim_pairs")
        if not kvp_stats or kvp_stats.row_count == 0:
            diag.issues.append("⚠️ killer_victim_pairs vide - Paires killer/victim non extraites")
            diag.recommendations.append(
                "Exécuter: python scripts/backfill_killer_victim_pairs.py --gamertag {gamertag}"
            )

        # 8. Analyse des métadonnées NULL
        try:
            null_metadata = conn.execute("""
                SELECT COUNT(*) FROM match_stats
                WHERE map_name IS NULL OR playlist_name IS NULL
            """).fetchone()[0]

            if null_metadata > 0 and ms_stats:
                pct = (null_metadata / ms_stats.row_count) * 100
                if pct > 5:
                    diag.issues.append(
                        f"⚠️ {null_metadata} matchs ({pct:.1f}%) avec métadonnées NULL"
                    )
                    diag.recommendations.append(
                        "Exécuter: python scripts/backfill_data.py --player {gamertag} --metadata"
                    )
        except Exception:
            pass

        conn.close()

    except Exception as e:
        diag.issues.append(f"Erreur d'accès à la base: {e}")

    return diag


def diagnose_metadata_db(verbose: bool = False) -> dict[str, Any]:
    """Diagnostic de la base de métadonnées globale."""
    metadata_path = WAREHOUSE_DIR / "metadata.duckdb"

    result = {
        "exists": False,
        "tables": {},
        "issues": [],
    }

    if not metadata_path.exists():
        result["issues"].append(f"Base de métadonnées non trouvée: {metadata_path}")
        return result

    result["exists"] = True

    try:
        conn = duckdb.connect(str(metadata_path), read_only=True)

        expected_tables = {
            "playlists": {"min": 10, "desc": "Définitions des playlists"},
            "maps": {"min": 20, "desc": "Définitions des cartes"},
            "game_modes": {"min": 50, "desc": "Modes de jeu"},
            "medal_definitions": {"min": 100, "desc": "Définitions des médailles"},
            "career_ranks": {"min": 200, "desc": "Rangs de carrière"},
            "players": {"min": 0, "desc": "Joueurs connus"},
        }

        for table_name, config in expected_tables.items():
            stats = {"exists": False, "count": 0, "status": "unknown"}

            check = conn.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = '{table_name}'
            """).fetchone()

            if check and check[0] > 0:
                stats["exists"] = True
                stats["count"] = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

                if stats["count"] == 0:
                    stats["status"] = "empty"
                    result["issues"].append(f"Table {table_name} vide")
                elif stats["count"] < config["min"]:
                    stats["status"] = "low"
                    result["issues"].append(
                        f"Table {table_name} incomplète ({stats['count']}/{config['min']})"
                    )
                else:
                    stats["status"] = "ok"
            else:
                stats["status"] = "missing"
                result["issues"].append(f"Table {table_name} manquante")

            result["tables"][table_name] = stats

        conn.close()

    except Exception as e:
        result["issues"].append(f"Erreur d'accès: {e}")

    return result


def print_diagnostic(diag: PlayerDiagnostic, verbose: bool = False) -> None:
    """Affiche le diagnostic d'un joueur."""
    print(f"\n{'='*70}")
    print(f"📊 DIAGNOSTIC: {diag.gamertag}")
    print(f"{'='*70}")
    print(f"XUID: {diag.xuid}")
    print(f"DB Path: {diag.db_path}")
    print(f"DB Exists: {'✅' if diag.db_exists else '❌'}")
    print(f"Total Matchs: {diag.total_matches}")

    # Tableau des tables
    print("\n📋 Tables:")
    print(f"{'Table':<25} {'Existe':<8} {'Lignes':<10} {'Status':<10}")
    print("-" * 60)

    for name, stats in diag.tables.items():
        exists_icon = "✅" if stats.exists else "❌"
        status_icon = {
            "ok": "✅",
            "low": "⚠️",
            "empty": "🔴",
            "missing": "❌",
            "unknown": "❓",
        }.get(stats.status, "❓")

        print(f"{name:<25} {exists_icon:<8} {stats.row_count:<10} {status_icon} {stats.status}")

    # Issues
    if diag.issues:
        print(f"\n🔴 Problèmes détectés ({len(diag.issues)}):")
        for issue in diag.issues:
            print(f"  • {issue}")
    else:
        print("\n✅ Aucun problème détecté")

    # Recommandations
    if diag.recommendations:
        print("\n💡 Recommandations:")
        for rec in diag.recommendations:
            print(f"  → {rec.format(gamertag=diag.gamertag)}")


def print_summary(diagnostics: list[PlayerDiagnostic], metadata_result: dict[str, Any]) -> None:
    """Affiche un résumé global."""
    print("\n" + "=" * 70)
    print("📈 RÉSUMÉ GLOBAL DE LA MIGRATION")
    print("=" * 70)

    # Metadata
    print("\n🗄️ Base de métadonnées (metadata.duckdb):")
    if metadata_result["exists"]:
        print("  ✅ Existe")
        for table, stats in metadata_result["tables"].items():
            icon = "✅" if stats["status"] == "ok" else "⚠️" if stats["status"] == "low" else "❌"
            print(f"    {icon} {table}: {stats['count']} lignes")
        if metadata_result["issues"]:
            for issue in metadata_result["issues"]:
                print(f"    ⚠️ {issue}")
    else:
        print("  ❌ Non trouvée")

    # Joueurs
    print("\n👥 Joueurs:")
    total_issues = 0
    for diag in diagnostics:
        icon = "✅" if not diag.issues else "⚠️" if len(diag.issues) < 3 else "🔴"
        print(
            f"  {icon} {diag.gamertag}: {diag.total_matches} matchs, {len(diag.issues)} problèmes"
        )
        total_issues += len(diag.issues)

    # Problèmes courants
    print("\n🔍 Problèmes les plus fréquents:")

    # Compter les problèmes par type
    issue_counts: dict[str, int] = {}
    for diag in diagnostics:
        for issue in diag.issues:
            # Extraire le type de problème (premier mot/emoji)
            key = issue.split()[0] if issue else "autre"
            issue_counts[key] = issue_counts.get(key, 0) + 1

    for issue_type, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
        print(f"  • {issue_type}: {count} joueurs")

    # Score global
    print("\n📊 Score de migration:")
    total_tables = sum(len(d.tables) for d in diagnostics)
    ok_tables = sum(1 for d in diagnostics for t in d.tables.values() if t.status == "ok")
    if total_tables > 0:
        score = (ok_tables / total_tables) * 100
        print(f"  {score:.1f}% des tables sont correctement migrées")

    print("\n🎯 Actions prioritaires:")

    # Déterminer les actions prioritaires
    actions = []

    has_empty_aliases = any(
        d.tables.get("xuid_aliases") and d.tables["xuid_aliases"].row_count == 0
        for d in diagnostics
    )
    if has_empty_aliases:
        actions.append("1. Exécuter backfill des xuid_aliases pour résoudre les gamertags")

    has_no_participants = any(
        not d.tables.get("match_participants") or d.tables["match_participants"].row_count == 0
        for d in diagnostics
    )
    if has_no_participants:
        actions.append("2. Créer et peupler la table match_participants")

    has_empty_kvp = any(
        d.tables.get("killer_victim_pairs") and d.tables["killer_victim_pairs"].row_count == 0
        for d in diagnostics
    )
    if has_empty_kvp:
        actions.append("3. Exécuter backfill des killer_victim_pairs")

    if actions:
        for action in actions:
            print(f"  → {action}")
    else:
        print("  ✅ Aucune action prioritaire")

    print("\n" + "=" * 70)


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Diagnostic de la migration SQLite → DuckDB",
    )
    parser.add_argument(
        "--gamertag",
        "-g",
        help="Gamertag d'un joueur spécifique",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Diagnostiquer tous les joueurs",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Afficher plus de détails",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Sortie au format JSON",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Fichier de sortie pour le rapport",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Charger les profils
    profiles = load_db_profiles()

    if not profiles.get("profiles"):
        logger.error("Aucun profil trouvé dans db_profiles.json")
        return 1

    # Déterminer les joueurs à diagnostiquer
    if args.all:
        gamertags = list(profiles["profiles"].keys())
    elif args.gamertag:
        gamertags = [args.gamertag]
    else:
        gamertags = list(profiles["profiles"].keys())

    print("=" * 70)
    print("🔬 DIAGNOSTIC DE MIGRATION SQLite → DuckDB")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Diagnostic de la base de métadonnées
    metadata_result = diagnose_metadata_db(verbose=args.verbose)

    # Diagnostic de chaque joueur
    diagnostics: list[PlayerDiagnostic] = []

    for gamertag in gamertags:
        if gamertag not in profiles["profiles"]:
            logger.warning(f"Joueur {gamertag} non trouvé dans db_profiles.json")
            continue

        profile = profiles["profiles"][gamertag]
        diag = diagnose_player(gamertag, profile, verbose=args.verbose)
        diagnostics.append(diag)

        if not args.json:
            print_diagnostic(diag, verbose=args.verbose)

    # Résumé
    if not args.json:
        print_summary(diagnostics, metadata_result)

    # Sortie JSON si demandé
    if args.json or args.output:
        report = {
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata_result,
            "players": [
                {
                    "gamertag": d.gamertag,
                    "xuid": d.xuid,
                    "db_path": d.db_path,
                    "db_exists": d.db_exists,
                    "total_matches": d.total_matches,
                    "tables": {
                        name: {
                            "exists": t.exists,
                            "row_count": t.row_count,
                            "status": t.status,
                            "issues": t.issues,
                        }
                        for name, t in d.tables.items()
                    },
                    "issues": d.issues,
                    "recommendations": d.recommendations,
                }
                for d in diagnostics
            ],
        }

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n📄 Rapport sauvegardé: {args.output}")
        elif args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))

    # Code de retour
    total_issues = sum(len(d.issues) for d in diagnostics)
    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
