"""Tests anti-régression : résolution XUID et chargement des matchs.

Ces tests couvrent le flux critique que AUCUN test existant ne testait :

    db_path → _resolve_player_xuid(db_path) → xuid
    → DuckDBRepository(db_path, xuid) → load_matches() → DataFrame non vide

C'est exactement le chemin emprunté par l'application réelle via load_df_optimized().
L'absence de ces tests a permis la régression « 0 matchs pour tous les joueurs »
(sync_meta sans XUID → xuid="" → JOIN WHERE xuid='' → 0 résultats).

Sprint anti-régression — février 2026.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl

from src.data.repositories.duckdb_repo import DuckDBRepository

# =============================================================================
# Constantes
# =============================================================================

PLAYER_XUID = "2533274833178266"
PLAYER_GAMERTAG = "TestPlayer"
MATCH_ID_1 = "aaaa-1111-bbbb-2222"
MATCH_ID_2 = "cccc-3333-dddd-4444"
MATCH_ID_3 = "eeee-5555-ffff-6666"


# =============================================================================
# Helpers de création de BD
# =============================================================================


def _create_shared_db(db_path: Path) -> None:
    """Crée une shared_matches.duckdb minimale pour les tests."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

    conn.execute("""
        CREATE TABLE match_registry (
            match_id VARCHAR PRIMARY KEY,
            start_time TIMESTAMP NOT NULL,
            duration_seconds INTEGER,
            map_id VARCHAR,
            map_name VARCHAR,
            playlist_id VARCHAR,
            playlist_name VARCHAR,
            pair_id VARCHAR,
            pair_name VARCHAR,
            game_variant_id VARCHAR,
            game_variant_name VARCHAR,
            team_0_score INTEGER,
            team_1_score INTEGER,
            is_firefight BOOLEAN DEFAULT FALSE,
            is_ranked BOOLEAN DEFAULT FALSE
        )
    """)
    conn.execute("""
        CREATE TABLE match_participants (
            match_id VARCHAR,
            xuid VARCHAR,
            team_id INTEGER,
            outcome INTEGER,
            kills INTEGER,
            deaths INTEGER,
            assists INTEGER,
            score INTEGER,
            shots_fired INTEGER DEFAULT 0,
            shots_hit INTEGER DEFAULT 0,
            PRIMARY KEY (match_id, xuid)
        )
    """)
    conn.execute("""
        CREATE TABLE xuid_aliases (
            xuid VARCHAR,
            gamertag VARCHAR
        )
    """)

    # 3 matchs dans le registre
    for i, (mid, ts) in enumerate(
        [
            (MATCH_ID_1, "2025-06-01 10:00:00"),
            (MATCH_ID_2, "2025-06-01 11:00:00"),
            (MATCH_ID_3, "2025-06-01 12:00:00"),
        ]
    ):
        conn.execute(
            "INSERT INTO match_registry VALUES (?, ?, 600, 'map1', 'Aquarius', "
            "'pl1', 'Ranked', 'pair1', 'Slayer', 'gv1', 'Slayer', 50, 48, FALSE, TRUE)",
            [mid, ts],
        )
        conn.execute(
            "INSERT INTO match_participants VALUES (?, ?, 0, 2, ?, ?, 3, 2000, 100, 55)",
            [mid, PLAYER_XUID, 10 + i, 5 + i],
        )

    # Alias joueur
    conn.execute(
        "INSERT INTO xuid_aliases VALUES (?, ?)",
        [PLAYER_XUID, PLAYER_GAMERTAG],
    )

    conn.close()


def _create_player_db(
    db_path: Path,
    *,
    with_sync_meta_xuid: bool = False,
    with_player_match_stats: bool = False,
    with_xuid_aliases: bool = False,
    with_match_stats: bool = False,
) -> None:
    """Crée un stats.duckdb joueur avec différents niveaux de données.

    Les flags contrôlent quelles sources de résolution XUID sont présentes,
    permettant de tester chaque stratégie de fallback isolément.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))

    # sync_meta (toujours créée, mais XUID optionnel)
    conn.execute("""
        CREATE TABLE sync_meta (
            key VARCHAR PRIMARY KEY,
            value VARCHAR
        )
    """)
    conn.execute("INSERT INTO sync_meta VALUES ('db_version', '5')")

    if with_sync_meta_xuid:
        conn.execute("INSERT INTO sync_meta VALUES ('xuid', ?)", [PLAYER_XUID])

    # player_match_enrichment (toujours créée, peut être vide)
    conn.execute("""
        CREATE TABLE player_match_enrichment (
            match_id VARCHAR PRIMARY KEY,
            performance_score FLOAT,
            session_id VARCHAR,
            session_label VARCHAR,
            is_with_friends BOOLEAN,
            teammates_signature VARCHAR,
            known_teammates_count SMALLINT,
            friends_xuids VARCHAR,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)

    # player_match_stats (legacy v3 — contient le XUID)
    if with_player_match_stats:
        conn.execute("""
            CREATE TABLE player_match_stats (
                match_id VARCHAR,
                xuid VARCHAR,
                team_id TINYINT,
                team_mmr FLOAT,
                enemy_mmr FLOAT,
                kills_expected FLOAT,
                kills_stddev FLOAT,
                deaths_expected FLOAT,
                deaths_stddev FLOAT,
                assists_expected FLOAT,
                assists_stddev FLOAT,
                created_at TIMESTAMP
            )
        """)
        for mid in [MATCH_ID_1, MATCH_ID_2, MATCH_ID_3]:
            conn.execute(
                "INSERT INTO player_match_stats VALUES (?, ?, 0, 1500.0, 1480.0, "
                "10.0, 3.0, 8.0, 2.5, 4.0, 1.0, CURRENT_TIMESTAMP)",
                [mid, PLAYER_XUID],
            )

    # xuid_aliases locale
    if with_xuid_aliases:
        conn.execute("""
            CREATE TABLE xuid_aliases (
                xuid VARCHAR,
                gamertag VARCHAR
            )
        """)
        conn.execute(
            "INSERT INTO xuid_aliases VALUES (?, ?)",
            [PLAYER_XUID, PLAYER_GAMERTAG],
        )

    # match_stats (v4 — table locale avec données complètes)
    if with_match_stats:
        conn.execute("""
            CREATE TABLE match_stats (
                match_id VARCHAR PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                map_id VARCHAR,
                map_name VARCHAR,
                playlist_id VARCHAR,
                playlist_name VARCHAR,
                pair_id VARCHAR,
                pair_name VARCHAR,
                game_variant_id VARCHAR,
                game_variant_name VARCHAR,
                outcome INTEGER,
                team_id INTEGER,
                kda FLOAT,
                max_killing_spree INTEGER,
                headshot_kills INTEGER,
                avg_life_seconds FLOAT,
                time_played_seconds INTEGER,
                kills INTEGER,
                deaths INTEGER,
                assists INTEGER,
                accuracy FLOAT,
                my_team_score INTEGER,
                enemy_team_score INTEGER,
                team_mmr FLOAT,
                enemy_mmr FLOAT,
                personal_score INTEGER,
                is_firefight BOOLEAN DEFAULT FALSE,
                is_ranked BOOLEAN DEFAULT FALSE
            )
        """)
        for i, (mid, ts) in enumerate(
            [
                (MATCH_ID_1, "2025-06-01 10:00:00"),
                (MATCH_ID_2, "2025-06-01 11:00:00"),
                (MATCH_ID_3, "2025-06-01 12:00:00"),
            ]
        ):
            conn.execute(
                "INSERT INTO match_stats VALUES (?, ?, 'map1', 'Aquarius', 'pl1', "
                "'Ranked', 'pair1', 'Slayer', 'gv1', 'Slayer', 2, 0, 2.5, 5, 3, "
                "30.0, 600, ?, ?, 3, 55.0, 50, 48, 1500.0, 1480.0, 2000, FALSE, TRUE)",
                [mid, ts, 10 + i, 5 + i],
            )

    conn.close()


# =============================================================================
# Tests _resolve_player_xuid — LE TEST QUI MANQUAIT
# =============================================================================


class TestResolvePlayerXuid:
    """Teste les 3 stratégies de résolution XUID + le cas dégradé.

    Ce test est le gardien n°1 contre la régression « 0 matchs ».
    """

    def test_strategy_1_sync_meta(self, tmp_path: Path) -> None:
        """sync_meta.key='xuid' → retourne le XUID directement."""
        from src.ui.cache_loaders import _resolve_player_xuid

        db_path = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db_path, with_sync_meta_xuid=True)

        result = _resolve_player_xuid(str(db_path))
        assert result == PLAYER_XUID

    def test_strategy_2_player_match_stats(self, tmp_path: Path) -> None:
        """Pas de sync_meta.xuid, mais player_match_stats.xuid existe → fallback."""
        from src.ui.cache_loaders import _resolve_player_xuid

        db_path = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db_path, with_player_match_stats=True)

        result = _resolve_player_xuid(str(db_path))
        assert result == PLAYER_XUID

    def test_strategy_3_xuid_aliases(self, tmp_path: Path) -> None:
        """Ni sync_meta.xuid ni player_match_stats → fallback xuid_aliases."""
        from src.ui.cache_loaders import _resolve_player_xuid

        db_path = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db_path, with_xuid_aliases=True)

        result = _resolve_player_xuid(str(db_path))
        assert result == PLAYER_XUID

    def test_no_xuid_source_returns_empty(self, tmp_path: Path) -> None:
        """Aucune source de XUID → retourne chaîne vide."""
        from src.ui.cache_loaders import _resolve_player_xuid

        db_path = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db_path)  # Rien activé

        result = _resolve_player_xuid(str(db_path))
        assert result == ""

    def test_priority_sync_meta_over_player_match_stats(self, tmp_path: Path) -> None:
        """sync_meta a la priorité sur player_match_stats."""
        from src.ui.cache_loaders import _resolve_player_xuid

        db_path = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(
            db_path,
            with_sync_meta_xuid=True,
            with_player_match_stats=True,
        )

        # Modifier player_match_stats pour utiliser un XUID différent
        conn = duckdb.connect(str(db_path))
        conn.execute("UPDATE player_match_stats SET xuid = 'other_xuid'")
        conn.close()

        result = _resolve_player_xuid(str(db_path))
        assert result == PLAYER_XUID  # sync_meta gagne

    def test_sync_meta_empty_value_falls_through(self, tmp_path: Path) -> None:
        """sync_meta.key='xuid' existe mais valeur vide → tombe dans le fallback."""
        from src.ui.cache_loaders import _resolve_player_xuid

        db_path = tmp_path / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(db_path, with_player_match_stats=True)

        # Insérer un XUID vide dans sync_meta
        conn = duckdb.connect(str(db_path))
        conn.execute("INSERT INTO sync_meta VALUES ('xuid', '')")
        conn.close()

        result = _resolve_player_xuid(str(db_path))
        assert result == PLAYER_XUID  # player_match_stats prend le relai

    def test_nonexistent_db_returns_empty(self) -> None:
        """DB inexistante → retourne chaîne vide sans crash."""
        from src.ui.cache_loaders import _resolve_player_xuid

        result = _resolve_player_xuid("/nonexistent/path/stats.duckdb")
        assert result == ""


# =============================================================================
# Tests flux end-to-end : résolution XUID → DuckDBRepository → matchs
# =============================================================================


class TestEndToEndMatchLoading:
    """Teste le flux COMPLET qui traverse la couture entre les couches.

    Ce flux est celui de l'application réelle :
    _resolve_player_xuid → DuckDBRepository → load_matches → données

    Aucun test existant ne couvrait ce chemin.
    """

    def test_v5_shared_with_sync_meta_xuid(self, tmp_path: Path) -> None:
        """Architecture v5 nominale : sync_meta a le XUID, données dans shared."""
        from src.ui.cache_loaders import _resolve_player_xuid

        # Créer l'arborescence
        player_db = tmp_path / "data" / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        shared_db = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"

        _create_player_db(player_db, with_sync_meta_xuid=True)
        _create_shared_db(shared_db)

        # Résolution XUID
        xuid = _resolve_player_xuid(str(player_db))
        assert xuid == PLAYER_XUID

        # Chargement via DuckDBRepository
        repo = DuckDBRepository(
            player_db_path=str(player_db),
            xuid=xuid,
            shared_db_path=str(shared_db),
            read_only=True,
        )
        try:
            matches = repo.load_matches()
            assert len(matches) == 3, f"Attendu 3 matchs depuis shared, obtenu {len(matches)}"
            assert matches[0].kills >= 0
        finally:
            repo.close()

    def test_v5_shared_without_sync_meta_xuid(self, tmp_path: Path) -> None:
        """Régression corrigée : sync_meta sans XUID mais player_match_stats l'a."""
        from src.ui.cache_loaders import _resolve_player_xuid

        player_db = tmp_path / "data" / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        shared_db = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"

        _create_player_db(player_db, with_player_match_stats=True)
        _create_shared_db(shared_db)

        # Résolution XUID — fallback via player_match_stats
        xuid = _resolve_player_xuid(str(player_db))
        assert xuid == PLAYER_XUID, f"XUID non résolu depuis player_match_stats ! Obtenu: '{xuid}'"

        # Chargement — doit fonctionner malgré l'absence de sync_meta.xuid
        repo = DuckDBRepository(
            player_db_path=str(player_db),
            xuid=xuid,
            shared_db_path=str(shared_db),
            read_only=True,
        )
        try:
            matches = repo.load_matches()
            assert (
                len(matches) == 3
            ), f"Attendu 3 matchs (régression 0 matchs !), obtenu {len(matches)}"
        finally:
            repo.close()

    def test_v4_local_match_stats_no_shared(self, tmp_path: Path) -> None:
        """Architecture v4 pure : données locales, pas de shared_matches."""
        from src.ui.cache_loaders import _resolve_player_xuid

        player_db = tmp_path / "data" / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        # Pas de shared_db

        _create_player_db(
            player_db,
            with_player_match_stats=True,
            with_match_stats=True,
        )

        xuid = _resolve_player_xuid(str(player_db))
        assert xuid == PLAYER_XUID

        repo = DuckDBRepository(
            player_db_path=str(player_db),
            xuid=xuid,
            read_only=True,
        )
        try:
            matches = repo.load_matches()
            assert len(matches) == 3
        finally:
            repo.close()

    def test_empty_xuid_with_shared_returns_zero_matches(self, tmp_path: Path) -> None:
        """Garde-fou : XUID vide + shared DB → mode local fallback, pas de crash."""
        player_db = tmp_path / "data" / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        shared_db = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"

        _create_player_db(player_db, with_match_stats=True)
        _create_shared_db(shared_db)

        repo = DuckDBRepository(
            player_db_path=str(player_db),
            xuid="",
            shared_db_path=str(shared_db),
            read_only=True,
        )
        try:
            matches = repo.load_matches()
            # Avec XUID vide, on tombe en mode local (match_stats)
            # -> doit quand même charger les données locales
            assert len(matches) == 3
        finally:
            repo.close()

    def test_polars_loading_with_resolved_xuid(self, tmp_path: Path) -> None:
        """Chemin Polars (zero-copy) fonctionne avec XUID résolu."""
        from src.ui.cache_loaders import _resolve_player_xuid

        player_db = tmp_path / "data" / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        shared_db = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"

        _create_player_db(player_db, with_player_match_stats=True)
        _create_shared_db(shared_db)

        xuid = _resolve_player_xuid(str(player_db))

        repo = DuckDBRepository(
            player_db_path=str(player_db),
            xuid=xuid,
            shared_db_path=str(shared_db),
            read_only=True,
        )
        try:
            df = repo.load_matches_as_polars()
            assert isinstance(df, pl.DataFrame)
            assert df.shape[0] == 3, f"Attendu 3 matchs Polars, obtenu {df.shape[0]}"
        finally:
            repo.close()


# =============================================================================
# Tests de non-régression spécifiques au bug « 0 matchs »
# =============================================================================


class TestZeroMatchesRegression:
    """Tests ciblés sur le scénario exact de la régression.

    Scénario réel :
    - shared_matches.duckdb existe et contient des données
    - sync_meta n'a PAS de ligne xuid (ou valeur NULL/vide)
    - player_match_stats a le XUID dans sa colonne xuid
    → Avant le fix : xuid="" → JOIN WHERE xuid='' → 0 matchs
    → Après le fix : fallback → xuid résolu → matchs chargés
    """

    def test_exact_regression_scenario(self, tmp_path: Path) -> None:
        """Reproduit EXACTEMENT le bug signalé par l'utilisateur."""
        from src.ui.cache_loaders import _resolve_player_xuid

        # Structure identique aux vraies DBs de l'utilisateur
        player_db = tmp_path / "data" / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        shared_db = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"

        # sync_meta sans xuid + player_match_stats avec xuid
        _create_player_db(player_db, with_player_match_stats=True)
        _create_shared_db(shared_db)

        # Vérifier que sync_meta n'a PAS de xuid (pré-condition)
        conn = duckdb.connect(str(player_db), read_only=True)
        xuid_row = conn.execute("SELECT value FROM sync_meta WHERE key = 'xuid'").fetchone()
        conn.close()
        assert xuid_row is None, "Pré-condition violée : sync_meta a un xuid"

        # Le flux qui cassait AVANT le fix
        xuid = _resolve_player_xuid(str(player_db))
        assert xuid != "", "RÉGRESSION DÉTECTÉE : XUID non résolu !"

        repo = DuckDBRepository(
            player_db_path=str(player_db),
            xuid=xuid,
            shared_db_path=str(shared_db),
            read_only=True,
        )
        try:
            matches = repo.load_matches()
            assert len(matches) > 0, (
                "RÉGRESSION DÉTECTÉE : 0 matchs chargés ! "
                "Le bug 'sync_meta sans xuid → 0 matchs' est de retour."
            )
        finally:
            repo.close()

    def test_sync_meta_null_xuid_scenario(self, tmp_path: Path) -> None:
        """sync_meta contient xuid=NULL (variante possible du bug)."""
        from src.ui.cache_loaders import _resolve_player_xuid

        player_db = tmp_path / "data" / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        shared_db = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"

        _create_player_db(player_db, with_player_match_stats=True)
        _create_shared_db(shared_db)

        # Insérer un xuid NULL dans sync_meta
        conn = duckdb.connect(str(player_db))
        conn.execute("INSERT INTO sync_meta VALUES ('xuid', NULL)")
        conn.close()

        xuid = _resolve_player_xuid(str(player_db))
        assert xuid == PLAYER_XUID, f"XUID NULL dans sync_meta non géré, obtenu: '{xuid}'"

        repo = DuckDBRepository(
            player_db_path=str(player_db),
            xuid=xuid,
            shared_db_path=str(shared_db),
            read_only=True,
        )
        try:
            matches = repo.load_matches()
            assert len(matches) > 0
        finally:
            repo.close()

    def test_player_match_enrichment_empty_but_shared_has_data(self, tmp_path: Path) -> None:
        """Cas XxDaemonGamerxX : enrichment=0 mais shared a des données."""
        from src.ui.cache_loaders import _resolve_player_xuid

        player_db = tmp_path / "data" / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        shared_db = tmp_path / "data" / "warehouse" / "shared_matches.duckdb"

        # player_match_enrichment vide (créée par _create_player_db mais sans insert)
        # player_match_stats a le XUID
        _create_player_db(player_db, with_player_match_stats=True)
        _create_shared_db(shared_db)

        # Vérifier pré-condition : enrichment vide
        conn = duckdb.connect(str(player_db), read_only=True)
        count = conn.execute("SELECT COUNT(*) FROM player_match_enrichment").fetchone()[0]
        conn.close()
        assert count == 0, "Pré-condition violée : enrichment non vide"

        xuid = _resolve_player_xuid(str(player_db))
        assert xuid == PLAYER_XUID

        repo = DuckDBRepository(
            player_db_path=str(player_db),
            xuid=xuid,
            shared_db_path=str(shared_db),
            read_only=True,
        )
        try:
            matches = repo.load_matches()
            assert len(matches) == 3, (
                f"Cas XxDaemonGamerxX : enrichment vide mais shared a 3 matchs, "
                f"obtenu {len(matches)}"
            )
        finally:
            repo.close()


# =============================================================================
# Tests du fallback _get_match_table_name (v4 → v3)
# =============================================================================


class TestGetMatchTableName:
    """Teste la détection de la table de matchs locale."""

    def test_match_stats_preferred(self, tmp_path: Path) -> None:
        """match_stats (v4) est préféré à player_match_stats (v3)."""
        player_db = tmp_path / "data" / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(
            player_db,
            with_match_stats=True,
            with_player_match_stats=True,
        )

        repo = DuckDBRepository(
            player_db_path=str(player_db),
            xuid="",
            read_only=True,
        )
        conn = repo._get_connection()
        table = repo._get_match_table_name(conn)
        repo.close()

        assert table == "match_stats"

    def test_fallback_to_player_match_stats(self, tmp_path: Path) -> None:
        """Sans match_stats, fallback sur player_match_stats (v3)."""
        player_db = tmp_path / "data" / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(
            player_db,
            with_player_match_stats=True,
        )

        repo = DuckDBRepository(
            player_db_path=str(player_db),
            xuid="",
            read_only=True,
        )
        conn = repo._get_connection()
        table = repo._get_match_table_name(conn)
        repo.close()

        assert table == "player_match_stats"

    def test_no_table_defaults_to_match_stats(self, tmp_path: Path) -> None:
        """Aucune table de matchs → retourne match_stats (défaut v4+)."""
        player_db = tmp_path / "data" / "players" / PLAYER_GAMERTAG / "stats.duckdb"
        _create_player_db(player_db)

        repo = DuckDBRepository(
            player_db_path=str(player_db),
            xuid="",
            read_only=True,
        )
        conn = repo._get_connection()
        table = repo._get_match_table_name(conn)
        repo.close()

        assert table == "match_stats"
