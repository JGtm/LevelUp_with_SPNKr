#!/usr/bin/env python3
"""Audit complet des données actuelles de toutes les bases joueur.

Produit un fichier `.ai/v5-baseline-audit.md` documentant :
- Nombre de matchs par joueur
- Nombre de médailles, événements, participants
- Plage temporelle couverte
- Tables et comptages détaillés

Usage:
    python scripts/audit_current_data.py
    python scripts/audit_current_data.py --summary
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
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


def audit_player(gamertag: str, db_path: Path, xuid: str) -> dict:
    """Audite une base joueur et retourne les statistiques complètes."""
    if not db_path.exists():
        return {"gamertag": gamertag, "error": f"DB introuvable: {db_path}"}

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        result: dict = {
            "gamertag": gamertag,
            "xuid": xuid,
            "db_path": str(db_path),
            "file_size_mb": round(db_path.stat().st_size / (1024 * 1024), 2),
        }

        # Tables existantes
        tables = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        result["tables"] = [t[0] for t in tables]

        # Comptages par table
        row_counts: dict[str, int] = {}
        for (tname,) in tables:
            try:
                cnt = con.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()
                row_counts[tname] = cnt[0] if cnt else 0
            except Exception:
                row_counts[tname] = -1
        result["row_counts"] = row_counts

        # Statistiques matchs
        try:
            match_stats = con.execute(
                """
                SELECT
                    COUNT(*) AS total_matches,
                    MIN(start_time) AS first_match,
                    MAX(start_time) AS last_match,
                    COUNT(DISTINCT playlist_id) AS distinct_playlists,
                    COUNT(DISTINCT map_id) AS distinct_maps,
                    SUM(CASE WHEN is_firefight = TRUE THEN 1 ELSE 0 END) AS firefight_count,
                    SUM(CASE WHEN is_ranked = TRUE THEN 1 ELSE 0 END) AS ranked_count,
                    AVG(kills) AS avg_kills,
                    AVG(deaths) AS avg_deaths,
                    SUM(kills) AS total_kills,
                    SUM(deaths) AS total_deaths,
                    SUM(time_played_seconds) AS total_time_seconds
                FROM match_stats
                """
            ).fetchone()
            result["match_stats"] = {
                "total": match_stats[0],
                "first_match": str(match_stats[1]) if match_stats[1] else None,
                "last_match": str(match_stats[2]) if match_stats[2] else None,
                "distinct_playlists": match_stats[3],
                "distinct_maps": match_stats[4],
                "firefight_count": match_stats[5],
                "ranked_count": match_stats[6],
                "avg_kills": round(match_stats[7], 2) if match_stats[7] else 0,
                "avg_deaths": round(match_stats[8], 2) if match_stats[8] else 0,
                "total_kills": match_stats[9],
                "total_deaths": match_stats[10],
                "total_time_hours": round((match_stats[11] or 0) / 3600, 1),
            }
        except Exception as e:
            result["match_stats"] = {"error": str(e)}

        # Match IDs (pour analyse overlap)
        try:
            match_ids = con.execute("SELECT match_id FROM match_stats").fetchall()
            result["match_ids"] = [m[0] for m in match_ids]
        except Exception:
            result["match_ids"] = []

        # Archives
        archive_dir = db_path.parent / "archive"
        if archive_dir.exists():
            parquet_files = list(archive_dir.glob("*.parquet"))
            result["archives"] = {
                "count": len(parquet_files),
                "files": [f.name for f in parquet_files],
            }
            # Compter les matchs archivés
            total_archived = 0
            archived_ids: list[str] = []
            for pf in parquet_files:
                try:
                    cnt = con.execute(
                        f"SELECT COUNT(*) FROM read_parquet('{pf.as_posix()}')"
                    ).fetchone()
                    total_archived += cnt[0] if cnt else 0
                    ids = con.execute(
                        f"SELECT match_id FROM read_parquet('{pf.as_posix()}')"
                    ).fetchall()
                    archived_ids.extend([i[0] for i in ids])
                except Exception:
                    pass
            result["archives"]["total_matches"] = total_archived
            result["archived_match_ids"] = archived_ids
        else:
            result["archives"] = {"count": 0, "files": []}
            result["archived_match_ids"] = []

        return result
    finally:
        con.close()


def format_summary(audits: list[dict]) -> str:
    """Formate un résumé des audits en texte."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("AUDIT DONNÉES BASELINE — LevelUp pré-v5")
    lines.append(f"Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    lines.append("")

    for audit in audits:
        gt = audit["gamertag"]
        if "error" in audit:
            lines.append(f"❌ {gt} : {audit['error']}")
            continue

        ms = audit.get("match_stats", {})
        lines.append(f"📊 {gt}")
        lines.append(f"   XUID       : {audit.get('xuid', '?')}")
        lines.append(f"   Taille DB  : {audit['file_size_mb']} MB")
        lines.append(f"   Matchs     : {ms.get('total', '?')}")
        lines.append(f"   Période    : {ms.get('first_match', '?')} → {ms.get('last_match', '?')}")
        lines.append(f"   Playlists  : {ms.get('distinct_playlists', '?')}")
        lines.append(f"   Maps       : {ms.get('distinct_maps', '?')}")
        lines.append(f"   Firefight  : {ms.get('firefight_count', 0)}")
        lines.append(f"   Ranked     : {ms.get('ranked_count', 0)}")
        lines.append(f"   Total K/D  : {ms.get('total_kills', 0)}/{ms.get('total_deaths', 0)}")
        lines.append(f"   Temps jeu  : {ms.get('total_time_hours', 0)}h")

        rc = audit.get("row_counts", {})
        lines.append(f"   Tables     : {len(audit.get('tables', []))}")
        lines.append(f"   Médailles  : {rc.get('medals_earned', 0)} lignes")
        lines.append(f"   Events     : {rc.get('highlight_events', 0)} lignes")
        lines.append(f"   Particip.  : {rc.get('match_participants', 0)} lignes")
        lines.append(f"   Antagonistes: {rc.get('antagonists', 0)} lignes")
        lines.append(f"   Coéquipiers: {rc.get('teammates_aggregate', 0)} lignes")

        archives = audit.get("archives", {})
        if archives.get("count", 0) > 0:
            lines.append(
                f"   Archives   : {archives['count']} fichiers, {archives.get('total_matches', 0)} matchs"
            )
        lines.append("")

    return "\n".join(lines)


def format_markdown_report(audits: list[dict]) -> str:
    """Formate le rapport complet en Markdown."""
    lines: list[str] = [
        "# Audit Baseline des Données — pré-v5 Migration",
        "",
        f"> Généré le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## Résumé",
        "",
        "| Joueur | Matchs DB | Matchs Archives | Total | Taille DB | Période |",
        "|--------|-----------|-----------------|-------|-----------|---------|",
    ]

    total_matches_all = 0
    total_size_all = 0.0

    for audit in audits:
        if "error" in audit:
            lines.append(f"| {audit['gamertag']} | ❌ | - | - | - | - |")
            continue

        ms = audit.get("match_stats", {})
        match_count = ms.get("total", 0)
        archive_count = audit.get("archives", {}).get("total_matches", 0)
        total = match_count + archive_count
        size = audit["file_size_mb"]
        period = f"{(ms.get('first_match', '?') or '?')[:10]} → {(ms.get('last_match', '?') or '?')[:10]}"

        total_matches_all += total
        total_size_all += size

        lines.append(
            f"| {audit['gamertag']} | {match_count} | {archive_count} "
            f"| {total} | {size} MB | {period} |"
        )

    lines.append(
        f"| **Total** | - | - | **{total_matches_all}** | **{round(total_size_all, 2)} MB** | - |"
    )
    lines.append("")

    # Détails par joueur
    for audit in audits:
        if "error" in audit:
            continue

        gt = audit["gamertag"]
        ms = audit.get("match_stats", {})
        rc = audit.get("row_counts", {})

        lines.append(f"## {gt}")
        lines.append("")
        lines.append(f"- **XUID** : `{audit.get('xuid', '?')}`")
        lines.append(f"- **DB** : `{audit['db_path']}`")
        lines.append(f"- **Taille** : {audit['file_size_mb']} MB")
        lines.append("")

        lines.append("### Statistiques de jeu")
        lines.append("")
        lines.append(f"- Matchs : **{ms.get('total', 0)}**")
        lines.append(f"- Période : {ms.get('first_match', '?')} → {ms.get('last_match', '?')}")
        lines.append(f"- Playlists distinctes : {ms.get('distinct_playlists', 0)}")
        lines.append(f"- Maps distinctes : {ms.get('distinct_maps', 0)}")
        lines.append(f"- Matchs Firefight : {ms.get('firefight_count', 0)}")
        lines.append(f"- Matchs Ranked : {ms.get('ranked_count', 0)}")
        lines.append(f"- K/D total : {ms.get('total_kills', 0)}/{ms.get('total_deaths', 0)}")
        lines.append(f"- Temps de jeu total : {ms.get('total_time_hours', 0)}h")
        lines.append("")

        lines.append("### Comptages par table")
        lines.append("")
        lines.append("| Table | Lignes |")
        lines.append("|-------|--------|")
        for tname in sorted(rc.keys()):
            lines.append(f"| `{tname}` | {rc[tname]} |")
        lines.append("")

        # Archives
        archives = audit.get("archives", {})
        if archives.get("count", 0) > 0:
            lines.append("### Archives Parquet")
            lines.append("")
            for f in archives.get("files", []):
                lines.append(f"- `{f}`")
            lines.append(f"- Total matchs archivés : **{archives.get('total_matches', 0)}**")
            lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(description="Audit des données pré-v5 migration")
    parser.add_argument("--summary", action="store_true", help="Afficher un résumé compact")
    parser.add_argument(
        "--output",
        type=str,
        default=".ai/v5-baseline-audit.md",
        help="Fichier de sortie Markdown",
    )
    parser.add_argument("--json", action="store_true", help="Exporter aussi en JSON")
    args = parser.parse_args()

    profiles = load_profiles()
    if not profiles or "profiles" not in profiles:
        logger.error("db_profiles.json invalide ou introuvable")
        sys.exit(1)

    audits: list[dict] = []
    for gamertag, profile in sorted(profiles["profiles"].items()):
        db_path = REPO_ROOT / profile["db_path"]
        xuid = profile["xuid"]
        logger.info("Audit de %s (%s)...", gamertag, db_path)
        audit = audit_player(gamertag, db_path, xuid)
        audits.append(audit)

    # Résumé console
    if args.summary:
        print(format_summary(audits))
    else:
        summary = format_summary(audits)
        print(summary)

    # Rapport Markdown
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = format_markdown_report(audits)
    output_path.write_text(report, encoding="utf-8")
    logger.info("Rapport exporté vers %s", output_path)

    # Export JSON optionnel
    if args.json:
        json_path = output_path.with_suffix(".json")
        # Retirer match_ids et archived_match_ids du JSON (trop volumineux)
        clean_audits = []
        for a in audits:
            clean = {k: v for k, v in a.items() if k not in ("match_ids", "archived_match_ids")}
            clean_audits.append(clean)
        json_path.write_text(json.dumps(clean_audits, indent=2, default=str), encoding="utf-8")
        logger.info("JSON exporté vers %s", json_path)


if __name__ == "__main__":
    main()
