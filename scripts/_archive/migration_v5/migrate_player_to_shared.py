"""Migre les données d'un joueur vers shared_matches.duckdb.

Logique :
1. Lire tous les matchs de data/players/{gamertag}/stats.duckdb
2. Pour chaque match :
   - Si match_id existe dans shared.match_registry :
     → Incrémenter player_count
     → Ajouter les participants manquants
   - Sinon :
     → Insérer dans match_registry
     → Insérer roster complet (match_participants)
     → Insérer events (highlight_events)
     → Insérer médailles (medals_earned) avec xuid
     → Marquer first_sync_by = gamertag

3. Migrer les xuid_aliases du joueur

Usage :
    python scripts/migration/migrate_player_to_shared.py Chocoboflor [--verbose] [--dry-run]
    python scripts/migration/migrate_player_to_shared.py --all [--verbose]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import polars as pl

# Résolution du répertoire racine du projet
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_SHARED_DB = PROJECT_ROOT / "data" / "warehouse" / "shared_matches.duckdb"
PROFILES_PATH = PROJECT_ROOT / "db_profiles.json"
XUID_ALIASES_JSON = PROJECT_ROOT / "data" / "xuid_aliases.json"

logger = logging.getLogger(__name__)


# =============================================================================
# Fonctions utilitaires
# =============================================================================


def load_profiles() -> dict[str, dict[str, str]]:
    """Charge db_profiles.json et retourne les profils joueurs."""
    if not PROFILES_PATH.exists():
        raise FileNotFoundError(f"Fichier profils introuvable : {PROFILES_PATH}")
    data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    return data.get("profiles", {})


def _safe_int(val: object) -> int | None:
    """Conversion sécurisée vers int."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# =============================================================================
# Migration des matchs (match_registry)
# =============================================================================


def _migrate_match_registry(
    conn_player: duckdb.DuckDBPyConnection,
    conn_shared: duckdb.DuckDBPyConnection,
    gamertag: str,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, int]:
    """Migre les matchs d'un joueur vers match_registry.

    Returns:
        Statistiques de migration (new, existing, total).
    """
    stats = {"matches_processed": 0, "matches_new": 0, "matches_existing": 0}

    # Charger tous les matchs du joueur
    try:
        matches_df = conn_player.execute("""
            SELECT
                match_id, start_time, end_time,
                playlist_id, playlist_name,
                map_id, map_name,
                pair_id, pair_name,
                game_variant_id, game_variant_name,
                mode_category, is_ranked, is_firefight,
                time_played_seconds,
                my_team_score,
                enemy_team_score
            FROM match_stats
            ORDER BY start_time ASC
        """).pl()
    except duckdb.CatalogException:
        logger.warning(f"  Table match_stats introuvable pour {gamertag}")
        return stats

    if matches_df.is_empty():
        logger.info(f"  Aucun match trouvé pour {gamertag}")
        return stats

    # Récupérer les match_ids déjà connus dans shared
    existing_ids: set[str] = set()
    try:
        existing_rows = conn_shared.execute(
            "SELECT match_id FROM match_registry"
        ).fetchall()
        existing_ids = {r[0] for r in existing_rows}
    except Exception:
        pass

    now = datetime.now(timezone.utc)

    # Séparer nouveaux vs existants via filtrage DataFrame (préserve les types)
    all_match_ids = matches_df["match_id"].to_list()
    existing_match_ids = [m for m in all_match_ids if m in existing_ids]
    new_match_ids_set = {m for m in all_match_ids if m not in existing_ids}

    stats["matches_processed"] = len(all_match_ids)
    stats["matches_existing"] = len(existing_match_ids)
    stats["matches_new"] = len(new_match_ids_set)

    if verbose:
        for mid in existing_match_ids:
            print(f"  ✓ {mid} (déjà connu)")
        for mid in new_match_ids_set:
            print(f"  ⭐ {mid} (nouveau)")

    # Incrément player_count pour les matchs existants
    # Note : le schéma v5 n'utilise pas de FK DuckDB (limitation OLAP :
    # UPDATE traité comme DELETE+INSERT violait les FK).
    # L'intégrité référentielle est assurée par la logique de migration.
    if existing_match_ids and not dry_run:
        existing_df = pl.DataFrame({"match_id": existing_match_ids})
        conn_shared.execute(
            "CREATE TEMPORARY TABLE IF NOT EXISTS _tmp_existing_ids (match_id VARCHAR)"
        )
        conn_shared.execute("DELETE FROM _tmp_existing_ids")
        conn_shared.execute(
            "INSERT INTO _tmp_existing_ids SELECT * FROM existing_df"
        )
        conn_shared.execute("""
            UPDATE match_registry
            SET player_count = player_count + 1,
                last_updated_at = CURRENT_TIMESTAMP
            WHERE match_id IN (SELECT match_id FROM _tmp_existing_ids)
        """)
        conn_shared.execute("DROP TABLE IF EXISTS _tmp_existing_ids")

    # Batch insert des nouveaux matchs (filtrage DataFrame pour préserver les types)
    if new_match_ids_set and not dry_run:
        insert_df = matches_df.filter(
            pl.col("match_id").is_in(list(new_match_ids_set))
        )

        # Renommer les colonnes pour correspondre au schéma shared
        insert_df = insert_df.rename({
            "time_played_seconds": "duration_seconds",
            "my_team_score": "team_0_score",
            "enemy_team_score": "team_1_score",
        })

        # Ajouter les colonnes de tracking
        insert_df = insert_df.with_columns([
            pl.lit(0).cast(pl.Int32).alias("backfill_completed"),
            pl.lit(False).alias("participants_loaded"),
            pl.lit(False).alias("events_loaded"),
            pl.lit(False).alias("medals_loaded"),
            pl.lit(gamertag).alias("first_sync_by"),
            pl.lit(now).alias("first_sync_at"),
            pl.lit(now).alias("last_updated_at"),
            pl.lit(1).cast(pl.Int16).alias("player_count"),
            pl.lit(now).alias("created_at"),
            pl.lit(now).alias("updated_at"),
        ])

        # S'assurer que l'ordre des colonnes correspond au schéma
        cols_order = [
            "match_id", "start_time", "end_time",
            "playlist_id", "playlist_name",
            "map_id", "map_name",
            "pair_id", "pair_name",
            "game_variant_id", "game_variant_name",
            "mode_category", "is_ranked", "is_firefight",
            "duration_seconds",
            "team_0_score", "team_1_score",
            "backfill_completed",
            "participants_loaded", "events_loaded", "medals_loaded",
            "first_sync_by", "first_sync_at", "last_updated_at",
            "player_count",
            "created_at", "updated_at",
        ]
        insert_df = insert_df.select([c for c in cols_order if c in insert_df.columns])

        conn_shared.execute(
            "INSERT INTO match_registry SELECT * FROM insert_df"
        )

    return stats


# =============================================================================
# Migration des participants (match_participants)
# =============================================================================


def _migrate_participants(
    conn_player: duckdb.DuckDBPyConnection,
    conn_shared: duckdb.DuckDBPyConnection,
    gamertag: str,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Migre match_participants vers shared_matches.

    Utilise INSERT OR IGNORE pour éviter les doublons
    (un participant peut exister si un autre joueur a déjà importé ce match).

    Returns:
        Nombre de participants insérés.
    """
    try:
        participants_df = conn_player.execute("""
            SELECT
                match_id, xuid,
                gamertag, team_id, outcome,
                rank, score,
                kills, deaths, assists,
                shots_fired, shots_hit,
                damage_dealt, damage_taken
            FROM match_participants
        """).pl()
    except duckdb.CatalogException:
        logger.warning(f"  Table match_participants introuvable pour {gamertag}")
        return 0

    if participants_df.is_empty():
        return 0

    # Ajouter created_at
    now = datetime.now(timezone.utc)
    participants_df = participants_df.with_columns(
        pl.lit(now).alias("created_at")
    )

    if dry_run:
        return len(participants_df)

    # Compter avant pour mesurer les insérés réels
    before_count = conn_shared.execute(
        "SELECT COUNT(*) FROM match_participants"
    ).fetchone()[0]

    # Utiliser INSERT OR IGNORE pour les doublons (match_id, xuid)
    conn_shared.execute(
        "INSERT OR IGNORE INTO match_participants SELECT * FROM participants_df"
    )

    after_count = conn_shared.execute(
        "SELECT COUNT(*) FROM match_participants"
    ).fetchone()[0]

    count = after_count - before_count

    if verbose:
        print(f"  📋 {count} participants insérés (sur {len(participants_df)} totaux)")

    # Mettre à jour participants_loaded dans match_registry
    match_ids = participants_df["match_id"].unique().to_list()
    if match_ids:
        placeholders = ", ".join(["?"] * len(match_ids))
        conn_shared.execute(
            f"UPDATE match_registry SET participants_loaded = TRUE "
            f"WHERE match_id IN ({placeholders})",
            match_ids,
        )

    return count


# =============================================================================
# Migration des highlight_events
# =============================================================================


def _parse_event_killer_victim(
    event_type: str,
    xuid: str | None,
    gamertag: str | None,
    raw_json: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Détermine killer_xuid/gamertag et victim_xuid/gamertag depuis un event v4.

    Dans le schéma v4 :
    - event_type='Kill' → xuid est le killer
    - event_type='Death' → xuid est le victim
    - Pour l'autre partie, on tente de parser raw_json

    Returns:
        (killer_xuid, killer_gamertag, victim_xuid, victim_gamertag)
    """
    killer_xuid = killer_gt = victim_xuid = victim_gt = None

    # Tenter d'extraire des infos depuis raw_json
    other_xuid = other_gt = None
    if raw_json:
        try:
            data = json.loads(raw_json)
            # Différents formats possibles dans raw_json
            for key_x in ("other_xuid", "opponent_xuid", "victim_xuid", "killer_xuid"):
                if key_x in data and data[key_x]:
                    other_xuid = str(data[key_x])
                    break
            for key_g in ("other_gamertag", "opponent_gamertag", "victim_gamertag",
                          "killer_gamertag", "gamertag"):
                if key_g in data and data[key_g]:
                    other_gt = str(data[key_g])
                    break
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    event_upper = event_type.upper() if event_type else ""

    if event_upper == "KILL":
        killer_xuid = xuid
        killer_gt = gamertag
        victim_xuid = other_xuid
        victim_gt = other_gt
    elif event_upper == "DEATH":
        victim_xuid = xuid
        victim_gt = gamertag
        killer_xuid = other_xuid
        killer_gt = other_gt
    else:
        # Autre type d'event (assist, etc.) — xuid est le joueur concerné
        killer_xuid = xuid
        killer_gt = gamertag

    return killer_xuid, killer_gt, victim_xuid, victim_gt


def _migrate_highlight_events(
    conn_player: duckdb.DuckDBPyConnection,
    conn_shared: duckdb.DuckDBPyConnection,
    gamertag: str,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Migre highlight_events vers shared_matches (conversion xuid→killer/victim).

    Returns:
        Nombre d'events insérés.
    """
    try:
        events_df = conn_player.execute("""
            SELECT
                match_id, event_type, time_ms,
                xuid, gamertag,
                type_hint, raw_json
            FROM highlight_events
        """).pl()
    except duckdb.CatalogException:
        logger.warning(f"  Table highlight_events introuvable pour {gamertag}")
        return 0

    if events_df.is_empty():
        return 0

    # Récupérer les match_ids déjà peuplés dans shared highlight_events
    # pour éviter les doublons (si un autre joueur a déjà importé les events d'un match)
    existing_event_matches: set[str] = set()
    try:
        rows = conn_shared.execute(
            "SELECT DISTINCT match_id FROM highlight_events"
        ).fetchall()
        existing_event_matches = {r[0] for r in rows}
    except Exception:
        pass

    # Filtrer : ne garder que les events de matchs pas encore dans shared
    match_ids_to_migrate = set(events_df["match_id"].unique().to_list()) - existing_event_matches

    if not match_ids_to_migrate:
        if verbose:
            print(f"  ⏭️  Tous les events déjà migrés ({len(existing_event_matches)} matchs)")
        return 0

    events_df = events_df.filter(pl.col("match_id").is_in(list(match_ids_to_migrate)))

    # Transformer les events v4 → v5 (xuid → killer_xuid/victim_xuid)
    rows_v5 = []
    now = datetime.now(timezone.utc)

    for row in events_df.iter_rows(named=True):
        killer_xuid, killer_gt, victim_xuid, victim_gt = _parse_event_killer_victim(
            row["event_type"],
            row.get("xuid"),
            row.get("gamertag"),
            row.get("raw_json"),
        )
        rows_v5.append({
            "match_id": row["match_id"],
            "event_type": row["event_type"],
            "time_ms": row.get("time_ms"),
            "killer_xuid": killer_xuid,
            "killer_gamertag": killer_gt,
            "victim_xuid": victim_xuid,
            "victim_gamertag": victim_gt,
            "type_hint": row.get("type_hint"),
            "raw_json": row.get("raw_json"),
            "created_at": now,
        })

    if not rows_v5:
        return 0

    if dry_run:
        return len(rows_v5)

    events_v5_df = pl.DataFrame(rows_v5)

    # Insérer dans shared (la colonne `id` est auto-générée via séquence)
    conn_shared.execute("""
        INSERT INTO highlight_events
            (match_id, event_type, time_ms,
             killer_xuid, killer_gamertag,
             victim_xuid, victim_gamertag,
             type_hint, raw_json, created_at)
        SELECT
            match_id, event_type, time_ms,
            killer_xuid, killer_gamertag,
            victim_xuid, victim_gamertag,
            type_hint, raw_json, created_at
        FROM events_v5_df
    """)

    # Mettre à jour events_loaded dans match_registry
    migrated_match_ids = list(match_ids_to_migrate)
    if migrated_match_ids:
        placeholders = ", ".join(["?"] * len(migrated_match_ids))
        conn_shared.execute(
            f"UPDATE match_registry SET events_loaded = TRUE "
            f"WHERE match_id IN ({placeholders})",
            migrated_match_ids,
        )

    if verbose:
        print(
            f"  🎬 {len(rows_v5)} events insérés "
            f"({len(match_ids_to_migrate)} matchs)"
        )

    return len(rows_v5)


# =============================================================================
# Migration des medals_earned
# =============================================================================


def _migrate_medals(
    conn_player: duckdb.DuckDBPyConnection,
    conn_shared: duckdb.DuckDBPyConnection,
    gamertag: str,
    xuid: str,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Migre medals_earned vers shared_matches (ajout colonne xuid).

    La table v4 n'a pas de colonne xuid (médailles implicitement liées au
    propriétaire de la DB). On injecte le xuid du profil.

    Returns:
        Nombre de médailles insérées.
    """
    try:
        medals_df = conn_player.execute("""
            SELECT match_id, medal_name_id, count
            FROM medals_earned
        """).pl()
    except duckdb.CatalogException:
        logger.warning(f"  Table medals_earned introuvable pour {gamertag}")
        return 0

    if medals_df.is_empty():
        return 0

    # Ajouter la colonne xuid + created_at
    now = datetime.now(timezone.utc)
    medals_df = medals_df.with_columns([
        pl.lit(xuid).alias("xuid"),
        pl.lit(now).alias("created_at"),
    ])

    # Réordonner pour correspondre au schéma v5 : match_id, xuid, medal_name_id, count, created_at
    medals_df = medals_df.select(["match_id", "xuid", "medal_name_id", "count", "created_at"])

    if dry_run:
        return len(medals_df)

    # Compter avant pour mesurer les insérés réels
    before_count = conn_shared.execute(
        "SELECT COUNT(*) FROM medals_earned"
    ).fetchone()[0]

    # INSERT OR IGNORE pour éviter doublons (match_id, xuid, medal_name_id)
    conn_shared.execute(
        "INSERT OR IGNORE INTO medals_earned SELECT * FROM medals_df"
    )

    after_count = conn_shared.execute(
        "SELECT COUNT(*) FROM medals_earned"
    ).fetchone()[0]
    count = after_count - before_count

    # Mettre à jour medals_loaded dans match_registry
    match_ids = medals_df["match_id"].unique().to_list()
    if match_ids:
        placeholders = ", ".join(["?"] * len(match_ids))
        conn_shared.execute(
            f"UPDATE match_registry SET medals_loaded = TRUE "
            f"WHERE match_id IN ({placeholders})",
            match_ids,
        )

    if verbose:
        print(f"  🏅 {count} médailles insérées (sur {len(medals_df)} totales)")

    return count


# =============================================================================
# Migration des xuid_aliases
# =============================================================================


def _migrate_xuid_aliases(
    conn_player: duckdb.DuckDBPyConnection,
    conn_shared: duckdb.DuckDBPyConnection,
    gamertag: str,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Migre xuid_aliases d'une DB joueur vers shared_matches.

    Utilise INSERT OR REPLACE pour mettre à jour les gamertags si plus récents.

    Returns:
        Nombre d'aliases migrés.
    """
    try:
        aliases_df = conn_player.execute("""
            SELECT xuid, gamertag, last_seen, source, updated_at
            FROM xuid_aliases
        """).pl()
    except duckdb.CatalogException:
        logger.info(f"  Table xuid_aliases introuvable pour {gamertag}")
        return 0

    if aliases_df.is_empty():
        return 0

    # Changer source pour traçabilité
    aliases_df = aliases_df.with_columns(
        pl.lit("migration").alias("source")
    )

    if dry_run:
        return len(aliases_df)

    # INSERT OR REPLACE pour upsert
    conn_shared.execute(
        "INSERT OR REPLACE INTO xuid_aliases SELECT * FROM aliases_df"
    )

    if verbose:
        print(f"  👤 {len(aliases_df)} aliases migrés")

    return len(aliases_df)


def _migrate_global_aliases_json(
    conn_shared: duckdb.DuckDBPyConnection,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Migre le fichier global data/xuid_aliases.json vers shared.xuid_aliases.

    Returns:
        Nombre d'aliases migrés.
    """
    if not XUID_ALIASES_JSON.exists():
        logger.info("  Fichier xuid_aliases.json introuvable, skip")
        return 0

    data = json.loads(XUID_ALIASES_JSON.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        return 0

    now = datetime.now(timezone.utc)
    rows = []
    for xuid_val, gt_val in data.items():
        if xuid_val and gt_val:
            rows.append({
                "xuid": str(xuid_val),
                "gamertag": str(gt_val),
                "last_seen": now,
                "source": "migration_json",
                "updated_at": now,
            })

    if not rows:
        return 0

    if dry_run:
        return len(rows)

    aliases_df = pl.DataFrame(rows)
    conn_shared.execute(
        "INSERT OR REPLACE INTO xuid_aliases SELECT * FROM aliases_df"
    )

    if verbose:
        print(f"  📁 {len(rows)} aliases importés depuis xuid_aliases.json")

    return len(rows)


# =============================================================================
# Recalcul des player_counts (post-migration)
# =============================================================================


def recalculate_player_counts(
    shared_db_path: Path = DEFAULT_SHARED_DB,
    profiles: dict[str, dict[str, str]] | None = None,
    *,
    verbose: bool = False,
) -> int:
    """Recalcule player_count dans match_registry depuis les données réelles.

    Pour chaque match, compte combien de joueurs trackés (dans db_profiles.json)
    ont ce match dans leur DB joueur, et met à jour player_count dans shared.

    Args:
        shared_db_path: Chemin vers shared_matches.duckdb.
        profiles: Profils joueurs (si None, chargé depuis db_profiles.json).
        verbose: Afficher le détail.

    Returns:
        Nombre de matchs mis à jour.
    """
    if profiles is None:
        profiles = load_profiles()

    # Compter les occurrences de chaque match_id dans les match_stats des joueurs
    match_counts: dict[str, int] = {}

    for _gt, profile in profiles.items():
        db_path_str = profile["db_path"]
        db_path = (
            Path(db_path_str) if Path(db_path_str).is_absolute()
            else PROJECT_ROOT / db_path_str
        )
        if not db_path.exists():
            continue

        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            match_ids = conn.execute(
                "SELECT match_id FROM match_stats"
            ).fetchall()
            for (mid,) in match_ids:
                match_counts[mid] = match_counts.get(mid, 0) + 1
        except Exception:
            pass
        finally:
            conn.close()

    if not match_counts:
        return 0

    conn_shared = duckdb.connect(str(shared_db_path))
    updated = 0

    try:
        counts_df = pl.DataFrame({
            "match_id": list(match_counts.keys()),
            "new_count": list(match_counts.values()),
        })
        conn_shared.execute(
            "CREATE TEMPORARY TABLE IF NOT EXISTS _tmp_counts "
            "(match_id VARCHAR, new_count SMALLINT)"
        )
        conn_shared.execute("DELETE FROM _tmp_counts")
        conn_shared.execute(
            "INSERT INTO _tmp_counts SELECT * FROM counts_df"
        )

        conn_shared.execute("""
            UPDATE match_registry
            SET player_count = (
                SELECT c.new_count FROM _tmp_counts c
                WHERE c.match_id = match_registry.match_id
            ),
            last_updated_at = CURRENT_TIMESTAMP
            WHERE match_id IN (SELECT match_id FROM _tmp_counts)
        """)
        updated = len(match_counts)

        conn_shared.execute("DROP TABLE IF EXISTS _tmp_counts")

    finally:
        conn_shared.close()

    if verbose:
        multi = sum(1 for c in match_counts.values() if c > 1)
        print(f"  📊 player_count recalculé: {updated} matchs, {multi} partagés")

    return updated


# =============================================================================
# Fonction principale de migration
# =============================================================================


def migrate_player_to_shared(
    gamertag: str,
    xuid: str,
    player_db_path: Path,
    shared_db_path: Path = DEFAULT_SHARED_DB,
    *,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict[str, int]:
    """Migre toutes les données d'un joueur vers shared_matches.duckdb.

    Args:
        gamertag: Gamertag du joueur.
        xuid: XUID du joueur.
        player_db_path: Chemin vers la DB joueur.
        shared_db_path: Chemin vers shared_matches.duckdb.
        dry_run: Si True, ne modifie rien.
        verbose: Si True, affiche le détail.

    Returns:
        Dictionnaire de statistiques de migration.
    """
    if not player_db_path.exists():
        raise FileNotFoundError(f"DB joueur introuvable : {player_db_path}")
    if not shared_db_path.exists():
        raise FileNotFoundError(
            f"DB partagée introuvable : {shared_db_path}\n"
            "Exécutez d'abord : python scripts/migration/create_shared_matches_db.py"
        )

    stats: dict[str, int] = {
        "matches_processed": 0,
        "matches_new": 0,
        "matches_existing": 0,
        "participants_inserted": 0,
        "events_inserted": 0,
        "medals_inserted": 0,
        "aliases_inserted": 0,
    }

    prefix = "[DRY-RUN] " if dry_run else ""
    print(f"\n{'='*60}")
    print(f"{prefix}Migration de {gamertag} (xuid={xuid})")
    print(f"  Source : {player_db_path}")
    print(f"  Cible  : {shared_db_path}")
    print(f"{'='*60}")

    conn_player = duckdb.connect(str(player_db_path), read_only=True)
    conn_shared = duckdb.connect(str(shared_db_path), read_only=dry_run)

    try:
        t0 = time.time()

        # 1. Match Registry
        print(f"\n{prefix}[1/5] Migration match_registry...")
        registry_stats = _migrate_match_registry(
            conn_player, conn_shared, gamertag,
            dry_run=dry_run, verbose=verbose,
        )
        stats.update(registry_stats)
        print(
            f"  → {registry_stats['matches_new']} nouveaux, "
            f"{registry_stats['matches_existing']} existants "
            f"(total: {registry_stats['matches_processed']})"
        )

        # 2. Match Participants
        print(f"\n{prefix}[2/5] Migration match_participants...")
        stats["participants_inserted"] = _migrate_participants(
            conn_player, conn_shared, gamertag,
            dry_run=dry_run, verbose=verbose,
        )

        # 3. Highlight Events
        print(f"\n{prefix}[3/5] Migration highlight_events...")
        stats["events_inserted"] = _migrate_highlight_events(
            conn_player, conn_shared, gamertag,
            dry_run=dry_run, verbose=verbose,
        )

        # 4. Medals
        print(f"\n{prefix}[4/5] Migration medals_earned...")
        stats["medals_inserted"] = _migrate_medals(
            conn_player, conn_shared, gamertag, xuid,
            dry_run=dry_run, verbose=verbose,
        )

        # 5. XUID Aliases
        print(f"\n{prefix}[5/5] Migration xuid_aliases...")
        stats["aliases_inserted"] = _migrate_xuid_aliases(
            conn_player, conn_shared, gamertag,
            dry_run=dry_run, verbose=verbose,
        )

        elapsed = time.time() - t0

        print(f"\n{'─'*60}")
        print(f"{prefix}Migration de {gamertag} terminée en {elapsed:.1f}s")
        print(f"  Matchs      : {stats['matches_new']} nouveaux + {stats['matches_existing']} existants")
        print(f"  Participants: {stats['participants_inserted']}")
        print(f"  Events      : {stats['events_inserted']}")
        print(f"  Médailles   : {stats['medals_inserted']}")
        print(f"  Aliases     : {stats['aliases_inserted']}")

    finally:
        conn_player.close()
        conn_shared.close()

    return stats


def migrate_all_players(
    shared_db_path: Path = DEFAULT_SHARED_DB,
    *,
    dry_run: bool = False,
    verbose: bool = True,
    include_global_aliases: bool = True,
) -> dict[str, dict[str, int]]:
    """Migre tous les joueurs de db_profiles.json vers shared_matches.

    Ordre de migration : Chocoboflor (référence) → Madina → JGtm → XxDaemonGamerxX.

    Returns:
        Dictionnaire {gamertag: stats} pour chaque joueur.
    """
    profiles = load_profiles()

    # Ordre de migration déterministe
    migration_order = ["Chocoboflor", "Madina97294", "JGtm", "XxDaemonGamerxX"]
    # Filtrer les joueurs présents dans les profils
    ordered_gamertags = [gt for gt in migration_order if gt in profiles]
    # Ajouter les joueurs non listés dans l'ordre prédéfini
    for gt in profiles:
        if gt not in ordered_gamertags:
            ordered_gamertags.append(gt)

    all_stats: dict[str, dict[str, int]] = {}

    # Migration du fichier global xuid_aliases.json en premier
    if include_global_aliases:
        print("\n📁 Import des aliases globaux (xuid_aliases.json)...")
        conn_shared = duckdb.connect(str(shared_db_path), read_only=dry_run)
        try:
            _migrate_global_aliases_json(
                conn_shared, dry_run=dry_run, verbose=verbose,
            )
        finally:
            conn_shared.close()

    for gt in ordered_gamertags:
        profile = profiles[gt]
        xuid = profile["xuid"]
        db_path = PROJECT_ROOT / profile["db_path"]

        if not db_path.exists():
            logger.warning(f"DB introuvable pour {gt} : {db_path}, skip")
            continue

        try:
            player_stats = migrate_player_to_shared(
                gamertag=gt,
                xuid=xuid,
                player_db_path=db_path,
                shared_db_path=shared_db_path,
                dry_run=dry_run,
                verbose=verbose,
            )
            all_stats[gt] = player_stats
        except Exception as exc:
            logger.error(f"Erreur migration {gt} : {exc}")
            all_stats[gt] = {"error": str(exc)}  # type: ignore[dict-item]

    # Résumé global
    print(f"\n{'='*60}")
    print("RÉSUMÉ GLOBAL DE LA MIGRATION")
    print(f"{'='*60}")

    total_new = sum(s.get("matches_new", 0) for s in all_stats.values() if isinstance(s.get("matches_new"), int))
    total_existing = sum(s.get("matches_existing", 0) for s in all_stats.values() if isinstance(s.get("matches_existing"), int))
    total_participants = sum(s.get("participants_inserted", 0) for s in all_stats.values() if isinstance(s.get("participants_inserted"), int))
    total_events = sum(s.get("events_inserted", 0) for s in all_stats.values() if isinstance(s.get("events_inserted"), int))
    total_medals = sum(s.get("medals_inserted", 0) for s in all_stats.values() if isinstance(s.get("medals_inserted"), int))

    for gt, s in all_stats.items():
        if "error" in s:
            print(f"  ❌ {gt}: ERREUR — {s['error']}")
        else:
            print(
                f"  ✅ {gt}: {s.get('matches_new',0)} new + "
                f"{s.get('matches_existing',0)} existing = "
                f"{s.get('matches_processed',0)} total"
            )

    print(f"\n  Total matchs shared : {total_new} uniques")
    print(f"  Total participants  : {total_participants}")
    print(f"  Total events        : {total_events}")
    print(f"  Total médailles     : {total_medals}")
    print(f"  Taux de partage     : {total_existing}/{total_existing + total_new:.0f} = "
          f"{total_existing / max(total_existing + total_new, 1) * 100:.1f}%")

    # Recalculer player_counts à partir des données réelles
    if not dry_run:
        print("\n📊 Recalcul des player_counts...")
        recalculate_player_counts(
            shared_db_path, profiles=profiles, verbose=True,
        )

    return all_stats


# =============================================================================
# CLI
# =============================================================================


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(
        description="Migre les données joueur vers shared_matches.duckdb"
    )
    parser.add_argument(
        "gamertag",
        nargs="?",
        help="Gamertag du joueur à migrer (ou --all pour tous)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrer tous les joueurs de db_profiles.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Afficher ce qui serait fait sans modifier la DB",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Afficher le détail match par match",
    )
    parser.add_argument(
        "--shared-db",
        type=Path,
        default=DEFAULT_SHARED_DB,
        help=f"Chemin vers shared_matches.duckdb (défaut: {DEFAULT_SHARED_DB})",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.all:
        migrate_all_players(
            shared_db_path=args.shared_db,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    elif args.gamertag:
        profiles = load_profiles()
        if args.gamertag not in profiles:
            print(f"❌ Gamertag '{args.gamertag}' non trouvé dans db_profiles.json")
            print(f"   Joueurs disponibles : {', '.join(profiles.keys())}")
            sys.exit(1)

        profile = profiles[args.gamertag]
        player_db = PROJECT_ROOT / profile["db_path"]

        migrate_player_to_shared(
            gamertag=args.gamertag,
            xuid=profile["xuid"],
            player_db_path=player_db,
            shared_db_path=args.shared_db,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
