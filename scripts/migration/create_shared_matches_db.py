"""Crée la base de données partagée shared_matches.duckdb.

Ce script initialise la base `data/warehouse/shared_matches.duckdb`
à partir du DDL défini dans `scripts/migration/schema_v5.sql`.

Idempotent : si la base existe déjà avec le bon schéma, ne fait rien.

Usage :
    python scripts/migration/create_shared_matches_db.py [--force] [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb

# Résolution du répertoire racine du projet
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL_PATH = PROJECT_ROOT / "scripts" / "migration" / "schema_v5.sql"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "warehouse" / "shared_matches.duckdb"

logger = logging.getLogger(__name__)


def _parse_sql_statements(sql_path: Path) -> list[str]:
    """Parse le fichier SQL et retourne les instructions individuelles.

    Ignore les commentaires et les lignes vides.
    Gère les instructions multi-lignes terminées par ';'.

    Args:
        sql_path: Chemin vers le fichier SQL.

    Returns:
        Liste d'instructions SQL prêtes à exécuter.
    """
    content = sql_path.read_text(encoding="utf-8")

    # Supprimer les commentaires de ligne (-- ...)
    lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        # Supprimer les commentaires en fin de ligne
        comment_pos = line.find("--")
        if comment_pos >= 0:
            line = line[:comment_pos]
        lines.append(line)

    full_text = "\n".join(lines)

    # Découper sur les ';' et filtrer les instructions vides
    raw_statements = full_text.split(";")
    statements: list[str] = []
    for stmt in raw_statements:
        cleaned = stmt.strip()
        if cleaned:
            statements.append(cleaned + ";")

    return statements


def _get_existing_tables(conn: duckdb.DuckDBPyConnection) -> set[str]:
    """Retourne les tables existantes dans le schéma main.

    Args:
        conn: Connexion DuckDB.

    Returns:
        Ensemble des noms de tables.
    """
    try:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main'"
        ).fetchall()
        return {r[0] for r in rows} if rows else set()
    except Exception:
        return set()


EXPECTED_TABLES = {
    "match_registry",
    "match_participants",
    "highlight_events",
    "medals_earned",
    "xuid_aliases",
    "schema_version",
}


def create_shared_matches_db(
    db_path: Path = DEFAULT_DB_PATH,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    """Crée la base shared_matches.duckdb avec le schéma v5.

    Args:
        db_path: Chemin de la base à créer.
        force: Si True, supprime et recrée la base existante.
        dry_run: Si True, affiche ce qui serait fait sans exécuter.

    Returns:
        Dictionnaire avec les statistiques de l'opération.

    Raises:
        FileNotFoundError: Si le fichier SQL n'existe pas.
        RuntimeError: Si la base existe déjà sans --force.
    """
    if not SCHEMA_SQL_PATH.exists():
        raise FileNotFoundError(f"Fichier DDL introuvable : {SCHEMA_SQL_PATH}")

    stats: dict[str, object] = {
        "db_path": str(db_path),
        "created": False,
        "tables_created": [],
        "indexes_created": 0,
        "statements_executed": 0,
        "dry_run": dry_run,
    }

    # Vérifier si la base existe déjà
    if db_path.exists():
        if force:
            if not dry_run:
                db_path.unlink()
                logger.info(f"Base existante supprimée : {db_path}")
            else:
                logger.info(f"[DRY-RUN] Supprimerait : {db_path}")
        else:
            # Vérifier si le schéma est complet
            conn = duckdb.connect(str(db_path), read_only=True)
            try:
                existing = _get_existing_tables(conn)
                missing = EXPECTED_TABLES - existing
                if not missing:
                    logger.info(
                        f"Base déjà complète ({len(existing)} tables). "
                        "Utilisez --force pour recréer."
                    )
                    stats["tables_created"] = list(existing)
                    return stats
                else:
                    logger.warning(
                        f"Base existante incomplète. Tables manquantes : {missing}. "
                        "Utilisez --force pour recréer."
                    )
                    raise RuntimeError(
                        f"Base existante incomplète ({missing} manquent). "
                        "Utilisez --force pour recréer."
                    )
            finally:
                conn.close()

    # Créer le répertoire parent si nécessaire
    if not dry_run:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # Parser le SQL
    statements = _parse_sql_statements(SCHEMA_SQL_PATH)
    logger.info(f"DDL parsé : {len(statements)} instructions à exécuter")

    if dry_run:
        for i, stmt in enumerate(statements, 1):
            first_line = stmt.split("\n")[0][:80]
            logger.info(f"  [{i}] {first_line}")
        stats["statements_executed"] = len(statements)
        return stats

    # Exécuter le DDL
    conn = duckdb.connect(str(db_path))
    try:
        for stmt in statements:
            conn.execute(stmt)
            stats["statements_executed"] = (
                int(stats["statements_executed"]) + 1  # type: ignore[arg-type]
            )

        # Vérifier les tables créées
        created_tables = _get_existing_tables(conn)
        stats["tables_created"] = sorted(created_tables)
        stats["created"] = True

        # Compter les index
        try:
            idx_rows = conn.execute(
                "SELECT COUNT(*) FROM duckdb_indexes()"
            ).fetchone()
            stats["indexes_created"] = idx_rows[0] if idx_rows else 0
        except Exception:
            pass

        # Validation finale
        missing = EXPECTED_TABLES - created_tables
        if missing:
            raise RuntimeError(
                f"Erreur de création : tables manquantes après exécution : {missing}"
            )

        logger.info(
            f"✅ Base créée : {db_path} "
            f"({len(created_tables)} tables, {stats['indexes_created']} index)"
        )

    finally:
        conn.close()

    return stats


def validate_shared_schema(db_path: Path = DEFAULT_DB_PATH) -> dict[str, object]:
    """Valide le schéma de shared_matches.duckdb.

    Vérifie la présence de toutes les tables, colonnes-clé et index.

    Args:
        db_path: Chemin de la base à valider.

    Returns:
        Dictionnaire avec les résultats de validation.

    Raises:
        FileNotFoundError: Si la base n'existe pas.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Base introuvable : {db_path}")

    result: dict[str, object] = {
        "valid": True,
        "tables": {},
        "errors": [],
    }

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        # Vérifier les tables
        existing = _get_existing_tables(conn)
        for table in EXPECTED_TABLES:
            if table in existing:
                # Compter les colonnes
                col_count = conn.execute(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = 'main' AND table_name = ?",
                    [table],
                ).fetchone()
                result["tables"][table] = {  # type: ignore[index]
                    "exists": True,
                    "columns": col_count[0] if col_count else 0,
                }
            else:
                result["tables"][table] = {"exists": False, "columns": 0}  # type: ignore[index]
                result["errors"].append(f"Table manquante : {table}")  # type: ignore[union-attr]
                result["valid"] = False

        # Vérifier les colonnes critiques
        critical_columns = {
            "match_registry": [
                "match_id", "start_time", "playlist_id", "map_id",
                "mode_category", "is_ranked", "player_count",
            ],
            "match_participants": [
                "match_id", "xuid", "gamertag", "team_id", "outcome",
                "kills", "deaths", "assists",
            ],
            "highlight_events": [
                "id", "match_id", "event_type", "killer_xuid", "victim_xuid",
            ],
            "medals_earned": [
                "match_id", "xuid", "medal_name_id", "count",
            ],
            "xuid_aliases": [
                "xuid", "gamertag", "source",
            ],
        }

        for table, columns in critical_columns.items():
            if table not in existing:
                continue
            existing_cols = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'main' AND table_name = ?",
                [table],
            ).fetchall()
            col_names = {r[0] for r in existing_cols} if existing_cols else set()

            for col in columns:
                if col not in col_names:
                    result["errors"].append(  # type: ignore[union-attr]
                        f"Colonne manquante : {table}.{col}"
                    )
                    result["valid"] = False

        # Vérifier les index
        try:
            indexes = conn.execute("SELECT * FROM duckdb_indexes()").fetchall()
            result["index_count"] = len(indexes) if indexes else 0
        except Exception:
            result["index_count"] = 0

        # Vérifier la version du schéma
        if "schema_version" in existing:
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            result["schema_version"] = version[0] if version else None
        else:
            result["schema_version"] = None

    finally:
        conn.close()

    return result


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(
        description="Crée la base de données partagée shared_matches.duckdb (v5)"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Chemin de la base (défaut : {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Supprimer et recréer la base si elle existe",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Afficher les opérations sans les exécuter",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Valider le schéma d'une base existante",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Activer les logs détaillés",
    )
    args = parser.parse_args()

    # Configuration du logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.validate:
        try:
            result = validate_shared_schema(args.db_path)
            if result["valid"]:
                print(f"✅ Schéma valide ({result.get('index_count', '?')} index)")
                for table, info in result.get("tables", {}).items():
                    if isinstance(info, dict):
                        print(f"  • {table}: {info.get('columns', '?')} colonnes")
            else:
                print("❌ Schéma invalide :")
                for error in result.get("errors", []):
                    print(f"  ✗ {error}")
                sys.exit(1)
        except FileNotFoundError as e:
            print(f"❌ {e}")
            sys.exit(1)
        return

    try:
        stats = create_shared_matches_db(
            db_path=args.db_path,
            force=args.force,
            dry_run=args.dry_run,
        )
        prefix = "[DRY-RUN] " if args.dry_run else ""
        tables = stats.get("tables_created", [])
        print(
            f"{prefix}✅ {stats['db_path']} — "
            f"{len(tables)} tables, "
            f"{stats.get('indexes_created', '?')} index, "
            f"{stats.get('statements_executed', 0)} instructions"
        )
    except (FileNotFoundError, RuntimeError) as e:
        print(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
