"""Script à exécuter depuis Streamlit pour corriger les métadonnées NULL.

Usage dans Streamlit:
    import streamlit as st
    exec(open('scripts/fix_null_metadata_streamlit.py').read())
"""

from pathlib import Path

import duckdb

base_path = Path(__file__).parent.parent

# Pour JGtm
jgtm_db = base_path / "data" / "players" / "JGtm" / "stats.duckdb"
if jgtm_db.exists():
    print("\n🔧 Correction pour JGtm...")
    conn = duckdb.connect(str(jgtm_db), read_only=False)
    try:
        conn.execute("""
            UPDATE match_stats
            SET
                map_name = COALESCE(map_name, map_id),
                playlist_name = COALESCE(playlist_name, playlist_id),
                pair_name = COALESCE(pair_name, pair_id),
                game_variant_name = COALESCE(game_variant_name, game_variant_id)
            WHERE map_name IS NULL
               OR playlist_name IS NULL
               OR pair_name IS NULL
               OR game_variant_name IS NULL
        """)
        conn.commit()

        recent = conn.execute("""
            SELECT match_id, start_time, map_name, playlist_name, pair_name
            FROM match_stats
            ORDER BY start_time DESC
            LIMIT 5
        """).fetchall()

        print("✅ Matchs corrigés pour JGtm")
        print("\n📊 5 matchs les plus récents:")
        for row in recent:
            print(
                f"   {row[1]} | Map: {row[2] or 'N/A'} | Playlist: {row[3] or 'N/A'} | Mode: {row[4] or 'N/A'}"
            )
    finally:
        conn.close()

# Pour Chocoboflor
choco_db = base_path / "data" / "players" / "Chocoboflor" / "stats.duckdb"
if choco_db.exists():
    print("\n🔧 Correction pour Chocoboflor...")
    conn = duckdb.connect(str(choco_db), read_only=False)
    try:
        # Match spécifique
        conn.execute("""
            UPDATE match_stats
            SET
                map_name = COALESCE(map_name, map_id),
                playlist_name = COALESCE(playlist_name, playlist_id),
                pair_name = COALESCE(pair_name, pair_id),
                game_variant_name = COALESCE(game_variant_name, game_variant_id)
            WHERE match_id = '410f1c01-aca6-4567-9df5-9b16bd550cb2'
        """)
        conn.commit()

        # Tous les autres
        conn.execute("""
            UPDATE match_stats
            SET
                map_name = COALESCE(map_name, map_id),
                playlist_name = COALESCE(playlist_name, playlist_id),
                pair_name = COALESCE(pair_name, pair_id),
                game_variant_name = COALESCE(game_variant_name, game_variant_id)
            WHERE map_name IS NULL
               OR playlist_name IS NULL
               OR pair_name IS NULL
               OR game_variant_name IS NULL
        """)
        conn.commit()

        match = conn.execute("""
            SELECT match_id, start_time, map_name, playlist_name, pair_name
            FROM match_stats
            WHERE match_id = '410f1c01-aca6-4567-9df5-9b16bd550cb2'
        """).fetchone()

        print("✅ Matchs corrigés pour Chocoboflor")
        if match:
            print("\n📊 Match spécifique:")
            print(
                f"   {match[1]} | Map: {match[2] or 'N/A'} | Playlist: {match[3] or 'N/A'} | Mode: {match[4] or 'N/A'}"
            )
    finally:
        conn.close()

print("\n✅ Corrections terminées! Rafraîchissez l'interface.")
