#!/usr/bin/env python3
"""Fusionne les assets (Maps, PlaylistMapModePairs) des bases sources vers la base unifiée.

Ce script résout le problème des assets non résolus après fusion multi-DB.
Il lit les tables d'assets de chaque base source et les insère dans halo_unified.db
en évitant les doublons (basé sur AssetId).

Usage:
    python scripts/merge_assets_to_unified.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def get_asset_ids_from_table(con: sqlite3.Connection, table: str) -> dict[str, str]:
    """Récupère tous les AssetId -> ResponseBody d'une table."""
    cur = con.cursor()
    cur.execute(f"SELECT ResponseBody FROM {table}")
    assets = {}
    for row in cur.fetchall():
        data = json.loads(row[0])
        asset_id = data.get("AssetId")
        if asset_id:
            assets[asset_id] = row[0]
    return assets


def merge_assets(
    unified_path: Path,
    source_paths: list[Path],
    table: str,
) -> tuple[int, int]:
    """Fusionne les assets d'une table depuis les sources vers la base unifiée.

    Returns:
        Tuple (nouveaux assets ajoutés, total assets après fusion)
    """
    # Ouvrir la base unifiée
    unified_con = sqlite3.connect(unified_path)

    # Recharger les assets existants à chaque appel (pour idempotence)
    existing = get_asset_ids_from_table(unified_con, table)
    initial_count = len(existing)
    print(f"  {table}: {initial_count} assets existants")

    # Collecter les assets de toutes les sources
    added_count = 0
    for src_path in source_paths:
        if not src_path.exists():
            print(f"    SKIP {src_path.name} (non trouvé)")
            continue
        src_con = sqlite3.connect(src_path)
        src_assets = get_asset_ids_from_table(src_con, table)
        src_con.close()

        # Compter les nouveaux pour cet source
        new_from_source = 0
        cur = unified_con.cursor()

        for aid, body in src_assets.items():
            if aid not in existing:
                # Insérer le nouvel asset
                cur.execute(f"INSERT INTO {table} (ResponseBody) VALUES (?)", (body,))
                existing[aid] = body  # Marquer comme existant pour éviter les doublons
                added_count += 1
                new_from_source += 1

        unified_con.commit()
        print(f"    {src_path.name}: {len(src_assets)} assets ({new_from_source} nouveaux)")

    unified_con.close()

    return added_count, initial_count + added_count


def main():
    data_dir = Path(__file__).parent.parent / "data"
    unified_path = data_dir / "halo_unified.db"

    if not unified_path.exists():
        print(f"ERREUR: Base unifiée non trouvée: {unified_path}")
        return

    # Lister les bases sources
    source_paths = list(data_dir.glob("spnkr_gt_*.db"))
    print(f"Bases sources trouvées: {len(source_paths)}")
    for p in source_paths:
        print(f"  - {p.name}")

    print(f"\nBase cible: {unified_path.name}")
    print()

    # Fusionner les tables d'assets
    tables = ["PlaylistMapModePairs", "Maps", "Playlists", "GameVariants"]

    total_added = 0
    for table in tables:
        added, total = merge_assets(unified_path, source_paths, table)
        total_added += added
        print(f"  -> {added} nouveaux ajoutés, {total} total\n")

    print("=== Fusion terminée ===")
    print(f"Total assets ajoutés: {total_added}")


if __name__ == "__main__":
    main()
