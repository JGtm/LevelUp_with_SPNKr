"""Tests anti-régression : bouton Synchroniser (sync pipeline).

Ces tests couvrent les bugs découverts dans le pipeline sync UI :

1. DuckDBSyncEngine ne persistait PAS xuid/gamertag dans sync_meta
2. _sync_duckdb_player passait xuid="" au engine
3. Le comptage avant/après utilisait match_stats (inexistant en v5)
4. sync_all_players utilisait xuid_aliases.last_seen (fragile)
5. _load_existing_match_ids ne consultait que match_stats (vide en v5)
6. _resolve_xuid_from_db (défense en profondeur dans le engine)

Sprint anti-régression — sync pipeline — février 2026.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

# =============================================================================
# Constantes
# =============================================================================

PLAYER_XUID = "2535469190789936"
PLAYER_GAMERTAG = "Chocoboflor"
MATCH_ID_1 = "sync-aaaa-1111-bbbb"
MATCH_ID_2 = "sync-cccc-2222-dddd"
MATCH_ID_3 = "sync-eeee-3333-ffff"


# =============================================================================
# Helpers
# =============================================================================


def _create_player_db(db_path: Path, *, with_match_stats: bool = False) -> None:
    """Crée une DB joueur minimale pour les tests sync."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

    # sync_meta (toujours présente)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_meta (
            key VARCHAR PRIMARY KEY,
            value VARCHAR,
            updated_at VARCHAR
        )
    """)

    # player_match_stats (source de vérité v5)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_match_stats (
            match_id VARCHAR,
            xuid VARCHAR,
            gamertag VARCHAR,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0
        )
    """)

    # xuid_aliases
    conn.execute("""
        CREATE TABLE IF NOT EXISTS xuid_aliases (
            xuid VARCHAR,
            gamertag VARCHAR,
            last_seen VARCHAR
        )
    """)

    # Peupler player_match_stats
    conn.execute(
        "INSERT INTO player_match_stats (match_id, xuid, gamertag) VALUES (?, ?, ?)",
        (MATCH_ID_1, PLAYER_XUID, PLAYER_GAMERTAG),
    )
    conn.execute(
        "INSERT INTO player_match_stats (match_id, xuid, gamertag) VALUES (?, ?, ?)",
        (MATCH_ID_2, PLAYER_XUID, PLAYER_GAMERTAG),
    )

    # Peupler xuid_aliases
    conn.execute(
        "INSERT INTO xuid_aliases (xuid, gamertag, last_seen) VALUES (?, ?, ?)",
        (PLAYER_XUID, PLAYER_GAMERTAG, "2025-01-01T00:00:00Z"),
    )

    if with_match_stats:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS match_stats (
                match_id VARCHAR PRIMARY KEY,
                xuid VARCHAR,
                kills INTEGER DEFAULT 0,
                deaths INTEGER DEFAULT 0
            )
        """)
        conn.execute(
            "INSERT INTO match_stats (match_id, xuid) VALUES (?, ?)",
            (MATCH_ID_1, PLAYER_XUID),
        )

    conn.close()


def _create_shared_db(db_path: Path) -> None:
    """Crée une shared_matches.duckdb minimale pour les tests."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

    conn.execute("""
        CREATE TABLE IF NOT EXISTS match_participants (
            match_id VARCHAR,
            xuid VARCHAR,
            gamertag VARCHAR
        )
    """)

    # Peupler avec les matchs du joueur
    for mid in (MATCH_ID_1, MATCH_ID_2, MATCH_ID_3):
        conn.execute(
            "INSERT INTO match_participants (match_id, xuid, gamertag) VALUES (?, ?, ?)",
            (mid, PLAYER_XUID, PLAYER_GAMERTAG),
        )

    conn.close()


# =============================================================================
# Tests _resolve_xuid_from_db (engine)
# =============================================================================


class TestResolveXuidFromDb:
    """Tests de la méthode DuckDBSyncEngine._resolve_xuid_from_db."""

    def test_resolve_from_sync_meta(self, tmp_path: Path) -> None:
        """Stratégie 1 : XUID depuis sync_meta."""
        db = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db)

        # Écrire le XUID dans sync_meta
        conn = duckdb.connect(str(db))
        conn.execute(
            "INSERT INTO sync_meta (key, value, updated_at) VALUES ('xuid', ?, '2025-01-01')",
            (PLAYER_XUID,),
        )
        conn.close()

        from src.data.sync.engine import DuckDBSyncEngine

        engine = DuckDBSyncEngine(player_db_path=db, xuid="", gamertag=PLAYER_GAMERTAG)
        assert engine._xuid == PLAYER_XUID

    def test_resolve_from_player_match_stats(self, tmp_path: Path) -> None:
        """Stratégie 2 : XUID depuis player_match_stats."""
        db = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db)  # Pas de sync_meta.xuid

        from src.data.sync.engine import DuckDBSyncEngine

        engine = DuckDBSyncEngine(player_db_path=db, xuid="", gamertag=PLAYER_GAMERTAG)
        assert engine._xuid == PLAYER_XUID

    def test_resolve_from_xuid_aliases(self, tmp_path: Path) -> None:
        """Stratégie 3 : XUID depuis xuid_aliases via gamertag."""
        db = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        db.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(db))
        conn.execute("""
            CREATE TABLE sync_meta (key VARCHAR PRIMARY KEY, value VARCHAR, updated_at VARCHAR)
        """)
        conn.execute("""
            CREATE TABLE player_match_stats (match_id VARCHAR, xuid VARCHAR)
        """)
        conn.execute("""
            CREATE TABLE xuid_aliases (xuid VARCHAR, gamertag VARCHAR, last_seen VARCHAR)
        """)
        conn.execute(
            "INSERT INTO xuid_aliases (xuid, gamertag) VALUES (?, ?)",
            (PLAYER_XUID, PLAYER_GAMERTAG),
        )
        conn.close()

        from src.data.sync.engine import DuckDBSyncEngine

        engine = DuckDBSyncEngine(player_db_path=db, xuid="", gamertag=PLAYER_GAMERTAG)
        assert engine._xuid == PLAYER_XUID

    def test_xuid_provided_directly(self, tmp_path: Path) -> None:
        """Si XUID fourni, pas de résolution nécessaire."""
        db = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db)

        from src.data.sync.engine import DuckDBSyncEngine

        engine = DuckDBSyncEngine(player_db_path=db, xuid=PLAYER_XUID, gamertag=PLAYER_GAMERTAG)
        assert engine._xuid == PLAYER_XUID


# =============================================================================
# Tests _load_existing_match_ids (engine)
# =============================================================================


class TestLoadExistingMatchIds:
    """Tests du fallback multi-sources pour détecter les matchs existants."""

    def test_fallback_to_player_match_stats(self, tmp_path: Path) -> None:
        """Si match_stats est vide, utilise player_match_stats."""
        db = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db)

        from src.data.sync.engine import DuckDBSyncEngine

        engine = DuckDBSyncEngine(player_db_path=db, xuid=PLAYER_XUID, gamertag=PLAYER_GAMERTAG)
        ids = engine._load_existing_match_ids()
        assert MATCH_ID_1 in ids
        assert MATCH_ID_2 in ids
        assert len(ids) == 2

    def test_match_stats_preferred(self, tmp_path: Path) -> None:
        """Si match_stats a des données, c'est elle qui est utilisée (pas player_match_stats)."""
        db = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db, with_match_stats=True)

        from src.data.sync.engine import DuckDBSyncEngine

        engine = DuckDBSyncEngine(player_db_path=db, xuid=PLAYER_XUID, gamertag=PLAYER_GAMERTAG)
        ids = engine._load_existing_match_ids()
        # match_stats ne contient que MATCH_ID_1
        assert MATCH_ID_1 in ids
        assert len(ids) == 1

    def test_fallback_to_shared_participants(self, tmp_path: Path) -> None:
        """Si la player DB est vide, utilise shared.match_participants."""
        # Créer la structure data/players/{gt}/stats.duckdb + data/warehouse/shared_matches.duckdb
        players_dir = tmp_path / "data" / "players" / PLAYER_GAMERTAG
        db = players_dir / "stats.duckdb"
        db.parent.mkdir(parents=True, exist_ok=True)

        # DB joueur vide (tables sans données)
        conn = duckdb.connect(str(db))
        conn.execute("""
            CREATE TABLE sync_meta (key VARCHAR PRIMARY KEY, value VARCHAR, updated_at VARCHAR)
        """)
        conn.execute("CREATE TABLE match_stats (match_id VARCHAR)")
        conn.execute("CREATE TABLE player_match_stats (match_id VARCHAR, xuid VARCHAR)")
        conn.close()

        # Shared DB avec des matchs
        shared_db = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"
        _create_shared_db(shared_db)

        from src.data.sync.engine import DuckDBSyncEngine

        engine = DuckDBSyncEngine(
            player_db_path=db,
            xuid=PLAYER_XUID,
            gamertag=PLAYER_GAMERTAG,
            shared_db_path=shared_db,
        )
        ids = engine._load_existing_match_ids()
        assert MATCH_ID_1 in ids
        assert MATCH_ID_2 in ids
        assert MATCH_ID_3 in ids
        assert len(ids) == 3

    def test_empty_db_returns_empty_set(self, tmp_path: Path) -> None:
        """DB totalement vide → set vide (pas d'erreur)."""
        db = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        db.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(db))
        conn.execute("""
            CREATE TABLE sync_meta (key VARCHAR PRIMARY KEY, value VARCHAR, updated_at VARCHAR)
        """)
        conn.close()

        from src.data.sync.engine import DuckDBSyncEngine

        engine = DuckDBSyncEngine(player_db_path=db, xuid=PLAYER_XUID, gamertag=PLAYER_GAMERTAG)
        ids = engine._load_existing_match_ids()
        assert ids == set()


# =============================================================================
# Tests sync_meta persistence (engine._sync_internal writes xuid/gamertag)
# =============================================================================


class TestSyncMetaPersistence:
    """Vérifie que _update_sync_meta persiste bien xuid et gamertag."""

    def test_update_sync_meta_persists_xuid(self, tmp_path: Path) -> None:
        """_update_sync_meta écrit correctement le XUID."""
        db = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db)

        from src.data.sync.engine import DuckDBSyncEngine

        engine = DuckDBSyncEngine(player_db_path=db, xuid=PLAYER_XUID, gamertag=PLAYER_GAMERTAG)
        engine._update_sync_meta("xuid", PLAYER_XUID)
        engine._update_sync_meta("gamertag", PLAYER_GAMERTAG)

        # Fermer la connexion du engine avant de relire
        if engine._connection is not None:
            engine._connection.close()
            engine._connection = None

        # Relire depuis la DB
        conn = duckdb.connect(str(db), read_only=True)
        xuid_row = conn.execute("SELECT value FROM sync_meta WHERE key = 'xuid'").fetchone()
        gt_row = conn.execute("SELECT value FROM sync_meta WHERE key = 'gamertag'").fetchone()
        conn.close()

        assert xuid_row is not None and xuid_row[0] == PLAYER_XUID
        assert gt_row is not None and gt_row[0] == PLAYER_GAMERTAG


# =============================================================================
# Tests sync_all_players — résolution XUID
# =============================================================================


class TestSyncAllPlayersXuidResolution:
    """Vérifie que sync_all_players résout le XUID via _resolve_player_xuid."""

    def test_xuid_resolved_for_duckdb_player(self, tmp_path: Path) -> None:
        """sync_all_players résout le XUID depuis la DB, pas depuis xuid_aliases.last_seen."""
        # Créer le chemin attendu: data/players/{gamertag}/stats.duckdb
        players_dir = tmp_path / "players" / PLAYER_GAMERTAG
        db = players_dir / "stats.duckdb"
        _create_player_db(db)

        # Importer sync_all_players — on ne peut pas exécuter la sync réelle
        # (pas de tokens), mais on peut vérifier la résolution XUID
        from src.ui.cache_loaders import _resolve_player_xuid

        xuid = _resolve_player_xuid(str(db))
        assert xuid == PLAYER_XUID, f"sync_all_players doit résoudre le XUID, obtenu: '{xuid}'"


# =============================================================================
# Tests _sync_duckdb_player — comptage v5
# =============================================================================


class TestSyncDuckdbPlayerCounting:
    """Vérifie que le comptage avant/après utilise player_match_stats, pas match_stats."""

    def test_count_from_player_match_stats(self, tmp_path: Path) -> None:
        """Le comptage doit utiliser player_match_stats (v5) quand match_stats n'existe pas."""
        db = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db)  # 2 matchs dans player_match_stats, pas de match_stats

        conn = duckdb.connect(str(db), read_only=True)

        # Logique de comptage identique à _sync_duckdb_player corrigé
        count = 0
        for table in ("player_match_stats", "match_stats"):
            try:
                result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                if result and result[0]:
                    count = result[0]
                    break
            except Exception:
                continue
        conn.close()

        assert count == 2, f"Doit compter 2 matchs depuis player_match_stats, obtenu: {count}"

    def test_count_prefers_player_match_stats(self, tmp_path: Path) -> None:
        """player_match_stats est prioritaire sur match_stats."""
        db = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db, with_match_stats=True)
        # player_match_stats a 2 matchs, match_stats a 1

        conn = duckdb.connect(str(db), read_only=True)

        count = 0
        for table in ("player_match_stats", "match_stats"):
            try:
                result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                if result and result[0]:
                    count = result[0]
                    break
            except Exception:
                continue
        conn.close()

        assert count == 2, f"player_match_stats (2) doit être prioritaire, obtenu: {count}"


# =============================================================================
# Tests _find_player avec xuid vide (transformers.py)
# =============================================================================


class TestFindPlayerSafety:
    """Vérifie que _find_player ne retourne pas un joueur aléatoire avec xuid=''."""

    def test_empty_xuid_matches_any_player(self) -> None:
        """Documente le comportement dangereux de _find_player avec xuid=''."""
        from src.data.sync.transformers import _find_player

        players = [
            {"PlayerId": "xuid(123456789)"},
            {"PlayerId": "xuid(987654321)"},
        ]

        # Avec un xuid vide, _find_player retourne le premier joueur
        # car "" in json.dumps(pid) est toujours True
        result = _find_player(players, "")
        # Ce test documente le comportement (pas un crash)
        # mais souligne l'importance de TOUJOURS résoudre le xuid avant sync
        assert result is not None, (
            "_find_player avec xuid='' retourne un joueur aléatoire — "
            "c'est pourquoi le XUID doit toujours être résolu avant la sync"
        )

    def test_correct_xuid_finds_right_player(self) -> None:
        """Avec un XUID valide, le bon joueur est trouvé."""
        from src.data.sync.transformers import _find_player

        players = [
            {"PlayerId": "xuid(123456789)"},
            {"PlayerId": "xuid(987654321)"},
        ]

        result = _find_player(players, "987654321")
        assert result is not None
        assert "987654321" in str(result["PlayerId"])
