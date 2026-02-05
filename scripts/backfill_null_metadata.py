#!/usr/bin/env python3
"""Backfill: Résout les métadonnées NULL depuis les référentiels.

Ce script met à jour les matchs existants qui ont des métadonnées NULL
en résolvant depuis metadata.duckdb.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import duckdb
from src.data.sync.transformers import create_metadata_resolver


def backfill_match_metadata(
    player_db_path: str,
    metadata_db_path: str | None = None,
    dry_run: bool = False,
    match_id: str | None = None,
) -> None:
    """Met à jour les métadonnées NULL depuis les référentiels.
    
    Args:
        player_db_path: Chemin vers stats.duckdb du joueur
        metadata_db_path: Chemin vers metadata.duckdb (auto-détecté si None)
        dry_run: Si True, affiche seulement ce qui serait fait
        match_id: Si fourni, ne traite que ce match spécifique
    """
    player_db = Path(player_db_path)
    if not player_db.exists():
        print(f"❌ Base de données non trouvée: {player_db}")
        return

    # Auto-détection de metadata.duckdb
    if metadata_db_path is None:
        data_dir = player_db.parent.parent.parent
        metadata_db_path = str(data_dir / "warehouse" / "metadata.duckdb")
    
    metadata_db = Path(metadata_db_path)
    if not metadata_db.exists():
        print(f"⚠️  metadata.duckdb non trouvé: {metadata_db}")
        print("   Les métadonnées ne pourront pas être résolues depuis les référentiels.")
        resolver = None
    else:
        resolver = create_metadata_resolver(metadata_db_path)
        if resolver is None:
            print(f"⚠️  Impossible de créer le resolver pour {metadata_db}")
        else:
            print(f"✅ Resolver créé depuis {metadata_db}")

    # Connexion à la DB joueur
    conn = duckdb.connect(str(player_db), read_only=False)
    
    try:
        # Trouver les matchs avec métadonnées NULL
        if match_id:
            query = """
                SELECT 
                    match_id,
                    start_time,
                    map_id,
                    map_name,
                    playlist_id,
                    playlist_name,
                    pair_id,
                    pair_name,
                    game_variant_id,
                    game_variant_name
                FROM match_stats
                WHERE match_id = ?
            """
            matches = conn.execute(query, [match_id]).fetchall()
        else:
            query = """
                SELECT 
                    match_id,
                    start_time,
                    map_id,
                    map_name,
                    playlist_id,
                    playlist_name,
                    pair_id,
                    pair_name,
                    game_variant_id,
                    game_variant_name
                FROM match_stats
                WHERE map_name IS NULL 
                   OR playlist_name IS NULL 
                   OR pair_name IS NULL
                   OR game_variant_name IS NULL
                ORDER BY start_time DESC
            """
            matches = conn.execute(query).fetchall()
        
        if not matches:
            print("✅ Aucun match avec métadonnées NULL trouvé.")
            return
        
        columns = [
            "match_id", "start_time", "map_id", "map_name",
            "playlist_id", "playlist_name", "pair_id", "pair_name",
            "game_variant_id", "game_variant_name"
        ]
        
        print(f"\n🔍 {len(matches)} match(s) à traiter\n")
        
        updated_count = 0
        
        for row in matches:
            row_dict = {col: row[columns.index(col)] for col in columns}
            match_id_val = row_dict["match_id"]
            
            print(f"Match: {match_id_val}")
            print(f"  Date: {row_dict['start_time']}")
            
            updates = {}
            
            # Résoudre map_name
            if not row_dict["map_name"] and row_dict["map_id"]:
                if resolver:
                    resolved = resolver("map", row_dict["map_id"])
                    if resolved:
                        updates["map_name"] = resolved
                        print(f"  ✅ map_name résolu: {resolved}")
                    else:
                        # Fallback sur l'ID
                        updates["map_name"] = row_dict["map_id"]
                        print(f"  ⚠️  map_name → fallback sur ID: {row_dict['map_id']}")
                else:
                    updates["map_name"] = row_dict["map_id"]
                    print(f"  ⚠️  map_name → fallback sur ID (pas de resolver)")
            
            # Résoudre playlist_name
            if not row_dict["playlist_name"] and row_dict["playlist_id"]:
                if resolver:
                    resolved = resolver("playlist", row_dict["playlist_id"])
                    if resolved:
                        updates["playlist_name"] = resolved
                        print(f"  ✅ playlist_name résolu: {resolved}")
                    else:
                        updates["playlist_name"] = row_dict["playlist_id"]
                        print(f"  ⚠️  playlist_name → fallback sur ID: {row_dict['playlist_id']}")
                else:
                    updates["playlist_name"] = row_dict["playlist_id"]
                    print(f"  ⚠️  playlist_name → fallback sur ID (pas de resolver)")
            
            # Résoudre pair_name
            if not row_dict["pair_name"] and row_dict["pair_id"]:
                if resolver:
                    resolved = resolver("pair", row_dict["pair_id"])
                    if resolved:
                        updates["pair_name"] = resolved
                        print(f"  ✅ pair_name résolu: {resolved}")
                    else:
                        updates["pair_name"] = row_dict["pair_id"]
                        print(f"  ⚠️  pair_name → fallback sur ID: {row_dict['pair_id']}")
                else:
                    updates["pair_name"] = row_dict["pair_id"]
                    print(f"  ⚠️  pair_name → fallback sur ID (pas de resolver)")
            
            # Résoudre game_variant_name
            if not row_dict["game_variant_name"] and row_dict["game_variant_id"]:
                if resolver:
                    resolved = resolver("game_variant", row_dict["game_variant_id"])
                    if resolved:
                        updates["game_variant_name"] = resolved
                        print(f"  ✅ game_variant_name résolu: {resolved}")
                    else:
                        updates["game_variant_name"] = row_dict["game_variant_id"]
                        print(f"  ⚠️  game_variant_name → fallback sur ID: {row_dict['game_variant_id']}")
                else:
                    updates["game_variant_name"] = row_dict["game_variant_id"]
                    print(f"  ⚠️  game_variant_name → fallback sur ID (pas de resolver)")
            
            if updates:
                if dry_run:
                    print(f"  🔄 [DRY RUN] Mise à jour: {updates}")
                else:
                    # Construire la requête UPDATE
                    set_clauses = []
                    params = []
                    for key, value in updates.items():
                        set_clauses.append(f"{key} = ?")
                        params.append(value)
                    
                    params.append(match_id_val)
                    
                    update_query = f"""
                        UPDATE match_stats
                        SET {', '.join(set_clauses)}
                        WHERE match_id = ?
                    """
                    
                    conn.execute(update_query, params)
                    updated_count += 1
                    print(f"  ✅ Mis à jour: {len(updates)} champ(s)")
            else:
                print(f"  ⏭️  Aucune mise à jour nécessaire")
            
            print()
        
        if not dry_run:
            conn.commit()
            print(f"✅ {updated_count} match(s) mis à jour avec succès.")
        else:
            print(f"🔍 [DRY RUN] {updated_count} match(s) seraient mis à jour.")
        
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Backfill des métadonnées NULL depuis les référentiels"
    )
    parser.add_argument(
        "--db",
        required=True,
        help="Chemin vers stats.duckdb du joueur"
    )
    parser.add_argument(
        "--metadata-db",
        help="Chemin vers metadata.duckdb (auto-détecté si non fourni)"
    )
    parser.add_argument(
        "--match-id",
        help="ID d'un match spécifique à traiter"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche seulement ce qui serait fait sans modifier la DB"
    )
    
    args = parser.parse_args()
    
    backfill_match_metadata(
        args.db,
        args.metadata_db,
        dry_run=args.dry_run,
        match_id=args.match_id,
    )
