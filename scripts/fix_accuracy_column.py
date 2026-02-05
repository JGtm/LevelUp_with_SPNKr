#!/usr/bin/env python3
"""
Script pour ajouter la colonne accuracy à match_stats si elle manque.

Ce script vérifie toutes les bases de données joueur et ajoute la colonne
accuracy si elle n'existe pas déjà.
"""

import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    print("ERREUR: Module duckdb non installé")
    print("Installez-le avec: pip install duckdb")
    sys.exit(1)


def fix_accuracy_column(db_path: Path) -> dict:
    """Ajoute la colonne accuracy si elle manque."""
    try:
        conn = duckdb.connect(str(db_path), read_only=False)

        # Vérifier si la table existe
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'match_stats'"
        ).fetchall()

        if not tables:
            return {"error": "Table match_stats n'existe pas", "fixed": False}

        # Vérifier si la colonne accuracy existe
        columns = conn.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'match_stats' AND column_name = 'accuracy'
            """
        ).fetchall()

        if columns:
            # La colonne existe déjà
            conn.close()
            return {"fixed": False, "reason": "Colonne accuracy déjà présente"}

        # Ajouter la colonne
        print("  Ajout de la colonne accuracy...")
        conn.execute("ALTER TABLE match_stats ADD COLUMN accuracy FLOAT")
        conn.commit()

        # Vérifier le nombre de lignes avec accuracy NULL
        stats = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                COUNT(accuracy) as non_null
            FROM match_stats
            """
        ).fetchone()

        conn.close()

        return {
            "fixed": True,
            "total_matches": stats[0],
            "non_null_accuracy": stats[1],
        }
    except Exception as e:
        return {"error": str(e), "fixed": False}


def main():
    """Point d'entrée principal."""
    print("=" * 60)
    print("CORRECTION: Ajout de la colonne accuracy à match_stats")
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
        sys.exit(0)

    print(f"Bases de données trouvées: {len(player_dbs)}")
    print()

    fixed_count = 0
    already_ok_count = 0
    error_count = 0

    # Corriger chaque base
    for db_path in player_dbs:
        gamertag = db_path.parent.name
        print(f"--- {gamertag} ---")
        print(f"Chemin: {db_path}")

        result = fix_accuracy_column(db_path)

        if "error" in result:
            print(f"  ERREUR: {result['error']}")
            error_count += 1
        elif result.get("fixed"):
            print("  ✓ Colonne accuracy ajoutée")
            print(f"  Total matchs: {result['total_matches']}")
            print(f"  Accuracy non-NULL: {result['non_null_accuracy']}")
            fixed_count += 1
        else:
            print(f"  ✓ {result.get('reason', 'Déjà OK')}")
            already_ok_count += 1

        print()

    # Résumé
    print("=" * 60)
    print("RÉSUMÉ")
    print("=" * 60)
    print(f"  Bases corrigées: {fixed_count}")
    print(f"  Bases déjà OK: {already_ok_count}")
    print(f"  Erreurs: {error_count}")
    print()

    if fixed_count > 0:
        print("⚠ IMPORTANT: Les matchs existants ont accuracy=NULL.")
        print("  Pour remplir ces valeurs, vous devez:")
        print("  1. Re-synchroniser les matchs (python scripts/sync.py --delta)")
        print("  2. Ou faire un backfill complet")
    print()


if __name__ == "__main__":
    main()
