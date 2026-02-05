#!/usr/bin/env python3
"""Diagnostic: Pourquoi certains matchs ont map_name/playlist_name/pair_name = NULL.

Ce script vérifie directement dans la DB DuckDB v4 pourquoi certains matchs récents
ont des valeurs NULL pour les métadonnées.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import duckdb
except ImportError:
    print("ERREUR: DuckDB non installé. Exécutez: pip install duckdb")
    sys.exit(1)


def check_refdata_resolution(
    metadata_db_path: str | None,
    map_id: str | None,
    playlist_id: str | None,
    pair_id: str | None,
) -> dict[str, str | None]:
    """Vérifie si on peut résoudre les noms depuis les référentiels.
    
    Returns:
        Dict avec 'map_name', 'playlist_name', 'pair_name' résolus depuis refdata.
    """
    result = {"map_name": None, "playlist_name": None, "pair_name": None}
    
    if not metadata_db_path or not Path(metadata_db_path).exists():
        return result
    
    try:
        ref_conn = duckdb.connect(metadata_db_path, read_only=True)
        
        try:
            # Résoudre map_name
            if map_id:
                map_result = ref_conn.execute(
                    "SELECT public_name FROM maps WHERE asset_id = ? LIMIT 1",
                    [map_id]
                ).fetchone()
                if map_result:
                    result["map_name"] = map_result[0]
            
            # Résoudre playlist_name
            if playlist_id:
                playlist_result = ref_conn.execute(
                    "SELECT public_name FROM playlists WHERE asset_id = ? LIMIT 1",
                    [playlist_id]
                ).fetchone()
                if playlist_result:
                    result["playlist_name"] = playlist_result[0]
            
            # Résoudre pair_name
            if pair_id:
                pair_result = ref_conn.execute(
                    "SELECT public_name FROM playlist_map_mode_pairs WHERE asset_id = ? LIMIT 1",
                    [pair_id]
                ).fetchone()
                if pair_result:
                    result["pair_name"] = pair_result[0]
        
        finally:
            ref_conn.close()
    
    except Exception as e:
        print(f"  ⚠️  Erreur lors de la résolution depuis refdata: {e}")
    
    return result


def diagnose_null_metadata(
    db_path: str,
    limit: int = 10,
    metadata_db_path: str | None = None,
) -> None:
    """Diagnostique pourquoi certains matchs ont des métadonnées NULL.
    
    Args:
        db_path: Chemin vers stats.duckdb
        limit: Nombre de matchs récents à vérifier
        metadata_db_path: Chemin optionnel vers metadata.duckdb pour vérifier la résolution
    """
    conn = duckdb.connect(db_path, read_only=True)
    
    try:
        # Trouver les matchs récents avec valeurs NULL
        print("=" * 80)
        print("DIAGNOSTIC: Matchs avec métadonnées NULL")
        print("=" * 80)
        
        query = f"""
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
        ORDER BY start_time DESC
        LIMIT {limit}
        """
        
        result = conn.execute(query).fetchall()
        columns = [desc[0] for desc in conn.execute(query).description]
        
        if not result:
            print("✅ Aucun match avec métadonnées NULL trouvé.")
            return
        
        print(f"\n🔍 {len(result)} matchs récents avec métadonnées NULL trouvés:\n")
        
        for row in result:
            row_dict = {col: row[columns.index(col)] for col in columns}
            print(f"Match ID: {row_dict['match_id']}")
            print(f"  Date: {row_dict['start_time']}")
            print(f"  map_id: {row_dict['map_id']}")
            print(f"  map_name: {row_dict['map_name']}")
            print(f"  playlist_id: {row_dict['playlist_id']}")
            print(f"  playlist_name: {row_dict['playlist_name']}")
            print(f"  pair_id: {row_dict['pair_id']}")
            print(f"  pair_name: {row_dict['pair_name']}")
            print(f"  game_variant_id: {row_dict['game_variant_id']}")
            print(f"  game_variant_name: {row_dict['game_variant_name']}")
            
            # Vérifier si on peut résoudre depuis les référentiels
            if metadata_db_path:
                resolved = check_refdata_resolution(
                    metadata_db_path,
                    row_dict['map_id'],
                    row_dict['playlist_id'],
                    row_dict['pair_id'],
                )
                if any(resolved.values()):
                    print(f"  📋 Résolution depuis refdata:")
                    if resolved['map_name']:
                        print(f"    → map_name: {resolved['map_name']}")
                    if resolved['playlist_name']:
                        print(f"    → playlist_name: {resolved['playlist_name']}")
                    if resolved['pair_name']:
                        print(f"    → pair_name: {resolved['pair_name']}")
                else:
                    print(f"  ❌ Aucune résolution possible depuis refdata")
            
            print()
        
        # Vérifier si ces matchs ont des IDs mais pas de noms
        print("\n" + "=" * 80)
        print("ANALYSE: IDs présents mais noms manquants")
        print("=" * 80)
        
        query2 = f"""
        SELECT 
            COUNT(*) as total,
            COUNT(map_id) as has_map_id,
            COUNT(map_name) as has_map_name,
            COUNT(playlist_id) as has_playlist_id,
            COUNT(playlist_name) as has_playlist_name,
            COUNT(pair_id) as has_pair_id,
            COUNT(pair_name) as has_pair_name
        FROM match_stats
        WHERE map_name IS NULL 
           OR playlist_name IS NULL 
           OR pair_name IS NULL
        """
        
        stats = conn.execute(query2).fetchone()
        if stats:
            print(f"Total matchs avec NULL: {stats[0]}")
            print(f"  - map_id présent: {stats[1]}/{stats[0]}")
            print(f"  - map_name présent: {stats[2]}/{stats[0]}")
            print(f"  - playlist_id présent: {stats[3]}/{stats[0]}")
            print(f"  - playlist_name présent: {stats[4]}/{stats[0]}")
            print(f"  - pair_id présent: {stats[5]}/{stats[0]}")
            print(f"  - pair_name présent: {stats[6]}/{stats[0]}")
        
        # Vérifier les matchs les plus récents pour comparaison
        print("\n" + "=" * 80)
        print("COMPARAISON: 5 matchs les plus récents (tous)")
        print("=" * 80)
        
        query3 = """
        SELECT 
            match_id,
            start_time,
            map_id,
            map_name,
            playlist_id,
            playlist_name,
            pair_id,
            pair_name
        FROM match_stats
        ORDER BY start_time DESC
        LIMIT 5
        """
        
        recent = conn.execute(query3).fetchall()
        cols = [desc[0] for desc in conn.execute(query3).description]
        
        for row in recent:
            row_dict = {col: row[cols.index(col)] for col in cols}
            nulls = []
            if row_dict['map_name'] is None:
                nulls.append("map_name")
            if row_dict['playlist_name'] is None:
                nulls.append("playlist_name")
            if row_dict['pair_name'] is None:
                nulls.append("pair_name")
            
            status = "❌ NULL" if nulls else "✅ OK"
            print(f"{status} {row_dict['start_time']} | Match: {row_dict['match_id'][:8]}...")
            if nulls:
                print(f"  NULL: {', '.join(nulls)}")
                print(f"  IDs présents: map_id={row_dict['map_id'] is not None}, "
                      f"playlist_id={row_dict['playlist_id'] is not None}, "
                      f"pair_id={row_dict['pair_id'] is not None}")
        
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnostique les matchs avec métadonnées NULL")
    parser.add_argument("--db", required=True, help="Chemin vers stats.duckdb")
    parser.add_argument("--limit", type=int, default=10, help="Nombre de matchs à vérifier")
    parser.add_argument("--metadata-db", help="Chemin optionnel vers metadata.duckdb pour vérifier la résolution")
    
    args = parser.parse_args()
    
    if not Path(args.db).exists():
        print(f"ERREUR: Le fichier {args.db} n'existe pas.")
        sys.exit(1)
    
    diagnose_null_metadata(args.db, args.limit, args.metadata_db)
