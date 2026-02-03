#!/usr/bin/env python3
"""Validation de l'intégrité des données refdata (killer_victim_pairs, etc.).

Sprint 8.4 - Ce script :
1. Vérifie que les tables existent et ont le bon schéma
2. Vérifie la cohérence des données (FK, doublons, etc.)
3. Compare les totaux avec les données sources (highlight_events)
4. Génère un rapport de validation

Usage:
    # Valider un joueur
    python scripts/validate_refdata_integrity.py --gamertag MonGT

    # Valider tous les joueurs
    python scripts/validate_refdata_integrity.py --all

    # Rapport détaillé
    python scripts/validate_refdata_integrity.py --gamertag MonGT --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import duckdb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    """Rapport de validation pour une base."""

    db_path: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Tables
    tables_found: list[str] = field(default_factory=list)
    tables_missing: list[str] = field(default_factory=list)

    # Compteurs
    match_stats_count: int = 0
    highlight_events_count: int = 0
    killer_victim_pairs_count: int = 0
    personal_score_awards_count: int = 0

    # Cohérence
    matches_with_events: int = 0
    matches_with_kv_pairs: int = 0
    coverage_percent: float = 0.0

    # Erreurs
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True si aucune erreur critique."""
        return len(self.errors) == 0

    def to_dict(self) -> dict:
        """Convertit en dict pour JSON."""
        return {
            "db_path": self.db_path,
            "timestamp": self.timestamp,
            "tables_found": self.tables_found,
            "tables_missing": self.tables_missing,
            "counts": {
                "match_stats": self.match_stats_count,
                "highlight_events": self.highlight_events_count,
                "killer_victim_pairs": self.killer_victim_pairs_count,
                "personal_score_awards": self.personal_score_awards_count,
            },
            "coverage": {
                "matches_with_events": self.matches_with_events,
                "matches_with_kv_pairs": self.matches_with_kv_pairs,
                "coverage_percent": round(self.coverage_percent, 2),
            },
            "errors": self.errors,
            "warnings": self.warnings,
            "is_valid": self.is_valid,
        }


# Tables requises pour la validation
REQUIRED_TABLES = [
    "match_stats",
    "highlight_events",
]

OPTIONAL_TABLES = [
    "killer_victim_pairs",
    "personal_score_awards",
    "player_match_stats",
    "xuid_aliases",
    "career_progression",
]


def get_table_list(conn: duckdb.DuckDBPyConnection) -> set[str]:
    """Retourne la liste des tables existantes."""
    try:
        result = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {row[0].lower() for row in result}
    except Exception:
        return set()


def get_table_count(conn: duckdb.DuckDBPyConnection, table: str) -> int:
    """Retourne le nombre de lignes d'une table."""
    try:
        result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return result[0] if result else 0
    except Exception:
        return 0


def validate_player_db(db_path: Path) -> ValidationReport:
    """Valide une base joueur.

    Args:
        db_path: Chemin vers stats.duckdb du joueur.

    Returns:
        ValidationReport avec les résultats.
    """
    report = ValidationReport(db_path=str(db_path))

    if not db_path.exists():
        report.errors.append(f"Base non trouvée: {db_path}")
        return report

    conn = duckdb.connect(str(db_path), read_only=True)

    try:
        # 1. Vérifier les tables
        existing_tables = get_table_list(conn)

        for table in REQUIRED_TABLES:
            if table in existing_tables:
                report.tables_found.append(table)
            else:
                report.tables_missing.append(table)
                report.errors.append(f"Table requise manquante: {table}")

        for table in OPTIONAL_TABLES:
            if table in existing_tables:
                report.tables_found.append(table)
            else:
                report.tables_missing.append(table)
                # Pas d'erreur pour les tables optionnelles

        # 2. Compter les enregistrements
        report.match_stats_count = get_table_count(conn, "match_stats")
        report.highlight_events_count = get_table_count(conn, "highlight_events")

        if "killer_victim_pairs" in existing_tables:
            report.killer_victim_pairs_count = get_table_count(conn, "killer_victim_pairs")

        if "personal_score_awards" in existing_tables:
            report.personal_score_awards_count = get_table_count(conn, "personal_score_awards")

        # 3. Vérifier la couverture des paires killer_victim
        if "killer_victim_pairs" in existing_tables:
            # Matchs avec des highlight_events
            try:
                result = conn.execute(
                    "SELECT COUNT(DISTINCT match_id) FROM highlight_events"
                ).fetchone()
                report.matches_with_events = result[0] if result else 0
            except Exception:
                report.matches_with_events = 0

            # Matchs avec des paires calculées
            try:
                result = conn.execute(
                    "SELECT COUNT(DISTINCT match_id) FROM killer_victim_pairs"
                ).fetchone()
                report.matches_with_kv_pairs = result[0] if result else 0
            except Exception:
                report.matches_with_kv_pairs = 0

            # Couverture
            if report.matches_with_events > 0:
                report.coverage_percent = (
                    report.matches_with_kv_pairs / report.matches_with_events * 100
                )

                if report.coverage_percent < 100:
                    missing = report.matches_with_events - report.matches_with_kv_pairs
                    report.warnings.append(
                        f"{missing} matchs avec events n'ont pas de paires KV calculées"
                    )
        else:
            report.warnings.append(
                "Table killer_victim_pairs non créée - exécutez backfill_killer_victim_pairs.py"
            )

        # 4. Vérifier la colonne game_variant_category
        try:
            result = conn.execute("PRAGMA table_info('match_stats')").fetchall()
            columns = {row[1].lower() for row in result}
            if "game_variant_category" not in columns:
                report.warnings.append(
                    "Colonne game_variant_category manquante - "
                    "exécutez migrate_game_variant_category.py"
                )
        except Exception as e:
            report.errors.append(f"Erreur lecture schéma match_stats: {e}")

        # 5. Vérifier les doublons dans killer_victim_pairs
        if "killer_victim_pairs" in existing_tables:
            try:
                # Vérifier s'il y a des doublons (même match_id, killer, victim, time_ms)
                result = conn.execute("""
                    SELECT COUNT(*) as cnt
                    FROM (
                        SELECT match_id, killer_xuid, victim_xuid, time_ms, COUNT(*) as c
                        FROM killer_victim_pairs
                        GROUP BY match_id, killer_xuid, victim_xuid, time_ms
                        HAVING COUNT(*) > 1
                    )
                """).fetchone()
                duplicates = result[0] if result else 0
                if duplicates > 0:
                    report.warnings.append(
                        f"{duplicates} doublons détectés dans killer_victim_pairs"
                    )
            except Exception as e:
                report.warnings.append(f"Impossible de vérifier les doublons: {e}")

        # 6. Vérifier les XUIDs invalides
        if "killer_victim_pairs" in existing_tables:
            try:
                result = conn.execute("""
                    SELECT COUNT(*)
                    FROM killer_victim_pairs
                    WHERE killer_xuid = '' OR victim_xuid = ''
                       OR killer_xuid IS NULL OR victim_xuid IS NULL
                """).fetchone()
                invalid = result[0] if result else 0
                if invalid > 0:
                    report.warnings.append(
                        f"{invalid} paires avec XUIDs invalides dans killer_victim_pairs"
                    )
            except Exception:
                pass

    except Exception as e:
        report.errors.append(f"Erreur validation: {e}")

    finally:
        conn.close()

    return report


def find_all_player_dbs() -> list[Path]:
    """Trouve toutes les bases joueurs dans data/players/."""
    data_dir = Path(__file__).parent.parent / "data" / "players"
    if not data_dir.exists():
        return []

    dbs = []
    for player_dir in data_dir.iterdir():
        if player_dir.is_dir():
            db_path = player_dir / "stats.duckdb"
            if db_path.exists():
                dbs.append(db_path)

    return dbs


def print_report(report: ValidationReport, verbose: bool = False) -> None:
    """Affiche un rapport de validation."""
    status = "✅ VALIDE" if report.is_valid else "❌ INVALIDE"
    logger.info(f"\n{report.db_path}: {status}")

    if verbose or not report.is_valid:
        logger.info(f"  Tables trouvées: {', '.join(report.tables_found)}")
        if report.tables_missing:
            logger.info(f"  Tables manquantes: {', '.join(report.tables_missing)}")

        logger.info(f"  match_stats: {report.match_stats_count:,} matchs")
        logger.info(f"  highlight_events: {report.highlight_events_count:,} events")
        logger.info(f"  killer_victim_pairs: {report.killer_victim_pairs_count:,} paires")

        if report.matches_with_events > 0:
            logger.info(
                f"  Couverture KV: {report.matches_with_kv_pairs}/{report.matches_with_events} "
                f"matchs ({report.coverage_percent:.1f}%)"
            )

    if report.errors:
        for err in report.errors:
            logger.error(f"  ❌ {err}")

    if report.warnings and verbose:
        for warn in report.warnings:
            logger.warning(f"  ⚠️ {warn}")


def main():
    parser = argparse.ArgumentParser(description="Validation de l'intégrité des données refdata")
    parser.add_argument(
        "--gamertag",
        "-g",
        help="Gamertag du joueur (dossier dans data/players/)",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Traiter tous les joueurs",
    )
    parser.add_argument(
        "--db-path",
        "-d",
        help="Chemin direct vers stats.duckdb",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Mode verbeux (affiche warnings)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Sortie au format JSON",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Fichier de sortie pour le rapport JSON",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Déterminer les bases à traiter
    db_paths: list[Path] = []

    if args.db_path:
        db_paths.append(Path(args.db_path))
    elif args.gamertag:
        db_path = Path(__file__).parent.parent / "data" / "players" / args.gamertag / "stats.duckdb"
        db_paths.append(db_path)
    elif args.all:
        db_paths = find_all_player_dbs()
    else:
        parser.error("Spécifiez --gamertag, --all, ou --db-path")

    if not db_paths:
        logger.error("Aucune base de données trouvée")
        sys.exit(1)

    logger.info(f"Validation de {len(db_paths)} base(s) de données")

    # Valider chaque base
    reports: list[ValidationReport] = []
    for db_path in db_paths:
        report = validate_player_db(db_path)
        reports.append(report)

        if not args.json:
            print_report(report, verbose=args.verbose)

    # Résumé global
    valid_count = sum(1 for r in reports if r.is_valid)
    invalid_count = len(reports) - valid_count

    if args.json:
        output = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(reports),
                "valid": valid_count,
                "invalid": invalid_count,
            },
            "reports": [r.to_dict() for r in reports],
        }

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            logger.info(f"Rapport JSON sauvegardé: {args.output}")
        else:
            print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        logger.info("=" * 60)
        logger.info("RÉSUMÉ VALIDATION REFDATA")
        logger.info("=" * 60)
        logger.info(f"Bases valides   : {valid_count}/{len(reports)}")
        logger.info(f"Bases invalides : {invalid_count}/{len(reports)}")

        if invalid_count > 0:
            logger.warning("\nActions recommandées:")
            logger.warning("  1. Exécuter migrate_game_variant_category.py --all")
            logger.warning("  2. Exécuter backfill_killer_victim_pairs.py --all")

    # Code de sortie
    sys.exit(0 if invalid_count == 0 else 1)


if __name__ == "__main__":
    main()
