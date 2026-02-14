#!/usr/bin/env python3
"""Scripts de validation post-migration v5.

Vérifie l'intégrité des données après migration vers shared_matches.duckdb :
- Aucune perte de matchs (comparaison avant/après)
- Cohérence des comptages (médailles, events, participants)
- Intégrité référentielle (FK, orphelins)
- Comparaison des données joueur (stats identiques)

Usage:
    python scripts/validate_migration.py --baseline .ai/v5-baseline-audit.json
    python scripts/validate_migration.py --check-integrity
    python scripts/validate_migration.py --compare-player Chocoboflor
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

SHARED_DB_PATH = REPO_ROOT / "data" / "warehouse" / "shared_matches.duckdb"


def load_profiles() -> dict:
    """Charge les profils joueurs depuis db_profiles.json."""
    profiles_path = REPO_ROOT / "db_profiles.json"
    with open(profiles_path, encoding="utf-8") as f:
        return json.load(f)


def check_shared_db_exists() -> bool:
    """Vérifie que shared_matches.duckdb existe."""
    if not SHARED_DB_PATH.exists():
        logger.error("shared_matches.duckdb introuvable : %s", SHARED_DB_PATH)
        return False
    logger.info("✓ shared_matches.duckdb trouvée (%s)", SHARED_DB_PATH)
    return True


def check_shared_db_schema() -> list[str]:
    """Vérifie que le schéma de shared_matches.duckdb est correct."""
    errors: list[str] = []

    expected_tables = {
        "match_registry",
        "match_participants",
        "highlight_events",
        "medals_earned",
        "xuid_aliases",
    }

    con = duckdb.connect(str(SHARED_DB_PATH), read_only=True)
    try:
        tables = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        actual_tables = {t[0] for t in tables}

        missing = expected_tables - actual_tables
        if missing:
            errors.append(f"Tables manquantes dans shared_matches : {missing}")
        else:
            logger.info("✓ Toutes les tables attendues sont présentes")

        # Vérifier les colonnes clés
        key_columns = {
            "match_registry": ["match_id", "start_time", "playlist_id", "map_id"],
            "match_participants": ["match_id", "xuid", "kills", "deaths", "assists"],
            "medals_earned": ["match_id", "xuid", "medal_name_id", "count"],
            "highlight_events": ["match_id", "event_type"],
            "xuid_aliases": ["xuid", "gamertag"],
        }

        for table, expected_cols in key_columns.items():
            if table not in actual_tables:
                continue
            cols = con.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
                [table],
            ).fetchall()
            actual_cols = {c[0] for c in cols}
            missing_cols = set(expected_cols) - actual_cols
            if missing_cols:
                errors.append(f"Colonnes manquantes dans {table} : {missing_cols}")
            else:
                logger.info("✓ %s : colonnes clés OK", table)

    finally:
        con.close()

    return errors


def check_match_completeness(baseline_path: Path | None = None) -> list[str]:
    """Vérifie qu'aucun match n'a été perdu lors de la migration."""
    errors: list[str] = []
    profiles = load_profiles()

    # Charger les match_ids depuis les DBs joueur originales
    player_match_ids: dict[str, set[str]] = {}
    for gamertag, profile in profiles.get("profiles", {}).items():
        db_path = REPO_ROOT / profile["db_path"]
        if not db_path.exists():
            continue
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            rows = con.execute("SELECT match_id FROM match_stats").fetchall()
            player_match_ids[gamertag] = {r[0] for r in rows}
        finally:
            con.close()

    # Tous les match_ids attendus
    all_expected: set[str] = set()
    for ids in player_match_ids.values():
        all_expected.update(ids)

    # Match_ids dans shared_matches
    con = duckdb.connect(str(SHARED_DB_PATH), read_only=True)
    try:
        rows = con.execute("SELECT match_id FROM match_registry").fetchall()
        shared_ids = {r[0] for r in rows}
    finally:
        con.close()

    missing = all_expected - shared_ids
    extra = shared_ids - all_expected

    if missing:
        errors.append(
            f"{len(missing)} matchs manquants dans shared_matches (exemples : {list(missing)[:5]})"
        )
    else:
        logger.info(
            "✓ Tous les %d matchs attendus sont présents dans shared_matches", len(all_expected)
        )

    if extra:
        logger.info(
            "ℹ %d matchs supplémentaires dans shared_matches (matchs d'autres joueurs du roster)",
            len(extra),
        )

    # Vérifier par joueur
    for gamertag, expected_ids in sorted(player_match_ids.items()):
        missing_for_player = expected_ids - shared_ids
        if missing_for_player:
            errors.append(f"{gamertag} : {len(missing_for_player)} matchs manquants")
        else:
            logger.info("✓ %s : %d matchs OK", gamertag, len(expected_ids))

    # Comparer avec baseline si fourni
    if baseline_path and baseline_path.exists():
        with open(baseline_path, encoding="utf-8") as f:
            baseline = json.load(f)
        for entry in baseline:
            gt = entry.get("gamertag")
            expected_count = entry.get("match_stats", {}).get("total", 0)
            actual_count = len(player_match_ids.get(gt, set()))
            if actual_count < expected_count:
                errors.append(
                    f"Baseline {gt} : attendu {expected_count} matchs, trouvé {actual_count}"
                )

    return errors


def check_referential_integrity() -> list[str]:
    """Vérifie l'intégrité référentielle dans shared_matches.duckdb."""
    errors: list[str] = []

    con = duckdb.connect(str(SHARED_DB_PATH), read_only=True)
    try:
        # Participants orphelins (match_id sans match_registry)
        orphan_participants = con.execute(
            """
            SELECT COUNT(*) FROM match_participants mp
            WHERE NOT EXISTS (
                SELECT 1 FROM match_registry mr WHERE mr.match_id = mp.match_id
            )
            """
        ).fetchone()
        if orphan_participants and orphan_participants[0] > 0:
            errors.append(f"{orphan_participants[0]} participants orphelins (match_id introuvable)")
        else:
            logger.info("✓ Aucun participant orphelin")

        # Médailles orphelines
        orphan_medals = con.execute(
            """
            SELECT COUNT(*) FROM medals_earned me
            WHERE NOT EXISTS (
                SELECT 1 FROM match_registry mr WHERE mr.match_id = me.match_id
            )
            """
        ).fetchone()
        if orphan_medals and orphan_medals[0] > 0:
            errors.append(f"{orphan_medals[0]} médailles orphelines")
        else:
            logger.info("✓ Aucune médaille orpheline")

        # Events orphelins
        orphan_events = con.execute(
            """
            SELECT COUNT(*) FROM highlight_events he
            WHERE NOT EXISTS (
                SELECT 1 FROM match_registry mr WHERE mr.match_id = he.match_id
            )
            """
        ).fetchone()
        if orphan_events and orphan_events[0] > 0:
            errors.append(f"{orphan_events[0]} événements orphelins")
        else:
            logger.info("✓ Aucun événement orphelin")

        # Doublons dans match_registry
        duplicates = con.execute(
            "SELECT match_id, COUNT(*) AS cnt FROM match_registry GROUP BY match_id HAVING cnt > 1"
        ).fetchall()
        if duplicates:
            errors.append(f"{len(duplicates)} match_id dupliqués dans match_registry")
        else:
            logger.info("✓ Aucun doublon dans match_registry")

        # Doublons dans match_participants
        dup_participants = con.execute(
            """
            SELECT match_id, xuid, COUNT(*) AS cnt
            FROM match_participants
            GROUP BY match_id, xuid
            HAVING cnt > 1
            """
        ).fetchall()
        if dup_participants:
            errors.append(f"{len(dup_participants)} doublons dans match_participants")
        else:
            logger.info("✓ Aucun doublon dans match_participants")

    finally:
        con.close()

    return errors


def compare_player_stats(gamertag: str) -> list[str]:
    """Compare les stats d'un joueur entre sa DB personnelle et shared_matches."""
    errors: list[str] = []
    profiles = load_profiles()

    profile = profiles.get("profiles", {}).get(gamertag)
    if not profile:
        errors.append(f"Profil {gamertag} introuvable")
        return errors

    db_path = REPO_ROOT / profile["db_path"]
    xuid = profile["xuid"]

    if not db_path.exists():
        errors.append(f"DB joueur introuvable : {db_path}")
        return errors

    player_con = duckdb.connect(str(db_path), read_only=True)
    shared_con = duckdb.connect(str(SHARED_DB_PATH), read_only=True)

    try:
        # Comparer nombre de matchs
        player_count = player_con.execute("SELECT COUNT(*) FROM match_stats").fetchone()[0]
        shared_count = shared_con.execute(
            """
            SELECT COUNT(*) FROM match_participants
            WHERE xuid = ?
            """,
            [xuid],
        ).fetchone()[0]

        if player_count != shared_count:
            errors.append(
                f"{gamertag} : {player_count} matchs en DB joueur vs "
                f"{shared_count} participations en shared"
            )
        else:
            logger.info("✓ %s : %d matchs correspondent", gamertag, player_count)

        # Comparer agrégats K/D
        player_kd = player_con.execute("SELECT SUM(kills), SUM(deaths) FROM match_stats").fetchone()
        shared_kd = shared_con.execute(
            "SELECT SUM(kills), SUM(deaths) FROM match_participants WHERE xuid = ?",
            [xuid],
        ).fetchone()

        if player_kd[0] != shared_kd[0] or player_kd[1] != shared_kd[1]:
            errors.append(
                f"{gamertag} K/D mismatch : joueur={player_kd[0]}/{player_kd[1]} "
                f"vs shared={shared_kd[0]}/{shared_kd[1]}"
            )
        else:
            logger.info(
                "✓ %s : totaux K/D identiques (%s/%s)", gamertag, player_kd[0], player_kd[1]
            )

        # Comparer médailles
        player_medals = player_con.execute("SELECT COUNT(*) FROM medals_earned").fetchone()[0]
        shared_medals = shared_con.execute(
            "SELECT COUNT(*) FROM medals_earned WHERE xuid = ?",
            [xuid],
        ).fetchone()[0]

        if player_medals != shared_medals:
            errors.append(
                f"{gamertag} médailles : {player_medals} en joueur vs {shared_medals} en shared"
            )
        else:
            logger.info("✓ %s : %d médailles correspondent", gamertag, player_medals)

    finally:
        player_con.close()
        shared_con.close()

    return errors


def main() -> None:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(description="Validation post-migration v5")
    parser.add_argument("--baseline", type=str, help="Chemin vers le JSON baseline")
    parser.add_argument(
        "--check-integrity", action="store_true", help="Vérifier intégrité référentielle"
    )
    parser.add_argument("--compare-player", type=str, help="Comparer un joueur spécifique")
    parser.add_argument("--all", action="store_true", help="Toutes les validations")
    args = parser.parse_args()

    all_errors: list[str] = []

    print("=" * 60)
    print("VALIDATION POST-MIGRATION v5")
    print(f"Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    if not check_shared_db_exists():
        print("\n❌ shared_matches.duckdb n'existe pas encore.")
        print("   Ce script sera utilisable après Sprint 1 (création de la base)")
        print("   et Sprint 2 (migration des données).")
        sys.exit(0)

    # Vérification du schéma
    print("\n--- Vérification du schéma ---")
    schema_errors = check_shared_db_schema()
    all_errors.extend(schema_errors)

    # Complétude des matchs
    if args.all or args.baseline:
        print("\n--- Vérification de complétude ---")
        baseline_path = Path(args.baseline) if args.baseline else None
        completeness_errors = check_match_completeness(baseline_path)
        all_errors.extend(completeness_errors)

    # Intégrité référentielle
    if args.all or args.check_integrity:
        print("\n--- Vérification intégrité référentielle ---")
        integrity_errors = check_referential_integrity()
        all_errors.extend(integrity_errors)

    # Comparaison joueur
    if args.compare_player:
        print(f"\n--- Comparaison {args.compare_player} ---")
        player_errors = compare_player_stats(args.compare_player)
        all_errors.extend(player_errors)
    elif args.all:
        profiles = load_profiles()
        for gamertag in sorted(profiles.get("profiles", {}).keys()):
            print(f"\n--- Comparaison {gamertag} ---")
            player_errors = compare_player_stats(gamertag)
            all_errors.extend(player_errors)

    # Résumé
    print("\n" + "=" * 60)
    if all_errors:
        print(f"❌ {len(all_errors)} ERREUR(S) DÉTECTÉE(S) :")
        for err in all_errors:
            print(f"   - {err}")
        sys.exit(1)
    else:
        print("✅ TOUTES LES VALIDATIONS PASSENT")
        sys.exit(0)


if __name__ == "__main__":
    main()
