"""Diagnostic de base joueur + audit de schéma/types.

Ce module fournit :
- diagnose() : diagnostic de base (compatibilité historique)
- audit_player_db_types() : audit des types incohérents (Sprint 15)

Usage CLI :
    python scripts/diagnose_player_db.py --player Chocoboflor
    python scripts/diagnose_player_db.py --player Chocoboflor --audit-types
    python scripts/diagnose_player_db.py --all --audit-types
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ajouter la racine du projet au path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

logger = logging.getLogger(__name__)


def diagnose(db_path: str) -> dict[str, Any]:
    """Diagnostique une base joueur et retourne un résumé.

    Args:
        db_path: Chemin vers la base DuckDB du joueur.

    Returns:
        Un dictionnaire contenant des informations de diagnostic.
    """
    from scripts._archive.diagnose_player_db import diagnose as _diagnose

    return _diagnose(db_path)


def audit_player_db_types(db_path: str) -> dict[str, Any]:
    """Audite les types incohérents dans une base joueur DuckDB.

    Vérifie chaque table connue contre le CAST_PLAN de référence.
    Détecte :
    - Colonnes manquantes (MISSING_COLUMN)
    - Types incompatibles (TYPE_MISMATCH)
    - Colonnes non documentées (EXTRA_COLUMN)

    Args:
        db_path: Chemin vers stats.duckdb du joueur.

    Returns:
        Dict avec :
        - db_path: chemin vérifié
        - tables_checked: nombre de tables vérifiées
        - total_issues: nombre total de problèmes
        - issues_by_table: dict table_name → liste d'issues
        - critical_issues: nombre d'issues sur tables critiques
    """
    import duckdb

    from src.data.sync.batch_insert import CRITICAL_TABLES, audit_all_tables

    result: dict[str, Any] = {
        "db_path": db_path,
        "tables_checked": 0,
        "total_issues": 0,
        "issues_by_table": {},
        "critical_issues": 0,
    }

    try:
        conn = duckdb.connect(str(db_path), read_only=True)
    except Exception as e:
        result["error"] = f"Impossible d'ouvrir {db_path}: {e}"
        return result

    try:
        all_issues = audit_all_tables(conn)
        result["tables_checked"] = len(all_issues) if all_issues else 0
        result["issues_by_table"] = all_issues
        result["total_issues"] = sum(len(v) for v in all_issues.values())
        result["critical_issues"] = sum(
            len(v) for table, v in all_issues.items() if table in CRITICAL_TABLES
        )
    finally:
        conn.close()

    return result


def _find_player_dbs() -> list[tuple[str, Path]]:
    """Trouve toutes les bases joueur dans data/players/."""
    players_dir = REPO_ROOT / "data" / "players"
    if not players_dir.exists():
        return []

    results = []
    for player_dir in sorted(players_dir.iterdir()):
        if player_dir.is_dir():
            db_path = player_dir / "stats.duckdb"
            if db_path.exists():
                results.append((player_dir.name, db_path))
    return results


def main() -> int:
    """Point d'entrée CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Diagnostic et audit de schéma des bases joueur DuckDB"
    )
    parser.add_argument("--player", help="Gamertag du joueur")
    parser.add_argument("--all", action="store_true", help="Auditer tous les joueurs")
    parser.add_argument(
        "--audit-types",
        action="store_true",
        help="Audit des types incohérents (Sprint 15)",
    )
    parser.add_argument("--json", action="store_true", help="Sortie en JSON")
    args = parser.parse_args()

    if not args.player and not args.all:
        parser.error("--player ou --all est requis")
        return 1

    if args.all:
        player_dbs = _find_player_dbs()
    else:
        db_path = REPO_ROOT / "data" / "players" / args.player / "stats.duckdb"
        if not db_path.exists():
            logger.error(f"Base introuvable: {db_path}")
            return 1
        player_dbs = [(args.player, db_path)]

    if not player_dbs:
        logger.error("Aucune base joueur trouvée")
        return 1

    all_results = {}
    total_critical = 0

    for gamertag, db_path in player_dbs:
        logger.info(f"\n{'='*60}")
        logger.info(f"Joueur: {gamertag}")
        logger.info(f"{'='*60}")

        if args.audit_types:
            result = audit_player_db_types(str(db_path))
            all_results[gamertag] = result

            if result.get("error"):
                logger.error(f"  ERREUR: {result['error']}")
                continue

            issues = result["issues_by_table"]
            total = result["total_issues"]
            critical = result["critical_issues"]
            total_critical += critical

            if total == 0:
                logger.info("  ✅ Aucune incohérence de type détectée")
            else:
                logger.warning(f"  ⚠️  {total} incohérences détectées ({critical} critiques)")
                for table, table_issues in issues.items():
                    for issue in table_issues:
                        status = issue["status"]
                        col = issue["column"]
                        expected = issue["expected_type"]
                        actual = issue["actual_type"]
                        marker = "🔴" if status != "EXTRA_COLUMN" else "🟡"
                        logger.warning(
                            f"  {marker} {table}.{col}: "
                            f"attendu={expected}, réel={actual} [{status}]"
                        )
        else:
            result = diagnose(str(db_path))
            all_results[gamertag] = result
            logger.info(f"  Matchs: {result.get('match_count', '?')}")

    if args.json:
        print(json.dumps(all_results, indent=2, default=str))

    if total_critical > 0:
        logger.warning(f"\n⚠️  Total issues critiques: {total_critical}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
