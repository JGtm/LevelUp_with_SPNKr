#!/usr/bin/env python3
"""Corrige les métadonnées NULL pour TOUS les joueurs.

Ce script :
1. Trouve toutes les bases joueurs dans data/players/
2. Corrige tous les matchs avec métadonnées NULL
3. Utilise un fallback sur les IDs si les noms sont absents

La root cause est corrigée dans transform_match_stats() qui utilise maintenant
automatiquement le resolver pour les nouveaux matchs synchronisés.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import duckdb
except ImportError:
    print("ERREUR: DuckDB non installé. Exécutez: pip install duckdb")
    sys.exit(1)


def find_all_player_dbs() -> list[Path]:
    """Trouve toutes les bases joueurs dans data/players/."""
    data_dir = Path(__file__).parent.parent / "data" / "players"
    if not data_dir.exists():
        return []

    dbs = []
    for player_dir in data_dir.iterdir():
        if player_dir.is_dir():
            db_path = player_dir / "stats.duckdb"
            if db_path.exists():
                dbs.append(db_path)

    return dbs


def fix_null_metadata_for_player(db_path: Path) -> dict[str, int]:
    """Corrige les métadonnées NULL pour un joueur.

    Returns:
        Dict avec 'updated' (nombre de matchs mis à jour) et 'total_null' (total avec NULL avant correction).
    """
    conn = duckdb.connect(str(db_path), read_only=False)

    try:
        # Compter les matchs avec NULL avant correction
        result = conn.execute("""
            SELECT COUNT(*)
            FROM match_stats
            WHERE map_name IS NULL
               OR playlist_name IS NULL
               OR pair_name IS NULL
               OR game_variant_name IS NULL
        """).fetchone()
        total_null = result[0] if result else 0

        if total_null == 0:
            return {"updated": 0, "total_null": 0}

        # Corriger avec fallback sur les IDs
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

        return {"updated": total_null, "total_null": total_null}

    finally:
        conn.close()


def main():
    """Corrige les métadonnées NULL pour tous les joueurs."""
    print("=" * 80)
    print("CORRECTION DES MÉTADONNÉES NULL - TOUS LES JOUEURS")
    print("=" * 80)
    print()

    player_dbs = find_all_player_dbs()

    if not player_dbs:
        print("❌ Aucune base joueur trouvée dans data/players/")
        return

    print(f"🔍 {len(player_dbs)} joueur(s) trouvé(s)\n")

    total_updated = 0
    total_players = 0

    for db_path in sorted(player_dbs):
        gamertag = db_path.parent.name
        print(f"📊 Traitement de {gamertag}...")

        try:
            result = fix_null_metadata_for_player(db_path)

            if result["updated"] > 0:
                print(f"   ✅ {result['updated']} match(s) corrigé(s)")
                total_updated += result["updated"]
                total_players += 1
            else:
                print("   ⏭️  Aucun match à corriger")
        except Exception as e:
            print(f"   ❌ Erreur: {e}")

    print()
    print("=" * 80)
    print("✅ CORRECTION TERMINÉE")
    print(f"   - {total_players} joueur(s) avec matchs corrigés")
    print(f"   - {total_updated} match(s) corrigé(s) au total")
    print()
    print("📝 NOTE: La root cause est corrigée dans le code.")
    print("   Les nouveaux matchs synchronisés seront automatiquement résolus.")
    print("=" * 80)


if __name__ == "__main__":
    main()
