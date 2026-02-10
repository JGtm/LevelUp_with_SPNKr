#!/usr/bin/env python3
"""Script de migration pour corriger le schéma de highlight_events.

Corrige la colonne id pour utiliser GENERATED ALWAYS AS IDENTITY.
"""

import argparse
import sys
from pathlib import Path

# Fix encoding pour Windows
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import duckdb


def migrate_highlight_events_schema(db_path: str, dry_run: bool = False) -> bool:
    """Migre le schéma de highlight_events pour utiliser IDENTITY."""
    conn = duckdb.connect(str(db_path), read_only=False)

    try:
        # Vérifier si la table existe
        table_check = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_name = 'highlight_events'"
        ).fetchone()

        if not table_check:
            print("✅ La table highlight_events n'existe pas encore, pas de migration nécessaire")
            return True

        # Compter les événements existants
        count = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
        print(f"📊 {count} événements existants dans highlight_events")

        if count > 0:
            print("⚠️  La table contient déjà des données.")
            print("   Pour migrer, il faut recréer la table avec le bon schéma.")
            print("   Les données existantes seront préservées.")

        if dry_run:
            print("\n🔍 DRY RUN - Aucune modification ne sera effectuée")
            return True

        # Sauvegarder les données existantes
        if count > 0:
            print("\n💾 Sauvegarde des données existantes...")
            existing_data = conn.execute(
                """
                SELECT match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json
                FROM highlight_events
                ORDER BY match_id, time_ms
                """
            ).fetchall()

        # Supprimer la table et la recréer avec le bon schéma
        print("\n🔄 Recréation de la table avec le schéma corrigé...")
        conn.execute("DROP TABLE IF EXISTS highlight_events")
        conn.execute("DROP INDEX IF EXISTS idx_highlight_match")

        # Créer la séquence d'abord
        conn.execute("CREATE SEQUENCE IF NOT EXISTS highlight_events_id_seq START 1")

        # Recréer avec séquence
        conn.execute("""
            CREATE TABLE highlight_events (
                id INTEGER PRIMARY KEY DEFAULT nextval('highlight_events_id_seq'),
                match_id VARCHAR NOT NULL,
                event_type VARCHAR NOT NULL,
                time_ms INTEGER,
                xuid VARCHAR,
                gamertag VARCHAR,
                type_hint INTEGER,
                raw_json VARCHAR
            )
        """)
        conn.execute("CREATE INDEX idx_highlight_match ON highlight_events(match_id)")

        # Restaurer les données
        if count > 0:
            print(f"📥 Restauration de {len(existing_data)} événements...")
            for row in existing_data:
                conn.execute(
                    """
                    INSERT INTO highlight_events (
                        match_id, event_type, time_ms, xuid, gamertag, type_hint, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )

        conn.commit()
        print("✅ Migration terminée avec succès")

        # Vérification
        new_count = conn.execute("SELECT COUNT(*) FROM highlight_events").fetchone()[0]
        print(f"✅ {new_count} événements dans la table après migration")

        return True

    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        conn.close()


def main() -> int:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Migre le schéma de highlight_events pour utiliser IDENTITY"
    )
    parser.add_argument(
        "--db-path",
        required=True,
        help="Chemin vers la DB DuckDB v4",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche ce qui serait fait sans effectuer les modifications",
    )

    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"❌ Erreur: La DB {db_path} n'existe pas", file=sys.stderr)
        return 1

    success = migrate_highlight_events_schema(str(db_path), dry_run=args.dry_run)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
