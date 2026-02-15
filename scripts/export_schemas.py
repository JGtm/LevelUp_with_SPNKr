#!/usr/bin/env python3
"""Exporte les schémas SQL de toutes les bases DuckDB du projet.

Produit un fichier `.ai/v5-schemas-export.md` documentant :
- Le schéma complet de chaque base joueur (tables, colonnes, types, index)
- Le schéma de metadata.duckdb (si existante)
- Un résumé comparatif inter-joueurs

Usage:
    python scripts/export_schemas.py
    python scripts/export_schemas.py --output .ai/v5-schemas-export.md
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_profiles() -> dict:
    """Charge les profils joueurs depuis db_profiles.json."""
    profiles_path = REPO_ROOT / "db_profiles.json"
    if not profiles_path.exists():
        logger.error("db_profiles.json introuvable")
        return {}
    with open(profiles_path, encoding="utf-8") as f:
        return json.load(f)


def export_table_schema(con: duckdb.DuckDBPyConnection, table_name: str) -> dict:
    """Exporte le schéma d'une table (colonnes, types, contraintes)."""
    columns = con.execute(
        """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = ?
        ORDER BY ordinal_position
        """,
        [table_name],
    ).fetchall()

    return {
        "columns": [
            {
                "name": c[0],
                "type": c[1],
                "nullable": c[2] == "YES",
                "default": c[3],
            }
            for c in columns
        ]
    }


def export_table_row_count(con: duckdb.DuckDBPyConnection, table_name: str) -> int:
    """Retourne le nombre de lignes d'une table."""
    try:
        result = con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
        return result[0] if result else 0
    except Exception:
        return -1


def export_indexes(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Liste les index de la base."""
    try:
        rows = con.execute(
            """
            SELECT index_name, table_name, is_unique, sql
            FROM duckdb_indexes()
            """
        ).fetchall()
        return [
            {
                "name": r[0],
                "table": r[1],
                "unique": r[2],
                "sql": r[3],
            }
            for r in rows
        ]
    except Exception:
        return []


def export_db_schema(db_path: Path) -> dict:
    """Exporte le schéma complet d'une base DuckDB."""
    if not db_path.exists():
        return {"error": f"Base introuvable : {db_path}"}

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        # Lister les tables
        tables_raw = con.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
            """
        ).fetchall()
        table_names = [t[0] for t in tables_raw]

        tables = {}
        for tname in table_names:
            schema = export_table_schema(con, tname)
            schema["row_count"] = export_table_row_count(con, tname)
            tables[tname] = schema

        indexes = export_indexes(con)

        # Taille du fichier
        file_size_mb = db_path.stat().st_size / (1024 * 1024)

        return {
            "path": str(db_path),
            "file_size_mb": round(file_size_mb, 2),
            "table_count": len(table_names),
            "tables": tables,
            "indexes": indexes,
        }
    finally:
        con.close()


def format_schema_markdown(label: str, schema: dict) -> str:
    """Formate un schéma en Markdown."""
    lines: list[str] = []
    if "error" in schema:
        lines.append(f"### {label}")
        lines.append(f"⚠️ {schema['error']}")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"### {label}")
    lines.append(f"- **Chemin** : `{schema['path']}`")
    lines.append(f"- **Taille** : {schema['file_size_mb']} MB")
    lines.append(f"- **Tables** : {schema['table_count']}")
    lines.append("")

    for tname, tinfo in sorted(schema["tables"].items()):
        lines.append(f"#### `{tname}` ({tinfo['row_count']} lignes)")
        lines.append("")
        lines.append("| Colonne | Type | Nullable | Default |")
        lines.append("|---------|------|----------|---------|")
        for col in tinfo["columns"]:
            nullable = "✓" if col["nullable"] else "✗"
            default = col["default"] or "-"
            lines.append(f"| `{col['name']}` | `{col['type']}` | {nullable} | {default} |")
        lines.append("")

    if schema["indexes"]:
        lines.append("#### Index")
        lines.append("")
        lines.append("| Nom | Table | Unique | SQL |")
        lines.append("|-----|-------|--------|-----|")
        for idx in schema["indexes"]:
            unique = "✓" if idx["unique"] else "✗"
            sql = (idx["sql"] or "")[:80]
            lines.append(f"| `{idx['name']}` | `{idx['table']}` | {unique} | `{sql}` |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(description="Export des schémas SQL DuckDB")
    parser.add_argument(
        "--output",
        type=str,
        default=".ai/v5-schemas-export.md",
        help="Fichier de sortie (défaut: .ai/v5-schemas-export.md)",
    )
    args = parser.parse_args()

    output_path = REPO_ROOT / args.output

    profiles = load_profiles()
    if not profiles:
        logger.error("Aucun profil trouvé")
        sys.exit(1)

    report_lines: list[str] = [
        "# Export des Schémas SQL — Baseline pré-v5",
        "",
        f"> Généré le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## Sommaire",
        "",
    ]

    # Metadata DB
    metadata_path = REPO_ROOT / profiles.get("metadata_db", "data/warehouse/metadata.duckdb")
    metadata_schema = export_db_schema(metadata_path)
    report_lines.append("- metadata.duckdb")

    # Player DBs
    player_schemas: dict[str, dict] = {}
    for gamertag, profile in profiles.get("profiles", {}).items():
        db_path = REPO_ROOT / profile["db_path"]
        player_schemas[gamertag] = export_db_schema(db_path)
        report_lines.append(f"- {gamertag}")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Metadata section
    report_lines.append("## Metadata DB")
    report_lines.append("")
    report_lines.append(format_schema_markdown("metadata.duckdb", metadata_schema))
    report_lines.append("")

    # Player sections
    report_lines.append("## Bases Joueurs")
    report_lines.append("")
    for gamertag, schema in sorted(player_schemas.items()):
        report_lines.append(format_schema_markdown(gamertag, schema))
        report_lines.append("")

    # Résumé comparatif
    report_lines.append("## Résumé Comparatif")
    report_lines.append("")
    report_lines.append(
        "| Joueur | Tables | Matchs | Médailles | Events | Participants | Taille (MB) |"
    )
    report_lines.append(
        "|--------|--------|--------|-----------|--------|-------------|-------------|"
    )

    for gamertag, schema in sorted(player_schemas.items()):
        if "error" in schema:
            report_lines.append(f"| {gamertag} | ❌ Erreur | - | - | - | - | - |")
            continue
        tables = schema["tables"]
        match_count = tables.get("match_stats", {}).get("row_count", 0)
        medal_count = tables.get("medals_earned", {}).get("row_count", 0)
        event_count = tables.get("highlight_events", {}).get("row_count", 0)
        participant_count = tables.get("match_participants", {}).get("row_count", 0)
        report_lines.append(
            f"| {gamertag} | {schema['table_count']} | {match_count} "
            f"| {medal_count} | {event_count} | {participant_count} "
            f"| {schema['file_size_mb']} |"
        )
    report_lines.append("")

    # Écriture du fichier
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(report_lines), encoding="utf-8")
    logger.info("Schémas exportés vers %s", output_path)


if __name__ == "__main__":
    main()
