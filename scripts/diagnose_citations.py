#!/usr/bin/env python3
"""Diagnostic des citations DuckDB.

Vérifie la cohérence et l'état des tables ``citation_mappings`` et
``match_citations`` pour chaque joueur.

Usage::

    python scripts/diagnose_citations.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb


def main() -> int:
    """Point d'entrée principal."""
    root = Path(__file__).resolve().parent.parent
    meta_path = root / "data" / "warehouse" / "metadata.duckdb"
    profiles_path = root / "db_profiles.json"

    print("=" * 70)
    print("🔍 Diagnostic Citations DuckDB")
    print("=" * 70)

    # 1) Vérifier metadata.duckdb
    print("\n📦 metadata.duckdb")
    if not meta_path.exists():
        print(f"   ❌ Fichier introuvable : {meta_path}")
        print("   → Exécuter : python scripts/create_citation_mappings_table.py")
        return 1

    conn = duckdb.connect(str(meta_path), read_only=True)
    try:
        exists = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = 'citation_mappings'"
        ).fetchone()[0]
        if not exists:
            print("   ❌ Table citation_mappings absente")
            print("   → Exécuter : python scripts/create_citation_mappings_table.py")
            return 1

        total = conn.execute("SELECT COUNT(*) FROM citation_mappings").fetchone()[0]
        print(f"   ✅ {total} citations dans citation_mappings")

        by_type = conn.execute(
            "SELECT mapping_type, COUNT(*) FROM citation_mappings "
            "GROUP BY mapping_type ORDER BY COUNT(*) DESC"
        ).fetchall()
        for mtype, count in by_type:
            print(f"      {mtype:10s} : {count}")
    finally:
        conn.close()

    # 2) Profils joueurs
    if not profiles_path.exists():
        print(f"\n⚠️  db_profiles.json introuvable : {profiles_path}")
        return 0

    with open(profiles_path, encoding="utf-8") as f:
        profiles = json.load(f)

    print(f"\n👤 {len(profiles)} profil(s) joueur(s)")

    total_matches_all = 0
    total_citations_all = 0

    for profile in profiles:
        gamertag = profile.get("gamertag", "???")
        db_path = root / "data" / "players" / gamertag / "stats.duckdb"

        if not db_path.exists():
            print(f"\n   [{gamertag}] ❌ DB introuvable : {db_path}")
            continue

        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            # Nombre de matchs
            n_matches = conn.execute("SELECT COUNT(*) FROM match_stats").fetchone()[0]

            # Table match_citations existe ?
            has_table = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'match_citations'"
            ).fetchone()[0]

            if not has_table:
                print(f"\n   [{gamertag}] ⚠️  {n_matches} matchs, pas de table match_citations")
                print("      → Exécuter : python scripts/create_match_citations_table.py")
                continue

            # Stats match_citations
            n_rows = conn.execute("SELECT COUNT(*) FROM match_citations").fetchone()[0]
            n_matches_with = conn.execute(
                "SELECT COUNT(DISTINCT match_id) FROM match_citations"
            ).fetchone()[0]
            n_matches_without = n_matches - n_matches_with

            total_matches_all += n_matches
            total_citations_all += n_rows

            status = "✅" if n_matches_without == 0 else "⚠️"
            print(f"\n   [{gamertag}] {status} {n_matches} matchs")
            print(f"      Matchs avec citations : {n_matches_with}/{n_matches}")
            if n_matches_without > 0:
                print(f"      Matchs sans citations : {n_matches_without}")
                print(
                    f"      → Exécuter : python scripts/backfill_data.py --player {gamertag} --citations"
                )
            print(f"      Lignes match_citations : {n_rows}")

            # Top citations
            top = conn.execute(
                "SELECT citation_name_norm, SUM(value) as total "
                "FROM match_citations GROUP BY citation_name_norm "
                "ORDER BY total DESC LIMIT 5"
            ).fetchall()
            if top:
                print("      Top 5 citations :")
                for name, val in top:
                    print(f"         {name:30s} : {val:>6}")
        finally:
            conn.close()

    print(f"\n{'=' * 70}")
    print(f"📊 Total : {total_matches_all} matchs, {total_citations_all} lignes match_citations")
    print(f"{'=' * 70}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
