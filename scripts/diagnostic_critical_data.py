#!/usr/bin/env python3
"""Script de diagnostic pour CRITICAL_DATA_MISSING.

Exécute les requêtes SQL listées dans .ai/explore/CRITICAL_DATA_MISSING_EXPLORATION.md
"""

from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLAYER_DB = PROJECT_ROOT / "data" / "players" / "XxDaemonGamerxX" / "stats.duckdb"
METADATA_DB = PROJECT_ROOT / "data" / "warehouse" / "metadata.duckdb"


def main() -> None:
    if not PLAYER_DB.exists():
        print(f"❌ Base joueur non trouvée: {PLAYER_DB}")
        return

    print("=" * 60)
    print("DIAGNOSTIC CRITICAL_DATA_MISSING")
    print("=" * 60)

    conn = duckdb.connect(str(PLAYER_DB), read_only=True)

    # Lister les tables
    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    print(f"\n📋 Tables dans stats.duckdb: {[t[0] for t in tables]}")

    if ("match_stats",) not in tables:
        print("❌ Table match_stats absente!")
        conn.close()
        return

    # Requête 1: Compteurs match_stats
    print("\n--- Requête 1: Compteurs noms dans match_stats ---")
    try:
        r = conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(playlist_name) as avec_playlist_name,
                COUNT(map_name) as avec_map_name,
                COUNT(pair_name) as avec_pair_name,
                COUNT(game_variant_name) as avec_game_variant_name
            FROM match_stats
        """).fetchone()
        print(f"  Total matchs: {r[0]}")
        print(f"  Avec playlist_name: {r[1]}")
        print(f"  Avec map_name: {r[2]}")
        print(f"  Avec pair_name: {r[3]}")
        print(f"  Avec game_variant_name: {r[4]}")
    except Exception as e:
        print(f"  Erreur: {e}")

    # Requête 2: Matchs avec noms NULL
    print("\n--- Requête 2: Matchs avec noms NULL ---")
    try:
        rows = conn.execute("""
            SELECT match_id, playlist_name, map_name, pair_name
            FROM match_stats
            WHERE playlist_name IS NULL OR map_name IS NULL OR pair_name IS NULL
            ORDER BY start_time DESC NULLS LAST
            LIMIT 5
        """).fetchall()
        for row in rows:
            print(f"  {row[0][:20]}... | playlist={row[1]} | map={row[2]} | pair={row[3]}")
        if not rows:
            print("  (aucun match avec noms NULL)")
    except Exception as e:
        print(f"  Erreur: {e}")

    # Requête 3: Exemples de noms (5 derniers matchs)
    print("\n--- Requête 3: Exemples noms (5 derniers matchs) ---")
    try:
        rows = conn.execute("""
            SELECT match_id, playlist_name, map_name, pair_name, game_variant_name
            FROM match_stats
            ORDER BY start_time DESC NULLS LAST
            LIMIT 5
        """).fetchall()
        for row in rows:
            print(f"  playlist={row[1]!r} | map={row[2]!r} | pair={row[3]!r}")
    except Exception as e:
        print(f"  Erreur: {e}")

    # Requête 4: player_match_stats - kills/deaths/assists expected
    print("\n--- Requête 4: Valeurs attendues (player_match_stats) ---")
    if ("player_match_stats",) in tables:
        try:
            r = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(kills_expected) as avec_kills_expected,
                    COUNT(deaths_expected) as avec_deaths_expected,
                    COUNT(assists_expected) as avec_assists_expected
                FROM player_match_stats
            """).fetchone()
            print(
                f"  Total: {r[0]} | kills_expected: {r[1]} | deaths_expected: {r[2]} | assists_expected: {r[3]}"
            )
        except Exception as e:
            print(f"  Erreur: {e}")
    else:
        print("  Table player_match_stats absente")

    # Requête 5: xuid_aliases
    print("\n--- Requête 5: Aliases (xuid_aliases) ---")
    if ("xuid_aliases",) in tables:
        try:
            count = conn.execute("SELECT COUNT(*) FROM xuid_aliases").fetchone()[0]
            print(f"  Total aliases: {count}")
            rows = conn.execute(
                "SELECT xuid, gamertag, last_seen FROM xuid_aliases ORDER BY last_seen DESC LIMIT 3"
            ).fetchall()
            for row in rows:
                print(f"    {row[1]} (xuid={row[0][:12]}...)")
        except Exception as e:
            print(f"  Erreur: {e}")
    else:
        print("  Table xuid_aliases absente")

    # Requête 6: highlight_events - gamertags
    print("\n--- Requête 6: highlight_events (gamertags) ---")
    if ("highlight_events",) in tables:
        try:
            r = conn.execute("SELECT COUNT(*), COUNT(gamertag) FROM highlight_events").fetchone()
            print(f"  Total events: {r[0]} | Avec gamertag: {r[1]}")
        except Exception as e:
            print(f"  Erreur: {e}")
    else:
        print("  Table highlight_events absente")

    # Metadata.duckdb
    print("\n--- metadata.duckdb ---")
    if METADATA_DB.exists():
        print(f"  ✅ Trouvé: {METADATA_DB}")
        try:
            meta = duckdb.connect(str(METADATA_DB), read_only=True)
            meta_tables = meta.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
            print(f"  Tables: {[t[0] for t in meta_tables]}")
            for t in meta_tables:
                count = meta.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
                print(f"    {t[0]}: {count} lignes")
            meta.close()
        except Exception as e:
            print(f"  Erreur: {e}")
    else:
        print(f"  ❌ NON TROUVÉ: {METADATA_DB}")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
