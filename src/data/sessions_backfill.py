"""Logique de backfill des sessions (sans Streamlit).

Utilisé par scripts/backfill_data.py --sessions pour charger les amis
et calculer/stocker session_id et session_label dans match_stats.
"""

from __future__ import annotations

import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import polars as pl


def get_friends_xuids_for_backfill(
    db_path: str | Path,
    self_xuid: str,
    *,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> frozenset[str]:
    """Charge les XUIDs des amis pour le backfill (sans Streamlit).

    Source : .streamlit/friends_defaults.json (format {xuid: [gamertag1, gamertag2, ...]})
    Résolution gamertag → XUID via xuid_aliases dans la DB.

    Args:
        db_path: Chemin vers la DB.
        self_xuid: XUID du joueur.
        conn: Connexion existante (évite conflit DuckDB multi-connexions). Si None, ouvre une nouvelle.

    Returns:
        Set des XUIDs des amis. Vide si pas de config ou résolution échouée.
    """
    path = Path(db_path)
    if not path.exists():
        return frozenset()

    # Charger friends_defaults.json
    friends_json = Path(__file__).resolve().parents[2] / ".streamlit" / "friends_defaults.json"
    if not friends_json.exists():
        return frozenset()

    try:
        with open(friends_json, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return frozenset()

    if not isinstance(data, dict):
        return frozenset()

    friends_raw = data.get(str(self_xuid).strip())
    if not friends_raw or not isinstance(friends_raw, list):
        return frozenset()

    own_conn = False
    if conn is None:
        conn = duckdb.connect(str(path), read_only=True)
        own_conn = True
    try:
        result = conn.execute(
            "SELECT xuid, gamertag FROM xuid_aliases WHERE xuid IS NOT NULL AND gamertag IS NOT NULL"
        ).fetchall()
        gamertag_to_xuid: dict[str, str] = {}
        for xuid, gamertag in result:
            if xuid and gamertag:
                gamertag_to_xuid[str(gamertag).strip().casefold()] = str(xuid).strip()

        xuids: set[str] = set()
        known_xuids = {
            str(r[0]).strip()
            for r in conn.execute(
                "SELECT DISTINCT xuid FROM xuid_aliases WHERE xuid IS NOT NULL"
            ).fetchall()
            if r[0]
        }

        for ident in friends_raw:
            s = str(ident or "").strip()
            if not s:
                continue
            # ~prefix = ami inactif, exclu des sessions par défaut
            if s.startswith("~"):
                continue
            if s.isdigit() and s in known_xuids:
                xuids.add(s)
                continue
            xu = gamertag_to_xuid.get(s.casefold())
            if xu:
                xuids.add(xu)
        return frozenset(xuids)
    finally:
        if own_conn:
            conn.close()


def get_top_two_teammate_xuids(
    db_path: str | Path,
    self_xuid: str,
    limit: int = 2,
    *,
    conn: duckdb.DuckDBPyConnection | None = None,
) -> frozenset[str]:
    """Top N coéquipiers depuis shared.match_participants."""
    path = Path(db_path)
    if not path.exists():
        return frozenset()

    # Trouver shared_matches.duckdb
    shared_db = path.parent.parent.parent / "warehouse" / "shared_matches.duckdb"
    if not shared_db.exists():
        return frozenset()

    own_conn = False
    if conn is None:
        conn = duckdb.connect(str(path), read_only=True)
        own_conn = True
    try:
        # Attacher shared en read-only
        with contextlib.suppress(Exception):
            conn.execute(
                "ATTACH ? AS shared_tmp (READ_ONLY)",
                [str(shared_db)],
            )

        result = conn.execute(
            """
            SELECT mp2.xuid, COUNT(DISTINCT mp2.match_id) AS match_count
            FROM shared_tmp.match_participants mp1
            JOIN shared_tmp.match_participants mp2
              ON mp1.match_id = mp2.match_id
             AND mp1.xuid != mp2.xuid
             AND mp1.team_id = mp2.team_id
            WHERE mp1.xuid = ?
            GROUP BY mp2.xuid
            ORDER BY match_count DESC
            LIMIT ?
            """,
            [str(self_xuid).strip(), limit],
        ).fetchall()

        with contextlib.suppress(Exception):
            conn.execute("DETACH shared_tmp")

        return frozenset(str(r[0]).strip() for r in result if r[0])
    except Exception:
        return frozenset()
    finally:
        if own_conn:
            conn.close()


def backfill_sessions_for_player(
    db_path: Path | str,
    xuid: str | None = None,
    *,
    conn: duckdb.DuckDBPyConnection | None = None,
    gap_minutes: int = 120,
    include_recent: bool = True,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Backfill session_id et session_label pour une DB joueur.

    Appelé par scripts/backfill_data.py --sessions.

    Args:
        db_path: Chemin vers la DB joueur.
        xuid: XUID du joueur (résolu depuis xuid_aliases si None).
        conn: Connexion existante (obligatoire si appelé depuis backfill_data.py qui a déjà une conn ouverte).
        gap_minutes, include_recent, force, dry_run: Options de backfill.

    Returns:
        Dict avec updated, skipped_recent, errors.
    """
    from src.analysis.sessions import compute_sessions_with_context_polars
    from src.config import SESSION_CONFIG

    path = Path(db_path)
    results: dict[str, Any] = {
        "updated": 0,
        "skipped_recent": 0,
        "errors": [],
    }
    stability_hours = SESSION_CONFIG.session_stability_hours

    if not path.exists():
        results["errors"].append("DB non trouvée")
        return results

    own_conn = False
    if conn is None:
        conn = duckdb.connect(str(path))
        own_conn = True

    try:
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = 'match_stats'"
        ).fetchall()
        col_names = {r[0] for r in cols} if cols else set()
        if "session_id" not in col_names:
            with contextlib.suppress(Exception):
                conn.execute("ALTER TABLE match_stats ADD COLUMN session_id INTEGER")
        if "session_label" not in col_names:
            with contextlib.suppress(Exception):
                conn.execute("ALTER TABLE match_stats ADD COLUMN session_label VARCHAR")

        if not xuid:
            row = conn.execute(
                "SELECT DISTINCT xuid FROM xuid_aliases WHERE xuid IS NOT NULL LIMIT 1"
            ).fetchone()
            xuid = str(row[0]).strip() if row and row[0] else None
        if not xuid:
            results["errors"].append("XUID non trouvé")
            return results

        friends = get_friends_xuids_for_backfill(path, xuid, conn=conn)
        if not friends:
            friends = get_top_two_teammate_xuids(path, xuid, limit=2, conn=conn)

        df = conn.execute("""
            SELECT match_id, start_time, teammates_signature, session_id
            FROM match_stats
            WHERE start_time IS NOT NULL
            ORDER BY start_time ASC
        """).pl()

        if df.is_empty():
            return results

        if not force:
            has_null = df.filter(pl.col("session_id").is_null())
            if has_null.is_empty():
                return results

        df_sessions = compute_sessions_with_context_polars(
            df.select(["match_id", "start_time", "teammates_signature"]),
            gap_minutes=gap_minutes,
            friends_xuids=friends if friends else None,
        )

        now = datetime.now(timezone.utc)
        threshold = now.timestamp() - (stability_hours * 3600)
        df_sessions = df_sessions.with_columns(
            pl.col("start_time").dt.epoch(time_unit="s").alias("_ts")
        )

        if dry_run:
            to_update = df_sessions.filter(~pl.col("_ts").is_null())
            if not include_recent:
                to_update = to_update.filter(pl.col("_ts") <= threshold)
            results["updated"] = len(to_update)
            return results

        updated = 0
        skipped = 0
        for row in df_sessions.iter_rows(named=True):
            match_id = row["match_id"]
            session_id = row["session_id"]
            session_label = row["session_label"]
            st_ts = row.get("_ts")

            if st_ts is None:
                continue
            if not include_recent and st_ts > threshold:
                skipped += 1
                continue

            try:
                conn.execute(
                    "UPDATE match_stats SET session_id = ?, session_label = ? WHERE match_id = ?",
                    [session_id, str(session_label) if session_label else None, match_id],
                )
                updated += 1
            except Exception as e:
                results["errors"].append(f"{match_id}: {e}")

        results["updated"] = updated
        results["skipped_recent"] = skipped
        conn.commit()

    finally:
        if own_conn:
            conn.close()

    return results
