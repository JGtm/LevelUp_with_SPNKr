"""
Script de diagnostic pour vérifier la résolution des métadonnées dans les requêtes SQL.
"""

import sys
from pathlib import Path

# Ajouter le répertoire racine au path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

try:
    import duckdb

    from src.data.repositories.duckdb_repo import DuckDBRepository
except ImportError as e:
    print(f"❌ Erreur d'import: {e}")
    print("Assurez-vous d'être dans l'environnement virtuel avec les dépendances installées.")
    sys.exit(1)


def diagnose_metadata_resolution(gamertag: str, xuid: str):
    """Diagnostique la résolution des métadonnées."""
    print(f"🔍 Diagnostic de la résolution des métadonnées pour {gamertag}")
    print("=" * 60)

    db_path = root / "data" / "players" / gamertag / "stats.duckdb"
    if not db_path.exists():
        print(f"❌ Base de données non trouvée: {db_path}")
        return

    repo = DuckDBRepository(str(db_path), xuid)

    try:
        conn = repo._get_connection()

        # Vérifier si meta est attaché
        print("\n1. Vérification de l'attachement de metadata.duckdb")
        print("-" * 60)
        attached_dbs = repo._attached_dbs
        print(f"Bases attachées: {attached_dbs}")

        if "meta" not in attached_dbs:
            print("❌ metadata.duckdb n'est PAS attaché!")
            print("   → Les jointures ne fonctionneront pas.")
            return
        else:
            print("✅ metadata.duckdb est attaché")

        # Vérifier les tables de métadonnées
        print("\n2. Vérification des tables de métadonnées")
        print("-" * 60)
        # Vérifier dans tous les schémas
        all_tables = conn.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "ORDER BY table_schema, table_name"
        ).fetchall()
        print("Toutes les tables disponibles:")
        for schema, table in all_tables:
            print(f"  {schema}.{table}")

        # Vérifier spécifiquement dans meta
        tables_result = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'meta' ORDER BY table_name"
        ).fetchall()
        meta_tables = [row[0] for row in tables_result]
        print(f"\nTables dans meta: {meta_tables}")

        # Vérifier si les tables sont dans le schéma main de metadata.duckdb
        # En DuckDB, quand on ATTACH une DB, les tables peuvent être dans 'main' ou dans le nom du schéma attaché
        try:
            # Essayer de voir les tables directement depuis meta
            direct_tables = conn.execute("SHOW TABLES FROM meta").fetchall()
            print(f"Tables directes depuis meta (SHOW TABLES): {direct_tables}")
        except Exception as e:
            print(f"Impossible d'exécuter SHOW TABLES FROM meta: {e}")

        # Vérifier si on peut accéder directement aux tables
        for table_name in ["maps", "playlists", "map_mode_pairs", "playlist_map_mode_pairs"]:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM meta.{table_name}").fetchone()[0]
                print(f"✅ meta.{table_name} existe ({count} lignes)")
            except Exception as e:
                print(f"❌ meta.{table_name} n'existe pas ou erreur: {e}")

        # Vérifier les données dans match_stats
        print("\n3. Exemple de données dans match_stats")
        print("-" * 60)
        sample = conn.execute(
            "SELECT map_id, map_name, playlist_id, playlist_name, pair_id, pair_name "
            "FROM match_stats "
            "WHERE map_name IS NOT NULL OR playlist_name IS NOT NULL OR pair_name IS NOT NULL "
            "LIMIT 5"
        ).fetchall()

        if not sample:
            print("⚠️  Aucune donnée trouvée dans match_stats")
        else:
            print("Exemples de match_stats:")
            for row in sample:
                print(f"  map_id={row[0]}, map_name={row[1]}")
                print(f"  playlist_id={row[2]}, playlist_name={row[3]}")
                print(f"  pair_id={row[4]}, pair_name={row[5]}")
                print()

        # Tester une jointure manuelle
        print("\n4. Test de jointure manuelle")
        print("-" * 60)
        if "maps" in meta_tables:
            test_query = """
                SELECT
                    match_stats.map_id,
                    match_stats.map_name as map_name_stored,
                    m_meta.public_name as map_name_resolved
                FROM match_stats
                LEFT JOIN meta.maps m_meta ON match_stats.map_id = m_meta.asset_id
                WHERE match_stats.map_id IS NOT NULL
                LIMIT 5
            """
            try:
                results = conn.execute(test_query).fetchall()
                print("Résultats de la jointure maps:")
                for row in results:
                    map_id, stored, resolved = row
                    status = "✅" if resolved and resolved != stored else "❌"
                    print(f"  {status} map_id={map_id}")
                    print(f"     Stored: {stored}")
                    print(f"     Resolved: {resolved}")
                    print()
            except Exception as e:
                print(f"❌ Erreur lors de la jointure: {e}")

        # Tester la méthode _build_metadata_resolution
        print("\n5. Test de _build_metadata_resolution")
        print("-" * 60)
        metadata_joins, map_expr, playlist_expr, pair_expr = repo._build_metadata_resolution(conn)
        print(f"Jointures générées: {metadata_joins}")
        print(f"Expression map_name: {map_expr}")
        print(f"Expression playlist_name: {playlist_expr}")
        print(f"Expression pair_name: {pair_expr}")

        # Tester la requête complète
        print("\n6. Test de la requête complète load_matches")
        print("-" * 60)
        try:
            matches = repo.load_matches(limit=3)
            print(f"✅ Requête réussie, {len(matches)} matchs chargés")
            if matches:
                m = matches[0]
                print("\nPremier match:")
                print(f"  map_name: {m.map_name}")
                print(f"  playlist_name: {m.playlist_name}")
                print(f"  map_mode_pair_name: {m.map_mode_pair_name}")
        except Exception as e:
            print(f"❌ Erreur lors du chargement: {e}")
            import traceback

            traceback.print_exc()

    finally:
        repo.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python diagnose_metadata_resolution.py <gamertag> <xuid>")
        sys.exit(1)

    gamertag = sys.argv[1]
    xuid = sys.argv[2]
    diagnose_metadata_resolution(gamertag, xuid)
