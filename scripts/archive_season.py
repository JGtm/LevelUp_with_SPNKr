#!/usr/bin/env python3
"""Script d'archivage des matchs anciens vers Parquet (cold storage).

Archive les matchs antérieurs à une date de cutoff vers des fichiers Parquet
compressés, permettant de garder la DB principale légère tout en conservant
l'historique complet.

Usage:
    python scripts/archive_season.py --gamertag Chocoboflor --cutoff 2024-01-01
    python scripts/archive_season.py --gamertag Chocoboflor --older-than-days 365
    python scripts/archive_season.py --gamertag Chocoboflor --dry-run
    python scripts/archive_season.py --gamertag Chocoboflor --list-archives

Structure de sortie:
    data/players/{gamertag}/
    ├── stats.duckdb          # Données récentes (après cutoff)
    └── archive/
        ├── matches_2023.parquet
        ├── matches_2024_Q1.parquet
        └── archive_index.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Ajouter le répertoire parent au path pour les imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_player_paths(gamertag: str) -> tuple[Path, Path] | None:
    """Retourne les chemins vers la DB et le dossier archive d'un joueur.

    Returns:
        Tuple (db_path, archive_dir) ou None si la DB n'existe pas.
    """
    players_dir = REPO_ROOT / "data" / "players" / gamertag
    db_path = players_dir / "stats.duckdb"
    archive_dir = players_dir / "archive"

    if not db_path.exists():
        return None

    return db_path, archive_dir


def list_all_players() -> list[str]:
    """Liste tous les joueurs ayant une DB DuckDB."""
    players_dir = REPO_ROOT / "data" / "players"
    if not players_dir.exists():
        return []

    players = []
    for player_dir in players_dir.iterdir():
        if player_dir.is_dir() and (player_dir / "stats.duckdb").exists():
            players.append(player_dir.name)
    return sorted(players)


def get_match_stats(
    db_path: Path,
) -> dict[str, Any]:
    """Récupère les statistiques des matchs (count, dates min/max).

    Returns:
        Dict avec total_matches, oldest_date, newest_date, years.
    """
    import duckdb

    conn = duckdb.connect(str(db_path), read_only=True)

    result = conn.execute("""
        SELECT
            COUNT(*) as total,
            MIN(start_time) as oldest,
            MAX(start_time) as newest,
            EXTRACT(YEAR FROM MIN(start_time)) as min_year,
            EXTRACT(YEAR FROM MAX(start_time)) as max_year
        FROM match_stats
    """).fetchone()

    # Répartition par année
    year_counts = conn.execute("""
        SELECT
            EXTRACT(YEAR FROM start_time) as year,
            COUNT(*) as count
        FROM match_stats
        GROUP BY year
        ORDER BY year
    """).fetchall()

    conn.close()

    return {
        "total_matches": result[0] or 0,
        "oldest_date": result[1],
        "newest_date": result[2],
        "min_year": int(result[3]) if result[3] else None,
        "max_year": int(result[4]) if result[4] else None,
        "by_year": {int(row[0]): row[1] for row in year_counts},
    }


def get_archive_index(archive_dir: Path) -> dict[str, Any]:
    """Charge l'index des archives existantes.

    Returns:
        Dict avec les métadonnées des archives.
    """
    index_file = archive_dir / "archive_index.json"

    if not index_file.exists():
        return {"version": 1, "archives": [], "last_updated": None}

    with open(index_file, encoding="utf-8") as f:
        return json.load(f)


def save_archive_index(archive_dir: Path, index: dict[str, Any]) -> None:
    """Sauvegarde l'index des archives."""
    index_file = archive_dir / "archive_index.json"
    index["last_updated"] = datetime.now().isoformat()

    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False, default=str)


def archive_matches(
    gamertag: str,
    cutoff_date: datetime,
    *,
    compression_level: int = 9,
    delete_after_archive: bool = False,
    dry_run: bool = False,
    by_year: bool = True,
) -> tuple[bool, str, dict]:
    """Archive les matchs antérieurs à la date de cutoff.

    Args:
        gamertag: Gamertag du joueur.
        cutoff_date: Date limite (les matchs AVANT cette date seront archivés).
        compression_level: Niveau de compression Zstd (1-22).
        delete_after_archive: Si True, supprime les matchs de la DB après archivage.
        dry_run: Si True, affiche les opérations sans les exécuter.
        by_year: Si True, crée un fichier par année.

    Returns:
        Tuple (success, message, stats).
    """
    import duckdb

    paths = get_player_paths(gamertag)
    if not paths:
        return False, f"DB non trouvée pour {gamertag}", {}

    db_path, archive_dir = paths

    # Créer le répertoire archive
    if not dry_run:
        archive_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        "matches_archived": 0,
        "files_created": [],
        "bytes_written": 0,
        "compression_level": compression_level,
        "cutoff_date": cutoff_date.isoformat(),
    }

    try:
        # Connexion en lecture seule d'abord pour analyser
        conn = duckdb.connect(str(db_path), read_only=True)

        # Compter les matchs à archiver
        count_result = conn.execute(
            "SELECT COUNT(*) FROM match_stats WHERE start_time < ?",
            [cutoff_date],
        ).fetchone()
        matches_to_archive = count_result[0] if count_result else 0

        if matches_to_archive == 0:
            conn.close()
            return True, f"Aucun match à archiver avant {cutoff_date.date()}", stats

        logger.info(
            f"Archivage de {gamertag}: {matches_to_archive} matchs avant {cutoff_date.date()}"
        )

        if dry_run:
            logger.info("[DRY-RUN] Aucune modification effectuée")
            conn.close()
            stats["matches_archived"] = matches_to_archive
            return True, f"[DRY-RUN] {matches_to_archive} matchs seraient archivés", stats

        # Récupérer les années distinctes à archiver
        years_result = conn.execute(
            """
            SELECT DISTINCT EXTRACT(YEAR FROM start_time) as year
            FROM match_stats
            WHERE start_time < ?
            ORDER BY year
        """,
            [cutoff_date],
        ).fetchall()
        years_to_archive = [int(row[0]) for row in years_result]

        conn.close()

        # Archiver par année ou en un seul fichier
        if by_year and len(years_to_archive) > 1:
            for year in years_to_archive:
                year_start = datetime(year, 1, 1)
                year_end = datetime(year + 1, 1, 1)
                # Ne pas dépasser la date de cutoff
                actual_end = min(year_end, cutoff_date)

                ok, msg, year_stats = _archive_date_range(
                    db_path,
                    archive_dir,
                    year_start,
                    actual_end,
                    f"matches_{year}",
                    compression_level,
                    delete_after_archive,
                )

                if ok and year_stats.get("matches_archived", 0) > 0:
                    stats["matches_archived"] += year_stats["matches_archived"]
                    stats["bytes_written"] += year_stats.get("bytes_written", 0)
                    if year_stats.get("file_path"):
                        stats["files_created"].append(year_stats["file_path"])
        else:
            # Archiver en un seul fichier
            archive_name = f"matches_before_{cutoff_date.strftime('%Y%m%d')}"
            ok, msg, single_stats = _archive_date_range(
                db_path,
                archive_dir,
                datetime(1970, 1, 1),
                cutoff_date,
                archive_name,
                compression_level,
                delete_after_archive,
            )

            if ok:
                stats["matches_archived"] = single_stats.get("matches_archived", 0)
                stats["bytes_written"] = single_stats.get("bytes_written", 0)
                if single_stats.get("file_path"):
                    stats["files_created"].append(single_stats["file_path"])

        # Mettre à jour l'index des archives
        index = get_archive_index(archive_dir)
        for file_path in stats["files_created"]:
            if file_path not in [a["file"] for a in index["archives"]]:
                index["archives"].append(
                    {
                        "file": file_path,
                        "created_at": datetime.now().isoformat(),
                        "cutoff_date": cutoff_date.isoformat(),
                    }
                )
        save_archive_index(archive_dir, index)

        # Résumé
        total_mb = stats["bytes_written"] / (1024 * 1024)
        msg = (
            f"Archivage {gamertag}: {stats['matches_archived']} matchs, "
            f"{len(stats['files_created'])} fichiers, {total_mb:.2f} MB"
        )
        logger.info(msg)

        return True, msg, stats

    except Exception as e:
        msg = f"Erreur archivage {gamertag}: {e}"
        logger.error(msg, exc_info=True)
        return False, msg, stats


def _archive_date_range(
    db_path: Path,
    archive_dir: Path,
    start_date: datetime,
    end_date: datetime,
    archive_name: str,
    compression_level: int,
    delete_after_archive: bool,
) -> tuple[bool, str, dict]:
    """Archive les matchs dans une plage de dates.

    Returns:
        Tuple (success, message, stats).
    """
    import duckdb

    stats = {"matches_archived": 0, "bytes_written": 0, "file_path": None}

    # Connexion en lecture pour l'export
    conn = duckdb.connect(str(db_path), read_only=True)

    # Compter les matchs dans cette plage
    count = conn.execute(
        "SELECT COUNT(*) FROM match_stats WHERE start_time >= ? AND start_time < ?",
        [start_date, end_date],
    ).fetchone()[0]

    if count == 0:
        conn.close()
        return True, "Aucun match dans cette plage", stats

    # Exporter vers Parquet
    output_file = archive_dir / f"{archive_name}.parquet"

    conn.execute(f"""
        COPY (
            SELECT * FROM match_stats
            WHERE start_time >= '{start_date.isoformat()}'
            AND start_time < '{end_date.isoformat()}'
            ORDER BY start_time
        ) TO '{output_file}'
        (FORMAT PARQUET, COMPRESSION 'zstd', COMPRESSION_LEVEL {compression_level})
    """)

    conn.close()

    stats["matches_archived"] = count
    stats["bytes_written"] = output_file.stat().st_size
    stats["file_path"] = output_file.name

    size_mb = stats["bytes_written"] / (1024 * 1024)
    logger.info(f"  {archive_name}: {count} matchs, {size_mb:.2f} MB")

    # Supprimer de la DB si demandé
    if delete_after_archive:
        write_conn = duckdb.connect(str(db_path), read_only=False)
        write_conn.execute(
            "DELETE FROM match_stats WHERE start_time >= ? AND start_time < ?",
            [start_date, end_date],
        )
        write_conn.close()
        logger.info(f"  Supprimé {count} matchs de la DB principale")

    return True, f"Archivé {count} matchs", stats


def list_archives(gamertag: str) -> None:
    """Affiche les archives existantes pour un joueur."""
    paths = get_player_paths(gamertag)
    if not paths:
        logger.error(f"DB non trouvée pour {gamertag}")
        return

    db_path, archive_dir = paths

    # Stats de la DB principale
    match_stats = get_match_stats(db_path)

    logger.info(f"\n{'='*60}")
    logger.info(f"Joueur: {gamertag}")
    logger.info(f"{'='*60}")

    logger.info(f"\nDB Principale ({db_path.name}):")
    logger.info(f"  Total matchs: {match_stats['total_matches']}")
    if match_stats["oldest_date"]:
        logger.info(f"  Plus ancien: {match_stats['oldest_date']}")
        logger.info(f"  Plus récent: {match_stats['newest_date']}")

    if match_stats["by_year"]:
        logger.info("\n  Par année:")
        for year, count in sorted(match_stats["by_year"].items()):
            logger.info(f"    {year}: {count} matchs")

    # Archives
    if archive_dir.exists():
        logger.info(f"\nArchives ({archive_dir}):")

        index = get_archive_index(archive_dir)

        parquet_files = list(archive_dir.glob("*.parquet"))
        if parquet_files:
            total_size = sum(f.stat().st_size for f in parquet_files)
            logger.info(f"  Fichiers: {len(parquet_files)}")
            logger.info(f"  Taille totale: {total_size / (1024*1024):.2f} MB")

            for pf in sorted(parquet_files):
                size_mb = pf.stat().st_size / (1024 * 1024)
                logger.info(f"    - {pf.name} ({size_mb:.2f} MB)")
        else:
            logger.info("  Aucune archive")

        if index.get("last_updated"):
            logger.info(f"\n  Dernière mise à jour: {index['last_updated']}")
    else:
        logger.info("\nArchives: Aucune (dossier inexistant)")

    # Recommandations
    logger.info(f"\n{'='*60}")
    logger.info("Recommandations:")

    if match_stats["total_matches"] >= 5000:
        logger.info("  ⚠ > 5000 matchs : archivage recommandé")

    if match_stats["min_year"] and match_stats["max_year"]:
        span = match_stats["max_year"] - match_stats["min_year"]
        if span >= 2:
            logger.info(f"  ⚠ Historique sur {span+1} années : archivage par année recommandé")

    if match_stats["total_matches"] < 1000:
        logger.info("  ✓ < 1000 matchs : archivage non nécessaire")


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Archive les matchs anciens vers Parquet (cold storage)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Lister les archives existantes
  python scripts/archive_season.py --gamertag Chocoboflor --list-archives

  # Archiver les matchs avant 2024
  python scripts/archive_season.py --gamertag Chocoboflor --cutoff 2024-01-01

  # Archiver les matchs de plus d'un an (365 jours)
  python scripts/archive_season.py --gamertag Chocoboflor --older-than-days 365

  # Dry-run (voir ce qui serait archivé sans effectuer l'opération)
  python scripts/archive_season.py --gamertag Chocoboflor --cutoff 2024-01-01 --dry-run

  # Archiver ET supprimer de la DB principale
  python scripts/archive_season.py --gamertag Chocoboflor --cutoff 2024-01-01 --delete

Seuils recommandés:
  - > 5000 matchs : archiver pour améliorer les performances
  - > 1 an d'historique : archiver par année
        """,
    )

    parser.add_argument(
        "--gamertag",
        "-g",
        type=str,
        required=True,
        help="Gamertag du joueur",
    )
    parser.add_argument(
        "--cutoff",
        type=str,
        help="Date de cutoff (format: YYYY-MM-DD). Les matchs AVANT cette date seront archivés.",
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        help="Archiver les matchs plus anciens que N jours",
    )
    parser.add_argument(
        "--compression-level",
        "-c",
        type=int,
        default=9,
        help="Niveau de compression Zstd (1-22, défaut: 9)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Supprimer les matchs de la DB après archivage (ATTENTION: irréversible!)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Afficher ce qui serait fait sans l'exécuter",
    )
    parser.add_argument(
        "--single-file",
        action="store_true",
        help="Créer un seul fichier d'archive au lieu de un par année",
    )
    parser.add_argument(
        "--list-archives",
        "-l",
        action="store_true",
        help="Lister les archives existantes et les statistiques",
    )
    parser.add_argument(
        "--list-players",
        action="store_true",
        help="Lister les joueurs disponibles",
    )

    args = parser.parse_args()

    # Lister les joueurs
    if args.list_players:
        players = list_all_players()
        if players:
            logger.info("Joueurs disponibles:")
            for p in players:
                paths = get_player_paths(p)
                if paths:
                    db_size = paths[0].stat().st_size / (1024 * 1024)
                    logger.info(f"  - {p} ({db_size:.1f} MB)")
        else:
            logger.info("Aucun joueur trouvé")
        return 0

    # Lister les archives
    if args.list_archives:
        list_archives(args.gamertag)
        return 0

    # Validation des arguments
    if not args.cutoff and not args.older_than_days:
        parser.error("--cutoff ou --older-than-days requis pour archiver")

    # Calculer la date de cutoff
    if args.cutoff:
        try:
            cutoff_date = datetime.strptime(args.cutoff, "%Y-%m-%d")
        except ValueError:
            parser.error("Format de date invalide. Utiliser YYYY-MM-DD")
    else:
        cutoff_date = datetime.now() - timedelta(days=args.older_than_days)

    # Avertissement si suppression demandée
    if args.delete and not args.dry_run:
        logger.warning("=" * 60)
        logger.warning("ATTENTION: --delete va SUPPRIMER les matchs de la DB!")
        logger.warning("Cette opération est IRRÉVERSIBLE.")
        logger.warning("Assurez-vous d'avoir un backup avant de continuer.")
        logger.warning("=" * 60)

        response = input("Continuer? (oui/non): ")
        if response.lower() not in ("oui", "yes", "o", "y"):
            logger.info("Opération annulée")
            return 0

    # Archiver
    success, msg, stats = archive_matches(
        args.gamertag,
        cutoff_date,
        compression_level=args.compression_level,
        delete_after_archive=args.delete,
        dry_run=args.dry_run,
        by_year=not args.single_file,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
