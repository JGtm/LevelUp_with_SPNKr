#!/usr/bin/env python3
"""
Script de diagnostic pour vérifier la colonne accuracy dans match_stats.

Vérifie:
1. Si la colonne accuracy existe dans la table match_stats
2. Si les données sont présentes dans la colonne
3. Si les requêtes SQL pointent vers la bonne colonne
"""

import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    print("ERREUR: Module duckdb non installé")
    sys.exit(1)


def check_table_schema(db_path: Path) -> dict:
    """Vérifie le schéma de la table match_stats."""
    try:
        conn = duckdb.connect(str(db_path), read_only=True)

        # Vérifier si la table existe
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'match_stats'"
        ).fetchall()

        if not tables:
            return {"error": "Table match_stats n'existe pas"}

        # Récupérer les colonnes de la table
        columns = conn.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'match_stats'
            ORDER BY ordinal_position
            """
        ).fetchall()

        # Vérifier si accuracy existe
        has_accuracy = any(col[0] == "accuracy" for col in columns)

        # Compter les lignes avec accuracy NULL vs non-NULL
        accuracy_stats = None
        if has_accuracy:
            stats = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(accuracy) as non_null,
                    COUNT(*) - COUNT(accuracy) as null_count,
                    AVG(accuracy) as avg_accuracy
                FROM match_stats
                """
            ).fetchone()
            accuracy_stats = {
                "total": stats[0],
                "non_null": stats[1],
                "null_count": stats[2],
                "avg_accuracy": stats[3],
            }

        conn.close()

        return {
            "table_exists": True,
            "has_accuracy_column": has_accuracy,
            "columns": [{"name": col[0], "type": col[1], "nullable": col[2]} for col in columns],
            "accuracy_stats": accuracy_stats,
        }
    except Exception as e:
        return {"error": str(e)}


def check_repository_queries() -> dict:
    """Vérifie si les requêtes du repository incluent accuracy."""
    repo_file = Path("src/data/repositories/duckdb_repo.py")
    if not repo_file.exists():
        return {"error": "Fichier repository non trouvé"}

    content = repo_file.read_text(encoding="utf-8")

    # Vérifier si accuracy est dans les SELECT
    has_accuracy_in_select = "accuracy" in content and "SELECT" in content

    # Compter les occurrences
    accuracy_count = content.count("accuracy")

    return {
        "has_accuracy_in_code": has_accuracy_in_select,
        "accuracy_mentions": accuracy_count,
    }


def check_dataframe_conversion() -> dict:
    """Vérifie si la conversion en DataFrame inclut accuracy."""
    bridge_file = Path("src/data/integration/streamlit_bridge.py")
    if not bridge_file.exists():
        return {"error": "Fichier bridge non trouvé"}

    content = bridge_file.read_text(encoding="utf-8")

    # Vérifier si accuracy est dans matches_to_dataframe
    has_accuracy = '"accuracy"' in content or "'accuracy'" in content

    return {
        "has_accuracy_in_dataframe": has_accuracy,
    }


def main():
    """Point d'entrée principal."""
    print("=" * 60)
    print("DIAGNOSTIC: Colonne accuracy dans match_stats")
    print("=" * 60)
    print()

    # Trouver les bases de données joueur
    data_dir = Path("data/players")
    if not data_dir.exists():
        print(f"ERREUR: Dossier {data_dir} non trouvé")
        sys.exit(1)

    player_dbs = list(data_dir.glob("*/stats.duckdb"))

    if not player_dbs:
        print("Aucune base de données joueur trouvée")
        sys.exit(1)

    print(f"Bases de données trouvées: {len(player_dbs)}")
    print()

    # Vérifier chaque base
    for db_path in player_dbs:
        gamertag = db_path.parent.name
        print(f"--- {gamertag} ---")
        print(f"Chemin: {db_path}")

        schema_info = check_table_schema(db_path)

        if "error" in schema_info:
            print(f"  ERREUR: {schema_info['error']}")
            continue

        print(f"  Table existe: {schema_info['table_exists']}")
        print(f"  Colonne accuracy existe: {schema_info['has_accuracy_column']}")

        if schema_info.get("accuracy_stats"):
            stats = schema_info["accuracy_stats"]
            print(f"  Total matchs: {stats['total']}")
            print(f"  Accuracy non-NULL: {stats['non_null']}")
            print(f"  Accuracy NULL: {stats['null_count']}")
            if stats["avg_accuracy"] is not None:
                print(f"  Précision moyenne: {stats['avg_accuracy']:.2f}%")

        print()

    # Vérifier le code
    print("--- Vérification du code ---")
    repo_info = check_repository_queries()
    if "error" not in repo_info:
        print(f"  Accuracy dans le code: {repo_info['has_accuracy_in_code']}")
        print(f"  Mentions de 'accuracy': {repo_info['accuracy_mentions']}")

    bridge_info = check_dataframe_conversion()
    if "error" not in bridge_info:
        print(f"  Accuracy dans DataFrame: {bridge_info['has_accuracy_in_dataframe']}")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
