#!/usr/bin/env python3
"""Script Python pour corriger les métadonnées NULL - Version simplifiée qui fonctionne."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import duckdb
except ImportError:
    print("ERREUR: DuckDB non installé")
    sys.exit(1)


def fix_null_metadata(
    player_db_path: str,
    metadata_db_path: str | None = None,
    match_id: str | None = None,
) -> None:
    """Corrige les métadonnées NULL directement via SQL."""

    player_db = Path(player_db_path)
    if not player_db.exists():
        print(f"❌ Base non trouvée: {player_db}")
        return

    # Auto-détection metadata.duckdb
    if metadata_db_path is None:
        data_dir = player_db.parent.parent.parent
        metadata_db_path = str(data_dir / "warehouse" / "metadata.duckdb")

    metadata_db = Path(metadata_db_path)
    has_metadata = metadata_db.exists()

    conn = duckdb.connect(str(player_db), read_only=False)

    try:
        # Attacher metadata.duckdb si disponible
        if has_metadata:
            try:
                conn.execute(f"ATTACH '{metadata_db_path}' AS meta (READ_ONLY)")
                print(f"✅ metadata.duckdb attaché: {metadata_db_path}")
            except Exception as e:
                print(f"⚠️  Impossible d'attacher metadata.duckdb: {e}")
                has_metadata = False

        # Construire le WHERE pour un match spécifique ou tous
        where_clause = "WHERE match_id = ?" if match_id else ""
        params = [match_id] if match_id else []

        # 1. Résoudre map_name
        if has_metadata:
            conn.execute(
                f"""
                UPDATE match_stats
                SET map_name = (
                    SELECT public_name
                    FROM meta.maps
                    WHERE meta.maps.asset_id = match_stats.map_id
                    LIMIT 1
                )
                {where_clause}
                AND map_name IS NULL
                AND map_id IS NOT NULL
                AND EXISTS (SELECT 1 FROM meta.maps WHERE meta.maps.asset_id = match_stats.map_id)
            """,
                params if match_id else [],
            )

        # Fallback sur map_id
        conn.execute(
            f"""
            UPDATE match_stats
            SET map_name = map_id
            {where_clause}
            AND map_name IS NULL
            AND map_id IS NOT NULL
        """,
            params if match_id else [],
        )

        # 2. Résoudre playlist_name
        if has_metadata:
            conn.execute(
                f"""
                UPDATE match_stats
                SET playlist_name = (
                    SELECT public_name
                    FROM meta.playlists
                    WHERE meta.playlists.asset_id = match_stats.playlist_id
                    LIMIT 1
                )
                {where_clause}
                AND playlist_name IS NULL
                AND playlist_id IS NOT NULL
                AND EXISTS (SELECT 1 FROM meta.playlists WHERE meta.playlists.asset_id = match_stats.playlist_id)
            """,
                params if match_id else [],
            )

        # Fallback sur playlist_id
        conn.execute(
            f"""
            UPDATE match_stats
            SET playlist_name = playlist_id
            {where_clause}
            AND playlist_name IS NULL
            AND playlist_id IS NOT NULL
        """,
            params if match_id else [],
        )

        # 3. Résoudre pair_name (essayer map_mode_pairs d'abord)
        if has_metadata:
            # Vérifier quelle table existe
            tables_result = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'meta'"
            ).fetchall()
            tables = {row[0] for row in tables_result}

            if "map_mode_pairs" in tables:
                conn.execute(
                    f"""
                    UPDATE match_stats
                    SET pair_name = (
                        SELECT public_name
                        FROM meta.map_mode_pairs
                        WHERE meta.map_mode_pairs.asset_id = match_stats.pair_id
                        LIMIT 1
                    )
                    {where_clause}
                    AND pair_name IS NULL
                    AND pair_id IS NOT NULL
                    AND EXISTS (SELECT 1 FROM meta.map_mode_pairs WHERE meta.map_mode_pairs.asset_id = match_stats.pair_id)
                """,
                    params if match_id else [],
                )
            elif "playlist_map_mode_pairs" in tables:
                conn.execute(
                    f"""
                    UPDATE match_stats
                    SET pair_name = (
                        SELECT public_name
                        FROM meta.playlist_map_mode_pairs
                        WHERE meta.playlist_map_mode_pairs.asset_id = match_stats.pair_id
                        LIMIT 1
                    )
                    {where_clause}
                    AND pair_name IS NULL
                    AND pair_id IS NOT NULL
                    AND EXISTS (SELECT 1 FROM meta.playlist_map_mode_pairs
                                WHERE meta.playlist_map_mode_pairs.asset_id = match_stats.pair_id)
                """,
                    params if match_id else [],
                )

        # Fallback sur pair_id
        conn.execute(
            f"""
            UPDATE match_stats
            SET pair_name = pair_id
            {where_clause}
            AND pair_name IS NULL
            AND pair_id IS NOT NULL
        """,
            params if match_id else [],
        )

        # 4. Résoudre game_variant_name
        if has_metadata:
            conn.execute(
                f"""
                UPDATE match_stats
                SET game_variant_name = (
                    SELECT public_name
                    FROM meta.game_variants
                    WHERE meta.game_variants.asset_id = match_stats.game_variant_id
                    LIMIT 1
                )
                {where_clause}
                AND game_variant_name IS NULL
                AND game_variant_id IS NOT NULL
                AND EXISTS (SELECT 1 FROM meta.game_variants
                            WHERE meta.game_variants.asset_id = match_stats.game_variant_id)
            """,
                params if match_id else [],
            )

        # Fallback sur game_variant_id
        conn.execute(
            f"""
            UPDATE match_stats
            SET game_variant_name = game_variant_id
            {where_clause}
            AND game_variant_name IS NULL
            AND game_variant_id IS NOT NULL
        """,
            params if match_id else [],
        )

        conn.commit()

        # Vérifier le résultat
        if match_id:
            result = conn.execute(
                "SELECT map_name, playlist_name, pair_name FROM match_stats WHERE match_id = ?",
                [match_id],
            ).fetchone()
            if result:
                print(f"\n✅ Match {match_id} mis à jour:")
                print(f"   map_name: {result[0]}")
                print(f"   playlist_name: {result[1]}")
                print(f"   pair_name: {result[2]}")
        else:
            count = conn.execute(
                "SELECT COUNT(*) FROM match_stats WHERE map_name IS NULL OR playlist_name IS NULL OR pair_name IS NULL"
            ).fetchone()[0]
            print(f"\n✅ Mise à jour terminée. {count} match(s) avec métadonnées NULL restant(s).")

    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Corrige les métadonnées NULL")
    parser.add_argument("--db", required=True, help="Chemin vers stats.duckdb")
    parser.add_argument("--metadata-db", help="Chemin vers metadata.duckdb (auto-détecté)")
    parser.add_argument("--match-id", help="ID d'un match spécifique")

    args = parser.parse_args()

    fix_null_metadata(args.db, args.metadata_db, args.match_id)
