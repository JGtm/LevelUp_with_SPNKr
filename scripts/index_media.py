#!/usr/bin/env python3
"""Script pour indexer manuellement les médias et les associer aux matchs.

Usage:
    python scripts/index_media.py --db-path data/players/JGtm/stats.duckdb --videos-dir <path> --screens-dir <path>

Note: Les médias sont automatiquement associés à TOUS les joueurs ayant un match correspondant.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ajouter le répertoire racine au path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.data.media_indexer import MediaIndexer


def load_settings() -> dict:
    """Charge les settings depuis app_settings.json."""
    settings_path = ROOT_DIR / "app_settings.json"
    if not settings_path.exists():
        return {}

    try:
        with open(settings_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Indexe les médias et les associe aux matchs")
    parser.add_argument(
        "--db-path",
        type=str,
        help="Chemin vers la DB DuckDB pour stocker les médias (défaut: depuis app_settings.json ou auto-détection)",
    )
    parser.add_argument(
        "--videos-dir",
        type=str,
        help="Dossier des vidéos (défaut: depuis app_settings.json)",
    )
    parser.add_argument(
        "--screens-dir",
        type=str,
        help="Dossier des captures (défaut: depuis app_settings.json)",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=5,
        help="Tolérance en minutes pour l'association (défaut: 5)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forcer le re-scan de tous les fichiers",
    )

    args = parser.parse_args()

    # Charger les settings
    settings = load_settings()

    # Résoudre les chemins
    db_path = args.db_path or settings.get("db_path")
    if not db_path:
        # Auto-détection : chercher la première DB DuckDB dans data/players/
        players_dir = ROOT_DIR / "data" / "players"
        if players_dir.exists():
            for player_dir in players_dir.iterdir():
                if player_dir.is_dir():
                    db_file = player_dir / "stats.duckdb"
                    if db_file.exists():
                        db_path = str(db_file)
                        print(f"📁 DB auto-détectée: {db_path}")
                        break

    if not db_path:
        print("❌ Erreur: Impossible de trouver la DB DuckDB")
        print("   Utilisez --db-path ou configurez dans app_settings.json")
        return 1

    db_path_obj = Path(db_path)
    if not db_path_obj.exists():
        print(f"❌ Erreur: DB introuvable: {db_path}")
        return 1

    videos_dir = args.videos_dir or settings.get("media_videos_dir") or ""
    screens_dir = args.screens_dir or settings.get("media_screens_dir") or ""

    if not videos_dir and not screens_dir:
        print("❌ Erreur: Aucun dossier média configuré")
        print("   Utilisez --videos-dir/--screens-dir ou configurez dans app_settings.json")
        return 1

    print("🔍 Indexation des médias")
    print(f"   DB: {db_path}")
    print(f"   Vidéos: {videos_dir or '(non configuré)'}")
    print(f"   Captures: {screens_dir or '(non configuré)'}")
    print(f"   Tolérance: {args.tolerance} minutes")
    print("   Note: Les médias seront associés à TOUS les joueurs ayant un match correspondant")
    print()

    # Créer l'indexeur (sans owner_xuid - association automatique multi-joueurs)
    indexer = MediaIndexer(db_path_obj)

    # Scanner et indexer
    videos_path = Path(videos_dir) if videos_dir and Path(videos_dir).exists() else None
    screens_path = Path(screens_dir) if screens_dir and Path(screens_dir).exists() else None

    if not videos_path and not screens_path:
        print("❌ Erreur: Aucun dossier média valide trouvé")
        return 1

    print("📁 Scan des dossiers...")
    result = indexer.scan_and_index(
        videos_dir=videos_path,
        screens_dir=screens_path,
        force_rescan=args.force,
    )

    print("✅ Scan terminé:")
    print(f"   - {result.n_scanned} fichiers scannés")
    print(f"   - {result.n_new} nouveaux")
    print(f"   - {result.n_updated} mis à jour")
    if result.errors:
        print(f"   - {len(result.errors)} erreurs")
        for err in result.errors[:5]:  # Afficher les 5 premières
            print(f"     ⚠️  {err}")

    # Associer avec les matchs
    print(f"\n🔗 Association avec les matchs (tolérance: {args.tolerance} min)...")
    n_associated = indexer.associate_with_matches(tolerance_minutes=args.tolerance)
    print(f"✅ {n_associated} média(s) associé(s)")

    # Générer les thumbnails
    if videos_path:
        print("\n🎬 Génération des thumbnails...")
        n_thumb_gen, n_thumb_errors = indexer.generate_thumbnails_for_new(videos_path)
        print(f"✅ {n_thumb_gen} thumbnail(s) généré(s), {n_thumb_errors} erreur(s)")

    print("\n✅ Indexation terminée!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
