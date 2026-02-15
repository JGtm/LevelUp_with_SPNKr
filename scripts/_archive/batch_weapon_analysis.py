#!/usr/bin/env python3
"""
Script batch pour analyser les weapon IDs des derniers matchs.

Ce script automatise :
1. Récupération des N derniers matchs d'un joueur
2. Téléchargement des chunks type 3 (highlight events) pour chaque match
3. Extraction des events binaires
4. Agrégation des weapon IDs

Usage:
    python scripts/batch_weapon_analysis.py --gamertag JGtm --matches 10

Prérequis:
    - Tokens API configurés dans .env.local ou environnement
    - Base DuckDB du joueur existante
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def get_match_ids(gamertag: str, limit: int) -> list[tuple[str, str]]:
    """Récupère les derniers match IDs depuis DuckDB."""
    try:
        import duckdb
    except ImportError:
        print("ERREUR: duckdb non disponible")
        sys.exit(1)

    db_path = Path(f"data/players/{gamertag}/stats.duckdb")
    if not db_path.exists():
        print(f"ERREUR: Base non trouvée: {db_path}")
        sys.exit(1)

    con = duckdb.connect(str(db_path), read_only=True)
    results = con.execute(f"""
        SELECT match_id, start_time
        FROM match_stats
        ORDER BY start_time DESC
        LIMIT {limit}
    """).fetchall()
    con.close()

    return [(row[0], str(row[1])[:10]) for row in results]


def run_command(cmd: list[str], description: str) -> bool:
    """Exécute une commande et retourne True si succès."""
    print(f"\n>>> {description}")
    print(f"    {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"ERREUR: {result.stderr}")
        return False

    # Afficher un résumé de stdout
    lines = result.stdout.strip().split("\n")
    for line in lines[-5:]:  # 5 dernières lignes
        print(f"    {line}")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyse batch des weapon IDs pour les derniers matchs"
    )
    parser.add_argument("--gamertag", required=True, help="Gamertag du joueur")
    parser.add_argument("--matches", type=int, default=10, help="Nombre de matchs à analyser")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip telechargement, utiliser chunks existants",
    )
    parser.add_argument(
        "--skip-extract", action="store_true", help="Skip extraction, utiliser events existants"
    )
    parser.add_argument("--verbose", action="store_true", help="Afficher plus de details")
    parser.add_argument(
        "--strict", action="store_true", help="Mode strict: gamertags majoritairement ASCII"
    )
    parser.add_argument(
        "--max-timestamp",
        type=int,
        default=None,
        help="Timestamp max en ms (suggere: 1800000 pour 30 min)",
    )

    args = parser.parse_args()

    # Dossier de base
    base_dir = Path("data/investigation/mapping")
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"{'=' * 70}")
    print("ANALYSE BATCH DES WEAPON IDs")
    print(f"{'=' * 70}")
    print(f"Gamertag: {args.gamertag}")
    print(f"Matchs à analyser: {args.matches}")
    print(f"Dossier de sortie: {base_dir}")

    # Étape 1: Récupérer les match IDs
    print(f"\n--- Étape 1: Récupération des {args.matches} derniers matchs ---")
    matches = get_match_ids(args.gamertag, args.matches)

    for i, (match_id, date) in enumerate(matches, 1):
        print(f"  {i}. {match_id[:8]}... ({date})")

    # Python executable (utiliser celui de l'environnement virtuel si disponible)
    python_exe = sys.executable

    success_count = 0
    error_matches = []

    for i, (match_id, date) in enumerate(matches, 1):
        print(f"\n{'=' * 70}")
        print(f"[{i}/{len(matches)}] Match: {match_id}")
        print(f"{'=' * 70}")

        # Dossier du match (utiliser les 8 premiers caractères)
        match_short = match_id[:8]
        match_dir = base_dir / match_short
        chunks_dir = match_dir / "chunks"
        events_file = match_dir / "events.json"

        # Étape 2: Télécharger les chunks
        if not args.skip_download:
            # Vérifier si le chunk type 3 existe déjà
            existing_type3 = list(chunks_dir.glob("type3__*.bin")) if chunks_dir.exists() else []

            if existing_type3:
                print(f"  -> Chunk type 3 deja present: {existing_type3[0].name}")
            else:
                cmd = [
                    python_exe,
                    "scripts/refetch_film_roster.py",
                    "--match-id",
                    match_id,
                    "--save-chunks-dir",
                    str(chunks_dir),
                    "--include-type2",
                    "--max-type2-chunks",
                    "0",  # On ne veut que le type 3
                ]

                if not run_command(cmd, "Telechargement chunks"):
                    print(f"  [WARN] Echec telechargement pour {match_id}")
                    error_matches.append(match_id)
                    continue

        # Étape 3: Extraire les events
        if not args.skip_extract:
            # Trouver le chunk type 3
            type3_chunks = list(chunks_dir.glob("type3__*.bin")) if chunks_dir.exists() else []

            if not type3_chunks:
                print(f"  [WARN] Pas de chunk type 3 trouve dans {chunks_dir}")
                error_matches.append(match_id)
                continue

            cmd = [
                python_exe,
                "scripts/extract_binary_events.py",
                "--chunk",
                str(type3_chunks[0]),
                "--output",
                str(events_file),
            ]

            if args.strict:
                cmd.append("--strict")

            if args.max_timestamp:
                cmd.extend(["--max-timestamp", str(args.max_timestamp)])

            if not run_command(cmd, "Extraction events"):
                print(f"  [WARN] Echec extraction pour {match_id}")
                error_matches.append(match_id)
                continue

        # Vérifier que events.json existe
        if events_file.exists():
            print(f"  [OK] Events extraits: {events_file}")
            success_count += 1
        else:
            print("  [WARN] Fichier events non cree")
            error_matches.append(match_id)

    # Étape 4: Agréger les weapon IDs
    print(f"\n{'=' * 70}")
    print("AGRÉGATION DES WEAPON IDs")
    print(f"{'=' * 70}")

    cmd = [
        python_exe,
        "scripts/aggregate_weapon_ids.py",
        "--base-dir",
        str(base_dir),
    ]

    if args.verbose:
        cmd.append("--verbose")

    subprocess.run(cmd)

    # Résumé final
    print(f"\n{'=' * 70}")
    print("RÉSUMÉ")
    print(f"{'=' * 70}")
    print(f"Matchs traités avec succès: {success_count}/{len(matches)}")

    if error_matches:
        print(f"Matchs en erreur ({len(error_matches)}):")
        for m in error_matches:
            print(f"  - {m}")

    summary_file = base_dir / "weapon_ids_summary.json"
    if summary_file.exists():
        print(f"\nRésultats disponibles: {summary_file}")

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
