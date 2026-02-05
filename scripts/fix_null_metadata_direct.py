#!/usr/bin/env python3
"""Corrige les métadonnées NULL - Version qui utilise les imports du projet."""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Maintenant on peut importer duckdb depuis l'environnement du projet
import duckdb

from src.data.sync.transformers import create_metadata_resolver


def fix_match_metadata(player_db: str, match_id: str | None = None) -> None:
    """Corrige les métadonnées NULL pour un match ou tous les matchs."""

    player_path = Path(player_db)
    if not player_path.exists():
        print(f"❌ Base non trouvée: {player_path}")
        return

    # Auto-détection metadata.duckdb
    data_dir = player_path.parent.parent.parent
    metadata_path = data_dir / "warehouse" / "metadata.duckdb"

    conn = duckdb.connect(str(player_path), read_only=False)

    try:
        resolver = None
        if metadata_path.exists():
            resolver = create_metadata_resolver(str(metadata_path))
            if resolver:
                print(f"✅ Resolver créé depuis {metadata_path}")
                # Attacher pour les requêtes SQL directes aussi
            try:
                conn.execute(f"ATTACH '{metadata_path}' AS meta (READ_ONLY)")
            except Exception:
                pass
            else:
                print("⚠️  Resolver non disponible")
        else:
            print(f"⚠️  metadata.duckdb non trouvé: {metadata_path}")

        # Trouver les matchs à corriger
        if match_id:
            query = "SELECT match_id, map_id, map_name, playlist_id, playlist_name, pair_id, pair_name, game_variant_id, game_variant_name FROM match_stats WHERE match_id = ?"
            matches = conn.execute(query, [match_id]).fetchall()
        else:
            query = "SELECT match_id, map_id, map_name, playlist_id, playlist_name, pair_id, pair_name, game_variant_id, game_variant_name FROM match_stats WHERE map_name IS NULL OR playlist_name IS NULL OR pair_name IS NULL OR game_variant_name IS NULL"
            matches = conn.execute(query).fetchall()

        if not matches:
            print("✅ Aucun match à corriger.")
            return

        print(f"\n🔍 {len(matches)} match(s) à corriger\n")

        updated = 0
        for row in matches:
            mid, map_id, map_name, pl_id, pl_name, pair_id, pair_name, gv_id, gv_name = row

            updates = {}

            # Résoudre map_name
            if not map_name and map_id:
                if resolver:
                    resolved = resolver("map", map_id)
                    updates["map_name"] = resolved or map_id
                else:
                    updates["map_name"] = map_id

            # Résoudre playlist_name
            if not pl_name and pl_id:
                if resolver:
                    resolved = resolver("playlist", pl_id)
                    updates["playlist_name"] = resolved or pl_id
                else:
                    updates["playlist_name"] = pl_id

            # Résoudre pair_name
            if not pair_name and pair_id:
                if resolver:
                    resolved = resolver("pair", pair_id)
                    updates["pair_name"] = resolved or pair_id
                else:
                    updates["pair_name"] = pair_id

            # Résoudre game_variant_name
            if not gv_name and gv_id:
                if resolver:
                    resolved = resolver("game_variant", gv_id)
                    updates["game_variant_name"] = resolved or gv_id
                else:
                    updates["game_variant_name"] = gv_id

            if updates:
                set_clauses = [f"{k} = ?" for k in updates]
                params = list(updates.values()) + [mid]

                update_sql = f"""
                    UPDATE match_stats
                    SET {', '.join(set_clauses)}
                    WHERE match_id = ?
                """

                conn.execute(update_sql, params)
                updated += 1

                print(f"✅ {mid[:8]}... mis à jour: {list(updates.keys())}")

        conn.commit()
        print(f"\n✅ {updated} match(s) corrigé(s)")

    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="Chemin vers stats.duckdb")
    parser.add_argument("--match-id", help="ID d'un match spécifique")

    args = parser.parse_args()

    fix_match_metadata(args.db, args.match_id)
