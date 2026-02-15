"""Crée des VIEWs de compatibilité dans les DBs joueur.

Après la migration vers shared_matches.duckdb, les DBs joueur sont simplifiées.
Ce script crée des VIEWs qui émulent l'ancien schéma (match_stats, medals_earned,
highlight_events) en lisant les données depuis shared_matches.duckdb via ATTACH.

Objectif : permettre à l'UI et au code existant de fonctionner sans modification
pendant la période de transition (Sprint 5).

Usage :
    python scripts/migration/create_compat_views.py [gamertag] [--all] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_SHARED_DB = PROJECT_ROOT / "data" / "warehouse" / "shared_matches.duckdb"
PROFILES_PATH = PROJECT_ROOT / "db_profiles.json"

logger = logging.getLogger(__name__)


def load_profiles() -> dict[str, dict[str, str]]:
    """Charge db_profiles.json."""
    data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    return data.get("profiles", {})


# =============================================================================
# Définitions des VIEWs de compatibilité
# =============================================================================

# Vue qui reconstruit match_stats depuis shared + player enrichment
COMPAT_VIEW_MATCH_STATS = """
CREATE OR REPLACE VIEW v_match_stats AS
SELECT
    r.match_id,
    r.start_time,
    r.end_time,
    r.playlist_id,
    r.playlist_name,
    r.map_id,
    r.map_name,
    r.pair_id,
    r.pair_name,
    r.game_variant_id,
    r.game_variant_name,
    r.mode_category,
    r.is_ranked,
    r.is_firefight,
    r.duration_seconds AS time_played_seconds,
    r.team_0_score AS my_team_score,
    r.team_1_score AS enemy_team_score,
    -- Données du joueur depuis match_participants
    p.outcome,
    p.team_id,
    p.rank,
    p.kills,
    p.deaths,
    p.assists,
    p.score,
    p.shots_fired,
    p.shots_hit,
    p.damage_dealt,
    p.damage_taken,
    p.avg_life_seconds,
    -- Données enrichies depuis la DB locale
    COALESCE(e.performance_score, NULL) AS performance_score,
    COALESCE(e.session_id, NULL) AS session_id,
    COALESCE(e.session_label, NULL) AS session_label,
    COALESCE(e.is_with_friends, NULL) AS is_with_friends
FROM shared.match_registry r
JOIN shared.match_participants p
    ON r.match_id = p.match_id AND p.xuid = '{xuid}'
LEFT JOIN player_match_enrichment e
    ON r.match_id = e.match_id
ORDER BY r.start_time DESC
"""

# Vue pour medals_earned (reconstruit le schéma v4 sans xuid)
COMPAT_VIEW_MEDALS = """
CREATE OR REPLACE VIEW v_medals_earned AS
SELECT
    m.match_id,
    m.medal_name_id,
    m.count
FROM shared.medals_earned m
WHERE m.xuid = '{xuid}'
"""

# Vue pour highlight_events (reconstruit le schéma v4 avec xuid/gamertag simples)
COMPAT_VIEW_EVENTS = """
CREATE OR REPLACE VIEW v_highlight_events AS
SELECT
    e.id,
    e.match_id,
    e.event_type,
    e.time_ms,
    CASE
        WHEN UPPER(e.event_type) = 'KILL' THEN e.killer_xuid
        WHEN UPPER(e.event_type) = 'DEATH' THEN e.victim_xuid
        ELSE e.killer_xuid
    END AS xuid,
    CASE
        WHEN UPPER(e.event_type) = 'KILL' THEN e.killer_gamertag
        WHEN UPPER(e.event_type) = 'DEATH' THEN e.victim_gamertag
        ELSE e.killer_gamertag
    END AS gamertag,
    e.type_hint,
    e.raw_json
FROM shared.highlight_events e
"""

# Vue pour match_participants depuis shared
COMPAT_VIEW_PARTICIPANTS = """
CREATE OR REPLACE VIEW v_match_participants AS
SELECT
    p.match_id,
    p.xuid,
    p.gamertag,
    p.team_id,
    p.outcome,
    p.rank,
    p.score,
    p.kills,
    p.deaths,
    p.assists,
    p.shots_fired,
    p.shots_hit,
    p.damage_dealt,
    p.damage_taken
FROM shared.match_participants p
"""


def create_enrichment_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Crée la table player_match_enrichment si elle n'existe pas.

    Cette table stocke les données personnelles calculées (performance_score,
    session_id, is_with_friends) qui restent dans la DB joueur.
    """
    conn.execute("""
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
    """)


def populate_enrichment_from_match_stats(
    conn: duckdb.DuckDBPyConnection,
) -> int:
    """Copie les données d'enrichissement depuis match_stats vers player_match_enrichment.

    Returns:
        Nombre de lignes insérées.
    """
    # Vérifier si match_stats existe
    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()
    table_names = {r[0] for r in tables}

    if "match_stats" not in table_names:
        return 0

    conn.execute("""
        INSERT OR IGNORE INTO player_match_enrichment
            (match_id, performance_score, session_id, session_label,
             is_with_friends, teammates_signature, known_teammates_count, friends_xuids)
        SELECT
            match_id,
            performance_score,
            session_id,
            session_label,
            is_with_friends,
            teammates_signature,
            known_teammates_count,
            friends_xuids
        FROM match_stats
        WHERE performance_score IS NOT NULL
           OR session_id IS NOT NULL
           OR is_with_friends IS NOT NULL
    """)

    count = conn.execute("SELECT COUNT(*) FROM player_match_enrichment").fetchone()
    return count[0] if count else 0


def create_compat_views(
    gamertag: str,
    xuid: str,
    player_db_path: Path,
    shared_db_path: Path = DEFAULT_SHARED_DB,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, bool]:
    """Crée les VIEWs de compatibilité dans la DB joueur.

    Args:
        gamertag: Gamertag du joueur.
        xuid: XUID du joueur.
        player_db_path: Chemin vers la DB joueur.
        shared_db_path: Chemin vers shared_matches.duckdb.
        dry_run: Si True, affiche les SQL sans exécuter.
        verbose: Afficher le détail.

    Returns:
        Dict {view_name: success}.
    """
    results: dict[str, bool] = {}

    if not player_db_path.exists():
        raise FileNotFoundError(f"DB joueur introuvable : {player_db_path}")

    conn = duckdb.connect(str(player_db_path))

    try:
        # 1. ATTACH shared_matches.duckdb
        attach_sql = f"ATTACH '{shared_db_path}' AS shared (READ_ONLY)"

        if dry_run:
            print(f"  [DRY-RUN] {attach_sql}")
        else:
            try:
                conn.execute(attach_sql)
            except duckdb.CatalogException:
                # Déjà attachée
                pass

        # 2. Créer la table d'enrichissement et la peupler
        if not dry_run:
            create_enrichment_table(conn)
            enrichment_count = populate_enrichment_from_match_stats(conn)
            if verbose:
                print(f"  📝 {enrichment_count} lignes d'enrichissement copiées")
            results["player_match_enrichment"] = True

        # 3. Créer les VIEWs
        views = {
            "v_match_stats": COMPAT_VIEW_MATCH_STATS.format(xuid=xuid),
            "v_medals_earned": COMPAT_VIEW_MEDALS.format(xuid=xuid),
            "v_highlight_events": COMPAT_VIEW_EVENTS,
            "v_match_participants": COMPAT_VIEW_PARTICIPANTS,
        }

        for view_name, view_sql in views.items():
            if dry_run:
                print(f"\n  [DRY-RUN] Création de {view_name}:")
                print(f"  {view_sql[:120]}...")
                results[view_name] = True
            else:
                try:
                    conn.execute(view_sql)
                    results[view_name] = True
                    if verbose:
                        print(f"  ✅ Vue {view_name} créée")
                except Exception as exc:
                    results[view_name] = False
                    logger.error(f"  ❌ Vue {view_name} : {exc}")

    finally:
        conn.close()

    return results


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(
        description="Crée les VIEWs de compatibilité v5 dans les DBs joueur"
    )
    parser.add_argument("gamertag", nargs="?", help="Gamertag cible")
    parser.add_argument("--all", action="store_true", help="Tous les joueurs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument(
        "--shared-db",
        type=Path,
        default=DEFAULT_SHARED_DB,
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8")).get("profiles", {})

    if args.all:
        gamertags = list(profiles.keys())
    elif args.gamertag:
        if args.gamertag not in profiles:
            print(f"❌ Gamertag '{args.gamertag}' inconnu")
            sys.exit(1)
        gamertags = [args.gamertag]
    else:
        parser.print_help()
        sys.exit(1)

    for gt in gamertags:
        profile = profiles[gt]
        xuid = profile["xuid"]
        db_path = PROJECT_ROOT / profile["db_path"]

        print(f"\n{'='*50}")
        print(f"VIEWs de compatibilité pour {gt}")
        print(f"{'='*50}")

        results = create_compat_views(
            gamertag=gt,
            xuid=xuid,
            player_db_path=db_path,
            shared_db_path=args.shared_db,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        ok = sum(1 for v in results.values() if v)
        total = len(results)
        print(f"  → {ok}/{total} VIEWs créées avec succès")


if __name__ == "__main__":
    main()
