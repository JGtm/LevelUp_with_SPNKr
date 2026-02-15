#!/usr/bin/env python3
"""Migration vers V5 finale — Enrichissement de shared.match_participants.

Ce script effectue 3 opérations NON DESTRUCTIVES :

1. migrate_shared()          : ALTER TABLE match_participants + 16 colonnes
2. ensure_enrichment_table() : Crée/peuple player_match_enrichment
3. backfill_from_local()     : Copie stats étendues + MMR vers shared

Usage :
    python scripts/migration/migrate_to_v5_final.py
    python scripts/migration/migrate_to_v5_final.py --dry-run
    python scripts/migration/migrate_to_v5_final.py --player Chocoboflor
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Colonnes à ajouter à shared.match_participants ──────────────────────────

EXTENDED_COLUMNS: list[tuple[str, str]] = [
    # Stats étendues (API CoreStats, disponibles pour TOUS les participants)
    ("headshot_kills", "SMALLINT"),
    ("max_killing_spree", "SMALLINT"),
    ("kda", "FLOAT"),
    ("accuracy", "FLOAT"),
    ("time_played_seconds", "INTEGER"),
    ("grenade_kills", "SMALLINT"),
    ("melee_kills", "SMALLINT"),
    ("power_weapon_kills", "SMALLINT"),
    ("personal_score", "INTEGER"),
    # MMR et expected stats (API Skill, disponibles pour TOUS les joueurs)
    ("team_mmr", "FLOAT"),
    ("kills_expected", "FLOAT"),
    ("kills_stddev", "FLOAT"),
    ("deaths_expected", "FLOAT"),
    ("deaths_stddev", "FLOAT"),
    ("assists_expected", "FLOAT"),
    ("assists_stddev", "FLOAT"),
]

# ── Colonnes match_stats locale mappables vers shared.match_participants ─────

STATS_TO_PARTICIPANTS_MAP: dict[str, str] = {
    "headshot_kills": "headshot_kills",
    "max_killing_spree": "max_killing_spree",
    "kda": "kda",
    "accuracy": "accuracy",
    "time_played_seconds": "time_played_seconds",
    "grenade_kills": "grenade_kills",
    "melee_kills": "melee_kills",
    "power_weapon_kills": "power_weapon_kills",
    "personal_score": "personal_score",
}

MMR_TO_PARTICIPANTS_MAP: dict[str, str] = {
    "team_mmr": "team_mmr",
    "kills_expected": "kills_expected",
    "kills_stddev": "kills_stddev",
    "deaths_expected": "deaths_expected",
    "deaths_stddev": "deaths_stddev",
    "assists_expected": "assists_expected",
    "assists_stddev": "assists_stddev",
}


def _get_project_root() -> Path:
    """Retourne la racine du projet LevelUp."""
    return Path(__file__).resolve().parent.parent.parent


def _get_shared_path() -> Path:
    """Retourne le chemin vers shared_matches.duckdb."""
    return _get_project_root() / "data" / "warehouse" / "shared_matches.duckdb"


def _get_profiles() -> dict:
    """Charge db_profiles.json."""
    profiles_path = _get_project_root() / "db_profiles.json"
    return json.loads(profiles_path.read_text(encoding="utf-8"))


def _table_has_column(conn: duckdb.DuckDBPyConnection, table: str, column: str) -> bool:
    """Vérifie si une colonne existe dans une table."""
    result = conn.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name = ? AND column_name = ?",
        [table, column],
    ).fetchone()
    return bool(result and result[0] > 0)


def _table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    """Vérifie si une table existe."""
    result = conn.execute(
        "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = ?",
        [table],
    ).fetchone()
    return bool(result and result[0] > 0)


# ═══════════════════════════════════════════════════════════════════════════════
# Étape 1 : ALTER TABLE shared.match_participants
# ═══════════════════════════════════════════════════════════════════════════════


def migrate_shared(dry_run: bool = False) -> dict[str, int]:
    """Ajoute les 16 colonnes étendues à shared.match_participants.

    Retourne un dict {'added': N, 'skipped': N, 'errors': N}.
    """
    shared_path = _get_shared_path()
    if not shared_path.exists():
        logger.error("shared_matches.duckdb introuvable : %s", shared_path)
        return {"added": 0, "skipped": 0, "errors": 1}

    conn = duckdb.connect(str(shared_path), read_only=dry_run)
    stats = {"added": 0, "skipped": 0, "errors": 0}

    logger.info("=== Étape 1 : ALTER TABLE match_participants ===")
    logger.info("DB : %s", shared_path)

    for col_name, col_type in EXTENDED_COLUMNS:
        if _table_has_column(conn, "match_participants", col_name):
            logger.info("  %-25s  existe déjà — skip", col_name)
            stats["skipped"] += 1
            continue

        if dry_run:
            logger.info("  %-25s  %-10s  [DRY-RUN] serait ajoutée", col_name, col_type)
            stats["added"] += 1
            continue

        try:
            conn.execute(
                f"ALTER TABLE match_participants ADD COLUMN {col_name} {col_type}"
            )
            logger.info("  %-25s  %-10s  ajoutée ✓", col_name, col_type)
            stats["added"] += 1
        except Exception as exc:
            logger.error("  %-25s  ERREUR : %s", col_name, exc)
            stats["errors"] += 1

    # Mise à jour schema_version
    if not dry_run and stats["added"] > 0:
        try:
            conn.execute(
                "INSERT INTO schema_version (version, description, applied_at) "
                "VALUES (6, 'V5 finale - extended match_participants (16 cols)', ?)",
                [datetime.now(timezone.utc)],
            )
            logger.info("  schema_version → v6 ✓")
        except Exception as exc:
            logger.warning("  schema_version : %s (peut-être déjà v6)", exc)

    conn.close()

    logger.info(
        "Résultat : %d ajoutées, %d déjà présentes, %d erreurs",
        stats["added"],
        stats["skipped"],
        stats["errors"],
    )
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# Étape 2 : Créer/peupler player_match_enrichment
# ═══════════════════════════════════════════════════════════════════════════════

ENRICHMENT_DDL = """
CREATE TABLE IF NOT EXISTS player_match_enrichment (
    match_id VARCHAR PRIMARY KEY,
    performance_score FLOAT,
    session_id VARCHAR,
    session_label VARCHAR,
    is_with_friends BOOLEAN,
    teammates_signature VARCHAR,
    known_teammates_count SMALLINT,
    friends_xuids VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# Colonnes de match_stats qui vont dans player_match_enrichment
ENRICHMENT_COLS_FROM_MATCH_STATS = [
    "performance_score",
    "session_id",
    "session_label",
    "is_with_friends",
    "teammates_signature",
    "known_teammates_count",
    "friends_xuids",
]


def ensure_enrichment_table(
    player_db_path: str | Path,
    gamertag: str,
    dry_run: bool = False,
) -> dict[str, int]:
    """Crée player_match_enrichment si absente et la peuple depuis match_stats.

    Retourne {'created': bool, 'migrated': N}.
    """
    db_path = Path(player_db_path)
    if not db_path.exists():
        logger.warning("  DB absente pour %s : %s", gamertag, db_path)
        return {"created": False, "migrated": 0}

    conn = duckdb.connect(str(db_path), read_only=dry_run)
    result: dict[str, int] = {"created": False, "migrated": 0}

    # Créer la table si absente
    has_pme = _table_exists(conn, "player_match_enrichment")
    if not has_pme:
        if dry_run:
            logger.info("  [DRY-RUN] Créerait player_match_enrichment pour %s", gamertag)
            result["created"] = True
            conn.close()
            return result

        conn.execute(ENRICHMENT_DDL)
        logger.info("  Table player_match_enrichment créée pour %s ✓", gamertag)
        result["created"] = True
    else:
        logger.info("  Table player_match_enrichment existe déjà pour %s", gamertag)

    # Vérifier s'il y a des données à migrer depuis match_stats
    has_ms = _table_exists(conn, "match_stats")
    if not has_ms:
        logger.info("  Pas de match_stats locale pour %s — rien à migrer", gamertag)
        conn.close()
        return result

    # Compter les lignes déjà dans enrichment
    pme_count = conn.execute("SELECT COUNT(*) FROM player_match_enrichment").fetchone()[0]

    # Compter les lignes source dans match_stats ayant des données d'enrichissement
    ms_count = conn.execute(
        "SELECT COUNT(*) FROM match_stats "
        "WHERE performance_score IS NOT NULL "
        "   OR session_id IS NOT NULL "
        "   OR is_with_friends IS NOT NULL"
    ).fetchone()[0]

    if ms_count == 0:
        logger.info("  Aucune donnée d'enrichissement dans match_stats pour %s", gamertag)
        conn.close()
        return result

    if pme_count >= ms_count:
        logger.info(
            "  player_match_enrichment déjà peuplée (%d lignes) pour %s — skip",
            pme_count,
            gamertag,
        )
        conn.close()
        return result

    if dry_run:
        logger.info(
            "  [DRY-RUN] Migrerait %d lignes de match_stats → enrichment pour %s",
            ms_count - pme_count,
            gamertag,
        )
        result["migrated"] = ms_count - pme_count
        conn.close()
        return result

    # Vérifier quelles colonnes existent dans match_stats
    available_cols = []
    for col in ENRICHMENT_COLS_FROM_MATCH_STATS:
        if _table_has_column(conn, "match_stats", col):
            available_cols.append(col)

    if not available_cols:
        logger.warning("  Aucune colonne d'enrichissement trouvée dans match_stats pour %s", gamertag)
        conn.close()
        return result

    cols_select = ", ".join(available_cols)
    cols_insert = ", ".join(["match_id"] + available_cols)

    # Insérer uniquement les lignes manquantes
    sql = f"""
        INSERT INTO player_match_enrichment ({cols_insert})
        SELECT match_id, {cols_select}
        FROM match_stats
        WHERE match_id NOT IN (SELECT match_id FROM player_match_enrichment)
          AND ({" OR ".join(f"{c} IS NOT NULL" for c in available_cols)})
    """
    conn.execute(sql)
    new_count = conn.execute("SELECT COUNT(*) FROM player_match_enrichment").fetchone()[0]
    migrated = new_count - pme_count
    logger.info("  Migré %d lignes match_stats → enrichment pour %s ✓", migrated, gamertag)
    result["migrated"] = migrated

    conn.close()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Étape 3 : Backfill shared.match_participants depuis les DBs locales
# ═══════════════════════════════════════════════════════════════════════════════


def backfill_from_local(
    shared_path: str | Path,
    player_db_path: str | Path,
    xuid: str,
    gamertag: str,
    dry_run: bool = False,
) -> dict[str, int]:
    """Copie les stats étendues + MMR depuis la DB joueur vers shared.match_participants.

    Ne copie que les colonnes du joueur principal (seul présent dans match_stats locale).
    Retourne {'stats_updated': N, 'mmr_updated': N}.
    """
    shared = Path(shared_path)
    player_db = Path(player_db_path)
    result: dict[str, int] = {"stats_updated": 0, "mmr_updated": 0}

    if not shared.exists() or not player_db.exists():
        logger.warning("  DB manquante — skip backfill pour %s", gamertag)
        return result

    # Ouvrir la DB joueur en lecture seule pour vérifier les colonnes disponibles
    player_conn = duckdb.connect(str(player_db), read_only=True)

    has_ms = _table_exists(player_conn, "match_stats")
    has_pms = _table_exists(player_conn, "player_match_stats")

    # ── Stats étendues depuis match_stats ──
    if has_ms:
        available_stats = []
        for local_col, shared_col in STATS_TO_PARTICIPANTS_MAP.items():
            if _table_has_column(player_conn, "match_stats", local_col):
                available_stats.append((local_col, shared_col))

        if available_stats:
            # Compter les matchs avec des données non-NULL
            non_null_conds = " OR ".join(f"ms.{lc} IS NOT NULL" for lc, _ in available_stats)
            count_query = f"""
                SELECT COUNT(*) FROM match_stats ms
                WHERE ({non_null_conds})
            """
            count = player_conn.execute(count_query).fetchone()[0]

            if count > 0:
                if dry_run:
                    logger.info(
                        "  [DRY-RUN] Backfillerait %d matchs (stats étendues) pour %s",
                        count,
                        gamertag,
                    )
                    result["stats_updated"] = count
                else:
                    # Exécuter le backfill via shared_conn avec ATTACH
                    shared_conn = duckdb.connect(str(shared))
                    shared_conn.execute(
                        f"ATTACH '{player_db}' AS player (READ_ONLY)"
                    )

                    set_clauses = ", ".join(
                        f"{sc} = player.match_stats.{lc}" for lc, sc in available_stats
                    )
                    update_sql = f"""
                        UPDATE match_participants p SET
                            {set_clauses}
                        FROM player.match_stats
                        WHERE p.match_id = player.match_stats.match_id
                          AND p.xuid = ?
                    """
                    shared_conn.execute(update_sql, [xuid])

                    # Compter les lignes effectivement mises à jour
                    # (vérifier qu'au moins une colonne est non-NULL)
                    verify_conds = " OR ".join(f"p.{sc} IS NOT NULL" for _, sc in available_stats)
                    updated = shared_conn.execute(
                        f"SELECT COUNT(*) FROM match_participants p WHERE p.xuid = ? AND ({verify_conds})",
                        [xuid],
                    ).fetchone()[0]

                    shared_conn.execute("DETACH player")
                    shared_conn.close()

                    result["stats_updated"] = updated
                    logger.info(
                        "  Backfill stats étendues : %d matchs mis à jour pour %s ✓",
                        updated,
                        gamertag,
                    )
            else:
                logger.info("  Aucune stat étendue à backfiller pour %s", gamertag)
        else:
            logger.info("  Aucune colonne de stats étendues dans match_stats pour %s", gamertag)
    else:
        logger.info("  Pas de match_stats locale pour %s — skip stats étendues", gamertag)

    # ── MMR depuis player_match_stats ──
    if has_pms:
        available_mmr = []
        for local_col, shared_col in MMR_TO_PARTICIPANTS_MAP.items():
            if _table_has_column(player_conn, "player_match_stats", local_col):
                available_mmr.append((local_col, shared_col))

        if available_mmr:
            count = player_conn.execute(
                "SELECT COUNT(*) FROM player_match_stats WHERE team_mmr IS NOT NULL"
            ).fetchone()[0]

            if count > 0:
                if dry_run:
                    logger.info(
                        "  [DRY-RUN] Backfillerait %d matchs (MMR) pour %s",
                        count,
                        gamertag,
                    )
                    result["mmr_updated"] = count
                else:
                    shared_conn = duckdb.connect(str(shared))
                    shared_conn.execute(
                        f"ATTACH '{player_db}' AS player (READ_ONLY)"
                    )

                    set_clauses = ", ".join(
                        f"{sc} = player.player_match_stats.{lc}"
                        for lc, sc in available_mmr
                    )
                    update_sql = f"""
                        UPDATE match_participants p SET
                            {set_clauses}
                        FROM player.player_match_stats
                        WHERE p.match_id = player.player_match_stats.match_id
                          AND p.xuid = ?
                    """
                    shared_conn.execute(update_sql, [xuid])

                    # Vérifier
                    updated = shared_conn.execute(
                        "SELECT COUNT(*) FROM match_participants WHERE xuid = ? AND team_mmr IS NOT NULL",
                        [xuid],
                    ).fetchone()[0]

                    shared_conn.execute("DETACH player")
                    shared_conn.close()

                    result["mmr_updated"] = updated
                    logger.info(
                        "  Backfill MMR : %d matchs mis à jour pour %s ✓",
                        updated,
                        gamertag,
                    )
            else:
                logger.info("  Aucun MMR à backfiller pour %s", gamertag)
        else:
            logger.info("  Aucune colonne MMR dans player_match_stats pour %s", gamertag)
    else:
        logger.info("  Pas de player_match_stats locale pour %s — skip MMR", gamertag)

    player_conn.close()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Vérification post-migration
# ═══════════════════════════════════════════════════════════════════════════════


def verify_migration() -> bool:
    """Vérifie que la migration est complète."""
    shared_path = _get_shared_path()
    if not shared_path.exists():
        logger.error("shared_matches.duckdb introuvable")
        return False

    conn = duckdb.connect(str(shared_path), read_only=True)

    # Vérifier les 16 nouvelles colonnes
    missing = []
    for col_name, _ in EXTENDED_COLUMNS:
        if not _table_has_column(conn, "match_participants", col_name):
            missing.append(col_name)

    if missing:
        logger.error("Colonnes manquantes dans match_participants : %s", missing)
        conn.close()
        return False

    # Compter les colonnes totales
    total = conn.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name = 'match_participants'"
    ).fetchone()[0]
    logger.info("match_participants : %d colonnes (attendues : 32)", total)

    # Vérifier le remplissage par joueur
    profiles = _get_profiles()
    for gt, p in profiles["profiles"].items():
        xuid = p.get("xuid", "")
        if not xuid:
            continue

        row = conn.execute(
            "SELECT COUNT(*), "
            "COUNT(headshot_kills), COUNT(max_killing_spree), "
            "COUNT(kda), COUNT(accuracy), COUNT(team_mmr) "
            "FROM match_participants WHERE xuid = ?",
            [xuid],
        ).fetchone()

        total_m = row[0]
        hs = row[1]
        spree = row[2]
        kda = row[3]
        acc = row[4]
        mmr = row[5]

        pct_hs = (hs / total_m * 100) if total_m > 0 else 0
        pct_mmr = (mmr / total_m * 100) if total_m > 0 else 0

        logger.info(
            "  %s : %d matchs | hs=%d (%.0f%%) spree=%d kda=%d acc=%d mmr=%d (%.0f%%)",
            gt,
            total_m,
            hs,
            pct_hs,
            spree,
            kda,
            acc,
            mmr,
            pct_mmr,
        )

    # Vérifier schema_version
    try:
        v = conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if v and v[0] >= 6:
            logger.info("schema_version : v%d ✓", v[0])
        else:
            logger.warning("schema_version < 6 : v%s", v[0] if v else "?")
    except Exception:
        logger.warning("Pas de table schema_version")

    conn.close()

    # Vérifier player_match_enrichment pour chaque joueur
    logger.info("")
    logger.info("=== Vérification player_match_enrichment ===")
    for gt, p in profiles["profiles"].items():
        db_path = Path(p["db_path"])
        if not db_path.exists():
            logger.warning("  %s : DB absente", gt)
            continue
        pconn = duckdb.connect(str(db_path), read_only=True)
        if _table_exists(pconn, "player_match_enrichment"):
            count = pconn.execute("SELECT COUNT(*) FROM player_match_enrichment").fetchone()[0]
            with_ps = pconn.execute(
                "SELECT COUNT(*) FROM player_match_enrichment WHERE performance_score IS NOT NULL"
            ).fetchone()[0]
            with_session = pconn.execute(
                "SELECT COUNT(*) FROM player_match_enrichment WHERE session_id IS NOT NULL"
            ).fetchone()[0]
            logger.info(
                "  %s : %d lignes (perf_score=%d, session=%d)",
                gt,
                count,
                with_ps,
                with_session,
            )
        else:
            logger.warning("  %s : table player_match_enrichment ABSENTE ❌", gt)
        pconn.close()

    return len(missing) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Orchestrateur principal
# ═══════════════════════════════════════════════════════════════════════════════


def run_migration(
    dry_run: bool = False,
    player_filter: str | None = None,
) -> bool:
    """Exécute la migration V5 finale complète.

    Args:
        dry_run: Si True, n'effectue aucune modification.
        player_filter: Si spécifié, ne migre que ce joueur.

    Returns:
        True si la migration est réussie.
    """
    logger.info("=" * 60)
    logger.info("MIGRATION V5 FINALE — Enrichissement shared.match_participants")
    logger.info("Mode : %s", "DRY-RUN 🔍" if dry_run else "EXÉCUTION ⚡")
    logger.info("=" * 60)
    logger.info("")

    # ── Étape 1 : ALTER TABLE shared ──
    step1 = migrate_shared(dry_run=dry_run)
    if step1["errors"] > 0:
        logger.error("Erreurs lors de l'ALTER TABLE — abandon")
        return False

    logger.info("")

    # ── Étape 2 + 3 : Pour chaque joueur ──
    profiles = _get_profiles()
    shared_path = _get_shared_path()

    total_enriched = 0
    total_stats = 0
    total_mmr = 0

    for gt, p in profiles["profiles"].items():
        if player_filter and gt.lower() != player_filter.lower():
            continue

        logger.info("--- %s ---", gt)
        db_path = p["db_path"]
        xuid = p.get("xuid", "")

        # Étape 2 : player_match_enrichment
        r2 = ensure_enrichment_table(db_path, gt, dry_run=dry_run)
        total_enriched += r2.get("migrated", 0)

        # Étape 3 : backfill shared
        if xuid:
            r3 = backfill_from_local(shared_path, db_path, xuid, gt, dry_run=dry_run)
            total_stats += r3.get("stats_updated", 0)
            total_mmr += r3.get("mmr_updated", 0)
        else:
            logger.warning("  Pas de xuid pour %s — skip backfill", gt)

        logger.info("")

    # ── Résumé ──
    logger.info("=" * 60)
    logger.info("RÉSUMÉ MIGRATION")
    logger.info("  Colonnes ajoutées à shared : %d", step1["added"])
    logger.info("  Lignes enrichment migrées  : %d", total_enriched)
    logger.info("  Matchs stats backfillés    : %d", total_stats)
    logger.info("  Matchs MMR backfillés      : %d", total_mmr)
    logger.info("=" * 60)
    logger.info("")

    # ── Vérification ──
    if not dry_run:
        logger.info("=== VÉRIFICATION POST-MIGRATION ===")
        ok = verify_migration()
        if ok:
            logger.info("")
            logger.info("✅ Migration V5 finale terminée avec succès !")
        else:
            logger.error("❌ Vérification échouée — vérifier les erreurs ci-dessus")
        return ok

    logger.info("✅ Dry-run terminé — aucune modification effectuée")
    return True


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(
        description="Migration V5 finale — Enrichissement shared.match_participants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python scripts/migration/migrate_to_v5_final.py --dry-run
  python scripts/migration/migrate_to_v5_final.py
  python scripts/migration/migrate_to_v5_final.py --player Chocoboflor
  python scripts/migration/migrate_to_v5_final.py --verify-only
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule la migration sans effectuer de modifications",
    )
    parser.add_argument(
        "--player",
        type=str,
        default=None,
        help="Ne migrer qu'un joueur spécifique (gamertag)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Vérifier l'état de la migration sans modifier",
    )

    args = parser.parse_args()

    if args.verify_only:
        ok = verify_migration()
        sys.exit(0 if ok else 1)

    ok = run_migration(dry_run=args.dry_run, player_filter=args.player)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
