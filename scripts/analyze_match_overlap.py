#!/usr/bin/env python3
"""Analyse du taux de partage de matchs entre joueurs.

Produit `.ai/v5-match-overlap-analysis.md` documentant :
- Matrice de partage (nb matchs communs entre chaque paire)
- Taux de recouvrement (%)
- Estimation des gains de stockage avec shared_matches.duckdb
- Matchs uniques vs dupliqués

Usage:
    python scripts/analyze_match_overlap.py
    python scripts/analyze_match_overlap.py --matrix
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from itertools import combinations
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_profiles() -> dict:
    """Charge les profils joueurs depuis db_profiles.json."""
    profiles_path = REPO_ROOT / "db_profiles.json"
    with open(profiles_path, encoding="utf-8") as f:
        return json.load(f)


def load_match_ids(db_path: Path) -> set[str]:
    """Charge tous les match_id d'une base joueur."""
    if not db_path.exists():
        logger.warning("DB introuvable : %s", db_path)
        return set()

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute("SELECT match_id FROM match_stats").fetchall()
        return {r[0] for r in rows}
    finally:
        con.close()


def load_archived_match_ids(db_path: Path) -> set[str]:
    """Charge les match_id des archives Parquet."""
    archive_dir = db_path.parent / "archive"
    if not archive_dir.exists():
        return set()

    ids: set[str] = set()
    con = duckdb.connect(":memory:")
    try:
        for pf in archive_dir.glob("*.parquet"):
            try:
                rows = con.execute(
                    f"SELECT match_id FROM read_parquet('{pf.as_posix()}')"
                ).fetchall()
                ids.update(r[0] for r in rows)
            except Exception as e:
                logger.warning("Erreur lecture archive %s : %s", pf, e)
    finally:
        con.close()
    return ids


def load_table_row_counts(db_path: Path) -> dict[str, int]:
    """Charge les comptages de lignes des tables principales pour estimer le stockage."""
    if not db_path.exists():
        return {}

    con = duckdb.connect(str(db_path), read_only=True)
    tables_to_check = [
        "match_stats",
        "medals_earned",
        "highlight_events",
        "match_participants",
        "killer_victim_pairs",
        "xuid_aliases",
    ]
    counts: dict[str, int] = {}
    try:
        for tname in tables_to_check:
            try:
                cnt = con.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()
                counts[tname] = cnt[0] if cnt else 0
            except Exception:
                counts[tname] = 0
    finally:
        con.close()
    return counts


def compute_overlap_matrix(
    player_matches: dict[str, set[str]],
) -> dict[tuple[str, str], dict]:
    """Calcule la matrice de recouvrement entre toutes les paires de joueurs."""
    matrix: dict[tuple[str, str], dict] = {}

    for p1, p2 in combinations(player_matches.keys(), 2):
        ids1 = player_matches[p1]
        ids2 = player_matches[p2]

        shared = ids1 & ids2
        unique_p1 = ids1 - ids2
        unique_p2 = ids2 - ids1

        overlap_p1 = len(shared) / len(ids1) * 100 if ids1 else 0
        overlap_p2 = len(shared) / len(ids2) * 100 if ids2 else 0

        matrix[(p1, p2)] = {
            "shared_count": len(shared),
            "unique_p1": len(unique_p1),
            "unique_p2": len(unique_p2),
            "overlap_pct_p1": round(overlap_p1, 1),
            "overlap_pct_p2": round(overlap_p2, 1),
            "total_without_dedup": len(ids1) + len(ids2),
            "total_with_dedup": len(ids1 | ids2),
        }

    return matrix


def format_markdown_report(
    player_matches: dict[str, set[str]],
    player_counts: dict[str, dict[str, int]],
    matrix: dict[tuple[str, str], dict],
) -> str:
    """Formate le rapport complet en Markdown."""
    lines: list[str] = [
        "# Analyse du Partage de Matchs — pré-v5 Migration",
        "",
        f"> Généré le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## Objectif",
        "",
        "Quantifier le taux de partage de matchs entre joueurs pour valider",
        "l'architecture `shared_matches.duckdb` et estimer les gains.",
        "",
        "---",
        "",
        "## Matchs par Joueur",
        "",
        "| Joueur | Matchs DB | Match IDs |",
        "|--------|-----------|-----------|",
    ]

    for gt in sorted(player_matches.keys()):
        ids = player_matches[gt]
        lines.append(f"| {gt} | {len(ids)} | {len(ids)} uniques |")

    lines.append("")

    # Union totale
    all_ids: set[str] = set()
    for ids in player_matches.values():
        all_ids.update(ids)

    total_rows = sum(len(ids) for ids in player_matches.values())
    unique_total = len(all_ids)
    duplicated = total_rows - unique_total
    dedup_pct = duplicated / total_rows * 100 if total_rows else 0

    lines.append("## Statistiques Globales")
    lines.append("")
    lines.append(f"- **Total matchs (somme brute)** : {total_rows}")
    lines.append(f"- **Matchs uniques (dédupliqués)** : {unique_total}")
    lines.append(f"- **Matchs dupliqués** : {duplicated} ({round(dedup_pct, 1)}%)")
    lines.append(f"- **Joueurs trackés** : {len(player_matches)}")
    lines.append("")

    # Matrice de partage
    lines.append("## Matrice de Partage (Paires)")
    lines.append("")
    lines.append(
        "| Joueur A | Joueur B | Matchs Communs | % de A | % de B | Uniques A | Uniques B |"
    )
    lines.append(
        "|----------|----------|----------------|--------|--------|-----------|-----------|"
    )

    for (p1, p2), data in sorted(matrix.items()):
        lines.append(
            f"| {p1} | {p2} | **{data['shared_count']}** "
            f"| {data['overlap_pct_p1']}% | {data['overlap_pct_p2']}% "
            f"| {data['unique_p1']} | {data['unique_p2']} |"
        )
    lines.append("")

    # Estimation des gains
    lines.append("## Estimation des Gains avec shared_matches.duckdb")
    lines.append("")
    lines.append("### Stockage")
    lines.append("")
    lines.append(
        f"- Avant : {total_rows} lignes match_stats réparties sur {len(player_matches)} DBs"
    )
    lines.append(f"- Après : {unique_total} lignes dans match_registry (shared)")
    lines.append(f"- **Réduction match_stats** : -{round(dedup_pct, 1)}%")
    lines.append("")

    # Estimation lignes dupliquées dans les tables associées
    total_events = sum(c.get("highlight_events", 0) for c in player_counts.values())
    total_medals = sum(c.get("medals_earned", 0) for c in player_counts.values())
    total_participants = sum(c.get("match_participants", 0) for c in player_counts.values())
    total_kvp = sum(c.get("killer_victim_pairs", 0) for c in player_counts.values())

    lines.append("### Tables Associées (estimation)")
    lines.append("")
    lines.append("| Table | Lignes Totales (somme DBs) | Est. Réduction |")
    lines.append("|-------|---------------------------|----------------|")
    lines.append(f"| highlight_events | {total_events} | ~{round(dedup_pct)}% |")
    lines.append(f"| medals_earned | {total_medals} | ~{round(dedup_pct)}% |")
    lines.append(f"| match_participants | {total_participants} | ~{round(dedup_pct)}% |")
    lines.append(f"| killer_victim_pairs | {total_kvp} | ~{round(dedup_pct)}% |")
    lines.append("")

    lines.append("### Appels API")
    lines.append("")
    lines.append(f"- Matchs actuellement sync 1x chacun par joueur : {total_rows} appels")
    lines.append(f"- Avec partage : {unique_total} appels (1 seul fetch par match)")
    lines.append(f"- **Réduction appels API** : -{round(dedup_pct, 1)}%")
    lines.append("")

    # Détail : quels matchs sont dans combien de DBs
    match_owner_count: dict[str, int] = {}
    for ids in player_matches.values():
        for mid in ids:
            match_owner_count[mid] = match_owner_count.get(mid, 0) + 1

    distribution: dict[int, int] = {}
    for count in match_owner_count.values():
        distribution[count] = distribution.get(count, 0) + 1

    lines.append("## Distribution de la Duplication")
    lines.append("")
    lines.append("| Nombre de DBs contenant le match | Nombre de matchs | % |")
    lines.append("|----------------------------------|------------------|---|")
    for n_dbs in sorted(distribution.keys()):
        count = distribution[n_dbs]
        pct = round(count / unique_total * 100, 1) if unique_total else 0
        label = "unique" if n_dbs == 1 else f"partagé entre {n_dbs} joueurs"
        lines.append(f"| {n_dbs} ({label}) | {count} | {pct}% |")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(description="Analyse du partage de matchs")
    parser.add_argument("--matrix", action="store_true", help="Afficher la matrice de partage")
    parser.add_argument(
        "--output",
        type=str,
        default=".ai/v5-match-overlap-analysis.md",
        help="Fichier de sortie",
    )
    args = parser.parse_args()

    profiles = load_profiles()
    if not profiles or "profiles" not in profiles:
        logger.error("db_profiles.json invalide")
        sys.exit(1)

    # Charger les match_ids de chaque joueur
    player_matches: dict[str, set[str]] = {}
    player_counts: dict[str, dict[str, int]] = {}

    for gamertag, profile in sorted(profiles["profiles"].items()):
        db_path = REPO_ROOT / profile["db_path"]
        logger.info("Chargement match_ids de %s...", gamertag)

        db_ids = load_match_ids(db_path)
        archive_ids = load_archived_match_ids(db_path)
        all_ids = db_ids | archive_ids

        player_matches[gamertag] = all_ids
        player_counts[gamertag] = load_table_row_counts(db_path)

        logger.info(
            "  %s: %d matchs DB + %d archives = %d uniques",
            gamertag,
            len(db_ids),
            len(archive_ids),
            len(all_ids),
        )

    # Calculer la matrice
    matrix = compute_overlap_matrix(player_matches)

    # Affichage console
    if args.matrix:
        print("\n=== MATRICE DE PARTAGE ===\n")
        for (p1, p2), data in sorted(matrix.items()):
            print(
                f"  {p1} ↔ {p2}: {data['shared_count']} matchs communs "
                f"({data['overlap_pct_p1']}% de {p1}, {data['overlap_pct_p2']}% de {p2})"
            )
        print()

    # Rapport Markdown
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = format_markdown_report(player_matches, player_counts, matrix)
    output_path.write_text(report, encoding="utf-8")
    logger.info("Rapport exporté vers %s", output_path)

    # Résumé final
    all_ids: set[str] = set()
    for ids in player_matches.values():
        all_ids.update(ids)
    total_rows = sum(len(ids) for ids in player_matches.values())
    unique_total = len(all_ids)
    dedup_pct = (total_rows - unique_total) / total_rows * 100 if total_rows else 0

    print("\n📊 Résumé :")
    print(f"   Total matchs (brut) : {total_rows}")
    print(f"   Matchs uniques      : {unique_total}")
    print(f"   Duplication         : {round(dedup_pct, 1)}%")
    print(f"   Gains potentiels    : ~{round(dedup_pct)}% de stockage/API en moins")


if __name__ == "__main__":
    main()
